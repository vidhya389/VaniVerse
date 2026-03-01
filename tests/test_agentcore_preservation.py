"""
Preservation Property Tests for AgentCore Cross-Region Fix

These tests verify that the fix for cross-region invocation does NOT break
existing behavior for same-region invocations and graceful degradation.

IMPORTANT: These tests should PASS on UNFIXED code (baseline behavior).
After the fix, they should STILL PASS (preservation confirmed).
"""

import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError
from hypothesis import given, strategies as st, settings
from src.context.memory import fetch_memory, store_interaction
from src.models.context_data import ContextData, WeatherData, CurrentWeather, Forecast6h


class TestAgentCorePreservation:
    """
    Property 2: Preservation - Same-Region and Graceful Degradation Behavior
    
    These tests verify that existing behavior is preserved after the fix.
    They should PASS on both unfixed and fixed code.
    """
    
    @pytest.fixture
    def mock_context_data(self):
        """Create mock context data for store_interaction test"""
        return ContextData(
            weather=WeatherData(
                current=CurrentWeather(
                    temperature=25.0,
                    humidity=60,
                    windSpeed=10.0,
                    precipitation=0.0,
                    description="Clear sky"
                ),
                forecast6h=Forecast6h(
                    temperature=26.0,
                    precipitationProbability=10,
                    expectedRainfall=0.0,
                    windSpeed=12.0
                ),
                forecast24h=Forecast6h(
                    temperature=28.0,
                    precipitationProbability=20,
                    expectedRainfall=2.0,
                    windSpeed=15.0
                )
            )
        )
    
    def test_same_region_fetch_memory_works(self):
        """
        Preservation: Same-region invocations should continue to work.
        
        When AGENTCORE_REGION == AWS_REGION (both ap-south-1), the system
        should successfully invoke the agent.
        
        This test should PASS on unfixed code and PASS on fixed code.
        """
        with patch('src.context.memory.Config') as mock_config:
            mock_config.AGENTCORE_AGENT_ID = 'TEST_AGENT_ID'
            mock_config.AGENTCORE_ALIAS_ID = 'TEST_ALIAS_ID'
            mock_config.AGENTCORE_REGION = 'ap-south-1'  # Same region
            mock_config.AWS_REGION = 'ap-south-1'  # Same region
            
            with patch('src.context.memory.boto3.client') as mock_boto3_client:
                mock_bedrock_agent_runtime = MagicMock()
                mock_boto3_client.return_value = mock_bedrock_agent_runtime
                
                # Simulate successful response
                mock_response = {
                    'completion': [
                        {
                            'chunk': {
                                'bytes': b'{"recentInteractions": [], "unresolvedIssues": []}'
                            }
                        }
                    ]
                }
                mock_bedrock_agent_runtime.invoke_agent.return_value = mock_response
                
                # Call fetch_memory
                result = fetch_memory('FARMER_TEST_123')
                
                # Verify successful invocation
                mock_boto3_client.assert_called_with(
                    'bedrock-agent-runtime',
                    region_name='ap-south-1'
                )
                mock_bedrock_agent_runtime.invoke_agent.assert_called_once()
                
                # Verify result is not empty
                assert result is not None
                assert hasattr(result, 'recentInteractions')
    
    def test_same_region_store_interaction_works(self, mock_context_data):
        """
        Preservation: Same-region store_interaction should continue to work.
        """
        with patch('src.context.memory.Config') as mock_config:
            mock_config.AGENTCORE_AGENT_ID = 'TEST_AGENT_ID'
            mock_config.AGENTCORE_ALIAS_ID = 'TEST_ALIAS_ID'
            mock_config.AGENTCORE_REGION = 'ap-south-1'
            mock_config.AWS_REGION = 'ap-south-1'
            
            with patch('src.context.memory.boto3.client') as mock_boto3_client:
                mock_bedrock_agent_runtime = MagicMock()
                mock_boto3_client.return_value = mock_bedrock_agent_runtime
                
                # Simulate successful response
                mock_response = {'completion': []}
                mock_bedrock_agent_runtime.invoke_agent.return_value = mock_response
                
                # Call store_interaction
                store_interaction(
                    farmer_id='FARMER_TEST_123',
                    question='Test question',
                    advice='Test advice',
                    context=mock_context_data
                )
                
                # Verify successful invocation
                mock_boto3_client.assert_called_with(
                    'bedrock-agent-runtime',
                    region_name='ap-south-1'
                )
                mock_bedrock_agent_runtime.invoke_agent.assert_called_once()
    
    def test_missing_agent_id_returns_empty_memory(self):
        """
        Preservation: Missing AGENTCORE_AGENT_ID should return empty memory gracefully.
        
        This is the graceful degradation behavior that must be preserved.
        """
        with patch('src.context.memory.Config') as mock_config:
            mock_config.AGENTCORE_AGENT_ID = None  # Missing!
            mock_config.AGENTCORE_ALIAS_ID = 'TEST_ALIAS_ID'
            mock_config.AGENTCORE_REGION = 'ap-south-1'
            mock_config.AWS_REGION = 'ap-south-1'
            
            # Call fetch_memory - should not call boto3
            result = fetch_memory('FARMER_TEST_123')
            
            # Verify empty memory returned
            assert result is not None
            assert hasattr(result, 'recentInteractions')
            assert len(result.recentInteractions) == 0
    
    def test_missing_alias_id_returns_empty_memory(self):
        """
        Preservation: Missing AGENTCORE_ALIAS_ID should return empty memory gracefully.
        """
        with patch('src.context.memory.Config') as mock_config:
            mock_config.AGENTCORE_AGENT_ID = 'TEST_AGENT_ID'
            mock_config.AGENTCORE_ALIAS_ID = None  # Missing!
            mock_config.AGENTCORE_REGION = 'ap-south-1'
            mock_config.AWS_REGION = 'ap-south-1'
            
            # Call fetch_memory - should not call boto3
            result = fetch_memory('FARMER_TEST_123')
            
            # Verify empty memory returned
            assert result is not None
            assert hasattr(result, 'recentInteractions')
            assert len(result.recentInteractions) == 0
    
    def test_network_error_returns_empty_memory(self):
        """
        Preservation: Network errors should be handled gracefully.
        
        The system should return empty memory on network errors, not crash.
        """
        with patch('src.context.memory.Config') as mock_config:
            mock_config.AGENTCORE_AGENT_ID = 'TEST_AGENT_ID'
            mock_config.AGENTCORE_ALIAS_ID = 'TEST_ALIAS_ID'
            mock_config.AGENTCORE_REGION = 'ap-south-1'
            mock_config.AWS_REGION = 'ap-south-1'
            
            with patch('src.context.memory.boto3.client') as mock_boto3_client:
                mock_bedrock_agent_runtime = MagicMock()
                mock_boto3_client.return_value = mock_bedrock_agent_runtime
                
                # Simulate network error
                mock_bedrock_agent_runtime.invoke_agent.side_effect = ClientError(
                    error_response={
                        'Error': {
                            'Code': 'ServiceUnavailable',
                            'Message': 'Service temporarily unavailable'
                        }
                    },
                    operation_name='InvokeAgent'
                )
                
                # Call fetch_memory - should not crash
                result = fetch_memory('FARMER_TEST_123')
                
                # Verify empty memory returned (graceful degradation)
                assert result is not None
                assert hasattr(result, 'recentInteractions')
                assert len(result.recentInteractions) == 0
    
    def test_store_interaction_network_error_does_not_crash(self, mock_context_data):
        """
        Preservation: store_interaction should not crash on network errors.
        """
        with patch('src.context.memory.Config') as mock_config:
            mock_config.AGENTCORE_AGENT_ID = 'TEST_AGENT_ID'
            mock_config.AGENTCORE_ALIAS_ID = 'TEST_ALIAS_ID'
            mock_config.AGENTCORE_REGION = 'ap-south-1'
            mock_config.AWS_REGION = 'ap-south-1'
            
            with patch('src.context.memory.boto3.client') as mock_boto3_client:
                mock_bedrock_agent_runtime = MagicMock()
                mock_boto3_client.return_value = mock_bedrock_agent_runtime
                
                # Simulate network error
                mock_bedrock_agent_runtime.invoke_agent.side_effect = ClientError(
                    error_response={
                        'Error': {
                            'Code': 'ServiceUnavailable',
                            'Message': 'Service temporarily unavailable'
                        }
                    },
                    operation_name='InvokeAgent'
                )
                
                # Call store_interaction - should not crash
                # This should complete without raising an exception
                store_interaction(
                    farmer_id='FARMER_TEST_123',
                    question='Test question',
                    advice='Test advice',
                    context=mock_context_data
                )
                
                # If we get here, the test passed (no exception raised)
                assert True


class TestAgentCorePreservationPropertyBased:
    """
    Property-based tests for preservation using Hypothesis.
    
    These tests generate many test cases to provide stronger guarantees
    that behavior is unchanged for all non-buggy inputs.
    """
    
    @given(
        farmer_id=st.text(min_size=1, max_size=50),
        region=st.sampled_from(['ap-south-1', 'us-east-1', 'eu-west-1', 'us-west-2'])
    )
    @settings(max_examples=20, deadline=None)
    def test_same_region_always_works(self, farmer_id, region):
        """
        Property: For any farmer_id and region, same-region invocation should work.
        
        This property-based test generates many combinations to verify
        same-region behavior is preserved across all inputs.
        """
        with patch('src.context.memory.Config') as mock_config:
            mock_config.AGENTCORE_AGENT_ID = 'TEST_AGENT_ID'
            mock_config.AGENTCORE_ALIAS_ID = 'TEST_ALIAS_ID'
            mock_config.AGENTCORE_REGION = region  # Same region
            mock_config.AWS_REGION = region  # Same region
            
            with patch('src.context.memory.boto3.client') as mock_boto3_client:
                mock_bedrock_agent_runtime = MagicMock()
                mock_boto3_client.return_value = mock_bedrock_agent_runtime
                
                # Simulate successful response
                mock_response = {
                    'completion': [
                        {
                            'chunk': {
                                'bytes': b'{"recentInteractions": [], "unresolvedIssues": []}'
                            }
                        }
                    ]
                }
                mock_bedrock_agent_runtime.invoke_agent.return_value = mock_response
                
                # Call fetch_memory
                result = fetch_memory(farmer_id)
                
                # Verify successful invocation
                mock_boto3_client.assert_called_with(
                    'bedrock-agent-runtime',
                    region_name=region
                )
                
                # Verify result is not empty
                assert result is not None
                assert hasattr(result, 'recentInteractions')
    
    @given(
        farmer_id=st.text(min_size=1, max_size=50),
        error_code=st.sampled_from([
            'ServiceUnavailable',
            'ThrottlingException',
            'InternalServerError',
            'ResourceNotFoundException'
        ])
    )
    @settings(max_examples=20, deadline=None)
    def test_all_errors_handled_gracefully(self, farmer_id, error_code):
        """
        Property: For any error type, the system should handle it gracefully.
        
        This verifies that all error scenarios return empty memory rather
        than crashing the entire request.
        """
        with patch('src.context.memory.Config') as mock_config:
            mock_config.AGENTCORE_AGENT_ID = 'TEST_AGENT_ID'
            mock_config.AGENTCORE_ALIAS_ID = 'TEST_ALIAS_ID'
            mock_config.AGENTCORE_REGION = 'ap-south-1'
            mock_config.AWS_REGION = 'ap-south-1'
            
            with patch('src.context.memory.boto3.client') as mock_boto3_client:
                mock_bedrock_agent_runtime = MagicMock()
                mock_boto3_client.return_value = mock_bedrock_agent_runtime
                
                # Simulate error
                mock_bedrock_agent_runtime.invoke_agent.side_effect = ClientError(
                    error_response={
                        'Error': {
                            'Code': error_code,
                            'Message': f'Test error: {error_code}'
                        }
                    },
                    operation_name='InvokeAgent'
                )
                
                # Call fetch_memory - should not crash
                result = fetch_memory(farmer_id)
                
                # Verify empty memory returned (graceful degradation)
                assert result is not None
                assert hasattr(result, 'recentInteractions')
                assert len(result.recentInteractions) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
