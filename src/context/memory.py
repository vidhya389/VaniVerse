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
    
    NOTE: Bedrock Agents with SESSION_SUMMARY memory automatically have access
    to conversation history within the same sessionId. This function uses the
    get_agent_memory API to retrieve stored session summaries directly.
    
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
            print(f"INFO: Fetching memory from Bedrock Agent in {Config.AGENTCORE_REGION} from Lambda in {Config.AWS_REGION}")
        
        # Configure client with shorter timeout for memory fetch
        from botocore.config import Config as BotoConfig
        boto_config = BotoConfig(
            read_timeout=30,  # 30 second read timeout
            connect_timeout=10,  # 10 second connect timeout
            retries={'max_attempts': 2, 'mode': 'standard'}
        )
        
        bedrock_agent_runtime = boto3.client(
            'bedrock-agent-runtime',
            region_name=Config.AGENTCORE_REGION,
            config=boto_config
        )
        
        # Use get_agent_memory API to retrieve session summaries directly
        if Config.AGENTCORE_MEMORY_ID:
            print(f"Fetching memory using memoryId: {Config.AGENTCORE_MEMORY_ID} for farmer {farmer_id}")
            
            try:
                response = bedrock_agent_runtime.get_agent_memory(
                    agentId=Config.AGENTCORE_AGENT_ID,
                    agentAliasId=Config.AGENTCORE_ALIAS_ID,
                    memoryId=Config.AGENTCORE_MEMORY_ID,
                    memoryType='SESSION_SUMMARY',
                    maxItems=5  # Get last 5 sessions
                )
                
                # Parse memory contents
                memory_contents = response.get('memoryContents', [])
                
                if memory_contents:
                    print(f"Found {len(memory_contents)} memory sessions")
                    
                    # Log all sessions for debugging
                    print(f"All sessions in memory:")
                    for idx, content in enumerate(memory_contents, 1):
                        session_summary = content.get('sessionSummary', {})
                        session_id = session_summary.get('sessionId', 'Unknown')
                        session_start = session_summary.get('sessionStartTime', 'Unknown')
                        summary_preview = session_summary.get('summaryText', '')[:150]
                        print(f"  Session {idx}: ID={session_id}, Start={session_start}")
                        print(f"    Summary preview: {summary_preview}...")
                    
                    # Look for the farmer's session
                    farmer_sessions = [
                        content for content in memory_contents
                        if content.get('sessionSummary', {}).get('sessionId') == farmer_id
                    ]
                    
                    if farmer_sessions:
                        # Get the most recent session
                        latest_session = farmer_sessions[0].get('sessionSummary', {})
                        summary_text = latest_session.get('summaryText', '')
                        session_start = latest_session.get('sessionStartTime', 'Unknown')
                        
                        print(f"Found session summary for farmer {farmer_id}")
                        print(f"  Session start time: {session_start}")
                        print(f"  Full summary text:")
                        print(f"  {'-'*60}")
                        print(f"  {summary_text}")
                        print(f"  {'-'*60}")
                        
                        # Parse the summary text into structured memory
                        memory_context = _parse_session_summary(summary_text, farmer_id)
                        
                        # Log what was parsed
                        print(f"  Parsed {len(memory_context.recentInteractions)} interactions from memory")
                        for i, interaction in enumerate(memory_context.recentInteractions, 1):
                            print(f"    Interaction {i}:")
                            print(f"      Question: {interaction.question[:100]}...")
                            print(f"      Advice: {interaction.advice[:100]}...")
                        
                        return memory_context
                    else:
                        print(f"No session found for farmer {farmer_id} in memory")
                else:
                    print(f"No memory contents found")
                    
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                if error_code == 'ValidationException':
                    print(f"get_agent_memory API not available or incorrect parameters: {e}")
                else:
                    raise
        
        # Return empty memory if nothing found
        return MemoryContext()
    
    except Exception as e:
        # Handle timeout errors specifically
        error_str = str(e)
        if 'timed out' in error_str.lower() or 'timeout' in error_str.lower():
            print(f"Timeout fetching memory for farmer {farmer_id}: {e}")
            print(f"  Memory fetch timed out after 30 seconds")
            print(f"  Continuing without memory context (graceful degradation)")
        elif isinstance(e, ClientError):
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
        
        # Configure client with timeout for storage
        from botocore.config import Config as BotoConfig
        boto_config = BotoConfig(
            read_timeout=20,  # 20 second read timeout for storage
            connect_timeout=10,  # 10 second connect timeout
            retries={'max_attempts': 2, 'mode': 'standard'}
        )
        
        bedrock_agent_runtime = boto3.client(
            'bedrock-agent-runtime',
            region_name=Config.AGENTCORE_REGION,
            config=boto_config
        )
        
        # Format interaction for AgentCore Memory
        interaction_text = _format_interaction_for_storage(
            question, advice, context
        )
        
        # Log what we're storing (first 500 chars for debugging)
        print(f"Storing interaction for farmer {farmer_id}:")
        print(f"  Text preview (first 500 chars): {interaction_text[:500]}...")
        
        # Build invoke_agent parameters
        invoke_params = {
            'agentId': Config.AGENTCORE_AGENT_ID,
            'agentAliasId': Config.AGENTCORE_ALIAS_ID,
            'sessionId': farmer_id,  # Use farmer_id as session ID for conversation continuity
            'inputText': interaction_text
        }
        
        # Add memoryId if configured (for consistent memory storage)
        if Config.AGENTCORE_MEMORY_ID:
            invoke_params['memoryId'] = Config.AGENTCORE_MEMORY_ID
            print(f"Using memoryId: {Config.AGENTCORE_MEMORY_ID} for farmer {farmer_id}")
        
        # Store in AgentCore Memory (automatic consolidation)
        response = bedrock_agent_runtime.invoke_agent(**invoke_params)
        
        # Consume the response stream to ensure storage completes
        _parse_agent_streaming_response(response)
        
        print(f"Interaction stored in AgentCore Memory for farmer {farmer_id}")
    
    except Exception as e:
        # Handle timeout errors specifically
        error_str = str(e)
        if 'timed out' in error_str.lower() or 'timeout' in error_str.lower():
            print(f"Timeout storing interaction for farmer {farmer_id}: {e}")
            print(f"  Storage timed out after 20 seconds")
            print(f"  Interaction may still be stored (async processing)")
        elif isinstance(e, ClientError):
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
        else:
            print(f"Error storing interaction for farmer {farmer_id}: {e}")


def _parse_session_summary(summary_text: str, farmer_id: str) -> MemoryContext:
    """
    Parse session summary text into MemoryContext.
    
    Args:
        summary_text: Summary text from SESSION_SUMMARY memory
        farmer_id: Farmer identifier
    
    Returns:
        MemoryContext with parsed information
    """
    # Extract user goals and assistant actions from summary
    interactions = []
    
    # Simple parsing - look for user_goal and assistant_action tags
    import re
    user_goals = re.findall(r'<user_goal>(.*?)</user_goal>', summary_text, re.DOTALL)
    assistant_actions = re.findall(r'<assistant_action>(.*?)</assistant_action>', summary_text, re.DOTALL)
    
    print(f"DEBUG: Parsing session summary for {farmer_id}")
    print(f"  Found {len(user_goals)} user goals")
    print(f"  Found {len(assistant_actions)} assistant actions")
    
    # Pair up goals and actions as interactions
    for i in range(min(len(user_goals), len(assistant_actions))):
        question = user_goals[i].strip()
        advice = assistant_actions[i].strip()
        
        print(f"  Pairing interaction {i+1}:")
        print(f"    Goal: {question[:80]}...")
        print(f"    Action: {advice[:80]}...")
        
        interactions.append(Interaction(
            question=question,
            advice=advice,
            timestamp=datetime.utcnow().isoformat()
        ))
    
    print(f"  Created {len(interactions)} interaction objects")
    
    return MemoryContext(
        recentInteractions=interactions[:3],  # Keep last 3 interactions
        unresolvedIssues=[],  # TODO: Parse unresolved issues if needed
        consolidatedInsights=ConsolidatedInsights(primaryCrop='Unknown')
    )


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
        
        # Set a timeout for reading the stream
        import time
        start_time = time.time()
        max_stream_time = 25  # 25 seconds max for stream reading
        
        for event in event_stream:
            # Check if we've exceeded the stream reading timeout
            if time.time() - start_time > max_stream_time:
                print(f"Warning: Stream reading exceeded {max_stream_time}s, stopping")
                break
                
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    completion += chunk['bytes'].decode('utf-8')
    except Exception as e:
        error_str = str(e)
        if 'timed out' in error_str.lower() or 'timeout' in error_str.lower():
            print(f"Timeout reading agent stream: {e}")
        else:
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
    
    Emphasizes key entities (plant names, crop names, symptoms) to ensure
    they are preserved in session summaries.
    
    Args:
        question: Farmer's question
        advice: System's advice
        context: Full context data
    
    Returns:
        Formatted text for storage with emphasized key details
    """
    # Extract key entities from question to emphasize them
    import re
    
    # Common plant/crop names to look for (case-insensitive)
    plant_patterns = [
        r'\b(hibiscus|rose|marigold|jasmine|tulsi|neem)\b',
        r'\b(tomato|potato|onion|chili|pepper|brinjal|eggplant)\b',
        r'\b(rice|wheat|maize|corn|millet|sorghum|bajra)\b',
        r'\b(cotton|sugarcane|groundnut|peanut|soybean)\b',
        r'\b(mango|banana|papaya|guava|coconut|cashew)\b'
    ]
    
    key_entities = []
    question_lower = question.lower()
    
    for pattern in plant_patterns:
        matches = re.findall(pattern, question_lower, re.IGNORECASE)
        key_entities.extend(matches)
    
    # Build entity emphasis string
    entity_emphasis = ""
    if key_entities:
        unique_entities = list(set(key_entities))
        entity_emphasis = f"\n\nKEY ENTITIES (MUST PRESERVE IN SUMMARY): {', '.join(unique_entities).upper()}"
    
    weather_summary = (
        f"Temperature: {context.weather.current.temperature}°C, "
        f"Humidity: {context.weather.current.humidity}%, "
        f"Rain forecast: {context.weather.forecast6h.precipitationProbability}%"
    )
    
    land_summary = "No land records"
    crop_emphasis = ""
    if context.landRecords:
        land_summary = (
            f"Land: {context.landRecords.landArea}ha, "
            f"Soil: {context.landRecords.soilType}, "
            f"Crop: {context.landRecords.currentCrop or 'Unknown'}"
        )
        if context.landRecords.currentCrop:
            crop_emphasis = f"\n\nFARMER'S PRIMARY CROP (MUST PRESERVE): {context.landRecords.currentCrop.upper()}"
    
    interaction_text = f"""
IMPORTANT: When creating session summary, PRESERVE specific plant names, crop names, and symptoms exactly as mentioned.

Farmer Question: {question}{entity_emphasis}

Advice Given: {advice}

Context:
- Weather: {weather_summary}
- {land_summary}{crop_emphasis}
- Timestamp: {datetime.utcnow().isoformat()}

STORAGE INSTRUCTIONS:
1. Store this interaction with ALL specific details preserved
2. In session summary, include the exact plant/crop name (e.g., "hibiscus leaves" not "plant leaves")
3. Include specific symptoms mentioned (e.g., "turning white" not just "problem")
4. Update consolidated insights with specific crop and issue details
"""
    
    return interaction_text
