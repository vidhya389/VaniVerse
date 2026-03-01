"""Google Cloud Speech-to-Text integration for speech-to-text conversion"""

import boto3
import base64
import subprocess
import tempfile
import os
from typing import Optional, Tuple
from google.cloud import speech_v1
from google.oauth2 import service_account
from src.config import Config
import logging

logger = logging.getLogger(__name__)


# Supported language codes for Google Speech-to-Text
SUPPORTED_LANGUAGES = {
    'hi-IN': 'Hindi',
    'ta-IN': 'Tamil',
    'te-IN': 'Telugu',
    'kn-IN': 'Kannada',
    'mr-IN': 'Marathi',
    'bn-IN': 'Bengali',
    'gu-IN': 'Gujarati',
    'pa-IN': 'Punjabi',
    'ml-IN': 'Malayalam',
    'or-IN': 'Odia'
}


class GoogleSpeechError(Exception):
    """Exception raised for Google Speech errors"""
    pass


class LowConfidenceError(Exception):
    """Exception raised when transcription confidence is too low"""
    pass


def convert_m4a_to_wav(audio_content: bytes) -> bytes:
    """
    Convert M4A/AAC audio to LINEAR16 WAV format for Google Speech-to-Text.
    
    Args:
        audio_content: Raw M4A audio bytes
    
    Returns:
        WAV audio bytes in LINEAR16 format at 16kHz
    
    Raises:
        GoogleSpeechError: If conversion fails
    """
    input_file = None
    output_file = None
    
    try:
        # Create temporary files for conversion
        with tempfile.NamedTemporaryFile(suffix='.m4a', delete=False) as input_temp:
            input_file = input_temp.name
            input_temp.write(audio_content)
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as output_temp:
            output_file = output_temp.name
        
        # Convert using ffmpeg
        # -i: input file
        # -acodec pcm_s16le: LINEAR16 encoding
        # -ar 16000: 16kHz sample rate
        # -ac 1: mono channel
        # -y: overwrite output
        result = subprocess.run([
            'ffmpeg',
            '-i', input_file,
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            '-y',
            output_file
        ], capture_output=True, text=True, check=True)
        
        # Read converted WAV file
        with open(output_file, 'rb') as f:
            wav_content = f.read()
        
        logger.info(f"Converted M4A ({len(audio_content)} bytes) to WAV ({len(wav_content)} bytes)")
        return wav_content
        
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg conversion failed: {e.stderr}")
        raise GoogleSpeechError(f"Audio conversion failed: {e.stderr}")
    except FileNotFoundError:
        raise GoogleSpeechError("FFmpeg not found. Please install ffmpeg for audio conversion.")
    except Exception as e:
        logger.error(f"Unexpected error during audio conversion: {str(e)}")
        raise GoogleSpeechError(f"Audio conversion error: {str(e)}")
    finally:
        # Clean up temporary files
        if input_file and os.path.exists(input_file):
            try:
                os.remove(input_file)
            except:
                pass
        if output_file and os.path.exists(output_file):
            try:
                os.remove(output_file)
            except:
                pass


def transcribe_audio_google(
    audio_key: str,
    language_hint: Optional[str] = None,
    low_bandwidth: bool = False,
    confidence_threshold: float = 0.7
) -> Tuple[str, str, float]:
    if not audio_key:
        raise GoogleSpeechError("Audio key is required")
    
    language_code = language_hint or 'hi-IN'
    
    if language_code not in SUPPORTED_LANGUAGES:
        raise GoogleSpeechError(f"Language {language_code} not supported.")
    
    try:
        # 1. Download audio from S3
        s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
        audio_obj = s3_client.get_object(Bucket=Config.AUDIO_INPUT_BUCKET, Key=audio_key)
        audio_content = audio_obj['Body'].read()
        
        logger.info(f"Downloaded audio from S3: {audio_key}, size: {len(audio_content)} bytes")
        
        # 2. Convert M4A to WAV if needed
        is_m4a = audio_key.endswith('.m4a') or audio_key.endswith('.mp4') or audio_key.endswith('.aac')
        if is_m4a:
            logger.info("Converting M4A/AAC to WAV format...")
            audio_content = convert_m4a_to_wav(audio_content)
            # Update the file extension for config determination
            audio_key_for_config = audio_key.rsplit('.', 1)[0] + '.wav'
        else:
            audio_key_for_config = audio_key
        
        # 3. Setup Config Parameters
        config_params = {
            'language_code': language_code,
            'enable_automatic_punctuation': True,
            'use_enhanced': not low_bandwidth,
        }

        # Determine audio encoding based on file extension
        if audio_key_for_config.endswith('.wav'):
            config_params['encoding'] = speech_v1.RecognitionConfig.AudioEncoding.LINEAR16
            config_params['sample_rate_hertz'] = 16000
        elif audio_key_for_config.endswith('.flac'):
            config_params['encoding'] = speech_v1.RecognitionConfig.AudioEncoding.FLAC
            config_params['sample_rate_hertz'] = 16000
        else:
            # Fallback - should not reach here after conversion
            config_params['encoding'] = speech_v1.RecognitionConfig.AudioEncoding.LINEAR16
            config_params['sample_rate_hertz'] = 16000

        logger.info(f"Final Request Config: {config_params}")

        # 4. Initialize Google Speech client
        if Config.GOOGLE_APPLICATION_CREDENTIALS:
            credentials = service_account.Credentials.from_service_account_file(Config.GOOGLE_APPLICATION_CREDENTIALS)
            client = speech_v1.SpeechClient(credentials=credentials)
        else:
            client = speech_v1.SpeechClient()
        
        # 5. Configure audio and final config object
        audio = speech_v1.RecognitionAudio(content=audio_content)
        config = speech_v1.RecognitionConfig(**config_params)
        
        # 6. Perform transcription
        logger.info("Calling Google Speech API...")
        response = client.recognize(config=config, audio=audio)
        
        # 7. Extract results
        if not response.results:
            raise GoogleSpeechError(f"No results returned. Size: {len(audio_content)} bytes, Lang: {language_code}")
        
        result = response.results[0]
        if not result.alternatives:
            raise GoogleSpeechError("No transcription alternatives found")
        
        alternative = result.alternatives[0]
        return alternative.transcript, language_code, alternative.confidence
        
    except LowConfidenceError:
        raise
    except Exception as e:
        # This handles the GoogleSpeechError logic you had...
        raise GoogleSpeechError(f"Unexpected error: {str(e)}")


def transcribe_with_google_retry(
    audio_key: str,
    language_hint: Optional[str] = None,
    low_bandwidth: bool = False,
    max_retries: int = 3
) -> Tuple[str, str, float]:
    """
    Transcribe audio with retry logic for handling transient failures.
    
    Args:
        audio_key: S3 key for the audio file
        language_hint: Optional language code hint
        low_bandwidth: Whether to use low-bandwidth mode
        max_retries: Maximum number of retry attempts
    
    Returns:
        Tuple of (transcribed_text, detected_language, confidence_score)
    
    Raises:
        GoogleSpeechError: If all retries fail
        LowConfidenceError: If confidence is too low
    """
    import time
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return transcribe_audio_google(audio_key, language_hint, low_bandwidth)
        except LowConfidenceError:
            # Don't retry on low confidence
            raise
        except GoogleSpeechError as e:
            last_error = e
            
            # Don't retry on authentication or quota errors
            if "authentication" in str(e).lower() or "quota" in str(e).lower():
                raise
            
            if attempt < max_retries - 1:
                # Exponential backoff: 1s, 2s, 4s
                wait_time = 2 ** attempt
                time.sleep(wait_time)
    
    # All retries failed
    raise GoogleSpeechError(
        f"Transcription failed after {max_retries} attempts. Last error: {last_error}"
    )


def is_google_speech_supported(language: str) -> bool:
    """
    Check if a language is supported by Google Speech-to-Text.
    
    Args:
        language: Language code to check
    
    Returns:
        True if supported, False otherwise
    """
    return language in SUPPORTED_LANGUAGES


def get_supported_google_languages() -> list:
    """
    Get list of languages supported by Google Speech-to-Text.
    
    Returns:
        List of language codes
    """
    return list(SUPPORTED_LANGUAGES.keys())
