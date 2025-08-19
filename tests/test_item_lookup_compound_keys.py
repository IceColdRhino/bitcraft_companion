"""
Tests for ItemLookupService compound key functionality.

Tests the updated item lookup system that uses only compound keys (id, table_source)
and verifies proper handling of ID conflicts between tables.
"""

import pytest
from unittest.mock import MagicMock

from app.core.utils.item_lookup_service import ItemLookupService


class TestItemLookupCompoundKeys:
    """Test ItemLookupService compound key functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock reference data with ID conflicts
        self.mock_reference_data = {
            "item_desc": [
                {"id": 1001, "name": "Iron Sword", "tier": 3, "tag": "Weapon"},
                {"id": 3001, "name": "Ancient Journal Page #2", "tier": 0, "tag": "Journal Page"},
                {"id": 5001, "name": "Basic Wood", "tier": 1, "tag": "Material"}
            ],
            "cargo_desc": [
                {"id": 1001, "name": "Supply Package", "tier": 1, "tag": "Package"},
                {"id": 3001, "name": "Pyrelite Ore Chunk", "tier": 2, "tag": "Ore Chunk"},
                {"id": 4001, "name": "Cargo Crate", "tier": 0, "tag": "Container"}
            ],
            "resource_desc": [
                {"id": 2001, "name": "Stone Deposit", "tier": 0, "tag": "Resource"},
                {"id": 5001, "name": "Wood Resource", "tier": 0, "tag": "Natural Resource"}
            ],
            "building_desc": [
                {"id": 100, "name": "Workshop", "description": "Basic crafting building"}
            ],
            "crafting_recipe_desc": [
                {"id": 200, "name": "Plank Recipe", "description": "Makes planks from wood"}
            ]
        }
        
        self.item_lookup_service = ItemLookupService(self.mock_reference_data)

    def test_compound_key_storage(self):
        """Test that items are stored with compound keys."""
        # Check that compound keys exist
        assert (1001, "item_desc") in self.item_lookup_service._item_lookups
        assert (1001, "cargo_desc") in self.item_lookup_service._item_lookups
        assert (3001, "item_desc") in self.item_lookup_service._item_lookups
        assert (3001, "cargo_desc") in self.item_lookup_service._item_lookups
        
        # Check that items with same ID have different data
        item_desc_data = self.item_lookup_service._item_lookups[(1001, "item_desc")]
        cargo_desc_data = self.item_lookup_service._item_lookups[(1001, "cargo_desc")]
        
        assert item_desc_data["name"] == "Iron Sword"
        assert cargo_desc_data["name"] == "Supply Package"
        assert item_desc_data["tier"] == 3
        assert cargo_desc_data["tier"] == 1

    def test_lookup_item_by_id_explicit_source(self):
        """Test looking up items with explicit table sources."""
        # Test item_desc lookup
        item = self.item_lookup_service.lookup_item_by_id(1001, "item_desc")
        assert item is not None
        assert item["name"] == "Iron Sword"
        assert item["tier"] == 3
        assert item["tag"] == "Weapon"
        
        # Test cargo_desc lookup for same ID
        cargo = self.item_lookup_service.lookup_item_by_id(1001, "cargo_desc")
        assert cargo is not None
        assert cargo["name"] == "Supply Package"
        assert cargo["tier"] == 1
        assert cargo["tag"] == "Package"
        
        # Test resource_desc lookup
        resource = self.item_lookup_service.lookup_item_by_id(2001, "resource_desc")
        assert resource is not None
        assert resource["name"] == "Stone Deposit"

    def test_lookup_item_missing_source(self):
        """Test looking up items from tables that don't contain the ID."""
        # ID 1001 doesn't exist in resource_desc
        result = self.item_lookup_service.lookup_item_by_id(1001, "resource_desc")
        assert result is None
        
        # ID 2001 doesn't exist in item_desc
        result = self.item_lookup_service.lookup_item_by_id(2001, "item_desc")
        assert result is None

    def test_lookup_item_invalid_source(self):
        """Test looking up items with invalid table source."""
        # Should handle gracefully and return None
        result = self.item_lookup_service.lookup_item_by_id(1001, "invalid_table")
        assert result is None

    def test_lookup_item_empty_source(self):
        """Test that empty table source returns None (doesn't raise)."""
        result = self.item_lookup_service.lookup_item_by_id(1001, "")
        assert result is None
        
        result = self.item_lookup_service.lookup_item_by_id(1001, None)
        assert result is None

    def test_get_item_name_explicit_source(self):
        """Test getting item names with explicit sources."""
        # Test different sources for same ID
        name_item = self.item_lookup_service.get_item_name(1001, "item_desc")
        name_cargo = self.item_lookup_service.get_item_name(1001, "cargo_desc")
        
        assert name_item == "Iron Sword"
        assert name_cargo == "Supply Package"
        
        # Test non-existent item
        name_missing = self.item_lookup_service.get_item_name(99999, "item_desc")
        assert name_missing == "Unknown Item (99999)"

    def test_get_item_tier_explicit_source(self):
        """Test getting item tiers with explicit sources."""
        # Test different sources for same ID
        tier_item = self.item_lookup_service.get_item_tier(1001, "item_desc")
        tier_cargo = self.item_lookup_service.get_item_tier(1001, "cargo_desc")
        
        assert tier_item == 3
        assert tier_cargo == 1
        
        # Test non-existent item
        tier_missing = self.item_lookup_service.get_item_tier(99999, "item_desc")
        assert tier_missing == 0

    def test_get_available_sources_for_item(self):
        """Test getting all available sources for an item ID."""
        # ID with conflicts
        sources_1001 = self.item_lookup_service.get_available_sources_for_item(1001)
        assert "item_desc" in sources_1001
        assert "cargo_desc" in sources_1001
        assert "resource_desc" not in sources_1001
        assert len(sources_1001) == 2
        
        # ID with single source
        sources_2001 = self.item_lookup_service.get_available_sources_for_item(2001)
        assert sources_2001 == ["resource_desc"]
        
        # Non-existent ID
        sources_missing = self.item_lookup_service.get_available_sources_for_item(99999)
        assert sources_missing == []

    def test_determine_best_source_for_item(self):
        """Test automatic source determination with context hints."""
        # Test context hints
        source_cargo = self.item_lookup_service.determine_best_source_for_item(1001, "cargo")
        assert source_cargo == "cargo_desc"
        
        source_resource = self.item_lookup_service.determine_best_source_for_item(5001, "resource")
        assert source_resource == "resource_desc"
        
        # Test default preference for item_desc when available
        source_default = self.item_lookup_service.determine_best_source_for_item(1001, "crafting")
        assert source_default == "item_desc"
        
        # Test single source item
        source_single = self.item_lookup_service.determine_best_source_for_item(2001, "any_context")
        assert source_single == "resource_desc"
        
        # Test non-existent item (should default to item_desc)
        source_missing = self.item_lookup_service.determine_best_source_for_item(99999, "any_context")
        assert source_missing == "item_desc"

    def test_get_all_item_names_for_id(self):
        """Test getting all item names for a conflicting ID."""
        # ID with conflicts
        names_1001 = self.item_lookup_service.get_all_item_names_for_id(1001)
        expected_names = {
            "item_desc": "Iron Sword",
            "cargo_desc": "Supply Package"
        }
        assert names_1001 == expected_names
        
        # ID with single source
        names_2001 = self.item_lookup_service.get_all_item_names_for_id(2001)
        expected_single = {"resource_desc": "Stone Deposit"}
        assert names_2001 == expected_single
        
        # Non-existent ID
        names_missing = self.item_lookup_service.get_all_item_names_for_id(99999)
        assert names_missing == {}

    def test_id_conflict_verification(self):
        """Test that ID conflicts are properly handled."""
        # Verify that conflicting IDs have different data
        conflicts = [1001, 3001, 5001]
        
        for item_id in conflicts:
            available_sources = self.item_lookup_service.get_available_sources_for_item(item_id)
            
            if len(available_sources) > 1:
                # Get data from all available sources
                all_data = {}
                for source in available_sources:
                    item_data = self.item_lookup_service.lookup_item_by_id(item_id, source)
                    all_data[source] = item_data
                
                # Verify that different sources have different names
                names = [data["name"] for data in all_data.values()]
                assert len(set(names)) == len(names), f"ID {item_id} has duplicate names across sources"

    def test_refresh_lookups(self):
        """Test that lookups can be refreshed with new reference data."""
        # Add new item to reference data
        new_reference_data = self.mock_reference_data.copy()
        new_reference_data["item_desc"] = self.mock_reference_data["item_desc"] + [
            {"id": 9001, "name": "New Test Item", "tier": 5, "tag": "Test"}
        ]
        
        # Refresh the lookups
        self.item_lookup_service.refresh_lookups(new_reference_data)
        
        # New item should be available
        new_item = self.item_lookup_service.lookup_item_by_id(9001, "item_desc")
        assert new_item is not None
        assert new_item["name"] == "New Test Item"
        
        # Old items should still be available
        old_item = self.item_lookup_service.lookup_item_by_id(1001, "item_desc")
        assert old_item is not None
        assert old_item["name"] == "Iron Sword"

    def test_error_handling(self):
        """Test error handling in lookup methods."""
        # Test with None lookups
        service_with_none = ItemLookupService({})
        service_with_none._item_lookups = None
        
        result = service_with_none.lookup_item_by_id(1001, "item_desc")
        assert result is None
        
        name = service_with_none.get_item_name(1001, "item_desc")
        assert name == "Unknown Item (1001)"
        
        tier = service_with_none.get_item_tier(1001, "item_desc")
        assert tier == 0

    def test_building_and_recipe_lookups_unchanged(self):
        """Test that building and recipe lookups still work normally."""
        # Building lookup should work as before
        building = self.item_lookup_service.lookup_building_by_id(100)
        assert building is not None
        assert building["name"] == "Workshop"
        
        # Recipe lookup should work as before
        recipe = self.item_lookup_service.lookup_recipe_by_id(200)
        assert recipe is not None
        assert recipe["name"] == "Plank Recipe"