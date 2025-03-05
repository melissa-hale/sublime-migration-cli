"""Commands for migrating action associations to rules between Sublime Security instances."""
from typing import Dict, List, Optional, Set, Tuple
import json
import math

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Confirm
from rich.table import Table

from sublime_migration_cli.api.client import get_api_client_from_env_or_args


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
    console = Console()
    results = {"status": "started", "message": "Migration of Action Associations to Rules"}
    
    if output_format == "table":
        console.print("[bold]Migration of Action Associations to Rules[/]")
    
    try:
        # Create API clients for source and destination
        source_client = get_api_client_from_env_or_args(source_api_key, source_region)
        dest_client = get_api_client_from_env_or_args(dest_api_key, dest_region, destination=True)
        
        # Fetch all rules from source with pagination
        source_rules = fetch_all_rules(source_client, console, output_format, "source")
        
        # Apply rule ID filters
        filtered_rules = filter_rules_by_id(source_rules, include_rule_ids, exclude_rule_ids)
        
        # Filter to only rules with actions
        rules_with_actions = [rule for rule in filtered_rules if rule.get("actions") and len(rule.get("actions")) > 0]
        
        if not rules_with_actions:
            message = "No rules with actions to process after applying filters."
            if output_format == "table":
                console.print(f"[yellow]{message}[/]")
            else:
                results["status"] = "completed"
                results["message"] = message
                click.echo(json.dumps(results, indent=2))
            return
            
        rules_count_message = f"Found {len(rules_with_actions)} rules with actions to process."
        if output_format == "table":
            console.print(f"[bold]{rules_count_message}[/]")
        else:
            results["count"] = len(rules_with_actions)
            results["message"] = rules_count_message
        
        # Filter actions if specified
        if include_action_ids or exclude_action_ids:
            rules_with_actions = filter_actions_in_rules(
                rules_with_actions, include_action_ids, exclude_action_ids
            )
            
            if not rules_with_actions:
                message = "No rules with matching actions after applying action filters."
                if output_format == "table":
                    console.print(f"[yellow]{message}[/]")
                else:
                    results["status"] = "completed"
                    results["message"] = message
                    click.echo(json.dumps(results, indent=2))
                return
            
        # Enrich rules with action details
        rules_with_actions = enrich_rules_with_action_details(
            source_client, rules_with_actions, console, output_format
        )
        
        # Fetch all rules from destination with pagination
        dest_rules = fetch_all_rules(dest_client, console, output_format, "destination")
        
        # Create mapping of rules by name and md5 in destination
        dest_rules_map = {
            (rule.get("name"), rule.get("source_md5")): rule 
            for rule in dest_rules
        }
        
        # Fetch all actions from destination
        if output_format == "table":
            with console.status("[blue]Fetching actions from destination instance...[/]"):
                dest_actions = dest_client.get("/v1/actions")
        else:
            dest_actions = dest_client.get("/v1/actions")
        
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
        
        # Preview changes
        if not rules_to_update:
            message = "No rules with actions can be migrated (all were skipped)."
            if output_format == "table":
                console.print(f"[yellow]{message}[/]")
            else:
                results["status"] = "completed"
                results["message"] = message
                results["skipped_rules"] = len(skipped_rules)
                results["skipped_actions"] = len(skipped_actions)
                click.echo(json.dumps(results, indent=2))
            return
            
        # Prepare preview message
        total_actions = sum(len(rule["matched_actions"]) for rule in rules_to_update)
        preview_message = (
            f"\nPreparing to update {len(rules_to_update)} rules with {total_actions} action associations."
        )
        
        if skipped_rules or skipped_actions:
            preview_message += f" {len(skipped_rules)} rules and {len(skipped_actions)} action associations will be skipped."
            
        if output_format == "table":
            console.print(f"[bold]{preview_message}[/]")
        
            # Display preview table for rules to update
            rules_table = Table(title="Rules and Actions to Update")
            rules_table.add_column("Rule Name", style="green")
            rules_table.add_column("Rule ID in Destination", style="dim")
            rules_table.add_column("Action Names", style="blue")
            
            for rule in rules_to_update:
                action_names = ", ".join([action["name"] for action in rule["matched_actions"]])
                rules_table.add_row(
                    rule["source_rule"].get("name", ""),
                    rule["dest_rule"].get("id", ""),
                    action_names
                )
            
            console.print(rules_table)
            
            # Display skipped items if any
            if skipped_rules:
                skipped_table = Table(title="Skipped Rules")
                skipped_table.add_column("Rule Name", style="yellow")
                skipped_table.add_column("Reason", style="red")
                
                for item in skipped_rules:
                    skipped_table.add_row(
                        item["rule"].get("name", ""),
                        item["reason"]
                    )
                
                console.print(skipped_table)
            
            if skipped_actions:
                skipped_actions_table = Table(title="Skipped Actions")
                skipped_actions_table.add_column("Rule Name", style="yellow")
                skipped_actions_table.add_column("Action Name", style="yellow")
                skipped_actions_table.add_column("Reason", style="red")
                
                for item in skipped_actions:
                    skipped_actions_table.add_row(
                        item["rule"].get("name", ""),
                        item["action"].get("name", ""),
                        item["reason"]
                    )
                
                console.print(skipped_actions_table)
        else:
            # JSON output
            results["rules_to_update"] = len(rules_to_update)
            results["total_actions"] = total_actions
            results["skipped_rules"] = len(skipped_rules)
            results["skipped_actions"] = len(skipped_actions)
            
            results["rules_details"] = [
                {
                    "rule_name": rule["source_rule"].get("name", ""),
                    "dest_rule_id": rule["dest_rule"].get("id", ""),
                    "actions": [action["name"] for action in rule["matched_actions"]]
                }
                for rule in rules_to_update
            ]
            
            if skipped_rules:
                results["skipped_rules_details"] = [
                    {
                        "rule_name": item["rule"].get("name", ""),
                        "reason": item["reason"]
                    }
                    for item in skipped_rules
                ]
            
            if skipped_actions:
                results["skipped_actions_details"] = [
                    {
                        "rule_name": item["rule"].get("name", ""),
                        "action_name": item["action"].get("name", ""),
                        "reason": item["reason"]
                    }
                    for item in skipped_actions
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
        
        # Perform the migration
        migration_results = apply_action_associations(
            console, dest_client, rules_to_update, output_format
        )
        
        # Display results
        results_message = (
            f"Migration completed: {migration_results['updated']} rules updated with action associations, "
            f"{migration_results['skipped']} skipped, {migration_results['failed']} failed"
        )
        
        if output_format == "table":
            console.print(f"\n[bold green]{results_message}[/]")
        else:
            results["status"] = "completed"
            results["message"] = results_message
            results["details"] = migration_results
            click.echo(json.dumps(results, indent=2))
        
    except Exception as e:
        error_message = f"Error during migration: {str(e)}"
        if output_format == "table":
            console.print(f"[bold red]{error_message}[/]")
        else:
            results["status"] = "error"
            results["error"] = error_message
            click.echo(json.dumps(results, indent=2))


def fetch_all_rules(client, console, output_format, instance_name):
    """Fetch all rules from an instance with pagination.
    
    Args:
        client: API client for the instance
        console: Rich console for output
        output_format: Output format (table or json)
        instance_name: Name of the instance (for display)
        
    Returns:
        List[Dict]: All rules from the instance
    """
    all_rules = []
    offset = 0
    limit = 100
    total = None
    
    if output_format == "table":
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[bold blue]Fetching rules from {instance_name}..."),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            console=console,
            transient=True
        ) as progress:
            # Start with indeterminate progress until we know the total
            task = progress.add_task("Fetching", total=None)
            
            while True:
                # Fetch a page of rules
                response = client.get("/v1/rules", params={
                    "limit": limit,
                    "offset": offset,
                    "include_deleted": "false"
                })
                
                # Extract rules
                if "rules" in response:
                    page_rules = response["rules"]
                    page_count = response.get("count", len(page_rules))
                    page_total = response.get("total", page_count)
                else:
                    page_rules = response
                    page_count = len(page_rules)
                    page_total = page_count
                
                # Update total if we don't have it yet
                if total is None:
                    total = page_total
                    progress.update(task, total=total)
                
                # Add rules to our collection
                all_rules.extend(page_rules)
                progress.update(task, completed=len(all_rules))
                
                # Check if we've fetched all rules
                if len(all_rules) >= total or len(page_rules) == 0:
                    break
                
                # Update offset for next page
                offset += limit
    else:
        # JSON output mode - no progress indicators
        while True:
            # Fetch a page of rules
            response = client.get("/v1/rules", params={
                "limit": limit,
                "offset": offset,
                "include_deleted": "false"
            })
            
            # Extract rules
            if "rules" in response:
                page_rules = response["rules"]
                page_count = response.get("count", len(page_rules))
                page_total = response.get("total", page_count)
            else:
                page_rules = response
                page_count = len(page_rules)
                page_total = page_count
            
            # Update total if we don't have it yet
            if total is None:
                total = page_total
            
            # Add rules to our collection
            all_rules.extend(page_rules)
            
            # Check if we've fetched all rules
            if len(all_rules) >= total or len(page_rules) == 0:
                break
            
            # Update offset for next page
            offset += limit
    
    return all_rules


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


def enrich_rules_with_action_details(source_client, rules_with_actions: List[Dict], 
                                     console: Console, output_format: str) -> List[Dict]:
    """Fetch action details and enrich the action objects in the rules.
    
    Args:
        source_client: API client for the source instance
        rules_with_actions: List of rules with action references
        console: Rich console for output
        output_format: Output format
        
    Returns:
        List[Dict]: Enriched rules with detailed action information
    """
    # Count total actions to process
    total_actions = sum(len(rule.get("actions", [])) for rule in rules_with_actions)
    
    if output_format == "table":
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Fetching action details..."),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("Fetching", total=total_actions)
            
            # Create a copy of the rules to avoid modifying the originals
            enriched_rules = []
            
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
                    except Exception as e:
                        console.print(f"[yellow]Warning: Failed to fetch details for action ID {action_id}: {str(e)}[/]")
                        # Include the action anyway, it will be skipped during matching if type is missing
                        enriched_actions.append(action)
                    
                    progress.update(task, advance=1)
                
                # Update the rule with enriched actions
                rule_copy["actions"] = enriched_actions
                enriched_rules.append(rule_copy)
    else:
        # JSON output mode - no progress indicators
        enriched_rules = []
        
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
            print(action_name)
            print(action_type)
            
            # Find matching action in destination
            dest_action = dest_actions_map.get((action_name, action_type))
            print(dest_action)
            
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


def apply_action_associations(console: Console, dest_client, rules_to_update: List[Dict], 
                            output_format: str) -> Dict:
    """Apply action associations to rules in the destination.
    
    Args:
        console: Rich console for output
        dest_client: API client for the destination
        rules_to_update: List of rules to update with matched actions
        output_format: Output format
        
    Returns:
        Dict: Migration results
    """
    results = {
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "details": []
    }
    
    if output_format == "table":
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Updating rule action associations..."),
            console=console
        ) as progress:
            task = progress.add_task("Updating", total=len(rules_to_update))
            
            for rule_update in rules_to_update:
                process_rule_action_update(rule_update, dest_client, results, console)
                progress.update(task, advance=1)
    else:
        # JSON output mode - no progress indicators
        for rule_update in rules_to_update:
            process_rule_action_update(rule_update, dest_client, results, console)
    
    return results


def process_rule_action_update(rule_update: Dict, dest_client, results: Dict, console: Console):
    """Process a rule action association update.
    
    Args:
        rule_update: Rule update information with matched actions
        dest_client: API client for the destination
        results: Results dictionary to update
        console: Rich console for output
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
            "status": "updated",
            "actions": len(action_ids)
        })
        
    except Exception as e:
        results["failed"] += 1
        results["details"].append({
            "name": rule_name,
            "status": "failed",
            "reason": str(e)
        })
        console.print(f"[red]Failed to update rule '{rule_name}' with action associations: {str(e)}[/]")