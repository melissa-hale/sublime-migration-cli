"""Refactored commands for migrating action associations to rules using utility functions."""
from typing import Dict, List, Optional, Set, Tuple
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
def migrate_actions_to_rules_between_instances(
    source_api_key=None, source_region=None, 
    dest_api_key=None, dest_region=None,
    include_rule_ids=None, exclude_rule_ids=None,
    include_action_ids=None, exclude_action_ids=None,
    dry_run=False, formatter=None
):
    """Implementation for migrating action associations to rules between instances.
    
    Args:
        source_api_key: API key for source instance
        source_region: Region for source instance
        dest_api_key: API key for destination instance
        dest_region: Region for destination instance
        include_rule_ids: Comma-separated list of rule IDs to include
        exclude_rule_ids: Comma-separated list of rule IDs to exclude
        include_action_ids: Comma-separated list of action IDs to include
        exclude_action_ids: Comma-separated list of action IDs to exclude
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
        
        # Filter to only rules with actions
        rules_with_actions = [rule for rule in filtered_rules if rule.get("actions") and len(rule.get("actions")) > 0]
        
        if not rules_with_actions:
            return CommandResult.error("No rules with actions to process after applying filters.")
            
        # Filter actions if specified
        if include_action_ids or exclude_action_ids:
            rules_with_actions = filter_actions_in_rules(
                rules_with_actions, include_action_ids, exclude_action_ids
            )
            
            if not rules_with_actions:
                return CommandResult.error("No rules with matching actions after applying action filters.")
        
        # Enrich rules with action details
        rules_with_actions = enrich_rules_with_action_details(
            source_client, rules_with_actions, formatter
        )
        
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
        
        # Fetch all actions from destination
        dest_actions = dest_fetcher.fetch_all(
            "/v1/actions",
            progress_message="Fetching actions from destination..."
        )
        
        # Create mapping of actions by name and type in destination
        dest_actions_map = {
            (action.get("name"), action.get("type")): action 
            for action in dest_actions
        }
        
        # Match rules and actions between source and destination
        matching_results = match_rules_and_actions(
            rules_with_actions, dest_rules_map, dest_actions_map
        )
        
        rules_to_update = matching_results["rules_to_update"]
        skipped_rules = matching_results["skipped_rules"]
        skipped_actions = matching_results["skipped_actions"]
        
        # If no rules to update, return early
        if not rules_to_update:
            return CommandResult.error(
                "No rule-action associations can be migrated (all were skipped).",
                {
                    "skipped_rules": len(skipped_rules),
                    "skipped_actions": len(skipped_actions)
                }
            )
            
        # Prepare response data
        total_actions = sum(len(rule["matched_actions"]) for rule in rules_to_update)
        
        migration_data = {
            "rules_to_update": [
                {
                    "rule_name": rule["source_rule"].get("name", ""),
                    "rule_id": rule["dest_rule"].get("id", ""),
                    "actions": [action["name"] for action in rule["matched_actions"]],
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
            "skipped_actions": [
                {
                    "rule_name": item["rule"].get("name", ""),
                    "action_name": item["action"].get("name", ""),
                    "reason": item["reason"]
                }
                for item in skipped_actions
            ]
        }
        
        # Add summary stats
        migration_data["summary"] = {
            "rules_count": len(rules_to_update),
            "actions_count": total_actions,
            "skipped_rules_count": len(skipped_rules),
            "skipped_actions_count": len(skipped_actions),
            "total_count": len(rules_to_update) + len(skipped_rules)
        }
        
        # If dry run, return preview data
        if dry_run:
            return CommandResult.success(
                "DRY RUN: Preview of rule-action associations to migrate",
                migration_data,
                "No changes were made to the destination instance."
            )
        
        # Show preview before confirmation in interactive mode
        formatter.output_result(CommandResult.success(
            "Rule-action associations that will be migrated:",
            migration_data,
            "Please confirm to proceed with migration."
        ))
        
        # Confirm migration if interactive
        if not formatter.prompt_confirmation("\nDo you want to proceed with the migration?"):
            return CommandResult.success("Migration canceled by user.")
        
        # Perform the migration
        results = apply_rule_action_associations(formatter, dest_client, rules_to_update)
        
        # Add results to migration data
        migration_data["results"] = results
        
        # Return overall results
        return CommandResult.success(
            f"Migration completed: {results['updated']} rules updated with action associations, "
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


def filter_actions_in_rules(rules: List[Dict], include_action_ids: Optional[str], 
                         exclude_action_ids: Optional[str]) -> List[Dict]:
    """Filter actions within rules based on action IDs.
    
    Args:
        rules: List of rule objects with actions
        include_action_ids: Comma-separated list of action IDs to include
        exclude_action_ids: Comma-separated list of action IDs to exclude
        
    Returns:
        List[Dict]: Filtered rules with filtered actions
    """
    # Create sets of action IDs to filter with
    include_ids = set(id.strip() for id in include_action_ids.split(",")) if include_action_ids else None
    exclude_ids = set(id.strip() for id in exclude_action_ids.split(",")) if exclude_action_ids else None
    
    filtered_rules = []
    
    for rule in rules:
        # Apply filters to actions in this rule
        filtered_actions = rule.get("actions", [])
        
        if include_ids:
            filtered_actions = [action for action in filtered_actions 
                               if action.get("id") in include_ids]
        
        if exclude_ids:
            filtered_actions = [action for action in filtered_actions 
                               if action.get("id") not in exclude_ids]
        
        # Only include rule if it still has actions after filtering
        if filtered_actions:
            # Create a copy of the rule with filtered actions
            rule_copy = rule.copy()
            rule_copy["actions"] = filtered_actions
            filtered_rules.append(rule_copy)
    
    return filtered_rules


def enrich_rules_with_action_details(source_client, rules_with_actions: List[Dict], formatter) -> List[Dict]:
    """Fetch action details and enrich the action objects in the rules.
    
    Args:
        source_client: API client for the source instance
        rules_with_actions: List of rules with action references
        formatter: Output formatter
        
    Returns:
        List[Dict]: Enriched rules with detailed action information
    """
    # Count total actions to process
    total_actions = sum(len(rule.get("actions", [])) for rule in rules_with_actions)
    
    # Create a copy of the rules to avoid modifying the originals
    enriched_rules = []
    
    with formatter.create_progress("Fetching action details...", total=total_actions) as (progress, task):
        # Process each rule
        for rule in rules_with_actions:
            rule_copy = rule.copy()
            enriched_actions = []
            
            # Process each action in the rule
            for action in rule.get("actions", []):
                action_id = action.get("id")
                try:
                    # Fetch detailed action information
                    action_details = source_client.get(f"/v1/actions/{action_id}")
                    
                    # Create enriched action object with type
                    enriched_action = action.copy()
                    enriched_action["type"] = action_details.get("type")
                    enriched_actions.append(enriched_action)
                except Exception:
                    # Include the action anyway, it will be skipped during matching if type is missing
                    enriched_actions.append(action)
                
                progress.update(task, advance=1)
            
            # Update the rule with enriched actions
            rule_copy["actions"] = enriched_actions
            enriched_rules.append(rule_copy)
    
    return enriched_rules


def match_rules_and_actions(source_rules: List[Dict], dest_rules_map: Dict, 
                          dest_actions_map: Dict) -> Dict:
    """Match rules and actions between source and destination.
    
    Args:
        source_rules: List of source rules with actions
        dest_rules_map: Map of destination rules by (name, source_md5)
        dest_actions_map: Map of destination actions by (name, type)
        
    Returns:
        Dict: Results of matching including rules to update and skipped items
    """
    rules_to_update = []
    skipped_rules = []
    skipped_actions = []
    
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
        
        # Match actions for this rule
        matched_actions = []
        
        for source_action in source_rule.get("actions", []):
            action_name = source_action.get("name")
            action_type = source_action.get("type")
            
            if not action_type:
                skipped_actions.append({
                    "rule": source_rule,
                    "action": source_action,
                    "reason": f"Missing action type for '{action_name}'"
                })
                continue
            
            # Find matching action in destination
            dest_action = dest_actions_map.get((action_name, action_type))
            
            if dest_action:
                matched_actions.append({
                    "id": dest_action.get("id"),
                    "name": action_name,
                    "type": action_type
                })
            else:
                skipped_actions.append({
                    "rule": source_rule,
                    "action": source_action,
                    "reason": f"No matching action found in destination (name='{action_name}', type='{action_type}')"
                })
        
        # Only include rule if it has matched actions
        if matched_actions:
            rules_to_update.append({
                "source_rule": source_rule,
                "dest_rule": dest_rule,
                "matched_actions": matched_actions
            })
    
    return {
        "rules_to_update": rules_to_update,
        "skipped_rules": skipped_rules,
        "skipped_actions": skipped_actions
    }


def apply_rule_action_associations(formatter, dest_client, rules_to_update: List[Dict]) -> Dict:
    """Apply action associations to rules in the destination.
    
    Args:
        formatter: Output formatter
        dest_client: API client for the destination
        rules_to_update: List of rules to update with matched actions
        
    Returns:
        Dict: Migration results
    """
    results = {
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "details": []
    }
    
    with formatter.create_progress("Updating rule action associations...", total=len(rules_to_update)) as (progress, task):
        for rule_update in rules_to_update:
            process_rule_action_update(rule_update, dest_client, results)
            progress.update(task, advance=1)
    
    return results


def process_rule_action_update(rule_update: Dict, dest_client, results: Dict):
    """Process a rule action association update.
    
    Args:
        rule_update: Rule update information with matched actions
        dest_client: API client for the destination
        results: Results dictionary to update
    """
    rule_name = rule_update["source_rule"].get("name", "")
    dest_rule_id = rule_update["dest_rule"].get("id", "")
    
    try:
        # Create update payload with action IDs
        action_ids = [action["id"] for action in rule_update["matched_actions"]]
        
        payload = {
            "action_ids": action_ids
        }
        
        # Update the rule with the action associations
        dest_client.patch(f"/v1/rules/{dest_rule_id}", payload)
        
        results["updated"] += 1
        results["details"].append({
            "name": rule_name,
            "type": "rule",
            "status": "updated",
            "actions_count": len(action_ids)
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
        results["failed"] += 1
        results["details"].append({
            "name": rule_name,
            "type": "rule",
            "status": "failed",
            "reason": str(e)
        })


# Click command definition
@click.command()
@click.option("--source-api-key", help="API key for the source instance")
@click.option("--source-region", help="Region of the source instance")
@click.option("--dest-api-key", help="API key for the destination instance")
@click.option("--dest-region", help="Region of the destination instance")
@click.option("--include-rule-ids", help="Comma-separated list of rule IDs to include")
@click.option("--exclude-rule-ids", help="Comma-separated list of rule IDs to exclude")
@click.option("--include-action-ids", help="Comma-separated list of action IDs to include")
@click.option("--exclude-action-ids", help="Comma-separated list of action IDs to exclude")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def actions_to_rules(source_api_key, source_region, dest_api_key, dest_region,
                     include_rule_ids, exclude_rule_ids, include_action_ids, exclude_action_ids,
                     dry_run, yes, output_format):
    """Migrate action associations to rules between Sublime Security instances.
    
    This command associates actions with rules in the destination instance,
    matching the associations from the source instance.
    
    Both rules and actions must already exist in the destination instance.
    Rules are matched by name and source_md5. Actions are matched by name and type.
    
    Examples:
        # Migrate all action associations
        sublime migrate actions-to-rules --source-api-key KEY1 --dest-api-key KEY2
        
        # Migrate action associations for specific rules
        sublime migrate actions-to-rules --include-rule-ids id1,id2 --source-api-key KEY1 --dest-api-key KEY2
        
        # Preview migration without making changes
        sublime migrate actions-to-rules --dry-run --source-api-key KEY1 --dest-api-key KEY2
    """
    # Create formatter based on output format
    formatter = create_formatter(output_format)
    
    # If --yes flag is provided, modify the formatter to auto-confirm
    if yes:
        original_prompt = formatter.prompt_confirmation
        formatter.prompt_confirmation = lambda _: True
    
    # Execute the implementation function
    result = migrate_actions_to_rules_between_instances(
        source_api_key, source_region, 
        dest_api_key, dest_region,
        include_rule_ids, exclude_rule_ids,
        include_action_ids, exclude_action_ids,
        dry_run, formatter
    )
    
    # Reset the formatter if it was modified
    if yes and hasattr(formatter, 'original_prompt'):
        formatter.prompt_confirmation = original_prompt
    
    # Output the result
    formatter.output_result(result)