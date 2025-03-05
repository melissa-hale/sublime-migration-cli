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

    def to_dict(self) -> Dict:
        """Convert the feed summary to a dictionary.
        
        Returns:
            Dict: Dictionary representation of the feed summary
        """
        return {
            "active": self.active,
            "available_changes": self.available_changes,
            "deletions": self.deletions,
            "invalid": self.invalid,
            "installed": self.installed,
            "new": self.new,
            "out_of_date": self.out_of_date,
            "total": self.total,
            "up_to_date": self.up_to_date,
            "yara_sigs": self.yara_sigs,
        }


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
    
    def to_dict(self) -> Dict:
        """Convert the feed to a dictionary.
        
        Returns:
            Dict: Dictionary representation of the feed
        """
        result = {
            "id": self.id,
            "name": self.name,
            "git_url": self.git_url,
            "git_branch": self.git_branch,
            "is_system": self.is_system,
            "checked_at": self.checked_at,
            "retrieved_at": self.retrieved_at,
            "auto_update_rules": self.auto_update_rules,
            "auto_activate_new_rules": self.auto_activate_new_rules,
            "detection_rule_file_filter": self.detection_rule_file_filter,
            "triage_rule_file_filter": self.triage_rule_file_filter,
            "yara_file_filter": self.yara_file_filter,
        }
        
        # Include summary if present
        if self.summary:
            result["summary"] = {
                "active": self.summary.active,
                "available_changes": self.summary.available_changes,
                "deletions": self.summary.deletions,
                "invalid": self.summary.invalid,
                "installed": self.summary.installed,
                "new": self.summary.new,
                "out_of_date": self.summary.out_of_date,
                "total": self.summary.total,
                "up_to_date": self.summary.up_to_date,
                "yara_sigs": self.summary.yara_sigs,
            }
        
        return result