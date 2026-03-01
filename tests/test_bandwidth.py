"""
Unit tests for bandwidth detection module.

Tests the bandwidth detection logic that determines whether to activate
low-bandwidth mode based on metadata and file size.
"""

import pytest
import subprocess
import json
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings
from src.utils.bandwidth import (
    detect_bandwidth_mode, 
    get_s3_object_size,
    compress_audio_to_64kbps,
    generate_ussd_fallback
)
from src.config import Config


class TestBandwidthDetection:
    """Test suite for bandwidth detection functionality"""
    
    def test_detect_low_bandwidth_from_metadata(self):
        """Test that low bandwidth is detected from metadata when below threshold"""
        metadata = {'bandwidth': 50}  # 50 kbps, below 100 kbps threshold
        
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=100000):
            mode = detect_bandwidth_mode('test-audio.wav', metadata)
        
        assert mode == 'low'
    
    def test_detect_normal_bandwidth_from_metadata(self):
        """Test that normal bandwidth is detected from metadata when above threshold"""
        metadata = {'bandwidth': 150}  # 150 kbps, above 100 kbps threshold
        
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=100000):
            mode = detect_bandwidth_mode('test-audio.wav', metadata)
        
        assert mode == 'normal'
    
    def test_detect_low_bandwidth_at_threshold(self):
        """Test bandwidth detection at exactly the threshold (99 kbps)"""
        metadata = {'bandwidth': 99}  # Just below threshold
        
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=100000):
            mode = detect_bandwidth_mode('test-audio.wav', metadata)
        
        assert mode == 'low'
    
    def test_detect_normal_bandwidth_at_threshold(self):
        """Test bandwidth detection at exactly the threshold (100 kbps)"""
        metadata = {'bandwidth': 100}  # At threshold
        
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=100000):
            mode = detect_bandwidth_mode('test-audio.wav', metadata)
        
        assert mode == 'normal'
    
    def test_detect_low_bandwidth_from_file_size(self):
        """Test that low bandwidth is detected from small file size"""
        # No metadata provided, should check file size
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=30000):  # 30KB
            mode = detect_bandwidth_mode('test-audio.wav', None)
        
        assert mode == 'low'
    
    def test_detect_normal_bandwidth_from_file_size(self):
        """Test that normal bandwidth is detected from normal file size"""
        # No metadata provided, should check file size
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=100000):  # 100KB
            mode = detect_bandwidth_mode('test-audio.wav', None)
        
        assert mode == 'normal'
    
    def test_file_size_fallback_when_metadata_invalid(self):
        """Test that file size check is used when metadata bandwidth is invalid"""
        metadata = {'bandwidth': 'invalid'}  # Invalid bandwidth value
        
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=30000):
            mode = detect_bandwidth_mode('test-audio.wav', metadata)
        
        assert mode == 'low'
    
    def test_file_size_fallback_when_metadata_missing_bandwidth(self):
        """Test that file size check is used when metadata lacks bandwidth field"""
        metadata = {'other_field': 'value'}  # No bandwidth field
        
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=30000):
            mode = detect_bandwidth_mode('test-audio.wav', metadata)
        
        assert mode == 'low'
    
    def test_metadata_takes_precedence_over_file_size(self):
        """Test that metadata bandwidth takes precedence over file size"""
        metadata = {'bandwidth': 150}  # High bandwidth in metadata
        
        # Even with small file size, metadata should take precedence
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=30000):
            mode = detect_bandwidth_mode('test-audio.wav', metadata)
        
        assert mode == 'normal'
    
    def test_file_size_at_threshold(self):
        """Test file size detection at exactly 50KB threshold"""
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=50000):
            mode = detect_bandwidth_mode('test-audio.wav', None)
        
        assert mode == 'normal'
    
    def test_file_size_just_below_threshold(self):
        """Test file size detection just below 50KB threshold"""
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=49999):
            mode = detect_bandwidth_mode('test-audio.wav', None)
        
        assert mode == 'low'


class TestS3ObjectSize:
    """Test suite for S3 object size retrieval"""
    
    @patch('src.utils.bandwidth.boto3.client')
    def test_get_s3_object_size_success(self, mock_boto_client):
        """Test successful retrieval of S3 object size"""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.head_object.return_value = {'ContentLength': 75000}
        
        size = get_s3_object_size('test-audio.wav')
        
        assert size == 75000
        mock_s3.head_object.assert_called_once_with(
            Bucket=Config.AUDIO_INPUT_BUCKET,
            Key='test-audio.wav'
        )
    
    @patch('src.utils.bandwidth.boto3.client')
    def test_get_s3_object_size_failure_returns_default(self, mock_boto_client):
        """Test that S3 access failure returns default size indicating normal bandwidth"""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.head_object.side_effect = Exception("S3 access error")
        
        size = get_s3_object_size('test-audio.wav')
        
        # Should return 100000 (default indicating normal bandwidth)
        assert size == 100000
    
    @patch('src.utils.bandwidth.boto3.client')
    def test_get_s3_object_size_uses_correct_bucket(self, mock_boto_client):
        """Test that the correct S3 bucket is used"""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.head_object.return_value = {'ContentLength': 50000}
        
        get_s3_object_size('test-audio.wav')
        
        # Verify the correct bucket is used
        call_args = mock_s3.head_object.call_args
        assert call_args[1]['Bucket'] == Config.AUDIO_INPUT_BUCKET


class TestBandwidthEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_metadata_dict(self):
        """Test with empty metadata dictionary"""
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=100000):
            mode = detect_bandwidth_mode('test-audio.wav', {})
        
        assert mode == 'normal'
    
    def test_negative_bandwidth_in_metadata(self):
        """Test handling of negative bandwidth value"""
        metadata = {'bandwidth': -50}
        
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=100000):
            mode = detect_bandwidth_mode('test-audio.wav', metadata)
        
        # Negative bandwidth should be treated as low
        assert mode == 'low'
    
    def test_zero_bandwidth_in_metadata(self):
        """Test handling of zero bandwidth value"""
        metadata = {'bandwidth': 0}
        
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=100000):
            mode = detect_bandwidth_mode('test-audio.wav', metadata)
        
        assert mode == 'low'
    
    def test_very_large_bandwidth(self):
        """Test handling of very large bandwidth value"""
        metadata = {'bandwidth': 10000}  # 10 Mbps
        
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=100000):
            mode = detect_bandwidth_mode('test-audio.wav', metadata)
        
        assert mode == 'normal'
    
    def test_very_small_file_size(self):
        """Test handling of very small file size (1 byte)"""
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=1):
            mode = detect_bandwidth_mode('test-audio.wav', None)
        
        assert mode == 'low'
    
    def test_very_large_file_size(self):
        """Test handling of very large file size (10 MB)"""
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=10000000):
            mode = detect_bandwidth_mode('test-audio.wav', None)
        
        assert mode == 'normal'



class TestAudioCompression:
    """Test suite for audio compression functionality"""
    
    def test_compress_audio_to_64kbps_basic(self):
        """Test basic audio compression functionality"""
        # Create a simple test audio file (mock MP3 data)
        # In a real scenario, this would be actual audio data
        test_audio_data = b'fake_audio_data_for_testing' * 1000  # ~27KB
        
        with patch('subprocess.run') as mock_run:
            # Mock successful ffmpeg execution
            mock_run.return_value = MagicMock(returncode=0)
            
            # Mock the file operations
            with patch('builtins.open', create=True) as mock_open:
                # Mock reading the compressed file
                mock_file = MagicMock()
                mock_file.read.return_value = b'compressed_audio_data'
                mock_open.return_value.__enter__.return_value = mock_file
                
                with patch('tempfile.NamedTemporaryFile') as mock_temp:
                    mock_temp_file = MagicMock()
                    mock_temp_file.name = '/tmp/test_audio.mp3'
                    mock_temp_file.__enter__.return_value = mock_temp_file
                    mock_temp.return_value = mock_temp_file
                    
                    with patch('os.path.exists', return_value=True):
                        with patch('os.remove'):
                            from src.utils.bandwidth import compress_audio_to_64kbps
                            result = compress_audio_to_64kbps(test_audio_data)
            
            # Verify ffmpeg was called with correct parameters
            assert mock_run.called
            call_args = mock_run.call_args[0][0]
            assert 'ffmpeg' in call_args
            assert '-b:a' in call_args
            assert '64k' in call_args
            assert '-ar' in call_args
            assert '22050' in call_args
    
    def test_compress_audio_ffmpeg_parameters(self):
        """Test that ffmpeg is called with correct compression parameters"""
        test_audio_data = b'test_audio'
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_file.read.return_value = b'compressed'
                mock_open.return_value.__enter__.return_value = mock_file
                
                with patch('tempfile.NamedTemporaryFile') as mock_temp:
                    mock_temp_file = MagicMock()
                    mock_temp_file.name = '/tmp/test.mp3'
                    mock_temp_file.__enter__.return_value = mock_temp_file
                    mock_temp.return_value = mock_temp_file
                    
                    with patch('os.path.exists', return_value=True):
                        with patch('os.remove'):
                            from src.utils.bandwidth import compress_audio_to_64kbps
                            compress_audio_to_64kbps(test_audio_data)
            
            # Verify the exact ffmpeg command structure
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == 'ffmpeg'
            assert '-i' in call_args
            assert '-b:a' in call_args
            assert '64k' in call_args
            assert '-ar' in call_args
            assert '22050' in call_args
            assert '-y' in call_args
    
    def test_compress_audio_cleanup_on_success(self):
        """Test that temporary files are cleaned up after successful compression"""
        test_audio_data = b'test_audio'
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_file.read.return_value = b'compressed'
                mock_open.return_value.__enter__.return_value = mock_file
                
                with patch('tempfile.NamedTemporaryFile') as mock_temp:
                    mock_temp_file = MagicMock()
                    mock_temp_file.name = '/tmp/test.mp3'
                    mock_temp_file.__enter__.return_value = mock_temp_file
                    mock_temp.return_value = mock_temp_file
                    
                    with patch('os.path.exists', return_value=True):
                        with patch('os.remove') as mock_remove:
                            from src.utils.bandwidth import compress_audio_to_64kbps
                            compress_audio_to_64kbps(test_audio_data)
                            
                            # Verify cleanup was called
                            assert mock_remove.called
    
    def test_compress_audio_cleanup_on_error(self):
        """Test that temporary files are cleaned up even when compression fails"""
        test_audio_data = b'test_audio'
        
        with patch('subprocess.run') as mock_run:
            # Simulate ffmpeg failure
            mock_run.side_effect = subprocess.CalledProcessError(1, 'ffmpeg')
            
            with patch('tempfile.NamedTemporaryFile') as mock_temp:
                mock_temp_file = MagicMock()
                mock_temp_file.name = '/tmp/test.mp3'
                mock_temp_file.__enter__.return_value = mock_temp_file
                mock_temp.return_value = mock_temp_file
                
                with patch('os.path.exists', return_value=True):
                    with patch('os.remove') as mock_remove:
                        from src.utils.bandwidth import compress_audio_to_64kbps
                        
                        with pytest.raises(subprocess.CalledProcessError):
                            compress_audio_to_64kbps(test_audio_data)
                        
                        # Verify cleanup was still called despite error
                        assert mock_remove.called
    
    def test_compress_audio_handles_missing_ffmpeg(self):
        """Test that appropriate error is raised when ffmpeg is not installed"""
        test_audio_data = b'test_audio'
        
        with patch('subprocess.run') as mock_run:
            # Simulate ffmpeg not found
            mock_run.side_effect = FileNotFoundError("ffmpeg not found")
            
            with patch('tempfile.NamedTemporaryFile') as mock_temp:
                mock_temp_file = MagicMock()
                mock_temp_file.name = '/tmp/test.mp3'
                mock_temp_file.__enter__.return_value = mock_temp_file
                mock_temp.return_value = mock_temp_file
                
                with patch('os.path.exists', return_value=True):
                    with patch('os.remove'):
                        from src.utils.bandwidth import compress_audio_to_64kbps
                        
                        with pytest.raises(FileNotFoundError):
                            compress_audio_to_64kbps(test_audio_data)
    
    def test_compress_audio_empty_input(self):
        """Test compression with empty audio data"""
        test_audio_data = b''
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_file.read.return_value = b''
                mock_open.return_value.__enter__.return_value = mock_file
                
                with patch('tempfile.NamedTemporaryFile') as mock_temp:
                    mock_temp_file = MagicMock()
                    mock_temp_file.name = '/tmp/test.mp3'
                    mock_temp_file.__enter__.return_value = mock_temp_file
                    mock_temp.return_value = mock_temp_file
                    
                    with patch('os.path.exists', return_value=True):
                        with patch('os.remove'):
                            from src.utils.bandwidth import compress_audio_to_64kbps
                            result = compress_audio_to_64kbps(test_audio_data)
                            
                            # Should still return bytes (even if empty)
                            assert isinstance(result, bytes)
    
    def test_compress_audio_large_input(self):
        """Test compression with large audio data"""
        # Simulate a large audio file (5 MB)
        test_audio_data = b'x' * (5 * 1024 * 1024)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                # Compressed should be much smaller
                mock_file.read.return_value = b'compressed' * 1000
                mock_open.return_value.__enter__.return_value = mock_file
                
                with patch('tempfile.NamedTemporaryFile') as mock_temp:
                    mock_temp_file = MagicMock()
                    mock_temp_file.name = '/tmp/test.mp3'
                    mock_temp_file.__enter__.return_value = mock_temp_file
                    mock_temp.return_value = mock_temp_file
                    
                    with patch('os.path.exists', return_value=True):
                        with patch('os.remove'):
                            from src.utils.bandwidth import compress_audio_to_64kbps
                            result = compress_audio_to_64kbps(test_audio_data)
                            
                            assert isinstance(result, bytes)
                            assert len(result) > 0



class TestUSSDFallbackGeneration:
    """Test suite for USSD/SMS fallback generation"""
    
    @patch('src.utils.bandwidth.simplify_advice_for_text')
    def test_generate_ussd_fallback_basic(self, mock_simplify):
        """Test basic USSD fallback generation"""
        mock_simplify.return_value = "Apply fertilizer in morning. Water after 2 hours."
        
        from src.utils.bandwidth import generate_ussd_fallback
        result = generate_ussd_fallback("Long advice text here...")
        
        assert result['type'] == 'ussd_fallback'
        assert 'chunks' in result
        assert 'ussd_menu' in result
        assert isinstance(result['chunks'], list)
        assert len(result['chunks']) > 0
    
    @patch('src.utils.bandwidth.simplify_advice_for_text')
    def test_generate_ussd_fallback_menu_structure(self, mock_simplify):
        """Test that USSD menu has correct structure"""
        mock_simplify.return_value = "Short advice"
        
        from src.utils.bandwidth import generate_ussd_fallback
        result = generate_ussd_fallback("Advice text")
        
        menu = result['ussd_menu']
        assert '1' in menu
        assert '2' in menu
        assert '3' in menu
        assert 'SMS' in menu['1']
        assert 'voice' in menu['2']
        assert 'human' in menu['3']
    
    @patch('src.utils.bandwidth.simplify_advice_for_text')
    def test_generate_ussd_fallback_short_text(self, mock_simplify):
        """Test USSD fallback with text shorter than 160 chars"""
        short_text = "Apply fertilizer now."
        mock_simplify.return_value = short_text
        
        from src.utils.bandwidth import generate_ussd_fallback
        result = generate_ussd_fallback("Original advice")
        
        # Should have exactly one chunk
        assert len(result['chunks']) == 1
        assert result['chunks'][0] == short_text
    
    @patch('src.utils.bandwidth.simplify_advice_for_text')
    def test_generate_ussd_fallback_long_text(self, mock_simplify):
        """Test USSD fallback with text longer than 160 chars"""
        long_text = "A" * 300  # 300 characters
        mock_simplify.return_value = long_text
        
        from src.utils.bandwidth import generate_ussd_fallback
        result = generate_ussd_fallback("Original advice")
        
        # Should have multiple chunks
        assert len(result['chunks']) > 1
        # Each chunk should be <= 160 chars
        for chunk in result['chunks']:
            assert len(chunk) <= 160
    
    @patch('src.utils.bandwidth.simplify_advice_for_text')
    def test_generate_ussd_fallback_exactly_160_chars(self, mock_simplify):
        """Test USSD fallback with text exactly 160 chars"""
        text_160 = "A" * 160
        mock_simplify.return_value = text_160
        
        from src.utils.bandwidth import generate_ussd_fallback
        result = generate_ussd_fallback("Original advice")
        
        # Should have exactly one chunk
        assert len(result['chunks']) == 1
        assert len(result['chunks'][0]) == 160


class TestSimplifyAdviceForText:
    """Test suite for advice simplification"""
    
    @patch('src.utils.bandwidth.boto3.client')
    def test_simplify_advice_basic(self, mock_boto_client):
        """Test basic advice simplification"""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Mock Bedrock response
        mock_response = {
            'body': MagicMock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': '- Apply fertilizer\n- Water crops'}]
        }).encode()
        mock_bedrock.invoke_model.return_value = mock_response
        
        from src.utils.bandwidth import simplify_advice_for_text
        result = simplify_advice_for_text("Long verbose advice about farming...")
        
        assert '- Apply fertilizer' in result
        assert '- Water crops' in result
        mock_bedrock.invoke_model.assert_called_once()
    
    @patch('src.utils.bandwidth.boto3.client')
    def test_simplify_advice_uses_claude(self, mock_boto_client):
        """Test that Claude model is used for simplification"""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_response = {
            'body': MagicMock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Simplified advice'}]
        }).encode()
        mock_bedrock.invoke_model.return_value = mock_response
        
        from src.utils.bandwidth import simplify_advice_for_text
        simplify_advice_for_text("Original advice")
        
        # Verify Claude model ID is used
        call_args = mock_bedrock.invoke_model.call_args
        assert call_args[1]['modelId'] == Config.CLAUDE_MODEL_ID
    
    @patch('src.utils.bandwidth.boto3.client')
    def test_simplify_advice_max_tokens(self, mock_boto_client):
        """Test that max_tokens is set to 300"""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_response = {
            'body': MagicMock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Simplified'}]
        }).encode()
        mock_bedrock.invoke_model.return_value = mock_response
        
        from src.utils.bandwidth import simplify_advice_for_text
        simplify_advice_for_text("Original advice")
        
        # Check the request body
        call_args = mock_bedrock.invoke_model.call_args
        body = json.loads(call_args[1]['body'])
        assert body['max_tokens'] == 300
    
    @patch('src.utils.bandwidth.boto3.client')
    def test_simplify_advice_removes_extra_whitespace(self, mock_boto_client):
        """Test that extra whitespace is cleaned up"""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_response = {
            'body': MagicMock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Text  with   extra    spaces'}]
        }).encode()
        mock_bedrock.invoke_model.return_value = mock_response
        
        from src.utils.bandwidth import simplify_advice_for_text
        result = simplify_advice_for_text("Original advice")
        
        # Should have single spaces only
        assert '  ' not in result
        assert result == 'Text with extra spaces'
    
    @patch('src.utils.bandwidth.boto3.client')
    def test_simplify_advice_fallback_on_error(self, mock_boto_client):
        """Test fallback behavior when Bedrock fails"""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Simulate Bedrock failure
        mock_bedrock.invoke_model.side_effect = Exception("Bedrock error")
        
        from src.utils.bandwidth import simplify_advice_for_text
        long_advice = "A" * 300
        result = simplify_advice_for_text(long_advice)
        
        # Should return truncated text with ellipsis
        assert len(result) <= 283  # 280 + '...'
        assert result.endswith('...')
    
    @patch('src.utils.bandwidth.boto3.client')
    def test_simplify_advice_fallback_short_text(self, mock_boto_client):
        """Test fallback with text shorter than 280 chars"""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        mock_bedrock.invoke_model.side_effect = Exception("Bedrock error")
        
        from src.utils.bandwidth import simplify_advice_for_text
        short_advice = "Short advice text"
        result = simplify_advice_for_text(short_advice)
        
        # Should return the full text without ellipsis
        assert result == short_advice
        assert not result.endswith('...')
    
    @patch('src.utils.bandwidth.boto3.client')
    def test_simplify_advice_empty_input(self, mock_boto_client):
        """Test simplification with empty input"""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_response = {
            'body': MagicMock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': ''}]
        }).encode()
        mock_bedrock.invoke_model.return_value = mock_response
        
        from src.utils.bandwidth import simplify_advice_for_text
        result = simplify_advice_for_text("")
        
        assert result == ""


class TestBreakIntoSMSChunks:
    """Test suite for SMS chunking helper function"""
    
    def test_break_short_text(self):
        """Test chunking text shorter than max length"""
        from src.utils.bandwidth import _break_into_sms_chunks
        
        text = "Short text"
        chunks = _break_into_sms_chunks(text, max_length=160)
        
        assert len(chunks) == 1
        assert chunks[0] == text
    
    def test_break_exactly_max_length(self):
        """Test chunking text exactly at max length"""
        from src.utils.bandwidth import _break_into_sms_chunks
        
        text = "A" * 160
        chunks = _break_into_sms_chunks(text, max_length=160)
        
        assert len(chunks) == 1
        assert len(chunks[0]) == 160
    
    def test_break_long_text_at_sentence(self):
        """Test that text breaks at sentence boundaries"""
        from src.utils.bandwidth import _break_into_sms_chunks
        
        text = "First sentence here. Second sentence here. " + "A" * 150
        chunks = _break_into_sms_chunks(text, max_length=160)
        
        # Should break after a sentence
        assert len(chunks) > 1
        # First chunk should end with sentence
        assert chunks[0].endswith('.')
    
    def test_break_at_word_boundary(self):
        """Test that text breaks at word boundaries"""
        from src.utils.bandwidth import _break_into_sms_chunks
        
        # Create text with no sentence breaks
        text = "word " * 100  # 500 characters
        chunks = _break_into_sms_chunks(text, max_length=160)
        
        # Should have multiple chunks
        assert len(chunks) > 1
        # Each chunk should not break in the middle of a word
        # (i.e., should not have partial words at boundaries)
        for chunk in chunks:
            # Chunks should end with complete words (no trailing partial words)
            assert chunk.strip() == chunk  # No leading/trailing whitespace
            # If it ends with 'word', that's fine - it's a complete word
            words = chunk.split()
            assert all(w == 'word' for w in words)  # All words should be complete
    
    def test_break_preserves_all_text(self):
        """Test that no text is lost during chunking"""
        from src.utils.bandwidth import _break_into_sms_chunks
        
        text = "This is a long text. " * 20  # ~420 characters
        chunks = _break_into_sms_chunks(text, max_length=160)
        
        # Reconstruct text from chunks
        reconstructed = ' '.join(chunks)
        # Should contain all original words (allowing for whitespace differences)
        original_words = text.split()
        reconstructed_words = reconstructed.split()
        assert original_words == reconstructed_words
    
    def test_break_respects_max_length(self):
        """Test that all chunks respect max length"""
        from src.utils.bandwidth import _break_into_sms_chunks
        
        text = "A" * 500
        chunks = _break_into_sms_chunks(text, max_length=160)
        
        for chunk in chunks:
            assert len(chunk) <= 160
    
    def test_break_at_phrase_boundary(self):
        """Test breaking at phrase boundaries (dash, colon, semicolon)"""
        from src.utils.bandwidth import _break_into_sms_chunks
        
        text = "First part - second part: third part; " + "A" * 150
        chunks = _break_into_sms_chunks(text, max_length=160)
        
        assert len(chunks) > 1
        # Should break at phrase boundary
        assert any(c.endswith(('-', ':', ';')) for c in chunks[:-1])
    
    def test_break_empty_text(self):
        """Test chunking empty text"""
        from src.utils.bandwidth import _break_into_sms_chunks
        
        chunks = _break_into_sms_chunks("", max_length=160)
        
        assert len(chunks) == 1
        assert chunks[0] == ""
    
    def test_break_custom_max_length(self):
        """Test chunking with custom max length"""
        from src.utils.bandwidth import _break_into_sms_chunks
        
        text = "A" * 200
        chunks = _break_into_sms_chunks(text, max_length=50)
        
        for chunk in chunks:
            assert len(chunk) <= 50
        assert len(chunks) >= 4  # 200 / 50 = 4
    
    def test_break_with_multiple_sentences(self):
        """Test chunking text with multiple sentences"""
        from src.utils.bandwidth import _break_into_sms_chunks
        
        text = "Sentence one. Sentence two. Sentence three. " * 5
        chunks = _break_into_sms_chunks(text, max_length=160)
        
        # Should have multiple chunks
        assert len(chunks) > 1
        # Each chunk should be reasonable length
        for chunk in chunks:
            assert len(chunk) <= 160
            assert len(chunk) > 0
    
    def test_break_no_good_break_point(self):
        """Test chunking when no good break point exists"""
        from src.utils.bandwidth import _break_into_sms_chunks
        
        # Very long word with no spaces
        text = "A" * 500
        chunks = _break_into_sms_chunks(text, max_length=160)
        
        # Should still break at max_length
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 160
    
    def test_break_strips_whitespace(self):
        """Test that chunks have whitespace stripped"""
        from src.utils.bandwidth import _break_into_sms_chunks
        
        text = "First sentence.   Second sentence.   " + "A" * 150
        chunks = _break_into_sms_chunks(text, max_length=160)
        
        # Chunks should not have leading/trailing whitespace
        for chunk in chunks:
            assert chunk == chunk.strip()


class TestUSSDFallbackIntegration:
    """Integration tests for USSD fallback functionality"""
    
    @patch('src.utils.bandwidth.boto3.client')
    def test_full_ussd_fallback_flow(self, mock_boto_client):
        """Test complete USSD fallback generation flow"""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Mock Claude response with realistic advice
        mock_response = {
            'body': MagicMock()
        }
        simplified = "- Apply urea fertilizer 50kg/acre\n- Water immediately after\n- Best time: early morning"
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': simplified}]
        }).encode()
        mock_bedrock.invoke_model.return_value = mock_response
        
        from src.utils.bandwidth import generate_ussd_fallback
        
        original_advice = """
        Good morning! Before I answer your question about fertilizer, 
        how is the pest issue on your rice crop that you mentioned last week?
        
        For your current question about fertilizer application, I recommend 
        applying urea fertilizer at 50 kg per acre. Based on your soil records 
        showing medium nitrogen levels, this amount is appropriate. Water the 
        field immediately after application. The best time is early morning 
        between 6-8 AM when temperature is moderate.
        """
        
        result = generate_ussd_fallback(original_advice)
        
        # Verify structure
        assert result['type'] == 'ussd_fallback'
        assert len(result['chunks']) > 0
        assert all(len(chunk) <= 160 for chunk in result['chunks'])
        assert '1' in result['ussd_menu']
        assert '2' in result['ussd_menu']
        assert '3' in result['ussd_menu']
    
    @patch('src.utils.bandwidth.boto3.client')
    def test_ussd_fallback_with_very_long_advice(self, mock_boto_client):
        """Test USSD fallback with very long advice text"""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Mock Claude response
        mock_response = {
            'body': MagicMock()
        }
        # Simulate a long simplified response
        long_simplified = "- Action 1: detailed instruction here. " * 10
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': long_simplified}]
        }).encode()
        mock_bedrock.invoke_model.return_value = mock_response
        
        from src.utils.bandwidth import generate_ussd_fallback
        
        very_long_advice = "Very detailed agricultural advice. " * 50
        result = generate_ussd_fallback(very_long_advice)
        
        # Should have multiple chunks
        assert len(result['chunks']) > 1
        # All chunks should be valid SMS size
        for chunk in result['chunks']:
            assert len(chunk) <= 160
            assert len(chunk) > 0
    
    @patch('src.utils.bandwidth.boto3.client')
    def test_ussd_fallback_handles_bedrock_failure(self, mock_boto_client):
        """Test USSD fallback when Bedrock fails"""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        mock_bedrock.invoke_model.side_effect = Exception("Bedrock unavailable")
        
        from src.utils.bandwidth import generate_ussd_fallback
        
        advice = "Apply fertilizer in the morning. Water after application."
        result = generate_ussd_fallback(advice)
        
        # Should still return valid structure with fallback text
        assert result['type'] == 'ussd_fallback'
        assert len(result['chunks']) > 0
        assert 'ussd_menu' in result



# Property-Based Tests
class TestBandwidthPropertyTests:
    """Property-based tests for bandwidth detection and low-bandwidth mode activation"""
    
    @given(
        bandwidth_kbps=st.floats(min_value=0.1, max_value=99.9),
        audio_file_key=st.text(min_size=5, max_size=50, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            whitelist_characters='-_.'
        ))
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.pbt
    def test_property_39_low_bandwidth_mode_activation(self, bandwidth_kbps, audio_file_key):
        """
        Property 39: Low-Bandwidth Mode Activation
        
        **Validates: Requirements 14.1, 14.2, 14.3**
        
        For any session with detected network speed below 100 kbps, the system 
        should activate low-bandwidth mode with compressed audio processing.
        
        This property verifies that:
        1. Any bandwidth < 100 kbps triggers low-bandwidth mode
        2. The mode detection is consistent across different file keys
        3. Metadata bandwidth takes precedence over file size
        """
        # Setup: Create metadata with bandwidth below threshold
        metadata = {'bandwidth': bandwidth_kbps}
        
        # Mock S3 file size (should be ignored when metadata is present)
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=100000):
            # Action: Detect bandwidth mode
            mode = detect_bandwidth_mode(audio_file_key, metadata)
        
        # Verify: Low-bandwidth mode should be activated
        assert mode == 'low', (
            f"Expected 'low' bandwidth mode for {bandwidth_kbps} kbps, "
            f"but got '{mode}'. Requirements 14.1 states that network speed "
            f"below 100 kbps should activate low-bandwidth mode."
        )
    
    @given(
        bandwidth_kbps=st.floats(min_value=100.0, max_value=10000.0),
        audio_file_key=st.text(min_size=5, max_size=50, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            whitelist_characters='-_.'
        ))
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.pbt
    def test_property_39_normal_bandwidth_mode(self, bandwidth_kbps, audio_file_key):
        """
        Property 39 (complement): Normal Bandwidth Mode
        
        **Validates: Requirements 14.1, 14.6**
        
        For any session with detected network speed at or above 100 kbps, 
        the system should use normal bandwidth mode (not low-bandwidth mode).
        
        This is the complement of Property 39, ensuring the threshold works
        correctly in both directions.
        """
        # Setup: Create metadata with bandwidth at or above threshold
        metadata = {'bandwidth': bandwidth_kbps}
        
        # Mock S3 file size (should be ignored when metadata is present)
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=100000):
            # Action: Detect bandwidth mode
            mode = detect_bandwidth_mode(audio_file_key, metadata)
        
        # Verify: Normal bandwidth mode should be used
        assert mode == 'normal', (
            f"Expected 'normal' bandwidth mode for {bandwidth_kbps} kbps, "
            f"but got '{mode}'. Requirements 14.1 states that network speed "
            f"at or above 100 kbps should use normal mode."
        )
    
    @given(
        file_size_bytes=st.integers(min_value=1, max_value=49999),
        audio_file_key=st.text(min_size=5, max_size=50, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            whitelist_characters='-_.'
        ))
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.pbt
    def test_property_39_file_size_proxy_low_bandwidth(self, file_size_bytes, audio_file_key):
        """
        Property 39 (file size proxy): Low-Bandwidth Detection via File Size
        
        **Validates: Requirements 14.1, 14.2**
        
        When metadata is unavailable, for any audio file smaller than 50KB,
        the system should infer low-bandwidth conditions and activate 
        low-bandwidth mode.
        
        This tests the fallback mechanism when client doesn't report bandwidth.
        """
        # Setup: No metadata provided, rely on file size
        metadata = None
        
        # Mock S3 file size below threshold
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=file_size_bytes):
            # Action: Detect bandwidth mode
            mode = detect_bandwidth_mode(audio_file_key, metadata)
        
        # Verify: Low-bandwidth mode should be activated
        assert mode == 'low', (
            f"Expected 'low' bandwidth mode for file size {file_size_bytes} bytes, "
            f"but got '{mode}'. Small file sizes (<50KB) indicate poor network "
            f"conditions and should trigger low-bandwidth mode."
        )
    
    @given(
        audio_data=st.binary(min_size=1000, max_size=100000)
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.pbt
    def test_property_39_compressed_audio_processing(self, audio_data):
        """
        Property 39 (compression): Compressed Audio Processing in Low-Bandwidth Mode
        
        **Validates: Requirements 14.2, 14.3**
        
        For any audio data in low-bandwidth mode, the system should apply
        compression to 64 kbps with reduced sample rate (22050 Hz) to optimize
        for 2G network speeds.
        
        This verifies that the compression function is called and produces
        valid compressed output.
        """
        # Mock ffmpeg execution
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            # Mock file operations
            with patch('builtins.open', create=True) as mock_open:
                # Mock reading the compressed file
                compressed_data = b'compressed_audio_' + audio_data[:100]
                mock_file = MagicMock()
                mock_file.read.return_value = compressed_data
                mock_open.return_value.__enter__.return_value = mock_file
                
                with patch('tempfile.NamedTemporaryFile') as mock_temp:
                    mock_temp_file = MagicMock()
                    mock_temp_file.name = '/tmp/test_audio.mp3'
                    mock_temp_file.__enter__.return_value = mock_temp_file
                    mock_temp.return_value = mock_temp_file
                    
                    with patch('os.path.exists', return_value=True):
                        with patch('os.remove'):
                            # Action: Compress audio
                            result = compress_audio_to_64kbps(audio_data)
            
            # Verify: ffmpeg was called with correct compression parameters
            assert mock_run.called, "ffmpeg should be called for compression"
            call_args = mock_run.call_args[0][0]
            
            # Verify 64 kbps bitrate (Requirement 14.2)
            assert '-b:a' in call_args, "Bitrate parameter should be specified"
            bitrate_index = call_args.index('-b:a')
            assert call_args[bitrate_index + 1] == '64k', (
                "Requirement 14.2: Audio should be compressed to 64 kbps for 2G networks"
            )
            
            # Verify reduced sample rate (Requirement 14.3)
            assert '-ar' in call_args, "Sample rate parameter should be specified"
            sample_rate_index = call_args.index('-ar')
            assert call_args[sample_rate_index + 1] == '22050', (
                "Requirement 14.3: Sample rate should be reduced to 22050 Hz for smaller file size"
            )
            
            # Verify result is valid bytes
            assert isinstance(result, bytes), "Compressed output should be bytes"
            assert len(result) > 0, "Compressed output should not be empty"
    
    @given(
        bandwidth_kbps=st.floats(min_value=0.1, max_value=99.9),
        file_size_bytes=st.integers(min_value=50000, max_value=1000000)
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.pbt
    def test_property_39_metadata_precedence(self, bandwidth_kbps, file_size_bytes):
        """
        Property 39 (precedence): Metadata Bandwidth Takes Precedence
        
        **Validates: Requirements 14.1**
        
        For any session where both metadata bandwidth and file size are available,
        the metadata bandwidth should take precedence in determining the mode,
        even if file size would suggest a different mode.
        
        This ensures consistent behavior when client reports bandwidth.
        """
        # Setup: Low bandwidth in metadata, but large file size
        metadata = {'bandwidth': bandwidth_kbps}
        audio_file_key = 'test-audio.wav'
        
        # Mock large file size that would normally indicate normal bandwidth
        with patch('src.utils.bandwidth.get_s3_object_size', return_value=file_size_bytes):
            # Action: Detect bandwidth mode
            mode = detect_bandwidth_mode(audio_file_key, metadata)
        
        # Verify: Should use low-bandwidth mode based on metadata, not file size
        assert mode == 'low', (
            f"Expected 'low' bandwidth mode based on metadata ({bandwidth_kbps} kbps), "
            f"even though file size ({file_size_bytes} bytes) is large. "
            f"Metadata should take precedence over file size."
        )

    @given(
        execution_time_seconds=st.floats(min_value=15.1, max_value=60.0),
        advice_text=st.text(min_size=50, max_size=500, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po'),
            blacklist_characters='\n\r\t'
        ))
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.pbt
    def test_property_40_ussd_fallback_trigger(self, execution_time_seconds, advice_text):
        """
        Property 40: USSD Fallback Trigger
        
        **Validates: Requirements 14.4, 14.5**
        
        For any voice loop that exceeds 15 seconds in low-bandwidth mode,
        the system should offer a USSD/SMS text fallback option.
        
        This ensures farmers on slow networks can still receive advice
        via text when voice delivery times out.
        """
        # Setup: Simulate low-bandwidth mode with timeout
        bandwidth_mode = 'low'
        
        # Mock the simplify_advice_for_text function to avoid Bedrock calls
        with patch('src.utils.bandwidth.simplify_advice_for_text') as mock_simplify:
            # Return a simplified version of the advice
            simplified = advice_text[:200] if len(advice_text) > 200 else advice_text
            mock_simplify.return_value = simplified
            
            # Action: Generate USSD fallback when execution time exceeds 15 seconds
            # This simulates the orchestrator detecting timeout and offering fallback
            if bandwidth_mode == 'low' and execution_time_seconds > 15:
                fallback = generate_ussd_fallback(advice_text)
                
                # Verify: USSD fallback should be offered (Requirement 14.4)
                assert fallback is not None, (
                    f"Requirement 14.4: Voice loop exceeded 15 seconds ({execution_time_seconds:.1f}s) "
                    f"in low-bandwidth mode, USSD fallback should be offered"
                )
                
                # Verify: Fallback has correct structure
                assert fallback['type'] == 'ussd_fallback', (
                    "USSD fallback should have type 'ussd_fallback'"
                )
                
                # Verify: Simplified text-based advice is provided (Requirement 14.5)
                assert 'chunks' in fallback, (
                    "Requirement 14.5: USSD fallback should provide simplified text chunks"
                )
                assert isinstance(fallback['chunks'], list), (
                    "USSD fallback chunks should be a list"
                )
                assert len(fallback['chunks']) > 0, (
                    "USSD fallback should have at least one text chunk"
                )
                
                # Verify: Each chunk is SMS-sized (160 characters max)
                for i, chunk in enumerate(fallback['chunks']):
                    assert len(chunk) <= 160, (
                        f"Requirement 14.5: SMS chunk {i+1} exceeds 160 characters "
                        f"(actual: {len(chunk)} chars). SMS standard requires max 160 chars."
                    )
                    assert isinstance(chunk, str), (
                        f"SMS chunk {i+1} should be a string"
                    )
                    assert len(chunk.strip()) > 0, (
                        f"SMS chunk {i+1} should not be empty"
                    )
                
                # Verify: USSD menu is provided (Requirement 14.4)
                assert 'ussd_menu' in fallback, (
                    "Requirement 14.4: USSD fallback should include menu options"
                )
                assert isinstance(fallback['ussd_menu'], dict), (
                    "USSD menu should be a dictionary"
                )
                
                # Verify: Menu has expected options
                menu = fallback['ussd_menu']
                assert '1' in menu, "USSD menu should have option 1 (SMS delivery)"
                assert '2' in menu, "USSD menu should have option 2 (retry voice)"
                assert '3' in menu, "USSD menu should have option 3 (human advisor)"
                
                # Verify: Menu options are descriptive
                assert 'SMS' in menu['1'] or 'sms' in menu['1'].lower(), (
                    "Option 1 should mention SMS delivery"
                )
                assert 'voice' in menu['2'].lower() or 'again' in menu['2'].lower(), (
                    "Option 2 should mention retrying voice"
                )
                assert 'human' in menu['3'].lower() or 'advisor' in menu['3'].lower(), (
                    "Option 3 should mention human advisor"
                )
                
                # Verify: Simplified advice was called
                mock_simplify.assert_called_once_with(advice_text)
