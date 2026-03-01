"""
Context data models.

Represents all contextual information used for generating agricultural advice.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class CurrentWeather(BaseModel):
    """Current weather conditions."""
    
    temperature: float = Field(..., description="Temperature in Celsius")
    humidity: float = Field(..., ge=0, le=100, description="Humidity percentage")
    windSpeed: float = Field(..., ge=0, description="Wind speed in km/h")
    precipitation: float = Field(..., ge=0, description="Precipitation in mm")
    
    class Config:
        json_schema_extra = {
            "example": {
                "temperature": 32.5,
                "humidity": 65.0,
                "windSpeed": 12.5,
                "precipitation": 0.0
            }
        }


class Forecast6h(BaseModel):
    """6-hour weather forecast."""
    
    precipitationProbability: float = Field(..., ge=0, le=100, description="Precipitation probability percentage")
    expectedRainfall: float = Field(..., ge=0, description="Expected rainfall in mm")
    temperature: float = Field(..., description="Forecasted temperature in Celsius")
    windSpeed: float = Field(..., ge=0, description="Forecasted wind speed in km/h")
    
    class Config:
        json_schema_extra = {
            "example": {
                "precipitationProbability": 35.0,
                "expectedRainfall": 2.5,
                "temperature": 30.0,
                "windSpeed": 15.0
            }
        }


class WeatherData(BaseModel):
    """Complete weather information including current and forecast."""
    
    current: CurrentWeather = Field(..., description="Current weather conditions")
    forecast6h: Forecast6h = Field(..., description="6-hour forecast")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO 8601 timestamp of weather data"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "current": {
                    "temperature": 32.5,
                    "humidity": 65.0,
                    "windSpeed": 12.5,
                    "precipitation": 0.0
                },
                "forecast6h": {
                    "precipitationProbability": 35.0,
                    "expectedRainfall": 2.5,
                    "temperature": 30.0,
                    "windSpeed": 15.0
                },
                "timestamp": "2024-02-14T10:30:00.000Z"
            }
        }


class CropHistory(BaseModel):
    """Historical crop information."""
    
    crop: str = Field(..., min_length=1, description="Crop name")
    season: str = Field(..., min_length=1, description="Growing season (e.g., Kharif, Rabi)")
    year: int = Field(..., ge=2000, le=2100, description="Year of cultivation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "crop": "Rice",
                "season": "Kharif",
                "year": 2023
            }
        }


class LandRecords(BaseModel):
    """
    Land records from AgriStack/UFSI.
    
    Attributes:
        landArea: Land area in hectares
        soilType: Soil classification (e.g., "Clay Loam", "Sandy")
        currentCrop: Currently growing crop (optional)
        cropHistory: Historical crop cultivation records
    """
    
    landArea: float = Field(..., gt=0, description="Land area in hectares")
    soilType: str = Field(..., min_length=1, description="Soil type classification")
    currentCrop: Optional[str] = Field(None, description="Current crop being grown")
    cropHistory: List[CropHistory] = Field(default_factory=list, description="Historical crop records")
    
    class Config:
        json_schema_extra = {
            "example": {
                "landArea": 2.5,
                "soilType": "Clay Loam",
                "currentCrop": "Rice",
                "cropHistory": [
                    {
                        "crop": "Wheat",
                        "season": "Rabi",
                        "year": 2023
                    },
                    {
                        "crop": "Rice",
                        "season": "Kharif",
                        "year": 2023
                    }
                ]
            }
        }


class Interaction(BaseModel):
    """A single farmer-system interaction."""
    
    question: str = Field(..., min_length=1, description="Farmer's question")
    advice: str = Field(..., min_length=1, description="System's advice")
    timestamp: str = Field(..., description="ISO 8601 timestamp of interaction")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "When should I spray pesticide on my rice crop?",
                "advice": "Based on current weather conditions...",
                "timestamp": "2024-02-14T10:30:00.000Z"
            }
        }


class UnresolvedIssue(BaseModel):
    """An unresolved crop issue from previous interactions."""
    
    issue: str = Field(..., min_length=1, description="Description of the issue")
    crop: str = Field(..., min_length=1, description="Affected crop")
    reportedDate: str = Field(..., description="ISO 8601 timestamp when issue was reported")
    daysSinceReport: int = Field(..., ge=0, description="Days since issue was reported")
    
    class Config:
        json_schema_extra = {
            "example": {
                "issue": "Leaf curl on tomato plants",
                "crop": "Tomato",
                "reportedDate": "2024-02-07T10:30:00.000Z",
                "daysSinceReport": 7
            }
        }


class ConsolidatedInsights(BaseModel):
    """Consolidated insights from conversation history."""
    
    primaryCrop: str = Field(..., min_length=1, description="Farmer's primary crop")
    commonConcerns: List[str] = Field(default_factory=list, description="Common concerns mentioned")
    farmerName: Optional[str] = Field(None, description="Farmer's name if known")
    
    class Config:
        json_schema_extra = {
            "example": {
                "primaryCrop": "Rice",
                "commonConcerns": ["pest management", "irrigation timing"],
                "farmerName": "Ramesh"
            }
        }


class MemoryContext(BaseModel):
    """
    Conversation memory context from AgentCore Memory.
    
    Attributes:
        recentInteractions: Recent Q&A pairs
        unresolvedIssues: Issues that need follow-up
        consolidatedInsights: Long-term patterns and preferences
    """
    
    recentInteractions: List[Interaction] = Field(
        default_factory=list,
        description="Recent conversation interactions"
    )
    unresolvedIssues: List[UnresolvedIssue] = Field(
        default_factory=list,
        description="Unresolved crop issues"
    )
    consolidatedInsights: ConsolidatedInsights = Field(
        default_factory=lambda: ConsolidatedInsights(primaryCrop="Unknown"),
        description="Consolidated insights from history"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "recentInteractions": [
                    {
                        "question": "When should I spray pesticide?",
                        "advice": "Based on current weather...",
                        "timestamp": "2024-02-14T10:30:00.000Z"
                    }
                ],
                "unresolvedIssues": [
                    {
                        "issue": "Leaf curl on tomato plants",
                        "crop": "Tomato",
                        "reportedDate": "2024-02-07T10:30:00.000Z",
                        "daysSinceReport": 7
                    }
                ],
                "consolidatedInsights": {
                    "primaryCrop": "Rice",
                    "commonConcerns": ["pest management"],
                    "farmerName": "Ramesh"
                }
            }
        }


class ContextData(BaseModel):
    """
    Complete context data for generating advice.
    
    Attributes:
        weather: Current weather and forecast
        landRecords: Land records from AgriStack (optional)
        memory: Conversation history and insights
    """
    
    weather: WeatherData = Field(..., description="Weather data")
    landRecords: Optional[LandRecords] = Field(None, description="Land records (if AgriStack ID available)")
    memory: MemoryContext = Field(
        default_factory=MemoryContext,
        description="Conversation memory"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "weather": {
                    "current": {
                        "temperature": 32.5,
                        "humidity": 65.0,
                        "windSpeed": 12.5,
                        "precipitation": 0.0
                    },
                    "forecast6h": {
                        "precipitationProbability": 35.0,
                        "expectedRainfall": 2.5,
                        "temperature": 30.0,
                        "windSpeed": 15.0
                    },
                    "timestamp": "2024-02-14T10:30:00.000Z"
                },
                "landRecords": {
                    "landArea": 2.5,
                    "soilType": "Clay Loam",
                    "currentCrop": "Rice",
                    "cropHistory": []
                },
                "memory": {
                    "recentInteractions": [],
                    "unresolvedIssues": [],
                    "consolidatedInsights": {
                        "primaryCrop": "Rice",
                        "commonConcerns": [],
                        "farmerName": None
                    }
                }
            }
        }
