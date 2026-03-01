"""Tests for speech processing module"""

import pytest
import sys
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch, MagicMock
import boto3
from moto import mock_aws
import uuid

from src.speech import (
    transcribe_audio,
    synthesize_speech,
    get_all_supported_languages,
    is_language_supported,
    TranscriptionError,
    SpeechRoutingError
)
from src.config import Config


# Supported languages for testing
ALL_SUPPORTED_LANGUAGES = [
    'hi-IN',  # Hindi
    'ta-IN',  # Tamil
    'te-IN',  # Telugu
    'kn-IN',  # Kannada
    'mr-IN',  # Marathi
    'bn-IN',  # Bengali
    'gu-IN',  # Gujarati
    'pa-IN',  # Punjabi
]


@pytest.fixture
def mock_s3_buckets():
    """Create mock S3 buckets for testing"""
    with mock_aws():
        s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
        s3_client.create_bucket(
            Bucket=Config.AUDIO_INPUT_BUCKET,
            CreateBucketConfiguration={'LocationConstraint': Config.AWS_REGION}
        )
        s3_client.create_bucket(
            Bucket=Config.AUDIO_OUTPUT_BUCKET,
            CreateBucketConfiguration={'LocationConstraint': Config.AWS_REGION}
        )
        yield s3_client


class TestSpeechProcessing:
    """Unit tests for speech processing functions"""
    
    def test_all_languages_supported(self):
        """Test that all 8 regional dialects are supported"""
        supported_langs = get_all_supported_languages()
        
        for lang in ALL_SUPPORTED_LANGUAGES:
            assert is_language_supported(lang), f"Language {lang} should be supported"
    
    def test_unsupported_language_raises_error(self):
        """Test that unsupported languages raise appropriate errors"""
        with pytest.raises(SpeechRoutingError):
            synthesize_speech("Test text", "xx-XX", low_bandwidth=False)
    
    @patch('src.speech.bhashini.Config.BHASHINI_API_KEY', 'test_api_key')
    @patch('src.speech.polly.boto3.client')
    def test_synthesize_speech_polly(self, mock_boto_client, mock_s3_buckets):
        """Test speech synthesis using Polly"""
        # Mock Polly client
        mock_polly = Mock()
        mock_audio_stream = MagicMock()
        mock_audio_stream.read.return_value = b'fake_audio_data'
        mock_polly.synthesize_speech.return_value = {
            'AudioStream': mock_audio_stream
        }
        
        # Mock S3 client with proper upload_fileobj support
        mock_s3 = Mock()
        mock_s3.upload_fileobj.return_value = None
        
        def client_factory(service, **kwargs):
            if service == 'polly':
                return mock_polly
            elif service == 's3':
                return mock_s3
            return Mock()
        
        mock_boto_client.side_effect = client_factory
        
        # Test synthesis
        audio_key, service = synthesize_speech("नमस्ते", "hi-IN", low_bandwidth=False)
        
        assert service == 'polly'
        assert audio_key.startswith('responses/')
        assert audio_key.endswith('.mp3')


@pytest.mark.pbt
class TestPropertyBasedSpeech:
    """Property-based tests for speech processing"""
    
    @given(
        language=st.sampled_from(ALL_SUPPORTED_LANGUAGES),
        text=st.text(min_size=10, max_size=500, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd', 'Po', 'Zs')
        ))
    )
    @settings(max_examples=100, deadline=None)
    @patch('src.speech.bhashini.Config.BHASHINI_API_KEY', 'test_api_key')
    @patch('src.speech.transcribe.boto3.client')
    @patch('src.speech.polly.boto3.client')
    @patch('src.speech.bhashini.boto3.client')
    @patch('src.speech.bhashini.requests.post')
    def test_property_19_multi_language_support_coverage(
        self,
        mock_bhashini_post,
        mock_bhashini_boto,
        mock_polly_client,
        mock_transcribe_client,
        language,
        text
    ):
        """
        Feature: vaniverse, Property 19: Multi-Language Support Coverage
        
        Validates: Requirements 7.1
        
        Test that any audio input in supported languages is successfully 
        transcribed and synthesized.
        
        For any language in the supported set (Hindi, Tamil, Telugu, Kannada, 
        Marathi, Bengali, Gujarati, Punjabi), the system should be able to:
        1. Accept the language code
        2. Route to appropriate TTS service
        3. Successfully synthesize speech
        """
        # Skip empty or whitespace-only text
        if not text or not text.strip():
            return
        
        # Mock S3 clients for both Polly and Bhashini
        mock_s3_output = Mock()
        mock_s3_output.upload_fileobj.return_value = None
        mock_s3_output.put_object.return_value = None
        
        mock_bhashini_boto.return_value = mock_s3_output
        
        # Mock Polly client
        mock_polly = Mock()
        mock_audio_stream = MagicMock()
        mock_audio_stream.read.return_value = b'fake_audio_data'
        mock_polly.synthesize_speech.return_value = {
            'AudioStream': mock_audio_stream
        }
        
        # Mock Bhashini response
        mock_bhashini_response = Mock()
        mock_bhashini_response.status_code = 200
        mock_bhashini_response.content = b'fake_bhashini_audio'
        mock_bhashini_post.return_value = mock_bhashini_response
        
        def client_factory(service, **kwargs):
            if service == 'polly':
                return mock_polly
            elif service == 's3':
                return mock_s3_output
            return Mock()
        
        mock_polly_client.side_effect = client_factory
        
        # Test that language is supported
        assert is_language_supported(language), \
            f"Language {language} must be supported"
        
        # Test that synthesis succeeds
        try:
            audio_key, service_used = synthesize_speech(
                text=text,
                language=language,
                low_bandwidth=False
            )
            
            # Verify output
            assert audio_key is not None, "Audio key should not be None"
            assert isinstance(audio_key, str), "Audio key should be a string"
            assert audio_key.startswith('responses/'), \
                "Audio key should start with 'responses/'"
            assert audio_key.endswith('.mp3'), \
                "Audio key should end with '.mp3'"
            
            assert service_used in ['polly', 'bhashini'], \
                f"Service used should be 'polly' or 'bhashini', got {service_used}"
            
        except Exception as e:
            pytest.fail(
                f"Synthesis failed for language {language} with text length {len(text)}. "
                f"Error: {str(e)}"
            )
    
    @given(
        language=st.sampled_from(ALL_SUPPORTED_LANGUAGES),
        low_bandwidth=st.booleans()
    )
    @settings(max_examples=50, deadline=None)
    @patch('src.speech.bhashini.Config.BHASHINI_API_KEY', 'test_api_key')
    @patch('src.speech.polly.boto3.client')
    @patch('src.speech.bhashini.boto3.client')
    @patch('src.speech.bhashini.requests.post')
    def test_low_bandwidth_mode_support(
        self,
        mock_bhashini_post,
        mock_bhashini_boto,
        mock_polly_client,
        language,
        low_bandwidth
    ):
        """
        Test that low-bandwidth mode is supported for all languages.
        
        Validates: Requirements 14.2, 14.3
        """
        # Mock S3 client
        mock_s3 = Mock()
        mock_s3.upload_fileobj.return_value = None
        mock_s3.put_object.return_value = None
        
        mock_bhashini_boto.return_value = mock_s3
        
        # Mock Polly client
        mock_polly = Mock()
        mock_audio_stream = MagicMock()
        mock_audio_stream.read.return_value = b'fake_audio_data'
        mock_polly.synthesize_speech.return_value = {
            'AudioStream': mock_audio_stream
        }
        
        # Mock Bhashini response
        mock_bhashini_response = Mock()
        mock_bhashini_response.status_code = 200
        mock_bhashini_response.content = b'fake_bhashini_audio'
        mock_bhashini_post.return_value = mock_bhashini_response
        
        def client_factory(service, **kwargs):
            if service == 'polly':
                return mock_polly
            elif service == 's3':
                return mock_s3
            return Mock()
        
        mock_polly_client.side_effect = client_factory
        
        # Test synthesis with low_bandwidth flag
        try:
            audio_key, service_used = synthesize_speech(
                text="Test message",
                language=language,
                low_bandwidth=low_bandwidth
            )
            
            assert audio_key is not None
            assert isinstance(audio_key, str)
            
        except Exception as e:
            pytest.fail(
                f"Low-bandwidth synthesis failed for {language} "
                f"(low_bandwidth={low_bandwidth}). Error: {str(e)}"
            )
    
    @given(
        language1=st.sampled_from(ALL_SUPPORTED_LANGUAGES),
        language2=st.sampled_from(ALL_SUPPORTED_LANGUAGES)
    )
    @settings(max_examples=30, deadline=None)
    def test_language_switching(self, language1, language2):
        """
        Test that the system can handle switching between different languages.
        
        Validates: Requirements 7.1, 7.2
        """
        # Both languages should be supported
        assert is_language_supported(language1)
        assert is_language_supported(language2)
        
        # Language switching should not cause errors
        # (This is a structural test - actual synthesis is mocked in other tests)


@pytest.mark.integration
class TestSpeechIntegration:
    """Integration tests for speech processing (require real AWS services)"""
    
    @pytest.mark.skip(reason="Requires real AWS Transcribe service")
    def test_real_transcription(self):
        """Test real transcription with AWS Transcribe"""
        # This test would require:
        # 1. Real audio file uploaded to S3
        # 2. Real AWS credentials
        # 3. Actual Transcribe API calls
        pass
    
    @pytest.mark.skip(reason="Requires real AWS Polly service")
    def test_real_synthesis(self):
        """Test real synthesis with AWS Polly"""
        # This test would require:
        # 1. Real AWS credentials
        # 2. Actual Polly API calls
        # 3. S3 bucket for output
        pass


class TestM4AConversion:
    """Tests for M4A to WAV conversion in Google Speech"""
    
    def test_convert_m4a_to_wav_success(self):
        """Test successful M4A to WAV conversion"""
        with patch.dict('sys.modules', {'google.cloud.speech_v1': MagicMock()}):
            from src.speech.google_speech import convert_m4a_to_wav
            
            # Mock M4A audio data
            mock_m4a_data = b'fake_m4a_audio_data'
            mock_wav_data = b'fake_wav_audio_data'
            
            with patch('subprocess.run') as mock_run, \
                 patch('builtins.open', create=True) as mock_open, \
                 patch('os.path.exists', return_value=True), \
                 patch('os.remove'):
                
                # Mock successful ffmpeg execution
                mock_run.return_value = MagicMock(returncode=0, stderr='')
                
                # Mock file read to return WAV data
                mock_file = MagicMock()
                mock_file.__enter__.return_value.read.return_value = mock_wav_data
                mock_open.return_value = mock_file
                
                result = convert_m4a_to_wav(mock_m4a_data)
                
                # Verify ffmpeg was called with correct parameters
                assert mock_run.called
                call_args = mock_run.call_args[0][0]
                assert 'ffmpeg' in call_args
                assert '-acodec' in call_args
                assert 'pcm_s16le' in call_args
                assert '-ar' in call_args
                assert '16000' in call_args
                assert '-ac' in call_args
                assert '1' in call_args
    
    def test_convert_m4a_ffmpeg_not_found(self):
        """Test error handling when ffmpeg is not installed"""
        with patch.dict('sys.modules', {'google.cloud.speech_v1': MagicMock()}):
            from src.speech.google_speech import convert_m4a_to_wav, GoogleSpeechError
            
            mock_m4a_data = b'fake_m4a_audio_data'
            
            with patch('subprocess.run') as mock_run, \
                 patch('os.path.exists', return_value=True), \
                 patch('os.remove'):
                
                # Simulate ffmpeg not found
                mock_run.side_effect = FileNotFoundError("ffmpeg not found")
                
                with pytest.raises(GoogleSpeechError, match="FFmpeg not found"):
                    convert_m4a_to_wav(mock_m4a_data)
    
    def test_convert_m4a_ffmpeg_failure(self):
        """Test error handling when ffmpeg conversion fails"""
        with patch.dict('sys.modules', {'google.cloud.speech_v1': MagicMock()}):
            from src.speech.google_speech import convert_m4a_to_wav, GoogleSpeechError
            import subprocess
            
            mock_m4a_data = b'fake_m4a_audio_data'
            
            with patch('subprocess.run') as mock_run, \
                 patch('os.path.exists', return_value=True), \
                 patch('os.remove'):
                
                # Simulate ffmpeg failure
                mock_run.side_effect = subprocess.CalledProcessError(
                    1, 'ffmpeg', stderr='Invalid audio format'
                )
                
                with pytest.raises(GoogleSpeechError, match="Audio conversion failed"):
                    convert_m4a_to_wav(mock_m4a_data)
    
    def test_transcribe_with_m4a_conversion(self):
        """Test that M4A files are converted before transcription"""
        with patch.dict('sys.modules', {'google.cloud.speech_v1': MagicMock()}):
            from src.speech.google_speech import transcribe_audio_google
            
            audio_key = 'test_audio.m4a'
            mock_m4a_data = b'fake_m4a_audio_data'
            mock_wav_data = b'fake_wav_audio_data'
            
            with patch('boto3.client') as mock_boto, \
                 patch('src.speech.google_speech.convert_m4a_to_wav') as mock_convert, \
                 patch('src.speech.google_speech.speech_v1.SpeechClient') as mock_client:
                
                # Mock S3 download
                mock_s3 = MagicMock()
                mock_s3.get_object.return_value = {'Body': MagicMock(read=lambda: mock_m4a_data)}
                mock_boto.return_value = mock_s3
                
                # Mock conversion
                mock_convert.return_value = mock_wav_data
                
                # Mock Google Speech API response
                mock_speech_client = MagicMock()
                mock_result = MagicMock()
                mock_result.alternatives = [MagicMock(transcript='test transcript', confidence=0.95)]
                mock_speech_client.recognize.return_value = MagicMock(results=[mock_result])
                mock_client.return_value = mock_speech_client
                
                # Call transcribe
                transcript, lang, confidence = transcribe_audio_google(audio_key, 'hi-IN')
                
                # Verify conversion was called
                assert mock_convert.called
                mock_convert.assert_called_once_with(mock_m4a_data)
                
                # Verify transcription succeeded
                assert transcript == 'test transcript'
                assert confidence == 0.95
    
    def test_transcribe_wav_no_conversion(self):
        """Test that WAV files are not converted"""
        with patch.dict('sys.modules', {'google.cloud.speech_v1': MagicMock()}):
            from src.speech.google_speech import transcribe_audio_google
            
            audio_key = 'test_audio.wav'
            mock_wav_data = b'fake_wav_audio_data'
            
            with patch('boto3.client') as mock_boto, \
                 patch('src.speech.google_speech.convert_m4a_to_wav') as mock_convert, \
                 patch('src.speech.google_speech.speech_v1.SpeechClient') as mock_client:
                
                # Mock S3 download
                mock_s3 = MagicMock()
                mock_s3.get_object.return_value = {'Body': MagicMock(read=lambda: mock_wav_data)}
                mock_boto.return_value = mock_s3
                
                # Mock Google Speech API response
                mock_speech_client = MagicMock()
                mock_result = MagicMock()
                mock_result.alternatives = [MagicMock(transcript='test transcript', confidence=0.95)]
                mock_speech_client.recognize.return_value = MagicMock(results=[mock_result])
                mock_client.return_value = mock_speech_client
                
                # Call transcribe
                transcript, lang, confidence = transcribe_audio_google(audio_key, 'hi-IN')
                
                # Verify conversion was NOT called
                assert not mock_convert.called
                
                # Verify transcription succeeded
                assert transcript == 'test transcript'
