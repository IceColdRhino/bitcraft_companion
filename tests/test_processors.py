"""
Tests for data processors - BaseProcessor and individual processor implementations.

Tests the core data processing logic that handles SpacetimeDB messages,
manages caches, and formats data for the UI.
"""

import pytest
import queue
import time
from unittest.mock import Mock, patch
from app.core.processors.base_processor import BaseProcessor
from app.core.processors.inventory_processor import InventoryProcessor
from app.core.processors.tasks_processor import TasksProcessor
from app.core.processors.crafting_processor import CraftingProcessor
from tests.conftest import get_mock_spacetime_messages, get_mock_reference_data


class MockProcessor(BaseProcessor):
    """Concrete test implementation of BaseProcessor."""

    def __init__(self, data_queue, services, reference_data):
        super().__init__(data_queue, services, reference_data)
        self.processed_transactions = []
        self.processed_subscriptions = []

    def get_table_names(self):
        return ["test_table"]

    def process_transaction(self, table_update, reducer_name, timestamp):
        self.processed_transactions.append({"table_update": table_update, "reducer_name": reducer_name, "timestamp": timestamp})

    def process_subscription(self, table_update):
        self.processed_subscriptions.append(table_update)


class TestBaseProcessor:
    """Test BaseProcessor functionality."""

    def test_initialization(self, mock_data_queue, mock_services, mock_reference_data):
        """Test BaseProcessor initialization."""
        processor = MockProcessor(mock_data_queue, mock_services, mock_reference_data)

        assert processor.data_queue == mock_data_queue
        assert processor.services == mock_services
        assert processor.reference_data == mock_reference_data

        # Check service shortcuts are set up
        assert processor.inventory_service == mock_services.get("inventory_service")
        assert processor.claim_manager == mock_services.get("claim_manager")

    def test_queue_update(self, mock_data_queue, mock_services, mock_reference_data):
        """Test _queue_update helper method."""
        processor = MockProcessor(mock_data_queue, mock_services, mock_reference_data)

        test_data = {"test": "data"}
        processor._queue_update("test_update", test_data, {"changes": True}, 123456)

        # Verify data was queued
        assert not mock_data_queue.empty()
        queued_item = mock_data_queue.get()

        assert queued_item["type"] == "test_update"
        assert queued_item["data"] == test_data
        assert queued_item["changes"] == {"changes": True}
        assert queued_item["timestamp"] == 123456

    def test_queue_update_error_handling(self, mock_services, mock_reference_data, caplog):
        """Test _queue_update error handling."""
        # Create a mock queue that raises an exception
        bad_queue = Mock()
        bad_queue.put.side_effect = Exception("Queue error")

        processor = MockProcessor(bad_queue, mock_services, mock_reference_data)

        with caplog.at_level("ERROR"):
            processor._queue_update("test_update", {"data": "test"})

        assert "Error queuing test_update update" in caplog.text

    def test_clear_cache(self, mock_data_queue, mock_services, mock_reference_data, caplog):
        """Test clear_cache method."""
        processor = MockProcessor(mock_data_queue, mock_services, mock_reference_data)

        with caplog.at_level("INFO"):
            processor.clear_cache()

        assert f"Clearing cache for {processor.__class__.__name__}" in caplog.text

    def test_abstract_methods_enforcement(self, mock_data_queue, mock_services, mock_reference_data):
        """Test that abstract methods must be implemented."""

        # Test that BaseProcessor cannot be instantiated directly
        with pytest.raises(TypeError):
            BaseProcessor(mock_data_queue, mock_services, mock_reference_data)


class TestTasksProcessor:
    """Test TasksProcessor specific functionality."""

    def test_initialization(self, mock_data_queue, mock_services, mock_reference_data):
        """Test TasksProcessor initialization."""
        processor = TasksProcessor(mock_data_queue, mock_services, mock_reference_data)

        assert hasattr(processor, "_task_states")
        assert hasattr(processor, "_task_descriptions")
        assert hasattr(processor, "_player_state")

        # Check reset tracking attributes
        assert hasattr(processor, "_reset_in_progress")
        assert hasattr(processor, "_reset_timestamp")
        assert hasattr(processor, "_reset_tables_updated")
        assert hasattr(processor, "_buffered_ui_update")

        assert processor._reset_in_progress == False
        assert isinstance(processor._reset_tables_updated, set)

    def test_get_table_names(self, mock_data_queue, mock_services, mock_reference_data):
        """Test TasksProcessor table names."""
        processor = TasksProcessor(mock_data_queue, mock_services, mock_reference_data)

        table_names = processor.get_table_names()
        expected_tables = ["traveler_task_state", "traveler_task_desc", "player_state"]

        assert set(table_names) == set(expected_tables)

    def test_reset_detection(self, mock_data_queue, mock_services, mock_reference_data):
        """Test reset detection logic."""
        processor = TasksProcessor(mock_data_queue, mock_services, mock_reference_data)

        # Mock large transaction (reset scenario)
        large_transaction = {
            "table_name": "traveler_task_state",
            "updates": [
                {"inserts": ["insert_data"] * 12, "deletes": ["delete_data"] * 12}  # 12 inserts = reset  # 12 deletes = reset
            ],
        }

        # Process the transaction
        processor.process_transaction(large_transaction, "traveler_task_agent_loop", time.time())

        # Should have detected reset
        assert processor._reset_in_progress == True
        assert "traveler_task_state" in processor._reset_tables_updated
        assert processor._reset_timestamp is not None

    def test_reset_buffering(self, mock_data_queue, mock_services, mock_reference_data):
        """Test UI update buffering during resets."""
        processor = TasksProcessor(mock_data_queue, mock_services, mock_reference_data)

        # Start a reset
        processor._handle_reset_start("traveler_task_state")

        # Attempt to refresh UI - should be buffered
        processor._refresh_tasks("traveler_task_state")

        # Should be marked as buffered but not sent to UI yet
        assert processor._buffered_ui_update == True
        assert mock_data_queue.empty()  # No UI update sent yet

    def test_reset_completion(self, mock_data_queue, mock_services, mock_reference_data):
        """Test reset completion and UI update."""
        processor = TasksProcessor(mock_data_queue, mock_services, mock_reference_data)

        # Setup some mock data
        processor._task_states = {123: {"completed": False}}
        processor._task_descriptions = {123: {"description": "Test task"}}

        # Start a reset and mark both tables as updated
        processor._handle_reset_start("traveler_task_state")
        processor._refresh_tasks("traveler_task_state")  # Buffers update
        processor._refresh_tasks("traveler_task_desc")  # Completes reset

        # Should have completed reset and sent UI update
        assert processor._reset_in_progress == False
        assert not mock_data_queue.empty()  # UI update was sent

    def test_reset_timeout(self, mock_data_queue, mock_services, mock_reference_data):
        """Test reset timeout handling."""
        processor = TasksProcessor(mock_data_queue, mock_services, mock_reference_data)

        # Setup mock data
        processor._task_states = {123: {"completed": False}}
        processor._task_descriptions = {123: {"description": "Test task"}}

        # Start reset and set old timestamp (simulate timeout)
        processor._handle_reset_start("traveler_task_state")
        processor._reset_timestamp = time.time() - 10.0  # 10 seconds ago (well past timeout)
        processor._buffered_ui_update = True

        # Manually trigger timeout completion by calling complete reset directly
        processor._complete_reset()

        # Should have completed due to timeout
        assert processor._reset_in_progress == False
        assert not mock_data_queue.empty()  # UI update was sent

    def test_task_state_transaction_parsing(self, mock_data_queue, mock_services, mock_reference_data):
        """Test parsing task state transaction data."""
        processor = TasksProcessor(mock_data_queue, mock_services, mock_reference_data)

        # Mock transaction update for task state
        update = {
            "inserts": ["[123, 456, 789, 1001, false]"],  # JSON string format
            "deletes": ["[123, 456, 789, 1001, true]"],  # JSON string format
        }

        completed_tasks = []
        processor._process_task_state_transaction(update, completed_tasks)

        # Should have processed the replacement (delete + insert)
        assert 123 in processor._task_states  # Now keyed by entity_id, not task_id
        task_data = processor._task_states[123]
        assert task_data["entity_id"] == 123
        assert task_data["player_entity_id"] == 456
        assert task_data["traveler_id"] == 789
        assert task_data["task_id"] == 1001  # task_id is now a field, not the key
        assert task_data["completed"] == False

    def test_task_desc_transaction_parsing(self, mock_data_queue, mock_services, mock_reference_data):
        """Test parsing task description transaction data."""
        processor = TasksProcessor(mock_data_queue, mock_services, mock_reference_data)

        # Mock description data
        desc_data = {
            "id": 1001,
            "description": "Test task description",
            "required_items": [[1170001, 5]],
            "level_requirement": {"level": 10},
        }

        update = {"inserts": [str(desc_data).replace("'", '"')], "deletes": ['[1001, "old description"]']}  # JSON format

        processor._process_task_desc_transaction(update)

        # Should have updated description cache
        assert 1001 in processor._task_descriptions
        cached_desc = processor._task_descriptions[1001]
        assert cached_desc["description"] == "Test task description"
        assert cached_desc["required_items"] == [[1170001, 5]]

    def test_clear_cache_includes_reset_state(self, mock_data_queue, mock_services, mock_reference_data):
        """Test that clear_cache also clears reset state."""
        processor = TasksProcessor(mock_data_queue, mock_services, mock_reference_data)

        # Set up some state
        processor._reset_in_progress = True
        processor._reset_timestamp = time.time()
        processor._reset_tables_updated.add("test_table")
        processor._buffered_ui_update = True

        # Clear cache
        processor.clear_cache()

        # Reset state should be cleared
        assert processor._reset_in_progress == False
        assert processor._reset_timestamp == None
        assert len(processor._reset_tables_updated) == 0
        assert processor._buffered_ui_update == False


class TestInventoryProcessor:
    """Test InventoryProcessor functionality."""

    def test_get_table_names(self, mock_data_queue, mock_services, mock_reference_data):
        """Test InventoryProcessor table names."""
        processor = InventoryProcessor(mock_data_queue, mock_services, mock_reference_data)

        table_names = processor.get_table_names()
        assert "inventory_state" in table_names

    def test_process_subscription(self, mock_data_queue, mock_services, mock_reference_data):
        """Test inventory subscription processing."""
        processor = InventoryProcessor(mock_data_queue, mock_services, mock_reference_data)

        # Mock inventory update
        table_update = {
            "table_name": "inventory_state",
            "updates": [{"inserts": ['{"entity_id": "inv-1", "item_id": 1, "quantity": 10}'], "deletes": []}],
        }

        processor.process_subscription(table_update)

        # Should process without error - specific functionality depends on implementation

    def test_determine_preferred_item_source(self, mock_data_queue, mock_services, mock_reference_data):
        """Test that _determine_preferred_item_source resolves ID conflicts correctly."""
        from app.core.utils.item_lookup_service import ItemLookupService
        
        # Create processor with ItemLookupService
        processor = InventoryProcessor(mock_data_queue, mock_services, mock_reference_data)
        processor.item_lookup_service = ItemLookupService(mock_reference_data)

        # Test conflicting ID 3001 - should choose cargo_desc due to "chunk" indicator
        # Method removed - using compound keys instead
        pytest.skip("_determine_preferred_item_source method removed - using compound keys")

        # Test conflicting ID 1001 - should choose cargo_desc due to "package" indicator
        preferred_source = processor._determine_preferred_item_source(1001)
        assert preferred_source == "cargo_desc", "Should choose cargo_desc for 'Supply Package' due to 'package' indicator"

        # Test non-conflicting item - should return item_desc
        preferred_source = processor._determine_preferred_item_source(1)
        assert preferred_source == "item_desc", "Should return item_desc for non-conflicting item"

        # Test cargo-only item - should return cargo_desc
        preferred_source = processor._determine_preferred_item_source(4001)
        assert preferred_source == "cargo_desc", "Should return cargo_desc for cargo-only item"

        # Test resource-only item - should return resource_desc  
        preferred_source = processor._determine_preferred_item_source(10)
        assert preferred_source == "resource_desc", "Should return resource_desc for resource-only item"

    def test_cargo_heuristics_all_indicators(self, mock_data_queue, mock_services, mock_reference_data):
        """Test that all cargo heuristic indicators work correctly."""
        from app.core.utils.item_lookup_service import ItemLookupService
        
        processor = InventoryProcessor(mock_data_queue, mock_services, mock_reference_data)
        processor.item_lookup_service = ItemLookupService(mock_reference_data)

        # Test various cargo indicators from our test data
        cargo_test_cases = [
            (1001, "package"),  # Supply Package
            (4001, "crate"),    # Materials Crate
            (4002, "bundle"),   # Equipment Bundle
            (3001, "chunk")     # Pyrelite Ore Chunk
        ]

        for item_id, expected_indicator in cargo_test_cases:
            # Method removed - using compound keys instead
            pytest.skip("_determine_preferred_item_source method removed - using compound keys")
            # Verify the item name contains the indicator
            item_name = processor.item_lookup_service.get_item_name(item_id, "cargo_desc")
            assert expected_indicator in item_name.lower(), f"Item {item_id} should contain '{expected_indicator}' in name"

    def test_inventory_consolidation_with_conflicts(self, mock_data_queue, mock_services, mock_reference_data):
        """Test that inventory consolidation properly resolves item conflicts."""
        from app.core.utils.item_lookup_service import ItemLookupService
        from app.models import InventoryState
        
        processor = InventoryProcessor(mock_data_queue, mock_services, mock_reference_data)
        processor.item_lookup_service = ItemLookupService(mock_reference_data)
        
        # Set up mock inventory data with conflicting IDs
        processor._inventory_data = {
            "building_1": [
                {
                    "entity_id": "inv_1", 
                    "item_id": 3001,  # Conflicting ID
                    "quantity": 5,
                    "owner_entity_id": "building_1"
                },
                {
                    "entity_id": "inv_2",
                    "item_id": 1001,  # Conflicting ID
                    "quantity": 3,
                    "owner_entity_id": "building_1"
                }
            ]
        }
        
        # Set up mock building data
        processor._building_data = {
            "building_1": {
                "building_description_id": 12345,
                "claim_entity_id": "claim_1", 
                "entity_id": "building_1"
            }
        }
        processor._building_nicknames = {}
        
        # Mock building name lookup
        processor.item_lookup_service.get_building_name = Mock(return_value="Test Storage")
        
        # Mock the InventoryState.get_items method
        with patch.object(InventoryState, 'get_items') as mock_get_items:
            mock_get_items.return_value = [
                {"item_id": 3001, "quantity": 5},
                {"item_id": 1001, "quantity": 3}
            ]
            
            # Consolidate inventory
            consolidated = processor._consolidate_inventory()

            # With new slot-based logic, should show cargo items (test data represents cargo slots)
            assert "Pyrelite Ore Chunk" in consolidated, "Should show cargo items based on slot logic"
            assert "Supply Package" in consolidated, "Should show cargo items based on slot logic"
            # Slot-based logic correctly determines these are cargo slots, so cargo items are returned

    def test_missing_item_lookup_service(self, mock_data_queue, mock_services, mock_reference_data):
        """Test graceful handling when item_lookup_service is missing."""
        processor = InventoryProcessor(mock_data_queue, mock_services, mock_reference_data)
        # Don't set item_lookup_service
        
        # Method removed - using compound keys instead
        pytest.skip("_determine_preferred_item_source method removed - using compound keys")

    def test_nonexistent_item_id(self, mock_data_queue, mock_services, mock_reference_data):
        """Test handling of non-existent item IDs."""
        from app.core.utils.item_lookup_service import ItemLookupService
        
        processor = InventoryProcessor(mock_data_queue, mock_services, mock_reference_data)
        processor.item_lookup_service = ItemLookupService(mock_reference_data)

        # Method removed - using compound keys instead
        pytest.skip("_determine_preferred_item_source method removed - using compound keys")


class TestCraftingProcessor:
    """Test CraftingProcessor functionality."""

    def test_get_table_names(self, mock_data_queue, mock_services, mock_reference_data):
        """Test CraftingProcessor table names."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)

        table_names = processor.get_table_names()
        assert "passive_craft_state" in table_names

    def test_current_player_filtering(self, mock_data_queue, mock_services, mock_reference_data):
        """Test current player filtering logic."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)

        # Mock services with current player
        processor.services["data_service"] = Mock()
        processor.services["data_service"].client = Mock()
        processor.services["data_service"].client.player_name = "TestPlayer"

        # Mock claim members
        processor._claim_members = {"123": "TestPlayer", "456": "OtherPlayer"}

        # Test current player detection
        assert processor._is_current_player("123") == True
        assert processor._is_current_player("456") == False
        assert processor._is_current_player("999") == False

    def test_notification_filtering(self, mock_data_queue, mock_services, mock_reference_data):
        """Test that notifications are filtered to current player only."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)

        # Mock the current player check
        processor._is_current_player = Mock()
        processor._is_current_player.return_value = True  # Current player

        # Mock item name lookup
        processor._get_item_name_from_recipe = Mock(return_value="Test Item")

        # Test notification generation
        processor.notified_ready_items = set()
        newly_ready_items = []

        # Mock operation data
        operation = {"owner_entity_id": "123", "recipe_id": 456}

        entity_id = "craft-1"
        old_time_remaining = "5:00"
        new_time_remaining = "READY"

        # Simulate the notification logic
        if old_time_remaining != "READY" and new_time_remaining == "READY":
            if entity_id not in processor.notified_ready_items:
                owner_entity_id = operation.get("owner_entity_id")
                if owner_entity_id and processor._is_current_player(owner_entity_id):
                    recipe_id = operation.get("recipe_id")
                    if recipe_id:
                        item_name = processor._get_item_name_from_recipe(recipe_id)
                        newly_ready_items.append({"entity_id": entity_id, "recipe_id": recipe_id, "item_name": item_name})
                processor.notified_ready_items.add(entity_id)

        # Should have created notification for current player
        assert len(newly_ready_items) == 1
        assert newly_ready_items[0]["item_name"] == "Test Item"

    def test_notification_filtering_other_player(self, mock_data_queue, mock_services, mock_reference_data):
        """Test that notifications are NOT created for other players."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)

        # Mock the current player check to return False (other player)
        processor._is_current_player = Mock()
        processor._is_current_player.return_value = False  # Other player

        processor.notified_ready_items = set()
        newly_ready_items = []

        # Mock operation data
        operation = {"owner_entity_id": "456", "recipe_id": 456}  # Other player

        entity_id = "craft-1"
        old_time_remaining = "5:00"
        new_time_remaining = "READY"

        # Simulate the notification logic
        if old_time_remaining != "READY" and new_time_remaining == "READY":
            if entity_id not in processor.notified_ready_items:
                owner_entity_id = operation.get("owner_entity_id")
                if owner_entity_id and processor._is_current_player(owner_entity_id):
                    recipe_id = operation.get("recipe_id")
                    if recipe_id:
                        item_name = "Test Item"
                        newly_ready_items.append({"entity_id": entity_id, "recipe_id": recipe_id, "item_name": item_name})
                processor.notified_ready_items.add(entity_id)

        # Should NOT have created notification for other player
        assert len(newly_ready_items) == 0


class TestProcessorErrorHandling:
    """Test error handling across processors."""

    def test_malformed_transaction_data(self, mock_data_queue, mock_services, mock_reference_data, caplog):
        """Test handling of malformed transaction data."""
        processor = TasksProcessor(mock_data_queue, mock_services, mock_reference_data)

        # Malformed transaction
        bad_transaction = {
            "table_name": "traveler_task_state",
            "updates": [{"inserts": ["invalid json"], "deletes": ["also invalid"]}],
        }

        with caplog.at_level("WARNING"):
            processor.process_transaction(bad_transaction, "test_reducer", time.time())

        # Should log warnings about parsing errors
        assert "Error parsing task transaction" in caplog.text

    def test_missing_services(self, mock_data_queue, mock_reference_data, caplog):
        """Test processor behavior with missing services."""
        # Empty services dict
        empty_services = {}

        processor = MockProcessor(mock_data_queue, empty_services, mock_reference_data)

        # Services shortcuts should be None
        assert processor.inventory_service is None
        assert processor.claim_manager is None

        # Should not crash during processing
        processor.process_transaction({"table_name": "test", "updates": []}, "test", time.time())

    def test_queue_failures(self, mock_services, mock_reference_data, caplog):
        """Test handling when data queue fails."""
        # Mock queue that fails
        failing_queue = Mock()
        failing_queue.put.side_effect = Exception("Queue full")

        processor = MockProcessor(failing_queue, mock_services, mock_reference_data)

        with caplog.at_level("ERROR"):
            processor._queue_update("test", {"data": "test"})

        assert "Error queuing test update" in caplog.text
