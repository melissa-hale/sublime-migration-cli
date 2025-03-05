"""Refactored commands for working with Lists."""
from typing import Optional, List as PyList
from concurrent.futures import ThreadPoolExecutor

import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.models.list import List
from sublime_migration_cli.presentation.base import CommandResult, OutputFormatter
from sublime_migration_cli.presentation.factory import create_formatter


# Implementation functions
def fetch_all_lists(api_key=None, region=None, list_type=None, fetch_details=False, formatter=None):
    """Implementation for fetching all lists."""
    # Default to table formatter if none provided
    if formatter is None:
        formatter = create_formatter("table")
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Prepare to store all lists
        all_lists = []
        
        # Determine which list types to retrieve
        list_types = []
        if list_type:
            list_types = [list_type]
        else:
            # Default: get both types
            list_types = ["string", "user_group"]
        
        # Get lists for each type
        with formatter.create_progress("Fetching lists...") as (progress, task):
            for lt in list_types:
                try:
                    response = client.get("/v1/lists", params={"list_types": lt})
                    all_lists.extend(response)
                    progress.update(task, advance=1)  # Update progress
                except Exception as e:
                    formatter.output_error(f"Warning: Failed to get lists of type '{lt}'", str(e))
        
        # If requested, fetch full details for each list to get accurate entry counts
        if fetch_details and all_lists:
            # Create a new list to hold detailed lists
            detailed_lists = []
            
            with formatter.create_progress("Fetching list details...", total=len(all_lists)) as (progress, task):
                for list_item in all_lists:
                    try:
                        list_id = list_item["id"]
                        # Fetch detailed info
                        details = client.get(f"/v1/lists/{list_id}")
                        # Add to our detailed lists
                        detailed_lists.append(details)
                    except Exception as e:
                        # If fetching details fails, use original item
                        detailed_lists.append(list_item)
                        formatter.output_error(f"Warning: Failed to fetch details for list '{list_item.get('name')}'", str(e))
                    
                    # Update progress
                    progress.update(task, advance=1)
                
                # Replace all_lists with detailed_lists
                all_lists = detailed_lists
        
        # Convert to List objects for additional processing
        lists_data = [List.from_dict(list_item) for list_item in all_lists]
        
        # Create a notes message for approx. counts if needed
        notes = None
        if not fetch_details:
            notes = "Note: Entry counts are approximate. Use --fetch-details for accurate counts."
        
        # Create result
        result = CommandResult.success(
            f"Successfully retrieved {len(lists_data)} lists",
            lists_data,
            notes
        )
        
        # Output the result
        formatter.output_result(result)
        
    except Exception as e:
        formatter.output_error(f"Failed to get lists: {str(e)}")


def get_list_details(list_id, api_key=None, region=None, formatter=None):
    """Implementation for getting details of a specific list.
    
    Args:
        list_id: ID of the list to fetch
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
        
        # Get list details from API
        with formatter.create_progress(f"Fetching list {list_id}...") as (progress, task):
            response = client.get(f"/v1/lists/{list_id}")
        
        # Convert to List object
        list_obj = List.from_dict(response)
        
        # Create result
        result = CommandResult.success(
            f"Successfully retrieved list: {list_obj.name}",
            list_obj
        )
        
        # Output the result
        formatter.output_result(result)
        
    except Exception as e:
        formatter.output_error(f"Failed to get list details: {str(e)}")


# Click command definitions
@click.group()
def lists():
    """Commands for working with Sublime Security Lists."""
    pass


@lists.command()
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--type", "list_type", help="Filter by list type (string or user_group)")
@click.option("--fetch-details", is_flag=True, help="Fetch full details for accurate entry counts")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def all(api_key=None, region=None, list_type=None, fetch_details=False, output_format="table"):
    """List all lists.
    
    By default, retrieves both string and user_group list types.
    Use --type to filter for a specific type.
    Use --fetch-details to get accurate entry counts (slower but more accurate).
    """
    formatter = create_formatter(output_format)
    fetch_all_lists(api_key, region, list_type, fetch_details, formatter)


@lists.command()
@click.argument("list_id")
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def list(list_id, api_key=None, region=None, output_format="table"):
    """Get details of a specific list, including entries."""
    formatter = create_formatter(output_format)
    get_list_details(list_id, api_key, region, formatter)