"""
Compare jobs processor for handling progressive_action_state table updates.
"""

import re
import json
import time
import logging
from .base_processor import BaseProcessor


class CompareJobsProcessor(BaseProcessor):
    """
    Processes progressive_action_state table updates from SpacetimeDB.

    Handles both real-time transactions and batch subscription updates
    for compare jobs (progressive action) changes.
    """

    def get_table_names(self):
        """Return list of table names this processor handles."""
        return [
            "progressive_action_state",
            "public_progressive_action_state",
            "building_state",
            "building_nickname_state",
            "claim_member_state",
        ]

    def process_transaction(self, table_update, reducer_name, timestamp):
        """
        Handle progressive_action_state transactions - LIVE incremental updates.

        Processes real-time compare jobs progress changes without full refresh.
        """
        try:
            table_name = table_update.get("table_name", "")
            updates = table_update.get("updates", [])

            # Track if we need to send updates
            has_compare_jobs_changes = False

            for update in updates:
                inserts = update.get("inserts", [])
                deletes = update.get("deletes", [])

                # Process progressive_action_state updates (progress changes)
                if table_name == "progressive_action_state":
                    # Collect all operations first to handle delete+insert as updates
                    delete_operations = {}
                    insert_operations = {}

                    # Parse all deletes
                    for delete_str in deletes:
                        parsed_data = self._parse_progressive_action_state(delete_str)
                        if parsed_data:
                            owner_id = parsed_data.get("owner_entity_id")
                            if self._is_current_claim_member(owner_id):
                                entity_id = parsed_data.get("entity_id")
                                delete_operations[entity_id] = parsed_data

                    # Parse all inserts
                    for insert_str in inserts:
                        parsed_data = self._parse_progressive_action_state(insert_str)
                        if parsed_data:
                            owner_id = parsed_data.get("owner_entity_id")
                            if self._is_current_claim_member(owner_id):
                                entity_id = parsed_data.get("entity_id")
                                insert_operations[entity_id] = parsed_data

                    # Process operations: handle delete+insert as updates, standalone deletes as removals
                    if not hasattr(self, "_progressive_action_data"):
                        self._progressive_action_data = {}

                    # Handle updates (delete+insert for same entity)
                    for entity_id in insert_operations:
                        insert_data = insert_operations[entity_id]
                        self._progressive_action_data[entity_id] = insert_data

                        building_id = insert_data.get("building_entity_id")
                        # Add missing building to building_data if it's not already there
                        if not hasattr(self, "_building_data"):
                            self._building_data = {}

                        if building_id not in self._building_data:
                            # Create a basic building entry - we'll populate it with known data
                            self._building_data[building_id] = {
                                "entity_id": building_id,
                                "building_description_id": None,
                                "claim_entity_id": None,
                            }

                        if entity_id in delete_operations:
                            # This is an update (delete+insert)
                            old_data = delete_operations[entity_id]
                            old_progress = old_data.get("progress", 0)
                            progress = insert_data.get("progress", 0)
                            preparation = insert_data.get("preparation", False)
                            recipe_id = insert_data.get("recipe_id", 0)
                            craft_count = insert_data.get("craft_count", 1)

                            # Check if this progress update represents completion (READY status)
                            if not preparation and recipe_id:
                                try:
                                    if self.reference_data:
                                        recipe_lookup = {r["id"]: r for r in self.reference_data.get("crafting_recipe_desc", [])}
                                        recipe_info = recipe_lookup.get(recipe_id, {})
                                        if recipe_info:
                                            recipe_actions_required = recipe_info.get("actions_required", 1)
                                            total_effort = recipe_actions_required * craft_count
                                            current_effort = progress
                                            remaining_effort = max(0, total_effort - current_effort)

                                            # Check if this is newly completed
                                            old_total_effort = recipe_actions_required * old_data.get("craft_count", 1)
                                            old_remaining_effort = max(0, old_total_effort - old_progress)

                                            if remaining_effort == 0 and old_remaining_effort > 0:
                                                # Only trigger notification if this craft belongs to the current player
                                                owner_entity_id = insert_data.get("owner_entity_id")
                                                if self._is_current_player(owner_entity_id):
                                                    self._trigger_active_craft_notification(recipe_id)
                                except Exception as e:
                                    logging.error(f"Error checking active craft completion status: {e}")

                            status_display = "Preparation" if preparation else f"{progress}%"
                        else:
                            # This is a new insert
                            recipe_id = insert_data.get("recipe_id", 0)
                            progress = insert_data.get("progress", 0)

                        has_compare_jobs_changes = True

                    # Handle standalone deletes (completions)
                    for entity_id in delete_operations:
                        if entity_id not in insert_operations:
                            # This is a standalone delete (completion/claimed)
                            if entity_id in self._progressive_action_data:
                                del self._progressive_action_data[entity_id]

                            delete_data = delete_operations[entity_id]
                            recipe_id = delete_data.get("recipe_id", 0)

                            # Notification is triggered when item becomes READY, not when claimed

                            has_compare_jobs_changes = True

                # Process public_progressive_action_state updates (accept help changes)
                elif table_name == "public_progressive_action_state":
                    # Initialize _public_actions if it doesn't exist
                    if not hasattr(self, "_public_actions"):
                        self._public_actions = set()

                    # Process inserts (buildings now accepting help)
                    for insert_str in inserts:
                        try:
                            # Parse the insert data
                            if isinstance(insert_str, str):
                                insert_data = json.loads(insert_str)
                            else:
                                insert_data = insert_str

                            # Handle both array format [entity_id, building_entity_id, owner_entity_id] and object format
                            building_entity_id = None
                            if isinstance(insert_data, list) and len(insert_data) > 1:
                                # Array format: [entity_id, building_entity_id, owner_entity_id]
                                building_entity_id = insert_data[1]  # building_entity_id is at position 1
                            elif isinstance(insert_data, dict):
                                # Object format: {"building_entity_id": value}
                                building_entity_id = insert_data.get("building_entity_id")

                            if building_entity_id:
                                self._public_actions.add(building_entity_id)

                                # Ensure building exists in building_data for accept help buildings
                                if not hasattr(self, "_building_data"):
                                    self._building_data = {}

                                if building_entity_id not in self._building_data:
                                    # Create a basic building entry for accept help toggle buildings
                                    self._building_data[building_entity_id] = {
                                        "entity_id": building_entity_id,
                                        "building_description_id": None,
                                        "claim_entity_id": None,
                                    }
                        except Exception as e:
                            logging.error(f"Error processing public action insert: {e}")

                    # Process deletes (buildings no longer accepting help)
                    for delete_str in deletes:
                        try:
                            # Parse the delete data
                            if isinstance(delete_str, str):
                                delete_data = json.loads(delete_str)
                            else:
                                delete_data = delete_str

                            # Handle both array format [entity_id, building_entity_id, owner_entity_id] and object format
                            building_entity_id = None
                            if isinstance(delete_data, list) and len(delete_data) > 1:
                                # Array format: [entity_id, building_entity_id, owner_entity_id]
                                building_entity_id = delete_data[1]  # building_entity_id is at position 1
                            elif isinstance(delete_data, dict):
                                # Object format: {"building_entity_id": value}
                                building_entity_id = delete_data.get("building_entity_id")

                            if building_entity_id and building_entity_id in self._public_actions:
                                self._public_actions.remove(building_entity_id)
                        except Exception as e:
                            logging.error(f"Error processing public action delete: {e}")

                    if inserts or deletes:
                        has_compare_jobs_changes = True

                # For other table types, do full refresh if we have changes
                elif inserts or deletes:
                    self._log_transaction_debug("progressive_action", len(inserts), len(deletes), reducer_name)
                    has_compare_jobs_changes = True

            # Send incremental update for progressive_action_state and public_progressive_action_state, full refresh for others
            if has_compare_jobs_changes:
                if table_name in ["progressive_action_state", "public_progressive_action_state"]:
                    # Debug what data we have before sending incremental update
                    progressive_data_count = len(getattr(self, "_progressive_action_data", {}))
                    building_data_count = len(getattr(self, "_building_data", {}))
                    member_data_count = len(getattr(self, "_claim_members", {}))
                    public_actions_count = len(getattr(self, "_public_actions", set()))

                    self._send_incremental_compare_jobs_update(reducer_name, timestamp)
                else:
                    logging.info(f"[ACTIVE_CRAFT_DEBUG] Sending full refresh for table: {table_name}")
                    self._refresh_compare_jobs()

        except Exception as e:
            logging.error(f"Error handling compare jobs transaction: {e}")

    def process_subscription(self, table_update):
        """
        Handle progressive_action_state, building_state, building_nickname_state, and claim_member_state subscription updates.
        Cache all data and combine them for consolidated compare jobs.
        """
        try:
            table_name = table_update.get("table_name", "")
            table_rows = []

            # Extract rows from table update
            for update in table_update.get("updates", []):
                for insert_str in update.get("inserts", []):
                    try:
                        row_data = json.loads(insert_str)
                        table_rows.append(row_data)
                    except json.JSONDecodeError:
                        logging.warning(f"Failed to parse {table_name} insert: {insert_str[:100]}...")

            if not table_rows:
                return

            # Handle different table types
            if table_name == "progressive_action_state":
                self._process_progressive_action_data(table_rows)
            elif table_name == "public_progressive_action_state":
                self._process_public_progressive_action_data(table_rows)
            elif table_name == "building_state":
                self._process_building_data(table_rows)
            elif table_name == "building_nickname_state":
                self._process_building_nickname_data(table_rows)
            elif table_name == "claim_member_state":
                self._process_claim_member_data(table_rows)

            # Try to send consolidated compare jobs if we have all necessary data
            self._send_compare_jobs_update()

        except Exception as e:
            logging.error(f"Error handling compare jobs subscription: {e}")

    def _process_progressive_action_data(self, action_rows):
        """Process progressive_action_state data to store compare jobs operations."""
        try:
            # Store action data keyed by entity_id
            if not hasattr(self, "_progressive_action_data"):
                self._progressive_action_data = {}

            # DEBUG: Track target building during subscription processing
            target_building = 360287970282671066
            found_target_in_subscription = False
            all_building_ids_in_subscription = set()

            for row in action_rows:
                entity_id = row.get("entity_id")
                building_id = row.get("building_entity_id")
                owner_id = row.get("owner_entity_id")

                # DEBUG: Track all buildings in subscription data
                if building_id:
                    all_building_ids_in_subscription.add(building_id)

                # DEBUG: Check if target building is in subscription data
                if building_id == target_building:
                    found_target_in_subscription = True

                if entity_id:
                    self._progressive_action_data[entity_id] = {
                        "entity_id": entity_id,
                        "building_entity_id": building_id,
                        "function_type": row.get("function_type"),
                        "progress": row.get("progress"),
                        "recipe_id": row.get("recipe_id"),
                        "craft_count": row.get("craft_count"),
                        "last_crit_outcome": row.get("last_crit_outcome"),
                        "owner_entity_id": owner_id,
                        "lock_expiration": row.get("lock_expiration"),
                        "preparation": row.get("preparation", False),
                    }

        except Exception as e:
            logging.error(f"Error processing progressive action data: {e}")

    def _process_public_progressive_action_data(self, public_action_rows):
        """Process public_progressive_action_state data to track which buildings accept help."""
        try:
            # Initialize and clear the public actions set for fresh subscription data
            if not hasattr(self, "_public_actions"):
                self._public_actions = set()
            else:
                # Clear existing data since subscription updates contain the full current state
                self._public_actions.clear()

            all_public_building_ids = []

            # Add all buildings that currently accept help
            for row in public_action_rows:
                building_entity_id = row.get("building_entity_id")
                if building_entity_id:
                    self._public_actions.add(building_entity_id)
                    all_public_building_ids.append(building_entity_id)

        except Exception as e:
            logging.error(f"Error processing public progressive action data: {e}")

    def _process_building_data(self, building_rows):
        """Process building_state data to store building info."""
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
        """Process building_nickname_state data to store custom building names."""
        try:
            # Store nickname data keyed by entity_id
            if not hasattr(self, "_building_nicknames"):
                self._building_nicknames = {}

            for row in nickname_rows:
                entity_id = row.get("entity_id")
                nickname = row.get("nickname")
                if entity_id and nickname:
                    self._building_nicknames[entity_id] = nickname

        except Exception as e:
            logging.error(f"Error processing building nickname data: {e}")

    def _process_claim_member_data(self, member_rows):
        """Process claim_member_state data to store player names for current claim members."""
        try:
            # Store member data keyed by player_entity_id
            if not hasattr(self, "_claim_members"):
                self._claim_members = {}

            for row in member_rows:
                claim_entity_id = row.get("claim_entity_id")
                player_entity_id = row.get("player_entity_id")
                user_name = row.get("user_name")

                # Store all claim member data since the query service already filters by current claim
                if player_entity_id and user_name:
                    self._claim_members[str(player_entity_id)] = user_name

        except Exception as e:
            logging.error(f"Error processing claim member data: {e}")

    def _send_compare_jobs_update(self):
        """Send consolidated compare jobs update by combining all cached data."""
        try:
            if not (hasattr(self, "_progressive_action_data") and self._progressive_action_data):
                return

            if not (hasattr(self, "_building_data") and self._building_data):
                return

            # Building nicknames are optional
            if not hasattr(self, "_building_nicknames"):
                self._building_nicknames = {}

            # Consolidate compare jobs by item
            consolidated_jobs = self._consolidate_compare_jobs()

            # Convert dictionary to list format for UI
            jobs_list = self._format_jobs_for_ui(consolidated_jobs)

            # Send to UI
            self._queue_update("compare_jobs_update", jobs_list)

        except Exception as e:
            logging.error(f"Error sending compare jobs update: {e}")

    def _consolidate_compare_jobs(self):
        """
        Consolidate compare jobs data into 3-level hierarchy: Item -> Crafter -> Building/Progress.

        Returns:
            Dictionary with items consolidated in hierarchical structure
        """
        try:
            # First collect all raw operations
            raw_operations = []

            # Check what progressive action data we have
            progressive_data = getattr(self, "_progressive_action_data", {})

            # Log ALL progressive action building IDs to find the right one
            all_building_ids = set()
            for action_id, action_data in progressive_data.items():
                building_id = action_data.get("building_entity_id")
                if building_id:
                    all_building_ids.add(building_id)

            for action_id, action_data in progressive_data.items():
                building_id = action_data.get("building_entity_id")
                owner_id = action_data.get("owner_entity_id")
                recipe_id = action_data.get("recipe_id")

            # Get reference data for lookups
            item_lookups = self._get_item_lookups()
            recipe_lookup = {r["id"]: r for r in self.reference_data.get("crafting_recipe_desc", [])}
            building_desc_lookup = {b["id"]: b["name"] for b in self.reference_data.get("building_desc", [])}

            # Process each compare jobs operation to extract individual items
            for action_id, action_data in self._progressive_action_data.items():
                try:
                    building_id = action_data.get("building_entity_id")
                    recipe_id = action_data.get("recipe_id")
                    owner_id = action_data.get("owner_entity_id")
                    progress = action_data.get("progress", 0)
                    craft_count = action_data.get("craft_count", 1)
                    preparation = action_data.get("preparation", False)

                except Exception as e:
                    continue

                # Skip actions from players who are not current claim members
                owner_id_str = str(owner_id)
                if hasattr(self, "_claim_members") and self._claim_members:
                    if owner_id_str not in self._claim_members:
                        continue

                # Get building info
                building_info = self._building_data.get(building_id, {})
                building_description_id = building_info.get("building_description_id")

                # Get container name (nickname or building type name)
                container_name = self._building_nicknames.get(building_id)
                if not container_name and building_description_id:
                    container_name = building_desc_lookup.get(building_description_id, f"Building {building_id}")
                if not container_name:
                    container_name = f"Unknown Building {building_id}"

                # Get recipe info
                recipe_info = recipe_lookup.get(recipe_id, {})
                recipe_name = recipe_info.get("name", f"Recipe {recipe_id}")
                recipe_name = re.sub(r"\{\d+\}", "", recipe_name).strip()

                # Calculate progress percentage and status using current_effort/total_effort approach
                recipe_actions_required = recipe_info.get("actions_required", 1)
                total_effort = recipe_actions_required * craft_count  # Total effort needed
                current_effort = progress  # Current progress is the current effort

                # Validate progress values
                if current_effort < 0:
                    current_effort = 0
                if total_effort <= 0:
                    total_effort = 1
                if current_effort > total_effort:
                    current_effort = total_effort

                # Calculate remaining effort
                remaining_effort = max(0, total_effort - current_effort)

                # Display remaining effort
                status_display = f"{remaining_effort:,}" if remaining_effort > 0 else "READY"

                # Check if this building accepts help
                accepts_help = "Yes" if hasattr(self, "_public_actions") and building_id in self._public_actions else "No"

                # Get crafter name
                crafter_name = self._get_player_name(owner_id)

                try:
                    # Process crafted items from this operation
                    crafted_items = recipe_info.get("crafted_item_stacks", [])

                    if not crafted_items:
                        logging.warning(f"Recipe {recipe_id} has empty crafted_item_stacks! Using recipe name fallback.")
                        # Create fallback operation using recipe name
                        fallback_item_name = re.sub(r"\{\d+\}", "", recipe_name).strip()

                        raw_operation = {
                            "item_name": fallback_item_name,
                            "tier": 0,
                            "quantity": craft_count,
                            "tag": "",
                            "crafter": crafter_name,
                            "building_name": container_name,
                            "remaining_effort": status_display,
                            "progress_value": f"{current_effort}/{total_effort}",
                            "accept_help": accepts_help,
                            "action_id": action_id,
                            "recipe_name": recipe_name,
                            "preparation": preparation,
                            "current_progress": current_effort,
                            "total_progress": total_effort,
                        }
                        raw_operations.append(raw_operation)
                        continue

                    for item_stack in crafted_items:
                        if isinstance(item_stack, list) and len(item_stack) >= 2:
                            item_id = item_stack[0]
                            base_quantity = item_stack[1]
                            total_quantity = base_quantity * craft_count

                            # Look up item details using smart lookup with preferred source
                            preferred_source = self._determine_preferred_item_source(recipe_info)
                            item_info = self._lookup_item_by_id(item_lookups, item_id, preferred_source)
                            item_name = (
                                item_info.get("name", f"Unknown Item {item_id}") if item_info else f"Unknown Item {item_id}"
                            )
                            item_tier = item_info.get("tier", 0) if item_info else 0
                            item_tag = item_info.get("tag", "") if item_info else ""
                        else:
                            logging.warning(f"Invalid item_stack format: {item_stack} - skipping")
                            continue

                        # Create raw operation
                        raw_operation = {
                            "item_name": item_name,
                            "job_name": "Filler",
                        }
                        raw_operations.append(raw_operation)

                except Exception as e:
                    logging.error(f"[COMPARE_JOB_DEBUG] Exception processing action {action_id} job: {e}")
                    continue

            # Now build the 3-level hierarchy
            return self._build_hierarchy(raw_operations)

        except Exception as e:
            logging.error(f"Error consolidating compare jobs: {e}")
            return {}

    def _build_hierarchy(self, raw_operations):
        """
        Build 1-level hierarchy from raw operations: Job -> ...?

        Args:
            raw_operations: List of individual compare jobs operations

        Returns:
            Dictionary with hierarchical structure for UI
        """
        logging.info(f"raw_operation: {raw_operations[0]}")
        try:
            hierarchy = {}

            # Group by item name first (Level 1)
            for op in raw_operations:
                item_name = op["item_name"]

                if item_name not in hierarchy:
                    hierarchy[item_name] = {
                        "job_name": op["job_name"]
                    }

            # Convert to UI format
            logging.info(f"hierarchy: {hierarchy}")
            return self._format_hierarchy_for_ui(hierarchy)

        except Exception as e:
            logging.error(f"Error building hierarchy: {e}")
            return {}

    def _summarize_accept_help(self, accept_help_values):
        """
        Summarize accept help values into a display string.

        Args:
            accept_help_values: Set of accept help values ("Yes", "No")

        Returns:
            str: Summary like "Yes", "No", "Mixed"
        """
        unique_values = list(accept_help_values)
        if len(unique_values) == 1:
            return unique_values[0]
        elif len(unique_values) > 1:
            return "Mixed"
        else:
            return "Unknown"

    def _format_hierarchy_for_ui(self, hierarchy):
        """
        Format hierarchical data for UI consumption - simplified for flat display.

        Args:
            hierarchy: The 1-level hierarchy structure

        Returns:
            Dictionary formatted for UI display
        """
        try:
            formatted = {}

            for item_name, item_data in hierarchy.items():
                # Create a simple entry that contains all the individual operations
                formatted[item_name] = {
                    "item": item_name,
                    "job": item_data["job_name"]
                }

            return formatted

        except Exception as e:
            logging.error(f"Error formatting hierarchy for UI: {e}")
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

    def _determine_preferred_item_source(self, recipe_info):
        """
        Determine the preferred item source based on recipe context.

        Args:
            recipe_info: Recipe information dictionary

        Returns:
            str: Preferred source ("item_desc", "cargo_desc", "resource_desc") or None
        """
        try:
            recipe_name = recipe_info.get("name", "").lower()

            # Heuristics to determine if this is likely a cargo item
            cargo_indicators = ["pack", "package", "bundle", "crate", "supplies", "materials", "goods", "cargo", "shipment"]

            for indicator in cargo_indicators:
                if indicator in recipe_name:
                    return "cargo_desc"

            # Default to item_desc for most crafting
            return "item_desc"

        except Exception as e:
            logging.error(f"Error determining preferred source: {e}")
            return None

    def _format_jobs_for_ui(self, consolidated_jobs):
        """
        Convert consolidated crafting dictionary to list format expected by UI.

        Args:
            consolidated_jobs: Dictionary with jobs consolidated by name

        Returns:
            List of item groups with operations for expandable UI
        """
        try:
            formatted_list = []

            for job_name, job_data in consolidated_jobs.items():
                # Keep all the properly formatted data from _format_hierarchy_for_ui
                formatted_list.append(job_data)

            # Sort by item name for consistent display
            formatted_list.sort(key=lambda x: x.get("item", "").lower())

            return formatted_list

        except Exception as e:
            logging.error(f"Error formatting jobs for UI: {e}")
            return []

    def _get_player_name(self, player_entity_id):
        """
        Get player name from entity ID using cached claim member data.

        Args:
            player_entity_id: The player's entity ID

        Returns:
            str: Player name or fallback
        """
        try:
            # Convert to string for consistent lookup
            player_id_str = str(player_entity_id)

            # Try cached claim member data (primary method)
            if hasattr(self, "_claim_members") and player_id_str in self._claim_members:
                player_name = self._claim_members[player_id_str]
                return player_name

            # Try claim members service as fallback
            claim_members_service = self.services.get("claim_members_service")
            if claim_members_service:
                player_name = claim_members_service.get_player_name(player_entity_id)
                if player_name and not player_name.startswith("Player "):
                    return player_name

            # Fallback to entity ID format
            return f"Player {player_entity_id}"

        except Exception as e:
            logging.warning(f"Error getting player name for {player_entity_id}: {e}")
            return f"Player {player_entity_id}"

    def _refresh_compare_jobs(self):
        """
        Legacy method for compatibility with transaction processing.
        """
        try:
            self._send_compare_jobs_update()
        except Exception as e:
            logging.error(f"Error refreshing compare_jobs: {e}")

    def _parse_progressive_action_state(self, data_str):
        """
        Parse progressive_action_state from SpacetimeDB transaction format.

        Format: [entity_id, building_entity_id, function_type, progress, recipe_id, craft_count, last_crit_outcome, owner_entity_id, [timestamp], preparation]
        Example: [360287970279931013,360287970244316930,25,432,405009,50,1,504403158299523086,[1754348000362779],false]
        """
        try:
            # First try JSON parsing since the data might already be parsed
            if isinstance(data_str, str):
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    # Fall back to ast.literal_eval for Python literal strings
                    import ast

                    data = ast.literal_eval(data_str)
            else:
                # Data is already parsed (likely from JSON)
                data = data_str

            if not isinstance(data, list) or len(data) < 10:
                return None

            # Extract values based on progressive_action_state structure
            entity_id = data[0]  # Position 0: entity_id
            building_entity_id = data[1]  # Position 1: building_entity_id
            function_type = data[2]  # Position 2: function_type
            progress = data[3]  # Position 3: progress
            recipe_id = data[4]  # Position 4: recipe_id
            craft_count = data[5]  # Position 5: craft_count
            last_crit_outcome = data[6]  # Position 6: last_crit_outcome
            owner_entity_id = data[7]  # Position 7: owner_entity_id
            lock_expiration = data[8]  # Position 8: lock_expiration (timestamp array)
            preparation = data[9]  # Position 9: preparation

            parsed_data = {
                "entity_id": entity_id,
                "building_entity_id": building_entity_id,
                "function_type": function_type,
                "progress": progress,
                "recipe_id": recipe_id,
                "craft_count": craft_count,
                "last_crit_outcome": last_crit_outcome,
                "owner_entity_id": owner_entity_id,
                "lock_expiration": lock_expiration,
                "preparation": preparation,
            }

            return parsed_data

        except Exception as e:
            return None

    def _is_current_claim_member(self, owner_entity_id):
        """Check if the owner is a member of the current claim."""
        if not hasattr(self, "_claim_members") or not self._claim_members:
            return True  # For display purposes, if no member data available, show everything

        owner_id_str = str(owner_entity_id)
        return owner_id_str in self._claim_members

    def _is_current_player(self, owner_entity_id):
        """Check if the owner entity ID belongs to the current player."""
        try:
            # Get current player name from data service
            data_service = self.services.get("data_service")
            if not data_service or not hasattr(data_service, "client") or not data_service.client:
                return False

            current_player_name = getattr(data_service.client, "player_name", None)
            if not current_player_name:
                return False

            # Get owner name from entity ID using claim members data
            if not hasattr(self, "_claim_members") or not self._claim_members:
                return False

            owner_id_str = str(owner_entity_id)
            owner_name = self._claim_members.get(owner_id_str)
            if not owner_name:
                return False

            # Check if owner is the current player
            return owner_name == current_player_name

        except Exception as e:
            logging.error(f"Error checking if owner {owner_entity_id} is current player: {e}")
            return False

    def _send_incremental_compare_jobs_update(self, reducer_name, timestamp):
        """
        Send incremental compare jobs update without full refresh.
        """
        try:
            # Get fresh compare jobs data using existing consolidation logic
            consolidated_jobs = self._consolidate_compare_jobs()

            # Convert dictionary to list format for UI (same as regular update)
            jobs_list = self._format_jobs_for_ui(consolidated_jobs)

            if jobs_list:
                # Send targeted update with incremental flag
                self._queue_update(
                    "compare_jobs_update",
                    jobs_list,
                    changes={"type": "incremental", "source": "live_transaction", "reducer": reducer_name},
                    timestamp=timestamp,
                )

        except Exception as e:
            logging.error(f"Error sending incremental compare jobs update: {e}")

    def clear_cache(self):
        """Clear cached compare jobs data when switching claims."""
        super().clear_cache()

        # Clear claim-specific cached data
        if hasattr(self, "_progressive_action_data"):
            self._progressive_action_data.clear()

        if hasattr(self, "_building_data"):
            self._building_data.clear()

        if hasattr(self, "_building_nicknames"):
            self._building_nicknames.clear()

        if hasattr(self, "_claim_members"):
            self._claim_members.clear()

        if hasattr(self, "_public_actions"):
            self._public_actions.clear()

    def _trigger_active_craft_notification(self, recipe_id: int):
        """Trigger an active craft completion notification."""
        try:
            item_name = self._get_item_name_from_recipe(recipe_id)

            if hasattr(self, "services") and self.services:
                data_service = self.services.get("data_service")
                if data_service and hasattr(data_service, "notification_service"):
                    data_service.notification_service.show_active_craft_notification(item_name)

        except Exception as e:
            logging.error(f"Error triggering active craft notification: {e}")

    def _get_item_name_from_recipe(self, recipe_id: int) -> str:
        """Get the actual item name from a recipe ID by looking up crafted_item_stacks."""
        try:
            if not self.reference_data or not recipe_id:
                return f"Recipe {recipe_id}"

            recipes = self.reference_data.get("crafting_recipe_desc", [])

            for recipe in recipes:
                if recipe.get("id") == recipe_id:
                    recipe_name = recipe.get("name", "Unknown Recipe")
                    crafted_items = recipe.get("crafted_item_stacks", [])

                    if crafted_items and len(crafted_items) > 0:
                        first_item = crafted_items[0]

                        if isinstance(first_item, list) and len(first_item) >= 2:
                            item_id = first_item[0]
                            item_lookups = self._get_item_lookups()
                            item_info = self._lookup_item_by_id(item_lookups, item_id)

                            if item_info:
                                return item_info.get("name", f"Item {item_id}")
                    else:
                        # Fallback to cleaned recipe name
                        return re.sub(r"\{\d+\}", "", recipe_name).strip()
                    break

            return f"Recipe {recipe_id}"

        except Exception as e:
            logging.error(f"Error resolving item name for recipe {recipe_id}: {e}")
            return f"Recipe {recipe_id}"
