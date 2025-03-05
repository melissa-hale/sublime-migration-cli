"""Utilities for error handling in the Sublime Migration CLI."""
from typing import Any, Dict, Optional, Type, Union


class SublimeError(Exception):
    """Base exception class for all Sublime Migration CLI errors."""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        """
        Initialize a Sublime error.
        
        Args:
            message: Error message
            details: Optional detailed error information
        """
        self.message = message
        self.details = details
        super().__init__(message)


class ApiError(SublimeError):
    """Exception raised for errors related to API calls."""
    
    def __init__(self, message: str, 
                status_code: Optional[int] = None, 
                response: Optional[Dict] = None, 
                request_info: Optional[Dict] = None):
        """
        Initialize an API error.
        
        Args:
            message: Error message
            status_code: HTTP status code
            response: API response data
            request_info: Information about the request that caused the error
        """
        self.status_code = status_code
        self.response = response
        self.request_info = request_info
        
        # Construct a detailed message including status code if available
        detailed_message = message
        if status_code:
            detailed_message = f"API Error ({status_code}): {message}"
        
        super().__init__(detailed_message, {
            "status_code": status_code,
            "response": response,
            "request_info": request_info
        })


class AuthenticationError(ApiError):
    """Exception raised for authentication-related errors."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        """Initialize an authentication error."""
        super().__init__(message, **kwargs)


class ResourceNotFoundError(ApiError):
    """Exception raised when a requested resource is not found."""
    
    def __init__(self, resource_type: str, resource_id: str, **kwargs):
        """
        Initialize a resource not found error.
        
        Args:
            resource_type: Type of resource (e.g., "rule", "action")
            resource_id: ID of the resource that was not found
            **kwargs: Additional arguments to pass to ApiError
        """
        message = f"{resource_type.capitalize()} with ID '{resource_id}' not found"
        super().__init__(message, **kwargs)
        self.resource_type = resource_type
        self.resource_id = resource_id


class ConfigurationError(SublimeError):
    """Exception raised for configuration-related errors."""
    
    def __init__(self, message: str, config_key: Optional[str] = None):
        """
        Initialize a configuration error.
        
        Args:
            message: Error message
            config_key: Key in configuration that caused the error
        """
        self.config_key = config_key
        super().__init__(message, {"config_key": config_key})


class ValidationError(SublimeError):
    """Exception raised for data validation errors."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None):
        """
        Initialize a validation error.
        
        Args:
            message: Error message
            field: Field that failed validation
            value: Value that failed validation
        """
        self.field = field
        self.value = value
        super().__init__(message, {"field": field, "value": value})


class MigrationError(SublimeError):
    """Exception raised for errors during migration operations."""
    
    def __init__(self, message: str, 
                stage: Optional[str] = None, 
                resource_type: Optional[str] = None,
                resource_name: Optional[str] = None):
        """
        Initialize a migration error.
        
        Args:
            message: Error message
            stage: Migration stage where the error occurred
            resource_type: Type of resource being migrated
            resource_name: Name of the resource being migrated
        """
        self.stage = stage
        self.resource_type = resource_type
        self.resource_name = resource_name
        
        super().__init__(message, {
            "stage": stage,
            "resource_type": resource_type,
            "resource_name": resource_name
        })


def handle_api_error(error: Exception) -> SublimeError:
    """
    Convert a requests.Exception into a SublimeError.
    
    Args:
        error: Original exception from requests library
        
    Returns:
        SublimeError: Converted exception
    """
    import requests
    
    if isinstance(error, requests.exceptions.HTTPError):
        response = error.response
        status_code = response.status_code
        request = error.request
        
        # Try to parse response as JSON
        try:
            response_data = response.json()
        except (ValueError, TypeError):
            response_data = {"raw": response.text}
        
        # Extract error message from response or use default
        error_message = response_data.get("error", {}).get("message", str(error))
        
        # Create appropriate error based on status code
        if status_code == 401:
            return AuthenticationError(
                error_message, 
                status_code=status_code,
                response=response_data,
                request_info={"method": request.method, "url": request.url}
            )
        elif status_code == 404:
            # Try to determine resource type and ID from URL
            url_parts = request.url.rstrip('/').split('/')
            resource_type = url_parts[-2] if len(url_parts) >= 2 else "resource"
            resource_id = url_parts[-1]
            
            return ResourceNotFoundError(
                resource_type, 
                resource_id,
                status_code=status_code,
                response=response_data,
                request_info={"method": request.method, "url": request.url}
            )
        else:
            return ApiError(
                error_message,
                status_code=status_code,
                response=response_data,
                request_info={"method": request.method, "url": request.url}
            )
    
    elif isinstance(error, requests.exceptions.ConnectionError):
        return ApiError(f"Connection error: {str(error)}")
    
    elif isinstance(error, requests.exceptions.Timeout):
        return ApiError(f"Request timed out: {str(error)}")
    
    elif isinstance(error, requests.exceptions.RequestException):
        return ApiError(f"Request error: {str(error)}")
    
    # If it's already a SublimeError, return it directly
    elif isinstance(error, SublimeError):
        return error
    
    # For any other exception type, wrap it in a generic SublimeError
    return SublimeError(f"Unexpected error: {str(error)}")


class ErrorHandler:
    """Handler for managing and processing errors in the CLI."""
    
    @staticmethod
    def is_fatal_error(error: Exception) -> bool:
        """
        Determine if an error should terminate the program.
        
        Args:
            error: The exception to check
            
        Returns:
            bool: True if the error is fatal, False otherwise
        """
        # Authentication errors are always fatal
        if isinstance(error, AuthenticationError):
            return True
        
        # Configuration errors are fatal
        if isinstance(error, ConfigurationError):
            return True
        
        # Other API errors depend on the status code
        if isinstance(error, ApiError) and error.status_code:
            # 5xx errors are fatal
            if error.status_code >= 500:
                return True
        
        # By default, other errors are not fatal
        return False
    
    @staticmethod
    def format_error_for_display(error: Exception) -> Dict[str, Any]:
        """
        Format an error for display in the CLI.
        
        Args:
            error: The exception to format
            
        Returns:
            Dict: Formatted error information
        """
        if isinstance(error, SublimeError):
            result = {
                "message": error.message,
                "type": error.__class__.__name__
            }
            
            if error.details:
                result["details"] = error.details
                
            # Add specific fields for specific error types
            if isinstance(error, ApiError) and error.status_code:
                result["status_code"] = error.status_code
                
            if isinstance(error, ResourceNotFoundError):
                result["resource_type"] = error.resource_type
                result["resource_id"] = error.resource_id
                
            if isinstance(error, ValidationError):
                result["field"] = error.field
                
            if isinstance(error, MigrationError):
                result["stage"] = error.stage
                result["resource_type"] = error.resource_type
                
            return result
        else:
            # For standard exceptions, just use the string representation
            return {
                "message": str(error),
                "type": error.__class__.__name__
            }