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
            "building_state",
            "sell_order_state",
            "character_stats_state",
            "equipment_state",
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
            elif table_name == "building_state":
                self._process_building_data(table_rows)
            elif table_name == "sell_order_state":
                # TODO
                #logging.info(f"TEMP - Sell Order State: {table_update}")
                ...
            elif table_name == "character_stats_state":
                # TODO
                # Look up Character State Type bindings to find meaning of "Values" field
                # Generally, there's good Speed info here but not good Power info
                logging.info(f"TEMP - Character Stats State: {table_update}")
                ...
            elif table_name == "equipment_state":
                # TODO:
                # Equipment state seems to just be for armor
                # For my needs, worsely redundant with character_states_state
                #logging.info(f"TEMP - Equipment State: {table_update}")
                ...
            # Seems that inventory_state is what I really need? Now, how to go about accessing that without
            # breaking pre-existing stuff?

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

            # Get reference data for lookups
            item_lookups = self._get_item_lookups()
            recipe_lookup = {r["id"]: r for r in self.reference_data.get("crafting_recipe_desc", [])}

            # Add crafting recipe info to list of raw_operations
            for recipe in recipe_lookup.values():
                job_id = f"Craft_{recipe["id"]}"

                # Find item name and replace {}-variables
                job_name = recipe["name"]
                job_name = job_name.replace("{2}","{1}")
                if "{1}" in job_name:
                    input_name = "{1}"
                    try:
                        primary_in = recipe["consumed_item_stacks"][0]
                    except:
                        continue
                    if primary_in[2][0] == 0:
                        input_name = item_lookups[(primary_in[0],"item_desc")]["name"]
                    elif primary_in[2][0] == 1:
                        input_name = item_lookups[(primary_in[0],"cargo_desc")]["name"]
                    job_name = job_name.replace("{1}",input_name)
                if "{0}" in job_name:
                    output_name = "{0}"
                    try:
                        primary_out = recipe["crafted_item_stacks"][0]
                    except:
                        continue
                    if primary_out[2][0] == 0:
                        output_name = item_lookups[(primary_out[0],"item_desc")]["name"]
                    elif primary_out[2][0] == 1:
                        output_name = item_lookups[(primary_out[0],"cargo_desc")]["name"]
                    job_name = job_name.replace("{0}",output_name)

                job_time = recipe["time_requirement"]
                job_stamina = recipe["stamina_requirement"]
                job_durability = recipe["tool_durability_lost"]
                job_building = recipe["building_requirement"]
                job_level = recipe["level_requirements"]
                job_tool = recipe["tool_requirements"]
                job_inputs = recipe["consumed_item_stacks"]
                job_xp = recipe["experience_per_progress"]
                job_outputs = recipe["crafted_item_stacks"]
                job_actions = recipe["actions_required"]
                job_hands = recipe["allow_use_hands"]
                job_passive = recipe["is_passive"]

                raw_operation = {
                    "job_id": job_id,
                    "job_name": job_name,
                    "time_requirement": job_time,
                    "stamina_requirement": job_stamina,
                    "tool_durability_lost": job_durability,
                    "building_requirement": job_building,
                    "level_requirement": job_level,
                    "tool_requirement": job_tool,
                    "input_stacks": job_inputs,
                    "xp_gain": job_xp,
                    "output_stacks": job_outputs,
                    "actions_required": job_actions,
                    "allow_use_hands": job_hands,
                    "is_passive": job_passive
                }
                raw_operations.append(raw_operation)

            # TODO: Add extraction recipe info to list of raw_operations

            # Now build the hierarchy
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
        try:
            hierarchy = {}

            # Group by item name first (Level 1)
            for op in raw_operations:
                job_id = op["job_id"]

                if job_id not in hierarchy:
                    hierarchy[job_id] = {
                        "job_id": job_id,
                        "job_name": op["job_name"],
                        "time_requirement": op["time_requirement"],
                        "stamina_requirement": op["stamina_requirement"],
                        "tool_durability_lost": op["tool_durability_lost"],
                        "building_requirement": op["building_requirement"],
                        "level_requirement": op["level_requirement"],
                        "tool_requirement": op["tool_requirement"],
                        "input_stacks": op["input_stacks"],
                        "xp_gain": op["xp_gain"],
                        "output_stacks": op["output_stacks"], 
                        "actions_required": op["actions_required"],
                        "allow_use_hands": op["allow_use_hands"],
                        "is_passive": op["is_passive"]
                    }

            # Convert to UI format
            return self._format_hierarchy_for_ui(hierarchy)

        except Exception as e:
            logging.error(f"Error building hierarchy: {e}")
            return {}

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

            for job_id, job_data in hierarchy.items():
                # Create a simple entry that contains all the individual operations
                formatted[job_id] = {
                    "job_id": job_id,
                    "job": job_data["job_name"],
                    "time": job_data["time_requirement"],
                    "stamina": job_data["stamina_requirement"],
                    "durability_cost": job_data["tool_durability_lost"],
                    "building": job_data["building_requirement"],
                    "skill": job_data["level_requirement"],
                    "tool": job_data["tool_requirement"],
                    "inputs": job_data["input_stacks"],
                    "xp": job_data["xp_gain"],
                    "outputs": job_data["output_stacks"],
                    "effort": job_data["actions_required"],
                    "use_hands": job_data["allow_use_hands"],
                    "is_passive": job_data["is_passive"],
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
            #if not hasattr(self, "_claim_members") or not self._claim_members:
            #    return False

            owner_id_str = str(owner_entity_id)
            #owner_name = self._claim_members.get(owner_id_str)
            #if not owner_name:
            #    return False

            # Check if owner is the current player
            #return owner_name == current_player_name

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

        #if hasattr(self, "_claim_members"):
        #    self._claim_members.clear()

        #if hasattr(self, "_public_actions"):
        #    self._public_actions.clear()

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
