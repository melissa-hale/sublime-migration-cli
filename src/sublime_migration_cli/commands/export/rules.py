"""Export rules from Sublime Security instance."""
import os
from typing import Dict, List, Optional, Set
import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.presentation.base import CommandResult
from sublime_migration_cli.presentation.factory import create_formatter
from sublime_migration_cli.utils.api import PaginatedFetcher
from sublime_migration_cli.utils.errors import handle_api_error
from sublime_migration_cli.commands.export.utils import (
    sanitize_filename, resolve_filename_collision, write_resource_file, parse_rule_exclusion
)


def export_rules_impl(api_key=None, region=None, detection_dir="./sublime-export/rules/detection",
                     triage_dir="./sublime-export/rules/triage", output_format="yaml", formatter=None):
    """Implementation for exporting rules.
    
    Args:
        api_key: API key for the instance
        region: Region for the instance
        detection_dir: Directory to export detection rules to
        triage_dir: Directory to export triage rules to
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
        
        # Fetch all user-created rules (not from feeds)
        fetcher = PaginatedFetcher(client, formatter)
        
        params = {
            "include_deleted": "false",
            "in_feed": "false"  # Only user-created rules
        }
        
        with formatter.create_progress("Fetching rules...") as (progress, task):
            all_rules = fetcher.fetch_all("/v1/rules", params=params)
            progress.update(task, advance=1)
        
        if not all_rules:
            return {"exported": 0, "failed": 0}
        
        # Separate rules by type
        detection_rules = [rule for rule in all_rules if rule.get("type") == "detection"]
        triage_rules = [rule for rule in all_rules if rule.get("type") == "triage"]
        
        total_rules = len(detection_rules) + len(triage_rules)
        if total_rules == 0:
            return {"exported": 0, "failed": 0}
        
        # Track exported files to avoid collisions
        detection_files = set()
        triage_files = set()
        exported_count = 0
        failed_count = 0
        
        extension = ".yml" if output_format == "yaml" else ".json"
        
        with formatter.create_progress("Exporting rules...", total=total_rules) as (progress, task):
            current_progress = 0
            
            # Export detection rules
            for rule in detection_rules:
                try:
                    # Get detailed rule info (including actions and exclusions)
                    detailed_rule = client.get(f"/v1/rules/{rule.get('id')}")
                    
                    # Convert rule to export format
                    export_data = convert_rule_to_export_format(detailed_rule, client)
                    
                    # Generate filename
                    base_name = sanitize_filename(rule.get("name", "unnamed-rule"))
                    filename = resolve_filename_collision(
                        base_name, detection_files, rule.get("id", ""), extension
                    )
                    detection_files.add(filename)
                    
                    # Write file
                    file_path = os.path.join(detection_dir, filename)
                    write_resource_file(export_data, file_path, output_format)
                    
                    exported_count += 1
                    
                except Exception as e:
                    error = handle_api_error(e)
                    formatter.output_error(
                        f"Failed to export detection rule '{rule.get('name', 'unknown')}': {error.message}"
                    )
                    failed_count += 1
                
                current_progress += 1
                progress.update(task, completed=current_progress)
            
            # Export triage rules
            for rule in triage_rules:
                try:
                    # Get detailed rule info (including actions and exclusions)
                    detailed_rule = client.get(f"/v1/rules/{rule.get('id')}")
                    
                    # Convert rule to export format
                    export_data = convert_rule_to_export_format(detailed_rule, client)
                    
                    # Generate filename
                    base_name = sanitize_filename(rule.get("name", "unnamed-rule"))
                    filename = resolve_filename_collision(
                        base_name, triage_files, rule.get("id", ""), extension
                    )
                    triage_files.add(filename)
                    
                    # Write file
                    file_path = os.path.join(triage_dir, filename)
                    write_resource_file(export_data, file_path, output_format)
                    
                    exported_count += 1
                    
                except Exception as e:
                    error = handle_api_error(e)
                    formatter.output_error(
                        f"Failed to export triage rule '{rule.get('name', 'unknown')}': {error.message}"
                    )
                    failed_count += 1
                
                current_progress += 1
                progress.update(task, completed=current_progress)
        
        return {"exported": exported_count, "failed": failed_count}
        
    except Exception as e:
        error = handle_api_error(e)
        formatter.output_error(f"Failed to export rules: {error.message}")
        return {"exported": 0, "failed": 1}


def convert_rule_to_export_format(rule: Dict, client) -> Dict:
    """Convert a rule object to export format.
    
    Args:
        rule: Rule object from API
        client: API client for fetching additional data
        
    Returns:
        Dict: Rule in export format
    """
    export_data = {
        "name": rule.get("name"),
        "type": "rule",  # Always "rule" as requested
        "severity": rule.get("severity")
    }
    
    # Add description if present
    if rule.get("description"):
        export_data["description"] = rule["description"]
    
    # Add source query
    if rule.get("source"):
        export_data["source"] = rule["source"]
    
    # Add optional fields
    optional_fields = [
        "tags", "attack_types", "tactics_and_techniques", "detection_methods",
        "false_positives", "maturity", "references", "authors"
    ]
    
    for field in optional_fields:
        if rule.get(field):
            export_data[field] = rule[field]
    
    # Add actions (convert to "Action Name - ID" format)
    if rule.get("actions"):
        actions_list = []
        for action in rule["actions"]:
            action_name = action.get("name", "Unknown Action")
            action_id = action.get("id", "")
            actions_list.append(f"{action_name} - {action_id}")
        
        if actions_list:
            export_data["actions"] = actions_list
    
    # Add rule exclusions (inline format)
    add_rule_exclusions(export_data, rule.get("id"), client)
    
    return export_data


def add_rule_exclusions(export_data: Dict, rule_id: str, client) -> None:
    """Add rule exclusions to the export data.
    
    Args:
        export_data: Export data dictionary to modify
        rule_id: Rule ID to fetch exclusions for
        client: API client
    """
    try:
        # Fetch rule exclusions
        params = {"scope": "rule_exclusion"}
        response = client.get("/v1/exclusions", params=params)
        
        # Get exclusions for this rule
        all_exclusions = response.get("exclusions", []) if isinstance(response, dict) else response
        rule_exclusions = [
            exc for exc in all_exclusions 
            if exc.get("originating_rule", {}).get("id") == rule_id
        ]
        
        if rule_exclusions:
            exclusions_dict = {}
            
            for exclusion in rule_exclusions:
                source = exclusion.get("source", "")
                parsed = parse_rule_exclusion(source)
                
                if parsed:
                    exclusion_type, exclusion_value = parsed
                    
                    if exclusion_type not in exclusions_dict:
                        exclusions_dict[exclusion_type] = []
                    
                    exclusions_dict[exclusion_type].append(exclusion_value)
            
            if exclusions_dict:
                export_data["exclusions"] = exclusions_dict
                
    except Exception:
        # If exclusion fetching fails, continue without exclusions
        pass


@click.command()
@click.option("--api-key", help="API key for authentication")
@click.option("--region", help="Region to connect to")
@click.option("--output-dir", "-o", default="./sublime-export", 
              help="Output directory (default: ./sublime-export)")
@click.option("--format", "output_format", type=click.Choice(["yaml", "json"]), 
              default="yaml", help="Output format (default: yaml)")
@click.option("--type", "rule_type", type=click.Choice(["detection", "triage"]),
              help="Export only specific rule type")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def rules(api_key, region, output_dir, output_format, rule_type, verbose):
    """Export rules from a Sublime Security instance.
    
    This command exports all user-created rules to local files organized by type.
    Rules from feeds are excluded by default.
    
    Examples:
        # Export all rules to default directory
        sublime export rules
        
        # Export only detection rules
        sublime export rules --type detection
        
        # Export to specific directory in JSON format
        sublime export rules --output-dir ./my-export --format json
    """
    formatter = create_formatter("table")
    
    # Create the rules subdirectories within the export directory
    detection_dir = os.path.join(output_dir, "rules", "detection")
    triage_dir = os.path.join(output_dir, "rules", "triage")
    
    if not rule_type or rule_type == "detection":
        os.makedirs(detection_dir, exist_ok=True)
    
    if not rule_type or rule_type == "triage":
        os.makedirs(triage_dir, exist_ok=True)
    
    # If filtering by type, adjust directories
    if rule_type == "detection":
        triage_dir = None
    elif rule_type == "triage":
        detection_dir = None
    
    # Export rules
    result = export_rules_impl(api_key, region, detection_dir, triage_dir, output_format, formatter)
    
    # Display results
    if result["exported"] > 0:
        rules_dir = os.path.join(output_dir, "rules")
        formatter.output_success(
            f"Successfully exported {result['exported']} rules to {rules_dir}"
        )
    
    if result["failed"] > 0:
        formatter.output_error(f"{result['failed']} rules failed to export")
    
    if result["exported"] == 0 and result["failed"] == 0:
        formatter.output_success("No user-created rules found to export")