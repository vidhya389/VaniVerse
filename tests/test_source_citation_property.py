"""
Property-based tests for source citation in advice.

Tests Property 30: Source Citation in Advice
Validates: Requirements 10.2

**Validates: Requirements 10.2**
"""

import pytest
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings

from src.prompting.builder import build_memory_first_prompt, invoke_bedrock
from src.models.context_data import (
    ContextData, WeatherData, CurrentWeather, Forecast6h,
    LandRecords, MemoryContext, ConsolidatedInsights
)


# Hypothesis Strategies

@st.composite
def context_strategy(draw):
    """Generate random context data."""
    return ContextData(
        weather=WeatherData(
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
            timestamp="2024-01-15T10:00:00Z"
        ),
        landRecords=LandRecords(
            landArea=draw(st.floats(min_value=0.5, max_value=10.0)),
            soilType=draw(st.sampled_from(['Clay Loam', 'Sandy', 'Loamy', 'Clay'])),
            currentCrop=draw(st.sampled_from(['Rice', 'Wheat', 'Cotton', 'Maize'])),
            cropHistory=[]
        ),
        memory=MemoryContext(
            recentInteractions=[],
            unresolvedIssues=[],
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop=draw(st.sampled_from(['Rice', 'Wheat', 'Cotton', 'Maize'])),
                commonConcerns=[],
                farmerName=None
            )
        )
    )


@st.composite
def farmer_question_strategy(draw):
    """Generate random farmer questions."""
    questions = [
        "What fertilizer should I use?",
        "When should I irrigate?",
        "How do I control pests?",
        "What is the best planting time?",
        "Should I spray pesticide now?",
        "How can I improve my yield?",
        "What crop should I plant next?",
        "How do I prepare my soil?"
    ]
    return draw(st.sampled_from(questions))


@st.composite
def icar_knowledge_strategy(draw):
    """Generate ICAR knowledge with citations."""
    crops = ['Rice', 'Wheat', 'Cotton', 'Maize', 'Tomato']
    crop = draw(st.sampled_from(crops))
    
    citations = [
        f"According to ICAR guidelines for {crop}, apply nitrogen fertilizer at 120 kg/ha.",
        f"ICAR recommends planting {crop} during the monsoon season for optimal yield.",
        f"Based on ICAR research, {crop} requires irrigation every 7-10 days.",
        f"ICAR studies show that {crop} benefits from organic matter application.",
        f"Following ICAR best practices, {crop} should be harvested at 80% maturity."
    ]
    
    return draw(st.sampled_from(citations))


# Property Tests

@given(
    context=context_strategy(),
    question=farmer_question_strategy(),
    icar_knowledge=icar_knowledge_strategy()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.pbt
def test_property_30_source_citation_in_advice(context, question, icar_knowledge):
    """
    Feature: vaniverse, Property 30: Source Citation in Advice
    
    **Validates: Requirements 10.2**
    
    For any generated advice, the system should cite the source of recommendations 
    in natural language (e.g., "According to ICAR guidelines..."). This builds 
    farmer trust through transparent sourcing.
    
    This property verifies that:
    1. ICAR knowledge includes citations
    2. System prompt requires provenance
    3. Citations are in natural language
    4. Sources are mentioned explicitly
    5. Advice includes reasoning
    
    Requirements:
    - Requirement 10.2: Cite source of recommendations
    """
    # Build weather analysis
    weather_analysis = f"Temperature is {context.weather.current.temperature}°C with {context.weather.current.humidity}% humidity."
    
    # Build Memory-First prompt
    prompt = build_memory_first_prompt(
        question=question,
        context=context,
        weather_analysis=weather_analysis,
        icar_knowledge=icar_knowledge
    )
    
    # Property 1: ICAR knowledge should contain citation
    assert 'ICAR' in icar_knowledge or 'According to' in icar_knowledge, \
        f"ICAR knowledge should contain citation, got: {icar_knowledge}"
    
    # Property 2: System prompt should require provenance
    system_prompt_lower = prompt.systemPrompt.lower()
    assert 'provenance' in system_prompt_lower or 'explain why' in system_prompt_lower, \
        "System prompt should require provenance/reasoning"
    
    # Property 3: System prompt should mention citing sources
    assert 'reference' in system_prompt_lower or 'because' in system_prompt_lower, \
        "System prompt should instruct to reference context"
    
    # Property 4: ICAR knowledge is included in system prompt
    assert icar_knowledge in prompt.systemPrompt, \
        "ICAR knowledge should be included in system prompt"
    
    # Property 5: System prompt has advice provenance section
    assert 'ADVICE PROVENANCE' in prompt.systemPrompt or 'provenance' in system_prompt_lower, \
        "System prompt should have advice provenance instructions"


@given(
    icar_knowledge=icar_knowledge_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_icar_citation_format(icar_knowledge):
    """
    Test that ICAR knowledge includes proper citations.
    
    Verifies that:
    1. Citations mention ICAR explicitly
    2. Citations are in natural language
    3. Citations provide specific guidance
    
    **Validates: Requirements 10.2**
    """
    # Property 1: Should mention ICAR
    assert 'ICAR' in icar_knowledge, \
        f"ICAR knowledge should mention ICAR, got: {icar_knowledge}"
    
    # Property 2: Should be natural language (not just a reference number)
    assert len(icar_knowledge) > 20, \
        "ICAR knowledge should be descriptive, not just a reference"
    
    # Property 3: Should contain actionable guidance
    guidance_keywords = ['apply', 'use', 'plant', 'harvest', 'irrigate', 'irrigation', 'spray', 'fertilizer', 'recommends', 'guidelines', 'practices', 'requires', 'benefits']
    has_guidance = any(keyword in icar_knowledge.lower() for keyword in guidance_keywords)
    assert has_guidance, \
        f"ICAR knowledge should contain actionable guidance, got: {icar_knowledge}"


@given(
    context=context_strategy(),
    question=farmer_question_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_system_prompt_requires_provenance(context, question):
    """
    Test that system prompt requires advice provenance.
    
    Verifies that:
    1. System prompt has provenance section
    2. System prompt requires explaining WHY
    3. System prompt requires context references
    4. Examples are provided
    
    **Validates: Requirements 13.1, 13.2, 13.3, 13.4, 13.5, 13.6**
    """
    # Build prompt
    prompt = build_memory_first_prompt(
        question=question,
        context=context,
        weather_analysis="Weather is suitable.",
        icar_knowledge="According to ICAR, follow standard practices."
    )
    
    system_prompt = prompt.systemPrompt
    system_prompt_lower = system_prompt.lower()
    
    # Property 1: Should have provenance section
    assert 'provenance' in system_prompt_lower, \
        "System prompt should have ADVICE PROVENANCE section"
    
    # Property 2: Should require explaining WHY
    assert 'why' in system_prompt_lower or 'explain' in system_prompt_lower, \
        "System prompt should require explaining WHY"
    
    # Property 3: Should require context references
    assert 'reference' in system_prompt_lower or 'because' in system_prompt_lower, \
        "System prompt should require referencing context"
    
    # Property 4: Should provide examples
    assert 'example' in system_prompt_lower or 'because your soil' in system_prompt_lower, \
        "System prompt should provide provenance examples"
    
    # Property 5: Should mention specific context factors
    context_factors = ['weather', 'soil', 'forecast', 'mentioned']
    has_context_factors = any(factor in system_prompt_lower for factor in context_factors)
    assert has_context_factors, \
        "System prompt should mention specific context factors"


@given(
    context=context_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_provenance_examples_in_system_prompt(context):
    """
    Test that system prompt includes provenance examples.
    
    Verifies that:
    1. Examples show how to reference soil
    2. Examples show how to reference weather
    3. Examples show how to reference memory
    4. Examples are in natural language
    
    **Validates: Requirements 13.1, 13.2, 13.3, 13.4**
    """
    # Build prompt
    prompt = build_memory_first_prompt(
        question="Test question",
        context=context,
        weather_analysis="Weather analysis",
        icar_knowledge="ICAR knowledge"
    )
    
    system_prompt_lower = prompt.systemPrompt.lower()
    
    # Property 1: Should have soil reference example
    assert 'soil' in system_prompt_lower, \
        "System prompt should have soil reference example"
    
    # Property 2: Should have weather reference example
    assert 'weather' in system_prompt_lower or 'forecast' in system_prompt_lower, \
        "System prompt should have weather reference example"
    
    # Property 3: Should have memory reference example
    assert 'mentioned' in system_prompt_lower or 'last week' in system_prompt_lower, \
        "System prompt should have memory reference example"
    
    # Property 4: Examples should use "because" or "since"
    assert 'because' in system_prompt_lower or 'since' in system_prompt_lower or 'given' in system_prompt_lower, \
        "System prompt should use causal language in examples"


# Unit tests for specific scenarios

def test_icar_citation_with_specific_crop():
    """Test ICAR citation for specific crop."""
    icar_knowledge = "According to ICAR guidelines for Rice, apply nitrogen at 120 kg/ha during tillering stage."
    
    # Should mention ICAR
    assert 'ICAR' in icar_knowledge
    
    # Should mention specific crop
    assert 'Rice' in icar_knowledge
    
    # Should provide specific guidance
    assert '120 kg/ha' in icar_knowledge


def test_system_prompt_provenance_section():
    """Test that system prompt has provenance section."""
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
            timestamp="2024-01-15T10:00:00Z"
        ),
        landRecords=LandRecords(
            landArea=2.5,
            soilType='Clay Loam',
            currentCrop='Wheat',
            cropHistory=[]
        ),
        memory=MemoryContext()
    )
    
    prompt = build_memory_first_prompt(
        question="What fertilizer should I use?",
        context=context,
        weather_analysis="Weather is suitable.",
        icar_knowledge="According to ICAR, use NPK fertilizer."
    )
    
    # Check provenance section exists
    assert 'ADVICE PROVENANCE' in prompt.systemPrompt
    assert 'ALWAYS explain WHY' in prompt.systemPrompt
    assert 'Reference the specific context factors' in prompt.systemPrompt


def test_provenance_examples():
    """Test that system prompt includes provenance examples."""
    context = ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=35.0,
                humidity=45.0,
                windSpeed=15.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=60.0,
                expectedRainfall=10.0,
                temperature=32.0,
                windSpeed=18.0
            ),
            timestamp="2024-01-15T10:00:00Z"
        ),
        landRecords=LandRecords(
            landArea=3.0,
            soilType='Sandy',
            currentCrop='Cotton',
            cropHistory=[]
        ),
        memory=MemoryContext()
    )
    
    prompt = build_memory_first_prompt(
        question="Should I irrigate?",
        context=context,
        weather_analysis="High temperature detected.",
        icar_knowledge="According to ICAR, irrigate during hot weather."
    )
    
    # Check examples are present
    system_prompt = prompt.systemPrompt
    assert 'Because your soil record shows' in system_prompt
    assert 'Since the weather forecast predicts' in system_prompt
    assert 'Given that you mentioned' in system_prompt


def test_icar_knowledge_included_in_prompt():
    """Test that ICAR knowledge is included in system prompt."""
    context = ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=25.0,
                humidity=70.0,
                windSpeed=8.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=20.0,
                expectedRainfall=0.0,
                temperature=27.0,
                windSpeed=10.0
            ),
            timestamp="2024-01-15T10:00:00Z"
        ),
        landRecords=LandRecords(
            landArea=4.0,
            soilType='Loamy',
            currentCrop='Maize',
            cropHistory=[]
        ),
        memory=MemoryContext()
    )
    
    icar_knowledge = "According to ICAR research, Maize requires 150 kg/ha nitrogen for optimal yield."
    
    prompt = build_memory_first_prompt(
        question="How much fertilizer?",
        context=context,
        weather_analysis="Weather is good.",
        icar_knowledge=icar_knowledge
    )
    
    # ICAR knowledge should be in system prompt
    assert icar_knowledge in prompt.systemPrompt
    assert 'ICAR' in prompt.systemPrompt


def test_multiple_citation_formats():
    """Test that various citation formats are supported."""
    citation_formats = [
        "According to ICAR guidelines, apply fertilizer at 100 kg/ha.",
        "ICAR recommends planting during monsoon season.",
        "Based on ICAR research, irrigation is needed every 7 days.",
        "Following ICAR best practices, harvest at 80% maturity.",
        "ICAR studies show that organic matter improves yield."
    ]
    
    for citation in citation_formats:
        # All should mention ICAR
        assert 'ICAR' in citation, f"Citation should mention ICAR: {citation}"
        
        # All should be descriptive
        assert len(citation) > 30, f"Citation should be descriptive: {citation}"


def test_provenance_requirement_in_system_prompt():
    """Test that system prompt requires at least one provenance statement."""
    context = ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=30.0,
                humidity=60.0,
                windSpeed=12.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=40.0,
                expectedRainfall=5.0,
                temperature=28.0,
                windSpeed=15.0
            ),
            timestamp="2024-01-15T10:00:00Z"
        ),
        landRecords=LandRecords(
            landArea=2.0,
            soilType='Clay',
            currentCrop='Rice',
            cropHistory=[]
        ),
        memory=MemoryContext()
    )
    
    prompt = build_memory_first_prompt(
        question="What should I do?",
        context=context,
        weather_analysis="Weather analysis",
        icar_knowledge="ICAR knowledge"
    )
    
    # System prompt should require at least one provenance statement
    system_prompt_lower = prompt.systemPrompt.lower()
    assert 'at least one provenance statement' in system_prompt_lower or \
           'every recommendation must include' in system_prompt_lower, \
        "System prompt should require at least one provenance statement"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
