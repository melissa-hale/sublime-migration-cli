"""Commands for migrating rules between Sublime Security instances."""
from typing import Dict, List, Optional
import json

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

from sublime_migration_cli.api.client import get_api_client_from_env_or_args

 
@click.command()
@click.option("--source-api-key", help="API key for the source instance")
@click.option("--source-region", help="Region of the source instance")
@click.option("--dest-api-key", help="API key for the destination instance")
@click.option("--dest-region", help="Region of the destination instance")
@click.option("--include-ids", help="Comma-separated list of rule IDs to include")
@click.option("--exclude-ids", help="Comma-separated list of rule IDs to exclude")
@click.option("--type", "rule_type", type=click.Choice(["detection", "triage"]), 
              help="Filter by rule type (detection or triage)")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def rules(source_api_key, source_region, dest_api_key, dest_region,
          include_ids, exclude_ids, rule_type, dry_run, yes, output_format):
    """Migrate rules between Sublime Security instances.
    
    This command copies rules from the source instance to the destination instance.
    Only user-created rules (not from feeds) are migrated.
    
    Note: This command migrates only the rule definitions, not associated actions
    or rule exclusions. Use separate commands for those components.
    
    Examples:
        # Migrate all user-created rules
        sublime migrate rules --source-api-key KEY1 --dest-api-key KEY2
        
        # Migrate specific rules by ID
        sublime migrate rules --include-ids id1,id2 --source-api-key KEY1 --dest-api-key KEY2
        
        # Migrate only detection rules
        sublime migrate rules --type detection --source-api-key KEY1 --dest-api-key KEY2
        
        # Preview migration without making changes
        sublime migrate rules --dry-run --source-api-key KEY1 --dest-api-key KEY2
    """
    console = Console()
    results = {"status": "started", "message": "Migration of Rules"}
    
    if output_format == "table":
        console.print("[bold]Migration of Rules[/]")
    
    try:
        # Create API clients for source and destination
        source_client = get_api_client_from_env_or_args(source_api_key, source_region)
        dest_client = get_api_client_from_env_or_args(dest_api_key, dest_region, destination=True)
        
        # Build query parameters for API request
        params = {
            "include_deleted": "false",
            "in_feed": "false"  # Always exclude feed rules
        }
        
        if rule_type:
            params["type"] = rule_type
        
        # Fetch rules from source
        if output_format == "table":
            with console.status("[blue]Fetching rules from source instance...[/]"):
                source_response = source_client.get("/v1/rules", params=params)
        else:
            source_response = source_client.get("/v1/rules", params=params)
        
        # Extract rules from response
        if "rules" in source_response:
            source_rules = source_response["rules"]
        else:
            source_rules = source_response
        
        # Apply ID filters
        filtered_rules = filter_rules_by_id(source_rules, include_ids, exclude_ids)
        
        if not filtered_rules:
            message = "No rules to migrate after applying filters."
            if output_format == "table":
                console.print(f"[yellow]{message}[/]")
            else:
                results["status"] = "completed"
                results["message"] = message
                click.echo(json.dumps(results, indent=2))
            return
            
        rules_count_message = f"Found {len(filtered_rules)} rules to migrate."
        if output_format == "table":
            console.print(f"[bold]{rules_count_message}[/]")
        else:
            results["count"] = len(filtered_rules)
            results["message"] = rules_count_message
        
        # Fetch rules from destination for comparison
        if output_format == "table":
            with console.status("[blue]Fetching rules from destination instance...[/]"):
                dest_response = dest_client.get("/v1/rules", params=params)
        else:
            dest_response = dest_client.get("/v1/rules", params=params)
        
        # Extract destination rules
        if "rules" in dest_response:
            dest_rules = dest_response["rules"]
        else:
            dest_rules = dest_response
        
        # Compare and categorize rules
        new_rules, update_rules, skipped_rules = categorize_rules(filtered_rules, dest_rules)
        
        # Preview changes
        if not new_rules and not update_rules:
            message = "No rules to migrate (all rules were skipped or already exist)."
            if output_format == "table":
                console.print(f"[yellow]{message}[/]")
            else:
                results["status"] = "completed"
                results["message"] = message
                click.echo(json.dumps(results, indent=2))
            return
            
        # Prepare preview message
        preview_message = (
            f"\nPreparing to migrate {len(new_rules)} new rules and "
            f"update {len(update_rules)} existing rules."
        )
        
        if skipped_rules:
            preview_message += f" {len(skipped_rules)} rules will be skipped due to content differences."
            
        if output_format == "table":
            console.print(f"[bold]{preview_message}[/]")
        
            # Display preview table for rules
            rules_table = Table(title="Rules to Migrate")
            rules_table.add_column("ID", style="dim", no_wrap=True)
            rules_table.add_column("Name", style="green")
            rules_table.add_column("Type", style="blue")
            rules_table.add_column("Severity", style="cyan")
            rules_table.add_column("Status", style="yellow")
            
            for rule in new_rules:
                rules_table.add_row(
                    rule.get("id", ""),
                    rule.get("name", ""),
                    rule.get("type", ""),
                    rule.get("severity", ""),
                    "New"
                )
            
            for rule in update_rules:
                rules_table.add_row(
                    rule.get("id", ""),
                    rule.get("name", ""),
                    rule.get("type", ""),
                    rule.get("severity", ""),
                    "Update"
                )
            
            if skipped_rules:
                for rule in skipped_rules:
                    rules_table.add_row(
                        rule.get("id", ""),
                        rule.get("name", ""),
                        rule.get("type", ""),
                        rule.get("severity", ""),
                        "Skipped - Different content"
                    )
            
            console.print(rules_table)
        else:
            # JSON output
            results["new_rules"] = len(new_rules)
            results["update_rules"] = len(update_rules)
            results["skipped_rules"] = len(skipped_rules)
            results["rules_to_migrate"] = [
                {
                    "id": rule.get("id", ""),
                    "name": rule.get("name", ""),
                    "type": rule.get("type", ""),
                    "severity": rule.get("severity", ""),
                    "status": "New"
                }
                for rule in new_rules
            ] + [
                {
                    "id": rule.get("id", ""),
                    "name": rule.get("name", ""),
                    "type": rule.get("type", ""),
                    "severity": rule.get("severity", ""),
                    "status": "Update"
                }
                for rule in update_rules
            ]
            
            if skipped_rules:
                results["skipped_details"] = [
                    {
                        "id": rule.get("id", ""),
                        "name": rule.get("name", ""),
                        "type": rule.get("type", ""),
                        "severity": rule.get("severity", ""),
                        "status": "Skipped - Different content"
                    }
                    for rule in skipped_rules
                ]
        
        # If dry run, stop here
        if dry_run:
            dry_run_message = "DRY RUN: No changes were made."
            if output_format == "table":
                console.print(f"\n[yellow]{dry_run_message}[/]")
            else:
                results["status"] = "dry_run"
                results["message"] = dry_run_message
                click.echo(json.dumps(results, indent=2))
            return
        
        # Ask for confirmation
        if not yes and output_format == "table" and not Confirm.ask("\nDo you want to proceed with the migration?"):
            cancel_message = "Migration canceled by user."
            console.print(f"[yellow]{cancel_message}[/]")
            return
        
        # Migrate rules
        rule_results = migrate_rules(
            console, dest_client, new_rules, update_rules, dest_rules, output_format
        )
        
        # Display results
        results_message = (
            f"Migration completed: {rule_results['created']} rules created, "
            f"{rule_results['updated']} rules updated, "
            f"{rule_results['skipped']} rules skipped, "
            f"{rule_results['failed']} rules failed"
        )
        
        if output_format == "table":
            console.print(f"\n[bold green]{results_message}[/]")
        else:
            results["status"] = "completed"
            results["message"] = results_message
            results["details"] = rule_results
            click.echo(json.dumps(results, indent=2))
        
    except Exception as e:
        error_message = f"Error during migration: {str(e)}"
        if output_format == "table":
            console.print(f"[bold red]{error_message}[/]")
        else:
            results["status"] = "error"
            results["error"] = error_message
            click.echo(json.dumps(results, indent=2))


def filter_rules_by_id(rules: List[Dict], include_ids: Optional[str], exclude_ids: Optional[str]) -> List[Dict]:
    """Filter rules based on ID.
    
    Args:
        rules: List of rule objects
        include_ids: Comma-separated list of rule IDs to include
        exclude_ids: Comma-separated list of rule IDs to exclude
        
    Returns:
        List[Dict]: Filtered rule objects
    """
    filtered = rules
    
    # Filter by IDs
    if include_ids:
        ids = [id.strip() for id in include_ids.split(",")]
        filtered = [rule for rule in filtered if rule.get("id") in ids]
        
    if exclude_ids:
        ids = [id.strip() for id in exclude_ids.split(",")]
        filtered = [rule for rule in filtered if rule.get("id") not in ids]
    
    return filtered


def categorize_rules(source_rules: List[Dict], dest_rules: List[Dict]) -> tuple:
    """Categorize rules as new, update, or skipped based on matching.
    
    Matches rules based on name and source_md5 to ensure we're updating
    the correct rules. Rules with matching names but different source_md5
    will be skipped.
    
    Args:
        source_rules: List of source rule objects
        dest_rules: List of destination rule objects
        
    Returns:
        tuple: (new_rules, update_rules, skipped_rules)
    """
    # Create lookup dicts for destination rules
    dest_rule_by_name = {rule.get("name"): rule for rule in dest_rules}
    # print(dest_rule_by_name)
    dest_rule_by_name_and_md5 = {
        (rule.get("name"), rule.get("source_md5")): rule 
        for rule in dest_rules
    }
    print(dest_rule_by_name_and_md5)
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
            skipped_rules.append(rule)
        else:
            # No match - new rule
            new_rules.append(rule)
    
    return new_rules, update_rules, skipped_rules


def migrate_rules(console: Console, dest_client, new_rules: List[Dict], 
                 update_rules: List[Dict], existing_rules: List[Dict],
                 output_format: str) -> Dict:
    """Migrate rules to the destination instance.
    
    Args:
        console: Rich console for output
        dest_client: API client for the destination
        new_rules: List of new rules to create
        update_rules: List of rules to potentially update
        existing_rules: List of existing rules in the destination
        output_format: Output format
        
    Returns:
        Dict: Migration results
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
        if output_format == "table":
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Creating new rules..."),
                console=console
            ) as progress:
                task = progress.add_task("Creating", total=len(new_rules))
                
                for rule in new_rules:
                    process_new_rule(rule, dest_client, results, console)
                    progress.update(task, advance=1)
        else:
            # JSON output mode - no progress indicators
            for rule in new_rules:
                process_new_rule(rule, dest_client, results, console)
    
    # Process updates
    if update_rules:
        if output_format == "table":
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Updating existing rules..."),
                console=console
            ) as progress:
                task = progress.add_task("Updating", total=len(update_rules))
                
                for rule in update_rules:
                    process_update_rule(rule, dest_client, existing_map, results, console)
                    progress.update(task, advance=1)
        else:
            # JSON output mode - no progress indicators
            for rule in update_rules:
                process_update_rule(rule, dest_client, existing_map, results, console)
    
    return results


def process_new_rule(rule: Dict, dest_client, results: Dict, console: Console):
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
            "status": "created"
        })
        
    except Exception as e:
        results["failed"] += 1
        results["details"].append({
            "name": rule_name,
            "status": "failed",
            "reason": str(e)
        })
        console.print(f"[red]Failed to create rule '{rule_name}': {str(e)}[/]")


def process_update_rule(rule: Dict, dest_client, existing_map: Dict[str, Dict], 
                       results: Dict, console: Console):
    """Process a rule update for migration."""
    rule_name = rule.get("name", "")
    existing = existing_map.get(rule_name)
    
    if not existing:
        results["skipped"] += 1
        results["details"].append({
            "name": rule_name,
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
            "status": "updated"
        })
            
    except Exception as e:
        results["failed"] += 1
        results["details"].append({
            "name": rule_name,
            "status": "failed",
            "reason": str(e)
        })
        console.print(f"[red]Failed to update rule '{rule_name}': {str(e)}[/]")


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