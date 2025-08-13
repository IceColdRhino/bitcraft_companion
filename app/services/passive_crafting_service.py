from typing import Dict, List, Any
import logging
from typing import List, Dict
import re
import time
import ast
import threading

from ..client.bitcraft_client import BitCraft
from ..models.claim import Claim


class PassiveCraftingService:
    """Service to handle passive crafting status and data processing with real-time timers."""

    def __init__(self, bitcraft_client: BitCraft, claim_instance: Claim, reference_data: dict):
        """Initializes the service with its dependencies."""
        self.client = bitcraft_client
        self.claim = claim_instance

        # --- Injected Reference Data ---
        self.crafting_recipes = {r["id"]: r for r in reference_data.get("crafting_recipe_desc", [])}
        self.building_desc = {b["id"]: b for b in reference_data.get("building_desc", [])}

        # Create combined item lookup from all item sources
        self.item_descriptions = {}
        for data_list in [
            reference_data.get("resource_desc", []),
            reference_data.get("item_desc", []),
            reference_data.get("cargo_desc", []),
        ]:
            if data_list:
                for item in data_list:
                    if "id" in item:
                        self.item_descriptions[item["id"]] = item

        # Store current crafting data for GUI
        self.current_crafting_data = []

        # Real-time timer management
        self.timer_thread = None
        self.timer_stop_event = threading.Event()
        self.ui_update_callback = None
        self.last_timer_update = 0

        # Store raw crafting operations for timer calculations
        self.raw_crafting_operations = []

    def start_real_time_timer(self, ui_update_callback):
        """
        Start the real-time countdown timer that updates the UI every second.

        Args:
            ui_update_callback: Function to call when timers need UI update
        """

        if self.timer_thread and self.timer_thread.is_alive():
            logging.warning("Timer thread already running")
            return

        self.ui_update_callback = ui_update_callback
        self.timer_stop_event.clear()

        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.timer_thread.start()
        logging.info("Started real-time crafting countdown timer")

    def stop_real_time_timer(self):
        """Stop the real-time countdown timer with improved cleanup."""
        logging.info("Stopping real-time crafting countdown timer...")

        try:
            if self.timer_thread:
                # Set stop event
                self.timer_stop_event.set()

                # Wait for thread with timeout
                if self.timer_thread.is_alive():
                    self.timer_thread.join(timeout=1.0)  # 1 second timeout

                    if self.timer_thread.is_alive():
                        logging.warning("Timer thread did not finish within timeout")
                    else:
                        logging.info("Timer thread finished cleanly")

                self.timer_thread = None

        except Exception as e:
            logging.error(f"Error stopping timer thread: {e}")
        finally:
            logging.info("Real-time timer shutdown complete")

    def _timer_loop(self):
        """Background thread that updates timers every second."""
        timer_count = 0
        while not self.timer_stop_event.is_set():
            try:
                current_time = time.time()

                # Only update every second to avoid excessive UI updates
                if current_time - self.last_timer_update >= 1.0:
                    timer_count += 1
                    self._update_all_timers()
                    self.last_timer_update = current_time

                # Sleep for a short time to avoid busy waiting
                time.sleep(0.1)

            except Exception as e:
                logging.error(f"Error in timer loop: {e}")
                time.sleep(1.0)  # Longer sleep on error

    def _update_all_timers(self):
        """Update all crafting timers and notify UI if needed."""
        try:
            has_timer_changes = False
            updated_operations = []

            for operation in self.raw_crafting_operations:
                # Calculate current time remaining
                new_time_remaining = self._calculate_current_time_remaining(operation)
                old_time_remaining = operation.get("time_remaining", "")

                recipe_id = operation.get("recipe_id", "unknown")

                # Check if status changed (e.g., from "5m 30s" to "READY")
                if new_time_remaining != old_time_remaining:
                    operation["time_remaining"] = new_time_remaining
                    has_timer_changes = True

                    # Log completions
                    if new_time_remaining == "READY" and old_time_remaining != "READY":
                        logging.warning(f"Timer detected completion: Recipe {recipe_id}")

                updated_operations.append(operation)

            # Update the stored operations
            self.raw_crafting_operations = updated_operations

            # If any timers changed, update the UI
            if has_timer_changes and self.ui_update_callback:
                # Re-group the data with updated timers
                grouped_data = self._group_crafting_data_by_item_name_enhanced(self.raw_crafting_operations)
                self.current_crafting_data = grouped_data

                # Notify UI of timer updates
                self.ui_update_callback({"type": "timer_update", "data": grouped_data, "timestamp": time.time()})

        except Exception as e:
            logging.error(f"Error updating timers: {e}")

    def _calculate_current_time_remaining(self, operation: Dict) -> str:
        """
        Calculate the current time remaining for a crafting operation.
        This is called by the timer thread every second.
        """
        try:
            # First check database status - this is still the source of truth
            raw_craft_state = operation.get("raw_craft_state", {})
            status = raw_craft_state.get("status")
            if status and isinstance(status, list) and len(status) > 0:
                if status[0] == 2:  # Completed
                    return "READY"
                elif status[0] != 1:  # Not in progress
                    return "Unknown"

            # For in-progress items, calculate real-time countdown
            recipe_id = raw_craft_state.get("recipe_id")
            if not recipe_id or recipe_id not in self.crafting_recipes:
                return "In Progress"

            recipe = self.crafting_recipes[recipe_id]
            duration_seconds = recipe.get("time_requirement", 0)

            # Get timestamp - handle multiple formats
            timestamp_data = raw_craft_state.get("timestamp")
            timestamp_micros = None

            if timestamp_data:
                # Handle nested format from subscription data
                timestamp_micros = timestamp_data.get("__timestamp_micros_since_unix_epoch__")

            if not timestamp_micros:
                # Handle direct format from processor data
                timestamp_micros = raw_craft_state.get("timestamp_micros")
                if isinstance(timestamp_micros, list) and len(timestamp_micros) > 0:
                    timestamp_micros = timestamp_micros[0]

            # Check timestamp on operation itself (from processor incremental updates)
            if not timestamp_micros:
                timestamp_micros = operation.get("timestamp_micros")
                if isinstance(timestamp_micros, list) and len(timestamp_micros) > 0:
                    timestamp_micros = timestamp_micros[0]

            if not timestamp_micros:
                return "In Progress"

            # Calculate remaining time with current timestamp
            start_time = timestamp_micros / 1_000_000
            current_time = time.time()
            elapsed_time = current_time - start_time
            remaining_time = duration_seconds - elapsed_time

            if remaining_time <= 0:
                return "READY"

            return self._format_duration_for_display(remaining_time)

        except Exception as e:
            logging.error(f"Error calculating timer: {e}")
            return "Error"

    def get_crafting_data_from_processor(self, processor_operations):
        """
        Get formatted crafting data from processor operations.
        This method allows the processor to pass data directly to the service
        instead of the service querying the database.

        Args:
            processor_operations: List of crafting operations from the processor

        Returns:
            List of formatted crafting data for UI
        """
        try:
            # Store the processor operations for timer updates
            self.raw_crafting_operations = processor_operations

            # Format and group the data for UI
            grouped_data = self._group_crafting_data_by_item_name_enhanced(processor_operations)
            self.current_crafting_data = grouped_data

            return grouped_data

        except Exception as e:
            logging.error(f"Error processing crafting data from processor: {e}")
            return []


    def get_all_crafting_data_enhanced(self) -> List[Dict]:
        """
        Enhanced version that stores raw operations for timer updates and uses better grouping.
        Fetches complete crafting state for all buildings in the claim.
        Returns data formatted for GUI display - ITEM-FOCUSED with expandable rows.
        Only includes crafting by claim members.
        """
        if not self.claim.claim_id:
            logging.error("Cannot fetch crafting data without a claim_id.")
            return []

        try:
            logging.info("Fetching all passive crafting data for claim with enhanced timers")

            # Get claim members FIRST to filter non-claim members
            claim_members_query = f"SELECT * FROM claim_member_state WHERE claim_entity_id = '{self.claim.claim_id}';"
            claim_members = self.client.query(claim_members_query)

            if not claim_members:
                logging.warning("No claim members found")
                return []

            # Build lookup for claim members only
            claim_member_ids = set()
            user_lookup = {}
            for member in claim_members:
                player_id = member.get("player_entity_id")
                user_name = member.get("user_name")
                if player_id:
                    claim_member_ids.add(player_id)
                    if user_name:
                        user_lookup[player_id] = user_name
                    else:
                        user_lookup[player_id] = f"User {player_id}"

            logging.info(f"Found {len(claim_member_ids)} claim members")

            # Get all buildings in the claim
            buildings_query = f"SELECT * FROM building_state WHERE claim_entity_id = '{self.claim.claim_id}';"
            buildings = self.client.query(buildings_query)

            if not buildings:
                logging.warning("No buildings found for crafting data fetch")
                return []

            # Get building nicknames for display
            nicknames_query = "SELECT * FROM building_nickname_state;"
            building_nicknames = self.client.query(nicknames_query)
            nickname_lookup = {n["entity_id"]: n["nickname"] for n in building_nicknames} if building_nicknames else {}

            # Filter to processing-capable buildings
            processing_buildings = []
            for building in buildings:
                building_id = building.get("entity_id")
                building_desc_id = building.get("building_description_id")

                if not building_id or not building_desc_id:
                    continue

                # Get building display name
                building_name = self.building_desc.get(building_desc_id, {}).get("name", "Unknown Building")

                # Check if this building supports crafting
                if self._building_supports_crafting(building_desc_id, building_name):
                    building_nickname = nickname_lookup.get(building_id)
                    display_name = building_nickname if building_nickname else building_name

                    processing_buildings.append(
                        {
                            "entity_id": building_id,
                            "building_description_id": building_desc_id,
                            "building_name": building_name,
                            "display_name": display_name,
                            "nickname": building_nickname,
                        }
                    )

            # Get passive craft states for all processing buildings
            building_ids = [b["entity_id"] for b in processing_buildings]
            if not building_ids:
                logging.info("No processing buildings found")
                return []

            crafting_operations = []

            # Get all passive crafting states
            for building_id in building_ids:
                crafting_query = f"SELECT * FROM passive_craft_state WHERE building_entity_id = '{building_id}';"
                crafting_states = self.client.query(crafting_query)

                if not crafting_states:
                    continue

                # Find building info
                building_info = next((b for b in processing_buildings if b["entity_id"] == building_id), None)
                if not building_info:
                    continue

                # Process each crafting operation
                for craft_state in crafting_states:
                    owner_entity_id = craft_state.get("owner_entity_id")

                    # FILTER OUT NON-CLAIM MEMBERS
                    if owner_entity_id not in claim_member_ids:
                        continue

                    crafting_entry = self._format_crafting_entry_item_focused_enhanced(craft_state, building_info, user_lookup)
                    if crafting_entry:
                        # Store the raw craft_state for timer calculations
                        crafting_entry["raw_craft_state"] = craft_state
                        crafting_operations.append(crafting_entry)

            # Store raw operations for timer updates
            self.raw_crafting_operations = crafting_operations

            # Group with enhanced logic that properly combines identical items
            grouped_data = self._group_crafting_data_by_item_name_enhanced(crafting_operations)

            self.current_crafting_data = grouped_data
            logging.info(f"Fetched crafting data for {len(grouped_data)} item groups with real-time timers")
            return grouped_data

        except Exception as e:
            logging.error(f"Error fetching enhanced crafting data: {e}")
            return []

    def _group_crafting_data_by_item_name_enhanced(self, operations: List[Dict]) -> List[Dict]:
        """
        Hierarchical grouping with mandatory two-level expansion:
        1. Group all items by item+tier+recipe
        2. First level expansion: by crafter (if multiple crafters)
        3. Second level expansion: by building (if multiple buildings within crafter)

        This creates a cleaner view showing completed/total quantities like "28/36".
        """
        if not operations:
            return []

        # Step 1: Group all operations by item+tier+recipe only
        item_groups = {}

        for operation in operations:
            item_name = operation.get("item_name", "Unknown Item")
            tier = operation.get("tier", 0)
            recipe = operation.get("recipe", "Unknown Recipe")

            # Group key for the item type
            item_key = f"{item_name}|{tier}|{recipe}"

            if item_key not in item_groups:
                item_groups[item_key] = {
                    "item_name": item_name,
                    "tier": tier,
                    "recipe": recipe,
                    "operations": [],
                    "all_crafters": set(),
                    "all_buildings": set(),
                }

            group = item_groups[item_key]
            group["operations"].append(operation)
            group["all_crafters"].add(operation.get("crafter", "Unknown"))
            group["all_buildings"].add(operation.get("building", "Unknown"))

        # Step 2: Process each item group to create hierarchical structure
        grouped_data = []

        for item_key, item_group in item_groups.items():
            operations = item_group["operations"]
            all_crafters = list(item_group["all_crafters"])
            all_buildings = list(item_group["all_buildings"])

            # Calculate totals and completion status
            total_quantity = sum(op.get("quantity", 0) for op in operations)
            completed_quantity = sum(op.get("quantity", 0) for op in operations if op.get("time_remaining") == "READY")

            # Find the longest remaining time for incomplete operations
            incomplete_operations = [op for op in operations if op.get("time_remaining") != "READY"]
            if incomplete_operations:
                # For now, use the first incomplete operation's time - could be enhanced to find max
                max_time_remaining = max(
                    incomplete_operations, key=lambda x: self._time_remaining_to_seconds(x.get("time_remaining", ""))
                )["time_remaining"]
            else:
                max_time_remaining = "READY"

            # Create top-level entry
            top_level_entry = {
                "item": item_group["item_name"],
                "tier": item_group["tier"],
                "quantity": (
                    f"{completed_quantity}/{total_quantity}" if completed_quantity < total_quantity else str(total_quantity)
                ),
                "recipe": item_group["recipe"],
                "time_remaining": max_time_remaining,
                "crafter": f"{len(all_crafters)} crafters" if len(all_crafters) > 1 else all_crafters[0],
                "building": f"{len(all_buildings)} buildings" if len(all_buildings) > 1 else all_buildings[0],
                "operations": [],
                "is_expandable": True,
                "expansion_level": 0,
            }

            # Step 3: Create first level expansion by crafter (if multiple crafters)
            if len(all_crafters) > 1:
                # Group by crafter
                crafter_groups = {}
                for operation in operations:
                    crafter = operation.get("crafter", "Unknown")
                    if crafter not in crafter_groups:
                        crafter_groups[crafter] = []
                    crafter_groups[crafter].append(operation)

                # Create crafter-level entries
                for crafter, crafter_ops in crafter_groups.items():
                    crafter_total = sum(op.get("quantity", 0) for op in crafter_ops)
                    crafter_completed = sum(op.get("quantity", 0) for op in crafter_ops if op.get("time_remaining") == "READY")
                    crafter_buildings = set(op.get("building", "Unknown") for op in crafter_ops)

                    # Find max time for this crafter
                    crafter_incomplete = [op for op in crafter_ops if op.get("time_remaining") != "READY"]
                    if crafter_incomplete:
                        crafter_max_time = max(
                            crafter_incomplete, key=lambda x: self._time_remaining_to_seconds(x.get("time_remaining", ""))
                        )["time_remaining"]
                    else:
                        crafter_max_time = "READY"

                    crafter_entry = {
                        "item": item_group["item_name"],
                        "tier": item_group["tier"],
                        "quantity": (
                            f"{crafter_completed}/{crafter_total}" if crafter_completed < crafter_total else str(crafter_total)
                        ),
                        "recipe": item_group["recipe"],
                        "time_remaining": crafter_max_time,
                        "crafter": crafter,
                        "building": (
                            f"{len(crafter_buildings)} buildings" if len(crafter_buildings) > 1 else list(crafter_buildings)[0]
                        ),
                        "operations": [],
                        "is_child": True,
                        "is_expandable": len(crafter_buildings) > 1,
                        "expansion_level": 1,
                    }

                    # Step 4: Create second level expansion by building (if multiple buildings for this crafter)
                    if len(crafter_buildings) > 1:
                        building_groups = {}
                        for operation in crafter_ops:
                            building = operation.get("building", "Unknown")
                            if building not in building_groups:
                                building_groups[building] = []
                            building_groups[building].append(operation)

                        # Create building-level entries
                        for building, building_ops in building_groups.items():
                            building_total = sum(op.get("quantity", 0) for op in building_ops)
                            building_completed = sum(
                                op.get("quantity", 0) for op in building_ops if op.get("time_remaining") == "READY"
                            )

                            # Find max time for this building
                            building_incomplete = [op for op in building_ops if op.get("time_remaining") != "READY"]
                            if building_incomplete:
                                building_max_time = max(
                                    building_incomplete,
                                    key=lambda x: self._time_remaining_to_seconds(x.get("time_remaining", "")),
                                )["time_remaining"]
                            else:
                                building_max_time = "READY"

                            building_entry = {
                                "item": item_group["item_name"],
                                "tier": item_group["tier"],
                                "quantity": (
                                    f"{building_completed}/{building_total}"
                                    if building_completed < building_total
                                    else str(building_total)
                                ),
                                "recipe": item_group["recipe"],
                                "time_remaining": building_max_time,
                                "crafter": crafter,
                                "building": building,
                                "operations": building_ops,
                                "is_child": True,
                                "is_expandable": False,
                                "expansion_level": 2,
                            }
                            crafter_entry["operations"].append(building_entry)
                    else:
                        # Single building for this crafter - no second level needed
                        crafter_entry["operations"] = crafter_ops

                    top_level_entry["operations"].append(crafter_entry)

            else:
                # Single crafter - check if we need building expansion
                single_crafter = all_crafters[0]
                if len(all_buildings) > 1:
                    # Group by building for the single crafter
                    building_groups = {}
                    for operation in operations:
                        building = operation.get("building", "Unknown")
                        if building not in building_groups:
                            building_groups[building] = []
                        building_groups[building].append(operation)

                    # Create building-level entries directly (skip crafter level)
                    for building, building_ops in building_groups.items():
                        building_total = sum(op.get("quantity", 0) for op in building_ops)
                        building_completed = sum(
                            op.get("quantity", 0) for op in building_ops if op.get("time_remaining") == "READY"
                        )

                        # Find max time for this building
                        building_incomplete = [op for op in building_ops if op.get("time_remaining") != "READY"]
                        if building_incomplete:
                            building_max_time = max(
                                building_incomplete, key=lambda x: self._time_remaining_to_seconds(x.get("time_remaining", ""))
                            )["time_remaining"]
                        else:
                            building_max_time = "READY"

                        building_entry = {
                            "item": item_group["item_name"],
                            "tier": item_group["tier"],
                            "quantity": (
                                f"{building_completed}/{building_total}"
                                if building_completed < building_total
                                else str(building_total)
                            ),
                            "recipe": item_group["recipe"],
                            "time_remaining": building_max_time,
                            "crafter": single_crafter,
                            "building": building,
                            "operations": building_ops,
                            "is_child": True,
                            "is_expandable": False,
                            "expansion_level": 1,
                        }
                        top_level_entry["operations"].append(building_entry)
                else:
                    # Single crafter, single building - no expansion needed
                    top_level_entry["operations"] = operations
                    top_level_entry["is_expandable"] = False

            grouped_data.append(top_level_entry)

        # Debug logging to see the structure
        for i, group in enumerate(grouped_data):
            crafter_info = group.get("crafter", "")
            building_info = group.get("building", "")
            expansion_info = f" (expandable: {group.get('is_expandable', False)})"

            operations = group.get("operations", [])
            if operations:
                for j, op in enumerate(operations):
                    op_crafter = op.get("crafter", "")
                    op_building = op.get("building", op.get("building", ""))
                    op_expandable = op.get("is_expandable", False)
                    op_level = op.get("expansion_level", 1)

                    # Check for grandchildren
                    grandchildren = op.get("operations", [])
                    if grandchildren:
                        for k, gc in enumerate(grandchildren):
                            gc_building = gc.get("building", gc.get("building", ""))
                            gc_level = gc.get("expansion_level", 2)

        return grouped_data

    def _time_remaining_to_seconds(self, time_str: str) -> int:
        """
        Convert time remaining string to seconds for comparison.
        Used to find the maximum time remaining in a group.
        """
        if not time_str or time_str == "READY":
            return 0
        if time_str in ["Unknown", "Error", "In Progress"]:
            return 999999  # Put unknown times at the end

        total_seconds = 0
        try:
            # Remove ~ prefix if present
            time_str = time_str.replace("~", "")

            # Parse formats like "2h 30m 15s", "30m 15s", "15s"
            import re

            hours_match = re.search(r"(\d+)h", time_str)
            minutes_match = re.search(r"(\d+)m", time_str)
            seconds_match = re.search(r"(\d+)s", time_str)

            if hours_match:
                total_seconds += int(hours_match.group(1)) * 3600
            if minutes_match:
                total_seconds += int(minutes_match.group(1)) * 60
            if seconds_match:
                total_seconds += int(seconds_match.group(1))

        except Exception as e:
            logging.warning(f"Error parsing time string '{time_str}': {e}")
            return 999999

        return total_seconds

    def _operations_are_different(self, operations: List[Dict]) -> bool:
        """
        Simplified check: operations are different if they have different crafters OR buildings.
        """
        if len(operations) <= 1:
            return False

        crafters = set(op.get("crafter", "") for op in operations)
        buildings = set(op.get("building", "") for op in operations)

        # Different if more than one unique crafter OR more than one unique building
        return len(crafters) > 1 or len(buildings) > 1

    def _format_crafting_entry_item_focused_enhanced(self, craft_state: Dict, building_info: Dict, user_lookup: Dict) -> Dict:
        """
        Enhanced version that uses database status instead of calculated time remaining.
        Formats a single crafting state entry for item-focused GUI display.
        """
        try:
            recipe_id = craft_state.get("recipe_id")
            owner_entity_id = craft_state.get("owner_entity_id")

            # Get recipe information
            recipe_info = self.crafting_recipes.get(recipe_id, {})
            recipe_name = recipe_info.get("name", f"Unknown Recipe {recipe_id}")
            # Clean up recipe name by removing {0} placeholder
            recipe_name = re.sub(r"\{\d+\}", "", recipe_name).strip()

            # Extract the actual item being crafted from recipe data
            crafted_item_name = "Unknown Item"
            crafted_item_tier = 0
            recipe_quantity = 1

            # Parse the crafted_item_stacks to get actual item info
            crafted_item_stacks = recipe_info.get("crafted_item_stacks", [])

            try:
                # Handle both string and list formats
                if isinstance(crafted_item_stacks, str):
                    produced_items = ast.literal_eval(crafted_item_stacks)
                elif isinstance(crafted_item_stacks, list):
                    produced_items = crafted_item_stacks
                else:
                    produced_items = []

                if produced_items and len(produced_items) > 0:
                    first_item = produced_items[0]

                    if isinstance(first_item, (list, tuple)) and len(first_item) >= 2:
                        item_id = first_item[0]
                        recipe_quantity = first_item[1]

                        if item_id in self.item_descriptions:
                            item_info = self.item_descriptions.get(item_id, {})
                            crafted_item_name = item_info.get("name", f"Item {item_id}")
                            crafted_item_tier = item_info.get("tier", 0)

            except Exception as e:
                logging.warning(f"Error processing crafted_item_stacks: {e}")

            # Get crafter name
            crafter_name = user_lookup.get(owner_entity_id, f"User {owner_entity_id}")

            # USE NEW DATABASE STATUS READING (no timer calculations!)
            status_display = self.get_crafting_status_from_db(craft_state)

            # Create building display name (building + crafter info)
            building_display = building_info["display_name"]
            if building_info["nickname"]:
                building_display = f"{building_info['nickname']}"
            else:
                building_display = building_info["building_name"]

            return {
                "item_name": crafted_item_name,
                "tier": crafted_item_tier,
                "quantity": recipe_quantity,
                "recipe": recipe_name,
                "time_remaining": status_display,  # This is now status, not calculated time!
                "crafter": crafter_name,
                "building": building_display,
                "building_full": building_info["building_name"],  # For filtering
                "is_empty": False,
            }

        except Exception as e:
            logging.error(f"Error formatting crafting entry: {e}")
            return None

    def _building_supports_crafting(self, building_desc_id: int, building_name: str) -> bool:
        """Checks if a building type supports passive crafting."""
        if not building_desc_id or building_desc_id not in self.building_desc:
            return False

        building_name_lower = building_name.lower()

        # Exclude storage and cargo buildings
        exclude_keywords = ["storage", "cargo stockpile", "stockpile", "bank", "chest"]
        if any(exclude in building_name_lower for exclude in exclude_keywords):
            return False

        # Include crafting-capable buildings
        crafting_keywords = [
            "station",
            "loom",
            "farming field",
            "kiln",
            "smelter",
            "oven",
            "workbench",
            "tanning tub",
            "mill",
            "brewery",
            "forge",
        ]

        return any(keyword in building_name_lower for keyword in crafting_keywords)

    def get_crafting_status_from_db(self, crafting_entry: Dict) -> str:
        """
        Read the actual crafting status directly from the database instead of calculating it.
        SpacetimeDB subscriptions will tell us when this changes - no timers needed!

        Args:
            crafting_entry: Raw crafting entry from the database

        Returns:
            str: Current status - "READY", "In Progress", "Unknown", etc.
        """
        try:
            # Check the status field first - this is the source of truth
            status = crafting_entry.get("status")
            if status and isinstance(status, list) and len(status) > 0:
                status_code = status[0]

                if status_code == 2:  # Status 2 means completed/ready
                    return "READY"
                elif status_code == 1:  # Status 1 means crafting in progress
                    # For in-progress items, we can show estimated time for user info
                    # but we don't actively count down - we wait for DB updates
                    return self._get_estimated_time_for_display(crafting_entry)
                else:
                    # Unknown status code
                    logging.warning(f"Unknown crafting status code: {status_code}")
                    return "Unknown"
            else:
                # No valid status found
                logging.warning("No valid status found in crafting entry")
                return "Unknown"

        except Exception as e:
            logging.error(f"Error reading crafting status from DB: {e}")
            return "Error"

    def _get_estimated_time_for_display(self, crafting_entry: Dict) -> str:
        """
        Calculate estimated time remaining for DISPLAY PURPOSES ONLY.
        This is NOT used for triggering updates - only for user information.
        SpacetimeDB will tell us when the status actually changes.

        Args:
            crafting_entry: Raw crafting entry from the database

        Returns:
            str: Estimated time remaining (e.g., "2h 30m" or "~45m")
        """
        try:
            recipe_id = crafting_entry.get("recipe_id")
            if not recipe_id or recipe_id not in self.crafting_recipes:
                return "In Progress"  # Generic status if we can't calculate

            recipe = self.crafting_recipes[recipe_id]
            duration_seconds = recipe.get("time_requirement", 0)

            # Get timestamp from the crafting entry - handle multiple formats
            timestamp_data = crafting_entry.get("timestamp")
            timestamp_micros = None

            if timestamp_data:
                # Handle nested format from subscription data
                timestamp_micros = timestamp_data.get("__timestamp_micros_since_unix_epoch__")

            if not timestamp_micros:
                # Handle direct format from processor data
                timestamp_micros = crafting_entry.get("timestamp_micros")
                if isinstance(timestamp_micros, list) and len(timestamp_micros) > 0:
                    timestamp_micros = timestamp_micros[0]

            if not timestamp_micros:
                # No timestamp - show generic progress with recipe duration
                return f"~{self._format_duration_for_display(duration_seconds)}"

            # Calculate estimated remaining time (for display only!)
            start_time = timestamp_micros / 1_000_000
            current_time = time.time()
            elapsed_time = current_time - start_time
            remaining_time = duration_seconds - elapsed_time

            # Debug logging for service time calculation
            recipe_id = crafting_entry.get("recipe_id", "unknown")

            if remaining_time <= 0:
                # This shouldn't happen if status is still [1, {}], but just in case
                return "Finishing..."

            # Don't add ~ since this will be updated by real-time timer
            return self._format_duration_for_display(remaining_time)

        except Exception as e:
            logging.error(f"Error calculating display time: {e}")
            return "In Progress"

    def _format_duration_for_display(self, seconds: float) -> str:
        """
        Format seconds into a human-readable duration string for display.

        Args:
            seconds: Duration in seconds

        Returns:
            str: Formatted duration (e.g., "2h 30m", "45m", "30s")
        """
        if seconds <= 0:
            return "0s"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        remaining_seconds = int(seconds % 60)

        if hours > 0:
            if minutes > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{hours}h"
        elif minutes > 0:
            if remaining_seconds > 0 and minutes < 5:  # Show seconds for short durations
                return f"{minutes}m {remaining_seconds}s"
            else:
                return f"{minutes}m"
        else:
            return f"{remaining_seconds}s"

    # REPLACE the existing calculate_remaining_time method with this new version
    def calculate_remaining_time(self, crafting_entry: Dict) -> str:
        """
        DEPRECATED: This method now delegates to database status reading.

        Instead of calculating when things should complete, we read the actual
        status from the database. SpacetimeDB subscriptions tell us when things change.

        Args:
            crafting_entry: Raw crafting entry from the database

        Returns:
            str: Current status from database
        """
        # Use the new database status reading instead of timer calculations
        return self.get_crafting_status_from_db(crafting_entry)

    def parse_subscription_update(self, db_update: dict) -> Dict[str, Any]:
        """
        Parse a SpacetimeDB subscription update to determine what specifically changed.
        This replaces the need for full data refreshes by identifying targeted changes.

        Args:
            db_update: Raw subscription update message from SpacetimeDB

        Returns:
            Dictionary indicating what changed:
            {
                "crafting_completed": [list of completed operations],
                "crafting_status_changed": [list of operations with status changes],
                "new_crafting_started": [list of new operations],
                "crafting_removed": [list of removed operations],
                "needs_full_refresh": bool,
                "error": str or None
            }
        """
        changes = {
            "crafting_completed": [],
            "crafting_status_changed": [],
            "new_crafting_started": [],
            "crafting_removed": [],
            "needs_full_refresh": False,
            "error": None,
        }

        try:
            # Convert update to string for initial analysis
            update_str = str(db_update)

            # Check if this update contains passive crafting data
            if "passive_craft_state" not in update_str:
                return changes

            # Parse the subscription update structure
            # SpacetimeDB sends updates in the format:
            # {"SubscriptionUpdate": {"database_update": {"tables": [...]}}}
            parsed_changes = self._extract_crafting_changes_from_update(db_update)

            if parsed_changes:
                changes.update(parsed_changes)
                logging.info(
                    f"Parsed subscription update: {len(changes['crafting_completed'])} completed, "
                    f"{len(changes['crafting_status_changed'])} status changed, "
                    f"{len(changes['new_crafting_started'])} new"
                )
            else:
                # If we can't parse the update properly, fall back to full refresh
                changes["needs_full_refresh"] = True
                logging.warning("Could not parse crafting changes, will trigger full refresh")

        except Exception as e:
            logging.error(f"Error parsing subscription update: {e}")
            changes["error"] = str(e)
            changes["needs_full_refresh"] = True

        return changes

    def _extract_crafting_changes_from_update(self, db_update: dict) -> Dict[str, List]:
        """
        Extract specific crafting changes from the SpacetimeDB update structure.

        This method digs into the subscription update to find:
        - Which crafting operations changed status
        - Which operations completed (status changed to [2, {}])
        - Which operations are new
        """
        changes = {"crafting_completed": [], "crafting_status_changed": [], "new_crafting_started": [], "crafting_removed": []}

        try:
            # Navigate the SpacetimeDB subscription update structure
            if "SubscriptionUpdate" in db_update:
                database_update = db_update["SubscriptionUpdate"].get("database_update", {})
            elif "TransactionUpdate" in db_update:
                database_update = db_update["TransactionUpdate"].get("database_update", {})
            else:
                logging.warning("Unknown update structure format")
                return None

            tables = database_update.get("tables", [])

            # Find the passive_craft_state table updates
            for table in tables:
                table_name = table.get("table_name", "")
                if table_name == "passive_craft_state":
                    changes = self._process_crafting_table_update(table)
                    break

        except Exception as e:
            logging.error(f"Error extracting crafting changes: {e}")
            return None

        return changes

    def _process_crafting_table_update(self, table_update: dict) -> Dict[str, List]:
        """
        Process updates to the passive_craft_state table specifically.

        Args:
            table_update: The table update portion of the subscription message

        Returns:
            Dictionary with categorized changes
        """
        changes = {"crafting_completed": [], "crafting_status_changed": [], "new_crafting_started": [], "crafting_removed": []}

        try:
            # Process inserts (new crafting operations or updates)
            inserts = table_update.get("inserts", [])
            for insert_row in inserts:
                crafting_op = self._parse_crafting_row(insert_row)
                if crafting_op:
                    # Check if this is a completion (status [2, {}])
                    if self._is_crafting_completed(crafting_op):
                        changes["crafting_completed"].append(crafting_op)
                    elif self._is_crafting_in_progress(crafting_op):
                        # Could be new or status change - for now, treat as status change
                        changes["crafting_status_changed"].append(crafting_op)

            # Process deletes (crafting operations removed)
            deletes = table_update.get("deletes", [])
            for delete_row in deletes:
                crafting_op = self._parse_crafting_row(delete_row)
                if crafting_op:
                    changes["crafting_removed"].append(crafting_op)

            # Note: SpacetimeDB may use "updates" or handle updates as delete+insert
            # We'll handle this as we see the actual message format

        except Exception as e:
            logging.error(f"Error processing crafting table update: {e}")

        return changes

    def _parse_crafting_row(self, row_data) -> Dict:
        """
        Parse a single crafting row from the subscription update.

        Args:
            row_data: Raw row data from SpacetimeDB

        Returns:
            Parsed crafting operation dictionary or None if parsing fails
        """
        try:
            # The exact format depends on how SpacetimeDB sends the data
            # It might be JSON string that needs parsing, or already a dict
            if isinstance(row_data, str):
                import json

                crafting_data = json.loads(row_data)
            else:
                crafting_data = row_data

            # Extract the key information we need
            parsed_op = {
                "recipe_id": crafting_data.get("recipe_id"),
                "building_entity_id": crafting_data.get("building_entity_id"),
                "owner_entity_id": crafting_data.get("owner_entity_id"),
                "status": crafting_data.get("status"),
                "timestamp": crafting_data.get("timestamp"),
                "raw_data": crafting_data,  # Keep original for debugging
            }

            return parsed_op

        except Exception as e:
            logging.error(f"Error parsing crafting row: {e}")
            return None

    def _is_crafting_completed(self, crafting_op: Dict) -> bool:
        """
        Check if a crafting operation has completed based on its status.

        Args:
            crafting_op: Parsed crafting operation

        Returns:
            True if the operation is completed (status [2, {}])
        """
        try:
            status = crafting_op.get("status")
            if status and isinstance(status, list) and len(status) > 0:
                return status[0] == 2  # Status 2 means completed
        except:
            pass
        return False

    def _is_crafting_in_progress(self, crafting_op: Dict) -> bool:
        """
        Check if a crafting operation is in progress.

        Args:
            crafting_op: Parsed crafting operation

        Returns:
            True if the operation is in progress (status [1, {}])
        """
        try:
            status = crafting_op.get("status")
            if status and isinstance(status, list) and len(status) > 0:
                return status[0] == 1  # Status 1 means in progress
        except:
            pass
        return False

    def parse_crafting_update(self, db_update: dict) -> bool:
        """
        Parses a database update message to check if it's relevant to passive crafting.
        Returns True if the data was updated and needs GUI refresh.
        """
        update_str = str(db_update)
        if "passive_craft_state" in update_str:
            logging.info("Received a passive crafting update.")
            # Refresh the crafting data using enhanced version
            self.current_crafting_data = self.get_all_crafting_data_enhanced()
            return True

        return False

    def get_current_crafting_data_for_gui(self) -> List[Dict]:
        """Returns the current crafting data formatted for GUI display."""
        return self.current_crafting_data

    def get_last_changes(self) -> Dict:
        """
        Get information about the last set of changes detected.
        This can be used by the UI to provide targeted updates and feedback.
        """
        return getattr(self, "_last_changes", {})
