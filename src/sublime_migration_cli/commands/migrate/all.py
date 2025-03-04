"""Command to migrate all components between Sublime Security instances."""
from typing import Dict, List, Optional
import json
import time

import click
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table
from rich.panel import Panel

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.commands.migrate.actions import actions
from sublime_migration_cli.commands.migrate.lists import lists
from sublime_migration_cli.commands.migrate.exclusions import exclusions
from sublime_migration_cli.commands.migrate.feeds import feeds
from sublime_migration_cli.commands.migrate.rules import rules
from sublime_migration_cli.commands.migrate.actions_to_rules import actions_to_rules
from sublime_migration_cli.commands.migrate.rule_exclusions import rule_exclusions


@click.command()
@click.option("--source-api-key", help="API key for the source instance")
@click.option("--source-region", help="Region of the source instance")
@click.option("--dest-api-key", help="API key for the destination instance")
@click.option("--dest-region", help="Region of the destination instance")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
@click.option("--skip", multiple=True, 
              type=click.Choice(["actions", "lists", "exclusions", "feeds", "rules", "actions-to-rules", "rule-exclusions"]),
              help="Skip specific migration steps (can specify multiple times)")
def all_objects(source_api_key, source_region, dest_api_key, dest_region,
        dry_run, yes, output_format, skip):
    """Migrate all components between Sublime Security instances.
    
    This command migrates all supported components in the correct order to maintain dependencies:
    1. Actions (independent objects)
    2. Lists (independent objects)
    3. Exclusions (independent objects)
    4. Feeds (independent objects)
    5. Rules (base rules without actions or exclusions)
    6. Actions to Rules (associates actions with rules)
    7. Rule Exclusions (adds exclusions to rules)
    
    Examples:
        # Migrate everything with a preview and confirmation for each step
        sublime migrate all --source-api-key KEY1 --dest-api-key KEY2
        
        # Migrate everything without prompts
        sublime migrate all --source-api-key KEY1 --dest-api-key KEY2 --yes
        
        # Preview migration without making changes
        sublime migrate all --dry-run --source-api-key KEY1 --dest-api-key KEY2
        
        # Skip certain steps
        sublime migrate all --skip feeds --skip rule-exclusions --source-api-key KEY1 --dest-api-key KEY2
    """
    console = Console()
    results = {"status": "started", "message": "Migration of All Components", "steps": {}}
    
    if output_format == "table":
        console.print(Panel.fit(
            "[bold]Migration of All Components[/]\n\n"
            "This will migrate all components in the following order:\n"
            "1. Actions\n"
            "2. Lists\n"
            "3. Exclusions\n"
            "4. Feeds\n"
            "5. Rules\n"
            "6. Actions to Rules\n"
            "7. Rule Exclusions",
            title="Migration Process",
            border_style="green"
        ))
    
    try:
        # Create API clients for validation
        source_client = get_api_client_from_env_or_args(source_api_key, source_region)
        dest_client = get_api_client_from_env_or_args(dest_api_key, dest_region, destination=True)
        
        # Validate connection
        if output_format == "table":
            with console.status("[blue]Validating connection to source and destination..."):
                source_info = source_client.get("/v1/me")
                dest_info = dest_client.get("/v1/me")
                
                console.print("[green]✓[/] Connected to source instance: "
                             f"[bold]{source_info.get('org_name', 'Unknown')}[/] "
                             f"({source_info.get('email_address', 'Unknown')})")
                
                console.print("[green]✓[/] Connected to destination instance: "
                             f"[bold]{dest_info.get('org_name', 'Unknown')}[/] "
                             f"({dest_info.get('email_address', 'Unknown')})")
        
        # Define migration steps
        migration_steps = [
            {"name": "actions", "title": "Actions", "command": actions, "skipped": "actions" in skip},
            {"name": "lists", "title": "Lists", "command": lists, "skipped": "lists" in skip},
            {"name": "exclusions", "title": "Exclusions", "command": exclusions, "skipped": "exclusions" in skip},
            {"name": "feeds", "title": "Feeds", "command": feeds, "skipped": "feeds" in skip},
            {"name": "rules", "title": "Rules", "command": rules, "skipped": "rules" in skip},
            {"name": "actions-to-rules", "title": "Actions to Rules", "command": actions_to_rules, "skipped": "actions-to-rules" in skip},
            {"name": "rule-exclusions", "title": "Rule Exclusions", "command": rule_exclusions, "skipped": "rule-exclusions" in skip}
        ]
        
        # Display migration plan
        if output_format == "table":
            steps_table = Table(title="Migration Steps")
            steps_table.add_column("#", style="dim")
            steps_table.add_column("Component", style="green")
            steps_table.add_column("Status", style="cyan")
            
            for i, step in enumerate(migration_steps, 1):
                status = "[yellow]Will Skip[/]" if step["skipped"] else "Will Migrate"
                steps_table.add_row(str(i), step["title"], status)
            
            console.print(steps_table)
        else:
            # JSON output
            results["migration_plan"] = [
                {
                    "step": i,
                    "component": step["title"],
                    "will_skip": step["skipped"]
                }
                for i, step in enumerate(migration_steps, 1)
            ]
        
        # Ask for initial confirmation
        if not yes and output_format == "table" and not Confirm.ask("\nDo you want to proceed with the migration?"):
            console.print("[yellow]Migration canceled.[/]")
            return
        
        # Track overall migration results
        overall_results = {}
        
        # Execute each migration step
        for i, step in enumerate(migration_steps, 1):
            step_name = step["name"]
            step_title = step["title"]
            command = step["command"]
            
            if step["skipped"]:
                if output_format == "table":
                    console.print(f"\n[yellow]Skipping step {i}: {step_title}[/]")
                continue
            
            # Prepare command parameters
            command_params = [
                "--source-api-key", source_api_key,
                "--source-region", source_region,
                "--dest-api-key", dest_api_key,
                "--dest-region", dest_region,
                "--format", output_format
            ]
            
            if dry_run:
                command_params.append("--dry-run")
            
            if yes:
                command_params.append("--yes")
            
            # Execute the command
            if output_format == "table":
                console.print(f"\n[bold]Step {i}: Migrating {step_title}[/]")
                console.print("-" * 50)
            
            result = None
            try:
                # Use the Click command runner to invoke the command
                ctx = click.Context(command, obj={})
                result = command.callback(**{
                    param.name: param.get_default(ctx) if param.name not in [
                        "source_api_key", "source_region", "dest_api_key", "dest_region", 
                        "dry_run", "yes", "output_format"
                    ] else param.type_cast_value(ctx, {
                        "source_api_key": source_api_key,
                        "source_region": source_region,
                        "dest_api_key": dest_api_key,
                        "dest_region": dest_region,
                        "dry_run": dry_run,
                        "yes": yes,
                        "output_format": output_format
                    }.get(param.name))
                    for param in command.params if param.name != "skip"
                })
                
                overall_results[step_name] = "success"
            except Exception as e:
                if output_format == "table":
                    console.print(f"[bold red]Error during {step_title} migration:[/] {str(e)}")
                overall_results[step_name] = {"status": "error", "message": str(e)}
            
            # Add a separator between steps
            if output_format == "table":
                console.print("\n" + "=" * 50)
            
            # Brief pause between steps
            time.sleep(0.5)
        
        # Display final summary
        if output_format == "table":
            summary_table = Table(title="Migration Summary")
            summary_table.add_column("Component", style="green")
            summary_table.add_column("Status", style="cyan")
            
            for step in migration_steps:
                if step["skipped"]:
                    status = "[yellow]Skipped[/]"
                elif step["name"] in overall_results:
                    if overall_results[step["name"]] == "success":
                        status = "[green]Success[/]"
                    else:
                        status = "[red]Failed[/]"
                else:
                    status = "[gray]Not Run[/]"
                
                summary_table.add_row(step["title"], status)
            
            console.print("\n[bold]Migration Complete[/]")
            console.print(summary_table)
        else:
            # JSON output
            results["status"] = "completed"
            results["results"] = {
                step["name"]: {
                    "status": "skipped" if step["skipped"] else 
                             overall_results.get(step["name"], "not_run")
                }
                for step in migration_steps
            }
            click.echo(json.dumps(results, indent=2))
        
    except Exception as e:
        error_message = f"Error during migration: {str(e)}"
        if output_format == "table":
            console.print(f"[bold red]{error_message}[/]")
        else:
            results["status"] = "error"
            results["error"] = error_message
            click.echo(json.dumps(results, indent=2))