"""Base classes for output formatting."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table


class OutputFormatter(ABC):
    """Abstract base class for output formatters."""

    @abstractmethod
    def output_result(self, result: Any) -> None:
        """Output a result to the user.
        
        Args:
            result: The data to output
        """
        pass
    
    @abstractmethod
    def output_error(self, error_message: str, details: Optional[Any] = None) -> None:
        """Output an error message to the user.
        
        Args:
            error_message: The main error message
            details: Additional error details (optional)
        """
        pass
    
    @abstractmethod
    def output_success(self, message: str) -> None:
        """Output a success message to the user.
        
        Args:
            message: The success message
        """
        pass
    
    @abstractmethod
    def create_progress(self, description: str, total: Optional[int] = None):
        """Create a progress indicator.
        
        Args:
            description: Description of the task
            total: Total number of steps (optional)
            
        Returns:
            A progress context manager
        """
        pass
    
    @abstractmethod
    def prompt_confirmation(self, message: str) -> bool:
        """Prompt the user for confirmation.
        
        Args:
            message: The confirmation message
            
        Returns:
            bool: True if confirmed, False otherwise
        """
        pass


class CommandResult:
    """Represents the result of a command operation."""
    
    def __init__(
        self, 
        success: bool, 
        message: str,
        data: Any = None,
        error_details: Optional[Any] = None,
        notes: Optional[str] = None
    ):
        """Initialize a command result.
        
        Args:
            success: Whether the command was successful
            message: Result message
            data: Result data (optional)
            error_details: Error details if failed (optional)
            notes: Additional notes about the result (optional)
        """
        self.success = success
        self.message = message
        self.data = data
        self.error_details = error_details
        self.notes = notes
    
    @classmethod
    def success(cls, message: str, data: Any = None, notes: Optional[str] = None) -> "CommandResult":
        """Create a success result.
        
        Args:
            message: Success message
            data: Result data (optional)
            notes: Additional notes (optional)
            
        Returns:
            CommandResult: Success result
        """
        return cls(True, message, data, notes=notes)
    
    @classmethod
    def error(cls, message: str, error_details: Optional[Any] = None) -> "CommandResult":
        """Create an error result.
        
        Args:
            message: Error message
            error_details: Error details (optional)
            
        Returns:
            CommandResult: Error result
        """
        return cls(False, message, error_details=error_details)
    
    def to_dict(self) -> Dict:
        """Convert result to a dictionary.
        
        Returns:
            Dict: Dictionary representation of result
        """
        result = {
            "success": self.success,
            "message": self.message,
        }
        
        if self.data is not None:
            result["data"] = self.data
            
        if self.error_details is not None:
            result["error_details"] = self.error_details
            
        if self.notes is not None:
            result["notes"] = self.notes
            
        return result