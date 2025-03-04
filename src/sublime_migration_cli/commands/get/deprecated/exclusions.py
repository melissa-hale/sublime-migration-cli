"""Commands for working with Exclusions."""
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.models.exclusion import Exclusion


@click.group()
def exclusions():
    """Commands for working with Sublime Security Exclusions."""
    pass


@exclusions.command()
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--scope", help="Filter by scope (exclusion or rule_exclusion)")
@click.option("--active", is_flag=True, help="Show only active exclusions")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def all(api_key=None, region=None, scope=None, active=False, output_format="table"):
    """List all exclusions."""
    # Import here to avoid any naming conflicts
    import json as json_module
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Get exclusions from API
        response = client.get("/v1/exclusions")
        
        # The API returns a nested object with an "exclusions" key
        if "exclusions" in response:
            exclusions_data = response["exclusions"]
        else:
            exclusions_data = response  # Fallback if structure changes
        
        # Apply filters if requested
        if scope:
            exclusions_data = [ex for ex in exclusions_data if ex.get("scope") == scope]
        
        if active:
            exclusions_data = [ex for ex in exclusions_data if ex.get("active")]
        
        if output_format == "json":
            # Output as JSON if requested
            click.echo(json_module.dumps(exclusions_data, indent=2))
        else:
            # Convert to Exclusion objects for additional processing
            parsed_exclusions = [Exclusion.from_dict(ex) for ex in exclusions_data]
            
            # Create a table for displaying exclusions
            table = Table(title="Exclusions")
            table.add_column("ID", style="dim", no_wrap=True)
            table.add_column("Name", style="green")
            table.add_column("Scope", style="blue")
            table.add_column("Active", style="cyan", justify="center")
            table.add_column("Created By", style="magenta")
            table.add_column("Rule Name", style="yellow")
            
            # Add exclusions to the table
            for ex in parsed_exclusions:
                # Handle rule name column
                rule_name = ""
                if ex.originating_rule:
                    rule_name = ex.originating_rule.name
                
                # Handle created by
                created_by = ex.created_by_user_name if ex.created_by_user_name else ex.created_by_org_name
                
                table.add_row(
                    ex.id,
                    ex.name,
                    ex.scope,
                    "✓" if ex.active else "✗",
                    created_by or "Unknown",
                    rule_name
                )
            
            # Use Console's pager for pagination
            with console.pager():
                console.print(table)
                
                # Show filter info if filters were applied
                filters = []
                if scope:
                    filters.append(f"scope={scope}")
                if active:
                    filters.append("active=true")
                
                filter_text = f" (filtered by {', '.join(filters)})" if filters else ""
                console.print(f"Total: {len(parsed_exclusions)} exclusions{filter_text}")
        
    except Exception as e:
        error_message = str(e)
        if output_format == "json":
            click.echo(json_module.dumps({"error": error_message}, indent=2))
        else:
            console.print(f"[bold red]Error:[/] {error_message}")


@exclusions.command()
@click.argument("exclusion_id")
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def exclusion(exclusion_id, api_key=None, region=None, output_format="table"):
    """Get details of a specific exclusion."""
    # Import here to avoid any naming conflicts
    import json as json_module
    from rich.console import Console
    from rich.table import Table
    from rich.syntax import Syntax
    
    console = Console()
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Get exclusion details from API
        response = client.get(f"/v1/exclusions/{exclusion_id}")
        
        if output_format == "json":
            # Output as JSON if requested
            click.echo(json_module.dumps(response, indent=2))
        else:
            # Use Console's pager for pagination
            with console.pager():
                # Display exclusion details
                console.print(f"[bold]Exclusion Details:[/] {response.get('name')}")
                
                # Create a table for the exclusion metadata
                meta_table = Table(show_header=False)
                meta_table.add_column("Property", style="cyan")
                meta_table.add_column("Value")
                
                # Add metadata rows, handling special cases
                for key, value in response.items():
                    if key in ["source", "originating_rule"]:
                        # Skip these for special handling
                        continue
                    
                    if type(value) is dict or type(value) is list:
                        formatted_value = json_module.dumps(value, indent=2)
                    elif isinstance(value, bool):
                        formatted_value = "✓" if value else "✗"
                    else:
                        formatted_value = str(value)
                    
                    meta_table.add_row(key, formatted_value)
                
                console.print(meta_table)
                
                # If it's a rule exclusion, show originating rule details
                if response.get("originating_rule"):
                    rule = response["originating_rule"]
                    console.print(f"\n[bold]Originating Rule:[/] {rule.get('name')}")
                    
                    rule_table = Table(show_header=False)
                    rule_table.add_column("Property", style="green")
                    rule_table.add_column("Value", style="cyan")
                    
                    for key, value in rule.items():
                        if type(value) is dict or type(value) is list:
                            formatted_value = json_module.dumps(value, indent=2)
                        elif isinstance(value, bool):
                            formatted_value = "✓" if value else "✗"
                        else:
                            formatted_value = str(value)
                        
                        rule_table.add_row(key, formatted_value)
                    
                    console.print(rule_table)
                
                # Show source code with syntax highlighting
                if response.get("source"):
                    console.print(f"\n[bold]Source Query:[/]")
                    # Highlighting as a generic query language
                    syntax = Syntax(response["source"], "sql", theme="monokai", line_numbers=True)
                    console.print(syntax)
        
    except Exception as e:
        error_message = str(e)
        if output_format == "json":
            click.echo(json_module.dumps({"error": error_message}, indent=2))
        else:
            console.print(f"[bold red]Error:[/] {error_message}")