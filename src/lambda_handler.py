"""
Main Lambda handler for VaniVerse orchestrator

This is the entry point for the Lambda function that orchestrates
the complete Guru Cycle from audio input to voice response.

Implements Requirements 11.1, 11.2, 11.4, 11.5, 11.6, 11.7
"""

import json
import logging
import time
import os
import boto3
import re
from typing import Dict, Any, Optional

from src.utils.bandwidth import (
    detect_bandwidth_mode,
    generate_ussd_fallback
)
from src.speech.transcribe import transcribe_with_retry, LowConfidenceError
from src.context.retrieval import fetch_context_parallel
from src.agents.orchestrator import invoke_agents_parallel
from src.prompting.builder import build_memory_first_prompt, invoke_bedrock
from src.safety.validator import validate_safety
from src.speech.router import synthesize_speech
from src.context.memory import store_interaction
from src.config import Config

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _store_interaction_async(
    farmer_id: str,
    question: str,
    advice: str,
    context: Any
) -> None:
    """
    Store interaction in AgentCore Memory asynchronously using Lambda invoke.
    
    This function invokes the current Lambda function asynchronously with a special
    event type to handle memory storage without blocking the main response.
    
    Args:
        farmer_id: Unique farmer identifier
        question: Farmer's question
        advice: System's advice
        context: Full context data
        
    Raises:
        Exception: If async invocation fails
    """
    try:
        lambda_client = boto3.client('lambda', region_name=Config.AWS_REGION)
        
        # Prepare payload for async memory storage
        payload = {
            'eventType': 'STORE_MEMORY',
            'farmer_id': farmer_id,
            'question': question,
            'advice': advice,
            'context': {
                'weather': {
                    'temperature': context.weather.current.temperature if context.weather else None,
                    'condition': context.weather.current.condition if context.weather else None,
                },
                'landRecords': context.landRecords is not None,
                'memory': {
                    'recentInteractions': len(context.memory.recentInteractions) if context.memory else 0
                }
            }
        }
        
        # Get Lambda function name from environment or config
        function_name = os.getenv('AWS_LAMBDA_FUNCTION_NAME', Config.LAMBDA_FUNCTION_NAME)
        
        # Invoke Lambda asynchronously (Event invocation type)
        lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )
        
        logger.info(f"Async memory storage invoked for farmer {farmer_id}")
        
    except Exception as e:
        logger.error(f"Failed to invoke async memory storage: {e}")
        raise


def strip_markdown_formatting(text: str) -> str:
    """
    Remove markdown formatting from text before TTS synthesis.
    
    Removes:
    - Bold markers: **text** or __text__
    - Italic markers: *text* or _text_
    - Headers: # text
    - Lists: - text or * text or 1. text
    - Links: [text](url)
    - Code blocks: ```text``` or `text`
    
    Args:
        text: Text with markdown formatting
        
    Returns:
        Plain text without markdown formatting
    """
    if not text:
        return text
    
    # Remove bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    
    # Remove italic: *text* or _text_ (but not in middle of words)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'\b_(.+?)_\b', r'\1', text)
    
    # Remove headers: # text
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # Remove list markers: - text or * text or 1. text
    text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # Remove links: [text](url) -> text
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    
    # Remove code blocks: ```text``` or `text`
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'`(.+?)`', r'\1', text)
    
    # Remove extra whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = text.strip()
    
    return text


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler triggered by S3 upload events or async memory storage.
    
    Handles two event types:
    1. S3 upload events: Complete Guru Cycle with audio response
    2. STORE_MEMORY events: Async memory storage (no response needed)
    
    Coordinates the complete Guru Cycle:
    1. Parse S3 event and detect bandwidth mode
    2. Transcribe audio to text
    3. Fetch context in parallel (weather, land records, memory)
    4. Invoke specialized agents (Weather Analytics, ICAR Knowledge)
    5. Build Memory-First prompt and invoke Claude
    6. Execute Chain-of-Verification safety validation
    7. Synthesize speech response
    8. Return audio immediately (improved response time)
    9. Store interaction in AgentCore Memory asynchronously
    10. Handle USSD fallback for low-bandwidth timeouts
    
    Args:
        event: S3 event or STORE_MEMORY event
        context: Lambda context object
        
    Returns:
        Response dictionary with status, audio key, and optional USSD fallback
        
    Validates:
        Requirements 11.1, 11.2, 11.4, 11.5, 11.6, 11.7
    """
    start_time = time.time()
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Check if this is an async memory storage event
    if event.get('eventType') == 'STORE_MEMORY':
        return _handle_async_memory_storage(event)
    
    try:
        # Parse S3 event to extract audio metadata
        audio_request = parse_s3_event(event)
        logger.info(f"Parsed audio request: farmer_id={audio_request['farmer_id']}, "
                   f"audio_key={audio_request['audio_key']}")
        
        # Step 1: Detect bandwidth mode (Requirement 14.1)
        bandwidth_mode = detect_bandwidth_mode(
            audio_request['audio_key'],
            audio_request.get('metadata')
        )
        logger.info(f"Bandwidth mode: {bandwidth_mode}")
        
        # Step 2: Transcribe audio (Requirement 1.1)
        detected_language = audio_request.get('language', 'hi-IN')  # Default language
        try:
            transcribed_text, detected_language, confidence = transcribe_with_retry(
                audio_request['audio_key'],
                language_hint=detected_language,
                low_bandwidth=(bandwidth_mode == 'low')
            )
            logger.info(f"Transcription complete: language={detected_language}, "
                       f"confidence={confidence:.2f}")
        except LowConfidenceError as e:
            # Handle low confidence by asking farmer to repeat
            logger.warning(f"Low confidence transcription: {e}")
            return _create_error_response(
                "I'm sorry, I couldn't understand that clearly. "
                "Could you please repeat your question in simpler words?",
                detected_language,
                bandwidth_mode
            )
        
        # Step 3: Parallel context retrieval (Requirement 11.2)
        context_data = fetch_context_parallel(
            farmer_id=audio_request['farmer_id'],
            latitude=audio_request['gps']['latitude'],
            longitude=audio_request['gps']['longitude'],
            agristack_id=audio_request.get('agristack_id')
        )
        logger.info(f"Context retrieved: weather={context_data.weather.current.temperature}°C, "
                   f"land_records={'available' if context_data.landRecords else 'none'}")
        
        # Step 4: Invoke specialized agents in parallel (Requirement 11.3)
        agent_outputs = invoke_agents_parallel(context_data, transcribed_text)
        logger.info("Specialized agents invoked successfully")
        
        # Step 5: Construct Memory-First prompt (Requirement 2.2, 13.1-13.6)
        prompt = build_memory_first_prompt(
            question=transcribed_text,
            context=context_data,
            weather_analysis=agent_outputs['weather_analysis'],
            icar_knowledge=agent_outputs['icar_knowledge'],
            language=detected_language
        )
        
        # Step 6: Invoke Claude via Bedrock (Requirement 11.4)
        advice_text = invoke_bedrock(prompt)
        logger.info(f"Advice generated: {len(advice_text)} characters")
        
        # Log first 500 and last 500 characters for debugging
        if len(advice_text) > 1000:
            logger.info(f"Advice text (first 500 chars): {advice_text[:500]}")
            logger.info(f"Advice text (last 500 chars): {advice_text[-500:]}")
        else:
            logger.info(f"Advice text (full): {advice_text}")
        
        # Step 7: Chain-of-Verification (Requirement 4.6, 11.5)
        validation_result = validate_safety(advice_text, context_data.weather)
        
        if not validation_result.isApproved:
            logger.warning(f"Advice blocked by safety validator: "
                          f"{len(validation_result.conflicts)} conflicts")
            advice_text = validation_result.alternativeRecommendation
        
        # Step 8: Synthesize speech (Requirement 1.2, 11.6)
        # Strip markdown formatting before TTS (removes **, __, *, etc.)
        tts_text = strip_markdown_formatting(advice_text)
        logger.info(f"Stripped markdown formatting for TTS: {len(advice_text)} -> {len(tts_text)} chars")
        
        # Log first 500 and last 500 characters after stripping for debugging
        if len(tts_text) > 1000:
            logger.info(f"TTS text after stripping (first 500 chars): {tts_text[:500]}")
            logger.info(f"TTS text after stripping (last 500 chars): {tts_text[-500:]}")
        else:
            logger.info(f"TTS text after stripping (full): {tts_text}")
        
        audio_key, synthesis_service = synthesize_speech(
            tts_text,
            detected_language,
            low_bandwidth=(bandwidth_mode == 'low'),
            request_id=audio_request.get('metadata', {}).get('request_id')
        )
        logger.info(f"Speech synthesized: service={synthesis_service}, key={audio_key}")
        
        # Calculate execution time BEFORE memory storage for accurate response time
        execution_time = time.time() - start_time
        logger.info(f"Voice loop completed (before memory storage) in {execution_time:.2f} seconds")
        
        # Step 9: Store interaction in AgentCore Memory asynchronously (Requirement 11.7)
        # This is done AFTER calculating response time to improve perceived latency
        try:
            _store_interaction_async(
                farmer_id=audio_request['farmer_id'],
                question=transcribed_text,
                advice=advice_text,
                context=context_data
            )
            logger.info("Interaction storage initiated asynchronously")
        except Exception as e:
            # Don't fail the response if async storage fails
            logger.error(f"Failed to initiate async memory storage: {e}")
            # Fall back to synchronous storage
            try:
                store_interaction(
                    farmer_id=audio_request['farmer_id'],
                    question=transcribed_text,
                    advice=advice_text,
                    context=context_data
                )
                logger.info("Interaction stored synchronously (fallback)")
            except Exception as sync_error:
                logger.error(f"Synchronous memory storage also failed: {sync_error}")
        
        # Step 10: Check for USSD fallback if timeout exceeded (Requirement 14.4, 14.5)
        response = {
            'statusCode': 200,
            'audioKey': audio_key,
            'synthesisService': synthesis_service,
            'validationResult': {
                'isApproved': validation_result.isApproved,
                'conflicts': [
                    {
                        'type': c.type,
                        'severity': c.severity,
                        'message': c.message
                    }
                    for c in validation_result.conflicts
                ],
                'alternativeRecommendation': validation_result.alternativeRecommendation
            },
            'executionTime': execution_time,
            'bandwidthMode': bandwidth_mode
        }
        
        # Offer USSD fallback if voice loop exceeded timeout in low-bandwidth mode
        if bandwidth_mode == 'low' and execution_time > Config.VOICE_LOOP_TIMEOUT_SECONDS:
            logger.info("Voice loop timeout exceeded, generating USSD fallback")
            response['ussdFallback'] = generate_ussd_fallback(advice_text)
        
        return response
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'error_type': type(e).__name__
            })
        }


def _handle_async_memory_storage(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle async memory storage event.
    
    This function is called when the Lambda is invoked asynchronously
    to store interaction in AgentCore Memory without blocking the main response.
    
    Args:
        event: STORE_MEMORY event with farmer_id, question, advice, context
        
    Returns:
        Success response
    """
    try:
        logger.info(f"Handling async memory storage for farmer {event['farmer_id']}")
        
        # Reconstruct minimal context for storage
        # Note: We don't need full context, just enough for memory formatting
        from src.models.context_data import ContextData, WeatherData, CurrentWeather, MemoryContext
        
        context_dict = event.get('context', {})
        weather_dict = context_dict.get('weather', {})
        
        # Create minimal context object
        context = ContextData(
            weather=WeatherData(
                current=CurrentWeather(
                    temperature=weather_dict.get('temperature', 0),
                    condition=weather_dict.get('condition', 'Unknown'),
                    humidity=0,
                    windSpeed=0,
                    precipitation=0
                ),
                forecast=[],
                alerts=[]
            ) if weather_dict.get('temperature') else None,
            landRecords=None,  # Not needed for memory storage
            memory=MemoryContext()  # Empty memory context
        )
        
        # Store interaction synchronously (this Lambda invocation is already async)
        store_interaction(
            farmer_id=event['farmer_id'],
            question=event['question'],
            advice=event['advice'],
            context=context
        )
        
        logger.info(f"Async memory storage completed for farmer {event['farmer_id']}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Memory stored successfully'})
        }
        
    except Exception as e:
        logger.error(f"Error in async memory storage: {e}", exc_info=True)
        # Don't fail - memory storage is not critical
        return {
            'statusCode': 200,  # Return 200 to avoid retries
            'body': json.dumps({'message': 'Memory storage failed', 'error': str(e)})
        }


def parse_s3_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse S3 upload event to extract audio metadata.
    
    Args:
        event: S3 event dictionary
        
    Returns:
        Dictionary with farmer_id, audio_key, gps, language, metadata
        
    Raises:
        ValueError: If event format is invalid or missing required fields
        
    Validates:
        Requirement 11.1
    """
    try:
        # Extract S3 record
        if 'Records' not in event or len(event['Records']) == 0:
            raise ValueError("No S3 records found in event")
        
        record = event['Records'][0]
        
        # Validate event source
        if record.get('eventSource') != 'aws:s3':
            raise ValueError(f"Invalid event source: {record.get('eventSource')}")
        
        # Extract S3 object key
        s3_info = record.get('s3', {})
        bucket = s3_info.get('bucket', {}).get('name')
        audio_key = s3_info.get('object', {}).get('key')
        
        if not audio_key:
            raise ValueError("Missing S3 object key in event")
        
        # Extract metadata from object key or user metadata
        # Expected format: {farmer_id}/{session_id}/{timestamp}.wav
        # Or metadata can be in S3 object metadata
        metadata = _extract_metadata_from_key(audio_key)
        
        # Validate required fields
        if 'farmer_id' not in metadata:
            raise ValueError("Missing farmer_id in audio metadata")
        
        if 'gps' not in metadata:
            raise ValueError("Missing GPS coordinates in audio metadata")
        
        return {
            'audio_key': audio_key,
            'bucket': bucket,
            'farmer_id': metadata['farmer_id'],
            'gps': metadata['gps'],
            'language': metadata.get('language'),
            'agristack_id': metadata.get('agristack_id'),
            'metadata': metadata
        }
        
    except KeyError as e:
        raise ValueError(f"Invalid S3 event structure: missing field {e}")
    except Exception as e:
        raise ValueError(f"Failed to parse S3 event: {str(e)}")


def _extract_metadata_from_key(audio_key: str) -> Dict[str, Any]:
    """
    Extract metadata from S3 object key and object metadata.
    
    Expected format: {farmer_id}/{session_id}/{timestamp}.wav
    Or metadata can be encoded in the key path.
    
    Args:
        audio_key: S3 object key
        
    Returns:
        Dictionary with extracted metadata
        
    Note:
        Reads S3 object metadata for language, GPS, etc.
    """
    # Parse key to extract farmer_id and session_id
    parts = audio_key.split('/')
    
    # Extract request_id from filename if present
    # Format: {timestamp}_{request_id}.m4a
    request_id = None
    if len(parts) > 2:
        filename = parts[2]
        # Remove extension
        filename_no_ext = filename.rsplit('.', 1)[0]
        # Split by underscore to get request_id
        filename_parts = filename_no_ext.split('_', 1)
        if len(filename_parts) > 1:
            request_id = filename_parts[1]
    
    # Initialize metadata with required fields (no language default yet)
    metadata = {
        'farmer_id': parts[0] if len(parts) > 1 else 'TEST_USER',
        'session_id': parts[1] if len(parts) > 2 else 'TEST_SESSION',
        'request_id': request_id,
        'gps': {
            'latitude': 28.6139, 
            'longitude': 77.2090
        }
    }
    
    # Try to read S3 object metadata FIRST before applying any language default
    try:
        s3_client = boto3.client('s3')
        response = s3_client.head_object(
            Bucket=Config.AUDIO_INPUT_BUCKET,
            Key=audio_key
        )
        
        # Extract metadata from S3 object metadata
        s3_metadata = response.get('Metadata', {})
        
        # Update with S3 metadata if available
        if 'language' in s3_metadata:
            metadata['language'] = s3_metadata['language']
            logger.info(f"Extracted language from S3 metadata: {metadata['language']}")
        
        if 'latitude' in s3_metadata and 'longitude' in s3_metadata:
            try:
                metadata['gps']['latitude'] = float(s3_metadata['latitude'])
                metadata['gps']['longitude'] = float(s3_metadata['longitude'])
            except (ValueError, TypeError):
                pass  # Keep defaults
        
        if 'agristackid' in s3_metadata:
            metadata['agristack_id'] = s3_metadata['agristackid']
            
        logger.info(f"Successfully extracted metadata from S3 object: language={metadata.get('language', 'NOT_SET')}, "
                   f"gps=({metadata['gps']['latitude']}, {metadata['gps']['longitude']})")
    except Exception as e:
        logger.warning(f"Could not read S3 object metadata: {e}. Will use default language if not set.")
    
    # Only apply Hindi default if language was not extracted from S3 metadata
    if 'language' not in metadata:
        metadata['language'] = 'hi-IN'
        logger.info("No language metadata found in S3, using default: hi-IN")
    
    return metadata


def _create_error_response(
    error_message: str,
    language: str,
    bandwidth_mode: str
) -> Dict[str, Any]:
    """
    Create an error response with synthesized audio.
    
    Args:
        error_message: Error message to speak to farmer
        language: Language code for synthesis
        bandwidth_mode: 'low' or 'normal'
        
    Returns:
        Response dictionary with error audio
    """
    try:
        # Strip markdown formatting before TTS
        tts_message = strip_markdown_formatting(error_message)
        
        # Synthesize error message
        audio_key, service = synthesize_speech(
            tts_message,
            language,
            low_bandwidth=(bandwidth_mode == 'low')
        )
        
        return {
            'statusCode': 200,
            'audioKey': audio_key,
            'synthesisService': service,
            'isError': True,
            'errorMessage': error_message
        }
    except Exception as e:
        # If synthesis fails, return text-only error
        logger.error(f"Failed to synthesize error message: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': error_message,
                'synthesis_failed': True
            })
        }
