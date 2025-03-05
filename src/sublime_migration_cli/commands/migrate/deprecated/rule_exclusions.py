"""Commands for migrating rule exclusions between Sublime Security instances."""
from typing import Dict, List, Optional, Set, Tuple
import json
import math
import re

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Confirm
from rich.table import Table

from sublime_migration_cli.api.client import get_api_client_from_env_or_args


# Regular expression patterns for different types of exclusions
EXCLUSION_PATTERNS = {
    "recipient_email": re.compile(r"any\(recipients\.to, \.email\.email == '([^']+)'\)"),
    "sender_email": re.compile(r"sender\.email\.email == '([^']+)'"),
    "sender_domain": re.compile(r"sender\.email\.domain\.domain == '([^']+)'")
}


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
    console = Console()
    results = {"status": "started", "message": "Migration of Rule Exclusions"}
    
    if output_format == "table":
        console.print("[bold]Migration of Rule Exclusions[/]")
    
    try:
        # Create API clients for source and destination
        source_client = get_api_client_from_env_or_args(source_api_key, source_region)
        dest_client = get_api_client_from_env_or_args(dest_api_key, dest_region, destination=True)
        
        # Fetch all rules from source with pagination
        source_rules = fetch_all_rules(source_client, console, output_format, "source")
        
        # Apply rule ID filters
        filtered_rules = filter_rules_by_id(source_rules, include_rule_ids, exclude_rule_ids)
        
        # Fetch detailed rule information including exclusions
        rules_with_details = fetch_rule_details(
            source_client, filtered_rules, console, output_format
        )
        
        # Filter to only rules with exclusions
        rules_with_exclusions = [
            rule for rule in rules_with_details 
            if rule.get("exclusions") and len(rule.get("exclusions")) > 0
        ]
        
        if not rules_with_exclusions:
            message = "No rules with exclusions found after applying filters."
            if output_format == "table":
                console.print(f"[yellow]{message}[/]")
            else:
                results["status"] = "completed"
                results["message"] = message
                click.echo(json.dumps(results, indent=2))
            return
            
        rules_count_message = f"Found {len(rules_with_exclusions)} rules with exclusions to process."
        if output_format == "table":
            console.print(f"[bold]{rules_count_message}[/]")
        else:
            results["count"] = len(rules_with_exclusions)
            results["message"] = rules_count_message
        
        # Fetch all rules from destination with pagination
        dest_rules = fetch_all_rules(dest_client, console, output_format, "destination")
        
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
        
        # Preview changes
        if not rules_to_update:
            message = "No rule exclusions can be migrated (all were skipped)."
            if output_format == "table":
                console.print(f"[yellow]{message}[/]")
            else:
                results["status"] = "completed"
                results["message"] = message
                results["skipped_rules"] = len(skipped_rules)
                click.echo(json.dumps(results, indent=2))
            return
            
        # Prepare preview message
        total_exclusions = sum(len(rule["parsed_exclusions"]) for rule in rules_to_update)
        preview_message = (
            f"\nPreparing to update {len(rules_to_update)} rules with {total_exclusions} exclusions."
        )
        
        if skipped_rules or skipped_exclusions:
            preview_message += f" {len(skipped_rules)} rules and {len(skipped_exclusions)} exclusions will be skipped."
            
        if output_format == "table":
            console.print(f"[bold]{preview_message}[/]")
        
            # Display preview table for rules to update
            rules_table = Table(title="Rules and Exclusions to Update")
            rules_table.add_column("Rule Name", style="green")
            rules_table.add_column("Rule ID in Destination", style="dim")
            rules_table.add_column("Exclusions", style="blue")
            
            for rule in rules_to_update:
                exclusion_strs = []
                for exc in rule["parsed_exclusions"]:
                    exc_type = list(exc.keys())[0]
                    exc_value = list(exc.values())[0]
                    exclusion_strs.append(f"{exc_type}: {exc_value}")
                    
                exclusions_text = "\n".join(exclusion_strs)
                rules_table.add_row(
                    rule["source_rule"].get("name", ""),
                    rule["dest_rule"].get("id", ""),
                    exclusions_text
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
            
            if skipped_exclusions:
                skipped_exc_table = Table(title="Skipped Exclusions")
                skipped_exc_table.add_column("Rule Name", style="yellow")
                skipped_exc_table.add_column("Exclusion", style="yellow")
                skipped_exc_table.add_column("Reason", style="red")
                
                for item in skipped_exclusions:
                    skipped_exc_table.add_row(
                        item["rule"].get("name", ""),
                        item["exclusion"],
                        item["reason"]
                    )
                
                console.print(skipped_exc_table)
        else:
            # JSON output
            results["rules_to_update"] = len(rules_to_update)
            results["total_exclusions"] = total_exclusions
            results["skipped_rules"] = len(skipped_rules)
            results["skipped_exclusions"] = len(skipped_exclusions)
            
            results["rules_details"] = [
                {
                    "rule_name": rule["source_rule"].get("name", ""),
                    "dest_rule_id": rule["dest_rule"].get("id", ""),
                    "exclusions": [
                        {k: v for k, v in exclusion.items()}
                        for exclusion in rule["parsed_exclusions"]
                    ]
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
            
            if skipped_exclusions:
                results["skipped_exclusions_details"] = [
                    {
                        "rule_name": item["rule"].get("name", ""),
                        "exclusion": item["exclusion"],
                        "reason": item["reason"]
                    }
                    for item in skipped_exclusions
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
        migration_results = apply_rule_exclusions(
            console, dest_client, rules_to_update, output_format
        )
        
        # Display results
        results_message = (
            f"Migration completed: {migration_results['updated']} rules updated with exclusions, "
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


def fetch_rule_details(client, rules: List[Dict], console: Console, output_format: str) -> List[Dict]:
    """Fetch detailed rule information including exclusions.
    
    Args:
        client: API client for the source instance
        rules: List of rule objects to fetch details for
        console: Rich console for output
        output_format: Output format
        
    Returns:
        List[Dict]: Rules with detailed information including exclusions
    """
    detailed_rules = []
    
    if output_format == "table":
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Fetching rule details..."),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("Fetching", total=len(rules))
            
            for rule in rules:
                rule_id = rule.get("id")
                try:
                    # Fetch detailed rule information
                    rule_details = client.get(f"/v1/rules/{rule_id}")
                    detailed_rules.append(rule_details)
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to fetch details for rule '{rule.get('name')}': {str(e)}[/]")
                    # Still include the rule without details
                    detailed_rules.append(rule)
                
                progress.update(task, advance=1)
    else:
        # JSON output mode - no progress indicators
        for rule in rules:
            rule_id = rule.get("id")
            try:
                # Fetch detailed rule information
                rule_details = client.get(f"/v1/rules/{rule_id}")
                detailed_rules.append(rule_details)
            except Exception as e:
                # Just skip the rule
                pass
    
    return detailed_rules


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


def apply_rule_exclusions(console: Console, dest_client, rules_to_update: List[Dict], 
                        output_format: str) -> Dict:
    """Apply exclusions to rules in the destination.
    
    Args:
        console: Rich console for output
        dest_client: API client for the destination
        rules_to_update: List of rules to update with parsed exclusions
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
            TextColumn("[bold blue]Updating rule exclusions..."),
            console=console
        ) as progress:
            task = progress.add_task("Updating", total=len(rules_to_update))
            
            for rule_update in rules_to_update:
                process_rule_exclusion_update(rule_update, dest_client, results, console)
                progress.update(task, advance=1)
    else:
        # JSON output mode - no progress indicators
        for rule_update in rules_to_update:
            process_rule_exclusion_update(rule_update, dest_client, results, console)
    
    return results


def process_rule_exclusion_update(rule_update: Dict, dest_client, results: Dict, console: Console):
    """Process a rule exclusion update.
    
    Args:
        rule_update: Rule update information with parsed exclusions
        dest_client: API client for the destination
        results: Results dictionary to update
        console: Rich console for output
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
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to add exclusion {exclusion} to rule '{rule_name}': {str(e)}[/]")
        
        if succeeded > 0:
            results["updated"] += 1
            results["details"].append({
                "name": rule_name,
                "status": "updated",
                "exclusions_added": succeeded,
                "exclusions_failed": len(exclusions) - succeeded
            })
        else:
            results["failed"] += 1
            results["details"].append({
                "name": rule_name,
                "status": "failed",
                "reason": "All exclusions failed to apply"
            })
        
    except Exception as e:
        results["failed"] += 1
        results["details"].append({
            "name": rule_name,
            "status": "failed",
            "reason": str(e)
        })
        console.print(f"[red]Failed to update rule '{rule_name}' with exclusions: {str(e)}[/]")