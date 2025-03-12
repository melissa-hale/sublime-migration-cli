"""Report commands for Sublime CLI."""
import click

from sublime_migration_cli.commands.report.compare import compare


@click.group()
def report():
    """Generate reports about Sublime Security instances.
    
    These commands allow you to analyze and compare configuration objects
    between different Sublime Security instances.
    """
    pass


# Add subcommands to the report group
report.add_command(compare)