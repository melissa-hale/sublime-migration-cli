"""Base resource class for all Sublime as Code resources."""
from typing import Dict, List, Optional, Any, Union, ClassVar, Type
from dataclasses import dataclass, field
import yaml
import json
from datetime import datetime
import hashlib


class Resource:
    """Base class for all Sublime resources."""
    
    # Class registry for resource types
    _registry: ClassVar[Dict[str, Type["Resource"]]] = {}
    
    def __init__(self, name: str, id: Optional[str] = None):
        """
        Initialize a resource.
        
        Args:
            name: The resource name (display name for the resource)
            id: Optional UUID for the resource (will be assigned by the API if not provided)
        """
        self.name = name
        self.id = id
        
        # Common metadata fields
        self.org_id: Optional[str] = None
        self.created_at: Optional[str] = None
        self.updated_at: Optional[str] = None
        self.description: Optional[str] = None
        
        # Tracking field for state management
        self.source_hash: Optional[str] = None
    
    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Register subclasses in the registry."""
        super().__init_subclass__(**kwargs)
        
        # Register the class if it has a RESOURCE_TYPE
        if hasattr(cls, 'RESOURCE_TYPE') and cls.RESOURCE_TYPE:
            Resource._registry[cls.RESOURCE_TYPE] = cls
    
    def id_key(self) -> str:
        """
        Get the unique identifier of the resource.
        
        For API-created resources, this will be the UUID.
        For locally-created resources without an ID, we use the name as a fallback.
        When applying changes to the API, resources without IDs will be created as new.
        """
        return self.id if self.id else self.name
    
    def get_resource_type(self) -> str:
        """
        Get the resource type.
        
        This should be implemented by subclasses to return their specific type.
        """
        # Subclasses should override this to return their specific type
        if hasattr(self, 'RESOURCE_TYPE'):
            return getattr(self, 'RESOURCE_TYPE')
        return self.__class__.__name__
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert resource to dictionary representation for configuration files.
        
        This base implementation includes common fields.
        Subclasses should extend this to add their specific fields.
        
        Returns:
            Dict: Configuration representation of the resource
        """
        # Base fields that apply to all resources
        result = {
            "version": "sublime.security/v1",
            "name": self.name,
        }
        
        # Add optional fields if they exist
        if self.description:
            result["description"] = self.description
        
        return result
    
    def to_state_dict(self) -> Dict[str, Any]:
        """
        Convert resource to dictionary representation for state tracking.
        
        This includes all fields including API-provided metadata.
        Subclasses may extend this to add their specific fields.
        
        Returns:
            Dict: Complete state representation of the resource
        """
        # Start with the configuration representation
        result = self.to_dict()
        
        # Add state-specific metadata
        if self.id:
            result["id"] = self.id
            
        if self.org_id:
            result["org_id"] = self.org_id
            
        # Add tracking metadata
        tracking = {}
        
        if self.created_at:
            tracking["created_at"] = self.created_at
            
        if self.updated_at:
            tracking["updated_at"] = self.updated_at
            
        if self.source_hash:
            tracking["source_hash"] = self.source_hash
            
        if tracking:
            result["tracking"] = tracking
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Resource":
        """
        Create a resource from a dictionary.
        
        This is a factory method that delegates to the appropriate subclass.
        
        Args:
            data: Dictionary containing resource data
            
        Returns:
            Resource: The created resource
        """
        # Determine which subclass to use based on the resource type
        # First, try to get the resource type from the data
        resource_type = cls._get_resource_type_from_data(data)
        
        # If we have a registered subclass for this type, use it
        if resource_type in cls._registry:
            return cls._registry[resource_type].from_dict(data)
        
        # Fallback: create a generic resource
        name = data.get("name", "")
        id = data.get("id")
        
        resource = cls(name, id)
        resource.description = data.get("description")
        resource.org_id = data.get("org_id")
        resource.created_at = data.get("created_at")
        resource.updated_at = data.get("updated_at")
        
        # Check for tracking data
        tracking = data.get("tracking", {})
        if tracking:
            resource.source_hash = tracking.get("source_hash")
        
        return resource
    
    @classmethod
    def _get_resource_type_from_data(cls, data: Dict[str, Any]) -> Optional[str]:
        """
        Determine the resource type from the data.
        
        This is a helper for the factory method.
        
        Args:
            data: Dictionary containing resource data
            
        Returns:
            Optional[str]: The resource type, or None if it can't be determined
        """
        # We will let each subclass define how to recognize its own data
        # This method will be used only as a fallback
        for subclass in cls._registry.values():
            if hasattr(subclass, 'is_type_match') and callable(getattr(subclass, 'is_type_match')):
                if subclass.is_type_match(data):
                    return subclass.RESOURCE_TYPE
        
        return None
    
    @classmethod
    def from_api_dict(cls, data: Dict[str, Any]) -> "Resource":
        """
        Create a resource from an API response dictionary.
        
        Subclasses should override this to handle their specific API format.
        
        Args:
            data: Dictionary from API response
            
        Returns:
            Resource: The created resource
        """
        # Base implementation that subclasses can override
        return cls.from_dict(data)
    
    def to_api_dict(self) -> Dict[str, Any]:
        """
        Convert resource to API request format.
        
        Subclasses should override this to handle their specific API format.
        
        Returns:
            Dict: API request payload
        """
        # Base implementation that subclasses can override
        return {
            "name": self.name,
            "description": self.description
        }
    
    def calculate_source_hash(self) -> str:
        """
        Calculate a hash of the resource's configuration.
        
        This is used for state tracking to detect changes.
        
        Returns:
            str: Hash string
        """
        # Convert to JSON for consistent serialization
        config_json = json.dumps(self.to_dict(), sort_keys=True)
        # Calculate SHA-256 hash
        return hashlib.sha256(config_json.encode('utf-8')).hexdigest()
    
    def update_source_hash(self) -> None:
        """Update the source hash based on the current configuration."""
        self.source_hash = self.calculate_source_hash()
    
    def to_yaml(self) -> str:
        """
        Generate YAML representation of the resource for configuration files.
        
        Returns:
            str: YAML representation
        """
        return yaml.dump(self.to_dict(), default_flow_style=False)
    
    def to_state_yaml(self) -> str:
        """
        Generate YAML representation of the resource for state files.
        
        Returns:
            str: YAML representation including state fields
        """
        return yaml.dump(self.to_state_dict(), default_flow_style=False)
    
    def to_json(self) -> str:
        """
        Generate JSON representation of the resource for configuration files.
        
        Returns:
            str: JSON representation
        """
        return json.dumps(self.to_dict(), indent=2)
    
    def to_state_json(self) -> str:
        """
        Generate JSON representation of the resource for state files.
        
        Returns:
            str: JSON representation including state fields
        """
        return json.dumps(self.to_state_dict(), indent=2)
    
    @classmethod
    def from_yaml(cls, yaml_str: str) -> "Resource":
        """
        Create resource from YAML representation.
        
        Args:
            yaml_str: YAML string
            
        Returns:
            Resource: Created resource
        """
        return cls.from_dict(yaml.safe_load(yaml_str))
    
    @classmethod
    def from_json(cls, json_str: str) -> "Resource":
        """
        Create resource from JSON representation.
        
        Args:
            json_str: JSON string
            
        Returns:
            Resource: Created resource
        """
        return cls.from_dict(json.loads(json_str))
    
    def __str__(self) -> str:
        """String representation of the resource."""
        return f"{self.get_resource_type()}/{self.name}"
    
    def __eq__(self, other: Any) -> bool:
        """Compare resources for equality."""
        if not isinstance(other, Resource):
            return False
        
        # If both resources have IDs, compare by ID
        if self.id and other.id:
            return self.id == other.id
        
        # If one or both don't have IDs, fall back to comparing type and name
        return (self.get_resource_type() == other.get_resource_type() and 
                self.name == other.name)
    
    def diff(self, other: "Resource") -> Dict[str, Dict[str, Any]]:
        """
        Calculate the difference between two resources.
        
        Args:
            other: Another resource to compare with
            
        Returns:
            Dict: Dictionary of changed fields with their old and new values
        """
        if not isinstance(other, Resource) or self.get_resource_type() != other.get_resource_type():
            return {"resource_type": {"old": self.get_resource_type(), 
                                  "new": getattr(other, "get_resource_type", lambda: None)()}}
        
        # Convert both resources to dictionaries for comparison
        self_dict = self.to_dict()
        other_dict = other.to_dict()
        
        # Compare fields
        changes = {}
        self._compare_dicts(self_dict, other_dict, changes)
        
        return changes
    
    @staticmethod
    def _compare_dicts(d1: Dict, d2: Dict, changes: Dict, path: str = "") -> None:
        """
        Helper to compare two dictionaries recursively and track changes.
        
        Args:
            d1: First dictionary
            d2: Second dictionary
            changes: Dictionary to store changes
            path: Current path in the nested structure
        """
        # Get all keys from both dictionaries
        all_keys = set(d1.keys()) | set(d2.keys())
        
        for key in all_keys:
            current_path = f"{path}.{key}" if path else key
            
            # Key exists in both dictionaries
            if key in d1 and key in d2:
                # Both values are dictionaries, compare recursively
                if isinstance(d1[key], dict) and isinstance(d2[key], dict):
                    Resource._compare_dicts(d1[key], d2[key], changes, current_path)
                # Lists require special handling
                elif isinstance(d1[key], list) and isinstance(d2[key], list):
                    if d1[key] != d2[key]:
                        changes[current_path] = {"old": d1[key], "new": d2[key]}
                # Simple value comparison
                elif d1[key] != d2[key]:
                    changes[current_path] = {"old": d1[key], "new": d2[key]}
            
            # Key exists only in d1
            elif key in d1:
                changes[current_path] = {"old": d1[key], "new": None}
            
            # Key exists only in d2
            else:
                changes[current_path] = {"old": None, "new": d2[key]}