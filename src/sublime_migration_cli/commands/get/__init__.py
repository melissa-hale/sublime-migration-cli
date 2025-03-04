"""Main CLI entry point and command groups."""
import click

from sublime_migration_cli.commands.get.actions import actions
from sublime_migration_cli.commands.get.auth import auth
from sublime_migration_cli.commands.get.lists import lists
from sublime_migration_cli.commands.get.feeds import feeds
from sublime_migration_cli.commands.get.exclusions import exclusions
from sublime_migration_cli.commands.get.rules import rules

@click.group()
def get():
    """Get configuration between Sublime Security instances.
    
    These commands allow you to get configuration objects (actions, rules, lists, etc.)
    from your Sublime Security instance.
    """
    pass

get.add_command(actions)
get.add_command(auth)
get.add_command(lists)
get.add_command(feeds)
get.add_command(exclusions)
get.add_command(rules)