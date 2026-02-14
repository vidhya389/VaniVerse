# Implementation Plan: VaniVerse - Proactive Voice-First Layer for Bharat-VISTAAR

## Overview

This implementation plan breaks down the VaniVerse system into discrete, incremental coding tasks. The system will be built using Python for AWS Lambda functions, with a focus on serverless architecture, managed services (AgentCore Memory, Bedrock, Transcribe, Polly), and the multi-agent orchestration pattern. Each task builds on previous work to create a complete voice-first AI assistant for Indian farmers.

## Tasks

- [ ] 1. Set up AWS infrastructure and project structure
  - Create Python project with virtual environment
  - Configure AWS SDK (boto3) with credentials
  - Set up S3 buckets for audio storage (input and output)
  - Configure IAM roles and policies for Lambda execution
  - Set up environment variables for API keys (OpenWeather, Bhashini, UFSI)
  - _Requirements: 11.1_

- [ ] 2. Implement core data models and types
  - [ ] 2.1 Create data model classes for FarmerSession, AudioRequest, ContextData
    - Define Python dataclasses or Pydantic models for type safety
    - Include WeatherData, LandRecords, MemoryContext structures
    - Implement serialization/deserialization methods
    - _Requirements: 3.1, 3.2, 5.3_
  
  - [ ] 2.2 Write property test for data model serialization
    - **Property: Serialization round trip**
    - **Validates: Requirements 2.3, 11.7**
    - Test that any data model instance can be serialized to JSON and deserialized back to an equivalent object

- [ ] 3. Implement speech processing module
  - [ ] 3.1 Create AWS Transcribe integration for speech-to-text
    - Implement transcribe_audio() function with language detection
    - Support all 8 regional dialects (Hindi, Tamil, Telugu, Kannada, Marathi, Bengali, Gujarati, Punjabi)
    - Handle low-bandwidth mode with compressed audio
    - Implement confidence scoring and retry logic
    - _Requirements: 1.1, 7.1, 7.2, 7.3, 14.2_
  
  - [ ] 3.2 Create Amazon Polly integration for text-to-speech
    - Implement synthesize_with_polly() function
    - Map languages to appropriate Polly voices
    - Support neural and standard engines for bandwidth modes
    - _Requirements: 1.2, 7.4_
  
  - [ ] 3.3 Create Bhashini API integration for unsupported languages
    - Implement synthesize_with_bhashini() function
    - Handle API authentication and error responses
    - _Requirements: 7.5_
  
  - [ ] 3.4 Implement speech service routing logic
    - Create synthesize_speech() dispatcher function
    - Route to Polly or Bhashini based on language support
    - _Requirements: 7.4, 7.5_
  
  - [ ] 3.5 Write property test for multi-language support
    - **Property 19: Multi-Language Support Coverage**
    - **Validates: Requirements 7.1**
    - Test that any audio input in supported languages is successfully transcribed and synthesized

- [ ] 4. Implement context retrieval module
  - [ ] 4.1 Create OpenWeather API client
    - Implement fetch_weather() function
    - Fetch current conditions and 6-hour forecast
    - Handle API errors with retry logic
    - Implement 30-minute cache invalidation
    - _Requirements: 3.1, 3.3_
  
  - [ ] 4.2 Create UFSI (AgriStack) API client
    - Implement fetch_land_records() function
    - Support OAuth 2.0 authentication
    - Include required headers (API key, consent token, request ID)
    - _Requirements: 3.2, 8.4, 12.4_
  
  - [ ] 4.3 Create mock UFSI layer for development
    - Implement fetch_mock_land_records() with sample data
    - Create 100+ diverse farmer profiles
    - _Requirements: 12.2_
  
  - [ ] 4.4 Implement AgentCore Memory integration
    - Create fetch_memory() function using bedrock-agent-runtime
    - Implement store_interaction() for automatic memory storage
    - Use FarmerID as session identifier
    - _Requirements: 2.1, 2.3, 5.3, 11.7_
  
  - [ ] 4.5 Implement parallel context retrieval
    - Create fetch_context_parallel() using ThreadPoolExecutor
    - Fetch weather, land records, and memory simultaneously
    - _Requirements: 11.2_
  
  - [ ] 4.6 Write property test for context assembly completeness
    - **Property 5: Context Assembly Completeness**
    - **Validates: Requirements 3.1, 3.2, 11.4**
    - Test that for any farmer request, all available context is fetched before advice generation

- [ ] 5. Checkpoint - Ensure context retrieval works end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement specialized agents (multi-agent approach)
  - [ ] 6.1 Create Weather Analytics Agent
    - Implement invoke_weather_analytics_agent() function
    - Create specialized system prompt for weather risk assessment
    - Invoke Claude 3.5 Sonnet via Bedrock
    - Return weather analysis and timing recommendations
    - _Requirements: 11.3, 11.4_
  
  - [ ] 6.2 Create ICAR Knowledge Agent
    - Implement invoke_icar_knowledge_agent() function
    - Create specialized system prompt with ICAR guidelines
    - Invoke Claude 3.5 Sonnet via Bedrock
    - Return crop-specific recommendations with citations
    - _Requirements: 11.3, 11.5, 10.2_
  
  - [ ] 6.3 Implement parallel agent invocation
    - Invoke both agents simultaneously using ThreadPoolExecutor
    - Combine agent outputs for final prompt construction
    - _Requirements: 11.3_
  
  - [ ] 6.4 Write property test for multi-agent invocation
    - **Property 37: Multi-Agent Invocation**
    - **Validates: Requirements 11.3, 11.4, 11.5**
    - Test that for any farmer question, both specialized agents are invoked in parallel

- [ ] 7. Implement Memory-First prompting module
  - [ ] 7.1 Create prompt construction function
    - Implement build_memory_first_prompt() combining agent outputs
    - Include Memory-First priority instructions
    - Add advice provenance requirements to system prompt
    - Format context data for Claude
    - _Requirements: 2.2, 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_
  
  - [ ] 7.2 Create Bedrock invocation function
    - Implement invoke_bedrock() for Claude 3.5 Sonnet
    - Handle API errors and timeouts
    - _Requirements: 11.4_
  
  - [ ] 7.3 Write property test for Memory-First proactive engagement
    - **Property 2: Memory-First Proactive Engagement**
    - **Validates: Requirements 2.2**
    - Test that for any farmer with unresolved issues, the advice includes follow-up questions about those issues
  
  - [ ] 7.4 Write property test for advice provenance inclusion
    - **Property 38: Advice Provenance Inclusion**
    - **Validates: Requirements 13.1, 13.2, 13.3, 13.4, 13.5, 13.6**
    - Test that for any generated advice, the text includes at least one provenance statement

- [ ] 8. Implement Chain-of-Verification safety module
  - [ ] 8.1 Create safety validation function
    - Implement validate_safety() for weather conflict detection
    - Check for pesticide/spray mentions in advice
    - Validate against rain forecast (>40% probability)
    - Check extreme weather conditions (temp, wind)
    - _Requirements: 4.1, 4.2, 4.4, 4.6_
  
  - [ ] 8.2 Create alternative recommendation generator
    - Implement generate_alternative_recommendation()
    - Calculate safe timing windows
    - Provide specific hour recommendations
    - _Requirements: 4.5, 4.7_
  
  - [ ] 8.3 Write property test for Chain-of-Verification execution order
    - **Property 8: Chain-of-Verification Execution Order**
    - **Validates: Requirements 4.6, 11.5**
    - Test that for any advice, safety validation occurs before speech synthesis
  
  - [ ] 8.4 Write property test for rain forecast safety blocking
    - **Property 9: Rain Forecast Safety Blocking**
    - **Validates: Requirements 4.2, 4.7**
    - Test that advice mentioning spraying is blocked when rain probability >40%
  
  - [ ] 8.5 Write property test for extreme weather warnings
    - **Property 10: Extreme Weather Warnings**
    - **Validates: Requirements 4.4**
    - Test that pesticide advice includes warnings during extreme conditions

- [ ] 9. Checkpoint - Ensure safety validation works correctly
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Implement low-bandwidth mode module
  - [ ] 10.1 Create bandwidth detection function
    - Implement detect_bandwidth_mode() checking metadata and file size
    - Activate low-bandwidth mode below 100 kbps
    - _Requirements: 14.1_
  
  - [ ] 10.2 Create audio compression function
    - Implement compress_audio_to_64kbps() using ffmpeg
    - Reduce sample rate and bitrate for 2G networks
    - _Requirements: 14.2_
  
  - [ ] 10.3 Create USSD/SMS fallback generator
    - Implement generate_ussd_fallback() for timeout scenarios
    - Create simplify_advice_for_text() using Claude
    - Break advice into SMS-sized chunks (160 chars)
    - _Requirements: 14.4, 14.5_
  
  - [ ] 10.4 Write property test for low-bandwidth mode activation
    - **Property 39: Low-Bandwidth Mode Activation**
    - **Validates: Requirements 14.1, 14.2, 14.3**
    - Test that sessions with <100 kbps activate compressed audio processing
  
  - [ ] 10.5 Write property test for USSD fallback trigger
    - **Property 40: USSD Fallback Trigger**
    - **Validates: Requirements 14.4, 14.5**
    - Test that voice loops exceeding 15 seconds offer USSD/SMS fallback

- [ ] 11. Implement Lambda orchestrator
  - [ ] 11.1 Create main Lambda handler function
    - Implement lambda_handler() as entry point
    - Parse S3 upload events
    - Coordinate all modules in correct sequence
    - Handle bandwidth mode detection
    - Implement error handling and logging
    - _Requirements: 11.1, 11.2, 11.4, 11.5, 11.6, 11.7_
  
  - [ ] 11.2 Configure S3 event trigger
    - Set up S3 bucket notification to trigger Lambda
    - Configure event filtering for audio uploads
    - _Requirements: 11.1_
  
  - [ ] 11.3 Write property test for S3 event Lambda trigger
    - **Property 33: S3 Event Lambda Trigger**
    - **Validates: Requirements 11.1**
    - Test that any audio upload triggers orchestrator within 1 second
  
  - [ ] 11.4 Write property test for voice loop completion
    - **Property 1: Voice Loop Completion**
    - **Validates: Requirements 1.1, 1.2, 1.3**
    - Test that for any valid audio input, the system completes the full cycle and returns audio response

- [ ] 12. Implement error handling and resilience
  - [ ] 12.1 Create retry logic with exponential backoff
    - Implement retry_with_backoff() for external API calls
    - Configure 3 attempts with 1s, 2s, 4s delays
    - _Requirements: 9.5_
  
  - [ ] 12.2 Create graceful degradation handlers
    - Implement fallback to general advice when APIs fail
    - Add disclaimers for missing context
    - _Requirements: 3.5, 9.5, 12.5_
  
  - [ ] 12.3 Create error response templates
    - Implement natural language error messages for each error type
    - Support all 8 languages
    - _Requirements: 1.5, 9.1_
  
  - [ ] 12.4 Write property test for graceful API failure handling
    - **Property 25: Graceful API Failure Handling**
    - **Validates: Requirements 3.5, 9.5, 12.5**
    - Test that API failures trigger retries and fallback to general advice with disclaimers

- [ ] 13. Implement farmer identity and personalization
  - [ ] 13.1 Create AgriStack ID validation
    - Implement validate_agristack_id() against UFSI
    - Handle OAuth token management
    - _Requirements: 5.2, 8.4_
  
  - [ ] 13.2 Create FarmerID management
    - Implement FarmerID generation for non-AgriStack users
    - Map AgriStack IDs to FarmerIDs
    - _Requirements: 5.3, 5.5_
  
  - [ ] 13.3 Create personalized greeting logic
    - Extract farmer name and primary crop from memory
    - Generate personalized greetings for returning farmers
    - _Requirements: 5.4_
  
  - [ ] 13.4 Write property test for personalized greeting
    - **Property 14: Personalized Greeting for Returning Farmers**
    - **Validates: Requirements 5.4**
    - Test that returning farmers receive greetings with their name and crop reference

- [ ] 14. Checkpoint - Ensure end-to-end orchestration works
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. Implement Flutter client app (basic version)
  - [ ] 15.1 Create Pulse Button UI component
    - Implement single-button interface with visual feedback
    - Handle press, hold, and interrupt gestures
    - _Requirements: 6.1, 6.2, 6.3_
  
  - [ ] 15.2 Create audio recording module
    - Implement audio capture with quality settings
    - Support bandwidth-aware compression
    - _Requirements: 1.3, 14.2_
  
  - [ ] 15.3 Create GPS location collector
    - Implement location services integration
    - Handle permission requests
    - _Requirements: 3.1_
  
  - [ ] 15.4 Create S3 upload module
    - Implement audio upload with metadata (FarmerID, GPS, language)
    - Handle upload failures and retries
    - _Requirements: 1.3, 11.1_
  
  - [ ] 15.5 Create audio playback module
    - Implement response audio download and playback
    - Support interrupt capability
    - _Requirements: 1.2, 6.3_
  
  - [ ] 15.6 Create offline cache module
    - Implement local storage for 10 most recent Q&A pairs
    - Handle sync when connectivity restored
    - _Requirements: 9.2, 9.3, 9.4_
  
  - [ ] 15.7 Create state transition audio cues
    - Implement audio feedback for listening, processing, speaking states
    - _Requirements: 6.4_
  
  - [ ] 15.8 Write integration tests for client-server communication
    - Test complete voice loop from button press to audio playback
    - Test offline mode and sync behavior
    - _Requirements: 1.3, 9.2, 9.4_

- [ ] 16. Implement additional property tests for comprehensive coverage
  - [ ] 16.1 Write property test for memory persistence round-trip
    - **Property 3: Memory Persistence Round-Trip**
    - **Validates: Requirements 2.1, 2.3, 11.7**
  
  - [ ] 16.2 Write property test for time-based proactive follow-up
    - **Property 4: Time-Based Proactive Follow-Up**
    - **Validates: Requirements 2.4**
  
  - [ ] 16.3 Write property test for weather data freshness
    - **Property 6: Weather Data Freshness**
    - **Validates: Requirements 3.3**
  
  - [ ] 16.4 Write property test for contextual grounding in advice
    - **Property 7: Contextual Grounding in Advice**
    - **Validates: Requirements 3.4**
  
  - [ ] 16.5 Write property test for AgriStack ID validation
    - **Property 12: AgriStack ID Validation**
    - **Validates: Requirements 5.2**
  
  - [ ] 16.6 Write property test for source citation in advice
    - **Property 30: Source Citation in Advice**
    - **Validates: Requirements 10.2**
  
  - [ ] 16.7 Write property test for crop growth stage specificity
    - **Property 31: Crop Growth Stage Specificity**
    - **Validates: Requirements 10.3**

- [ ] 17. Integration testing and deployment
  - [ ] 17.1 Create integration test suite
    - Test complete Guru Cycle with real AWS services
    - Test all 8 supported languages end-to-end
    - Test error scenarios and fallback behaviors
    - _Requirements: All_
  
  - [ ] 17.2 Deploy to AWS staging environment
    - Configure Lambda functions with appropriate memory and timeout
    - Set up CloudWatch logging and monitoring
    - Configure API Gateway if needed for client communication
    - _Requirements: 8.1, 8.2, 8.3_
  
  - [ ] 17.3 Performance testing and optimization
    - Measure voice loop latency (target: <6 seconds)
    - Optimize parallel API calls
    - Test under various network conditions
    - _Requirements: 1.4_
  
  - [ ] 17.4 Create deployment documentation
    - Document environment variables and configuration
    - Create setup guide for AgriStack, OpenWeather, Bhashini APIs
    - Document testing procedures

- [ ] 18. Final checkpoint - Complete system validation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- The multi-agent approach (Weather Analytics + ICAR Knowledge) improves accuracy over single-agent systems
- Chain-of-Verification provides hidden safety interlock before synthesis
- Low-bandwidth mode ensures accessibility for farmers on 2G networks
- Advice provenance builds trust through transparent reasoning
