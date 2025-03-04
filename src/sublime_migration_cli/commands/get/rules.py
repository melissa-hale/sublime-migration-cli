"""Commands for working with Rules."""
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.syntax import Syntax

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.models.rule import Rule


@click.group()
def rules():
    """Commands for working with Sublime Security Rules."""
    pass


@rules.command()
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--type", "rule_type", type=click.Choice(["detection", "triage"]),
              help="Filter by rule type (detection or triage)")
@click.option("--active", is_flag=True, help="Show only active rules")
@click.option("--feed", help="Filter by feed ID (returns rules from this feed)")
@click.option("--in-feed/--not-in-feed", default=None, 
              help="Filter to show only rules in feeds or not in feeds")
@click.option("--limit", type=int, default=100, 
              help="Number of rules to fetch per page (adjust based on API limitations)")
@click.option("--show-exclusions", is_flag=True, 
              help="Show exclusion information (slower, requires additional API calls)")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def all(api_key=None, region=None, rule_type=None, active=False, feed=None, 
         in_feed=None, limit=100, show_exclusions=False, output_format="table"):
    """List all rules with pagination and filtering options.
    
    Filters available:
      --type: Show only detection or triage rules
      --active: Show only active rules
      --feed: Show only rules from a specific feed (provide feed ID)
      --in-feed/--not-in-feed: Show rules that are in feeds or not in feeds
    """
    # Import here to avoid any naming conflicts
    import json as json_module
    
    console = Console()
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Build query parameters for filtering
        params = {
            "limit": limit
        }
        
        if rule_type:
            params["type"] = rule_type
            
        if feed:
            params["feed"] = feed
        
        if in_feed is not None:
            params["in_feed"] = "true" if in_feed else "false"
            
        # Initialize variables for pagination
        all_rules = []
        offset = 0
        total_rules = None
        
        # Create progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Fetching rules..."),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            console=console,
            transient=True
        ) as progress:
            # We don't know the total yet, so start with an indefinite progress
            fetch_task = progress.add_task("Fetching", total=None)
            
            # Fetch first page to get the total
            page_params = params.copy()
            page_params["offset"] = offset
            first_page = client.get("/v1/rules", params=page_params)
            
            # Extract total count and update progress
            count = first_page.get("count", 0)
            total_rules = first_page.get("total", 0)
            all_rules.extend(first_page.get("rules", []))
            
            # Now that we know the total, update the progress bar
            progress.update(fetch_task, total=total_rules, completed=len(all_rules))
            
            # Fetch remaining pages if needed
            while len(all_rules) < total_rules:
                offset += limit
                page_params["offset"] = offset
                
                page = client.get("/v1/rules", params=page_params)
                page_rules = page.get("rules", [])
                all_rules.extend(page_rules)
                
                # Update progress
                progress.update(fetch_task, completed=len(all_rules))
        
        # Apply active filter client-side if requested
        # (We could add this to the API params, but this makes it consistent with other filters)
        rules_data = all_rules
        if active:
            rules_data = [rule for rule in rules_data if rule.get("active")]
            
        # If showing exclusions, fetch detailed info for each rule
        if show_exclusions and rules_data and output_format != "json":
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Fetching rule details for exclusion information..."),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console,
                transient=True
            ) as progress:
                task = progress.add_task("Fetching", total=len(rules_data))
                
                # Function to fetch individual rule details
                def fetch_rule_details(rule_item):
                    try:
                        rule_id = rule_item["id"]
                        details = client.get(f"/v1/rules/{rule_id}")
                        # Update the has_exclusions flag if exclusions exist
                        rule_item["exclusions"] = details.get("exclusions", [])
                        return rule_item
                    except Exception:
                        # If fetching details fails, return original item
                        return rule_item
                    finally:
                        # Always update progress
                        progress.update(task, advance=1)
                
                # Use ThreadPoolExecutor to fetch details in parallel
                with ThreadPoolExecutor(max_workers=5) as executor:
                    rules_data = list(executor.map(fetch_rule_details, rules_data))
        
        if output_format == "json":
            # Output as JSON if requested
            click.echo(json_module.dumps(rules_data, indent=2))
        else:
            # Convert to Rule objects for additional processing
            parsed_rules = [Rule.from_dict(rule) for rule in rules_data]
            
            # Create a table for displaying rules
            table = Table(title=f"Rules{' (with exclusion information)' if show_exclusions else ''}")
            table.add_column("ID", style="dim", no_wrap=True)
            table.add_column("Name", style="green")
            table.add_column("Type", style="blue")
            table.add_column("Severity", style="magenta")
            table.add_column("Active", style="cyan", justify="center")
            table.add_column("Actions", style="yellow", justify="right")
            
            if show_exclusions:
                table.add_column("Exclusions", style="red", justify="center")
            
            # Add rules to the table
            for rule in parsed_rules:
                # Count actions
                action_count = len([a for a in rule.actions if a.active])
                
                # Prepare row data
                row_data = [
                    rule.id,
                    rule.name,
                    rule.type,
                    rule.severity or "N/A",
                    "✓" if rule.active else "✗",
                    str(action_count)
                ]
                
                # Add exclusions column if requested
                if show_exclusions:
                    row_data.append("✓" if rule.has_exclusions else "")
                
                table.add_row(*row_data)
            
            # Use Console's pager for pagination
            with console.pager():
                console.print(table)
                
                # Show filter info if filters were applied
                filters = []
                if rule_type:
                    filters.append(f"type={rule_type}")
                if active:
                    filters.append("active=true")
                if feed:
                    filters.append(f"feed={feed}")
                if in_feed is not None:
                    filters.append(f"in_feed={'true' if in_feed else 'false'}")
                
                filter_text = f" (filtered by {', '.join(filters)})" if filters else ""
                console.print(f"Total: {len(parsed_rules)} rules{filter_text}")
                if total_rules and len(parsed_rules) < total_rules:
                    console.print(f"[italic](showing {len(parsed_rules)} of {total_rules} total rules after filtering)[/]")
        
    except Exception as e:
        error_message = str(e)
        if output_format == "json":
            click.echo(json_module.dumps({"error": error_message}, indent=2))
        else:
            console.print(f"[bold red]Error:[/] {error_message}")


@rules.command()
@click.argument("rule_id")
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def rule(rule_id, api_key=None, region=None, output_format="table"):
    """Get details of a specific rule."""
    # Import here to avoid any naming conflicts
    import json as json_module
    
    console = Console()
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Get rule details from API
        response = client.get(f"/v1/rules/{rule_id}")
        
        if output_format == "json":
            # Output as JSON if requested
            click.echo(json_module.dumps(response, indent=2))
        else:
            # Use Console's pager for pagination
            with console.pager():
                # Convert to Rule object
                rule = Rule.from_dict(response)
                
                # Display rule details
                console.print(f"[bold]Rule:[/] {rule.name}")
                
                # Main info section
                console.print("\n[bold]Basic Information:[/]")
                basic_table = Table(show_header=False)
                basic_table.add_column("Property", style="cyan")
                basic_table.add_column("Value")
                
                basic_fields = [
                    ("ID", rule.id),
                    ("Type", rule.full_type),
                    ("Severity", rule.severity or "N/A"),
                    ("Active", "✓" if rule.active else "✗"),
                    ("Passive", "✓" if rule.passive else "✗"),
                    ("Immutable", "✓" if rule.immutable else "✗"),
                    ("Description", rule.description or "N/A"),
                ]
                
                for field, value in basic_fields:
                    basic_table.add_row(field, str(value))
                
                console.print(basic_table)
                
                # Actions section
                if rule.actions:
                    console.print("\n[bold]Associated Actions:[/]")
                    actions_table = Table()
                    actions_table.add_column("ID", style="dim")
                    actions_table.add_column("Name", style="green")
                    actions_table.add_column("Active", style="cyan", justify="center")
                    
                    for action in rule.actions:
                        actions_table.add_row(
                            action.id,
                            action.name,
                            "✓" if action.active else "✗"
                        )
                    
                    console.print(actions_table)
                
                # Exclusions section
                if rule.exclusions:
                    console.print("\n[bold]Rule Exclusions:[/]")
                    exclusions_table = Table()
                    exclusions_table.add_column("Exclusion", style="green")
                    
                    for exclusion in rule.exclusions:
                        exclusions_table.add_row(exclusion)
                    
                    console.print(exclusions_table)
                
                # Source query section
                console.print("\n[bold]Source Query:[/]")
                source_syntax = Syntax(rule.source, "sql", theme="monokai", line_numbers=True)
                console.print(source_syntax)
                
                # Additional metadata
                if any([rule.authors, rule.references, rule.tags]):
                    console.print("\n[bold]Additional Metadata:[/]")
                    meta_table = Table(show_header=False)
                    meta_table.add_column("Property", style="cyan")
                    meta_table.add_column("Value")
                    
                    if rule.authors:
                        meta_table.add_row("Authors", ", ".join(rule.authors))
                    
                    if rule.references:
                        meta_table.add_row("References", "\n".join(rule.references))
                    
                    if rule.tags:
                        meta_table.add_row("Tags", ", ".join(rule.tags))
                    
                    console.print(meta_table)
        
    except Exception as e:
        error_message = str(e)
        if output_format == "json":
            click.echo(json_module.dumps({"error": error_message}, indent=2))
        else:
            console.print(f"[bold red]Error:[/] {error_message}")