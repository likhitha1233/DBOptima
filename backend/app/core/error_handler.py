"""
Centralized error handling and logging utilities
"""

import logging
import traceback
import functools
from datetime import datetime
from .exceptions import DatabaseOptimizerException

logger = logging.getLogger(__name__)

class ErrorHandler:
    """Centralized error handling with logging and graceful degradation"""
    
    def __init__(self, logger_name: str = None):
        self.logger = logging.getLogger(logger_name or __name__)
        self.error_stats = {
            'total_errors': 0,
            'error_types': {},
            'last_error': None
        }
    
    def handle_exception(
        self, 
        exception: Exception, 
        context: str = None, 
        user_message: str = None,
        fallback_value: Any = None,
        reraise: bool = False
    ) -> Any:
        """
        Handle exception with logging and optional fallback
        
        Args:
            exception: The exception that occurred
            context: Context where the error occurred
            user_message: User-friendly error message
            fallback_value: Value to return instead of raising
            reraise: Whether to re-raise the exception
        
        Returns:
            fallback_value if provided and reraise is False
        """
        # Update error statistics
        self.error_stats['total_errors'] += 1
        error_type = type(exception).__name__
        self.error_stats['error_types'][error_type] = self.error_stats['error_types'].get(error_type, 0) + 1
        self.error_stats['last_error'] = {
            'type': error_type,
            'message': str(exception),
            'context': context,
            'timestamp': datetime.now().isoformat()
        }
        
        # Log the error
        self._log_error(exception, context)
        
        # Return fallback or re-raise
        if reraise:
            raise exception
        elif fallback_value is not None:
            if user_message:
                self.logger.warning(f"Using fallback due to error: {user_message}")
            return fallback_value
        else:
            # Return error response for API calls
            return self._create_error_response(exception, user_message)
    
    def _log_error(self, exception: Exception, context: str = None):
        """Log error with appropriate level and details"""
        error_msg = f"Error in {context}: {str(exception)}" if context else str(exception)
        
        if isinstance(exception, DatabaseOptimizerException):
            # Log custom exceptions with details
            self.logger.error(
                f"{error_msg} [Code: {getattr(exception, 'error_code', 'UNKNOWN')}]"
                f"\nDetails: {getattr(exception, 'details', {})}"
                f"\nTraceback: {traceback.format_exc()}"
            )
        else:
            # Log unexpected exceptions
            self.logger.error(
                f"Unexpected error: {error_msg}"
                f"\nTraceback: {traceback.format_exc()}"
            )
    
    def _create_error_response(self, exception: Exception, user_message: str = None) -> Dict[str, Any]:
        """Create standardized error response for APIs"""
        if isinstance(exception, DatabaseOptimizerException):
            return {
                "status": "error",
                "error_code": getattr(exception, 'error_code', 'UNKNOWN'),
                "message": user_message or str(exception),
                "details": getattr(exception, 'details', {}),
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": user_message or "An internal error occurred",
                "details": {"original_error": str(exception)},
                "timestamp": datetime.now().isoformat()
            }
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        return self.error_stats.copy()

# Global error handler instance
global_error_handler = ErrorHandler()

def handle_errors(
    context: str = None,
    fallback_value: Any = None,
    user_message: str = None,
    reraise: bool = False,
    exception_types: Union[Type[Exception], tuple] = Exception
):
    """
    Decorator for automatic error handling
    
    Args:
        context: Context description for error logging
        fallback_value: Value to return on error
        user_message: User-friendly error message
        reraise: Whether to re-raise exceptions
        exception_types: Exception types to catch
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception_types as e:
                func_context = context or f"{func.__module__}.{func.__name__}"
                return global_error_handler.handle_exception(
                    exception=e,
                    context=func_context,
                    user_message=user_message,
                    fallback_value=fallback_value,
                    reraise=reraise
                )
        return wrapper
    return decorator

def safe_execute(
    func: Callable,
    args: tuple = (),
    kwargs: dict = None,
    context: str = None,
    fallback_value: Any = None,
    user_message: str = None
) -> Any:
    """
    Safely execute a function with error handling
    
    Args:
        func: Function to execute
        args: Function arguments
        kwargs: Function keyword arguments
        context: Context description
        fallback_value: Value to return on error
        user_message: User-friendly error message
    
    Returns:
        Function result or fallback value
    """
    kwargs = kwargs or {}
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return global_error_handler.handle_exception(
            exception=e,
            context=context,
            user_message=user_message,
            fallback_value=fallback_value
        )

def validate_input(value: Any, field_name: str, validator: Callable, error_message: str = None) -> Any:
    """
    Validate input with custom validator
    
    Args:
        value: Value to validate
        field_name: Name of the field for error reporting
        validator: Validation function that raises ValueError on invalid input
        error_message: Custom error message
    
    Returns:
        Validated value
    
    Raises:
        ValidationError: If validation fails
    """
    try:
        validator(value)
        return value
    except ValueError as e:
        from .exceptions import ValidationError
        raise ValidationError(
            message=error_message or f"Invalid {field_name}: {str(e)}",
            field=field_name,
            value=str(value)
        )

def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying functions on failure
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff: Multiplier for delay on each retry
        exceptions: Exception types to retry on
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        # Last attempt failed
                        break
                    
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}. "
                        f"Retrying in {current_delay:.1f} seconds..."
                    )
                    import time
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            # All attempts failed, handle the error
            return global_error_handler.handle_exception(
                exception=last_exception,
                context=f"{func.__module__}.{func.__name__} (after {max_attempts} attempts)",
                user_message=f"Operation failed after {max_attempts} attempts"
            )
        return wrapper
    return decorator

def log_performance(func: Callable) -> Callable:
    """
    Decorator for logging function performance
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        try:
            result = func(*args, **kwargs)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(
                f"Performance: {func.__module__}.{func.__name__} "
                f"completed in {duration:.3f}s"
            )
            
            return result
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.error(
                f"Performance: {func.__module__}.{func.__name__} "
                f"failed after {duration:.3f}s: {str(e)}"
            )
            raise
    
    return wrapper

class CircuitBreaker:
    """
    Circuit breaker pattern for handling repeated failures
    """
    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable, *args, **kwargs):
        """Call function with circuit breaker protection"""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise DatabaseOptimizerException(
                    f"Circuit breaker is OPEN for {func.__name__}",
                    error_code="CIRCUIT_BREAKER_OPEN"
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt to reset"""
        import time
        return time.time() - self.last_failure_time > self.timeout
    
    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self):
        """Handle failed call"""
        import time
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
