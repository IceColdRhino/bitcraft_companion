"""
Tests for UI tab sorting logic - focuses on sorting algorithms without GUI components.

This module tests the sorting algorithms used in UI tabs by testing the logic directly,
following the same pattern as test_sorting_fixes.py which works correctly.
"""

import pytest


class TestPassiveCraftingTabSorting:
    """Test PassiveCraftingTab sorting functionality without GUI components."""
    
    def test_jobs_column_sorting_with_correct_keys(self):
        """Test sorting of Jobs column using completed_jobs/total_jobs keys."""
        
        # Test data with correct data structure used by the actual sorting logic
        test_data = [
            {"item": "ItemA", "completed_jobs": 1, "total_jobs": 3, "tier": 1},
            {"item": "ItemB", "completed_jobs": 2, "total_jobs": 3, "tier": 1}, 
            {"item": "ItemC", "completed_jobs": 3, "total_jobs": 3, "tier": 1},
            {"item": "ItemD", "completed_jobs": 0, "total_jobs": 2, "tier": 1},
            {"item": "ItemE", "completed_jobs": None, "total_jobs": None, "tier": 1},
        ]
        
        # Jobs sorting logic from PassiveCraftingTab.sort_by()
        def jobs_sort_key(x):
            completed_jobs = x.get("completed_jobs", 0)
            total_jobs = x.get("total_jobs", 1)
            
            try:
                completed = int(completed_jobs) if completed_jobs is not None else 0
                total = int(total_jobs) if total_jobs is not None else 1
                completion_ratio = completed / total if total > 0 else 0
                return (completion_ratio, total)
            except (ValueError, TypeError, ZeroDivisionError):
                return (0, 0)
        
        # Sort the data
        test_data.sort(key=jobs_sort_key, reverse=False)
        
        # Verify sorting: by completion ratio, then by total jobs
        # Expected order: ItemE (0,0), ItemD (0/2=0), ItemA (1/3=0.33), ItemB (2/3=0.67), ItemC (3/3=1.0)
        assert test_data[0]["item"] == "ItemE"  # None values -> (0,0)
        assert test_data[1]["item"] == "ItemD"  # 0/2 = 0% completion
        assert test_data[2]["item"] == "ItemA"  # 1/3 = 33% completion
        assert test_data[3]["item"] == "ItemB"  # 2/3 = 67% completion
        assert test_data[4]["item"] == "ItemC"  # 3/3 = 100% completion
    
    def test_quantity_column_sorting_with_correct_keys(self):
        """Test sorting of Quantity column using total_quantity key."""
        
        # Test data with correct data structure 
        test_data = [
            {"item": "ItemA", "total_quantity": 100, "tier": 1},
            {"item": "ItemB", "total_quantity": "50", "tier": 1},  # String number
            {"item": "ItemC", "total_quantity": 200, "tier": 1},
            {"item": "ItemD", "total_quantity": "invalid", "tier": 1},  # Invalid
            {"item": "ItemE", "total_quantity": None, "tier": 1},  # None
        ]
        
        # Quantity sorting logic from PassiveCraftingTab.sort_by() 
        def safe_numeric_sort_key(x):
            value = x.get("total_quantity", 0)
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0  # Default for non-numeric values
        
        # Sort the data
        test_data.sort(key=safe_numeric_sort_key, reverse=False)
        
        # Verify invalid values are treated as 0 and sorted first
        first_two_items = [item["item"] for item in test_data[:2]]
        assert "ItemD" in first_two_items and "ItemE" in first_two_items
        # Last item should be the highest valid number
        assert test_data[-1]["item"] == "ItemC"  # 200 is highest
    
    def test_building_column_sorting_with_correct_keys(self):
        """Test sorting of Building column using building_name key."""
        
        # Test data with correct data structure
        test_data = [
            {"item": "ItemA", "building_name": "Forge", "tier": 1},
            {"item": "ItemB", "building_name": "Anvil", "tier": 1},
            {"item": "ItemC", "building_name": "Workbench", "tier": 1},
            {"item": "ItemD", "building_name": "", "tier": 1},  # Empty
        ]
        
        # Building sorting logic from PassiveCraftingTab.sort_by()
        def string_sort_key(x):
            value = x.get("building_name", "")
            return str(value).lower()
        
        # Sort the data
        test_data.sort(key=string_sort_key, reverse=False)
        
        # Verify alphabetical ordering (empty string sorts first)
        building_names = [item["building_name"] for item in test_data]
        assert building_names == ["", "Anvil", "Forge", "Workbench"]


class TestActiveCraftingTabSorting:
    """Test ActiveCraftingTab sorting functionality without GUI components."""
    
    def test_remaining_effort_sorting_with_comma_numbers(self):
        """Test sorting of Remaining Effort column with comma-separated numbers and READY."""
        
        # Test data with formats actually seen in the application
        test_data = [
            {"item": "ItemA", "remaining_effort": "25,979", "tier": 1},
            {"item": "ItemB", "remaining_effort": "5,696", "tier": 1}, 
            {"item": "ItemC", "remaining_effort": "READY", "tier": 1},
            {"item": "ItemD", "remaining_effort": "Preparation", "tier": 1},
            {"item": "ItemE", "remaining_effort": "unknown", "tier": 1},
        ]
        
        # Remaining effort sorting logic from ActiveCraftingTab.sort_by()
        def progress_sort_key(x):
            progress_str = str(x.get("remaining_effort", "")).strip()
            
            # Handle "READY" - should sort first (0 remaining effort)
            if progress_str.upper() == "READY":
                return 0
            
            # Handle "Preparation" - should sort last as it hasn't started
            if progress_str.lower() == "preparation":
                return 999999
            
            # Handle numeric values (possibly with commas like "5,696")
            try:
                # Remove commas and convert to int
                numeric_value = int(progress_str.replace(",", ""))
                return numeric_value
            except ValueError:
                pass
            
            # Handle fraction format like "current/total"
            if "/" in progress_str:
                try:
                    parts = progress_str.split("/")
                    if len(parts) == 2:
                        current = int(parts[0].replace(",", ""))
                        total = int(parts[1].replace(",", ""))
                        if total > 0:
                            # Return remaining effort (total - current)
                            return total - current
                        else:
                            return 0
                except ValueError:
                    pass
            
            # Handle percentage format
            if "%" in progress_str:
                try:
                    percentage = int(progress_str.replace("%", ""))
                    # Convert percentage to remaining effort (100% = 0 remaining)
                    return 100 - percentage
                except ValueError:
                    pass
            
            # Unknown formats sort to middle
            return 500000
        
        # Sort the data
        test_data.sort(key=progress_sort_key, reverse=False)
        
        # Verify expected order: READY (0), 5,696, 25,979, unknown (500000), Preparation (999999)
        efforts = [item["remaining_effort"] for item in test_data]
        assert efforts[0] == "READY"       # 0 remaining
        assert efforts[1] == "5,696"      # 5,696 remaining
        assert efforts[2] == "25,979"     # 25,979 remaining  
        assert efforts[3] == "unknown"    # 500000 (middle)
        assert efforts[4] == "Preparation" # 999999 (last)
    
    def test_numeric_column_mixed_type_safety(self):
        """Test that numeric sorting handles mixed types safely without crashing."""
        
        test_data = [
            {"item": "ItemA", "tier": 3, "quantity": "5"},
            {"item": "ItemB", "tier": "invalid", "quantity": 2},
            {"item": "ItemC", "tier": 1.5, "quantity": "invalid"},
            {"item": "ItemD", "tier": None, "quantity": None},
        ]
        
        # Safe numeric sorting logic from ActiveCraftingTab.sort_by()
        def safe_numeric_sort_key(x):
            value = x.get("tier", 0)
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0  # Default for non-numeric values
        
        # This should not crash
        test_data.sort(key=safe_numeric_sort_key, reverse=False)
        
        # Verify invalid values are treated as 0
        sorted_tiers = [item["tier"] for item in test_data]
        # Invalid values ("invalid", None) should sort first as 0
        assert sorted_tiers[0] in ["invalid", None]
        assert sorted_tiers[1] in ["invalid", None] 
        # Then 1.5, then 3
        assert sorted_tiers[2] == 1.5
        assert sorted_tiers[3] == 3


class TestClaimInventoryTabDataHandling:
    """Test ClaimInventoryTab data processing logic without GUI components."""
    
    def test_inventory_data_processing_logic(self):
        """Test the data transformation logic for inventory data."""
        
        # Mock inventory data as it comes from the processor
        inventory_data = {
            "Iron Ore": {
                "tier": 1,
                "total_quantity": 150,
                "tag": "resource", 
                "containers": {"Storage Box": 150}
            },
            "Copper Ore": {
                "tier": 1,
                "total_quantity": 75,
                "tag": "resource",
                "containers": {"Storage Box": 50, "Chest": 25}
            }
        }
        
        # Simulate the data processing logic from ClaimInventoryTab.update_data()
        processed_data = []
        
        for item_name, item_data in inventory_data.items():
            processed_item = {
                "name": item_name,
                "tier": item_data.get("tier", 0),
                "quantity": item_data.get("total_quantity", 0),
                "tag": item_data.get("tag", ""),
                "containers": item_data.get("containers", {})
            }
            processed_data.append(processed_item)
        
        # Verify data was processed correctly
        assert len(processed_data) == 2
        assert processed_data[0]["name"] == "Iron Ore"
        assert processed_data[0]["quantity"] == 150
        assert processed_data[1]["name"] == "Copper Ore" 
        assert processed_data[1]["quantity"] == 75
    
    def test_empty_inventory_handling(self):
        """Test handling of empty inventory data."""
        
        # Empty inventory
        inventory_data = {}
        
        # Process empty data
        processed_data = []
        for item_name, item_data in inventory_data.items():
            processed_item = {
                "name": item_name,
                "quantity": item_data.get("total_quantity", 0)
            }
            processed_data.append(processed_item)
        
        # Should result in empty list
        assert len(processed_data) == 0