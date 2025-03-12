"""Migration command for applying rule-level exclusions."""
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
            
        # Fetch rule exclusions directly from source
        params = {"scope": "rule_exclusion"}
        source_fetcher = PaginatedFetcher(source_client, formatter)
        source_exclusions = source_fetcher.fetch_all(
            "/v1/exclusions",
            params=params,
            progress_message="Fetching rule exclusions from source...",
        )
        
        if not source_exclusions:
            return CommandResult.error("No rule exclusions found in source instance.")
            
        # Apply filters if rule IDs were specified
        if include_rule_ids or exclude_rule_ids:
            source_exclusions = filter_rule_exclusions_by_rule_ids(
                source_exclusions, include_rule_ids, exclude_rule_ids
            )
            
            if not source_exclusions:
                return CommandResult.error("No rule exclusions match the specified rule ID filters.")
                
        # Fetch all rules from destination to build match map
        dest_fetcher = PaginatedFetcher(dest_client, formatter)
        dest_rules = dest_fetcher.fetch_all(
            "/v1/rules",
            progress_message="Fetching rules from destination..."
        )
        
        # Create mapping of destination rules by name and source_md5
        dest_rules_map = {
            (rule.get("name"), rule.get("source_md5")): rule 
            for rule in dest_rules
        }
        
        # Match rule exclusions to destination rules
        matching_results = match_exclusions_to_rules(
            source_exclusions, dest_rules_map
        )
        
        exclusions_to_apply = matching_results["exclusions_to_apply"]
        skipped_exclusions = matching_results["skipped_exclusions"]
        
        # If no exclusions to apply, return early
        if not exclusions_to_apply:
            return CommandResult.error(
                "No rule exclusions can be migrated (all were skipped).",
                {"skipped_exclusions": len(skipped_exclusions)}
            )
            
        # Prepare response data
        total_exclusions = len(exclusions_to_apply)
        # Group exclusions by rule
        exclusions_by_rule = {}
        for exclusion in exclusions_to_apply:
            rule_id = exclusion["dest_rule"]["id"]
            rule_name = exclusion["dest_rule"]["name"]
            if rule_id not in exclusions_by_rule:
                exclusions_by_rule[rule_id] = {
                    "rule_name": rule_name,
                    "rule_id": rule_id,
                    "exclusions": [],
                    "status": "Update"
                }
            exclusions_by_rule[rule_id]["exclusions"].append(
                f"{exclusion['exclusion_type']}: {exclusion['exclusion_value']}"
            )
        
        migration_data = {
            "rules_to_update": list(exclusions_by_rule.values()),
            "skipped_exclusions": [
                {
                    "rule_name": item.get("originating_rule", {}).get("name", "Unknown"),
                    "exclusion": item.get("source", ""),
                    "reason": item.get("reason", "Unknown reason")
                }
                for item in skipped_exclusions
            ]
        }
        
        # Add summary stats
        migration_data["summary"] = {
            "rules_count": len(exclusions_by_rule),
            "exclusions_count": total_exclusions,
            "skipped_exclusions_count": len(skipped_exclusions),
            "total_count": total_exclusions + len(skipped_exclusions)
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
        results = apply_rule_exclusions(formatter, dest_client, exclusions_to_apply)
        
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


def filter_rule_exclusions_by_rule_ids(exclusions: List[Dict], include_rule_ids: Optional[str], exclude_rule_ids: Optional[str]) -> List[Dict]:
    """Filter rule exclusions based on rule IDs.
    
    Args:
        exclusions: List of rule exclusion objects
        include_rule_ids: Comma-separated list of rule IDs to include
        exclude_rule_ids: Comma-separated list of rule IDs to exclude
        
    Returns:
        List[Dict]: Filtered rule exclusions
    """
    # Convert rule ID strings to sets
    include_ids = set(id.strip() for id in include_rule_ids.split(",")) if include_rule_ids else None
    exclude_ids = set(id.strip() for id in exclude_rule_ids.split(",")) if exclude_rule_ids else None
    
    filtered_exclusions = []
    
    for exclusion in exclusions:
        if not exclusion.get("originating_rule"):
            # Skip if no originating rule
            continue
            
        rule_id = exclusion["originating_rule"].get("id")
        
        # Apply filters
        if include_ids and rule_id not in include_ids:
            continue
            
        if exclude_ids and rule_id in exclude_ids:
            continue
            
        filtered_exclusions.append(exclusion)
    
    return filtered_exclusions


def match_exclusions_to_rules(source_exclusions: List[Dict], dest_rules_map: Dict) -> Dict:
    """Match rule exclusions to destination rules.
    
    Args:
        source_exclusions: List of source rule exclusions
        dest_rules_map: Map of destination rules by (name, source_md5)
        
    Returns:
        Dict: Results of matching
    """
    exclusions_to_apply = []
    skipped_exclusions = []
    
    for exclusion in source_exclusions:
        # Get originating rule details
        originating_rule = exclusion.get("originating_rule")
        
        if not originating_rule:
            skipped_exclusions.append({
                **exclusion,
                "reason": "No originating rule information found"
            })
            continue
            
        rule_name = originating_rule.get("name")
        rule_md5 = originating_rule.get("source_md5")
        
        # Find matching rule in destination
        dest_rule = dest_rules_map.get((rule_name, rule_md5))
        
        if not dest_rule:
            skipped_exclusions.append({
                **exclusion,
                "reason": "No matching rule found in destination (name and source_md5 must match)"
            })
            continue
            
        # Parse exclusion
        source_text = exclusion.get("source", "")
        parsed_exclusion = parse_exclusion_string(source_text)
        
        if not parsed_exclusion:
            skipped_exclusions.append({
                **exclusion,
                "reason": "Could not parse exclusion format"
            })
            continue
            
        # Add to list of exclusions to apply
        exclusions_to_apply.append({
            "source_exclusion": exclusion,
            "dest_rule": dest_rule,
            "exclusion_type": parsed_exclusion[0],
            "exclusion_value": parsed_exclusion[1]
        })
    
    return {
        "exclusions_to_apply": exclusions_to_apply,
        "skipped_exclusions": skipped_exclusions
    }


def parse_exclusion_string(exclusion_str: str) -> Optional[Tuple[str, str]]:
    """Parse an exclusion string to determine its type.
    
    Args:
        exclusion_str: Exclusion string from the rule
        
    Returns:
        Optional[Tuple[str, str]]: Exclusion type and value, or None if not recognized
    """
    for exc_type, pattern in EXCLUSION_PATTERNS.items():
        match = pattern.search(exclusion_str)
        if match:
            return (exc_type, match.group(1))
    
    return None


def apply_rule_exclusions(formatter, dest_client, exclusions_to_apply: List[Dict]) -> Dict:
    """Apply exclusions to rules in the destination.
    
    Args:
        formatter: Output formatter
        dest_client: API client for the destination
        exclusions_to_apply: List of exclusions to apply with rule information
        
    Returns:
        Dict: Migration results
    """
    results = {
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "details": []
    }
    
    # Group exclusions by rule for efficient updates
    exclusions_by_rule = {}
    for exclusion in exclusions_to_apply:
        rule_id = exclusion["dest_rule"]["id"]
        if rule_id not in exclusions_by_rule:
            exclusions_by_rule[rule_id] = {
                "rule": exclusion["dest_rule"],
                "exclusions": []
            }
        exclusions_by_rule[rule_id]["exclusions"].append({
            exclusion["exclusion_type"]: exclusion["exclusion_value"]
        })
    
    with formatter.create_progress("Updating rule exclusions...", total=len(exclusions_by_rule)) as (progress, task):
        for i, (rule_id, rule_data) in enumerate(exclusions_by_rule.items()):
            rule = rule_data["rule"]
            exclusions = rule_data["exclusions"]
            
            process_rule_exclusion_update(rule, exclusions, dest_client, results)
            
            # Update progress
            if progress and task:
                progress.update(task, completed=i+1)
    
    return results


def process_rule_exclusion_update(rule: Dict, exclusions: List[Dict], dest_client, results: Dict):
    """Process rule exclusion updates for a single rule.
    
    Args:
        rule: Rule to update
        exclusions: List of exclusions to apply to the rule
        dest_client: API client for the destination
        results: Results dictionary to update
    """
    rule_name = rule.get("name", "")
    rule_id = rule.get("id", "")
    
    try:
        # Apply each exclusion one by one
        succeeded = 0
        for exclusion in exclusions:
            try:
                # Add exclusion to rule
                dest_client.post(f"/v1/rules/{rule_id}/add-exclusion", exclusion)
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