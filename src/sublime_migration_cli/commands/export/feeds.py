"""Export feeds from Sublime Security instance."""
import os
from typing import Dict, List, Optional, Set
import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.presentation.base import CommandResult
from sublime_migration_cli.presentation.factory import create_formatter
from sublime_migration_cli.utils.api import PaginatedFetcher
from sublime_migration_cli.utils.errors import handle_api_error
from sublime_migration_cli.commands.export.utils import (
    sanitize_filename, resolve_filename_collision, write_resource_file
)


def export_feeds_impl(api_key=None, region=None, output_dir="./sublime-export/feeds",
                     output_format="yaml", formatter=None):
    """Implementation for exporting feeds.
    
    Args:
        api_key: API key for the instance
        region: Region for the instance
        output_dir: Directory to export feeds to
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
        
        # Fetch all feeds
        fetcher = PaginatedFetcher(client, formatter)
        
        with formatter.create_progress("Fetching feeds...") as (progress, task):
            all_feeds = fetcher.fetch_all(
                "/v1/feeds",
                progress_message=None,
                result_extractor=lambda resp: resp.get("feeds", []) if isinstance(resp, dict) else resp,
                total_extractor=lambda resp: len(resp.get("feeds", [])) if isinstance(resp, dict) else len(resp)
            )
            progress.update(task, advance=1)
        
        if not all_feeds:
            return {"exported": 0, "failed": 0}
        
        # Filter out system feeds
        user_feeds = [feed for feed in all_feeds if not feed.get("is_system", False)]
        
        if not user_feeds:
            return {"exported": 0, "failed": 0}
        
        # Track exported files to avoid collisions
        existing_files = set()
        exported_count = 0
        failed_count = 0
        
        extension = ".yml" if output_format == "yaml" else ".json"
        
        with formatter.create_progress("Exporting feeds...", total=len(user_feeds)) as (progress, task):
            for i, feed in enumerate(user_feeds):
                try:
                    # Convert feed to export format
                    export_data = convert_feed_to_export_format(feed)
                    
                    # Generate filename
                    base_name = sanitize_filename(feed.get("name", "unnamed-feed"))
                    filename = resolve_filename_collision(
                        base_name, existing_files, feed.get("id", ""), extension
                    )
                    existing_files.add(filename)
                    
                    # Write file
                    file_path = os.path.join(output_dir, filename)
                    write_resource_file(export_data, file_path, output_format)
                    
                    exported_count += 1
                    
                except Exception as e:
                    error = handle_api_error(e)
                    formatter.output_error(
                        f"Failed to export feed '{feed.get('name', 'unknown')}': {error.message}"
                    )
                    failed_count += 1
                
                progress.update(task, completed=i+1)
        
        return {"exported": exported_count, "failed": failed_count}
        
    except Exception as e:
        error = handle_api_error(e)
        formatter.output_error(f"Failed to export feeds: {error.message}")
        return {"exported": 0, "failed": 1}


def convert_feed_to_export_format(feed: Dict) -> Dict:
    """Convert a feed object to export format.
    
    Args:
        feed: Feed object from API
        
    Returns:
        Dict: Feed in export format
    """
    export_data = {
        "name": feed.get("name"),
        "git_url": feed.get("git_url"),
        "git_branch": feed.get("git_branch"),
        "auto_update_rules": feed.get("auto_update_rules", False),
        "auto_activate_new_rules": feed.get("auto_activate_new_rules", False)
    }
    
    # Add file filters
    if feed.get("detection_rule_file_filter"):
        export_data["detection_rule_file_filter"] = feed["detection_rule_file_filter"]
    
    if feed.get("triage_rule_file_filter"):
        export_data["triage_rule_file_filter"] = feed["triage_rule_file_filter"]
    
    if feed.get("yara_file_filter"):
        export_data["yara_file_filter"] = feed["yara_file_filter"]
    
    # Add other relevant fields, excluding system-generated ones
    excluded_fields = {
        "id", "is_system", "checked_at", "retrieved_at", "summary"
    }
    
    for key, value in feed.items():
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
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def feeds(api_key, region, output_dir, output_format, verbose):
    """Export feeds from a Sublime Security instance.
    
    This command exports all user-created feeds to local files.
    System feeds are excluded by default.
    
    Examples:
        # Export feeds to default directory
        sublime export feeds
        
        # Export to specific directory in JSON format
        sublime export feeds --output-dir ./my-export --format json
    """
    formatter = create_formatter("table")
    
    # Create the feeds subdirectory within the export directory
    feeds_dir = os.path.join(output_dir, "feeds")
    os.makedirs(feeds_dir, exist_ok=True)
    
    # Export feeds
    result = export_feeds_impl(api_key, region, feeds_dir, output_format, formatter)
    
    # Display results
    if result["exported"] > 0:
        formatter.output_success(
            f"Successfully exported {result['exported']} feeds to {feeds_dir}"
        )
    
    if result["failed"] > 0:
        formatter.output_error(f"{result['failed']} feeds failed to export")
    
    if result["exported"] == 0 and result["failed"] == 0:
        formatter.output_success("No user-created feeds found to export")