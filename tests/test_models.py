"""
Property-based tests for data models.

Tests serialization/deserialization round-trip for all data models.
"""

import json
from datetime import datetime, timedelta
from hypothesis import given, strategies as st
import pytest

from src.models import (
    FarmerSession,
    GPSCoordinates,
    AudioRequest,
    ContextData,
    WeatherData,
    CurrentWeather,
    Forecast6h,
    LandRecords,
    CropHistory,
    MemoryContext,
    Interaction,
    UnresolvedIssue,
    ConsolidatedInsights
)


# Custom strategies for generating valid test data
@st.composite
def gps_coordinates_strategy(draw):
    """Generate valid GPS coordinates."""
    return GPSCoordinates(
        latitude=draw(st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False)),
        longitude=draw(st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False))
    )


@st.composite
def farmer_session_strategy(draw):
    """Generate valid FarmerSession instances."""
    supported_languages = ['hi-IN', 'ta-IN', 'te-IN', 'kn-IN', 'mr-IN', 'bn-IN', 'gu-IN', 'pa-IN']
    
    return FarmerSession(
        farmerId=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'))),
        agriStackId=draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
        sessionId=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'))),
        language=draw(st.sampled_from(supported_languages)),
        gpsCoordinates=draw(gps_coordinates_strategy()),
        timestamp=datetime.utcnow().isoformat()
    )


@st.composite
def audio_request_strategy(draw):
    """Generate valid AudioRequest instances."""
    return AudioRequest(
        audioFileKey=draw(st.text(min_size=1, max_size=200)),
        farmerId=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'))),
        sessionId=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'))),
        gpsCoordinates=draw(gps_coordinates_strategy()),
        timestamp=datetime.utcnow().isoformat()
    )


@st.composite
def current_weather_strategy(draw):
    """Generate valid CurrentWeather instances."""
    return CurrentWeather(
        temperature=draw(st.floats(min_value=-50, max_value=60, allow_nan=False, allow_infinity=False)),
        humidity=draw(st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False)),
        windSpeed=draw(st.floats(min_value=0, max_value=200, allow_nan=False, allow_infinity=False)),
        precipitation=draw(st.floats(min_value=0, max_value=500, allow_nan=False, allow_infinity=False))
    )


@st.composite
def forecast_6h_strategy(draw):
    """Generate valid Forecast6h instances."""
    return Forecast6h(
        precipitationProbability=draw(st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False)),
        expectedRainfall=draw(st.floats(min_value=0, max_value=500, allow_nan=False, allow_infinity=False)),
        temperature=draw(st.floats(min_value=-50, max_value=60, allow_nan=False, allow_infinity=False)),
        windSpeed=draw(st.floats(min_value=0, max_value=200, allow_nan=False, allow_infinity=False))
    )


@st.composite
def weather_data_strategy(draw):
    """Generate valid WeatherData instances."""
    return WeatherData(
        current=draw(current_weather_strategy()),
        forecast6h=draw(forecast_6h_strategy()),
        timestamp=datetime.utcnow().isoformat()
    )


@st.composite
def crop_history_strategy(draw):
    """Generate valid CropHistory instances."""
    return CropHistory(
        crop=draw(st.text(min_size=1, max_size=50)),
        season=draw(st.sampled_from(['Kharif', 'Rabi', 'Zaid'])),
        year=draw(st.integers(min_value=2000, max_value=2100))
    )


@st.composite
def land_records_strategy(draw):
    """Generate valid LandRecords instances."""
    return LandRecords(
        landArea=draw(st.floats(min_value=0.1, max_value=1000, allow_nan=False, allow_infinity=False)),
        soilType=draw(st.text(min_size=1, max_size=50)),
        currentCrop=draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
        cropHistory=draw(st.lists(crop_history_strategy(), max_size=10))
    )


@st.composite
def interaction_strategy(draw):
    """Generate valid Interaction instances."""
    return Interaction(
        question=draw(st.text(min_size=1, max_size=500)),
        advice=draw(st.text(min_size=1, max_size=1000)),
        timestamp=datetime.utcnow().isoformat()
    )


@st.composite
def unresolved_issue_strategy(draw):
    """Generate valid UnresolvedIssue instances."""
    days_since = draw(st.integers(min_value=0, max_value=365))
    reported_date = (datetime.utcnow() - timedelta(days=days_since)).isoformat()
    
    return UnresolvedIssue(
        issue=draw(st.text(min_size=1, max_size=200)),
        crop=draw(st.text(min_size=1, max_size=50)),
        reportedDate=reported_date,
        daysSinceReport=days_since
    )


@st.composite
def consolidated_insights_strategy(draw):
    """Generate valid ConsolidatedInsights instances."""
    return ConsolidatedInsights(
        primaryCrop=draw(st.text(min_size=1, max_size=50)),
        commonConcerns=draw(st.lists(st.text(min_size=1, max_size=100), max_size=10)),
        farmerName=draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    )


@st.composite
def memory_context_strategy(draw):
    """Generate valid MemoryContext instances."""
    return MemoryContext(
        recentInteractions=draw(st.lists(interaction_strategy(), max_size=10)),
        unresolvedIssues=draw(st.lists(unresolved_issue_strategy(), max_size=5)),
        consolidatedInsights=draw(consolidated_insights_strategy())
    )


@st.composite
def context_data_strategy(draw):
    """Generate valid ContextData instances."""
    return ContextData(
        weather=draw(weather_data_strategy()),
        landRecords=draw(st.one_of(st.none(), land_records_strategy())),
        memory=draw(memory_context_strategy())
    )


# Property Tests

@given(gps=gps_coordinates_strategy())
@pytest.mark.pbt
def test_gps_coordinates_serialization_round_trip(gps):
    """
    Feature: vaniverse, Property: Serialization round trip
    Validates: Requirements 2.3, 11.7
    
    Test that GPSCoordinates can be serialized to JSON and deserialized back
    to an equivalent object.
    """
    # Serialize to JSON
    json_str = gps.model_dump_json()
    json_dict = json.loads(json_str)
    
    # Deserialize back
    deserialized = GPSCoordinates(**json_dict)
    
    # Verify equivalence
    assert deserialized.latitude == gps.latitude
    assert deserialized.longitude == gps.longitude
    assert deserialized == gps


@given(session=farmer_session_strategy())
@pytest.mark.pbt
def test_farmer_session_serialization_round_trip(session):
    """
    Feature: vaniverse, Property: Serialization round trip
    Validates: Requirements 2.3, 11.7
    
    Test that FarmerSession can be serialized to JSON and deserialized back
    to an equivalent object.
    """
    # Serialize to JSON
    json_str = session.model_dump_json()
    json_dict = json.loads(json_str)
    
    # Deserialize back
    deserialized = FarmerSession(**json_dict)
    
    # Verify equivalence
    assert deserialized.farmerId == session.farmerId
    assert deserialized.agriStackId == session.agriStackId
    assert deserialized.sessionId == session.sessionId
    assert deserialized.language == session.language
    assert deserialized.gpsCoordinates == session.gpsCoordinates
    assert deserialized == session


@given(request=audio_request_strategy())
@pytest.mark.pbt
def test_audio_request_serialization_round_trip(request):
    """
    Feature: vaniverse, Property: Serialization round trip
    Validates: Requirements 2.3, 11.7
    
    Test that AudioRequest can be serialized to JSON and deserialized back
    to an equivalent object.
    """
    # Serialize to JSON
    json_str = request.model_dump_json()
    json_dict = json.loads(json_str)
    
    # Deserialize back
    deserialized = AudioRequest(**json_dict)
    
    # Verify equivalence
    assert deserialized.audioFileKey == request.audioFileKey
    assert deserialized.farmerId == request.farmerId
    assert deserialized.sessionId == request.sessionId
    assert deserialized.gpsCoordinates == request.gpsCoordinates
    assert deserialized == request


@given(weather=weather_data_strategy())
@pytest.mark.pbt
def test_weather_data_serialization_round_trip(weather):
    """
    Feature: vaniverse, Property: Serialization round trip
    Validates: Requirements 2.3, 11.7
    
    Test that WeatherData can be serialized to JSON and deserialized back
    to an equivalent object.
    """
    # Serialize to JSON
    json_str = weather.model_dump_json()
    json_dict = json.loads(json_str)
    
    # Deserialize back
    deserialized = WeatherData(**json_dict)
    
    # Verify equivalence
    assert deserialized.current == weather.current
    assert deserialized.forecast6h == weather.forecast6h
    assert deserialized == weather


@given(land=land_records_strategy())
@pytest.mark.pbt
def test_land_records_serialization_round_trip(land):
    """
    Feature: vaniverse, Property: Serialization round trip
    Validates: Requirements 2.3, 11.7
    
    Test that LandRecords can be serialized to JSON and deserialized back
    to an equivalent object.
    """
    # Serialize to JSON
    json_str = land.model_dump_json()
    json_dict = json.loads(json_str)
    
    # Deserialize back
    deserialized = LandRecords(**json_dict)
    
    # Verify equivalence
    assert deserialized.landArea == land.landArea
    assert deserialized.soilType == land.soilType
    assert deserialized.currentCrop == land.currentCrop
    assert len(deserialized.cropHistory) == len(land.cropHistory)
    assert deserialized == land


@given(memory=memory_context_strategy())
@pytest.mark.pbt
def test_memory_context_serialization_round_trip(memory):
    """
    Feature: vaniverse, Property: Serialization round trip
    Validates: Requirements 2.3, 11.7
    
    Test that MemoryContext can be serialized to JSON and deserialized back
    to an equivalent object.
    """
    # Serialize to JSON
    json_str = memory.model_dump_json()
    json_dict = json.loads(json_str)
    
    # Deserialize back
    deserialized = MemoryContext(**json_dict)
    
    # Verify equivalence
    assert len(deserialized.recentInteractions) == len(memory.recentInteractions)
    assert len(deserialized.unresolvedIssues) == len(memory.unresolvedIssues)
    assert deserialized.consolidatedInsights == memory.consolidatedInsights
    assert deserialized == memory


@given(context=context_data_strategy())
@pytest.mark.pbt
def test_context_data_serialization_round_trip(context):
    """
    Feature: vaniverse, Property: Serialization round trip
    Validates: Requirements 2.3, 11.7
    
    Test that ContextData can be serialized to JSON and deserialized back
    to an equivalent object.
    """
    # Serialize to JSON
    json_str = context.model_dump_json()
    json_dict = json.loads(json_str)
    
    # Deserialize back
    deserialized = ContextData(**json_dict)
    
    # Verify equivalence
    assert deserialized.weather == context.weather
    assert deserialized.landRecords == context.landRecords
    assert deserialized.memory == context.memory
    assert deserialized == context
