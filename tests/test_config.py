"""Tests for configuration module"""

import pytest
import os
from src.config import Config


class TestConfig:
    """Test configuration management"""
    
    def test_config_has_required_attributes(self):
        """Test that Config class has all required attributes"""
        assert hasattr(Config, 'AWS_REGION')
        assert hasattr(Config, 'AUDIO_INPUT_BUCKET')
        assert hasattr(Config, 'AUDIO_OUTPUT_BUCKET')
        assert hasattr(Config, 'OPENWEATHER_API_KEY')
        assert hasattr(Config, 'BHASHINI_API_KEY')
        assert hasattr(Config, 'UFSI_ENDPOINT')
        assert hasattr(Config, 'CLAUDE_MODEL_ARN')
    
    def test_default_region_is_mumbai(self):
        """Test that default AWS region is Mumbai (ap-south-1)"""
        # If not set in environment, should default to Mumbai
        if not os.getenv('AWS_REGION'):
            assert Config.AWS_REGION == 'ap-south-1'
    
    def test_default_bucket_names(self):
        """Test default S3 bucket names"""
        if not os.getenv('AUDIO_INPUT_BUCKET'):
            assert Config.AUDIO_INPUT_BUCKET == 'vaniverse-audio-input'
        if not os.getenv('AUDIO_OUTPUT_BUCKET'):
            assert Config.AUDIO_OUTPUT_BUCKET == 'vaniverse-audio-output'
    
    def test_use_mock_ufsi_default(self):
        """Test that mock UFSI is enabled by default"""
        if not os.getenv('USE_MOCK_UFSI'):
            assert Config.USE_MOCK_UFSI is True
    
    def test_low_bandwidth_threshold(self):
        """Test low bandwidth threshold configuration"""
        assert Config.LOW_BANDWIDTH_THRESHOLD_KBPS == 100
    
    def test_voice_loop_timeout(self):
        """Test voice loop timeout configuration"""
        assert Config.VOICE_LOOP_TIMEOUT_SECONDS == 15
