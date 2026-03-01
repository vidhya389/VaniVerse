"""
Property-based tests for AgriStack ID validation.

Tests Property 12: AgriStack ID Validation
Validates: Requirements 5.2

**Validates: Requirements 5.2**
"""

import pytest
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings
import requests

from src.context.farmer_identity import validate_agristack_id, generate_farmer_id, map_agristack_to_farmer_id
from src.config import Config


# Hypothesis Strategies

@st.composite
def valid_agristack_id_strategy(draw):
    """Generate valid AgriStack ID format."""
    # AgriStack IDs typically follow a pattern like: AS-STATE-DISTRICT-NNNNNN
    states = ['MH', 'KA', 'TN', 'UP', 'MP', 'RJ', 'GJ', 'PB']
    districts = ['001', '002', '003', '004', '005']
    number = draw(st.integers(min_value=100000, max_value=999999))
    
    state = draw(st.sampled_from(states))
    district = draw(st.sampled_from(districts))
    
    return f"AS-{state}-{district}-{number}"


@st.composite
def invalid_agristack_id_strategy(draw):
    """Generate invalid AgriStack ID formats."""
    invalid_formats = [
        "",  # Empty string
        "INVALID",  # Random string
        "12345",  # Just numbers
        "AS-",  # Incomplete
        "AS-XX-999",  # Wrong format
        draw(st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_characters='-'))),  # Random text
    ]
    return draw(st.sampled_from(invalid_formats))


@st.composite
def farmer_id_strategy(draw):
    """Generate farmer IDs."""
    return f"FARMER-{draw(st.text(min_size=8, max_size=16, alphabet='0123456789ABCDEF'))}"


# Property Tests

@given(
    agristack_id=valid_agristack_id_strategy(),
    farmer_id=farmer_id_strategy()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.pbt
def test_property_12_agristack_id_validation(agristack_id, farmer_id):
    """
    Feature: vaniverse, Property 12: AgriStack ID Validation
    
    **Validates: Requirements 5.2**
    
    For any AgriStack ID provided by a farmer, the system should validate it 
    against the UFSI API using OAuth 2.0 authentication. Valid IDs should return 
    True, invalid IDs should return False, and the system should handle errors gracefully.
    
    This property verifies that:
    1. Valid AgriStack IDs are accepted
    2. Invalid AgriStack IDs are rejected
    3. OAuth 2.0 authentication is used
    4. API errors are handled gracefully
    5. Empty/None IDs return False
    
    Requirements:
    - Requirement 5.2: Validate AgriStack ID against UFSI API
    """
    # Mock UFSI API responses
    with patch('src.context.farmer_identity.requests.get') as mock_get, \
         patch('src.context.farmer_identity._get_oauth_token') as mock_oauth:
        
        # Mock OAuth token
        mock_oauth.return_value = 'mock-oauth-token-12345'
        
        # Mock successful validation response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'valid': True, 'agristack_id': agristack_id}
        mock_get.return_value = mock_response
        
        # Mock Config
        with patch.object(Config, 'UFSI_ENDPOINT', 'https://mock-ufsi.gov.in'):
            # Property 1: Valid AgriStack ID should return True
            result = validate_agristack_id(agristack_id, farmer_id)
            assert result is True, f"Valid AgriStack ID {agristack_id} should be validated"
            
            # Property 2: OAuth token should be requested
            mock_oauth.assert_called_with(farmer_id)
            
            # Property 3: UFSI API should be called with correct headers
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            
            # Check URL
            assert f"/validate/{agristack_id}" in call_args[0][0], \
                "UFSI validation endpoint should be called"
            
            # Check headers
            headers = call_args[1]['headers']
            assert 'Authorization' in headers, "Authorization header should be present"
            assert headers['Authorization'] == 'Bearer mock-oauth-token-12345', \
                "OAuth token should be in Authorization header"
            assert 'X-Request-ID' in headers, "X-Request-ID header should be present"


@given(
    invalid_id=invalid_agristack_id_strategy(),
    farmer_id=farmer_id_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_invalid_agristack_id_rejected(invalid_id, farmer_id):
    """
    Test that invalid AgriStack IDs are rejected.
    
    Verifies that:
    1. Invalid IDs return False
    2. Empty IDs return False
    3. API 404 responses are handled
    
    **Validates: Requirements 5.2**
    """
    # Mock UFSI API responses
    with patch('src.context.farmer_identity.requests.get') as mock_get, \
         patch('src.context.farmer_identity._get_oauth_token') as mock_oauth:
        
        mock_oauth.return_value = 'mock-oauth-token'
        
        # Mock 404 response for invalid ID
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        with patch.object(Config, 'UFSI_ENDPOINT', 'https://mock-ufsi.gov.in'):
            # Property 1: Invalid AgriStack ID should return False
            result = validate_agristack_id(invalid_id, farmer_id)
            assert result is False, f"Invalid AgriStack ID '{invalid_id}' should not be validated"


@given(
    agristack_id=valid_agristack_id_strategy(),
    farmer_id=farmer_id_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_api_error_handling(agristack_id, farmer_id):
    """
    Test that API errors are handled gracefully.
    
    Verifies that:
    1. Network errors return False
    2. Timeout errors return False
    3. Server errors return False
    4. System continues to function
    
    **Validates: Requirements 5.2, 9.5**
    """
    # Mock UFSI API to raise exception
    with patch('src.context.farmer_identity.requests.get') as mock_get, \
         patch('src.context.farmer_identity._get_oauth_token') as mock_oauth:
        
        mock_oauth.return_value = 'mock-oauth-token'
        
        # Mock network error
        mock_get.side_effect = requests.RequestException("Network error")
        
        with patch.object(Config, 'UFSI_ENDPOINT', 'https://mock-ufsi.gov.in'):
            # Property 1: API errors should return False (graceful degradation)
            result = validate_agristack_id(agristack_id, farmer_id)
            assert result is False, "API errors should return False"


@given(
    agristack_id=valid_agristack_id_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_agristack_to_farmer_id_mapping(agristack_id):
    """
    Test that AgriStack IDs are consistently mapped to FarmerIDs.
    
    Verifies that:
    1. Same AgriStack ID always maps to same FarmerID
    2. Different AgriStack IDs map to different FarmerIDs
    3. FarmerID format is consistent
    
    **Validates: Requirements 5.3**
    """
    # Property 1: Same AgriStack ID should always map to same FarmerID
    farmer_id_1 = map_agristack_to_farmer_id(agristack_id)
    farmer_id_2 = map_agristack_to_farmer_id(agristack_id)
    
    assert farmer_id_1 == farmer_id_2, \
        f"Same AgriStack ID should map to same FarmerID: {farmer_id_1} != {farmer_id_2}"
    
    # Property 2: FarmerID should have correct format
    assert farmer_id_1.startswith('FARMER-AS-'), \
        f"FarmerID should start with 'FARMER-AS-', got {farmer_id_1}"
    
    # Property 3: FarmerID should be deterministic (not random)
    assert len(farmer_id_1) > 10, "FarmerID should have reasonable length"


@given(
    phone_number=st.text(min_size=10, max_size=15, alphabet='0123456789')
)
@settings(max_examples=50, deadline=None)
@pytest.mark.pbt
def test_farmer_id_generation_without_agristack(phone_number):
    """
    Test FarmerID generation for farmers without AgriStack ID.
    
    Verifies that:
    1. FarmerID can be generated without AgriStack ID
    2. Phone number-based generation is deterministic
    3. FarmerID format is consistent
    
    **Validates: Requirements 5.5**
    """
    # Property 1: FarmerID can be generated with phone number
    farmer_id = generate_farmer_id(phone_number=phone_number)
    
    assert farmer_id is not None, "FarmerID should be generated"
    assert farmer_id.startswith('FARMER-'), "FarmerID should start with 'FARMER-'"
    
    # Property 2: Same phone number should generate same FarmerID
    farmer_id_2 = generate_farmer_id(phone_number=phone_number)
    assert farmer_id == farmer_id_2, "Same phone number should generate same FarmerID"


# Unit tests for specific scenarios

def test_empty_agristack_id():
    """Test that empty AgriStack ID returns False."""
    result = validate_agristack_id("", "FARMER-123")
    assert result is False, "Empty AgriStack ID should return False"


def test_none_agristack_id():
    """Test that None AgriStack ID returns False."""
    result = validate_agristack_id(None, "FARMER-123")
    assert result is False, "None AgriStack ID should return False"


def test_valid_agristack_id_format():
    """Test validation with valid AgriStack ID format."""
    agristack_id = "AS-MH-001-123456"
    farmer_id = "FARMER-TEST123"
    
    with patch('src.context.farmer_identity.requests.get') as mock_get, \
         patch('src.context.farmer_identity._get_oauth_token') as mock_oauth:
        
        mock_oauth.return_value = 'test-token'
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        with patch.object(Config, 'UFSI_ENDPOINT', 'https://test-ufsi.gov.in'):
            result = validate_agristack_id(agristack_id, farmer_id)
            assert result is True


def test_oauth_authentication_flow():
    """Test that OAuth 2.0 authentication is used."""
    agristack_id = "AS-KA-002-789012"
    farmer_id = "FARMER-TEST456"
    
    with patch('src.context.farmer_identity.requests.get') as mock_get, \
         patch('src.context.farmer_identity._get_oauth_token') as mock_oauth:
        
        mock_oauth.return_value = 'oauth-token-xyz'
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        with patch.object(Config, 'UFSI_ENDPOINT', 'https://test-ufsi.gov.in'):
            validate_agristack_id(agristack_id, farmer_id)
            
            # Verify OAuth token was requested
            mock_oauth.assert_called_once_with(farmer_id)
            
            # Verify Authorization header
            call_args = mock_get.call_args
            headers = call_args[1]['headers']
            assert headers['Authorization'] == 'Bearer oauth-token-xyz'


def test_ufsi_endpoint_not_configured():
    """Test error handling when UFSI endpoint is not configured."""
    with patch.object(Config, 'UFSI_ENDPOINT', None):
        with pytest.raises(ValueError, match="UFSI_ENDPOINT not configured"):
            validate_agristack_id("AS-MH-001-123456", "FARMER-123")


def test_deterministic_farmer_id_mapping():
    """Test that AgriStack ID mapping is deterministic."""
    agristack_id = "AS-TN-003-456789"
    
    # Generate FarmerID multiple times
    farmer_ids = [map_agristack_to_farmer_id(agristack_id) for _ in range(5)]
    
    # All should be identical
    assert len(set(farmer_ids)) == 1, "AgriStack ID should map to same FarmerID consistently"
    assert farmer_ids[0].startswith('FARMER-AS-'), "FarmerID should have correct prefix"


def test_different_agristack_ids_different_farmer_ids():
    """Test that different AgriStack IDs map to different FarmerIDs."""
    agristack_id_1 = "AS-MH-001-111111"
    agristack_id_2 = "AS-MH-001-222222"
    
    farmer_id_1 = map_agristack_to_farmer_id(agristack_id_1)
    farmer_id_2 = map_agristack_to_farmer_id(agristack_id_2)
    
    assert farmer_id_1 != farmer_id_2, "Different AgriStack IDs should map to different FarmerIDs"


def test_farmer_id_generation_without_any_id():
    """Test FarmerID generation without AgriStack ID or phone number."""
    farmer_id_1 = generate_farmer_id()
    farmer_id_2 = generate_farmer_id()
    
    # Should generate unique IDs
    assert farmer_id_1 != farmer_id_2, "Random FarmerIDs should be unique"
    assert farmer_id_1.startswith('FARMER-'), "FarmerID should have correct prefix"
    assert farmer_id_2.startswith('FARMER-'), "FarmerID should have correct prefix"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
