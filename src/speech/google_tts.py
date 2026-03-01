"""Google Cloud Text-to-Speech integration for speech synthesis"""

import boto3
import uuid
from typing import Optional
from google.cloud import texttospeech_v1
from google.oauth2 import service_account
from src.config import Config
import logging

logger = logging.getLogger(__name__)


# Supported language codes for Google TTS
GOOGLE_TTS_LANGUAGE_MAP = {
    'hi-IN': {
        'language_code': 'hi-IN',
        'voice_name': 'hi-IN-Wavenet-D',  # Female voice
        'ssml_gender': texttospeech_v1.SsmlVoiceGender.FEMALE
    },
    'ta-IN': {
        'language_code': 'ta-IN',
        'voice_name': 'ta-IN-Wavenet-A',  # Female voice
        'ssml_gender': texttospeech_v1.SsmlVoiceGender.FEMALE
    },
    'te-IN': {
        'language_code': 'te-IN',
        'voice_name': 'te-IN-Standard-A',  # Female voice
        'ssml_gender': texttospeech_v1.SsmlVoiceGender.FEMALE
    },
    'kn-IN': {
        'language_code': 'kn-IN',
        'voice_name': 'kn-IN-Standard-A',  # Female voice
        'ssml_gender': texttospeech_v1.SsmlVoiceGender.FEMALE
    },
    'ml-IN': {
        'language_code': 'ml-IN',
        'voice_name': 'ml-IN-Wavenet-A',  # Female voice
        'ssml_gender': texttospeech_v1.SsmlVoiceGender.FEMALE
    },
    'bn-IN': {
        'language_code': 'bn-IN',
        'voice_name': 'bn-IN-Wavenet-A',  # Female voice
        'ssml_gender': texttospeech_v1.SsmlVoiceGender.FEMALE
    },
    'gu-IN': {
        'language_code': 'gu-IN',
        'voice_name': 'gu-IN-Wavenet-A',  # Female voice
        'ssml_gender': texttospeech_v1.SsmlVoiceGender.FEMALE
    },
    'mr-IN': {
        'language_code': 'mr-IN',
        'voice_name': 'mr-IN-Wavenet-A',  # Female voice
        'ssml_gender': texttospeech_v1.SsmlVoiceGender.FEMALE
    },
    'pa-IN': {
        'language_code': 'pa-IN',
        'voice_name': 'pa-IN-Wavenet-A',  # Female voice
        'ssml_gender': texttospeech_v1.SsmlVoiceGender.FEMALE
    }
}


class GoogleTTSError(Exception):
    """Exception raised for Google TTS errors"""
    pass


def synthesize_with_google_tts(
    text: str,
    language: str,
    low_bandwidth: bool = False,
    request_id: Optional[str] = None
) -> str:
    """
    Synthesize speech using Google Cloud Text-to-Speech API.
    
    Args:
        text: Text to convert to speech
        language: Language code (e.g., 'ta-IN')
        low_bandwidth: Whether to use low-bandwidth optimized settings
        request_id: Optional request ID for organizing output files
    
    Returns:
        S3 key for the synthesized audio file
    
    Raises:
        GoogleTTSError: If synthesis fails
    """
    if not text or not text.strip():
        raise GoogleTTSError("Cannot synthesize empty text")
    
    # Check if language is supported
    if language not in GOOGLE_TTS_LANGUAGE_MAP:
        raise GoogleTTSError(
            f"Language {language} not supported by Google TTS. "
            f"Supported languages: {', '.join(GOOGLE_TTS_LANGUAGE_MAP.keys())}"
        )
    
    try:
        # Initialize Google TTS client
        if Config.GOOGLE_APPLICATION_CREDENTIALS:
            logger.info(f"Using Google credentials from: {Config.GOOGLE_APPLICATION_CREDENTIALS}")
            credentials = service_account.Credentials.from_service_account_file(
                Config.GOOGLE_APPLICATION_CREDENTIALS
            )
            client = texttospeech_v1.TextToSpeechClient(credentials=credentials)
        else:
            logger.info("Using default Google credentials from environment")
            client = texttospeech_v1.TextToSpeechClient()
        
        # Get voice configuration
        voice_config = GOOGLE_TTS_LANGUAGE_MAP[language]
        
        # Set the text input to be synthesized
        synthesis_input = texttospeech_v1.SynthesisInput(text=text)
        
        # Build the voice request
        voice = texttospeech_v1.VoiceSelectionParams(
            language_code=voice_config['language_code'],
            name=voice_config['voice_name'],
            ssml_gender=voice_config['ssml_gender']
        )
        
        # Select the audio format
        # Use LINEAR16 for low bandwidth (WAV), MP3 for normal
        if low_bandwidth:
            audio_config = texttospeech_v1.AudioConfig(
                audio_encoding=texttospeech_v1.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000
            )
            file_extension = 'wav'
            content_type = 'audio/wav'
        else:
            audio_config = texttospeech_v1.AudioConfig(
                audio_encoding=texttospeech_v1.AudioEncoding.MP3,
                sample_rate_hertz=24000
            )
            file_extension = 'mp3'
            content_type = 'audio/mpeg'
        
        logger.info(f"Google TTS synthesis: language={language}, voice={voice_config['voice_name']}, "
                   f"text_length={len(text)}")
        logger.info(f"First 200 chars of text: {text[:200]}")
        
        # Perform the text-to-speech request
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        # Get audio content
        audio_data = response.audio_content
        audio_size = len(audio_data)
        
        logger.info(f"Google TTS generated audio: {audio_size} bytes")
        
        if audio_size < 5000:
            logger.warning(f"Audio size is very small ({audio_size} bytes) for {len(text)} characters of text.")
        
        # Upload to S3
        s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
        
        # Generate S3 key
        if request_id:
            audio_key = f"{request_id}/response.{file_extension}"
        else:
            audio_key = f"responses/{uuid.uuid4()}.{file_extension}"
        
        s3_client.put_object(
            Bucket=Config.AUDIO_OUTPUT_BUCKET,
            Key=audio_key,
            Body=audio_data,
            ContentType=content_type,
            Metadata={
                'language': language,
                'voice_name': voice_config['voice_name'],
                'service': 'google_tts',
                'low_bandwidth': str(low_bandwidth),
                'text_length': str(len(text)),
                'audio_size': str(audio_size)
            }
        )
        
        logger.info(f"Uploaded audio to S3: {audio_key}")
        return audio_key
        
    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower():
            raise GoogleTTSError("Google TTS API quota exceeded")
        elif "authentication" in error_msg.lower() or "credentials" in error_msg.lower():
            raise GoogleTTSError("Google TTS API authentication failed. Check credentials.")
        elif "invalid" in error_msg.lower():
            raise GoogleTTSError(f"Invalid request: {error_msg}")
        else:
            raise GoogleTTSError(f"Unexpected error during Google TTS synthesis: {error_msg}")


def synthesize_with_google_tts_retry(
    text: str,
    language: str,
    low_bandwidth: bool = False,
    request_id: Optional[str] = None,
    max_retries: int = 3
) -> str:
    """
    Synthesize speech with retry logic for handling transient failures.
    
    Args:
        text: Text to convert to speech
        language: Language code
        low_bandwidth: Whether to use low-bandwidth mode
        request_id: Optional request ID for organizing output files
        max_retries: Maximum number of retry attempts
    
    Returns:
        S3 key for the synthesized audio file
    
    Raises:
        GoogleTTSError: If all retries fail
    """
    import time
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return synthesize_with_google_tts(text, language, low_bandwidth, request_id)
        except GoogleTTSError as e:
            last_error = e
            
            # Don't retry on validation errors
            if "not supported" in str(e).lower() or "authentication" in str(e).lower():
                raise
            
            if attempt < max_retries - 1:
                # Exponential backoff: 1s, 2s, 4s
                wait_time = 2 ** attempt
                time.sleep(wait_time)
    
    raise GoogleTTSError(
        f"Google TTS synthesis failed after {max_retries} attempts. Last error: {last_error}"
    )


def is_google_tts_supported(language: str) -> bool:
    """
    Check if a language is supported by Google TTS.
    
    Args:
        language: Language code to check
    
    Returns:
        True if supported, False otherwise
    """
    return language in GOOGLE_TTS_LANGUAGE_MAP


def get_supported_google_tts_languages() -> list:
    """
    Get list of languages supported by Google TTS.
    
    Returns:
        List of language codes
    """
    return list(GOOGLE_TTS_LANGUAGE_MAP.keys())
