"""
Multi-agent orchestrator for parallel agent invocation.

Coordinates specialized agents (Weather Analytics and ICAR Knowledge)
to provide comprehensive agricultural advice.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Tuple
from src.models.context_data import ContextData
from src.agents.weather_analytics import invoke_weather_analytics_agent
from src.agents.icar_knowledge import invoke_icar_knowledge_agent


def invoke_agents_parallel(context: ContextData, question: str) -> Dict[str, str]:
    """
    Invoke both specialized agents in parallel.
    
    Args:
        context: Complete context data including weather, land records, and memory
        question: Farmer's question
        
    Returns:
        Dictionary with 'weather_analysis' and 'icar_knowledge' keys containing
        the outputs from each specialized agent
        
    Raises:
        Exception: If either agent invocation fails
    """
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both agent invocations
        weather_future = executor.submit(
            invoke_weather_analytics_agent,
            context.weather,
            question
        )
        
        icar_future = executor.submit(
            invoke_icar_knowledge_agent,
            context.landRecords,
            context.memory,
            question
        )
        
        # Wait for both to complete and collect results
        weather_analysis = weather_future.result()
        icar_knowledge = icar_future.result()
    
    return {
        'weather_analysis': weather_analysis,
        'icar_knowledge': icar_knowledge
    }


def combine_agent_outputs(
    weather_analysis: str,
    icar_knowledge: str,
    context: ContextData
) -> str:
    """
    Combine outputs from specialized agents for final prompt construction.
    
    Args:
        weather_analysis: Output from Weather Analytics Agent
        icar_knowledge: Output from ICAR Knowledge Agent
        context: Complete context data
        
    Returns:
        Combined agent outputs formatted for Memory-First prompting
    """
    combined = f"""
SPECIALIZED AGENT INPUTS:

Weather Analysis (from Weather Analytics Agent):
{weather_analysis}

ICAR Knowledge (from ICAR Knowledge Agent):
{icar_knowledge}

CURRENT CONTEXT:
Weather: Temperature {context.weather.current.temperature}°C, Humidity {context.weather.current.humidity}%, Wind {context.weather.current.windSpeed} km/h
6h Forecast: {context.weather.forecast6h.precipitationProbability}% rain probability
"""
    
    if context.landRecords:
        combined += f"\nLand: {context.landRecords.landArea} hectares, {context.landRecords.soilType} soil"
        if context.landRecords.currentCrop:
            combined += f", Current crop: {context.landRecords.currentCrop}"
    
    if context.memory.unresolvedIssues:
        combined += f"\nUnresolved Issues: {len(context.memory.unresolvedIssues)} pending"
    
    return combined
