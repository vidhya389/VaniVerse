"""
OpenWeather API client for fetching weather data.

Provides current conditions and 6-hour forecast with caching and retry logic.
"""

import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import requests
from src.config import Config
from src.models.context_data import WeatherData, CurrentWeather, Forecast6h


# In-memory cache for weather data (30-minute TTL)
_weather_cache: Dict[str, tuple[WeatherData, datetime]] = {}
CACHE_TTL_MINUTES = 30


def _get_cache_key(latitude: float, longitude: float) -> str:
    """Generate cache key from GPS coordinates (rounded to 2 decimal places)."""
    return f"{round(latitude, 2)},{round(longitude, 2)}"


def _is_cache_valid(cached_time: datetime) -> bool:
    """Check if cached data is still valid (within 30 minutes)."""
    age = datetime.utcnow() - cached_time
    return age < timedelta(minutes=CACHE_TTL_MINUTES)


def _retry_with_backoff(func, max_attempts: int = 3, base_delay: float = 1.0):
    """
    Retry function with exponential backoff.
    
    Args:
        func: Function to retry
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds (doubles each retry)
    
    Returns:
        Function result
    
    Raises:
        Last exception if all retries fail
    """
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempt)  # 1s, 2s, 4s
            time.sleep(delay)


def fetch_weather(latitude: float, longitude: float, force_refresh: bool = False) -> WeatherData:
    """
    Fetch current weather and 6-hour forecast from OpenWeather API.
    
    Implements 30-minute caching and retry logic with exponential backoff.
    
    Args:
        latitude: GPS latitude in decimal degrees
        longitude: GPS longitude in decimal degrees
        force_refresh: If True, bypass cache and fetch fresh data
    
    Returns:
        WeatherData object with current conditions and 6-hour forecast
    
    Raises:
        ValueError: If API key is not configured
        requests.RequestException: If API call fails after retries
    
    Requirements: 3.1, 3.3
    """
    if not Config.OPENWEATHER_API_KEY:
        raise ValueError("OPENWEATHER_API_KEY not configured")
    
    # Check cache first (unless force refresh)
    cache_key = _get_cache_key(latitude, longitude)
    if not force_refresh and cache_key in _weather_cache:
        cached_data, cached_time = _weather_cache[cache_key]
        if _is_cache_valid(cached_time):
            return cached_data
    
    # Fetch fresh data with retry logic
    def _fetch():
        return _fetch_weather_from_api(latitude, longitude)
    
    weather_data = _retry_with_backoff(_fetch, max_attempts=3, base_delay=1.0)
    
    # Update cache
    _weather_cache[cache_key] = (weather_data, datetime.utcnow())
    
    return weather_data


def _fetch_weather_from_api(latitude: float, longitude: float) -> WeatherData:
    """
    Internal function to fetch weather data from OpenWeather API.
    
    Args:
        latitude: GPS latitude
        longitude: GPS longitude
    
    Returns:
        WeatherData object
    
    Raises:
        requests.RequestException: If API call fails
    """
    api_key = Config.OPENWEATHER_API_KEY
    
    # Fetch current weather
    current_url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?lat={latitude}&lon={longitude}&appid={api_key}&units=metric"
    )
    current_response = requests.get(current_url, timeout=10)
    current_response.raise_for_status()
    current_data = current_response.json()
    
    # Fetch 6-hour forecast (2 data points at 3-hour intervals)
    forecast_url = (
        f"https://api.openweathermap.org/data/2.5/forecast"
        f"?lat={latitude}&lon={longitude}&appid={api_key}&units=metric&cnt=2"
    )
    forecast_response = requests.get(forecast_url, timeout=10)
    forecast_response.raise_for_status()
    forecast_data = forecast_response.json()
    
    # Parse current weather
    current_weather = CurrentWeather(
        temperature=current_data['main']['temp'],
        humidity=current_data['main']['humidity'],
        windSpeed=current_data['wind']['speed'] * 3.6,  # m/s to km/h
        precipitation=current_data.get('rain', {}).get('1h', 0.0)
    )
    
    # Parse 6-hour forecast (use second data point for 6-hour ahead)
    forecast_item = forecast_data['list'][1] if len(forecast_data['list']) > 1 else forecast_data['list'][0]
    forecast_6h = Forecast6h(
        precipitationProbability=forecast_item.get('pop', 0.0) * 100,  # Convert to percentage
        expectedRainfall=forecast_item.get('rain', {}).get('3h', 0.0),
        temperature=forecast_item['main']['temp'],
        windSpeed=forecast_item['wind']['speed'] * 3.6  # m/s to km/h
    )
    
    return WeatherData(
        current=current_weather,
        forecast6h=forecast_6h,
        timestamp=datetime.utcnow().isoformat()
    )


def is_weather_data_fresh(weather_data: WeatherData) -> bool:
    """
    Check if weather data is fresh (less than 30 minutes old).
    
    Args:
        weather_data: WeatherData object to check
    
    Returns:
        True if data is fresh (≤30 minutes old), False otherwise
    
    Requirements: 3.3
    """
    try:
        timestamp = datetime.fromisoformat(weather_data.timestamp.replace('Z', '+00:00'))
        age = datetime.utcnow() - timestamp.replace(tzinfo=None)
        return age <= timedelta(minutes=CACHE_TTL_MINUTES)
    except (ValueError, AttributeError):
        # If timestamp is invalid or missing, consider data stale
        return False


def clear_weather_cache():
    """Clear the weather cache. Useful for testing."""
    global _weather_cache
    _weather_cache.clear()
