"""Tests for the filter utilities module."""
import unittest

from sublime_migration_cli.utils.filter_utils import (
    filter_by_ids,
    filter_by_types,
    filter_by_creator,
    apply_filters,
    create_attribute_filter,
    create_boolean_filter
)


class TestFilterUtils(unittest.TestCase):
    """Test case for the filter utilities module."""

    def setUp(self):
        """Set up test data."""
        self.test_items = [
            {"id": "id1", "name": "Item 1", "type": "type1", "active": True, "created_by_user_name": "User 1"},
            {"id": "id2", "name": "Item 2", "type": "type2", "active": False, "created_by_user_name": "User 2"},
            {"id": "id3", "name": "Item 3", "type": "type1", "active": True, "created_by_user_name": "System"},
            {"id": "id4", "name": "Item 4", "type": "type3", "active": False, "created_by_org_name": "Sublime Security"},
            {"id": "id5", "name": "Item 5", "type": "type2", "active": True, "created_by_user_name": "User 3"}
        ]

    def test_filter_by_ids_include(self):
        """Test filtering by included IDs."""
        filtered = filter_by_ids(self.test_items, include_ids="id1,id3")
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["id"], "id1")
        self.assertEqual(filtered[1]["id"], "id3")
    
    def test_filter_by_ids_exclude(self):
        """Test filtering by excluded IDs."""
        filtered = filter_by_ids(self.test_items, exclude_ids="id1,id3")
        self.assertEqual(len(filtered), 3)
        self.assertEqual(filtered[0]["id"], "id2")
        self.assertEqual(filtered[1]["id"], "id4")
        self.assertEqual(filtered[2]["id"], "id5")
    
    def test_filter_by_ids_include_and_exclude(self):
        """Test filtering by both included and excluded IDs."""
        filtered = filter_by_ids(self.test_items, include_ids="id1,id2,id3", exclude_ids="id2")
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["id"], "id1")
        self.assertEqual(filtered[1]["id"], "id3")
    
    def test_filter_by_ids_custom_field(self):
        """Test filtering by IDs with a custom ID field."""
        items = [
            {"custom_id": "cid1", "name": "Item 1"},
            {"custom_id": "cid2", "name": "Item 2"},
            {"custom_id": "cid3", "name": "Item 3"}
        ]
        filtered = filter_by_ids(items, include_ids="cid1,cid3", id_field="custom_id")
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["custom_id"], "cid1")
        self.assertEqual(filtered[1]["custom_id"], "cid3")
    
    def test_filter_by_types_include(self):
        """Test filtering by included types."""
        filtered = filter_by_types(self.test_items, include_types="type1")
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["type"], "type1")
        self.assertEqual(filtered[1]["type"], "type1")
    
    def test_filter_by_types_exclude(self):
        """Test filtering by excluded types."""
        filtered = filter_by_types(self.test_items, exclude_types="type1,type3")
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["type"], "type2")
        self.assertEqual(filtered[1]["type"], "type2")
    
    def test_filter_by_types_ignored(self):
        """Test filtering by ignored types."""
        filtered = filter_by_types(self.test_items, ignored_types={"type1"})
        self.assertEqual(len(filtered), 3)
        self.assertEqual(filtered[0]["type"], "type2")
        self.assertEqual(filtered[1]["type"], "type3")
        self.assertEqual(filtered[2]["type"], "type2")
    
    def test_filter_by_types_combined(self):
        """Test combining type filters."""
        filtered = filter_by_types(
            self.test_items, 
            include_types="type1,type2", 
            exclude_types="type1",
            ignored_types={"type3"}
        )
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["type"], "type2")
        self.assertEqual(filtered[1]["type"], "type2")
    
    def test_filter_by_types_custom_field(self):
        """Test filtering by types with a custom type field."""
        items = [
            {"category": "cat1", "name": "Item 1"},
            {"category": "cat2", "name": "Item 2"},
            {"category": "cat1", "name": "Item 3"}
        ]
        filtered = filter_by_types(items, include_types="cat1", type_field="category")
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["category"], "cat1")
        self.assertEqual(filtered[1]["category"], "cat1")
    
    def test_filter_by_creator_exclude_system(self):
        """Test filtering out system-created items."""
        filtered = filter_by_creator(
            self.test_items,
            include_system_created=False,
            excluded_authors={"System", "Sublime Security"}
        )
        self.assertEqual(len(filtered), 3)
        self.assertEqual(filtered[0]["created_by_user_name"], "User 1")
        self.assertEqual(filtered[1]["created_by_user_name"], "User 2")
        self.assertEqual(filtered[2]["created_by_user_name"], "User 3")
    
    def test_filter_by_creator_include_system(self):
        """Test including system-created items."""
        filtered = filter_by_creator(
            self.test_items,
            include_system_created=True,
            excluded_authors={"System", "Sublime Security"}
        )
        self.assertEqual(len(filtered), 5)  # All items should be included
    
    def test_apply_filters_id_and_type(self):
        """Test applying multiple filters (ID and type)."""
        filtered = apply_filters(self.test_items, {
            "include_ids": "id1,id2,id3,id5",
            "include_types": "type1"
        })
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["id"], "id1")
        self.assertEqual(filtered[1]["id"], "id3")
    
    def test_apply_filters_with_creator(self):
        """Test applying multiple filters including creator filter."""
        filtered = apply_filters(self.test_items, {
            "include_types": "type1,type2",
            "include_system_created": False,
            "excluded_authors": {"System", "Sublime Security"}
        })
        self.assertEqual(len(filtered), 3)
        self.assertEqual(filtered[0]["name"], "Item 1")
        self.assertEqual(filtered[1]["name"], "Item 2")
        self.assertEqual(filtered[2]["name"], "Item 5")
    
    def test_apply_filters_with_custom_filter(self):
        """Test applying a custom filter function."""
        # Custom filter that keeps only items with even-numbered IDs
        def even_id_filter(items):
            return [item for item in items if int(item["id"].replace("id", "")) % 2 == 0]
        
        filtered = apply_filters(self.test_items, {
            "include_types": "type1,type2",
            "custom_filters": [even_id_filter]
        })
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["id"], "id2")
        self.assertEqual(filtered[1]["id"], "id4")
    
    def test_create_attribute_filter(self):
        """Test creating and using an attribute filter."""
        name_filter = create_attribute_filter("name", "Item 3")
        filtered = name_filter(self.test_items)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["name"], "Item 3")
    
    def test_create_boolean_filter_true(self):
        """Test creating and using a boolean filter (True)."""
        active_filter = create_boolean_filter("active", True)
        filtered = active_filter(self.test_items)
        self.assertEqual(len(filtered), 3)
        self.assertTrue(all(item["active"] for item in filtered))
    
    def test_create_boolean_filter_false(self):
        """Test creating and using a boolean filter (False)."""
        inactive_filter = create_boolean_filter("active", False)
        filtered = inactive_filter(self.test_items)
        self.assertEqual(len(filtered), 2)
        self.assertFalse(any(item["active"] for item in filtered))


if __name__ == '__main__':
    unittest.main()