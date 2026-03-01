"""
Prompt models for Memory-First prompting.

Represents the structured prompts sent to Claude via AWS Bedrock.
"""

from typing import Dict, Any
from pydantic import BaseModel, Field
from src.models.context_data import ContextData


class MemoryFirstPrompt(BaseModel):
    """
    Memory-First prompt structure for Claude.
    
    Combines system instructions, context data, and the current question
    to create a prompt that prioritizes checking unresolved issues before
    answering new queries.
    
    Attributes:
        systemPrompt: System-level instructions including Memory-First priority
        context: Complete context data (weather, land, memory)
        currentQuestion: The farmer's current question
        agentOutputs: Outputs from specialized agents (weather, ICAR)
    """
    
    systemPrompt: str = Field(..., min_length=1, description="System prompt with Memory-First instructions")
    context: ContextData = Field(..., description="Complete context data")
    currentQuestion: str = Field(..., min_length=1, description="Farmer's current question")
    agentOutputs: Dict[str, str] = Field(
        default_factory=dict,
        description="Outputs from specialized agents"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "systemPrompt": "You are VaniVerse, a proactive agricultural advisor...",
                "context": {
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
                    "landRecords": None,
                    "memory": {
                        "recentInteractions": [],
                        "unresolvedIssues": [],
                        "consolidatedInsights": {
                            "primaryCrop": "Rice",
                            "commonConcerns": [],
                            "farmerName": None
                        }
                    }
                },
                "currentQuestion": "When should I spray pesticide?",
                "agentOutputs": {
                    "weather_analysis": "Current conditions are favorable...",
                    "icar_knowledge": "According to ICAR guidelines..."
                }
            }
        }
