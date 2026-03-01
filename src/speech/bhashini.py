"""Bhashini API integration for text-to-speech conversion"""

import boto3
import uuid
import requests
from typing import Optional
from src.config import Config


# Bhashini language code mapping
BHASHINI_LANGUAGE_MAP = {
    'mr-IN': 'mr',  # Marathi
    'bn-IN': 'bn',  # Bengali
    'gu-IN': 'gu',  # Gujarati
    'pa-IN': 'pa',  # Punjabi
    'hi-IN': 'hi',  # Hindi (fallback)
    'ta-IN': 'ta',  # Tamil (fallback)
    'te-IN': 'te',  # Telugu (fallback)
    'kn-IN': 'kn',  # Kannada (fallback)
}


class BhashiniSynthesisError(Exception):
    """Exception raised for Bhashini synthesis errors"""
    pass


class BhashiniAuthenticationError(Exception):
    """Exception raised for Bhashini authentication errors"""
    pass


def synthesize_with_bhashini(
    text: str,
    language: str,
    low_bandwidth: bool = False
) -> str:
    """
    Synthesize speech using Bhashini API.
    
    Args:
        text: Text to convert to speech
        language: Language code (e.g., 'mr-IN')
        low_bandwidth: Whether to use low-bandwidth optimized settings
    
    Returns:
        S3 key for the synthesized audio file
    
    Raises:
        BhashiniSynthesisError: If synthesis fails
        BhashiniAuthenticationError: If authentication fails
    """
    if not text or not text.strip():
        raise BhashiniSynthesisError("Cannot synthesize empty text")
    
    # Check if API key is configured
    if not Config.BHASHINI_API_KEY:
        raise BhashiniAuthenticationError(
            "BHASHINI_API_KEY not configured. Please set it in environment variables."
        )
    
    # Map language code to Bhashini format
    bhashini_lang = BHASHINI_LANGUAGE_MAP.get(language)
    if not bhashini_lang:
        raise BhashiniSynthesisError(
            f"Language {language} not supported by Bhashini. "
            f"Supported languages: {', '.join(BHASHINI_LANGUAGE_MAP.keys())}"
        )
    
    try:
        # Prepare request payload
        payload = {
            'text': text,
            'language': bhashini_lang,
            'gender': 'female',  # Default to female voice
            'speed': 1.0
        }
        
        # Adjust for low-bandwidth mode
        if low_bandwidth:
            payload['quality'] = 'low'
            payload['sample_rate'] = 16000  # Lower sample rate
        else:
            payload['quality'] = 'high'
            payload['sample_rate'] = 22050
        
        # Make API request
        headers = {
            'Authorization': f'Bearer {Config.BHASHINI_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(
            Config.BHASHINI_TTS_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        # Handle authentication errors
        if response.status_code == 401:
            raise BhashiniAuthenticationError("Invalid Bhashini API key")
        elif response.status_code == 403:
            raise BhashiniAuthenticationError("Bhashini API access forbidden")
        
        # Handle other errors
        if response.status_code != 200:
            error_msg = response.json().get('error', 'Unknown error') if response.text else 'Unknown error'
            raise BhashiniSynthesisError(
                f"Bhashini API returned status {response.status_code}: {error_msg}"
            )
        
        # Get audio data
        audio_data = response.content
        
        if not audio_data:
            raise BhashiniSynthesisError("Empty audio data received from Bhashini")
        
        # Upload to S3
        s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
        audio_key = f"responses/{uuid.uuid4()}.mp3"
        
        s3_client.put_object(
            Bucket=Config.AUDIO_OUTPUT_BUCKET,
            Key=audio_key,
            Body=audio_data,
            ContentType='audio/mpeg',
            Metadata={
                'language': language,
                'bhashini_lang': bhashini_lang,
                'service': 'bhashini',
                'low_bandwidth': str(low_bandwidth)
            }
        )
        
        return audio_key
    
    except (BhashiniSynthesisError, BhashiniAuthenticationError):
        raise
    except requests.exceptions.Timeout:
        raise BhashiniSynthesisError("Bhashini API request timed out")
    except requests.exceptions.ConnectionError:
        raise BhashiniSynthesisError("Failed to connect to Bhashini API")
    except requests.exceptions.RequestException as e:
        raise BhashiniSynthesisError(f"Bhashini API request failed: {str(e)}")
    except Exception as e:
        raise BhashiniSynthesisError(f"Unexpected error during Bhashini synthesis: {str(e)}")


def get_supported_bhashini_languages() -> list:
    """
    Get list of languages supported by Bhashini integration.
    
    Returns:
        List of language codes
    """
    return list(BHASHINI_LANGUAGE_MAP.keys())


def is_bhashini_supported(language: str) -> bool:
    """
    Check if a language is supported by Bhashini.
    
    Args:
        language: Language code to check
    
    Returns:
        True if supported, False otherwise
    """
    return language in BHASHINI_LANGUAGE_MAP


def synthesize_with_bhashini_retry(
    text: str,
    language: str,
    low_bandwidth: bool = False,
    max_retries: int = 3
) -> str:
    """
    Synthesize speech with retry logic for handling transient failures.
    
    Args:
        text: Text to convert to speech
        language: Language code
        low_bandwidth: Whether to use low-bandwidth mode
        max_retries: Maximum number of retry attempts
    
    Returns:
        S3 key for the synthesized audio file
    
    Raises:
        BhashiniSynthesisError: If all retries fail
        BhashiniAuthenticationError: If authentication fails
    """
    import time
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return synthesize_with_bhashini(text, language, low_bandwidth)
        except BhashiniAuthenticationError:
            # Don't retry authentication errors
            raise
        except BhashiniSynthesisError as e:
            last_error = e
            
            # Don't retry on validation errors
            if "not supported" in str(e).lower() or "empty" in str(e).lower():
                raise
            
            if attempt < max_retries - 1:
                # Exponential backoff: 1s, 2s, 4s
                wait_time = 2 ** attempt
                time.sleep(wait_time)
            continue
    
    raise BhashiniSynthesisError(
        f"Bhashini synthesis failed after {max_retries} attempts. Last error: {last_error}"
    )


def transcribe_with_bhashini(
    audio_key: str,
    language: str
) -> str:
    """
    Transcribe audio using Bhashini ASR (Automatic Speech Recognition).
    This can be used as a fallback for languages not well-supported by AWS Transcribe.
    
    Args:
        audio_key: S3 key for the audio file
        language: Language code (e.g., 'mr-IN')
    
    Returns:
        Transcribed text
    
    Raises:
        BhashiniSynthesisError: If transcription fails
        BhashiniAuthenticationError: If authentication fails
    """
    if not Config.BHASHINI_API_KEY:
        raise BhashiniAuthenticationError(
            "BHASHINI_API_KEY not configured. Please set it in environment variables."
        )
    
    # Map language code to Bhashini format
    bhashini_lang = BHASHINI_LANGUAGE_MAP.get(language)
    if not bhashini_lang:
        raise BhashiniSynthesisError(
            f"Language {language} not supported by Bhashini ASR"
        )
    
    try:
        # Download audio from S3
        s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
        audio_obj = s3_client.get_object(
            Bucket=Config.AUDIO_INPUT_BUCKET,
            Key=audio_key
        )
        audio_data = audio_obj['Body'].read()
        
        # Prepare request
        headers = {
            'Authorization': f'Bearer {Config.BHASHINI_API_KEY}'
        }
        
        files = {
            'audio': ('audio.wav', audio_data, 'audio/wav')
        }
        
        data = {
            'language': bhashini_lang
        }
        
        # Make API request
        response = requests.post(
            Config.BHASHINI_ASR_ENDPOINT,
            headers=headers,
            files=files,
            data=data,
            timeout=60
        )
        
        # Handle authentication errors
        if response.status_code == 401:
            raise BhashiniAuthenticationError("Invalid Bhashini API key")
        elif response.status_code == 403:
            raise BhashiniAuthenticationError("Bhashini API access forbidden")
        
        # Handle other errors
        if response.status_code != 200:
            error_msg = response.json().get('error', 'Unknown error') if response.text else 'Unknown error'
            raise BhashiniSynthesisError(
                f"Bhashini ASR API returned status {response.status_code}: {error_msg}"
            )
        
        # Extract transcription
        result = response.json()
        transcript = result.get('transcript', '').strip()
        
        if not transcript:
            raise BhashiniSynthesisError("Empty transcript received from Bhashini ASR")
        
        return transcript
    
    except (BhashiniSynthesisError, BhashiniAuthenticationError):
        raise
    except requests.exceptions.Timeout:
        raise BhashiniSynthesisError("Bhashini ASR request timed out")
    except requests.exceptions.ConnectionError:
        raise BhashiniSynthesisError("Failed to connect to Bhashini ASR API")
    except Exception as e:
        raise BhashiniSynthesisError(f"Unexpected error during Bhashini ASR: {str(e)}")
