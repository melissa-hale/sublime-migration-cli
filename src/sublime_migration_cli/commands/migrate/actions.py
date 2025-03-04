"""Commands for migrating actions between Sublime Security instances."""
from typing import Dict, List, Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

from sublime_migration_cli.api.client import get_api_client_from_env_or_args

IGNORE_TYPES = {
    "quarantine_message", 
    "auto_review", 
    "move_to_spam", 
    "delete_message"
}

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
def actions(source_api_key, source_region, dest_api_key, dest_region,
            include_ids, exclude_ids, include_types, exclude_types,
            dry_run, yes):
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
    console = Console()
    console.print("[bold]Migration of Actions[/]")
    
    try:
        # Create API clients for source and destination
        source_client = get_api_client_from_env_or_args(source_api_key, source_region)
        dest_client = get_api_client_from_env_or_args(dest_api_key, dest_region, destination=True)
        
        # Fetch actions from source
        with console.status("[blue]Fetching actions from source instance...[/]"):
            source_actions = source_client.get("/v1/actions")
        
        # Apply filters if specified
        filtered_actions = filter_actions(source_actions, include_ids, exclude_ids, include_types, exclude_types)
        
        if not filtered_actions:
            console.print("[yellow]No actions to migrate after applying filters.[/]")
            return
            
        console.print(f"Found [bold]{len(filtered_actions)}[/] actions to migrate.")
        
        # Fetch actions from destination for comparison
        with console.status("[blue]Fetching actions from destination instance...[/]"):
            dest_actions = dest_client.get("/v1/actions")
        
        # Compare and categorize actions
        new_actions, update_actions = categorize_actions(filtered_actions, dest_actions)
        
        # Preview changes
        if not new_actions and not update_actions:
            console.print("[green]All selected actions already exist in the destination instance.[/]")
            return
            
        console.print(f"\nPreparing to migrate [bold]{len(new_actions)}[/] new actions and potentially update [bold]{len(update_actions)}[/] existing actions.")
        
        # Display preview table
        preview_table = Table(title="Actions to Migrate")
        preview_table.add_column("ID", style="dim", no_wrap=True)
        preview_table.add_column("Name", style="green")
        preview_table.add_column("Type", style="blue")
        preview_table.add_column("Status", style="cyan")
        
        for action in new_actions:
            preview_table.add_row(
                action.get("id", ""),
                action.get("name", ""),
                action.get("type", ""),
                "New"
            )
        
        for action in update_actions:
            preview_table.add_row(
                action.get("id", ""),
                action.get("name", ""),
                action.get("type", ""),
                "Update (if different)"
            )
        
        console.print(preview_table)
        
        # If dry run, stop here
        if dry_run:
            console.print("\n[yellow]DRY RUN[/]: No changes were made.")
            return
        
        # Ask for confirmation
        if not yes and not Confirm.ask("\nDo you want to proceed with the migration?"):
            console.print("[yellow]Migration canceled by user.[/]")
            return
        
        # Perform actual migration
        results = migrate_actions(console, dest_client, new_actions, update_actions, dest_actions)
        
        # Display results
        console.print(f"\n[bold green]Migration completed:[/] {results['created']} created, {results['updated']} updated, {results['skipped']} skipped, {results['failed']} failed")
        
    except Exception as e:
        console.print(f"[bold red]Error during migration:[/] {str(e)}")


def filter_actions(actions: List[Dict], include_ids: Optional[str], exclude_ids: Optional[str],
                   include_types: Optional[str], exclude_types: Optional[str]) -> List[Dict]:
    """Filter actions based on the provided criteria.
    
    Args:
        actions: List of action objects
        include_ids: Comma-separated list of action IDs to include
        exclude_ids: Comma-separated list of action IDs to exclude
        include_types: Comma-separated list of action types to include
        exclude_types: Comma-separated list of action types to exclude
        
    Returns:
        List[Dict]: Filtered list of actions
    """
    filtered = [a for a in actions if a.get("type") not in IGNORE_TYPES]
    
    # Filter by IDs
    if include_ids:
        ids = [id.strip() for id in include_ids.split(",")]
        filtered = [a for a in filtered if a.get("id") in ids]
        
    if exclude_ids:
        ids = [id.strip() for id in exclude_ids.split(",")]
        filtered = [a for a in filtered if a.get("id") not in ids]
    
    # Filter by types
    if include_types:
        types = [t.strip() for t in include_types.split(",")]
        filtered = [a for a in filtered if a.get("type") in types]
        
    if exclude_types:
        types = [t.strip() for t in exclude_types.split(",")]
        filtered = [a for a in filtered if a.get("type") not in types]
    
    return filtered


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


def migrate_actions(console: Console, dest_client, new_actions: List[Dict], 
                    update_actions: List[Dict], existing_actions: List[Dict]) -> Dict:
    """Migrate actions to the destination instance.
    
    Args:
        console: Rich console for output
        dest_client: API client for the destination
        new_actions: List of new actions to create
        update_actions: List of actions to potentially update
        existing_actions: List of existing actions in the destination
        
    Returns:
        Dict: Migration results summary
    """
    results = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0
    }
    
    # Create a map of existing actions by name for quick lookup
    existing_map = {a.get("name"): a for a in existing_actions}
    
    # Process new actions
    if new_actions:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Creating new actions..."),
            console=console
        ) as progress:
            task = progress.add_task("Creating", total=len(new_actions))
            
            for action in new_actions:
                try:
                    # Create a clean payload from the source action
                    payload = create_action_payload(action)
                    
                    # Post to destination
                    dest_client.post("/v1/actions", payload)
                    results["created"] += 1
                    
                except Exception as e:
                    console.print(f"[red]Failed to create action '{action.get('name')}': {str(e)}[/]")
                    results["failed"] += 1
                
                progress.update(task, advance=1)
    
    # Process updates
    if update_actions:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Updating existing actions..."),
            console=console
        ) as progress:
            task = progress.add_task("Updating", total=len(update_actions))
            
            for action in update_actions:
                action_name = action.get("name")
                existing = existing_map.get(action_name)
                
                if not existing:
                    results["skipped"] += 1
                    progress.update(task, advance=1)
                    continue
                
                try:
                    # Check if update is needed by comparing config
                    if action.get("config") != existing.get("config"):
                        # Create update payload
                        payload = create_action_payload(action)
                        
                        # Update the action
                        dest_client.patch(f"/v1/actions/{existing.get('id')}", payload)
                        results["updated"] += 1
                    else:
                        results["skipped"] += 1
                        
                except Exception as e:
                    console.print(f"[red]Failed to update action '{action_name}': {str(e)}[/]")
                    results["failed"] += 1
                
                progress.update(task, advance=1)
    
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