"""
Farmer identity management module.

Handles AgriStack ID validation, FarmerID generation, and personalized greetings.
"""

import uuid
import hashlib
from typing import Optional, Tuple
import requests
from src.config import Config
from src.context.ufsi import _get_oauth_token
from src.models.context_data import MemoryContext


def validate_agristack_id(agristack_id: str, farmer_id: str) -> bool:
    """
    Validate AgriStack ID against UFSI API.
    
    Checks if the provided AgriStack ID exists and is valid in the
    AgriStack system using OAuth 2.0 authentication.
    
    Args:
        agristack_id: AgriStack ID to validate
        farmer_id: Internal farmer identifier for OAuth scope
    
    Returns:
        True if AgriStack ID is valid, False otherwise
    
    Raises:
        ValueError: If UFSI endpoint not configured
    
    Requirements: 5.2, 8.4
    """
    if not agristack_id:
        return False
    
    if not Config.UFSI_ENDPOINT:
        raise ValueError("UFSI_ENDPOINT not configured")
    
    try:
        # Get OAuth token
        oauth_token = _get_oauth_token(farmer_id)
        
        # Validate AgriStack ID via UFSI
        url = f"{Config.UFSI_ENDPOINT}/validate/{agristack_id}"
        headers = {
            'Authorization': f'Bearer {oauth_token}',
            'X-Request-ID': str(uuid.uuid4()),
            'Content-Type': 'application/json'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        # 200 = valid, 404 = not found, other = error
        return response.status_code == 200
    
    except requests.RequestException:
        # Return False on error (graceful degradation)
        return False


def generate_farmer_id(agristack_id: Optional[str] = None, phone_number: Optional[str] = None) -> str:
    """
    Generate unique FarmerID for non-AgriStack users or map AgriStack ID to FarmerID.
    
    If AgriStack ID is provided, generates a deterministic FarmerID based on it.
    Otherwise, generates a random UUID-based FarmerID.
    
    Args:
        agristack_id: Optional AgriStack ID to map
        phone_number: Optional phone number for deterministic generation
    
    Returns:
        Unique FarmerID string
    
    Requirements: 5.3, 5.5
    """
    if agristack_id:
        # Generate deterministic FarmerID from AgriStack ID
        # This ensures same AgriStack ID always maps to same FarmerID
        hash_input = f"agristack:{agristack_id}".encode('utf-8')
        hash_digest = hashlib.sha256(hash_input).hexdigest()[:16]
        return f"FARMER-AS-{hash_digest.upper()}"
    
    elif phone_number:
        # Generate deterministic FarmerID from phone number
        hash_input = f"phone:{phone_number}".encode('utf-8')
        hash_digest = hashlib.sha256(hash_input).hexdigest()[:16]
        return f"FARMER-PH-{hash_digest.upper()}"
    
    else:
        # Generate random FarmerID
        unique_id = str(uuid.uuid4()).replace('-', '')[:16].upper()
        return f"FARMER-{unique_id}"


def map_agristack_to_farmer_id(agristack_id: str) -> str:
    """
    Map AgriStack ID to FarmerID.
    
    Creates a deterministic mapping from AgriStack ID to internal FarmerID.
    
    Args:
        agristack_id: AgriStack ID
    
    Returns:
        Corresponding FarmerID
    
    Requirements: 5.3
    """
    return generate_farmer_id(agristack_id=agristack_id)


def generate_personalized_greeting(
    memory: MemoryContext,
    is_returning_farmer: bool = True
) -> Optional[str]:
    """
    Generate personalized greeting for returning farmers.
    
    Extracts farmer name and primary crop from memory consolidated insights
    and creates a warm, personalized greeting.
    
    Args:
        memory: MemoryContext with consolidated insights
        is_returning_farmer: Whether this is a returning farmer
    
    Returns:
        Personalized greeting string or None if insufficient data
    
    Requirements: 5.4
    """
    if not is_returning_farmer:
        return None
    
    insights = memory.consolidatedInsights
    
    # Check if we have enough information for personalization
    if not insights:
        return None
    
    farmer_name = insights.farmerName
    primary_crop = insights.primaryCrop
    
    # Generate greeting based on available information
    if farmer_name and primary_crop and primary_crop != 'Unknown':
        return f"Namaste {farmer_name}! How is your {primary_crop} crop doing today?"
    
    elif farmer_name:
        return f"Namaste {farmer_name}! How can I help you with your farm today?"
    
    elif primary_crop and primary_crop != 'Unknown':
        return f"Welcome back! How is your {primary_crop} crop doing?"
    
    else:
        # Not enough information for personalization
        return None


def extract_farmer_info_from_memory(memory: MemoryContext) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract farmer name and primary crop from memory.
    
    Helper function to retrieve personalization data from consolidated insights.
    
    Args:
        memory: MemoryContext with consolidated insights
    
    Returns:
        Tuple of (farmer_name, primary_crop)
    
    Requirements: 5.4
    """
    if not memory or not memory.consolidatedInsights:
        return None, None
    
    insights = memory.consolidatedInsights
    farmer_name = insights.farmerName
    primary_crop = insights.primaryCrop if insights.primaryCrop != 'Unknown' else None
    
    return farmer_name, primary_crop
