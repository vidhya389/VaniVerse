"""
Tests for retry logic with exponential backoff.

Tests Requirement 9.5: Retry failed API calls up to 3 times with exponential backoff
"""

import pytest
import time
from unittest.mock import Mock, patch

from src.utils.retry import (
    retry_with_backoff,
    with_retry,
    retry_api_call,
    is_retryable_error,
    smart_retry,
    RetryableError,
    NonRetryableError
)


class TestRetryWithBackoff:
    """Tests for retry_with_backoff function."""
    
    def test_successful_first_attempt(self):
        """Test that successful calls don't retry."""
        mock_func = Mock(return_value="success")
        
        result = retry_with_backoff(mock_func, max_attempts=3)
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    def test_retry_on_failure(self):
        """Test that failures trigger retries."""
        mock_func = Mock(side_effect=[
            Exception("Attempt 1 failed"),
            Exception("Attempt 2 failed"),
            "success"
        ])
        
        result = retry_with_backoff(mock_func, max_attempts=3, base_delay=0.1)
        
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_all_attempts_fail(self):
        """Test that exception is raised after all attempts fail."""
        mock_func = Mock(side_effect=Exception("Always fails"))
        
        with pytest.raises(Exception, match="Always fails"):
            retry_with_backoff(mock_func, max_attempts=3, base_delay=0.1)
        
        assert mock_func.call_count == 3
    
    def test_exponential_backoff_timing(self):
        """Test that delays follow exponential backoff pattern."""
        mock_func = Mock(side_effect=[
            Exception("Fail 1"),
            Exception("Fail 2"),
            "success"
        ])
        
        start_time = time.time()
        result = retry_with_backoff(
            mock_func,
            max_attempts=3,
            base_delay=0.1,
            exponential_base=2.0
        )
        elapsed_time = time.time() - start_time
        
        # Expected delays: 0.1s (1st retry) + 0.2s (2nd retry) = 0.3s minimum
        assert result == "success"
        assert elapsed_time >= 0.3
        assert elapsed_time < 1.0  # Should not take too long
    
    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        mock_func = Mock(side_effect=[
            Exception("Fail 1"),
            Exception("Fail 2"),
            "success"
        ])
        
        start_time = time.time()
        result = retry_with_backoff(
            mock_func,
            max_attempts=3,
            base_delay=1.0,
            max_delay=0.5,  # Cap at 0.5 seconds
            exponential_base=2.0
        )
        elapsed_time = time.time() - start_time
        
        # With cap, delays should be: 0.5s + 0.5s = 1.0s maximum
        assert result == "success"
        assert elapsed_time < 1.5
    
    def test_specific_exception_types(self):
        """Test that only specified exceptions trigger retries."""
        mock_func = Mock(side_effect=ValueError("Wrong type"))
        
        # Should not retry ValueError if only catching ConnectionError
        with pytest.raises(ValueError):
            retry_with_backoff(
                mock_func,
                max_attempts=3,
                base_delay=0.1,
                exceptions=(ConnectionError,)
            )
        
        # Should only be called once (no retries)
        assert mock_func.call_count == 1


class TestWithRetryDecorator:
    """Tests for @with_retry decorator."""
    
    def test_decorator_successful_call(self):
        """Test decorator on successful function."""
        @with_retry(max_attempts=3, base_delay=0.1)
        def successful_func():
            return "success"
        
        result = successful_func()
        assert result == "success"
    
    def test_decorator_with_retries(self):
        """Test decorator retries on failure."""
        call_count = {'count': 0}
        
        @with_retry(max_attempts=3, base_delay=0.1)
        def failing_func():
            call_count['count'] += 1
            if call_count['count'] < 3:
                raise Exception("Not yet")
            return "success"
        
        result = failing_func()
        assert result == "success"
        assert call_count['count'] == 3
    
    def test_decorator_with_arguments(self):
        """Test decorator on function with arguments."""
        @with_retry(max_attempts=3, base_delay=0.1)
        def func_with_args(x, y):
            if x + y < 10:
                raise Exception("Too small")
            return x + y
        
        result = func_with_args(5, 6)
        assert result == 11


class TestRetryApiCall:
    """Tests for retry_api_call convenience function."""
    
    def test_successful_api_call(self):
        """Test successful API call without retries."""
        mock_api = Mock(return_value={"data": "success"})
        
        result = retry_api_call(mock_api, operation_name="Test API")
        
        assert result == {"data": "success"}
        assert mock_api.call_count == 1
    
    def test_api_call_with_retries(self):
        """Test API call that succeeds after retries."""
        mock_api = Mock(side_effect=[
            RetryableError("Temporary failure"),
            RetryableError("Still failing"),
            {"data": "success"}
        ])
        
        result = retry_api_call(mock_api, operation_name="Test API", max_attempts=3)
        
        assert result == {"data": "success"}
        assert mock_api.call_count == 3
    
    def test_api_call_all_attempts_fail(self):
        """Test API call that fails all attempts."""
        mock_api = Mock(side_effect=RetryableError("Always fails"))
        
        with pytest.raises(RetryableError):
            retry_api_call(mock_api, operation_name="Test API", max_attempts=3)
        
        assert mock_api.call_count == 3


class TestIsRetryableError:
    """Tests for is_retryable_error function."""
    
    def test_retryable_errors(self):
        """Test that retryable errors are identified correctly."""
        assert is_retryable_error(RetryableError("Test"))
        assert is_retryable_error(ConnectionError("Network issue"))
        assert is_retryable_error(TimeoutError("Timeout"))
    
    def test_non_retryable_errors(self):
        """Test that non-retryable errors are identified correctly."""
        assert not is_retryable_error(NonRetryableError("Don't retry"))
    
    def test_http_status_codes(self):
        """Test HTTP status code detection."""
        # Retryable status codes
        error_503 = Exception("Service unavailable")
        error_503.status_code = 503
        assert is_retryable_error(error_503)
        
        error_429 = Exception("Too many requests")
        error_429.status_code = 429
        assert is_retryable_error(error_429)
        
        # Non-retryable status codes
        error_401 = Exception("Unauthorized")
        error_401.status_code = 401
        assert not is_retryable_error(error_401)
        
        error_404 = Exception("Not found")
        error_404.status_code = 404
        assert not is_retryable_error(error_404)
    
    def test_generic_exceptions(self):
        """Test that generic exceptions are retryable by default."""
        assert is_retryable_error(Exception("Generic error"))
        assert is_retryable_error(RuntimeError("Runtime error"))


class TestSmartRetry:
    """Tests for smart_retry function."""
    
    def test_smart_retry_success(self):
        """Test smart retry on successful call."""
        mock_func = Mock(return_value="success")
        
        result = smart_retry(mock_func, max_attempts=3, base_delay=0.1)
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    def test_smart_retry_retryable_error(self):
        """Test smart retry retries on retryable errors."""
        mock_func = Mock(side_effect=[
            RetryableError("Temporary"),
            "success"
        ])
        
        result = smart_retry(mock_func, max_attempts=3, base_delay=0.1)
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    def test_smart_retry_non_retryable_error(self):
        """Test smart retry doesn't retry on non-retryable errors."""
        mock_func = Mock(side_effect=NonRetryableError("Don't retry"))
        
        with pytest.raises(NonRetryableError):
            smart_retry(mock_func, max_attempts=3, base_delay=0.1)
        
        # Should only be called once (no retries)
        assert mock_func.call_count == 1
    
    def test_smart_retry_http_errors(self):
        """Test smart retry handles HTTP errors correctly."""
        # 503 should retry
        error_503 = Exception("Service unavailable")
        error_503.status_code = 503
        
        mock_func = Mock(side_effect=[error_503, "success"])
        result = smart_retry(mock_func, max_attempts=3, base_delay=0.1)
        
        assert result == "success"
        assert mock_func.call_count == 2
        
        # 401 should not retry
        error_401 = Exception("Unauthorized")
        error_401.status_code = 401
        
        mock_func = Mock(side_effect=error_401)
        with pytest.raises(Exception, match="Unauthorized"):
            smart_retry(mock_func, max_attempts=3, base_delay=0.1)
        
        assert mock_func.call_count == 1


class TestRetryIntegration:
    """Integration tests for retry logic."""
    
    def test_retry_pattern_1s_2s_4s(self):
        """Test that retry follows 1s, 2s, 4s delay pattern as specified."""
        mock_func = Mock(side_effect=[
            Exception("Fail 1"),
            Exception("Fail 2"),
            Exception("Fail 3")
        ])
        
        start_time = time.time()
        
        with pytest.raises(Exception):
            retry_with_backoff(
                mock_func,
                max_attempts=3,
                base_delay=1.0,
                exponential_base=2.0
            )
        
        elapsed_time = time.time() - start_time
        
        # Expected: 1s + 2s = 3s minimum (no delay after last attempt)
        assert elapsed_time >= 3.0
        assert elapsed_time < 4.0  # Should not take much longer
        assert mock_func.call_count == 3
    
    @patch('src.utils.retry.logger')
    def test_retry_logging(self, mock_logger):
        """Test that retry logic logs appropriately."""
        mock_func = Mock(side_effect=[
            Exception("Fail 1"),
            "success"
        ])
        
        result = retry_with_backoff(mock_func, max_attempts=3, base_delay=0.1)
        
        assert result == "success"
        
        # Verify logging calls
        assert mock_logger.warning.called
        assert mock_logger.info.called
    
    def test_real_world_api_scenario(self):
        """Test retry logic in a realistic API scenario."""
        # Simulate API that fails twice then succeeds
        api_responses = [
            ConnectionError("Network timeout"),
            ConnectionError("Connection refused"),
            {"status": "ok", "data": [1, 2, 3]}
        ]
        
        call_count = {'count': 0}
        
        def mock_api_call():
            response = api_responses[call_count['count']]
            call_count['count'] += 1
            if isinstance(response, Exception):
                raise response
            return response
        
        result = retry_api_call(
            mock_api_call,
            operation_name="External API",
            max_attempts=3
        )
        
        assert result == {"status": "ok", "data": [1, 2, 3]}
        assert call_count['count'] == 3
