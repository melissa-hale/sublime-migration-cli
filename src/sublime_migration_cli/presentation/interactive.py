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
            
        if isinstance(data, list) and data and hasattr(data[0], "__class__") and data[0].__class__.__name__ == "Rule":
            self._output_rules_list(data)
            return
        
        # Original code for other data types...
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