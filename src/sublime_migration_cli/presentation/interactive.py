"""Interactive output formatter using Rich."""
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Confirm

from sublime_migration_cli.presentation.base import OutputFormatter, CommandResult


class InteractiveFormatter(OutputFormatter):
    """Formatter for interactive console output using Rich."""
    
    def __init__(self, use_pager: bool = True):
        """Initialize interactive formatter.
        
        Args:
            use_pager: Whether to use a pager for large outputs
        """
        self.console = Console()
        self.use_pager = use_pager
    
    def output_result(self, result: Any) -> None:
        """Output a result to the console.
        
        Args:
            result: The data to output (CommandResult or other)
        """
        if isinstance(result, CommandResult):
            if result.success:
                self.output_success(result.message)
                
                # Output data if present
                if result.data is not None:
                    self._output_data(result.data)
            else:
                self.output_error(result.message, result.error_details)
        else:
            # Direct output of other data types
            self._output_data(result)
    
    def output_error(self, error_message: str, details: Optional[Any] = None) -> None:
        """Output an error message to the console.
        
        Args:
            error_message: The main error message
            details: Additional error details (optional)
        """
        self.console.print(f"[bold red]Error:[/] {error_message}")
        
        if details:
            if isinstance(details, str):
                self.console.print(f"[red]{details}[/]")
            else:
                self.console.print("\n[bold]Details:[/]")
                self._output_data(details)
    
    def output_success(self, message: str) -> None:
        """Output a success message to the console.
        
        Args:
            message: The success message
        """
        self.console.print(f"[bold green]{message}[/]")
    
    @contextmanager
    def create_progress(self, description: str, total: Optional[int] = None):
        """Create a progress indicator.
        
        Args:
            description: Description of the task
            total: Total number of steps (optional)
            
        Returns:
            A progress context manager
        """
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[bold blue]{description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})") if total is not None else TextColumn(""),
            console=self.console,
            transient=True
        ) as progress:
            task = progress.add_task("Working", total=total)
            yield progress, task
    
    def prompt_confirmation(self, message: str) -> bool:
        """Prompt the user for confirmation.
        
        Args:
            message: The confirmation message
            
        Returns:
            bool: True if confirmed, False otherwise
        """
        return Confirm.ask(message, console=self.console)
    
    def _output_data(self, data: Any) -> None:
        """Output data based on its type.
        
        Args:
            data: The data to output
        """
        # Handle Rule objects specially
        if hasattr(data, "__class__") and data.__class__.__name__ == "Rule":
            self._output_rule(data)
            return
        
        # Check for model objects by looking for to_dict method
        if hasattr(data, "to_dict") and callable(getattr(data, "to_dict")):
            # Convert model to dictionary and display as a property table
            self._output_property_table(data.to_dict())
            return
        
        # Handle lists of model objects
        if isinstance(data, list) and data and hasattr(data[0], "to_dict") and callable(getattr(data[0], "to_dict")):
            # Convert list of models to list of dictionaries
            dict_list = [item.to_dict() for item in data]
            self._output_table_from_dict_list(dict_list)
            return
            
        if isinstance(data, list) and data and hasattr(data[0], "__class__") and data[0].__class__.__name__ == "Rule":
            self._output_rules_list(data)
            return
        
        # Other data types...
        if isinstance(data, list) and data and isinstance(data[0], dict):
            # List of dictionaries - create a table
            self._output_table_from_dict_list(data)
        elif isinstance(data, dict):
            # Dictionary - create a property table
            self._output_property_table(data)
        elif isinstance(data, Table):
            # Already a Rich table
            self._output_table(data)
        else:
            # Other data types
            self.console.print(data)

        # Check for migration data (has specific structure)
        if isinstance(data, dict) and any(key in data for key in [
                "new_actions", "new_lists", "new_exclusions", "new_feeds", "new_rules", "rules_to_update"
            ]) and "summary" in data:
            self._output_migration_preview(data)
            return
        
        # Check for migration plan data
        if isinstance(data, dict) and "migration_plan" in data:
            self._output_migration_plan(data)
            return
    
    def _output_table(self, table: Table) -> None:
        """Output a Rich table.
        
        Args:
            table: The Rich table to output
        """
        if self.use_pager and table.row_count > 20:
            with self.console.pager():
                self.console.print(table)
        else:
            self.console.print(table)
    
    def _output_table_from_dict_list(self, data: List[Dict]) -> None:
        """Create and output a table from a list of dictionaries.
        
        Args:
            data: List of dictionaries
        """
        if not data:
            return
        
        # Extract column names from the first dictionary
        columns = list(data[0].keys())
        
        table = Table(title=f"Results ({len(data)} items)")
        
        # Add columns
        for column in columns:
            table.add_column(column.replace("_", " ").title())
        
        # Add rows
        for item in data:
            row_values = []
            for column in columns:
                value = item.get(column, "")
                if isinstance(value, bool):
                    value = "✓" if value else "✗"
                elif value is None:
                    value = ""
                else:
                    value = str(value)
                row_values.append(value)
            
            table.add_row(*row_values)
        
        self._output_table(table)
    
    def _output_property_table(self, data: Dict) -> None:
        """Create and output a property table from a dictionary.
        
        Args:
            data: Dictionary of properties
        """
        table = Table(show_header=False)
        table.add_column("Property", style="cyan")
        table.add_column("Value")
        
        for key, value in data.items():
            # Format the key
            formatted_key = key.replace("_", " ").title()
            
            # Format the value based on type
            if isinstance(value, bool):
                formatted_value = "✓" if value else "✗"
            elif isinstance(value, (list, dict)):
                import json
                formatted_value = json.dumps(value, indent=2)
            elif value is None:
                formatted_value = ""
            else:
                formatted_value = str(value)
            
            table.add_row(formatted_key, formatted_value)
        
        self.console.print(table)

    def _output_rule(self, rule) -> None:
        """Output a single rule with syntax highlighting.
        
        Args:
            rule: Rule object to display
        """
        from rich.syntax import Syntax
        from rich.panel import Panel
        
        # Display basic rule info
        self.console.print(f"[bold]Rule:[/] {rule.name}")
        
        # Main info section
        self.console.print("\n[bold]Basic Information:[/]")
        basic_table = Table(show_header=False)
        basic_table.add_column("Property", style="cyan")
        basic_table.add_column("Value")
        
        basic_fields = [
            ("ID", rule.id),
            ("Type", rule.full_type),
            ("Severity", rule.severity or "N/A"),
            ("Active", "✓" if rule.active else "✗"),
            ("Passive", "✓" if rule.passive else "✗"),
        ]
        
        if hasattr(rule, "immutable") and rule.immutable is not None:
            basic_fields.append(("Immutable", "✓" if rule.immutable else "✗"))
            
        if rule.description:
            basic_fields.append(("Description", rule.description))
        
        for field, value in basic_fields:
            basic_table.add_row(field, str(value))
        
        self.console.print(basic_table)
        
        # Actions section
        if rule.actions:
            self.console.print("\n[bold]Associated Actions:[/]")
            actions_table = Table()
            actions_table.add_column("ID", style="dim")
            actions_table.add_column("Name", style="green")
            actions_table.add_column("Active", style="cyan", justify="center")
            
            for action in rule.actions:
                actions_table.add_row(
                    action.id,
                    action.name,
                    "✓" if action.active else "✗"
                )
            
            self.console.print(actions_table)
        
        # Exclusions section
        if rule.exclusions:
            self.console.print("\n[bold]Rule Exclusions:[/]")
            exclusions_table = Table()
            exclusions_table.add_column("Exclusion", style="green")
            
            for exclusion in rule.exclusions:
                exclusions_table.add_row(exclusion)
            
            self.console.print(exclusions_table)
        
        # Source query section
        self.console.print("\n[bold]Source Query:[/]")
        source_syntax = Syntax(rule.source, "sql", theme="monokai", line_numbers=True)
        self.console.print(source_syntax)
        
        # Additional metadata
        meta_fields = []
        if rule.authors:
            meta_fields.append(("Authors", ", ".join(rule.authors) if isinstance(rule.authors, list) else rule.authors))
        
        if rule.references:
            meta_fields.append(("References", "\n".join(rule.references) if isinstance(rule.references, list) else rule.references))
        
        if rule.tags:
            meta_fields.append(("Tags", ", ".join(rule.tags) if isinstance(rule.tags, list) else rule.tags))
        
        if meta_fields:
            self.console.print("\n[bold]Additional Metadata:[/]")
            meta_table = Table(show_header=False)
            meta_table.add_column("Property", style="cyan")
            meta_table.add_column("Value")
            
            for field, value in meta_fields:
                meta_table.add_row(field, str(value))
            
            self.console.print(meta_table)

    def _output_rules_list(self, rules: List) -> None:
        """Output a list of rules.
        
        Args:
            rules: List of Rule objects to display
        """
        # Create a table for displaying rules
        table = Table(title=f"Rules ({len(rules)} items)")
        table.add_column("ID", style="dim", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Type", style="blue")
        table.add_column("Severity", style="magenta")
        table.add_column("Active", style="cyan", justify="center")
        table.add_column("Actions", style="yellow", justify="right")
        
        if any(rule.has_exclusions for rule in rules):
            table.add_column("Exclusions", style="red", justify="center")
        
        # Add rules to the table
        for rule in rules:
            # Count actions
            action_count = len([a for a in rule.actions if a.active])
            
            # Prepare row data
            row_data = [
                rule.id,
                rule.name,
                rule.type,
                rule.severity or "N/A",
                "✓" if rule.active else "✗",
                str(action_count)
            ]
            
            # Add exclusions column if any rule has exclusions
            if any(rule.has_exclusions for rule in rules):
                row_data.append("✓" if rule.has_exclusions else "")
            
            table.add_row(*row_data)
        
        # Output the table
        self._output_table(table)

    def _output_migration_preview(self, data: Dict) -> None:
        """Format and display migration preview data.
        
        Args:
            data: Migration preview data
        """
        # Determine migration type and extract items
        migration_type, new_items, update_items, skipped_items = self._determine_migration_type(data)
        
        if not migration_type:
            # Generic handling for unknown migration types
            self.console.print(data)
            return
        
        # Display summary
        summary = data.get("summary", {})
        self.console.print(f"\n[bold]Migration Summary:[/]")
        
        # Different types have different summary fields
        if "new_count" in summary:
            self.console.print(f"New items: {summary.get('new_count', 0)}")
        if "update_count" in summary:
            self.console.print(f"Updates: {summary.get('update_count', 0)}")
        if "actions_count" in summary:
            self.console.print(f"Actions: {summary.get('actions_count', 0)}")
        if "rules_count" in summary:
            self.console.print(f"Rules: {summary.get('rules_count', 0)}")
        if "skipped_count" in summary:
            self.console.print(f"Skipped: {summary.get('skipped_count', 0)}")
        if "skipped_rules_count" in summary:
            self.console.print(f"Skipped rules: {summary.get('skipped_rules_count', 0)}")
        if "skipped_actions_count" in summary:
            self.console.print(f"Skipped actions: {summary.get('skipped_actions_count', 0)}")
        if "total_count" in summary:
            self.console.print(f"Total: {summary.get('total_count', 0)}")
        
        # Display new items if any
        if new_items:
            self._display_items_table(migration_type, "New", new_items)
        
        # Display update items if any
        if update_items:
            # For action-to-rule associations, use a special display format
            if migration_type == "actions-to-rules":
                self._display_rule_action_associations(update_items)
            else:
                self._display_items_table(migration_type, "Update", update_items)
        
        # Display skipped items if any
        if skipped_items:
            self._display_skipped_items(migration_type, skipped_items)
        
        # Display results if available
        results = data.get("results")
        if results:
            self._display_migration_results(results)

    def _determine_migration_type(self, data: Dict) -> tuple[Optional[str], List, List, List]:
        """Determine migration type and extract relevant items.
        
        Args:
            data: Migration data
            
        Returns:
            Tuple[str, List, List, List]: Migration type, new items, update items, skipped items
        """
        if "new_actions" in data:
            return "actions", data.get("new_actions", []), data.get("update_actions", []), []
        elif "new_lists" in data:
            return "lists", data.get("new_lists", []), data.get("update_lists", []), []
        elif "new_exclusions" in data:
            return "exclusions", data.get("new_exclusions", []), data.get("update_exclusions", []), []
        elif "new_feeds" in data:
            return "feeds", data.get("new_feeds", []), data.get("update_feeds", []), []
        elif "new_rules" in data:
            return "rules", data.get("new_rules", []), data.get("update_rules", []), data.get("skipped_rules", [])
        elif "rules_to_update" in data and any("actions" in rule for rule in data.get("rules_to_update", [])):
            return "actions-to-rules", [], data.get("rules_to_update", []), data.get("skipped_rules", []) + data.get("skipped_actions", [])
        elif "rules_to_update" in data and any("exclusions" in rule for rule in data.get("rules_to_update", [])):
            return "rule-exclusions", [], data.get("rules_to_update", []), data.get("skipped_rules", []) + data.get("skipped_exclusions", [])
        
        return None, [], [], []

    def _display_items_table(self, migration_type: str, action_type: str, items: List):
        """Display a table of items to migrate.
        
        Args:
            migration_type: Type of migration (actions, lists, etc.)
            action_type: Type of action (New, Update, etc.)
            items: List of items to display
        """
        if not items:
            return
            
        self.console.print(f"\n[bold]{action_type} {migration_type.title()} to {action_type}:[/]")
        table = Table()
        
        # Common columns for all migration types
        table.add_column("Name", style="green")
        table.add_column("Status", style="cyan")
        
        # Type-specific columns
        if migration_type == "actions":
            table.add_column("Type", style="blue")
        elif migration_type == "lists":
            table.add_column("Type", style="blue")
            table.add_column("Entries", style="magenta", justify="right")
        elif migration_type == "exclusions":
            table.add_column("Scope", style="blue")
            table.add_column("Active", style="magenta", justify="center")
            table.add_column("Created By", style="yellow")
        elif migration_type == "feeds":
            table.add_column("Git URL", style="blue")
            table.add_column("Branch", style="magenta")
            table.add_column("System", style="yellow", justify="center")
        elif migration_type == "rules":
            table.add_column("Type", style="blue")
            table.add_column("Severity", style="magenta")
        elif migration_type == "rule-exclusions":
            table.add_column("Exclusions", style="blue")
        
        # Add rows based on migration type
        for item in items:
            
            item_name = item.get("rule_name", item.get("name", ""))
            row_data = [item_name, item.get("status", "")]
            
            if migration_type == "actions":
                row_data.append(item.get("type", ""))
            elif migration_type == "lists":
                row_data.append(item.get("type", ""))
                row_data.append(str(item.get("entries", 0)))
            elif migration_type == "exclusions":
                row_data.append(item.get("scope", ""))
                row_data.append("✓" if item.get("active", False) else "✗")
                row_data.append(item.get("created_by", ""))
            elif migration_type == "feeds":
                row_data.append(item.get("git_url", ""))
                row_data.append(item.get("git_branch", ""))
                row_data.append("✓" if item.get("is_system", False) else "✗")
            elif migration_type == "rules":
                row_data.append(item.get("type", ""))
                row_data.append(item.get("severity", ""))
            elif migration_type == "rule-exclusions":
                # Format exclusions count or list for rule-exclusions
                exclusions = item.get("exclusions", [])
                if isinstance(exclusions, list):
                    exclusions_count = len(exclusions)
                    row_data.append(f"{exclusions_count} exclusions")
                else:
                    row_data.append(str(exclusions))
            
            table.add_row(*row_data)
        
        self.console.print(table)

    def _display_rule_action_associations(self, rules_to_update: List):
        """Display rule-action associations or rule-exclusions to migrate.
        
        Args:
            rules_to_update: List of rules to update with action associations or exclusions
        """
        if not rules_to_update:
            return
        
        # Determine if these are action associations or exclusions based on the first item
        is_actions = "actions" in rules_to_update[0] if rules_to_update else False
        is_exclusions = "exclusions" in rules_to_update[0] if rules_to_update else False
        
        if is_actions:
            title = "Rule-Action Associations"
            col2_title = "Actions"
        elif is_exclusions:
            title = "Rule Exclusions"
            col2_title = "Exclusions"
        else:
            title = "Rule Updates"
            col2_title = "Details"
            
        self.console.print(f"\n[bold]{title} to Update:[/]")
        table = Table()
        
        table.add_column("Rule Name", style="green")
        table.add_column(col2_title, style="blue")
        table.add_column("Status", style="cyan")
        
        ##### the rule name display issue w/ rule_exclusions is somewhere here
        ##### tip: rules works well, compare the json outputs
        for rule in rules_to_update:
            details = ""
            if is_actions:
                details = ", ".join(rule.get("actions", []))
            elif is_exclusions:
                details = "\n".join(rule.get("exclusions", []))
            
            rule_name = rule.get("rule_name", rule.get("name", ""))
        
            table.add_row(
                rule_name,
                details,
                rule.get("status", "")
            )
        
        self.console.print(table)

    def _display_skipped_items(self, migration_type: str, skipped_items: List):
        """Display skipped items.
        
        Args:
            migration_type: Type of migration
            skipped_items: List of skipped items
        """
        if not skipped_items:
            return
            
        self.console.print(f"\n[bold]Skipped {migration_type.title()}:[/]")
        table = Table()
        
        if migration_type in ["actions-to-rules", "rule-exclusions"]:
            # Special handling for action-to-rule associations and rule exclusions
            is_exclusions = migration_type == "rule-exclusions"
            
            table.add_column("Rule Name", style="yellow")
            table.add_column("Exclusion" if is_exclusions else "Action Name", style="blue")
            table.add_column("Reason", style="red")
            
            for item in skipped_items:
                # Check if this is a skipped action/exclusion or a skipped rule
                col2_key = "exclusion" if is_exclusions else "action_name"
                
                if col2_key in item:
                    table.add_row(
                        item.get("rule_name", ""),
                        item.get(col2_key, ""),
                        item.get("reason", "")
                    )
                else:
                    table.add_row(
                        item.get("rule_name", ""),
                        "",
                        item.get("reason", "")
                    )
        else:
            # General handling for other types
            table.add_column("Name", style="yellow")
            table.add_column("Type", style="dim")
            table.add_column("Reason", style="red")
            
            for item in skipped_items:
                table.add_row(
                    item.get("name", ""),
                    item.get("type", ""),
                    item.get("reason", "")
                )
        
        self.console.print(table)

    def _display_migration_results(self, results: Dict):
        """Display migration results.
        
        Args:
            results: Migration results
        """
        self.console.print("\n[bold]Migration Results:[/]")
        
        # Display summary counts
        if "created" in results:
            self.console.print(f"Created: {results.get('created', 0)}")
        if "updated" in results:
            self.console.print(f"Updated: {results.get('updated', 0)}")
        if "skipped" in results:
            self.console.print(f"Skipped: {results.get('skipped', 0)}")
        if "failed" in results:
            self.console.print(f"Failed: {results.get('failed', 0)}")
        
        # Display details if available
        details = results.get("details", [])
        if details:
            self.console.print("\n[bold]Operation Details:[/]")
            details_table = Table()
            details_table.add_column("Name", style="green")
            details_table.add_column("Type", style="blue")
            details_table.add_column("Status", style="cyan")
            details_table.add_column("Details", style="yellow")
            
            for detail in details:
                # Get reason or actions count for details column
                detail_info = detail.get("reason", "")
                if not detail_info and "actions_count" in detail:
                    detail_info = f"{detail['actions_count']} actions"
                
                details_table.add_row(
                    detail.get("name", ""),
                    detail.get("type", ""),
                    detail.get("status", ""),
                    detail_info
                )
            
            self.console.print(details_table)

    def _output_migration_plan(self, data: Dict) -> None:
        """Format and display migration plan data.
        
        Args:
            data: Migration plan data
        """
        # Display connection info
        if "connection_info" in data:
            conn_info = data["connection_info"]
            self.console.print("\n[bold]Connection Information:[/]")
            self.console.print(f"Source: [green]{conn_info['source']['org_name']}[/] ({conn_info['source']['email']})")
            self.console.print(f"Destination: [green]{conn_info['destination']['org_name']}[/] ({conn_info['destination']['email']})")
        
        # Display migration plan
        if "migration_plan" in data:
            self.console.print("\n[bold]Migration Plan:[/]")
            plan_table = Table()
            plan_table.add_column("#", style="dim")
            plan_table.add_column("Component", style="green")
            plan_table.add_column("Status", style="cyan")
            
            for step in data["migration_plan"]:
                status = "[yellow]Will Skip[/]" if step.get("will_skip") else "Will Migrate"
                plan_table.add_row(str(step.get("step")), step.get("component"), status)
            
            self.console.print(plan_table)
        
        # Display migration summary if available
        if "summary" in data:
            self.console.print("\n[bold]Migration Summary:[/]")
            summary_table = Table()
            summary_table.add_column("Component", style="green")
            summary_table.add_column("Status", style="cyan")
            
            for item in data["summary"]:
                status = item.get("status", "")
                status_style = ""
                
                if status == "success":
                    status_style = "[green]Success[/]"
                elif status == "failed":
                    status_style = "[red]Failed[/]"
                elif status == "skipped":
                    status_style = "[yellow]Skipped[/]"
                else:
                    status_style = "[gray]Not Run[/]"
                
                summary_table.add_row(item.get("component", ""), status_style)
            
            self.console.print(summary_table)