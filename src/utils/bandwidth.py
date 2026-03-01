"""
Bandwidth detection and low-bandwidth mode utilities.

This module provides functions to detect network bandwidth conditions
and determine whether to activate low-bandwidth mode for audio processing.
It also includes USSD/SMS fallback generation for timeout scenarios.
"""

import boto3
import subprocess
import tempfile
import os
import json
from typing import Dict, Any, Optional, List
from src.config import Config


def detect_bandwidth_mode(
    audio_file_key: str,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Detect network bandwidth and determine operational mode.
    
    This function checks both client-reported bandwidth metadata and audio file size
    to determine if low-bandwidth mode should be activated. Low-bandwidth mode is
    activated when network speed is below 100 kbps, which is typical for 2G networks.
    
    Metadata bandwidth takes precedence over file size when available.
    
    Args:
        audio_file_key: S3 key for the uploaded audio file
        metadata: Optional metadata dictionary that may contain 'bandwidth' field
    
    Returns:
        str: Either 'low' or 'normal' indicating the bandwidth mode
    
    Validates: Requirements 14.1
    """
    # Check metadata for client-reported bandwidth (takes precedence)
    if metadata and 'bandwidth' in metadata:
        try:
            bandwidth_kbps = float(metadata['bandwidth'])
            if bandwidth_kbps < Config.LOW_BANDWIDTH_THRESHOLD_KBPS:
                return 'low'
            else:
                return 'normal'
        except (ValueError, TypeError):
            # If bandwidth value is invalid, fall through to file size check
            pass
    
    # Check audio file size as proxy for bandwidth
    # If farmer uploaded very small file, likely on slow connection
    audio_size = get_s3_object_size(audio_file_key)
    
    # TEMPORARY: Log file size for debugging
    print(f"DEBUG: Audio file size: {audio_size} bytes ({audio_size / 1024:.2f} KB)")
    
    # TEMPORARY: Disable bandwidth detection to test transcription
    # Less than 50KB suggests heavy compression due to poor network
    # if audio_size < 50000:
    #     return 'low'
    
    # ALWAYS return normal for now to test if bandwidth mode is the issue
    print("DEBUG: Forcing normal bandwidth mode for testing")
    return 'normal'


def get_s3_object_size(object_key: str) -> int:
    """
    Get the size of an S3 object in bytes.
    
    Args:
        object_key: S3 key for the object
    
    Returns:
        int: Size of the object in bytes
    
    Raises:
        Exception: If the object cannot be accessed or does not exist
    """
    s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
    
    try:
        response = s3_client.head_object(
            Bucket=Config.AUDIO_INPUT_BUCKET,
            Key=object_key
        )
        return response['ContentLength']
    except Exception as e:
        # If we can't get the file size, assume normal bandwidth
        # This prevents bandwidth detection from blocking the voice loop
        print(f"Warning: Could not get S3 object size for {object_key}: {e}")
        return 100000  # Return a size that indicates normal bandwidth


def compress_audio_to_64kbps(audio_data: bytes) -> bytes:
    """
    Compress audio to 64 kbps for low-bandwidth mode.
    
    This function uses ffmpeg to compress audio files to 64 kbps bitrate
    with a reduced sample rate of 22050 Hz, optimizing for 2G network speeds
    while maintaining acceptable voice quality.
    
    Args:
        audio_data: Raw audio data as bytes
    
    Returns:
        bytes: Compressed audio data
    
    Raises:
        subprocess.CalledProcessError: If ffmpeg compression fails
        FileNotFoundError: If ffmpeg is not installed
    
    Validates: Requirements 14.2
    """
    input_path = None
    output_path = None
    
    try:
        # Write input audio to temp file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as input_file:
            input_file.write(audio_data)
            input_path = input_file.name
        
        # Create output path
        output_path = input_path.replace('.mp3', '_compressed.mp3')
        
        # Compress using ffmpeg
        # -b:a 64k: Set audio bitrate to 64 kbps
        # -ar 22050: Set sample rate to 22050 Hz (half of standard 44100 Hz)
        # -y: Overwrite output file if it exists
        subprocess.run([
            'ffmpeg',
            '-i', input_path,
            '-b:a', '64k',      # 64 kbps bitrate for 2G networks
            '-ar', '22050',     # Lower sample rate for smaller file size
            '-y',               # Overwrite output
            output_path
        ], check=True, capture_output=True, text=True)
        
        # Read compressed audio
        with open(output_path, 'rb') as f:
            compressed_data = f.read()
        
        return compressed_data
        
    finally:
        # Cleanup temp files
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        if output_path and os.path.exists(output_path):
            os.remove(output_path)



def generate_ussd_fallback(advice_text: str) -> Dict[str, Any]:
    """
    Generate USSD/SMS fallback when voice loop times out.
    
    This function creates a text-based fallback for farmers experiencing
    network timeouts. It simplifies the advice and breaks it into SMS-sized
    chunks (160 characters each) for delivery via SMS or USSD menu.
    
    Args:
        advice_text: The full agricultural advice text to simplify
    
    Returns:
        dict: Dictionary containing:
            - type: 'ussd_fallback'
            - chunks: List of SMS-sized text chunks (max 160 chars each)
            - ussd_menu: Dictionary of menu options for USSD interface
    
    Validates: Requirements 14.4, 14.5
    """
    # Simplify advice to text-only format
    simplified_text = simplify_advice_for_text(advice_text)
    
    # Break into SMS-sized chunks (160 characters)
    # Each chunk should be a complete thought when possible
    chunks = _break_into_sms_chunks(simplified_text, max_length=160)
    
    return {
        'type': 'ussd_fallback',
        'chunks': chunks,
        'ussd_menu': {
            '1': 'Get full advice via SMS',
            '2': 'Try voice again',
            '3': 'Talk to human advisor'
        }
    }


def simplify_advice_for_text(advice_text: str) -> str:
    """
    Simplify verbose advice into concise text for SMS/USSD.
    
    This function uses Claude via AWS Bedrock to condense agricultural advice
    into a concise, actionable format suitable for SMS delivery. It removes
    conversational elements and focuses on key action items.
    
    Args:
        advice_text: The full agricultural advice text to simplify
    
    Returns:
        str: Simplified advice text (typically 200-300 characters)
    
    Raises:
        Exception: If Bedrock API call fails
    
    Validates: Requirements 14.4, 14.5
    """
    bedrock_runtime = boto3.client('bedrock-runtime', region_name=Config.AWS_REGION)
    
    request_body = {
        'anthropic_version': 'bedrock-2023-05-31',
        'max_tokens': 300,
        'messages': [
            {
                'role': 'user',
                'content': f"""
Simplify this agricultural advice into a concise SMS format (max 300 characters):

{advice_text}

Requirements:
- Keep key action items only
- Remove conversational elements and greetings
- Use bullet points with dashes (-)
- Be direct and actionable
- Focus on what, when, and how
- Use simple language

Example format:
- Action 1: specific instruction
- Action 2: specific instruction
- Timing: when to do it
"""
            }
        ]
    }
    
    try:
        response = bedrock_runtime.invoke_model(
            modelId=Config.CLAUDE_MODEL_ID,
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        simplified_text = response_body['content'][0]['text']
        
        # Clean up any extra whitespace
        simplified_text = ' '.join(simplified_text.split())
        
        return simplified_text
        
    except Exception as e:
        # If Claude fails, provide a basic fallback
        # Extract first 280 characters and add ellipsis
        fallback = advice_text[:280].strip()
        if len(advice_text) > 280:
            fallback += '...'
        return fallback


def _break_into_sms_chunks(text: str, max_length: int = 160) -> List[str]:
    """
    Break text into SMS-sized chunks while preserving word boundaries.
    
    This helper function splits text into chunks of maximum length,
    ensuring that words are not broken in the middle. It attempts to
    break at sentence or phrase boundaries when possible.
    
    Args:
        text: The text to break into chunks
        max_length: Maximum length of each chunk (default: 160 for SMS)
    
    Returns:
        List[str]: List of text chunks, each <= max_length characters
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    remaining_text = text
    
    while remaining_text:
        # If remaining text fits in one chunk, add it and break
        if len(remaining_text) <= max_length:
            chunks.append(remaining_text)
            break
        
        # Find the best break point within max_length
        chunk = remaining_text[:max_length]
        
        # Try to break at sentence boundary (. ! ?)
        sentence_breaks = [chunk.rfind('. '), chunk.rfind('! '), chunk.rfind('? ')]
        best_sentence_break = max(sentence_breaks)
        
        if best_sentence_break > max_length * 0.5:  # At least halfway through
            break_point = best_sentence_break + 2  # Include the punctuation and space
        else:
            # Try to break at phrase boundary (- : ;)
            phrase_breaks = [chunk.rfind('- '), chunk.rfind(': '), chunk.rfind('; ')]
            best_phrase_break = max(phrase_breaks)
            
            if best_phrase_break > max_length * 0.5:
                break_point = best_phrase_break + 2
            else:
                # Fall back to word boundary
                last_space = chunk.rfind(' ')
                if last_space > 0:
                    break_point = last_space + 1
                else:
                    # No good break point, force break at max_length
                    break_point = max_length
        
        # Add chunk and continue with remaining text
        chunks.append(remaining_text[:break_point].strip())
        remaining_text = remaining_text[break_point:].strip()
    
    return chunks
