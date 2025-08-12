"""
Inventory processor for handling inventory_state table updates.
"""

import logging
from .base_processor import BaseProcessor


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

                    # Parse all deletes
                    for delete_str in deletes:
                        parsed_data = self._parse_inventory_state(delete_str)
                        if parsed_data:
                            entity_id = parsed_data.get("entity_id")
                            delete_operations[entity_id] = parsed_data

                    # Parse all inserts
                    for insert_str in inserts:
                        parsed_data = self._parse_inventory_state(insert_str)
                        if parsed_data:
                            entity_id = parsed_data.get("entity_id")
                            insert_operations[entity_id] = parsed_data

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
                owner_entity_id = row.get("owner_entity_id")
                if owner_entity_id:
                    if row.get("inventory_index") == 0:
                        if owner_entity_id not in self._inventory_data:
                            self._inventory_data[owner_entity_id] = []

                        # Store the inventory record
                        self._inventory_data[owner_entity_id].append(row)

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
                entity_id = row.get("entity_id")
                if entity_id:
                    self._building_data[entity_id] = {
                        "building_description_id": row.get("building_description_id"),
                        "claim_entity_id": row.get("claim_entity_id"),
                        "entity_id": entity_id,
                    }

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
                entity_id = row.get("entity_id")
                nickname = row.get("nickname")
                if entity_id and nickname:
                    self._building_nicknames[entity_id] = nickname

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

            # Get reference data for lookups
            item_lookups = self._get_item_lookups()
            building_desc_lookup = {b["id"]: b["name"] for b in self.reference_data.get("building_desc", [])}

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
                    container_name = building_desc_lookup.get(building_description_id, f"Building {building_id}")
                if not container_name:
                    container_name = f"Unknown Building {building_id}"

                # Process each inventory record for this building
                for inventory_record in inventory_records:
                    pockets = inventory_record.get("pockets", [])

                    # Process each pocket (inventory slot)
                    for pocket in pockets:
                        try:
                            # Parse pocket structure: [slot_info, [type, item_data]]
                            if len(pocket) >= 2 and isinstance(pocket[1], list) and len(pocket[1]) >= 2:
                                item_data = pocket[1][1]
                                if isinstance(item_data, list) and len(item_data) >= 2:
                                    item_id = item_data[0]
                                    quantity = item_data[1]

                                    # Look up item details using smart lookup
                                    item_info = self._lookup_item_by_id(item_lookups, item_id)
                                    item_name = (
                                        item_info.get("name", f"Unknown Item {item_id}")
                                        if item_info
                                        else f"Unknown Item {item_id}"
                                    )
                                    item_tier = item_info.get("tier", 0) if item_info else 0
                                    item_tag = item_info.get("tag", "") if item_info else ""

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
                            continue

            return consolidated

        except Exception as e:
            logging.error(f"Error consolidating inventory: {e}")
            return {}

    def _get_item_lookups(self):
        """
        Create combined item lookup dictionary from all reference data sources.

        Uses compound keys to prevent ID conflicts between tables.
        Example: item_id 1050001 exists in both item_desc and cargo_desc as different items.

        Returns:
            Dictionary mapping both (item_id, table_source) and item_id to item details
        """
        try:
            item_lookups = {}

            # Combine all item reference data with compound keys to prevent overwrites
            for data_source in ["resource_desc", "item_desc", "cargo_desc"]:
                items = self.reference_data.get(data_source, [])
                for item in items:
                    item_id = item.get("id")
                    if item_id is not None:
                        # Use compound key (item_id, table_source) to prevent overwrites
                        compound_key = (item_id, data_source)
                        item_lookups[compound_key] = item

                        # Also maintain simple item_id lookup for backwards compatibility
                        # Priority: item_desc > cargo_desc > resource_desc
                        if item_id not in item_lookups or data_source == "item_desc":
                            item_lookups[item_id] = item

            return item_lookups

        except Exception as e:
            logging.error(f"Error creating item lookups: {e}")
            return {}

    def _lookup_item_by_id(self, item_lookups, item_id, preferred_source=None):
        """
        Smart item lookup that handles both compound keys and simple keys.

        Args:
            item_lookups: The lookup dictionary from _get_item_lookups()
            item_id: The item ID to look up
            preferred_source: Preferred table source ("item_desc", "cargo_desc", "resource_desc")

        Returns:
            Item details dictionary or None if not found
        """
        try:
            # Try preferred source first if specified
            if preferred_source:
                compound_key = (item_id, preferred_source)
                if compound_key in item_lookups:
                    return item_lookups[compound_key]

            # Try simple item_id lookup (uses priority system)
            if item_id in item_lookups:
                return item_lookups[item_id]

            # Try all compound keys if simple lookup failed
            for source in ["item_desc", "cargo_desc", "resource_desc"]:
                compound_key = (item_id, source)
                if compound_key in item_lookups:
                    return item_lookups[compound_key]

            return None

        except Exception as e:
            logging.error(f"Error looking up item {item_id}: {e}")
            return None

    def _format_inventory_data(self, inventory_data):
        """
        Format raw inventory data using reference data for UI display.

        Args:
            inventory_data: List of inventory records from subscription

        Returns:
            Formatted inventory data for UI
        """
        try:
            if not inventory_data:
                return []

            # Use consolidated item lookups instead of separate dictionaries
            item_lookups = self._get_item_lookups()

            formatted_items = []

            for item in inventory_data:
                resource_id = item.get("resource_id", 0)
                quantity = item.get("quantity", 0)

                # Look up item details using smart lookup
                item_info = self._lookup_item_by_id(item_lookups, resource_id)

                if item_info:
                    formatted_item = {
                        "resource_id": resource_id,
                        "quantity": quantity,
                        "name": item_info.get("name", f"Unknown Item {resource_id}"),
                        "description": item_info.get("description", ""),
                        "owner_entity_id": item.get("owner_entity_id"),
                        "entity_id": item.get("entity_id"),
                    }
                    formatted_items.append(formatted_item)
                else:
                    # Item not found in reference data
                    formatted_item = {
                        "resource_id": resource_id,
                        "quantity": quantity,
                        "name": f"Unknown Item {resource_id}",
                        "description": "",
                        "owner_entity_id": item.get("owner_entity_id"),
                        "entity_id": item.get("entity_id"),
                    }
                    formatted_items.append(formatted_item)

            return formatted_items

        except Exception as e:
            logging.error(f"Error formatting inventory data: {e}")
            return []

    def _parse_inventory_state(self, data_str):
        """
        Parse inventory_state from SpacetimeDB transaction format.

        Format: [entity_id, pockets, inventory_index, cargo_index, owner_entity_id, player_owner_entity_id]
        """
        try:
            # First try JSON parsing since the data might already be parsed
            if isinstance(data_str, str):
                try:
                    import json

                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    # Fall back to ast.literal_eval for Python literal strings
                    import ast

                    data = ast.literal_eval(data_str)
            else:
                # Data is already parsed (likely from JSON)
                data = data_str

            if not isinstance(data, list) or len(data) < 6:
                logging.warning(
                    f"Invalid inventory_state data structure: {type(data)}, length: {len(data) if isinstance(data, list) else 'N/A'}"
                )
                return None

            # Extract values based on inventory_state structure
            entity_id = data[0]  # Position 0: entity_id
            pockets = data[1]  # Position 1: pockets
            inventory_index = data[2]  # Position 2: inventory_index
            cargo_index = data[3]  # Position 3: cargo_index
            owner_entity_id = data[4]  # Position 4: owner_entity_id
            player_owner_entity_id = data[5]  # Position 5: player_owner_entity_id

            parsed_data = {
                "entity_id": entity_id,
                "pockets": pockets,
                "inventory_index": inventory_index,
                "cargo_index": cargo_index,
                "owner_entity_id": owner_entity_id,
                "player_owner_entity_id": player_owner_entity_id,
            }

            return parsed_data

        except Exception as e:
            logging.warning(
                f"Error parsing inventory_state: {e} - Data type: {type(data_str)}, Data preview: {str(data_str)[:100]}"
            )
            return None

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
