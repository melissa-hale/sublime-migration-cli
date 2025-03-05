"""Refactored commands for migrating lists using utility functions."""
from typing import Dict, List, Optional, Set
import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.presentation.base import CommandResult
from sublime_migration_cli.presentation.factory import create_formatter

# Import our utility functions
from sublime_migration_cli.utils.api import PaginatedFetcher
from sublime_migration_cli.utils.filtering import filter_by_creator, filter_by_ids
from sublime_migration_cli.utils.errors import (
    ApiError, MigrationError, handle_api_error, ErrorHandler
)

# Authors to exclude from migration (system and built-in lists)
EXCLUDED_AUTHORS = {"Sublime Security", "System"}


# Implementation functions
def migrate_lists_between_instances(
    source_api_key=None, source_region=None, 
    dest_api_key=None, dest_region=None,
    include_ids=None, exclude_ids=None, 
    include_types=None, include_system_created=False,
    dry_run=False, formatter=None
):
    """Implementation for migrating lists between instances.
    
    Args:
        source_api_key: API key for source instance
        source_region: Region for source instance
        dest_api_key: API key for destination instance
        dest_region: Region for destination instance
        include_ids: Comma-separated list of list IDs to include
        exclude_ids: Comma-separated list of list IDs to exclude
        include_types: Comma-separated list of list types to include
        include_system_created: Include system-created lists
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
        
        # Get all list types
        list_types = ["string", "user_group"]
        
        # Apply type filter if specified
        if include_types:
            specified_types = [t.strip() for t in include_types.split(",")]
            list_types = [t for t in list_types if t in specified_types]
        
        # Use PaginatedFetcher to fetch all lists from source
        source_fetcher = PaginatedFetcher(source_client, formatter)
        all_source_lists = []
        
        with formatter.create_progress("Fetching lists from source...", total=len(list_types)) as (progress, task):
            for i, list_type in enumerate(list_types):
                try:
                    params = {"list_types": list_type}
                    type_lists = source_fetcher.fetch_all(
                        "/v1/lists", 
                        params=params,
                        progress_message=None  # Don't show nested progress
                    )
                    all_source_lists.extend(type_lists)
                except ApiError as e:
                    formatter.output_error(f"Warning: Failed to fetch {list_type} lists: {e.message}")
                
                # Update progress
                if progress and task:
                    progress.update(task, completed=i+1)
        
        # Apply filters using our utility functions
        filtered_lists = filter_by_creator(
            all_source_lists, 
            include_system_created, 
            EXCLUDED_AUTHORS
        )
        
        filtered_lists = filter_by_ids(
            filtered_lists, 
            include_ids, 
            exclude_ids
        )
        
        if not filtered_lists:
            return CommandResult.error("No lists to migrate after applying filters.")
            
        # Fetch complete list data with entries for each list
        source_lists_with_entries = []
        if filtered_lists:
            with formatter.create_progress("Fetching list entries...", total=len(filtered_lists)) as (progress, task):
                for i, list_item in enumerate(filtered_lists):
                    # Only fetch details for string lists, user_group lists don't need entries
                    if list_item.get("entry_type") == "string":
                        list_id = list_item.get("id")
                        try:
                            detailed_list = source_client.get(f"/v1/lists/{list_id}")
                            source_lists_with_entries.append(detailed_list)
                        except ApiError as e:
                            formatter.output_error(f"Warning: Failed to fetch entries for list '{list_item.get('name')}': {e.message}")
                            # Still include the list without entries
                            source_lists_with_entries.append(list_item)
                    else:
                        # For user_group lists, use as-is without fetching entries
                        source_lists_with_entries.append(list_item)
                    
                    # Update progress
                    if progress and task:
                        progress.update(task, completed=i+1)
        
        if not source_lists_with_entries:
            return CommandResult.error("No lists to migrate after fetching details.")
            
        # For user_group lists, we need to fetch user groups from destination
        dest_user_groups = {}
        if any(l.get("entry_type") == "user_group" for l in source_lists_with_entries):
            with formatter.create_progress("Fetching user groups from destination...") as (progress, task):
                try:
                    user_groups_response = dest_client.get("/v1/user-groups")
                    # Create a mapping of user group names to IDs
                    dest_user_groups = {
                        group.get("name"): group.get("id") 
                        for group in user_groups_response
                    }
                    if progress and task:
                        progress.update(task, advance=1)
                except ApiError as e:
                    formatter.output_error(f"Warning: Failed to fetch user groups from destination: {e.message}")
        
        # Use PaginatedFetcher to fetch all lists from destination
        dest_fetcher = PaginatedFetcher(dest_client, formatter)
        dest_lists = []
        
        with formatter.create_progress("Fetching lists from destination...", total=len(list_types)) as (progress, task):
            for i, list_type in enumerate(list_types):
                try:
                    params = {"list_types": list_type}
                    type_lists = dest_fetcher.fetch_all(
                        "/v1/lists", 
                        params=params,
                        progress_message=None  # Don't show nested progress
                    )
                    dest_lists.extend(type_lists)
                except ApiError as e:
                    formatter.output_error(f"Warning: Failed to fetch {list_type} lists from destination: {e.message}")
                
                # Update progress
                if progress and task:
                    progress.update(task, completed=i+1)
        
        # Compare and categorize lists
        new_lists, update_lists = categorize_lists(source_lists_with_entries, dest_lists)
        
        # If no lists to migrate, return early
        if not new_lists and not update_lists:
            return CommandResult.success("All selected lists already exist in the destination instance.")
            
        # Prepare response data
        migration_data = {
            "new_lists": [
                {
                    "id": list_item.get("id", ""),
                    "name": list_item.get("name", ""),
                    "type": list_item.get("entry_type", ""),
                    "entries": len(list_item.get("entries", [])) if list_item.get("entries") is not None else 0,
                    "status": "New"
                }
                for list_item in new_lists
            ],
            "update_lists": [
                {
                    "id": list_item.get("id", ""),
                    "name": list_item.get("name", ""),
                    "type": list_item.get("entry_type", ""),
                    "entries": len(list_item.get("entries", [])) if list_item.get("entries") is not None else 0,
                    "status": "Update (if different)"
                }
                for list_item in update_lists
            ]
        }
        
        # Add summary stats
        migration_data["summary"] = {
            "new_count": len(new_lists),
            "update_count": len(update_lists),
            "total_count": len(new_lists) + len(update_lists)
        }
        
        # If dry run, return preview data
        if dry_run:
            return CommandResult.success(
                "DRY RUN: Preview of lists to migrate",
                migration_data,
                "No changes were made to the destination instance."
            )
        
        # Show preview before confirmation in interactive mode
        formatter.output_result(CommandResult.success(
            "Lists that will be migrated:",
            migration_data,
            "Please confirm to proceed with migration."
        ))
        
        # Confirm migration if interactive
        if not formatter.prompt_confirmation("\nDo you want to proceed with the migration?"):
            return CommandResult.success("Migration canceled by user.")
        
        # Perform the migration
        results = perform_migration(formatter, dest_client, new_lists, update_lists, dest_lists, dest_user_groups)
        
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


def categorize_lists(source_lists: List[Dict], dest_lists: List[Dict]) -> tuple:
    """Categorize lists as new or updates based on name matching.
    
    Args:
        source_lists: List of source list objects
        dest_lists: List of destination list objects
        
    Returns:
        tuple: (new_lists, update_lists)
    """
    # Create lookup dict for destination lists by name
    dest_list_map = {lst.get("name"): lst for lst in dest_lists}
    
    new_lists = []
    update_lists = []
    
    for list_item in source_lists:
        list_name = list_item.get("name")
        if list_name in dest_list_map:
            update_lists.append(list_item)
        else:
            new_lists.append(list_item)
    
    return new_lists, update_lists


def perform_migration(formatter, dest_client, new_lists: List[Dict], 
                     update_lists: List[Dict], existing_lists: List[Dict],
                     dest_user_groups: Dict[str, str]) -> Dict:
    """Perform the actual migration of lists to the destination.
    
    Args:
        formatter: Output formatter
        dest_client: API client for destination
        new_lists: List of new lists to create
        update_lists: List of lists to update
        existing_lists: List of existing lists in destination
        dest_user_groups: Mapping of user group names to IDs
        
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
    
    # Create a map of existing lists by name for quick lookup
    existing_map = {lst.get("name"): lst for lst in existing_lists}
    
    # Process new lists
    if new_lists:
        with formatter.create_progress("Creating new lists...", total=len(new_lists)) as (progress, task):
            for i, list_item in enumerate(new_lists):
                process_new_list(list_item, dest_client, dest_user_groups, results)
                # Update progress
                if progress and task:
                    progress.update(task, completed=i+1)
    
    # Process updates
    if update_lists:
        with formatter.create_progress("Updating existing lists...", total=len(update_lists)) as (progress, task):
            for i, list_item in enumerate(update_lists):
                process_update_list(list_item, dest_client, existing_map, dest_user_groups, results, formatter)
                # Update progress
                if progress and task:
                    progress.update(task, completed=i+1)
    
    return results


def process_new_list(list_item: Dict, dest_client, dest_user_groups: Dict[str, str], results: Dict):
    """Process a new list for migration."""
    list_name = list_item.get("name", "")
    try:
        # Create the appropriate payload based on list type
        entry_type = list_item.get("entry_type", "string")
        
        if entry_type == "user_group":
            # For user_group lists, we need to map the provider_group_name to an ID
            provider_group_name = list_item.get("provider_group_name")
            provider_group_id = dest_user_groups.get(provider_group_name)
            
            if not provider_group_id:
                results["failed"] += 1
                results["details"].append({
                    "name": list_name,
                    "type": entry_type,
                    "status": "failed",
                    "reason": f"User group '{provider_group_name}' not found in destination"
                })
                return
                
            payload = {
                "name": list_name,
                "description": list_item.get("description", ""),
                "entry_type": "user_group",
                "provider_group_id": provider_group_id
            }
        else:  # string list
            payload = {
                "name": list_name,
                "description": list_item.get("description", ""),
                "entry_type": "string",
                "entries": list_item.get("entries", [])
            }
        
        # Post to destination
        dest_client.post("/v1/lists", payload)
        results["created"] += 1
        results["details"].append({
            "name": list_name,
            "type": entry_type,
            "status": "created"
        })
        
    except ApiError as e:
        results["failed"] += 1
        results["details"].append({
            "name": list_name,
            "type": list_item.get("entry_type", "unknown"),
            "status": "failed",
            "reason": e.message
        })
    except Exception as e:
        results["failed"] += 1
        results["details"].append({
            "name": list_name,
            "type": list_item.get("entry_type", "unknown"),
            "status": "failed",
            "reason": str(e)
        })


def process_update_list(list_item: Dict, dest_client, existing_map: Dict[str, Dict], 
                       dest_user_groups: Dict[str, str], results: Dict, formatter):
    """Process a list update for migration."""
    list_name = list_item.get("name", "")
    entry_type = list_item.get("entry_type", "string")
    existing = existing_map.get(list_name)
    
    if not existing:
        results["skipped"] += 1
        results["details"].append({
            "name": list_name,
            "type": entry_type,
            "status": "skipped",
            "reason": "List not found in destination"
        })
        return
    
    try:
        # Handle different list types
        if entry_type == "user_group":
            # For user_group lists, we need to check if the provider group has changed
            source_provider_name = list_item.get("provider_group_name")
            dest_provider_id = dest_user_groups.get(source_provider_name)
            
            if not dest_provider_id:
                results["failed"] += 1
                results["details"].append({
                    "name": list_name,
                    "type": entry_type,
                    "status": "failed",
                    "reason": f"User group '{source_provider_name}' not found in destination"
                })
                return
                
            # Check if provider group ID has changed
            if existing.get("provider_group_id") != dest_provider_id:
                payload = {
                    "provider_group_id": dest_provider_id
                }
                
                # Update the list
                dest_client.patch(f"/v1/lists/{existing.get('id')}", payload)
                results["updated"] += 1
                results["details"].append({
                    "name": list_name,
                    "type": entry_type,
                    "status": "updated",
                    "reason": "Provider group changed"
                })
            else:
                results["skipped"] += 1
                results["details"].append({
                    "name": list_name,
                    "type": entry_type,
                    "status": "skipped",
                    "reason": "No changes needed"
                })
                
        else:  # string list
            # For string lists, compare and update entries
            # Get detailed list info if we don't have it already
            existing_with_entries = dest_client.get(f"/v1/lists/{existing.get('id')}")
            existing_entries = set(existing_with_entries.get("entries", []))
            source_entries = set(list_item.get("entries", []))
            
            # If entries are different, update the list
            if existing_entries != source_entries:
                payload = {
                    "entries": list(source_entries)
                }
                
                # Update the list
                dest_client.patch(f"/v1/lists/{existing.get('id')}", payload)
                results["updated"] += 1
                results["details"].append({
                    "name": list_name,
                    "type": entry_type,
                    "status": "updated",
                    "reason": "Entries changed"
                })
            else:
                results["skipped"] += 1
                results["details"].append({
                    "name": list_name,
                    "type": entry_type,
                    "status": "skipped",
                    "reason": "No changes needed"
                })
                
    except ApiError as e:
        results["failed"] += 1
        results["details"].append({
            "name": list_name,
            "type": entry_type,
            "status": "failed",
            "reason": e.message
        })
    except Exception as e:
        results["failed"] += 1
        results["details"].append({
            "name": list_name,
            "type": entry_type,
            "status": "failed",
            "reason": str(e)
        })


# Click command definition
@click.command()
@click.option("--source-api-key", help="API key for the source instance")
@click.option("--source-region", help="Region of the source instance")
@click.option("--dest-api-key", help="API key for the destination instance")
@click.option("--dest-region", help="Region of the destination instance")
@click.option("--include-ids", help="Comma-separated list of list IDs to include")
@click.option("--exclude-ids", help="Comma-separated list of list IDs to exclude")
@click.option("--include-types", help="Comma-separated list of list types to include (string, user_group)")
@click.option("--include-system-created", is_flag=True, 
              help="Include system-created lists (by default, only user-created lists are migrated)")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def lists(source_api_key, source_region, dest_api_key, dest_region,
          include_ids, exclude_ids, include_types, include_system_created,
          dry_run, yes, output_format):
    """Migrate lists between Sublime Security instances.
    
    This command copies lists from the source instance to the destination instance.
    It can selectively migrate specific lists by ID or type.
    
    By default, only user-created lists are migrated (not those created by "Sublime Security" or "System").
    Use --include-system-created to include system-created lists in the migration.
    
    Examples:
        # Migrate all user-created lists
        sublime migrate lists --source-api-key KEY1 --dest-api-key KEY2
        
        # Migrate only string lists
        sublime migrate lists --include-types string --source-api-key KEY1 --dest-api-key KEY2
        
        # Preview migration without making changes
        sublime migrate lists --dry-run --source-api-key KEY1 --dest-api-key KEY2
    """
    # Create formatter based on output format
    formatter = create_formatter(output_format)
    
    # If --yes flag is provided, modify the formatter to auto-confirm
    if yes:
        original_prompt = formatter.prompt_confirmation
        formatter.prompt_confirmation = lambda _: True
    
    # Execute the implementation function
    result = migrate_lists_between_instances(
        source_api_key, source_region, 
        dest_api_key, dest_region,
        include_ids, exclude_ids, 
        include_types, include_system_created,
        dry_run, formatter
    )
    
    # Reset the formatter if it was modified
    if yes and hasattr(formatter, 'original_prompt'):
        formatter.prompt_confirmation = original_prompt
    
    # Output the result
    formatter.output_result(result)