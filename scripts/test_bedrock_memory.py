#!/usr/bin/env python3
"""
Test Bedrock Agent Memory functionality
"""

import os
import sys
import json
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
AGENT_ID = os.getenv('AGENTCORE_AGENT_ID', '')
ALIAS_ID = os.getenv('AGENTCORE_ALIAS_ID', '')
MEMORY_ID = os.getenv('AGENTCORE_MEMORY_ID', '')
REGION = os.getenv('AGENTCORE_REGION', 'us-east-1')
SESSION_ID = 'FARMER_TEST_12345'

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def print_success(text):
    print(f"✓ {text}")

def print_error(text):
    print(f"✗ {text}")

def print_info(text):
    print(f"  {text}")

def test_agent_exists():
    """Test if agent exists"""
    print_header("Test 1: Check if Agent Exists")
    
    try:
        client = boto3.client('bedrock-agent', region_name=REGION)
        response = client.get_agent(agentId=AGENT_ID)
        
        print_success("Agent exists")
        print_info(f"Agent Name: {response['agent']['agentName']}")
        print_info(f"Agent Status: {response['agent']['agentStatus']}")
        return True
    except ClientError as e:
        print_error(f"Agent not found: {e}")
        return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_alias_exists():
    """Test if alias exists"""
    print_header("Test 2: Check if Alias Exists")
    
    try:
        client = boto3.client('bedrock-agent', region_name=REGION)
        response = client.get_agent_alias(
            agentId=AGENT_ID,
            agentAliasId=ALIAS_ID
        )
        
        print_success("Alias exists")
        print_info(f"Alias Name: {response['agentAlias']['agentAliasName']}")
        print_info(f"Alias Status: {response['agentAlias']['agentAliasStatus']}")
        return True
    except ClientError as e:
        print_error(f"Alias not found: {e}")
        return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_memory_configuration():
    """Test if agent has memory configured"""
    print_header("Test 2.5: Check Memory Configuration")
    
    try:
        client = boto3.client('bedrock-agent', region_name=REGION)
        response = client.get_agent(agentId=AGENT_ID)
        
        # Check if memory configuration exists
        memory_config = response.get('agent', {}).get('memoryConfiguration')
        
        if memory_config:
            print_success("Agent has memory configuration")
            print_info(f"Memory Config: {json.dumps(memory_config, indent=2)}")
            
            # Check for enabled memory types
            enabled_types = memory_config.get('enabledMemoryTypes', [])
            if enabled_types:
                print_info(f"Enabled memory types: {', '.join(enabled_types)}")
            else:
                print_error("No memory types enabled!")
                print_info("Agent needs SESSION_SUMMARY memory type enabled")
                return False
        else:
            print_error("Agent has NO memory configuration!")
            print_info("You need to configure memory in the AWS Console:")
            print_info("1. Go to Amazon Bedrock > Agents")
            print_info("2. Select your agent")
            print_info("3. Edit agent settings")
            print_info("4. Enable 'Memory' and configure SESSION_SUMMARY")
            return False
        
        return True
        
    except ClientError as e:
        print_error(f"Error checking memory config: {e}")
        return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_invoke_agent():
    """Test invoking the agent"""
    print_header("Test 3: Invoke Agent (Store Interaction)")
    
    try:
        client = boto3.client('bedrock-agent-runtime', region_name=REGION)
        
        input_text = "Store this: Farmer asked about rice planting. Advised to plant in June-July."
        
        # Build parameters
        params = {
            'agentId': AGENT_ID,
            'agentAliasId': ALIAS_ID,
            'sessionId': SESSION_ID,
            'inputText': input_text,
            'enableTrace': True  # Enable trace to see what's happening
        }
        
        # Add memory ID if configured
        if MEMORY_ID:
            params['memoryId'] = MEMORY_ID
            print_info(f"Using memoryId: {MEMORY_ID}")
        
        print_info(f"Invoking agent in region: {REGION}")
        print_info(f"Session ID: {SESSION_ID}")
        
        response = client.invoke_agent(**params)
        
        # Read the streaming response
        completion = ""
        traces = []
        event_stream = response.get('completion', [])
        
        for event in event_stream:
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    completion += chunk['bytes'].decode('utf-8')
            if 'trace' in event:
                traces.append(event['trace'])
        
        print_success("Agent invoked successfully")
        print_info(f"Response preview: {completion[:200]}...")
        
        # Show trace info if available
        if traces:
            print_info(f"Trace events captured: {len(traces)}")
        
        return True
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        print_error(f"Failed to invoke agent")
        print_info(f"Error Code: {error_code}")
        print_info(f"Error Message: {error_msg}")
        return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_retrieve_memory():
    """Test retrieving memory"""
    print_header("Test 4: Retrieve Memory")
    
    try:
        client = boto3.client('bedrock-agent-runtime', region_name=REGION)
        
        input_text = "What did the farmer ask about in our previous conversation?"
        
        # Build parameters
        params = {
            'agentId': AGENT_ID,
            'agentAliasId': ALIAS_ID,
            'sessionId': SESSION_ID,
            'inputText': input_text,
            'enableTrace': True
        }
        
        # Add memory ID if configured
        if MEMORY_ID:
            params['memoryId'] = MEMORY_ID
        
        print_info(f"Retrieving memory for session: {SESSION_ID}")
        
        response = client.invoke_agent(**params)
        
        # Read the streaming response
        completion = ""
        traces = []
        event_stream = response.get('completion', [])
        
        for event in event_stream:
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    completion += chunk['bytes'].decode('utf-8')
            if 'trace' in event:
                traces.append(event['trace'])
        
        print_success("Memory retrieved successfully")
        print("\nMemory Content:")
        print("-" * 60)
        print(completion)
        print("-" * 60)
        
        # Show trace info if available
        if traces:
            print_info(f"Trace events captured: {len(traces)}")
        
        return True
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        print_error(f"Failed to retrieve memory")
        print_info(f"Error Code: {error_code}")
        print_info(f"Error Message: {error_msg}")
        return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def main():
    print_header("Bedrock Agent Memory Test")
    
    # Validate configuration
    if not AGENT_ID:
        print_error("AGENTCORE_AGENT_ID not set in .env")
        sys.exit(1)
    
    if not ALIAS_ID:
        print_error("AGENTCORE_ALIAS_ID not set in .env")
        sys.exit(1)
    
    print_info(f"Configuration:")
    print_info(f"  Region: {REGION}")
    print_info(f"  Agent ID: {AGENT_ID}")
    print_info(f"  Alias ID: {ALIAS_ID}")
    print_info(f"  Memory ID: {MEMORY_ID or '(not set)'}")
    print_info(f"  Session ID: {SESSION_ID}")
    
    # Run tests
    results = []
    results.append(("Agent Exists", test_agent_exists()))
    results.append(("Alias Exists", test_alias_exists()))
    results.append(("Memory Configuration", test_memory_configuration()))
    results.append(("Store Interaction", test_invoke_agent()))
    
    # Wait a moment for memory to consolidate
    print_info("\nWaiting 3 seconds for memory consolidation...")
    import time
    time.sleep(3)
    
    results.append(("Retrieve Memory", test_retrieve_memory()))
    
    # Summary
    print_header("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! Your Bedrock Agent memory is working correctly.")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed. Check the errors above.")
        sys.exit(1)

if __name__ == '__main__':
    main()
