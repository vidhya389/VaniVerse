"""
ICAR Knowledge Agent for agricultural best practices.

This specialized agent retrieves and applies ICAR (Indian Council of Agricultural Research)
guidelines to farmer questions, providing evidence-based recommendations.
"""

import json
import boto3
from typing import Optional
from src.config import Config
from src.models.context_data import LandRecords, MemoryContext


def invoke_icar_knowledge_agent(
    land_records: Optional[LandRecords],
    memory: MemoryContext,
    question: str
) -> str:
    """
    Specialized agent for ICAR agricultural knowledge retrieval.
    
    Args:
        land_records: Land records from AgriStack (optional)
        memory: Conversation memory context
        question: Farmer's question
        
    Returns:
        ICAR-based agricultural guidance as text
        
    Raises:
        Exception: If Bedrock invocation fails
    """
    # Use mock response if configured
    if Config.USE_MOCK_LLM:
        return _mock_icar_knowledge(land_records, memory)
    
    bedrock_runtime = boto3.client('bedrock-runtime', region_name=Config.AWS_REGION)
    
    system_prompt = """
You are an ICAR Knowledge Agent specializing in Indian agricultural best practices.
Your role is to retrieve and apply ICAR guidelines to farmer questions.

KNOWLEDGE BASE:
- ICAR crop-specific guidelines
- Soil management practices
- Pest and disease management
- Fertilizer recommendations
- Irrigation best practices
- Organic farming techniques

RESPONSIBILITIES:
1. Match farmer's crop and growth stage to relevant ICAR guidelines
2. Provide evidence-based recommendations
3. Cite specific ICAR publications or guidelines
4. Consider soil type and regional factors

RESPONSE FORMAT:
- Relevant ICAR Guidelines
- Crop-Specific Recommendations
- Growth Stage Considerations
- Source Citations

Be specific and cite sources when providing recommendations.
"""
    
    # Convert data to dicts for JSON serialization
    land_dict = land_records.model_dump() if land_records else None
    insights_dict = memory.consolidatedInsights.model_dump()
    
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

Land Records:
{json.dumps(land_dict, indent=2) if land_dict else "Not available"}

Farmer Context:
{json.dumps(insights_dict, indent=2)}

Farmer's Question: {question}

Provide ICAR-based agricultural guidance."""
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
Land Records:
{json.dumps(land_dict, indent=2) if land_dict else "Not available"}

Farmer Context:
{json.dumps(insights_dict, indent=2)}

Farmer's Question: {question}

Provide ICAR-based agricultural guidance.
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



def _mock_icar_knowledge(land_records: Optional[LandRecords], memory: MemoryContext) -> str:
    """Mock ICAR knowledge for testing without Bedrock."""
    crop = memory.consolidatedInsights.primaryCrop
    soil = land_records.soilType if land_records else "Unknown"
    
    return f"""ICAR AGRICULTURAL GUIDELINES:

Crop: {crop}
Soil Type: {soil}

Relevant ICAR Recommendations:
1. Soil Management: Maintain soil health through organic matter addition and proper drainage
2. Nutrient Management: Follow soil test-based fertilizer recommendations
3. Water Management: Use efficient irrigation methods to conserve water
4. Pest Management: Implement Integrated Pest Management (IPM) practices

Growth Stage Considerations:
- Monitor crop development regularly
- Adjust inputs based on growth stage requirements
- Follow crop-specific ICAR guidelines for your region

Source: ICAR Crop Production Guidelines (General Recommendations)

Note: For specific recommendations, consult your local Krishi Vigyan Kendra (KVK) or agricultural extension officer."""
