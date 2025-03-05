"""Commands for migrating lists between Sublime Security instances."""
from typing import Dict, List, Optional, Set
import json

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

from sublime_migration_cli.api.client import get_api_client_from_env_or_args


# Authors to exclude from migration (system and built-in lists)
EXCLUDED_AUTHORS = {"Sublime Security", "System"}


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
        sublime migrate lists --include-user-created --source-api-key KEY1 --dest-api-key KEY2
        
        # Migrate only string lists
        sublime migrate lists --include-types string --source-api-key KEY1 --dest-api-key KEY2
        
        # Preview migration without making changes
        sublime migrate lists --dry-run --source-api-key KEY1 --dest-api-key KEY2
    """
    console = Console()
    results = {"status": "started", "message": "Migration of Lists"}
    
    if output_format == "table":
        console.print("[bold]Migration of Lists[/]")
    
    try:
        # Create API clients for source and destination
        source_client = get_api_client_from_env_or_args(source_api_key, source_region)
        dest_client = get_api_client_from_env_or_args(dest_api_key, dest_region, destination=True)
        
        # Get all list types
        list_types = ["string", "user_group"]
        
        # Apply type filter if specified
        if include_types:
            specified_types = [t.strip() for t in include_types.split(",")]
            list_types = [t for t in list_types if t in specified_types]
        
        # Fetch all lists from source
        all_source_lists = []
        if output_format == "table":
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Fetching lists from source..."),
                console=console
            ) as progress:
                task = progress.add_task("Fetching", total=len(list_types))
                
                for list_type in list_types:
                    try:
                        response = source_client.get("/v1/lists", params={"list_types": list_type})
                        all_source_lists.extend(response)
                    except Exception as e:
                        console.print(f"[yellow]Warning: Failed to fetch {list_type} lists: {str(e)}[/]")
                    
                    progress.update(task, advance=1)
        else:
            # JSON output mode - no progress indicators
            for list_type in list_types:
                try:
                    response = source_client.get("/v1/lists", params={"list_types": list_type})
                    all_source_lists.extend(response)
                except Exception as e:
                    results["warning"] = f"Failed to fetch {list_type} lists: {str(e)}"
        
        # Apply filters
        filtered_lists = filter_lists(
            all_source_lists, 
            include_ids, 
            exclude_ids, 
            include_system_created
        )
        
        if not filtered_lists:
            message = "No lists to migrate after applying filters."
            if output_format == "table":
                console.print(f"[yellow]{message}[/]")
            else:
                results["status"] = "completed"
                results["message"] = message
                click.echo(json.dumps(results, indent=2))
            return
        
        # Fetch complete list data with entries for each list
        source_lists_with_entries = []
        if filtered_lists:
            if output_format == "table":
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold blue]Fetching list entries..."),
                    console=console
                ) as progress:
                    task = progress.add_task("Fetching", total=len(filtered_lists))
                    
                    for list_item in filtered_lists:
                        # Only fetch details for string lists, user_group lists don't need entries
                        if list_item.get("entry_type") == "string":
                            list_id = list_item.get("id")
                            try:
                                detailed_list = source_client.get(f"/v1/lists/{list_id}")
                                source_lists_with_entries.append(detailed_list)
                            except Exception as e:
                                console.print(f"[yellow]Warning: Failed to fetch entries for list '{list_item.get('name')}': {str(e)}[/]")
                                # Still include the list without entries
                                source_lists_with_entries.append(list_item)
                        else:
                            # For user_group lists, use as-is without fetching entries
                            source_lists_with_entries.append(list_item)
                        
                        progress.update(task, advance=1)
            else:
                # JSON output mode
                for list_item in filtered_lists:
                    if list_item.get("entry_type") == "string":
                        list_id = list_item.get("id")
                        try:
                            detailed_list = source_client.get(f"/v1/lists/{list_id}")
                            source_lists_with_entries.append(detailed_list)
                        except Exception as e:
                            # Add a warning to results
                            results.setdefault("warnings", []).append(
                            f"Failed to fetch entries for list '{list_item.get('name')}': {str(e)}"
                        )
                            # Still include the list without entries
                            source_lists_with_entries.append(list_item)
                    else:
                        source_lists_with_entries.append(list_item)
        
        # # Apply filters
        # filtered_lists = filter_lists(
        #     source_lists_with_entries, 
        #     include_ids, 
        #     exclude_ids, 
        #     include_system_created
        # )
        
        # if not filtered_lists:
        #     message = "No lists to migrate after applying filters."
        #     if output_format == "table":
        #         console.print(f"[yellow]{message}[/]")
        #     else:
        #         results["status"] = "completed"
        #         results["message"] = message
        #         click.echo(json.dumps(results, indent=2))
        #     return
            
        list_count_message = f"Found {len(source_lists_with_entries)} lists to migrate."
        if output_format == "table":
            console.print(f"[bold]{list_count_message}[/]")
        else:
            results["count"] = len(source_lists_with_entries)
            results["message"] = list_count_message
        
        # For user_group lists, we need to fetch user groups from destination
        dest_user_groups = {}
        if any(l.get("entry_type") == "user_group" for l in source_lists_with_entries):
            try:
                user_groups_response = dest_client.get("/v1/user-groups")
                # Create a mapping of user group names to IDs
                dest_user_groups = {
                    group.get("name"): group.get("id") 
                    for group in user_groups_response
                }
            except Exception as e:
                error_msg = f"Failed to fetch user groups from destination: {str(e)}"
                if output_format == "table":
                    console.print(f"[yellow]Warning: {error_msg}[/]")
                else:
                    results.setdefault("warnings", []).append(error_msg)
        
        # Fetch lists from destination for comparison
        dest_lists = []
        if output_format == "table":
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Fetching lists from destination..."),
                console=console
            ) as progress:
                task = progress.add_task("Fetching", total=len(list_types))
                
                for list_type in list_types:
                    try:
                        response = dest_client.get("/v1/lists", params={"list_types": list_type})
                        dest_lists.extend(response)
                    except Exception as e:
                        console.print(f"[yellow]Warning: Failed to fetch {list_type} lists from destination: {str(e)}[/]")
                    
                    progress.update(task, advance=1)
        else:
            # JSON output mode
            for list_type in list_types:
                try:
                    response = dest_client.get("/v1/lists", params={"list_types": list_type})
                    dest_lists.extend(response)
                except Exception as e:
                    results.setdefault("warnings", []).append(
                        f"Failed to fetch {list_type} lists from destination: {str(e)}"
                    )
        
        # Compare and categorize lists
        new_lists, update_lists = categorize_lists(source_lists_with_entries, dest_lists)
        
        # Preview changes
        if not new_lists and not update_lists:
            message = "All selected lists already exist in the destination instance."
            if output_format == "table":
                console.print(f"[green]{message}[/]")
            else:
                results["status"] = "completed"
                results["message"] = message
                click.echo(json.dumps(results, indent=2))
            return
            
        preview_message = f"\nPreparing to migrate {len(new_lists)} new lists and potentially update {len(update_lists)} existing lists."
        if output_format == "table":
            console.print(f"[bold]{preview_message}[/]")
        
            # Display preview table
            preview_table = Table(title="Lists to Migrate")
            preview_table.add_column("ID", style="dim", no_wrap=True)
            preview_table.add_column("Name", style="green")
            preview_table.add_column("Type", style="blue")
            preview_table.add_column("Entries", style="cyan", justify="right")
            preview_table.add_column("Status", style="magenta")
            
            for list_item in new_lists:
                preview_table.add_row(
                    list_item.get("id", ""),
                    list_item.get("name", ""),
                    list_item.get("entry_type", ""),
                    str(list_item.get("entry_count", len(list_item.get("entries", [])) if list_item.get("entries") is not None else 0)),
                    "New"
                )
            
            for list_item in update_lists:
                preview_table.add_row(
                    list_item.get("id", ""),
                    list_item.get("name", ""),
                    list_item.get("entry_type", ""),
                    str(list_item.get("entry_count", len(list_item.get("entries", [])) if list_item.get("entries") is not None else 0)),
                    "Update (if different)"
                )
            
            console.print(preview_table)
        else:
            # JSON output
            results["new_lists"] = len(new_lists)
            results["update_lists"] = len(update_lists)
            results["lists_to_migrate"] = [
                {
                    "id": item.get("id", ""),
                    "name": item.get("name", ""),
                    "type": item.get("entry_type", ""),
                    "entries": len(item.get("entries", [])),
                    "status": "New"
                }
                for item in new_lists
            ] + [
                {
                    "id": item.get("id", ""),
                    "name": item.get("name", ""),
                    "type": item.get("entry_type", ""),
                    "entries": len(item.get("entries", [])),
                    "status": "Update (if different)"
                }
                for item in update_lists
            ]
        
        # If dry run, stop here
        if dry_run:
            dry_run_message = "DRY RUN: No changes were made."
            if output_format == "table":
                console.print(f"\n[yellow]{dry_run_message}[/]")
            else:
                results["status"] = "dry_run"
                results["message"] = dry_run_message
                click.echo(json.dumps(results, indent=2))
            return
        
        # Ask for confirmation
        if not yes and output_format == "table" and not Confirm.ask("\nDo you want to proceed with the migration?"):
            cancel_message = "Migration canceled by user."
            console.print(f"[yellow]{cancel_message}[/]")
            return
        
        # Perform actual migration
        migration_results = migrate_lists(
            console, dest_client, new_lists, update_lists, dest_lists, 
            dest_user_groups, output_format
        )
        
        # Display results
        results_message = f"Migration completed: {migration_results['created']} created, {migration_results['updated']} updated, {migration_results['skipped']} skipped, {migration_results['failed']} failed"
        
        if output_format == "table":
            console.print(f"\n[bold green]{results_message}[/]")
        else:
            results["status"] = "completed"
            results["message"] = results_message
            results["details"] = migration_results
            click.echo(json.dumps(results, indent=2))
        
    except Exception as e:
        error_message = f"Error during migration: {str(e)}"
        if output_format == "table":
            console.print(f"[bold red]{error_message}[/]")
        else:
            results["status"] = "error"
            results["error"] = error_message
            click.echo(json.dumps(results, indent=2))


def filter_lists(lists: List[Dict], include_ids: Optional[str], exclude_ids: Optional[str],
                 include_system_created: bool) -> List[Dict]:
    """Filter lists based on the provided criteria.
    
    Args:
        lists: List of list objects
        include_ids: Comma-separated list of list IDs to include
        exclude_ids: Comma-separated list of list IDs to exclude
        include_system_created: Include system-created lists (not system)
        
    Returns:
        List[Dict]: Filtered list objects
    """
    filtered = lists
    
    # Filter by user-created
    if not include_system_created:
        filtered = [lst for lst in filtered if lst.get("created_by_user_name") not in EXCLUDED_AUTHORS]
    
    # Filter by IDs
    if include_ids:
        ids = [id.strip() for id in include_ids.split(",")]
        filtered = [lst for lst in filtered if lst.get("id") in ids]
        
    if exclude_ids:
        ids = [id.strip() for id in exclude_ids.split(",")]
        filtered = [lst for lst in filtered if lst.get("id") not in ids]
    
    return filtered


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


def migrate_lists(console: Console, dest_client, new_lists: List[Dict], 
                  update_lists: List[Dict], existing_lists: List[Dict],
                  dest_user_groups: Dict[str, str], output_format: str) -> Dict:
    """Migrate lists to the destination instance.
    
    Args:
        console: Rich console for output
        dest_client: API client for the destination
        new_lists: List of new lists to create
        update_lists: List of lists to potentially update
        existing_lists: List of existing lists in the destination
        dest_user_groups: Mapping of user group names to IDs
        output_format: Output format ("table" or "json")
        
    Returns:
        Dict: Migration results summary
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
        if output_format == "table":
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Creating new lists..."),
                console=console
            ) as progress:
                task = progress.add_task("Creating", total=len(new_lists))
                
                for list_item in new_lists:
                    process_new_list(list_item, dest_client, dest_user_groups, results)
                    progress.update(task, advance=1)
        else:
            # JSON output mode - no progress indicators
            for list_item in new_lists:
                process_new_list(list_item, dest_client, dest_user_groups, results)
    
    # Process updates
    if update_lists:
        if output_format == "table":
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Updating existing lists..."),
                console=console
            ) as progress:
                task = progress.add_task("Updating", total=len(update_lists))
                
                for list_item in update_lists:
                    process_update_list(list_item, dest_client, existing_map, dest_user_groups, results, console, output_format)
                    progress.update(task, advance=1)
        else:
            # JSON output mode - no progress indicators
            for list_item in update_lists:
                process_update_list(list_item, dest_client, existing_map, dest_user_groups, results, console, output_format)
    
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
            "status": "created"
        })
        
    except Exception as e:
        results["failed"] += 1
        results["details"].append({
            "name": list_name,
            "status": "failed",
            "reason": str(e)
        })


def process_update_list(list_item: Dict, dest_client, existing_map: Dict[str, Dict], 
                        dest_user_groups: Dict[str, str], results: Dict, 
                        console: Console, output_format: str):
    """Process a list update for migration."""
    list_name = list_item.get("name", "")
    existing = existing_map.get(list_name)
    
    if not existing:
        results["skipped"] += 1
        results["details"].append({
            "name": list_name,
            "status": "skipped",
            "reason": "List not found in destination"
        })
        return
    
    try:
        # Handle different list types
        entry_type = list_item.get("entry_type", "string")
        
        if entry_type == "user_group":
            # For user_group lists, we need to check if the provider group has changed
            source_provider_name = list_item.get("provider_group_name")
            dest_provider_id = dest_user_groups.get(source_provider_name)
            
            if not dest_provider_id:
                results["failed"] += 1
                results["details"].append({
                    "name": list_name,
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
                    "status": "updated",
                    "reason": "Provider group changed"
                })
            else:
                results["skipped"] += 1
                results["details"].append({
                    "name": list_name,
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
                    "status": "updated",
                    "reason": "Entries changed"
                })
            else:
                results["skipped"] += 1
                results["details"].append({
                    "name": list_name,
                    "status": "skipped",
                    "reason": "No changes needed"
                })
                
    except Exception as e:
        error_message = f"Failed to update list '{list_name}': {str(e)}"
        results["failed"] += 1
        results["details"].append({
            "name": list_name,
            "status": "failed",
            "reason": str(e)
        })
        
        if output_format == "table":
            console.print(f"[red]{error_message}[/]")