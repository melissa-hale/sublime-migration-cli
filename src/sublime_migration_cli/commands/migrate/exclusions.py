"""Commands for migrating exclusions between Sublime Security instances."""
from typing import Dict, List, Optional
import json

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

from sublime_migration_cli.api.client import get_api_client_from_env_or_args


# Authors to exclude from migration (system and built-in exclusions)
EXCLUDED_AUTHORS = {"Sublime Security", "System"}


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
               include_ids, exclude_ids, include_system_created, dry_run, yes, output_format):
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
    console = Console()
    results = {"status": "started", "message": "Migration of Global Exclusions"}
    
    if output_format == "table":
        console.print("[bold]Migration of Global Exclusions[/]")
    
    try:
        # Create API clients for source and destination
        source_client = get_api_client_from_env_or_args(source_api_key, source_region)
        dest_client = get_api_client_from_env_or_args(dest_api_key, dest_region, destination=True)
        
        # Fetch exclusions from source (only global exclusions, not rule exclusions)
        params = {
            "include_deleted": "false",
            "scope": ["detection_exclusion", "exclusion"]  # Only global exclusions
        }
        
        if output_format == "table":
            with console.status("[blue]Fetching exclusions from source instance...[/]"):
                source_response = source_client.get("/v1/exclusions", params=params)
        else:
            source_response = source_client.get("/v1/exclusions", params=params)
        
        # Extract exclusions from response
        if "exclusions" in source_response:
            source_exclusions = source_response["exclusions"]
        else:
            source_exclusions = source_response
        
        # Apply filters
        filtered_exclusions = filter_exclusions(
            source_exclusions, include_ids, exclude_ids, include_system_created
        )
        
        if not filtered_exclusions:
            message = "No exclusions to migrate after applying filters."
            if output_format == "table":
                console.print(f"[yellow]{message}[/]")
            else:
                results["status"] = "completed"
                results["message"] = message
                click.echo(json.dumps(results, indent=2))
            return
            
        exclusions_count_message = f"Found {len(filtered_exclusions)} exclusions to migrate."
        if output_format == "table":
            console.print(f"[bold]{exclusions_count_message}[/]")
        else:
            results["count"] = len(filtered_exclusions)
            results["message"] = exclusions_count_message
        
        # Preview changes - no need to fetch destination exclusions
        # since we're only creating new ones, not updating
        if output_format == "table":
            preview_table = Table(title="Exclusions to Migrate")
            preview_table.add_column("ID", style="dim", no_wrap=True)
            preview_table.add_column("Name", style="green")
            preview_table.add_column("Scope", style="blue")
            preview_table.add_column("Active", style="cyan", justify="center")
            preview_table.add_column("Created By", style="magenta")
            
            for exclusion in filtered_exclusions:
                preview_table.add_row(
                    exclusion.get("id", ""),
                    exclusion.get("name", ""),
                    exclusion.get("scope", ""),
                    "✓" if exclusion.get("active", False) else "✗",
                    exclusion.get("created_by_user_name") or exclusion.get("created_by_org_name") or "Unknown"
                )
            
            console.print(preview_table)
        else:
            # JSON output
            results["exclusions_to_migrate"] = [
                {
                    "id": exclusion.get("id", ""),
                    "name": exclusion.get("name", ""),
                    "scope": exclusion.get("scope", ""),
                    "active": exclusion.get("active", False),
                    "created_by": exclusion.get("created_by_user_name") or exclusion.get("created_by_org_name") or "Unknown"
                }
                for exclusion in filtered_exclusions
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
        
        # Perform the migration (create only, no updates)
        migration_results = migrate_exclusions(
            console, dest_client, filtered_exclusions, output_format
        )
        
        # Display results
        results_message = f"Migration completed: {migration_results['created']} exclusions created, {migration_results['failed']} failed"
        
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


def filter_exclusions(exclusions: List[Dict], include_ids: Optional[str], 
                     exclude_ids: Optional[str], include_system_created: bool) -> List[Dict]:
    """Filter exclusions based on the provided criteria.
    
    Args:
        exclusions: List of exclusion objects
        include_ids: Comma-separated list of exclusion IDs to include
        exclude_ids: Comma-separated list of exclusion IDs to exclude
        include_system_created: Include system-created exclusions
        
    Returns:
        List[Dict]: Filtered exclusion objects
    """
    filtered = exclusions
    
    # Filter out system-created exclusions unless include_system_created is True
    if not include_system_created:
        filtered = [exc for exc in filtered if exc.get("created_by_user_name") not in EXCLUDED_AUTHORS and
                    exc.get("created_by_org_name") not in EXCLUDED_AUTHORS]
    
    # Filter by IDs
    if include_ids:
        ids = [id.strip() for id in include_ids.split(",")]
        filtered = [exc for exc in filtered if exc.get("id") in ids]
        
    if exclude_ids:
        ids = [id.strip() for id in exclude_ids.split(",")]
        filtered = [exc for exc in filtered if exc.get("id") not in ids]
    
    return filtered


def migrate_exclusions(console: Console, dest_client, exclusions: List[Dict], output_format: str) -> Dict:
    """Migrate exclusions to the destination instance (create only, no updates).
    
    Args:
        console: Rich console for output
        dest_client: API client for the destination
        exclusions: List of exclusions to create
        output_format: Output format
        
    Returns:
        Dict: Migration results
    """
    results = {
        "created": 0,
        "failed": 0,
        "details": []
    }
    
    if output_format == "table":
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Creating exclusions..."),
            console=console
        ) as progress:
            task = progress.add_task("Creating", total=len(exclusions))
            
            for exclusion in exclusions:
                process_exclusion(exclusion, dest_client, results, console)
                progress.update(task, advance=1)
    else:
        # JSON output mode - no progress indicators
        for exclusion in exclusions:
            process_exclusion(exclusion, dest_client, results, console)
    
    return results


def process_exclusion(exclusion: Dict, dest_client, results: Dict, console: Console):
    """Process an exclusion for migration.
    
    Args:
        exclusion: Source exclusion object
        dest_client: API client for the destination
        results: Results dictionary to update
        console: Rich console for output
    """
    exclusion_name = exclusion.get("name", "")
    try:
        # Create exclusion payload for API request
        payload = create_exclusion_payload(exclusion)
        
        # Post to destination
        dest_client.post("/v1/exclusions", payload)
        results["created"] += 1
        results["details"].append({
            "name": exclusion_name,
            "status": "created"
        })
        
    except Exception as e:
        results["failed"] += 1
        results["details"].append({
            "name": exclusion_name,
            "status": "failed",
            "reason": str(e)
        })
        console.print(f"[red]Failed to create exclusion '{exclusion_name}': {str(e)}[/]")


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