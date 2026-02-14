# Requirements Document: VaniVerse - Proactive AI Guru for Indian Farmers

## Introduction

VaniVerse is a voice-first, proactive AI assistant designed to bridge the digital divide for small-scale farmers in India. The system synthesizes Government Digital Public Infrastructure (AgriStack), real-time environmental data, and conversational memory to provide hyper-local, expert-level spoken agricultural advice. Unlike reactive chatbots, VaniVerse proactively engages farmers by checking on previous crop issues and providing contextually-grounded recommendations based on live weather conditions and land records.

### System Architecture

VaniVerse is built on a serverless AWS architecture using an "Orchestrator" pattern:

- **Client Layer**: Flutter mobile application for voice capture, GPS collection, and farmer ID transmission
- **Compute Layer**: AWS Lambda functions serving as the orchestration brain
- **Intelligence Layer**: 
  - AWS Bedrock (Claude 3.5 Sonnet) for agricultural reasoning with specialized system prompts
  - AWS Transcribe for multi-dialect speech recognition
  - Amazon Polly for regional voice synthesis
- **Storage Layer**:
  - Amazon DynamoDB for persistent conversation memory (partitioned by FarmerID)
  - Amazon S3 for audio file staging and advice history logs

### The "Guru Cycle" Data Flow

1. **Request**: Farmer speaks; Flutter app sends Audio + GPS + FarmerID to S3
2. **Context Retrieval**: Lambda orchestrator fetches:
   - Current weather (temperature, humidity, precipitation) from OpenWeather API
   - Land records (size, soil type, current crop) from UFSI
   - Last interaction summary from DynamoDB
3. **Agentic Synthesis**: Claude 3.5 Sonnet performs stateful evaluation using Memory-First Prompting
4. **Execution**: Advice is converted to speech via Polly and delivered to the app

### Memory-First Prompting Strategy

The system uses a specialized prompting approach that forces the LLM to act as a concerned mentor:
- **Priority 1**: Inquire about unresolved past issues from conversation memory
- **Priority 2**: Cross-reference new requests with weather safety conditions
- **Priority 3**: Deliver the final answer with contextual grounding

## Glossary

- **VaniVerse_System**: The complete voice-first AI assistant platform built on AWS serverless architecture
- **Orchestrator**: AWS Lambda function that coordinates all system components and data flows
- **Client_App**: Flutter mobile application for voice capture, GPS collection, and farmer ID transmission
- **Speech_Processor**: AWS Transcribe for speech-to-text and Amazon Polly for text-to-speech conversion
- **Context_Engine**: Lambda component that retrieves conversation history from DynamoDB, weather data from OpenWeather API, and land records from UFSI
- **Advisory_Generator**: AWS Bedrock (Claude 3.5 Sonnet) with specialized system prompts for agricultural reasoning
- **Safety_Validator**: Logic within the Orchestrator that checks environmental conditions before approving farmer actions
- **AgriStack**: India's Digital Public Infrastructure for agriculture, providing farmer identity and land records via UFSI (Unified Farmer Service Interface)
- **UFSI**: Unified Farmer Service Interface - standardized API protocol for accessing AgriStack data
- **Conversation_Memory**: Amazon DynamoDB table storing farmer interactions with FarmerID as partition key
- **Audio_Storage**: Amazon S3 bucket for staging audio files and storing advice history logs
- **Regional_Dialect**: Indian language variants including Hindi, Tamil, Telugu, Kannada, Marathi, Bengali, and others
- **Pulse_Button**: Single-button interface in the Flutter app for initiating voice interactions
- **Voice_Loop**: Complete cycle from farmer speech input to AI voice response (target: under 6 seconds)
- **Memory_First_Prompting**: Prompting strategy that prioritizes checking unresolved past issues before answering new queries
- **Guru_Cycle**: Complete data flow from farmer request through context retrieval, AI synthesis, and voice response
- **FarmerID**: Unique identifier for each farmer, linked to AgriStack ID when available

## Requirements

### Requirement 1: Voice Interface

**User Story:** As a farmer with limited digital literacy, I want to interact with the system using my voice in my regional dialect, so that I can access farming advice without typing or complex navigation.

#### Acceptance Criteria

1. WHEN a farmer speaks in a Regional_Dialect, THE Speech_Processor SHALL convert the audio to text using AWS Transcribe with dialect-specific models
2. WHEN the Advisory_Generator produces text advice, THE Speech_Processor SHALL convert it to natural speech using Amazon Polly neural voices
3. WHEN a farmer presses the Pulse_Button in the Client_App, THE VaniVerse_System SHALL upload audio to Audio_Storage and trigger the Orchestrator
4. THE VaniVerse_System SHALL complete the entire Voice_Loop within 6 seconds from speech input to audio response delivery
5. WHEN speech recognition fails or produces low-confidence results, THE VaniVerse_System SHALL ask the farmer to repeat their question in simpler terms

### Requirement 2: Proactive Engagement

**User Story:** As a farmer managing crops over time, I want the system to remember my previous issues and follow up on them, so that I receive continuous support rather than isolated answers.

#### Acceptance Criteria

1. WHEN a farmer asks a new question, THE Context_Engine SHALL retrieve the last 5 interactions from Conversation_Memory in DynamoDB using the FarmerID
2. WHEN previous interactions mention unresolved crop issues, THE Advisory_Generator SHALL use Memory_First_Prompting to ask follow-up questions about those issues before answering the new query
3. WHEN a farmer reports a crop problem, THE Orchestrator SHALL store the issue details with timestamp and crop identifier in DynamoDB
4. WHEN 7 days have passed since a reported crop issue, THE VaniVerse_System SHALL proactively ask about the issue status during the next interaction
5. THE VaniVerse_System SHALL associate all Conversation_Memory entries with the FarmerID as the DynamoDB partition key

### Requirement 3: Contextual Grounding

**User Story:** As a farmer seeking advice, I want recommendations based on my actual land conditions and current weather, so that the advice is relevant and actionable for my specific situation.

#### Acceptance Criteria

1. WHEN generating advice, THE Context_Engine SHALL fetch current weather data from OpenWeather API using GPS coordinates from the Client_App
2. WHEN a FarmerID is linked to AgriStack, THE Context_Engine SHALL retrieve land records including soil type, land area, and crop history from UFSI
3. WHEN weather data is older than 30 minutes, THE Context_Engine SHALL refresh the data before the Advisory_Generator produces advice
4. THE Advisory_Generator SHALL reference specific weather conditions and land characteristics in its spoken advice using Claude 3.5 Sonnet's reasoning
5. WHEN external data sources are unavailable, THE VaniVerse_System SHALL inform the farmer and provide general advice with appropriate disclaimers

### Requirement 4: Safety Validation for Agricultural Actions

**User Story:** As a farmer planning to spray pesticides or perform weather-sensitive operations, I want the system to warn me about adverse conditions, so that I avoid wasting resources or harming my crops.

#### Acceptance Criteria

1. WHEN a farmer requests advice about spraying pesticides, THE Safety_Validator SHALL check weather forecasts for the next 6 hours
2. IF rain is predicted within 6 hours with probability above 40%, THEN THE Safety_Validator SHALL warn against spraying and explain the risk
3. WHEN a farmer asks about irrigation timing, THE Safety_Validator SHALL check temperature forecasts and advise optimal timing to minimize water loss
4. WHEN extreme weather conditions are detected (temperature above 40°C or below 5°C, wind speed above 20 km/h), THE Safety_Validator SHALL warn against pesticide application
5. THE Safety_Validator SHALL provide alternative timing recommendations when current conditions are unsuitable

### Requirement 5: Farmer Identity and Personalization

**User Story:** As a farmer with an AgriStack ID, I want the system to recognize me and remember my farm details, so that I don't have to repeat basic information in every interaction.

#### Acceptance Criteria

1. WHEN a farmer first uses VaniVerse, THE Client_App SHALL request their AgriStack ID via voice input
2. WHEN an AgriStack ID is provided, THE Orchestrator SHALL validate it against the UFSI API
3. THE Orchestrator SHALL store the mapping between FarmerID and AgriStack ID in DynamoDB for subsequent interactions
4. WHEN a returning farmer initiates a session, THE VaniVerse_System SHALL greet them by name and reference their primary crop from stored context
5. WHERE a farmer does not have an AgriStack ID, THE VaniVerse_System SHALL create a FarmerID and provide advice using GPS-based context only

### Requirement 6: Accessibility and Simple Navigation

**User Story:** As a farmer with limited smartphone experience, I want to use the system with minimal button presses, so that I can focus on farming rather than learning complex interfaces.

#### Acceptance Criteria

1. THE Client_App SHALL provide a single Pulse_Button as the primary interaction mechanism
2. WHEN the Pulse_Button is pressed once, THE Client_App SHALL start recording audio and display visual feedback
3. WHEN the Pulse_Button is pressed during system speech playback, THE Client_App SHALL pause playback and allow the farmer to interrupt
4. THE Client_App SHALL provide audio cues for all state changes (listening, processing, speaking)
5. WHEN no voice input is detected for 5 seconds after activation, THE VaniVerse_System SHALL prompt the farmer with an example question via Polly

### Requirement 7: Multi-Language Support

**User Story:** As a farmer speaking a regional Indian language, I want the system to understand and respond in my language, so that I can communicate naturally without language barriers.

#### Acceptance Criteria

1. THE VaniVerse_System SHALL support Hindi, Tamil, Telugu, Kannada, Marathi, Bengali, Gujarati, and Punjabi Regional_Dialects
2. WHEN a farmer first uses the system, THE VaniVerse_System SHALL detect the spoken language automatically
3. WHEN language detection confidence is below 70%, THE VaniVerse_System SHALL ask the farmer to confirm their preferred language
4. THE Speech_Processor SHALL use language-specific AWS Transcribe models for each supported Regional_Dialect
5. THE Speech_Processor SHALL use language-appropriate AWS Polly neural voices for natural-sounding responses

### Requirement 8: Data Sovereignty and Privacy

**User Story:** As a farmer in India, I want my personal and farm data to be stored securely within India, so that my information is protected according to Indian data protection laws.

#### Acceptance Criteria

1. THE VaniVerse_System SHALL store all Conversation_Memory and farmer data in AWS services configured for the Asia Pacific (Mumbai) region
2. THE VaniVerse_System SHALL encrypt all farmer data at rest in DynamoDB and S3 using AWS KMS with customer-managed keys
3. THE VaniVerse_System SHALL encrypt all data in transit using TLS 1.3 for API communications
4. WHEN accessing AgriStack APIs via UFSI, THE Orchestrator SHALL use OAuth 2.0 authentication with farmer consent following UFSI standards
5. THE VaniVerse_System SHALL provide farmers the ability to delete their Conversation_Memory from DynamoDB via voice command

### Requirement 9: Offline Capability and Resilience

**User Story:** As a farmer in an area with intermittent connectivity, I want the system to handle network issues gracefully, so that I can still receive basic advice when connectivity is poor.

#### Acceptance Criteria

1. WHEN network connectivity is lost during a session, THE Client_App SHALL inform the farmer via audio message
2. THE Client_App SHALL cache the last 10 common farming questions and answers locally for offline access
3. WHEN operating in offline mode, THE Client_App SHALL clearly state that advice is not based on current weather data
4. WHEN connectivity is restored, THE Client_App SHALL upload any cached audio files to Audio_Storage and sync interactions to DynamoDB
5. THE Orchestrator SHALL retry failed API calls to OpenWeather and UFSI up to 3 times with exponential backoff before returning cached or general advice

### Requirement 10: Expert Knowledge Integration

**User Story:** As a farmer seeking scientific advice, I want recommendations based on agricultural research and best practices, so that I can improve my crop yields using proven methods.

#### Acceptance Criteria

1. THE Advisory_Generator SHALL use Claude 3.5 Sonnet with a specialized system prompt containing agricultural best practices from ICAR (Indian Council of Agricultural Research)
2. WHEN generating advice, THE Advisory_Generator SHALL cite the source of recommendations in natural language (e.g., "According to ICAR guidelines...")
3. THE Advisory_Generator SHALL provide crop-specific advice based on growth stages stored in Conversation_Memory
4. WHEN multiple valid approaches exist, THE Advisory_Generator SHALL present options and explain trade-offs using Claude's reasoning capabilities
5. THE VaniVerse_System SHALL update the ICAR knowledge base in the system prompt monthly with new agricultural research and guidelines

### Requirement 11: Lambda Orchestration and Event Flow

**User Story:** As a system architect, I want the Lambda orchestrator to efficiently coordinate all components and handle the complete Guru Cycle, so that the system delivers responses within the 6-second latency target.

#### Acceptance Criteria

1. WHEN audio is uploaded to Audio_Storage, THE S3 event SHALL trigger the Orchestrator Lambda function
2. THE Orchestrator SHALL execute context retrieval operations in parallel (weather API, UFSI API, DynamoDB query) to minimize latency
3. WHEN all context is retrieved, THE Orchestrator SHALL construct the Memory_First_Prompting payload and invoke AWS Bedrock with Claude 3.5 Sonnet
4. WHEN Claude generates advice text, THE Orchestrator SHALL invoke Amazon Polly to synthesize speech and store the audio file in Audio_Storage
5. THE Orchestrator SHALL log the complete interaction (input audio reference, context used, advice generated, output audio reference) to DynamoDB for audit and improvement

### Requirement 12: UFSI Integration and Mock Layer

**User Story:** As a developer, I want to integrate with AgriStack using UFSI standards, so that the system can access farmer land records and identity information following government protocols.

#### Acceptance Criteria

1. THE Context_Engine SHALL implement UFSI API client following the Unified Farmer Service Interface specification
2. WHEN AgriStack production APIs are unavailable, THE Context_Engine SHALL use a mock UFSI layer with sample farmer data for development and testing
3. THE UFSI client SHALL include a consent manager placeholder for Aadhaar-based data sharing authorization
4. WHEN calling UFSI APIs, THE Context_Engine SHALL include required headers (API key, consent token, request ID) per UFSI standards
5. THE Context_Engine SHALL handle UFSI error responses gracefully and fall back to GPS-based context when land records are unavailable
