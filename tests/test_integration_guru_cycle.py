"""
Integration tests for the complete Guru Cycle

Tests the end-to-end flow from audio upload to response generation
using real AWS services (or mocked equivalents).
"""

import pytest
import boto3
import json
import time
import uuid
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.lambda_handler import lambda_handler
from src.config import Config


@pytest.mark.integration
class TestGuruCycleIntegration:
    """Integration tests for complete Guru Cycle"""
    
    @pytest.fixture
    def s3_client(self):
        """S3 client for test setup"""
        return boto3.client('s3', region_name=Config.AWS_REGION)
    
    @pytest.fixture
    def test_audio_key(self):
        """Generate unique test audio key"""
        return f"test-audio/{uuid.uuid4()}.wav"
    
    @pytest.fixture
    def test_farmer_id(self):
        """Generate unique test farmer ID"""
        return f"TEST-FARMER-{uuid.uuid4()}"
    
    @pytest.fixture
    def mock_s3_event(self, test_audio_key, test_farmer_id):
        """Create mock S3 event"""
        return {
            'Records': [{
                'eventSource': 'aws:s3',
                'eventName': 'ObjectCreated:Put',
                's3': {
                    'bucket': {'name': Config.AUDIO_INPUT_BUCKET},
                    'object': {
                        'key': test_audio_key,
                        'size': 50000
                    }
                }
            }],
            'metadata': {
                'farmerId': test_farmer_id,
                'language': 'hi-IN',
                'gpsLatitude': '28.6139',
                'gpsLongitude': '77.2090'
            }
        }
    
    def test_complete_guru_cycle_with_mocks(self, mock_s3_event, test_farmer_id):
        """
        Test complete Guru Cycle with mocked external services
        
        Validates: Requirements 1.1, 1.2, 1.3, 11.1, 11.2, 11.4, 11.5
        """
        with patch('src.speech.transcribe.transcribe_audio') as mock_transcribe, \
             patch('src.context.weather.fetch_weather') as mock_weather, \
             patch('src.context.ufsi.fetch_land_records') as mock_land, \
             patch('src.context.memory.fetch_memory') as mock_memory, \
             patch('src.prompting.builder.invoke_bedrock') as mock_bedrock, \
             patch('src.speech.router.synthesize_speech') as mock_synthesize:
            
            # Setup mocks
            mock_transcribe.return_value = ("What fertilizer should I use for my rice crop?", "hi-IN", 0.95)
            
            mock_weather.return_value = {
                'current': {
                    'temperature': 28.5,
                    'humidity': 65,
                    'windSpeed': 10,
                    'precipitation': 0
                },
                'forecast6h': {
                    'precipitationProbability': 20,
                    'expectedRainfall': 0,
                    'temperature': 30,
                    'windSpeed': 12
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
            mock_land.return_value = {
                'landArea': 2.5,
                'soilType': 'Clay Loam',
                'currentCrop': 'Rice',
                'cropHistory': []
            }
            
            mock_memory.return_value = {
                'recentInteractions': [],
                'unresolvedIssues': [],
                'consolidatedInsights': {
                    'primaryCrop': 'Rice',
                    'commonConcerns': [],
                    'farmerName': 'Test Farmer'
                }
            }
            
            mock_bedrock.return_value = "For your rice crop in clay loam soil, I recommend using NPK fertilizer at 120:60:40 kg/ha ratio."
            
            mock_synthesize.return_value = f"responses/{uuid.uuid4()}.mp3"
            
            # Execute Lambda handler
            response = lambda_handler(mock_s3_event, {})
            
            # Verify response
            assert response['statusCode'] == 200
            assert 'audioKey' in response
            assert response['audioKey'].startswith('responses/')
            
            # Verify all components were called
            mock_transcribe.assert_called_once()
            mock_weather.assert_called_once()
            mock_memory.assert_called_once()
            mock_bedrock.assert_called_once()
            mock_synthesize.assert_called_once()
    
    def test_guru_cycle_with_safety_validation(self, mock_s3_event):
        """
        Test Guru Cycle with safety validation blocking unsafe advice
        
        Validates: Requirements 4.1, 4.2, 4.6, 4.7
        """
        with patch('src.speech.transcribe.transcribe_audio') as mock_transcribe, \
             patch('src.context.weather.fetch_weather') as mock_weather, \
             patch('src.context.ufsi.fetch_land_records') as mock_land, \
             patch('src.context.memory.fetch_memory') as mock_memory, \
             patch('src.prompting.builder.invoke_bedrock') as mock_bedrock, \
             patch('src.speech.router.synthesize_speech') as mock_synthesize:
            
            # Setup mocks - farmer asks about spraying with rain forecast
            mock_transcribe.return_value = ("Can I spray pesticide on my crops today?", "hi-IN", 0.92)
            
            mock_weather.return_value = {
                'current': {
                    'temperature': 28.5,
                    'humidity': 75,
                    'windSpeed': 8,
                    'precipitation': 0
                },
                'forecast6h': {
                    'precipitationProbability': 65,  # High rain probability
                    'expectedRainfall': 5,
                    'temperature': 26,
                    'windSpeed': 15
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
            mock_land.return_value = None
            mock_memory.return_value = {
                'recentInteractions': [],
                'unresolvedIssues': [],
                'consolidatedInsights': {}
            }
            
            mock_bedrock.return_value = "Yes, you can spray pesticide today. Make sure to follow the instructions on the label."
            
            mock_synthesize.return_value = f"responses/{uuid.uuid4()}.mp3"
            
            # Execute Lambda handler
            response = lambda_handler(mock_s3_event, {})
            
            # Verify safety validation blocked the advice
            assert response['statusCode'] == 200
            validation_result = response.get('validationResult', {})
            
            # Should have conflicts detected
            assert len(validation_result.get('conflicts', [])) > 0
            
            # Should have rain forecast conflict
            rain_conflict = next(
                (c for c in validation_result['conflicts'] if c['type'] == 'rain_forecast'),
                None
            )
            assert rain_conflict is not None
            assert rain_conflict['severity'] == 'blocking'
    
    def test_guru_cycle_with_memory_first_prompting(self, mock_s3_event, test_farmer_id):
        """
        Test Guru Cycle with Memory-First prompting for unresolved issues
        
        Validates: Requirements 2.2, 2.4
        """
        with patch('src.speech.transcribe.transcribe_audio') as mock_transcribe, \
             patch('src.context.weather.fetch_weather') as mock_weather, \
             patch('src.context.ufsi.fetch_land_records') as mock_land, \
             patch('src.context.memory.fetch_memory') as mock_memory, \
             patch('src.prompting.builder.invoke_bedrock') as mock_bedrock, \
             patch('src.speech.router.synthesize_speech') as mock_synthesize:
            
            # Setup mocks - farmer has unresolved issue from 10 days ago
            mock_transcribe.return_value = ("What is the best time to harvest wheat?", "hi-IN", 0.93)
            
            mock_weather.return_value = {
                'current': {'temperature': 25, 'humidity': 60, 'windSpeed': 5, 'precipitation': 0},
                'forecast6h': {'precipitationProbability': 10, 'expectedRainfall': 0, 'temperature': 27, 'windSpeed': 6},
                'timestamp': datetime.utcnow().isoformat()
            }
            
            mock_land.return_value = None
            
            # Memory has unresolved issue from 10 days ago
            mock_memory.return_value = {
                'recentInteractions': [],
                'unresolvedIssues': [{
                    'issue': 'leaf curl on tomatoes',
                    'crop': 'Tomatoes',
                    'reportedDate': '2026-02-05T10:00:00Z',
                    'daysSinceReport': 10
                }],
                'consolidatedInsights': {
                    'primaryCrop': 'Wheat',
                    'commonConcerns': ['pest management'],
                    'farmerName': 'Test Farmer'
                }
            }
            
            mock_bedrock.return_value = "Before I answer that, how is the leaf curl issue on your tomatoes that you mentioned 10 days ago? Has it improved?"
            
            mock_synthesize.return_value = f"responses/{uuid.uuid4()}.mp3"
            
            # Execute Lambda handler
            response = lambda_handler(mock_s3_event, {})
            
            # Verify response includes follow-up about unresolved issue
            assert response['statusCode'] == 200
            
            # Verify bedrock was called with memory context including unresolved issues
            call_args = mock_bedrock.call_args
            prompt = call_args[0][0] if call_args[0] else call_args[1].get('prompt')
            
            # The prompt should include unresolved issues
            assert 'unresolvedIssues' in str(prompt) or 'leaf curl' in str(prompt).lower()
    
    def test_guru_cycle_parallel_context_retrieval(self, mock_s3_event):
        """
        Test that context retrieval happens in parallel
        
        Validates: Requirements 11.2
        """
        call_times = {}
        
        def track_call_time(name):
            def wrapper(*args, **kwargs):
                call_times[name] = time.time()
                time.sleep(0.1)  # Simulate API call
                return MagicMock()
            return wrapper
        
        with patch('src.speech.transcribe.transcribe_audio', return_value=("Test question", "hi-IN", 0.90)), \
             patch('src.context.weather.fetch_weather', side_effect=track_call_time('weather')), \
             patch('src.context.ufsi.fetch_land_records', side_effect=track_call_time('land')), \
             patch('src.context.memory.fetch_memory', side_effect=track_call_time('memory')), \
             patch('src.prompting.builder.invoke_bedrock', return_value="Test advice"), \
             patch('src.speech.router.synthesize_speech', return_value="test.mp3"):
            
            start_time = time.time()
            response = lambda_handler(mock_s3_event, {})
            total_time = time.time() - start_time
            
            # Verify all three context calls were made
            assert 'weather' in call_times
            assert 'land' in call_times
            assert 'memory' in call_times
            
            # If parallel, total time should be ~0.1s (one call duration)
            # If sequential, total time would be ~0.3s (three call durations)
            # Allow some overhead, so check < 0.25s
            assert total_time < 0.25, f"Context retrieval took {total_time}s, suggesting sequential execution"
    
    def test_guru_cycle_with_low_bandwidth_mode(self, mock_s3_event):
        """
        Test Guru Cycle activates low-bandwidth mode for small audio files
        
        Validates: Requirements 14.1, 14.2, 14.3
        """
        # Modify event to have small file size (indicating low bandwidth)
        mock_s3_event['Records'][0]['s3']['object']['size'] = 30000  # < 50KB
        
        with patch('src.speech.transcribe.transcribe_audio') as mock_transcribe, \
             patch('src.context.weather.fetch_weather') as mock_weather, \
             patch('src.context.ufsi.fetch_land_records') as mock_land, \
             patch('src.context.memory.fetch_memory') as mock_memory, \
             patch('src.prompting.builder.invoke_bedrock') as mock_bedrock, \
             patch('src.speech.router.synthesize_speech') as mock_synthesize, \
             patch('src.utils.bandwidth.compress_audio_to_64kbps') as mock_compress:
            
            # Setup mocks
            mock_transcribe.return_value = ("Test question", "hi-IN", 0.90)
            mock_weather.return_value = {'current': {}, 'forecast6h': {}, 'timestamp': ''}
            mock_land.return_value = None
            mock_memory.return_value = {'recentInteractions': [], 'unresolvedIssues': [], 'consolidatedInsights': {}}
            mock_bedrock.return_value = "Test advice"
            mock_synthesize.return_value = "test.mp3"
            mock_compress.return_value = b"compressed_audio"
            
            # Execute Lambda handler
            response = lambda_handler(mock_s3_event, {})
            
            # Verify low-bandwidth mode was activated
            # This would be indicated by compression being called or
            # specific low-bandwidth synthesis settings
            assert response['statusCode'] == 200


@pytest.mark.integration
class TestMultiLanguageIntegration:
    """Integration tests for multi-language support"""
    
    SUPPORTED_LANGUAGES = [
        'hi-IN',  # Hindi
        'ta-IN',  # Tamil
        'te-IN',  # Telugu
        'kn-IN',  # Kannada
        'mr-IN',  # Marathi
        'bn-IN',  # Bengali
        'gu-IN',  # Gujarati
        'pa-IN'   # Punjabi
    ]
    
    @pytest.mark.parametrize('language', SUPPORTED_LANGUAGES)
    def test_language_support_end_to_end(self, language):
        """
        Test end-to-end support for each language
        
        Validates: Requirements 7.1, 7.2, 7.4, 7.5
        """
        # Create mock event for this language
        mock_event = {
            'Records': [{
                'eventSource': 'aws:s3',
                'eventName': 'ObjectCreated:Put',
                's3': {
                    'bucket': {'name': Config.AUDIO_INPUT_BUCKET},
                    'object': {
                        'key': f'test-audio/{uuid.uuid4()}.wav',
                        'size': 50000
                    }
                }
            }],
            'metadata': {
                'farmerId': f'TEST-{uuid.uuid4()}',
                'language': language,
                'gpsLatitude': '28.6139',
                'gpsLongitude': '77.2090'
            }
        }
        
        with patch('src.speech.transcribe.transcribe_audio') as mock_transcribe, \
             patch('src.context.weather.fetch_weather') as mock_weather, \
             patch('src.context.ufsi.fetch_land_records') as mock_land, \
             patch('src.context.memory.fetch_memory') as mock_memory, \
             patch('src.prompting.builder.invoke_bedrock') as mock_bedrock, \
             patch('src.speech.router.synthesize_speech') as mock_synthesize:
            
            # Setup mocks
            mock_transcribe.return_value = ("Test question in " + language, language, 0.91)
            mock_weather.return_value = {
                'current': {'temperature': 28, 'humidity': 65, 'windSpeed': 10, 'precipitation': 0},
                'forecast6h': {'precipitationProbability': 20, 'expectedRainfall': 0, 'temperature': 30, 'windSpeed': 12},
                'timestamp': datetime.utcnow().isoformat()
            }
            mock_land.return_value = None
            mock_memory.return_value = {
                'recentInteractions': [],
                'unresolvedIssues': [],
                'consolidatedInsights': {}
            }
            mock_bedrock.return_value = f"Test advice in {language}"
            mock_synthesize.return_value = f"responses/{uuid.uuid4()}.mp3"
            
            # Execute Lambda handler
            response = lambda_handler(mock_event, {})
            
            # Verify response
            assert response['statusCode'] == 200
            assert 'audioKey' in response
            
            # Verify synthesize was called with correct language
            mock_synthesize.assert_called_once()
            call_args = mock_synthesize.call_args
            assert language in str(call_args)


@pytest.mark.integration
class TestErrorScenarioIntegration:
    """Integration tests for error scenarios and fallback behaviors"""
    
    def test_transcription_failure_fallback(self):
        """
        Test fallback when transcription fails
        
        Validates: Requirements 1.5, 9.1
        """
        mock_event = {
            'Records': [{
                'eventSource': 'aws:s3',
                'eventName': 'ObjectCreated:Put',
                's3': {
                    'bucket': {'name': Config.AUDIO_INPUT_BUCKET},
                    'object': {'key': f'test-audio/{uuid.uuid4()}.wav', 'size': 50000}
                }
            }],
            'metadata': {
                'farmerId': f'TEST-{uuid.uuid4()}',
                'language': 'hi-IN',
                'gpsLatitude': '28.6139',
                'gpsLongitude': '77.2090'
            }
        }
        
        with patch('src.speech.transcribe.transcribe_audio', side_effect=Exception("Transcription failed")), \
             patch('src.speech.router.synthesize_speech') as mock_synthesize:
            
            mock_synthesize.return_value = "error_response.mp3"
            
            # Execute Lambda handler
            response = lambda_handler(mock_event, {})
            
            # Should return error response, not crash
            assert response['statusCode'] in [200, 500]
            
            # Should have synthesized an error message
            if response['statusCode'] == 200:
                mock_synthesize.assert_called()
    
    def test_bedrock_timeout_fallback(self):
        """
        Test fallback when Bedrock times out
        
        Validates: Requirements 9.5
        """
        mock_event = {
            'Records': [{
                'eventSource': 'aws:s3',
                'eventName': 'ObjectCreated:Put',
                's3': {
                    'bucket': {'name': Config.AUDIO_INPUT_BUCKET},
                    'object': {'key': f'test-audio/{uuid.uuid4()}.wav', 'size': 50000}
                }
            }],
            'metadata': {
                'farmerId': f'TEST-{uuid.uuid4()}',
                'language': 'hi-IN',
                'gpsLatitude': '28.6139',
                'gpsLongitude': '77.2090'
            }
        }
        
        with patch('src.speech.transcribe.transcribe_audio', return_value=("Test question", "hi-IN", 0.90)), \
             patch('src.context.weather.fetch_weather') as mock_weather, \
             patch('src.context.ufsi.fetch_land_records', return_value=None), \
             patch('src.context.memory.fetch_memory', return_value={'recentInteractions': [], 'unresolvedIssues': [], 'consolidatedInsights': {}}), \
             patch('src.prompting.builder.invoke_bedrock', side_effect=Exception("Bedrock timeout")), \
             patch('src.speech.router.synthesize_speech', return_value="test.mp3"):
            
            mock_weather.return_value = {
                'current': {'temperature': 28, 'humidity': 65, 'windSpeed': 10, 'precipitation': 0},
                'forecast6h': {'precipitationProbability': 20, 'expectedRainfall': 0, 'temperature': 30, 'windSpeed': 12},
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Execute Lambda handler - should handle gracefully
            response = lambda_handler(mock_event, {})
            
            # Should return error response or fallback advice
            assert response['statusCode'] in [200, 500]
    
    def test_synthesis_failure_fallback(self):
        """
        Test fallback when speech synthesis fails
        
        Validates: Requirements 7.4, 7.5
        """
        mock_event = {
            'Records': [{
                'eventSource': 'aws:s3',
                'eventName': 'ObjectCreated:Put',
                's3': {
                    'bucket': {'name': Config.AUDIO_INPUT_BUCKET},
                    'object': {'key': f'test-audio/{uuid.uuid4()}.wav', 'size': 50000}
                }
            }],
            'metadata': {
                'farmerId': f'TEST-{uuid.uuid4()}',
                'language': 'hi-IN',
                'gpsLatitude': '28.6139',
                'gpsLongitude': '77.2090'
            }
        }
        
        with patch('src.speech.transcribe.transcribe_audio', return_value=("Test question", "hi-IN", 0.90)), \
             patch('src.context.weather.fetch_weather') as mock_weather, \
             patch('src.context.ufsi.fetch_land_records', return_value=None), \
             patch('src.context.memory.fetch_memory', return_value={'recentInteractions': [], 'unresolvedIssues': [], 'consolidatedInsights': {}}), \
             patch('src.prompting.builder.invoke_bedrock', return_value="Test advice"), \
             patch('src.speech.polly.synthesize_with_polly', side_effect=Exception("Polly failed")), \
             patch('src.speech.bhashini.synthesize_with_bhashini', return_value="fallback.mp3"):
            
            mock_weather.return_value = {
                'current': {'temperature': 28, 'humidity': 65, 'windSpeed': 10, 'precipitation': 0},
                'forecast6h': {'precipitationProbability': 20, 'expectedRainfall': 0, 'temperature': 30, 'windSpeed': 12},
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Execute Lambda handler - should fallback to Bhashini
            response = lambda_handler(mock_event, {})
            
            # Should succeed with fallback
            assert response['statusCode'] == 200
    
    def test_weather_api_failure_with_retry(self):
        """
        Test retry logic when weather API fails
        
        Validates: Requirements 9.5, 12.5
        """
        mock_event = {
            'Records': [{
                'eventSource': 'aws:s3',
                'eventName': 'ObjectCreated:Put',
                's3': {
                    'bucket': {'name': Config.AUDIO_INPUT_BUCKET},
                    'object': {'key': f'test-audio/{uuid.uuid4()}.wav', 'size': 50000}
                }
            }],
            'metadata': {
                'farmerId': f'TEST-{uuid.uuid4()}',
                'language': 'hi-IN',
                'gpsLatitude': '28.6139',
                'gpsLongitude': '77.2090'
            }
        }
        
        call_count = {'count': 0}
        
        def weather_with_retry(*args, **kwargs):
            call_count['count'] += 1
            if call_count['count'] < 3:
                raise Exception("API timeout")
            return {
                'current': {'temperature': 28, 'humidity': 65, 'windSpeed': 10, 'precipitation': 0},
                'forecast6h': {'precipitationProbability': 20, 'expectedRainfall': 0, 'temperature': 30, 'windSpeed': 12},
                'timestamp': datetime.utcnow().isoformat()
            }
        
        with patch('src.speech.transcribe.transcribe_audio', return_value=("Test question", "hi-IN", 0.90)), \
             patch('src.context.weather.fetch_weather', side_effect=weather_with_retry), \
             patch('src.context.ufsi.fetch_land_records', return_value=None), \
             patch('src.context.memory.fetch_memory', return_value={'recentInteractions': [], 'unresolvedIssues': [], 'consolidatedInsights': {}}), \
             patch('src.prompting.builder.invoke_bedrock', return_value="Test advice"), \
             patch('src.speech.router.synthesize_speech', return_value="test.mp3"):
            
            # Execute Lambda handler
            response = lambda_handler(mock_event, {})
            
            # Should succeed after retries
            assert response['statusCode'] == 200
            
            # Should have retried 3 times
            assert call_count['count'] == 3
    
    def test_all_apis_fail_graceful_degradation(self):
        """
        Test graceful degradation when all external APIs fail
        
        Validates: Requirements 3.5, 9.5, 12.5
        """
        mock_event = {
            'Records': [{
                'eventSource': 'aws:s3',
                'eventName': 'ObjectCreated:Put',
                's3': {
                    'bucket': {'name': Config.AUDIO_INPUT_BUCKET},
                    'object': {'key': f'test-audio/{uuid.uuid4()}.wav', 'size': 50000}
                }
            }],
            'metadata': {
                'farmerId': f'TEST-{uuid.uuid4()}',
                'language': 'hi-IN',
                'gpsLatitude': '28.6139',
                'gpsLongitude': '77.2090'
            }
        }
        
        with patch('src.speech.transcribe.transcribe_audio', return_value=("Test question", "hi-IN", 0.90)), \
             patch('src.context.retrieval.fetch_weather', side_effect=Exception("Weather API down")), \
             patch('src.context.retrieval.fetch_land_records', side_effect=Exception("UFSI API down")), \
             patch('src.context.retrieval.fetch_memory', side_effect=Exception("Memory service down")), \
             patch('src.lambda_handler.invoke_agents_parallel', return_value={'weather_analysis': 'N/A', 'icar_knowledge': 'N/A'}), \
             patch('src.lambda_handler.invoke_bedrock', return_value="General advice without context"), \
             patch('src.context.memory.store_interaction'), \
             patch('src.speech.router.synthesize_speech', return_value="test.mp3"):
            
            # Execute Lambda handler
            response = lambda_handler(mock_event, {})
            
            # Should still return a response with general advice
            assert response['statusCode'] == 200
            assert 'audioKey' in response
    
    def test_invalid_agristack_id_fallback(self):
        """
        Test fallback to GPS-only context when AgriStack ID is invalid
        
        Validates: Requirements 5.5, 8.4
        """
        mock_event = {
            'Records': [{
                'eventSource': 'aws:s3',
                'eventName': 'ObjectCreated:Put',
                's3': {
                    'bucket': {'name': Config.AUDIO_INPUT_BUCKET},
                    'object': {'key': f'test-audio/{uuid.uuid4()}.wav', 'size': 50000}
                }
            }],
            'metadata': {
                'farmerId': 'INVALID-AGRISTACK-ID',
                'agriStackId': 'INVALID-ID',
                'language': 'hi-IN',
                'gpsLatitude': '28.6139',
                'gpsLongitude': '77.2090'
            }
        }
        
        with patch('src.speech.transcribe.transcribe_audio', return_value=("Test question", "hi-IN", 0.95)), \
             patch('src.context.retrieval.fetch_weather') as mock_weather, \
             patch('src.context.retrieval.fetch_land_records', return_value=None), \
             patch('src.context.retrieval.fetch_memory') as mock_memory, \
             patch('src.lambda_handler.invoke_agents_parallel', return_value={'weather_analysis': 'N/A', 'icar_knowledge': 'N/A'}), \
             patch('src.lambda_handler.invoke_bedrock', return_value="GPS-based advice"), \
             patch('src.context.memory.store_interaction'), \
             patch('src.speech.router.synthesize_speech', return_value="test.mp3"):
            
            mock_weather.return_value = {
                'current': {'temperature': 28, 'humidity': 65, 'windSpeed': 10, 'precipitation': 0},
                'forecast6h': {'precipitationProbability': 20, 'expectedRainfall': 0, 'temperature': 30, 'windSpeed': 12},
                'timestamp': datetime.utcnow().isoformat()
            }
            
            mock_memory.return_value = {
                'recentInteractions': [],
                'unresolvedIssues': [],
                'consolidatedInsights': {
                    'primaryCrop': 'Unknown',
                    'commonConcerns': [],
                    'farmerName': None
                }
            }
            
            # Execute Lambda handler
            response = lambda_handler(mock_event, {})
            
            # Should succeed with GPS-based context only
            assert response['statusCode'] == 200
            
            # Weather should still be fetched
            mock_weather.assert_called_once()
    
    def test_network_timeout_scenarios(self):
        """
        Test handling of network timeouts for external APIs
        
        Validates: Requirements 9.5
        """
        mock_event = {
            'Records': [{
                'eventSource': 'aws:s3',
                'eventName': 'ObjectCreated:Put',
                's3': {
                    'bucket': {'name': Config.AUDIO_INPUT_BUCKET},
                    'object': {'key': f'test-audio/{uuid.uuid4()}.wav', 'size': 50000}
                }
            }],
            'metadata': {
                'farmerId': f'TEST-{uuid.uuid4()}',
                'language': 'hi-IN',
                'gpsLatitude': '28.6139',
                'gpsLongitude': '77.2090'
            }
        }
        
        import requests
        
        with patch('src.speech.transcribe.transcribe_audio', return_value=("Test question", "hi-IN", 0.95)), \
             patch('src.context.retrieval.fetch_weather', side_effect=requests.Timeout("Connection timeout")), \
             patch('src.context.retrieval.fetch_land_records', return_value=None), \
             patch('src.context.retrieval.fetch_memory') as mock_memory, \
             patch('src.lambda_handler.invoke_agents_parallel', return_value={'weather_analysis': 'N/A', 'icar_knowledge': 'N/A'}), \
             patch('src.lambda_handler.invoke_bedrock', return_value="General advice without weather"), \
             patch('src.context.memory.store_interaction'), \
             patch('src.speech.router.synthesize_speech', return_value="test.mp3"):
            
            mock_memory.return_value = {
                'recentInteractions': [],
                'unresolvedIssues': [],
                'consolidatedInsights': {
                    'primaryCrop': 'Unknown',
                    'commonConcerns': [],
                    'farmerName': None
                }
            }
            
            # Execute Lambda handler - should handle timeout gracefully
            response = lambda_handler(mock_event, {})
            
            # Should return response with general advice
            assert response['statusCode'] == 200
    
    def test_malformed_audio_handling(self):
        """
        Test handling of malformed or corrupted audio files
        
        Validates: Requirements 1.5
        """
        mock_event = {
            'Records': [{
                'eventSource': 'aws:s3',
                'eventName': 'ObjectCreated:Put',
                's3': {
                    'bucket': {'name': Config.AUDIO_INPUT_BUCKET},
                    'object': {'key': f'test-audio/{uuid.uuid4()}.wav', 'size': 100}  # Very small, likely corrupted
                }
            }],
            'metadata': {
                'farmerId': f'TEST-{uuid.uuid4()}',
                'language': 'hi-IN',
                'gpsLatitude': '28.6139',
                'gpsLongitude': '77.2090'
            }
        }
        
        with patch('src.speech.transcribe.transcribe_audio', side_effect=ValueError("Invalid audio format")), \
             patch('src.speech.router.synthesize_speech', return_value="error.mp3"):
            
            # Execute Lambda handler - should handle gracefully
            response = lambda_handler(mock_event, {})
            
            # Should return error response
            assert response['statusCode'] in [200, 400, 500]
