"""
Preservation Property Tests for Tamil Language Response Fix

These tests MUST PASS on unfixed code to establish baseline behavior.
They ensure the fix doesn't break existing functionality.

Property 2: Preservation - Default Language Behavior
For any S3 event where audio is uploaded WITHOUT Tamil language metadata,
the fixed function SHALL produce exactly the same behavior as the original function.
"""

import pytest
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings, example
from src.lambda_handler import _extract_metadata_from_key
from src.config import Config


# Strategy for generating S3 audio keys
@st.composite
def audio_keys(draw):
    """Generate S3 audio keys"""
    farmer_id = draw(st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
    session_id = f"SESSION_{draw(st.integers(min_value=1000000000000, max_value=9999999999999))}"
    timestamp = draw(st.integers(min_value=1000000000000, max_value=9999999999999))
    request_id = draw(st.uuids()).hex
    
    return f"{farmer_id}/{session_id}/{timestamp}_{request_id}.wav"


class TestLanguagePreservation:
    """
    Preservation Property Tests
    
    These tests MUST PASS on unfixed code to establish baseline behavior.
    """
    
    def test_hindi_metadata_extraction(self):
        """
        Preservation: Hindi language metadata extraction
        
        EXPECTED ON UNFIXED CODE: PASS
        EXPECTED ON FIXED CODE: PASS
        
        Verify that audio with Hindi metadata continues to work correctly.
        """
        audio_key = "FARMER_HINDI/SESSION_123/1234567890_test.wav"
        
        # Mock S3 client to return Hindi language metadata
        with patch('boto3.client') as mock_boto_client:
            mock_s3 = MagicMock()
            mock_boto_client.return_value = mock_s3
            
            # Simulate successful S3 metadata read with Hindi language
            mock_s3.head_object.return_value = {
                'Metadata': {
                    'language': 'hi-IN',
                    'latitude': '28.6139',
                    'longitude': '77.2090'
                }
            }
            
            # Extract metadata
            result = _extract_metadata_from_key(audio_key)
            
            # Assert Hindi language is extracted correctly
            assert result['language'] == 'hi-IN'
            assert result['gps']['latitude'] == 28.6139
            assert result['gps']['longitude'] == 77.2090
    
    def test_no_metadata_defaults_to_hindi(self):
        """
        Preservation: Default to Hindi when no language metadata exists
        
        EXPECTED ON UNFIXED CODE: PASS
        EXPECTED ON FIXED CODE: PASS
        
        Verify that audio without language metadata defaults to Hindi.
        """
        audio_key = "FARMER_DEFAULT/SESSION_123/1234567890_test.wav"
        
        # Mock S3 client to return metadata without language
        with patch('boto3.client') as mock_boto_client:
            mock_s3 = MagicMock()
            mock_boto_client.return_value = mock_s3
            
            # Simulate S3 metadata read without language field
            mock_s3.head_object.return_value = {
                'Metadata': {
                    'latitude': '28.6139',
                    'longitude': '77.2090'
                }
            }
            
            # Extract metadata
            result = _extract_metadata_from_key(audio_key)
            
            # Assert default Hindi language is used
            assert result['language'] == 'hi-IN'
    
    @pytest.mark.parametrize('language_code,language_name', [
        ('te-IN', 'Telugu'),
        ('kn-IN', 'Kannada'),
        ('mr-IN', 'Marathi'),
        ('bn-IN', 'Bengali'),
        ('gu-IN', 'Gujarati'),
        ('pa-IN', 'Punjabi'),
        ('ml-IN', 'Malayalam'),
        ('or-IN', 'Odia'),
    ])
    def test_other_languages_extraction(self, language_code, language_name):
        """
        Preservation: Other supported languages extraction
        
        EXPECTED ON UNFIXED CODE: PASS
        EXPECTED ON FIXED CODE: PASS
        
        Verify that audio with other language metadata continues to work correctly.
        """
        audio_key = f"FARMER_{language_name.upper()}/SESSION_123/1234567890_test.wav"
        
        # Mock S3 client to return specified language metadata
        with patch('boto3.client') as mock_boto_client:
            mock_s3 = MagicMock()
            mock_boto_client.return_value = mock_s3
            
            # Simulate successful S3 metadata read with specified language
            mock_s3.head_object.return_value = {
                'Metadata': {
                    'language': language_code,
                    'latitude': '15.0',
                    'longitude': '75.0'
                }
            }
            
            # Extract metadata
            result = _extract_metadata_from_key(audio_key)
            
            # Assert language is extracted correctly
            assert result['language'] == language_code, \
                f"Expected '{language_code}' for {language_name}, but got '{result['language']}'"
    
    def test_gps_coordinates_extraction(self):
        """
        Preservation: GPS coordinates extraction
        
        EXPECTED ON UNFIXED CODE: PASS
        EXPECTED ON FIXED CODE: PASS
        
        Verify that GPS coordinates extraction remains unchanged.
        """
        audio_key = "FARMER_GPS/SESSION_123/1234567890_test.wav"
        
        # Mock S3 client to return GPS metadata
        with patch('boto3.client') as mock_boto_client:
            mock_s3 = MagicMock()
            mock_boto_client.return_value = mock_s3
            
            # Simulate S3 metadata read with GPS coordinates
            mock_s3.head_object.return_value = {
                'Metadata': {
                    'language': 'hi-IN',
                    'latitude': '12.9716',
                    'longitude': '77.5946'
                }
            }
            
            # Extract metadata
            result = _extract_metadata_from_key(audio_key)
            
            # Assert GPS coordinates are extracted correctly
            assert 'gps' in result
            assert result['gps']['latitude'] == 12.9716
            assert result['gps']['longitude'] == 77.5946
    
    def test_agristack_id_extraction(self):
        """
        Preservation: AgriStack ID extraction
        
        EXPECTED ON UNFIXED CODE: PASS
        EXPECTED ON FIXED CODE: PASS
        
        Verify that AgriStack ID extraction remains unchanged.
        """
        audio_key = "FARMER_AGRISTACK/SESSION_123/1234567890_test.wav"
        
        # Mock S3 client to return AgriStack ID metadata
        with patch('boto3.client') as mock_boto_client:
            mock_s3 = MagicMock()
            mock_boto_client.return_value = mock_s3
            
            # Simulate S3 metadata read with AgriStack ID
            mock_s3.head_object.return_value = {
                'Metadata': {
                    'language': 'hi-IN',
                    'latitude': '28.6139',
                    'longitude': '77.2090',
                    'agristackid': 'AGRI_12345'
                }
            }
            
            # Extract metadata
            result = _extract_metadata_from_key(audio_key)
            
            # Assert AgriStack ID is extracted correctly
            assert result['agristack_id'] == 'AGRI_12345'
    
    @given(audio_key=audio_keys())
    @settings(max_examples=20, deadline=None)
    def test_default_language_property(self, audio_key):
        """
        Preservation Property: Default language for missing metadata
        
        For ALL S3 audio keys without language metadata,
        the system SHALL default to 'hi-IN'.
        
        EXPECTED ON UNFIXED CODE: PASS
        EXPECTED ON FIXED CODE: PASS
        """
        # Mock S3 client to return metadata without language
        with patch('boto3.client') as mock_boto_client:
            mock_s3 = MagicMock()
            mock_boto_client.return_value = mock_s3
            
            # Simulate S3 metadata read without language field
            mock_s3.head_object.return_value = {
                'Metadata': {
                    'latitude': '28.6139',
                    'longitude': '77.2090'
                }
            }
            
            # Extract metadata
            result = _extract_metadata_from_key(audio_key)
            
            # Property: For all missing language metadata, default to 'hi-IN'
            assert result['language'] == 'hi-IN', \
                f"Property violation: Expected 'hi-IN' default for missing metadata, but got '{result['language']}'"
    
    @given(audio_key=audio_keys())
    @settings(max_examples=10, deadline=None)
    def test_s3_read_failure_defaults_to_hindi(self, audio_key):
        """
        Preservation Property: S3 read failure defaults to Hindi
        
        For ALL S3 audio keys where S3 metadata read fails,
        the system SHALL default to 'hi-IN'.
        
        EXPECTED ON UNFIXED CODE: PASS
        EXPECTED ON FIXED CODE: PASS
        
        NOTE: This is the current behavior that we want to preserve
        for non-Tamil metadata cases.
        """
        # Mock S3 client to throw exception during metadata read
        with patch('boto3.client') as mock_boto_client:
            mock_s3 = MagicMock()
            mock_boto_client.return_value = mock_s3
            
            # Simulate S3 read exception
            mock_s3.head_object.side_effect = Exception("S3 read failed")
            
            # Extract metadata
            result = _extract_metadata_from_key(audio_key)
            
            # Property: For all S3 read failures, default to 'hi-IN'
            assert result['language'] == 'hi-IN', \
                f"Property violation: Expected 'hi-IN' default for S3 read failure, but got '{result['language']}'"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
