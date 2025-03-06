"""Refactored commands for migrating feeds using utility functions."""
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


# Implementation functions
def migrate_feeds_between_instances(
    source_api_key=None, source_region=None, 
    dest_api_key=None, dest_region=None,
    include_ids=None, exclude_ids=None, 
    include_system=False,
    dry_run=False, formatter=None
):
    """Implementation for migrating feeds between instances.
    
    Args:
        source_api_key: API key for source instance
        source_region: Region for source instance
        dest_api_key: API key for destination instance
        dest_region: Region for destination instance
        include_ids: Comma-separated list of feed IDs to include
        exclude_ids: Comma-separated list of feed IDs to exclude
        include_system: Include system feeds
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
        
        # Use PaginatedFetcher to fetch feeds from source
        source_fetcher = PaginatedFetcher(source_client, formatter)
        source_feeds = source_fetcher.fetch_all(
            "/v1/feeds",
            progress_message="Fetching feeds from source...",
            # Custom extractors for the feeds endpoint
            result_extractor=lambda resp: resp.get("feeds", []) if isinstance(resp, dict) else resp,
            total_extractor=lambda resp: len(resp.get("feeds", [])) if isinstance(resp, dict) else len(resp)
        )
        
        # Apply filters to feeds
        # First, filter by system vs. user feeds
        if not include_system:
            filtered_feeds = [feed for feed in source_feeds if not feed.get("is_system", False)]
        else:
            filtered_feeds = source_feeds
        
        # Then apply ID filters
        filtered_feeds = filter_by_ids(filtered_feeds, include_ids, exclude_ids)
        
        if not filtered_feeds:
            return CommandResult.error("No feeds to migrate after applying filters.")
            
        # Use PaginatedFetcher to fetch feeds from destination
        dest_fetcher = PaginatedFetcher(dest_client, formatter)
        dest_feeds = dest_fetcher.fetch_all(
            "/v1/feeds",
            progress_message="Fetching feeds from destination...",
            # Custom extractors for the feeds endpoint
            result_extractor=lambda resp: resp.get("feeds", []) if isinstance(resp, dict) else resp,
            total_extractor=lambda resp: len(resp.get("feeds", [])) if isinstance(resp, dict) else len(resp)
        )
        
        # Compare and categorize feeds
        new_feeds, update_feeds = categorize_feeds(filtered_feeds, dest_feeds)
        
        # If no feeds to migrate, return early
        if not new_feeds and not update_feeds:
            return CommandResult.success("All selected feeds already exist in the destination instance.")
            
        # Prepare response data
        migration_data = {
            "new_feeds": [
                {
                    "id": feed.get("id", ""),
                    "name": feed.get("name", ""),
                    "git_url": feed.get("git_url", ""),
                    "git_branch": feed.get("git_branch", ""),
                    "is_system": feed.get("is_system", False),
                    "status": "New"
                }
                for feed in new_feeds
            ],
            "update_feeds": [
                {
                    "id": feed.get("id", ""),
                    "name": feed.get("name", ""),
                    "git_url": feed.get("git_url", ""),
                    "git_branch": feed.get("git_branch", ""),
                    "is_system": feed.get("is_system", False),
                    "status": "Update (if different)"
                }
                for feed in update_feeds
            ]
        }
        
        # Add summary stats
        migration_data["summary"] = {
            "new_count": len(new_feeds),
            "update_count": len(update_feeds),
            "total_count": len(new_feeds) + len(update_feeds)
        }
        
        # If dry run, return preview data
        if dry_run:
            return CommandResult.success(
                "DRY RUN: Preview of feeds to migrate",
                migration_data,
                "No changes were made to the destination instance."
            )
        
        # Show preview before confirmation in interactive mode
        formatter.output_result(CommandResult.success(
            "Feeds that will be migrated:",
            migration_data,
            "Please confirm to proceed with migration."
        ))
        
        # Confirm migration if interactive
        if not formatter.prompt_confirmation("\nDo you want to proceed with the migration?"):
            return CommandResult.success("Migration canceled by user.")
        
        # Perform the migration
        results = perform_migration(formatter, dest_client, new_feeds, update_feeds, dest_feeds)
        
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


def perform_migration(formatter, dest_client, new_feeds: List[Dict], 
                     update_feeds: List[Dict], existing_feeds: List[Dict]) -> Dict:
    """Perform the actual migration of feeds to the destination.
    
    Args:
        formatter: Output formatter
        dest_client: API client for destination
        new_feeds: List of new feeds to create
        update_feeds: List of feeds to update
        existing_feeds: List of existing feeds in destination
        
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
    
    # Create a map of existing feeds by name for quick lookup
    existing_map = {feed.get("name"): feed for feed in existing_feeds}
    
    # Process new feeds
    if new_feeds:
        with formatter.create_progress("Creating new feeds...", total=len(new_feeds)) as (progress, task):
            for i, feed in enumerate(new_feeds):
                process_new_feed(feed, dest_client, results)
                progress.update(task, completed=i+1)
    
    # Process updates
    if update_feeds:
        with formatter.create_progress("Updating existing feeds...", total=len(update_feeds)) as (progress, task):
            for i, feed in enumerate(update_feeds):
                process_update_feed(feed, dest_client, existing_map, results)
                progress.update(task, completed=i+1)
    
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
            "type": "feed",
            "status": "created"
        })
        
    except ApiError as e:
        results["failed"] += 1
        results["details"].append({
            "name": feed_name,
            "type": "feed",
            "status": "failed",
            "reason": e.message
        })
    except Exception as e:
        sublime_error = handle_api_error(e)
        results["failed"] += 1
        results["details"].append({
            "name": feed_name,
            "type": "feed",
            "status": "failed",
            "reason": str(sublime_error.message)
        })


def process_update_feed(feed: Dict, dest_client, existing_map: Dict[str, Dict], results: Dict):
    """Process a feed update for migration."""
    feed_name = feed.get("name", "")
    existing = existing_map.get(feed_name)
    
    if not existing:
        results["skipped"] += 1
        results["details"].append({
            "name": feed_name,
            "type": "feed",
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
                "type": "feed",
                "status": "updated",
                "reason": "Feed configuration changed"
            })
        else:
            results["skipped"] += 1
            results["details"].append({
                "name": feed_name,
                "type": "feed",
                "status": "skipped",
                "reason": "No changes needed"
            })
                
    except ApiError as e:
        results["failed"] += 1
        results["details"].append({
            "name": feed_name,
            "type": "feed",
            "status": "failed",
            "reason": e.message
        })
    except Exception as e:
        sublime_error = handle_api_error(e)
        results["failed"] += 1
        results["details"].append({
            "name": feed_name,
            "type": "feed",
            "status": "failed",
            "reason": str(sublime_error.message)
        })


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


# Click command definition
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
    # Create formatter based on output format
    formatter = create_formatter(output_format)
    
    # If --yes flag is provided, modify the formatter to auto-confirm
    if yes:
        original_prompt = formatter.prompt_confirmation
        formatter.prompt_confirmation = lambda _: True
    
    # Execute the implementation function
    result = migrate_feeds_between_instances(
        source_api_key, source_region, 
        dest_api_key, dest_region,
        include_ids, exclude_ids, 
        include_system,
        dry_run, formatter
    )
    
    # Reset the formatter if it was modified
    if yes and hasattr(formatter, 'original_prompt'):
        formatter.prompt_confirmation = original_prompt
    
    # Output the result
    formatter.output_result(result)