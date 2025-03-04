"""Factory for creating output formatters."""
from typing import Optional

from sublime_migration_cli.presentation.base import OutputFormatter
from sublime_migration_cli.presentation.interactive import InteractiveFormatter
from sublime_migration_cli.presentation.json_output import JsonFormatter


def create_formatter(output_format: str, use_pager: bool = True) -> OutputFormatter:
    """Create an output formatter based on the specified format.
    
    Args:
        output_format: The desired output format ("table", "json", etc.)
        use_pager: Whether to use a pager for large outputs (interactive mode only)
        
    Returns:
        OutputFormatter: The appropriate formatter
        
    Raises:
        ValueError: If the output format is not supported
    """
    if output_format == "json":
        return JsonFormatter()
    elif output_format in ("table", "interactive"):
        return InteractiveFormatter(use_pager=use_pager)
    else:
        raise ValueError(f"Unsupported output format: {output_format}")