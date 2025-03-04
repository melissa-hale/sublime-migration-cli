"""API client for Sublime Security Platform."""
import os
from typing import Dict, List, Optional

import requests

from sublime_migration_cli.api.regions import Region, get_region


class ApiClient:
    """Simple client for interacting with the Sublime Security API."""

    def __init__(self, api_key: str, region_code: str):
        """Initialize API client.

        Args:
            api_key: API key for authentication
            region_code: Region code to connect to
        """
        self.api_key = api_key
        self.region = get_region(region_code)
        self.base_url = self.region.api_url
        
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
        
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a GET request to the API.
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Optional query parameters
            
        Returns:
            Dict: Response data
            
        Raises:
            requests.exceptions.RequestException: If the request fails
        """
        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        return response.json()
        
    def post(self, endpoint: str, data: Dict) -> Dict:
        """Make a POST request to the API.
        
        Args:
            endpoint: API endpoint (without base URL)
            data: Request payload
            
        Returns:
            Dict: Response data
            
        Raises:
            requests.exceptions.RequestException: If the request fails
        """
        url = f"{self.base_url}{endpoint}"
        response = requests.post(url, headers=self._get_headers(), json=data)
        response.raise_for_status()
        return response.json()

    def patch(self, endpoint: str, data: Dict) -> Dict:
        """Make a PATCH request to the API.
        
        Args:
            endpoint: API endpoint (without base URL)
            data: Request payload
            
        Returns:
            Dict: Response data
            
        Raises:
            requests.exceptions.RequestException: If the request fails
        """
        url = f"{self.base_url}{endpoint}"
        response = requests.patch(url, headers=self._get_headers(), json=data)
        response.raise_for_status()
        return response.json()


def get_api_client_from_env_or_args(api_key: Optional[str] = None, region: Optional[str] = None, destination: Optional[bool] = False) -> ApiClient:
    """Create an API client using environment variables or args.
    
    Args:
        api_key: API key from command-line args (optional)
        region: Region code from command-line args (optional)
        
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
    
    return ApiClient(api_key=api_key, region_code=region)
