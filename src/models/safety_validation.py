"""
Safety validation models.

Models for representing safety validation results and conflicts.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class SafetyConflict(BaseModel):
    """A detected safety conflict."""
    
    type: str = Field(..., description="Type of conflict (e.g., 'rain_forecast', 'extreme_temperature')")
    severity: str = Field(..., description="Severity level: 'warning' or 'blocking'")
    message: str = Field(..., description="Human-readable conflict message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "rain_forecast",
                "severity": "blocking",
                "message": "Rain is predicted within 6 hours (45% probability). Spraying now will waste pesticide."
            }
        }


class SafetyValidationResult(BaseModel):
    """
    Result of safety validation check.
    
    Attributes:
        isApproved: Whether the advice is safe to deliver
        conflicts: List of detected safety conflicts
        alternativeRecommendation: Alternative advice if blocked
    """
    
    isApproved: bool = Field(..., description="Whether the advice passes safety validation")
    conflicts: List[SafetyConflict] = Field(
        default_factory=list,
        description="List of detected safety conflicts"
    )
    alternativeRecommendation: Optional[str] = Field(
        None,
        description="Alternative recommendation when advice is blocked"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "isApproved": False,
                "conflicts": [
                    {
                        "type": "rain_forecast",
                        "severity": "blocking",
                        "message": "Rain is predicted within 6 hours (45% probability)."
                    }
                ],
                "alternativeRecommendation": "Wait at least 12 hours and check the weather again..."
            }
        }
