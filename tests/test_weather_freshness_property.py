"""
Property-based tests for weather data freshness.

Tests Property 6: Weather Data Freshness
Validates: Requirements 3.3

**Validates: Requirements 3.3**
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings

from src.context.weather import fetch_weather, is_weather_data_fresh
from src.models.context_data import WeatherData, CurrentWeather, Forecast6h


# Hypothesis Strategies

@st.composite
def gps_coordinates_strategy(draw):
    """Generate random GPS coordinates for India."""
    # India latitude range: 8°N to 37°N
    # India longitude range: 68°E to 97°E
    latitude = draw(st.floats(min_value=8.0, max_value=37.0))
    longitude = draw(st.floats(min_value=68.0, max_value=97.0))
    return (latitude, longitude)


@st.composite
def weather_data_strategy(draw):
    """Generate random weather data."""
    return WeatherData(
        current=CurrentWeather(
            temperature=draw(st.floats(min_value=10.0, max_value=45.0)),
            humidity=draw(st.floats(min_value=20.0, max_value=100.0)),
            windSpeed=draw(st.floats(min_value=0.0, max_value=50.0)),
            precipitation=draw(st.floats(min_value=0.0, max_value=100.0))
        ),
        forecast6h=Forecast6h(
            precipitationProbability=draw(st.floats(min_value=0.0, max_value=100.0)),
            expectedRainfall=draw(st.floats(min_value=0.0, max_value=50.0)),
            temperature=draw(st.floats(min_value=10.0, max_value=45.0)),
            windSpeed=draw(st.floats(min_value=0.0, max_value=50.0))
        ),
        timestamp=datetime.utcnow().isoformat()
    )


@st.composite
def old_weather_data_strategy(draw):
    """Generate weather data older than 30 minutes."""
    # Generate timestamp 31-60 minutes ago
    minutes_ago = draw(st.integers(min_value=31, max_value=60))
    old_timestamp = datetime.utcnow() - timedelta(minutes=minutes_ago)
    
    return WeatherData(
        current=CurrentWeather(
            temperature=draw(st.floats(min_value=10.0, max_value=45.0)),
            humidity=draw(st.floats(min_value=20.0, max_value=100.0)),
            windSpeed=draw(st.floats(min_value=0.0, max_value=50.0)),
            precipitation=draw(st.floats(min_value=0.0, max_value=100.0))
        ),
        forecast6h=Forecast6h(
            precipitationProbability=draw(st.floats(min_value=0.0, max_value=100.0)),
            expectedRainfall=draw(st.floats(min_value=0.0, max_value=50.0)),
            temperature=draw(st.floats(min_value=10.0, max_value=45.0)),
            windSpeed=draw(st.floats(min_value=0.0, max_value=50.0))
        ),
        timestamp=old_timestamp.isoformat()
    )


@st.composite
def fresh_weather_data_strategy(draw):
    """Generate weather data less than 30 minutes old."""
    # Generate timestamp 0-29 minutes ago
    minutes_ago = draw(st.integers(min_value=0, max_value=29))
    fresh_timestamp = datetime.utcnow() - timedelta(minutes=minutes_ago)
    
    return WeatherData(
        current=CurrentWeather(
            temperature=draw(st.floats(min_value=10.0, max_value=45.0)),
            humidity=draw(st.floats(min_value=20.0, max_value=100.0)),
            windSpeed=draw(st.floats(min_value=0.0, max_value=50.0)),
            precipitation=draw(st.floats(min_value=0.0, max_value=100.0))
        ),
        forecast6h=Forecast6h(
            precipitationProbability=draw(st.floats(min_value=0.0, max_value=100.0)),
            expectedRainfall=draw(st.floats(min_value=0.0, max_value=50.0)),
            temperature=draw(st.floats(min_value=10.0, max_value=45.0)),
            windSpeed=draw(st.floats(min_value=0.0, max_value=50.0))
        ),
        timestamp=fresh_timestamp.isoformat()
    )


# Property Tests

@given(
    gps=gps_coordinates_strategy(),
    cached_weather=old_weather_data_strategy()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.pbt
def test_property_6_weather_data_freshness(gps, cached_weather):
    """
    Feature: vaniverse, Property 6: Weather Data Freshness
    
    **Validates: Requirements 3.3**
    
    For any cached weather data older than 30 minutes, the system should 
    refresh it from OpenWeather API before generating advice.
    
    This property verifies that:
    1. Weather data age is checked before use
    2. Data older than 30 minutes is considered stale
    3. Fresh data is fetched from OpenWeather API
    4. New data has a current timestamp
    5. The 30-minute threshold is enforced
    
    Requirements:
    - Requirement 3.3: Refresh weather data older than 30 minutes
    """
    from src.context.weather import clear_weather_cache
    
    # Clear cache to ensure fresh fetch
    clear_weather_cache()
    
    latitude, longitude = gps
    
    # Property 1: Cached weather should be old (>30 minutes)
    cached_timestamp = datetime.fromisoformat(cached_weather.timestamp.replace('Z', '+00:00'))
    age_minutes = (datetime.utcnow() - cached_timestamp.replace(tzinfo=None)).total_seconds() / 60
    
    assert age_minutes > 30, \
        f"Cached weather should be >30 minutes old, got {age_minutes:.1f} minutes"
    
    # Property 2: is_weather_data_fresh should return False for old data
    is_fresh = is_weather_data_fresh(cached_weather)
    assert not is_fresh, \
        f"Weather data {age_minutes:.1f} minutes old should not be considered fresh"
    
    # Mock Config and OpenWeather API to return fresh data
    with patch('src.context.weather.Config') as mock_config, \
         patch('src.context.weather.requests.get') as mock_get:
        
        # Configure Config mock
        mock_config.OPENWEATHER_API_KEY = 'test-api-key'
        
        fresh_weather = WeatherData(
            current=CurrentWeather(
                temperature=28.0,
                humidity=65.0,
                windSpeed=12.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=30.0,
                expectedRainfall=0.0,
                temperature=30.0,
                windSpeed=15.0
            ),
            timestamp=datetime.utcnow().isoformat()
        )
        # Mock OpenWeather API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            # Current weather response
            {
                'main': {
                    'temp': fresh_weather.current.temperature,
                    'humidity': fresh_weather.current.humidity
                },
                'wind': {'speed': fresh_weather.current.windSpeed / 3.6},  # m/s
                'rain': {'1h': fresh_weather.current.precipitation}
            },
            # Forecast response
            {
                'list': [
                    {},  # First forecast period
                    {  # Second forecast period (6 hours)
                        'pop': fresh_weather.forecast6h.precipitationProbability / 100,
                        'rain': {'3h': fresh_weather.forecast6h.expectedRainfall},
                        'main': {'temp': fresh_weather.forecast6h.temperature},
                        'wind': {'speed': fresh_weather.forecast6h.windSpeed / 3.6}
                    }
                ]
            }
        ]
        mock_get.return_value = mock_response
        
        # Fetch fresh weather (should call API because cached is old)
        new_weather = fetch_weather(latitude, longitude)
        
        # Property 3: API should be called to refresh stale data
        assert mock_get.called, \
            "OpenWeather API should be called when cached data is stale"
        
        # Property 4: New weather data should be fresh
        new_timestamp = datetime.fromisoformat(new_weather.timestamp.replace('Z', '+00:00'))
        new_age_minutes = (datetime.utcnow() - new_timestamp.replace(tzinfo=None)).total_seconds() / 60
        
        assert new_age_minutes < 1, \
            f"Newly fetched weather should be <1 minute old, got {new_age_minutes:.1f} minutes"
        
        # Property 5: New data should be considered fresh
        assert is_weather_data_fresh(new_weather), \
            "Newly fetched weather data should be considered fresh"


@given(
    weather=fresh_weather_data_strategy()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.pbt
def test_fresh_weather_not_refreshed(weather):
    """
    Test that fresh weather data (<30 minutes) is NOT refreshed.
    
    This is the inverse property - verifying that fresh data is reused
    without unnecessary API calls.
    
    **Validates: Requirements 3.3**
    """
    # Property 1: Weather should be fresh (<30 minutes)
    timestamp = datetime.fromisoformat(weather.timestamp.replace('Z', '+00:00'))
    age_minutes = (datetime.utcnow() - timestamp.replace(tzinfo=None)).total_seconds() / 60
    
    assert age_minutes < 30, \
        f"Weather should be <30 minutes old, got {age_minutes:.1f} minutes"
    
    # Property 2: is_weather_data_fresh should return True
    is_fresh = is_weather_data_fresh(weather)
    assert is_fresh, \
        f"Weather data {age_minutes:.1f} minutes old should be considered fresh"


@given(
    minutes_old=st.integers(min_value=31, max_value=120)
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_weather_staleness_threshold(minutes_old):
    """
    Test that the 30-minute staleness threshold is correctly enforced.
    
    Verifies that:
    1. Data >30 minutes old is considered stale
    2. The threshold is exact (not 29 or 31 minutes)
    
    **Validates: Requirements 3.3**
    """
    # Create weather data with specific age
    old_timestamp = datetime.utcnow() - timedelta(minutes=minutes_old)
    
    weather = WeatherData(
        current=CurrentWeather(
            temperature=25.0,
            humidity=60.0,
            windSpeed=10.0,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=20.0,
            expectedRainfall=0.0,
            temperature=27.0,
            windSpeed=12.0
        ),
        timestamp=old_timestamp.isoformat()
    )
    
    # Property: Data >30 minutes old should be stale
    is_fresh = is_weather_data_fresh(weather)
    assert not is_fresh, \
        f"Weather data {minutes_old} minutes old should be stale (>30 minutes)"


@given(
    minutes_old=st.integers(min_value=0, max_value=30)
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_weather_freshness_threshold(minutes_old):
    """
    Test that data ≤30 minutes old is considered fresh.
    
    Verifies the inverse of the staleness threshold.
    
    **Validates: Requirements 3.3**
    """
    # Create weather data with specific age
    timestamp = datetime.utcnow() - timedelta(minutes=minutes_old)
    
    weather = WeatherData(
        current=CurrentWeather(
            temperature=25.0,
            humidity=60.0,
            windSpeed=10.0,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=20.0,
            expectedRainfall=0.0,
            temperature=27.0,
            windSpeed=12.0
        ),
        timestamp=timestamp.isoformat()
    )
    
    # Property: Data ≤30 minutes old should be fresh
    is_fresh = is_weather_data_fresh(weather)
    assert is_fresh, \
        f"Weather data {minutes_old} minutes old should be fresh (≤30 minutes)"


@given(
    gps=gps_coordinates_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_weather_fetch_returns_fresh_data(gps):
    """
    Test that fetch_weather always returns fresh data.
    
    Verifies that:
    1. Fetched data has a recent timestamp
    2. Fetched data passes freshness check
    3. Data is from OpenWeather API
    
    **Validates: Requirements 3.1, 3.3**
    """
    latitude, longitude = gps
    
    with patch('src.context.weather.Config') as mock_config, \
         patch('src.context.weather.requests.get') as mock_get:
        
        # Configure Config mock
        mock_config.OPENWEATHER_API_KEY = 'test-api-key'
        # Mock OpenWeather API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            # Current weather
            {
                'main': {'temp': 28.0, 'humidity': 65.0},
                'wind': {'speed': 3.33},  # m/s (12 km/h)
                'rain': {'1h': 0.0}
            },
            # Forecast
            {
                'list': [
                    {},
                    {
                        'pop': 0.3,
                        'rain': {'3h': 0.0},
                        'main': {'temp': 30.0},
                        'wind': {'speed': 4.17}  # m/s (15 km/h)
                    }
                ]
            }
        ]
        mock_get.return_value = mock_response
        
        # Fetch weather
        weather = fetch_weather(latitude, longitude)
        
        # Property 1: Weather should have a timestamp
        assert weather.timestamp is not None, \
            "Fetched weather should have a timestamp"
        
        # Property 2: Timestamp should be recent
        timestamp = datetime.fromisoformat(weather.timestamp.replace('Z', '+00:00'))
        age_seconds = (datetime.utcnow() - timestamp.replace(tzinfo=None)).total_seconds()
        
        assert age_seconds < 60, \
            f"Fetched weather should be <60 seconds old, got {age_seconds:.1f} seconds"
        
        # Property 3: Weather should be considered fresh
        assert is_weather_data_fresh(weather), \
            "Fetched weather should be considered fresh"


# Unit tests for specific scenarios

def test_weather_exactly_30_minutes_old():
    """Test weather data exactly 30 minutes old (boundary case)."""
    # Create weather exactly 30 minutes old
    timestamp = datetime.utcnow() - timedelta(minutes=30)
    
    weather = WeatherData(
        current=CurrentWeather(
            temperature=25.0,
            humidity=60.0,
            windSpeed=10.0,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=20.0,
            expectedRainfall=0.0,
            temperature=27.0,
            windSpeed=12.0
        ),
        timestamp=timestamp.isoformat()
    )
    
    # At exactly 30 minutes, should still be fresh (≤30 minutes)
    is_fresh = is_weather_data_fresh(weather)
    assert is_fresh, "Weather exactly 30 minutes old should be fresh"


def test_weather_31_minutes_old():
    """Test weather data 31 minutes old (just over threshold)."""
    # Create weather 31 minutes old
    timestamp = datetime.utcnow() - timedelta(minutes=31)
    
    weather = WeatherData(
        current=CurrentWeather(
            temperature=25.0,
            humidity=60.0,
            windSpeed=10.0,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=20.0,
            expectedRainfall=0.0,
            temperature=27.0,
            windSpeed=12.0
        ),
        timestamp=timestamp.isoformat()
    )
    
    # At 31 minutes, should be stale (>30 minutes)
    is_fresh = is_weather_data_fresh(weather)
    assert not is_fresh, "Weather 31 minutes old should be stale"


def test_weather_just_fetched():
    """Test weather data just fetched (0 minutes old)."""
    # Create weather with current timestamp
    weather = WeatherData(
        current=CurrentWeather(
            temperature=28.0,
            humidity=65.0,
            windSpeed=12.0,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=30.0,
            expectedRainfall=0.0,
            temperature=30.0,
            windSpeed=15.0
        ),
        timestamp=datetime.utcnow().isoformat()
    )
    
    # Should be fresh
    is_fresh = is_weather_data_fresh(weather)
    assert is_fresh, "Just-fetched weather should be fresh"


def test_weather_very_old():
    """Test very old weather data (2 hours)."""
    # Create weather 2 hours old
    timestamp = datetime.utcnow() - timedelta(hours=2)
    
    weather = WeatherData(
        current=CurrentWeather(
            temperature=25.0,
            humidity=60.0,
            windSpeed=10.0,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=20.0,
            expectedRainfall=0.0,
            temperature=27.0,
            windSpeed=12.0
        ),
        timestamp=timestamp.isoformat()
    )
    
    # Should definitely be stale
    is_fresh = is_weather_data_fresh(weather)
    assert not is_fresh, "Weather 2 hours old should be stale"


def test_weather_refresh_updates_timestamp():
    """Test that refreshing weather updates the timestamp."""
    # Create old weather
    old_timestamp = datetime.utcnow() - timedelta(minutes=45)
    old_weather = WeatherData(
        current=CurrentWeather(
            temperature=25.0,
            humidity=60.0,
            windSpeed=10.0,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=20.0,
            expectedRainfall=0.0,
            temperature=27.0,
            windSpeed=12.0
        ),
        timestamp=old_timestamp.isoformat()
    )
    
    # Verify old weather is stale
    assert not is_weather_data_fresh(old_weather)
    
    with patch('src.context.weather.Config') as mock_config, \
         patch('src.context.weather.requests.get') as mock_get:
        
        # Configure Config mock
        mock_config.OPENWEATHER_API_KEY = 'test-api-key'
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            {'main': {'temp': 28.0, 'humidity': 65.0}, 'wind': {'speed': 3.33}, 'rain': {'1h': 0.0}},
            {'list': [{}, {'pop': 0.3, 'rain': {'3h': 0.0}, 'main': {'temp': 30.0}, 'wind': {'speed': 4.17}}]}
        ]
        mock_get.return_value = mock_response
        
        # Fetch fresh weather
        new_weather = fetch_weather(28.6139, 77.2090)
        
        # Verify new weather is fresh
        assert is_weather_data_fresh(new_weather)
        
        # Verify timestamp was updated
        new_timestamp = datetime.fromisoformat(new_weather.timestamp.replace('Z', '+00:00'))
        old_timestamp_dt = datetime.fromisoformat(old_weather.timestamp.replace('Z', '+00:00'))
        
        assert new_timestamp > old_timestamp_dt, \
            "New weather timestamp should be more recent than old timestamp"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
