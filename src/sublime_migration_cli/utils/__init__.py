"""Utility modules for the Sublime Migration CLI."""

from sublime_migration_cli.utils.api import (
    PaginatedFetcher,
    extract_items_auto,
    extract_total_auto,
    extract_items_from_key,
    extract_total_from_key,
)

from sublime_migration_cli.utils.filtering import (
    filter_by_ids,
    filter_by_types,
    filter_by_creator,
    apply_filters,
    create_attribute_filter,
    create_boolean_filter,
)

from sublime_migration_cli.utils.errors import (
    SublimeError,
    ApiError,
    AuthenticationError,
    ResourceNotFoundError,
    ConfigurationError,
    ValidationError,
    MigrationError,
    handle_api_error,
    ErrorHandler,
)

__all__ = [
    # API utilities
    'PaginatedFetcher',
    'extract_items_auto',
    'extract_total_auto',
    'extract_items_from_key',
    'extract_total_from_key',
    
    # Filter utilities
    'filter_by_ids',
    'filter_by_types',
    'filter_by_creator',
    'apply_filters',
    'create_attribute_filter',
    'create_boolean_filter',
    
    # Error handling
    'SublimeError',
    'ApiError',
    'AuthenticationError',
    'ResourceNotFoundError',
    'ConfigurationError',
    'ValidationError',
    'MigrationError',
    'handle_api_error',
    'ErrorHandler',
]