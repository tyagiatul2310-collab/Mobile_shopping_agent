"""Error Handler - Graceful error handling for API calls."""
import time
import requests
from typing import Optional, Dict, Any, Tuple
from enum import Enum

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ErrorType(Enum):
    """Types of errors we can handle."""
    RATE_LIMIT = "rate_limit"
    API_ERROR = "api_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    INVALID_RESPONSE = "invalid_response"
    UNKNOWN = "unknown"


class APIErrorHandler:
    """Handles API errors gracefully with user-friendly messages."""

    @staticmethod
    def classify_error(exception: Exception, response: Optional[requests.Response] = None) -> Tuple[ErrorType, str]:
        """Classify an error and return error type and user-friendly message.
        
        Args:
            exception: The exception that occurred
            response: Optional HTTP response object
            
        Returns:
            Tuple of (ErrorType, user_friendly_message)
        """
        error_str = str(exception).lower()
        
        # Check for rate limiting (429)
        if response and response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")
            return (
                ErrorType.RATE_LIMIT,
                f"⏳ **Rate Limit Reached**\n\n"
                f"I'm processing too many requests right now. Please wait about {retry_after} seconds and try again.\n\n"
                f"💡 **Tip:** The free tier has rate limits. Try waiting a minute between queries, or consider upgrading your API plan."
            )
        
        # Check for other HTTP errors
        if response:
            status = response.status_code
            if status == 400:
                return (
                    ErrorType.API_ERROR,
                    "⚠️ **Invalid Request**\n\n"
                    "The request couldn't be processed. Please try rephrasing your question or check your query."
                )
            elif status == 401:
                return (
                    ErrorType.API_ERROR,
                    "🔐 **Authentication Error**\n\n"
                    "There's an issue with API authentication. Please check your API key configuration."
                )
            elif status == 403:
                return (
                    ErrorType.API_ERROR,
                    "🚫 **Access Denied**\n\n"
                    "Access to the API is restricted. Please check your API permissions."
                )
            elif status == 500:
                return (
                    ErrorType.API_ERROR,
                    "🔧 **Service Temporarily Unavailable**\n\n"
                    "The AI service is experiencing issues. Please try again in a few moments."
                )
            elif status == 503:
                return (
                    ErrorType.API_ERROR,
                    "⏸️ **Service Overloaded**\n\n"
                    "The service is currently overloaded. Please wait a moment and try again."
                )
        
        # Network errors
        if isinstance(exception, requests.exceptions.ConnectionError):
            return (
                ErrorType.NETWORK_ERROR,
                "🌐 **Connection Error**\n\n"
                "Couldn't connect to the AI service. Please check your internet connection and try again."
            )
        
        if isinstance(exception, requests.exceptions.Timeout):
            return (
                ErrorType.TIMEOUT,
                "⏱️ **Request Timeout**\n\n"
                "The request took too long to complete. Please try again with a simpler query."
            )
        
        # Rate limit in error message
        if "429" in error_str or "rate limit" in error_str or "quota" in error_str:
            return (
                ErrorType.RATE_LIMIT,
                "⏳ **Rate Limit Reached**\n\n"
                "I'm processing too many requests. Please wait about 60 seconds and try again.\n\n"
                "💡 **Tip:** Free tier has rate limits. Wait a minute between queries for best results."
            )
        
        # Default error
        return (
            ErrorType.UNKNOWN,
            "😔 **Something Went Wrong**\n\n"
            "I encountered an unexpected error. Please try again in a moment, or rephrase your question.\n\n"
            "If this persists, the service might be temporarily unavailable."
        )

    @staticmethod
    def handle_with_retry(
        func,
        max_retries: int = 2,
        retry_delay: float = 2.0,
        backoff_factor: float = 2.0,
        retry_on_rate_limit: bool = True
    ) -> Tuple[Any, Optional[Dict[str, Any]]]:
        """Execute a function with retry logic for rate limits.
        
        Args:
            func: Function to execute (should raise requests.HTTPError on failure)
            max_retries: Maximum number of retries
            retry_delay: Initial delay between retries (seconds)
            backoff_factor: Multiplier for retry delay
            retry_on_rate_limit: Whether to retry on rate limit errors
            
        Returns:
            Tuple of (result, error_info). error_info is None on success.
        """
        last_exception = None
        last_response = None
        
        for attempt in range(max_retries + 1):
            try:
                result = func()
                return result, None
            except requests.exceptions.HTTPError as e:
                last_exception = e
                last_response = e.response if hasattr(e, 'response') else None
                
                # Check if it's a rate limit error
                if last_response and last_response.status_code == 429:
                    if not retry_on_rate_limit or attempt >= max_retries:
                        error_type, message = APIErrorHandler.classify_error(e, last_response)
                        return None, {
                            "type": error_type,
                            "message": message,
                            "retry_after": int(last_response.headers.get("Retry-After", 60))
                        }
                    
                    # Calculate retry delay
                    retry_after = int(last_response.headers.get("Retry-After", retry_delay * (backoff_factor ** attempt)))
                    logger.warning(f"Rate limit hit, retrying after {retry_after}s (attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(retry_after)
                    continue
                
                # For other HTTP errors, don't retry
                error_type, message = APIErrorHandler.classify_error(e, last_response)
                return None, {
                    "type": error_type,
                    "message": message
                }
                
            except requests.exceptions.RequestException as e:
                last_exception = e
                # For network errors, retry with backoff
                if attempt < max_retries:
                    delay = retry_delay * (backoff_factor ** attempt)
                    logger.warning(f"Network error, retrying after {delay}s (attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(delay)
                    continue
                
                error_type, message = APIErrorHandler.classify_error(e)
                return None, {
                    "type": error_type,
                    "message": message
                }
                
            except Exception as e:
                # For other exceptions, don't retry
                error_type, message = APIErrorHandler.classify_error(e)
                return None, {
                    "type": error_type,
                    "message": message
                }
        
        # If we exhausted retries
        error_type, message = APIErrorHandler.classify_error(last_exception, last_response)
        return None, {
            "type": error_type,
            "message": message
        }

    @staticmethod
    def get_user_friendly_message(error_info: Dict[str, Any]) -> str:
        """Get user-friendly error message from error info.
        
        Args:
            error_info: Error info dict from handle_with_retry
            
        Returns:
            User-friendly error message
        """
        return error_info.get("message", "An unexpected error occurred. Please try again.")

