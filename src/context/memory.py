"""
AgentCore Memory integration for conversation history and insights.

Provides automatic storage and retrieval of farmer interactions with
short-term session context and long-term insight consolidation.
"""

import json
from datetime import datetime
from typing import Optional
import boto3
from botocore.exceptions import ClientError
from src.config import Config
from src.models.context_data import (
    MemoryContext, Interaction, UnresolvedIssue, ConsolidatedInsights,
    ContextData
)


def fetch_memory(farmer_id: str) -> MemoryContext:
    """
    Fetch conversation memory from AgentCore Memory.
    
    Retrieves session context and consolidated insights using FarmerID
    as the partition key.
    
    Args:
        farmer_id: Unique farmer identifier (used as session ID)
    
    Returns:
        MemoryContext with recent interactions, unresolved issues, and insights
    
    Raises:
        ValueError: If AgentCore Memory not configured
        ClientError: If AWS API call fails
    
    Requirements: 2.1, 2.3, 5.3, 11.7
    """
    if not Config.AGENTCORE_AGENT_ID or not Config.AGENTCORE_ALIAS_ID:
        # Return empty memory if not configured (graceful degradation)
        return MemoryContext()
    
    try:
        # Log cross-region invocation if applicable
        if Config.AGENTCORE_REGION != Config.AWS_REGION:
            print(f"INFO: Invoking Bedrock Agent in {Config.AGENTCORE_REGION} from Lambda in {Config.AWS_REGION}")
        
        bedrock_agent_runtime = boto3.client(
            'bedrock-agent-runtime',
            region_name=Config.AGENTCORE_REGION
        )
        
        # Query AgentCore Memory using InvokeAgent
        response = bedrock_agent_runtime.invoke_agent(
            agentId=Config.AGENTCORE_AGENT_ID,
            agentAliasId=Config.AGENTCORE_ALIAS_ID,
            sessionId=farmer_id,
            inputText=f"Retrieve conversation history and unresolved issues for this farmer session"
        )
        
        # Parse streaming response
        memory_text = _parse_agent_streaming_response(response)
        
        # Parse AgentCore Memory response
        memory_data = _parse_memory_text(memory_text)
        
        return MemoryContext(
            recentInteractions=memory_data.get('recentInteractions', []),
            unresolvedIssues=memory_data.get('unresolvedIssues', []),
            consolidatedInsights=memory_data.get(
                'consolidatedInsights',
                ConsolidatedInsights(primaryCrop='Unknown')
            )
        )
    
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        # Provide actionable error messages
        if error_code == 'AccessDeniedException':
            print(f"Error fetching memory for farmer {farmer_id}: Access denied")
            print(f"  Error Code: {error_code}")
            print(f"  Message: {error_message}")
            if Config.AGENTCORE_REGION != Config.AWS_REGION:
                print(f"  Cross-region invocation detected (Lambda: {Config.AWS_REGION}, Agent: {Config.AGENTCORE_REGION})")
                print(f"  Check IAM policy allows cross-region invocation:")
                print(f"    Resource: arn:aws:bedrock:*:ACCOUNT_ID:agent-alias/{Config.AGENTCORE_AGENT_ID}/{Config.AGENTCORE_ALIAS_ID}")
        elif error_code == 'ResourceNotFoundException':
            print(f"Error fetching memory for farmer {farmer_id}: Resource not found")
            print(f"  Error Code: {error_code}")
            print(f"  Message: {error_message}")
            if Config.AGENTCORE_REGION != Config.AWS_REGION:
                print(f"  Cross-region invocation detected (Lambda: {Config.AWS_REGION}, Agent: {Config.AGENTCORE_REGION})")
                print(f"  Verify agent exists in region: {Config.AGENTCORE_REGION}")
                print(f"  Agent ID: {Config.AGENTCORE_AGENT_ID}, Alias ID: {Config.AGENTCORE_ALIAS_ID}")
        else:
            print(f"Error fetching memory for farmer {farmer_id}: {e}")
        
        # Return empty memory on error (graceful degradation)
        return MemoryContext()


def store_interaction(
    farmer_id: str,
    question: str,
    advice: str,
    context: ContextData
) -> None:
    """
    Store interaction in AgentCore Memory for automatic consolidation.
    
    AgentCore Memory automatically handles extraction criteria,
    consolidation rules, and memory persistence.
    
    Args:
        farmer_id: Unique farmer identifier
        question: Farmer's question
        advice: System's advice
        context: Full context data (weather, land, memory)
    
    Raises:
        ValueError: If AgentCore Memory not configured
        ClientError: If AWS API call fails
    
    Requirements: 2.1, 2.3, 5.3, 11.7
    """
    if not Config.AGENTCORE_AGENT_ID or not Config.AGENTCORE_ALIAS_ID:
        # Skip storage if not configured (graceful degradation)
        print(f"AgentCore Memory not configured, skipping storage for farmer {farmer_id}")
        return
    
    try:
        # Log cross-region invocation if applicable
        if Config.AGENTCORE_REGION != Config.AWS_REGION:
            print(f"INFO: Storing interaction to Bedrock Agent in {Config.AGENTCORE_REGION} from Lambda in {Config.AWS_REGION}")
        
        bedrock_agent_runtime = boto3.client(
            'bedrock-agent-runtime',
            region_name=Config.AGENTCORE_REGION
        )
        
        # Format interaction for AgentCore Memory
        interaction_text = _format_interaction_for_storage(
            question, advice, context
        )
        
        # Store in AgentCore Memory (automatic consolidation)
        bedrock_agent_runtime.invoke_agent(
            agentId=Config.AGENTCORE_AGENT_ID,
            agentAliasId=Config.AGENTCORE_ALIAS_ID,
            sessionId=farmer_id,
            inputText=interaction_text
        )
    
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        # Provide actionable error messages
        if error_code == 'AccessDeniedException':
            print(f"Error storing interaction for farmer {farmer_id}: Access denied")
            print(f"  Error Code: {error_code}")
            print(f"  Message: {error_message}")
            if Config.AGENTCORE_REGION != Config.AWS_REGION:
                print(f"  Cross-region invocation detected (Lambda: {Config.AWS_REGION}, Agent: {Config.AGENTCORE_REGION})")
                print(f"  Check IAM policy allows cross-region invocation")
        elif error_code == 'ResourceNotFoundException':
            print(f"Error storing interaction for farmer {farmer_id}: Resource not found")
            print(f"  Error Code: {error_code}")
            print(f"  Message: {error_message}")
            if Config.AGENTCORE_REGION != Config.AWS_REGION:
                print(f"  Cross-region invocation detected (Lambda: {Config.AWS_REGION}, Agent: {Config.AGENTCORE_REGION})")
                print(f"  Verify agent exists in region: {Config.AGENTCORE_REGION}")
        else:
            print(f"Error storing interaction for farmer {farmer_id}: {e}")


def _parse_agent_streaming_response(response: dict) -> str:
    """
    Parse streaming response from InvokeAgent.
    
    Args:
        response: Streaming response from bedrock-agent-runtime
    
    Returns:
        Complete text from agent response
    """
    completion = ""
    
    try:
        # InvokeAgent returns an EventStream
        event_stream = response.get('completion', [])
        
        for event in event_stream:
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    completion += chunk['bytes'].decode('utf-8')
    except Exception as e:
        print(f"Error parsing agent streaming response: {e}")
    
    return completion


def _parse_memory_text(text: str) -> dict:
    """
    Parse memory text into structured data.
    
    Args:
        text: Text response from agent
    
    Returns:
        Dictionary with recentInteractions, unresolvedIssues, consolidatedInsights
    """
    # Try to parse as JSON first
    try:
        parsed_data = json.loads(text)
        return _convert_to_memory_context_dict(parsed_data)
    except json.JSONDecodeError:
        # If not JSON, parse as natural language
        return _parse_natural_language_memory(text)


def _parse_agentcore_response(response: dict) -> dict:
    """
    Parse AgentCore Memory response into structured data.
    
    Args:
        response: Raw response from bedrock-agent-runtime
    
    Returns:
        Dictionary with recentInteractions, unresolvedIssues, consolidatedInsights
    """
    # Extract generated text from response
    output_text = response.get('output', {}).get('text', '')
    
    # Try to parse as JSON (AgentCore may return structured data)
    try:
        parsed_data = json.loads(output_text)
        return _convert_to_memory_context_dict(parsed_data)
    except json.JSONDecodeError:
        # If not JSON, parse as natural language
        return _parse_natural_language_memory(output_text)


def _convert_to_memory_context_dict(data: dict) -> dict:
    """Convert parsed JSON to MemoryContext-compatible dictionary."""
    result = {
        'recentInteractions': [],
        'unresolvedIssues': [],
        'consolidatedInsights': ConsolidatedInsights(primaryCrop='Unknown')
    }
    
    # Parse recent interactions
    for interaction in data.get('recentInteractions', []):
        result['recentInteractions'].append(Interaction(
            question=interaction.get('question', ''),
            advice=interaction.get('advice', ''),
            timestamp=interaction.get('timestamp', datetime.utcnow().isoformat())
        ))
    
    # Parse unresolved issues
    for issue in data.get('unresolvedIssues', []):
        result['unresolvedIssues'].append(UnresolvedIssue(
            issue=issue.get('issue', ''),
            crop=issue.get('crop', ''),
            reportedDate=issue.get('reportedDate', datetime.utcnow().isoformat()),
            daysSinceReport=issue.get('daysSinceReport', 0)
        ))
    
    # Parse consolidated insights
    insights_data = data.get('consolidatedInsights', {})
    result['consolidatedInsights'] = ConsolidatedInsights(
        primaryCrop=insights_data.get('primaryCrop', 'Unknown'),
        commonConcerns=insights_data.get('commonConcerns', []),
        farmerName=insights_data.get('farmerName')
    )
    
    return result


def _parse_natural_language_memory(text: str) -> dict:
    """
    Parse natural language memory response.
    
    This is a fallback when AgentCore returns unstructured text.
    """
    # Return empty memory structure
    # In production, this could use NLP to extract structured data
    return {
        'recentInteractions': [],
        'unresolvedIssues': [],
        'consolidatedInsights': ConsolidatedInsights(primaryCrop='Unknown')
    }


def _format_interaction_for_storage(
    question: str,
    advice: str,
    context: ContextData
) -> str:
    """
    Format interaction for AgentCore Memory storage.
    
    Args:
        question: Farmer's question
        advice: System's advice
        context: Full context data
    
    Returns:
        Formatted text for storage
    """
    weather_summary = (
        f"Temperature: {context.weather.current.temperature}°C, "
        f"Humidity: {context.weather.current.humidity}%, "
        f"Rain forecast: {context.weather.forecast6h.precipitationProbability}%"
    )
    
    land_summary = "No land records"
    if context.landRecords:
        land_summary = (
            f"Land: {context.landRecords.landArea}ha, "
            f"Soil: {context.landRecords.soilType}, "
            f"Crop: {context.landRecords.currentCrop or 'Unknown'}"
        )
    
    interaction_text = f"""
Farmer Question: {question}

Advice Given: {advice}

Context:
- Weather: {weather_summary}
- {land_summary}
- Timestamp: {datetime.utcnow().isoformat()}

Please store this interaction and update consolidated insights.
"""
    
    return interaction_text
