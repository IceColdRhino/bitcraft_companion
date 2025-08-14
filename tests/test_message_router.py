"""
Tests for MessageRouter - the core message routing system.

Tests routing of SpacetimeDB messages (TransactionUpdate, SubscriptionUpdate, 
InitialSubscription) to appropriate processors based on table names.
"""

import pytest
import queue
from unittest.mock import Mock, patch
from app.core.message_router import MessageRouter
from tests.conftest import MockProcessor, get_mock_spacetime_messages


class TestMessageRouter:
    """Test the MessageRouter class functionality."""

    def test_router_initialization(self, mock_processors, mock_data_queue):
        """Test MessageRouter initialization and processor mapping."""
        router = MessageRouter(mock_processors, mock_data_queue)
        
        # Verify processors are stored
        assert router.processors == mock_processors
        assert router.data_queue == mock_data_queue
        
        # Verify table-to-processor mapping is built correctly
        expected_tables = {
            "inventory_state": [mock_processors[0]],
            "passive_craft_state": [mock_processors[1]], 
            "traveler_task_state": [mock_processors[1]],
            "claim_state": [mock_processors[2]]
        }
        
        for table_name, expected_procs in expected_tables.items():
            assert table_name in router.table_to_processors
            assert router.table_to_processors[table_name] == expected_procs

    def test_transaction_update_routing(self, mock_processors, mock_data_queue, mock_spacetime_messages):
        """Test routing of TransactionUpdate messages to processors."""
        router = MessageRouter(mock_processors, mock_data_queue)
        
        # Get the transaction update message
        transaction_msg = mock_spacetime_messages["transaction_update"]
        
        # Process the message
        router.handle_message(transaction_msg)
        
        # Verify the inventory processor received the transaction
        inventory_processor = mock_processors[0]  # Handles inventory_state
        assert len(inventory_processor.processed_transactions) == 1
        
        transaction = inventory_processor.processed_transactions[0]
        assert transaction["reducer_name"] == "add_item"
        assert transaction["timestamp"] == 1640995200.0  # Converted from micros
        assert "inventory_state" in transaction["table_update"]["table_name"]

    def test_subscription_update_routing(self, mock_processors, mock_data_queue, mock_spacetime_messages):
        """Test routing of SubscriptionUpdate messages to processors."""
        router = MessageRouter(mock_processors, mock_data_queue)
        
        # Get the subscription update message
        subscription_msg = mock_spacetime_messages["subscription_update"]
        
        # Process the message
        router.handle_message(subscription_msg)
        
        # Verify the inventory processor received the subscription update
        inventory_processor = mock_processors[0]
        assert len(inventory_processor.processed_subscriptions) == 1
        
        subscription = inventory_processor.processed_subscriptions[0]
        assert subscription["table_name"] == "inventory_state"
        assert len(subscription["inserts"]) == 2  # Two inventory items

    def test_initial_subscription_routing(self, mock_processors, mock_data_queue, mock_spacetime_messages):
        """Test routing of InitialSubscription messages to processors."""
        router = MessageRouter(mock_processors, mock_data_queue)
        
        # Get the initial subscription message
        initial_msg = mock_spacetime_messages["initial_subscription"]
        
        # Process the message
        router.handle_message(initial_msg)
        
        # Verify both inventory and crafting processors received updates
        inventory_processor = mock_processors[0]  # inventory_state
        crafting_processor = mock_processors[1]   # passive_craft_state
        
        assert len(inventory_processor.processed_subscriptions) == 1
        assert len(crafting_processor.processed_subscriptions) == 1
        
        # Verify table names are correct
        inv_sub = inventory_processor.processed_subscriptions[0]
        craft_sub = crafting_processor.processed_subscriptions[0]
        
        assert inv_sub["table_name"] == "inventory_state"
        assert craft_sub["table_name"] == "passive_craft_state"

    def test_unknown_message_type(self, mock_processors, mock_data_queue, caplog):
        """Test handling of unknown message types."""
        router = MessageRouter(mock_processors, mock_data_queue)
        
        unknown_msg = {"UnknownMessageType": {"some_data": "test"}}
        
        with caplog.at_level("WARNING"):
            router.handle_message(unknown_msg)
        
        # Should log warning about unknown message type
        assert "Unknown message type" in caplog.text
        assert "UnknownMessageType" in caplog.text

    def test_transaction_not_committed(self, mock_processors, mock_data_queue):
        """Test that uncommitted transactions are ignored."""
        router = MessageRouter(mock_processors, mock_data_queue)
        
        # Create transaction with failed status
        failed_transaction = {
            "TransactionUpdate": {
                "status": {"Failed": {"error": "Some error"}},
                "reducer_call": {"reducer_name": "test_reducer"},
                "timestamp": {"__timestamp_micros_since_unix_epoch__": 1640995200000000}
            }
        }
        
        router.handle_message(failed_transaction)
        
        # Verify no processors received the transaction
        for processor in mock_processors:
            assert len(processor.processed_transactions) == 0

    def test_table_not_handled_by_any_processor(self, mock_processors, mock_data_queue, caplog):
        """Test handling of tables not handled by any processor."""
        router = MessageRouter(mock_processors, mock_data_queue)
        
        # Create transaction for unknown table
        unknown_table_msg = {
            "TransactionUpdate": {
                "status": {
                    "Committed": {
                        "tables": [{
                            "table_name": "unknown_table",
                            "inserts": [{"id": 1}],
                            "deletes": []
                        }]
                    }
                },
                "reducer_call": {"reducer_name": "test_reducer"},
                "timestamp": {"__timestamp_micros_since_unix_epoch__": 1640995200000000}
            }
        }
        
        with caplog.at_level("DEBUG"):
            router.handle_message(unknown_table_msg)
        
        # Should log that no processors were found for the table
        assert "No processors found for table 'unknown_table'" in caplog.text

    def test_processor_error_handling(self, mock_data_queue, caplog):
        """Test error handling when processors throw exceptions."""
        # Create a processor that throws an exception
        error_processor = MockProcessor(["inventory_state"])
        
        def failing_process_transaction(*args, **kwargs):
            raise ValueError("Test processor error")
        
        error_processor.process_transaction = failing_process_transaction
        
        router = MessageRouter([error_processor], mock_data_queue)
        
        transaction_msg = {
            "TransactionUpdate": {
                "status": {
                    "Committed": {
                        "tables": [{
                            "table_name": "inventory_state",
                            "inserts": [{"id": 1}],
                            "deletes": []
                        }]
                    }
                },
                "reducer_call": {"reducer_name": "test_reducer"},
                "timestamp": {"__timestamp_micros_since_unix_epoch__": 1640995200000000}
            }
        }
        
        with caplog.at_level("ERROR"):
            router.handle_message(transaction_msg)
        
        # Should log the error but not crash
        assert "Error in MockProcessor processing transaction" in caplog.text
        assert "Test processor error" in caplog.text

    def test_clear_all_processor_caches(self, mock_processors, mock_data_queue):
        """Test clearing caches in all processors."""
        router = MessageRouter(mock_processors, mock_data_queue)
        
        # Mock the clear_cache method for each processor
        for processor in mock_processors:
            processor.clear_cache = Mock()
        
        # Clear all caches
        router.clear_all_processor_caches()
        
        # Verify clear_cache was called on each processor
        for processor in mock_processors:
            processor.clear_cache.assert_called_once()

    def test_processor_without_clear_cache_method(self, mock_data_queue, caplog):
        """Test handling processors that don't have clear_cache method."""
        # Create processor without clear_cache method
        processor_no_cache = MockProcessor(["test_table"])
        # Remove the clear_cache method
        processor_no_cache.clear_cache = None
        
        router = MessageRouter([processor_no_cache], mock_data_queue)
        
        # Should not crash when processor lacks clear_cache
        with caplog.at_level("ERROR"):
            router.clear_all_processor_caches()
        
        # Should log an error about the failed cache clear
        assert "Error clearing processor caches" in caplog.text

    def test_multiple_processors_same_table(self, mock_data_queue):
        """Test that multiple processors can handle the same table."""
        # Create two processors that both handle inventory_state
        processor1 = MockProcessor(["inventory_state"])
        processor2 = MockProcessor(["inventory_state"])
        
        router = MessageRouter([processor1, processor2], mock_data_queue)
        
        # Verify both processors are mapped to the same table
        assert len(router.table_to_processors["inventory_state"]) == 2
        assert processor1 in router.table_to_processors["inventory_state"]
        assert processor2 in router.table_to_processors["inventory_state"]
        
        # Send a transaction and verify both processors receive it
        transaction_msg = {
            "TransactionUpdate": {
                "status": {
                    "Committed": {
                        "tables": [{
                            "table_name": "inventory_state",
                            "inserts": [{"id": 1}],
                            "deletes": []
                        }]
                    }
                },
                "reducer_call": {"reducer_name": "test_reducer"},
                "timestamp": {"__timestamp_micros_since_unix_epoch__": 1640995200000000}
            }
        }
        
        router.handle_message(transaction_msg)
        
        # Both processors should have received the transaction
        assert len(processor1.processed_transactions) == 1
        assert len(processor2.processed_transactions) == 1