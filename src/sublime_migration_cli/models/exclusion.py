"""Model for Sublime Security Exclusion."""
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class OriginatingRule:
    """Represents a rule associated with a rule exclusion."""

    id: str
    name: str
    type: str
    active: bool
    org_id: str
    
    @classmethod
    def from_dict(cls, data: Dict) -> "OriginatingRule":
        """Create an OriginatingRule instance from a dictionary."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            type=data.get("type", ""),
            active=data.get("active", False),
            org_id=data.get("org_id", "")
        )


@dataclass
class Exclusion:
    """Represents an exclusion in the Sublime Security Platform."""

    id: str
    org_id: str
    active: bool
    source: str
    source_md5: str
    name: str
    description: str
    scope: str
    created_at: str
    updated_at: str
    active_updated_at: str
    tags: Optional[List[str]] = None
    created_by_org_id: Optional[str] = None
    created_by_org_name: Optional[str] = None
    created_by_user_id: Optional[str] = None
    created_by_user_name: Optional[str] = None
    originating_rule: Optional[OriginatingRule] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Exclusion":
        """Create an Exclusion instance from a dictionary.
        
        Args:
            data: Dictionary containing exclusion data
            
        Returns:
            Exclusion: New Exclusion instance
        """
        # Process originating rule if it exists
        originating_rule = None
        if data.get("originating_rule"):
            originating_rule = OriginatingRule.from_dict(data["originating_rule"])
            
        return cls(
            id=data.get("id", ""),
            org_id=data.get("org_id", ""),
            active=data.get("active", False),
            source=data.get("source", ""),
            source_md5=data.get("source_md5", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            scope=data.get("scope", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            active_updated_at=data.get("active_updated_at", ""),
            tags=data.get("tags"),
            created_by_org_id=data.get("created_by_org_id"),
            created_by_org_name=data.get("created_by_org_name"),
            created_by_user_id=data.get("created_by_user_id"),
            created_by_user_name=data.get("created_by_user_name"),
            originating_rule=originating_rule
        )
    
    def to_dict(self) -> Dict:
        """Convert the exclusion to a dictionary.
        
        Returns:
            Dict: Dictionary representation of the exclusion
        """
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "scope": self.scope,
            "active": self.active,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        
        # Include optional fields if present
        if self.created_by_user_name:
            result["created_by"] = self.created_by_user_name
        elif self.created_by_org_name:
            result["created_by"] = self.created_by_org_name
        
        if self.tags:
            result["tags"] = self.tags
        
        # Include originating rule if present
        if self.originating_rule:
            result["originating_rule"] = {
                "id": self.originating_rule.id,
                "name": self.originating_rule.name,
                "type": self.originating_rule.type,
                "active": self.originating_rule.active
            }
        
        return result