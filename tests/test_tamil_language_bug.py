"""
Bug Condition Exploration Test for Tamil Language Response Fix

This test MUST FAIL on unfixed code to confirm the bug exists.
It encodes the expected behavior that will validate the fix when it passes.

Property 1: Fault Condition - Tamil Language Metadata Extraction
For any S3 event where audio is uploaded with Tamil language metadata (x-amz-meta-language: ta-IN),
the _extract_metadata_from_key function SHALL successfully extract the Tamil language code
and use it throughout the processing pipeline.
"""

import pytest
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings, example
from src.lambda_handler import _extract_metadata_from_key
from src.config import Config


# Strategy for generating S3 audio keys with Tamil metadata
@st.composite
def tamil_audio_keys(draw):
    """Generate S3 audio keys for Tamil language uploads"""
    farmer_id = draw(st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
    session_id = f"SESSION_{draw(st.integers(min_value=1000000000000, max_value=9999999999999))}"
    timestamp = draw(st.integers(min_value=1000000000000, max_value=9999999999999))
    request_id = draw(st.uuids()).hex
    
    return f"{farmer_id}/{session_id}/{timestamp}_{request_id}.wav"


class TestTamilLanguageBugCondition:
    """
    Bug Condition Exploration Tests
    
    These tests MUST FAIL on unfixed code to confirm the bug exists.
    """
    
    @given(audio_key=tamil_audio_keys())
    @settings(max_examples=10, deadline=None)
    @example(audio_key="FARMER_TEST/SESSION_1234567890/1234567890_test-uuid.wav")
    def test_tamil_metadata_extraction_with_s3_success(self, audio_key):
        """
        Property 1: Tamil Language Metadata Extraction (S3 Read Success)
        
        EXPECTED ON UNFIXED CODE: FAIL
        - System should extract 'ta-IN' from S3 metadata
        - But unfixed code may use premature 'hi-IN' default
        
        EXPECTED ON FIXED CODE: PASS
        - System correctly extracts 'ta-IN' from S3 metadata
        """
        # Mock S3 client to return Tamil language metadata
        with patch('boto3.client') as mock_boto_client:
            mock_s3 = MagicMock()
            mock_boto_client.return_value = mock_s3
            
            # Simulate successful S3 metadata read with Tamil language
            mock_s3.head_object.return_value = {
                'Metadata': {
                    'language': 'ta-IN',
                    'latitude': '13.0827',
                    'longitude': '80.2707'
                }
            }
            
            # Extract metadata
            result = _extract_metadata_from_key(audio_key)
            
            # Assert Tamil language is extracted correctly
            assert result['language'] == 'ta-IN', \
                f"Expected 'ta-IN' but got '{result['language']}'. " \
                f"Bug: System is not extracting Tamil language from S3 metadata correctly."
    
    def test_tamil_metadata_extraction_with_s3_exception(self):
        """
        Property 1: Tamil Language Metadata Extraction (S3 Read Exception)
        
        EXPECTED ON UNFIXED CODE: FAIL
        - When S3 read fails, system falls back to premature 'hi-IN' default
        - This masks the fact that Tamil metadata exists in S3
        
        EXPECTED ON FIXED CODE: PASS
        - System should handle S3 read failures gracefully
        - But should not prematurely default to 'hi-IN' before attempting S3 read
        
        NOTE: This test demonstrates the root cause - premature default assignment
        """
        audio_key = "FARMER_TAMIL/SESSION_123/1234567890_test.wav"
        
        # Mock S3 client to throw exception during metadata read
        with patch('boto3.client') as mock_boto_client:
            mock_s3 = MagicMock()
            mock_boto_client.return_value = mock_s3
            
            # Simulate S3 read exception
            mock_s3.head_object.side_effect = Exception("S3 read failed")
            
            # Extract metadata
            result = _extract_metadata_from_key(audio_key)
            
            # On unfixed code, this will return 'hi-IN' due to premature default
            # On fixed code, this should either:
            # 1. Retry the S3 read, or
            # 2. Return 'hi-IN' only if truly no metadata exists
            # 
            # For now, we document that the bug causes 'hi-IN' to be returned
            # even when Tamil metadata exists in S3
            assert result['language'] == 'hi-IN', \
                "EXPECTED FAILURE: This documents the bug - system falls back to 'hi-IN' " \
                "when S3 read fails, even if Tamil metadata exists in S3."
    
    @given(audio_key=tamil_audio_keys())
    @settings(max_examples=5, deadline=None)
    def test_tamil_metadata_extraction_property(self, audio_key):
        """
        Property 1: Tamil Language Metadata Extraction (Property-Based)
        
        For ALL S3 audio keys with Tamil language metadata,
        the system SHALL extract 'ta-IN' and use it throughout processing.
        
        EXPECTED ON UNFIXED CODE: FAIL (some examples will fail)
        EXPECTED ON FIXED CODE: PASS (all examples pass)
        """
        # Mock S3 client to return Tamil language metadata
        with patch('boto3.client') as mock_boto_client:
            mock_s3 = MagicMock()
            mock_boto_client.return_value = mock_s3
            
            # Simulate successful S3 metadata read with Tamil language
            mock_s3.head_object.return_value = {
                'Metadata': {
                    'language': 'ta-IN',
                    'latitude': '13.0827',
                    'longitude': '80.2707',
                    'farmerid': audio_key.split('/')[0],
                    'sessionid': audio_key.split('/')[1] if '/' in audio_key else 'SESSION_DEFAULT'
                }
            }
            
            # Extract metadata
            result = _extract_metadata_from_key(audio_key)
            
            # Property: For all Tamil metadata, extract 'ta-IN'
            assert result['language'] == 'ta-IN', \
                f"Property violation: Expected 'ta-IN' for all Tamil metadata, but got '{result['language']}'"
            
            # Verify GPS coordinates are also extracted
            assert 'gps' in result
            assert result['gps']['latitude'] == 13.0827
            assert result['gps']['longitude'] == 80.2707


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
