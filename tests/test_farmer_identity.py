"""
Unit tests for farmer identity management.

Tests AgriStack ID validation, FarmerID generation, and personalized greetings.
"""

import pytest
from unittest.mock import patch, Mock
import requests
from src.context.farmer_identity import (
    validate_agristack_id,
    generate_farmer_id,
    map_agristack_to_farmer_id,
    generate_personalized_greeting,
    extract_farmer_info_from_memory
)
from src.models.context_data import MemoryContext, ConsolidatedInsights


class TestAgriStackIDValidation:
    """Tests for AgriStack ID validation."""
    
    @patch('src.context.farmer_identity._get_oauth_token')
    @patch('src.context.farmer_identity.requests.get')
    def test_validate_agristack_id_valid(self, mock_get, mock_oauth):
        """Test validation of valid AgriStack ID."""
        mock_oauth.return_value = 'test-token'
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = validate_agristack_id('AGRI001', 'FARMER-123')
        
        assert result is True
        mock_oauth.assert_called_once_with('FARMER-123')
        assert mock_get.called
    
    @patch('src.context.farmer_identity._get_oauth_token')
    @patch('src.context.farmer_identity.requests.get')
    def test_validate_agristack_id_not_found(self, mock_get, mock_oauth):
        """Test validation of non-existent AgriStack ID."""
        mock_oauth.return_value = 'test-token'
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = validate_agristack_id('INVALID', 'FARMER-123')
        
        assert result is False
    
    @patch('src.context.farmer_identity._get_oauth_token')
    @patch('src.context.farmer_identity.requests.get')
    def test_validate_agristack_id_api_error(self, mock_get, mock_oauth):
        """Test graceful handling of API errors."""
        mock_oauth.return_value = 'test-token'
        mock_get.side_effect = requests.RequestException('API error')
        
        result = validate_agristack_id('AGRI001', 'FARMER-123')
        
        assert result is False
    
    def test_validate_agristack_id_empty(self):
        """Test validation of empty AgriStack ID."""
        result = validate_agristack_id('', 'FARMER-123')
        assert result is False
    
    def test_validate_agristack_id_none(self):
        """Test validation of None AgriStack ID."""
        result = validate_agristack_id(None, 'FARMER-123')
        assert result is False


class TestFarmerIDGeneration:
    """Tests for FarmerID generation and mapping."""
    
    def test_generate_farmer_id_from_agristack(self):
        """Test deterministic FarmerID generation from AgriStack ID."""
        farmer_id_1 = generate_farmer_id(agristack_id='AGRI001')
        farmer_id_2 = generate_farmer_id(agristack_id='AGRI001')
        
        # Should be deterministic
        assert farmer_id_1 == farmer_id_2
        assert farmer_id_1.startswith('FARMER-AS-')
        assert len(farmer_id_1) == 26  # FARMER-AS- + 16 hex chars
    
    def test_generate_farmer_id_from_phone(self):
        """Test deterministic FarmerID generation from phone number."""
        farmer_id_1 = generate_farmer_id(phone_number='+919876543210')
        farmer_id_2 = generate_farmer_id(phone_number='+919876543210')
        
        # Should be deterministic
        assert farmer_id_1 == farmer_id_2
        assert farmer_id_1.startswith('FARMER-PH-')
        assert len(farmer_id_1) == 26  # FARMER-PH- + 16 hex chars
    
    def test_generate_farmer_id_random(self):
        """Test random FarmerID generation."""
        farmer_id_1 = generate_farmer_id()
        farmer_id_2 = generate_farmer_id()
        
        # Should be different
        assert farmer_id_1 != farmer_id_2
        assert farmer_id_1.startswith('FARMER-')
        assert len(farmer_id_1) == 23  # FARMER- + 16 chars
    
    def test_generate_farmer_id_different_agristack_ids(self):
        """Test that different AgriStack IDs produce different FarmerIDs."""
        farmer_id_1 = generate_farmer_id(agristack_id='AGRI001')
        farmer_id_2 = generate_farmer_id(agristack_id='AGRI002')
        
        assert farmer_id_1 != farmer_id_2
    
    def test_map_agristack_to_farmer_id(self):
        """Test AgriStack ID to FarmerID mapping."""
        farmer_id = map_agristack_to_farmer_id('AGRI001')
        
        assert farmer_id.startswith('FARMER-AS-')
        
        # Should be consistent with generate_farmer_id
        expected = generate_farmer_id(agristack_id='AGRI001')
        assert farmer_id == expected


class TestPersonalizedGreeting:
    """Tests for personalized greeting generation."""
    
    def test_generate_greeting_with_name_and_crop(self):
        """Test greeting with both name and crop."""
        memory = MemoryContext(
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop='Rice',
                farmerName='Ramesh',
                commonConcerns=[]
            )
        )
        
        greeting = generate_personalized_greeting(memory, is_returning_farmer=True)
        
        assert greeting is not None
        assert 'Ramesh' in greeting
        assert 'Rice' in greeting
    
    def test_generate_greeting_with_name_only(self):
        """Test greeting with name but no crop."""
        memory = MemoryContext(
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop='Unknown',
                farmerName='Ramesh',
                commonConcerns=[]
            )
        )
        
        greeting = generate_personalized_greeting(memory, is_returning_farmer=True)
        
        assert greeting is not None
        assert 'Ramesh' in greeting
        assert 'Rice' not in greeting
    
    def test_generate_greeting_with_crop_only(self):
        """Test greeting with crop but no name."""
        memory = MemoryContext(
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop='Wheat',
                farmerName=None,
                commonConcerns=[]
            )
        )
        
        greeting = generate_personalized_greeting(memory, is_returning_farmer=True)
        
        assert greeting is not None
        assert 'Wheat' in greeting
    
    def test_generate_greeting_no_personalization_data(self):
        """Test greeting with no personalization data."""
        memory = MemoryContext(
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop='Unknown',
                farmerName=None,
                commonConcerns=[]
            )
        )
        
        greeting = generate_personalized_greeting(memory, is_returning_farmer=True)
        
        assert greeting is None
    
    def test_generate_greeting_new_farmer(self):
        """Test that new farmers don't get personalized greeting."""
        memory = MemoryContext(
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop='Rice',
                farmerName='Ramesh',
                commonConcerns=[]
            )
        )
        
        greeting = generate_personalized_greeting(memory, is_returning_farmer=False)
        
        assert greeting is None
    
    def test_generate_greeting_empty_memory(self):
        """Test greeting with empty memory."""
        memory = MemoryContext()
        
        greeting = generate_personalized_greeting(memory, is_returning_farmer=True)
        
        assert greeting is None


class TestExtractFarmerInfo:
    """Tests for extracting farmer information from memory."""
    
    def test_extract_farmer_info_complete(self):
        """Test extracting complete farmer information."""
        memory = MemoryContext(
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop='Rice',
                farmerName='Ramesh',
                commonConcerns=[]
            )
        )
        
        name, crop = extract_farmer_info_from_memory(memory)
        
        assert name == 'Ramesh'
        assert crop == 'Rice'
    
    def test_extract_farmer_info_unknown_crop(self):
        """Test extracting info when crop is Unknown."""
        memory = MemoryContext(
            consolidatedInsights=ConsolidatedInsights(
                primaryCrop='Unknown',
                farmerName='Ramesh',
                commonConcerns=[]
            )
        )
        
        name, crop = extract_farmer_info_from_memory(memory)
        
        assert name == 'Ramesh'
        assert crop is None
    
    def test_extract_farmer_info_empty_memory(self):
        """Test extracting info from empty memory."""
        memory = MemoryContext()
        
        name, crop = extract_farmer_info_from_memory(memory)
        
        assert name is None
        assert crop is None
    
    def test_extract_farmer_info_none_memory(self):
        """Test extracting info from None memory."""
        name, crop = extract_farmer_info_from_memory(None)
        
        assert name is None
        assert crop is None
