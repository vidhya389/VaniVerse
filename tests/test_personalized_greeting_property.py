"""
Property-based tests for personalized greeting functionality.

Tests Property 14: Personalized Greeting for Returning Farmers
Validates: Requirements 5.4
"""

import pytest
from hypothesis import given, strategies as st, assume
from src.context.farmer_identity import generate_personalized_greeting
from src.models.context_data import MemoryContext, ConsolidatedInsights


# Strategy for generating farmer names
farmer_name_strategy = st.one_of(
    st.none(),
    st.text(min_size=2, max_size=50, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll'),
        whitelist_characters=' '
    )).filter(lambda x: x.strip() != '')
)

# Strategy for generating crop names
crop_name_strategy = st.one_of(
    st.just('Unknown'),
    st.sampled_from([
        'Rice', 'Wheat', 'Cotton', 'Sugarcane', 'Maize',
        'Soybean', 'Groundnut', 'Pulses', 'Vegetables', 'Fruits'
    ])
)

# Strategy for generating consolidated insights
@st.composite
def consolidated_insights_strategy(draw):
    """Generate random ConsolidatedInsights."""
    return ConsolidatedInsights(
        primaryCrop=draw(crop_name_strategy),
        farmerName=draw(farmer_name_strategy),
        commonConcerns=draw(st.lists(st.text(min_size=5, max_size=50), max_size=5))
    )

# Strategy for generating memory context
@st.composite
def memory_context_strategy(draw):
    """Generate random MemoryContext with consolidated insights."""
    return MemoryContext(
        consolidatedInsights=draw(consolidated_insights_strategy())
    )


@given(memory=memory_context_strategy())
@pytest.mark.property_test
def test_property_14_personalized_greeting_for_returning_farmers(memory):
    """
    Feature: vaniverse, Property 14: Personalized Greeting for Returning Farmers
    
    For any returning farmer with existing memory, the initial greeting should 
    include their name and reference their primary crop from consolidated insights.
    
    Validates: Requirements 5.4
    """
    # Get consolidated insights
    insights = memory.consolidatedInsights
    
    # Assume we have at least some personalization data
    has_name = insights.farmerName is not None and insights.farmerName.strip() != ''
    has_crop = insights.primaryCrop is not None and insights.primaryCrop != 'Unknown'
    
    # Generate greeting for returning farmer
    greeting = generate_personalized_greeting(memory, is_returning_farmer=True)
    
    # Property: If farmer has name OR crop, greeting should be personalized
    if has_name or has_crop:
        assert greeting is not None, \
            f"Expected personalized greeting for farmer with name={insights.farmerName}, crop={insights.primaryCrop}"
        
        # If has name, greeting should include it
        if has_name:
            assert insights.farmerName in greeting, \
                f"Greeting should include farmer name '{insights.farmerName}', got: {greeting}"
        
        # If has crop (and not Unknown), greeting should reference it
        if has_crop:
            assert insights.primaryCrop in greeting, \
                f"Greeting should reference crop '{insights.primaryCrop}', got: {greeting}"
    
    else:
        # No personalization data available
        assert greeting is None, \
            f"Expected no greeting for farmer without personalization data, got: {greeting}"


@given(memory=memory_context_strategy())
@pytest.mark.property_test
def test_property_14_no_greeting_for_new_farmers(memory):
    """
    Feature: vaniverse, Property 14: Personalized Greeting for Returning Farmers
    
    New farmers (is_returning_farmer=False) should not receive personalized greetings,
    regardless of memory content.
    
    Validates: Requirements 5.4
    """
    # Generate greeting for new farmer
    greeting = generate_personalized_greeting(memory, is_returning_farmer=False)
    
    # Property: New farmers should never get personalized greeting
    assert greeting is None, \
        f"New farmers should not receive personalized greeting, got: {greeting}"


@given(
    farmer_name=farmer_name_strategy,
    primary_crop=crop_name_strategy
)
@pytest.mark.property_test
def test_property_14_greeting_contains_personalization_data(farmer_name, primary_crop):
    """
    Feature: vaniverse, Property 14: Personalized Greeting for Returning Farmers
    
    For any combination of farmer name and crop, if a greeting is generated,
    it must contain the available personalization data.
    
    Validates: Requirements 5.4
    """
    # Create memory with specific personalization data
    memory = MemoryContext(
        consolidatedInsights=ConsolidatedInsights(
            primaryCrop=primary_crop,
            farmerName=farmer_name,
            commonConcerns=[]
        )
    )
    
    # Generate greeting
    greeting = generate_personalized_greeting(memory, is_returning_farmer=True)
    
    # Check if we have personalization data
    has_name = farmer_name is not None and farmer_name.strip() != ''
    has_crop = primary_crop is not None and primary_crop != 'Unknown'
    
    if greeting is not None:
        # Property: Greeting must contain available personalization data
        if has_name:
            assert farmer_name in greeting, \
                f"Greeting must contain farmer name '{farmer_name}', got: {greeting}"
        
        if has_crop:
            assert primary_crop in greeting, \
                f"Greeting must contain crop '{primary_crop}', got: {greeting}"
    
    else:
        # Property: No greeting only if no personalization data
        assert not has_name and not has_crop, \
            f"Expected greeting for farmer with name={farmer_name}, crop={primary_crop}"


@given(memory=memory_context_strategy())
@pytest.mark.property_test
def test_property_14_greeting_is_string_or_none(memory):
    """
    Feature: vaniverse, Property 14: Personalized Greeting for Returning Farmers
    
    The greeting function should always return either a string or None,
    never any other type.
    
    Validates: Requirements 5.4
    """
    greeting = generate_personalized_greeting(memory, is_returning_farmer=True)
    
    # Property: Result must be string or None
    assert greeting is None or isinstance(greeting, str), \
        f"Greeting must be string or None, got type: {type(greeting)}"
    
    # If string, should not be empty
    if isinstance(greeting, str):
        assert len(greeting) > 0, "Greeting string should not be empty"


@given(
    farmer_name=st.text(min_size=2, max_size=50, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll'),
        whitelist_characters=' '
    )).filter(lambda x: x.strip() != ''),
    primary_crop=st.sampled_from([
        'Rice', 'Wheat', 'Cotton', 'Sugarcane', 'Maize'
    ])
)
@pytest.mark.property_test
def test_property_14_greeting_consistency(farmer_name, primary_crop):
    """
    Feature: vaniverse, Property 14: Personalized Greeting for Returning Farmers
    
    For the same farmer data, the greeting generation should be consistent
    (deterministic).
    
    Validates: Requirements 5.4
    """
    # Create memory
    memory = MemoryContext(
        consolidatedInsights=ConsolidatedInsights(
            primaryCrop=primary_crop,
            farmerName=farmer_name,
            commonConcerns=[]
        )
    )
    
    # Generate greeting twice
    greeting1 = generate_personalized_greeting(memory, is_returning_farmer=True)
    greeting2 = generate_personalized_greeting(memory, is_returning_farmer=True)
    
    # Property: Should be consistent
    assert greeting1 == greeting2, \
        f"Greeting should be consistent for same data. Got: '{greeting1}' and '{greeting2}'"


@given(memory=memory_context_strategy())
@pytest.mark.property_test
def test_property_14_greeting_format_validity(memory):
    """
    Feature: vaniverse, Property 14: Personalized Greeting for Returning Farmers
    
    Any generated greeting should be a valid, non-empty string that could
    be spoken naturally.
    
    Validates: Requirements 5.4
    """
    greeting = generate_personalized_greeting(memory, is_returning_farmer=True)
    
    if greeting is not None:
        # Property: Greeting should be valid
        assert isinstance(greeting, str), "Greeting must be a string"
        assert len(greeting) > 0, "Greeting must not be empty"
        assert greeting.strip() == greeting or greeting.endswith('?') or greeting.endswith('!'), \
            "Greeting should be properly formatted"
        
        # Should not contain placeholder text
        assert '[' not in greeting and ']' not in greeting, \
            f"Greeting should not contain placeholders: {greeting}"
