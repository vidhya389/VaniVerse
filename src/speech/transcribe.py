"""Speech-to-text transcription with AWS Transcribe and Google Speech-to-Text"""

import boto3
import uuid
import time
import requests
import logging
from typing import Dict, Optional, Tuple
from src.config import Config

logger = logging.getLogger(__name__)

# Import Google Speech if available
try:
    from src.speech.google_speech import (
        transcribe_with_google_retry,
        is_google_speech_supported,
        GoogleSpeechError
    )
    GOOGLE_SPEECH_AVAILABLE = True
    logger.info("Google Speech-to-Text library loaded successfully")
except ImportError as e:
    GOOGLE_SPEECH_AVAILABLE = False
    logger.warning(f"Google Speech-to-Text library not available: {e}")


# Supported language codes for AWS Transcribe
SUPPORTED_LANGUAGES = {
    'hi-IN': 'Hindi',
    'ta-IN': 'Tamil',
    'te-IN': 'Telugu',
    'kn-IN': 'Kannada',
    'mr-IN': 'Marathi',
    'bn-IN': 'Bengali',
    'gu-IN': 'Gujarati',
    'pa-IN': 'Punjabi'
}


class TranscriptionError(Exception):
    """Exception raised for transcription errors"""
    pass


class LowConfidenceError(Exception):
    """Exception raised when transcription confidence is too low"""
    pass


def transcribe_audio(
    audio_key: str,
    language_hint: Optional[str] = None,
    low_bandwidth: bool = False,
    confidence_threshold: float = 0.7
) -> Tuple[str, str, float]:
    """
    Transcribe audio using AWS Transcribe with language detection.
    
    Args:
        audio_key: S3 key for the audio file
        language_hint: Optional language code hint (e.g., 'hi-IN')
        low_bandwidth: Whether to use low-bandwidth optimized settings
        confidence_threshold: Minimum confidence score to accept (0.0-1.0)
    
    Returns:
        Tuple of (transcribed_text, detected_language, confidence_score)
    
    Raises:
        TranscriptionError: If transcription fails
        LowConfidenceError: If confidence is below threshold
    """
    transcribe_client = boto3.client('transcribe', region_name=Config.AWS_REGION)
    
    # Generate unique job name
    job_name = f"transcribe-{uuid.uuid4()}"
    audio_uri = f"s3://{Config.AUDIO_INPUT_BUCKET}/{audio_key}"
    
    # Determine language code
    language_code = language_hint or 'hi-IN'  # Default to Hindi
    
    # Validate language support
    if language_code not in SUPPORTED_LANGUAGES:
        raise TranscriptionError(
            f"Unsupported language: {language_code}. "
            f"Supported languages: {', '.join(SUPPORTED_LANGUAGES.keys())}"
        )
    
    try:
        # Configure transcription settings
        settings = {}
        
        # Add low-bandwidth optimizations
        if low_bandwidth:
            settings['ChannelIdentification'] = False
        
        # Start transcription job
        transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': audio_uri},
            MediaFormat='wav',  # Assuming WAV format, can be extended
            LanguageCode=language_code,
            Settings=settings
        )
        
        # Wait for completion with timeout
        max_attempts = 60  # 5 minutes max (5 second intervals)
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            time.sleep(5)
            
            status_response = transcribe_client.get_transcription_job(
                TranscriptionJobName=job_name
            )
            
            status = status_response['TranscriptionJob']['TranscriptionJobStatus']
            
            if status == 'COMPLETED':
                break
            elif status == 'FAILED':
                failure_reason = status_response['TranscriptionJob'].get(
                    'FailureReason', 'Unknown error'
                )
                raise TranscriptionError(f"Transcription failed: {failure_reason}")
        
        if attempt >= max_attempts:
            raise TranscriptionError("Transcription timed out after 5 minutes")
        
        # Get transcription results
        result = transcribe_client.get_transcription_job(
            TranscriptionJobName=job_name
        )
        
        transcript_uri = result['TranscriptionJob']['Transcript']['TranscriptFileUri']
        
        # Download and parse transcript
        transcript_response = requests.get(transcript_uri, timeout=30)
        transcript_response.raise_for_status()
        transcript_data = transcript_response.json()
        
        # Extract transcript text
        transcripts = transcript_data.get('results', {}).get('transcripts', [])
        if not transcripts:
            raise TranscriptionError("No transcript found in results")
        
        transcript_text = transcripts[0].get('transcript', '').strip()
        
        if not transcript_text:
            raise TranscriptionError("Empty transcript returned")
        
        # Calculate average confidence score
        items = transcript_data.get('results', {}).get('items', [])
        confidence_scores = [
            float(item.get('alternatives', [{}])[0].get('confidence', 0))
            for item in items
            if 'alternatives' in item and item['alternatives']
        ]
        
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        # Check confidence threshold
        if avg_confidence < confidence_threshold:
            raise LowConfidenceError(
                f"Transcription confidence ({avg_confidence:.2f}) below threshold ({confidence_threshold})"
            )
        
        # Clean up transcription job (optional, for cost management)
        try:
            transcribe_client.delete_transcription_job(TranscriptionJobName=job_name)
        except Exception:
            pass  # Ignore cleanup errors
        
        return transcript_text, language_code, avg_confidence
    
    except (TranscriptionError, LowConfidenceError):
        raise
    except Exception as e:
        raise TranscriptionError(f"Unexpected error during transcription: {str(e)}")


def detect_language(audio_key: str) -> str:
    """
    Detect the language of an audio file using AWS Transcribe.
    
    Args:
        audio_key: S3 key for the audio file
    
    Returns:
        Detected language code (e.g., 'hi-IN')
    
    Raises:
        TranscriptionError: If language detection fails
    """
    transcribe_client = boto3.client('transcribe', region_name=Config.AWS_REGION)
    
    job_name = f"detect-lang-{uuid.uuid4()}"
    audio_uri = f"s3://{Config.AUDIO_INPUT_BUCKET}/{audio_key}"
    
    try:
        # Start language identification job
        transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': audio_uri},
            MediaFormat='wav',
            IdentifyLanguage=True,
            LanguageOptions=list(SUPPORTED_LANGUAGES.keys())
        )
        
        # Wait for completion
        max_attempts = 60
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            time.sleep(5)
            
            status_response = transcribe_client.get_transcription_job(
                TranscriptionJobName=job_name
            )
            
            status = status_response['TranscriptionJob']['TranscriptionJobStatus']
            
            if status == 'COMPLETED':
                break
            elif status == 'FAILED':
                raise TranscriptionError("Language detection failed")
        
        if attempt >= max_attempts:
            raise TranscriptionError("Language detection timed out")
        
        # Get detected language
        result = transcribe_client.get_transcription_job(
            TranscriptionJobName=job_name
        )
        
        detected_language = result['TranscriptionJob'].get('LanguageCode')
        
        if not detected_language:
            raise TranscriptionError("No language detected")
        
        # Clean up
        try:
            transcribe_client.delete_transcription_job(TranscriptionJobName=job_name)
        except Exception:
            pass
        
        return detected_language
    
    except TranscriptionError:
        raise
    except Exception as e:
        raise TranscriptionError(f"Unexpected error during language detection: {str(e)}")


def transcribe_with_retry(
    audio_key: str,
    language_hint: Optional[str] = None,
    low_bandwidth: bool = False,
    max_retries: int = 3
) -> Tuple[str, str, float]:
    """
    Transcribe audio with retry logic for handling transient failures.
    Routes to Google Speech-to-Text or AWS Transcribe based on configuration.
    
    Args:
        audio_key: S3 key for the audio file
        language_hint: Optional language code hint
        low_bandwidth: Whether to use low-bandwidth mode
        max_retries: Maximum number of retry attempts
    
    Returns:
        Tuple of (transcribed_text, detected_language, confidence_score)
    
    Raises:
        TranscriptionError: If all retries fail
        LowConfidenceError: If confidence is consistently too low
    """
    # Use mock transcription if configured (for testing)
    if Config.USE_MOCK_TRANSCRIBE:
        logger.info("Using mock transcription (USE_MOCK_TRANSCRIBE=true)")
        return _mock_transcribe(audio_key, language_hint)
    
    # Use Google Speech-to-Text if configured
    if Config.USE_GOOGLE_SPEECH:
        if not GOOGLE_SPEECH_AVAILABLE:
            raise TranscriptionError(
                "Google Speech-to-Text is enabled (USE_GOOGLE_SPEECH=true) but the library is not available. "
                "Ensure google-cloud-speech is installed in the Lambda package."
            )
        
        logger.info("Using Google Speech-to-Text (USE_GOOGLE_SPEECH=true)")
        try:
            return transcribe_with_google_retry(audio_key, language_hint, low_bandwidth, max_retries)
        except Exception as e:
            # Do NOT fall back to AWS Transcribe if Google Speech is explicitly enabled
            raise TranscriptionError(f"Google Speech-to-Text failed: {str(e)}")
    
    # Use AWS Transcribe (default)
    logger.info("Using AWS Transcribe (default)")
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return transcribe_audio(audio_key, language_hint, low_bandwidth)
        except LowConfidenceError:
            # Don't retry on low confidence - this is a data quality issue
            raise
        except TranscriptionError as e:
            last_error = e
            if attempt < max_retries - 1:
                # Exponential backoff: 1s, 2s, 4s
                wait_time = 2 ** attempt
                time.sleep(wait_time)
            continue
    
    raise TranscriptionError(
        f"Transcription failed after {max_retries} attempts. Last error: {last_error}"
    )


def _mock_transcribe(audio_key: str, language_hint: Optional[str] = None) -> Tuple[str, str, float]:
    """
    Mock transcription for testing without AWS Transcribe subscription.
    
    Args:
        audio_key: S3 key for the audio file
        language_hint: Optional language code hint
    
    Returns:
        Tuple of (mock_text, language, confidence)
    """
    language = language_hint or 'hi-IN'
    
    # Return a mock transcription based on language
    mock_texts = {
        'hi-IN': 'मेरी फसल के लिए मौसम की जानकारी चाहिए',  # "I need weather information for my crop"
        'ta-IN': 'எனது பயிருக்கு வானிலை தகவல் வேண்டும்',
        'te-IN': 'నా పంటకు వాతావరణ సమాచారం కావాలి',
        'kn-IN': 'ನನ್ನ ಬೆಳೆಗೆ ಹವಾಮಾನ ಮಾಹಿತಿ ಬೇಕು',
        'mr-IN': 'माझ्या पिकासाठी हवामान माहिती हवी',
        'bn-IN': 'আমার ফসলের জন্য আবহাওয়ার তথ্য দরকার',
        'gu-IN': 'મારા પાક માટે હવામાન માહિતી જોઈએ છે',
        'pa-IN': 'ਮੇਰੀ ਫਸਲ ਲਈ ਮੌਸਮ ਦੀ ਜਾਣਕਾਰੀ ਚਾਹੀਦੀ ਹੈ'
    }
    
    mock_text = mock_texts.get(language, mock_texts['hi-IN'])
    
    return mock_text, language, 0.95
