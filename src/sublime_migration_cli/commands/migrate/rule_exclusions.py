"""Refactored commands for migrating rule exclusions using utility functions."""
from typing import Dict, List, Optional, Set, Tuple
import re
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


# Regular expression patterns for different types of exclusions
EXCLUSION_PATTERNS = {
    "recipient_email": re.compile(r"any\(recipients\.to, \.email\.email == '([^']+)'\)"),
    "sender_email": re.compile(r"sender\.email\.email == '([^']+)'"),
    "sender_domain": re.compile(r"sender\.email\.domain\.domain == '([^']+)'")
}


# Implementation functions
def migrate_rule_exclusions_between_instances(
    source_api_key=None, source_region=None, 
    dest_api_key=None, dest_region=None,
    include_rule_ids=None, exclude_rule_ids=None,
    dry_run=False, formatter=None
):
    """Implementation for migrating rule exclusions between instances.
    
    Args:
        source_api_key: API key for source instance
        source_region: Region for source instance
        dest_api_key: API key for destination instance
        dest_region: Region for destination instance
        include_rule_ids: Comma-separated list of rule IDs to include
        exclude_rule_ids: Comma-separated list of rule IDs to exclude
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
            
        # Use PaginatedFetcher to fetch all rules from source
        source_fetcher = PaginatedFetcher(source_client, formatter)
        source_rules = source_fetcher.fetch_all(
            "/v1/rules",
            progress_message="Fetching rules from source..."
        )
        
        # Apply rule ID filters using our utility function
        filtered_rules = filter_by_ids(source_rules, include_rule_ids, exclude_rule_ids)
        
        # Fetch detailed rule information including exclusions
        with formatter.create_progress("Fetching rule details for exclusions...", total=len(filtered_rules)) as (progress, task):
            detailed_rules = []
            
            for i, rule in enumerate(filtered_rules):
                try:
                    rule_id = rule.get("id")
                    # Fetch detailed info
                    details = source_client.get(f"/v1/rules/{rule_id}")
                    detailed_rules.append(details)
                except ApiError as e:
                    formatter.output_error(f"Warning: Failed to fetch details for rule '{rule.get('name')}': {e.message}")
                except Exception as e:
                    sublime_error = handle_api_error(e)
                    formatter.output_error(f"Warning: Failed to fetch details for rule '{rule.get('name')}': {sublime_error.message}")
                
                # Update progress
                progress.update(task, completed=i+1)
        
        # Filter to only rules with exclusions
        rules_with_exclusions = [
            rule for rule in detailed_rules 
            if rule.get("exclusions") and len(rule.get("exclusions")) > 0
        ]
        
        if not rules_with_exclusions:
            return CommandResult.error("No rules with exclusions found after applying filters.")
            
        # Use PaginatedFetcher to fetch all rules from destination
        dest_fetcher = PaginatedFetcher(dest_client, formatter)
        dest_rules = dest_fetcher.fetch_all(
            "/v1/rules",
            progress_message="Fetching rules from destination..."
        )
        
        # Create mapping of rules by name and md5 in destination
        dest_rules_map = {
            (rule.get("name"), rule.get("source_md5")): rule 
            for rule in dest_rules
        }
        
        # Match rules and parse exclusions
        matching_results = match_rules_and_parse_exclusions(
            rules_with_exclusions, dest_rules_map
        )
        
        rules_to_update = matching_results["rules_to_update"]
        skipped_rules = matching_results["skipped_rules"]
        skipped_exclusions = matching_results["skipped_exclusions"]
        
        # If no rules to update, return early
        if not rules_to_update:
            return CommandResult.error(
                "No rule exclusions can be migrated (all were skipped).",
                {
                    "skipped_rules": len(skipped_rules),
                    "skipped_exclusions": len(skipped_exclusions)
                }
            )
            
        # Prepare response data
        total_exclusions = sum(len(rule["parsed_exclusions"]) for rule in rules_to_update)
        
        migration_data = {
            "rules_to_update": [
                {
                    "rule_name": rule["source_rule"].get("name", ""),
                    "rule_id": rule["dest_rule"].get("id", ""),
                    "exclusions": [
                        f"{next(iter(exc.keys()))}: {next(iter(exc.values()))}"
                        for exc in rule["parsed_exclusions"]
                    ],
                    "status": "Update"
                }
                for rule in rules_to_update
            ],
            "skipped_rules": [
                {
                    "rule_name": item["rule"].get("name", ""),
                    "reason": item["reason"]
                }
                for item in skipped_rules
            ],
            "skipped_exclusions": [
                {
                    "rule_name": item["rule"].get("name", ""),
                    "exclusion": item["exclusion"],
                    "reason": item["reason"]
                }
                for item in skipped_exclusions
            ]
        }
        
        # Add summary stats
        migration_data["summary"] = {
            "rules_count": len(rules_to_update),
            "exclusions_count": total_exclusions,
            "skipped_rules_count": len(skipped_rules),
            "skipped_exclusions_count": len(skipped_exclusions),
            "total_count": len(rules_to_update) + len(skipped_rules)
        }
        
        # If dry run, return preview data
        if dry_run:
            return CommandResult.success(
                "DRY RUN: Preview of rule exclusions to migrate",
                migration_data,
                "No changes were made to the destination instance."
            )
        
        # Show preview before confirmation in interactive mode
        formatter.output_result(CommandResult.success(
            "Rule exclusions that will be migrated:",
            migration_data,
            "Please confirm to proceed with migration."
        ))
        
        # Confirm migration if interactive
        if not formatter.prompt_confirmation("\nDo you want to proceed with the migration?"):
            return CommandResult.success("Migration canceled by user.")
        
        # Perform the migration
        results = apply_rule_exclusions(formatter, dest_client, rules_to_update)
        
        # Add results to migration data
        migration_data["results"] = results
        
        # Return overall results
        return CommandResult.success(
            f"Migration completed: {results['updated']} rules updated with exclusions, "
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


def match_rules_and_parse_exclusions(source_rules: List[Dict], dest_rules_map: Dict) -> Dict:
    """Match rules between source and destination and parse exclusions.
    
    Args:
        source_rules: List of source rules with exclusions
        dest_rules_map: Map of destination rules by (name, source_md5)
        
    Returns:
        Dict: Results of matching including rules to update and skipped items
    """
    rules_to_update = []
    skipped_rules = []
    skipped_exclusions = []
    
    for source_rule in source_rules:
        rule_name = source_rule.get("name")
        rule_md5 = source_rule.get("source_md5")
        
        # Find matching rule in destination
        dest_rule = dest_rules_map.get((rule_name, rule_md5))
        
        if not dest_rule:
            # Rule not found in destination or has different content
            skipped_rules.append({
                "rule": source_rule,
                "reason": "No matching rule found in destination (name and source_md5 must match)"
            })
            continue
        
        # Parse exclusions
        parsed_exclusions = []
        
        for exclusion_str in source_rule.get("exclusions", []):
            exclusion = parse_exclusion_string(exclusion_str)
            if exclusion:
                parsed_exclusions.append(exclusion)
            else:
                skipped_exclusions.append({
                    "rule": source_rule,
                    "exclusion": exclusion_str,
                    "reason": "Could not parse exclusion format"
                })
        
        # Only include rule if it has parsed exclusions
        if parsed_exclusions:
            rules_to_update.append({
                "source_rule": source_rule,
                "dest_rule": dest_rule,
                "parsed_exclusions": parsed_exclusions
            })
    
    return {
        "rules_to_update": rules_to_update,
        "skipped_rules": skipped_rules,
        "skipped_exclusions": skipped_exclusions
    }


def parse_exclusion_string(exclusion_str: str) -> Optional[Dict]:
    """Parse an exclusion string to determine its type.
    
    Args:
        exclusion_str: Exclusion string from the rule
        
    Returns:
        Optional[Dict]: Exclusion payload or None if not recognized
    """
    for exc_type, pattern in EXCLUSION_PATTERNS.items():
        match = pattern.search(exclusion_str)
        if match:
            return {exc_type: match.group(1)}
    
    return None


def apply_rule_exclusions(formatter, dest_client, rules_to_update: List[Dict]) -> Dict:
    """Apply exclusions to rules in the destination.
    
    Args:
        formatter: Output formatter
        dest_client: API client for the destination
        rules_to_update: List of rules to update with parsed exclusions
        
    Returns:
        Dict: Migration results
    """
    results = {
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "details": []
    }
    
    with formatter.create_progress("Updating rule exclusions...", total=len(rules_to_update)) as (progress, task):
        for i, rule_update in enumerate(rules_to_update):
            process_rule_exclusion_update(rule_update, dest_client, results)
            progress.update(task, completed=i+1)
    
    return results


def process_rule_exclusion_update(rule_update: Dict, dest_client, results: Dict):
    """Process a rule exclusion update.
    
    Args:
        rule_update: Rule update information with parsed exclusions
        dest_client: API client for the destination
        results: Results dictionary to update
    """
    rule_name = rule_update["source_rule"].get("name", "")
    dest_rule_id = rule_update["dest_rule"].get("id", "")
    exclusions = rule_update["parsed_exclusions"]
    
    try:
        # Apply each exclusion one by one
        succeeded = 0
        for exclusion in exclusions:
            try:
                # Add exclusion to rule
                dest_client.post(f"/v1/rules/{dest_rule_id}/add-exclusion", exclusion)
                succeeded += 1
            except ApiError as e:
                # Record failure but continue with others
                results["details"].append({
                    "name": rule_name,
                    "type": "exclusion",
                    "status": "failed",
                    "reason": f"Failed to add exclusion {exclusion}: {e.message}"
                })
            except Exception as e:
                sublime_error = handle_api_error(e)
                results["details"].append({
                    "name": rule_name,
                    "type": "exclusion",
                    "status": "failed",
                    "reason": f"Failed to add exclusion {exclusion}: {sublime_error.message}"
                })
        
        if succeeded > 0:
            results["updated"] += 1
            results["details"].append({
                "name": rule_name,
                "type": "rule",
                "status": "updated",
                "exclusions_count": succeeded
            })
        else:
            results["failed"] += 1
            results["details"].append({
                "name": rule_name,
                "type": "rule",
                "status": "failed",
                "reason": "All exclusions failed to apply"
            })
        
    except ApiError as e:
        results["failed"] += 1
        results["details"].append({
            "name": rule_name,
            "type": "rule",
            "status": "failed",
            "reason": e.message
        })
    except Exception as e:
        sublime_error = handle_api_error(e)
        results["failed"] += 1
        results["details"].append({
            "name": rule_name,
            "type": "rule",
            "status": "failed",
            "reason": str(sublime_error.message)
        })


# Click command definition
@click.command()
@click.option("--source-api-key", help="API key for the source instance")
@click.option("--source-region", help="Region of the source instance")
@click.option("--dest-api-key", help="API key for the destination instance")
@click.option("--dest-region", help="Region of the destination instance")
@click.option("--include-rule-ids", help="Comma-separated list of rule IDs to include")
@click.option("--exclude-rule-ids", help="Comma-separated list of rule IDs to exclude")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def rule_exclusions(source_api_key, source_region, dest_api_key, dest_region,
                    include_rule_ids, exclude_rule_ids, dry_run, yes, output_format):
    """Migrate rule exclusions between Sublime Security instances.
    
    This command copies rule-specific exclusions from the source instance to matching rules
    in the destination instance.
    
    Rules are matched by name and source_md5 hash. Exclusions are added to matching rules
    in the destination instance.
    
    Examples:
        # Migrate all rule exclusions
        sublime migrate rule-exclusions --source-api-key KEY1 --dest-api-key KEY2
        
        # Migrate exclusions for specific rules
        sublime migrate rule-exclusions --include-rule-ids id1,id2 --source-api-key KEY1 --dest-api-key KEY2
        
        # Preview migration without making changes
        sublime migrate rule-exclusions --dry-run --source-api-key KEY1 --dest-api-key KEY2
    """
    # Create formatter based on output format
    formatter = create_formatter(output_format)
    
    # If --yes flag is provided, modify the formatter to auto-confirm
    if yes:
        original_prompt = formatter.prompt_confirmation
        formatter.prompt_confirmation = lambda _: True
    
    # Execute the implementation function
    result = migrate_rule_exclusions_between_instances(
        source_api_key, source_region, 
        dest_api_key, dest_region,
        include_rule_ids, exclude_rule_ids,
        dry_run, formatter
    )
    
    # Reset the formatter if it was modified
    if yes and hasattr(formatter, 'original_prompt'):
        formatter.prompt_confirmation = original_prompt
    
    # Output the result
    formatter.output_result(result)