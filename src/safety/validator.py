"""
Safety validation module for agricultural advice.

Implements Chain-of-Verification to check if advice conflicts with weather conditions.
Validates Requirements 4.1, 4.2, 4.4, 4.6.
"""

from typing import List
from src.models.context_data import WeatherData
from src.models.safety_validation import SafetyValidationResult, SafetyConflict


# Keywords that indicate pesticide/spray application
SPRAY_KEYWORDS = [
    'spray', 'pesticide', 'insecticide', 'fungicide', 
    'apply', 'application', 'chemical'
]

# Keywords that indicate irrigation
IRRIGATION_KEYWORDS = ['water', 'irrigate', 'irrigation']


def validate_safety(advice_text: str, weather: WeatherData) -> SafetyValidationResult:
    """
    Chain-of-Verification: Check if advice conflicts with weather conditions.
    
    This function implements the safety validation layer that checks agricultural
    advice against current and forecasted weather conditions to prevent harmful
    actions.
    
    Args:
        advice_text: The generated agricultural advice text
        weather: Current weather and 6-hour forecast data
    
    Returns:
        SafetyValidationResult with approval status, conflicts, and alternatives
    
    Validates:
        - Requirement 4.1: Check for pesticide/spray mentions
        - Requirement 4.2: Validate against rain forecast (>40% probability)
        - Requirement 4.4: Check extreme weather conditions
        - Requirement 4.6: Execute Chain-of-Verification before delivery
    """
    conflicts: List[SafetyConflict] = []
    
    # Check for pesticide/spray mentions
    advice_lower = advice_text.lower()
    mentions_spraying = any(keyword in advice_lower for keyword in SPRAY_KEYWORDS)
    
    if mentions_spraying:
        # Requirement 4.2: Check rain forecast (>40% probability)
        if weather.forecast6h.precipitationProbability > 40:
            conflicts.append(SafetyConflict(
                type='rain_forecast',
                severity='blocking',
                message=(
                    f"Rain is predicted within 6 hours "
                    f"({weather.forecast6h.precipitationProbability:.0f}% probability). "
                    f"Spraying now will waste pesticide."
                )
            ))
        
        # Requirement 4.4: Check wind speed (>20 km/h)
        if weather.current.windSpeed > 20:
            conflicts.append(SafetyConflict(
                type='high_wind',
                severity='warning',
                message=(
                    f"Wind speed is {weather.current.windSpeed:.1f} km/h. "
                    f"Spray drift may affect neighboring fields."
                )
            ))
        
        # Requirement 4.4: Check extreme temperature (>40°C or <5°C)
        if weather.current.temperature > 40:
            conflicts.append(SafetyConflict(
                type='extreme_heat',
                severity='warning',
                message=(
                    f"Temperature is {weather.current.temperature:.1f}°C. "
                    f"Pesticides may evaporate quickly and be less effective."
                )
            ))
        elif weather.current.temperature < 5:
            conflicts.append(SafetyConflict(
                type='extreme_cold',
                severity='warning',
                message=(
                    f"Temperature is {weather.current.temperature:.1f}°C. "
                    f"Pesticides may not work effectively in cold conditions."
                )
            ))
    
    # Check for irrigation mentions
    mentions_irrigation = any(keyword in advice_lower for keyword in IRRIGATION_KEYWORDS)
    
    if mentions_irrigation and weather.current.temperature > 35:
        conflicts.append(SafetyConflict(
            type='high_evaporation',
            severity='warning',
            message=(
                f"Temperature is {weather.current.temperature:.1f}°C. "
                f"Consider irrigating in early morning or evening to reduce water loss."
            )
        ))
    
    # Determine if advice is approved
    blocking_conflicts = [c for c in conflicts if c.severity == 'blocking']
    is_approved = len(blocking_conflicts) == 0
    
    # Generate alternative recommendation if blocked
    alternative = None
    if not is_approved:
        alternative = _generate_alternative_recommendation(
            advice_text, 
            conflicts, 
            weather
        )
    
    return SafetyValidationResult(
        isApproved=is_approved,
        conflicts=conflicts,
        alternativeRecommendation=alternative
    )


def generate_alternative_recommendation(
    original_advice: str,
    conflicts: List[SafetyConflict],
    weather: WeatherData
) -> str:
    """
    Generate alternative recommendation when original advice is blocked.
    
    This function calculates safe timing windows based on weather conflicts
    and provides specific hour recommendations for when to perform the action.
    
    Args:
        original_advice: The original advice that was blocked
        conflicts: List of safety conflicts detected
        weather: Current weather data
    
    Returns:
        Alternative recommendation with timing suggestions
    
    Validates:
        - Requirement 4.5: Provide alternative timing recommendations
        - Requirement 4.7: Modify or block advice when conflicts detected
    """
    blocking_messages = [
        c.message for c in conflicts if c.severity == 'blocking'
    ]
    
    # Calculate safe timing windows based on conflicts
    hours_until_safe = _calculate_safe_timing_window(conflicts, weather)
    
    # Provide specific hour recommendations
    recommended_hours = _get_recommended_hours(conflicts, weather)
    
    alternative = f"""
I understand you want to proceed with this action, but I must advise against it right now due to weather conditions:

{' '.join(blocking_messages)}

ALTERNATIVE RECOMMENDATION:
Wait at least {hours_until_safe} hours and check the weather again. The best time would be {recommended_hours} when:
- Wind speeds are typically lower
- Temperature is moderate
- Dew has dried but heat hasn't peaked

I'll remind you to check back in {hours_until_safe} hours. Your crop's health is important, and timing this correctly will make your efforts more effective.
"""
    
    return alternative.strip()


def _calculate_safe_timing_window(
    conflicts: List[SafetyConflict],
    weather: WeatherData
) -> int:
    """
    Calculate the minimum hours to wait before the action becomes safe.
    
    Args:
        conflicts: List of safety conflicts
        weather: Current weather data
    
    Returns:
        Number of hours to wait
    """
    hours_until_safe = 6  # Default minimum wait time
    
    # Check for rain-related conflicts
    for conflict in conflicts:
        if conflict.type == 'rain_forecast':
            # If high rain probability, wait longer for rain to pass
            if weather.forecast6h.precipitationProbability > 60:
                hours_until_safe = max(hours_until_safe, 18)  # Wait until next day
            elif weather.forecast6h.precipitationProbability > 40:
                hours_until_safe = max(hours_until_safe, 12)  # Wait 12 hours
    
    return hours_until_safe


def _get_recommended_hours(
    conflicts: List[SafetyConflict],
    weather: WeatherData
) -> str:
    """
    Get specific hour recommendations for safe timing.
    
    Args:
        conflicts: List of safety conflicts
        weather: Current weather data
    
    Returns:
        String describing recommended hours (e.g., "early morning (6-8 AM)")
    """
    # Check if there are temperature-related concerns
    has_heat_concern = any(
        c.type in ['extreme_heat', 'high_evaporation'] 
        for c in conflicts
    )
    
    has_cold_concern = any(
        c.type == 'extreme_cold' 
        for c in conflicts
    )
    
    # Provide specific timing based on concerns
    if has_heat_concern:
        return "early morning (6-8 AM) or late evening (5-7 PM)"
    elif has_cold_concern:
        return "late morning (10 AM-12 PM) when temperature is warmer"
    else:
        # Default recommendation for general safety
        return "early morning (6-8 AM)"


def _generate_alternative_recommendation(
    original_advice: str,
    conflicts: List[SafetyConflict],
    weather: WeatherData
) -> str:
    """
    Private wrapper for backward compatibility.
    Delegates to the public generate_alternative_recommendation function.
    """
    return generate_alternative_recommendation(original_advice, conflicts, weather)
