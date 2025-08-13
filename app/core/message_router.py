"""
Message router for handling SpacetimeDB messages.

Routes TransactionUpdate, SubscriptionUpdate, and InitialSubscription messages
to the appropriate data processors based on table names.
"""

import json
import logging


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

    def _process_transaction_update(self, transaction_data):
        """Process TransactionUpdate messages - LIVE real-time updates."""
        try:
            status = transaction_data.get("status", {})
            reducer_call = transaction_data.get("reducer_call", {})

            logging.debug(f"[MessageRouter] TRANSACTION DEBUG - Status keys: {list(status.keys())}")
            logging.debug(f"[MessageRouter] Reducer call: {reducer_call.get('reducer_name', 'unknown')}")

            # Check if transaction was successful
            if "Committed" not in status:
                logging.debug(f"[MessageRouter] Transaction not committed, status: {list(status.keys())}")
                return

            reducer_name = reducer_call.get("reducer_name", "unknown")
            timestamp_micros = transaction_data.get("timestamp", {}).get("__timestamp_micros_since_unix_epoch__", 0)
            timestamp_seconds = timestamp_micros / 1_000_000 if timestamp_micros else 0

            # Process table updates
            tables = status.get("Committed", {}).get("tables", [])
            logging.debug(f"[MessageRouter] Processing {len(tables)} table updates for reducer: {reducer_name}")

            for table_update in tables:
                table_name = table_update.get("table_name", "")
                logging.debug(f"[MessageRouter] Table update - Name: {table_name}")

                # Route to appropriate processors
                processors = self.table_to_processors.get(table_name, [])
                logging.debug(f"[MessageRouter] Found {len(processors)} processors for table {table_name}")

                for processor in processors:
                    try:
                        logging.debug(f"[MessageRouter] Routing to {processor.__class__.__name__} for table {table_name}")
                        processor.process_transaction(table_update, reducer_name, timestamp_seconds)
                    except Exception as e:
                        logging.error(f"Error in {processor.__class__.__name__} processing transaction: {e}")

        except Exception as e:
            logging.error(f"Error processing transaction update: {e}")

    def _process_subscription_update(self, subscription_data, is_initial=False):
        """Process SubscriptionUpdate messages - batch updates."""
        try:
            database_update = subscription_data.get("database_update", {})
            tables = database_update.get("tables", [])

            update_type = "InitialSubscription" if is_initial else "SubscriptionUpdate"
            logging.info(f"[MessageRouter] Processing {update_type} with {len(tables)} table updates")

            # Group table updates by processor
            processor_updates = {}

            for table_update in tables:
                table_name = table_update.get("table_name", "")
                logging.debug(f"[MessageRouter] {update_type} - Processing table: {table_name}")

                processors = self.table_to_processors.get(table_name, [])
                for processor in processors:
                    if processor not in processor_updates:
                        processor_updates[processor] = []
                    processor_updates[processor].append(table_update)

            # Process updates for each processor
            for processor, updates in processor_updates.items():
                try:
                    logging.debug(
                        f"[MessageRouter] {update_type} - Sending {len(updates)} table updates to {processor.__class__.__name__}"
                    )
                    for update in updates:
                        # Pass is_initial context to processors that support it
                        if hasattr(processor, "process_subscription_with_context"):
                            processor.process_subscription_with_context(update, is_initial=is_initial)
                        else:
                            processor.process_subscription(update)
                except Exception as e:
                    logging.error(f"[MessageRouter] Error in {processor.__class__.__name__} processing {update_type}: {e}")

        except Exception as e:
            logging.error(f"[MessageRouter] Error processing {update_type}: {e}")

    def _process_initial_subscription(self, initial_data):
        """Process InitialSubscription messages - first data load."""
        try:
            database_update = initial_data.get("database_update", {})
            tables = database_update.get("tables", [])

            logging.info(f"[MessageRouter] Processing InitialSubscription with {len(tables)} table updates")

            # Log which tables are in the initial subscription
            table_names = [table.get("table_name", "unknown") for table in tables]
            logging.debug(f"[MessageRouter] InitialSubscription tables: {table_names}")

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
        except Exception as e:
            logging.error(f"Error clearing processor caches: {e}")
