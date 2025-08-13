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
            "buy_order_state",
            "sell_order_state",
            "character_stats_state",
            "inventory_state",
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

                # TODO
                # Handle buy_order_state transactions

                # TODO
                # Handle sell_order_state transactions

                # TODO
                # Handle character_stats_state transactions

                # TODO
                # Handle toolbelt-specific inventory_state transactions

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
            if table_name == "buy_order_state":
                self._process_buy_order_data(table_rows)
            elif table_name == "sell_order_state":
                self._process_sell_order_data(table_rows)
            elif table_name == "character_stats_state":
                # TODO
                # Look up Character State Type bindings to find meaning of "Values" field
                # Generally, there's good Speed info here but not good Power info
                #logging.info(f"TEMP - Character Stats State: {table_update}")
                ...
            elif table_name == "inventory_state":
                # TODO
                #logging.info(f"TEMP - Inventory State: {table_update}")
                ...

            # Try to send consolidated compare jobs if we have all necessary data
            self._send_compare_jobs_update()

        except Exception as e:
            logging.error(f"Error handling compare jobs subscription: {e}")

    def _process_buy_order_data(self, buy_order_rows):
        """Process buy_order_state data to store buy order info"""
        try:
            if not hasattr(self, "_buy_order_data"):
                self._buy_order_data = {}

            for row in buy_order_rows:
                entity_id = row.get("entity_id")
                if entity_id:
                    self._buy_order_data[entity_id] = {
                        "item_id": row.get("item_id"),
                        "item_type": row.get("item_type"),
                        "price_threshold": row.get("price_threshold"),
                        "quantity": row.get("quantity")
                    }
        except Exception as e:
            logging.error(f"Error processing buy order data: {e}")
    
    def _process_sell_order_data(self, sell_order_rows):
        """Process sell_order_state data to store sell order info"""
        try:
            if not hasattr(self, "_sell_order_data"):
                self._sell_order_data = {}

            for row in sell_order_rows:
                entity_id = row.get("entity_id")
                if entity_id:
                    self._sell_order_data[entity_id] = {
                        "item_id": row.get("item_id"),
                        "item_type": row.get("item_type"),
                        "price_threshold": row.get("price_threshold"),
                        "quantity": row.get("quantity")
                    }
        except Exception as e:
            logging.error(f"Error processing sell order data: {e}")

    def _process_toolbelt_data(self, inventory_rows):
        """Process inventory_state data to store toolbelt info"""
        try:
            if not hasattr(self, "_toolbelt_data"):
                self._toolbelt_data = {}

            for row in inventory_rows:
                #logging.info(f"TEMP - Toolbelt Row: {row}")
                ...
        except Exception as e:
            logging.error(f"Error processing toolbelt data: {e}")

    def _send_compare_jobs_update(self):
        """Send consolidated compare jobs update by combining all cached data."""
        try:
            # TODO
            # Maybe some "return" catching if certain attributes don't exist?

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
        Consolidate compare jobs data into hierarchy: Job -> ...?

        Returns:
            Dictionary with items consolidated in hierarchical structure
        """
        try:
            # First collect all raw operations
            raw_operations = []

            # Get reference data for lookups
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
                        item_id = primary_in[0]
                    except:
                        continue

                    if primary_in[2][0] == 0:
                        item_info = self.item_lookup_service.lookup_item_by_id(
                            item_id, "item_desc"
                            )
                    elif primary_in[2][0] == 1:
                        item_info = self.item_lookup_service.lookup_item_by_id(
                            item_id, "cargo_desc"
                            )
                    input_name = (
                                item_info.get("name", f"Unknown Item {item_id}") if item_info else f"Unknown Item {item_id}"
                            )
                    job_name = job_name.replace("{1}",input_name)
                if "{0}" in job_name:
                    output_name = "{0}"
                    try:
                        primary_out = recipe["crafted_item_stacks"][0]
                        item_id = primary_out[0]
                    except:
                        continue

                    if primary_out[2][0] == 0:
                        item_info = self.item_lookup_service.lookup_item_by_id(
                            item_id, "item_desc"
                            )
                    elif primary_out[2][0] == 1:
                        item_info = self.item_lookup_service.lookup_item_by_id(
                            item_id, "cargo_desc"
                            )
                    output_name = (
                                item_info.get("name", f"Unknown Item {item_id}") if item_info else f"Unknown Item {item_id}"
                            )
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
        Build hierarchy from raw operations: Job -> ...?

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
        # TODO
        # Clear cached data
        if hasattr(self, "_buy_order_data"):
            self._buy_order_data.clear()

        if hasattr(self, "_sell_order_data"):
            self._sell_order_data.clear()
