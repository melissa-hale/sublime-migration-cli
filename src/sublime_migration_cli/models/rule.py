"""Models for Sublime Security Rules."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RuleAction:
    """Represents an action associated with a rule."""
    
    id: str
    name: str
    active: bool


@dataclass
class Rule:
    """Represents a rule in the Sublime Security Platform."""
    
    id: str
    org_id: str
    full_type: str
    type: str
    active: bool
    passive: bool
    source: str
    source_md5: str
    name: str
    created_at: str
    updated_at: str
    active_updated_at: str
    
    # Optional fields
    description: Optional[str] = None
    severity: Optional[str] = None
    authors: Optional[List[str]] = None
    references: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    false_positives: Optional[str] = None
    maturity: Optional[str] = None
    label: Optional[str] = None
    created_by_api_request_id: Optional[str] = None
    created_by_org_id: Optional[str] = None
    created_by_org_name: Optional[str] = None
    created_by_user_id: Optional[str] = None
    created_by_user_name: Optional[str] = None
    immutable: Optional[bool] = None
    feed_id: Optional[str] = None
    feed_external_rule_id: Optional[str] = None
    
    # Related objects
    actions: List[RuleAction] = field(default_factory=list)
    exclusions: List[str] = field(default_factory=list)
    
    # Additional properties for display
    has_exclusions: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Rule":
        """Create a Rule instance from a dictionary.
        
        Args:
            data: Dictionary containing rule data
            
        Returns:
            Rule: New Rule instance
        """
        # Process actions if they exist
        actions = []
        if "actions" in data and data["actions"]:
            actions = [
                RuleAction(
                    id=action.get("id", ""),
                    name=action.get("name", ""),
                    active=action.get("active", False)
                )
                for action in data["actions"]
            ]
        
        # Process exclusions if they exist
        exclusions = []
        if "exclusions" in data and data["exclusions"]:
            exclusions = data["exclusions"]
        
        return cls(
            id=data.get("id", ""),
            org_id=data.get("org_id", ""),
            full_type=data.get("full_type", ""),
            type=data.get("type", ""),
            active=data.get("active", False),
            passive=data.get("passive", False),
            source=data.get("source", ""),
            source_md5=data.get("source_md5", ""),
            name=data.get("name", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            active_updated_at=data.get("active_updated_at", ""),
            description=data.get("description"),
            severity=data.get("severity"),
            authors=data.get("authors"),
            references=data.get("references"),
            tags=data.get("tags"),
            false_positives=data.get("false_positives"),
            maturity=data.get("maturity"),
            label=data.get("label"),
            created_by_api_request_id=data.get("created_by_api_request_id"),
            created_by_org_id=data.get("created_by_org_id"),
            created_by_org_name=data.get("created_by_org_name"),
            created_by_user_id=data.get("created_by_user_id"),
            created_by_user_name=data.get("created_by_user_name"),
            immutable=data.get("immutable"),
            feed_id=data.get("feed_id"),
            feed_external_rule_id=data.get("feed_external_rule_id"),
            actions=actions,
            exclusions=exclusions,
            has_exclusions=bool(exclusions)
        )