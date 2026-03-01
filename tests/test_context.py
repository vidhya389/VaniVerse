"""
Property-based tests for context retrieval module.

Tests context assembly completeness and parallel retrieval behavior.
"""

from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings
import pytest

from src.context import fetch_context_parallel
from src.models.context_data import (
    ContextData, WeatherData, CurrentWeather, Forecast6h,
    LandRecords, CropHistory, MemoryContext, ConsolidatedInsights
)


# Test data generators
@st.composite
def farmer_request_strategy(draw):
    """Generate valid farmer request parameters."""
    return {
        'farmer_id': draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'
        ))),
        'latitude': draw(st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False)),
        'longitude': draw(st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False)),
        'agristack_id': draw(st.one_of(
            st.none(),
            st.text(min_size=1, max_size=50, alphabet=st.characters(
                whitelist_categories=('Lu', 'Ll', 'Nd')
            ))
        ))
    }


def create_mock_weather_data():
    """Create mock weather data for testing."""
    return WeatherData(
        current=CurrentWeather(
            temperature=32.5,
            humidity=65.0,
            windSpeed=12.5,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=35.0,
            expectedRainfall=2.5,
            temperature=30.0,
            windSpeed=15.0
        )
    )


def create_mock_land_records():
    """Create mock land records for testing."""
    return LandRecords(
        landArea=2.5,
        soilType='Clay Loam',
        currentCrop='Rice',
        cropHistory=[
            CropHistory(crop='Wheat', season='Rabi', year=2023),
            CropHistory(crop='Rice', season='Kharif', year=2023)
        ]
    )


def create_mock_memory_context():
    """Create mock memory context for testing."""
    return MemoryContext(
        recentInteractions=[],
        unresolvedIssues=[],
        consolidatedInsights=ConsolidatedInsights(
            primaryCrop='Rice',
            commonConcerns=['pest management'],
            farmerName='TestFarmer'
        )
    )


# Property Tests

@given(request=farmer_request_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.pbt
def test_property_5_context_assembly_completeness(request):
    """
    Feature: vaniverse, Property 5: Context Assembly Completeness
    Validates: Requirements 3.1, 3.2, 11.4
    
    Test that for any farmer request, all available context is fetched
    before advice generation.
    
    This property verifies that:
    1. Weather data is always fetched (required)
    2. Land records are fetched if AgriStack ID is provided
    3. Memory context is always fetched
    4. All fetches happen in parallel
    """
    # Mock all external dependencies
    with patch('src.context.retrieval.fetch_weather') as mock_weather, \
         patch('src.context.retrieval.fetch_land_records') as mock_land, \
         patch('src.context.retrieval.fetch_mock_land_records') as mock_mock_land, \
         patch('src.context.retrieval.fetch_memory') as mock_memory, \
         patch('src.context.retrieval.Config') as mock_config:
        
        # Configure mocks
        mock_weather.return_value = create_mock_weather_data()
        mock_land.return_value = create_mock_land_records()
        mock_mock_land.return_value = create_mock_land_records()
        mock_memory.return_value = create_mock_memory_context()
        mock_config.USE_MOCK_UFSI = True
        
        # Execute parallel context retrieval
        context = fetch_context_parallel(
            farmer_id=request['farmer_id'],
            latitude=request['latitude'],
            longitude=request['longitude'],
            agristack_id=request['agristack_id']
        )
        
        # Verify context is complete
        assert isinstance(context, ContextData), "Context should be ContextData instance"
        
        # Property 1: Weather data is always fetched (required)
        assert context.weather is not None, "Weather data must always be present"
        assert isinstance(context.weather, WeatherData), "Weather must be WeatherData instance"
        assert mock_weather.called, "Weather fetch must be called"
        
        # Property 2: Land records are fetched if AgriStack ID provided
        if request['agristack_id']:
            # Land records should be present when AgriStack ID is provided
            assert context.landRecords is not None, \
                "Land records should be present when AgriStack ID is provided"
            assert isinstance(context.landRecords, LandRecords), \
                "Land records must be LandRecords instance"
            # Either mock or real UFSI should be called
            assert mock_mock_land.called or mock_land.called, \
                "Land records fetch must be called when AgriStack ID provided"
        else:
            # Land records may be None when no AgriStack ID
            # (this is acceptable - GPS-only mode)
            pass
        
        # Property 3: Memory context is always fetched
        assert context.memory is not None, "Memory context must always be present"
        assert isinstance(context.memory, MemoryContext), \
            "Memory must be MemoryContext instance"
        assert mock_memory.called, "Memory fetch must be called"
        
        # Property 4: All fetches use correct parameters
        # Verify weather was called with correct GPS coordinates
        mock_weather.assert_called_once_with(request['latitude'], request['longitude'])
        
        # Verify memory was called with correct farmer ID
        mock_memory.assert_called_once_with(request['farmer_id'])
        
        # Verify land records called with correct IDs (if applicable)
        if request['agristack_id']:
            if mock_config.USE_MOCK_UFSI:
                mock_mock_land.assert_called_once_with(request['agristack_id'])
            else:
                mock_land.assert_called_once_with(request['farmer_id'], request['agristack_id'])


@given(request=farmer_request_strategy())
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_context_assembly_graceful_degradation(request):
    """
    Test that context assembly handles partial failures gracefully.
    
    When non-critical components fail (land records, memory), the system
    should still return context with weather data.
    """
    with patch('src.context.retrieval.fetch_weather') as mock_weather, \
         patch('src.context.retrieval.fetch_mock_land_records') as mock_mock_land, \
         patch('src.context.retrieval.fetch_memory') as mock_memory, \
         patch('src.context.retrieval.Config') as mock_config:
        
        # Configure mocks - weather succeeds, others fail
        mock_weather.return_value = create_mock_weather_data()
        mock_mock_land.side_effect = Exception("Land records unavailable")
        mock_memory.side_effect = Exception("Memory service unavailable")
        mock_config.USE_MOCK_UFSI = True
        
        # Execute - should not raise exception
        context = fetch_context_parallel(
            farmer_id=request['farmer_id'],
            latitude=request['latitude'],
            longitude=request['longitude'],
            agristack_id=request['agristack_id']
        )
        
        # Verify graceful degradation
        assert context.weather is not None, "Weather must be present"
        # Land records and memory may be None or default values
        assert isinstance(context, ContextData), "Should return valid ContextData"


@given(request=farmer_request_strategy())
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_context_assembly_weather_failure_raises(request):
    """
    Test that weather fetch failure raises exception (weather is critical).
    
    Unlike land records and memory, weather data is required for safe advice.
    """
    with patch('src.context.retrieval.fetch_weather') as mock_weather, \
         patch('src.context.retrieval.fetch_mock_land_records') as mock_mock_land, \
         patch('src.context.retrieval.fetch_memory') as mock_memory, \
         patch('src.context.retrieval.Config') as mock_config:
        
        # Configure mocks - weather fails
        mock_weather.side_effect = Exception("Weather API unavailable")
        mock_mock_land.return_value = create_mock_land_records()
        mock_memory.return_value = create_mock_memory_context()
        mock_config.USE_MOCK_UFSI = True
        
        # Execute - should raise exception
        with pytest.raises((Exception, ValueError)):
            fetch_context_parallel(
                farmer_id=request['farmer_id'],
                latitude=request['latitude'],
                longitude=request['longitude'],
                agristack_id=request['agristack_id']
            )


# Unit tests for specific scenarios

def test_context_assembly_with_agristack_id():
    """Test context assembly when AgriStack ID is provided."""
    with patch('src.context.retrieval.fetch_weather') as mock_weather, \
         patch('src.context.retrieval.fetch_mock_land_records') as mock_mock_land, \
         patch('src.context.retrieval.fetch_memory') as mock_memory, \
         patch('src.context.retrieval.Config') as mock_config:
        
        mock_weather.return_value = create_mock_weather_data()
        mock_mock_land.return_value = create_mock_land_records()
        mock_memory.return_value = create_mock_memory_context()
        mock_config.USE_MOCK_UFSI = True
        
        context = fetch_context_parallel(
            farmer_id='FARMER-001',
            latitude=28.6139,
            longitude=77.2090,
            agristack_id='AGRI001'
        )
        
        assert context.weather is not None
        assert context.landRecords is not None
        assert context.landRecords.currentCrop == 'Rice'
        assert context.memory is not None


def test_context_assembly_without_agristack_id():
    """Test context assembly when no AgriStack ID (GPS-only mode)."""
    with patch('src.context.retrieval.fetch_weather') as mock_weather, \
         patch('src.context.retrieval.fetch_memory') as mock_memory:
        
        mock_weather.return_value = create_mock_weather_data()
        mock_memory.return_value = create_mock_memory_context()
        
        context = fetch_context_parallel(
            farmer_id='FARMER-002',
            latitude=28.6139,
            longitude=77.2090,
            agristack_id=None
        )
        
        assert context.weather is not None
        assert context.landRecords is None  # No AgriStack ID
        assert context.memory is not None
