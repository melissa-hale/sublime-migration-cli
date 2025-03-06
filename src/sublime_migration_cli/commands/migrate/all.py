"""Refactored command to migrate all components using utility functions."""
import time
import click

from sublime_migration_cli.api.client import get_api_client_from_env_or_args
from sublime_migration_cli.presentation.base import CommandResult
from sublime_migration_cli.presentation.factory import create_formatter

# Import our utility functions
from sublime_migration_cli.utils.errors import (
    ApiError, MigrationError, handle_api_error, ErrorHandler
)

# Import all the refactored migration commands
from sublime_migration_cli.commands.migrate.actions import migrate_actions_between_instances
from sublime_migration_cli.commands.migrate.lists import migrate_lists_between_instances
from sublime_migration_cli.commands.migrate.exclusions import migrate_exclusions_between_instances
from sublime_migration_cli.commands.migrate.feeds import migrate_feeds_between_instances
from sublime_migration_cli.commands.migrate.rules import migrate_rules_between_instances
from sublime_migration_cli.commands.migrate.actions_to_rules import migrate_actions_to_rules_between_instances
from sublime_migration_cli.commands.migrate.rule_exclusions import migrate_rule_exclusions_between_instances


# Implementation function
def migrate_all_components_between_instances(
    source_api_key=None, source_region=None, 
    dest_api_key=None, dest_region=None,
    skip=None, dry_run=False, formatter=None
):
    """Implementation for migrating all components between instances.
    
    Args:
        source_api_key: API key for source instance
        source_region: Region for source instance
        dest_api_key: API key for destination instance
        dest_region: Region for destination instance
        skip: List of components to skip
        dry_run: If True, preview changes without applying them
        formatter: Output formatter
    """
    # Default to table formatter if none provided
    if formatter is None:
        formatter = create_formatter("table")
    
    # Use empty list if skip is None
    skip = skip or []
        
    try:
        # Create API clients for validation
        with formatter.create_progress("Validating connection to source and destination...") as (progress, task):
            source_client = get_api_client_from_env_or_args(source_api_key, source_region)
            dest_client = get_api_client_from_env_or_args(dest_api_key, dest_region, destination=True)
            
            # Test connection by fetching user info
            source_info = source_client.get("/v1/me")
            dest_info = dest_client.get("/v1/me")
            
            progress.update(task, advance=1)
        
        # Define migration steps
        migration_steps = [
            {
                "name": "actions", 
                "title": "Actions", 
                "function": migrate_actions_between_instances,
                "skipped": "actions" in skip
            },
            {
                "name": "lists", 
                "title": "Lists", 
                "function": migrate_lists_between_instances,
                "skipped": "lists" in skip
            },
            {
                "name": "exclusions", 
                "title": "Exclusions", 
                "function": migrate_exclusions_between_instances,
                "skipped": "exclusions" in skip
            },
            {
                "name": "feeds", 
                "title": "Feeds", 
                "function": migrate_feeds_between_instances,
                "skipped": "feeds" in skip
            },
            {
                "name": "rules", 
                "title": "Rules", 
                "function": migrate_rules_between_instances,
                "skipped": "rules" in skip
            },
            {
                "name": "actions-to-rules", 
                "title": "Actions to Rules", 
                "function": migrate_actions_to_rules_between_instances,
                "skipped": "actions-to-rules" in skip
            },
            {
                "name": "rule-exclusions", 
                "title": "Rule Exclusions", 
                "function": migrate_rule_exclusions_between_instances,
                "skipped": "rule-exclusions" in skip
            }
        ]
        
        # Prepare migration plan
        migration_plan = []
        for i, step in enumerate(migration_steps, 1):
            migration_plan.append({
                "step": i,
                "component": step["title"],
                "will_skip": step["skipped"]
            })
        
        # Prepare response data
        migration_data = {
            "migration_plan": migration_plan,
            "connection_info": {
                "source": {
                    "org_name": source_info.get("org_name", "Unknown"),
                    "email": source_info.get("email_address", "Unknown")
                },
                "destination": {
                    "org_name": dest_info.get("org_name", "Unknown"),
                    "email": dest_info.get("email_address", "Unknown")
                }
            },
            "steps_results": {}
        }
        
        # Show migration plan and ask for confirmation
        formatter.output_result(CommandResult.success(
            "Migration Plan",
            migration_data,
            "Please confirm to proceed with migration."
        ))
        
        # Confirm migration if interactive
        if not formatter.prompt_confirmation("\nDo you want to proceed with the migration?"):
            return CommandResult.success("Migration canceled by user.")
        
        # Track overall migration results
        overall_results = {}
        
        # Execute each migration step
        for i, step in enumerate(migration_steps, 1):
            step_name = step["name"]
            step_title = step["title"]
            
            # Skip if requested
            if step["skipped"]:
                formatter.output_result(CommandResult.success(
                    f"Skipping step {i}: {step_title}",
                    {"step": i, "component": step_title, "status": "skipped"}
                ))
                overall_results[step_name] = "skipped"
                migration_data["steps_results"][step_name] = {"status": "skipped"}
                continue
            
            # Execute the step
            formatter.output_result(CommandResult.success(
                f"Step {i}: Migrating {step_title}",
                {"step": i, "component": step_title, "status": "in_progress"}
            ))
            
            try:
                # Call the implementation function
                result = step["function"](
                    source_api_key, source_region,
                    dest_api_key, dest_region,
                    dry_run=dry_run,
                    formatter=formatter
                )
                
                # Record result
                overall_results[step_name] = "success"
                migration_data["steps_results"][step_name] = {
                    "status": "success",
                    "data": result.data if hasattr(result, "data") else None
                }
                
            except Exception as e:
                # Handle and record error
                sublime_error = handle_api_error(e)
                error_message = f"Error during {step_title} migration: {sublime_error.message}"
                formatter.output_error(error_message)
                
                overall_results[step_name] = {
                    "status": "error",
                    "message": sublime_error.message
                }
                migration_data["steps_results"][step_name] = {
                    "status": "error",
                    "error": sublime_error.message
                }
            
            # Add a pause between steps
            time.sleep(0.5)
        
        # Prepare summary data
        summary_data = []
        for step in migration_steps:
            status = "skipped"
            if step["name"] in overall_results:
                if overall_results[step["name"]] == "success":
                    status = "success"
                elif isinstance(overall_results[step["name"]], dict) and overall_results[step["name"]].get("status") == "error":
                    status = "failed"
            
            summary_data.append({
                "component": step["title"],
                "status": status
            })
        
        migration_data["summary"] = summary_data
        
        # Return overall results
        return CommandResult.success(
            "Migration Complete",
            migration_data,
            "See details for each component above."
        )
        
    except Exception as e:
        sublime_error = handle_api_error(e)
        if isinstance(sublime_error, ApiError):
            return CommandResult.error(f"API error during migration: {sublime_error.message}", sublime_error.details)
        else:
            return CommandResult.error(f"Error during migration: {sublime_error.message}")


# Click command definition
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
    # Create formatter based on output format
    formatter = create_formatter(output_format)
    
    # If --yes flag is provided, modify the formatter to auto-confirm
    if yes:
        original_prompt = formatter.prompt_confirmation
        formatter.prompt_confirmation = lambda _: True
    
    # Execute the implementation function
    result = migrate_all_components_between_instances(
        source_api_key, source_region, 
        dest_api_key, dest_region,
        skip, dry_run, formatter
    )
    
    # Reset the formatter if it was modified
    if yes and hasattr(formatter, 'original_prompt'):
        formatter.prompt_confirmation = original_prompt
    
    # Output the result
    formatter.output_result(result)