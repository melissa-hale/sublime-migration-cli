"""Export exclusions from Sublime Security instance."""
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


# Authors to exclude from export (system exclusions)
EXCLUDED_AUTHORS = {"Sublime Security", "System"}


def export_exclusions_impl(api_key=None, region=None, global_dir="./sublime-export/exclusions/global",
                          detection_dir="./sublime-export/exclusions/detection", output_format="yaml", formatter=None):
    """Implementation for exporting exclusions.
    
    Args:
        api_key: API key for the instance
        region: Region for the instance
        global_dir: Directory to export global exclusions to
        detection_dir: Directory to export detection exclusions to
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
        
        # Fetch exclusions by scope
        fetcher = PaginatedFetcher(client, formatter)
        
        all_exclusions = []
        scopes = ["exclusion", "detection_exclusion"]
        
        with formatter.create_progress("Fetching exclusions...") as (progress, task):
            for i, scope in enumerate(scopes):
                try:
                    params = {
                        "include_deleted": "false",
                        "scope": scope
                    }
                    scope_exclusions = fetcher.fetch_all(
                        "/v1/exclusions",
                        params=params,
                        progress_message=None,
                        result_extractor=lambda resp: resp.get("exclusions", []) if isinstance(resp, dict) else resp,
                        total_extractor=lambda resp: len(resp.get("exclusions", [])) if isinstance(resp, dict) else len(resp)
                    )
                    all_exclusions.extend(scope_exclusions)
                except Exception as e:
                    error = handle_api_error(e)
                    formatter.output_error(f"Warning: Failed to fetch {scope} exclusions: {error.message}")
                
                progress.update(task, completed=i+1)
        
        if not all_exclusions:
            return {"exported": 0, "failed": 0}
        
        # Filter out system-created exclusions
        user_exclusions = filter_by_creator(all_exclusions, False, EXCLUDED_AUTHORS)
        
        if not user_exclusions:
            return {"exported": 0, "failed": 0}
        
        # Separate exclusions by scope
        global_exclusions = [exc for exc in user_exclusions if exc.get("scope") == "exclusion"]
        detection_exclusions = [exc for exc in user_exclusions if exc.get("scope") == "detection_exclusion"]
        
        # Track exported files to avoid collisions
        global_files = set()
        detection_files = set()
        exported_count = 0
        failed_count = 0
        
        extension = ".yml" if output_format == "yaml" else ".json"
        total_exclusions = len(global_exclusions) + len(detection_exclusions)
        
        with formatter.create_progress("Exporting exclusions...", total=total_exclusions) as (progress, task):
            current_progress = 0
            
            # Export global exclusions
            for exclusion in global_exclusions:
                try:
                    # Convert exclusion to export format
                    export_data = convert_exclusion_to_export_format(exclusion)
                    
                    # Generate filename
                    base_name = sanitize_filename(exclusion.get("name", "unnamed-exclusion"))
                    filename = resolve_filename_collision(
                        base_name, global_files, exclusion.get("id", ""), extension
                    )
                    global_files.add(filename)
                    
                    # Write file
                    file_path = os.path.join(global_dir, filename)
                    write_resource_file(export_data, file_path, output_format)
                    
                    exported_count += 1
                    
                except Exception as e:
                    error = handle_api_error(e)
                    formatter.output_error(
                        f"Failed to export global exclusion '{exclusion.get('name', 'unknown')}': {error.message}"
                    )
                    failed_count += 1
                
                current_progress += 1
                progress.update(task, completed=current_progress)
            
            # Export detection exclusions
            for exclusion in detection_exclusions:
                try:
                    # Convert exclusion to export format
                    export_data = convert_exclusion_to_export_format(exclusion)
                    
                    # Generate filename
                    base_name = sanitize_filename(exclusion.get("name", "unnamed-exclusion"))
                    filename = resolve_filename_collision(
                        base_name, detection_files, exclusion.get("id", ""), extension
                    )
                    detection_files.add(filename)
                    
                    # Write file
                    file_path = os.path.join(detection_dir, filename)
                    write_resource_file(export_data, file_path, output_format)
                    
                    exported_count += 1
                    
                except Exception as e:
                    error = handle_api_error(e)
                    formatter.output_error(
                        f"Failed to export detection exclusion '{exclusion.get('name', 'unknown')}': {error.message}"
                    )
                    failed_count += 1
                
                current_progress += 1
                progress.update(task, completed=current_progress)
        
        return {"exported": exported_count, "failed": failed_count}
        
    except Exception as e:
        error = handle_api_error(e)
        formatter.output_error(f"Failed to export exclusions: {error.message}")
        return {"exported": 0, "failed": 1}


def convert_exclusion_to_export_format(exclusion: Dict) -> Dict:
    """Convert an exclusion object to export format.
    
    Args:
        exclusion: Exclusion object from API
        
    Returns:
        Dict: Exclusion in export format
    """
    export_data = {
        "name": exclusion.get("name"),
        "description": exclusion.get("description", ""),
        "scope": exclusion.get("scope"),
        "active": exclusion.get("active", False),
        "source": exclusion.get("source", "")
    }
    
    # Add tags if present
    if exclusion.get("tags"):
        export_data["tags"] = exclusion["tags"]
    
    # Add other relevant fields, excluding system-generated ones
    excluded_fields = {
        "id", "org_id", "created_at", "updated_at", "active_updated_at", "source_md5",
        "created_by_user_id", "created_by_user_name", "created_by_org_id", "created_by_org_name",
        "originating_rule"  # Don't export rule relationship for standalone exclusions
    }
    
    for key, value in exclusion.items():
        if key not in excluded_fields and key not in export_data and value is not None:
            export_data[key] = value
    
    return export_data


@click.command()
@click.option("--api-key", help="API key for authentication")
@click.option("--region", help="Region to connect to")
@click.option("--output-dir", "-o", default="./sublime-export", 
              help="Output directory (default: ./sublime-export)")
@click.option("--format", "output_format", type=click.Choice(["yaml", "json"]), 
              default="yaml", help="Output format (default: yaml)")
@click.option("--scope", type=click.Choice(["global", "detection"]),
              help="Export only specific exclusion scope (global=exclusion, detection=detection_exclusion)")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def exclusions(api_key, region, output_dir, output_format, scope, verbose):
    """Export exclusions from a Sublime Security instance.
    
    This command exports user-created exclusions to local files organized by scope.
    Both global exclusions and detection exclusions are exported.
    Rule exclusions are handled separately as part of rule exports.
    
    Examples:
        # Export all exclusions to default directory
        sublime export exclusions
        
        # Export only global exclusions
        sublime export exclusions --scope global
        
        # Export to specific directory in JSON format
        sublime export exclusions --output-dir ./my-export --format json
    """
    formatter = create_formatter("table")
    
    # Create the exclusions subdirectories within the export directory
    global_dir = os.path.join(output_dir, "exclusions", "global")
    detection_dir = os.path.join(output_dir, "exclusions", "detection")
    
    if not scope or scope == "global":
        os.makedirs(global_dir, exist_ok=True)
    
    if not scope or scope == "detection":
        os.makedirs(detection_dir, exist_ok=True)
    
    # If filtering by scope, adjust directories
    if scope == "global":
        detection_dir = None
    elif scope == "detection":
        global_dir = None
    
    # Export exclusions
    result = export_exclusions_impl(api_key, region, global_dir, detection_dir, output_format, formatter)
    
    # Display results
    if result["exported"] > 0:
        exclusions_dir = os.path.join(output_dir, "exclusions")
        formatter.output_success(
            f"Successfully exported {result['exported']} exclusions to {exclusions_dir}"
        )
    
    if result["failed"] > 0:
        formatter.output_error(f"{result['failed']} exclusions failed to export")
    
    if result["exported"] == 0 and result["failed"] == 0:
        formatter.output_success("No user-created exclusions found to export")