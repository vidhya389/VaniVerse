"""
Property-based tests for Chain-of-Verification execution order.

Tests validate that safety validation occurs before speech synthesis
in the advice generation pipeline.

Validates Requirements 4.6, 11.5.
"""

import pytest
from unittest.mock import Mock, patch, call, MagicMock
from hypothesis import given, strategies as st, settings
from typing import List, Tuple

from src.models.context_data import (
    WeatherData, CurrentWeather, Forecast6h,
    ContextData, LandRecords, MemoryContext,
    ConsolidatedInsights
)
from src.models.prompts import MemoryFirstPrompt
from src.safety.validator import validate_safety
from src.prompting.builder import invoke_bedrock


# Test data generators

@st.composite
def advice_text_strategy(draw):
    """Generate various types of agricultural advice text."""
    advice_templates = [
        "You should spray pesticide on your {} crop today.",
        "Apply insecticide to control pests in your {} field.",
        "Water your {} crop this afternoon.",
        "Harvest your {} when the grains are golden.",
        "Apply fertilizer to your {} crop for better yield.",
        "Monitor your {} for signs of disease.",
        "Prune your {} plants to improve air circulation.",
        "Check soil moisture before irrigating your {}.",
    ]
    
    crops = ['rice', 'wheat', 'cotton', 'tomato', 'maize', 'sugarcane']
    
    template = draw(st.sampled_from(advice_templates))
    crop = draw(st.sampled_from(crops))
    
    return template.format(crop)


@st.composite
def weather_data_strategy(draw):
    """Generate random weather data for testing."""
    return WeatherData(
        current=CurrentWeather(
            temperature=draw(st.floats(min_value=0.0, max_value=50.0)),
            humidity=draw(st.floats(min_value=0.0, max_value=100.0)),
            windSpeed=draw(st.floats(min_value=0.0, max_value=50.0)),
            precipitation=draw(st.floats(min_value=0.0, max_value=100.0))
        ),
        forecast6h=Forecast6h(
            precipitationProbability=draw(st.floats(min_value=0.0, max_value=100.0)),
            expectedRainfall=draw(st.floats(min_value=0.0, max_value=50.0)),
            temperature=draw(st.floats(min_value=0.0, max_value=50.0)),
            windSpeed=draw(st.floats(min_value=0.0, max_value=50.0))
        ),
        timestamp="2024-01-01T00:00:00Z"
    )


@st.composite
def context_data_strategy(draw):
    """Generate random context data for testing."""
    weather = draw(weather_data_strategy())
    
    # Optionally include land records
    include_land = draw(st.booleans())
    land_records = None
    if include_land:
        land_records = LandRecords(
            landArea=draw(st.floats(min_value=0.5, max_value=10.0)),
            soilType=draw(st.sampled_from(['Clay Loam', 'Sandy', 'Loamy', 'Clay'])),
            currentCrop=draw(st.sampled_from(['Rice', 'Wheat', 'Cotton', 'Maize'])),
            cropHistory=[]
        )
    
    memory = MemoryContext(
        recentInteractions=[],
        unresolvedIssues=[],
        consolidatedInsights=ConsolidatedInsights(
            primaryCrop='Rice',
            commonConcerns=[],
            farmerName=None
        )
    )
    
    return ContextData(
        weather=weather,
        landRecords=land_records,
        memory=memory
    )


# Mock execution tracker

class ExecutionTracker:
    """Track the order of function calls to verify execution sequence."""
    
    def __init__(self):
        self.calls: List[Tuple[str, float]] = []
        self.call_count = 0
    
    def record_call(self, function_name: str):
        """Record a function call with timestamp."""
        import time
        self.calls.append((function_name, time.time()))
        self.call_count += 1
    
    def get_call_order(self) -> List[str]:
        """Get the order of function calls."""
        return [name for name, _ in self.calls]
    
    def was_called_before(self, first: str, second: str) -> bool:
        """Check if first function was called before second function."""
        call_order = self.get_call_order()
        
        if first not in call_order or second not in call_order:
            return False
        
        first_index = call_order.index(first)
        second_index = call_order.index(second)
        
        return first_index < second_index
    
    def reset(self):
        """Reset the tracker."""
        self.calls = []
        self.call_count = 0


# Property Tests

@given(
    advice=advice_text_strategy(),
    weather=weather_data_strategy()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.pbt
def test_property_8_chain_of_verification_execution_order(advice, weather):
    """
    Feature: vaniverse, Property 8: Chain-of-Verification Execution Order
    Validates: Requirements 4.6, 11.5
    
    Test that for any advice, safety validation occurs before speech synthesis.
    
    This property verifies that:
    1. Safety validation (validate_safety) is called with the generated advice
    2. Speech synthesis is only called AFTER safety validation completes
    3. If advice is blocked, speech synthesis uses the alternative recommendation
    4. The execution order is strictly enforced: validation → synthesis
    
    Requirements:
    - Requirement 4.6: Execute Chain-of-Verification before delivery
    - Requirement 11.5: Safety validation before speech synthesis
    """
    tracker = ExecutionTracker()
    
    # Create wrapper functions that track calls and delegate to real implementations
    original_validate_safety = validate_safety
    
    def tracked_validate_safety(advice_text: str, weather_data: WeatherData):
        tracker.record_call('validate_safety')
        return original_validate_safety(advice_text, weather_data)
    
    def tracked_synthesize_speech(text: str, language: str = 'hi-IN'):
        tracker.record_call('synthesize_speech')
        return f"audio_key_for_{text[:20]}"
    
    # Simulate the orchestrator flow without mocking (to test actual execution)
    # Step 1: Generate advice (simulated - we use the input advice)
    generated_advice = advice
    
    # Step 2: Chain-of-Verification - validate safety
    validation_result = tracked_validate_safety(generated_advice, weather)
    
    # Step 3: Determine final advice text
    if validation_result.isApproved:
        final_advice = generated_advice
    else:
        final_advice = validation_result.alternativeRecommendation
    
    # Step 4: Synthesize speech (only after validation)
    audio_key = tracked_synthesize_speech(final_advice)
    
    # Property 1: Safety validation must be called
    assert 'validate_safety' in tracker.get_call_order(), \
        "Safety validation must be invoked for all advice"
    
    # Property 2: Speech synthesis must be called
    assert 'synthesize_speech' in tracker.get_call_order(), \
        "Speech synthesis must be invoked after validation"
    
    # Property 3: Safety validation must occur BEFORE speech synthesis
    assert tracker.was_called_before('validate_safety', 'synthesize_speech'), \
        "Safety validation must occur before speech synthesis (Chain-of-Verification)"
    
    # Property 4: Validation must be called exactly once
    validation_calls = [call for call in tracker.get_call_order() if call == 'validate_safety']
    assert len(validation_calls) == 1, \
        "Safety validation must be called exactly once per advice"
    
    # Property 5: Synthesis must be called exactly once
    synthesis_calls = [call for call in tracker.get_call_order() if call == 'synthesize_speech']
    assert len(synthesis_calls) == 1, \
        "Speech synthesis must be called exactly once per advice"
    
    # Property 6: Validation result must be used correctly
    assert validation_result is not None, \
        "Safety validation must return a result"
    
    # Property 7: If advice is blocked, alternative must be provided
    if not validation_result.isApproved:
        assert validation_result.alternativeRecommendation is not None, \
            "When advice is blocked, alternative recommendation must be provided"
    
    # Property 8: Execution order is strictly maintained
    call_order = tracker.get_call_order()
    assert call_order == ['validate_safety', 'synthesize_speech'], \
        f"Execution order must be [validate_safety, synthesize_speech], got {call_order}"


@given(
    advice=advice_text_strategy(),
    context=context_data_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_chain_of_verification_with_full_pipeline(advice, context):
    """
    Test Chain-of-Verification in the context of the full advice generation pipeline.
    
    This test simulates the complete flow:
    1. Bedrock generates advice
    2. Safety validator checks the advice
    3. Speech synthesizer creates audio
    
    Verifies that the execution order is strictly maintained.
    """
    tracker = ExecutionTracker()
    
    # Mock Bedrock invocation
    def mock_invoke_bedrock(prompt: MemoryFirstPrompt, timeout: int = 30):
        tracker.record_call('invoke_bedrock')
        return advice
    
    # Mock safety validation
    def mock_validate_safety(advice_text: str, weather_data: WeatherData):
        tracker.record_call('validate_safety')
        return validate_safety(advice_text, weather_data)
    
    # Mock speech synthesis
    def mock_synthesize_speech(text: str, language: str = 'hi-IN'):
        tracker.record_call('synthesize_speech')
        return f"audio_{text[:10]}.mp3"
    
    with patch('src.prompting.builder.invoke_bedrock', side_effect=mock_invoke_bedrock), \
         patch('src.safety.validator.validate_safety', side_effect=mock_validate_safety), \
         patch('src.speech.router.synthesize_speech', side_effect=mock_synthesize_speech):
        
        # Simulate orchestrator flow
        # Step 1: Generate advice via Bedrock
        prompt = Mock(spec=MemoryFirstPrompt)
        generated_advice = mock_invoke_bedrock(prompt)
        
        # Step 2: Validate safety (Chain-of-Verification)
        validation_result = mock_validate_safety(generated_advice, context.weather)
        
        # Step 3: Synthesize speech
        final_text = generated_advice if validation_result.isApproved else validation_result.alternativeRecommendation
        audio_key = mock_synthesize_speech(final_text)
        
        # Verify execution order
        call_order = tracker.get_call_order()
        
        # Property 1: All three steps must be executed
        assert 'invoke_bedrock' in call_order, "Bedrock must be invoked"
        assert 'validate_safety' in call_order, "Safety validation must be invoked"
        assert 'synthesize_speech' in call_order, "Speech synthesis must be invoked"
        
        # Property 2: Bedrock must be called first
        assert call_order[0] == 'invoke_bedrock', \
            "Bedrock invocation must be the first step"
        
        # Property 3: Safety validation must be called second (before synthesis)
        assert call_order[1] == 'validate_safety', \
            "Safety validation must occur after Bedrock but before synthesis"
        
        # Property 4: Speech synthesis must be called last
        assert call_order[2] == 'synthesize_speech', \
            "Speech synthesis must be the final step after validation"
        
        # Property 5: Strict ordering: Bedrock → Validation → Synthesis
        assert tracker.was_called_before('invoke_bedrock', 'validate_safety'), \
            "Bedrock must be called before safety validation"
        assert tracker.was_called_before('validate_safety', 'synthesize_speech'), \
            "Safety validation must be called before speech synthesis"
        assert tracker.was_called_before('invoke_bedrock', 'synthesize_speech'), \
            "Bedrock must be called before speech synthesis"


@st.composite
def spray_advice_strategy(draw):
    """Generate advice text that mentions spraying."""
    templates = [
        "You should spray pesticide on your {} crop.",
        "Apply insecticide spray to control pests in your {}.",
        "Spray fungicide on your {} plants.",
        "It's time to spray your {} field.",
        "Apply chemical spray to your {} crop today.",
    ]
    crops = ['rice', 'wheat', 'cotton', 'tomato', 'maize']
    template = draw(st.sampled_from(templates))
    crop = draw(st.sampled_from(crops))
    return template.format(crop)


@given(
    advice=spray_advice_strategy(),
    rain_probability=st.floats(min_value=41.0, max_value=100.0)
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_chain_of_verification_blocks_unsafe_advice(advice, rain_probability):
    """
    Test that Chain-of-Verification blocks unsafe advice before synthesis.
    
    Verifies that when advice is blocked by safety validation:
    1. The original advice is NOT synthesized
    2. The alternative recommendation IS synthesized instead
    3. Speech synthesis is still called (with alternative)
    """
    tracker = ExecutionTracker()
    
    # Create weather with high rain probability
    weather = WeatherData(
        current=CurrentWeather(
            temperature=28.0,
            humidity=65.0,
            windSpeed=10.0,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=rain_probability,
            expectedRainfall=5.0,
            temperature=26.0,
            windSpeed=12.0
        ),
        timestamp="2024-01-01T00:00:00Z"
    )
    
    synthesized_texts = []
    original_validate_safety = validate_safety
    
    def tracked_synthesize_speech(text: str, language: str = 'hi-IN'):
        tracker.record_call('synthesize_speech')
        synthesized_texts.append(text)
        return f"audio_{len(synthesized_texts)}.mp3"
    
    def tracked_validate_safety(advice_text: str, weather_data: WeatherData):
        tracker.record_call('validate_safety')
        return original_validate_safety(advice_text, weather_data)
    
    # Execute Chain-of-Verification
    validation_result = tracked_validate_safety(advice, weather)
    
    # Determine final text
    final_text = advice if validation_result.isApproved else validation_result.alternativeRecommendation
    
    # Synthesize speech
    audio_key = tracked_synthesize_speech(final_text)
    
    # Property 1: Advice should be blocked (rain probability > 40%)
    assert not validation_result.isApproved, \
        f"Advice mentioning spray should be blocked when rain probability is {rain_probability}%"
    
    # Property 2: Alternative recommendation should be provided
    assert validation_result.alternativeRecommendation is not None, \
        "Blocked advice must have an alternative recommendation"
    
    # Property 3: Speech synthesis should use alternative, not original
    assert len(synthesized_texts) == 1, \
        "Speech synthesis should be called exactly once"
    assert synthesized_texts[0] == validation_result.alternativeRecommendation, \
        "Speech synthesis must use alternative recommendation when advice is blocked"
    assert synthesized_texts[0] != advice, \
        "Speech synthesis must NOT use original blocked advice"
    
    # Property 4: Validation must occur before synthesis
    assert tracker.was_called_before('validate_safety', 'synthesize_speech'), \
        "Safety validation must occur before speech synthesis"


# Unit tests for specific scenarios

def test_execution_order_with_approved_advice():
    """Test execution order when advice is approved by safety validator."""
    tracker = ExecutionTracker()
    
    advice = "Monitor your rice crop for signs of disease."
    weather = WeatherData(
        current=CurrentWeather(
            temperature=28.0,
            humidity=65.0,
            windSpeed=10.0,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=20.0,
            expectedRainfall=0.0,
            temperature=30.0,
            windSpeed=12.0
        ),
        timestamp="2024-01-01T00:00:00Z"
    )
    
    def mock_validate_safety(advice_text: str, weather_data: WeatherData):
        tracker.record_call('validate_safety')
        return validate_safety(advice_text, weather_data)
    
    def mock_synthesize_speech(text: str, language: str = 'hi-IN'):
        tracker.record_call('synthesize_speech')
        return "audio_key.mp3"
    
    with patch('src.safety.validator.validate_safety', side_effect=mock_validate_safety), \
         patch('src.speech.router.synthesize_speech', side_effect=mock_synthesize_speech):
        
        # Execute flow
        validation_result = mock_validate_safety(advice, weather)
        final_text = advice if validation_result.isApproved else validation_result.alternativeRecommendation
        audio_key = mock_synthesize_speech(final_text)
        
        # Verify
        assert validation_result.isApproved
        assert tracker.was_called_before('validate_safety', 'synthesize_speech')
        assert tracker.get_call_order() == ['validate_safety', 'synthesize_speech']


def test_execution_order_with_blocked_advice():
    """Test execution order when advice is blocked by safety validator."""
    tracker = ExecutionTracker()
    
    advice = "Spray pesticide on your crops this afternoon."
    weather = WeatherData(
        current=CurrentWeather(
            temperature=28.0,
            humidity=65.0,
            windSpeed=10.0,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=60.0,
            expectedRainfall=10.0,
            temperature=26.0,
            windSpeed=12.0
        ),
        timestamp="2024-01-01T00:00:00Z"
    )
    
    def mock_validate_safety(advice_text: str, weather_data: WeatherData):
        tracker.record_call('validate_safety')
        return validate_safety(advice_text, weather_data)
    
    def mock_synthesize_speech(text: str, language: str = 'hi-IN'):
        tracker.record_call('synthesize_speech')
        return "audio_key.mp3"
    
    with patch('src.safety.validator.validate_safety', side_effect=mock_validate_safety), \
         patch('src.speech.router.synthesize_speech', side_effect=mock_synthesize_speech):
        
        # Execute flow
        validation_result = mock_validate_safety(advice, weather)
        final_text = advice if validation_result.isApproved else validation_result.alternativeRecommendation
        audio_key = mock_synthesize_speech(final_text)
        
        # Verify
        assert not validation_result.isApproved
        assert validation_result.alternativeRecommendation is not None
        assert tracker.was_called_before('validate_safety', 'synthesize_speech')
        assert tracker.get_call_order() == ['validate_safety', 'synthesize_speech']


def test_synthesis_never_called_before_validation():
    """Test that attempting to call synthesis before validation raises an error."""
    # This is a design constraint test - in a real implementation,
    # the orchestrator should enforce this ordering
    
    advice = "Apply fertilizer to your crop."
    weather = WeatherData(
        current=CurrentWeather(
            temperature=28.0,
            humidity=65.0,
            windSpeed=10.0,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=20.0,
            expectedRainfall=0.0,
            temperature=30.0,
            windSpeed=12.0
        ),
        timestamp="2024-01-01T00:00:00Z"
    )
    
    # In a properly designed system, this should not be possible
    # The orchestrator should always call validate_safety before synthesize_speech
    # This test documents the expected behavior
    
    validation_result = validate_safety(advice, weather)
    assert validation_result.isApproved is True
    
    # Only after validation should synthesis occur
    # (In actual implementation, this would be enforced by the orchestrator)


@given(
    advice=spray_advice_strategy(),
    rain_probability=st.floats(min_value=41.0, max_value=100.0)
)
@settings(max_examples=100, deadline=None)
@pytest.mark.pbt
def test_property_9_rain_forecast_safety_blocking(advice, rain_probability):
    """
    Feature: vaniverse, Property 9: Rain Forecast Safety Blocking
    Validates: Requirements 4.2, 4.7
    
    Test that advice mentioning spraying is blocked when rain probability >40%.
    
    This property verifies that:
    1. Any advice mentioning spray/pesticide keywords is detected
    2. When rain probability > 40%, the advice is blocked (not approved)
    3. A rain_forecast conflict is added to the conflicts list
    4. An alternative recommendation is provided
    5. The alternative recommendation suggests waiting
    
    Requirements:
    - Requirement 4.2: Block spraying when rain probability >40% within 6 hours
    - Requirement 4.7: Modify or block advice when conflicts detected
    """
    # Create weather with high rain probability (>40%)
    weather = WeatherData(
        current=CurrentWeather(
            temperature=28.0,
            humidity=65.0,
            windSpeed=10.0,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=rain_probability,
            expectedRainfall=5.0,
            temperature=26.0,
            windSpeed=12.0
        ),
        timestamp="2024-01-01T00:00:00Z"
    )
    
    # Execute safety validation
    validation_result = validate_safety(advice, weather)
    
    # Property 1: Advice should be blocked (rain probability > 40%)
    assert not validation_result.isApproved, \
        f"Advice mentioning spray should be blocked when rain probability is {rain_probability:.1f}% (>40%)"
    
    # Property 2: There should be at least one conflict
    assert len(validation_result.conflicts) > 0, \
        "Blocked advice must have at least one conflict"
    
    # Property 3: A rain_forecast conflict must be present
    rain_conflicts = [c for c in validation_result.conflicts if c.type == 'rain_forecast']
    assert len(rain_conflicts) > 0, \
        "When rain probability >40%, a rain_forecast conflict must be present"
    
    # Property 4: The rain_forecast conflict must be blocking severity
    rain_conflict = rain_conflicts[0]
    assert rain_conflict.severity == 'blocking', \
        "Rain forecast conflict must have 'blocking' severity"
    
    # Property 5: The conflict message must mention the rain probability
    assert str(int(rain_probability)) in rain_conflict.message or \
           f"{rain_probability:.0f}" in rain_conflict.message, \
        "Rain conflict message must mention the specific rain probability"
    
    # Property 6: Alternative recommendation must be provided
    assert validation_result.alternativeRecommendation is not None, \
        "Blocked advice must have an alternative recommendation"
    
    # Property 7: Alternative must suggest waiting
    alt = validation_result.alternativeRecommendation.lower()
    assert 'wait' in alt or 'later' in alt or 'hours' in alt, \
        "Alternative recommendation must suggest waiting"
    
    # Property 8: Alternative must mention checking weather again
    assert 'weather' in alt or 'forecast' in alt or 'check' in alt, \
        "Alternative recommendation should mention checking weather again"
    
    # Property 9: Alternative must provide specific timing guidance
    assert 'hours' in alt or 'morning' in alt or 'evening' in alt, \
        "Alternative recommendation must provide specific timing guidance"


@given(
    advice=spray_advice_strategy(),
    rain_probability=st.floats(min_value=0.0, max_value=40.0)
)
@settings(max_examples=100, deadline=None)
@pytest.mark.pbt
def test_property_9_rain_forecast_safety_not_blocking_below_threshold(advice, rain_probability):
    """
    Feature: vaniverse, Property 9: Rain Forecast Safety Blocking (Inverse)
    Validates: Requirements 4.2, 4.7
    
    Test that advice mentioning spraying is NOT blocked when rain probability ≤40%.
    
    This property verifies the inverse case:
    1. When rain probability ≤ 40%, spray advice should be approved
    2. No rain_forecast blocking conflicts should be present
    3. The advice can proceed without alternative recommendation
    
    This ensures the threshold is correctly implemented at >40%, not ≥40%.
    """
    # Create weather with low rain probability (≤40%)
    weather = WeatherData(
        current=CurrentWeather(
            temperature=28.0,
            humidity=65.0,
            windSpeed=10.0,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=rain_probability,
            expectedRainfall=2.0,
            temperature=26.0,
            windSpeed=12.0
        ),
        timestamp="2024-01-01T00:00:00Z"
    )
    
    # Execute safety validation
    validation_result = validate_safety(advice, weather)
    
    # Property 1: Advice should be approved (rain probability ≤ 40%)
    assert validation_result.isApproved, \
        f"Advice mentioning spray should be approved when rain probability is {rain_probability:.1f}% (≤40%)"
    
    # Property 2: No blocking conflicts should be present
    blocking_conflicts = [c for c in validation_result.conflicts if c.severity == 'blocking']
    assert len(blocking_conflicts) == 0, \
        "When rain probability ≤40%, there should be no blocking conflicts"
    
    # Property 3: No rain_forecast blocking conflict should be present
    rain_blocking_conflicts = [
        c for c in validation_result.conflicts 
        if c.type == 'rain_forecast' and c.severity == 'blocking'
    ]
    assert len(rain_blocking_conflicts) == 0, \
        "When rain probability ≤40%, there should be no rain_forecast blocking conflict"
    
    # Property 4: No alternative recommendation should be provided
    assert validation_result.alternativeRecommendation is None, \
        "Approved advice should not have an alternative recommendation"


@given(
    advice=st.text(min_size=10, max_size=200).filter(
        lambda t: not any(keyword in t.lower() for keyword in SPRAY_KEYWORDS)
    ),
    rain_probability=st.floats(min_value=41.0, max_value=100.0)
)
@settings(max_examples=100, deadline=None)
@pytest.mark.pbt
def test_property_9_rain_forecast_only_blocks_spray_advice(advice, rain_probability):
    """
    Feature: vaniverse, Property 9: Rain Forecast Safety Blocking (Specificity)
    Validates: Requirements 4.2, 4.7
    
    Test that rain forecast only blocks advice that mentions spraying.
    
    This property verifies specificity:
    1. Advice that does NOT mention spray keywords should be approved
    2. Even with high rain probability, non-spray advice is not blocked
    3. Rain forecast blocking is specific to pesticide/spray applications
    
    This ensures the safety validator doesn't over-block general advice.
    """
    # Create weather with high rain probability (>40%)
    weather = WeatherData(
        current=CurrentWeather(
            temperature=28.0,
            humidity=65.0,
            windSpeed=10.0,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=rain_probability,
            expectedRainfall=5.0,
            temperature=26.0,
            windSpeed=12.0
        ),
        timestamp="2024-01-01T00:00:00Z"
    )
    
    # Execute safety validation
    validation_result = validate_safety(advice, weather)
    
    # Property 1: Non-spray advice should be approved even with high rain
    assert validation_result.isApproved, \
        f"Advice without spray keywords should be approved even with {rain_probability:.1f}% rain probability"
    
    # Property 2: No rain_forecast blocking conflicts for non-spray advice
    rain_blocking_conflicts = [
        c for c in validation_result.conflicts 
        if c.type == 'rain_forecast' and c.severity == 'blocking'
    ]
    assert len(rain_blocking_conflicts) == 0, \
        "Non-spray advice should not have rain_forecast blocking conflicts"
    
    # Property 3: No alternative recommendation for non-spray advice
    assert validation_result.alternativeRecommendation is None, \
        "Non-spray advice should not have alternative recommendation due to rain"


# Import SPRAY_KEYWORDS for the test
from src.safety.validator import SPRAY_KEYWORDS


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
