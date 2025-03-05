"""Commands for working with Actions."""
import json
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.models.action import Action


@click.group()
def actions():
    """Commands for working with Sublime Security Actions."""
    pass


@actions.command()
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--json", is_flag=True, help="Output in JSON format")
def all(api_key: Optional[str], region: Optional[str], json: bool):
    """List all actions."""
    console = Console()
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Get actions from API
        response = client.get("/v1/actions")
        
        # Convert to Action objects if needed for additional processing
        actions_list = [Action.from_dict(action) for action in response]
        
        if json:
            # Output as JSON if requested
            click.echo(json.dumps(response, indent=2))
        else:
            # Create a table for displaying actions
            table = Table(title="Actions")
            table.add_column("ID", style="dim")
            table.add_column("Name", style="green")
            table.add_column("Type", style="cyan")
            table.add_column("Active", style="magenta")
            
            # Add actions to the table
            for action in actions_list:
                table.add_row(
                    action.id, 
                    action.name, 
                    action.type,
                    "✓" if action.active else "✗"
                )
            
            # Display the table
            console.print(table)
            console.print(f"Total: {len(actions_list)} actions")
        
    except Exception as e:
        if json:
            click.echo(json.dumps({"error": str(e)}, indent=2))
        else:
            console.print(f"[bold red]Error:[/] {str(e)}")


@actions.command()
@click.argument("action_id")
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", 
              help="Output format (table or json)")
def action(action_id, api_key=None, region=None, output_format="table"):
    """Get details of a specific action."""
    # Import here to avoid any naming conflicts
    import json as json_module
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Get action details from API
        response = client.get(f"/v1/actions/{action_id}")
        
        if output_format == "json":
            # Output as JSON if requested
            click.echo(json_module.dumps(response, indent=2))
        else:
            # Display action details
            console.print(f"[bold]Action Details:[/] {response.get('name')}")
            
            # Convert to table rows for better display
            table = Table(show_header=False)
            table.add_column("Property", style="cyan")
            table.add_column("Value")
            
            for key, value in response.items():
                # Handle different value types
                if type(value) is dict or type(value) is list:
                    formatted_value = json_module.dumps(value, indent=2)
                else:
                    formatted_value = str(value)
                
                table.add_row(key, formatted_value)
            
            console.print(table)
        
    except Exception as e:
        error_message = str(e)
        if output_format == "json":
            click.echo(json_module.dumps({"error": error_message}, indent=2))
        else:
            console.print(f"[bold red]Error:[/] {error_message}")