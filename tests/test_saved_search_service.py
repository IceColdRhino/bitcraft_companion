"""
Tests for SavedSearchService functionality.

Tests the complete saved search system including persistence, validation,
and management operations.
"""

import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from app.services.saved_search_service import SavedSearchService


class TestSavedSearchService:
    """Test saved search service functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.test_file_path = os.path.join(self.temp_dir, "test_saved_searches.json")

        # Mock the get_user_data_path to use our test file
        self.get_user_data_path_patcher = patch("app.services.saved_search_service.get_user_data_path")
        self.mock_get_user_data_path = self.get_user_data_path_patcher.start()
        self.mock_get_user_data_path.return_value = self.test_file_path

    def teardown_method(self):
        """Clean up test fixtures."""
        self.get_user_data_path_patcher.stop()

        # Clean up test files
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)
        os.rmdir(self.temp_dir)

    def test_service_initialization_no_file(self):
        """Test service initialization when no saved searches file exists."""
        service = SavedSearchService()

        assert service.get_search_count() == 0
        assert service.get_all_searches() == []

    def test_service_initialization_with_existing_file(self):
        """Test service initialization with an existing saved searches file."""
        # Create test data
        test_data = {
            "searches": [
                {
                    "id": "test-id-1",
                    "name": "Test Search",
                    "query": "item=plank tier>2",
                    "created": "2025-01-15T10:30:00Z",
                    "last_used": "2025-01-16T08:15:00Z",
                }
            ]
        }

        # Write test data to file
        with open(self.test_file_path, "w") as f:
            json.dump(test_data, f)

        # Initialize service
        service = SavedSearchService()

        assert service.get_search_count() == 1
        searches = service.get_all_searches()
        assert len(searches) == 1
        assert searches[0]["name"] == "Test Search"
        assert searches[0]["query"] == "item=plank tier>2"

    def test_save_search_success(self):
        """Test successfully saving a new search."""
        service = SavedSearchService()

        search_id = service.save_search("High Tier Items", "tier>3 qty<100")

        assert search_id is not None
        assert service.get_search_count() == 1

        search = service.get_search_by_id(search_id)
        assert search is not None
        assert search["name"] == "High Tier Items"
        assert search["query"] == "tier>3 qty<100"
        assert "created" in search
        assert "last_used" in search

    def test_save_search_validation(self):
        """Test search validation during save."""
        service = SavedSearchService()

        # Empty name should fail
        assert service.save_search("", "tier>3") is None
        assert service.save_search("   ", "tier>3") is None

        # Empty query should fail
        assert service.save_search("Test", "") is None
        assert service.save_search("Test", "   ") is None

        # Duplicate name should fail
        service.save_search("Duplicate", "tier>1")
        assert service.save_search("Duplicate", "tier>2") is None

    def test_get_search_by_name(self):
        """Test retrieving searches by name."""
        service = SavedSearchService()

        search_id = service.save_search("Test Search", "item=stone")

        # Should find exact match
        search = service.get_search_by_name("Test Search")
        assert search is not None
        assert search["id"] == search_id

        # Should be case insensitive
        search = service.get_search_by_name("test search")
        assert search is not None
        assert search["id"] == search_id

        # Should handle whitespace
        search = service.get_search_by_name("  Test Search  ")
        assert search is not None

        # Should return None for non-existent search
        assert service.get_search_by_name("Non-existent") is None

    def test_use_search(self):
        """Test using a search (updating last_used timestamp)."""
        service = SavedSearchService()

        search_id = service.save_search("Test Search", "item=wood")
        original_search = service.get_search_by_id(search_id)
        original_last_used = original_search["last_used"]

        # Add small delay to ensure timestamp difference
        import time

        time.sleep(0.01)

        # Use the search
        query = service.use_search(search_id)

        assert query == "item=wood"

        # Check that last_used was updated
        updated_search = service.get_search_by_id(search_id)
        assert updated_search["last_used"] != original_last_used

        # Using non-existent search should return None
        assert service.use_search("non-existent") is None

    def test_delete_search(self):
        """Test deleting searches."""
        service = SavedSearchService()

        search_id = service.save_search("To Delete", "item=stone")
        assert service.get_search_count() == 1

        # Delete the search
        assert service.delete_search(search_id) is True
        assert service.get_search_count() == 0
        assert service.get_search_by_id(search_id) is None

        # Deleting non-existent search should return False
        assert service.delete_search("non-existent") is False

    def test_update_search_name(self):
        """Test updating search names."""
        service = SavedSearchService()

        search_id = service.save_search("Original Name", "item=plank")

        # Update name successfully
        assert service.update_search_name(search_id, "New Name") is True

        search = service.get_search_by_id(search_id)
        assert search["name"] == "New Name"

        # Create another search
        other_id = service.save_search("Other Search", "tier>5")

        # Try to update to existing name (should fail)
        assert service.update_search_name(search_id, "Other Search") is False

        # Update to empty name should fail
        assert service.update_search_name(search_id, "") is False
        assert service.update_search_name(search_id, "   ") is False

        # Update non-existent search should fail
        assert service.update_search_name("non-existent", "Some Name") is False

    def test_search_ordering(self):
        """Test that searches are returned in last_used order."""
        service = SavedSearchService()

        # Create multiple searches
        id1 = service.save_search("First", "tier=1")
        id2 = service.save_search("Second", "tier=2")
        id3 = service.save_search("Third", "tier=3")

        # Add small delay to ensure time difference
        import time

        time.sleep(0.01)

        # Use searches in different order
        service.use_search(id2)  # Use second
        time.sleep(0.01)
        service.use_search(id1)  # Use first

        # Get all searches - should be ordered by last_used (most recent first)
        searches = service.get_all_searches()
        assert len(searches) == 3
        assert searches[0]["id"] == id1  # Most recently used
        assert searches[1]["id"] == id2  # Second most recently used
        assert searches[2]["id"] == id3  # Least recently used

    def test_clear_all_searches(self):
        """Test clearing all searches."""
        service = SavedSearchService()

        # Add some searches
        service.save_search("Search 1", "tier=1")
        service.save_search("Search 2", "tier=2")
        assert service.get_search_count() == 2

        # Clear all
        assert service.clear_all_searches() is True
        assert service.get_search_count() == 0
        assert service.get_all_searches() == []

    def test_file_persistence(self):
        """Test that searches persist across service instances."""
        # Create first service instance and add search
        service1 = SavedSearchService()
        search_id = service1.save_search("Persistent Search", "item=persistent")

        # Create second service instance
        service2 = SavedSearchService()

        # Should load the persisted search
        assert service2.get_search_count() == 1
        search = service2.get_search_by_id(search_id)
        assert search is not None
        assert search["name"] == "Persistent Search"
        assert search["query"] == "item=persistent"

    def test_malformed_json_handling(self):
        """Test handling of malformed JSON files."""
        # Write malformed JSON
        with open(self.test_file_path, "w") as f:
            f.write("{ invalid json")

        # Service should handle gracefully and start with empty collection
        service = SavedSearchService()
        assert service.get_search_count() == 0

    def test_missing_searches_key_handling(self):
        """Test handling of JSON without 'searches' key."""
        # Write JSON without searches key
        with open(self.test_file_path, "w") as f:
            json.dump({"other_data": "value"}, f)

        # Service should handle gracefully
        service = SavedSearchService()
        assert service.get_search_count() == 0

    @patch("app.services.saved_search_service.Path")
    def test_file_save_error_handling(self, mock_path):
        """Test handling of file save errors."""
        service = SavedSearchService()

        # Mock Path.mkdir to raise an exception
        mock_path.return_value.parent.mkdir.side_effect = OSError("Permission denied")

        # Save should fail gracefully
        search_id = service.save_search("Test", "test=query")
        assert search_id is None

    def test_comprehensive_workflow(self):
        """Test a comprehensive workflow with multiple operations."""
        service = SavedSearchService()

        # Create several searches
        id1 = service.save_search("Logs", "item=log tier>2")
        id2 = service.save_search("High Tier", "tier>=5")
        id3 = service.save_search("Containers", "container=carving")

        assert service.get_search_count() == 3

        # Use some searches with timing
        import time

        query1 = service.use_search(id1)
        time.sleep(0.1)  # Increased sleep time for more reliable ordering
        query3 = service.use_search(id3)

        assert query1 == "item=log tier>2"
        assert query3 == "container=carving"

        # Update a search name
        assert service.update_search_name(id2, "Super High Tier") is True

        # Verify searches are ordered by usage
        searches = service.get_all_searches()
        ids = [s["id"] for s in searches[:2]]
        # At least one of the two most recent searches should be id3 or id1
        assert id3 in ids or id1 in ids
        assert searches[2]["id"] == id2  # Least recent (unused)
        assert searches[2]["name"] == "Super High Tier"  # Name was updated

        # Delete one search
        assert service.delete_search(id1) is True
        assert service.get_search_count() == 2

        # Verify final state
        final_searches = service.get_all_searches()
        assert len(final_searches) == 2
        assert all(s["id"] != id1 for s in final_searches)  # id1 should be gone
