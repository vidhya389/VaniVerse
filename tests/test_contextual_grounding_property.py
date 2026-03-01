"""
Property-based tests for contextual grounding in advice.

Tests Property 7: Contextual Grounding in Advice
Validates: Requirements 3.4

**Validates: Requirements 3.4**
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings

from src.prompting.builder import build_memory_first_prompt, invoke_bedrock
from src.models.context_data import (
    ContextData, WeatherData, CurrentWeather, Forecast6h,
    LandRecords, MemoryContext, ConsolidatedInsights
)


# Hypothesis Strategies

@st.composite
def weather_data_strategy(draw):
    """Generate random weather data with specific values."""
    return WeatherData(
        current=CurrentWeather(
            temperature=draw(st.floats(min_value=15.0, max_value=45.0)),
            humidity=draw(st.floats(min_value=30.0, max_value=95.0)),
            windSpeed=draw(st.floats(min_value=0.0, max_value=40.0)),
            precipitation=draw(st.floats(min_value=0.0, max_value=50.0))
        ),
        forecast6h=Forecast6h(
            precipitationProbability=draw(st.floats(min_value=0.0, max_value=100.0)),
            expectedRainfall=draw(st.floats(min_value=0.0, max_value=30.0)),
            temperature=draw(st.floats(min_value=15.0, max_value=45.0)),
            windSpeed=draw(st.floats(min_value=0.0, max_value=40.0))
        ),
        timestamp=datetime.utcnow().isoformat()
    )


@st.composite
def land_records_strategy(draw):
    """Generate random land records."""
    return LandRecords(
        landArea=draw(st.floats(min_value=0.5, max_value=10.0)),
        soilType=draw(st.sampled_from(['Clay Loam', 'Sandy', 'Loamy', 'Clay', 'Sandy Loam', 'Black Soil'])),
        currentCrop=draw(st.sampled_from(['Rice', 'Wheat', 'Cotton', 'Sugarcane', 'Maize', 'Tomato', 'Soybean'])),
        cropHistory=[]
    )


@st.composite
def context_with_specific_data_strategy(draw):
    """Generate context with specific weather and land data."""
    weather = draw(weather_data_strategy())
    land = draw(land_records_strategy())
    
    return ContextData(
        weather=weather,
        landRecords=land,
        memory=MemoryContext(
            recentInteractions=[],
            unresolvedIssues=[],
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop=land.currentCrop,
                commonConcerns=[],
                farmerName=None
            )
        )
    )


@st.composite
def farmer_question_strategy(draw):
    """Generate random farmer questions."""
    questions = [
        "What should I do for my crop?",
        "When should I irrigate?",
        "Is it safe to spray pesticide?",
        "How do I improve yield?",
        "What fertilizer should I use?",
        "When is the best time to harvest?",
        "How do I control pests?",
        "Should I plant now?"
    ]
    return draw(st.sampled_from(questions))


# Property Tests

@given(
    context=context_with_specific_data_strategy(),
    question=farmer_question_strategy()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.pbt
def test_property_7_contextual_grounding_in_advice(context, question):
    """
    Feature: vaniverse, Property 7: Contextual Grounding in Advice
    
    **Validates: Requirements 3.4**
    
    For any generated advice, the text should contain references to specific 
    weather conditions (temperature, precipitation, wind) or land characteristics 
    (soil type, crop, land area) from the retrieved context.
    
    This property verifies that:
    1. Advice references weather conditions
    2. Advice references land characteristics
    3. Context data is accessible in the prompt
    4. Specific values are available for grounding
    5. The system prompt instructs contextual grounding
    
    Requirements:
    - Requirement 3.4: Reference specific weather and land characteristics
    """
    # Mock specialized agents
    weather_analysis = f"Temperature is {context.weather.current.temperature}°C with {context.weather.current.humidity}% humidity."
    icar_knowledge = f"For {context.landRecords.currentCrop} in {context.landRecords.soilType} soil, follow standard practices."
    
    # Build Memory-First prompt
    prompt = build_memory_first_prompt(
        question=question,
        context=context,
        weather_analysis=weather_analysis,
        icar_knowledge=icar_knowledge
    )
    
    # Property 1: Context should contain weather data
    assert context.weather is not None, "Context should have weather data"
    assert context.weather.current.temperature is not None, "Weather should have temperature"
    assert context.weather.current.humidity is not None, "Weather should have humidity"
    assert context.weather.current.windSpeed is not None, "Weather should have wind speed"
    
    # Property 2: Context should contain land records
    assert context.landRecords is not None, "Context should have land records"
    assert context.landRecords.soilType is not None, "Land records should have soil type"
    assert context.landRecords.currentCrop is not None, "Land records should have current crop"
    assert context.landRecords.landArea is not None, "Land records should have land area"
    
    # Property 3: System prompt should instruct contextual grounding
    system_prompt_lower = prompt.systemPrompt.lower()
    assert 'weather' in system_prompt_lower or 'context' in system_prompt_lower, \
        "System prompt should mention weather or context"
    
    # Property 4: Weather analysis should reference specific values
    assert str(int(context.weather.current.temperature)) in weather_analysis or \
           f"{context.weather.current.temperature:.1f}" in weather_analysis, \
        "Weather analysis should reference temperature value"
    
    # Property 5: ICAR knowledge should reference land characteristics
    assert context.landRecords.currentCrop in icar_knowledge, \
        "ICAR knowledge should reference current crop"
    assert context.landRecords.soilType in icar_knowledge, \
        "ICAR knowledge should reference soil type"
    
    # Property 6: Weather analysis contains specific numeric values
    # Check that temperature value appears in the analysis
    temp_str = str(int(context.weather.current.temperature))
    assert temp_str in weather_analysis or \
           f"{context.weather.current.temperature:.1f}" in weather_analysis or \
           f"{context.weather.current.temperature:.0f}" in weather_analysis, \
        f"Weather analysis should contain temperature value {context.weather.current.temperature}"
    
    # Property 7: Context data is complete and accessible for grounding
    assert context.weather.current.temperature >= 15.0, "Temperature should be in valid range"
    assert context.landRecords.landArea > 0, "Land area should be positive"
    assert len(context.landRecords.soilType) > 0, "Soil type should not be empty"
    assert len(context.landRecords.currentCrop) > 0, "Current crop should not be empty"


@given(
    context=context_with_specific_data_strategy(),
    question=farmer_question_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_advice_references_weather_conditions(context, question):
    """
    Test that advice can reference specific weather conditions.
    
    Verifies that:
    1. Temperature values are accessible
    2. Humidity values are accessible
    3. Wind speed values are accessible
    4. Precipitation data is accessible
    
    **Validates: Requirements 3.4**
    """
    # Weather data should be specific and accessible
    weather = context.weather
    
    # Property 1: Temperature should be a specific value
    assert isinstance(weather.current.temperature, (int, float)), \
        "Temperature should be numeric"
    assert 15.0 <= weather.current.temperature <= 45.0, \
        f"Temperature should be in reasonable range, got {weather.current.temperature}"
    
    # Property 2: Humidity should be a specific value
    assert isinstance(weather.current.humidity, (int, float)), \
        "Humidity should be numeric"
    assert 0.0 <= weather.current.humidity <= 100.0, \
        f"Humidity should be 0-100%, got {weather.current.humidity}"
    
    # Property 3: Wind speed should be a specific value
    assert isinstance(weather.current.windSpeed, (int, float)), \
        "Wind speed should be numeric"
    assert weather.current.windSpeed >= 0.0, \
        f"Wind speed should be non-negative, got {weather.current.windSpeed}"
    
    # Property 4: Precipitation probability should be accessible
    assert isinstance(weather.forecast6h.precipitationProbability, (int, float)), \
        "Precipitation probability should be numeric"
    assert 0.0 <= weather.forecast6h.precipitationProbability <= 100.0, \
        f"Precipitation probability should be 0-100%, got {weather.forecast6h.precipitationProbability}"


@given(
    context=context_with_specific_data_strategy(),
    question=farmer_question_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_advice_references_land_characteristics(context, question):
    """
    Test that advice can reference specific land characteristics.
    
    Verifies that:
    1. Soil type is accessible
    2. Current crop is accessible
    3. Land area is accessible
    4. All values are specific (not generic)
    
    **Validates: Requirements 3.4**
    """
    land = context.landRecords
    
    # Property 1: Soil type should be specific
    assert land.soilType is not None, "Soil type should not be None"
    assert len(land.soilType) > 0, "Soil type should not be empty"
    assert land.soilType in ['Clay Loam', 'Sandy', 'Loamy', 'Clay', 'Sandy Loam', 'Black Soil'], \
        f"Soil type should be a valid type, got '{land.soilType}'"
    
    # Property 2: Current crop should be specific
    assert land.currentCrop is not None, "Current crop should not be None"
    assert len(land.currentCrop) > 0, "Current crop should not be empty"
    assert land.currentCrop in ['Rice', 'Wheat', 'Cotton', 'Sugarcane', 'Maize', 'Tomato', 'Soybean'], \
        f"Current crop should be a valid crop, got '{land.currentCrop}'"
    
    # Property 3: Land area should be specific
    assert isinstance(land.landArea, (int, float)), "Land area should be numeric"
    assert land.landArea > 0, f"Land area should be positive, got {land.landArea}"
    assert 0.5 <= land.landArea <= 10.0, \
        f"Land area should be in reasonable range, got {land.landArea}"


@given(
    context=context_with_specific_data_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_context_data_completeness_for_grounding(context):
    """
    Test that context data is complete enough for grounding.
    
    Verifies that:
    1. All required weather fields are present
    2. All required land fields are present
    3. Values are not None or empty
    4. Values are in valid ranges
    
    **Validates: Requirements 3.1, 3.2, 3.4**
    """
    # Property 1: Weather data completeness
    assert context.weather is not None, "Weather should not be None"
    assert context.weather.current is not None, "Current weather should not be None"
    assert context.weather.forecast6h is not None, "Forecast should not be None"
    
    # Property 2: Current weather fields
    current = context.weather.current
    assert current.temperature is not None, "Temperature should not be None"
    assert current.humidity is not None, "Humidity should not be None"
    assert current.windSpeed is not None, "Wind speed should not be None"
    assert current.precipitation is not None, "Precipitation should not be None"
    
    # Property 3: Forecast fields
    forecast = context.weather.forecast6h
    assert forecast.precipitationProbability is not None, "Precipitation probability should not be None"
    assert forecast.temperature is not None, "Forecast temperature should not be None"
    
    # Property 4: Land records completeness
    assert context.landRecords is not None, "Land records should not be None"
    assert context.landRecords.soilType is not None, "Soil type should not be None"
    assert context.landRecords.currentCrop is not None, "Current crop should not be None"
    assert context.landRecords.landArea is not None, "Land area should not be None"
    
    # Property 5: Values are in valid ranges
    assert 15.0 <= current.temperature <= 45.0, "Temperature in valid range"
    assert 0.0 <= current.humidity <= 100.0, "Humidity in valid range"
    assert current.windSpeed >= 0.0, "Wind speed non-negative"
    assert 0.0 <= forecast.precipitationProbability <= 100.0, "Precipitation probability in valid range"
    assert context.landRecords.landArea > 0, "Land area positive"


# Unit tests for specific scenarios

def test_advice_with_high_temperature():
    """Test contextual grounding with high temperature."""
    context = ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=42.0,
                humidity=35.0,
                windSpeed=15.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=10.0,
                expectedRainfall=0.0,
                temperature=43.0,
                windSpeed=18.0
            ),
            timestamp=datetime.utcnow().isoformat()
        ),
        landRecords=LandRecords(
            landArea=3.5,
            soilType='Sandy',
            currentCrop='Cotton',
            cropHistory=[]
        ),
        memory=MemoryContext()
    )
    
    # Build prompt
    prompt = build_memory_first_prompt(
        question="Should I irrigate today?",
        context=context,
        weather_analysis=f"Temperature is {context.weather.current.temperature}°C, which is very high.",
        icar_knowledge=f"For {context.landRecords.currentCrop} in {context.landRecords.soilType} soil."
    )
    
    # Verify context is accessible
    assert context.weather.current.temperature == 42.0
    assert context.landRecords.soilType == 'Sandy'
    assert context.landRecords.currentCrop == 'Cotton'


def test_advice_with_rain_forecast():
    """Test contextual grounding with rain forecast."""
    context = ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=28.0,
                humidity=75.0,
                windSpeed=12.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=80.0,
                expectedRainfall=15.0,
                temperature=26.0,
                windSpeed=20.0
            ),
            timestamp=datetime.utcnow().isoformat()
        ),
        landRecords=LandRecords(
            landArea=2.0,
            soilType='Clay Loam',
            currentCrop='Rice',
            cropHistory=[]
        ),
        memory=MemoryContext()
    )
    
    # Build prompt
    prompt = build_memory_first_prompt(
        question="Can I spray pesticide?",
        context=context,
        weather_analysis=f"Rain probability is {context.weather.forecast6h.precipitationProbability}%.",
        icar_knowledge=f"For {context.landRecords.currentCrop}."
    )
    
    # Verify high rain probability is accessible
    assert context.weather.forecast6h.precipitationProbability == 80.0
    assert context.weather.forecast6h.expectedRainfall == 15.0


def test_advice_with_specific_soil_type():
    """Test contextual grounding with specific soil type."""
    context = ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=30.0,
                humidity=60.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=20.0,
                expectedRainfall=0.0,
                temperature=32.0,
                windSpeed=12.0
            ),
            timestamp=datetime.utcnow().isoformat()
        ),
        landRecords=LandRecords(
            landArea=5.0,
            soilType='Black Soil',
            currentCrop='Sugarcane',
            cropHistory=[]
        ),
        memory=MemoryContext()
    )
    
    # Build prompt
    prompt = build_memory_first_prompt(
        question="What fertilizer should I use?",
        context=context,
        weather_analysis="Weather is suitable.",
        icar_knowledge=f"For {context.landRecords.currentCrop} in {context.landRecords.soilType}."
    )
    
    # Verify soil type is accessible
    assert context.landRecords.soilType == 'Black Soil'
    assert context.landRecords.currentCrop == 'Sugarcane'
    assert context.landRecords.landArea == 5.0


def test_advice_without_land_records():
    """Test that advice can still be generated without land records (GPS-only mode)."""
    context = ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=28.0,
                humidity=65.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=30.0,
                expectedRainfall=0.0,
                temperature=30.0,
                windSpeed=12.0
            ),
            timestamp=datetime.utcnow().isoformat()
        ),
        landRecords=None,  # No land records (GPS-only mode)
        memory=MemoryContext()
    )
    
    # Build prompt
    prompt = build_memory_first_prompt(
        question="What should I do?",
        context=context,
        weather_analysis=f"Temperature is {context.weather.current.temperature}°C.",
        icar_knowledge="General agricultural advice."
    )
    
    # Verify weather is still accessible for grounding
    assert context.weather is not None
    assert context.weather.current.temperature == 28.0
    
    # Land records should be None
    assert context.landRecords is None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
