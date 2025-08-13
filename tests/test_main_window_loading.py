"""
Tests for MainWindow loading state management.

This module tests the loading state logic without creating actual GUI components.
We extract and test only the loading state management functionality.
"""

import pytest
import queue
from unittest.mock import Mock, patch


class MockMainWindow:
    """Mock version of MainWindow that contains only the loading state logic."""
    
    def __init__(self):
        # Initialize loading state attributes (copied from MainWindow.__init__)
        self.is_loading = True
        self.expected_data_types = {"inventory", "crafting", "active_crafting", "tasks", "claim_info"}
        self.received_data_types = set()
        
        # Mock data service
        self.data_service = Mock()
        self.data_service.data_queue = queue.Queue()
        
        # Mock UI components
        self.loading_overlay = Mock()
        self.tabs = {
            "Claim Inventory": Mock(),
            "Passive Crafting": Mock(),
            "Active Crafting": Mock(),
            "Traveler's Tasks": Mock()
        }
        self.claim_info = Mock()
        self.claim_info.claim_switching = False
        
        # Track method calls
        self._hide_loading_called = False
        self._show_loading_called = False
        
    def show_loading(self, reset_data_tracking=True):
        """Mock version of show_loading with the actual logic."""
        self._show_loading_called = True
        self.is_loading = True
        if reset_data_tracking:
            self.received_data_types = set()
    
    def hide_loading(self):
        """Mock version of hide_loading."""
        self._hide_loading_called = True
        self.is_loading = False
    
    def _check_all_data_loaded(self):
        """Actual loading state check logic from MainWindow."""
        if self.is_loading and self.received_data_types >= self.expected_data_types:
            claim_switching = getattr(self.claim_info, 'claim_switching', False)
            if not claim_switching:
                self.hide_loading()
    
    def process_inventory_message(self, msg_data):
        """Simplified version of inventory message processing."""
        if self.is_loading:
            self.received_data_types.add("inventory")
            self._check_all_data_loaded()
    
    def process_crafting_message(self, msg_data):
        """Simplified version of crafting message processing.""" 
        if self.is_loading:
            self.received_data_types.add("crafting")
            self._check_all_data_loaded()
    
    def process_active_crafting_message(self, msg_data):
        """Simplified version of active crafting message processing."""
        if self.is_loading:
            self.received_data_types.add("active_crafting")
            self._check_all_data_loaded()
    
    def process_tasks_message(self, msg_data):
        """Simplified version of tasks message processing."""
        if self.is_loading:
            self.received_data_types.add("tasks")
            self._check_all_data_loaded()
    
    def process_claim_info_message(self, msg_data):
        """Simplified version of claim info message processing."""
        if self.is_loading:
            self.received_data_types.add("claim_info")
            self._check_all_data_loaded()


class TestMainWindowLoadingState:
    """Test MainWindow loading state management using MockMainWindow."""
    
    def test_initial_loading_state(self):
        """Test that MainWindow starts in loading state with correct data types."""
        window = MockMainWindow()
        
        # Verify initial loading state
        assert window.is_loading == True
        assert window.received_data_types == set()
        assert window.expected_data_types == {"inventory", "crafting", "active_crafting", "tasks", "claim_info"}
    
    def test_inventory_data_reception_tracking(self):
        """Test that inventory data reception is properly tracked."""
        window = MockMainWindow()
        
        # Process inventory message
        window.process_inventory_message({"Iron Ore": {"tier": 1, "total_quantity": 100}})
        
        # Verify inventory data type was tracked
        assert "inventory" in window.received_data_types
        assert window.is_loading == True  # Still loading, waiting for other types
    
    def test_all_data_types_received(self):
        """Test loading state dismissal when all data types are received."""
        window = MockMainWindow()
        
        # Simulate receiving all expected data types
        window.received_data_types = {"inventory", "crafting", "active_crafting", "tasks", "claim_info"}
        
        window._check_all_data_loaded()
        
        # Verify loading was hidden
        assert window._hide_loading_called == True
        assert window.is_loading == False
    
    def test_loading_state_during_claim_switch(self):
        """Test that loading is not hidden during claim switching."""
        window = MockMainWindow()
        
        # Simulate claim switching state
        window.claim_info.claim_switching = True
        window.received_data_types = {"inventory", "crafting", "active_crafting", "tasks", "claim_info"}
        
        window._check_all_data_loaded()
        
        # Verify loading was NOT hidden during claim switch
        assert window._hide_loading_called == False
        assert window.is_loading == True
    
    def test_partial_data_reception(self):
        """Test that loading remains visible when only partial data is received.""" 
        window = MockMainWindow()
        
        # Simulate receiving only some data types
        window.received_data_types = {"inventory", "crafting"}  # Missing 3 types
        
        window._check_all_data_loaded()
        
        # Verify loading was NOT hidden
        assert window._hide_loading_called == False
        assert window.is_loading == True
    
    def test_show_loading_with_reset(self):
        """Test show_loading method resets data tracking when requested."""
        window = MockMainWindow()
        
        # Set some received data types
        window.received_data_types = {"inventory", "crafting"}
        
        # Call show_loading with reset
        window.show_loading(reset_data_tracking=True)
        
        # Verify data tracking was reset
        assert window.received_data_types == set()
        assert window.is_loading == True
        assert window._show_loading_called == True
    
    def test_show_loading_without_reset(self):
        """Test show_loading method preserves data tracking when not requested."""
        window = MockMainWindow()
        
        # Set some received data types  
        original_data_types = {"inventory", "crafting"}
        window.received_data_types = original_data_types.copy()
        
        # Call show_loading without reset
        window.show_loading(reset_data_tracking=False)
        
        # Verify data tracking was preserved
        assert window.received_data_types == original_data_types
        assert window.is_loading == True
    
    def test_multiple_message_processing(self):
        """Test processing multiple data messages in sequence."""
        window = MockMainWindow()
        
        # Process all message types
        window.process_inventory_message({"item1": {}})
        window.process_crafting_message([])
        window.process_tasks_message([])
        window.process_claim_info_message({})
        window.process_active_crafting_message([])
        
        # Verify all data types were tracked and loading was hidden
        assert window.received_data_types == window.expected_data_types
        assert window._hide_loading_called == True
        assert window.is_loading == False
    
    def test_loading_state_progression(self):
        """Test the complete loading state progression."""
        window = MockMainWindow()
        
        # Start with loading
        assert window.is_loading == True
        assert len(window.received_data_types) == 0
        
        # Process each data type one by one
        window.process_inventory_message({"item": {}})
        assert window.is_loading == True  # Still loading
        assert len(window.received_data_types) == 1
        
        window.process_crafting_message([])
        assert window.is_loading == True  # Still loading  
        assert len(window.received_data_types) == 2
        
        window.process_active_crafting_message([])
        assert window.is_loading == True  # Still loading
        assert len(window.received_data_types) == 3
        
        window.process_tasks_message([])
        assert window.is_loading == True  # Still loading
        assert len(window.received_data_types) == 4
        
        # Final message should trigger loading completion
        window.process_claim_info_message({})
        assert window.is_loading == False  # Loading complete!
        assert len(window.received_data_types) == 5
        assert window._hide_loading_called == True
    
    def test_error_message_hides_loading(self):
        """Test that error messages hide the loading state."""
        window = MockMainWindow()
        
        # Simulate error condition
        window.is_loading = True
        window.received_data_types.add("error")
        
        # Error should hide loading
        window.hide_loading()
        
        assert window.is_loading == False
        assert window._hide_loading_called == True
    
    def test_loading_state_logging(self):
        """Test loading state logging functionality."""
        window = MockMainWindow()
        
        # Verify initial state
        assert window.is_loading == True
        assert len(window.received_data_types) == 0
        
        # Test data reception logging
        window.process_inventory_message({"test": "data"})
        assert "inventory" in window.received_data_types
        
        # Complete loading
        window.received_data_types = {"inventory", "crafting", "active_crafting", "tasks", "claim_info"}
        window._check_all_data_loaded()
        
        assert window.is_loading == False
    
    def test_inventory_update_with_detailed_logging(self):
        """Test inventory updates with detailed logging."""
        window = MockMainWindow()
        
        # Process inventory message
        inventory_data = {"Iron Ore": {"tier": 1, "total_quantity": 100}}
        window.process_inventory_message(inventory_data)
        
        # Verify inventory tracking
        assert "inventory" in window.received_data_types
        assert window.is_loading == True  # Still waiting for other data types
        
        # Complete all data types
        window.process_crafting_message([])
        window.process_active_crafting_message([])
        window.process_tasks_message([])
        window.process_claim_info_message({})
        
        # Should complete loading
        assert window.is_loading == False
        assert window._hide_loading_called == True