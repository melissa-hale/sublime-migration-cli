"""Export organization settings from Sublime Security instance."""
import os
from typing import Dict, Optional
import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.models.organization import OrganizationSettings
from sublime_migration_cli.presentation.base import CommandResult
from sublime_migration_cli.presentation.factory import create_formatter
from sublime_migration_cli.utils.errors import handle_api_error
from sublime_migration_cli.commands.export.utils import write_resource_file


def export_organization_impl(api_key=None, region=None, output_dir="./sublime-export",
                            output_format="yaml", include_sensitive=False, formatter=None):
    """Implementation for exporting organization settings.
    
    Args:
        api_key: API key for the instance
        region: Region for the instance
        output_dir: Directory to export to
        output_format: Output format (yaml or json)
        include_sensitive: Include sensitive fields like client secrets
        formatter: Output formatter
        
    Returns:
        Dict: Export results with counts
    """
    if formatter is None:
        formatter = create_formatter("table")
    
    try:
        # Create API client
        client = get_api_client_from_env_or_args(api_key, region)
        
        with formatter.create_progress("Fetching organization settings...") as (progress, task):
            # Fetch organization settings
            org_settings_data = client.get(f"/v1/organizations/mine/settings")
            progress.update(task, advance=1)
        
        # Convert to model
        org_settings = OrganizationSettings.from_dict(org_settings_data)
        
        # Convert to export format
        export_data = org_settings.to_dict(include_sensitive=include_sensitive)
        
        # Write organization settings file
        extension = ".yml" if output_format == "yaml" else ".json"
        file_path = os.path.join(output_dir, f"organization{extension}")
        write_resource_file(export_data, file_path, output_format)
        
        return {"exported": 1, "failed": 0}
        
    except Exception as e:
        error = handle_api_error(e)
        formatter.output_error(f"Failed to export organization settings: {error.message}")
        return {"exported": 0, "failed": 1}


@click.command()
@click.option("--api-key", help="API key for authentication")
@click.option("--region", help="Region to connect to")
@click.option("--output-dir", "-o", default="./sublime-export", 
              help="Output directory (default: ./sublime-export)")
@click.option("--format", "output_format", type=click.Choice(["yaml", "json"]), 
              default="yaml", help="Output format (default: yaml)")
@click.option("--include-sensitive", is_flag=True, 
              help="Include sensitive fields like client secrets and S3 configurations")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def organization(api_key, region, output_dir, output_format, include_sensitive, verbose):
    """Export organization settings from a Sublime Security instance.
    
    This command exports organization-wide configuration settings.
    Sensitive fields like client secrets are excluded by default.
    
    Examples:
        # Export organization settings
        sublime export organization
        
        # Include sensitive fields
        sublime export organization --include-sensitive
    """
    formatter = create_formatter("table")
    
    # Create output directory if needed
    os.makedirs(output_dir, exist_ok=True)
    
    # Export organization settings
    result = export_organization_impl(api_key, region, output_dir, output_format, include_sensitive, formatter)
    
    # Display results
    if result["exported"] > 0:
        formatter.output_success(f"Successfully exported organization settings to {output_dir}")
        if not include_sensitive:
            formatter.output_success("Note: Sensitive fields excluded. Use --include-sensitive to include them.")
    
    if result["failed"] > 0:
        formatter.output_error("Failed to export organization settings")