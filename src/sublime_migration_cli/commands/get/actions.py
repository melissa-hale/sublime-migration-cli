"""Refactored commands for working with Actions using utility functions."""
from typing import Optional

import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.models.action import Action
from sublime_migration_cli.presentation.base import CommandResult
from sublime_migration_cli.presentation.factory import create_formatter

# Import our utility functions
from sublime_migration_cli.utils.api import PaginatedFetcher
from sublime_migration_cli.utils.errors import (
    ApiError, ResourceNotFoundError, handle_api_error, ErrorHandler
)


# Implementation functions
def list_actions(api_key=None, region=None, formatter=None):
    """Implementation for listing all actions.
    
    Args:
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
        
        # Use PaginatedFetcher to get all actions
        fetcher = PaginatedFetcher(client, formatter)
        actions_data = fetcher.fetch_all(
            "/v1/actions",
            progress_message="Fetching actions..."
        )
        
        # Convert to Action objects
        actions_list = [Action.from_dict(action) for action in actions_data]
        
        # Create result
        result = CommandResult.success(
            f"Successfully retrieved {len(actions_list)} actions",
            actions_list
        )
        
        # Output the result
        formatter.output_result(result)
        
    except Exception as e:
        # Use our error handling utilities
        sublime_error = handle_api_error(e)
        error_details = ErrorHandler.format_error_for_display(sublime_error)
        formatter.output_error(f"Failed to get actions: {sublime_error.message}", error_details)


def get_action_details(action_id, api_key=None, region=None, formatter=None):
    """Implementation for getting details of a specific action.
    
    Args:
        action_id: ID of the action to fetch
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
        
        # Get action details from API
        with formatter.create_progress(f"Fetching action {action_id}...") as (progress, task):
            response = client.get(f"/v1/actions/{action_id}")
            if progress and task:
                progress.update(task, advance=1)
        
        # Convert to Action object
        action_obj = Action.from_dict(response)
        
        # Create result
        result = CommandResult.success(
            f"Successfully retrieved action: {action_obj.name}",
            action_obj
        )
        
        # Output the result
        formatter.output_result(result)
        
    except ResourceNotFoundError as e:
        formatter.output_error(f"Action not found: {e.resource_id}", e.details)
    except ApiError as e:
        formatter.output_error(f"Failed to get action details: {e.message}", e.details)
    except Exception as e:
        sublime_error = handle_api_error(e)
        formatter.output_error(f"Error: {sublime_error.message}")


# Click command definitions
@click.group()
def actions():
    """Commands for working with Sublime Security Actions."""
    pass


@actions.command()
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def all(api_key=None, region=None, output_format="table"):
    """List all actions."""
    formatter = create_formatter(output_format)
    list_actions(api_key, region, formatter)


@actions.command()
@click.argument("action_id")
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def action(action_id, api_key=None, region=None, output_format="table"):
    """Get details of a specific action."""
    formatter = create_formatter(output_format)
    get_action_details(action_id, api_key, region, formatter)