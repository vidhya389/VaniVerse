"""Speech processing module for VaniVerse"""

from src.speech.transcribe import (
    transcribe_audio,
    transcribe_with_retry,
    detect_language,
    TranscriptionError,
    LowConfidenceError,
    SUPPORTED_LANGUAGES as TRANSCRIBE_SUPPORTED_LANGUAGES
)

from src.speech.polly import (
    synthesize_with_polly,
    synthesize_with_polly_retry,
    is_polly_supported,
    get_supported_polly_languages,
    PollySynthesisError
)

from src.speech.bhashini import (
    synthesize_with_bhashini,
    synthesize_with_bhashini_retry,
    transcribe_with_bhashini,
    is_bhashini_supported,
    get_supported_bhashini_languages,
    BhashiniSynthesisError,
    BhashiniAuthenticationError
)

from src.speech.router import (
    synthesize_speech,
    get_all_supported_languages,
    get_preferred_service,
    is_language_supported,
    get_service_info,
    synthesize_with_fallback,
    SpeechRoutingError
)

__all__ = [
    # Transcription
    'transcribe_audio',
    'transcribe_with_retry',
    'detect_language',
    'TranscriptionError',
    'LowConfidenceError',
    'TRANSCRIBE_SUPPORTED_LANGUAGES',
    
    # Polly
    'synthesize_with_polly',
    'synthesize_with_polly_retry',
    'is_polly_supported',
    'get_supported_polly_languages',
    'PollySynthesisError',
    
    # Bhashini
    'synthesize_with_bhashini',
    'synthesize_with_bhashini_retry',
    'transcribe_with_bhashini',
    'is_bhashini_supported',
    'get_supported_bhashini_languages',
    'BhashiniSynthesisError',
    'BhashiniAuthenticationError',
    
    # Router
    'synthesize_speech',
    'get_all_supported_languages',
    'get_preferred_service',
    'is_language_supported',
    'get_service_info',
    'synthesize_with_fallback',
    'SpeechRoutingError',
]
