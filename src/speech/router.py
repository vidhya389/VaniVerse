"""Speech service routing logic for VaniVerse"""

import uuid
from typing import Tuple, Optional
from src.config import Config
from src.speech.polly import (
    synthesize_with_polly_retry,
    is_polly_supported,
    get_supported_polly_languages
)
from src.speech.bhashini import (
    synthesize_with_bhashini_retry,
    is_bhashini_supported,
    get_supported_bhashini_languages
)
from src.speech.google_tts import (
    synthesize_with_google_tts_retry,
    is_google_tts_supported,
    get_supported_google_tts_languages
)


class SpeechRoutingError(Exception):
    """Exception raised for speech routing errors"""
    pass


def synthesize_speech(
    text: str,
    language: str,
    low_bandwidth: bool = False,
    request_id: Optional[str] = None
) -> Tuple[str, str]:
    """
    Synthesize speech by routing to the appropriate TTS service.
    
    Priority order:
    1. Google TTS for Tamil and other Indian languages (better script support)
    2. Polly for Hindi (good quality, lower latency)
    3. Bhashini as fallback
    
    Args:
        text: Text to convert to speech
        language: Language code (e.g., 'hi-IN', 'ta-IN')
        low_bandwidth: Whether to use low-bandwidth optimized settings
        request_id: Optional request ID for organizing output files
    
    Returns:
        Tuple of (audio_s3_key, service_used)
        where service_used is either 'google_tts', 'polly', 'bhashini', or 'mock'
    
    Raises:
        SpeechRoutingError: If synthesis fails on all services
    """
    # Use mock TTS if configured
    if Config.USE_MOCK_TTS:
        return _mock_tts(text, language, request_id), 'mock'
    
    if not text or not text.strip():
        raise SpeechRoutingError("Cannot synthesize empty text")
    
    if not language:
        raise SpeechRoutingError("Language code is required")
    
    # Priority 1: Use Google TTS for Tamil and other Indian languages (except Hindi)
    # Google TTS has better support for Tamil script (தமிழ்) than Polly
    if language != 'hi-IN' and is_google_tts_supported(language):
        try:
            audio_key = synthesize_with_google_tts_retry(text, language, low_bandwidth, request_id)
            return audio_key, 'google_tts'
        except Exception as google_error:
            # If Google TTS fails, try Polly as fallback
            if is_polly_supported(language):
                try:
                    audio_key = synthesize_with_polly_retry(text, language, low_bandwidth, request_id)
                    return audio_key, 'polly'
                except Exception as polly_error:
                    # If both fail, try Bhashini
                    if is_bhashini_supported(language):
                        try:
                            audio_key = synthesize_with_bhashini_retry(text, language, low_bandwidth)
                            return audio_key, 'bhashini'
                        except Exception as bhashini_error:
                            raise SpeechRoutingError(
                                f"All TTS services failed. "
                                f"Google error: {google_error}. "
                                f"Polly error: {polly_error}. "
                                f"Bhashini error: {bhashini_error}"
                            )
                    else:
                        raise SpeechRoutingError(
                            f"Google TTS and Polly failed, Bhashini doesn't support {language}. "
                            f"Google error: {google_error}. Polly error: {polly_error}"
                        )
            # If Polly doesn't support, try Bhashini
            elif is_bhashini_supported(language):
                try:
                    audio_key = synthesize_with_bhashini_retry(text, language, low_bandwidth)
                    return audio_key, 'bhashini'
                except Exception as bhashini_error:
                    raise SpeechRoutingError(
                        f"Google TTS and Bhashini failed. "
                        f"Google error: {google_error}. Bhashini error: {bhashini_error}"
                    )
            else:
                raise SpeechRoutingError(
                    f"Google TTS failed and no other service supports {language}. Error: {google_error}"
                )
    
    # Priority 2: Use Polly for Hindi (good quality, lower latency)
    elif is_polly_supported(language):
        try:
            audio_key = synthesize_with_polly_retry(text, language, low_bandwidth, request_id)
            return audio_key, 'polly'
        except Exception as polly_error:
            # If Polly fails, try Google TTS as fallback
            if is_google_tts_supported(language):
                try:
                    audio_key = synthesize_with_google_tts_retry(text, language, low_bandwidth, request_id)
                    return audio_key, 'google_tts'
                except Exception as google_error:
                    # If both fail, try Bhashini
                    if is_bhashini_supported(language):
                        try:
                            audio_key = synthesize_with_bhashini_retry(text, language, low_bandwidth)
                            return audio_key, 'bhashini'
                        except Exception as bhashini_error:
                            raise SpeechRoutingError(
                                f"All TTS services failed. "
                                f"Polly error: {polly_error}. "
                                f"Google error: {google_error}. "
                                f"Bhashini error: {bhashini_error}"
                            )
                    else:
                        raise SpeechRoutingError(
                            f"Polly and Google TTS failed, Bhashini doesn't support {language}. "
                            f"Polly error: {polly_error}. Google error: {google_error}"
                        )
            # If Google doesn't support, try Bhashini
            elif is_bhashini_supported(language):
                try:
                    audio_key = synthesize_with_bhashini_retry(text, language, low_bandwidth)
                    return audio_key, 'bhashini'
                except Exception as bhashini_error:
                    raise SpeechRoutingError(
                        f"Polly and Bhashini failed. "
                        f"Polly error: {polly_error}. Bhashini error: {bhashini_error}"
                    )
            else:
                raise SpeechRoutingError(
                    f"Polly failed and no other service supports {language}. Error: {polly_error}"
                )
    
    # Priority 3: Use Bhashini if neither Google nor Polly support the language
    elif is_bhashini_supported(language):
        try:
            audio_key = synthesize_with_bhashini_retry(text, language, low_bandwidth)
            return audio_key, 'bhashini'
        except Exception as bhashini_error:
            raise SpeechRoutingError(
                f"Bhashini synthesis failed for {language}. Error: {bhashini_error}"
            )
    
    # Language not supported by any service
    else:
        supported_langs = get_all_supported_languages()
        raise SpeechRoutingError(
            f"Language {language} is not supported by any TTS service. "
            f"Supported languages: {', '.join(supported_langs)}"
        )


def get_all_supported_languages() -> list:
    """
    Get list of all languages supported by any TTS service.
    
    Returns:
        List of unique language codes
    """
    polly_langs = set(get_supported_polly_languages())
    bhashini_langs = set(get_supported_bhashini_languages())
    google_langs = set(get_supported_google_tts_languages())
    all_langs = polly_langs.union(bhashini_langs).union(google_langs)
    return sorted(list(all_langs))


def get_preferred_service(language: str) -> str:
    """
    Get the preferred TTS service for a given language.
    
    Args:
        language: Language code
    
    Returns:
        'google_tts', 'polly', 'bhashini', or 'unsupported'
    """
    # Prefer Google TTS for Tamil and other Indian languages (except Hindi)
    if language != 'hi-IN' and is_google_tts_supported(language):
        return 'google_tts'
    # Prefer Polly for Hindi
    elif is_polly_supported(language):
        return 'polly'
    elif is_bhashini_supported(language):
        return 'bhashini'
    else:
        return 'unsupported'


def is_language_supported(language: str) -> bool:
    """
    Check if a language is supported by any TTS service.
    
    Args:
        language: Language code to check
    
    Returns:
        True if supported, False otherwise
    """
    return (is_google_tts_supported(language) or 
            is_polly_supported(language) or 
            is_bhashini_supported(language))


def get_service_info(language: str) -> dict:
    """
    Get information about which service will be used for a language.
    
    Args:
        language: Language code
    
    Returns:
        Dictionary with service information
    """
    preferred = get_preferred_service(language)
    
    return {
        'language': language,
        'preferred_service': preferred,
        'google_tts_supported': is_google_tts_supported(language),
        'polly_supported': is_polly_supported(language),
        'bhashini_supported': is_bhashini_supported(language),
        'is_supported': preferred != 'unsupported'
    }


def synthesize_with_fallback(
    text: str,
    language: str,
    low_bandwidth: bool = False,
    fallback_language: str = 'hi-IN'
) -> Tuple[str, str, str]:
    """
    Synthesize speech with automatic fallback to a default language if needed.
    Useful for handling edge cases where the requested language fails.
    
    Args:
        text: Text to convert to speech
        language: Preferred language code
        low_bandwidth: Whether to use low-bandwidth mode
        fallback_language: Language to use if preferred language fails
    
    Returns:
        Tuple of (audio_s3_key, service_used, language_used)
    
    Raises:
        SpeechRoutingError: If synthesis fails even with fallback
    """
    try:
        audio_key, service = synthesize_speech(text, language, low_bandwidth)
        return audio_key, service, language
    except SpeechRoutingError as e:
        # Try fallback language
        if language != fallback_language:
            try:
                audio_key, service = synthesize_speech(text, fallback_language, low_bandwidth)
                return audio_key, service, fallback_language
            except SpeechRoutingError as fallback_error:
                raise SpeechRoutingError(
                    f"Synthesis failed for both {language} and fallback {fallback_language}. "
                    f"Original error: {e}. Fallback error: {fallback_error}"
                )
        else:
            raise



def _mock_tts(text: str, language: str) -> str:
    """
    Generate a mock TTS response for testing without Polly/Bhashini.
    Returns a fake S3 key that represents synthesized audio.
    
    Args:
        text: Text to "synthesize"
        language: Language code
        
    Returns:
        Mock S3 key for audio file
    """
    # Generate a deterministic but unique key based on text hash
    import hashlib
    text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
    mock_key = f"mock-responses/{language}/{text_hash}-{uuid.uuid4()}.mp3"
    return mock_key
