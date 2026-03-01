"""
Parallel context retrieval orchestrator.

Fetches weather, land records, and memory simultaneously to minimize latency.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from src.config import Config
from src.models.context_data import ContextData, WeatherData, LandRecords, MemoryContext
from src.context.weather import fetch_weather
from src.context.ufsi import fetch_land_records
from src.context.mock_ufsi import fetch_mock_land_records
from src.context.memory import fetch_memory
from src.utils.graceful_degradation import (
    handle_weather_api_failure,
    handle_ufsi_api_failure,
    handle_memory_api_failure
)


def fetch_context_parallel(
    farmer_id: str,
    latitude: float,
    longitude: float,
    agristack_id: Optional[str] = None
) -> ContextData:
    """
    Fetch all context data in parallel for minimal latency.
    
    Executes weather, land records, and memory retrieval simultaneously
    using ThreadPoolExecutor.
    
    Args:
        farmer_id: Unique farmer identifier
        latitude: GPS latitude
        longitude: GPS longitude
        agristack_id: Optional AgriStack ID for land records
    
    Returns:
        ContextData with weather, land records (if available), and memory
    
    Requirements: 11.2
    """
    weather_data: Optional[WeatherData] = None
    land_records: Optional[LandRecords] = None
    memory_context: MemoryContext = MemoryContext()
    
    # Execute all fetches in parallel
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all tasks
        weather_future = executor.submit(fetch_weather, latitude, longitude)
        
        # Land records fetch (use mock or real UFSI based on config)
        if agristack_id:
            if Config.USE_MOCK_UFSI:
                land_future = executor.submit(fetch_mock_land_records, farmer_id, agristack_id)
            else:
                land_future = executor.submit(fetch_land_records, farmer_id, agristack_id)
        else:
            land_future = None
        
        memory_future = executor.submit(fetch_memory, farmer_id)
        
        # Collect results as they complete
        futures = {
            'weather': weather_future,
            'land': land_future,
            'memory': memory_future
        }
        
        for future_name, future in futures.items():
            if future is None:
                continue
            
            try:
                if future_name == 'weather':
                    weather_data = future.result(timeout=10)
                elif future_name == 'land':
                    land_records = future.result(timeout=10)
                elif future_name == 'memory':
                    memory_context = future.result(timeout=10)
            except Exception as e:
                # Log error but continue with partial data (graceful degradation)
                print(f"Error fetching {future_name} context: {e}")
                
                # Use graceful degradation handlers
                if future_name == 'weather' and weather_data is None:
                    weather_data = handle_weather_api_failure(latitude, longitude)
                elif future_name == 'land' and land_records is None:
                    land_records = handle_ufsi_api_failure(farmer_id, agristack_id)
                elif future_name == 'memory' and memory_context is None:
                    memory_context = handle_memory_api_failure(farmer_id)
    
    # Ensure weather data is present (use fallback if still None)
    if weather_data is None:
        weather_data = handle_weather_api_failure(latitude, longitude)
    
    # Ensure memory context is present
    if memory_context is None:
        memory_context = handle_memory_api_failure(farmer_id)
    
    return ContextData(
        weather=weather_data,
        landRecords=land_records,
        memory=memory_context
    )
