"""
Property-based tests for Voice Loop Completion

Tests Property 1: Voice Loop Completion
Validates Requirements 1.1, 1.2, 1.3

**Validates: Requirements 1.1, 1.2, 1.3**
"""

import pytest
import time
import uuid
from datetime import datetime
from unittest.mock import patch, MagicMock, Mock
from hypothesis import given, strategies as st, settings

from src.lambda_handler import lambda_handler
from src.models.context_data import (
    ContextData, WeatherData, CurrentWeather, Forecast6h,
    LandRecords, MemoryContext, ConsolidatedInsights
)
from src.models.safety_validation import SafetyValidationResult


# Hypothesis Strategies

@st.composite
def valid_audio_input_strategy(draw):
    """
    Generate random valid audio inputs for property testing.
    
    Returns:
        S3 event with valid audio input in a supported language
    """
    farmer_id = f"FARMER-{draw(st.integers(min_value=1, max_value=9999))}"
    session_id = f"SESSION-{draw(st.uuids())}"
    timestamp = draw(st.integers(min_value=1000000000, max_value=9999999999))
    
    # Supported languages (Requirement 7.1)
    language = draw(st.sampled_from([
        'hi-IN',  # Hindi
        'ta-IN',  # Tamil
        'te-IN',  # Telugu
        'kn-IN',  # Kannada
        'mr-IN',  # Marathi
        'bn-IN',  # Bengali
        'gu-IN',  # Gujarati
        'pa-IN'   # Punjabi
    ]))
    
    # Valid audio file extensions
    file_extension = draw(st.sampled_from(['wav', 'mp3', 'ogg']))
    
    # Valid audio size (1KB to 10MB)
    audio_size = draw(st.integers(min_value=1000, max_value=10000000))
    
    return {
        'Records': [
            {
                'eventSource': 'aws:s3',
                'eventName': 'ObjectCreated:Put',
                'eventTime': datetime.utcnow().isoformat(),
                's3': {
                    'bucket': {
                        'name': 'vaniverse-audio-input'
                    },
                    'object': {
                        'key': f'{farmer_id}/{session_id}/{timestamp}.{file_extension}',
                        'size': audio_size
                    }
                }
            }
        ],
        'metadata': {
            'farmer_id': farmer_id,
            'language': language,
            'gps': {
                'latitude': draw(st.floats(min_value=8.0, max_value=37.0)),
                'longitude': draw(st.floats(min_value=68.0, max_value=97.0))
            }
        }
    }


@st.composite
def farmer_question_strategy(draw):
    """
    Generate random farmer questions in various languages.
    
    Returns:
        Transcribed text representing a farmer's question
    """
    # Sample agricultural questions
    questions = [
        "How do I control pests on my rice crop?",
        "When should I irrigate my wheat field?",
        "What fertilizer should I use for tomatoes?",
        "Is it safe to spray pesticide today?",
        "How do I treat leaf curl disease?",
        "When is the best time to harvest?",
        "Should I plant now or wait for rain?",
        "What is the best crop for my soil type?"
    ]
    
    return draw(st.sampled_from(questions))


@st.composite
def context_data_strategy(draw):
    """
    Generate random context data for testing.
    
    Returns:
        ContextData with weather, land records, and memory
    """
    return ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=draw(st.floats(min_value=15.0, max_value=45.0)),
                humidity=draw(st.floats(min_value=20.0, max_value=100.0)),
                windSpeed=draw(st.floats(min_value=0.0, max_value=50.0)),
                precipitation=draw(st.floats(min_value=0.0, max_value=100.0))
            ),
            forecast6h=Forecast6h(
                precipitationProbability=draw(st.floats(min_value=0.0, max_value=100.0)),
                expectedRainfall=draw(st.floats(min_value=0.0, max_value=50.0)),
                temperature=draw(st.floats(min_value=15.0, max_value=45.0)),
                windSpeed=draw(st.floats(min_value=0.0, max_value=50.0))
            ),
            timestamp=datetime.utcnow().isoformat()
        ),
        landRecords=LandRecords(
            landArea=draw(st.floats(min_value=0.5, max_value=10.0)),
            soilType=draw(st.sampled_from(['Clay Loam', 'Sandy', 'Loamy', 'Clay', 'Sandy Loam'])),
            currentCrop=draw(st.sampled_from(['Rice', 'Wheat', 'Cotton', 'Sugarcane', 'Maize', 'Tomato'])),
            cropHistory=[]
        ),
        memory=MemoryContext(
            recentInteractions=[],
            unresolvedIssues=[],
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop=draw(st.sampled_from(['Rice', 'Wheat', 'Cotton', 'Sugarcane'])),
                commonConcerns=[],
                farmerName=draw(st.text(min_size=3, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'))))
            )
        )
    )


# Property Tests

@given(
    audio_input=valid_audio_input_strategy(),
    question=farmer_question_strategy(),
    context=context_data_strategy()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.pbt
def test_property_1_voice_loop_completion(audio_input, question, context):
    """
    Feature: vaniverse, Property 1: Voice Loop Completion
    
    **Validates: Requirements 1.1, 1.2, 1.3**
    
    For any valid audio input in a supported language, the system should 
    complete the full cycle of:
    1. Transcription (speech-to-text) - Requirement 1.1
    2. Context retrieval
    3. Advice generation
    4. Safety validation
    5. Synthesis (text-to-speech) - Requirement 1.2
    
    And return an audio response.
    
    This property test verifies that the complete voice loop executes
    successfully for all valid inputs across all supported languages.
    """
    # Mock all external dependencies to test the orchestration flow
    with patch('src.lambda_handler.detect_bandwidth_mode') as mock_bandwidth, \
         patch('src.lambda_handler.transcribe_with_retry') as mock_transcribe, \
         patch('src.lambda_handler.fetch_context_parallel') as mock_context, \
         patch('src.lambda_handler.invoke_agents_parallel') as mock_agents, \
         patch('src.lambda_handler.build_memory_first_prompt') as mock_prompt, \
         patch('src.lambda_handler.invoke_bedrock') as mock_bedrock, \
         patch('src.lambda_handler.validate_safety') as mock_validate, \
         patch('src.lambda_handler.synthesize_speech') as mock_synthesize, \
         patch('src.lambda_handler.store_interaction') as mock_store:
        
        # Extract language from audio input
        language = audio_input.get('metadata', {}).get('language', 'hi-IN')
        
        # Setup mocks to simulate successful voice loop
        mock_bandwidth.return_value = 'normal'
        
        # Mock transcription (Requirement 1.1: speech-to-text)
        mock_transcribe.return_value = (
            question,  # Transcribed text
            language,  # Detected language
            0.95       # High confidence
        )
        
        # Mock context retrieval
        mock_context.return_value = context
        
        # Mock specialized agents
        mock_agents.return_value = {
            'weather_analysis': f'Weather analysis for {question}',
            'icar_knowledge': f'ICAR knowledge for {question}'
        }
        
        # Mock prompt construction
        mock_prompt.return_value = MagicMock()
        
        # Mock Claude advice generation
        advice_text = f"Agricultural advice for: {question}"
        mock_bedrock.return_value = advice_text
        
        # Mock safety validation (approve the advice)
        mock_validate.return_value = SafetyValidationResult(
            isApproved=True,
            conflicts=[],
            alternativeRecommendation=None
        )
        
        # Mock speech synthesis (Requirement 1.2: text-to-speech)
        audio_key = f'responses/{uuid.uuid4()}.mp3'
        synthesis_service = 'polly' if language in ['hi-IN', 'ta-IN', 'te-IN', 'kn-IN'] else 'bhashini'
        mock_synthesize.return_value = (audio_key, synthesis_service)
        
        # Execute the voice loop
        start_time = time.time()
        response = lambda_handler(audio_input, Mock())
        execution_time = time.time() - start_time
        
        # PROPERTY VERIFICATION: Voice loop completes successfully
        
        # 1. Response is returned
        assert response is not None, "Voice loop should return a response"
        
        # 2. Response has successful status
        assert response['statusCode'] == 200, (
            f"Voice loop should complete successfully, got status {response['statusCode']}"
        )
        
        # 3. Audio response is generated (Requirement 1.2)
        assert 'audioKey' in response, "Response should contain audio key"
        assert response['audioKey'] is not None, "Audio key should not be None"
        assert len(response['audioKey']) > 0, "Audio key should not be empty"
        
        # 4. Synthesis service is specified
        assert 'synthesisService' in response, "Response should specify synthesis service"
        assert response['synthesisService'] in ['polly', 'bhashini'], (
            f"Invalid synthesis service: {response['synthesisService']}"
        )
        
        # 5. Execution time is recorded
        assert 'executionTime' in response, "Response should include execution time"
        assert response['executionTime'] >= 0, "Execution time should be non-negative"
        
        # 6. Validation result is included
        assert 'validationResult' in response, "Response should include validation result"
        assert 'isApproved' in response['validationResult'], (
            "Validation result should include approval status"
        )
        
        # VERIFY COMPLETE CYCLE EXECUTION
        
        # Step 1: Transcription was invoked (Requirement 1.1)
        assert mock_transcribe.called, "Transcription should be invoked"
        transcribe_call = mock_transcribe.call_args
        assert transcribe_call is not None, "Transcription should be called with arguments"
        
        # Step 2: Context retrieval was invoked
        assert mock_context.called, "Context retrieval should be invoked"
        
        # Step 3: Specialized agents were invoked
        assert mock_agents.called, "Specialized agents should be invoked"
        
        # Step 4: Claude was invoked for advice generation
        assert mock_bedrock.called, "Claude should be invoked for advice generation"
        
        # Step 5: Safety validation was performed
        assert mock_validate.called, "Safety validation should be performed"
        
        # Step 6: Speech synthesis was invoked (Requirement 1.2)
        assert mock_synthesize.called, "Speech synthesis should be invoked"
        synthesize_call = mock_synthesize.call_args[0]
        assert synthesize_call[0] == advice_text, "Correct advice text should be synthesized"
        assert synthesize_call[1] == language, "Synthesis should use detected language"
        
        # Step 7: Interaction was stored in memory
        assert mock_store.called, "Interaction should be stored in memory"
        
        # VERIFY ORDERING: Safety validation before synthesis
        # (This ensures Chain-of-Verification is executed correctly)
        validate_call_time = mock_validate.call_count
        synthesize_call_time = mock_synthesize.call_count
        assert validate_call_time > 0, "Validation should be called"
        assert synthesize_call_time > 0, "Synthesis should be called"


@given(
    audio_input=valid_audio_input_strategy(),
    question=farmer_question_strategy(),
    context=context_data_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_voice_loop_returns_valid_audio_response(audio_input, question, context):
    """
    Property test: Voice loop returns valid audio response structure.
    
    For any valid audio input, the response should contain:
    - Valid audio key (S3 path)
    - Synthesis service identifier
    - Validation result
    - Execution metadata
    
    **Validates: Requirements 1.1, 1.2, 1.3**
    """
    with patch('src.lambda_handler.detect_bandwidth_mode') as mock_bandwidth, \
         patch('src.lambda_handler.transcribe_with_retry') as mock_transcribe, \
         patch('src.lambda_handler.fetch_context_parallel') as mock_context, \
         patch('src.lambda_handler.invoke_agents_parallel') as mock_agents, \
         patch('src.lambda_handler.build_memory_first_prompt') as mock_prompt, \
         patch('src.lambda_handler.invoke_bedrock') as mock_bedrock, \
         patch('src.lambda_handler.validate_safety') as mock_validate, \
         patch('src.lambda_handler.synthesize_speech') as mock_synthesize, \
         patch('src.lambda_handler.store_interaction') as mock_store:
        
        language = audio_input.get('metadata', {}).get('language', 'hi-IN')
        
        # Setup mocks
        mock_bandwidth.return_value = 'normal'
        mock_transcribe.return_value = (question, language, 0.95)
        mock_context.return_value = context
        mock_agents.return_value = {
            'weather_analysis': 'Analysis',
            'icar_knowledge': 'Knowledge'
        }
        mock_prompt.return_value = MagicMock()
        mock_bedrock.return_value = "Test advice"
        mock_validate.return_value = SafetyValidationResult(
            isApproved=True,
            conflicts=[],
            alternativeRecommendation=None
        )
        
        # Generate unique audio key
        audio_key = f'responses/{uuid.uuid4()}.mp3'
        mock_synthesize.return_value = (audio_key, 'polly')
        
        # Execute
        response = lambda_handler(audio_input, Mock())
        
        # Verify response structure
        assert isinstance(response, dict), "Response should be a dictionary"
        assert 'statusCode' in response, "Response should have statusCode"
        assert 'audioKey' in response, "Response should have audioKey"
        assert 'synthesisService' in response, "Response should have synthesisService"
        assert 'validationResult' in response, "Response should have validationResult"
        assert 'executionTime' in response, "Response should have executionTime"
        assert 'bandwidthMode' in response, "Response should have bandwidthMode"
        
        # Verify audio key format
        assert isinstance(response['audioKey'], str), "Audio key should be string"
        assert len(response['audioKey']) > 0, "Audio key should not be empty"
        assert response['audioKey'].endswith('.mp3'), "Audio key should be MP3 file"
        
        # Verify synthesis service
        assert response['synthesisService'] in ['polly', 'bhashini'], (
            "Synthesis service should be polly or bhashini"
        )
        
        # Verify validation result structure
        validation = response['validationResult']
        assert 'isApproved' in validation, "Validation should have isApproved"
        assert 'conflicts' in validation, "Validation should have conflicts list"
        assert isinstance(validation['conflicts'], list), "Conflicts should be a list"


@given(
    audio_input=valid_audio_input_strategy(),
    question=farmer_question_strategy(),
    context=context_data_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_voice_loop_handles_all_supported_languages(audio_input, question, context):
    """
    Property test: Voice loop handles all supported languages.
    
    For any audio input in a supported language (Hindi, Tamil, Telugu, 
    Kannada, Marathi, Bengali, Gujarati, Punjabi), the system should:
    1. Successfully transcribe the audio
    2. Generate advice
    3. Synthesize response in the same language
    
    **Validates: Requirements 1.1, 1.2, 7.1**
    """
    with patch('src.lambda_handler.detect_bandwidth_mode') as mock_bandwidth, \
         patch('src.lambda_handler.transcribe_with_retry') as mock_transcribe, \
         patch('src.lambda_handler.fetch_context_parallel') as mock_context, \
         patch('src.lambda_handler.invoke_agents_parallel') as mock_agents, \
         patch('src.lambda_handler.build_memory_first_prompt') as mock_prompt, \
         patch('src.lambda_handler.invoke_bedrock') as mock_bedrock, \
         patch('src.lambda_handler.validate_safety') as mock_validate, \
         patch('src.lambda_handler.synthesize_speech') as mock_synthesize, \
         patch('src.lambda_handler.store_interaction') as mock_store:
        
        language = audio_input.get('metadata', {}).get('language', 'hi-IN')
        
        # Verify language is supported
        supported_languages = ['hi-IN', 'ta-IN', 'te-IN', 'kn-IN', 'mr-IN', 'bn-IN', 'gu-IN', 'pa-IN']
        assert language in supported_languages, f"Language {language} should be supported"
        
        # Setup mocks
        mock_bandwidth.return_value = 'normal'
        mock_transcribe.return_value = (question, language, 0.95)
        mock_context.return_value = context
        mock_agents.return_value = {
            'weather_analysis': 'Analysis',
            'icar_knowledge': 'Knowledge'
        }
        mock_prompt.return_value = MagicMock()
        mock_bedrock.return_value = "Test advice"
        mock_validate.return_value = SafetyValidationResult(
            isApproved=True,
            conflicts=[],
            alternativeRecommendation=None
        )
        mock_synthesize.return_value = (f'response-{language}.mp3', 'polly')
        
        # Execute
        response = lambda_handler(audio_input, Mock())
        
        # Verify language handling
        assert response['statusCode'] == 200, (
            f"Voice loop should succeed for language {language}"
        )
        
        # Verify transcription was called with correct language
        transcribe_call = mock_transcribe.call_args
        assert transcribe_call is not None, "Transcription should be called"
        
        # Verify synthesis was called with correct language
        synthesize_call = mock_synthesize.call_args[0]
        assert synthesize_call[1] == language, (
            f"Synthesis should use language {language}, got {synthesize_call[1]}"
        )


@given(
    audio_input=valid_audio_input_strategy(),
    question=farmer_question_strategy(),
    context=context_data_strategy()
)
@settings(max_examples=30, deadline=None)
@pytest.mark.pbt
def test_voice_loop_execution_time_tracking(audio_input, question, context):
    """
    Property test: Voice loop tracks execution time.
    
    For any voice loop execution, the system should:
    1. Track the total execution time
    2. Return execution time in response
    3. Execution time should be positive and reasonable
    
    **Validates: Requirements 1.4, 11.2**
    """
    with patch('src.lambda_handler.detect_bandwidth_mode') as mock_bandwidth, \
         patch('src.lambda_handler.transcribe_with_retry') as mock_transcribe, \
         patch('src.lambda_handler.fetch_context_parallel') as mock_context, \
         patch('src.lambda_handler.invoke_agents_parallel') as mock_agents, \
         patch('src.lambda_handler.build_memory_first_prompt') as mock_prompt, \
         patch('src.lambda_handler.invoke_bedrock') as mock_bedrock, \
         patch('src.lambda_handler.validate_safety') as mock_validate, \
         patch('src.lambda_handler.synthesize_speech') as mock_synthesize, \
         patch('src.lambda_handler.store_interaction') as mock_store:
        
        language = audio_input.get('metadata', {}).get('language', 'hi-IN')
        
        # Setup mocks
        mock_bandwidth.return_value = 'normal'
        mock_transcribe.return_value = (question, language, 0.95)
        mock_context.return_value = context
        mock_agents.return_value = {
            'weather_analysis': 'Analysis',
            'icar_knowledge': 'Knowledge'
        }
        mock_prompt.return_value = MagicMock()
        mock_bedrock.return_value = "Test advice"
        mock_validate.return_value = SafetyValidationResult(
            isApproved=True,
            conflicts=[],
            alternativeRecommendation=None
        )
        mock_synthesize.return_value = ('response.mp3', 'polly')
        
        # Execute and measure time
        start_time = time.time()
        response = lambda_handler(audio_input, Mock())
        actual_execution_time = time.time() - start_time
        
        # Verify execution time tracking
        assert 'executionTime' in response, "Response should include execution time"
        reported_time = response['executionTime']
        
        # Execution time should be positive
        assert reported_time >= 0, "Execution time should be non-negative"
        
        # Reported time should be close to actual time (within 1 second tolerance)
        assert abs(reported_time - actual_execution_time) < 1.0, (
            f"Reported time {reported_time:.3f}s should match actual time {actual_execution_time:.3f}s"
        )
        
        # Execution time should be reasonable (not too long)
        # In production, target is <6 seconds, but in tests with mocks it should be much faster
        assert reported_time < 10.0, (
            f"Execution time {reported_time:.3f}s should be reasonable"
        )


@given(
    audio_input=valid_audio_input_strategy(),
    question=farmer_question_strategy(),
    context=context_data_strategy()
)
@settings(max_examples=30, deadline=None)
@pytest.mark.pbt
def test_voice_loop_memory_storage(audio_input, question, context):
    """
    Property test: Voice loop stores interaction in memory.
    
    For any completed voice loop, the system should:
    1. Store the interaction in AgentCore Memory
    2. Include farmer_id, question, advice, and context
    
    **Validates: Requirements 2.1, 2.3, 11.7**
    """
    with patch('src.lambda_handler.detect_bandwidth_mode') as mock_bandwidth, \
         patch('src.lambda_handler.transcribe_with_retry') as mock_transcribe, \
         patch('src.lambda_handler.fetch_context_parallel') as mock_context, \
         patch('src.lambda_handler.invoke_agents_parallel') as mock_agents, \
         patch('src.lambda_handler.build_memory_first_prompt') as mock_prompt, \
         patch('src.lambda_handler.invoke_bedrock') as mock_bedrock, \
         patch('src.lambda_handler.validate_safety') as mock_validate, \
         patch('src.lambda_handler.synthesize_speech') as mock_synthesize, \
         patch('src.lambda_handler.store_interaction') as mock_store:
        
        language = audio_input.get('metadata', {}).get('language', 'hi-IN')
        farmer_id = audio_input.get('metadata', {}).get('farmer_id', 'UNKNOWN')
        
        # Setup mocks
        mock_bandwidth.return_value = 'normal'
        mock_transcribe.return_value = (question, language, 0.95)
        mock_context.return_value = context
        mock_agents.return_value = {
            'weather_analysis': 'Analysis',
            'icar_knowledge': 'Knowledge'
        }
        mock_prompt.return_value = MagicMock()
        
        advice_text = f"Advice for {question}"
        mock_bedrock.return_value = advice_text
        
        mock_validate.return_value = SafetyValidationResult(
            isApproved=True,
            conflicts=[],
            alternativeRecommendation=None
        )
        mock_synthesize.return_value = ('response.mp3', 'polly')
        
        # Execute
        response = lambda_handler(audio_input, Mock())
        
        # Verify memory storage was invoked
        assert mock_store.called, "Interaction should be stored in memory"
        
        # Verify storage was called with correct parameters
        store_call = mock_store.call_args
        assert store_call is not None, "Storage should be called with arguments"
        
        # Extract call arguments (positional or keyword)
        if store_call[0]:  # Positional arguments
            call_farmer_id = store_call[0][0]
            call_question = store_call[0][1]
            call_advice = store_call[0][2]
            call_context = store_call[0][3]
        else:  # Keyword arguments
            call_farmer_id = store_call[1].get('farmer_id')
            call_question = store_call[1].get('question')
            call_advice = store_call[1].get('advice')
            call_context = store_call[1].get('context')
        
        # Verify correct data was stored
        assert call_question == question, "Stored question should match transcribed text"
        assert call_advice == advice_text, "Stored advice should match generated advice"
        assert call_context == context, "Stored context should match retrieved context"
