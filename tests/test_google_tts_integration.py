"""
Tests for Google TTS integration in the speech router

Validates that:
1. Google TTS is prioritized for Tamil and other Indian languages (except Hindi)
2. Polly is prioritized for Hindi
3. Fallback logic works correctly
"""

import pytest
from unittest.mock import patch, MagicMock
from src.speech.router import (
    synthesize_speech,
    get_preferred_service,
    is_language_supported,
    get_service_info,
    SpeechRoutingError
)


class TestGoogleTTSIntegration:
    """Test Google TTS integration in speech router"""
    
    def test_tamil_uses_google_tts(self):
        """Tamil should use Google TTS as preferred service"""
        preferred = get_preferred_service('ta-IN')
        assert preferred == 'google_tts', "Tamil should prefer Google TTS"
    
    def test_hindi_uses_polly(self):
        """Hindi should use Polly as preferred service"""
        preferred = get_preferred_service('hi-IN')
        assert preferred == 'polly', "Hindi should prefer Polly"
    
    def test_telugu_uses_google_tts(self):
        """Telugu should use Google TTS as preferred service"""
        preferred = get_preferred_service('te-IN')
        assert preferred == 'google_tts', "Telugu should prefer Google TTS"
    
    def test_kannada_uses_google_tts(self):
        """Kannada should use Google TTS as preferred service"""
        preferred = get_preferred_service('kn-IN')
        assert preferred == 'google_tts', "Kannada should prefer Google TTS"
    
    def test_malayalam_uses_google_tts(self):
        """Malayalam should use Google TTS as preferred service"""
        preferred = get_preferred_service('ml-IN')
        assert preferred == 'google_tts', "Malayalam should prefer Google TTS"
    
    def test_tamil_is_supported(self):
        """Tamil should be supported by the router"""
        assert is_language_supported('ta-IN'), "Tamil should be supported"
    
    def test_service_info_for_tamil(self):
        """Service info should show Google TTS support for Tamil"""
        info = get_service_info('ta-IN')
        assert info['language'] == 'ta-IN'
        assert info['preferred_service'] == 'google_tts'
        assert info['google_tts_supported'] is True
        assert info['is_supported'] is True
    
    def test_service_info_for_hindi(self):
        """Service info should show Polly support for Hindi"""
        info = get_service_info('hi-IN')
        assert info['language'] == 'hi-IN'
        assert info['preferred_service'] == 'polly'
        assert info['polly_supported'] is True
        assert info['is_supported'] is True
    
    @patch('src.speech.router.synthesize_with_google_tts_retry')
    @patch('src.speech.router.Config')
    def test_tamil_synthesis_calls_google_tts(self, mock_config, mock_google_tts):
        """Tamil synthesis should call Google TTS"""
        mock_config.USE_MOCK_TTS = False
        mock_google_tts.return_value = 'test-audio-key.mp3'
        
        audio_key, service = synthesize_speech('வணக்கம்', 'ta-IN')
        
        assert service == 'google_tts'
        assert audio_key == 'test-audio-key.mp3'
        mock_google_tts.assert_called_once()
    
    @patch('src.speech.router.synthesize_with_polly_retry')
    @patch('src.speech.router.Config')
    def test_hindi_synthesis_calls_polly(self, mock_config, mock_polly):
        """Hindi synthesis should call Polly"""
        mock_config.USE_MOCK_TTS = False
        mock_polly.return_value = 'test-audio-key.mp3'
        
        audio_key, service = synthesize_speech('नमस्ते', 'hi-IN')
        
        assert service == 'polly'
        assert audio_key == 'test-audio-key.mp3'
        mock_polly.assert_called_once()
    
    @patch('src.speech.router.synthesize_with_polly_retry')
    @patch('src.speech.router.synthesize_with_google_tts_retry')
    @patch('src.speech.router.Config')
    def test_tamil_fallback_to_polly_on_google_failure(
        self, mock_config, mock_google_tts, mock_polly
    ):
        """Tamil should fallback to Polly if Google TTS fails"""
        mock_config.USE_MOCK_TTS = False
        mock_google_tts.side_effect = Exception("Google TTS failed")
        mock_polly.return_value = 'fallback-audio-key.mp3'
        
        audio_key, service = synthesize_speech('வணக்கம்', 'ta-IN')
        
        assert service == 'polly'
        assert audio_key == 'fallback-audio-key.mp3'
        mock_google_tts.assert_called_once()
        mock_polly.assert_called_once()
    
    @patch('src.speech.router.synthesize_with_google_tts_retry')
    @patch('src.speech.router.synthesize_with_polly_retry')
    @patch('src.speech.router.Config')
    def test_hindi_fallback_to_google_on_polly_failure(
        self, mock_config, mock_polly, mock_google_tts
    ):
        """Hindi should fallback to Google TTS if Polly fails"""
        mock_config.USE_MOCK_TTS = False
        mock_polly.side_effect = Exception("Polly failed")
        mock_google_tts.return_value = 'fallback-audio-key.mp3'
        
        audio_key, service = synthesize_speech('नमस्ते', 'hi-IN')
        
        assert service == 'google_tts'
        assert audio_key == 'fallback-audio-key.mp3'
        mock_polly.assert_called_once()
        mock_google_tts.assert_called_once()
    
    @patch('src.speech.router.Config')
    def test_empty_text_raises_error(self, mock_config):
        """Empty text should raise SpeechRoutingError"""
        mock_config.USE_MOCK_TTS = False
        
        with pytest.raises(SpeechRoutingError, match="Cannot synthesize empty text"):
            synthesize_speech('', 'ta-IN')
    
    @patch('src.speech.router.Config')
    def test_missing_language_raises_error(self, mock_config):
        """Missing language should raise SpeechRoutingError"""
        mock_config.USE_MOCK_TTS = False
        
        with pytest.raises(SpeechRoutingError, match="Language code is required"):
            synthesize_speech('test text', '')
