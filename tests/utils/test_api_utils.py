"""Tests for the API utilities module."""
import unittest
from unittest.mock import MagicMock, patch

from sublime_migration_cli.utils.api_utils import (
    PaginatedFetcher,
    extract_items_auto,
    extract_total_auto,
    extract_items_from_key,
    extract_total_from_key
)


class TestApiUtils(unittest.TestCase):
    """Test case for the API utilities module."""

    def test_extract_items_auto_from_list(self):
        """Test extracting items from a direct list response."""
        response = [{"id": 1}, {"id": 2}, {"id": 3}]
        items = extract_items_auto(response)
        self.assertEqual(items, response)

    def test_extract_items_auto_from_dict_with_known_key(self):
        """Test extracting items from a dict with a known key."""
        response = {"rules": [{"id": 1}, {"id": 2}, {"id": 3}]}
        items = extract_items_auto(response)
        self.assertEqual(items, response["rules"])

    def test_extract_items_auto_from_dict_with_generic_key(self):
        """Test extracting items from a dict with a generic key."""
        response = {"items": [{"id": 1}, {"id": 2}, {"id": 3}]}
        items = extract_items_auto(response)
        self.assertEqual(items, response["items"])

    def test_extract_items_auto_from_unknown_dict(self):
        """Test extracting items from a dict with no known keys."""
        response = {"unknown": "data"}
        items = extract_items_auto(response)
        self.assertEqual(items, [response])

    def test_extract_items_auto_from_non_dict_non_list(self):
        """Test extracting items from a non-dict, non-list response."""
        response = "not a dict or list"
        items = extract_items_auto(response)
        self.assertEqual(items, [])

    def test_extract_total_auto_from_list(self):
        """Test extracting total from a direct list response."""
        response = [{"id": 1}, {"id": 2}, {"id": 3}]
        total = extract_total_auto(response)
        self.assertEqual(total, 3)

    def test_extract_total_auto_from_dict_with_total(self):
        """Test extracting total from a dict with a 'total' key."""
        response = {"total": 10, "items": [{"id": 1}, {"id": 2}, {"id": 3}]}
        total = extract_total_auto(response)
        self.assertEqual(total, 10)

    def test_extract_total_auto_from_dict_with_count(self):
        """Test extracting total from a dict with a 'count' key."""
        response = {"count": 5, "items": [{"id": 1}, {"id": 2}, {"id": 3}]}
        total = extract_total_auto(response)
        self.assertEqual(total, 5)

    def test_extract_total_auto_from_dict_with_meta_total(self):
        """Test extracting total from a dict with a 'meta.total' pattern."""
        response = {"meta": {"total": 15}, "items": [{"id": 1}, {"id": 2}, {"id": 3}]}
        total = extract_total_auto(response)
        self.assertEqual(total, 15)

    def test_extract_total_auto_from_dict_with_pagination_total(self):
        """Test extracting total from a dict with a 'pagination.total' pattern."""
        response = {"pagination": {"total": 25}, "items": [{"id": 1}, {"id": 2}, {"id": 3}]}
        total = extract_total_auto(response)
        self.assertEqual(total, 25)

    def test_extract_total_auto_from_dict_with_items(self):
        """Test extracting total from a dict with items but no total field."""
        response = {"items": [{"id": 1}, {"id": 2}, {"id": 3}]}
        total = extract_total_auto(response)
        self.assertEqual(total, 3)

    def test_extract_items_from_key(self):
        """Test the extract_items_from_key function."""
        extractor = extract_items_from_key("rules")
        response = {"rules": [{"id": 1}, {"id": 2}, {"id": 3}]}
        items = extractor(response)
        self.assertEqual(items, response["rules"])

    def test_extract_items_from_key_missing(self):
        """Test the extract_items_from_key function with a missing key."""
        extractor = extract_items_from_key("missing")
        response = {"rules": [{"id": 1}, {"id": 2}, {"id": 3}]}
        items = extractor(response)
        self.assertEqual(items, [])

    def test_extract_items_from_key_not_a_list(self):
        """Test the extract_items_from_key function with a non-list value."""
        extractor = extract_items_from_key("rules")
        response = {"rules": "not a list"}
        items = extractor(response)
        self.assertEqual(items, [])

    def test_extract_total_from_key(self):
        """Test the extract_total_from_key function."""
        extractor = extract_total_from_key("total")
        response = {"total": 10}
        total = extractor(response)
        self.assertEqual(total, 10)

    def test_extract_total_from_key_missing(self):
        """Test the extract_total_from_key function with a missing key."""
        extractor = extract_total_from_key("missing")
        response = {"total": 10}
        total = extractor(response)
        self.assertEqual(total, 0)


class TestPaginatedFetcher(unittest.TestCase):
    """Test case for the PaginatedFetcher class."""

    def setUp(self):
        """Set up the test case."""
        self.client = MagicMock()
        self.formatter = MagicMock()
        self.progress = MagicMock()
        self.task = 1
        self.formatter.create_progress.return_value.__enter__.return_value = (self.progress, self.task)
        self.fetcher = PaginatedFetcher(self.client, self.formatter)

    def test_fetch_all_single_page(self):
        """Test fetching a single page of results."""
        # Set up the mock to return a single page of results
        self.client.get.return_value = {
            "items": [{"id": 1}, {"id": 2}, {"id": 3}],
            "total": 3
        }
        
        # Call the fetch_all method
        items = self.fetcher.fetch_all(
            "/test",
            params={"param": "value"},
            progress_message="Test progress"
        )
        
        # Check that the client was called correctly
        self.client.get.assert_called_once_with(
            "/test",
            params={"param": "value", "limit": 100, "offset": 0}
        )
        
        # Check that the formatter was used correctly
        self.formatter.create_progress.assert_called_once_with("Test progress")
        
        # Check that we got the expected items
        self.assertEqual(items, [{"id": 1}, {"id": 2}, {"id": 3}])
        
        # Check that the progress was updated correctly
        self.progress.update.assert_called_with(self.task, completed=3)

    def test_fetch_all_multiple_pages(self):
        """Test fetching multiple pages of results."""
        # Set up the mock to return multiple pages of results
        self.client.get.side_effect = [
            {
                "items": [{"id": 1}, {"id": 2}, {"id": 3}],
                "total": 5
            },
            {
                "items": [{"id": 4}, {"id": 5}],
                "total": 5
            }
        ]
        
        # Call the fetch_all method
        items = self.fetcher.fetch_all(
            "/test",
            params={"param": "value"},
            progress_message="Test progress"
        )
        
        # Check that the client was called correctly for both pages
        self.assertEqual(self.client.get.call_count, 2)
        self.client.get.assert_any_call(
            "/test",
            params={"param": "value", "limit": 100, "offset": 0}
        )
        self.client.get.assert_any_call(
            "/test",
            params={"param": "value", "limit": 100, "offset": 100}
        )
        
        # Check that the formatter was used correctly
        self.formatter.create_progress.assert_called_once_with("Test progress")
        
        # Check that we got the expected items
        self.assertEqual(items, [
            {"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}, {"id": 5}
        ])
        
        # Check that the progress was updated correctly
        self.progress.update.assert_any_call(self.task, total=5)
        self.progress.update.assert_any_call(self.task, completed=3)
        self.progress.update.assert_any_call(self.task, completed=5)

    def test_fetch_all_custom_extractors(self):
        """Test fetching with custom extractors."""
        # Set up the mock to return a custom response format
        self.client.get.return_value = {
            "custom_items": [{"id": 1}, {"id": 2}, {"id": 3}],
            "custom_total": 3
        }
        
        # Define custom extractors
        def custom_result_extractor(response):
            return response.get("custom_items", [])
            
        def custom_total_extractor(response):
            return response.get("custom_total", 0)
        
        # Call the fetch_all method with custom extractors
        items = self.fetcher.fetch_all(
            "/test",
            params={"param": "value"},
            progress_message="Test progress",
            result_extractor=custom_result_extractor,
            total_extractor=custom_total_extractor
        )
        
        # Check that we got the expected items
        self.assertEqual(items, [{"id": 1}, {"id": 2}, {"id": 3}])

    def test_fetch_all_without_formatter(self):
        """Test fetching without a formatter."""
        # Create a fetcher without a formatter
        fetcher = PaginatedFetcher(self.client)
        
        # Set up the mock to return a single page of results
        self.client.get.return_value = {
            "items": [{"id": 1}, {"id": 2}, {"id": 3}],
            "total": 3
        }
        
        # Call the fetch_all method
        items = fetcher.fetch_all(
            "/test",
            params={"param": "value"},
            progress_message="Test progress"  # This should be ignored
        )
        
        # Check that the client was called correctly
        self.client.get.assert_called_once_with(
            "/test",
            params={"param": "value", "limit": 100, "offset": 0}
        )
        
        # Check that the formatter was not used
        self.formatter.create_progress.assert_not_called()
        
        # Check that we got the expected items
        self.assertEqual(items, [{"id": 1}, {"id": 2}, {"id": 3}])


if __name__ == '__main__':
    unittest.main()