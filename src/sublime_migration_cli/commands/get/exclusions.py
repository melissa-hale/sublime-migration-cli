"""Refactored commands for working with Exclusions using utility functions."""
from typing import Optional

import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.models.exclusion import Exclusion
from sublime_migration_cli.presentation.base import CommandResult
from sublime_migration_cli.presentation.factory import create_formatter

# Import our utility functions
from sublime_migration_cli.utils.api import PaginatedFetcher
from sublime_migration_cli.utils.filtering import create_boolean_filter
from sublime_migration_cli.utils.errors import (
    ApiError, ResourceNotFoundError, handle_api_error, ErrorHandler
)


# Implementation functions
def fetch_all_exclusions(api_key=None, region=None, scope=None, active=False, formatter=None):
    """Implementation for fetching all exclusions.
    
    Args:
        api_key: Optional API key
        region: Optional region code
        scope: Filter by scope (exclusion or rule_exclusion)
        active: Show only active exclusions
        formatter: Output formatter to use
    """
    # Default to table formatter if none provided
    if formatter is None:
        formatter = create_formatter("table")
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Prepare parameters
        params = {}
        if scope:
            params["scope"] = scope
        
        # Use PaginatedFetcher to get all exclusions
        fetcher = PaginatedFetcher(client, formatter)
        exclusions_data = fetcher.fetch_all(
            "/v1/exclusions",
            params=params,
            progress_message="Fetching exclusions...",
            # Provide custom extractors specifically for exclusions endpoint
            result_extractor=lambda resp: resp.get("exclusions", []) if isinstance(resp, dict) else resp,
            total_extractor=lambda resp: len(resp.get("exclusions", [])) if isinstance(resp, dict) else len(resp)
        )
        
        # Apply active filter if requested (client-side filtering)
        if active:
            # Use our filter utility
            active_filter = create_boolean_filter("active", True)
            exclusions_data = active_filter(exclusions_data)
        
        # Convert to Exclusion objects
        exclusions_list = [Exclusion.from_dict(ex) for ex in exclusions_data]
        
        # Create result
        result = CommandResult.success(
            f"Successfully retrieved {len(exclusions_list)} exclusions",
            exclusions_list
        )
        
        # Add filter notes if filters were applied
        filters = []
        if scope:
            filters.append(f"scope={scope}")
        if active:
            filters.append("active=true")
        
        if filters:
            result.notes = f"Filtered by {', '.join(filters)}"
        
        # Output the result
        formatter.output_result(result)
        
    except Exception as e:
        # Use our error handling utilities
        sublime_error = handle_api_error(e)
        error_details = ErrorHandler.format_error_for_display(sublime_error)
        formatter.output_error(f"Failed to get exclusions: {sublime_error.message}", error_details)


def get_exclusion_details(exclusion_id, api_key=None, region=None, formatter=None):
    """Implementation for getting details of a specific exclusion.
    
    Args:
        exclusion_id: ID of the exclusion to fetch
        api_key: Optional API key
        region: Optional region code
        formatter: Output formatter to use
    """
    # Default to table formatter if none provided
    if formatter is None:
        formatter = create_formatter("table")
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Get exclusion details from API
        with formatter.create_progress(f"Fetching exclusion {exclusion_id}...") as (progress, task):
            response = client.get(f"/v1/exclusions/{exclusion_id}")
            if progress and task:
                progress.update(task, advance=1)
        
        # Convert to Exclusion object
        exclusion_obj = Exclusion.from_dict(response)
        
        # Create result
        result = CommandResult.success(
            f"Successfully retrieved exclusion: {exclusion_obj.name}",
            exclusion_obj
        )
        
        # Output the result
        formatter.output_result(result)
        
    except ResourceNotFoundError as e:
        formatter.output_error(f"Exclusion not found: {e.resource_id}", e.details)
    except ApiError as e:
        formatter.output_error(f"Failed to get exclusion details: {e.message}", e.details)
    except Exception as e:
        sublime_error = handle_api_error(e)
        formatter.output_error(f"Error: {sublime_error.message}")


# Click command definitions
@click.group()
def exclusions():
    """Commands for working with Sublime Security Exclusions."""
    pass


@exclusions.command()
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--scope", help="Filter by scope (exclusion or rule_exclusion)")
@click.option("--active", is_flag=True, help="Show only active exclusions")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def all(api_key=None, region=None, scope=None, active=False, output_format="table"):
    """List all exclusions."""
    formatter = create_formatter(output_format)
    fetch_all_exclusions(api_key, region, scope, active, formatter)


@exclusions.command()
@click.argument("exclusion_id")
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def exclusion(exclusion_id, api_key=None, region=None, output_format="table"):
    """Get details of a specific exclusion."""
    formatter = create_formatter(output_format)
    get_exclusion_details(exclusion_id, api_key, region, formatter)