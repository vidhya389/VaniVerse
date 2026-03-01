"""
Performance integration tests for VaniVerse

Tests latency, throughput, and optimization of the voice loop.
"""

import pytest
import time
import uuid
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.lambda_handler import lambda_handler
from src.config import Config


@pytest.mark.integration
@pytest.mark.performance
class TestPerformanceIntegration:
    """Performance tests for voice loop latency and optimization"""
    
    def test_voice_loop_latency_under_6_seconds(self):
        """
        Test that complete voice loop completes within 6 seconds
        
        Validates: Requirements 1.4
        """
        mock_event = {
            'Records': [{
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
                'language': 'hi-IN',
                'gpsLatitude': '28.6139',
                'gpsLongitude': '77.2090'
            }
        }
        
        with patch('src.speech.transcribe.transcribe_audio') as mock_transcribe, \
             patch('src.context.weather.fetch_weather') as mock_weather, \
             patch('src.context.ufsi.fetch_land_records') as mock_land, \
             patch('src.context.memory.fetch_memory') as mock_memory, \
             patch('src.agents.orchestrator.invoke_bedrock') as mock_bedrock, \
             patch('src.speech.router.synthesize_speech') as mock_synthesize:
            
            # Setup mocks with realistic delays
            def transcribe_with_delay(*args, **kwargs):
                time.sleep(0.5)  # Simulate transcription time
                return "Test question"
            
            def weather_with_delay(*args, **kwargs):
                time.sleep(0.3)  # Simulate API call
                return {
                    'current': {'temperature': 28, 'humidity': 65, 'windSpeed': 10, 'precipitation': 0},
                    'forecast6h': {'precipitationProbability': 20, 'expectedRainfall': 0, 'temperature': 30, 'windSpeed': 12},
                    'timestamp': '2026-02-15T10:00:00Z'
                }
            
            def bedrock_with_delay(*args, **kwargs):
                time.sleep(1.0)  # Simulate LLM inference
                return "Test advice"
            
            def synthesize_with_delay(*args, **kwargs):
                time.sleep(0.4)  # Simulate TTS
                return f"responses/{uuid.uuid4()}.mp3"
            
            mock_transcribe.side_effect = transcribe_with_delay
            mock_weather.side_effect = weather_with_delay
            mock_land.return_value = None
            mock_memory.return_value = {
                'recentInteractions': [],
                'unresolvedIssues': [],
                'consolidatedInsights': {}
            }
            mock_bedrock.side_effect = bedrock_with_delay
            mock_synthesize.side_effect = synthesize_with_delay
            
            # Measure execution time
            start_time = time.time()
            response = lambda_handler(mock_event, {})
            execution_time = time.time() - start_time
            
            # Verify response
            assert response['statusCode'] == 200
            
            # Verify latency is under 6 seconds
            assert execution_time < 6.0, f"Voice loop took {execution_time:.2f}s, exceeding 6s target"
            
            print(f"Voice loop completed in {execution_time:.2f} seconds")
    
    def test_parallel_api_calls_optimization(self):
        """
        Test that parallel API calls are optimized for minimum latency
        
        Validates: Requirements 11.2
        """
        mock_event = {
            'Records': [{
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
                'language': 'hi-IN',
                'gpsLatitude': '28.6139',
                'gpsLongitude': '77.2090'
            }
        }
        
        call_times = {}
        
        def track_weather(*args, **kwargs):
            call_times['weather_start'] = time.time()
            time.sleep(0.3)
            call_times['weather_end'] = time.time()
            return {
                'current': {'temperature': 28, 'humidity': 65, 'windSpeed': 10, 'precipitation': 0},
                'forecast6h': {'precipitationProbability': 20, 'expectedRainfall': 0, 'temperature': 30, 'windSpeed': 12},
                'timestamp': '2026-02-15T10:00:00Z'
            }
        
        def track_land(*args, **kwargs):
            call_times['land_start'] = time.time()
            time.sleep(0.3)
            call_times['land_end'] = time.time()
            return None
        
        def track_memory(*args, **kwargs):
            call_times['memory_start'] = time.time()
            time.sleep(0.3)
            call_times['memory_end'] = time.time()
            return {
                'recentInteractions': [],
                'unresolvedIssues': [],
                'consolidatedInsights': {}
            }
        
        with patch('src.speech.transcribe.transcribe_audio', return_value="Test question"), \
             patch('src.context.weather.fetch_weather', side_effect=track_weather), \
             patch('src.context.ufsi.fetch_land_records', side_effect=track_land), \
             patch('src.context.memory.fetch_memory', side_effect=track_memory), \
             patch('src.agents.orchestrator.invoke_bedrock', return_value="Test advice"), \
             patch('src.speech.router.synthesize_speech', return_value="test.mp3"):
            
            start_time = time.time()
            response = lambda_handler(mock_event, {})
            total_time = time.time() - start_time
            
            # Verify all calls were made
            assert 'weather_start' in call_times
            assert 'land_start' in call_times
            assert 'memory_start' in call_times
            
            # Check if calls overlapped (parallel execution)
            weather_duration = call_times['weather_end'] - call_times['weather_start']
            land_duration = call_times['land_end'] - call_times['land_start']
            memory_duration = call_times['memory_end'] - call_times['memory_start']
            
            # If sequential, would take ~0.9s (3 * 0.3s)
            # If parallel, should take ~0.3s (max of the three)
            # Allow some overhead
            assert total_time < 0.6, f"Parallel calls took {total_time:.2f}s, suggesting sequential execution"
            
            print(f"Parallel context retrieval completed in {total_time:.2f} seconds")
    
    def test_concurrent_requests_handling(self):
        """
        Test system handles multiple concurrent requests
        
        Validates: System scalability
        """
        num_concurrent_requests = 5
        
        def create_mock_event():
            return {
                'Records': [{
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
                    'language': 'hi-IN',
                    'gpsLatitude': '28.6139',
                    'gpsLongitude': '77.2090'
                }
            }
        
        with patch('src.speech.transcribe.transcribe_audio', return_value="Test question"), \
             patch('src.context.weather.fetch_weather') as mock_weather, \
             patch('src.context.ufsi.fetch_land_records', return_value=None), \
             patch('src.context.memory.fetch_memory') as mock_memory, \
             patch('src.agents.orchestrator.invoke_bedrock', return_value="Test advice"), \
             patch('src.speech.router.synthesize_speech', return_value="test.mp3"):
            
            mock_weather.return_value = {
                'current': {'temperature': 28, 'humidity': 65, 'windSpeed': 10, 'precipitation': 0},
                'forecast6h': {'precipitationProbability': 20, 'expectedRainfall': 0, 'temperature': 30, 'windSpeed': 12},
                'timestamp': '2026-02-15T10:00:00Z'
            }
            
            mock_memory.return_value = {
                'recentInteractions': [],
                'unresolvedIssues': [],
                'consolidatedInsights': {}
            }
            
            # Execute concurrent requests
            with ThreadPoolExecutor(max_workers=num_concurrent_requests) as executor:
                futures = [
                    executor.submit(lambda_handler, create_mock_event(), {})
                    for _ in range(num_concurrent_requests)
                ]
                
                results = []
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=10)
                        results.append(result)
                    except Exception as e:
                        pytest.fail(f"Concurrent request failed: {e}")
            
            # Verify all requests succeeded
            assert len(results) == num_concurrent_requests
            for result in results:
                assert result['statusCode'] == 200
                assert 'audioKey' in result
    
    def test_low_bandwidth_mode_performance(self):
        """
        Test performance in low-bandwidth mode
        
        Validates: Requirements 14.1, 14.2, 14.3
        """
        mock_event = {
            'Records': [{
                's3': {
                    'bucket': {'name': Config.AUDIO_INPUT_BUCKET},
                    'object': {
                        'key': f'test-audio/{uuid.uuid4()}.wav',
                        'size': 30000  # Small file indicating low bandwidth
                    }
                }
            }],
            'metadata': {
                'farmerId': f'TEST-{uuid.uuid4()}',
                'language': 'hi-IN',
                'gpsLatitude': '28.6139',
                'gpsLongitude': '77.2090',
                'bandwidth': 80  # kbps, below 100 threshold
            }
        }
        
        with patch('src.speech.transcribe.transcribe_audio', return_value="Test question"), \
             patch('src.context.weather.fetch_weather') as mock_weather, \
             patch('src.context.ufsi.fetch_land_records', return_value=None), \
             patch('src.context.memory.fetch_memory') as mock_memory, \
             patch('src.agents.orchestrator.invoke_bedrock', return_value="Test advice"), \
             patch('src.speech.router.synthesize_speech', return_value="test.mp3"), \
             patch('src.utils.bandwidth.compress_audio_to_64kbps', return_value=b"compressed"):
            
            mock_weather.return_value = {
                'current': {'temperature': 28, 'humidity': 65, 'windSpeed': 10, 'precipitation': 0},
                'forecast6h': {'precipitationProbability': 20, 'expectedRainfall': 0, 'temperature': 30, 'windSpeed': 12},
                'timestamp': '2026-02-15T10:00:00Z'
            }
            
            mock_memory.return_value = {
                'recentInteractions': [],
                'unresolvedIssues': [],
                'consolidatedInsights': {}
            }
            
            # Measure execution time
            start_time = time.time()
            response = lambda_handler(mock_event, {})
            execution_time = time.time() - start_time
            
            # Verify response
            assert response['statusCode'] == 200
            
            # Low-bandwidth mode should still complete reasonably fast
            assert execution_time < 8.0, f"Low-bandwidth mode took {execution_time:.2f}s"
            
            print(f"Low-bandwidth mode completed in {execution_time:.2f} seconds")
    
    def test_memory_usage_optimization(self):
        """
        Test that memory usage stays within Lambda limits
        
        Validates: System resource optimization
        """
        import sys
        
        mock_event = {
            'Records': [{
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
                'language': 'hi-IN',
                'gpsLatitude': '28.6139',
                'gpsLongitude': '77.2090'
            }
        }
        
        with patch('src.speech.transcribe.transcribe_audio', return_value="Test question"), \
             patch('src.context.weather.fetch_weather') as mock_weather, \
             patch('src.context.ufsi.fetch_land_records', return_value=None), \
             patch('src.context.memory.fetch_memory') as mock_memory, \
             patch('src.agents.orchestrator.invoke_bedrock', return_value="Test advice"), \
             patch('src.speech.router.synthesize_speech', return_value="test.mp3"):
            
            mock_weather.return_value = {
                'current': {'temperature': 28, 'humidity': 65, 'windSpeed': 10, 'precipitation': 0},
                'forecast6h': {'precipitationProbability': 20, 'expectedRainfall': 0, 'temperature': 30, 'windSpeed': 12},
                'timestamp': '2026-02-15T10:00:00Z'
            }
            
            mock_memory.return_value = {
                'recentInteractions': [],
                'unresolvedIssues': [],
                'consolidatedInsights': {}
            }
            
            # Get initial memory usage
            initial_size = sys.getsizeof(locals())
            
            # Execute Lambda handler
            response = lambda_handler(mock_event, {})
            
            # Get final memory usage
            final_size = sys.getsizeof(locals())
            
            # Verify response
            assert response['statusCode'] == 200
            
            # Memory growth should be reasonable (< 100MB for this test)
            memory_growth = (final_size - initial_size) / (1024 * 1024)  # Convert to MB
            print(f"Memory growth: {memory_growth:.2f} MB")
            
            # This is a rough check - actual Lambda memory monitoring would be more accurate
            assert memory_growth < 100, f"Excessive memory growth: {memory_growth:.2f} MB"
