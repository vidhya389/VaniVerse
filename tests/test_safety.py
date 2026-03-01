"""
Tests for safety validation module.

Tests validate Requirements 4.1, 4.2, 4.4, 4.6.
"""

import pytest
from hypothesis import given, strategies as st, settings
from src.safety.validator import validate_safety
from src.models.context_data import WeatherData, CurrentWeather, Forecast6h
from src.models.safety_validation import SafetyValidationResult


class TestSafetyValidation:
    """Unit tests for safety validation function."""
    
    def test_safe_advice_no_conflicts(self):
        """Test that safe advice with no weather conflicts is approved."""
        advice = "Your rice crop looks healthy. Continue regular monitoring."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=28.0,
                humidity=65.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=20.0,
                expectedRainfall=0.0,
                temperature=30.0,
                windSpeed=12.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is True
        assert len(result.conflicts) == 0
        assert result.alternativeRecommendation is None
    
    def test_spray_advice_with_high_rain_probability_blocked(self):
        """Test that spray advice is blocked when rain probability >40%."""
        advice = "You should spray pesticide on your crops this afternoon."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=28.0,
                humidity=65.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=45.0,
                expectedRainfall=5.0,
                temperature=26.0,
                windSpeed=12.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is False
        assert len(result.conflicts) == 1
        assert result.conflicts[0].type == 'rain_forecast'
        assert result.conflicts[0].severity == 'blocking'
        assert '45%' in result.conflicts[0].message
        assert result.alternativeRecommendation is not None
        assert 'wait' in result.alternativeRecommendation.lower()
    
    def test_spray_advice_at_40_percent_rain_approved(self):
        """Test that spray advice is approved at exactly 40% rain probability."""
        advice = "Apply insecticide to control pests."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=28.0,
                humidity=65.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=40.0,
                expectedRainfall=2.0,
                temperature=26.0,
                windSpeed=12.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is True
        assert len(result.conflicts) == 0
    
    def test_spray_advice_with_high_wind_warning(self):
        """Test that spray advice gets warning for high wind speed."""
        advice = "Spray fungicide on your wheat crop."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=28.0,
                humidity=65.0,
                windSpeed=25.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=10.0,
                expectedRainfall=0.0,
                temperature=30.0,
                windSpeed=22.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is True  # Warning, not blocking
        assert len(result.conflicts) == 1
        assert result.conflicts[0].type == 'high_wind'
        assert result.conflicts[0].severity == 'warning'
        assert '25.0 km/h' in result.conflicts[0].message
        assert result.alternativeRecommendation is None
    
    def test_spray_advice_with_extreme_heat_warning(self):
        """Test that spray advice gets warning for extreme heat."""
        advice = "Apply pesticide to control insects."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=42.0,
                humidity=45.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=5.0,
                expectedRainfall=0.0,
                temperature=41.0,
                windSpeed=12.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is True  # Warning, not blocking
        assert len(result.conflicts) == 1
        assert result.conflicts[0].type == 'extreme_heat'
        assert result.conflicts[0].severity == 'warning'
        assert '42.0°C' in result.conflicts[0].message
        assert 'evaporate' in result.conflicts[0].message.lower()
    
    def test_spray_advice_with_extreme_cold_warning(self):
        """Test that spray advice gets warning for extreme cold."""
        advice = "Spray insecticide on your crop."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=3.0,
                humidity=70.0,
                windSpeed=8.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=10.0,
                expectedRainfall=0.0,
                temperature=4.0,
                windSpeed=10.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is True  # Warning, not blocking
        assert len(result.conflicts) == 1
        assert result.conflicts[0].type == 'extreme_cold'
        assert result.conflicts[0].severity == 'warning'
        assert '3.0°C' in result.conflicts[0].message
    
    def test_spray_advice_with_multiple_conflicts(self):
        """Test spray advice with multiple weather conflicts."""
        advice = "Apply chemical pesticide now."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=43.0,
                humidity=40.0,
                windSpeed=25.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=50.0,
                expectedRainfall=8.0,
                temperature=38.0,
                windSpeed=22.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is False  # Blocked due to rain
        assert len(result.conflicts) == 3  # rain, wind, heat
        conflict_types = {c.type for c in result.conflicts}
        assert 'rain_forecast' in conflict_types
        assert 'high_wind' in conflict_types
        assert 'extreme_heat' in conflict_types
        assert result.alternativeRecommendation is not None
    
    def test_irrigation_advice_with_high_temperature_warning(self):
        """Test that irrigation advice gets warning for high temperature."""
        advice = "Water your crops this afternoon."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=38.0,
                humidity=35.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=5.0,
                expectedRainfall=0.0,
                temperature=36.0,
                windSpeed=12.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is True  # Warning, not blocking
        assert len(result.conflicts) == 1
        assert result.conflicts[0].type == 'high_evaporation'
        assert result.conflicts[0].severity == 'warning'
        assert 'early morning or evening' in result.conflicts[0].message
    
    def test_irrigation_advice_at_35_degrees_no_warning(self):
        """Test that irrigation advice at exactly 35°C has no warning."""
        advice = "Irrigate your field today."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=35.0,
                humidity=50.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=10.0,
                expectedRainfall=0.0,
                temperature=34.0,
                windSpeed=12.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is True
        assert len(result.conflicts) == 0
    
    def test_case_insensitive_keyword_detection(self):
        """Test that keyword detection is case-insensitive."""
        advice = "SPRAY the PESTICIDE on your crops."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=28.0,
                humidity=65.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=50.0,
                expectedRainfall=5.0,
                temperature=26.0,
                windSpeed=12.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is False
        assert len(result.conflicts) == 1
        assert result.conflicts[0].type == 'rain_forecast'
    
    def test_alternative_recommendation_format(self):
        """Test that alternative recommendation has proper format."""
        advice = "Apply insecticide to your rice crop."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=28.0,
                humidity=65.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=60.0,
                expectedRainfall=10.0,
                temperature=26.0,
                windSpeed=12.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is False
        assert result.alternativeRecommendation is not None
        alt = result.alternativeRecommendation
        assert 'ALTERNATIVE RECOMMENDATION' in alt
        assert 'hours' in alt.lower()
        assert 'early morning' in alt.lower()
    
    def test_various_spray_keywords(self):
        """Test detection of various spray-related keywords."""
        keywords = ['spray', 'pesticide', 'insecticide', 'fungicide', 'apply', 'chemical']
        
        for keyword in keywords:
            advice = f"You should {keyword} on your crops."
            weather = WeatherData(
                current=CurrentWeather(
                    temperature=28.0,
                    humidity=65.0,
                    windSpeed=10.0,
                    precipitation=0.0
                ),
                forecast6h=Forecast6h(
                    precipitationProbability=50.0,
                    expectedRainfall=5.0,
                    temperature=26.0,
                    windSpeed=12.0
                )
            )
            
            result = validate_safety(advice, weather)
            
            assert result.isApproved is False, f"Failed for keyword: {keyword}"
            assert len(result.conflicts) > 0
    
    def test_various_irrigation_keywords(self):
        """Test detection of various irrigation-related keywords."""
        keywords = ['water', 'irrigate', 'irrigation']
        
        for keyword in keywords:
            advice = f"You should {keyword} your field."
            weather = WeatherData(
                current=CurrentWeather(
                    temperature=38.0,
                    humidity=35.0,
                    windSpeed=10.0,
                    precipitation=0.0
                ),
                forecast6h=Forecast6h(
                    precipitationProbability=5.0,
                    expectedRainfall=0.0,
                    temperature=36.0,
                    windSpeed=12.0
                )
            )
            
            result = validate_safety(advice, weather)
            
            assert result.isApproved is True  # Warning, not blocking
            assert len(result.conflicts) == 1
            assert result.conflicts[0].type == 'high_evaporation'


class TestAlternativeRecommendationGenerator:
    """Unit tests for alternative recommendation generator."""
    
    def test_safe_timing_window_for_moderate_rain(self):
        """Test that moderate rain (40-60%) suggests 12-hour wait."""
        advice = "Spray pesticide on your crops."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=28.0,
                humidity=65.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=50.0,
                expectedRainfall=5.0,
                temperature=26.0,
                windSpeed=12.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is False
        assert result.alternativeRecommendation is not None
        assert '12 hours' in result.alternativeRecommendation
    
    def test_safe_timing_window_for_high_rain(self):
        """Test that high rain (>60%) suggests 18-hour wait."""
        advice = "Apply insecticide to control pests."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=28.0,
                humidity=70.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=75.0,
                expectedRainfall=15.0,
                temperature=26.0,
                windSpeed=12.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is False
        assert result.alternativeRecommendation is not None
        assert '18 hours' in result.alternativeRecommendation
    
    def test_specific_hours_for_heat_concern(self):
        """Test that heat concerns suggest early morning or late evening."""
        advice = "Spray fungicide on your wheat."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=42.0,
                humidity=40.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=50.0,
                expectedRainfall=5.0,
                temperature=40.0,
                windSpeed=12.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is False
        assert result.alternativeRecommendation is not None
        alt = result.alternativeRecommendation
        assert 'early morning (6-8 AM)' in alt or 'late evening (5-7 PM)' in alt
    
    def test_specific_hours_for_cold_concern(self):
        """Test that cold concerns suggest late morning when warmer."""
        advice = "Apply pesticide to your crop."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=3.0,
                humidity=70.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=50.0,
                expectedRainfall=2.0,
                temperature=4.0,
                windSpeed=12.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is False
        assert result.alternativeRecommendation is not None
        assert 'late morning (10 AM-12 PM)' in result.alternativeRecommendation
        assert 'warmer' in result.alternativeRecommendation
    
    def test_default_timing_for_general_conflicts(self):
        """Test that general conflicts suggest early morning by default."""
        advice = "Spray insecticide on your crops."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=28.0,
                humidity=65.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=45.0,
                expectedRainfall=5.0,
                temperature=26.0,
                windSpeed=12.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is False
        assert result.alternativeRecommendation is not None
        assert 'early morning (6-8 AM)' in result.alternativeRecommendation
    
    def test_alternative_includes_all_blocking_messages(self):
        """Test that alternative recommendation includes all blocking conflict messages."""
        advice = "Apply chemical pesticide now."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=28.0,
                humidity=65.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=80.0,
                expectedRainfall=20.0,
                temperature=26.0,
                windSpeed=12.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is False
        assert result.alternativeRecommendation is not None
        alt = result.alternativeRecommendation
        assert '80%' in alt  # Rain probability should be mentioned
        assert 'Rain is predicted' in alt
    
    def test_alternative_provides_actionable_guidance(self):
        """Test that alternative recommendation provides clear actionable guidance."""
        advice = "Spray pesticide on your rice crop."
        weather = WeatherData(
            current=CurrentWeather(
                temperature=28.0,
                humidity=65.0,
                windSpeed=10.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=55.0,
                expectedRainfall=8.0,
                temperature=26.0,
                windSpeed=12.0
            )
        )
        
        result = validate_safety(advice, weather)
        
        assert result.isApproved is False
        alt = result.alternativeRecommendation
        assert 'ALTERNATIVE RECOMMENDATION' in alt
        assert 'Wait at least' in alt
        assert 'hours' in alt
        assert 'check the weather again' in alt
        assert 'Wind speeds are typically lower' in alt
        assert 'Temperature is moderate' in alt


if __name__ == '__main__':
    pytest.main([__file__, '-v'])



# Property-Based Tests
class TestSafetyValidationProperties:
    """Property-based tests for safety validation."""
    
    @given(
        spray_keyword=st.sampled_from([
            'spray', 'pesticide', 'insecticide', 'fungicide', 'apply', 'chemical'
        ]),
        crop=st.sampled_from(['rice', 'wheat', 'cotton', 'tomato', 'corn', 'soybean']),
        extreme_condition=st.sampled_from([
            'extreme_heat',  # Temperature > 40°C
            'extreme_cold',  # Temperature < 5°C
            'high_wind'      # Wind speed > 20 km/h
        ]),
        temperature=st.one_of(
            st.floats(min_value=41.0, max_value=50.0),  # Extreme heat
            st.floats(min_value=-5.0, max_value=4.9),   # Extreme cold
            st.floats(min_value=20.0, max_value=35.0)   # Normal (for wind test)
        ),
        wind_speed=st.one_of(
            st.floats(min_value=21.0, max_value=50.0),  # High wind
            st.floats(min_value=5.0, max_value=20.0)    # Normal wind
        ),
        rain_probability=st.floats(min_value=0.0, max_value=40.0)  # Below blocking threshold
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.pbt
    def test_property_10_extreme_weather_warnings(
        self,
        spray_keyword,
        crop,
        extreme_condition,
        temperature,
        wind_speed,
        rain_probability
    ):
        """
        Feature: vaniverse, Property 10: Extreme Weather Warnings
        
        Validates: Requirements 4.4
        
        For any advice about pesticide application, if current weather conditions 
        are extreme (temperature >40°C or <5°C, or wind speed >20 km/h), the 
        Safety Validator should include a warning in the response.
        
        This property test generates random pesticide advice with various extreme
        weather conditions and verifies that appropriate warnings are included.
        """
        # Generate advice text that includes the spray keyword
        advice_text = f"You should {spray_keyword} on your {crop} crop to control pests."
        
        # Set up weather conditions based on the extreme condition being tested
        if extreme_condition == 'extreme_heat':
            # Ensure temperature is extreme heat (>40°C)
            test_temperature = max(temperature, 41.0) if temperature > 40 else 42.0
            test_wind_speed = min(wind_speed, 20.0)  # Keep wind normal
        elif extreme_condition == 'extreme_cold':
            # Ensure temperature is extreme cold (<5°C)
            test_temperature = min(temperature, 4.9) if temperature < 5 else 3.0
            test_wind_speed = min(wind_speed, 20.0)  # Keep wind normal
        else:  # high_wind
            # Ensure wind is high (>20 km/h)
            test_wind_speed = max(wind_speed, 21.0) if wind_speed > 20 else 25.0
            test_temperature = min(max(temperature, 20.0), 35.0)  # Keep temp normal
        
        # Create weather data with extreme conditions
        weather = WeatherData(
            current=CurrentWeather(
                temperature=test_temperature,
                humidity=50.0,
                windSpeed=test_wind_speed,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=rain_probability,
                expectedRainfall=0.0,
                temperature=test_temperature,
                windSpeed=test_wind_speed
            )
        )
        
        # Validate the advice
        result = validate_safety(advice_text, weather)
        
        # Property 1: Result must contain conflicts for extreme conditions
        assert len(result.conflicts) > 0, \
            f"Extreme weather condition '{extreme_condition}' must generate conflicts. " \
            f"Temp: {test_temperature}°C, Wind: {test_wind_speed} km/h"
        
        # Property 2: The specific extreme condition must be detected
        conflict_types = {c.type for c in result.conflicts}
        
        if extreme_condition == 'extreme_heat':
            assert 'extreme_heat' in conflict_types, \
                f"Extreme heat (>{test_temperature}°C) must be detected in conflicts. " \
                f"Found conflicts: {conflict_types}"
        elif extreme_condition == 'extreme_cold':
            assert 'extreme_cold' in conflict_types, \
                f"Extreme cold (<{test_temperature}°C) must be detected in conflicts. " \
                f"Found conflicts: {conflict_types}"
        else:  # high_wind
            assert 'high_wind' in conflict_types, \
                f"High wind (>{test_wind_speed} km/h) must be detected in conflicts. " \
                f"Found conflicts: {conflict_types}"
        
        # Property 3: Extreme weather warnings should be 'warning' severity (not blocking)
        extreme_conflicts = [
            c for c in result.conflicts 
            if c.type in ['extreme_heat', 'extreme_cold', 'high_wind']
        ]
        
        for conflict in extreme_conflicts:
            assert conflict.severity == 'warning', \
                f"Extreme weather conflicts should be warnings, not blocking. " \
                f"Found severity: {conflict.severity} for type: {conflict.type}"
        
        # Property 4: Advice should still be approved (warnings don't block)
        # unless there's also a blocking conflict (like rain >40%)
        if rain_probability <= 40:
            assert result.isApproved is True, \
                f"Advice with only extreme weather warnings should be approved. " \
                f"Rain probability: {rain_probability}%, Conflicts: {conflict_types}"
            assert result.alternativeRecommendation is None, \
                "Warnings should not generate alternative recommendations"
        
        # Property 5: Warning messages must include specific weather values
        for conflict in extreme_conflicts:
            if conflict.type == 'extreme_heat':
                assert f"{test_temperature:.1f}°C" in conflict.message, \
                    f"Extreme heat warning must include temperature value. " \
                    f"Message: {conflict.message}"
                assert 'evaporate' in conflict.message.lower() or 'effective' in conflict.message.lower(), \
                    f"Extreme heat warning must explain the risk. Message: {conflict.message}"
            elif conflict.type == 'extreme_cold':
                assert f"{test_temperature:.1f}°C" in conflict.message, \
                    f"Extreme cold warning must include temperature value. " \
                    f"Message: {conflict.message}"
                assert 'cold' in conflict.message.lower() and 'effective' in conflict.message.lower(), \
                    f"Extreme cold warning must explain the risk. Message: {conflict.message}"
            elif conflict.type == 'high_wind':
                assert f"{test_wind_speed:.1f} km/h" in conflict.message, \
                    f"High wind warning must include wind speed value. " \
                    f"Message: {conflict.message}"
                assert 'drift' in conflict.message.lower() or 'neighboring' in conflict.message.lower(), \
                    f"High wind warning must explain spray drift risk. Message: {conflict.message}"
        
        # Property 6: Multiple extreme conditions can be detected simultaneously
        # (This is implicitly tested by the test setup allowing multiple conditions)
        # Verify that all applicable extreme conditions are detected
        if test_temperature > 40:
            assert 'extreme_heat' in conflict_types, \
                "Extreme heat must be detected when temperature > 40°C"
        if test_temperature < 5:
            assert 'extreme_cold' in conflict_types, \
                "Extreme cold must be detected when temperature < 5°C"
        if test_wind_speed > 20:
            assert 'high_wind' in conflict_types, \
                "High wind must be detected when wind speed > 20 km/h"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
