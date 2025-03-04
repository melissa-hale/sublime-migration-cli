"""Basic tests for API client."""
import pytest
from unittest.mock import patch, MagicMock

from sublime_cli.api.client import ApiClient, get_api_client_from_env_or_args
from sublime_cli.api.regions import get_region


def test_api_client_initialization():
    """Test basic API client initialization."""
    client = ApiClient("test-api-key", "NA_EAST")
    
    assert client.api_key == "test-api-key"
    assert client.region == get_region("NA_EAST")
    assert client.base_url == "https://platform.sublime.security"


@patch("sublime_cli.api.client.os.environ")
def test_get_client_from_env(mock_environ):
    """Test creating client from environment variables."""
    mock_environ.get.side_effect = lambda key, default=None: {
        "SUBLIME_API_KEY": "env-api-key",
        "SUBLIME_REGION": "EU_DUBLIN"
    }.get(key, default)
    
    client = get_api_client_from_env_or_args()
    
    assert client.api_key == "env-api-key"
    assert client.region.code == "EU_DUBLIN"


@patch("sublime_cli.api.client.requests.get")
def test_get_request(mock_get):
    """Test making a GET request."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {"test": "data"}
    mock_get.return_value = mock_response
    
    # Create client and make request
    client = ApiClient("test-api-key", "NA_EAST")
    result = client.get("/test/endpoint")
    
    # Assert request was made correctly
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    
    # Verify URL
    assert args[0] == "https://platform.sublime.security/test/endpoint"
    
    # Verify headers
    assert "Authorization" in kwargs["headers"]
    assert kwargs["headers"]["Authorization"] == "Bearer test-api-key"
    
    # Verify result
    assert result == {"test": "data"}
