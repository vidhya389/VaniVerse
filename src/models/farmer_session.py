"""
FarmerSession data model.

Represents a farmer's session with GPS coordinates, language, and identity information.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class GPSCoordinates(BaseModel):
    """GPS coordinates for location-based services."""
    
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    
    class Config:
        json_schema_extra = {
            "example": {
                "latitude": 28.6139,
                "longitude": 77.2090
            }
        }


class FarmerSession(BaseModel):
    """
    Represents a farmer's session with identity and context information.
    
    Attributes:
        farmerId: Unique identifier (linked to AgriStack ID if available)
        agriStackId: Optional AgriStack ID for land records access
        sessionId: Current session identifier
        language: Detected language code (e.g., "hi-IN", "ta-IN")
        gpsCoordinates: Current location coordinates
        timestamp: ISO 8601 timestamp of session creation
    """
    
    farmerId: str = Field(..., min_length=1, description="Unique farmer identifier")
    agriStackId: Optional[str] = Field(None, description="Optional AgriStack ID")
    sessionId: str = Field(..., min_length=1, description="Current session identifier")
    language: str = Field(..., pattern=r'^[a-z]{2}-[A-Z]{2}$', description="Language code (e.g., hi-IN)")
    gpsCoordinates: GPSCoordinates = Field(..., description="GPS location")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO 8601 timestamp"
    )
    
    @field_validator('language')
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validate that language is in supported list."""
        supported_languages = [
            'hi-IN',  # Hindi
            'ta-IN',  # Tamil
            'te-IN',  # Telugu
            'kn-IN',  # Kannada
            'mr-IN',  # Marathi
            'bn-IN',  # Bengali
            'gu-IN',  # Gujarati
            'pa-IN'   # Punjabi
        ]
        if v not in supported_languages:
            raise ValueError(f"Language {v} not supported. Must be one of {supported_languages}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "farmerId": "FARMER-12345",
                "agriStackId": "AGRI001",
                "sessionId": "SESSION-67890",
                "language": "hi-IN",
                "gpsCoordinates": {
                    "latitude": 28.6139,
                    "longitude": 77.2090
                },
                "timestamp": "2024-02-14T10:30:00.000Z"
            }
        }
