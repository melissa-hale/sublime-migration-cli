"""Refactored commands for working with Rules using utility functions."""
from typing import Dict, List, Optional, Any
import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.models.rule import Rule
from sublime_migration_cli.presentation.base import CommandResult
from sublime_migration_cli.presentation.factory import create_formatter

# Import our utility functions
from sublime_migration_cli.utils.api import PaginatedFetcher
from sublime_migration_cli.utils.filtering import filter_by_ids, create_boolean_filter
from sublime_migration_cli.utils.errors import (
    ApiError, ResourceNotFoundError, handle_api_error, ErrorHandler
)


# Implementation functions
def fetch_all_rules(api_key=None, region=None, rule_type=None, active=False, feed=None, 
                    in_feed=None, limit=100, show_exclusions=False, formatter=None):
    """Implementation for fetching all rules with pagination and filtering options.
    
    Args:
        api_key: Optional API key
        region: Optional region code
        rule_type: Filter by rule type (detection or triage)
        active: Show only active rules
        feed: Show only rules from a specific feed (provide feed ID)
        in_feed: Show rules that are in feeds or not in feeds
        limit: Number of rules to fetch per page
        show_exclusions: Show exclusion information (requires additional API calls)
        formatter: Output formatter to use
    """
    # Default to table formatter if none provided
    if formatter is None:
        formatter = create_formatter("table")
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Build query parameters for filtering
        params = {}
        
        if rule_type:
            params["type"] = rule_type
            
        if feed:
            params["feed"] = feed
        
        if in_feed is not None:
            params["in_feed"] = "true" if in_feed else "false"
            
        # Use our PaginatedFetcher to handle pagination
        fetcher = PaginatedFetcher(client, formatter)
        rules_data = fetcher.fetch_all(
            "/v1/rules",
            params=params,
            progress_message="Fetching rules...",
            page_size=limit
        )
        
        # Apply active filter if requested (client-side filtering)
        if active:
            # Use our filter utility
            active_filter = create_boolean_filter("active", True)
            rules_data = active_filter(rules_data)
            
        # If showing exclusions, fetch detailed info for each rule
        if show_exclusions and rules_data:
            detailed_rules = []
            
            with formatter.create_progress("Fetching rule details for exclusions...", 
                                         total=len(rules_data)) as (progress, task):
                
                for i, rule_item in enumerate(rules_data):
                    try:
                        rule_id = rule_item["id"]
                        details = client.get(f"/v1/rules/{rule_id}")
                        detailed_rules.append(details)
                    except ApiError as e:
                        # If fetching details fails, use original item
                        detailed_rules.append(rule_item)
                        formatter.output_error(
                            f"Warning: Failed to fetch details for rule '{rule_item.get('name')}'", 
                            str(e)
                        )
                    
                    # Update progress
                    if progress and task:
                        progress.update(task, completed=i+1)
                
                # Replace rules_data with detailed_rules
                rules_data = detailed_rules
        
        # Convert to Rule objects
        rules_list = [Rule.from_dict(rule) for rule in rules_data]
        
        # Create result
        result = CommandResult.success(
            f"Successfully retrieved {len(rules_list)} rules",
            rules_list
        )
        
        # Add filter notes if filters were applied
        filters = []
        if rule_type:
            filters.append(f"type={rule_type}")
        if active:
            filters.append("active=true")
        if feed:
            filters.append(f"feed={feed}")
        if in_feed is not None:
            filters.append(f"in_feed={'true' if in_feed else 'false'}")
        
        if filters:
            result.notes = f"Filtered by {', '.join(filters)}"
                
        if show_exclusions:
            exclusion_note = "Including exclusion information"
            if result.notes:
                result.notes += f"\n{exclusion_note}"
            else:
                result.notes = exclusion_note
        
        # Output the result
        formatter.output_result(result)
        
    except Exception as e:
        # Use our error handling utilities
        sublime_error = handle_api_error(e)
        error_details = ErrorHandler.format_error_for_display(sublime_error)
        formatter.output_error(f"Failed to get rules: {sublime_error.message}", error_details)


def get_rule_details(rule_id, api_key=None, region=None, formatter=None):
    """Implementation for getting details of a specific rule.
    
    Args:
        rule_id: ID of the rule to fetch
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
        
        # Get rule details from API
        with formatter.create_progress(f"Fetching rule {rule_id}...") as (progress, task):
            response = client.get(f"/v1/rules/{rule_id}")
            if progress and task:
                progress.update(task, advance=1)
        
        # Convert to Rule object
        rule_obj = Rule.from_dict(response)
        
        # Create result
        result = CommandResult.success(
            f"Successfully retrieved rule: {rule_obj.name}",
            rule_obj
        )
        
        # Output the result
        formatter.output_result(result)
        
    except ResourceNotFoundError as e:
        formatter.output_error(f"Rule not found: {e.resource_id}", e.details)
    except ApiError as e:
        formatter.output_error(f"Failed to get rule details: {e.message}", e.details)
    except Exception as e:
        sublime_error = handle_api_error(e)
        formatter.output_error(f"Error: {sublime_error.message}")


# Click command definitions
@click.group()
def rules():
    """Commands for working with Sublime Security Rules."""
    pass


@rules.command()
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--type", "rule_type", type=click.Choice(["detection", "triage"]),
              help="Filter by rule type (detection or triage)")
@click.option("--active", is_flag=True, help="Show only active rules")
@click.option("--feed", help="Filter by feed ID (returns rules from this feed)")
@click.option("--in-feed/--not-in-feed", default=None, 
              help="Filter to show only rules in feeds or not in feeds")
@click.option("--limit", type=int, default=100, 
              help="Number of rules to fetch per page (adjust based on API limitations)")
@click.option("--show-exclusions", is_flag=True, 
              help="Show exclusion information (slower, requires additional API calls)")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def all(api_key=None, region=None, rule_type=None, active=False, feed=None, 
         in_feed=None, limit=100, show_exclusions=False, output_format="table"):
    """List all rules with pagination and filtering options.
    
    Filters available:
      --type: Show only detection or triage rules
      --active: Show only active rules
      --feed: Show only rules from a specific feed (provide feed ID)
      --in-feed/--not-in-feed: Show rules that are in feeds or not in feeds
    """
    formatter = create_formatter(output_format)
    fetch_all_rules(
        api_key, region, rule_type, active, feed, in_feed, 
        limit, show_exclusions, formatter
    )


@rules.command()
@click.argument("rule_id")
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def rule(rule_id, api_key=None, region=None, output_format="table"):
    """Get details of a specific rule."""
    formatter = create_formatter(output_format)
    get_rule_details(rule_id, api_key, region, formatter)