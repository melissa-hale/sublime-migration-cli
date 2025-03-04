"""Refactored commands for working with Feeds."""
from typing import Optional

import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.models.feed import Feed
from sublime_migration_cli.presentation.base import CommandResult
from sublime_migration_cli.presentation.factory import create_formatter


# Implementation functions
def fetch_all_feeds(api_key=None, region=None, formatter=None):
    """Implementation for fetching all feeds.
    
    Args:
        api_key: Optional API key
        region: Optional region code
        formatter: Output formatter to use
    """
    # Default to table formatter if none provided
    if formatter is None:
        formatter = create_formatter("table")
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Get feeds from API
        with formatter.create_progress("Fetching feeds...") as (progress, task):
            response = client.get("/v1/feeds")
            
            # The API returns a nested object with a "feeds" key
            if "feeds" in response:
                feeds_data = response["feeds"]
            else:
                feeds_data = response  # Fallback if structure changes
        
        # Convert to Feed objects
        feeds_list = [Feed.from_dict(feed) for feed in feeds_data]
        
        # Create result
        result = CommandResult.success(
            f"Successfully retrieved {len(feeds_list)} feeds",
            feeds_list
        )
        
        # Output the result
        formatter.output_result(result)
        
    except Exception as e:
        formatter.output_error(f"Failed to get feeds: {str(e)}")


def get_feed_details(feed_id, api_key=None, region=None, formatter=None):
    """Implementation for getting details of a specific feed.
    
    Args:
        feed_id: ID of the feed to fetch
        api_key: Optional API key
        region: Optional region code
        formatter: Output formatter to use
    """
    # Default to table formatter if none provided
    if formatter is None:
        formatter = create_formatter("table")
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Get feed details from API
        with formatter.create_progress(f"Fetching feed {feed_id}...") as (progress, task):
            response = client.get(f"/v1/feeds/{feed_id}")
        
        # Convert to Feed object
        feed_obj = Feed.from_dict(response)
        
        # Create result
        result = CommandResult.success(
            f"Successfully retrieved feed: {feed_obj.name}",
            feed_obj
        )
        
        # Output the result
        formatter.output_result(result)
        
    except Exception as e:
        formatter.output_error(f"Failed to get feed details: {str(e)}")


# Click command definitions
@click.group()
def feeds():
    """Commands for working with Sublime Security Feeds."""
    pass


@feeds.command()
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def all(api_key=None, region=None, output_format="table"):
    """List all feeds."""
    formatter = create_formatter(output_format)
    fetch_all_feeds(api_key, region, formatter)


@feeds.command()
@click.argument("feed_id")
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def feed(feed_id, api_key=None, region=None, output_format="table"):
    """Get details of a specific feed."""
    formatter = create_formatter(output_format)
    get_feed_details(feed_id, api_key, region, formatter)