"""JSON output formatter."""
import json
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

import click

from sublime_migration_cli.presentation.base import OutputFormatter, CommandResult


class JsonFormatter(OutputFormatter):
    """Formatter for JSON output."""
    
    def output_result(self, result: Any) -> None:
        """Output a result as JSON.
        
        Args:
            result: The data to output (CommandResult or other)
        """
        if isinstance(result, CommandResult):
            data_to_output = result.to_dict()
            click.echo(json.dumps(self._prepare_data(data_to_output), indent=2))
        else:
            # Direct output of other data types
            click.echo(json.dumps(self._prepare_data(result), indent=2))
    
    def output_error(self, error_message: str, details: Optional[Any] = None) -> None:
        """Output an error message as JSON.
        
        Args:
            error_message: The main error message
            details: Additional error details (optional)
        """
        error_data = {
            "success": False,
            "message": error_message
        }
        
        if details:
            error_data["error_details"] = self._prepare_data(details)
        
        click.echo(json.dumps(error_data, indent=2))
    
    def output_success(self, message: str) -> None:
        """Output a success message as JSON.
        
        Args:
            message: The success message
        """
        success_data = {
            "success": True,
            "message": message
        }
        
        click.echo(json.dumps(success_data, indent=2))
    
    @contextmanager
    def create_progress(self, description: str, total: Optional[int] = None):
        """Create a 'progress indicator' for JSON output (no-op).
        
        In JSON mode, no progress is shown, but we still provide the interface.
        
        Args:
            description: Description of the task (unused)
            total: Total number of steps (unused)
            
        Returns:
            A dummy progress context manager
        """
        class DummyProgress:
            def update(self, *args, **kwargs):
                pass
        
        dummy = DummyProgress()
        yield dummy, 0
    
    def prompt_confirmation(self, message: str) -> bool:
        """Prompt the user for confirmation.
        
        In JSON mode, this doesn't actually prompt - it assumes yes.
        
        Args:
            message: The confirmation message (unused)
            
        Returns:
            bool: Always True in JSON mode
        """
        return True
    
    def _prepare_data(self, data: Any) -> Any:
        """Prepare data for JSON serialization.
        
        Args:
            data: The data to prepare
            
        Returns:
            JSON-serializable data
        """
        # Handle dataclasses or objects with to_dict method
        if hasattr(data, "to_dict"):
            return self._prepare_data(data.to_dict())
        
        # Handle lists
        if isinstance(data, list):
            return [self._prepare_data(item) for item in data]
        
        # Handle dictionaries
        if isinstance(data, dict):
            return {k: self._prepare_data(v) for k, v in data.items()}
        
        # Handle other types
        return data