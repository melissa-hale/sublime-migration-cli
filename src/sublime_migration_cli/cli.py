"""Main CLI entry point and command groups."""
import click

# from sublime_migration_cli.commands.actions import actions
# from sublime_cli.commands.auth import auth
# from sublime_cli.commands.lists import lists
# from sublime_cli.commands.feeds import feeds
# from sublime_cli.commands.exclusions import exclusions
# from sublime_cli.commands.rules import rules

from sublime_migration_cli.commands.get import get
from sublime_migration_cli.commands.migrate import migrate

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


# Add command groups
# cli.add_command(auth)
# cli.add_command(actions)
# cli.add_command(lists)
# cli.add_command(feeds)
# cli.add_command(exclusions)
# cli.add_command(rules)

cli.add_command(get)
cli.add_command(migrate)

if __name__ == "__main__":
    cli()
