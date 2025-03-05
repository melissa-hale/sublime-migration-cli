# Utility Implementation Guide

This guide provides instructions for using the utility modules in the Sublime Migration CLI.

## Table of Contents

1. [API Utilities](#api-utilities)
2. [Filter Utilities](#filter-utilities)
3. [Error Handling](#error-handling)
4. [Implementing in Command Modules](#implementing-in-command-modules)

## API Utilities

### PaginatedFetcher

The `PaginatedFetcher` class handles pagination for API endpoints, making it easy to fetch all items from a paginated API.

```python
from sublime_migration_cli.utils.api_utils import PaginatedFetcher

# Create a fetcher with a client and formatter
fetcher = PaginatedFetcher(client, formatter)

# Fetch all items from a paginated endpoint
items = fetcher.fetch_all(
    "/v1/resources",              # API endpoint
    params={"param": "value"},     # Optional parameters
    progress_message="Fetching resources...",  # Progress message
    result_extractor=None,         # Optional custom extractor for items
    total_extractor=None,          # Optional custom extractor for total count
    page_size=100                  # Number of items per page
)
```

### Custom Extractors

For APIs with non-standard response formats, you can provide custom extractors:

```python
# Custom extractors for a specific response format
feeds = fetcher.fetch_all(
    "/v1/feeds",
    progress_message="Fetching feeds...",
    result_extractor=lambda resp: resp.get("feeds", []) if isinstance(resp, dict) else resp,
    total_extractor=lambda resp: len(resp.get("feeds", [])) if isinstance(resp, dict) else len(resp)
)
```

### Helper Functions

The API utilities module also provides helper functions for common extraction patterns:

```python
from sublime_migration_cli.utils.api_utils import (
    extract_items_auto,           # Automatically extract items from various response formats
    extract_total_auto,          # Automatically extract total count from various response formats
    extract_items_from_key,      # Create an extractor for a specific response key
    extract_total_from_key       # Create a total extractor for a specific response key
)

# Example: Create an extractor for a specific key
rules_extractor = extract_items_from_key("rules")
total_extractor = extract_total_from_key("total")
```

## Filter Utilities

### Basic Filtering

The filter utilities provide standardized filtering functions:

```python
from sublime_migration_cli.utils.filter_utils import (
    filter_by_ids,              # Filter items by ID
    filter_by_types,            # Filter items by type
    filter_by_creator,          # Filter items by creator
    apply_filters              # Apply multiple filters at once
)

# Filter by IDs
filtered_items = filter_by_ids(
    items,                      # List of items to filter
    include_ids="id1,id2,id3",  # Comma-separated list of IDs to include
    exclude_ids="id4,id5",      # Comma-separated list of IDs to exclude
    id_field="id"               # Field name containing the ID (default: "id")
)

# Filter by types
filtered_items = filter_by_types(
    items,                      # List of items to filter
    include_types="type1,type2", # Comma-separated list of types to include
    exclude_types="type3",      # Comma-separated list of types to exclude
    ignored_types={"type4"},    # Set of types to always exclude
    type_field="type"           # Field name containing the type (default: "type")
)

# Filter by creator
filtered_items = filter_by_creator(
    items,                      # List of items to filter
    include_system_created=False, # Whether to include system-created items
    excluded_authors={"System", "Sublime Security"}  # Set of author names to exclude
)
```

### Custom Filters

You can create custom filter functions:

```python
from sublime_migration_cli.utils.filter_utils import (
    create_attribute_filter,    # Create a filter for a specific attribute value
    create_boolean_filter       # Create a filter for a boolean attribute
)

# Create an attribute filter
name_filter = create_attribute_filter("name", "My Item")

# Create a boolean filter
active_filter = create_boolean_filter("active", True)

# Apply the filter
active_items = active_filter(items)
```

### Combining Filters

You can combine multiple filters:

```python
# Apply multiple filters at once
filtered_items = apply_filters(items, {
    "include_ids": "id1,id2,id3",
    "include_types": "type1,type2",
    "exclude_types": "type3",
    "include_system_created": False,
    "excluded_authors": {"System", "Sublime Security"},
    "custom_filters": [active_filter, name_filter]
})
```

## Error Handling

### Error Classes

The error handling module provides standardized error classes:

```python
from sublime_migration_cli.utils.error_utils import (
    SublimeError,              # Base error class
    ApiError,                  # API-related error
    AuthenticationError,       # Authentication error
    ResourceNotFoundError,     # Resource not found error
    ConfigurationError,        # Configuration error
    ValidationError,           # Validation error
    MigrationError             # Migration-related error
)
```

### Handling Errors

Use the `handle_api_error` function to convert various exceptions into standardized errors:

```python
from sublime_migration_cli.utils.error_utils import handle_api_error

try:
    # API call or other operation
    result = client.get("/v1/resources/123")
except Exception as e:
    # Convert to standardized error
    sublime_error = handle_api_error(e)
    
    # Output the error
    formatter.output_error(f"Error: {sublime_error.message}", sublime_error.details)
```

### Error Formatting

Use the `ErrorHandler` class to format errors for display:

```python
from sublime_migration_cli.utils.error_utils import ErrorHandler

try:
    # Operation that might fail
    result = client.get("/v1/resources/123")
except Exception as e:
    # Convert to standardized error
    sublime_error = handle_api_error(e)
    
    # Format for display
    error_details = ErrorHandler.format_error_for_display(sublime_error)
    
    # Output the error
    formatter.output_error(f"Error: {sublime_error.message}", error_details)
```

## Implementing in Command Modules

### Basic Structure

Here's a template for implementing utilities in a command module:

```python
"""Module description."""
from typing import Optional

import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.models.your_model import YourModel
from sublime_migration_cli.presentation.base import CommandResult
from sublime_migration_cli.presentation.factory import create_formatter

# Import utilities
from sublime_migration_cli.utils.api_utils import PaginatedFetcher
from sublime_migration_cli.utils.filter_utils import filter_by_ids, create_boolean_filter
from sublime_migration_cli.utils.error_utils import (
    ApiError, ResourceNotFoundError, handle_api_error, ErrorHandler
)

# Implementation function
def fetch_all_resources(api_key=None, region=None, resource_type=None, active=False, formatter=None):
    """Implementation for fetching all resources."""
    # Default to table formatter if none provided
    if formatter is None:
        formatter = create_formatter("table")
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Prepare parameters
        params = {}
        if resource_type:
            params["type"] = resource_type
        
        # Use PaginatedFetcher to get all resources
        fetcher = PaginatedFetcher(client, formatter)
        resources_data = fetcher.fetch_all(
            "/v1/resources",
            params=params,
            progress_message="Fetching resources..."
        )
        
        # Apply filters if needed
        if active:
            active_filter = create_boolean_filter("active", True)
            resources_data = active_filter(resources_data)
        
        # Convert to model objects
        resources_list = [YourModel.from_dict(resource) for resource in resources_data]
        
        # Create result
        result = CommandResult.success(
            f"Successfully retrieved {len(resources_list)} resources",
            resources_list
        )
        
        # Add filter notes if applicable
        filters = []
        if resource_type:
            filters.append(f"type={resource_type}")
        if active:
            filters.append("active=true")
        
        if filters:
            result.notes = f"Filtered by {', '.join(filters)}"
        
        # Output the result
        formatter.output_result(result)
        
    except Exception as e:
        # Use error handling utilities
        sublime_error = handle_api_error(e)
        error_details = ErrorHandler.format_error_for_display(sublime_error)
        formatter.output_error(f"Failed to get resources: {sublime_error.message}", error_details)

# Click command definitions
@click.group()
def resources():
    """Commands for working with Resources."""
    pass

@resources.command()
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--type", "resource_type", help="Filter by resource type")
@click.option("--active", is_flag=True, help="Show only active resources")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def all(api_key=None, region=None, resource_type=None, active=False, output_format="table"):
    """List all resources."""
    formatter = create_formatter(output_format)
    fetch_all_resources(api_key, region, resource_type, active, formatter)
```

### Migration Commands

For migration commands, follow this pattern:

1. Set up source and destination clients
2. Fetch resources from source with PaginatedFetcher
3. Apply filters using filter utilities
4. Fetch destination resources for comparison
5. Process and categorize resources
6. Handle errors consistently
7. Return a CommandResult with details

See `src/sublime_migration_cli/commands/migrate/lists.py` for a complete example.

## Best Practices

1. **Error Handling**: Always wrap API calls in try/except blocks and use the error handling utilities
2. **Progress Indicators**: Use formatter.create_progress for long-running operations
3. **Command Results**: Return CommandResult objects with detailed information
4. **Filtering**: Use the standard filter utilities for consistency
5. **API Requests**: Use PaginatedFetcher for all paginated endpoints
6. **Documentation**: Include detailed docstrings for all functions
7. **Testing**: Write unit tests for all functions