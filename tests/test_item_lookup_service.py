"""
Tests for ItemLookupService - item/resource/cargo resolution and conflict handling.

Tests the core item lookup logic that handles ID conflicts between different
desc tables (item_desc, cargo_desc, resource_desc) and ensures proper resolution.
"""

import pytest
from unittest.mock import Mock
from app.core.utils.item_lookup_service import ItemLookupService
from tests.conftest import get_mock_reference_data


class TestItemLookupService:
    """Test ItemLookupService functionality including ID conflict resolution."""

    @pytest.fixture
    def item_lookup_service(self):
        """Create ItemLookupService with mock reference data including conflicts."""
        reference_data = get_mock_reference_data()
        return ItemLookupService(reference_data)

    def test_compound_key_system(self, item_lookup_service):
        """Test that compound key (item_id, table_source) system prevents overwrites."""
        # Test that conflicting ID 3001 exists in multiple sources
        assert (3001, "item_desc") in item_lookup_service._item_lookups
        assert (3001, "cargo_desc") in item_lookup_service._item_lookups
        
        # Verify they have different names
        item_desc_data = item_lookup_service._item_lookups[(3001, "item_desc")]
        cargo_desc_data = item_lookup_service._item_lookups[(3001, "cargo_desc")]
        
        assert item_desc_data["name"] == "Ancient Journal Page #2"
        assert cargo_desc_data["name"] == "Pyrelite Ore Chunk"
        
        # Test that non-conflicting items work normally
        assert (1, "item_desc") in item_lookup_service._item_lookups
        assert (4001, "cargo_desc") in item_lookup_service._item_lookups

    def test_preferred_source_parameter(self, item_lookup_service):
        """Test that preferred_source parameter correctly chooses the right table."""
        # Test conflicting ID 3001 with explicit preferred source
        item_from_item_desc = item_lookup_service.lookup_item_by_id(3001, "item_desc")
        item_from_cargo_desc = item_lookup_service.lookup_item_by_id(3001, "cargo_desc")
        
        assert item_from_item_desc["name"] == "Ancient Journal Page #2"
        assert item_from_cargo_desc["name"] == "Pyrelite Ore Chunk"
        
        # Test that tier and tag are also different
        assert item_from_item_desc["tier"] == 0
        assert item_from_cargo_desc["tier"] == 2
        assert item_from_item_desc["tag"] == "Journal Page"
        assert item_from_cargo_desc["tag"] == "Ore Chunk"

    def test_priority_system_fallback(self, item_lookup_service):
        """Test that ItemLookupService can find items by ID using compound key system."""
        # Test ID 3001 - should be able to find all items with this ID
        found_items = item_lookup_service.find_items_by_id(3001)
        assert len(found_items) >= 1
        # Check that we can find the item_desc version
        item_desc_found = any(item["name"] == "Ancient Journal Page #2" for item in found_items)
        assert item_desc_found
        
        # Test ID 1001 - should find the Iron Sword
        found_items = item_lookup_service.find_items_by_id(1001)
        assert len(found_items) >= 1
        item_desc_found = any(item["name"] == "Iron Sword" for item in found_items)
        assert item_desc_found

    def test_non_conflicting_items(self, item_lookup_service):
        """Test that items without conflicts work normally."""
        # Test item_desc only - use compound key lookup
        wood = item_lookup_service.lookup_item_by_id_and_name(1, "Wood")
        assert wood["name"] == "Wood"
        assert wood["tier"] == 0
        
        # Test cargo_desc only - use compound key lookup
        crate = item_lookup_service.lookup_item_by_id_and_name(4001, "Materials Crate")
        assert crate["name"] == "Materials Crate"
        assert crate["tier"] == 1
        
        # Test resource_desc only - use compound key lookup
        stone = item_lookup_service.lookup_item_by_id_and_name(10, "Stone")
        assert stone["name"] == "Stone"
        assert stone["tier"] == 0

    def test_get_item_name_consistency(self, item_lookup_service):
        """Test that get_item_name returns consistent results with lookup_item_by_id."""
        # Test conflicting item with preferred source
        name_item_desc = item_lookup_service.get_item_name(3001, "item_desc")
        name_cargo_desc = item_lookup_service.get_item_name(3001, "cargo_desc")
        
        assert name_item_desc == "Ancient Journal Page #2"
        assert name_cargo_desc == "Pyrelite Ore Chunk"
        
        # Test compound key lookup
        found_items = item_lookup_service.find_items_by_id(3001)
        assert len(found_items) >= 2  # Should find both versions

    def test_get_item_tier_consistency(self, item_lookup_service):
        """Test that get_item_tier returns consistent results with lookup_item_by_id."""
        # Test conflicting item with different tiers
        tier_item_desc = item_lookup_service.get_item_tier(3001, "item_desc")
        tier_cargo_desc = item_lookup_service.get_item_tier(3001, "cargo_desc")
        
        assert tier_item_desc == 0  # Ancient Journal Page #2
        assert tier_cargo_desc == 2  # Pyrelite Ore Chunk
        
        # Test compound key lookup for tier consistency
        found_items = item_lookup_service.find_items_by_id(3001)
        tiers = [item.get("tier", 0) for item in found_items]
        assert 0 in tiers and 2 in tiers  # Both tiers should exist

    def test_missing_item_fallback(self, item_lookup_service):
        """Test fallback behavior for non-existent items."""
        # Test completely missing item
        found_items = item_lookup_service.find_items_by_id(99999)
        assert len(found_items) == 0
        
        missing_name = item_lookup_service.get_item_name(99999, "item_desc")
        assert missing_name == "Unknown Item (99999)"
        
        missing_tier = item_lookup_service.get_item_tier(99999, "item_desc")
        assert missing_tier == 0

    def test_invalid_preferred_source(self, item_lookup_service):
        """Test behavior with invalid preferred_source parameter."""
        # Test with invalid source - should return None
        result = item_lookup_service.lookup_item_by_id(3001, "invalid_source")
        assert result is None
        
        # Test with None - should return None (table_source required)
        result = item_lookup_service.lookup_item_by_id(3001, None)
        assert result is None

    def test_all_cargo_indicators(self, item_lookup_service):
        """Test that cargo items can be accessed with explicit preferred_source."""
        # Test various cargo indicators - need to explicitly request cargo_desc
        cargo_items = [
            (1001, "package"),  # Supply Package
            (4001, "crate"),    # Materials Crate  
            (4002, "bundle"),   # Equipment Bundle
            (3001, "chunk")     # Pyrelite Ore Chunk
        ]
        
        for item_id, expected_indicator in cargo_items:
            # Test with explicit cargo_desc preference
            result = item_lookup_service.lookup_item_by_id(item_id, "cargo_desc")
            if result:  # Only test if cargo version exists
                assert expected_indicator in result["name"].lower(), f"Item {item_id} should contain '{expected_indicator}' when using cargo_desc"

    def test_refresh_lookups(self, item_lookup_service):
        """Test that refresh_lookups properly rebuilds the lookup cache."""
        # Store original lookup count
        original_count = len(item_lookup_service._item_lookups)
        
        # Refresh with new data
        new_reference_data = {
            "item_desc": [{"id": 9001, "name": "Test Item", "tier": 0, "tag": "Test"}],
            "cargo_desc": [],
            "resource_desc": []
        }
        
        item_lookup_service.refresh_lookups(new_reference_data)
        
        # Verify new item is accessible using compound key
        test_item = item_lookup_service.lookup_item_by_id_and_name(9001, "Test Item")
        assert test_item["name"] == "Test Item"
        
        # Verify old items are gone
        found_old_items = item_lookup_service.find_items_by_id(3001)
        assert len(found_old_items) == 0