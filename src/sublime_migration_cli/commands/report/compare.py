"""Compare configuration between Sublime Security instances."""
from typing import Dict, List, Optional, Set
import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.presentation.base import CommandResult
from sublime_migration_cli.presentation.factory import create_formatter

# Import utility functions
from sublime_migration_cli.utils.api import PaginatedFetcher
from sublime_migration_cli.utils.errors import (
    ApiError, handle_api_error, ErrorHandler
)


def compare_instances(
    source_api_key=None, source_region=None, 
    dest_api_key=None, dest_region=None,
    include_types=None, exclude_types=None,
    output_file=None, formatter=None
):
    """Compare configuration objects between two Sublime Security instances.
    
    Args:
        source_api_key: API key for source instance
        source_region: Region for source instance
        dest_api_key: API key for destination instance
        dest_region: Region for destination instance
        include_types: Comma-separated list of object types to include (actions, rules, etc.)
        exclude_types: Comma-separated list of object types to exclude
        output_file: File to write report to (for markdown output)
        formatter: Output formatter to use
    
    Returns:
        CommandResult: Result of the comparison
    """
    # Default to markdown formatter if none provided
    if formatter is None:
        formatter = create_formatter("markdown", output_file=output_file)
    
    try:
        # Create API clients for source and destination
        with formatter.create_progress("Connecting to source and destination instances...") as (progress, task):
            source_client = get_api_client_from_env_or_args(source_api_key, source_region)
            dest_client = get_api_client_from_env_or_args(dest_api_key, dest_region, destination=True)
            progress.update(task, advance=1)
        
        # Get instance information for report headers
        with formatter.create_progress("Fetching instance information...") as (progress, task):
            source_info = source_client.get("/v1/me")
            dest_info = dest_client.get("/v1/me")
            progress.update(task, advance=1)
        
        # Determine types to compare
        all_types = ["actions", "lists", "exclusions", "feeds", "rules"]
        
        # Filter types if specified
        compare_types = all_types
        if include_types:
            include_list = [t.strip() for t in include_types.split(",")]
            compare_types = [t for t in all_types if t in include_list]
        if exclude_types:
            exclude_list = [t.strip() for t in exclude_types.split(",")]
            compare_types = [t for t in compare_types if t not in exclude_list]
        
        # Create fetchers for source and destination
        source_fetcher = PaginatedFetcher(source_client, formatter)
        dest_fetcher = PaginatedFetcher(dest_client, formatter)
        
        # Store results for all object types
        summary = {}
        differences = {}
        
        # Fetch and compare each object type
        for obj_type in compare_types:
            with formatter.create_progress(f"Comparing {obj_type}...") as (progress, task):
                # Fetch objects from source and destination
                source_objects = fetch_objects_by_type(source_fetcher, obj_type)
                dest_objects = fetch_objects_by_type(dest_fetcher, obj_type)
                
                # Compare objects and get results
                type_summary, type_differences = compare_objects(source_objects, dest_objects, obj_type)
                
                # Store results
                summary[obj_type] = type_summary
                differences[obj_type] = type_differences
                
                progress.update(task, advance=1)
        
        # Calculate totals for summary
        total_summary = {
            "source_count": sum(s.get("source_count", 0) for s in summary.values()),
            "dest_count": sum(s.get("dest_count", 0) for s in summary.values()),
            "matching": sum(s.get("matching", 0) for s in summary.values()),
            "differences": sum(s.get("differences", 0) for s in summary.values())
        }
        summary["total"] = total_summary
        
        # Prepare source and destination info for the report
        source_report_info = {
            "org_name": source_info.get("org_name", "Unknown"),
            "email": source_info.get("email_address", "Unknown"),
            "region": source_region or "Unknown"
        }
        
        dest_report_info = {
            "org_name": dest_info.get("org_name", "Unknown"),
            "email": dest_info.get("email_address", "Unknown"),
            "region": dest_region or "Unknown"
        }
        
        # Create report data
        report_data = {
            "summary": summary,
            "differences": differences,
            "source_info": source_report_info,
            "dest_info": dest_report_info
        }
        
        # Create report title
        total_diffs = total_summary["differences"]
        report_title = "Sublime Security Configuration Comparison Report"
        if total_diffs == 0:
            report_title += " - All Configurations Match!"
        else:
            report_title += f" - {total_diffs} Differences Found"
        
        # Return the report
        return CommandResult.success(
            report_title,
            report_data,
            "Use the migrate command to resolve differences if needed."
        )
        
    except Exception as e:
        sublime_error = handle_api_error(e)
        if isinstance(sublime_error, ApiError):
            return CommandResult.error(
                f"API error during comparison: {sublime_error.message}", 
                sublime_error.details
            )
        else:
            return CommandResult.error(
                f"Error during comparison: {sublime_error.message}"
            )


def fetch_objects_by_type(fetcher: PaginatedFetcher, obj_type: str) -> List[Dict]:
    """Fetch objects from an instance based on type.
    
    Args:
        fetcher: PaginatedFetcher to use
        obj_type: Type of objects to fetch (actions, rules, etc.)
    
    Returns:
        List[Dict]: Fetched objects
    """
    endpoint = f"/v1/{obj_type}"
    params = {}
    
    # Add object type specific parameters
    if obj_type == "rules":
        # Only fetch user-created rules, not feed rules
        params["in_feed"] = "false"
    elif obj_type == "exclusions":
        # Only fetch global exclusions, not rule exclusions
        params["scope"] = "exclusion"
    
    # Use extractor functions appropriate for this endpoint
    if obj_type == "feeds":
        # Feeds API has a different response structure
        result_extractor = lambda resp: resp.get("feeds", []) if isinstance(resp, dict) else resp
        total_extractor = lambda resp: len(resp.get("feeds", [])) if isinstance(resp, dict) else len(resp)
    elif obj_type == "exclusions":
        # Exclusions API has a different response structure
        result_extractor = lambda resp: resp.get("exclusions", []) if isinstance(resp, dict) else resp
        total_extractor = lambda resp: len(resp.get("exclusions", [])) if isinstance(resp, dict) else len(resp)
    else:
        # Use default extractors for other types
        result_extractor = None
        total_extractor = None
    
    # Fetch objects
    objects = fetcher.fetch_all(
        endpoint,
        params=params,
        progress_message=None,  # Don't show nested progress
        result_extractor=result_extractor,
        total_extractor=total_extractor
    )
    
    return objects


def compare_objects(source_objects: List[Dict], dest_objects: List[Dict], obj_type: str) -> tuple:
    """Compare objects between source and destination.
    
    Args:
        source_objects: List of objects from source
        dest_objects: List of objects from destination
        obj_type: Type of objects being compared
    
    Returns:
        tuple: (summary_dict, differences_dict)
    """
    # Create lookup maps for destination objects
    dest_by_name = {obj.get("name"): obj for obj in dest_objects}
    
    # For rules, also use source_md5 for deeper comparison
    if obj_type == "rules":
        dest_by_name_md5 = {
            (obj.get("name"), obj.get("source_md5")): obj 
            for obj in dest_objects
        }
    
    # Track different categories
    matching = []
    missing_in_dest = []
    missing_in_source = []
    content_differs = []
    
    # Compare each source object to destination
    for source_obj in source_objects:
        name = source_obj.get("name")
        
        if obj_type == "rules":
            # Special handling for rules - check name and source_md5
            md5 = source_obj.get("source_md5")
            if (name, md5) in dest_by_name_md5:
                # Exact match (same content)
                matching.append(name)
            elif name in dest_by_name:
                # Name exists but content differs
                content_differs.append(name)
            else:
                # Rule doesn't exist in destination
                missing_in_dest.append(name)
        else:
            # Standard handling for other object types
            if name in dest_by_name:
                if are_objects_equivalent(source_obj, dest_by_name[name], obj_type):
                    matching.append(name)
                else:
                    content_differs.append(name)
            else:
                missing_in_dest.append(name)
    
    # Find objects in destination but not in source
    source_names = {obj.get("name") for obj in source_objects}
    for dest_obj in dest_objects:
        name = dest_obj.get("name")
        if name not in source_names:
            missing_in_source.append(name)
    
    # Prepare summary
    summary = {
        "source_count": len(source_objects),
        "dest_count": len(dest_objects),
        "matching": len(matching),
        "differences": len(missing_in_dest) + len(missing_in_source) + len(content_differs)
    }
    
    # Prepare differences details
    differences = {
        "missing_in_dest": missing_in_dest,
        "missing_in_source": missing_in_source,
        "content_differs": content_differs
    }
    
    return summary, differences


def are_objects_equivalent(obj1: Dict, obj2: Dict, obj_type: str) -> bool:
    """Check if two objects are functionally equivalent.
    
    Args:
        obj1: First object
        obj2: Second object
        obj_type: Type of objects being compared
    
    Returns:
        bool: True if objects are equivalent
    """
    # Different comparison logic based on object type

    if obj_type == "actions":
        # For actions, compare type and config
        return (
            obj1.get("type") == obj2.get("type") and
            obj1.get("config") == obj2.get("config")
        )
    
    elif obj_type == "lists":
        # For lists, compare entry_type
        return (
            obj1.get("entry_type") == obj2.get("entry_type") and
            obj1.get("name") == obj2.get("name") and
            obj1.get("description") == obj2.get("description")
        )
    
    elif obj_type == "exclusions":
        # For exclusions, compare source_md5 instead of source and scope
        return obj1.get("source_md5") == obj2.get("source_md5")
    
    elif obj_type == "feeds":
        # For feeds, compare git_url and git_branch
        return (
            obj1.get("git_url") == obj2.get("git_url") and
            obj1.get("git_branch") == obj2.get("git_branch")
        )
    
    elif obj_type == "rules":
        # For rules, compare source_md5 (should never happen as this is handled separately)
        return obj1.get("source_md5") == obj2.get("source_md5")
    
    # Default comparison
    return obj1 == obj2


@click.command()
@click.option("--source-api-key", help="API key for the source instance")
@click.option("--source-region", help="Region of the source instance")
@click.option("--dest-api-key", help="API key for the destination instance")
@click.option("--dest-region", help="Region of the destination instance")
@click.option("--include-types", help="Comma-separated list of object types to include (actions, rules, etc.)")
@click.option("--exclude-types", help="Comma-separated list of object types to exclude")
@click.option("--output-file", "-o", help="File to write report to (for markdown output)")
@click.option("--format", "output_format", type=click.Choice(["table", "json", "markdown"]), 
              default="markdown", help="Output format")
def compare(source_api_key, source_region, dest_api_key, dest_region,
            include_types, exclude_types, output_file, output_format):
    """Compare configuration between Sublime Security instances.
    
    This command analyzes and compares configuration objects between two
    Sublime Security instances, generating a report of the differences.
    
    Examples:
        # Compare all configuration types
        sublime report compare --source-api-key KEY1 --dest-api-key KEY2
        
        # Compare only specific object types
        sublime report compare --include-types actions,rules --source-api-key KEY1 --dest-api-key KEY2
        
        # Write report to a file
        sublime report compare --output-file report.md --source-api-key KEY1 --dest-api-key KEY2
    """
    # Create formatter based on output format
    formatter = create_formatter(output_format, output_file=output_file)
    
    # Execute the implementation function
    result = compare_instances(
        source_api_key, source_region, 
        dest_api_key, dest_region,
        include_types, exclude_types,
        output_file, formatter
    )
    
    # Output the result
    formatter.output_result(result)