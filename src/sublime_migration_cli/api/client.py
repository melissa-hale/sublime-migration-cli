"""API client for Sublime Security Platform."""
import os
import time
from typing import Dict, List, Optional, Union, Any

import requests

from sublime_migration_cli.api.regions import Region, get_region
from sublime_migration_cli.utils.errors import (
    ApiError, 
    AuthenticationError, 
    ResourceNotFoundError,
    handle_api_error
)


class ApiClient:
    """Client for interacting with the Sublime Security API."""

    def __init__(self, api_key: str, region_code: str, max_retries: int = 3, retry_delay: float = 1.0):
        """Initialize API client.

        Args:
            api_key: API key for authentication
            region_code: Region code to connect to
            max_retries: Maximum number of retry attempts for transient errors
            retry_delay: Base delay between retries (will be exponentially increased)
        """
        self.api_key = api_key
        self.region = get_region(region_code)
        self.base_url = self.region.api_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
    def _get_headers(self) -> Dict[str, str]:
        """Create request headers with auth token.
        
        Returns:
            Dict[str, str]: Headers for API requests
        """
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    def _make_request(self, method: str, endpoint: str, 
                     params: Optional[Dict] = None, 
                     data: Optional[Dict] = None,
                     json: Optional[Dict] = None,
                     retry_on_codes: Optional[List[int]] = None) -> Dict:
        """
        Make an HTTP request to the API with retries for transient errors.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            params: Optional query parameters
            data: Optional request body (form data)
            json: Optional request body (JSON)
            retry_on_codes: HTTP status codes to retry on
            
        Returns:
            Dict: Response data
            
        Raises:
            ApiError: If the request fails
        """
        if retry_on_codes is None:
            retry_on_codes = [429, 500, 502, 503, 504]
        
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        
        for attempt in range(self.max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    data=data,
                    json=json,
                    timeout=(10, 30)  # (connect_timeout, read_timeout)
                )
                
                # Check if we got a retryable status code
                if response.status_code in retry_on_codes and attempt < self.max_retries - 1:
                    # Calculate exponential backoff with jitter
                    delay = self.retry_delay * (2 ** attempt) * (0.8 + 0.4 * (time.time() % 1))
                    time.sleep(delay)
                    continue
                    
                # Raise an exception for error status codes
                response.raise_for_status()
                
                # Return the JSON response for success
                return response.json()
                
            except (requests.exceptions.RequestException, ValueError) as e:
                # Don't retry on client errors (4xx, except those in retry_on_codes)
                if isinstance(e, requests.exceptions.HTTPError):
                    status_code = e.response.status_code
                    if status_code // 100 == 4 and status_code not in retry_on_codes:
                        raise handle_api_error(e)
                    
                # On the last attempt, raise the error
                if attempt >= self.max_retries - 1:
                    raise handle_api_error(e)
                
                # For other errors, retry with backoff
                delay = self.retry_delay * (2 ** attempt) * (0.8 + 0.4 * (time.time() % 1))
                time.sleep(delay)
        
        # This should not be reached, but just in case
        raise ApiError("Maximum retry attempts exceeded")
        
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a GET request to the API.
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Optional query parameters
            
        Returns:
            Dict: Response data
            
        Raises:
            ApiError: If the request fails
        """
        return self._make_request("GET", endpoint, params=params)
        
    def post(self, endpoint: str, data: Dict) -> Dict:
        """Make a POST request to the API.
        
        Args:
            endpoint: API endpoint (without base URL)
            data: Request payload
            
        Returns:
            Dict: Response data
            
        Raises:
            ApiError: If the request fails
        """
        return self._make_request("POST", endpoint, json=data)

    def patch(self, endpoint: str, data: Dict) -> Dict:
        """Make a PATCH request to the API.
        
        Args:
            endpoint: API endpoint (without base URL)
            data: Request payload
            
        Returns:
            Dict: Response data
            
        Raises:
            ApiError: If the request fails
        """
        return self._make_request("PATCH", endpoint, json=data)
        
    def delete(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a DELETE request to the API.
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Optional query parameters
            
        Returns:
            Dict: Response data or empty dict
            
        Raises:
            ApiError: If the request fails
        """
        return self._make_request("DELETE", endpoint, params=params)


def get_api_client_from_env_or_args(api_key: Optional[str] = None, 
                                   region: Optional[str] = None, 
                                   destination: Optional[bool] = False,
                                   max_retries: int = 3) -> ApiClient:
    """Create an API client using environment variables or args.
    
    Args:
        api_key: API key from command-line args (optional)
        region: Region code from command-line args (optional)
        destination: Whether this is for a destination instance
        max_retries: Maximum number of retry attempts
        
    Returns:
        ApiClient: Configured API client
        
    Raises:
        ValueError: If API key or region is not provided
    """
    # First try command-line args
    if destination:
        # Use destination environment variables
        api_key = api_key or os.environ.get("SUBLIME_DEST_API_KEY")
        region = region or os.environ.get("SUBLIME_DEST_REGION")
        error_prefix = "Destination"
        env_var = "SUBLIME_DEST_API_KEY"
    else:
        # Use source environment variables (existing behavior)
        api_key = api_key or os.environ.get("SUBLIME_API_KEY")
        region = region or os.environ.get("SUBLIME_REGION")
        error_prefix = "API"
        env_var = "SUBLIME_API_KEY"
    
    if not api_key:
        raise ValueError(
            f"{error_prefix} key not provided. Use --api-key option or set {env_var} environment variable."
        )
    
    if not region:
        raise ValueError(
            f"Region not provided. Use --region option or set SUBLIME_REGION environment variable."
        )
    
    return ApiClient(api_key=api_key, region_code=region, max_retries=max_retries)