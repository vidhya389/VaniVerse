"""
Tests for Lambda handler orchestration.

Tests the main entry point and coordination of all system components.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.lambda_handler import (
    lambda_handler,
    parse_s3_event,
    _extract_metadata_from_key,
    _create_error_response
)
from src.models.context_data import (
    ContextData, WeatherData, CurrentWeather, Forecast6h,
    LandRecords, MemoryContext, ConsolidatedInsights
)
from src.models.safety_validation import SafetyValidationResult


@pytest.fixture
def sample_s3_event():
    """Sample S3 upload event."""
    return {
        'Records': [
            {
                'eventSource': 'aws:s3',
                'eventName': 'ObjectCreated:Put',
                's3': {
                    'bucket': {
                        'name': 'vaniverse-audio-input'
                    },
                    'object': {
                        'key': 'FARMER-123/SESSION-456/1234567890.wav'
                    }
                }
            }
        ]
    }


@pytest.fixture
def sample_context_data():
    """Sample context data for testing."""
    return ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=28.5,
                humidity=65.0,
                windSpeed=12.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=20.0,
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
            recentInteractions=[],
            unresolvedIssues=[],
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop='Rice',
                commonConcerns=[],
                farmerName='Test Farmer'
            )
        )
    )


class TestParseS3Event:
    """Tests for S3 event parsing."""
    
    def test_parse_valid_event(self, sample_s3_event):
        """Test parsing a valid S3 event."""
        result = parse_s3_event(sample_s3_event)
        
        assert result['audio_key'] == 'FARMER-123/SESSION-456/1234567890.wav'
        assert result['bucket'] == 'vaniverse-audio-input'
        assert result['farmer_id'] == 'FARMER-123'
        assert 'gps' in result
        assert 'latitude' in result['gps']
        assert 'longitude' in result['gps']
    
    def test_parse_event_missing_records(self):
        """Test parsing event with missing Records field."""
        event = {}
        
        with pytest.raises(ValueError, match="No S3 records found"):
            parse_s3_event(event)
    
    def test_parse_event_empty_records(self):
        """Test parsing event with empty Records list."""
        event = {'Records': []}
        
        with pytest.raises(ValueError, match="No S3 records found"):
            parse_s3_event(event)
    
    def test_parse_event_invalid_source(self):
        """Test parsing event with invalid event source."""
        event = {
            'Records': [
                {
                    'eventSource': 'aws:sns',
                    's3': {}
                }
            ]
        }
        
        with pytest.raises(ValueError, match="Invalid event source"):
            parse_s3_event(event)
    
    def test_parse_event_missing_object_key(self):
        """Test parsing event with missing object key."""
        event = {
            'Records': [
                {
                    'eventSource': 'aws:s3',
                    's3': {
                        'bucket': {'name': 'test-bucket'},
                        'object': {}
                    }
                }
            ]
        }
        
        with pytest.raises(ValueError, match="Missing S3 object key"):
            parse_s3_event(event)


class TestExtractMetadataFromKey:
    """Tests for metadata extraction from S3 keys."""
    
    def test_extract_from_standard_format(self):
        """Test extracting metadata from standard key format."""
        key = 'FARMER-123/SESSION-456/1234567890.wav'
        
        metadata = _extract_metadata_from_key(key)
        
        assert metadata['farmer_id'] == 'FARMER-123'
        assert metadata['session_id'] == 'SESSION-456'
        assert 'gps' in metadata
    
    def test_extract_from_short_key(self):
        """Test extracting metadata from short key (fallback)."""
        key = 'audio.wav'
        
        metadata = _extract_metadata_from_key(key)
        
        assert metadata['farmer_id'] == 'UNKNOWN'
        assert 'gps' in metadata


class TestLambdaHandler:
    """Tests for main Lambda handler function."""
    
    @patch('src.lambda_handler.detect_bandwidth_mode')
    @patch('src.lambda_handler.transcribe_with_retry')
    @patch('src.lambda_handler.fetch_context_parallel')
    @patch('src.lambda_handler.invoke_agents_parallel')
    @patch('src.lambda_handler.build_memory_first_prompt')
    @patch('src.lambda_handler.invoke_bedrock')
    @patch('src.lambda_handler.validate_safety')
    @patch('src.lambda_handler.synthesize_speech')
    @patch('src.lambda_handler.store_interaction')
    def test_successful_voice_loop(
        self,
        mock_store,
        mock_synthesize,
        mock_validate,
        mock_bedrock,
        mock_prompt,
        mock_agents,
        mock_context,
        mock_transcribe,
        mock_bandwidth,
        sample_s3_event,
        sample_context_data
    ):
        """Test successful completion of voice loop."""
        # Setup mocks
        mock_bandwidth.return_value = 'normal'
        mock_transcribe.return_value = (
            "How do I control pests on my rice crop?",
            "hi-IN",
            0.95
        )
        mock_context.return_value = sample_context_data
        mock_agents.return_value = {
            'weather_analysis': 'Weather is suitable for spraying',
            'icar_knowledge': 'Use neem-based pesticides'
        }
        mock_prompt.return_value = Mock()
        mock_bedrock.return_value = "Apply neem-based pesticide in the evening"
        mock_validate.return_value = SafetyValidationResult(
            isApproved=True,
            conflicts=[],
            alternativeRecommendation=None
        )
        mock_synthesize.return_value = ('response-audio-key.mp3', 'polly')
        
        # Execute
        response = lambda_handler(sample_s3_event, Mock())
        
        # Verify
        assert response['statusCode'] == 200
        assert response['audioKey'] == 'response-audio-key.mp3'
        assert response['synthesisService'] == 'polly'
        assert response['bandwidthMode'] == 'normal'
        assert 'executionTime' in response
        
        # Verify all steps were called
        mock_bandwidth.assert_called_once()
        mock_transcribe.assert_called_once()
        mock_context.assert_called_once()
        mock_agents.assert_called_once()
        mock_bedrock.assert_called_once()
        mock_validate.assert_called_once()
        mock_synthesize.assert_called_once()
        mock_store.assert_called_once()
    
    @patch('src.lambda_handler.detect_bandwidth_mode')
    @patch('src.lambda_handler.transcribe_with_retry')
    @patch('src.lambda_handler.fetch_context_parallel')
    @patch('src.lambda_handler.invoke_agents_parallel')
    @patch('src.lambda_handler.build_memory_first_prompt')
    @patch('src.lambda_handler.invoke_bedrock')
    @patch('src.lambda_handler.validate_safety')
    @patch('src.lambda_handler.synthesize_speech')
    @patch('src.lambda_handler.store_interaction')
    def test_safety_validation_blocks_advice(
        self,
        mock_store,
        mock_synthesize,
        mock_validate,
        mock_bedrock,
        mock_prompt,
        mock_agents,
        mock_context,
        mock_transcribe,
        mock_bandwidth,
        sample_s3_event,
        sample_context_data
    ):
        """Test that blocked advice uses alternative recommendation."""
        # Setup mocks
        mock_bandwidth.return_value = 'normal'
        mock_transcribe.return_value = ("Should I spray pesticide now?", "hi-IN", 0.95)
        mock_context.return_value = sample_context_data
        mock_agents.return_value = {
            'weather_analysis': 'Rain expected',
            'icar_knowledge': 'Use pesticides carefully'
        }
        mock_prompt.return_value = Mock()
        mock_bedrock.return_value = "Yes, spray pesticide now"
        
        # Safety validator blocks the advice
        from src.models.safety_validation import SafetyConflict
        mock_validate.return_value = SafetyValidationResult(
            isApproved=False,
            conflicts=[
                SafetyConflict(
                    type='rain_forecast',
                    severity='blocking',
                    message='Rain predicted in 4 hours'
                )
            ],
            alternativeRecommendation="Wait 12 hours until rain passes"
        )
        mock_synthesize.return_value = ('response-audio-key.mp3', 'polly')
        
        # Execute
        response = lambda_handler(sample_s3_event, Mock())
        
        # Verify
        assert response['statusCode'] == 200
        assert not response['validationResult']['isApproved']
        assert len(response['validationResult']['conflicts']) == 1
        assert response['validationResult']['alternativeRecommendation'] is not None
        
        # Verify alternative recommendation was synthesized
        mock_synthesize.assert_called_once()
        call_args = mock_synthesize.call_args[0]
        assert call_args[0] == "Wait 12 hours until rain passes"
    
    @patch('src.lambda_handler.detect_bandwidth_mode')
    @patch('src.lambda_handler.transcribe_with_retry')
    def test_low_confidence_transcription(
        self,
        mock_transcribe,
        mock_bandwidth,
        sample_s3_event
    ):
        """Test handling of low confidence transcription."""
        from src.speech.transcribe import LowConfidenceError
        
        # Setup mocks
        mock_bandwidth.return_value = 'normal'
        mock_transcribe.side_effect = LowConfidenceError("Confidence too low")
        
        # Mock synthesize_speech for error response
        with patch('src.lambda_handler.synthesize_speech') as mock_synthesize:
            mock_synthesize.return_value = ('error-audio.mp3', 'polly')
            
            # Execute
            response = lambda_handler(sample_s3_event, Mock())
            
            # Verify error response
            assert response['statusCode'] == 200
            assert response['isError'] is True
            assert 'repeat your question' in response['errorMessage']
    
    @patch('src.lambda_handler.detect_bandwidth_mode')
    @patch('src.lambda_handler.transcribe_with_retry')
    @patch('src.lambda_handler.fetch_context_parallel')
    @patch('src.lambda_handler.invoke_agents_parallel')
    @patch('src.lambda_handler.build_memory_first_prompt')
    @patch('src.lambda_handler.invoke_bedrock')
    @patch('src.lambda_handler.validate_safety')
    @patch('src.lambda_handler.synthesize_speech')
    @patch('src.lambda_handler.store_interaction')
    @patch('src.lambda_handler.generate_ussd_fallback')
    @patch('src.lambda_handler.time')
    def test_ussd_fallback_on_timeout(
        self,
        mock_time,
        mock_ussd,
        mock_store,
        mock_synthesize,
        mock_validate,
        mock_bedrock,
        mock_prompt,
        mock_agents,
        mock_context,
        mock_transcribe,
        mock_bandwidth,
        sample_s3_event,
        sample_context_data
    ):
        """Test USSD fallback when voice loop exceeds timeout in low-bandwidth mode."""
        # Setup mocks
        mock_bandwidth.return_value = 'low'
        mock_transcribe.return_value = ("Test question", "hi-IN", 0.95)
        mock_context.return_value = sample_context_data
        mock_agents.return_value = {
            'weather_analysis': 'Analysis',
            'icar_knowledge': 'Knowledge'
        }
        mock_prompt.return_value = Mock()
        mock_bedrock.return_value = "Test advice"
        mock_validate.return_value = SafetyValidationResult(
            isApproved=True,
            conflicts=[],
            alternativeRecommendation=None
        )
        mock_synthesize.return_value = ('audio.mp3', 'polly')
        mock_ussd.return_value = {
            'type': 'ussd_fallback',
            'chunks': ['Test advice chunk'],
            'ussd_menu': {}
        }
        
        # Simulate timeout (16 seconds > 15 second threshold)
        mock_time.time.side_effect = [0, 16]
        
        # Execute
        response = lambda_handler(sample_s3_event, Mock())
        
        # Verify USSD fallback is included
        assert response['statusCode'] == 200
        assert 'ussdFallback' in response
        assert response['ussdFallback']['type'] == 'ussd_fallback'
        mock_ussd.assert_called_once()
    
    def test_exception_handling(self, sample_s3_event):
        """Test that exceptions are caught and returned as error responses."""
        # Mock to raise exception
        with patch('src.lambda_handler.parse_s3_event') as mock_parse:
            mock_parse.side_effect = Exception("Test error")
            
            # Execute
            response = lambda_handler(sample_s3_event, Mock())
            
            # Verify error response
            assert response['statusCode'] == 500
            assert 'error' in json.loads(response['body'])


class TestCreateErrorResponse:
    """Tests for error response creation."""
    
    @patch('src.lambda_handler.synthesize_speech')
    def test_successful_error_synthesis(self, mock_synthesize):
        """Test successful creation of error response with audio."""
        mock_synthesize.return_value = ('error-audio.mp3', 'polly')
        
        response = _create_error_response(
            "Test error message",
            "hi-IN",
            "normal"
        )
        
        assert response['statusCode'] == 200
        assert response['audioKey'] == 'error-audio.mp3'
        assert response['isError'] is True
        assert response['errorMessage'] == "Test error message"
    
    @patch('src.lambda_handler.synthesize_speech')
    def test_synthesis_failure(self, mock_synthesize):
        """Test error response when synthesis fails."""
        mock_synthesize.side_effect = Exception("Synthesis failed")
        
        response = _create_error_response(
            "Test error message",
            "hi-IN",
            "normal"
        )
        
        assert response['statusCode'] == 500
        assert 'synthesis_failed' in json.loads(response['body'])


class TestIntegration:
    """Integration tests for Lambda handler."""
    
    @pytest.mark.integration
    @patch('src.lambda_handler.detect_bandwidth_mode')
    @patch('src.lambda_handler.transcribe_with_retry')
    @patch('src.lambda_handler.fetch_context_parallel')
    @patch('src.lambda_handler.invoke_agents_parallel')
    @patch('src.lambda_handler.build_memory_first_prompt')
    @patch('src.lambda_handler.invoke_bedrock')
    @patch('src.lambda_handler.validate_safety')
    @patch('src.lambda_handler.synthesize_speech')
    @patch('src.lambda_handler.store_interaction')
    def test_complete_guru_cycle(
        self,
        mock_store,
        mock_synthesize,
        mock_validate,
        mock_bedrock,
        mock_prompt,
        mock_agents,
        mock_context,
        mock_transcribe,
        mock_bandwidth,
        sample_s3_event,
        sample_context_data
    ):
        """Test complete Guru Cycle from S3 event to response."""
        # Setup realistic mocks
        mock_bandwidth.return_value = 'normal'
        mock_transcribe.return_value = (
            "मेरी धान की फसल में कीट लग गए हैं, मुझे क्या करना चाहिए?",
            "hi-IN",
            0.92
        )
        mock_context.return_value = sample_context_data
        mock_agents.return_value = {
            'weather_analysis': (
                "Current weather is suitable for pesticide application. "
                "Temperature is 28.5°C with low wind speed. "
                "No rain expected in next 6 hours."
            ),
            'icar_knowledge': (
                "For rice pest control, ICAR recommends neem-based pesticides. "
                "Apply in evening hours for best results."
            )
        }
        mock_prompt.return_value = Mock()
        mock_bedrock.return_value = (
            "आपकी धान की फसल में कीट नियंत्रण के लिए नीम आधारित कीटनाशक का उपयोग करें। "
            "शाम के समय छिड़काव करें जब तापमान कम हो।"
        )
        mock_validate.return_value = SafetyValidationResult(
            isApproved=True,
            conflicts=[],
            alternativeRecommendation=None
        )
        mock_synthesize.return_value = ('hindi-response.mp3', 'polly')
        
        # Execute
        response = lambda_handler(sample_s3_event, Mock())
        
        # Verify complete flow
        assert response['statusCode'] == 200
        assert response['audioKey'] == 'hindi-response.mp3'
        assert response['synthesisService'] == 'polly'
        assert response['validationResult']['isApproved'] is True
        assert 'executionTime' in response
        assert response['executionTime'] >= 0  # Execution time should be non-negative
        
        # Verify all components were invoked in correct order
        assert mock_bandwidth.call_count == 1
        assert mock_transcribe.call_count == 1
        assert mock_context.call_count == 1
        assert mock_agents.call_count == 1
        assert mock_bedrock.call_count == 1
        assert mock_validate.call_count == 1
        assert mock_synthesize.call_count == 1
        assert mock_store.call_count == 1
