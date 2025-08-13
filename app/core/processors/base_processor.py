"""
Base processor class for handling SpacetimeDB message data.

All data processors inherit from this class and implement the standard interface
for processing transactions and subscriptions.
"""

import logging
from abc import ABC, abstractmethod


class BaseProcessor(ABC):
    """
    Abstract base class for all data processors.

    Provides standard interface and shared functionality for processing
    SpacetimeDB transactions and subscriptions.
    """

    def __init__(self, data_queue, services, reference_data):
        """
        Initialize the processor with required dependencies.

        Args:
            data_queue: Thread-safe queue for sending data to UI
            services: Dictionary of service instances (inventory_service, etc.)
            reference_data: Game reference data (items, recipes, etc.)
        """
        self.data_queue = data_queue
        self.services = services
        self.reference_data = reference_data

        # Quick access to commonly used services
        self.inventory_service = services.get("inventory_service")
        self.passive_crafting_service = services.get("passive_crafting_service")
        self.traveler_tasks_service = services.get("traveler_tasks_service")
        self.active_crafting_service = services.get("active_crafting_service")
        self.compare_jobs_service = services.get("compare_jobs_service")
        self.claim_manager = services.get("claim_manager")
        self.item_lookup_service = services.get("item_lookup_service")

    @abstractmethod
    def process_transaction(self, table_update, reducer_name, timestamp):
        """
        Process a TransactionUpdate for this processor's table type.

        Args:
            table_update: The table update data from SpacetimeDB
            reducer_name: Name of the reducer that caused this transaction
            timestamp: Transaction timestamp in seconds
        """
        pass

    @abstractmethod
    def process_subscription(self, table_update):
        """
        Process a SubscriptionUpdate for this processor's table type.

        Args:
            table_update: The table update data from SpacetimeDB
        """
        pass

    @abstractmethod
    def get_table_names(self):
        """
        Return list of table names this processor handles.

        Returns:
            List[str]: Table names this processor is responsible for
        """
        pass

    def clear_cache(self):
        """
        Clear cached subscription data when switching claims.
        Override in subclasses to clear processor-specific cached data.

        This method is called during claim switching to prevent data contamination
        between different claims.
        """
        logging.info(f"Clearing cache for {self.__class__.__name__}")

    def _queue_update(self, update_type, data, changes=None, timestamp=None):
        """
        Helper method to send data updates to the UI queue.

        Args:
            update_type: Type of update (e.g., 'inventory_update')
            data: The data to send
            changes: Optional changes dictionary
            timestamp: Optional timestamp
        """
        try:
            update = {"type": update_type, "data": data}

            if changes is not None:
                update["changes"] = changes

            if timestamp is not None:
                update["timestamp"] = timestamp

            self.data_queue.put(update)

        except Exception as e:
            logging.error(f"Error queuing {update_type} update: {e}")

    def _log_transaction_debug(self, table_name, inserts, deletes, reducer_name):
        """
        Helper method for consistent transaction logging.

        Args:
            table_name: Name of the table being updated
            inserts: Number of inserts
            deletes: Number of deletes
            reducer_name: Name of the reducer
        """
        if inserts or deletes:
            pass
