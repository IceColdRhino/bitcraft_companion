"""
Inventory processor for handling inventory_state table updates.
"""

import logging
from .base_processor import BaseProcessor
from app.models import InventoryState, BuildingState


class InventoryProcessor(BaseProcessor):
    """
    Processes inventory_state table updates from SpacetimeDB.

    Handles both real-time transactions and batch subscription updates
    for inventory changes.
    """

    def get_table_names(self):
        """Return list of table names this processor handles."""
        return ["inventory_state", "building_state", "building_nickname_state"]

    def process_transaction(self, table_update, reducer_name, timestamp):
        """
        Handle inventory_state transactions - LIVE incremental updates.

        Process real-time inventory changes without full refresh.
        """
        try:
            table_name = table_update.get("table_name", "")
            updates = table_update.get("updates", [])

            # Track if we need to send updates
            has_inventory_changes = False

            for update in updates:
                inserts = update.get("inserts", [])
                deletes = update.get("deletes", [])

                # Process inventory_state updates (item moves, additions, removals)
                if table_name == "inventory_state":
                    # Collect all operations first to handle delete+insert as updates
                    delete_operations = {}
                    insert_operations = {}

                    # Parse all deletes using dataclass
                    for delete_str in deletes:
                        try:
                            inventory_state = InventoryState.from_array(delete_str)
                            if inventory_state:
                                delete_operations[inventory_state.entity_id] = inventory_state.to_dict()
                        except (ValueError, TypeError) as e:
                            logging.debug(f"Failed to parse inventory delete: {e}")
                            continue

                    # Parse all inserts using dataclass
                    for insert_str in inserts:
                        try:
                            inventory_state = InventoryState.from_array(insert_str)
                            if inventory_state:
                                insert_operations[inventory_state.entity_id] = inventory_state.to_dict()
                        except (ValueError, TypeError) as e:
                            logging.debug(f"Failed to parse inventory insert: {e}")
                            continue

                    # Process operations: handle delete+insert as updates, standalone deletes as removals
                    if not hasattr(self, "_inventory_data"):
                        self._inventory_data = {}

                    # Handle updates (delete+insert for same entity) and new inserts
                    for entity_id in insert_operations:
                        insert_data = insert_operations[entity_id]
                        owner_entity_id = insert_data.get("owner_entity_id")

                        if owner_entity_id:
                            # Update inventory data cache
                            if owner_entity_id not in self._inventory_data:
                                self._inventory_data[owner_entity_id] = []

                            # Remove old record if this is an update
                            if entity_id in delete_operations:
                                # Find and remove the old record
                                self._inventory_data[owner_entity_id] = [
                                    record
                                    for record in self._inventory_data[owner_entity_id]
                                    if record.get("entity_id") != entity_id
                                ]

                            # Add new record
                            self._inventory_data[owner_entity_id].append(insert_data)
                            has_inventory_changes = True

                    # Handle standalone deletes (item removals)
                    for entity_id in delete_operations:
                        if entity_id not in insert_operations:
                            # This is a standalone delete (item removal)
                            delete_data = delete_operations[entity_id]
                            owner_entity_id = delete_data.get("owner_entity_id")

                            if owner_entity_id and owner_entity_id in self._inventory_data:
                                # Remove the record
                                self._inventory_data[owner_entity_id] = [
                                    record
                                    for record in self._inventory_data[owner_entity_id]
                                    if record.get("entity_id") != entity_id
                                ]
                                has_inventory_changes = True

                # For other table types, do full refresh if we have changes
                elif inserts or deletes:
                    self._log_transaction_debug("inventory", len(inserts), len(deletes), reducer_name)
                    has_inventory_changes = True

            # Send incremental update if we have changes
            if has_inventory_changes:
                if table_name == "inventory_state":
                    self._send_incremental_inventory_update(reducer_name, timestamp)
                else:
                    self._refresh_inventory()

        except Exception as e:
            logging.error(f"Error handling inventory transaction: {e}")

    def process_subscription(self, table_update):
        """
        Handle inventory_state, building_state, and building_nickname_state subscription updates.
        Cache all data and combine them for consolidated inventory.
        """
        try:
            table_name = table_update.get("table_name", "")
            table_rows = []

            # Extract rows from table update
            for update in table_update.get("updates", []):
                for insert_str in update.get("inserts", []):
                    try:
                        import json

                        row_data = json.loads(insert_str)
                        table_rows.append(row_data)
                    except json.JSONDecodeError:
                        logging.warning(f"Failed to parse {table_name} insert: {insert_str[:100]}...")

            if not table_rows:
                return

            # Handle different table types
            if table_name == "inventory_state":
                self._process_inventory_data(table_rows)
            elif table_name == "building_state":
                self._process_building_data(table_rows)
            elif table_name == "building_nickname_state":
                self._process_building_nickname_data(table_rows)

            # Try to send consolidated inventory if we have all necessary data
            self._send_inventory_update()

        except Exception as e:
            logging.error(f"Error handling inventory subscription: {e}")

    def _refresh_inventory(self):
        """
        Process inventory data from subscription and send to UI.
        Called from transaction updates.
        """
        try:
            # For transaction updates, trigger a refresh if we have subscription data
            if hasattr(self, "_inventory_data") and self._inventory_data:
                self._send_inventory_update()
            else:
                # Send empty data for transaction-only updates
                empty_inventory_data = {}
                self._queue_update("inventory_update", empty_inventory_data, {"transaction_update": True})

        except Exception as e:
            logging.error(f"Error processing inventory from transaction: {e}")

    def _process_inventory_data(self, inventory_rows):
        """
        Process inventory_state data to store inventory contents.
        """
        try:
            # Store inventory data keyed by owner_entity_id (building)
            if not hasattr(self, "_inventory_data"):
                self._inventory_data = {}

            for row in inventory_rows:
                try:
                    # Create InventoryState dataclass instance
                    inventory_state = InventoryState.from_dict(row)
                    if inventory_state.owner_entity_id:
                        if inventory_state.owner_entity_id not in self._inventory_data:
                            self._inventory_data[inventory_state.owner_entity_id] = []

                        # Store the inventory record as dict for compatibility
                        self._inventory_data[inventory_state.owner_entity_id].append(inventory_state.to_dict())
                except (ValueError, TypeError) as e:
                    logging.debug(f"Failed to process inventory row: {e}")
                    continue

            # for building_id, items in self._inventory_data.items():

        except Exception as e:
            logging.error(f"Error processing inventory data: {e}")

    def _process_building_data(self, building_rows):
        """
        Process building_state data to store building info.
        """
        try:
            # Store building data keyed by entity_id
            if not hasattr(self, "_building_data"):
                self._building_data = {}

            for row in building_rows:
                try:
                    # Create BuildingState dataclass instance
                    building_state = BuildingState.from_dict(row)
                    self._building_data[building_state.entity_id] = {
                        "building_description_id": building_state.building_description_id,
                        "claim_entity_id": building_state.claim_entity_id,
                        "entity_id": building_state.entity_id,
                    }
                except (ValueError, TypeError) as e:
                    logging.debug(f"Failed to process building row: {e}")
                    continue

        except Exception as e:
            logging.error(f"Error processing building data: {e}")

    def _process_building_nickname_data(self, nickname_rows):
        """
        Process building_nickname_state data to store custom building names.
        """
        try:
            # Store nickname data keyed by entity_id
            if not hasattr(self, "_building_nicknames"):
                self._building_nicknames = {}

            for row in nickname_rows:
                try:
                    # Process building nickname data directly (no dataclass available yet)
                    entity_id = row.get("entity_id")
                    nickname = row.get("nickname")
                    if entity_id and nickname:
                        self._building_nicknames[entity_id] = nickname
                except Exception as e:
                    logging.debug(f"Failed to process building nickname row: {e}")
                    continue

            # for building_id, nickname in self._building_nicknames.items():

        except Exception as e:
            logging.error(f"Error processing building nickname data: {e}")

    def _send_inventory_update(self):
        """
        Send consolidated inventory update by combining all cached data.
        """
        try:
            if not (hasattr(self, "_inventory_data") and self._inventory_data):
                return

            if not (hasattr(self, "_building_data") and self._building_data):
                return

            # Building nicknames are optional
            if not hasattr(self, "_building_nicknames"):
                self._building_nicknames = {}

            # Consolidate inventory by item
            consolidated_inventory = self._consolidate_inventory()

            # Send to UI
            self._queue_update("inventory_update", consolidated_inventory)

        except Exception as e:
            logging.error(f"Error sending inventory update: {e}")

    def _is_town_bank_building(self, building_description_id):
        """
        Check if a building is a Town Bank type that should be excluded from inventory display.

        Args:
            building_description_id: The building description ID to check

        Returns:
            bool: True if the building is a Town Bank type
        """
        if not building_description_id:
            return False

        # Town Bank building IDs from building_desc reference data
        town_bank_ids = {
            418481362,  # TownDecorTownCenterBank
            985246037,  # Town Bank
            1615467546,  # Ancient Bank
        }

        return building_description_id in town_bank_ids

    def _consolidate_inventory(self):
        """
        Consolidate inventory data by item name, combining quantities from all containers.

        Returns:
            Dictionary with items consolidated by name with container details
        """
        try:
            consolidated = {}

            # Process each building's inventory
            for building_id, inventory_records in self._inventory_data.items():
                building_info = self._building_data.get(building_id, {})
                building_description_id = building_info.get("building_description_id")

                # Skip Town Bank buildings
                if self._is_town_bank_building(building_description_id):
                    continue

                # Get container name (nickname or building type name)
                container_name = self._building_nicknames.get(building_id)
                if not container_name and building_description_id:
                    # Use ItemLookupService for building name lookup
                    container_name = self.item_lookup_service.get_building_name(building_description_id)
                if not container_name:
                    container_name = f"Unknown Building {building_id}"

                # Process each inventory record for this building using dataclass methods
                for inventory_record in inventory_records:
                    try:
                        # Create InventoryState from dict to use dataclass methods
                        inventory_state = InventoryState.from_dict(inventory_record)
                        
                        # Get items from inventory state
                        items = inventory_state.get_items({})  # Don't need to pass reference data anymore
                        
                        for item_info in items:
                            item_id = item_info.get("item_id", 0)
                            quantity = item_info.get("quantity", 0)
                            
                            # Use ItemLookupService for all item details
                            item_name = self.item_lookup_service.get_item_name(item_id)
                            item_tier = self.item_lookup_service.get_item_tier(item_id)
                            
                            # Get tag from item lookup
                            item_data = self.item_lookup_service.lookup_item_by_id(item_id)
                            item_tag = item_data.get("tag", "") if item_data else ""

                            # Add to consolidated inventory
                            if item_name not in consolidated:
                                consolidated[item_name] = {
                                    "tier": item_tier,
                                    "total_quantity": 0,
                                    "tag": item_tag,
                                    "containers": {},
                                }

                            # Add quantity to total and container
                            consolidated[item_name]["total_quantity"] += quantity
                            if container_name not in consolidated[item_name]["containers"]:
                                consolidated[item_name]["containers"][container_name] = 0
                            consolidated[item_name]["containers"][container_name] += quantity
                            
                    except Exception as e:
                        logging.debug(f"Error processing inventory record: {e}")
                        continue

            return consolidated

        except Exception as e:
            logging.error(f"Error consolidating inventory: {e}")
            return {}




    def _send_incremental_inventory_update(self, reducer_name, timestamp):
        """
        Send incremental inventory update without full refresh.
        """
        try:
            # Get fresh inventory data using existing consolidation logic
            consolidated_inventory = self._consolidate_inventory()

            if consolidated_inventory:
                # Send targeted update with incremental flag
                self._queue_update(
                    "inventory_update",
                    consolidated_inventory,
                    changes={"type": "incremental", "source": "live_transaction", "reducer": reducer_name},
                    timestamp=timestamp,
                )

                logging.info(f"[INVENTORY] Sent incremental update: {len(consolidated_inventory)} unique items - {reducer_name}")

        except Exception as e:
            logging.error(f"Error sending incremental inventory update: {e}")

    def clear_cache(self):
        """Clear cached inventory data when switching claims."""
        super().clear_cache()

        # Clear claim-specific cached data
        if hasattr(self, "_inventory_data"):
            self._inventory_data.clear()

        if hasattr(self, "_building_data"):
            self._building_data.clear()

        if hasattr(self, "_building_nicknames"):
            self._building_nicknames.clear()
