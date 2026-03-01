"""
Mock UFSI layer for development and testing.

Provides deterministic farmer profiles based on farmer_id for consistent testing.
"""

import hashlib
from typing import Optional
from src.models.context_data import LandRecords, CropHistory


def _get_deterministic_random(seed: str, max_value: int) -> int:
    """
    Generate a deterministic random number based on a seed string.
    
    Args:
        seed: Seed string (e.g., farmer_id + field_name)
        max_value: Maximum value (exclusive)
    
    Returns:
        Deterministic integer between 0 and max_value-1
    """
    hash_value = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    return hash_value % max_value


def _get_deterministic_float(seed: str, min_value: float, max_value: float) -> float:
    """
    Generate a deterministic float based on a seed string.
    
    Args:
        seed: Seed string
        min_value: Minimum value
        max_value: Maximum value
    
    Returns:
        Deterministic float between min_value and max_value
    """
    hash_value = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    normalized = (hash_value % 10000) / 10000.0  # 0.0 to 1.0
    return min_value + (normalized * (max_value - min_value))


def fetch_mock_land_records(farmer_id: str, agristack_id: Optional[str] = None) -> Optional[LandRecords]:
    """
    Fetch mock land records for development and testing.
    
    Generates deterministic data based on farmer_id to ensure consistency.
    The same farmer_id will always get the same mock data.
    
    Args:
        farmer_id: Farmer identifier (used as seed for deterministic generation)
        agristack_id: AgriStack ID (optional, not used in mock)
    
    Returns:
        LandRecords object with deterministic data based on farmer_id
    
    Requirements: 12.2
    """
    if not farmer_id:
        return None
    
    # Use farmer_id as seed for deterministic generation
    crops = [
        'Rice', 'Wheat', 'Cotton', 'Sugarcane', 'Maize', 'Soybean', 'Groundnut',
        'Pulses', 'Millets', 'Barley', 'Jowar', 'Bajra', 'Ragi', 'Mustard',
        'Sunflower', 'Sesame', 'Potato', 'Tomato', 'Onion', 'Chili', 'Turmeric',
        'Ginger', 'Garlic', 'Cabbage', 'Cauliflower', 'Brinjal', 'Okra', 'Beans',
        'Peas', 'Carrot', 'Radish', 'Cucumber', 'Pumpkin', 'Bitter Gourd',
        'Bottle Gourd', 'Ridge Gourd', 'Spinach', 'Coriander', 'Mint', 'Fenugreek'
    ]
    
    soil_types = [
        'Clay Loam', 'Sandy Loam', 'Silty Clay', 'Red Soil', 'Black Soil',
        'Alluvial Soil', 'Laterite Soil', 'Desert Soil', 'Mountain Soil',
        'Peaty Soil', 'Saline Soil', 'Chalky Soil'
    ]
    
    seasons = ['Kharif', 'Rabi', 'Zaid']
    years = [2021, 2022, 2023, 2024]
    
    # Generate deterministic land area (0.5 to 10 hectares)
    land_area = round(_get_deterministic_float(f"{farmer_id}_land_area", 0.5, 10.0), 2)
    
    # Deterministic soil type
    soil_type_idx = _get_deterministic_random(f"{farmer_id}_soil_type", len(soil_types))
    soil_type = soil_types[soil_type_idx]
    
    # Deterministic current crop (80% have current crop)
    has_current_crop = _get_deterministic_random(f"{farmer_id}_has_crop", 100) < 80
    if has_current_crop:
        crop_idx = _get_deterministic_random(f"{farmer_id}_current_crop", len(crops))
        current_crop = crops[crop_idx]
    else:
        current_crop = None
    
    # Generate deterministic crop history (2-5 entries)
    num_history = _get_deterministic_random(f"{farmer_id}_history_count", 4) + 2  # 2-5
    crop_history = []
    for i in range(num_history):
        crop_idx = _get_deterministic_random(f"{farmer_id}_history_{i}_crop", len(crops))
        season_idx = _get_deterministic_random(f"{farmer_id}_history_{i}_season", len(seasons))
        year_idx = _get_deterministic_random(f"{farmer_id}_history_{i}_year", len(years))
        
        crop_history.append(CropHistory(
            crop=crops[crop_idx],
            season=seasons[season_idx],
            year=years[year_idx]
        ))
    
    return LandRecords(
        landArea=land_area,
        soilType=soil_type,
        currentCrop=current_crop,
        cropHistory=crop_history
    )
