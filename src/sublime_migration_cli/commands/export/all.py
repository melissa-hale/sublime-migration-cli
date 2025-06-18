"""Export all configuration objects from a Sublime Security instance."""
import os
import datetime
from typing import Dict, List, Optional
import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.presentation.base import CommandResult
from sublime_migration_cli.presentation.factory import create_formatter

# Import export functions from individual modules
from sublime_migration_cli.commands.export.actions import export_actions_impl
from sublime_migration_cli.commands.export.rules import export_rules_impl
from sublime_migration_cli.commands.export.lists import export_lists_impl
from sublime_migration_cli.commands.export.exclusions import export_exclusions_impl
from sublime_migration_cli.commands.export.feeds import export_feeds_impl
from sublime_migration_cli.commands.export.organization import export_organization_impl
from sublime_migration_cli.commands.export.utils import (
    create_directory_structure, generate_export_summary
)
from sublime_migration_cli.utils.errors import handle_api_error


def export_all_objects_impl(
    api_key=None, region=None, output_dir="./sublime-export",
    output_format="yaml", include_types=None, exclude_types=None,
    include_sensitive=False, formatter=None
):
    """Implementation for exporting all objects from an instance.
    
    Args:
        api_key: API key for the instance
        region: Region for the instance
        output_dir: Directory to export to
        output_format: Output format (yaml or json)
        include_types: Comma-separated list of types to include
        exclude_types: Comma-separated list of types to exclude
        include_sensitive: Include sensitive organization settings
        formatter: Output formatter
        
    Returns:
        CommandResult: Result of the export operation
    """
    if formatter is None:
        formatter = create_formatter("table")
    
    try:
        # Create API client
        with formatter.create_progress("Connecting to Sublime Security instance...") as (progress, task):
            client = get_api_client_from_env_or_args(api_key, region)
            
            # Get instance information
            source_info = client.get("/v1/me")
            source_info["region"] = region or "Unknown"
            
            progress.update(task, advance=1)
        
        # Determine types to export
        all_types = ["actions", "rules", "lists", "exclusions", "feeds", "organization"]
        export_types = all_types
        
        if include_types:
            include_list = [t.strip() for t in include_types.split(",")]
            export_types = [t for t in all_types if t in include_list]
        
        if exclude_types:
            exclude_list = [t.strip() for t in exclude_types.split(",")]
            export_types = [t for t in export_types if t not in exclude_list]
        
        if not export_types:
            return CommandResult.error("No resource types selected for export.")
        
        # Create directory structure
        formatter.output_success(f"Creating export directory structure in: {output_dir}")
        directories = create_directory_structure(output_dir)
        
        # Track export results
        export_results = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        }
        
        # Export each type
        total_exported = 0
        total_failed = 0
        
        formatter.output_success(f"Exporting {len(export_types)} resource types...")
        
        for i, resource_type in enumerate(export_types, 1):
            formatter.output_success(f"[{i}/{len(export_types)}] Exporting {resource_type}...")
            
            try:
                if resource_type == "actions":
                    result = export_actions_impl(
                        api_key, region, directories["actions"], 
                        output_format, formatter
                    )
                elif resource_type == "rules":
                    result = export_rules_impl(
                        api_key, region, 
                        directories["rules_detection"], directories["rules_triage"],
                        output_format, formatter
                    )
                elif resource_type == "lists":
                    result = export_lists_impl(
                        api_key, region,
                        directories["lists_string"], directories["lists_user_group"],
                        output_format, formatter
                    )
                elif resource_type == "exclusions":
                    result = export_exclusions_impl(
                        api_key, region,
                        directories["exclusions_global"], directories["exclusions_detection"],
                        output_format, formatter
                    )
                elif resource_type == "feeds":
                    result = export_feeds_impl(
                        api_key, region, directories["feeds"],
                        output_format, formatter
                    )
                elif resource_type == "organization":
                    result = export_organization_impl(
                        api_key, region, output_dir,  # Organization goes in root dir
                        output_format, include_sensitive, formatter
                    )
                else:
                    continue
                
                export_results[resource_type] = result
                total_exported += result.get("exported", 0)
                total_failed += result.get("failed", 0)
                
                formatter.output_success(
                    f"✓ {resource_type}: {result.get('exported', 0)} exported, "
                    f"{result.get('failed', 0)} failed"
                )
                
            except Exception as e:
                error = handle_api_error(e)
                formatter.output_error(f"Failed to export {resource_type}: {error.message}")
                export_results[resource_type] = {"exported": 0, "failed": 1}
                total_failed += 1
        
        # Generate summary README
        readme_path = generate_export_summary(export_results, output_dir, source_info)
        
        # Create final result
        summary_data = {
            "total_exported": total_exported,
            "total_failed": total_failed,
            "export_types": export_types,
            "output_directory": output_dir,
            "results_by_type": export_results,
            "readme_path": readme_path
        }
        
        if total_failed == 0:
            return CommandResult.success(
                f"Export completed successfully! {total_exported} objects exported to {output_dir}",
                summary_data,
                f"See {readme_path} for detailed summary."
            )
        else:
            return CommandResult.success(
                f"Export completed with {total_failed} failures. {total_exported} objects exported to {output_dir}",
                summary_data,
                f"See {readme_path} for detailed summary."
            )
            
    except Exception as e:
        error = handle_api_error(e)
        return CommandResult.error(f"Export failed: {error.message}", error.details)


@click.command()
@click.option("--api-key", help="API key for authentication")
@click.option("--region", help="Region to connect to")
@click.option("--output-dir", "-o", default="./sublime-export", 
              help="Output directory (default: ./sublime-export)")
@click.option("--format", "output_format", type=click.Choice(["yaml", "json"]), 
              default="yaml", help="Output format (default: yaml)")
@click.option("--include-types", help="Comma-separated list of types to include (actions,rules,lists,exclusions,feeds,organization)")
@click.option("--exclude-types", help="Comma-separated list of types to exclude")
@click.option("--include-sensitive", is_flag=True, help="Include sensitive organization settings")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def all_objects(api_key, region, output_dir, output_format, include_types, 
                exclude_types, include_sensitive, verbose):
    """Export all configuration objects from a Sublime Security instance.
    
    This command exports all user-created configuration objects (actions, rules, 
    lists, exclusions, feeds, organization settings) to local files for version control and backup.
    
    Examples:
        # Export everything to default directory
        sublime export all
        
        # Export to specific directory in JSON format
        sublime export all --output-dir ./config --format json
        
        # Export only rules and actions
        sublime export all --include-types rules,actions
        
        # Export everything except organization settings
        sublime export all --exclude-types organization
        
        # Include sensitive organization data
        sublime export all --include-sensitive
    """
    formatter = create_formatter("table" if verbose else "table")
    
    result = export_all_objects_impl(
        api_key, region, output_dir, output_format,
        include_types, exclude_types, include_sensitive, formatter
    )
    
    formatter.output_result(result)