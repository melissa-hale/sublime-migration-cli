"""Authentication commands for Sublime CLI."""
import click
from rich.console import Console
from rich.table import Table

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.api.regions import get_regions_for_display


@click.group()
def auth():
    """Authentication and connection commands."""
    pass


@auth.command()
@click.option("--api-key", help="API key to use for validation")
@click.option("--region", help="Region to connect to")
def verify(api_key, region):
    """Verify API key is valid by making a test API call."""
    console = Console()
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Test the connection by getting user info
        user_info = client.get("/v1/me")
        
        # Display success message
        console.print(f"[bold green]Authentication successful![/]")
        console.print(f"Connected to: [bold]{client.region.description}[/]")
        console.print(f"Organization: [bold]{user_info.get('org_name', 'Unknown')}[/]")
        console.print(f"Username: [bold]{user_info.get('first_name', '')} {user_info.get('last_name', '')}[/]")
        
    except ValueError as e:
        console.print(f"[bold red]Configuration Error:[/] {str(e)}")
        
    except Exception as e:
        console.print(f"[bold red]Authentication Failed:[/] {str(e)}")


@auth.command()
def regions():
    """List available regions."""
    console = Console()
    
    # Create a table for displaying regions
    table = Table(title="Available Regions")
    table.add_column("Code", style="cyan")
    table.add_column("Description", style="green")
    
    # Add regions to the table
    for code, description in get_regions_for_display():
        table.add_row(code, description)
    
    # Display the table
    console.print(table)
