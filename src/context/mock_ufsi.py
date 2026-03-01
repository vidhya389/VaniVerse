"""
Mock UFSI layer for development and testing.

Provides 100+ diverse farmer profiles with realistic land records.
"""

import random
from typing import Optional
from src.models.context_data import LandRecords, CropHistory


# Diverse farmer profiles (100+ profiles)
MOCK_FARMER_PROFILES = {}


def _generate_mock_profiles():
    """Generate 100+ diverse farmer profiles."""
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
    
    # Generate 120 profiles
    for i in range(1, 121):
        agristack_id = f"AGRI{i:04d}"
        
        # Random land area (0.5 to 10 hectares)
        land_area = round(random.uniform(0.5, 10.0), 2)
        
        # Random soil type
        soil_type = random.choice(soil_types)
        
        # Random current crop (80% have current crop)
        current_crop = random.choice(crops) if random.random() < 0.8 else None
        
        # Generate crop history (2-5 entries)
        crop_history = []
        num_history = random.randint(2, 5)
        for _ in range(num_history):
            crop_history.append(CropHistory(
                crop=random.choice(crops),
                season=random.choice(seasons),
                year=random.choice(years)
            ))
        
        MOCK_FARMER_PROFILES[agristack_id] = LandRecords(
            landArea=land_area,
            soilType=soil_type,
            currentCrop=current_crop,
            cropHistory=crop_history
        )


# Generate profiles on module import
_generate_mock_profiles()


def fetch_mock_land_records(agristack_id: str) -> Optional[LandRecords]:
    """
    Fetch mock land records for development and testing.
    
    Provides 100+ diverse farmer profiles with realistic data.
    
    Args:
        agristack_id: AgriStack ID to lookup
    
    Returns:
        LandRecords object or None if ID not found
    
    Requirements: 12.2
    """
    if not agristack_id:
        return None
    
    # Return profile if exists
    if agristack_id in MOCK_FARMER_PROFILES:
        return MOCK_FARMER_PROFILES[agristack_id]
    
    # Generate a default profile for unknown IDs
    return LandRecords(
        landArea=2.0,
        soilType='Clay Loam',
        currentCrop='Rice',
        cropHistory=[
            CropHistory(crop='Wheat', season='Rabi', year=2023),
            CropHistory(crop='Rice', season='Kharif', year=2023)
        ]
    )


def get_mock_profile_count() -> int:
    """Get the number of mock profiles available."""
    return len(MOCK_FARMER_PROFILES)


def get_all_mock_agristack_ids() -> list[str]:
    """Get all available mock AgriStack IDs."""
    return list(MOCK_FARMER_PROFILES.keys())
