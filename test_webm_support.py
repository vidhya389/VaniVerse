#!/usr/bin/env python3
"""
Test script to verify WebM format support in Google Speech API
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from google.cloud import speech_v1

def test_webm_encoding():
    """Test that WebM format is properly configured"""
    
    print("Testing WebM format configuration...")
    
    # Test 1: Verify OGG_OPUS encoding exists
    try:
        encoding = speech_v1.RecognitionConfig.AudioEncoding.OGG_OPUS
        print(f"✅ OGG_OPUS encoding available: {encoding}")
    except AttributeError as e:
        print(f"❌ OGG_OPUS encoding not found: {e}")
        return False
    
    # Test 2: Create a config with OGG_OPUS
    try:
        config = speech_v1.RecognitionConfig(
            encoding=speech_v1.RecognitionConfig.AudioEncoding.OGG_OPUS,
            sample_rate_hertz=16000,
            language_code='hi-IN',
            enable_automatic_punctuation=True
        )
        print(f"✅ Config created successfully")
        print(f"   - Encoding: {config.encoding}")
        print(f"   - Sample Rate: {config.sample_rate_hertz}")
        print(f"   - Language: {config.language_code}")
    except Exception as e:
        print(f"❌ Failed to create config: {e}")
        return False
    
    print("\n✅ All WebM format tests passed!")
    print("\nNote: This only tests configuration. Actual transcription requires:")
    print("  1. Valid Google Cloud credentials")
    print("  2. A real WebM audio file")
    print("  3. Network connectivity to Google Cloud")
    
    return True

if __name__ == '__main__':
    success = test_webm_encoding()
    sys.exit(0 if success else 1)
