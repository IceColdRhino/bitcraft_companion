"""
Message router for handling SpacetimeDB messages.

Routes TransactionUpdate, SubscriptionUpdate, and InitialSubscription messages
to the appropriate data processors based on table names.
"""

import json
import logging
from app.models import (
    InventoryState, PassiveCraftState, ProgressiveActionState,
    TravelerTaskState, ClaimLocalState, ClaimState, ClaimMemberState,
    BuildingState, PublicProgressiveActionState,
    # Reference data dataclasses
    ResourceDesc, ItemDesc, CargoDesc, BuildingDesc, BuildingTypeDesc,
    CraftingRecipeDesc, ClaimTileCost, NpcDesc, BuildingFunctionTypeMappingDesc
)


class MessageRouter:
    """
    Routes SpacetimeDB messages to appropriate data processors.

    Handles the message routing logic that was previously in DataService._handle_message()
    """

    def __init__(self, processors, data_queue):
        """
        Initialize the message router with processors.

        Args:
            processors: List of data processor instances
            data_queue: Thread-safe queue for sending data to UI
        """
        self.processors = processors
        self.data_queue = data_queue

        # Build mapping of table names to processors
        self.table_to_processors = {}
        for processor in processors:
            for table_name in processor.get_table_names():
                if table_name not in self.table_to_processors:
                    self.table_to_processors[table_name] = []
                self.table_to_processors[table_name].append(processor)

        # Mapping of table names to their corresponding dataclasses for validation
        self.table_dataclass_mapping = {
            "inventory_state": InventoryState,
            "passive_craft_state": PassiveCraftState,
            "progressive_action_state": ProgressiveActionState,
            "traveler_task_state": TravelerTaskState,
            "claim_local_state": ClaimLocalState,
            "claim_state": ClaimState,
            "claim_member_state": ClaimMemberState,
            "building_state": BuildingState,
            "public_progressive_action_state": PublicProgressiveActionState,
            # Reference data tables
            "resource_desc": ResourceDesc,
            "item_desc": ItemDesc,
            "cargo_desc": CargoDesc,
            "building_desc": BuildingDesc,
            "building_type_desc": BuildingTypeDesc,
            "crafting_recipe_desc": CraftingRecipeDesc,
            "claim_tile_cost": ClaimTileCost,
            "npc_desc": NpcDesc,
            "building_function_type_mapping_desc": BuildingFunctionTypeMappingDesc,
        }

        # Statistics for monitoring dataclass validation
        self.validation_stats = {
            "total_validations": 0,
            "successful_validations": 0,
            "validation_errors": 0,
            "table_validation_counts": {},
        }

    def handle_message(self, message):
        """
        Main message handler - routes all SpacetimeDB message types.

        This replaces DataService._handle_message() and routes messages to processors.

        Args:
            message: The complete message from SpacetimeDB
        """
        try:
            if "TransactionUpdate" in message:
                self._process_transaction_update(message["TransactionUpdate"])
            elif "SubscriptionUpdate" in message:
                self._process_subscription_update(message["SubscriptionUpdate"])
            elif "InitialSubscription" in message:
                self._process_initial_subscription(message["InitialSubscription"])
            else:
                logging.warning(f"Unknown message type: {list(message.keys())}")

        except Exception as e:
            logging.error(f"Error in message router: {e}")
            # Log validation stats on error for debugging
            self._log_validation_stats()

    def _process_transaction_update(self, transaction_data):
        """Process TransactionUpdate messages - LIVE real-time updates."""
        try:
            status = transaction_data.get("status", {})
            reducer_call = transaction_data.get("reducer_call", {})

            # Check if transaction was successful
            if "Committed" not in status:
                if status:
                    logging.warning(f"Transaction not committed, status: {list(status.keys())} - data may be outdated")
                return

            reducer_name = reducer_call.get("reducer_name", "unknown")
            timestamp_micros = transaction_data.get("timestamp", {}).get("__timestamp_micros_since_unix_epoch__", 0)
            timestamp_seconds = timestamp_micros / 1_000_000 if timestamp_micros else 0

            # Process table updates
            tables = status.get("Committed", {}).get("tables", [])

            for table_update in tables:
                table_name = table_update.get("table_name", "")

                # Route to appropriate processors
                processors = self.table_to_processors.get(table_name, [])
                if not processors and table_name:
                    logging.warning(f"No processors found for table '{table_name}' - data will not be processed")

                # Validate data if we have a dataclass for this table
                self._validate_table_data(table_name, table_update, "transaction")

                for processor in processors:
                    try:
                        processor.process_transaction(table_update, reducer_name, timestamp_seconds)
                    except Exception as e:
                        logging.error(f"Error in {processor.__class__.__name__} processing transaction: {e}")
                        # Log additional context for debugging
                        self._log_processor_error(processor, table_name, "transaction", e)

        except Exception as e:
            logging.error(f"Error processing transaction update: {e}")

    def _process_subscription_update(self, subscription_data, is_initial=False):
        """Process SubscriptionUpdate messages - batch updates."""
        try:
            database_update = subscription_data.get("database_update", {})
            tables = database_update.get("tables", [])

            update_type = "InitialSubscription" if is_initial else "SubscriptionUpdate"
            if is_initial:
                logging.info(f"Loading initial game data ({len(tables)} tables)")
            else:
                pass

            # Group table updates by processor
            processor_updates = {}

            for table_update in tables:
                table_name = table_update.get("table_name", "")

                processors = self.table_to_processors.get(table_name, [])
                if not processors and table_name:
                    logging.warning(f"No processors found for subscription table '{table_name}' - data will not be processed")
                
                for processor in processors:
                    if processor not in processor_updates:
                        processor_updates[processor] = []
                    processor_updates[processor].append(table_update)

            # Process updates for each processor
            for processor, updates in processor_updates.items():
                try:
                    for update in updates:
                        # Validate subscription data if we have a dataclass for this table
                        table_name = update.get("table_name", "")
                        self._validate_table_data(table_name, update, "subscription")

                        # Pass is_initial context to processors that support it
                        if hasattr(processor, "process_subscription_with_context"):
                            processor.process_subscription_with_context(update, is_initial=is_initial)
                        else:
                            processor.process_subscription(update)
                except Exception as e:
                    logging.error(f"[MessageRouter] Error in {processor.__class__.__name__} processing {update_type}: {e}")
                    # Enhanced error logging for subscription processing
                    self._log_processor_error(processor, "subscription_batch", update_type, e)

        except Exception as e:
            logging.error(f"[MessageRouter] Error processing {update_type}: {e}")

    def _process_initial_subscription(self, initial_data):
        """Process InitialSubscription messages - first data load."""
        try:
            database_update = initial_data.get("database_update", {})
            tables = database_update.get("tables", [])

            logging.info(f"Loading initial subscription data ({len(tables)} tables)")

            # Log which tables are in the initial subscription
            table_names = [table.get("table_name", "unknown") for table in tables]

            # Process similar to subscription update but mark as initial
            self._process_subscription_update(initial_data, is_initial=True)

        except Exception as e:
            logging.error(f"[MessageRouter] Error processing initial subscription: {e}")

    def clear_all_processor_caches(self):
        """Clear caches in all processors to ensure fresh data on refresh."""
        try:
            for processor in self.processors:
                if hasattr(processor, "clear_cache"):
                    processor.clear_cache()
                    logging.debug(f"Cleared cache for {processor.__class__.__name__}")
            logging.info(f"Cleared caches for {len(self.processors)} processors")
            # Reset validation stats on cache clear
            self._reset_validation_stats()
        except Exception as e:
            logging.error(f"Error clearing processor caches: {e}")

    def _validate_table_data(self, table_name, table_update, update_type):
        """
        Validate table data using appropriate dataclass if available.
        
        Args:
            table_name: Name of the table being updated
            table_update: The table update data
            update_type: Type of update ("transaction" or "subscription")
        """
        try:
            dataclass_type = self.table_dataclass_mapping.get(table_name)
            if not dataclass_type:
                return  # No validation available for this table

            self.validation_stats["total_validations"] += 1
            if table_name not in self.validation_stats["table_validation_counts"]:
                self.validation_stats["table_validation_counts"][table_name] = {"success": 0, "error": 0}

            # Extract sample data for validation
            updates = table_update.get("updates", [])
            validation_samples = 0
            validation_errors = 0

            for update in updates:
                inserts = update.get("inserts", [])
                
                # Validate a sample of inserts (limit to avoid performance impact)
                for i, insert_str in enumerate(inserts[:5]):  # Only validate first 5 records
                    try:
                        if isinstance(insert_str, str):
                            import json
                            data = json.loads(insert_str)
                        else:
                            data = insert_str

                        # Try to create dataclass instance for validation
                        if update_type == "subscription":
                            # Subscription data is usually in dict format
                            if isinstance(data, dict):
                                dataclass_type.from_dict(data)
                            else:
                                # Check if from_array method exists
                                if hasattr(dataclass_type, 'from_array'):
                                    dataclass_type.from_array(data)
                                else:
                                    # Skip validation for classes without from_array
                                    continue
                        else:
                            # Transaction data is usually in array format  
                            if isinstance(data, list):
                                # Check if from_array method exists
                                if hasattr(dataclass_type, 'from_array'):
                                    dataclass_type.from_array(data)
                                else:
                                    # Skip validation for classes without from_array
                                    continue
                            else:
                                dataclass_type.from_dict(data)
                        
                        validation_samples += 1
                        
                    except Exception as validation_error:
                        validation_errors += 1
                        if validation_errors <= 2:  # Only log first few errors per batch
                            logging.warning(f"Dataclass validation failed for {table_name}, data may be inconsistent: {validation_error}")
                            logging.debug(f"Dataclass validation warning for {table_name}: {validation_error}")

            # Update statistics
            if validation_errors == 0 and validation_samples > 0:
                self.validation_stats["successful_validations"] += 1
                self.validation_stats["table_validation_counts"][table_name]["success"] += 1
            elif validation_errors > 0:
                self.validation_stats["validation_errors"] += 1
                self.validation_stats["table_validation_counts"][table_name]["error"] += 1
                
        except Exception as e:
            logging.debug(f"Error in dataclass validation for {table_name}: {e}")

    def _log_processor_error(self, processor, table_name, operation_type, error):
        """
        Enhanced error logging for processor operations.
        
        Args:
            processor: The processor that encountered the error
            table_name: Name of the table being processed
            operation_type: Type of operation ("transaction", "subscription", etc.)
            error: The exception that occurred
        """
        try:
            error_context = {
                "processor": processor.__class__.__name__,
                "table_name": table_name,
                "operation_type": operation_type,
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
            
            logging.error(f"Processor error context: {error_context}")
            
        except Exception as log_error:
            logging.error(f"Error logging processor error context: {log_error}")

    def _log_validation_stats(self):
        """
        Log current dataclass validation statistics for monitoring.
        """
        try:
            if self.validation_stats["total_validations"] > 0:
                success_rate = (self.validation_stats["successful_validations"] / 
                               self.validation_stats["total_validations"]) * 100
                
                logging.info(
                    f"Dataclass validation stats: {self.validation_stats['successful_validations']}/"
                    f"{self.validation_stats['total_validations']} successful ({success_rate:.1f}%)"
                )
                
                # Log per-table stats if there are errors
                if self.validation_stats["validation_errors"] > 0:
                    for table_name, counts in self.validation_stats["table_validation_counts"].items():
                        if counts["error"] > 0:
                            logging.debug(f"Table {table_name}: {counts['success']} success, {counts['error']} errors")
                            
        except Exception as e:
            logging.debug(f"Error logging validation stats: {e}")

    def _reset_validation_stats(self):
        """
        Reset validation statistics (called on cache clear).
        """
        self.validation_stats = {
            "total_validations": 0,
            "successful_validations": 0,
            "validation_errors": 0,
            "table_validation_counts": {},
        }
        logging.debug("Reset dataclass validation statistics")

    def get_validation_stats(self):
        """
        Get current validation statistics for monitoring.
        
        Returns:
            dict: Current validation statistics
        """
        return self.validation_stats.copy()
