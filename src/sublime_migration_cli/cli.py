"""Main CLI entry point and command groups."""
import click

from sublime_migration_cli.commands.get import get
from sublime_migration_cli.commands.migrate import migrate
from sublime_migration_cli.commands.report import report
from sublime_migration_cli.commands.export import export

@click.group()
@click.option("--api-key", help="API key for authentication")
@click.option("--region", help="Region to connect to (default: NA_EAST)")
@click.pass_context
def cli(ctx, api_key, region):
    """Sublime Security CLI - Interact with the Sublime Security Platform.
    
    Authentication can be provided via command-line options or environment 
    variables (SUBLIME_API_KEY and SUBLIME_REGION).
    """
    # Store API key and region in the context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["api_key"] = api_key
    ctx.obj["region"] = region

cli.add_command(get)
cli.add_command(migrate)
cli.add_command(report)
cli.add_command(export)

if __name__ == "__main__":
    cli()