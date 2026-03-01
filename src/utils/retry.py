"""
Retry logic with exponential backoff for external API calls.

Implements Requirement 9.5: Retry failed API calls up to 3 times with exponential backoff
"""

import time
import logging
from typing import Callable, TypeVar, Optional, Type, Tuple
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_with_backoff(
    func: Callable[..., T],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> T:
    """
    Retry a function with exponential backoff.
    
    Args:
        func: Function to retry
        max_attempts: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 10.0)
        exponential_base: Base for exponential calculation (default: 2.0)
        exceptions: Tuple of exception types to catch and retry
        
    Returns:
        Result of the function call
        
    Raises:
        Last exception if all retries fail
        
    Example:
        >>> result = retry_with_backoff(lambda: api_call(), max_attempts=3)
        
    Validates:
        Requirement 9.5
    """
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            result = func()
            if attempt > 0:
                logger.info(f"Retry succeeded on attempt {attempt + 1}")
            return result
            
        except exceptions as e:
            last_exception = e
            
            if attempt == max_attempts - 1:
                # Last attempt failed, raise the exception
                logger.error(f"All {max_attempts} retry attempts failed: {str(e)}")
                raise
            
            # Calculate delay with exponential backoff
            delay = min(base_delay * (exponential_base ** attempt), max_delay)
            
            logger.warning(
                f"Attempt {attempt + 1}/{max_attempts} failed: {str(e)}. "
                f"Retrying in {delay:.2f} seconds..."
            )
            
            time.sleep(delay)
    
    # Should never reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic failed unexpectedly")


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator for adding retry logic with exponential backoff to functions.
    
    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 10.0)
        exponential_base: Base for exponential calculation (default: 2.0)
        exceptions: Tuple of exception types to catch and retry
        
    Returns:
        Decorated function with retry logic
        
    Example:
        >>> @with_retry(max_attempts=3, base_delay=1.0)
        >>> def fetch_data():
        >>>     return api_call()
        
    Validates:
        Requirement 9.5
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return retry_with_backoff(
                lambda: func(*args, **kwargs),
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                exceptions=exceptions
            )
        return wrapper
    return decorator


class RetryableError(Exception):
    """Base exception for errors that should trigger retries."""
    pass


class NonRetryableError(Exception):
    """Exception for errors that should not trigger retries."""
    pass


def retry_api_call(
    func: Callable[..., T],
    operation_name: str = "API call",
    max_attempts: int = 3
) -> T:
    """
    Convenience function for retrying API calls with standard configuration.
    
    Uses 1s, 2s, 4s delay pattern as specified in requirements.
    
    Args:
        func: API call function to retry
        operation_name: Name of the operation for logging
        max_attempts: Maximum number of attempts (default: 3)
        
    Returns:
        Result of the API call
        
    Raises:
        Last exception if all retries fail
        
    Example:
        >>> weather_data = retry_api_call(
        >>>     lambda: fetch_weather(lat, lon),
        >>>     operation_name="OpenWeather API"
        >>> )
        
    Validates:
        Requirement 9.5
    """
    logger.info(f"Executing {operation_name} with retry logic")
    
    try:
        return retry_with_backoff(
            func,
            max_attempts=max_attempts,
            base_delay=1.0,
            exponential_base=2.0,
            exceptions=(RetryableError, ConnectionError, TimeoutError)
        )
    except Exception as e:
        logger.error(f"{operation_name} failed after {max_attempts} attempts: {str(e)}")
        raise


def is_retryable_error(exception: Exception) -> bool:
    """
    Determine if an exception should trigger a retry.
    
    Args:
        exception: Exception to check
        
    Returns:
        True if the error is retryable, False otherwise
        
    Retryable errors include:
    - Network errors (ConnectionError, TimeoutError)
    - Temporary service errors (503, 429)
    - RetryableError instances
    
    Non-retryable errors include:
    - Authentication errors (401, 403)
    - Client errors (400, 404)
    - NonRetryableError instances
    """
    # Check exception type
    if isinstance(exception, NonRetryableError):
        return False
    
    if isinstance(exception, (RetryableError, ConnectionError, TimeoutError)):
        return True
    
    # Check HTTP status codes if available
    if hasattr(exception, 'status_code'):
        status_code = exception.status_code
        
        # Retryable HTTP status codes
        retryable_codes = {429, 500, 502, 503, 504}
        if status_code in retryable_codes:
            return True
        
        # Non-retryable HTTP status codes
        non_retryable_codes = {400, 401, 403, 404}
        if status_code in non_retryable_codes:
            return False
    
    # Default: retry on generic exceptions
    return True


def smart_retry(
    func: Callable[..., T],
    max_attempts: int = 3,
    base_delay: float = 1.0
) -> T:
    """
    Retry function with smart error detection.
    
    Only retries on retryable errors (network issues, temporary failures).
    Immediately raises non-retryable errors (auth failures, bad requests).
    
    Args:
        func: Function to retry
        max_attempts: Maximum number of attempts
        base_delay: Initial delay in seconds
        
    Returns:
        Result of the function call
        
    Raises:
        Exception if all retries fail or error is non-retryable
        
    Example:
        >>> result = smart_retry(lambda: api_call())
        
    Validates:
        Requirement 9.5
    """
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            return func()
            
        except Exception as e:
            last_exception = e
            
            # Check if error is retryable
            if not is_retryable_error(e):
                logger.error(f"Non-retryable error encountered: {str(e)}")
                raise
            
            if attempt == max_attempts - 1:
                logger.error(f"All {max_attempts} retry attempts failed: {str(e)}")
                raise
            
            # Calculate delay
            delay = base_delay * (2 ** attempt)
            logger.warning(
                f"Retryable error on attempt {attempt + 1}/{max_attempts}: {str(e)}. "
                f"Retrying in {delay:.2f} seconds..."
            )
            time.sleep(delay)
    
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic failed unexpectedly")
