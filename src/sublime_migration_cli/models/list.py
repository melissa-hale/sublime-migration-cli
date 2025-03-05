"""Model for Sublime Security List."""
from dataclasses import dataclass
from typing import Dict, List as PyList, Optional


@dataclass
class List:
    """Represents a list in the Sublime Security Platform."""

    id: str
    name: str
    description: str
    download_url: str
    org_id: str
    org_name: str
    created_by_user_id: str
    created_by_user_name: str
    viewable: bool
    editable: bool
    entry_type: str
    created_at: str
    updated_at: str
    entries: Optional[PyList[str]] = None
    entry_count: int = 0
    provider_group_id: Optional[str] = None
    provider_group_name: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> "List":
        """Create a List instance from a dictionary.
        
        Args:
            data: Dictionary containing list data
            
        Returns:
            List: New List instance
        """
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            download_url=data.get("download_url", ""),
            org_id=data.get("org_id", ""),
            org_name=data.get("org_name", ""),
            created_by_user_id=data.get("created_by_user_id", ""),
            created_by_user_name=data.get("created_by_user_name", ""),
            viewable=data.get("viewable", False),
            editable=data.get("editable", False),
            entry_type=data.get("entry_type", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            entries=data.get("entries"),
            entry_count=data.get("entry_count", 0),
            provider_group_id=data.get("provider_group_id"),
            provider_group_name=data.get("provider_group_name"),
        )
    
    def to_dict(self) -> Dict:
        """Convert the list to a dictionary.
        
        Returns:
            Dict: Dictionary representation of the list
        """
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "entry_type": self.entry_type,
            "entry_count": self.entry_count,
            "created_by_user_name": self.created_by_user_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        
        # Only include non-empty fields
        if self.entries:
            result["entries"] = self.entries
        
        if self.provider_group_id:
            result["provider_group_id"] = self.provider_group_id
            
        if self.provider_group_name:
            result["provider_group_name"] = self.provider_group_name
        
        return result