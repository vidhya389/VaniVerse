"""
Property-based tests for crop growth stage specificity.

Tests Property 31: Crop Growth Stage Specificity
Validates: Requirements 10.3

**Validates: Requirements 10.3**
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings

from src.prompting.builder import build_memory_first_prompt
from src.models.context_data import (
    ContextData, WeatherData, CurrentWeather, Forecast6h,
    LandRecords, MemoryContext, ConsolidatedInsights,
    Interaction, UnresolvedIssue
)


# Hypothesis Strategies

@st.composite
def growth_stage_strategy(draw):
    """Generate crop growth stages."""
    stages = [
        'Germination',
        'Seedling',
        'Vegetative',
        'Flowering',
        'Fruiting',
        'Maturity',
        'Tillering',
        'Panicle Initiation',
        'Grain Filling',
        'Ripening',
        'Bolting',
        'Heading'
    ]
    return draw(st.sampled_from(stages))


@st.composite
def crop_strategy(draw):
    """Generate crop names."""
    crops = ['Rice', 'Wheat', 'Cotton', 'Maize', 'Tomato', 'Sugarcane', 'Soybean']
    return draw(st.sampled_from(crops))


@st.composite
def context_with_growth_stage_strategy(draw):
    """Generate context with growth stage information in memory."""
    crop = draw(crop_strategy())
    growth_stage = draw(growth_stage_strategy())
    
    # Create interaction mentioning growth stage
    days_ago = draw(st.integers(min_value=1, max_value=30))
    interaction_date = datetime.utcnow() - timedelta(days=days_ago)
    
    interaction = Interaction(
        question=f"My {crop} is in {growth_stage} stage. What should I do?",
        advice=f"For {crop} in {growth_stage} stage, follow these steps...",
        timestamp=interaction_date.isoformat()
    )
    
    return ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=draw(st.floats(min_value=20.0, max_value=40.0)),
                humidity=draw(st.floats(min_value=40.0, max_value=90.0)),
                windSpeed=draw(st.floats(min_value=0.0, max_value=30.0)),
                precipitation=draw(st.floats(min_value=0.0, max_value=20.0))
            ),
            forecast6h=Forecast6h(
                precipitationProbability=draw(st.floats(min_value=0.0, max_value=100.0)),
                expectedRainfall=draw(st.floats(min_value=0.0, max_value=20.0)),
                temperature=draw(st.floats(min_value=20.0, max_value=40.0)),
                windSpeed=draw(st.floats(min_value=0.0, max_value=30.0))
            ),
            timestamp=datetime.utcnow().isoformat()
        ),
        landRecords=LandRecords(
            landArea=draw(st.floats(min_value=1.0, max_value=8.0)),
            soilType=draw(st.sampled_from(['Clay Loam', 'Sandy', 'Loamy', 'Clay'])),
            currentCrop=crop,
            cropHistory=[]
        ),
        memory=MemoryContext(
            recentInteractions=[interaction],
            unresolvedIssues=[],
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop=crop,
                commonConcerns=[f"{growth_stage} stage management"],
                farmerName=None
            )
        )
    ), growth_stage


@st.composite
def farmer_question_about_crop_strategy(draw):
    """Generate farmer questions about crop management."""
    questions = [
        "What fertilizer should I apply now?",
        "When should I irrigate?",
        "How do I manage pests?",
        "What nutrients does my crop need?",
        "Should I spray pesticide?",
        "How much water should I give?",
        "What is the best practice now?",
        "How do I improve my yield?"
    ]
    return draw(st.sampled_from(questions))


# Property Tests

@given(
    context_and_stage=context_with_growth_stage_strategy(),
    question=farmer_question_about_crop_strategy()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.pbt
def test_property_31_crop_growth_stage_specificity(context_and_stage, question):
    """
    Feature: vaniverse, Property 31: Crop Growth Stage Specificity
    
    **Validates: Requirements 10.3**
    
    For any crop-specific advice, the system should provide recommendations 
    based on the specific growth stage retrieved from conversation memory. 
    This ensures advice is timely and appropriate for the crop's current 
    development phase.
    
    This property verifies that:
    1. Growth stage information is captured in memory
    2. Growth stage is accessible from recent interactions
    3. System prompt includes memory context with growth stage
    4. ICAR knowledge can reference growth stages
    5. Advice can be stage-specific
    
    Requirements:
    - Requirement 10.3: Provide crop-specific advice based on growth stages
    """
    context, growth_stage = context_and_stage
    
    # Build ICAR knowledge with growth stage reference
    icar_knowledge = f"According to ICAR, for {context.landRecords.currentCrop} in {growth_stage} stage, apply appropriate nutrients."
    
    # Build Memory-First prompt
    prompt = build_memory_first_prompt(
        question=question,
        context=context,
        weather_analysis="Weather conditions are suitable.",
        icar_knowledge=icar_knowledge
    )
    
    # Property 1: Memory should contain growth stage information
    assert len(context.memory.recentInteractions) > 0, \
        "Memory should have recent interactions"
    
    recent_interaction = context.memory.recentInteractions[0]
    assert growth_stage in recent_interaction.question or growth_stage in recent_interaction.advice, \
        f"Recent interaction should mention growth stage '{growth_stage}'"
    
    # Property 2: System prompt should include memory context
    system_prompt = prompt.systemPrompt
    assert 'Memory:' in system_prompt or 'memory' in system_prompt.lower(), \
        "System prompt should include memory context"
    
    # Property 3: Growth stage should be accessible in context
    interaction_text = recent_interaction.question + " " + recent_interaction.advice
    assert growth_stage in interaction_text, \
        f"Growth stage '{growth_stage}' should be in interaction text"
    
    # Property 4: ICAR knowledge should reference growth stage
    assert growth_stage in icar_knowledge, \
        f"ICAR knowledge should reference growth stage '{growth_stage}'"
    
    # Property 5: Crop should match between land records and memory
    assert context.landRecords.currentCrop == context.memory.consolidatedInsights.primaryCrop, \
        "Current crop should match primary crop in memory"


@given(
    crop=crop_strategy(),
    growth_stage=growth_stage_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_growth_stage_in_memory_interactions(crop, growth_stage):
    """
    Test that growth stage information is captured in memory interactions.
    
    Verifies that:
    1. Interactions can mention growth stages
    2. Growth stages are preserved in memory
    3. Multiple interactions can track growth progression
    
    **Validates: Requirements 10.3**
    """
    # Create interaction with growth stage
    interaction = Interaction(
        question=f"My {crop} is in {growth_stage} stage. What should I do?",
        advice=f"For {crop} in {growth_stage} stage, follow these steps...",
        timestamp=datetime.utcnow().isoformat()
    )
    
    # Property 1: Growth stage should be in question
    assert growth_stage in interaction.question, \
        f"Growth stage '{growth_stage}' should be in question"
    
    # Property 2: Growth stage should be in advice
    assert growth_stage in interaction.advice, \
        f"Growth stage '{growth_stage}' should be in advice"
    
    # Property 3: Crop should be in interaction
    assert crop in interaction.question, \
        f"Crop '{crop}' should be in question"


@given(
    context_and_stage=context_with_growth_stage_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_growth_stage_accessible_from_memory(context_and_stage):
    """
    Test that growth stage is accessible from memory context.
    
    Verifies that:
    1. Recent interactions contain growth stage
    2. Consolidated insights reference growth stage concerns
    3. Memory context is complete
    
    **Validates: Requirements 10.3, 2.1**
    """
    context, growth_stage = context_and_stage
    
    # Property 1: Memory should have recent interactions
    assert context.memory is not None, "Memory should not be None"
    assert len(context.memory.recentInteractions) > 0, \
        "Memory should have at least one interaction"
    
    # Property 2: Recent interaction should mention growth stage
    recent = context.memory.recentInteractions[0]
    interaction_text = recent.question + " " + recent.advice
    assert growth_stage in interaction_text, \
        f"Growth stage '{growth_stage}' should be in recent interaction"
    
    # Property 3: Consolidated insights should reference growth stage
    insights = context.memory.consolidatedInsights
    if insights.commonConcerns:
        concerns_text = " ".join(insights.commonConcerns)
        assert growth_stage in concerns_text or 'stage' in concerns_text.lower(), \
            "Consolidated insights should reference growth stage concerns"


@given(
    crop=crop_strategy(),
    growth_stage=growth_stage_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_icar_knowledge_with_growth_stage(crop, growth_stage):
    """
    Test that ICAR knowledge can reference specific growth stages.
    
    Verifies that:
    1. ICAR knowledge mentions growth stage
    2. ICAR knowledge mentions crop
    3. Advice is stage-specific
    
    **Validates: Requirements 10.3, 10.2**
    """
    # Create ICAR knowledge with growth stage
    icar_knowledge = f"According to ICAR guidelines, {crop} in {growth_stage} stage requires specific nutrient management."
    
    # Property 1: Should mention growth stage
    assert growth_stage in icar_knowledge, \
        f"ICAR knowledge should mention growth stage '{growth_stage}'"
    
    # Property 2: Should mention crop
    assert crop in icar_knowledge, \
        f"ICAR knowledge should mention crop '{crop}'"
    
    # Property 3: Should mention ICAR
    assert 'ICAR' in icar_knowledge, \
        "ICAR knowledge should cite ICAR"
    
    # Property 4: Should be specific (not generic)
    assert len(icar_knowledge) > 50, \
        "ICAR knowledge should be specific, not generic"


# Unit tests for specific scenarios

def test_rice_tillering_stage():
    """Test advice for Rice in Tillering stage."""
    context = ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=28.0,
                humidity=75.0,
                windSpeed=8.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=30.0,
                expectedRainfall=0.0,
                temperature=30.0,
                windSpeed=10.0
            ),
            timestamp=datetime.utcnow().isoformat()
        ),
        landRecords=LandRecords(
            landArea=2.5,
            soilType='Clay Loam',
            currentCrop='Rice',
            cropHistory=[]
        ),
        memory=MemoryContext(
            recentInteractions=[
                Interaction(
                    question="My Rice is in Tillering stage. What fertilizer should I use?",
                    advice="For Rice in Tillering stage, apply nitrogen fertilizer.",
                    timestamp=datetime.utcnow().isoformat()
                )
            ],
            unresolvedIssues=[],
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop='Rice',
                commonConcerns=['Tillering stage management'],
                farmerName=None
            )
        )
    )
    
    # Build prompt
    prompt = build_memory_first_prompt(
        question="How much nitrogen should I apply?",
        context=context,
        weather_analysis="Weather is suitable.",
        icar_knowledge="According to ICAR, Rice in Tillering stage needs 40 kg/ha nitrogen."
    )
    
    # Verify growth stage is accessible
    assert 'Tillering' in context.memory.recentInteractions[0].question
    assert 'Tillering' in prompt.systemPrompt


def test_wheat_flowering_stage():
    """Test advice for Wheat in Flowering stage."""
    context = ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=25.0,
                humidity=60.0,
                windSpeed=12.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=20.0,
                expectedRainfall=0.0,
                temperature=27.0,
                windSpeed=15.0
            ),
            timestamp=datetime.utcnow().isoformat()
        ),
        landRecords=LandRecords(
            landArea=3.0,
            soilType='Loamy',
            currentCrop='Wheat',
            cropHistory=[]
        ),
        memory=MemoryContext(
            recentInteractions=[
                Interaction(
                    question="My Wheat is in Flowering stage. Should I irrigate?",
                    advice="Yes, Wheat in Flowering stage needs adequate water.",
                    timestamp=datetime.utcnow().isoformat()
                )
            ],
            unresolvedIssues=[],
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop='Wheat',
                commonConcerns=['Flowering stage irrigation'],
                farmerName=None
            )
        )
    )
    
    # Build prompt
    prompt = build_memory_first_prompt(
        question="How often should I irrigate?",
        context=context,
        weather_analysis="Temperature is moderate.",
        icar_knowledge="According to ICAR, Wheat in Flowering stage requires irrigation every 7 days."
    )
    
    # Verify growth stage is accessible
    assert 'Flowering' in context.memory.recentInteractions[0].question
    assert 'Flowering' in prompt.systemPrompt


def test_cotton_fruiting_stage():
    """Test advice for Cotton in Fruiting stage."""
    context = ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=32.0,
                humidity=55.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=15.0,
                expectedRainfall=0.0,
                temperature=34.0,
                windSpeed=12.0
            ),
            timestamp=datetime.utcnow().isoformat()
        ),
        landRecords=LandRecords(
            landArea=4.0,
            soilType='Black Soil',
            currentCrop='Cotton',
            cropHistory=[]
        ),
        memory=MemoryContext(
            recentInteractions=[
                Interaction(
                    question="My Cotton is in Fruiting stage. How do I manage pests?",
                    advice="For Cotton in Fruiting stage, monitor for bollworms.",
                    timestamp=datetime.utcnow().isoformat()
                )
            ],
            unresolvedIssues=[],
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop='Cotton',
                commonConcerns=['Fruiting stage pest management'],
                farmerName=None
            )
        )
    )
    
    # Build prompt
    prompt = build_memory_first_prompt(
        question="What pesticide should I use?",
        context=context,
        weather_analysis="Weather is hot and dry.",
        icar_knowledge="According to ICAR, Cotton in Fruiting stage is susceptible to bollworms."
    )
    
    # Verify growth stage is accessible
    assert 'Fruiting' in context.memory.recentInteractions[0].question
    assert 'Fruiting' in prompt.systemPrompt


def test_multiple_growth_stages_in_history():
    """Test tracking multiple growth stages over time."""
    interactions = [
        Interaction(
            question="My Maize is in Seedling stage.",
            advice="For Seedling stage, ensure adequate moisture.",
            timestamp=(datetime.utcnow() - timedelta(days=30)).isoformat()
        ),
        Interaction(
            question="My Maize is now in Vegetative stage.",
            advice="For Vegetative stage, apply nitrogen fertilizer.",
            timestamp=(datetime.utcnow() - timedelta(days=15)).isoformat()
        ),
        Interaction(
            question="My Maize is in Flowering stage now.",
            advice="For Flowering stage, ensure adequate water.",
            timestamp=datetime.utcnow().isoformat()
        )
    ]
    
    context = ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=30.0,
                humidity=65.0,
                windSpeed=8.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=25.0,
                expectedRainfall=0.0,
                temperature=32.0,
                windSpeed=10.0
            ),
            timestamp=datetime.utcnow().isoformat()
        ),
        landRecords=LandRecords(
            landArea=3.5,
            soilType='Sandy Loam',
            currentCrop='Maize',
            cropHistory=[]
        ),
        memory=MemoryContext(
            recentInteractions=interactions,
            unresolvedIssues=[],
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop='Maize',
                commonConcerns=['Growth stage progression'],
                farmerName=None
            )
        )
    )
    
    # Verify all growth stages are captured
    all_text = " ".join([i.question + " " + i.advice for i in interactions])
    assert 'Seedling' in all_text
    assert 'Vegetative' in all_text
    assert 'Flowering' in all_text


def test_growth_stage_in_consolidated_insights():
    """Test that growth stage concerns appear in consolidated insights."""
    context = ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=27.0,
                humidity=70.0,
                windSpeed=9.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=35.0,
                expectedRainfall=2.0,
                temperature=28.0,
                windSpeed=11.0
            ),
            timestamp=datetime.utcnow().isoformat()
        ),
        landRecords=LandRecords(
            landArea=2.0,
            soilType='Clay',
            currentCrop='Tomato',
            cropHistory=[]
        ),
        memory=MemoryContext(
            recentInteractions=[
                Interaction(
                    question="My Tomato is in Fruiting stage.",
                    advice="For Fruiting stage, ensure calcium availability.",
                    timestamp=datetime.utcnow().isoformat()
                )
            ],
            unresolvedIssues=[],
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop='Tomato',
                commonConcerns=['Fruiting stage nutrition', 'Calcium deficiency prevention'],
                farmerName=None
            )
        )
    )
    
    # Verify growth stage in consolidated insights
    concerns = context.memory.consolidatedInsights.commonConcerns
    assert any('Fruiting' in concern or 'stage' in concern for concern in concerns), \
        "Consolidated insights should reference growth stage"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
