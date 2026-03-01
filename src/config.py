"""Configuration management for VaniVerse"""

import os

# Try to load .env file for local development (not needed in Lambda)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available (e.g., in Lambda), skip it
    pass


class Config:
    """Configuration class for VaniVerse system"""
    
    # AWS Configuration
    AWS_REGION = os.getenv('AWS_REGION', 'ap-south-1')
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    
    # S3 Buckets
    AUDIO_INPUT_BUCKET = os.getenv('AUDIO_INPUT_BUCKET', 'vaniverse-audio-input')
    AUDIO_OUTPUT_BUCKET = os.getenv('AUDIO_OUTPUT_BUCKET', 'vaniverse-audio-output')
    
    # Lambda Configuration
    LAMBDA_FUNCTION_NAME = os.getenv('LAMBDA_FUNCTION_NAME', 'vaniverse-orchestrator')
    LAMBDA_ROLE_ARN = os.getenv('LAMBDA_ROLE_ARN')
    
    # AgentCore Memory
    AGENTCORE_MEMORY_ID = os.getenv('AGENTCORE_MEMORY_ID')
    AGENTCORE_AGENT_ID = os.getenv('AGENTCORE_AGENT_ID')
    AGENTCORE_ALIAS_ID = os.getenv('AGENTCORE_ALIAS_ID')
    AGENTCORE_REGION = os.getenv('AGENTCORE_REGION', AWS_REGION)  # Allow separate region for agent
    
    # LLM Model (Amazon Nova or Claude)
    MODEL_ARN = os.getenv(
        'MODEL_ARN',
        'arn:aws:bedrock:ap-south-1::foundation-model/apac.amazon.nova-lite-v1:0'
    )
    MODEL_ID = os.getenv(
        'MODEL_ID',
        'apac.amazon.nova-lite-v1:0'
    )
    
    # Legacy Claude config (for backward compatibility)
    CLAUDE_MODEL_ARN = os.getenv('CLAUDE_MODEL_ARN', MODEL_ARN)
    CLAUDE_MODEL_ID = os.getenv('CLAUDE_MODEL_ID', MODEL_ID)
    
    # External APIs
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
    BHASHINI_API_KEY = os.getenv('BHASHINI_API_KEY')
    BHASHINI_TTS_ENDPOINT = os.getenv('BHASHINI_TTS_ENDPOINT', 'https://api.bhashini.gov.in/tts')
    BHASHINI_ASR_ENDPOINT = os.getenv('BHASHINI_ASR_ENDPOINT', 'https://api.bhashini.gov.in/asr')
    
    # Google Cloud Speech-to-Text
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    USE_GOOGLE_SPEECH = os.getenv('USE_GOOGLE_SPEECH', 'false').lower() == 'true'
    
    # UFSI (AgriStack)
    UFSI_ENDPOINT = os.getenv('UFSI_ENDPOINT', 'https://ufsi.agristack.gov.in/api/v1')
    UFSI_CLIENT_ID = os.getenv('UFSI_CLIENT_ID')
    UFSI_CLIENT_SECRET = os.getenv('UFSI_CLIENT_SECRET')
    USE_MOCK_UFSI = os.getenv('USE_MOCK_UFSI', 'true').lower() == 'true'
    
    # Mock Services (for testing without AWS service subscriptions)
    USE_MOCK_TRANSCRIBE = os.getenv('USE_MOCK_TRANSCRIBE', 'false').lower() == 'true'
    USE_MOCK_LLM = os.getenv('USE_MOCK_LLM', 'false').lower() == 'true'
    USE_MOCK_TTS = os.getenv('USE_MOCK_TTS', 'false').lower() == 'true'
    
    # Low-Bandwidth Configuration
    LOW_BANDWIDTH_THRESHOLD_KBPS = int(os.getenv('LOW_BANDWIDTH_THRESHOLD_KBPS', '100'))
    VOICE_LOOP_TIMEOUT_SECONDS = int(os.getenv('VOICE_LOOP_TIMEOUT_SECONDS', '15'))
    
    @classmethod
    def validate(cls):
        """Validate that required configuration is present"""
        required_vars = []
        
        # Check AWS credentials (only if not using IAM role)
        if not cls.AWS_ACCESS_KEY_ID and not os.getenv('AWS_EXECUTION_ENV'):
            required_vars.append('AWS_ACCESS_KEY_ID')
        if not cls.AWS_SECRET_ACCESS_KEY and not os.getenv('AWS_EXECUTION_ENV'):
            required_vars.append('AWS_SECRET_ACCESS_KEY')
        
        # Check external API keys
        if not cls.OPENWEATHER_API_KEY:
            required_vars.append('OPENWEATHER_API_KEY')
        
        if required_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(required_vars)}\n"
                f"Please copy .env.example to .env and fill in the required values."
            )
        
        # Validate AGENTCORE_REGION format if set
        if cls.AGENTCORE_REGION:
            # Basic AWS region format validation (e.g., us-east-1, ap-south-1)
            import re
            region_pattern = r'^[a-z]{2}-[a-z]+-\d+$'
            if not re.match(region_pattern, cls.AGENTCORE_REGION):
                print(f"Warning: AGENTCORE_REGION '{cls.AGENTCORE_REGION}' may not be a valid AWS region format")
        
        # Log warning if cross-region configuration detected
        if cls.AGENTCORE_REGION and cls.AGENTCORE_REGION != cls.AWS_REGION:
            print(f"INFO: Cross-region AgentCore configuration detected:")
            print(f"  Lambda Region: {cls.AWS_REGION}")
            print(f"  Agent Region: {cls.AGENTCORE_REGION}")
            print(f"  Ensure IAM policy allows cross-region invocation")
        
        return True


# Validate configuration on import (only in production)
if os.getenv('VALIDATE_CONFIG', 'false').lower() == 'true':
    Config.validate()
