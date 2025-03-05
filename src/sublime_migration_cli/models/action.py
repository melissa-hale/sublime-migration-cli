"""Model for Sublime Security Action."""
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class Action:
    """Represents an action in the Sublime Security Platform."""

    id: str
    name: str
    type: str
    active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Action":
        """Create an Action instance from a dictionary.
        
        Args:
            data: Dictionary containing action data
            
        Returns:
            Action: New Action instance
        """
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            type=data.get("type", ""),
            active=data.get("active", False),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
    
    def to_dict(self) -> Dict:
        """Convert the action to a dictionary.
        
        Returns:
            Dict: Dictionary representation of the action
        """
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "active": self.active,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }