"""
Property-based tests for memory persistence round-trip.

Tests Property 3: Memory Persistence Round-Trip
Validates: Requirements 2.1, 2.3, 11.7

**Validates: Requirements 2.1, 2.3, 11.7**
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings

from src.context.memory import store_interaction, fetch_memory
from src.models.context_data import (
    ContextData, WeatherData, CurrentWeather, Forecast6h,
    LandRecords, MemoryContext, ConsolidatedInsights,
    Interaction
)


# Hypothesis Strategies

@st.composite
def farmer_id_strategy(draw):
    """Generate random farmer IDs."""
    return f"FARMER-{draw(st.integers(min_value=1, max_value=9999))}"


@st.composite
def question_strategy(draw):
    """Generate random farmer questions."""
    questions = [
        "How do I control pests on my rice crop?",
        "When should I irrigate my wheat field?",
        "What fertilizer should I use for tomatoes?",
        "Is it safe to spray pesticide today?",
        "How do I treat leaf curl disease?",
        "When is the best time to harvest?",
        "Should I plant now or wait for rain?",
        "What is the best crop for my soil type?",
        "How much water does my cotton need?",
        "What are the signs of nitrogen deficiency?"
    ]
    return draw(st.sampled_from(questions))


@st.composite
def advice_strategy(draw):
    """Generate random agricultural advice."""
    advice_templates = [
        "Based on current weather conditions, you should {}.",
        "According to ICAR guidelines, {}.",
        "Given your soil type, {}.",
        "The best approach is to {}.",
    ]
    
    actions = [
        "apply fertilizer in the morning",
        "wait for better weather conditions",
        "irrigate your field this evening",
        "monitor for pest activity",
        "harvest within the next week",
        "apply organic compost",
        "check soil moisture levels"
    ]
    
    template = draw(st.sampled_from(advice_templates))
    action = draw(st.sampled_from(actions))
    
    return template.format(action)


@st.composite
def weather_data_strategy(draw):
    """Generate random weather data."""
    return WeatherData(
        current=CurrentWeather(
            temperature=draw(st.floats(min_value=15.0, max_value=45.0)),
            humidity=draw(st.floats(min_value=20.0, max_value=100.0)),
            windSpeed=draw(st.floats(min_value=0.0, max_value=50.0)),
            precipitation=draw(st.floats(min_value=0.0, max_value=100.0))
        ),
        forecast6h=Forecast6h(
            precipitationProbability=draw(st.floats(min_value=0.0, max_value=100.0)),
            expectedRainfall=draw(st.floats(min_value=0.0, max_value=50.0)),
            temperature=draw(st.floats(min_value=15.0, max_value=45.0)),
            windSpeed=draw(st.floats(min_value=0.0, max_value=50.0))
        ),
        timestamp=datetime.utcnow().isoformat()
    )


@st.composite
def land_records_strategy(draw):
    """Generate random land records."""
    include_land = draw(st.booleans())
    if not include_land:
        return None
    
    return LandRecords(
        landArea=draw(st.floats(min_value=0.5, max_value=10.0)),
        soilType=draw(st.sampled_from(['Clay Loam', 'Sandy', 'Loamy', 'Clay', 'Sandy Loam'])),
        currentCrop=draw(st.sampled_from(['Rice', 'Wheat', 'Cotton', 'Sugarcane', 'Maize', 'Tomato'])),
        cropHistory=[]
    )


@st.composite
def context_data_strategy(draw):
    """Generate random context data."""
    return ContextData(
        weather=draw(weather_data_strategy()),
        landRecords=draw(land_records_strategy()),
        memory=MemoryContext(
            recentInteractions=[],
            unresolvedIssues=[],
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop=draw(st.sampled_from(['Rice', 'Wheat', 'Cotton', 'Sugarcane'])),
                commonConcerns=[],
                farmerName=None
            )
        )
    )


# Property Tests

@given(
    farmer_id=farmer_id_strategy(),
    question=question_strategy(),
    advice=advice_strategy(),
    context=context_data_strategy()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.pbt
def test_property_3_memory_persistence_round_trip(farmer_id, question, advice, context):
    """
    Feature: vaniverse, Property 3: Memory Persistence Round-Trip
    
    **Validates: Requirements 2.1, 2.3, 11.7**
    
    For any interaction (question + advice + context), after storing it in 
    AgentCore Memory and then retrieving memory for that FarmerID, the 
    interaction should appear in the retrieved context.
    
    This property verifies that:
    1. Interactions can be stored in AgentCore Memory
    2. Stored interactions can be retrieved using FarmerID
    3. Retrieved interactions contain the original question and advice
    4. The round-trip preserves data integrity
    5. FarmerID is used consistently as the partition key
    
    Requirements:
    - Requirement 2.1: Store interactions in AgentCore Memory
    - Requirement 2.3: AgentCore Memory automatically stores and categorizes
    - Requirement 11.7: Use FarmerID as session identifier
    """
    # Create a mock stored interaction that will be returned by fetch_memory
    stored_interaction = Interaction(
        question=question,
        advice=advice,
        timestamp=datetime.utcnow().isoformat()
    )
    
    # Mock AgentCore Memory responses
    with patch('src.context.memory.boto3.client') as mock_boto_client, \
         patch('src.context.memory.Config') as mock_config:
        
        # Configure Config mock
        mock_config.AGENTCORE_MEMORY_ID = 'test-memory-id'
        mock_config.AGENTCORE_AGENT_ID = 'test-agent-id'
        mock_config.AGENTCORE_ALIAS_ID = 'test-alias-id'
        mock_config.AWS_REGION = 'us-east-1'
        mock_config.CLAUDE_MODEL_ARN = 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0'
        
        # Create mock bedrock agent runtime client
        mock_bedrock_client = MagicMock()
        mock_boto_client.return_value = mock_bedrock_client
        
        # Mock store_interaction (invoke_agent)
        mock_bedrock_client.invoke_agent.return_value = {
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        
        # Mock fetch_memory (retrieve_and_generate)
        # Simulate that the stored interaction is now in memory
        mock_bedrock_client.retrieve_and_generate.return_value = {
            'output': {
                'text': f'''{{
                    "recentInteractions": [
                        {{
                            "question": "{question}",
                            "advice": "{advice}",
                            "timestamp": "{stored_interaction.timestamp}"
                        }}
                    ],
                    "unresolvedIssues": [],
                    "consolidatedInsights": {{
                        "primaryCrop": "{context.memory.consolidatedInsights.primaryCrop}",
                        "commonConcerns": [],
                        "farmerName": null
                    }}
                }}'''
            }
        }
        
        # Step 1: Store the interaction
        store_interaction(farmer_id, question, advice, context)
        
        # Verify store was called
        assert mock_bedrock_client.invoke_agent.called, \
            "store_interaction should invoke AgentCore Memory"
        
        # Verify store was called with correct farmer_id (as sessionId)
        store_call = mock_bedrock_client.invoke_agent.call_args
        assert store_call is not None, "invoke_agent should be called with arguments"
        
        # Extract sessionId from call
        if store_call[1]:  # Keyword arguments
            session_id = store_call[1].get('sessionId')
        else:  # Positional arguments would be unusual for boto3
            session_id = None
        
        # Property 1: FarmerID is used as session identifier for storage
        assert session_id == farmer_id, \
            f"Storage should use farmer_id '{farmer_id}' as sessionId, got '{session_id}'"
        
        # Step 2: Retrieve memory for the same farmer
        retrieved_memory = fetch_memory(farmer_id)
        
        # Verify fetch was called
        assert mock_bedrock_client.retrieve_and_generate.called, \
            "fetch_memory should query AgentCore Memory"
        
        # Verify fetch was called with correct farmer_id (as sessionId)
        fetch_call = mock_bedrock_client.retrieve_and_generate.call_args
        assert fetch_call is not None, "retrieve_and_generate should be called with arguments"
        
        # Extract sessionId from call
        if fetch_call[1]:  # Keyword arguments
            fetch_session_id = fetch_call[1].get('sessionId')
        else:
            fetch_session_id = None
        
        # Property 2: FarmerID is used consistently for retrieval
        assert fetch_session_id == farmer_id, \
            f"Retrieval should use farmer_id '{farmer_id}' as sessionId, got '{fetch_session_id}'"
        
        # Property 3: Retrieved memory contains the stored interaction
        assert retrieved_memory is not None, \
            "fetch_memory should return MemoryContext"
        
        assert isinstance(retrieved_memory, MemoryContext), \
            "Retrieved memory should be MemoryContext instance"
        
        # Property 4: Recent interactions list contains our interaction
        assert len(retrieved_memory.recentInteractions) > 0, \
            "Retrieved memory should contain at least one interaction"
        
        # Find our interaction in the retrieved list
        found_interaction = None
        for interaction in retrieved_memory.recentInteractions:
            if interaction.question == question and interaction.advice == advice:
                found_interaction = interaction
                break
        
        # Property 5: The stored interaction is present in retrieved memory
        assert found_interaction is not None, \
            f"Stored interaction should be present in retrieved memory. " \
            f"Question: '{question}', Advice: '{advice}'"
        
        # Property 6: Interaction data is preserved (round-trip integrity)
        assert found_interaction.question == question, \
            f"Retrieved question should match stored question. " \
            f"Expected: '{question}', Got: '{found_interaction.question}'"
        
        assert found_interaction.advice == advice, \
            f"Retrieved advice should match stored advice. " \
            f"Expected: '{advice}', Got: '{found_interaction.advice}'"
        
        assert found_interaction.timestamp is not None, \
            "Retrieved interaction should have a timestamp"


@given(
    farmer_id=farmer_id_strategy(),
    question=question_strategy(),
    advice=advice_strategy(),
    context=context_data_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_memory_persistence_farmer_id_partitioning(farmer_id, question, advice, context):
    """
    Test that memory is correctly partitioned by FarmerID.
    
    Verifies that:
    1. Each farmer's memory is isolated
    2. FarmerID is used consistently as partition key
    3. Different farmers don't see each other's interactions
    
    **Validates: Requirements 2.3, 5.3, 11.7**
    """
    # Create a different farmer ID
    other_farmer_id = f"{farmer_id}-OTHER"
    
    with patch('src.context.memory.boto3.client') as mock_boto_client, \
         patch('src.context.memory.Config') as mock_config:
        
        # Configure Config mock
        mock_config.AGENTCORE_MEMORY_ID = 'test-memory-id'
        mock_config.AGENTCORE_AGENT_ID = 'test-agent-id'
        mock_config.AGENTCORE_ALIAS_ID = 'test-alias-id'
        mock_config.AWS_REGION = 'us-east-1'
        mock_config.CLAUDE_MODEL_ARN = 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0'
        
        mock_bedrock_client = MagicMock()
        mock_boto_client.return_value = mock_bedrock_client
        
        # Mock responses
        mock_bedrock_client.invoke_agent.return_value = {
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        
        # Mock fetch for original farmer - has the interaction
        def mock_retrieve_and_generate(**kwargs):
            session_id = kwargs.get('sessionId')
            if session_id == farmer_id:
                return {
                    'output': {
                        'text': f'''{{
                            "recentInteractions": [
                                {{
                                    "question": "{question}",
                                    "advice": "{advice}",
                                    "timestamp": "{datetime.utcnow().isoformat()}"
                                }}
                            ],
                            "unresolvedIssues": [],
                            "consolidatedInsights": {{"primaryCrop": "Rice"}}
                        }}'''
                    }
                }
            else:
                # Other farmer has no interactions
                return {
                    'output': {
                        'text': '''{{
                            "recentInteractions": [],
                            "unresolvedIssues": [],
                            "consolidatedInsights": {"primaryCrop": "Unknown"}
                        }}'''
                    }
                }
        
        mock_bedrock_client.retrieve_and_generate.side_effect = mock_retrieve_and_generate
        
        # Store interaction for original farmer
        store_interaction(farmer_id, question, advice, context)
        
        # Retrieve memory for original farmer
        farmer_memory = fetch_memory(farmer_id)
        
        # Retrieve memory for different farmer
        other_memory = fetch_memory(other_farmer_id)
        
        # Property 1: Original farmer's memory contains the interaction
        assert len(farmer_memory.recentInteractions) > 0, \
            "Original farmer should have interactions"
        
        found = any(
            i.question == question and i.advice == advice
            for i in farmer_memory.recentInteractions
        )
        assert found, "Original farmer should have their interaction"
        
        # Property 2: Other farmer's memory does NOT contain the interaction
        assert len(other_memory.recentInteractions) == 0, \
            "Different farmer should not have original farmer's interactions"
        
        # Property 3: Memory is partitioned by FarmerID
        # Verify that retrieve_and_generate was called with different sessionIds
        calls = mock_bedrock_client.retrieve_and_generate.call_args_list
        session_ids = [call[1].get('sessionId') for call in calls if call[1]]
        
        assert farmer_id in session_ids, \
            f"Original farmer_id '{farmer_id}' should be used as sessionId"
        assert other_farmer_id in session_ids, \
            f"Other farmer_id '{other_farmer_id}' should be used as sessionId"


@given(
    farmer_id=farmer_id_strategy(),
    question=question_strategy(),
    advice=advice_strategy(),
    context=context_data_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_memory_persistence_handles_storage_failure_gracefully(farmer_id, question, advice, context):
    """
    Test that storage failures are handled gracefully without crashing.
    
    Verifies that:
    1. Storage failures don't raise exceptions
    2. System continues to operate
    3. Errors are logged but don't block the request
    
    **Validates: Requirements 2.1, 2.3, 9.5**
    """
    with patch('src.context.memory.boto3.client') as mock_boto_client, \
         patch('src.context.memory.Config') as mock_config:
        
        # Configure Config mock
        mock_config.AGENTCORE_MEMORY_ID = 'test-memory-id'
        mock_config.AGENTCORE_AGENT_ID = 'test-agent-id'
        mock_config.AGENTCORE_ALIAS_ID = 'test-alias-id'
        mock_config.AWS_REGION = 'us-east-1'
        
        mock_bedrock_client = MagicMock()
        mock_boto_client.return_value = mock_bedrock_client
        
        # Mock storage failure
        from botocore.exceptions import ClientError
        mock_bedrock_client.invoke_agent.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'invoke_agent'
        )
        
        # Property 1: Storage failure should not raise exception
        try:
            store_interaction(farmer_id, question, advice, context)
            # Should complete without raising
            storage_succeeded = True
        except Exception as e:
            storage_succeeded = False
            pytest.fail(f"store_interaction should handle errors gracefully, but raised: {e}")
        
        assert storage_succeeded, \
            "store_interaction should handle storage failures gracefully"


@given(
    farmer_id=farmer_id_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_memory_persistence_handles_retrieval_failure_gracefully(farmer_id):
    """
    Test that retrieval failures return empty memory gracefully.
    
    Verifies that:
    1. Retrieval failures don't raise exceptions
    2. Empty MemoryContext is returned
    3. System can continue with degraded functionality
    
    **Validates: Requirements 2.1, 2.3, 9.5**
    """
    with patch('src.context.memory.boto3.client') as mock_boto_client, \
         patch('src.context.memory.Config') as mock_config:
        
        # Configure Config mock
        mock_config.AGENTCORE_MEMORY_ID = 'test-memory-id'
        mock_config.AWS_REGION = 'us-east-1'
        mock_config.CLAUDE_MODEL_ARN = 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0'
        
        mock_bedrock_client = MagicMock()
        mock_boto_client.return_value = mock_bedrock_client
        
        # Mock retrieval failure
        from botocore.exceptions import ClientError
        mock_bedrock_client.retrieve_and_generate.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'retrieve_and_generate'
        )
        
        # Property 1: Retrieval failure should not raise exception
        try:
            memory = fetch_memory(farmer_id)
            retrieval_succeeded = True
        except Exception as e:
            retrieval_succeeded = False
            pytest.fail(f"fetch_memory should handle errors gracefully, but raised: {e}")
        
        assert retrieval_succeeded, \
            "fetch_memory should handle retrieval failures gracefully"
        
        # Property 2: Should return valid MemoryContext (possibly empty)
        assert memory is not None, \
            "fetch_memory should return MemoryContext even on failure"
        
        assert isinstance(memory, MemoryContext), \
            "fetch_memory should return MemoryContext instance on failure"


@given(
    farmer_id=farmer_id_strategy(),
    num_interactions=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=30, deadline=None)
@pytest.mark.pbt
def test_memory_persistence_multiple_interactions(farmer_id, num_interactions):
    """
    Test that multiple interactions are stored and retrieved correctly.
    
    Verifies that:
    1. Multiple interactions can be stored sequentially
    2. All interactions are preserved in memory
    3. Interactions are retrieved in order
    
    **Validates: Requirements 2.1, 2.3, 11.7**
    """
    # Generate multiple interactions
    interactions = []
    for i in range(num_interactions):
        interactions.append({
            'question': f"Question {i}: How do I manage my crop?",
            'advice': f"Advice {i}: Follow these steps for your crop.",
            'context': ContextData(
                weather=WeatherData(
                    current=CurrentWeather(
                        temperature=25.0 + i,
                        humidity=60.0,
                        windSpeed=10.0,
                        precipitation=0.0
                    ),
                    forecast6h=Forecast6h(
                        precipitationProbability=30.0,
                        expectedRainfall=0.0,
                        temperature=27.0,
                        windSpeed=12.0
                    ),
                    timestamp=datetime.utcnow().isoformat()
                ),
                landRecords=None,
                memory=MemoryContext()
            )
        })
    
    with patch('src.context.memory.boto3.client') as mock_boto_client, \
         patch('src.context.memory.Config') as mock_config:
        
        # Configure Config mock
        mock_config.AGENTCORE_MEMORY_ID = 'test-memory-id'
        mock_config.AGENTCORE_AGENT_ID = 'test-agent-id'
        mock_config.AGENTCORE_ALIAS_ID = 'test-alias-id'
        mock_config.AWS_REGION = 'us-east-1'
        mock_config.CLAUDE_MODEL_ARN = 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0'
        
        mock_bedrock_client = MagicMock()
        mock_boto_client.return_value = mock_bedrock_client
        
        # Mock storage
        mock_bedrock_client.invoke_agent.return_value = {
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        
        # Mock retrieval - return all stored interactions
        interactions_json = ',\n'.join([
            f'''{{
                "question": "{inter['question']}",
                "advice": "{inter['advice']}",
                "timestamp": "{datetime.utcnow().isoformat()}"
            }}'''
            for inter in interactions
        ])
        
        mock_bedrock_client.retrieve_and_generate.return_value = {
            'output': {
                'text': f'''{{
                    "recentInteractions": [{interactions_json}],
                    "unresolvedIssues": [],
                    "consolidatedInsights": {{"primaryCrop": "Rice"}}
                }}'''
            }
        }
        
        # Store all interactions
        for inter in interactions:
            store_interaction(
                farmer_id,
                inter['question'],
                inter['advice'],
                inter['context']
            )
        
        # Verify all were stored
        assert mock_bedrock_client.invoke_agent.call_count == num_interactions, \
            f"Should store {num_interactions} interactions"
        
        # Retrieve memory
        memory = fetch_memory(farmer_id)
        
        # Property 1: All interactions should be present
        assert len(memory.recentInteractions) == num_interactions, \
            f"Should retrieve {num_interactions} interactions, got {len(memory.recentInteractions)}"
        
        # Property 2: All questions should be present
        retrieved_questions = [i.question for i in memory.recentInteractions]
        expected_questions = [i['question'] for i in interactions]
        
        for expected_q in expected_questions:
            assert expected_q in retrieved_questions, \
                f"Question '{expected_q}' should be in retrieved memory"


# Unit tests for specific scenarios

def test_memory_persistence_with_complete_context():
    """Test memory persistence with full context data."""
    farmer_id = "FARMER-TEST-001"
    question = "How do I control pests?"
    advice = "Apply organic pesticide in the morning."
    
    context = ContextData(
        weather=WeatherData(
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
        ),
        landRecords=LandRecords(
            landArea=2.5,
            soilType='Clay Loam',
            currentCrop='Rice',
            cropHistory=[]
        ),
        memory=MemoryContext(
            recentInteractions=[],
            unresolvedIssues=[],
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop='Rice',
                commonConcerns=[],
                farmerName='TestFarmer'
            )
        )
    )
    
    with patch('src.context.memory.boto3.client') as mock_boto_client, \
         patch('src.context.memory.Config') as mock_config:
        
        # Configure Config mock
        mock_config.AGENTCORE_MEMORY_ID = 'test-memory-id'
        mock_config.AGENTCORE_AGENT_ID = 'test-agent-id'
        mock_config.AGENTCORE_ALIAS_ID = 'test-alias-id'
        mock_config.AWS_REGION = 'us-east-1'
        mock_config.CLAUDE_MODEL_ARN = 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0'
        
        mock_bedrock_client = MagicMock()
        mock_boto_client.return_value = mock_bedrock_client
        
        mock_bedrock_client.invoke_agent.return_value = {
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        
        mock_bedrock_client.retrieve_and_generate.return_value = {
            'output': {
                'text': f'''{{
                    "recentInteractions": [
                        {{
                            "question": "{question}",
                            "advice": "{advice}",
                            "timestamp": "{datetime.utcnow().isoformat()}"
                        }}
                    ],
                    "unresolvedIssues": [],
                    "consolidatedInsights": {{
                        "primaryCrop": "Rice",
                        "commonConcerns": [],
                        "farmerName": "TestFarmer"
                    }}
                }}'''
            }
        }
        
        # Store and retrieve
        store_interaction(farmer_id, question, advice, context)
        memory = fetch_memory(farmer_id)
        
        # Verify
        assert len(memory.recentInteractions) == 1
        assert memory.recentInteractions[0].question == question
        assert memory.recentInteractions[0].advice == advice
        assert memory.consolidatedInsights.primaryCrop == 'Rice'
        assert memory.consolidatedInsights.farmerName == 'TestFarmer'


def test_memory_persistence_without_agentcore_config():
    """Test that memory operations handle missing AgentCore configuration."""
    farmer_id = "FARMER-TEST-002"
    question = "Test question"
    advice = "Test advice"
    context = ContextData(
        weather=WeatherData(
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
            timestamp=datetime.utcnow().isoformat()
        ),
        landRecords=None,
        memory=MemoryContext()
    )
    
    with patch('src.context.memory.Config') as mock_config:
        # Simulate missing configuration
        mock_config.AGENTCORE_MEMORY_ID = None
        mock_config.AGENTCORE_AGENT_ID = None
        mock_config.AGENTCORE_ALIAS_ID = None
        
        # Should not raise exceptions
        store_interaction(farmer_id, question, advice, context)
        memory = fetch_memory(farmer_id)
        
        # Should return empty memory
        assert isinstance(memory, MemoryContext)
        assert len(memory.recentInteractions) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
