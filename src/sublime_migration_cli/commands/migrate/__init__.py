"""Migration commands for Sublime CLI."""
import click

from sublime_migration_cli.commands.migrate.actions import actions
from sublime_migration_cli.commands.migrate.lists import lists
from sublime_migration_cli.commands.migrate.exclusions import exclusions
from sublime_migration_cli.commands.migrate.feeds import feeds
from sublime_migration_cli.commands.migrate.rules import rules
from sublime_migration_cli.commands.migrate.actions_to_rules import actions_to_rules
from sublime_migration_cli.commands.migrate.rule_exclusions import rule_exclusions
from sublime_migration_cli.commands.migrate.all import all_objects


@click.group()
def migrate():
    """Migrate configuration between Sublime Security instances.
    
    These commands allow you to copy configuration objects (actions, rules, lists, etc.)
    from one Sublime Security instance to another.
    """
    pass


# Add subcommands to the migrate group
migrate.add_command(actions)
migrate.add_command(lists)
migrate.add_command(exclusions)
migrate.add_command(feeds)
migrate.add_command(rules)
migrate.add_command(actions_to_rules, name="actions-to-rules")
migrate.add_command(rule_exclusions, name="rule-exclusions")

migrate.add_command(all_objects, name="all")