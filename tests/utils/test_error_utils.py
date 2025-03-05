"""Tests for the error handling utilities module."""
import unittest
from unittest.mock import MagicMock, patch

import requests

from sublime_migration_cli.utils.error_utils import (
    SublimeError,
    ApiError,
    AuthenticationError,
    ResourceNotFoundError,
    ConfigurationError,
    ValidationError,
    MigrationError,
    handle_api_error,
    ErrorHandler
)


class TestErrorClasses(unittest.TestCase):
    """Test case for the error classes."""

    def test_sublime_error(self):
        """Test the SublimeError class."""
        error = SublimeError("Test error", {"key": "value"})
        self.assertEqual(str(error), "Test error")
        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.details, {"key": "value"})

    def test_api_error(self):
        """Test the ApiError class."""
        error = ApiError(
            "Test API error",
            status_code=400,
            response={"error": "Bad request"},
            request_info={"method": "GET", "url": "https://example.com"}
        )
        self.assertEqual(str(error), "API Error (400): Test API error")
        self.assertEqual(error.message, "API Error (400): Test API error")
        self.assertEqual(error.status_code, 400)
        self.assertEqual(error.response, {"error": "Bad request"})
        self.assertEqual(error.request_info, {"method": "GET", "url": "https://example.com"})

    def test_authentication_error(self):
        """Test the AuthenticationError class."""
        error = AuthenticationError(status_code=401)
        self.assertEqual(str(error), "API Error (401): Authentication failed")
        self.assertEqual(error.status_code, 401)

    def test_resource_not_found_error(self):
        """Test the ResourceNotFoundError class."""
        error = ResourceNotFoundError("rule", "12345", status_code=404)
        self.assertEqual(str(error), "API Error (404): Rule with ID '12345' not found")
        self.assertEqual(error.resource_type, "rule")
        self.assertEqual(error.resource_id, "12345")
        self.assertEqual(error.status_code, 404)

    def test_configuration_error(self):
        """Test the ConfigurationError class."""
        error = ConfigurationError("Missing API key", "api_key")
        self.assertEqual(str(error), "Missing API key")
        self.assertEqual(error.config_key, "api_key")

    def test_validation_error(self):
        """Test the ValidationError class."""
        error = ValidationError("Invalid value", "field_name", "bad_value")
        self.assertEqual(str(error), "Invalid value")
        self.assertEqual(error.field, "field_name")
        self.assertEqual(error.value, "bad_value")

    def test_migration_error(self):
        """Test the MigrationError class."""
        error = MigrationError(
            "Migration failed",
            stage="export",
            resource_type="rule",
            resource_name="My Rule"
        )
        self.assertEqual(str(error), "Migration failed")
        self.assertEqual(error.stage, "export")
        self.assertEqual(error.resource_type, "rule")
        self.assertEqual(error.resource_name, "My Rule")


class TestHandleApiError(unittest.TestCase):
    """Test case for the handle_api_error function."""

    def create_http_error(self, status_code, json_response=None, text_response=None):
        """Create a mock requests.HTTPError for testing."""
        response = MagicMock()
        response.status_code = status_code
        
        if json_response:
            response.json.return_value = json_response
        else:
            response.json.side_effect = ValueError("Invalid JSON")
            response.text = text_response or "Error text"
        
        request = MagicMock()
        request.method = "GET"
        request.url = "https://example.com/api/resource/123"
        
        error = requests.exceptions.HTTPError("HTTP Error")
        error.response = response
        error.request = request
        
        return error

    def test_handle_http_error_401(self):
        """Test handling a 401 HTTP error."""
        http_error = self.create_http_error(
            401, 
            json_response={"error": {"message": "Unauthorized"}}
        )
        
        result = handle_api_error(http_error)
        
        self.assertIsInstance(result, AuthenticationError)
        self.assertEqual(result.status_code, 401)
        self.assertEqual(result.message, "API Error (401): Unauthorized")

    def test_handle_http_error_404(self):
        """Test handling a 404 HTTP error."""
        http_error = self.create_http_error(
            404, 
            json_response={"error": {"message": "Not found"}}
        )
        
        result = handle_api_error(http_error)
        
        self.assertIsInstance(result, ResourceNotFoundError)
        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.resource_type, "resource")
        self.assertEqual(result.resource_id, "123")

    def test_handle_http_error_500(self):
        """Test handling a 500 HTTP error."""
        http_error = self.create_http_error(
            500, 
            json_response={"error": {"message": "Server error"}}
        )
        
        result = handle_api_error(http_error)
        
        self.assertIsInstance(result, ApiError)
        self.assertEqual(result.status_code, 500)
        self.assertEqual(result.message, "API Error (500): Server error")

    def test_handle_http_error_invalid_json(self):
        """Test handling an HTTP error with invalid JSON response."""
        http_error = self.create_http_error(
            400, 
            text_response="Bad request"
        )
        
        result = handle_api_error(http_error)
        
        self.assertIsInstance(result, ApiError)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.response, {"raw": "Bad request"})

    def test_handle_connection_error(self):
        """Test handling a connection error."""
        error = requests.exceptions.ConnectionError("Connection refused")
        
        result = handle_api_error(error)
        
        self.assertIsInstance(result, ApiError)
        self.assertTrue("Connection error" in result.message)

    def test_handle_timeout_error(self):
        """Test handling a timeout error."""
        error = requests.exceptions.Timeout("Request timed out")
        
        result = handle_api_error(error)
        
        self.assertIsInstance(result, ApiError)
        self.assertTrue("Request timed out" in result.message)

    def test_handle_sublime_error(self):
        """Test handling an existing SublimeError."""
        original_error = ValidationError("Original error", "field", "value")
        
        result = handle_api_error(original_error)
        
        self.assertIs(result, original_error)  # Should return the same object

    def test_handle_generic_error(self):
        """Test handling a generic exception."""
        error = ValueError("Generic error")
        
        result = handle_api_error(error)
        
        self.assertIsInstance(result, SublimeError)
        self.assertTrue("Unexpected error" in result.message)
        self.assertTrue("Generic error" in result.message)


class TestErrorHandler(unittest.TestCase):
    """Test case for the ErrorHandler class."""

    def test_is_fatal_error_authentication(self):
        """Test identifying authentication errors as fatal."""
        error = AuthenticationError()
        self.assertTrue(ErrorHandler.is_fatal_error(error))

    def test_is_fatal_error_configuration(self):
        """Test identifying configuration errors as fatal."""
        error = ConfigurationError("Missing config")
        self.assertTrue(ErrorHandler.is_fatal_error(error))

    def test_is_fatal_error_server_error(self):
        """Test identifying server errors as fatal."""
        error = ApiError("Server error", status_code=500)
        self.assertTrue(ErrorHandler.is_fatal_error(error))

    def test_is_fatal_error_client_error(self):
        """Test identifying client errors as non-fatal."""
        error = ApiError("Client error", status_code=400)
        self.assertFalse(ErrorHandler.is_fatal_error(error))

    def test_is_fatal_error_validation(self):
        """Test identifying validation errors as non-fatal."""
        error = ValidationError("Invalid input")
        self.assertFalse(ErrorHandler.is_fatal_error(error))

    def test_is_fatal_error_migration(self):
        """Test identifying migration errors as non-fatal."""
        error = MigrationError("Migration failed")
        self.assertFalse(ErrorHandler.is_fatal_error(error))

    def test_format_error_for_display_sublime_error(self):
        """Test formatting a SublimeError for display."""
        error = SublimeError("Test error", {"field": "value"})
        result = ErrorHandler.format_error_for_display(error)
        
        self.assertEqual(result["message"], "Test error")
        self.assertEqual(result["type"], "SublimeError")
        self.assertEqual(result["details"], {"field": "value"})

    def test_format_error_for_display_api_error(self):
        """Test formatting an ApiError for display."""
        error = ApiError("Test API error", status_code=404)
        result = ErrorHandler.format_error_for_display(error)
        
        self.assertEqual(result["message"], "Test API error")
        self.assertEqual(result["type"], "ApiError")
        self.assertEqual(result["status_code"], 404)

    def test_format_error_for_display_resource_not_found(self):
        """Test formatting a ResourceNotFoundError for display."""
        error = ResourceNotFoundError("rule", "123")
        result = ErrorHandler.format_error_for_display(error)
        
        self.assertEqual(result["type"], "ResourceNotFoundError")
        self.assertEqual(result["resource_type"], "rule")
        self.assertEqual(result["resource_id"], "123")

    def test_format_error_for_display_generic_exception(self):
        """Test formatting a generic exception for display."""
        error = ValueError("Generic error")
        result = ErrorHandler.format_error_for_display(error)
        
        self.assertEqual(result["message"], "Generic error")
        self.assertEqual(result["type"], "ValueError")


if __name__ == '__main__':
    unittest.main()