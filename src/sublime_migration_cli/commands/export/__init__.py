"""Export commands for Sublime CLI."""
import click

from sublime_migration_cli.commands.export.all import all_objects
from sublime_migration_cli.commands.export.actions import actions
from sublime_migration_cli.commands.export.rules import rules
from sublime_migration_cli.commands.export.lists import lists
from sublime_migration_cli.commands.export.exclusions import exclusions
from sublime_migration_cli.commands.export.feeds import feeds
from sublime_migration_cli.commands.export.organization import organization


@click.group()
def export():
    """Export configuration from Sublime Security instances.
    
    These commands allow you to export configuration objects (actions, rules, lists, etc.)
    from your Sublime Security instance to local files for version control.
    """
    pass


# Add subcommands to the export group
export.add_command(all_objects, name="all")
export.add_command(actions)
export.add_command(rules)
export.add_command(lists)
export.add_command(exclusions)
export.add_command(feeds)
export.add_command(organization)