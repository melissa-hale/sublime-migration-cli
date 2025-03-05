"""Utilities for filtering API resources."""
from typing import Any, Callable, Dict, List, Optional, Set, Union


def filter_by_ids(items: List[Dict], 
                 include_ids: Optional[str] = None, 
                 exclude_ids: Optional[str] = None,
                 id_field: str = "id") -> List[Dict]:
    """
    Filter a list of items by ID.
    
    Args:
        items: List of items to filter
        include_ids: Comma-separated list of IDs to include
        exclude_ids: Comma-separated list of IDs to exclude
        id_field: Field name containing the ID in each item
        
    Returns:
        List[Dict]: Filtered items
    """
    filtered = items
    
    # Filter by included IDs if specified
    if include_ids:
        ids = set(id.strip() for id in include_ids.split(","))
        filtered = [item for item in filtered if item.get(id_field) in ids]
    
    # Filter by excluded IDs if specified
    if exclude_ids:
        ids = set(id.strip() for id in exclude_ids.split(","))
        filtered = [item for item in filtered if item.get(id_field) not in ids]
    
    return filtered


def filter_by_types(items: List[Dict],
                   include_types: Optional[str] = None,
                   exclude_types: Optional[str] = None,
                   ignored_types: Optional[Set[str]] = None,
                   type_field: str = "type") -> List[Dict]:
    """
    Filter a list of items by type.
    
    Args:
        items: List of items to filter
        include_types: Comma-separated list of types to include
        exclude_types: Comma-separated list of types to exclude
        ignored_types: Set of types to always exclude
        type_field: Field name containing the type in each item
        
    Returns:
        List[Dict]: Filtered items
    """
    # First, exclude ignored types if specified
    filtered = items
    if ignored_types:
        filtered = [item for item in filtered if item.get(type_field) not in ignored_types]
    
    # Filter by included types if specified
    if include_types:
        types = set(t.strip() for t in include_types.split(","))
        filtered = [item for item in filtered if item.get(type_field) in types]
    
    # Filter by excluded types if specified
    if exclude_types:
        types = set(t.strip() for t in exclude_types.split(","))
        filtered = [item for item in filtered if item.get(type_field) not in types]
    
    return filtered


def filter_by_creator(items: List[Dict],
                     include_system_created: bool = False,
                     excluded_authors: Optional[Set[str]] = None) -> List[Dict]:
    """
    Filter a list of items by creator.
    
    Args:
        items: List of items to filter
        include_system_created: Whether to include system-created items
        excluded_authors: Set of author names to exclude if not include_system_created
        
    Returns:
        List[Dict]: Filtered items
    """
    if include_system_created or not excluded_authors:
        return items
    
    return [
        item for item in items 
        if (item.get("created_by_user_name") not in excluded_authors and
            item.get("created_by_org_name") not in excluded_authors)
    ]


def apply_filters(items: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
    """
    Apply multiple filters to a list of items.
    
    Args:
        items: List of items to filter
        filters: Dictionary of filter functions and their parameters
        
    Returns:
        List[Dict]: Filtered items
    """
    filtered = items
    
    # Apply ID filters
    if any(k in filters for k in ["include_ids", "exclude_ids", "id_field"]):
        filtered = filter_by_ids(
            filtered,
            include_ids=filters.get("include_ids"),
            exclude_ids=filters.get("exclude_ids"),
            id_field=filters.get("id_field", "id")
        )
    
    # Apply type filters
    if any(k in filters for k in ["include_types", "exclude_types", "ignored_types", "type_field"]):
        filtered = filter_by_types(
            filtered,
            include_types=filters.get("include_types"),
            exclude_types=filters.get("exclude_types"),
            ignored_types=filters.get("ignored_types"),
            type_field=filters.get("type_field", "type")
        )
    
    # Apply creator filters
    if any(k in filters for k in ["include_system_created", "excluded_authors"]):
        filtered = filter_by_creator(
            filtered,
            include_system_created=filters.get("include_system_created", False),
            excluded_authors=filters.get("excluded_authors")
        )
    
    # Apply custom filters
    for custom_filter in filters.get("custom_filters", []):
        if callable(custom_filter):
            filtered = custom_filter(filtered)
    
    return filtered


def create_attribute_filter(attr_name: str, attr_value: Any) -> Callable[[List[Dict]], List[Dict]]:
    """
    Create a filter function for a specific attribute value.
    
    Args:
        attr_name: Name of the attribute to filter on
        attr_value: Value to filter for
        
    Returns:
        Callable: Function that filters items by the attribute
    """
    def filter_func(items: List[Dict]) -> List[Dict]:
        return [item for item in items if item.get(attr_name) == attr_value]
    return filter_func


def create_boolean_filter(attr_name: str, value: bool = True) -> Callable[[List[Dict]], List[Dict]]:
    """
    Create a filter function for a boolean attribute.
    
    Args:
        attr_name: Name of the boolean attribute to filter on
        value: Boolean value to filter for (True or False)
        
    Returns:
        Callable: Function that filters items by the boolean attribute
    """
    def filter_func(items: List[Dict]) -> List[Dict]:
        return [item for item in items if bool(item.get(attr_name)) == value]
    return filter_func