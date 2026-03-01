#!/usr/bin/env python3
"""
Diagnose why Bedrock Agent memory is not being retrieved
"""

import os
import sys
import json
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Configuration
AGENT_ID = os.getenv('AGENTCORE_AGENT_ID', '')
ALIAS_ID = os.getenv('AGENTCORE_ALIAS_ID', '')
MEMORY_ID = os.getenv('AGENTCORE_MEMORY_ID', '')
REGION = os.getenv('AGENTCORE_REGION', 'us-east-1')
SESSION_ID = 'FARMER_MEMORY_TEST'

def print_header(text):
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")

def check_agent_instructions():
    """Check what instructions the agent has"""
    print_header("Agent Instructions Check")
    
    try:
        client = boto3.client('bedrock-agent', region_name=REGION)
        response = client.get_agent(agentId=AGENT_ID)
        
        agent = response['agent']
        instruction = agent.get('instruction', '')
        
        print("Agent Instructions:")
        print("-" * 70)
        print(instruction[:500] + "..." if len(instruction) > 500 else instruction)
        print("-" * 70)
        
        # Check if instructions mention memory
        if 'memory' in instruction.lower() or 'history' in instruction.lower() or 'previous' in instruction.lower():
            print("✓ Instructions mention memory/history")
        else:
            print("⚠ Instructions DO NOT mention memory/history")
            print("  The agent may not know to use memory!")
        
        return instruction
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return None

def test_multiple_turns():
    """Test multiple conversation turns to see if memory builds up"""
    print_header("Multi-Turn Conversation Test")
    
    try:
        client = boto3.client('bedrock-agent-runtime', region_name=REGION)
        
        conversations = [
            "My name is Ravi and I grow rice.",
            "What crop did I say I grow?",
            "What is my name?"
        ]
        
        for i, input_text in enumerate(conversations, 1):
            print(f"\nTurn {i}: {input_text}")
            print("-" * 70)
            
            params = {
                'agentId': AGENT_ID,
                'agentAliasId': ALIAS_ID,
                'sessionId': SESSION_ID,
                'inputText': input_text,
                'enableTrace': True
            }
            
            if MEMORY_ID:
                params['memoryId'] = MEMORY_ID
            
            response = client.invoke_agent(**params)
            
            # Read response
            completion = ""
            event_stream = response.get('completion', [])
            
            for event in event_stream:
                if 'chunk' in event:
                    chunk = event['chunk']
                    if 'bytes' in chunk:
                        completion += chunk['bytes'].decode('utf-8')
            
            print(f"Response: {completion}")
            
            # Wait between turns
            if i < len(conversations):
                print("\nWaiting 2 seconds...")
                time.sleep(2)
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def check_session_attributes():
    """Check if we can get session attributes"""
    print_header("Session Attributes Check")
    
    try:
        client = boto3.client('bedrock-agent-runtime', region_name=REGION)
        
        # Try to get session
        try:
            response = client.get_agent_memory(
                agentId=AGENT_ID,
                agentAliasId=ALIAS_ID,
                memoryId=MEMORY_ID,
                memoryType='SESSION_SUMMARY',
                maxItems=10
            )
            
            print("✓ Memory API accessible")
            print(f"Response: {json.dumps(response, indent=2, default=str)}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationException':
                print("⚠ get_agent_memory API not available or incorrect parameters")
                print(f"  Error: {e}")
            else:
                raise
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_with_session_state():
    """Test with explicit session state"""
    print_header("Test with Session State")
    
    try:
        client = boto3.client('bedrock-agent-runtime', region_name=REGION)
        
        # First turn - store info
        print("Turn 1: Storing information...")
        params1 = {
            'agentId': AGENT_ID,
            'agentAliasId': ALIAS_ID,
            'sessionId': SESSION_ID + '_STATE',
            'inputText': "Remember this: The farmer's name is Kumar and he grows wheat on 5 hectares.",
            'enableTrace': True
        }
        
        if MEMORY_ID:
            params1['memoryId'] = MEMORY_ID
        
        response1 = client.invoke_agent(**params1)
        
        completion1 = ""
        for event in response1.get('completion', []):
            if 'chunk' in event and 'bytes' in event['chunk']:
                completion1 += event['chunk']['bytes'].decode('utf-8')
        
        print(f"Response: {completion1[:200]}...")
        
        # Wait
        print("\nWaiting 5 seconds for memory consolidation...")
        time.sleep(5)
        
        # Second turn - retrieve info
        print("\nTurn 2: Retrieving information...")
        params2 = {
            'agentId': AGENT_ID,
            'agentAliasId': ALIAS_ID,
            'sessionId': SESSION_ID + '_STATE',
            'inputText': "What is the farmer's name and what crop does he grow?",
            'enableTrace': True
        }
        
        if MEMORY_ID:
            params2['memoryId'] = MEMORY_ID
        
        response2 = client.invoke_agent(**params2)
        
        completion2 = ""
        for event in response2.get('completion', []):
            if 'chunk' in event and 'bytes' in event['chunk']:
                completion2 += event['chunk']['bytes'].decode('utf-8')
        
        print(f"Response: {completion2}")
        
        # Check if it remembered
        if 'kumar' in completion2.lower() and 'wheat' in completion2.lower():
            print("\n✓ Agent successfully retrieved memory!")
            return True
        else:
            print("\n✗ Agent did NOT retrieve memory")
            print("  The agent may not be configured to use SESSION_SUMMARY")
            return False
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    print_header("Bedrock Agent Memory Diagnosis")
    
    if not AGENT_ID or not ALIAS_ID:
        print("✗ Missing AGENTCORE_AGENT_ID or AGENTCORE_ALIAS_ID in .env")
        sys.exit(1)
    
    print(f"Agent ID: {AGENT_ID}")
    print(f"Alias ID: {ALIAS_ID}")
    print(f"Memory ID: {MEMORY_ID or '(not set)'}")
    print(f"Region: {REGION}")
    
    # Run diagnostics
    print("\n" + "="*70)
    print("DIAGNOSIS STEPS")
    print("="*70)
    
    # Step 1: Check agent instructions
    instruction = check_agent_instructions()
    
    # Step 2: Check session attributes
    check_session_attributes()
    
    # Step 3: Test multi-turn conversation
    test_multiple_turns()
    
    # Step 4: Test with explicit session state
    test_with_session_state()
    
    # Summary
    print_header("Diagnosis Summary")
    print("Possible issues:")
    print("1. Agent instructions may not tell it to use memory")
    print("2. SESSION_SUMMARY memory takes time to consolidate (not immediate)")
    print("3. Memory might only work within the same session, not across sessions")
    print("4. Agent might need a knowledge base or action group to access memory")
    print("\nRecommendations:")
    print("- Update agent instructions to explicitly mention using conversation history")
    print("- Test within the same session (multiple turns) rather than separate invocations")
    print("- Check AWS Console > Bedrock > Agents > Memory settings")
    print("- Consider using sessionAttributes for immediate context passing")

if __name__ == '__main__':
    main()
