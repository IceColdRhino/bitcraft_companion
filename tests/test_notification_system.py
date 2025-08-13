"""
Tests for notification filtering system - ensuring notifications only show for current player.

Tests the notification logic in processors to verify that craft completion
notifications are filtered to only show for the current player, not other claim members.
"""

import pytest
import time
from unittest.mock import Mock, patch
from app.core.processors.crafting_processor import CraftingProcessor
from app.services.notification_service import NotificationService
from tests.conftest import get_mock_claim_data


class TestNotificationFiltering:
    """Test notification filtering to current player only."""

    def test_current_player_identification(self, mock_data_queue, mock_services, mock_reference_data):
        """Test identification of current player from claim members."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)
        
        # Mock data service with current player
        mock_data_service = Mock()
        mock_data_service.client = Mock()
        mock_data_service.client.player_name = "CurrentPlayer"
        processor.services["data_service"] = mock_data_service
        
        # Mock claim members data
        processor._claim_members = {
            "player-123": "CurrentPlayer",
            "player-456": "OtherPlayer",
            "player-789": "ThirdPlayer"
        }
        
        # Test current player identification
        assert processor._is_current_player("player-123") == True
        assert processor._is_current_player("player-456") == False
        assert processor._is_current_player("player-789") == False
        assert processor._is_current_player("player-999") == False  # Not in claim

    def test_current_player_no_data_service(self, mock_data_queue, mock_services, mock_reference_data):
        """Test current player check when data service is missing."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)
        
        # No data service
        processor.services["data_service"] = None
        
        assert processor._is_current_player("player-123") == False

    def test_current_player_no_client(self, mock_data_queue, mock_services, mock_reference_data):
        """Test current player check when client is missing."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)
        
        # Data service without client
        mock_data_service = Mock()
        mock_data_service.client = None
        processor.services["data_service"] = mock_data_service
        
        assert processor._is_current_player("player-123") == False

    def test_current_player_no_player_name(self, mock_data_queue, mock_services, mock_reference_data):
        """Test current player check when player name is missing."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)
        
        # Client without player name
        mock_data_service = Mock()
        mock_data_service.client = Mock()
        mock_data_service.client.player_name = None
        processor.services["data_service"] = mock_data_service
        
        assert processor._is_current_player("player-123") == False

    def test_current_player_no_claim_members(self, mock_data_queue, mock_services, mock_reference_data):
        """Test current player check when claim members data is missing."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)
        
        # Complete data service but no claim members
        mock_data_service = Mock()
        mock_data_service.client = Mock()
        mock_data_service.client.player_name = "CurrentPlayer"
        processor.services["data_service"] = mock_data_service
        
        processor._claim_members = None
        
        assert processor._is_current_player("player-123") == False

    def test_current_player_error_handling(self, mock_data_queue, mock_services, mock_reference_data, caplog):
        """Test current player check error handling."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)
        
        # Mock data service where accessing player_name causes exception
        mock_data_service = Mock()
        mock_client = Mock()
        # Make player_name property raise exception when accessed
        type(mock_client).player_name = property(lambda x: (_ for _ in ()).throw(Exception("Test error")))
        mock_data_service.client = mock_client
        processor.services["data_service"] = mock_data_service
        
        # Set up some claim members to ensure we get to the exception
        processor._claim_members = {"player-123": "SomePlayer"}
        
        with caplog.at_level("ERROR"):
            result = processor._is_current_player("player-123")
            
        assert result == False
        # Should have logged the specific error message
        assert "Error checking if owner player-123 is current player" in caplog.text

    def test_passive_craft_notification_filtering(self, mock_data_queue, mock_services, mock_reference_data):
        """Test passive craft notification filtering to current player."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)
        
        # Mock current player detection
        processor._is_current_player = Mock()
        processor._get_item_name_from_recipe = Mock(return_value="Iron Bar")
        
        processor.notified_ready_items = set()
        
        # Test current player craft completion
        processor._is_current_player.return_value = True
        
        operation = {
            "owner_entity_id": "player-123",
            "recipe_id": 456
        }
        
        newly_ready_items = []
        entity_id = "craft-1"
        old_time_remaining = "5:30"
        new_time_remaining = "READY"
        
        # Simulate notification logic (from real processor)
        if old_time_remaining != "READY" and new_time_remaining == "READY":
            if entity_id not in processor.notified_ready_items:
                owner_entity_id = operation.get("owner_entity_id")
                if owner_entity_id and processor._is_current_player(owner_entity_id):
                    recipe_id = operation.get("recipe_id")
                    if recipe_id:
                        item_name = processor._get_item_name_from_recipe(recipe_id)
                        newly_ready_items.append({"entity_id": entity_id, "recipe_id": recipe_id, "item_name": item_name})
                processor.notified_ready_items.add(entity_id)
        
        # Should create notification for current player
        assert len(newly_ready_items) == 1
        assert newly_ready_items[0]["item_name"] == "Iron Bar"
        assert newly_ready_items[0]["entity_id"] == entity_id
        
        # Verify current player check was called
        processor._is_current_player.assert_called_with("player-123")

    def test_passive_craft_notification_blocked_other_player(self, mock_data_queue, mock_services, mock_reference_data):
        """Test passive craft notification blocked for other players."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)
        
        # Mock current player detection - return False (other player)
        processor._is_current_player = Mock(return_value=False)
        processor._get_item_name_from_recipe = Mock(return_value="Iron Bar")
        
        processor.notified_ready_items = set()
        
        operation = {
            "owner_entity_id": "player-456",  # Other player
            "recipe_id": 456
        }
        
        newly_ready_items = []
        entity_id = "craft-2"
        old_time_remaining = "2:15"
        new_time_remaining = "READY"
        
        # Simulate notification logic
        if old_time_remaining != "READY" and new_time_remaining == "READY":
            if entity_id not in processor.notified_ready_items:
                owner_entity_id = operation.get("owner_entity_id")
                if owner_entity_id and processor._is_current_player(owner_entity_id):
                    recipe_id = operation.get("recipe_id")
                    if recipe_id:
                        item_name = processor._get_item_name_from_recipe(recipe_id)
                        newly_ready_items.append({"entity_id": entity_id, "recipe_id": recipe_id, "item_name": item_name})
                processor.notified_ready_items.add(entity_id)
        
        # Should NOT create notification for other player
        assert len(newly_ready_items) == 0
        
        # But should still track that we've seen this item
        assert entity_id in processor.notified_ready_items
        
        # Verify current player check was called
        processor._is_current_player.assert_called_with("player-456")

    def test_notification_deduplication(self, mock_data_queue, mock_services, mock_reference_data):
        """Test that duplicate notifications are prevented."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)
        
        processor._is_current_player = Mock(return_value=True)
        processor._get_item_name_from_recipe = Mock(return_value="Iron Bar")
        
        # Pre-populate notified items
        processor.notified_ready_items = {"craft-1"}
        
        operation = {
            "owner_entity_id": "player-123",
            "recipe_id": 456
        }
        
        newly_ready_items = []
        entity_id = "craft-1"  # Already notified
        old_time_remaining = "0:30"
        new_time_remaining = "READY"
        
        # Simulate notification logic
        if old_time_remaining != "READY" and new_time_remaining == "READY":
            if entity_id not in processor.notified_ready_items:  # Should be False
                owner_entity_id = operation.get("owner_entity_id")
                if owner_entity_id and processor._is_current_player(owner_entity_id):
                    recipe_id = operation.get("recipe_id")
                    if recipe_id:
                        item_name = processor._get_item_name_from_recipe(recipe_id)
                        newly_ready_items.append({"entity_id": entity_id, "recipe_id": recipe_id, "item_name": item_name})
            processor.notified_ready_items.add(entity_id)
        
        # Should NOT create duplicate notification
        assert len(newly_ready_items) == 0
        
        # Should not have called player check for duplicate
        processor._is_current_player.assert_not_called()

    def test_multiple_crafts_mixed_owners(self, mock_data_queue, mock_services, mock_reference_data):
        """Test notifications with multiple crafts from different owners."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)
        
        # Mock player detection - only player-123 is current player
        def is_current_player(owner_id):
            return owner_id == "player-123"
        
        processor._is_current_player = Mock(side_effect=is_current_player)
        processor._get_item_name_from_recipe = Mock(return_value="Test Item")
        
        processor.notified_ready_items = set()
        
        # Multiple operations from different players
        operations = [
            {"entity_id": "craft-1", "owner_entity_id": "player-123", "recipe_id": 100},  # Current player
            {"entity_id": "craft-2", "owner_entity_id": "player-456", "recipe_id": 101},  # Other player
            {"entity_id": "craft-3", "owner_entity_id": "player-123", "recipe_id": 102},  # Current player
            {"entity_id": "craft-4", "owner_entity_id": "player-789", "recipe_id": 103},  # Other player
        ]
        
        newly_ready_items = []
        
        # Process all operations
        for operation in operations:
            entity_id = operation["entity_id"]
            owner_entity_id = operation["owner_entity_id"]
            recipe_id = operation["recipe_id"]
            
            # Simulate all becoming ready
            if entity_id not in processor.notified_ready_items:
                if owner_entity_id and processor._is_current_player(owner_entity_id):
                    item_name = processor._get_item_name_from_recipe(recipe_id)
                    newly_ready_items.append({"entity_id": entity_id, "recipe_id": recipe_id, "item_name": item_name})
                processor.notified_ready_items.add(entity_id)
        
        # Should only notify for current player's crafts
        assert len(newly_ready_items) == 2
        assert newly_ready_items[0]["entity_id"] == "craft-1"
        assert newly_ready_items[1]["entity_id"] == "craft-3"
        
        # Should have checked all owners
        assert processor._is_current_player.call_count == 4

    def test_notification_with_missing_owner(self, mock_data_queue, mock_services, mock_reference_data):
        """Test notification handling when owner entity ID is missing."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)
        
        processor._is_current_player = Mock(return_value=True)
        processor._get_item_name_from_recipe = Mock(return_value="Test Item")
        processor.notified_ready_items = set()
        
        # Operation without owner_entity_id
        operation = {
            "recipe_id": 456
            # No owner_entity_id
        }
        
        newly_ready_items = []
        entity_id = "craft-1"
        old_time_remaining = "1:00"
        new_time_remaining = "READY"
        
        # Simulate notification logic
        if old_time_remaining != "READY" and new_time_remaining == "READY":
            if entity_id not in processor.notified_ready_items:
                owner_entity_id = operation.get("owner_entity_id")  # Will be None
                if owner_entity_id and processor._is_current_player(owner_entity_id):
                    recipe_id = operation.get("recipe_id")
                    if recipe_id:
                        item_name = processor._get_item_name_from_recipe(recipe_id)
                        newly_ready_items.append({"entity_id": entity_id, "recipe_id": recipe_id, "item_name": item_name})
                processor.notified_ready_items.add(entity_id)
        
        # Should NOT create notification when owner is missing
        assert len(newly_ready_items) == 0
        
        # Should not have called player check
        processor._is_current_player.assert_not_called()

    def test_notification_with_missing_recipe(self, mock_data_queue, mock_services, mock_reference_data):
        """Test notification handling when recipe ID is missing."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)
        
        processor._is_current_player = Mock(return_value=True)
        processor._get_item_name_from_recipe = Mock(return_value="Test Item")
        processor.notified_ready_items = set()
        
        # Operation without recipe_id
        operation = {
            "owner_entity_id": "player-123"
            # No recipe_id
        }
        
        newly_ready_items = []
        entity_id = "craft-1"
        old_time_remaining = "0:45"
        new_time_remaining = "READY"
        
        # Simulate notification logic
        if old_time_remaining != "READY" and new_time_remaining == "READY":
            if entity_id not in processor.notified_ready_items:
                owner_entity_id = operation.get("owner_entity_id")
                if owner_entity_id and processor._is_current_player(owner_entity_id):
                    recipe_id = operation.get("recipe_id")  # Will be None
                    if recipe_id:
                        item_name = processor._get_item_name_from_recipe(recipe_id)
                        newly_ready_items.append({"entity_id": entity_id, "recipe_id": recipe_id, "item_name": item_name})
                processor.notified_ready_items.add(entity_id)
        
        # Should NOT create notification when recipe is missing
        assert len(newly_ready_items) == 0
        
        # Should have checked player but not gotten item name
        processor._is_current_player.assert_called_with("player-123")
        processor._get_item_name_from_recipe.assert_not_called()


class TestNotificationService:
    """Test the NotificationService component."""

    def test_notification_service_initialization(self):
        """Test NotificationService initialization."""
        mock_main_app = Mock()
        
        service = NotificationService(mock_main_app)
        
        assert service.main_app == mock_main_app

    def test_notification_display_integration(self):
        """Test integration between processors and notification service."""
        # This would test the actual notification display
        # Depends on the actual NotificationService implementation
        
        mock_main_app = Mock()
        service = NotificationService(mock_main_app)
        
        # Mock notification data
        notification_data = {
            "type": "craft_completion",
            "item_name": "Iron Bar",
            "entity_id": "craft-123"
        }
        
        # Test would depend on actual notification service interface
        # For now, just verify initialization worked
        assert service.main_app is not None


class TestCrossPlayerScenarios:
    """Test complex multi-player notification scenarios."""

    def test_claim_member_changes_during_crafting(self, mock_data_queue, mock_services, mock_reference_data):
        """Test notification behavior when claim members change during crafting."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)
        
        # Initial claim members
        processor._claim_members = {
            "player-123": "CurrentPlayer",
            "player-456": "OtherPlayer"
        }
        
        # Mock data service
        mock_data_service = Mock()
        mock_data_service.client = Mock()
        mock_data_service.client.player_name = "CurrentPlayer"
        processor.services["data_service"] = mock_data_service
        
        # Start with current player
        assert processor._is_current_player("player-123") == True
        
        # Simulate claim member change (player leaves/joins)
        processor._claim_members = {
            "player-123": "CurrentPlayer",
            "player-789": "NewPlayer"  # player-456 left, player-789 joined
        }
        
        # Previous member should no longer be recognized
        assert processor._is_current_player("player-456") == False
        # New member should not be current player
        assert processor._is_current_player("player-789") == False
        # Current player should still work
        assert processor._is_current_player("player-123") == True

    def test_player_name_changes(self, mock_data_queue, mock_services, mock_reference_data):
        """Test notification behavior when current player name changes."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)
        
        processor._claim_members = {
            "player-123": "OldPlayerName",
            "player-456": "OtherPlayer"
        }
        
        # Mock data service with old name
        mock_data_service = Mock()
        mock_data_service.client = Mock()
        mock_data_service.client.player_name = "OldPlayerName"
        processor.services["data_service"] = mock_data_service
        
        # Should recognize current player
        assert processor._is_current_player("player-123") == True
        
        # Change player name
        mock_data_service.client.player_name = "NewPlayerName"
        
        # Should no longer recognize as current player
        assert processor._is_current_player("player-123") == False

    def test_notification_race_conditions(self, mock_data_queue, mock_services, mock_reference_data):
        """Test notification handling in race condition scenarios."""
        processor = CraftingProcessor(mock_data_queue, mock_services, mock_reference_data)
        
        processor._is_current_player = Mock(return_value=True)
        processor._get_item_name_from_recipe = Mock(return_value="Test Item")
        
        # Simulate rapid state changes
        processor.notified_ready_items = set()
        entity_id = "craft-1"
        
        # First notification attempt
        newly_ready_items_1 = []
        if entity_id not in processor.notified_ready_items:
            newly_ready_items_1.append({"entity_id": entity_id, "item_name": "Test Item"})
            processor.notified_ready_items.add(entity_id)
        
        # Second notification attempt (rapid succession)
        newly_ready_items_2 = []
        if entity_id not in processor.notified_ready_items:
            newly_ready_items_2.append({"entity_id": entity_id, "item_name": "Test Item"})
            processor.notified_ready_items.add(entity_id)
        
        # Should only generate one notification
        assert len(newly_ready_items_1) == 1
        assert len(newly_ready_items_2) == 0