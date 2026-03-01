"""
UFSI (Unified Farmer Service Interface) API client for AgriStack integration.

Provides access to farmer land records with OAuth 2.0 authentication.
"""

import uuid
import time
from typing import Optional, Dict, Any
import requests
from src.config import Config
from src.models.context_data import LandRecords, CropHistory


# OAuth token cache
_oauth_token_cache: Dict[str, tuple[str, float]] = {}  # farmer_id -> (token, expiry_time)


def _get_oauth_token(farmer_id: str) -> str:
    """
    Get OAuth 2.0 token for UFSI API access.
    
    Implements token caching to avoid repeated authentication calls.
    
    Args:
        farmer_id: Farmer identifier for token scope
    
    Returns:
        OAuth bearer token
    
    Raises:
        ValueError: If UFSI credentials not configured
        requests.RequestException: If authentication fails
    """
    if not Config.UFSI_CLIENT_ID or not Config.UFSI_CLIENT_SECRET:
        raise ValueError("UFSI_CLIENT_ID and UFSI_CLIENT_SECRET must be configured")
    
    # Check cache
    if farmer_id in _oauth_token_cache:
        token, expiry = _oauth_token_cache[farmer_id]
        if time.time() < expiry:
            return token
    
    # Request new token
    token_url = f"{Config.UFSI_ENDPOINT}/oauth/token"
    response = requests.post(
        token_url,
        data={
            'grant_type': 'client_credentials',
            'client_id': Config.UFSI_CLIENT_ID,
            'client_secret': Config.UFSI_CLIENT_SECRET,
            'scope': f'farmer:{farmer_id}'
        },
        timeout=10
    )
    response.raise_for_status()
    
    token_data = response.json()
    access_token = token_data['access_token']
    expires_in = token_data.get('expires_in', 3600)  # Default 1 hour
    
    # Cache token (expire 5 minutes early for safety)
    expiry_time = time.time() + expires_in - 300
    _oauth_token_cache[farmer_id] = (access_token, expiry_time)
    
    return access_token


def _retry_with_backoff(func, max_attempts: int = 3, base_delay: float = 1.0):
    """
    Retry function with exponential backoff.
    
    Args:
        func: Function to retry
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds
    
    Returns:
        Function result
    
    Raises:
        Last exception if all retries fail
    """
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)


def fetch_land_records(farmer_id: str, agristack_id: str) -> Optional[LandRecords]:
    """
    Fetch land records from UFSI API.
    
    Implements OAuth 2.0 authentication and required UFSI headers.
    Returns None if farmer has no AgriStack ID or if API call fails.
    
    Args:
        farmer_id: Internal farmer identifier
        agristack_id: AgriStack ID for land records lookup
    
    Returns:
        LandRecords object or None if not available
    
    Raises:
        ValueError: If UFSI endpoint not configured
        requests.RequestException: If API call fails after retries
    
    Requirements: 3.2, 8.4, 12.4
    """
    if not agristack_id:
        return None
    
    if not Config.UFSI_ENDPOINT:
        raise ValueError("UFSI_ENDPOINT not configured")
    
    # Get OAuth token
    def _fetch():
        return _fetch_land_records_from_api(farmer_id, agristack_id)
    
    try:
        return _retry_with_backoff(_fetch, max_attempts=3, base_delay=1.0)
    except requests.RequestException:
        # Return None on failure (graceful degradation)
        return None


def _fetch_land_records_from_api(farmer_id: str, agristack_id: str) -> LandRecords:
    """
    Internal function to fetch land records from UFSI API.
    
    Args:
        farmer_id: Internal farmer identifier
        agristack_id: AgriStack ID
    
    Returns:
        LandRecords object
    
    Raises:
        requests.RequestException: If API call fails
    """
    oauth_token = _get_oauth_token(farmer_id)
    request_id = str(uuid.uuid4())
    
    # UFSI API call with required headers
    url = f"{Config.UFSI_ENDPOINT}/land-records/{agristack_id}"
    headers = {
        'Authorization': f'Bearer {oauth_token}',
        'X-Request-ID': request_id,
        'X-Consent-Token': f'consent-{farmer_id}',  # Placeholder for consent management
        'Content-Type': 'application/json'
    }
    
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    
    data = response.json()
    
    # Parse crop history
    crop_history = []
    for crop_data in data.get('cropHistory', []):
        crop_history.append(CropHistory(
            crop=crop_data['crop'],
            season=crop_data['season'],
            year=crop_data['year']
        ))
    
    return LandRecords(
        landArea=data['landArea'],
        soilType=data['soilType'],
        currentCrop=data.get('currentCrop'),
        cropHistory=crop_history
    )


def clear_oauth_cache():
    """Clear OAuth token cache. Useful for testing."""
    global _oauth_token_cache
    _oauth_token_cache.clear()
