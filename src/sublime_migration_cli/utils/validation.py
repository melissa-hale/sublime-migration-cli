"""Validation utilities for input validation."""
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union

from sublime_migration_cli.utils.errors import ValidationError

T = TypeVar('T')  # Generic type for values being validated

def validate_required(
    value: Optional[T],
    name: str,
    custom_message: Optional[str] = None
) -> T:
    """Validate that a required value is provided and not None.
    
    Args:
        value: Value to validate
        name: Name of the value (for error messages)
        custom_message: Optional custom error message
        
    Returns:
        T: The validated value
        
    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        message = custom_message or f"{name} is required"
        raise ValidationError(message)
    return value


def validate_not_empty(
    value: Union[str, List, Dict, Set],
    name: str,
    custom_message: Optional[str] = None
) -> Union[str, List, Dict, Set]:
    """Validate that a value is not empty.
    
    Args:
        value: Value to validate
        name: Name of the value (for error messages)
        custom_message: Optional custom error message
        
    Returns:
        Union[str, List, Dict, Set]: The validated value
        
    Raises:
        ValidationError: If validation fails
    """
    if not value:
        message = custom_message or f"{name} cannot be empty"
        raise ValidationError(message)
    return value


def validate_min_length(
    value: Union[str, List],
    min_length: int,
    name: str,
    custom_message: Optional[str] = None
) -> Union[str, List]:
    """Validate that a value has at least the minimum length.
    
    Args:
        value: Value to validate
        min_length: Minimum required length
        name: Name of the value (for error messages)
        custom_message: Optional custom error message
        
    Returns:
        Union[str, List]: The validated value
        
    Raises:
        ValidationError: If validation fails
    """
    if len(value) < min_length:
        message = custom_message or f"{name} must be at least {min_length} characters/items long"
        raise ValidationError(message)
    return value


def validate_max_length(
    value: Union[str, List],
    max_length: int,
    name: str,
    custom_message: Optional[str] = None
) -> Union[str, List]:
    """Validate that a value does not exceed the maximum length.
    
    Args:
        value: Value to validate
        max_length: Maximum allowed length
        name: Name of the value (for error messages)
        custom_message: Optional custom error message
        
    Returns:
        Union[str, List]: The validated value
        
    Raises:
        ValidationError: If validation fails
    """
    if len(value) > max_length:
        message = custom_message or f"{name} must not exceed {max_length} characters/items"
        raise ValidationError(message)
    return value


def validate_pattern(
    value: str,
    pattern: str,
    name: str,
    custom_message: Optional[str] = None
) -> str:
    """Validate that a string matches a regular expression pattern.
    
    Args:
        value: String to validate
        pattern: Regular expression pattern
        name: Name of the value (for error messages)
        custom_message: Optional custom error message
        
    Returns:
        str: The validated string
        
    Raises:
        ValidationError: If validation fails
    """
    if not re.match(pattern, value):
        message = custom_message or f"{name} has an invalid format"
        raise ValidationError(message)
    return value


def validate_in_set(
    value: T,
    valid_values: Set[T],
    name: str,
    custom_message: Optional[str] = None
) -> T:
    """Validate that a value is in a set of valid values.
    
    Args:
        value: Value to validate
        valid_values: Set of valid values
        name: Name of the value (for error messages)
        custom_message: Optional custom error message
        
    Returns:
        T: The validated value
        
    Raises:
        ValidationError: If validation fails
    """
    if value not in valid_values:
        valid_str = ", ".join(str(v) for v in valid_values)
        message = custom_message or f"{name} must be one of: {valid_str}"
        raise ValidationError(message)
    return value


def validate_custom(
    value: T,
    validator: Callable[[T], bool],
    name: str,
    custom_message: Optional[str] = None
) -> T:
    """Validate a value using a custom validation function.
    
    Args:
        value: Value to validate
        validator: Function that returns True for valid values
        name: Name of the value (for error messages)
        custom_message: Optional custom error message
        
    Returns:
        T: The validated value
        
    Raises:
        ValidationError: If validation fails
    """
    if not validator(value):
        message = custom_message or f"{name} is invalid"
        raise ValidationError(message)
    return value


def validate_id_format(
    value: str,
    name: str = "ID",
    custom_message: Optional[str] = None
) -> str:
    """Validate that a string has a valid ID format.
    
    Args:
        value: String to validate
        name: Name of the value (for error messages)
        custom_message: Optional custom error message
        
    Returns:
        str: The validated ID
        
    Raises:
        ValidationError: If validation fails
    """
    # Validate common ID formats (alphanumeric, dashes, underscores)
    pattern = r'^[a-zA-Z0-9\-_]+$'
    if not re.match(pattern, value):
        message = custom_message or f"{name} must contain only letters, numbers, dashes, and underscores"
        raise ValidationError(message)
    return value


def validate_email(
    value: str,
    name: str = "Email",
    custom_message: Optional[str] = None
) -> str:
    """Validate that a string is a valid email address.
    
    Args:
        value: String to validate
        name: Name of the value (for error messages)
        custom_message: Optional custom error message
        
    Returns:
        str: The validated email
        
    Raises:
        ValidationError: If validation fails
    """
    # Simple email validation pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, value):
        message = custom_message or f"{name} is not a valid email address"
        raise ValidationError(message)
    return value


def validate_url(
    value: str,
    name: str = "URL",
    custom_message: Optional[str] = None
) -> str:
    """Validate that a string is a valid URL.
    
    Args:
        value: String to validate
        name: Name of the value (for error messages)
        custom_message: Optional custom error message
        
    Returns:
        str: The validated URL
        
    Raises:
        ValidationError: If validation fails
    """
    # Simple URL validation pattern
    pattern = r'^https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(/[-\w%!$&\'()*+,;=:@/~]+)*(?:\?[-\w%!$&\'()*+,;=:@/~]*)?(?:#[-\w%!$&\'()*+,;=:@/~]*)?$'
    if not re.match(pattern, value):
        message = custom_message or f"{name} is not a valid URL"
        raise ValidationError(message)
    return value


def validate_date_format(
    value: str,
    format_pattern: str = r'^\d{4}-\d{2}-\d{2}$',
    name: str = "Date",
    custom_message: Optional[str] = None
) -> str:
    """Validate that a string has a valid date format.
    
    Args:
        value: String to validate
        format_pattern: Regular expression pattern for the date format
        name: Name of the value (for error messages)
        custom_message: Optional custom error message
        
    Returns:
        str: The validated date string
        
    Raises:
        ValidationError: If validation fails
    """
    if not re.match(format_pattern, value):
        message = custom_message or f"{name} has an invalid format"
        raise ValidationError(message)
    return value


def validate_id_list(
    value: str,
    name: str = "ID list",
    custom_message: Optional[str] = None
) -> List[str]:
    """Validate and parse a comma-separated list of IDs.
    
    Args:
        value: Comma-separated string to validate and parse
        name: Name of the value (for error messages)
        custom_message: Optional custom error message
        
    Returns:
        List[str]: The validated and parsed list of IDs
        
    Raises:
        ValidationError: If validation fails
    """
    if not value:
        return []
        
    # Split and strip whitespace
    id_list = [id.strip() for id in value.split(",")]
    
    # Validate each ID
    for i, id_value in enumerate(id_list):
        if not id_value:
            message = custom_message or f"Empty ID found at position {i+1} in {name}"
            raise ValidationError(message)
        
        # Validate ID format
        validate_id_format(id_value, f"ID at position {i+1} in {name}")
    
    return id_list