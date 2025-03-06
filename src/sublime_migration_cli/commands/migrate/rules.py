"""Refactored commands for migrating rules using utility functions."""
from typing import Dict, List, Optional, Set
import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.presentation.base import CommandResult
from sublime_migration_cli.presentation.factory import create_formatter

# Import our utility functions
from sublime_migration_cli.utils.api import PaginatedFetcher
from sublime_migration_cli.utils.filtering import filter_by_ids
from sublime_migration_cli.utils.errors import (
    ApiError, MigrationError, handle_api_error, ErrorHandler
)


# Implementation functions
def migrate_rules_between_instances(
    source_api_key=None, source_region=None, 
    dest_api_key=None, dest_region=None,
    include_rule_ids=None, exclude_rule_ids=None, 
    rule_type=None,
    dry_run=False, formatter=None
):
    """Implementation for migrating rules between instances.
    
    Args:
        source_api_key: API key for source instance
        source_region: Region for source instance
        dest_api_key: API key for destination instance
        dest_region: Region for destination instance
        include_rule_ids: Comma-separated list of rule IDs to include
        exclude_rule_ids: Comma-separated list of rule IDs to exclude
        rule_type: Filter by rule type (detection or triage)
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
        
        # Build query parameters for filtering
        params = {
            "include_deleted": "false",
            "in_feed": "false"
        }
        
        if rule_type:
            params["type"] = rule_type
        
        # Use PaginatedFetcher to fetch all rules from source with pagination
        source_fetcher = PaginatedFetcher(source_client, formatter)
        source_rules = source_fetcher.fetch_all(
            "/v1/rules",
            params=params,
            progress_message="Fetching rules from source..."
        )
        
        # Apply ID filters using our utility function
        filtered_rules = filter_by_ids(source_rules, include_rule_ids, exclude_rule_ids)
        
        if not filtered_rules:
            return CommandResult.error("No rules to migrate after applying filters.")
            
        # Use PaginatedFetcher to fetch all rules from destination 
        dest_fetcher = PaginatedFetcher(dest_client, formatter)
        dest_rules = dest_fetcher.fetch_all(
            "/v1/rules",
            params=params,
            progress_message="Fetching rules from destination..."
        )
        
        # Compare and categorize rules
        matching_results = match_rules_and_categorize(filtered_rules, dest_rules)
        
        new_rules = matching_results["new_rules"]
        update_rules = matching_results["update_rules"]
        skipped_rules = matching_results["skipped_rules"]
        
        # If no rules to migrate, return early
        if not new_rules and not update_rules:
            return CommandResult.success(
                "No rules to migrate (all rules were skipped or already exist).",
                {"skipped_rules": len(skipped_rules)}
            )
        
        # Prepare response data
        migration_data = {
            "new_rules": [
                {
                    "id": rule.get("id", ""),
                    "name": rule.get("name", ""),
                    "type": rule.get("type", ""),
                    "severity": rule.get("severity", ""),
                    "status": "New"
                }
                for rule in new_rules
            ],
            "update_rules": [
                {
                    "id": rule.get("id", ""),
                    "name": rule.get("name", ""),
                    "type": rule.get("type", ""),
                    "severity": rule.get("severity", ""),
                    "status": "Update"
                }
                for rule in update_rules
            ],
            "skipped_rules": [
                {
                    "id": rule["rule"].get("id", ""),
                    "name": rule["rule"].get("name", ""),
                    "type": rule["rule"].get("type", ""),
                    "severity": rule["rule"].get("severity", ""),
                    "reason": rule["reason"]
                }
                for rule in skipped_rules
            ]
        }
        
        # Add summary stats
        migration_data["summary"] = {
            "new_count": len(new_rules),
            "update_count": len(update_rules),
            "skipped_count": len(skipped_rules),
            "total_count": len(new_rules) + len(update_rules) + len(skipped_rules)
        }
        
        # If dry run, return preview data
        if dry_run:
            return CommandResult.success(
                "DRY RUN: Preview of rules to migrate",
                migration_data,
                "No changes were made to the destination instance."
            )
        
        # Show preview before confirmation in interactive mode
        formatter.output_result(CommandResult.success(
            "Rules that will be migrated:",
            migration_data,
            "Please confirm to proceed with migration."
        ))
        
        # Confirm migration if interactive
        if not formatter.prompt_confirmation("\nDo you want to proceed with the migration?"):
            return CommandResult.success("Migration canceled by user.")
        
        # Perform the migration
        results = perform_migration(formatter, dest_client, new_rules, update_rules, dest_rules)
        
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


def match_rules_and_categorize(source_rules: List[Dict], dest_rules: List[Dict]) -> Dict:
    """Match rules between source and destination and categorize them.
    
    Args:
        source_rules: List of source rules
        dest_rules: List of destination rules
        
    Returns:
        Dict: Results of matching including rules to create, update, and skip
    """
    # Create lookup dicts for destination rules
    dest_rule_by_name = {rule.get("name"): rule for rule in dest_rules}
    dest_rule_by_name_and_md5 = {
        (rule.get("name"), rule.get("source_md5")): rule 
        for rule in dest_rules
    }
    
    new_rules = []
    update_rules = []
    skipped_rules = []
    
    for rule in source_rules:
        rule_name = rule.get("name")
        rule_md5 = rule.get("source_md5")
        
        # Check if we have an exact match on name and source_md5
        if (rule_name, rule_md5) in dest_rule_by_name_and_md5:
            # Exact match - update the rule
            update_rules.append(rule)
        elif rule_name in dest_rule_by_name:
            # Name match but different source - skip
            skipped_rules.append({
                "rule": rule,
                "reason": "Rule exists with same name but different content (source_md5 mismatch)"
            })
        else:
            # No match - new rule
            new_rules.append(rule)
    
    return {
        "new_rules": new_rules,
        "update_rules": update_rules,
        "skipped_rules": skipped_rules
    }


def perform_migration(formatter, dest_client, new_rules: List[Dict], 
                     update_rules: List[Dict], existing_rules: List[Dict]) -> Dict:
    """Perform the actual migration of rules to the destination.
    
    Args:
        formatter: Output formatter
        dest_client: API client for destination
        new_rules: List of new rules to create
        update_rules: List of rules to update
        existing_rules: List of existing rules
        
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
    
    # Create a map of existing rules by name for quick lookup
    existing_map = {rule.get("name"): rule for rule in existing_rules}
    
    # Process new rules
    if new_rules:
        with formatter.create_progress("Creating new rules...", total=len(new_rules)) as (progress, task):
            for i, rule in enumerate(new_rules):
                process_new_rule(rule, dest_client, results)
                progress.update(task, completed=i+1)
    
    # Process updates
    if update_rules:
        with formatter.create_progress("Updating existing rules...", total=len(update_rules)) as (progress, task):
            for i, rule in enumerate(update_rules):
                process_update_rule(rule, dest_client, existing_map, results)
                progress.update(task, completed=i+1)
    
    return results


def process_new_rule(rule: Dict, dest_client, results: Dict):
    """Process a new rule for migration."""
    rule_name = rule.get("name", "")
    try:
        # Create rule payload for API request
        payload = create_rule_payload(rule)
        
        # Post to destination
        dest_client.post("/v1/rules", payload)
        results["created"] += 1
        results["details"].append({
            "name": rule_name,
            "type": rule.get("type", ""),
            "status": "created"
        })
        
    except ApiError as e:
        results["failed"] += 1
        results["details"].append({
            "name": rule_name,
            "type": rule.get("type", ""),
            "status": "failed",
            "reason": e.message
        })
    except Exception as e:
        sublime_error = handle_api_error(e)
        results["failed"] += 1
        results["details"].append({
            "name": rule_name,
            "type": rule.get("type", ""),
            "status": "failed",
            "reason": str(sublime_error.message)
        })


def process_update_rule(rule: Dict, dest_client, existing_map: Dict[str, Dict], results: Dict):
    """Process a rule update for migration."""
    rule_name = rule.get("name", "")
    existing = existing_map.get(rule_name)
    
    if not existing:
        results["skipped"] += 1
        results["details"].append({
            "name": rule_name,
            "type": rule.get("type", ""),
            "status": "skipped",
            "reason": "Rule not found in destination"
        })
        return
    
    try:
        # Create update payload
        payload = create_rule_payload(rule)
        
        # Update the rule
        dest_client.patch(f"/v1/rules/{existing.get('id')}", payload)
        results["updated"] += 1
        results["details"].append({
            "name": rule_name,
            "type": rule.get("type", ""),
            "status": "updated"
        })
            
    except ApiError as e:
        results["failed"] += 1
        results["details"].append({
            "name": rule_name,
            "type": rule.get("type", ""),
            "status": "failed",
            "reason": e.message
        })
    except Exception as e:
        sublime_error = handle_api_error(e)
        results["failed"] += 1
        results["details"].append({
            "name": rule_name,
            "type": rule.get("type", ""),
            "status": "failed",
            "reason": str(sublime_error.message)
        })


def create_rule_payload(rule: Dict) -> Dict:
    """Create a clean rule payload for API requests.
    
    Args:
        rule: Source rule object
        
    Returns:
        Dict: Cleaned rule payload
    """
    # Extract only the fields needed for creation/update
    payload = {
        "name": rule.get("name"),
        "description": rule.get("description", ""),
        "source": rule.get("source", ""),
        "active": rule.get("active", False),
        "type": rule.get("type", "detection")
    }
    
    # Include optional fields if present
    optional_fields = [
        "attack_types", "auto_review_auto_share", "auto_review_classification",
        "detection_methods", "false_positives", "maturity", "references",
        "severity", "tactics_and_techniques", "tags", "user_provided_tags",
        "triage_abuse_reports", "triage_flagged_messages"
    ]
    
    for field in optional_fields:
        if field in rule and rule[field] is not None:
            payload[field] = rule[field]
    
    return payload


# Click command definition
@click.command()
@click.option("--source-api-key", help="API key for the source instance")
@click.option("--source-region", help="Region of the source instance")
@click.option("--dest-api-key", help="API key for the destination instance")
@click.option("--dest-region", help="Region of the destination instance")
@click.option("--include-rule-ids", help="Comma-separated list of rule IDs to include")
@click.option("--exclude-rule-ids", help="Comma-separated list of rule IDs to exclude")
@click.option("--type", "rule_type", type=click.Choice(["detection", "triage"]), 
              help="Filter by rule type (detection or triage)")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def rules(source_api_key, source_region, dest_api_key, dest_region,
          include_rule_ids, exclude_rule_ids, rule_type, dry_run, yes, output_format):
    """Migrate rules between Sublime Security instances.
    
    This command copies rules from the source instance to the destination instance.
    Only user-created rules (not from feeds) are migrated.
    
    Note: This command migrates only the rule definitions, not associated actions
    or rule exclusions. Use separate commands for those components.
    
    Examples:
        # Migrate all user-created rules
        sublime migrate rules --source-api-key KEY1 --dest-api-key KEY2
        
        # Migrate specific rules by ID
        sublime migrate rules --include-rule-ids id1,id2 --source-api-key KEY1 --dest-api-key KEY2
        
        # Migrate only detection rules
        sublime migrate rules --type detection --source-api-key KEY1 --dest-api-key KEY2
        
        # Preview migration without making changes
        sublime migrate rules --dry-run --source-api-key KEY1 --dest-api-key KEY2
    """
    # Create formatter based on output format
    formatter = create_formatter(output_format)
    
    # If --yes flag is provided, modify the formatter to auto-confirm
    if yes:
        original_prompt = formatter.prompt_confirmation
        formatter.prompt_confirmation = lambda _: True
    
    # Execute the implementation function
    result = migrate_rules_between_instances(
        source_api_key, source_region, 
        dest_api_key, dest_region,
        include_rule_ids, exclude_rule_ids, 
        rule_type,
        dry_run, formatter
    )
    
    # Reset the formatter if it was modified
    if yes and hasattr(formatter, 'original_prompt'):
        formatter.prompt_confirmation = original_prompt
    
    # Output the result
    formatter.output_result(result)