"""
Weather Analytics Agent for agricultural risk assessment.

This specialized agent analyzes weather data and provides risk assessments
for agricultural activities, timing recommendations, and specific warnings.
"""

import json
import boto3
from typing import Dict, Any
from src.config import Config
from src.models.context_data import WeatherData


def invoke_weather_analytics_agent(weather: WeatherData, question: str) -> str:
    """
    Specialized agent for weather analysis and risk assessment.
    
    Args:
        weather: Current weather data and 6-hour forecast
        question: Farmer's question
        
    Returns:
        Weather analysis and risk assessment as text
        
    Raises:
        Exception: If Bedrock invocation fails
    """
    # Use mock response if configured
    if Config.USE_MOCK_LLM:
        return _mock_weather_analysis(weather)
    
    bedrock_runtime = boto3.client('bedrock-runtime', region_name=Config.AWS_REGION)
    
    system_prompt = """
You are a Weather Analytics Agent specializing in agricultural meteorology.
Your role is to analyze weather data and assess risks for farming activities.

RESPONSIBILITIES:
1. Interpret current weather conditions for agricultural impact
2. Analyze 6-hour forecasts for activity timing
3. Identify risks (rain, extreme heat, high wind, frost)
4. Recommend optimal timing windows for weather-sensitive operations

RESPONSE FORMAT:
- Current Conditions Summary
- Risk Assessment (High/Medium/Low for various activities)
- Timing Recommendations
- Specific Warnings

Be concise and focus on actionable insights for farmers.
"""
    
    # Convert weather data to dict for JSON serialization
    weather_dict = weather.model_dump()
    
    # Determine if using Nova or Claude format
    is_nova = 'nova' in Config.MODEL_ID.lower()
    
    if is_nova:
        # Nova format
        request_body = {
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {
                            'text': f"""{system_prompt}

Weather Data:
{json.dumps(weather_dict, indent=2)}

Farmer's Question: {question}

Provide weather analysis and risk assessment."""
                        }
                    ]
                }
            ],
            'inferenceConfig': {
                'max_new_tokens': 500,
                'temperature': 0.7,
                'top_p': 0.9
            }
        }
    else:
        # Claude format
        request_body = {
            'anthropic_version': 'bedrock-2023-05-31',
            'max_tokens': 500,
            'system': system_prompt,
            'messages': [
                {
                    'role': 'user',
                    'content': f"""
Weather Data:
{json.dumps(weather_dict, indent=2)}

Farmer's Question: {question}

Provide weather analysis and risk assessment.
"""
                }
            ]
        }
    
    response = bedrock_runtime.invoke_model(
        modelId=Config.MODEL_ID,
        body=json.dumps(request_body)
    )
    
    response_body = json.loads(response['body'].read())
    
    # Extract response based on model type
    is_nova = 'nova' in Config.MODEL_ID.lower()
    if is_nova:
        # Nova response format
        return response_body['output']['message']['content'][0]['text']
    else:
        # Claude response format
        return response_body['content'][0]['text']



def _mock_weather_analysis(weather: WeatherData) -> str:
    """Mock weather analysis for testing without Bedrock."""
    temp = weather.current.temperature
    humidity = weather.current.humidity
    rain_prob = weather.forecast6h.precipitationProbability
    rainfall = weather.forecast6h.expectedRainfall
    
    # Determine risk level
    if rain_prob > 70 or temp > 35:
        risk = "HIGH"
    elif rain_prob > 40 or temp > 30:
        risk = "MEDIUM"
    else:
        risk = "LOW"
    
    return f"""WEATHER ANALYSIS:

Current Conditions:
- Temperature: {temp}°C
- Humidity: {humidity}%
- Wind Speed: {weather.current.windSpeed} km/h

6-Hour Forecast:
- Rain Probability: {rain_prob}%
- Expected Rainfall: {rainfall}mm
- Temperature: {weather.forecast6h.temperature}°C

Risk Assessment: {risk}

Recommendations:
- Pesticide spraying: {'NOT RECOMMENDED (rain expected)' if rain_prob > 50 else 'SAFE'}
- Irrigation: {'NOT NEEDED (rain expected)' if rain_prob > 60 else 'CONSIDER IF NEEDED'}
- Field work: {'PLAN CAREFULLY (weather conditions)' if risk == 'HIGH' else 'PROCEED NORMALLY'}

Timing: {'Wait for weather to clear' if rain_prob > 50 else 'Good conditions for field activities'}"""
