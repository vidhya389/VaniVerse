"""
Memory-First prompt construction.

Builds prompts that combine agent outputs with Memory-First priority instructions
and advice provenance requirements.
"""

import json
from typing import Dict
from src.models.context_data import ContextData
from src.models.prompts import MemoryFirstPrompt


def build_memory_first_prompt(
    question: str,
    context: ContextData,
    weather_analysis: str,
    icar_knowledge: str,
    language: str = 'hi-IN'
) -> MemoryFirstPrompt:
    """
    Construct Memory-First prompt combining specialized agent outputs.
    
    This function creates a structured prompt that:
    1. Prioritizes checking unresolved issues from conversation memory
    2. Includes outputs from Weather Analytics and ICAR Knowledge agents
    3. Requires advice provenance (explicit reasoning with context references)
    4. Formats all context data for Claude
    
    Args:
        question: Farmer's current question (transcribed text)
        context: Complete context data (weather, land records, memory)
        weather_analysis: Output from Weather Analytics Agent
        icar_knowledge: Output from ICAR Knowledge Agent
        language: Language code (e.g., 'hi-IN', 'ta-IN') for response generation
        
    Returns:
        MemoryFirstPrompt ready for Bedrock invocation
        
    Validates:
        Requirements 2.2, 13.1, 13.2, 13.3, 13.4, 13.5, 13.6
    """
    # Build system prompt with Memory-First instructions and provenance requirements
    system_prompt = _build_system_prompt(weather_analysis, icar_knowledge, context, language)
    
    # Create the prompt object
    prompt = MemoryFirstPrompt(
        systemPrompt=system_prompt,
        context=context,
        currentQuestion=question,
        agentOutputs={
            'weather_analysis': weather_analysis,
            'icar_knowledge': icar_knowledge
        }
    )
    
    return prompt


def _build_system_prompt(
    weather_analysis: str,
    icar_knowledge: str,
    context: ContextData,
    language: str = 'hi-IN'
) -> str:
    """
    Build the system prompt with Memory-First priority and provenance requirements.
    
    Args:
        weather_analysis: Weather Analytics Agent output
        icar_knowledge: ICAR Knowledge Agent output
        context: Complete context data
        language: Language code for response generation
        
    Returns:
        Complete system prompt string
    """
    # Map language codes to language names
    language_names = {
        'hi-IN': 'Hindi (हिन्दी)',
        'ta-IN': 'Tamil (தமிழ்)',
        'te-IN': 'Telugu (తెలుగు)',
        'kn-IN': 'Kannada (ಕನ್ನಡ)',
        'mr-IN': 'Marathi (मराठी)',
        'bn-IN': 'Bengali (বাংলা)',
        'gu-IN': 'Gujarati (ગુજરાતી)',
        'pa-IN': 'Punjabi (ਪੰਜਾਬੀ)',
        'ml-IN': 'Malayalam (മലയാളം)',
        'or-IN': 'Odia (ଓଡ଼ିଆ)'
    }
    
    language_name = language_names.get(language, 'Hindi')
    
    # Format context data for inclusion in system prompt
    weather_summary = _format_weather_context(context.weather)
    land_summary = _format_land_context(context.landRecords)
    memory_summary = _format_memory_context(context.memory)
    
    system_prompt = f"""
You are VaniVerse, a proactive agricultural advisor for Indian farmers. You act as a concerned mentor, not just an information provider.

CRITICAL LANGUAGE INSTRUCTION: You MUST respond ONLY in {language_name}. The farmer is speaking {language_name}, so your entire response must be in {language_name}. Do NOT use English or any other language.

CRITICAL LENGTH CONSTRAINT: Your response MUST be under 4000 characters (including spaces). This is a hard limit for text-to-speech conversion. Keep your response concise and focused. If you need to provide detailed information, prioritize the most important points.

CRITICAL INSTRUCTIONS - FOLLOW IN ORDER:

1. MEMORY-FIRST PRIORITY (CRITICAL - MUST FOLLOW):
   - Check the previous conversations in the Memory section above
   - If there any previous conversation:
     * You MUST start your response by asking briefly about the last conversation
     * Example: "வணக்கம்! முதலில், கடந்த வாரம் நீங்கள் குறிப்பிட்ட தக்காளி இலை சுருள் பிரச்சனை எப்படி உள்ளது? அது சரியாகிவிட்டதா?"
     * Example: "नमस्ते! पहले बताइए, पिछले हफ्ते आपने जो टमाटर की पत्ती मुड़ने की समस्या बताई थी, वह कैसी है? क्या वह ठीक हो गई?"
     * Only AFTER asking about the previous issue, then answer their current question
   - If there are NO previous issues:
     * Proceed directly to answering the current question and no need to inform that are no previous unresolved issues.
   - This is MANDATORY - previous issues take priority over new questions

2. SPECIALIZED AGENT INPUTS:
   
   Weather Analysis (from Weather Analytics Agent):
   {weather_analysis}
   
   ICAR Knowledge (from ICAR Knowledge Agent):
   {icar_knowledge}

3. CURRENT CONTEXT:
   {weather_summary}
   {land_summary}
   {memory_summary}

4. ADVICE PROVENANCE (CRITICAL):
   - ALWAYS explain WHY you're giving specific advice
   - Reference the specific context factors that influenced your recommendation
   - Examples:
     * "Because your soil record shows low nitrogen..."
     * "Since the weather forecast predicts rain in 4 hours..."
     * "Given that you mentioned pest issues last week..."
   - Every recommendation must include at least one provenance statement
   - Build trust through transparency - farmers need to understand your reasoning

5. RESPONSE STYLE:
   - Speak naturally in {language_name}
   - Use simple, practical terms
   - Provide specific, actionable steps (2-3 key points maximum)
   - Explain WHY, not just WHAT
   - Be conversational but professional
   - Show concern for the farmer's crops and livelihood
   - KEEP IT CONCISE - under 5000 characters total

6. SAFETY:
   - Your advice will be verified against weather conditions
   - If suggesting pesticide application, mention timing considerations
   - If suggesting irrigation, mention temperature and evaporation factors
   - Always consider the farmer's safety and resource efficiency

REMEMBER: 
- Your response must be ENTIRELY in {language_name}. Do not mix languages.
- Your response must be UNDER 5000 characters (this is critical for audio conversion)
- Focus on the most important 2-3 actionable points
"""
    
    return system_prompt


def _format_weather_context(weather) -> str:
    """
    Format weather data for system prompt.
    
    Args:
        weather: WeatherData object
        
    Returns:
        Formatted weather context string
    """
    return f"""Weather:
   - Current: {weather.current.temperature}°C, {weather.current.humidity}% humidity, {weather.current.windSpeed} km/h wind
   - 6h Forecast: {weather.forecast6h.precipitationProbability}% rain probability, {weather.forecast6h.expectedRainfall}mm expected rainfall
   - Temperature forecast: {weather.forecast6h.temperature}°C"""


def _format_land_context(land_records) -> str:
    """
    Format land records for system prompt.
    
    Args:
        land_records: LandRecords object or None
        
    Returns:
        Formatted land context string
    """
    if not land_records:
        return "Land: No land records available (farmer not linked to AgriStack)"
    
    context = f"""Land:
   - Area: {land_records.landArea} hectares
   - Soil Type: {land_records.soilType}"""
    
    if land_records.currentCrop:
        context += f"\n   - Current Crop: {land_records.currentCrop}"
    
    if land_records.cropHistory:
        recent_crops = [f"{ch.crop} ({ch.season} {ch.year})" for ch in land_records.cropHistory[:3]]
        context += f"\n   - Recent Crops: {', '.join(recent_crops)}"
    
    return context


def _format_memory_context(memory) -> str:
    """
    Format memory context for system prompt.
    
    Args:
        memory: MemoryContext object
        
    Returns:
        Formatted memory context string
    """
    context = "Memory:\n"
    
    # Recent interactions
    if memory.recentInteractions:
        context += f"   - Recent Interactions: {len(memory.recentInteractions)} in history\n"
        # Include the most recent interaction for context
        if memory.recentInteractions:
            latest = memory.recentInteractions[-1]
            context += f"     Last question: \"{latest.question[:100]}...\"\n"
    else:
        context += "   - Recent Interactions: None (first-time user)\n"
    
    # Unresolved issues (CRITICAL for Memory-First)
    if memory.unresolvedIssues:
        context += f"   - UNRESOLVED ISSUES ({len(memory.unresolvedIssues)}):\n"
        for issue in memory.unresolvedIssues:
            context += f"     * {issue.issue} on {issue.crop} (reported {issue.daysSinceReport} days ago)\n"
    else:
        context += "   - Unresolved Issues: None\n"
    
    # Consolidated insights
    insights = memory.consolidatedInsights
    context += f"   - Primary Crop: {insights.primaryCrop}\n"
    
    if insights.farmerName:
        context += f"   - Farmer Name: {insights.farmerName}\n"
    
    if insights.commonConcerns:
        context += f"   - Common Concerns: {', '.join(insights.commonConcerns)}\n"
    
    return context


def format_prompt_for_bedrock(prompt: MemoryFirstPrompt) -> Dict:
    """
    Format MemoryFirstPrompt for AWS Bedrock API invocation.
    
    Converts the structured prompt into the format expected by Claude via Bedrock.
    
    Args:
        prompt: MemoryFirstPrompt object
        
    Returns:
        Dictionary ready for Bedrock invoke_model API
    """
    # Convert context to JSON for the user message
    context_json = prompt.context.model_dump()
    
    request_body = {
        'anthropic_version': 'bedrock-2023-05-31',
        'max_tokens': 1000,
        'system': prompt.systemPrompt,
        'messages': [
            {
                'role': 'user',
                'content': f"""
Context Data:
{json.dumps(context_json, indent=2)}

Farmer's Question: {prompt.currentQuestion}

Remember: 
1. Check for unresolved issues FIRST and ask about them before answering
2. Include provenance (explain WHY with specific context references)
3. Be conversational and show concern for the farmer's situation
"""
            }
        ]
    }
    
    return request_body


def invoke_bedrock(prompt: MemoryFirstPrompt, timeout: int = 30) -> str:
    """
    Invoke LLM (Claude or Amazon Nova) via AWS Bedrock.
    
    This function sends the Memory-First prompt to the configured model via Bedrock
    and returns the generated agricultural advice text. It handles API errors, timeouts,
    and response parsing for both Claude and Nova formats.
    
    Args:
        prompt: MemoryFirstPrompt object containing system prompt, context, and question
        timeout: Maximum time in seconds to wait for response (default: 30)
        
    Returns:
        Generated advice text from the model
        
    Raises:
        ValueError: If the response format is invalid or empty
        RuntimeError: If Bedrock API call fails after retries
        TimeoutError: If the API call exceeds the timeout
        
    Validates:
        Requirements 11.4
    """
    from src.config import Config as AppConfig
    
    # Use mock LLM if configured (for testing without Bedrock model access)
    if AppConfig.USE_MOCK_LLM:
        return _mock_llm_response(prompt)
    
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError, ReadTimeoutError
    
    # Configure boto3 client with timeout
    boto_config = Config(
        region_name=AppConfig.AWS_REGION,
        read_timeout=timeout,
        connect_timeout=10,
        retries={'max_attempts': 3, 'mode': 'adaptive'}
    )
    
    try:
        # Initialize Bedrock Runtime client
        bedrock_runtime = boto3.client('bedrock-runtime', config=boto_config)
        
        # Determine model type and format request accordingly
        model_id = AppConfig.MODEL_ID
        is_nova = 'nova' in model_id.lower()
        is_claude = 'claude' in model_id.lower() or 'anthropic' in model_id.lower()
        
        if is_nova:
            request_body = _format_prompt_for_nova(prompt)
        elif is_claude:
            request_body = format_prompt_for_bedrock(prompt)
        else:
            # Default to Claude format for unknown models
            request_body = format_prompt_for_bedrock(prompt)
        
        # Invoke model
        response = bedrock_runtime.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body),
            contentType='application/json',
            accept='application/json'
        )
        
        # Parse response
        response_body = json.loads(response['body'].read())
        
        # Extract advice text based on model type
        if is_nova:
            advice_text = _extract_nova_response(response_body)
        elif is_claude:
            advice_text = _extract_claude_response(response_body)
        else:
            # Try Claude format first, then Nova
            try:
                advice_text = _extract_claude_response(response_body)
            except (ValueError, KeyError):
                advice_text = _extract_nova_response(response_body)
        
        if not advice_text or not advice_text.strip():
            raise ValueError("Model response has empty advice text")
        
        return advice_text.strip()
        
    except ReadTimeoutError as e:
        raise TimeoutError(
            f"Bedrock API call timed out after {timeout} seconds. "
            f"The model may be taking too long to generate a response."
        ) from e
    
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        # Handle specific error codes
        if error_code == 'ThrottlingException':
            raise RuntimeError(
                "Bedrock API rate limit exceeded. Please retry after a short delay."
            ) from e
        elif error_code == 'ModelNotReadyException':
            raise RuntimeError(
                "Model is not ready. Please retry in a few moments."
            ) from e
        elif error_code == 'ValidationException':
            raise ValueError(
                f"Invalid request to Bedrock API: {error_message}"
            ) from e
        elif error_code == 'AccessDeniedException':
            raise RuntimeError(
                "Access denied to Bedrock API. Check IAM permissions and model access."
            ) from e
        else:
            raise RuntimeError(
                f"Bedrock API error ({error_code}): {error_message}"
            ) from e
    
    except json.JSONDecodeError as e:
        raise ValueError(
            "Failed to parse Bedrock API response as JSON. "
            "The response may be malformed."
        ) from e
    
    except ValueError:
        # Re-raise ValueError exceptions without wrapping
        raise
    
    except KeyError as e:
        raise ValueError(
            f"Bedrock response missing expected field: {e}"
        ) from e
    
    except Exception as e:
        # Catch-all for unexpected errors
        raise RuntimeError(
            f"Unexpected error invoking Bedrock: {type(e).__name__}: {str(e)}"
        ) from e


def _format_prompt_for_nova(prompt: MemoryFirstPrompt) -> Dict:
    """
    Format MemoryFirstPrompt for Amazon Nova models.
    
    Nova uses a different message format than Claude.
    
    Args:
        prompt: MemoryFirstPrompt object
        
    Returns:
        Dictionary ready for Nova via Bedrock
    """
    # Convert context to JSON
    context_json = prompt.context.model_dump()
    
    # Combine system prompt and user message for Nova
    full_message = f"""{prompt.systemPrompt}

Context Data:
{json.dumps(context_json, indent=2)}

Farmer's Question: {prompt.currentQuestion}

Remember: 
1. Check for unresolved issues FIRST and ask about them before answering
2. Include provenance (explain WHY with specific context references)
3. Be conversational and show concern for the farmer's situation
"""
    
    request_body = {
        'messages': [
            {
                'role': 'user',
                'content': [
                    {
                        'text': full_message
                    }
                ]
            }
        ],
        'inferenceConfig': {
            'max_new_tokens': 1000,
            'temperature': 0.7,
            'top_p': 0.9
        }
    }
    
    return request_body


def _extract_claude_response(response_body: Dict) -> str:
    """Extract text from Claude response format."""
    if 'content' not in response_body:
        raise ValueError("Response missing 'content' field")
    
    content_blocks = response_body['content']
    if not content_blocks or len(content_blocks) == 0:
        raise ValueError("Response has empty content blocks")
    
    return content_blocks[0].get('text', '')


def _extract_nova_response(response_body: Dict) -> str:
    """Extract text from Amazon Nova response format."""
    if 'output' in response_body:
        output = response_body['output']
        if 'message' in output:
            message = output['message']
            if 'content' in message and len(message['content']) > 0:
                return message['content'][0].get('text', '')
    
    raise ValueError("Could not extract text from Nova response format")



def _mock_llm_response(prompt: MemoryFirstPrompt) -> str:
    """
    Generate a mock LLM response for testing without Bedrock model access.
    
    Args:
        prompt: MemoryFirstPrompt object
        
    Returns:
        Mock agricultural advice text in the appropriate language
    """
    question = prompt.currentQuestion.lower()
    weather = prompt.context.weather
    
    # Detect language from question
    language = 'hi-IN'  # Default to Hindi
    if any(char in question for char in ['मौसम', 'फसल', 'खेत', 'कीट', 'खाद']):
        language = 'hi-IN'
    elif any(char in question for char in ['வானிலை', 'பயிர்', 'வயல்']):
        language = 'ta-IN'
    elif any(char in question for char in ['వాతావరణం', 'పంట', 'పొలం']):
        language = 'te-IN'
    elif any(char in question for char in ['ಹವಾಮಾನ', 'ಬೆಳೆ', 'ಹೊಲ']):
        language = 'kn-IN'
    
    # Generate response in appropriate language
    if language == 'hi-IN':
        if 'weather' in question or 'rain' in question or 'मौसम' in question or 'बारिश' in question:
            return f"""वर्तमान मौसम की स्थिति के आधार पर (तापमान: {weather.current.temperature}°C, आर्द्रता: {weather.current.humidity}%), यहाँ मेरी सलाह है:

मौसम पूर्वानुमान अगले 6 घंटों में {weather.forecast6h.precipitationProbability}% बारिश की संभावना दिखाता है। इन परिस्थितियों को देखते हुए, मैं सुझाव देता हूं:

1. यदि आप कीटनाशक छिड़काव की योजना बना रहे हैं, तो संभावित बारिश के बाद तक प्रतीक्षा करें
2. मिट्टी की नमी के स्तर की सावधानीपूर्वक निगरानी करें
3. अपने खेतों में उचित जल निकासी सुनिश्चित करें

यह सलाह वर्तमान मौसम डेटा पर आधारित है जो {weather.forecast6h.expectedRainfall}mm अपेक्षित वर्षा दिखाता है।"""
        
        elif 'pest' in question or 'disease' in question or 'कीट' in question or 'रोग' in question:
            return """कीट प्रबंधन के लिए, मैं सुझाव देता हूं:

1. शीघ्र पता लगाने के लिए अपनी फसलों की नियमित निगरानी करें
2. एकीकृत कीट प्रबंधन (IPM) प्रथाओं का उपयोग करें
3. पहली रक्षा पंक्ति के रूप में नीम-आधारित जैविक कीटनाशकों पर विचार करें
4. उचित खेत स्वच्छता बनाए रखें

यह सलाह टिकाऊ कीट प्रबंधन के लिए ICAR दिशानिर्देशों का पालन करती है।"""
        
        elif 'fertilizer' in question or 'खाद' in question or 'उर्वरक' in question:
            return """उर्वरक अनुप्रयोग के लिए:

1. पोषक तत्वों की आवश्यकताओं को निर्धारित करने के लिए मिट्टी परीक्षण करवाएं
2. फसल की वृद्धि अवस्था के आधार पर उर्वरक लगाएं
3. अपनी फसल के लिए उपयुक्त संतुलित NPK अनुपात का उपयोग करें
4. खाद जैसे जैविक विकल्पों पर विचार करें

यह सिफारिश ICAR मृदा स्वास्थ्य प्रबंधन दिशानिर्देशों पर आधारित है।"""
        
        else:
            return f"""आपके प्रश्न के लिए धन्यवाद: "{prompt.currentQuestion}"

उपलब्ध संदर्भ के आधार पर:
- वर्तमान तापमान: {weather.current.temperature}°C
- आर्द्रता: {weather.current.humidity}%
- आपकी प्रमुख फसल: {prompt.context.memory.consolidatedInsights.primaryCrop}

मैं इस मामले पर विशिष्ट मार्गदर्शन के लिए स्थानीय कृषि विस्तार अधिकारियों से परामर्श करने की सलाह देता हूं। इस बीच, सुनिश्चित करें कि आप अपनी फसल के लिए अच्छी कृषि प्रथाओं का पालन कर रहे हैं और मौसम की स्थिति की नियमित निगरानी कर रहे हैं।"""
    
    # For other languages, return English for now (can be expanded)
    else:
        return f"""Based on the current weather conditions (temperature: {weather.current.temperature}°C, humidity: {weather.current.humidity}%), here's my advice:

The forecast shows {weather.forecast6h.precipitationProbability}% chance of rain in the next 6 hours. Given these conditions, I recommend monitoring your crops carefully and planning field activities accordingly.

This advice is based on the current weather data."""
