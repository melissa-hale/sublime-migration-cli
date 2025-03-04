"""Commands for working with Lists."""
from typing import Optional, List as PyList
from concurrent.futures import ThreadPoolExecutor

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import json as json_module

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.models.list import List


@click.group()
def lists():
    """Commands for working with Sublime Security Lists."""
    pass


@lists.command()
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--type", "list_type", help="Filter by list type (string or user_group)")
@click.option("--fetch-details", is_flag=True, help="Fetch full details for accurate entry counts")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def all(api_key=None, region=None, list_type=None, fetch_details=False, output_format="table"):
    """List all lists.
    
    By default, retrieves both string and user_group list types.
    Use --type to filter for a specific type.
    Use --fetch-details to get accurate entry counts (slower but more accurate).
    """
    console = Console()
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Prepare to store all lists
        all_lists = []
        
        # Determine which list types to retrieve
        list_types = []
        if list_type:
            list_types = [list_type]
        else:
            # Default: get both types
            list_types = ["string", "user_group"]
            
        # Get lists for each type
        for lt in list_types:
            try:
                response = client.get("/v1/lists", params={"list_types": lt})
                all_lists.extend(response)
            except Exception as e:
                console.print(f"[yellow]Warning:[/] Failed to get lists of type '{lt}': {str(e)}")
        
        # If requested, fetch full details for each list to get accurate entry counts
        if fetch_details and all_lists and output_format != "json":
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Fetching list details..."),
                console=console,
                transient=True
            ) as progress:
                progress.add_task("Fetching", total=None)
                
                # Function to fetch individual list details
                def fetch_list_details(list_item):
                    try:
                        list_id = list_item["id"]
                        details = client.get(f"/v1/lists/{list_id}")
                        # Update the original list item with accurate information
                        list_item["entries"] = details.get("entries", [])
                        list_item["entry_count"] = details.get("entry_count", 0)
                        return list_item
                    except Exception:
                        # If fetching details fails, return original item
                        return list_item
                
                # Use ThreadPoolExecutor to fetch details in parallel
                with ThreadPoolExecutor(max_workers=5) as executor:
                    all_lists = list(executor.map(fetch_list_details, all_lists))
        
        if output_format == "json":
            # Output as JSON if requested
            click.echo(json_module.dumps(all_lists, indent=2))
        else:
            # Convert to List objects for additional processing
            lists_data = [List.from_dict(list_item) for list_item in all_lists]
            
            # Create a table for displaying lists
            accuracy_note = " (approximate)" if not fetch_details else ""
            table = Table(title="Lists")
            table.add_column("ID", style="dim", no_wrap=True)
            table.add_column("Name", style="green")
            table.add_column("Type", style="blue")
            table.add_column(f"Entry Count{accuracy_note}", style="cyan", justify="right")
            table.add_column("Created By", style="magenta")
            
            # Add lists to the table
            for list_item in lists_data:
                table.add_row(
                    list_item.id, 
                    list_item.name, 
                    list_item.entry_type,
                    str(list_item.entry_count),
                    list_item.created_by_user_name
                )
            
            # Use Console's pager for pagination
            with console.pager():
                console.print(table)
                console.print(f"Total: {len(all_lists)} lists")
                if not fetch_details:
                    console.print("[italic]Note: Entry counts are approximate. Use --fetch-details for accurate counts.[/]")
        
    except Exception as e:
        error_message = str(e)
        if output_format == "json":
            click.echo(json_module.dumps({"error": error_message}, indent=2))
        else:
            console.print(f"[bold red]Error:[/] {error_message}")


@lists.command()
@click.argument("list_id")
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def list(list_id, api_key=None, region=None, output_format="table"):
    """Get details of a specific list, including entries."""
    console = Console()
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Get list details from API
        response = client.get(f"/v1/lists/{list_id}")
        
        if output_format == "json":
            # Output as JSON if requested
            click.echo(json_module.dumps(response, indent=2))
        else:
            # Use Console's pager for pagination
            with console.pager():
                # Display list details
                console.print(f"[bold]List Details:[/] {response.get('name')}")
                
                # Create a table for the list metadata
                meta_table = Table(show_header=False)
                meta_table.add_column("Property", style="cyan")
                meta_table.add_column("Value")
                
                # Add metadata rows, excluding entries
                for key, value in response.items():
                    if key != "entries":  # Skip entries for now
                        if type(value) is dict or type(value) is list:
                            formatted_value = json_module.dumps(value, indent=2)
                        else:
                            formatted_value = str(value)
                        
                        meta_table.add_row(key, formatted_value)
                
                console.print(meta_table)
                
                # If entries exist, display them in a separate table
                entries = response.get("entries")
                if entries:
                    console.print(f"\n[bold]List Entries:[/] ({len(entries)} items)")
                    
                    entries_table = Table()
                    entries_table.add_column("Entry", style="green")
                    
                    for entry in entries:
                        entries_table.add_row(str(entry))
                    
                    console.print(entries_table)
        
    except Exception as e:
        error_message = str(e)
        if output_format == "json":
            click.echo(json_module.dumps({"error": error_message}, indent=2))
        else:
            console.print(f"[bold red]Error:[/] {error_message}")