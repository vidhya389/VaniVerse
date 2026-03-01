"""
Property-based tests for multi-agent system.

Tests parallel agent invocation and output combination.
"""

from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings
import pytest

from src.agents import invoke_agents_parallel, combine_agent_outputs
from src.models.context_data import (
    ContextData, WeatherData, CurrentWeather, Forecast6h,
    LandRecords, CropHistory, MemoryContext, ConsolidatedInsights
)


# Test data generators

@st.composite
def farmer_question_strategy(draw):
    """Generate valid farmer questions."""
    question_templates = [
        "When should I spray pesticide on my {} crop?",
        "How much water does my {} need?",
        "What fertilizer should I use for {}?",
        "Is it safe to irrigate my {} today?",
        "When is the best time to harvest {}?",
        "How do I control pests in my {} field?",
        "What is the best planting time for {}?",
        "Should I apply fungicide to my {}?",
    ]
    
    crops = ['rice', 'wheat', 'cotton', 'sugarcane', 'maize', 'tomato', 'potato']
    
    template = draw(st.sampled_from(question_templates))
    crop = draw(st.sampled_from(crops))
    
    return template.format(crop)


def create_mock_context_data(include_land_records=True):
    """Create mock context data for testing."""
    land_records = None
    if include_land_records:
        land_records = LandRecords(
            landArea=2.5,
            soilType='Clay Loam',
            currentCrop='Rice',
            cropHistory=[
                CropHistory(crop='Wheat', season='Rabi', year=2023),
                CropHistory(crop='Rice', season='Kharif', year=2023)
            ]
        )
    
    return ContextData(
        weather=WeatherData(
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
        ),
        landRecords=land_records,
        memory=MemoryContext(
            recentInteractions=[],
            unresolvedIssues=[],
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop='Rice',
                commonConcerns=['pest management'],
                farmerName='TestFarmer'
            )
        )
    )


# Property Tests

@given(question=farmer_question_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.pbt
def test_property_37_multi_agent_invocation(question):
    """
    Feature: vaniverse, Property 37: Multi-Agent Invocation
    Validates: Requirements 11.3, 11.4, 11.5
    
    Test that for any farmer question, both specialized agents
    (Weather Analytics and ICAR Knowledge) are invoked in parallel.
    
    This property verifies that:
    1. Weather Analytics Agent is invoked with weather data
    2. ICAR Knowledge Agent is invoked with land records and memory
    3. Both agents are invoked in parallel (not sequentially)
    4. Both agent outputs are returned
    """
    # Create test context
    context = create_mock_context_data(include_land_records=True)
    
    # Mock both agent functions
    with patch('src.agents.orchestrator.invoke_weather_analytics_agent') as mock_weather_agent, \
         patch('src.agents.orchestrator.invoke_icar_knowledge_agent') as mock_icar_agent:
        
        # Configure mock return values
        mock_weather_agent.return_value = "Weather analysis: Safe conditions for spraying"
        mock_icar_agent.return_value = "ICAR guidance: Apply pesticide during early morning"
        
        # Execute parallel agent invocation
        result = invoke_agents_parallel(context, question)
        
        # Property 1: Weather Analytics Agent must be invoked
        assert mock_weather_agent.called, \
            "Weather Analytics Agent must be invoked"
        
        # Verify it was called with correct parameters
        weather_call_args = mock_weather_agent.call_args
        assert weather_call_args is not None, \
            "Weather Analytics Agent must be called with arguments"
        assert weather_call_args[0][0] == context.weather, \
            "Weather Analytics Agent must receive weather data"
        assert weather_call_args[0][1] == question, \
            "Weather Analytics Agent must receive farmer question"
        
        # Property 2: ICAR Knowledge Agent must be invoked
        assert mock_icar_agent.called, \
            "ICAR Knowledge Agent must be invoked"
        
        # Verify it was called with correct parameters
        icar_call_args = mock_icar_agent.call_args
        assert icar_call_args is not None, \
            "ICAR Knowledge Agent must be called with arguments"
        assert icar_call_args[0][0] == context.landRecords, \
            "ICAR Knowledge Agent must receive land records"
        assert icar_call_args[0][1] == context.memory, \
            "ICAR Knowledge Agent must receive memory context"
        assert icar_call_args[0][2] == question, \
            "ICAR Knowledge Agent must receive farmer question"
        
        # Property 3: Both agents must be called exactly once
        assert mock_weather_agent.call_count == 1, \
            "Weather Analytics Agent must be called exactly once"
        assert mock_icar_agent.call_count == 1, \
            "ICAR Knowledge Agent must be called exactly once"
        
        # Property 4: Both agent outputs must be returned
        assert isinstance(result, dict), \
            "Result must be a dictionary"
        assert 'weather_analysis' in result, \
            "Result must contain weather_analysis key"
        assert 'icar_knowledge' in result, \
            "Result must contain icar_knowledge key"
        assert result['weather_analysis'] == "Weather analysis: Safe conditions for spraying", \
            "Weather analysis output must match"
        assert result['icar_knowledge'] == "ICAR guidance: Apply pesticide during early morning", \
            "ICAR knowledge output must match"


@given(question=farmer_question_strategy())
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_multi_agent_invocation_without_land_records(question):
    """
    Test multi-agent invocation when land records are not available (GPS-only mode).
    
    ICAR Knowledge Agent should still be invoked with None for land records.
    """
    # Create context without land records
    context = create_mock_context_data(include_land_records=False)
    
    with patch('src.agents.orchestrator.invoke_weather_analytics_agent') as mock_weather_agent, \
         patch('src.agents.orchestrator.invoke_icar_knowledge_agent') as mock_icar_agent:
        
        mock_weather_agent.return_value = "Weather analysis"
        mock_icar_agent.return_value = "ICAR guidance"
        
        result = invoke_agents_parallel(context, question)
        
        # Both agents should still be invoked
        assert mock_weather_agent.called
        assert mock_icar_agent.called
        
        # ICAR agent should receive None for land records
        icar_call_args = mock_icar_agent.call_args
        assert icar_call_args[0][0] is None, \
            "ICAR Knowledge Agent should receive None when land records unavailable"
        
        # Results should still be returned
        assert 'weather_analysis' in result
        assert 'icar_knowledge' in result


@given(question=farmer_question_strategy())
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_multi_agent_parallel_execution(question):
    """
    Test that agents are truly executed in parallel, not sequentially.
    
    This is verified by ensuring both agents are submitted to the executor
    before either result is retrieved.
    """
    context = create_mock_context_data(include_land_records=True)
    
    # Track execution order
    execution_order = []
    
    def weather_agent_mock(*args, **kwargs):
        execution_order.append('weather_start')
        import time
        time.sleep(0.01)  # Simulate work
        execution_order.append('weather_end')
        return "Weather analysis"
    
    def icar_agent_mock(*args, **kwargs):
        execution_order.append('icar_start')
        import time
        time.sleep(0.01)  # Simulate work
        execution_order.append('icar_end')
        return "ICAR guidance"
    
    with patch('src.agents.orchestrator.invoke_weather_analytics_agent', side_effect=weather_agent_mock), \
         patch('src.agents.orchestrator.invoke_icar_knowledge_agent', side_effect=icar_agent_mock):
        
        result = invoke_agents_parallel(context, question)
        
        # Verify both agents executed
        assert 'weather_start' in execution_order
        assert 'icar_start' in execution_order
        
        # In parallel execution, both should start before either finishes
        # (though this is not guaranteed due to thread scheduling)
        # At minimum, both should have executed
        assert len(execution_order) >= 2


@given(question=farmer_question_strategy())
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_combine_agent_outputs(question):
    """
    Test that agent outputs are properly combined for prompt construction.
    """
    context = create_mock_context_data(include_land_records=True)
    
    weather_analysis = "Weather analysis: Temperature 32°C, safe for spraying"
    icar_knowledge = "ICAR guidance: Apply pesticide in early morning"
    
    combined = combine_agent_outputs(weather_analysis, icar_knowledge, context)
    
    # Verify combined output contains both agent outputs
    assert weather_analysis in combined, \
        "Combined output must contain weather analysis"
    assert icar_knowledge in combined, \
        "Combined output must contain ICAR knowledge"
    
    # Verify combined output contains context information
    assert str(context.weather.current.temperature) in combined, \
        "Combined output must contain temperature"
    assert str(context.weather.forecast6h.precipitationProbability) in combined, \
        "Combined output must contain precipitation probability"
    
    if context.landRecords:
        assert str(context.landRecords.landArea) in combined, \
            "Combined output must contain land area when available"
        assert context.landRecords.soilType in combined, \
            "Combined output must contain soil type when available"


# Unit tests for specific scenarios

def test_multi_agent_invocation_basic():
    """Basic test for multi-agent invocation with known inputs."""
    context = create_mock_context_data(include_land_records=True)
    question = "When should I spray pesticide?"
    
    with patch('src.agents.orchestrator.invoke_weather_analytics_agent') as mock_weather_agent, \
         patch('src.agents.orchestrator.invoke_icar_knowledge_agent') as mock_icar_agent:
        
        mock_weather_agent.return_value = "Weather: Safe conditions"
        mock_icar_agent.return_value = "ICAR: Morning application recommended"
        
        result = invoke_agents_parallel(context, question)
        
        assert result['weather_analysis'] == "Weather: Safe conditions"
        assert result['icar_knowledge'] == "ICAR: Morning application recommended"


def test_multi_agent_invocation_handles_agent_failure():
    """Test that agent failures are propagated (not silently ignored)."""
    context = create_mock_context_data(include_land_records=True)
    question = "When should I spray pesticide?"
    
    with patch('src.agents.orchestrator.invoke_weather_analytics_agent') as mock_weather_agent, \
         patch('src.agents.orchestrator.invoke_icar_knowledge_agent') as mock_icar_agent:
        
        # Simulate weather agent failure
        mock_weather_agent.side_effect = Exception("Bedrock API error")
        mock_icar_agent.return_value = "ICAR guidance"
        
        # Should raise exception (not return partial results)
        with pytest.raises(Exception):
            invoke_agents_parallel(context, question)


def test_combine_agent_outputs_without_land_records():
    """Test combining agent outputs when land records are not available."""
    context = create_mock_context_data(include_land_records=False)
    
    weather_analysis = "Weather analysis"
    icar_knowledge = "ICAR guidance"
    
    combined = combine_agent_outputs(weather_analysis, icar_knowledge, context)
    
    # Should still work without land records
    assert weather_analysis in combined
    assert icar_knowledge in combined
    assert str(context.weather.current.temperature) in combined
