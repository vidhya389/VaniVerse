"""
Tests for Memory-First prompt construction.

Tests the build_memory_first_prompt function and related formatting utilities.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError, ReadTimeoutError
from hypothesis import given, strategies as st, settings
from src.prompting.builder import (
    build_memory_first_prompt,
    format_prompt_for_bedrock,
    invoke_bedrock,
    _format_weather_context,
    _format_land_context,
    _format_memory_context
)
from src.models.context_data import (
    ContextData,
    WeatherData,
    CurrentWeather,
    Forecast6h,
    LandRecords,
    MemoryContext,
    UnresolvedIssue,
    Interaction,
    ConsolidatedInsights,
    CropHistory
)
from src.models.prompts import MemoryFirstPrompt


# Fixtures

@pytest.fixture
def sample_weather():
    """Sample weather data."""
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
        ),
        timestamp=datetime.utcnow().isoformat()
    )


@pytest.fixture
def sample_land_records():
    """Sample land records."""
    return LandRecords(
        landArea=2.5,
        soilType="Clay Loam",
        currentCrop="Rice",
        cropHistory=[
            CropHistory(crop="Wheat", season="Rabi", year=2023),
            CropHistory(crop="Rice", season="Kharif", year=2023)
        ]
    )


@pytest.fixture
def sample_memory_with_issues():
    """Sample memory context with unresolved issues."""
    return MemoryContext(
        recentInteractions=[
            Interaction(
                question="How do I treat leaf curl on tomatoes?",
                advice="Apply neem oil spray...",
                timestamp=(datetime.utcnow() - timedelta(days=7)).isoformat()
            )
        ],
        unresolvedIssues=[
            UnresolvedIssue(
                issue="Leaf curl on tomato plants",
                crop="Tomato",
                reportedDate=(datetime.utcnow() - timedelta(days=7)).isoformat(),
                daysSinceReport=7
            )
        ],
        consolidatedInsights=ConsolidatedInsights(
            primaryCrop="Rice",
            commonConcerns=["pest management", "irrigation timing"],
            farmerName="Ramesh"
        )
    )


@pytest.fixture
def sample_memory_empty():
    """Sample empty memory context for first-time user."""
    return MemoryContext(
        recentInteractions=[],
        unresolvedIssues=[],
        consolidatedInsights=ConsolidatedInsights(
            primaryCrop="Unknown",
            commonConcerns=[],
            farmerName=None
        )
    )


@pytest.fixture
def sample_context(sample_weather, sample_land_records, sample_memory_with_issues):
    """Sample complete context data."""
    return ContextData(
        weather=sample_weather,
        landRecords=sample_land_records,
        memory=sample_memory_with_issues
    )


@pytest.fixture
def sample_agent_outputs():
    """Sample agent outputs."""
    return {
        'weather_analysis': """
Current Conditions Summary:
- Temperature is moderate at 32.5°C
- Humidity at 65% is suitable for most activities
- Wind speed is low at 12.5 km/h

Risk Assessment:
- Spraying: MEDIUM risk (35% rain probability in 6h)
- Irrigation: LOW risk
- Harvesting: LOW risk

Timing Recommendations:
- If spraying, do it within next 2-3 hours before rain probability increases
- Irrigation can be done anytime, but early morning preferred
""",
        'icar_knowledge': """
Relevant ICAR Guidelines:
- For rice crop at current growth stage, monitor for stem borer and leaf folder
- Apply recommended NPK fertilizer based on soil test
- Maintain 2-3 inches water level during vegetative stage

Crop-Specific Recommendations:
- Clay loam soil is ideal for rice cultivation
- Ensure proper drainage to prevent waterlogging
- Monitor for blast disease in humid conditions

Source Citations:
- ICAR Rice Production Guidelines 2023
- Soil Management Handbook for Clay Loam
"""
    }


# Unit Tests

class TestBuildMemoryFirstPrompt:
    """Tests for build_memory_first_prompt function."""
    
    def test_basic_prompt_construction(self, sample_context, sample_agent_outputs):
        """Test basic prompt construction with all inputs."""
        question = "When should I apply fertilizer to my rice crop?"
        
        prompt = build_memory_first_prompt(
            question=question,
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        # Verify prompt structure
        assert isinstance(prompt, MemoryFirstPrompt)
        assert prompt.currentQuestion == question
        assert prompt.context == sample_context
        assert 'weather_analysis' in prompt.agentOutputs
        assert 'icar_knowledge' in prompt.agentOutputs
    
    def test_system_prompt_includes_memory_first_priority(self, sample_context, sample_agent_outputs):
        """Test that system prompt includes Memory-First priority instructions."""
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        # Verify Memory-First instructions are present
        assert "MEMORY-FIRST PRIORITY" in prompt.systemPrompt
        assert "unresolved issues" in prompt.systemPrompt.lower()
        assert "BEFORE answering" in prompt.systemPrompt
    
    def test_system_prompt_includes_provenance_requirements(self, sample_context, sample_agent_outputs):
        """Test that system prompt includes advice provenance requirements."""
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        # Verify provenance requirements
        assert "ADVICE PROVENANCE" in prompt.systemPrompt
        assert "explain WHY" in prompt.systemPrompt
        assert "specific context factors" in prompt.systemPrompt.lower()
        assert "at least one provenance statement" in prompt.systemPrompt.lower()
    
    def test_system_prompt_includes_agent_outputs(self, sample_context, sample_agent_outputs):
        """Test that system prompt includes specialized agent outputs."""
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        # Verify agent outputs are included
        assert "Weather Analysis" in prompt.systemPrompt
        assert "ICAR Knowledge" in prompt.systemPrompt
        assert sample_agent_outputs['weather_analysis'] in prompt.systemPrompt
        assert sample_agent_outputs['icar_knowledge'] in prompt.systemPrompt
    
    def test_system_prompt_includes_weather_context(self, sample_context, sample_agent_outputs):
        """Test that system prompt includes formatted weather context."""
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        # Verify weather context
        assert "32.5°C" in prompt.systemPrompt
        assert "65.0% humidity" in prompt.systemPrompt
        assert "35.0% rain probability" in prompt.systemPrompt
    
    def test_system_prompt_includes_land_context(self, sample_context, sample_agent_outputs):
        """Test that system prompt includes formatted land context."""
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        # Verify land context
        assert "2.5 hectares" in prompt.systemPrompt
        assert "Clay Loam" in prompt.systemPrompt
        assert "Rice" in prompt.systemPrompt
    
    def test_system_prompt_includes_unresolved_issues(self, sample_context, sample_agent_outputs):
        """Test that system prompt highlights unresolved issues."""
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        # Verify unresolved issues are highlighted
        assert "UNRESOLVED ISSUES" in prompt.systemPrompt
        assert "Leaf curl on tomato plants" in prompt.systemPrompt
        assert "7 days ago" in prompt.systemPrompt
    
    def test_prompt_with_no_land_records(self, sample_weather, sample_memory_empty, sample_agent_outputs):
        """Test prompt construction when land records are not available."""
        context = ContextData(
            weather=sample_weather,
            landRecords=None,
            memory=sample_memory_empty
        )
        
        prompt = build_memory_first_prompt(
            question="Test question",
            context=context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        # Verify handling of missing land records
        assert "No land records available" in prompt.systemPrompt
        assert "not linked to AgriStack" in prompt.systemPrompt
    
    def test_prompt_with_empty_memory(self, sample_weather, sample_land_records, sample_memory_empty, sample_agent_outputs):
        """Test prompt construction for first-time user with no memory."""
        context = ContextData(
            weather=sample_weather,
            landRecords=sample_land_records,
            memory=sample_memory_empty
        )
        
        prompt = build_memory_first_prompt(
            question="Test question",
            context=context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        # Verify handling of empty memory
        assert "first-time user" in prompt.systemPrompt.lower()
        assert "Unresolved Issues: None" in prompt.systemPrompt


class TestFormatPromptForBedrock:
    """Tests for format_prompt_for_bedrock function."""
    
    def test_bedrock_format_structure(self, sample_context, sample_agent_outputs):
        """Test that Bedrock format has correct structure."""
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        bedrock_request = format_prompt_for_bedrock(prompt)
        
        # Verify structure
        assert 'anthropic_version' in bedrock_request
        assert 'max_tokens' in bedrock_request
        assert 'system' in bedrock_request
        assert 'messages' in bedrock_request
        assert bedrock_request['anthropic_version'] == 'bedrock-2023-05-31'
        assert bedrock_request['max_tokens'] == 1000
    
    def test_bedrock_format_includes_system_prompt(self, sample_context, sample_agent_outputs):
        """Test that Bedrock format includes the system prompt."""
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        bedrock_request = format_prompt_for_bedrock(prompt)
        
        assert bedrock_request['system'] == prompt.systemPrompt
    
    def test_bedrock_format_includes_question(self, sample_context, sample_agent_outputs):
        """Test that Bedrock format includes the farmer's question."""
        question = "When should I harvest my rice crop?"
        prompt = build_memory_first_prompt(
            question=question,
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        bedrock_request = format_prompt_for_bedrock(prompt)
        
        # Verify question is in user message
        user_message = bedrock_request['messages'][0]['content']
        assert question in user_message
    
    def test_bedrock_format_includes_context_json(self, sample_context, sample_agent_outputs):
        """Test that Bedrock format includes context as JSON."""
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        bedrock_request = format_prompt_for_bedrock(prompt)
        
        # Verify context is serialized in user message
        user_message = bedrock_request['messages'][0]['content']
        assert "Context Data:" in user_message
        # Should be able to find JSON-serialized context elements
        assert '"temperature": 32.5' in user_message or '"temperature":32.5' in user_message


class TestFormatWeatherContext:
    """Tests for _format_weather_context function."""
    
    def test_format_weather_includes_current_conditions(self, sample_weather):
        """Test that weather formatting includes current conditions."""
        formatted = _format_weather_context(sample_weather)
        
        assert "32.5°C" in formatted
        assert "65.0% humidity" in formatted
        assert "12.5 km/h wind" in formatted
    
    def test_format_weather_includes_forecast(self, sample_weather):
        """Test that weather formatting includes 6h forecast."""
        formatted = _format_weather_context(sample_weather)
        
        assert "35.0% rain probability" in formatted
        assert "2.5mm expected rainfall" in formatted
        assert "30.0°C" in formatted


class TestFormatLandContext:
    """Tests for _format_land_context function."""
    
    def test_format_land_with_records(self, sample_land_records):
        """Test land formatting with complete records."""
        formatted = _format_land_context(sample_land_records)
        
        assert "2.5 hectares" in formatted
        assert "Clay Loam" in formatted
        assert "Rice" in formatted
        assert "Wheat" in formatted
    
    def test_format_land_without_records(self):
        """Test land formatting when no records available."""
        formatted = _format_land_context(None)
        
        assert "No land records available" in formatted
        assert "not linked to AgriStack" in formatted


class TestFormatMemoryContext:
    """Tests for _format_memory_context function."""
    
    def test_format_memory_with_issues(self, sample_memory_with_issues):
        """Test memory formatting with unresolved issues."""
        formatted = _format_memory_context(sample_memory_with_issues)
        
        assert "UNRESOLVED ISSUES" in formatted
        assert "Leaf curl on tomato plants" in formatted
        assert "7 days ago" in formatted
        assert "Ramesh" in formatted
        assert "Rice" in formatted
    
    def test_format_memory_empty(self, sample_memory_empty):
        """Test memory formatting for first-time user."""
        formatted = _format_memory_context(sample_memory_empty)
        
        assert "first-time user" in formatted.lower()
        assert "Unresolved Issues: None" in formatted
        assert "Unknown" in formatted


# Edge Cases

class TestEdgeCases:
    """Tests for edge cases and error conditions."""
    
    def test_very_long_question(self, sample_context, sample_agent_outputs):
        """Test handling of very long farmer questions."""
        long_question = "How do I " + "manage my crops " * 100  # Very long question
        
        prompt = build_memory_first_prompt(
            question=long_question,
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        assert prompt.currentQuestion == long_question
    
    def test_empty_agent_outputs(self, sample_context):
        """Test handling of empty agent outputs."""
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis="",
            icar_knowledge=""
        )
        
        # Should still create valid prompt
        assert isinstance(prompt, MemoryFirstPrompt)
        assert "MEMORY-FIRST PRIORITY" in prompt.systemPrompt
    
    def test_multiple_unresolved_issues(self, sample_weather, sample_land_records, sample_agent_outputs):
        """Test handling of multiple unresolved issues."""
        memory = MemoryContext(
            recentInteractions=[],
            unresolvedIssues=[
                UnresolvedIssue(
                    issue="Leaf curl on tomatoes",
                    crop="Tomato",
                    reportedDate=(datetime.utcnow() - timedelta(days=7)).isoformat(),
                    daysSinceReport=7
                ),
                UnresolvedIssue(
                    issue="Stem borer in rice",
                    crop="Rice",
                    reportedDate=(datetime.utcnow() - timedelta(days=10)).isoformat(),
                    daysSinceReport=10
                ),
                UnresolvedIssue(
                    issue="Yellowing leaves on wheat",
                    crop="Wheat",
                    reportedDate=(datetime.utcnow() - timedelta(days=5)).isoformat(),
                    daysSinceReport=5
                )
            ],
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop="Rice",
                commonConcerns=[],
                farmerName=None
            )
        )
        
        context = ContextData(
            weather=sample_weather,
            landRecords=sample_land_records,
            memory=memory
        )
        
        prompt = build_memory_first_prompt(
            question="Test question",
            context=context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        # All issues should be mentioned
        assert "Leaf curl on tomatoes" in prompt.systemPrompt
        assert "Stem borer in rice" in prompt.systemPrompt
        assert "Yellowing leaves on wheat" in prompt.systemPrompt
        assert "UNRESOLVED ISSUES (3)" in prompt.systemPrompt



class TestInvokeBedrock:
    """Tests for invoke_bedrock function."""
    
    @patch('boto3.client')
    def test_successful_invocation(self, mock_boto_client, sample_context, sample_agent_outputs):
        """Test successful Bedrock invocation with valid response."""
        # Setup mock response
        mock_bedrock = Mock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [
                {
                    'text': 'This is agricultural advice from Claude.'
                }
            ]
        }).encode('utf-8')
        
        mock_bedrock.invoke_model.return_value = mock_response
        
        # Create prompt
        prompt = build_memory_first_prompt(
            question="When should I apply fertilizer?",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        # Invoke Bedrock
        advice = invoke_bedrock(prompt)
        
        # Verify
        assert advice == 'This is agricultural advice from Claude.'
        mock_bedrock.invoke_model.assert_called_once()
        
        # Verify model ID
        call_args = mock_bedrock.invoke_model.call_args
        assert call_args[1]['modelId'] == 'anthropic.claude-3-5-sonnet-20241022-v2:0'
    
    @patch('boto3.client')
    def test_invocation_with_custom_timeout(self, mock_boto_client, sample_context, sample_agent_outputs):
        """Test Bedrock invocation with custom timeout."""
        mock_bedrock = Mock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Advice text'}]
        }).encode('utf-8')
        
        mock_bedrock.invoke_model.return_value = mock_response
        
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        # Invoke with custom timeout
        advice = invoke_bedrock(prompt, timeout=60)
        
        assert advice == 'Advice text'
    
    @patch('boto3.client')
    def test_empty_content_blocks_raises_error(self, mock_boto_client, sample_context, sample_agent_outputs):
        """Test that empty content blocks raise ValueError."""
        mock_bedrock = Mock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': []
        }).encode('utf-8')
        
        mock_bedrock.invoke_model.return_value = mock_response
        
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        with pytest.raises(ValueError, match="empty content blocks"):
            invoke_bedrock(prompt)
    
    @patch('boto3.client')
    def test_missing_content_field_raises_error(self, mock_boto_client, sample_context, sample_agent_outputs):
        """Test that missing content field raises ValueError."""
        mock_bedrock = Mock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'id': 'msg_123',
            'type': 'message'
        }).encode('utf-8')
        
        mock_bedrock.invoke_model.return_value = mock_response
        
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        with pytest.raises(ValueError, match="missing 'content' field"):
            invoke_bedrock(prompt)
    
    @patch('boto3.client')
    def test_empty_advice_text_raises_error(self, mock_boto_client, sample_context, sample_agent_outputs):
        """Test that empty advice text raises ValueError."""
        mock_bedrock = Mock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': '   '}]  # Only whitespace
        }).encode('utf-8')
        
        mock_bedrock.invoke_model.return_value = mock_response
        
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        with pytest.raises(ValueError, match="empty advice text"):
            invoke_bedrock(prompt)
    
    @patch('boto3.client')
    def test_timeout_error_handling(self, mock_boto_client, sample_context, sample_agent_outputs):
        """Test handling of timeout errors."""
        mock_bedrock = Mock()
        mock_boto_client.return_value = mock_bedrock
        
        # Simulate timeout
        mock_bedrock.invoke_model.side_effect = ReadTimeoutError(
            endpoint_url='https://bedrock.amazonaws.com'
        )
        
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        with pytest.raises(TimeoutError, match="timed out after"):
            invoke_bedrock(prompt)
    
    @patch('boto3.client')
    def test_throttling_exception_handling(self, mock_boto_client, sample_context, sample_agent_outputs):
        """Test handling of throttling exceptions."""
        mock_bedrock = Mock()
        mock_boto_client.return_value = mock_bedrock
        
        # Simulate throttling
        error_response = {
            'Error': {
                'Code': 'ThrottlingException',
                'Message': 'Rate exceeded'
            }
        }
        mock_bedrock.invoke_model.side_effect = ClientError(error_response, 'InvokeModel')
        
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        with pytest.raises(RuntimeError, match="rate limit exceeded"):
            invoke_bedrock(prompt)
    
    @patch('boto3.client')
    def test_model_not_ready_exception_handling(self, mock_boto_client, sample_context, sample_agent_outputs):
        """Test handling of model not ready exceptions."""
        mock_bedrock = Mock()
        mock_boto_client.return_value = mock_bedrock
        
        error_response = {
            'Error': {
                'Code': 'ModelNotReadyException',
                'Message': 'Model is loading'
            }
        }
        mock_bedrock.invoke_model.side_effect = ClientError(error_response, 'InvokeModel')
        
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        with pytest.raises(RuntimeError, match="not ready"):
            invoke_bedrock(prompt)
    
    @patch('boto3.client')
    def test_validation_exception_handling(self, mock_boto_client, sample_context, sample_agent_outputs):
        """Test handling of validation exceptions."""
        mock_bedrock = Mock()
        mock_boto_client.return_value = mock_bedrock
        
        error_response = {
            'Error': {
                'Code': 'ValidationException',
                'Message': 'Invalid request format'
            }
        }
        mock_bedrock.invoke_model.side_effect = ClientError(error_response, 'InvokeModel')
        
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        with pytest.raises(ValueError, match="Invalid request"):
            invoke_bedrock(prompt)
    
    @patch('boto3.client')
    def test_access_denied_exception_handling(self, mock_boto_client, sample_context, sample_agent_outputs):
        """Test handling of access denied exceptions."""
        mock_bedrock = Mock()
        mock_boto_client.return_value = mock_bedrock
        
        error_response = {
            'Error': {
                'Code': 'AccessDeniedException',
                'Message': 'Insufficient permissions'
            }
        }
        mock_bedrock.invoke_model.side_effect = ClientError(error_response, 'InvokeModel')
        
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        with pytest.raises(RuntimeError, match="Access denied"):
            invoke_bedrock(prompt)
    
    @patch('boto3.client')
    def test_generic_client_error_handling(self, mock_boto_client, sample_context, sample_agent_outputs):
        """Test handling of generic client errors."""
        mock_bedrock = Mock()
        mock_boto_client.return_value = mock_bedrock
        
        error_response = {
            'Error': {
                'Code': 'UnknownError',
                'Message': 'Something went wrong'
            }
        }
        mock_bedrock.invoke_model.side_effect = ClientError(error_response, 'InvokeModel')
        
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        with pytest.raises(RuntimeError, match="UnknownError"):
            invoke_bedrock(prompt)
    
    @patch('boto3.client')
    def test_json_decode_error_handling(self, mock_boto_client, sample_context, sample_agent_outputs):
        """Test handling of malformed JSON responses."""
        mock_bedrock = Mock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = b'Not valid JSON'
        
        mock_bedrock.invoke_model.return_value = mock_response
        
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        with pytest.raises(ValueError, match="Failed to parse.*JSON"):
            invoke_bedrock(prompt)
    
    @patch('boto3.client')
    def test_strips_whitespace_from_advice(self, mock_boto_client, sample_context, sample_agent_outputs):
        """Test that advice text is stripped of leading/trailing whitespace."""
        mock_bedrock = Mock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [
                {
                    'text': '  \n  Agricultural advice with whitespace  \n  '
                }
            ]
        }).encode('utf-8')
        
        mock_bedrock.invoke_model.return_value = mock_response
        
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        advice = invoke_bedrock(prompt)
        
        assert advice == 'Agricultural advice with whitespace'
        assert not advice.startswith(' ')
        assert not advice.endswith(' ')
    
    @patch('boto3.client')
    def test_request_body_format(self, mock_boto_client, sample_context, sample_agent_outputs):
        """Test that request body is correctly formatted for Bedrock."""
        mock_bedrock = Mock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Advice'}]
        }).encode('utf-8')
        
        mock_bedrock.invoke_model.return_value = mock_response
        
        prompt = build_memory_first_prompt(
            question="Test question",
            context=sample_context,
            weather_analysis=sample_agent_outputs['weather_analysis'],
            icar_knowledge=sample_agent_outputs['icar_knowledge']
        )
        
        invoke_bedrock(prompt)
        
        # Verify request body structure
        call_args = mock_bedrock.invoke_model.call_args
        body_str = call_args[1]['body']
        body = json.loads(body_str)
        
        assert body['anthropic_version'] == 'bedrock-2023-05-31'
        assert body['max_tokens'] == 1000
        assert 'system' in body
        assert 'messages' in body
        assert len(body['messages']) == 1
        assert body['messages'][0]['role'] == 'user'



# Property-Based Tests

# Test data generators for property tests
@st.composite
def unresolved_issue_strategy(draw):
    """Generate valid UnresolvedIssue instances for property testing."""
    days_since = draw(st.integers(min_value=1, max_value=365))
    reported_date = (datetime.utcnow() - timedelta(days=days_since)).isoformat()
    
    # Common crop issues
    issues = [
        "Leaf curl", "Yellowing leaves", "Stem borer infestation", "Fungal infection",
        "Pest damage", "Wilting", "Root rot", "Nutrient deficiency", "Powdery mildew",
        "Aphid infestation", "Caterpillar damage", "Blight", "Rust disease"
    ]
    
    # Common crops
    crops = [
        "Rice", "Wheat", "Tomato", "Potato", "Cotton", "Sugarcane",
        "Maize", "Soybean", "Chickpea", "Onion", "Chili", "Brinjal"
    ]
    
    return UnresolvedIssue(
        issue=draw(st.sampled_from(issues)),
        crop=draw(st.sampled_from(crops)),
        reportedDate=reported_date,
        daysSinceReport=days_since
    )


@st.composite
def memory_with_issues_strategy(draw):
    """Generate MemoryContext with unresolved issues for property testing."""
    # Generate 1-5 unresolved issues
    num_issues = draw(st.integers(min_value=1, max_value=5))
    unresolved_issues = [draw(unresolved_issue_strategy()) for _ in range(num_issues)]
    
    # Generate some recent interactions
    num_interactions = draw(st.integers(min_value=0, max_value=3))
    recent_interactions = []
    for _ in range(num_interactions):
        days_ago = draw(st.integers(min_value=1, max_value=30))
        recent_interactions.append(
            Interaction(
                question=draw(st.text(min_size=10, max_size=100)),
                advice=draw(st.text(min_size=20, max_size=200)),
                timestamp=(datetime.utcnow() - timedelta(days=days_ago)).isoformat()
            )
        )
    
    # Generate consolidated insights
    crops = ["Rice", "Wheat", "Tomato", "Potato", "Cotton", "Sugarcane"]
    farmer_names = ["Ramesh", "Suresh", "Lakshmi", "Priya", "Kumar", "Devi"]
    
    consolidated_insights = ConsolidatedInsights(
        primaryCrop=draw(st.sampled_from(crops)),
        commonConcerns=draw(st.lists(st.text(min_size=5, max_size=30), min_size=0, max_size=5)),
        farmerName=draw(st.one_of(st.none(), st.sampled_from(farmer_names)))
    )
    
    return MemoryContext(
        recentInteractions=recent_interactions,
        unresolvedIssues=unresolved_issues,
        consolidatedInsights=consolidated_insights
    )


@st.composite
def context_with_issues_strategy(draw):
    """Generate ContextData with unresolved issues for property testing."""
    # Weather data
    weather = WeatherData(
        current=CurrentWeather(
            temperature=draw(st.floats(min_value=15, max_value=45, allow_nan=False, allow_infinity=False)),
            humidity=draw(st.floats(min_value=30, max_value=90, allow_nan=False, allow_infinity=False)),
            windSpeed=draw(st.floats(min_value=0, max_value=30, allow_nan=False, allow_infinity=False)),
            precipitation=draw(st.floats(min_value=0, max_value=50, allow_nan=False, allow_infinity=False))
        ),
        forecast6h=Forecast6h(
            precipitationProbability=draw(st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False)),
            expectedRainfall=draw(st.floats(min_value=0, max_value=50, allow_nan=False, allow_infinity=False)),
            temperature=draw(st.floats(min_value=15, max_value=45, allow_nan=False, allow_infinity=False)),
            windSpeed=draw(st.floats(min_value=0, max_value=30, allow_nan=False, allow_infinity=False))
        ),
        timestamp=datetime.utcnow().isoformat()
    )
    
    # Land records (optional)
    has_land_records = draw(st.booleans())
    land_records = None
    if has_land_records:
        crops = ["Rice", "Wheat", "Tomato", "Potato", "Cotton", "Sugarcane"]
        soil_types = ["Clay Loam", "Sandy", "Loamy", "Clay", "Silt Loam"]
        land_records = LandRecords(
            landArea=draw(st.floats(min_value=0.5, max_value=10, allow_nan=False, allow_infinity=False)),
            soilType=draw(st.sampled_from(soil_types)),
            currentCrop=draw(st.one_of(st.none(), st.sampled_from(crops))),
            cropHistory=[]
        )
    
    # Memory with unresolved issues
    memory = draw(memory_with_issues_strategy())
    
    return ContextData(
        weather=weather,
        landRecords=land_records,
        memory=memory
    )


@given(
    context=context_with_issues_strategy(),
    question=st.text(min_size=10, max_size=200, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po')
    ))
)
@settings(max_examples=100, deadline=None)
@pytest.mark.pbt
@patch('boto3.client')
def test_property_2_memory_first_proactive_engagement(mock_boto_client, context, question):
    """
    Feature: vaniverse, Property 2: Memory-First Proactive Engagement
    Validates: Requirements 2.2
    
    Test that for any farmer with unresolved issues, the advice includes
    follow-up questions about those issues.
    
    This property verifies that:
    1. When unresolved issues exist in memory, the system prompt includes them
    2. The system prompt explicitly instructs Claude to ask about unresolved issues FIRST
    3. The generated advice (when mocked) demonstrates the Memory-First pattern
    4. The unresolved issues are prominently featured in the context
    """
    # Setup mock Bedrock response that demonstrates Memory-First pattern
    mock_bedrock = Mock()
    mock_boto_client.return_value = mock_bedrock
    
    # Get the first unresolved issue for the mock response
    first_issue = context.memory.unresolvedIssues[0]
    
    # Create a mock response that follows Memory-First pattern
    mock_advice = f"""Before I answer your question about {question[:50]}, I want to check on something important.

How is the {first_issue.issue.lower()} issue on your {first_issue.crop.lower()} that you reported {first_issue.daysSinceReport} days ago? Has the situation improved, or do you still need help with that?

Once I know how that's going, I'll be happy to address your current question."""
    
    mock_response = {
        'body': Mock()
    }
    mock_response['body'].read.return_value = json.dumps({
        'content': [{'text': mock_advice}]
    }).encode('utf-8')
    
    mock_bedrock.invoke_model.return_value = mock_response
    
    # Sample agent outputs
    weather_analysis = "Weather analysis output"
    icar_knowledge = "ICAR knowledge output"
    
    # Build Memory-First prompt
    prompt = build_memory_first_prompt(
        question=question,
        context=context,
        weather_analysis=weather_analysis,
        icar_knowledge=icar_knowledge
    )
    
    # Property 1: System prompt must include Memory-First priority instructions
    assert "MEMORY-FIRST PRIORITY" in prompt.systemPrompt, \
        "System prompt must include Memory-First priority section"
    assert "unresolved issues" in prompt.systemPrompt.lower(), \
        "System prompt must mention unresolved issues"
    assert "BEFORE answering" in prompt.systemPrompt, \
        "System prompt must instruct to check issues BEFORE answering"
    
    # Property 2: All unresolved issues must be listed in the system prompt
    for issue in context.memory.unresolvedIssues:
        assert issue.issue in prompt.systemPrompt, \
            f"Unresolved issue '{issue.issue}' must be in system prompt"
        assert issue.crop in prompt.systemPrompt, \
            f"Crop '{issue.crop}' for unresolved issue must be in system prompt"
        assert f"{issue.daysSinceReport} days ago" in prompt.systemPrompt, \
            f"Days since report ({issue.daysSinceReport}) must be in system prompt"
    
    # Property 3: System prompt must highlight unresolved issues prominently
    assert "UNRESOLVED ISSUES" in prompt.systemPrompt, \
        "System prompt must have UNRESOLVED ISSUES section"
    assert f"UNRESOLVED ISSUES ({len(context.memory.unresolvedIssues)})" in prompt.systemPrompt, \
        "System prompt must show count of unresolved issues"
    
    # Property 4: System prompt must include example of Memory-First pattern
    assert "Before I answer that" in prompt.systemPrompt or "BEFORE answering" in prompt.systemPrompt, \
        "System prompt must include example or instruction for Memory-First pattern"
    
    # Property 5: Invoke Bedrock and verify the advice follows Memory-First pattern
    advice = invoke_bedrock(prompt)
    
    # The advice should mention at least one unresolved issue
    issue_mentioned = any(
        issue.issue.lower() in advice.lower() or issue.crop.lower() in advice.lower()
        for issue in context.memory.unresolvedIssues
    )
    
    assert issue_mentioned, \
        "Generated advice must mention at least one unresolved issue from memory"
    
    # Property 6: The advice should show proactive engagement (asking about the issue)
    # Look for question patterns that indicate follow-up
    proactive_patterns = [
        "how is", "how's", "has the", "did the", "is the", "are you still",
        "have you", "what happened", "any improvement", "any progress",
        "before i answer", "before we", "first,", "let me check"
    ]
    
    shows_proactive_engagement = any(
        pattern in advice.lower() for pattern in proactive_patterns
    )
    
    assert shows_proactive_engagement, \
        "Generated advice must show proactive engagement by asking about unresolved issues"
    
    # Verify Bedrock was called with the correct prompt
    mock_bedrock.invoke_model.assert_called_once()
    call_args = mock_bedrock.invoke_model.call_args
    assert call_args[1]['modelId'] == 'anthropic.claude-3-5-sonnet-20241022-v2:0'


# Additional unit test for Memory-First pattern with specific scenario
def test_memory_first_pattern_specific_scenario():
    """
    Unit test for Memory-First pattern with a specific realistic scenario.
    
    This complements the property test by verifying a concrete example.
    """
    # Create a specific scenario: farmer with tomato leaf curl issue from 7 days ago
    memory = MemoryContext(
        recentInteractions=[
            Interaction(
                question="My tomato plants have leaf curl. What should I do?",
                advice="Apply neem oil spray and ensure proper watering...",
                timestamp=(datetime.utcnow() - timedelta(days=7)).isoformat()
            )
        ],
        unresolvedIssues=[
            UnresolvedIssue(
                issue="Leaf curl on tomato plants",
                crop="Tomato",
                reportedDate=(datetime.utcnow() - timedelta(days=7)).isoformat(),
                daysSinceReport=7
            )
        ],
        consolidatedInsights=ConsolidatedInsights(
            primaryCrop="Tomato",
            commonConcerns=["pest management", "disease control"],
            farmerName="Ramesh"
        )
    )
    
    weather = WeatherData(
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
        ),
        timestamp=datetime.utcnow().isoformat()
    )
    
    land_records = LandRecords(
        landArea=1.5,
        soilType="Clay Loam",
        currentCrop="Tomato",
        cropHistory=[]
    )
    
    context = ContextData(
        weather=weather,
        landRecords=land_records,
        memory=memory
    )
    
    # Build prompt
    prompt = build_memory_first_prompt(
        question="When should I apply fertilizer to my tomato plants?",
        context=context,
        weather_analysis="Weather is suitable for fertilizer application",
        icar_knowledge="ICAR recommends NPK fertilizer for tomato at vegetative stage"
    )
    
    # Verify Memory-First instructions are present
    assert "MEMORY-FIRST PRIORITY" in prompt.systemPrompt
    assert "Leaf curl on tomato plants" in prompt.systemPrompt
    assert "7 days ago" in prompt.systemPrompt
    assert "UNRESOLVED ISSUES (1)" in prompt.systemPrompt
    
    # Verify the prompt instructs to ask about the issue BEFORE answering
    assert "BEFORE answering the current question" in prompt.systemPrompt
    
    # Verify example is provided
    assert "Before I answer that" in prompt.systemPrompt


# Property Test for Advice Provenance

@st.composite
def farmer_question_strategy(draw):
    """Generate realistic farmer questions for property testing."""
    question_templates = [
        "When should I spray pesticide on my {} crop?",
        "How much water does my {} need?",
        "What fertilizer should I use for {}?",
        "Is it safe to irrigate my {} today?",
        "When is the best time to harvest {}?",
        "How do I control pests in my {} field?",
        "What is the best planting time for {}?",
        "Should I apply fungicide to my {}?",
        "Why are my {} leaves turning yellow?",
        "How often should I water my {}?",
        "What is causing wilting in my {}?",
        "When should I apply nitrogen to my {}?",
    ]
    
    crops = ['rice', 'wheat', 'cotton', 'sugarcane', 'maize', 'tomato', 'potato', 'onion', 'chili']
    
    template = draw(st.sampled_from(question_templates))
    crop = draw(st.sampled_from(crops))
    
    return template.format(crop)


@st.composite
def context_data_strategy(draw):
    """Generate valid ContextData for property testing."""
    # Weather data
    weather = WeatherData(
        current=CurrentWeather(
            temperature=draw(st.floats(min_value=15, max_value=45, allow_nan=False, allow_infinity=False)),
            humidity=draw(st.floats(min_value=30, max_value=90, allow_nan=False, allow_infinity=False)),
            windSpeed=draw(st.floats(min_value=0, max_value=30, allow_nan=False, allow_infinity=False)),
            precipitation=draw(st.floats(min_value=0, max_value=50, allow_nan=False, allow_infinity=False))
        ),
        forecast6h=Forecast6h(
            precipitationProbability=draw(st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False)),
            expectedRainfall=draw(st.floats(min_value=0, max_value=50, allow_nan=False, allow_infinity=False)),
            temperature=draw(st.floats(min_value=15, max_value=45, allow_nan=False, allow_infinity=False)),
            windSpeed=draw(st.floats(min_value=0, max_value=30, allow_nan=False, allow_infinity=False))
        ),
        timestamp=datetime.utcnow().isoformat()
    )
    
    # Land records (optional)
    has_land_records = draw(st.booleans())
    land_records = None
    if has_land_records:
        crops = ["Rice", "Wheat", "Tomato", "Potato", "Cotton", "Sugarcane"]
        soil_types = ["Clay Loam", "Sandy", "Loamy", "Clay", "Silt Loam", "Red Soil", "Black Soil"]
        land_records = LandRecords(
            landArea=draw(st.floats(min_value=0.5, max_value=10, allow_nan=False, allow_infinity=False)),
            soilType=draw(st.sampled_from(soil_types)),
            currentCrop=draw(st.one_of(st.none(), st.sampled_from(crops))),
            cropHistory=[]
        )
    
    # Memory context
    has_unresolved_issues = draw(st.booleans())
    unresolved_issues = []
    if has_unresolved_issues:
        num_issues = draw(st.integers(min_value=1, max_value=3))
        for _ in range(num_issues):
            days_since = draw(st.integers(min_value=1, max_value=30))
            unresolved_issues.append(
                UnresolvedIssue(
                    issue=draw(st.sampled_from(["Leaf curl", "Yellowing", "Pest damage", "Wilting"])),
                    crop=draw(st.sampled_from(["Rice", "Wheat", "Tomato", "Cotton"])),
                    reportedDate=(datetime.utcnow() - timedelta(days=days_since)).isoformat(),
                    daysSinceReport=days_since
                )
            )
    
    memory = MemoryContext(
        recentInteractions=[],
        unresolvedIssues=unresolved_issues,
        consolidatedInsights=ConsolidatedInsights(
            primaryCrop=draw(st.sampled_from(["Rice", "Wheat", "Tomato", "Cotton", "Unknown"])),
            commonConcerns=[],
            farmerName=draw(st.one_of(st.none(), st.sampled_from(["Ramesh", "Suresh", "Lakshmi"])))
        )
    )
    
    return ContextData(
        weather=weather,
        landRecords=land_records,
        memory=memory
    )


@given(
    context=context_data_strategy(),
    question=farmer_question_strategy()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.pbt
@patch('boto3.client')
def test_property_38_advice_provenance_inclusion(mock_boto_client, context, question):
    """
    Feature: vaniverse, Property 38: Advice Provenance Inclusion
    Validates: Requirements 13.1, 13.2, 13.3, 13.4, 13.5, 13.6
    
    Test that for any generated advice, the text includes at least one
    provenance statement explaining why the recommendation is being made.
    
    This property verifies that:
    1. The system prompt includes explicit provenance requirements
    2. The system prompt provides examples of provenance statements
    3. The system prompt instructs to reference specific context factors
    4. Generated advice contains at least one provenance statement
    5. Provenance statements reference weather, soil, or conversation history
    """
    # Setup mock Bedrock response with provenance statements
    mock_bedrock = Mock()
    mock_boto_client.return_value = mock_bedrock
    
    # Create realistic advice with provenance based on context
    provenance_statements = []
    
    # Add weather-based provenance
    if context.weather.current.temperature > 35:
        provenance_statements.append(
            f"Because the current temperature is {context.weather.current.temperature}°C, which is quite high"
        )
    elif context.weather.forecast6h.precipitationProbability > 40:
        provenance_statements.append(
            f"Since the weather forecast predicts {context.weather.forecast6h.precipitationProbability}% chance of rain in the next 6 hours"
        )
    else:
        provenance_statements.append(
            f"Given the current weather conditions with {context.weather.current.temperature}°C temperature and {context.weather.current.humidity}% humidity"
        )
    
    # Add soil-based provenance if available
    if context.landRecords:
        provenance_statements.append(
            f"Because your soil record shows {context.landRecords.soilType} soil"
        )
    
    # Add memory-based provenance if available
    if context.memory.unresolvedIssues:
        first_issue = context.memory.unresolvedIssues[0]
        provenance_statements.append(
            f"Given that you mentioned {first_issue.issue.lower()} issues {first_issue.daysSinceReport} days ago"
        )
    
    # Construct advice with provenance
    mock_advice = f"""I recommend the following approach for your {question.split()[-2] if len(question.split()) > 1 else 'crop'}.

{provenance_statements[0]}, I suggest you proceed with caution. """
    
    if len(provenance_statements) > 1:
        mock_advice += f"{provenance_statements[1]}, this is particularly important for your situation. "
    
    mock_advice += """Here are the specific steps:
1. Check the soil moisture level
2. Apply the recommended treatment
3. Monitor the results over the next few days

This approach will help ensure the best outcome for your crop."""
    
    mock_response = {
        'body': Mock()
    }
    mock_response['body'].read.return_value = json.dumps({
        'content': [{'text': mock_advice}]
    }).encode('utf-8')
    
    mock_bedrock.invoke_model.return_value = mock_response
    
    # Sample agent outputs
    weather_analysis = f"Current temperature: {context.weather.current.temperature}°C, suitable for most operations"
    icar_knowledge = "ICAR guidelines recommend following best practices for crop management"
    
    # Build Memory-First prompt
    prompt = build_memory_first_prompt(
        question=question,
        context=context,
        weather_analysis=weather_analysis,
        icar_knowledge=icar_knowledge
    )
    
    # Property 1: System prompt must include ADVICE PROVENANCE section
    assert "ADVICE PROVENANCE" in prompt.systemPrompt, \
        "System prompt must include ADVICE PROVENANCE section"
    
    # Property 2: System prompt must require explaining WHY
    assert "explain WHY" in prompt.systemPrompt or "ALWAYS explain WHY" in prompt.systemPrompt, \
        "System prompt must instruct to explain WHY recommendations are made"
    
    # Property 3: System prompt must require referencing specific context factors
    assert "specific context factors" in prompt.systemPrompt.lower(), \
        "System prompt must instruct to reference specific context factors"
    
    # Property 4: System prompt must provide examples of provenance statements
    provenance_examples = [
        "Because your soil record shows",
        "Since the weather forecast predicts",
        "Given that you mentioned"
    ]
    
    examples_found = sum(1 for example in provenance_examples if example in prompt.systemPrompt)
    assert examples_found >= 2, \
        "System prompt must provide at least 2 examples of provenance statements"
    
    # Property 5: System prompt must require at least one provenance statement
    assert "at least one provenance statement" in prompt.systemPrompt.lower(), \
        "System prompt must explicitly require at least one provenance statement"
    
    # Property 6: System prompt must mention building trust through transparency
    assert "trust" in prompt.systemPrompt.lower() and "transparency" in prompt.systemPrompt.lower(), \
        "System prompt must mention building trust through transparency"
    
    # Property 7: Invoke Bedrock and verify the advice contains provenance
    advice = invoke_bedrock(prompt)
    
    # Check for provenance indicators in the advice
    provenance_indicators = [
        # Causal indicators
        "because", "since", "given that", "given the", "due to", "as", "considering",
        # Reference indicators
        "your soil", "the weather", "the forecast", "you mentioned", "your record",
        "the temperature", "the humidity", "the conditions", "your land",
        # Reasoning indicators
        "this is why", "the reason", "that's why", "therefore", "thus",
        # Context references
        "shows", "indicates", "predicts", "suggests", "reveals"
    ]
    
    advice_lower = advice.lower()
    provenance_found = any(indicator in advice_lower for indicator in provenance_indicators)
    
    assert provenance_found, \
        f"Generated advice must include at least one provenance statement with reasoning. " \
        f"Expected indicators like 'because', 'since', 'given that', etc. Advice: {advice[:200]}"
    
    # Property 8: Verify provenance references actual context
    # Check if advice mentions specific context values
    context_references = []
    
    # Check for weather references
    temp_str = str(int(context.weather.current.temperature))
    if temp_str in advice or f"{context.weather.current.temperature}" in advice:
        context_references.append("temperature")
    
    humidity_str = str(int(context.weather.current.humidity))
    if humidity_str in advice or f"{context.weather.current.humidity}" in advice:
        context_references.append("humidity")
    
    rain_prob_str = str(int(context.weather.forecast6h.precipitationProbability))
    if rain_prob_str in advice or f"{context.weather.forecast6h.precipitationProbability}" in advice:
        context_references.append("rain probability")
    
    # Check for soil references
    if context.landRecords and context.landRecords.soilType.lower() in advice_lower:
        context_references.append("soil type")
    
    # Check for memory references
    if context.memory.unresolvedIssues:
        for issue in context.memory.unresolvedIssues:
            if issue.issue.lower() in advice_lower or issue.crop.lower() in advice_lower:
                context_references.append("previous issue")
                break
    
    # At least one context reference should be present
    assert len(context_references) > 0, \
        f"Advice must reference at least one specific context factor (weather, soil, or history). " \
        f"Context available: weather={context.weather.current.temperature}°C, " \
        f"soil={context.landRecords.soilType if context.landRecords else 'N/A'}, " \
        f"issues={len(context.memory.unresolvedIssues)}. " \
        f"Advice: {advice[:200]}"
    
    # Verify Bedrock was called correctly
    mock_bedrock.invoke_model.assert_called_once()
    call_args = mock_bedrock.invoke_model.call_args
    assert call_args[1]['modelId'] == 'anthropic.claude-3-5-sonnet-20241022-v2:0'


# Unit test for specific provenance scenarios
def test_advice_provenance_specific_scenarios():
    """
    Unit test for advice provenance with specific realistic scenarios.
    
    This complements the property test by verifying concrete examples.
    """
    # Scenario 1: High temperature affecting pesticide application
    weather_hot = WeatherData(
        current=CurrentWeather(
            temperature=42.0,
            humidity=45.0,
            windSpeed=8.0,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=10.0,
            expectedRainfall=0.0,
            temperature=40.0,
            windSpeed=10.0
        ),
        timestamp=datetime.utcnow().isoformat()
    )
    
    land_records = LandRecords(
        landArea=2.5,
        soilType="Sandy Loam",
        currentCrop="Cotton",
        cropHistory=[]
    )
    
    memory = MemoryContext(
        recentInteractions=[],
        unresolvedIssues=[],
        consolidatedInsights=ConsolidatedInsights(
            primaryCrop="Cotton",
            commonConcerns=[],
            farmerName="Ramesh"
        )
    )
    
    context = ContextData(
        weather=weather_hot,
        landRecords=land_records,
        memory=memory
    )
    
    prompt = build_memory_first_prompt(
        question="When should I spray pesticide?",
        context=context,
        weather_analysis="Temperature is very high at 42°C, not ideal for spraying",
        icar_knowledge="ICAR recommends spraying during cooler hours"
    )
    
    # Verify provenance requirements are in system prompt
    assert "ADVICE PROVENANCE" in prompt.systemPrompt
    assert "42.0°C" in prompt.systemPrompt or "42°C" in prompt.systemPrompt
    assert "Sandy Loam" in prompt.systemPrompt
    
    # Scenario 2: Rain forecast affecting operations
    weather_rainy = WeatherData(
        current=CurrentWeather(
            temperature=28.0,
            humidity=85.0,
            windSpeed=15.0,
            precipitation=2.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=75.0,
            expectedRainfall=15.0,
            temperature=26.0,
            windSpeed=20.0
        ),
        timestamp=datetime.utcnow().isoformat()
    )
    
    context_rainy = ContextData(
        weather=weather_rainy,
        landRecords=land_records,
        memory=memory
    )
    
    prompt_rainy = build_memory_first_prompt(
        question="Should I irrigate my field today?",
        context=context_rainy,
        weather_analysis="High rain probability of 75% in next 6 hours",
        icar_knowledge="ICAR advises against irrigation before expected rainfall"
    )
    
    # Verify weather-based provenance context is included
    assert "75.0%" in prompt_rainy.systemPrompt or "75%" in prompt_rainy.systemPrompt
    assert "15.0mm" in prompt_rainy.systemPrompt or "15mm" in prompt_rainy.systemPrompt
