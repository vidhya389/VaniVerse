"""
AudioRequest data model.

Represents an incoming audio upload request with metadata.
"""

from datetime import datetime
from pydantic import BaseModel, Field
from .farmer_session import GPSCoordinates


class AudioRequest(BaseModel):
    """
    Represents an audio upload request from the client app.
    
    Attributes:
        audioFileKey: S3 key for uploaded audio file
        farmerId: Unique farmer identifier
        sessionId: Current session identifier
        gpsCoordinates: Location where audio was recorded
        timestamp: ISO 8601 timestamp of request
    """
    
    audioFileKey: str = Field(..., min_length=1, description="S3 key for audio file")
    farmerId: str = Field(..., min_length=1, description="Unique farmer identifier")
    sessionId: str = Field(..., min_length=1, description="Current session identifier")
    gpsCoordinates: GPSCoordinates = Field(..., description="GPS location")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO 8601 timestamp"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "audioFileKey": "uploads/FARMER-12345/audio-67890.wav",
                "farmerId": "FARMER-12345",
                "sessionId": "SESSION-67890",
                "gpsCoordinates": {
                    "latitude": 28.6139,
                    "longitude": 77.2090
                },
                "timestamp": "2024-02-14T10:30:00.000Z"
            }
        }
