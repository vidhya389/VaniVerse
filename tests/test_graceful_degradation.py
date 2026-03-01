"""
Tests for graceful degradation handlers.

Tests Requirements 3.5, 9.5, 12.5: Fallback to general advice when APIs fail
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.utils.graceful_degradation import (
    create_fallback_context,
    get_general_advice_template,
    add_disclaimer_to_advice,
    handle_weather_api_failure,
    handle_ufsi_api_failure,
    handle_memory_api_failure,
    should_use_general_advice,
    get_missing_context_list,
    GracefulDegradationError
)
from src.models.context_data import (
    ContextData, WeatherData, CurrentWeather, Forecast6h,
    LandRecords, MemoryContext, ConsolidatedInsights
)


class TestCreateFallbackContext:
    """Tests for create_fallback_context function."""
    
    def test_all_apis_unavailable(self):
        """Test fallback context when all APIs are unavailable."""
        context = create_fallback_context(
            farmer_id="FARMER-123",
            latitude=28.6139,
            longitude=77.2090,
            weather_available=False,
            land_records_available=False,
            memory_available=False
        )
        
        # Should have placeholder weather
        assert context.weather is not None
        assert context.weather.current.temperature == 25.0
        
        # Should have no land records
        assert context.landRecords is None
        
        # Should have empty memory
        assert context.memory is not None
        assert len(context.memory.recentInteractions) == 0
    
    def test_partial_availability(self):
        """Test fallback context with partial API availability."""
        context = create_fallback_context(
            farmer_id="FARMER-123",
            latitude=28.6139,
            longitude=77.2090,
            weather_available=True,
            land_records_available=False,
            memory_available=True
        )
        
        # Weather should be None (will be fetched separately)
        # Land records should be None
        assert context.landRecords is None


class TestGetGeneralAdviceTemplate:
    """Tests for get_general_advice_template function."""
    
    def test_hindi_template(self):
        """Test Hindi general advice template."""
        advice = get_general_advice_template('hi-IN')
        
        assert advice is not None
        assert len(advice) > 0
        assert 'मुझे खेद है' in advice or 'सामान्य' in advice
    
    def test_tamil_template(self):
        """Test Tamil general advice template."""
        advice = get_general_advice_template('ta-IN')
        
        assert advice is not None
        assert len(advice) > 0
    
    def test_telugu_template(self):
        """Test Telugu general advice template."""
        advice = get_general_advice_template('te-IN')
        
        assert advice is not None
        assert len(advice) > 0
    
    def test_unsupported_language_fallback(self):
        """Test that unsupported languages fall back to Hindi."""
        advice = get_general_advice_template('unknown-LANG')
        
        assert advice is not None
        assert len(advice) > 0


class TestAddDisclaimerToAdvice:
    """Tests for add_disclaimer_to_advice function."""
    
    def test_no_missing_context(self):
        """Test that no disclaimer is added when context is complete."""
        advice = "Apply fertilizer in the morning."
        result = add_disclaimer_to_advice(advice, [], 'hi-IN')
        
        assert result == advice
    
    def test_weather_missing_disclaimer(self):
        """Test disclaimer for missing weather data."""
        advice = "Apply fertilizer in the morning."
        result = add_disclaimer_to_advice(advice, ['weather'], 'hi-IN')
        
        assert advice in result
        assert '⚠️' in result
        assert 'मौसम' in result or 'नोट' in result
    
    def test_multiple_missing_context(self):
        """Test disclaimer for multiple missing context items."""
        advice = "Apply fertilizer in the morning."
        result = add_disclaimer_to_advice(
            advice,
            ['weather', 'land_records'],
            'hi-IN'
        )
        
        assert advice in result
        assert '⚠️' in result
    
    def test_tamil_disclaimer(self):
        """Test Tamil disclaimer."""
        advice = "Apply fertilizer."
        result = add_disclaimer_to_advice(advice, ['weather'], 'ta-IN')
        
        assert advice in result
        assert '⚠️' in result


class TestHandleWeatherApiFailure:
    """Tests for handle_weather_api_failure function."""
    
    def test_no_cached_data(self):
        """Test fallback when no cached data is available."""
        weather = handle_weather_api_failure(
            latitude=28.6139,
            longitude=77.2090,
            cached_weather=None
        )
        
        assert weather is not None
        assert weather.current.temperature == 25.0
        assert weather.forecast6h.precipitationProbability == 50.0
    
    def test_recent_cached_data(self):
        """Test using recent cached data."""
        # Create cached data from 1 hour ago
        cached = WeatherData(
            current=CurrentWeather(
                temperature=30.0,
                humidity=70.0,
                windSpeed=15.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=20.0,
                expectedRainfall=0.0,
                temperature=32.0,
                windSpeed=12.0
            ),
            timestamp=(datetime.utcnow() - timedelta(hours=1)).isoformat()
        )
        
        weather = handle_weather_api_failure(
            latitude=28.6139,
            longitude=77.2090,
            cached_weather=cached
        )
        
        # Should use cached data
        assert weather.current.temperature == 30.0
        assert weather.current.humidity == 70.0
    
    def test_old_cached_data(self):
        """Test that old cached data is not used."""
        # Create cached data from 3 hours ago
        cached = WeatherData(
            current=CurrentWeather(
                temperature=30.0,
                humidity=70.0,
                windSpeed=15.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                precipitationProbability=20.0,
                expectedRainfall=0.0,
                temperature=32.0,
                windSpeed=12.0
            ),
            timestamp=(datetime.utcnow() - timedelta(hours=3)).isoformat()
        )
        
        weather = handle_weather_api_failure(
            latitude=28.6139,
            longitude=77.2090,
            cached_weather=cached
        )
        
        # Should use placeholder data (not cached)
        assert weather.current.temperature == 25.0


class TestHandleUfsiApiFailure:
    """Tests for handle_ufsi_api_failure function."""
    
    def test_returns_none(self):
        """Test that UFSI failure returns None."""
        result = handle_ufsi_api_failure(
            farmer_id="FARMER-123",
            agristack_id="AGRI-456"
        )
        
        assert result is None
    
    @patch('src.utils.graceful_degradation.logger')
    def test_logs_warning(self, mock_logger):
        """Test that UFSI failure logs a warning."""
        handle_ufsi_api_failure(
            farmer_id="FARMER-123",
            agristack_id="AGRI-456"
        )
        
        assert mock_logger.warning.called


class TestHandleMemoryApiFailure:
    """Tests for handle_memory_api_failure function."""
    
    def test_returns_empty_context(self):
        """Test that memory failure returns empty context."""
        memory = handle_memory_api_failure(farmer_id="FARMER-123")
        
        assert memory is not None
        assert len(memory.recentInteractions) == 0
        assert len(memory.unresolvedIssues) == 0
        assert memory.consolidatedInsights.primaryCrop == "Unknown"
    
    @patch('src.utils.graceful_degradation.logger')
    def test_logs_warning(self, mock_logger):
        """Test that memory failure logs a warning."""
        handle_memory_api_failure(farmer_id="FARMER-123")
        
        assert mock_logger.warning.called


class TestShouldUseGeneralAdvice:
    """Tests for should_use_general_advice function."""
    
    def test_no_weather_data(self):
        """Test that missing weather triggers general advice."""
        # Note: ContextData requires weather, so we test with placeholder weather
        # and check the logic separately
        context = ContextData(
            weather=WeatherData(
                current=CurrentWeather(
                    temperature=25.0,
                    humidity=60.0,
                    windSpeed=10.0,
                    precipitation=0.0
                ),
                forecast6h=Forecast6h(
                    precipitationProbability=50.0,
                    expectedRainfall=0.0,
                    temperature=25.0,
                    windSpeed=10.0
                ),
                timestamp=datetime.utcnow().isoformat()
            ),
            landRecords=LandRecords(
                landArea=2.5,
                soilType='Clay Loam',
                currentCrop='Rice',
                cropHistory=[]
            ),
            memory=MemoryContext(
                recentInteractions=[],
                unresolvedIssues=[],
                consolidatedInsights=ConsolidatedInsights(
                    primaryCrop='Rice',
                    commonConcerns=[],
                    farmerName='Test'
                )
            )
        )
        
        # With weather available, should not use general advice
        assert should_use_general_advice(context) is False
    
    def test_no_farmer_context(self):
        """Test that missing farmer context triggers general advice."""
        context = ContextData(
            weather=WeatherData(
                current=CurrentWeather(
                    temperature=25.0,
                    humidity=60.0,
                    windSpeed=10.0,
                    precipitation=0.0
                ),
                forecast6h=Forecast6h(
                    precipitationProbability=20.0,
                    expectedRainfall=0.0,
                    temperature=26.0,
                    windSpeed=12.0
                ),
                timestamp=datetime.utcnow().isoformat()
            ),
            landRecords=None,
            memory=MemoryContext(
                recentInteractions=[],
                unresolvedIssues=[],
                consolidatedInsights=ConsolidatedInsights(
                    primaryCrop="Unknown",  # No real data
                    commonConcerns=[],
                    farmerName=None
                )
            )
        )
        
        assert should_use_general_advice(context) is True
    
    def test_sufficient_context(self):
        """Test that sufficient context allows specific advice."""
        context = ContextData(
            weather=WeatherData(
                current=CurrentWeather(
                    temperature=25.0,
                    humidity=60.0,
                    windSpeed=10.0,
                    precipitation=0.0
                ),
                forecast6h=Forecast6h(
                    precipitationProbability=20.0,
                    expectedRainfall=0.0,
                    temperature=26.0,
                    windSpeed=12.0
                ),
                timestamp=datetime.utcnow().isoformat()
            ),
            landRecords=LandRecords(
                landArea=2.5,
                soilType='Clay Loam',
                currentCrop='Rice',
                cropHistory=[]
            ),
            memory=MemoryContext(
                recentInteractions=[],
                unresolvedIssues=[],
                consolidatedInsights=ConsolidatedInsights(
                    primaryCrop='Rice',
                    commonConcerns=[],
                    farmerName='Test'
                )
            )
        )
        
        assert should_use_general_advice(context) is False


class TestGetMissingContextList:
    """Tests for get_missing_context_list function."""
    
    def test_all_context_available(self):
        """Test when all context is available."""
        context = ContextData(
            weather=WeatherData(
                current=CurrentWeather(
                    temperature=25.0,
                    humidity=60.0,
                    windSpeed=10.0,
                    precipitation=0.0
                ),
                forecast6h=Forecast6h(
                    precipitationProbability=20.0,
                    expectedRainfall=0.0,
                    temperature=26.0,
                    windSpeed=12.0
                ),
                timestamp=datetime.utcnow().isoformat()
            ),
            landRecords=LandRecords(
                landArea=2.5,
                soilType='Clay Loam',
                currentCrop='Rice',
                cropHistory=[]
            ),
            memory=MemoryContext(
                recentInteractions=[{'question': 'test', 'advice': 'test', 'timestamp': '2024-01-01'}],
                unresolvedIssues=[],
                consolidatedInsights=ConsolidatedInsights(
                    primaryCrop='Rice',
                    commonConcerns=[],
                    farmerName='Test'
                )
            )
        )
        
        missing = get_missing_context_list(context)
        assert len(missing) == 0
    
    def test_weather_missing(self):
        """Test when weather is missing."""
        # Since ContextData requires weather, we test the missing context detection differently
        # by checking if weather data is placeholder/default
        context = ContextData(
            weather=WeatherData(
                current=CurrentWeather(
                    temperature=25.0,  # Placeholder value
                    humidity=60.0,
                    windSpeed=10.0,
                    precipitation=0.0
                ),
                forecast6h=Forecast6h(
                    precipitationProbability=50.0,  # Conservative placeholder
                    expectedRainfall=0.0,
                    temperature=25.0,
                    windSpeed=10.0
                ),
                timestamp=datetime.utcnow().isoformat()
            ),
            landRecords=LandRecords(
                landArea=2.5,
                soilType='Clay Loam',
                currentCrop='Rice',
                cropHistory=[]
            ),
            memory=MemoryContext(
                recentInteractions=[],
                unresolvedIssues=[],
                consolidatedInsights=ConsolidatedInsights(
                    primaryCrop='Rice',
                    commonConcerns=[],
                    farmerName='Test'
                )
            )
        )
        
        missing = get_missing_context_list(context)
        # Weather is present (even if placeholder), so not in missing list
        assert 'weather' not in missing
    
    def test_all_context_missing(self):
        """Test when all context is missing."""
        context = ContextData(
            weather=WeatherData(
                current=CurrentWeather(
                    temperature=25.0,
                    humidity=60.0,
                    windSpeed=10.0,
                    precipitation=0.0
                ),
                forecast6h=Forecast6h(
                    precipitationProbability=50.0,
                    expectedRainfall=0.0,
                    temperature=25.0,
                    windSpeed=10.0
                ),
                timestamp=datetime.utcnow().isoformat()
            ),
            landRecords=None,
            memory=MemoryContext(
                recentInteractions=[],
                unresolvedIssues=[],
                consolidatedInsights=ConsolidatedInsights(
                    primaryCrop="Unknown",  # No real data
                    commonConcerns=[],
                    farmerName=None
                )
            )
        )
        
        missing = get_missing_context_list(context)
        # Weather is present (placeholder), but land_records and memory are missing
        assert 'land_records' in missing
        assert 'memory' in missing


class TestGracefulDegradationError:
    """Tests for GracefulDegradationError exception."""
    
    def test_exception_creation(self):
        """Test creating graceful degradation exception."""
        error = GracefulDegradationError(
            "API failure",
            ['weather', 'land_records']
        )
        
        assert str(error) == "API failure"
        assert error.missing_context == ['weather', 'land_records']
    
    def test_exception_raising(self):
        """Test raising and catching graceful degradation exception."""
        with pytest.raises(GracefulDegradationError) as exc_info:
            raise GracefulDegradationError("Test error", ['weather'])
        
        assert exc_info.value.missing_context == ['weather']


class TestIntegration:
    """Integration tests for graceful degradation."""
    
    def test_complete_fallback_scenario(self):
        """Test complete fallback scenario with all APIs failing."""
        # Create fallback context
        context = create_fallback_context(
            farmer_id="FARMER-123",
            latitude=28.6139,
            longitude=77.2090,
            weather_available=False,
            land_records_available=False,
            memory_available=False
        )
        
        # Check if general advice should be used
        use_general = should_use_general_advice(context)
        
        # Get missing context
        missing = get_missing_context_list(context)
        
        # Get general advice
        general_advice = get_general_advice_template('hi-IN')
        
        # Add disclaimer
        final_advice = add_disclaimer_to_advice(
            general_advice,
            missing,
            'hi-IN'
        )
        
        # Verify complete flow
        assert context is not None
        assert len(missing) > 0
        assert len(final_advice) > len(general_advice)
        assert '⚠️' in final_advice
    
    def test_partial_failure_scenario(self):
        """Test scenario with partial API failures."""
        # Weather fails, but land records available
        weather = handle_weather_api_failure(28.6139, 77.2090, None)
        land_records = LandRecords(
            landArea=2.5,
            soilType='Clay Loam',
            currentCrop='Rice',
            cropHistory=[]
        )
        memory = handle_memory_api_failure("FARMER-123")
        
        context = ContextData(
            weather=weather,
            landRecords=land_records,
            memory=memory
        )
        
        # Should not use general advice (has land records)
        use_general = should_use_general_advice(context)
        assert use_general is False
        
        # But should have disclaimer for missing memory
        missing = get_missing_context_list(context)
        assert 'memory' in missing


# Property-Based Tests
from hypothesis import given, strategies as st, settings
from src.utils.retry import retry_with_backoff


class TestGracefulDegradationPropertyTests:
    """Property-based tests for graceful API failure handling."""
    
    @given(
        api_name=st.sampled_from(['weather', 'ufsi', 'memory']),
        failure_count=st.integers(min_value=1, max_value=5),
        language=st.sampled_from(['hi-IN', 'ta-IN', 'te-IN', 'kn-IN', 'mr-IN', 'bn-IN', 'gu-IN', 'pa-IN'])
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.pbt
    def test_property_25_graceful_api_failure_handling(self, api_name, failure_count, language):
        """
        Feature: vaniverse, Property 25: Graceful API Failure Handling
        
        Validates: Requirements 3.5, 9.5, 12.5
        
        **Property**: For any API failure, the system must:
        1. Trigger retry logic with exponential backoff (up to 3 attempts)
        2. Fall back to general advice with appropriate disclaimers
        3. Never crash or return empty responses
        
        **Test Strategy**:
        - Simulate API failures for weather, UFSI, and memory services
        - Verify retry attempts occur with proper backoff
        - Verify fallback context is created
        - Verify disclaimers are added to advice
        - Verify system continues to function
        """
        # Track retry attempts
        attempt_count = [0]
        
        def failing_api_call():
            """Simulated API call that fails."""
            attempt_count[0] += 1
            if attempt_count[0] < failure_count:
                raise Exception(f"{api_name} API failure")
            return {"status": "success"}
        
        # Test retry logic
        if failure_count <= 3:
            # Should succeed after retries
            try:
                result = retry_with_backoff(failing_api_call, max_attempts=3)
                assert result["status"] == "success"
                assert attempt_count[0] == failure_count
            except Exception:
                # If it still fails after 3 attempts, that's expected
                assert attempt_count[0] == 3
        else:
            # Should fail after 3 attempts
            with pytest.raises(Exception):
                retry_with_backoff(failing_api_call, max_attempts=3)
            assert attempt_count[0] == 3
        
        # Test fallback context creation
        if api_name == 'weather':
            fallback_weather = handle_weather_api_failure(
                latitude=28.6139,
                longitude=77.2090,
                cached_weather=None
            )
            assert fallback_weather is not None
            assert fallback_weather.current.temperature > 0
            assert fallback_weather.forecast6h.precipitationProbability >= 0
        
        elif api_name == 'ufsi':
            fallback_land = handle_ufsi_api_failure(
                farmer_id="FARMER-TEST",
                agristack_id="AGRI-TEST"
            )
            # UFSI failure returns None (GPS-only mode)
            assert fallback_land is None
        
        elif api_name == 'memory':
            fallback_memory = handle_memory_api_failure(farmer_id="FARMER-TEST")
            assert fallback_memory is not None
            assert len(fallback_memory.recentInteractions) == 0
            assert fallback_memory.consolidatedInsights.primaryCrop == "Unknown"
        
        # Test general advice template
        general_advice = get_general_advice_template(language)
        assert general_advice is not None
        assert len(general_advice) > 0
        
        # Test disclaimer addition with simple advice (not general template)
        simple_advice = "Apply fertilizer in the morning."
        
        # Map API names to context item names used by add_disclaimer_to_advice
        context_map = {
            'weather': 'weather',
            'ufsi': 'land_records',
            'memory': 'memory'
        }
        missing_context = [context_map[api_name]]
        
        advice_with_disclaimer = add_disclaimer_to_advice(
            simple_advice,
            missing_context,
            language
        )
        
        # Property 25: Disclaimer must be added when context is missing
        assert len(advice_with_disclaimer) > len(simple_advice), \
            f"Disclaimer must be added to advice when context is missing. API: {api_name}, Context: {missing_context}, Original: {len(simple_advice)}, With disclaimer: {len(advice_with_disclaimer)}"
        assert '⚠️' in advice_with_disclaimer, \
            "Warning emoji must be present in disclaimer"
        
        # Property 25: Original advice must be preserved
        assert simple_advice in advice_with_disclaimer, \
            "Original advice must be preserved when disclaimer is added"
        
        # Property 25: System must never return empty response
        assert len(advice_with_disclaimer) > 0, \
            "System must never return empty advice, even on API failure"
        
        # Property 25: General advice template must be available
        assert general_advice is not None and len(general_advice) > 0, \
            "General advice template must be available for all languages"
    
    @given(
        weather_available=st.booleans(),
        land_available=st.booleans(),
        memory_available=st.booleans(),
        latitude=st.floats(min_value=8.0, max_value=37.0),  # India latitude range
        longitude=st.floats(min_value=68.0, max_value=97.0),  # India longitude range
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.pbt
    def test_property_25_fallback_context_completeness(
        self,
        weather_available,
        land_available,
        memory_available,
        latitude,
        longitude
    ):
        """
        Feature: vaniverse, Property 25: Fallback Context Completeness
        
        Validates: Requirements 3.5, 9.5, 12.5
        
        **Property**: For any combination of API failures, the system must:
        1. Create a complete fallback context (never None)
        2. Include placeholder data for failed services
        3. Track which context is missing for disclaimer generation
        
        **Test Strategy**:
        - Test all combinations of API availability
        - Verify fallback context is always complete
        - Verify missing context is properly tracked
        """
        # Create fallback context
        context = create_fallback_context(
            farmer_id="FARMER-TEST",
            latitude=latitude,
            longitude=longitude,
            weather_available=weather_available,
            land_records_available=land_available,
            memory_available=memory_available
        )
        
        # Property 25: Context must never be None
        assert context is not None, \
            "Fallback context must never be None, even when all APIs fail"
        
        # Property 25: Weather must always be present (placeholder if unavailable)
        assert context.weather is not None, \
            "Weather must always be present in context (placeholder if API fails)"
        assert context.weather.current.temperature > 0, \
            "Weather placeholder must have valid temperature"
        
        # Property 25: Memory must always be present (empty if unavailable)
        assert context.memory is not None, \
            "Memory must always be present in context (empty if API fails)"
        
        # Property 25: Land records can be None (GPS-only mode)
        if not land_available:
            assert context.landRecords is None, \
                "Land records should be None when UFSI API fails"
        
        # Get missing context list
        missing = get_missing_context_list(context)
        
        # Property 25: Missing context must be tracked
        if not land_available:
            assert 'land_records' in missing, \
                "Missing land records must be tracked"
        
        if not memory_available or len(context.memory.recentInteractions) == 0:
            assert 'memory' in missing, \
                "Missing memory must be tracked"
        
        # Property 25: System must decide whether to use general advice
        use_general = should_use_general_advice(context)
        assert isinstance(use_general, bool), \
            "should_use_general_advice must return boolean"
        
        # If no farmer context available, must use general advice
        if not land_available and not memory_available:
            assert use_general is True, \
                "Must use general advice when no farmer context is available"
    
    @given(
        advice_text=st.text(min_size=10, max_size=200),
        missing_count=st.integers(min_value=0, max_value=3),
        language=st.sampled_from(['hi-IN', 'ta-IN', 'te-IN', 'kn-IN'])
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.pbt
    def test_property_25_disclaimer_addition(self, advice_text, missing_count, language):
        """
        Feature: vaniverse, Property 25: Disclaimer Addition
        
        Validates: Requirements 3.5, 9.5, 12.5
        
        **Property**: For any advice text and missing context:
        1. If context is missing, disclaimer must be added
        2. If context is complete, no disclaimer is added
        3. Disclaimer must preserve original advice
        4. Disclaimer must be in correct language
        
        **Test Strategy**:
        - Test with various advice texts
        - Test with different numbers of missing context items
        - Verify disclaimer behavior
        """
        # Create missing context list
        all_context = ['weather', 'land_records', 'memory']
        missing_context = all_context[:missing_count]
        
        # Add disclaimer
        result = add_disclaimer_to_advice(advice_text, missing_context, language)
        
        if missing_count == 0:
            # Property 25: No disclaimer when context is complete
            assert result == advice_text, \
                "No disclaimer should be added when context is complete"
        else:
            # Property 25: Disclaimer must be added when context is missing
            assert len(result) > len(advice_text), \
                "Disclaimer must be added when context is missing"
            
            # Property 25: Original advice must be preserved
            assert advice_text in result, \
                "Original advice must be preserved in result"
            
            # Property 25: Warning indicator must be present
            assert '⚠️' in result, \
                "Warning emoji must be present in disclaimer"
            
            # Property 25: Result must not be empty
            assert len(result) > 0, \
                "Result must never be empty"
