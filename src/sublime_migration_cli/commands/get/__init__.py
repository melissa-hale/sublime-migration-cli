"""Migration commands for Sublime CLI."""
import click

from sublime_migration_cli.commands.get.actions import actions
from sublime_migration_cli.commands.get.lists import lists
from sublime_migration_cli.commands.get.exclusions import exclusions
from sublime_migration_cli.commands.get.feeds import feeds
from sublime_migration_cli.commands.get.rules import rules


@click.group()
def get():
    """Get configuration in a Sublime Security instance.
    
    These commands allow you to get configuration objects (actions, rules, lists, etc.)
    from your Sublime Security instance.
    """
    pass


# Add subcommands to the get group
get.add_command(actions)
get.add_command(lists)
get.add_command(exclusions)
get.add_command(feeds)
get.add_command(rules)