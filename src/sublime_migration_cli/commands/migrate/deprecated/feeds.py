"""Commands for migrating feeds between Sublime Security instances."""
from typing import Dict, List, Optional
import json

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

from sublime_migration_cli.api.client import get_api_client_from_env_or_args


@click.command()
@click.option("--source-api-key", help="API key for the source instance")
@click.option("--source-region", help="Region of the source instance")
@click.option("--dest-api-key", help="API key for the destination instance")
@click.option("--dest-region", help="Region of the destination instance")
@click.option("--include-ids", help="Comma-separated list of feed IDs to include")
@click.option("--exclude-ids", help="Comma-separated list of feed IDs to exclude")
@click.option("--include-system", is_flag=True, help="Include system feeds (by default, only user-created feeds are migrated)")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def feeds(source_api_key, source_region, dest_api_key, dest_region,
          include_ids, exclude_ids, include_system, dry_run, yes, output_format):
    """Migrate feeds between Sublime Security instances.
    
    This command copies feed configurations from the source instance to the destination instance.
    By default, only user-created feeds are migrated (not those marked as system feeds).
    
    Examples:
        # Migrate all user-created feeds
        sublime migrate feeds --source-api-key KEY1 --dest-api-key KEY2
        
        # Migrate specific feeds by ID
        sublime migrate feeds --include-ids id1,id2 --source-api-key KEY1 --dest-api-key KEY2
        
        # Preview migration without making changes
        sublime migrate feeds --dry-run --source-api-key KEY1 --dest-api-key KEY2
        
        # Include system feeds in migration
        sublime migrate feeds --include-system --source-api-key KEY1 --dest-api-key KEY2
    """
    console = Console()
    results = {"status": "started", "message": "Migration of Feeds"}
    
    if output_format == "table":
        console.print("[bold]Migration of Feeds[/]")
    
    try:
        # Create API clients for source and destination
        source_client = get_api_client_from_env_or_args(source_api_key, source_region)
        dest_client = get_api_client_from_env_or_args(dest_api_key, dest_region, destination=True)
        
        # Fetch feeds from source
        if output_format == "table":
            with console.status("[blue]Fetching feeds from source instance...[/]"):
                source_response = source_client.get("/v1/feeds")
        else:
            source_response = source_client.get("/v1/feeds")
        
        # Extract feeds from response
        if "feeds" in source_response:
            source_feeds = source_response["feeds"]
        else:
            source_feeds = source_response
        
        # Apply filters
        filtered_feeds = filter_feeds(source_feeds, include_ids, exclude_ids, include_system)
        
        if not filtered_feeds:
            message = "No feeds to migrate after applying filters."
            if output_format == "table":
                console.print(f"[yellow]{message}[/]")
            else:
                results["status"] = "completed"
                results["message"] = message
                click.echo(json.dumps(results, indent=2))
            return
            
        feeds_count_message = f"Found {len(filtered_feeds)} feeds to migrate."
        if output_format == "table":
            console.print(f"[bold]{feeds_count_message}[/]")
        else:
            results["count"] = len(filtered_feeds)
            results["message"] = feeds_count_message
        
        # Fetch feeds from destination for comparison
        if output_format == "table":
            with console.status("[blue]Fetching feeds from destination instance...[/]"):
                dest_response = dest_client.get("/v1/feeds")
        else:
            dest_response = dest_client.get("/v1/feeds")
        
        # Extract destination feeds
        if "feeds" in dest_response:
            dest_feeds = dest_response["feeds"]
        else:
            dest_feeds = dest_response
        
        # Compare and categorize feeds
        new_feeds, update_feeds = categorize_feeds(filtered_feeds, dest_feeds)
        
        # Preview changes
        if not new_feeds and not update_feeds:
            message = "All selected feeds already exist in the destination instance."
            if output_format == "table":
                console.print(f"[green]{message}[/]")
            else:
                results["status"] = "completed"
                results["message"] = message
                click.echo(json.dumps(results, indent=2))
            return
            
        preview_message = f"\nPreparing to migrate {len(new_feeds)} new feeds and potentially update {len(update_feeds)} existing feeds."
        if output_format == "table":
            console.print(f"[bold]{preview_message}[/]")
        
            # Display preview table
            preview_table = Table(title="Feeds to Migrate")
            preview_table.add_column("ID", style="dim", no_wrap=True)
            preview_table.add_column("Name", style="green")
            preview_table.add_column("Git URL", style="blue")
            preview_table.add_column("Branch", style="cyan")
            preview_table.add_column("Status", style="magenta")
            
            for feed in new_feeds:
                preview_table.add_row(
                    feed.get("id", ""),
                    feed.get("name", ""),
                    feed.get("git_url", ""),
                    feed.get("git_branch", ""),
                    "New"
                )
            
            for feed in update_feeds:
                preview_table.add_row(
                    feed.get("id", ""),
                    feed.get("name", ""),
                    feed.get("git_url", ""),
                    feed.get("git_branch", ""),
                    "Update (if different)"
                )
            
            console.print(preview_table)
        else:
            # JSON output
            results["new_feeds"] = len(new_feeds)
            results["update_feeds"] = len(update_feeds)
            results["feeds_to_migrate"] = [
                {
                    "id": feed.get("id", ""),
                    "name": feed.get("name", ""),
                    "git_url": feed.get("git_url", ""),
                    "git_branch": feed.get("git_branch", ""),
                    "status": "New"
                }
                for feed in new_feeds
            ] + [
                {
                    "id": feed.get("id", ""),
                    "name": feed.get("name", ""),
                    "git_url": feed.get("git_url", ""),
                    "git_branch": feed.get("git_branch", ""),
                    "status": "Update (if different)"
                }
                for feed in update_feeds
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
        migration_results = migrate_feeds(
            console, dest_client, new_feeds, update_feeds, dest_feeds, output_format
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


def filter_feeds(feeds: List[Dict], include_ids: Optional[str], 
                exclude_ids: Optional[str], include_system: bool) -> List[Dict]:
    """Filter feeds based on the provided criteria.
    
    Args:
        feeds: List of feed objects
        include_ids: Comma-separated list of feed IDs to include
        exclude_ids: Comma-separated list of feed IDs to exclude
        include_system: Include system feeds
        
    Returns:
        List[Dict]: Filtered feed objects
    """
    filtered = feeds
    
    # Filter out system feeds unless include_system is True
    if not include_system:
        filtered = [feed for feed in filtered if not feed.get("is_system", False)]
    
    # Filter by IDs
    if include_ids:
        ids = [id.strip() for id in include_ids.split(",")]
        filtered = [feed for feed in filtered if feed.get("id") in ids]
        
    if exclude_ids:
        ids = [id.strip() for id in exclude_ids.split(",")]
        filtered = [feed for feed in filtered if feed.get("id") not in ids]
    
    return filtered


def categorize_feeds(source_feeds: List[Dict], dest_feeds: List[Dict]) -> tuple:
    """Categorize feeds as new or updates based on name matching.
    
    Args:
        source_feeds: List of source feed objects
        dest_feeds: List of destination feed objects
        
    Returns:
        tuple: (new_feeds, update_feeds)
    """
    # Create lookup dict for destination feeds by name
    dest_feed_map = {feed.get("name"): feed for feed in dest_feeds}
    
    new_feeds = []
    update_feeds = []
    
    for feed in source_feeds:
        feed_name = feed.get("name")
        if feed_name in dest_feed_map:
            update_feeds.append(feed)
        else:
            new_feeds.append(feed)
    
    return new_feeds, update_feeds


def migrate_feeds(console: Console, dest_client, new_feeds: List[Dict], 
                 update_feeds: List[Dict], existing_feeds: List[Dict],
                 output_format: str) -> Dict:
    """Migrate feeds to the destination instance.
    
    Args:
        console: Rich console for output
        dest_client: API client for the destination
        new_feeds: List of new feeds to create
        update_feeds: List of feeds to potentially update
        existing_feeds: List of existing feeds in the destination
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
    
    # Create a map of existing feeds by name for quick lookup
    existing_map = {feed.get("name"): feed for feed in existing_feeds}
    
    # Process new feeds
    if new_feeds:
        if output_format == "table":
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Creating new feeds..."),
                console=console
            ) as progress:
                task = progress.add_task("Creating", total=len(new_feeds))
                
                for feed in new_feeds:
                    process_new_feed(feed, dest_client, results)
                    progress.update(task, advance=1)
        else:
            # JSON output mode - no progress indicators
            for feed in new_feeds:
                process_new_feed(feed, dest_client, results)
    
    # Process updates
    if update_feeds:
        if output_format == "table":
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Updating existing feeds..."),
                console=console
            ) as progress:
                task = progress.add_task("Updating", total=len(update_feeds))
                
                for feed in update_feeds:
                    process_update_feed(feed, dest_client, existing_map, results, console, output_format)
                    progress.update(task, advance=1)
        else:
            # JSON output mode - no progress indicators
            for feed in update_feeds:
                process_update_feed(feed, dest_client, existing_map, results, console, output_format)
    
    return results


def process_new_feed(feed: Dict, dest_client, results: Dict):
    """Process a new feed for migration."""
    feed_name = feed.get("name", "")
    try:
        # Create feed payload for API request
        payload = create_feed_payload(feed)
        
        # Post to destination
        dest_client.post("/v1/feeds", payload)
        results["created"] += 1
        results["details"].append({
            "name": feed_name,
            "status": "created"
        })
        
    except Exception as e:
        results["failed"] += 1
        results["details"].append({
            "name": feed_name,
            "status": "failed",
            "reason": str(e)
        })


def process_update_feed(feed: Dict, dest_client, existing_map: Dict[str, Dict], 
                      results: Dict, console: Console, output_format: str):
    """Process a feed update for migration."""
    feed_name = feed.get("name", "")
    existing = existing_map.get(feed_name)
    
    if not existing:
        results["skipped"] += 1
        results["details"].append({
            "name": feed_name,
            "status": "skipped",
            "reason": "Feed not found in destination"
        })
        return
    
    try:
        # Check if update is needed by comparing key fields
        if (feed.get("git_url") != existing.get("git_url") or 
            feed.get("git_branch") != existing.get("git_branch") or
            feed.get("detection_rule_file_filter") != existing.get("detection_rule_file_filter") or
            feed.get("triage_rule_file_filter") != existing.get("triage_rule_file_filter") or
            feed.get("yara_file_filter") != existing.get("yara_file_filter") or
            feed.get("auto_update_rules") != existing.get("auto_update_rules") or
            feed.get("auto_activate_new_rules") != existing.get("auto_activate_new_rules")):
            
            # Create update payload
            payload = create_feed_payload(feed)
            
            # Update the feed
            dest_client.patch(f"/v1/feeds/{existing.get('id')}", payload)
            results["updated"] += 1
            results["details"].append({
                "name": feed_name,
                "status": "updated",
                "reason": "Feed configuration changed"
            })
        else:
            results["skipped"] += 1
            results["details"].append({
                "name": feed_name,
                "status": "skipped",
                "reason": "No changes needed"
            })
                
    except Exception as e:
        error_message = f"Failed to update feed '{feed_name}': {str(e)}"
        results["failed"] += 1
        results["details"].append({
            "name": feed_name,
            "status": "failed",
            "reason": str(e)
        })
        
        if output_format == "table":
            console.print(f"[red]{error_message}[/]")


def create_feed_payload(feed: Dict) -> Dict:
    """Create a clean feed payload for API requests.
    
    Args:
        feed: Source feed object
        
    Returns:
        Dict: Cleaned feed payload
    """
    # Extract only the fields needed for creation/update
    payload = {
        "name": feed.get("name"),
        "git_url": feed.get("git_url"),
        "git_branch": feed.get("git_branch"),
        "detection_rule_file_filter": feed.get("detection_rule_file_filter", ""),
        "triage_rule_file_filter": feed.get("triage_rule_file_filter", ""),
        "yara_file_filter": feed.get("yara_file_filter", ""),
        "auto_update_rules": feed.get("auto_update_rules", False),
        "auto_activate_new_rules": feed.get("auto_activate_new_rules", False)
    }
    
    return payload