"""
Graceful degradation handlers for API failures.

Implements Requirements 3.5, 9.5, 12.5: Fallback to general advice when APIs fail
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from src.models.context_data import (
    ContextData, WeatherData, CurrentWeather, Forecast6h,
    LandRecords, MemoryContext, ConsolidatedInsights
)

logger = logging.getLogger(__name__)


def create_fallback_context(
    farmer_id: str,
    latitude: float,
    longitude: float,
    weather_available: bool = False,
    land_records_available: bool = False,
    memory_available: bool = False
) -> ContextData:
    """
    Create fallback context when APIs are unavailable.
    
    Args:
        farmer_id: Farmer identifier
        latitude: GPS latitude
        longitude: GPS longitude
        weather_available: Whether weather data is available
        land_records_available: Whether land records are available
        memory_available: Whether memory is available
        
    Returns:
        ContextData with available data and placeholders for missing data
        
    Validates:
        Requirements 3.5, 9.5, 12.5
    """
    # Create minimal weather data if unavailable
    weather = None
    if not weather_available:
        logger.warning("Weather API unavailable, using placeholder data")
        weather = WeatherData(
            current=CurrentWeather(
                temperature=25.0,  # Placeholder
                humidity=60.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=0.0,
                expectedRainfall=0.0,
                temperature=25.0,
                windSpeed=10.0
            ),
            timestamp=datetime.utcnow().isoformat()
        )
    else:
        # Weather will be fetched separately, use placeholder for now
        weather = WeatherData(
            current=CurrentWeather(
                temperature=25.0,
                humidity=60.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=0.0,
                expectedRainfall=0.0,
                temperature=25.0,
                windSpeed=10.0
            ),
            timestamp=datetime.utcnow().isoformat()
        )
    
    # Create minimal land records if unavailable
    land_records = None
    if not land_records_available:
        logger.warning("Land records unavailable, proceeding without farm data")
        land_records = None
    
    # Create minimal memory context if unavailable
    memory = MemoryContext(
        recentInteractions=[],
        unresolvedIssues=[],
        consolidatedInsights=ConsolidatedInsights(
            primaryCrop="Unknown",  # Placeholder when no data available
            commonConcerns=[],
            farmerName=None
        )
    )
    
    if not memory_available:
        logger.warning("Memory service unavailable, proceeding without history")
    
    return ContextData(
        weather=weather,
        landRecords=land_records,
        memory=memory
    )


def get_general_advice_template(language: str = 'hi-IN') -> str:
    """
    Get general agricultural advice template when specific context is unavailable.
    
    Args:
        language: Language code for the advice
        
    Returns:
        General advice text with disclaimer
        
    Validates:
        Requirements 3.5, 9.5, 12.5
    """
    # General advice templates by language
    templates = {
        'hi-IN': (
            "मुझे खेद है, मैं अभी आपके खेत की विशिष्ट जानकारी प्राप्त नहीं कर पा रहा हूं। "
            "यहां कुछ सामान्य कृषि सलाह है:\n\n"
            "1. नियमित रूप से अपनी फसल की जांच करें\n"
            "2. मौसम की स्थिति के अनुसार सिंचाई करें\n"
            "3. कीटनाशक का उपयोग करने से पहले मौसम की जांच करें\n"
            "4. स्थानीय कृषि विशेषज्ञ से सलाह लें\n\n"
            "कृपया बाद में फिर से प्रयास करें जब मैं आपके खेत की विशिष्ट जानकारी प्राप्त कर सकूं।"
        ),
        'ta-IN': (
            "மன்னிக்கவும், உங்கள் பண்ணையின் குறிப்பிட்ட தகவல்களை இப்போது பெற முடியவில்லை। "
            "இதோ சில பொதுவான விவசாய ஆலோசனைகள்:\n\n"
            "1. உங்கள் பயிரை தொடர்ந்து சரிபார்க்கவும்\n"
            "2. வானிலை நிலைமைகளுக்கு ஏற்ப நீர்ப்பாசனம் செய்யவும்\n"
            "3. பூச்சிக்கொல்லி பயன்படுத்தும் முன் வானிலையை சரிபார்க்கவும்\n"
            "4. உள்ளூர் விவசாய நிபுணரை அணுகவும்\n\n"
            "தயவுசெய்து பின்னர் மீண்டும் முயற்சிக்கவும்."
        ),
        'te-IN': (
            "క్షమించండి, మీ పొలం యొక్క నిర్దిష్ట సమాచారాన్ని ఇప్పుడు పొందలేకపోతున్నాను. "
            "ఇక్కడ కొన్ని సాధారణ వ్యవసాయ సలహాలు ఉన్నాయి:\n\n"
            "1. మీ పంటను క్రమం తప్పకుండా తనిఖీ చేయండి\n"
            "2. వాతావరణ పరిస్థితులకు అనుగుణంగా నీటిపారుదల చేయండి\n"
            "3. పురుగుమందు వాడే ముందు వాతావరణాన్ని తనిఖీ చేయండి\n"
            "4. స్థానిక వ్యవసాయ నిపుణులను సంప్రదించండి\n\n"
            "దయచేసి తర్వాత మళ్లీ ప్రయత్నించండి."
        )
    }
    
    # Default to Hindi if language not found
    return templates.get(language, templates['hi-IN'])


def add_disclaimer_to_advice(
    advice: str,
    missing_context: list[str],
    language: str = 'hi-IN'
) -> str:
    """
    Add disclaimer to advice when context is missing.
    
    Args:
        advice: Original advice text
        missing_context: List of missing context items (e.g., ['weather', 'land_records'])
        language: Language code
        
    Returns:
        Advice with appropriate disclaimer
        
    Validates:
        Requirements 3.5, 9.5, 12.5
    """
    if not missing_context:
        return advice
    
    # Disclaimer templates by language
    disclaimers = {
        'hi-IN': {
            'weather': "नोट: मौसम की जानकारी उपलब्ध नहीं है। कृपया स्थानीय मौसम की जांच करें।",
            'land_records': "नोट: आपके खेत की विशिष्ट जानकारी उपलब्ध नहीं है।",
            'memory': "नोट: आपके पिछले इंटरैक्शन का इतिहास उपलब्ध नहीं है।"
        },
        'ta-IN': {
            'weather': "குறிப்பு: வானிலை தகவல் கிடைக்கவில்லை. உள்ளூர் வானிலையை சரிபார்க்கவும்.",
            'land_records': "குறிப்பு: உங்கள் பண்ணையின் குறிப்பிட்ட தகவல் கிடைக்கவில்லை.",
            'memory': "குறிப்பு: உங்கள் முந்தைய உரையாடல் வரலாறு கிடைக்கவில்லை."
        },
        'te-IN': {
            'weather': "గమనిక: వాతావరణ సమాచారం అందుబాటులో లేదు. స్థానిక వాతావరణాన్ని తనిఖీ చేయండి.",
            'land_records': "గమనిక: మీ పొలం యొక్క నిర్దిష్ట సమాచారం అందుబాటులో లేదు.",
            'memory': "గమనిక: మీ మునుపటి సంభాషణ చరిత్ర అందుబాటులో లేదు."
        }
    }
    
    # Get disclaimers for the language (default to Hindi)
    lang_disclaimers = disclaimers.get(language, disclaimers['hi-IN'])
    
    # Build disclaimer text
    disclaimer_parts = []
    for context_item in missing_context:
        if context_item in lang_disclaimers:
            disclaimer_parts.append(lang_disclaimers[context_item])
    
    if disclaimer_parts:
        disclaimer_text = "\n\n⚠️ " + " ".join(disclaimer_parts)
        return advice + disclaimer_text
    
    return advice


def handle_weather_api_failure(
    latitude: float,
    longitude: float,
    cached_weather: Optional[WeatherData] = None
) -> WeatherData:
    """
    Handle weather API failure with fallback strategies.
    
    Strategy:
    1. Use cached weather data if available and recent (< 2 hours old)
    2. Use placeholder data with conservative values
    
    Args:
        latitude: GPS latitude
        longitude: GPS longitude
        cached_weather: Previously cached weather data
        
    Returns:
        WeatherData (cached or placeholder)
        
    Validates:
        Requirements 3.5, 9.5
    """
    # Try to use cached data if available
    if cached_weather:
        try:
            cache_time = datetime.fromisoformat(cached_weather.timestamp)
            age_hours = (datetime.utcnow() - cache_time).total_seconds() / 3600
            
            if age_hours < 2.0:
                logger.info(f"Using cached weather data ({age_hours:.1f} hours old)")
                return cached_weather
            else:
                logger.warning(f"Cached weather data too old ({age_hours:.1f} hours)")
        except Exception as e:
            logger.error(f"Error checking cached weather: {e}")
    
    # Fallback to placeholder data
    logger.warning("Using placeholder weather data due to API failure")
    return WeatherData(
        current=CurrentWeather(
            temperature=25.0,  # Conservative moderate temperature
            humidity=60.0,
            windSpeed=10.0,
            precipitation=0.0
        ),
        forecast6h=Forecast6h(
            precipitationProbability=50.0,  # Conservative: assume rain possible
            expectedRainfall=5.0,
            temperature=25.0,
            windSpeed=10.0
        ),
        timestamp=datetime.utcnow().isoformat()
    )


def handle_ufsi_api_failure(
    farmer_id: str,
    agristack_id: Optional[str] = None
) -> Optional[LandRecords]:
    """
    Handle UFSI API failure with fallback strategies.
    
    Strategy:
    1. Return None (advice will be based on GPS location only)
    2. Log the failure for monitoring
    
    Args:
        farmer_id: Farmer identifier
        agristack_id: AgriStack ID if available
        
    Returns:
        None (no land records available)
        
    Validates:
        Requirements 3.5, 9.5, 12.5
    """
    logger.warning(
        f"UFSI API unavailable for farmer {farmer_id}. "
        "Proceeding with GPS-based advice only."
    )
    return None


def handle_memory_api_failure(farmer_id: str) -> MemoryContext:
    """
    Handle AgentCore Memory API failure with fallback strategies.
    
    Strategy:
    1. Return empty memory context
    2. Advice will be stateless (no proactive follow-up)
    
    Args:
        farmer_id: Farmer identifier
        
    Returns:
        Empty MemoryContext
        
    Validates:
        Requirements 3.5, 9.5
    """
    logger.warning(
        f"AgentCore Memory unavailable for farmer {farmer_id}. "
        "Proceeding without conversation history."
    )
    return MemoryContext(
        recentInteractions=[],
        unresolvedIssues=[],
        consolidatedInsights=ConsolidatedInsights(
            primaryCrop="Unknown",  # Placeholder when no data available
            commonConcerns=[],
            farmerName=None
        )
    )


def should_use_general_advice(context: ContextData) -> bool:
    """
    Determine if general advice should be used due to missing critical context.
    
    Args:
        context: Available context data
        
    Returns:
        True if general advice should be used, False otherwise
        
    Critical context includes:
    - Weather data (for safety validation)
    - At least one of: land records OR memory
    """
    # Weather is critical for safety validation
    if not context.weather:
        return True
    
    # Need at least some farmer-specific context
    has_land_records = context.landRecords is not None
    has_memory = (
        context.memory and 
        (len(context.memory.recentInteractions) > 0 or 
         (context.memory.consolidatedInsights.primaryCrop is not None and 
          context.memory.consolidatedInsights.primaryCrop != "Unknown"))
    )
    
    # If we have neither land records nor memory, use general advice
    if not has_land_records and not has_memory:
        logger.warning("Insufficient context for specific advice, using general advice")
        return True
    
    return False


def get_missing_context_list(context: ContextData) -> list[str]:
    """
    Get list of missing context items.
    
    Args:
        context: Available context data
        
    Returns:
        List of missing context item names
    """
    missing = []
    
    if not context.weather:
        missing.append('weather')
    
    if not context.landRecords:
        missing.append('land_records')
    
    if not context.memory or len(context.memory.recentInteractions) == 0:
        missing.append('memory')
    
    return missing


class GracefulDegradationError(Exception):
    """Exception raised when graceful degradation is triggered."""
    
    def __init__(self, message: str, missing_context: list[str]):
        super().__init__(message)
        self.missing_context = missing_context
