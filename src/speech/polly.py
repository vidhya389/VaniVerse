"""Amazon Polly integration for text-to-speech conversion"""

import boto3
import uuid
from typing import Optional
from src.config import Config


# Language to Polly voice mapping
POLLY_VOICE_MAP = {
    'hi-IN': {
        'voice_id': 'Aditi',
        'engine': 'standard',  # Aditi only supports standard engine
        'language_code': 'hi-IN'
    },
    'ta-IN': {
        'voice_id': 'Kajal',  # Using Kajal for Tamil (bilingual voice)
        'engine': 'neural',  # Kajal requires neural engine
        'language_code': 'ta-IN'
    },
    'te-IN': {
        'voice_id': 'Kajal',  # Fallback to Kajal
        'engine': 'neural',  # Kajal requires neural engine
        'language_code': 'te-IN'
    },
    'kn-IN': {
        'voice_id': 'Kajal',  # Fallback to Kajal
        'engine': 'neural',  # Kajal requires neural engine
        'language_code': 'kn-IN'
    },
    'ml-IN': {
        'voice_id': 'Kajal',  # Malayalam support
        'engine': 'neural',  # Kajal requires neural engine
        'language_code': 'ml-IN'
    }
}


class PollySynthesisError(Exception):
    """Exception raised for Polly synthesis errors"""
    pass


def synthesize_with_polly(
    text: str,
    language: str,
    low_bandwidth: bool = False,
    request_id: Optional[str] = None
) -> str:
    """
    Synthesize speech using Amazon Polly.
    
    Args:
        text: Text to convert to speech
        language: Language code (e.g., 'hi-IN')
        low_bandwidth: Whether to use low-bandwidth optimized settings
        request_id: Optional request ID for organizing output files
    
    Returns:
        S3 key for the synthesized audio file
    
    Raises:
        PollySynthesisError: If synthesis fails
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not text or not text.strip():
        raise PollySynthesisError("Cannot synthesize empty text")
    
    # Check if language is supported by Polly
    if language not in POLLY_VOICE_MAP:
        raise PollySynthesisError(
            f"Language {language} not supported by Polly. "
            f"Supported languages: {', '.join(POLLY_VOICE_MAP.keys())}"
        )
    
    polly_client = boto3.client('polly', region_name=Config.AWS_REGION)
    s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
    
    # Get voice configuration
    voice_config = POLLY_VOICE_MAP[language]
    voice_id = voice_config['voice_id']
    engine = voice_config['engine']
    language_code = voice_config['language_code']
    
    # Log the text being synthesized for debugging
    logger.info(f"Polly synthesis: language={language}, voice={voice_id}, engine={engine}, text_length={len(text)}")
    logger.info(f"First 200 chars of text: {text[:200]}")
    
    # Use standard engine for low-bandwidth mode (faster, smaller files)
    if low_bandwidth:
        engine = 'standard'
        logger.info(f"Low bandwidth mode: switching to standard engine")
    
    try:
        # Synthesize speech
        response = polly_client.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId=voice_id,
            Engine=engine,
            LanguageCode=language_code,
            TextType='text'
        )
        
        # Check if audio stream is present
        if 'AudioStream' not in response:
            raise PollySynthesisError("No audio stream in Polly response")
        
        # Read audio stream to check size
        audio_data = response['AudioStream'].read()
        audio_size = len(audio_data)
        logger.info(f"Polly generated audio: {audio_size} bytes")
        
        if audio_size < 5000:  # Less than 5KB is suspiciously small
            logger.warning(f"Audio size is very small ({audio_size} bytes) for {len(text)} characters of text. "
                          f"This may indicate the text is not in the expected language or Polly failed to synthesize properly.")
        
        # Generate S3 key - use request_id if provided, otherwise use UUID
        if request_id:
            audio_key = f"{request_id}/response.mp3"
        else:
            audio_key = f"responses/{uuid.uuid4()}.mp3"
        
        # Upload to S3
        from io import BytesIO
        s3_client.upload_fileobj(
            BytesIO(audio_data),
            Config.AUDIO_OUTPUT_BUCKET,
            audio_key,
            ExtraArgs={
                'ContentType': 'audio/mpeg',
                'Metadata': {
                    'language': language,
                    'voice_id': voice_id,
                    'engine': engine,
                    'low_bandwidth': str(low_bandwidth),
                    'text_length': str(len(text)),
                    'audio_size': str(audio_size)
                }
            }
        )
        
        logger.info(f"Uploaded audio to S3: {audio_key}")
        return audio_key
    
    except Exception as e:
        # Check for specific Polly errors in the exception message
        error_msg = str(e)
        if "TextLengthExceeded" in error_msg or "text is too long" in error_msg.lower():
            raise PollySynthesisError("Text is too long for Polly synthesis (max 3000 characters)")
        elif "InvalidSsml" in error_msg:
            raise PollySynthesisError("Invalid SSML in text")
        elif "LanguageNotSupported" in error_msg:
            raise PollySynthesisError(f"Language {language} not supported by Polly")
        else:
            raise PollySynthesisError(f"Unexpected error during Polly synthesis: {str(e)}")


def get_supported_polly_languages() -> list:
    """
    Get list of languages supported by Polly integration.
    
    Returns:
        List of language codes
    """
    return list(POLLY_VOICE_MAP.keys())


def is_polly_supported(language: str) -> bool:
    """
    Check if a language is supported by Polly.
    
    Args:
        language: Language code to check
    
    Returns:
        True if supported, False otherwise
    """
    return language in POLLY_VOICE_MAP


def synthesize_with_polly_retry(
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
        PollySynthesisError: If all retries fail
    """
    import time
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return synthesize_with_polly(text, language, low_bandwidth, request_id)
        except PollySynthesisError as e:
            last_error = e
            
            # Don't retry on validation errors
            if "not supported" in str(e).lower() or "too long" in str(e).lower():
                raise
            
            if attempt < max_retries - 1:
                # Exponential backoff: 1s, 2s, 4s
                wait_time = 2 ** attempt
                time.sleep(wait_time)
            continue
    
    raise PollySynthesisError(
        f"Polly synthesis failed after {max_retries} attempts. Last error: {last_error}"
    )


def split_long_text(text: str, max_length: int = 2900) -> list:
    """
    Split long text into chunks suitable for Polly synthesis.
    Polly has a 3000 character limit, so we split at sentence boundaries.
    
    Args:
        text: Text to split
        max_length: Maximum length per chunk
    
    Returns:
        List of text chunks
    """
    if len(text) <= max_length:
        return [text]
    
    # Split by sentences
    import re
    sentences = re.split(r'([.!?।]\s+)', text)
    
    chunks = []
    current_chunk = ""
    
    for i in range(0, len(sentences), 2):
        sentence = sentences[i]
        delimiter = sentences[i + 1] if i + 1 < len(sentences) else ""
        
        if len(current_chunk) + len(sentence) + len(delimiter) <= max_length:
            current_chunk += sentence + delimiter
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + delimiter
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks


def synthesize_long_text(
    text: str,
    language: str,
    low_bandwidth: bool = False
) -> list:
    """
    Synthesize long text by splitting into chunks and synthesizing each.
    
    Args:
        text: Text to convert to speech (can be >3000 characters)
        language: Language code
        low_bandwidth: Whether to use low-bandwidth mode
    
    Returns:
        List of S3 keys for synthesized audio files
    
    Raises:
        PollySynthesisError: If synthesis fails
    """
    chunks = split_long_text(text)
    audio_keys = []
    
    for chunk in chunks:
        audio_key = synthesize_with_polly_retry(chunk, language, low_bandwidth)
        audio_keys.append(audio_key)
    
    return audio_keys
