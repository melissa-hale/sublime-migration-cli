"""Refactored commands for migrating exclusions using utility functions."""
from typing import Dict, List, Optional, Set
import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.presentation.base import CommandResult
from sublime_migration_cli.presentation.factory import create_formatter

# Import our utility functions
from sublime_migration_cli.utils.api import PaginatedFetcher
from sublime_migration_cli.utils.filtering import filter_by_ids, filter_by_creator
from sublime_migration_cli.utils.errors import (
    ApiError, MigrationError, handle_api_error, ErrorHandler
)

# Authors to exclude from migration (system and built-in exclusions)
EXCLUDED_AUTHORS = {"Sublime Security", "System"}


# Implementation functions
def migrate_exclusions_between_instances(
    source_api_key=None, source_region=None, 
    dest_api_key=None, dest_region=None,
    include_ids=None, exclude_ids=None, 
    include_system_created=False,
    dry_run=False, formatter=None
):
    """Implementation for migrating global exclusions between instances.
    
    Args:
        source_api_key: API key for source instance
        source_region: Region for source instance
        dest_api_key: API key for destination instance
        dest_region: Region for destination instance
        include_ids: Comma-separated list of exclusion IDs to include
        exclude_ids: Comma-separated list of exclusion IDs to exclude
        include_system_created: Include system-created exclusions
        dry_run: If True, preview changes without applying them
        formatter: Output formatter
    """
    # Default to table formatter if none provided
    if formatter is None:
        formatter = create_formatter("table")
        
    try:
        # Create API clients for source and destination
        with formatter.create_progress("Connecting to source and destination instances...") as (progress, task):
            source_client = get_api_client_from_env_or_args(source_api_key, source_region)
            dest_client = get_api_client_from_env_or_args(dest_api_key, dest_region, destination=True)
            progress.update(task, advance=1)
        
        # Prepare parameters for fetching exclusions
        params = {
            "include_deleted": "false",
            "scope": ["detection_exclusion", "exclusion"]  # Only global exclusions
        }
        
        # Use PaginatedFetcher to fetch exclusions from source
        source_fetcher = PaginatedFetcher(source_client, formatter)
        source_exclusions = source_fetcher.fetch_all(
            "/v1/exclusions",
            params=params,
            progress_message="Fetching exclusions from source...",
            # Custom extractors for the exclusions endpoint
            result_extractor=lambda resp: resp.get("exclusions", []) if isinstance(resp, dict) else resp,
            total_extractor=lambda resp: len(resp.get("exclusions", [])) if isinstance(resp, dict) else len(resp)
        )
        
        # Apply filters using our utility functions
        # First filter by creator
        filtered_exclusions = filter_by_creator(
            source_exclusions,
            include_system_created,
            EXCLUDED_AUTHORS
        )
        
        # Then apply ID filters
        filtered_exclusions = filter_by_ids(
            filtered_exclusions,
            include_ids,
            exclude_ids
        )
        
        if not filtered_exclusions:
            return CommandResult.error("No exclusions to migrate after applying filters.")
            
        # Prepare response data
        migration_data = {
            "new_exclusions": [
                {
                    "id": exclusion.get("id", ""),
                    "name": exclusion.get("name", ""),
                    "scope": exclusion.get("scope", ""),
                    "active": exclusion.get("active", False),
                    "created_by": exclusion.get("created_by_user_name") or exclusion.get("created_by_org_name") or "Unknown",
                    "status": "New"
                }
                for exclusion in filtered_exclusions
            ],
            "update_exclusions": []  # No updates for exclusions, only create
        }
        
        # Add summary stats
        migration_data["summary"] = {
            "new_count": len(filtered_exclusions),
            "update_count": 0,  # No updates for exclusions
            "total_count": len(filtered_exclusions)
        }
        
        # If dry run, return preview data
        if dry_run:
            return CommandResult.success(
                "DRY RUN: Preview of exclusions to migrate",
                migration_data,
                "No changes were made to the destination instance."
            )
        
        # Show preview before confirmation in interactive mode
        formatter.output_result(CommandResult.success(
            "Exclusions that will be migrated:",
            migration_data,
            "Please confirm to proceed with migration."
        ))
        
        # Confirm migration if interactive
        if not formatter.prompt_confirmation("\nDo you want to proceed with the migration?"):
            return CommandResult.success("Migration canceled by user.")
        
        # Perform the migration (create only, no updates)
        results = perform_migration(formatter, dest_client, filtered_exclusions)
        
        # Add results to migration data
        migration_data["results"] = results
        
        # Return overall results
        return CommandResult.success(
            f"Migration completed: {results['created']} exclusions created, {results['failed']} failed",
            migration_data,
            "See details below for operation results."
        )
        
    except Exception as e:
        sublime_error = handle_api_error(e)
        if isinstance(sublime_error, ApiError):
            return CommandResult.error(f"API error during migration: {sublime_error.message}", sublime_error.details)
        else:
            return CommandResult.error(f"Error during migration: {sublime_error.message}")


def perform_migration(formatter, dest_client, exclusions: List[Dict]) -> Dict:
    """Perform the actual migration of exclusions to the destination.
    
    Args:
        formatter: Output formatter
        dest_client: API client for destination
        exclusions: List of exclusions to create
        
    Returns:
        Dict: Results of the migration
    """
    results = {
        "created": 0,
        "failed": 0,
        "details": []
    }
    
    with formatter.create_progress("Creating exclusions...", total=len(exclusions)) as (progress, task):
        for i, exclusion in enumerate(exclusions):
            process_exclusion(exclusion, dest_client, results)
            progress.update(task, completed=i+1)
    
    return results


def process_exclusion(exclusion: Dict, dest_client, results: Dict):
    """Process an exclusion for migration."""
    exclusion_name = exclusion.get("name", "")
    exclusion_scope = exclusion.get("scope", "exclusion")
    
    try:
        # Create exclusion payload for API request
        payload = create_exclusion_payload(exclusion)
        
        # Post to destination
        dest_client.post("/v1/exclusions", payload)
        results["created"] += 1
        results["details"].append({
            "name": exclusion_name,
            "type": exclusion_scope,
            "status": "created"
        })
        
    except ApiError as e:
        results["failed"] += 1
        results["details"].append({
            "name": exclusion_name,
            "type": exclusion_scope,
            "status": "failed",
            "reason": e.message
        })
    except Exception as e:
        sublime_error = handle_api_error(e)
        results["failed"] += 1
        results["details"].append({
            "name": exclusion_name,
            "type": exclusion_scope,
            "status": "failed",
            "reason": str(sublime_error.message)
        })


def create_exclusion_payload(exclusion: Dict) -> Dict:
    """Create a clean exclusion payload for API requests.
    
    Args:
        exclusion: Source exclusion object
        
    Returns:
        Dict: Cleaned exclusion payload
    """
    # Extract only the fields needed for creation
    payload = {
        "name": exclusion.get("name"),
        "scope": exclusion.get("scope", "exclusion"),
        "description": exclusion.get("description", ""),
        "source": exclusion.get("source", ""),
        "active": exclusion.get("active", False)
    }
    
    # Include tags if present
    if "tags" in exclusion and exclusion["tags"]:
        payload["tags"] = exclusion["tags"]
    
    return payload


# Click command definition
@click.command()
@click.option("--source-api-key", help="API key for the source instance")
@click.option("--source-region", help="Region of the source instance")
@click.option("--dest-api-key", help="API key for the destination instance")
@click.option("--dest-region", help="Region of the destination instance")
@click.option("--include-ids", help="Comma-separated list of exclusion IDs to include")
@click.option("--exclude-ids", help="Comma-separated list of exclusion IDs to exclude")
@click.option("--include-system-created", is_flag=True, 
              help="Include system-created exclusions (by default, only user-created exclusions are migrated)")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def exclusions(source_api_key, source_region, dest_api_key, dest_region,
               include_ids, exclude_ids, include_system_created,
               dry_run, yes, output_format):
    """Migrate global exclusions between Sublime Security instances.
    
    This command copies global exclusions from the source instance to the destination instance.
    By default, only user-created exclusions are migrated (not rule-specific exclusions).
    
    Examples:
        # Migrate all user-created exclusions
        sublime migrate exclusions --source-api-key KEY1 --dest-api-key KEY2
        
        # Migrate specific exclusions by ID
        sublime migrate exclusions --include-ids id1,id2 --source-api-key KEY1 --dest-api-key KEY2
        
        # Include system-created exclusions
        sublime migrate exclusions --include-system-created --source-api-key KEY1 --dest-api-key KEY2
        
        # Preview migration without making changes
        sublime migrate exclusions --dry-run --source-api-key KEY1 --dest-api-key KEY2
    """
    # Create formatter based on output format
    formatter = create_formatter(output_format)
    
    # If --yes flag is provided, modify the formatter to auto-confirm
    if yes:
        original_prompt = formatter.prompt_confirmation
        formatter.prompt_confirmation = lambda _: True
    
    # Execute the implementation function
    result = migrate_exclusions_between_instances(
        source_api_key, source_region, 
        dest_api_key, dest_region,
        include_ids, exclude_ids, 
        include_system_created,
        dry_run, formatter
    )
    
    # Reset the formatter if it was modified
    if yes and hasattr(formatter, 'original_prompt'):
        formatter.prompt_confirmation = original_prompt
    
    # Output the result
    formatter.output_result(result)