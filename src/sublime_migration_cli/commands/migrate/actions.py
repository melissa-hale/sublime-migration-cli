"""Refactored commands for migrating actions using utility functions."""
from typing import Dict, List, Optional, Set
import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.presentation.base import CommandResult
from sublime_migration_cli.presentation.factory import create_formatter

# Import our utility functions
from sublime_migration_cli.utils.api import PaginatedFetcher
from sublime_migration_cli.utils.filtering import filter_by_ids, filter_by_types
from sublime_migration_cli.utils.errors import (
    ApiError, MigrationError, handle_api_error, ErrorHandler
)

# Set of action types to exclude from migration
IGNORE_TYPES = {
    "quarantine_message", 
    "auto_review", 
    "move_to_spam", 
    "delete_message"
}


# Implementation functions
def migrate_actions_between_instances(
    source_api_key=None, source_region=None, 
    dest_api_key=None, dest_region=None,
    include_ids=None, exclude_ids=None, 
    include_types=None, exclude_types=None,
    dry_run=False, formatter=None
):
    """Implementation for migrating actions between instances.
    
    Args:
        source_api_key: API key for source instance
        source_region: Region for source instance
        dest_api_key: API key for destination instance
        dest_region: Region for destination instance
        include_ids: Comma-separated list of action IDs to include
        exclude_ids: Comma-separated list of action IDs to exclude
        include_types: Comma-separated list of action types to include
        exclude_types: Comma-separated list of action types to exclude
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
        
        # Use PaginatedFetcher to fetch actions from source
        source_fetcher = PaginatedFetcher(source_client, formatter)
        source_actions = source_fetcher.fetch_all(
            "/v1/actions",
            progress_message="Fetching actions from source instance..."
        )
        
        # Apply filters using our utility functions
        # First filter by ignored types
        filtered_actions = filter_by_types(
            source_actions,
            ignored_types=IGNORE_TYPES,
            type_field="type"
        )
        
        # Then apply ID filters
        filtered_actions = filter_by_ids(
            filtered_actions, 
            include_ids, 
            exclude_ids
        )
        
        # Then apply type filters
        if include_types or exclude_types:
            filtered_actions = filter_by_types(
                filtered_actions,
                include_types=include_types,
                exclude_types=exclude_types,
                type_field="type"
            )
        
        if not filtered_actions:
            return CommandResult.error("No actions to migrate after applying filters.")
            
        # Use PaginatedFetcher to fetch actions from destination
        dest_fetcher = PaginatedFetcher(dest_client, formatter)
        dest_actions = dest_fetcher.fetch_all(
            "/v1/actions",
            progress_message="Fetching actions from destination instance..."
        )
        
        # Compare and categorize actions
        new_actions, update_actions = categorize_actions(filtered_actions, dest_actions)
        
        # If no actions to migrate, return early
        if not new_actions and not update_actions:
            return CommandResult.success("All selected actions already exist in the destination instance.")
            
        # Prepare response data
        migration_data = {
            "new_actions": [
                {
                    "id": action.get("id", ""),
                    "name": action.get("name", ""),
                    "type": action.get("type", ""),
                    "status": "New"
                }
                for action in new_actions
            ],
            "update_actions": [
                {
                    "id": action.get("id", ""),
                    "name": action.get("name", ""),
                    "type": action.get("type", ""),
                    "status": "Update (if different)"
                }
                for action in update_actions
            ]
        }
        
        # Add summary stats
        migration_data["summary"] = {
            "new_count": len(new_actions),
            "update_count": len(update_actions),
            "total_count": len(new_actions) + len(update_actions)
        }
        
        # If dry run, return preview data
        if dry_run:
            return CommandResult.success(
                "DRY RUN: Preview of actions to migrate",
                migration_data,
                "No changes were made to the destination instance."
            )
        
        # Show preview before confirmation in interactive mode
        formatter.output_result(CommandResult.success(
            "Actions that will be migrated:",
            migration_data,
            "Please confirm to proceed with migration."
        ))
        
        # Confirm migration if interactive
        if not formatter.prompt_confirmation("\nDo you want to proceed with the migration?"):
            return CommandResult.success("Migration canceled by user.")
        
        # Perform the migration
        results = perform_migration(formatter, dest_client, new_actions, update_actions, dest_actions)
        
        # Add results to migration data
        migration_data["results"] = results
        
        # Return overall results
        return CommandResult.success(
            f"Migration completed: {results['created']} created, {results['updated']} updated, "
            f"{results['skipped']} skipped, {results['failed']} failed",
            migration_data,
            "See details below for operation results."
        )
        
    except Exception as e:
        sublime_error = handle_api_error(e)
        if isinstance(sublime_error, ApiError):
            return CommandResult.error(f"API error during migration: {sublime_error.message}", sublime_error.details)
        else:
            return CommandResult.error(f"Error during migration: {sublime_error.message}")


def categorize_actions(source_actions: List[Dict], dest_actions: List[Dict]) -> tuple:
    """Categorize actions as new or updates based on name matching.
    
    Args:
        source_actions: List of source action objects
        dest_actions: List of destination action objects
        
    Returns:
        tuple: (new_actions, update_actions)
    """
    # Create lookup dict for destination actions by name
    dest_action_map = {a.get("name"): a for a in dest_actions}
    
    new_actions = []
    update_actions = []
    
    for action in source_actions:
        action_name = action.get("name")
        if action_name in dest_action_map:
            update_actions.append(action)
        else:
            new_actions.append(action)
    
    return new_actions, update_actions


def perform_migration(formatter, dest_client, new_actions: List[Dict], 
                     update_actions: List[Dict], existing_actions: List[Dict]) -> Dict:
    """Perform the actual migration of actions to the destination.
    
    Args:
        formatter: Output formatter
        dest_client: API client for destination
        new_actions: List of new actions to create
        update_actions: List of actions to update
        existing_actions: List of existing actions in destination
        
    Returns:
        Dict: Results of the migration
    """
    results = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "details": []
    }
    
    # Create a map of existing actions by name for quick lookup
    existing_map = {a.get("name"): a for a in existing_actions}
    
    # Process new actions
    if new_actions:
        with formatter.create_progress("Creating new actions...", total=len(new_actions)) as (progress, task):
            for i, action in enumerate(new_actions):
                try:
                    # Create a clean payload from the source action
                    payload = create_action_payload(action)
                    
                    # Post to destination
                    dest_client.post("/v1/actions", payload)
                    results["created"] += 1
                    results["details"].append({
                        "name": action.get("name"),
                        "type": action.get("type"),
                        "status": "created"
                    })
                    
                except ApiError as e:
                    results["failed"] += 1
                    results["details"].append({
                        "name": action.get("name"),
                        "type": action.get("type"),
                        "status": "failed",
                        "reason": e.message
                    })
                except Exception as e:
                    results["failed"] += 1
                    results["details"].append({
                        "name": action.get("name"),
                        "type": action.get("type"),
                        "status": "failed",
                        "reason": str(e)
                    })
                
                # Update progress
                if progress and task:
                    progress.update(task, completed=i+1)
    
    # Process updates
    if update_actions:
        with formatter.create_progress("Updating existing actions...", total=len(update_actions)) as (progress, task):
            for i, action in enumerate(update_actions):
                action_name = action.get("name")
                existing = existing_map.get(action_name)
                
                if not existing:
                    results["skipped"] += 1
                    results["details"].append({
                        "name": action_name,
                        "type": action.get("type"),
                        "status": "skipped",
                        "reason": "Action no longer exists in destination"
                    })
                    if progress and task:
                        progress.update(task, completed=i+1)
                    continue
                
                try:
                    # Check if update is needed by comparing config
                    if action.get("config") != existing.get("config"):
                        # Create update payload
                        payload = create_action_payload(action)
                        
                        # Update the action
                        dest_client.patch(f"/v1/actions/{existing.get('id')}", payload)
                        results["updated"] += 1
                        results["details"].append({
                            "name": action_name,
                            "type": action.get("type"),
                            "status": "updated"
                        })
                    else:
                        results["skipped"] += 1
                        results["details"].append({
                            "name": action_name,
                            "type": action.get("type"),
                            "status": "skipped",
                            "reason": "No changes needed"
                        })
                        
                except ApiError as e:
                    results["failed"] += 1
                    results["details"].append({
                        "name": action_name,
                        "type": action.get("type"),
                        "status": "failed",
                        "reason": e.message
                    })
                except Exception as e:
                    results["failed"] += 1
                    results["details"].append({
                        "name": action_name,
                        "type": action.get("type"),
                        "status": "failed",
                        "reason": str(e)
                    })
                
                # Update progress
                if progress and task:
                    progress.update(task, completed=i+1)
    
    return results


def create_action_payload(action: Dict) -> Dict:
    """Create a clean action payload for API requests.
    
    Args:
        action: Source action object
        
    Returns:
        Dict: Cleaned action payload
    """
    action_type = action.get("type")
    
    # Special case for warning_banner
    if action_type == "warning_banner":
        # Use the exact template structure required for warning banner
        banner_config = action.get("config", {})
        return {
            "config": {
                "warning_banner_title": banner_config.get("warning_banner_title", ""),
                "warning_banner_body": banner_config.get("warning_banner_body", "")
            }
        }

    # Extract only the fields needed for creation/update
    payload = {
        "name": action.get("name"),
        "type": action.get("type"),
        "active": action.get("active", False)
    }
    
    # Include config if present
    if "config" in action and action["config"]:
        payload["config"] = action["config"]
    
    # Handle any type-specific requirements
    action_type = action.get("type")
    
    if action_type == "webhook" and "config" in payload:
        # Ensure webhook config has required fields
        if "custom_headers" not in payload["config"]:
            payload["config"]["custom_headers"] = []
        
        # Include wait_for_complete_rule_evaluation if present
        if "wait_for_complete_rule_evaluation" in action:
            payload["wait_for_complete_rule_evaluation"] = action["wait_for_complete_rule_evaluation"]
    
    return payload


# Click command definition
@click.command()
@click.option("--source-api-key", help="API key for the source instance")
@click.option("--source-region", help="Region of the source instance")
@click.option("--dest-api-key", help="API key for the destination instance")
@click.option("--dest-region", help="Region of the destination instance")
@click.option("--include-ids", help="Comma-separated list of action IDs to include")
@click.option("--exclude-ids", help="Comma-separated list of action IDs to exclude")
@click.option("--include-types", help="Comma-separated list of action types to include")
@click.option("--exclude-types", help="Comma-separated list of action types to exclude")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def actions(source_api_key, source_region, dest_api_key, dest_region,
            include_ids, exclude_ids, include_types, exclude_types,
            dry_run, yes, output_format):
    """Migrate actions between Sublime Security instances.
    
    This command copies actions from the source instance to the destination instance.
    It can selectively migrate specific actions by ID or type.
    
    Examples:
        # Migrate all actions
        sublime migrate actions --source-api-key KEY1 --source-region NA_EAST --dest-api-key KEY2 --dest-region NA_WEST
        
        # Migrate only webhook actions
        sublime migrate actions --include-types webhook --source-api-key KEY1 --dest-api-key KEY2
        
        # Preview migration without making changes
        sublime migrate actions --dry-run --source-api-key KEY1 --dest-api-key KEY2
    """
    # Create formatter based on output format
    formatter = create_formatter(output_format)
    
    # If --yes flag is provided, modify the formatter to auto-confirm
    if yes:
        original_prompt = formatter.prompt_confirmation
        formatter.prompt_confirmation = lambda _: True
    
    # Execute the implementation function
    result = migrate_actions_between_instances(
        source_api_key, source_region, 
        dest_api_key, dest_region,
        include_ids, exclude_ids, 
        include_types, exclude_types,
        dry_run, formatter
    )
    
    # Reset the formatter if it was modified
    if yes and hasattr(formatter, 'original_prompt'):
        formatter.prompt_confirmation = original_prompt
    
    # Output the result
    formatter.output_result(result)