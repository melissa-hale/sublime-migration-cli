"""Commands for working with Feeds."""
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.models.feed import Feed


@click.group()
def feeds():
    """Commands for working with Sublime Security Feeds."""
    pass


@feeds.command()
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def all(api_key=None, region=None, output_format="table"):
    """List all feeds."""
    # Import here to avoid any naming conflicts
    import json as json_module
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Get feeds from API
        response = client.get("/v1/feeds")
        
        # The API returns a nested object with a "feeds" key
        if "feeds" in response:
            feeds_data = response["feeds"]
        else:
            feeds_data = response  # Fallback if structure changes
        
        if output_format == "json":
            # Output as JSON if requested
            click.echo(json_module.dumps(feeds_data, indent=2))
        else:
            # Convert to Feed objects for additional processing
            parsed_feeds = [Feed.from_dict(feed) for feed in feeds_data]
            
            # Create a table for displaying feeds
            table = Table(title="Feeds")
            table.add_column("ID", style="dim", no_wrap=True)
            table.add_column("Name", style="green")
            table.add_column("Branch", style="blue")
            table.add_column("System", style="cyan", justify="center")
            table.add_column("Rules", style="magenta", justify="right")
            table.add_column("Auto Update", style="yellow", justify="center")
            
            # Add feeds to the table
            for feed in parsed_feeds:
                total_rules = feed.summary.total if feed.summary else "N/A"
                
                table.add_row(
                    feed.id,
                    feed.name,
                    feed.git_branch,
                    "✓" if feed.is_system else "✗",
                    str(total_rules),
                    "✓" if feed.auto_update_rules else "✗"
                )
            
            # Use Console's pager for pagination
            with console.pager():
                console.print(table)
                console.print(f"Total: {len(feeds_data)} feeds")
        
    except Exception as e:
        error_message = str(e)
        if output_format == "json":
            click.echo(json_module.dumps({"error": error_message}, indent=2))
        else:
            console.print(f"[bold red]Error:[/] {error_message}")


@feeds.command()
@click.argument("feed_id")
@click.option("--api-key", help="API key to use")
@click.option("--region", help="Region to connect to")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
def feed(feed_id, api_key=None, region=None, output_format="table"):
    """Get details of a specific feed."""
    # Import here to avoid any naming conflicts
    import json as json_module
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    
    try:
        # Create client from args or environment variables
        client = get_api_client_from_env_or_args(api_key, region)
        
        # Get feed details from API
        response = client.get(f"/v1/feeds/{feed_id}")
        
        if output_format == "json":
            # Output as JSON if requested
            click.echo(json_module.dumps(response, indent=2))
        else:
            # Use Console's pager for pagination
            with console.pager():
                # Display feed details
                console.print(f"[bold]Feed Details:[/] {response.get('name')}")
                
                # Create a table for the feed metadata
                meta_table = Table(show_header=False)
                meta_table.add_column("Property", style="cyan")
                meta_table.add_column("Value")
                
                # Add metadata rows, handling special cases
                for key, value in response.items():
                    if key == "summary":
                        # Skip summary for now, we'll display it separately
                        continue
                    
                    if type(value) is dict or type(value) is list:
                        formatted_value = json_module.dumps(value, indent=2)
                    elif isinstance(value, bool):
                        formatted_value = "✓" if value else "✗"
                    else:
                        formatted_value = str(value)
                    
                    meta_table.add_row(key, formatted_value)
                
                console.print(meta_table)
                
                # If summary exists, display it in a separate table
                summary = response.get("summary")
                if summary:
                    console.print(f"\n[bold]Feed Summary:[/]")
                    
                    summary_table = Table(show_header=False)
                    summary_table.add_column("Metric", style="green")
                    summary_table.add_column("Value", style="cyan")
                    
                    for metric, value in summary.items():
                        summary_table.add_row(metric, str(value))
                    
                    console.print(summary_table)
        
    except Exception as e:
        error_message = str(e)
        if output_format == "json":
            click.echo(json_module.dumps({"error": error_message}, indent=2))
        else:
            console.print(f"[bold red]Error:[/] {error_message}")