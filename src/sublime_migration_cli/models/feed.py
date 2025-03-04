"""Model for Sublime Security Feed."""
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class FeedSummary:
    """Summary information for a feed."""

    active: int
    available_changes: bool
    deletions: int
    invalid: int
    installed: int
    new: int
    out_of_date: int
    total: int
    up_to_date: int
    yara_sigs: int


@dataclass
class Feed:
    """Represents a feed in the Sublime Security Platform."""

    id: str
    name: str
    git_url: str
    git_branch: str
    is_system: bool
    checked_at: str
    retrieved_at: str
    auto_update_rules: bool
    auto_activate_new_rules: bool
    detection_rule_file_filter: str
    triage_rule_file_filter: str
    yara_file_filter: str
    summary: Optional[FeedSummary] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Feed":
        """Create a Feed instance from a dictionary.
        
        Args:
            data: Dictionary containing feed data
            
        Returns:
            Feed: New Feed instance
        """
        # Process summary if it exists
        summary = None
        if data.get("summary"):
            summary = FeedSummary(**data["summary"])
            
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            git_url=data.get("git_url", ""),
            git_branch=data.get("git_branch", ""),
            is_system=data.get("is_system", False),
            checked_at=data.get("checked_at", ""),
            retrieved_at=data.get("retrieved_at", ""),
            auto_update_rules=data.get("auto_update_rules", False),
            auto_activate_new_rules=data.get("auto_activate_new_rules", False),
            detection_rule_file_filter=data.get("detection_rule_file_filter", ""),
            triage_rule_file_filter=data.get("triage_rule_file_filter", ""),
            yara_file_filter=data.get("yara_file_filter", ""),
            summary=summary
        )