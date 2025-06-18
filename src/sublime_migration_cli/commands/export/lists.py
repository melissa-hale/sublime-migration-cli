"""Export lists from Sublime Security instance."""
import os
from typing import Dict, List, Optional, Set
import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.presentation.base import CommandResult
from sublime_migration_cli.presentation.factory import create_formatter
from sublime_migration_cli.utils.api import PaginatedFetcher
from sublime_migration_cli.utils.filtering import filter_by_creator
from sublime_migration_cli.utils.errors import handle_api_error
from sublime_migration_cli.commands.export.utils import (
    sanitize_filename, resolve_filename_collision, write_resource_file
)


# Authors to exclude from export (system lists)
EXCLUDED_AUTHORS = {"Sublime Security", "System"}


def export_lists_impl(api_key=None, region=None, string_dir="./sublime-export/lists/string",
                     user_group_dir="./sublime-export/lists/user_group", output_format="yaml", formatter=None):
    """Implementation for exporting lists.
    
    Args:
        api_key: API key for the instance
        region: Region for the instance
        string_dir: Directory to export string lists to
        user_group_dir: Directory to export user_group lists to
        output_format: Output format (yaml or json)
        formatter: Output formatter
        
    Returns:
        Dict: Export results with counts
    """
    if formatter is None:
        formatter = create_formatter("table")
    
    try:
        # Create API client
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Fetch all lists by type
        fetcher = PaginatedFetcher(client, formatter)
        
        all_lists = []
        list_types = ["string", "user_group"]
        
        with formatter.create_progress("Fetching lists...") as (progress, task):
            for i, list_type in enumerate(list_types):
                try:
                    params = {"list_types": list_type}
                    type_lists = fetcher.fetch_all(
                        "/v1/lists", 
                        params=params,
                        progress_message=None
                    )
                    all_lists.extend(type_lists)
                except Exception as e:
                    error = handle_api_error(e)
                    formatter.output_error(f"Warning: Failed to fetch {list_type} lists: {error.message}")
                
                progress.update(task, completed=i+1)
        
        if not all_lists:
            return {"exported": 0, "failed": 0}
        
        # Filter out system-created lists
        user_lists = filter_by_creator(all_lists, False, EXCLUDED_AUTHORS)
        
        if not user_lists:
            return {"exported": 0, "failed": 0}
        
        # Separate lists by type
        string_lists = [lst for lst in user_lists if lst.get("entry_type") == "string"]
        user_group_lists = [lst for lst in user_lists if lst.get("entry_type") == "user_group"]
        
        # Track exported files to avoid collisions
        string_files = set()
        user_group_files = set()
        exported_count = 0
        failed_count = 0
        
        extension = ".yml" if output_format == "yaml" else ".json"
        total_lists = len(string_lists) + len(user_group_lists)
        
        with formatter.create_progress("Exporting lists...", total=total_lists) as (progress, task):
            current_progress = 0
            
            # Export string lists (fetch entries)
            for lst in string_lists:
                try:
                    # Get detailed list info with entries
                    list_id = lst.get("id")
                    detailed_list = client.get(f"/v1/lists/{list_id}")
                    
                    # Convert list to export format
                    export_data = convert_list_to_export_format(detailed_list)
                    
                    # Generate filename
                    base_name = sanitize_filename(lst.get("name", "unnamed-list"))
                    filename = resolve_filename_collision(
                        base_name, string_files, lst.get("id", ""), extension
                    )
                    string_files.add(filename)
                    
                    # Write file
                    file_path = os.path.join(string_dir, filename)
                    write_resource_file(export_data, file_path, output_format)
                    
                    exported_count += 1
                    
                except Exception as e:
                    error = handle_api_error(e)
                    formatter.output_error(
                        f"Failed to export string list '{lst.get('name', 'unknown')}': {error.message}"
                    )
                    failed_count += 1
                
                current_progress += 1
                progress.update(task, completed=current_progress)
            
            # Export user_group lists (no entries to fetch)
            for lst in user_group_lists:
                try:
                    # Convert list to export format
                    export_data = convert_list_to_export_format(lst)
                    
                    # Generate filename
                    base_name = sanitize_filename(lst.get("name", "unnamed-list"))
                    filename = resolve_filename_collision(
                        base_name, user_group_files, lst.get("id", ""), extension
                    )
                    user_group_files.add(filename)
                    
                    # Write file
                    file_path = os.path.join(user_group_dir, filename)
                    write_resource_file(export_data, file_path, output_format)
                    
                    exported_count += 1
                    
                except Exception as e:
                    error = handle_api_error(e)
                    formatter.output_error(
                        f"Failed to export user_group list '{lst.get('name', 'unknown')}': {error.message}"
                    )
                    failed_count += 1
                
                current_progress += 1
                progress.update(task, completed=current_progress)
        
        return {"exported": exported_count, "failed": failed_count}
        
    except Exception as e:
        error = handle_api_error(e)
        formatter.output_error(f"Failed to export lists: {error.message}")
        return {"exported": 0, "failed": 1}


def convert_list_to_export_format(lst: Dict) -> Dict:
    """Convert a list object to export format.
    
    Args:
        lst: List object from API
        
    Returns:
        Dict: List in export format
    """
    export_data = {
        "name": lst.get("name"),
        "type": lst.get("entry_type"),
        "description": lst.get("description", "")
    }
    
    # Add entries for string lists
    if lst.get("entry_type") == "string" and lst.get("entries"):
        export_data["entries"] = lst["entries"]
    
    # Add provider group info for user_group lists (always include these fields)
    if lst.get("entry_type") == "user_group":
        export_data["provider_group_id"] = lst.get("provider_group_id")
        export_data["provider_group_name"] = lst.get("provider_group_name")
    
    # Add other relevant fields, excluding system-generated ones
    excluded_fields = {
        "id", "org_id", "org_name", "created_by_user_id", "created_by_user_name",
        "created_at", "updated_at", "download_url", "viewable", "editable", "entry_count",
        "entries", "entry_type", "name", "description", "provider_group_id", "provider_group_name"
    }
    
    for key, value in lst.items():
        if key not in excluded_fields and value is not None:
            export_data[key] = value
    
    return export_data


@click.command()
@click.option("--api-key", help="API key for authentication")
@click.option("--region", help="Region to connect to")
@click.option("--output-dir", "-o", default="./sublime-export", 
              help="Output directory (default: ./sublime-export)")
@click.option("--format", "output_format", type=click.Choice(["yaml", "json"]), 
              default="yaml", help="Output format (default: yaml)")
@click.option("--type", "list_type", type=click.Choice(["string", "user_group"]),
              help="Export only specific list type")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def lists(api_key, region, output_dir, output_format, list_type, verbose):
    """Export lists from a Sublime Security instance.
    
    This command exports all user-created lists to local files organized by type.
    System-created lists are excluded by default.
    
    Examples:
        # Export all lists to default directory
        sublime export lists
        
        # Export only string lists
        sublime export lists --type string
        
        # Export to specific directory in JSON format
        sublime export lists --output-dir ./my-export --format json
    """
    formatter = create_formatter("table")
    
    # Create the lists subdirectories within the export directory
    string_dir = os.path.join(output_dir, "lists", "string")
    user_group_dir = os.path.join(output_dir, "lists", "user_group")
    
    if not list_type or list_type == "string":
        os.makedirs(string_dir, exist_ok=True)
    
    if not list_type or list_type == "user_group":
        os.makedirs(user_group_dir, exist_ok=True)
    
    # If filtering by type, adjust directories
    if list_type == "string":
        user_group_dir = None
    elif list_type == "user_group":
        string_dir = None
    
    # Export lists
    result = export_lists_impl(api_key, region, string_dir, user_group_dir, output_format, formatter)
    
    # Display results
    if result["exported"] > 0:
        lists_dir = os.path.join(output_dir, "lists")
        formatter.output_success(
            f"Successfully exported {result['exported']} lists to {lists_dir}"
        )
    
    if result["failed"] > 0:
        formatter.output_error(f"{result['failed']} lists failed to export")
    
    if result["exported"] == 0 and result["failed"] == 0:
        formatter.output_success("No user-created lists found to export")