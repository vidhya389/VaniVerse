"""
Multi-agent system for VaniVerse.

Provides specialized agents for weather analysis and ICAR knowledge,
with parallel invocation capabilities.
"""

from src.agents.weather_analytics import invoke_weather_analytics_agent
from src.agents.icar_knowledge import invoke_icar_knowledge_agent
from src.agents.orchestrator import invoke_agents_parallel, combine_agent_outputs

__all__ = [
    'invoke_weather_analytics_agent',
    'invoke_icar_knowledge_agent',
    'invoke_agents_parallel',
    'combine_agent_outputs',
]
