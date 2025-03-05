"""Utilities for working with the Sublime Security API."""
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from contextlib import nullcontext

from sublime_migration_cli.presentation.base import OutputFormatter

# Type for generic items
T = TypeVar('T')


class PaginatedFetcher:
    """Helper for fetching paginated resources from the API."""
    
    def __init__(self, client, formatter: Optional[OutputFormatter] = None):
        """Initialize with API client and optional formatter.
        
        Args:
            client: API client that provides get/post methods
            formatter: Optional output formatter for progress display
        """
        self.client = client
        self.formatter = formatter
    
    def fetch_all(self, 
                 endpoint: str, 
                 params: Optional[Dict] = None, 
                 progress_message: Optional[str] = None,
                 result_extractor: Optional[Callable[[Dict], List[T]]] = None,
                 total_extractor: Optional[Callable[[Dict], int]] = None,
                 page_size: int = 100) -> List[T]:
        """
        Fetch all items from a paginated API endpoint.
        
        Args:
            endpoint: API endpoint path
            params: Optional base parameters
            progress_message: Message for progress display
            result_extractor: Function to extract items from response
            total_extractor: Function to extract total count from response
            page_size: Number of items per page
            
        Returns:
            List[T]: All items from the paginated endpoint
        """
        # Initialize default extractors if not provided
        if result_extractor is None:
            result_extractor = extract_items_auto
        
        if total_extractor is None:
            total_extractor = extract_total_auto
        
        # Initialize collection and pagination variables
        all_items = []
        offset = 0
        total = None
        
        # Copy and update params to avoid modifying the original
        params = params.copy() if params else {}
        params["limit"] = page_size
        
        # Use progress context if formatter is provided and message is specified
        progress_context = (
            self.formatter.create_progress(progress_message)
            if self.formatter and progress_message
            else nullcontext()
        )
        
        with progress_context as progress_data:
            progress, task = progress_data if progress_data else (None, None)
            
            # Continue fetching until we have all items
            while True:
                # Update offset for pagination
                page_params = params.copy()
                page_params["offset"] = offset
                
                # Fetch a page of items
                response = self.client.get(endpoint, params=page_params)
                
                # Extract items and total from the response
                page_items = result_extractor(response)
                page_total = total_extractor(response)
                
                # Update total if not set yet
                if total is None:
                    total = page_total
                    # Update progress total if we have a progress bar
                    if progress and task:
                        progress.update(task, total=total)
                
                # Add items to our collection
                all_items.extend(page_items)
                
                # Update progress if we have a progress bar
                if progress and task:
                    progress.update(task, completed=len(all_items))
                
                # Check if we've fetched all items
                if len(all_items) >= total or not page_items:
                    break
                
                # Update offset for next page
                offset += page_size
        
        return all_items


# Helper functions for extracting data from API responses

def extract_items_auto(response: Any) -> List[Any]:
    """
    Automatically extract items from a response based on its structure.
    
    Handles:
    - Direct list responses
    - Dict with known item keys (rules, actions, etc.)
    - Dict with items under a generic 'items' or 'data' key
    
    Args:
        response: API response object
        
    Returns:
        List[Any]: Extracted items
    """
    if isinstance(response, list):
        return response
    
    if not isinstance(response, dict):
        return []
    
    # Check for common item keys
    for key in ["rules", "feeds", "actions", "lists", "exclusions", "items", "data"]:
        if key in response and isinstance(response[key], list):
            return response[key]
    
    # If no recognized keys, return the dict itself as a single item
    return [response]


def extract_total_auto(response: Any) -> int:
    """
    Automatically extract the total count from a response based on its structure.
    
    Handles:
    - Direct list responses (returns length)
    - Dict with a 'total' key
    - Dict with a 'count' key
    - Dict with a 'meta.total' or 'pagination.total' pattern
    
    Args:
        response: API response object
        
    Returns:
        int: Total number of items
    """
    if isinstance(response, list):
        return len(response)
    
    if not isinstance(response, dict):
        return 0
    
    # Check for common total keys
    if "total" in response:
        return response["total"]
    
    if "count" in response:
        return response["count"]
    
    # Check for nested total in meta or pagination
    meta = response.get("meta", {})
    if isinstance(meta, dict) and "total" in meta:
        return meta["total"]
    
    pagination = response.get("pagination", {})
    if isinstance(pagination, dict) and "total" in pagination:
        return pagination["total"]
    
    # If no total found, check for item keys and return their length
    for key in ["rules", "feeds", "actions", "lists", "exclusions", "items", "data"]:
        if key in response and isinstance(response[key], list):
            return len(response[key])
    
    # If all else fails, return 0
    return 0


def extract_items_from_key(key: str) -> Callable[[Dict], List[Any]]:
    """
    Create an extractor function for a specific response key.
    
    Args:
        key: The key to extract items from
        
    Returns:
        Callable: Function that extracts items from the response
    """
    def extractor(response: Dict) -> List[Any]:
        if not isinstance(response, dict):
            return []
        return response.get(key, []) if isinstance(response.get(key), list) else []
    return extractor


def extract_total_from_key(key: str) -> Callable[[Dict], int]:
    """
    Create a total extractor function for a specific response key.
    
    Args:
        key: The key to extract total from
        
    Returns:
        Callable: Function that extracts total from the response
    """
    def extractor(response: Dict) -> int:
        if not isinstance(response, dict):
            return 0
        return response.get(key, 0)
    return extractor