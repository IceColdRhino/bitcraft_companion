"""
Compare jobs processor for handling progressive_action_state table updates.
"""

import re
import json
import time
import logging
import numpy as np
from .base_processor import BaseProcessor
from app.models import (
    MarketOrderState,
    # Reference data dataclasses
    CraftingRecipeDesc,
    ItemListDesc
)


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
            "crafting_recipe_desc",
            "item_list_desc",
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

                # TODO: Handle buy_order_state transactions

                # TODO: Handle sell_order_state transactions

                # TODO: Handle character_stats_state transactions

                # TODO: Handle toolbelt-specific inventory_state transactions

                # TODO: Maybe handle desc transactions?

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
                self._process_character_stat_data(table_rows)
            elif table_name == "inventory_state":
                self._process_toolbelt_data(table_rows)
            elif table_name == "crafting_recipe_desc":
                self._process_crafting_recipe_data(table_rows)
            elif table_name == "item_list_desc":
                self._process_item_list_data(table_rows)

            # Try to send consolidated compare jobs if we have all necessary data
            self._send_compare_jobs_update()

        except Exception as e:
            logging.error(f"Error handling compare jobs subscription: {e}")

    def _process_buy_order_data(self, buy_order_rows):
        """Process buy_order_state data to store buy order info"""
        try:
            if not hasattr(self, "_buy_orders"):
                self._buy_orders = {}

            for row in buy_order_rows:
                buy_order = MarketOrderState.from_dict(row)
                self._buy_orders[buy_order.entity_id] = buy_order
        except Exception as e:
            logging.error(f"Error processing buy order data: {e}")
    
    def _process_sell_order_data(self, sell_order_rows):
        """Process sell_order_state data to store sell order info"""
        try:
            if not hasattr(self, "_sell_orders"):
                self._sell_orders = {}

            for row in sell_order_rows:
                sell_order = MarketOrderState.from_dict(row)
                self._sell_orders[sell_order.entity_id] = sell_order
        except Exception as e:
            logging.error(f"Error processing sell order data: {e}")

    def _process_character_stat_data(self,stat_rows):
        """Process character_stats_state data to store character stat info"""
        # TODO: Handle character stat data
        # Look up Character State Type bindings to find meaning of "Values" field
        # Generally, there's good Speed info here but not good Power info
        try:
            if not hasattr(self,"_character_stat_data"):
                self._character_stat_data = {}

            logging.info(f"TEMP - Character Stat Rows: {stat_rows}")
        
        except Exception as e:
            logging.error(f"Error processing character stat data: {e}")

    def _process_toolbelt_data(self, inventory_rows):
        """Process inventory_state data to store toolbelt info"""
        try:
            if not hasattr(self, "_toolbelt_data"):
                self._toolbelt_data = {}

            for row in inventory_rows:
                if row["owner_entity_id"]==360287970202671962 and row["inventory_index"] == 1:
                    logging.info(f"TEMP - Toolbelt Row: {row}")
                    ...
        except Exception as e:
            logging.error(f"Error processing toolbelt data: {e}")

    # TODO: Check reference data processor
    # Right now I'm manually handling some desc tables below, but this might be redundant?
    def _process_crafting_recipe_data(self, recipe_rows):
        """Process crafting_recipe_desc data to store crafting recipe info."""
        try:
            if not hasattr(self,"_crafting_recipes"):
                self._crafting_recipes = {}

            for row in recipe_rows:
                crafting_recipe = CraftingRecipeDesc.from_dict(row)
                self._crafting_recipes[crafting_recipe.id] = crafting_recipe
        
        except Exception as e:
            logging.error(f"Error processing crafting recipe data: {e}")

    def _process_item_list_data(self, item_list_rows):
        """Process item_list_desc data to store item list info."""
        try:
            if not hasattr(self,"_item_lists"):
                self._item_lists = {}

            for row in item_list_rows:
                item_list = ItemListDesc.from_dict(row)
                self._item_lists[item_list.id] = item_list
        
        except Exception as e:
            logging.error(f"Error processing item list data: {e}")

    def _send_compare_jobs_update(self):
        """Send consolidated compare jobs update by combining all cached data."""
        try:
            # TODO: Maybe handle some catching
            # Possibly some "return" clauses if certain attributes don't exist?

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

            # Add crafting recipe info to list of raw_operations
            # TODO: Get actual crafting speed value
            craft_speed = 1.28
            job_type = "Craft"
            for job_id in self._crafting_recipes:
                recipe = self._crafting_recipes[job_id]
                try:
                    primary_out = recipe.crafted_item_stacks[0]
                    source = self._source_convert(primary_out[2])
                    job_name = self.item_lookup_service.get_item_name(
                        primary_out[0],source)
                except:
                    job_name = "Unknown Item"
                    logging.debug(f"Unresolved output name in job_id: craft_{job_id}")

                long_name = self._replace_curly_variables(recipe)

                job_actions = recipe.actions_required
                job_passive = recipe.is_passive

                # TODO: Get actual skill speeds
                # Temporary fallback value
                skill_speed = 1.09

                combined_speed = (craft_speed - 1)+skill_speed
                # swing_speed is in [seconds/swing], as in the game
                swing_speed = recipe.time_requirement/combined_speed

                # TODO: Get actual tool powers
                # Temporary fallback value
                tool_power = 10

                job_actions = recipe.actions_required
                total_swings = np.ceil(job_actions*swing_speed/tool_power)

                job_time = recipe.time_requirement*total_swings
                job_stamina = recipe.stamina_requirement*total_swings
                job_durability = recipe.tool_durability_lost*total_swings

                input_stacks = recipe.consumed_item_stacks
                job_inputs = self._format_input_stacks(input_stacks)

                output_stacks = recipe.crafted_item_stacks
                job_outputs = self._format_output_stacks(output_stacks)

                job_cost = sum(i[5] for i in job_inputs)
                job_gross = sum(o[5] for o in job_outputs)

                job_building = recipe.building_requirement
                job_level = recipe.level_requirements
                job_tool = recipe.tool_requirements
                job_xp = recipe.experience_per_progress
                job_hands = recipe.allow_use_hands

                job_profit = job_gross - job_cost
                job_pfm = 60*job_profit/job_time

                raw_operation = {
                    "job_id": job_id,
                    "job_type": job_type,
                    "job_name": job_name,
                    "long_name": long_name,
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
                    "is_passive": job_passive,
                    "cost": job_cost,
                    "gross": job_gross,
                    "profit": job_profit,
                    "profit_per_min": job_pfm,
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
                        "job_type": op["job_type"],
                        "job_name": op["job_name"],
                        "long_name": op["long_name"],
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
                        "is_passive": op["is_passive"],
                        "cost": op["cost"],
                        "gross": op["gross"],
                        "profit": op["profit"],
                        "profit_per_min": op["profit_per_min"],
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
                    "job_type": job_data["job_type"],
                    "job": job_data["job_name"],
                    "long_name": job_data["long_name"],
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
                    "passive": job_data["is_passive"],
                    "cost": job_data["cost"],
                    "gross": job_data["gross"],
                    "profit": job_data["profit"],
                    "profit_per_min": job_data["profit_per_min"],
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
        # TODO: Clear cached data
        if hasattr(self, "_buy_orders"):
            self._buy_orders.clear()

        if hasattr(self, "_sell_orders"):
            self._sell_orders.clear()

    def _replace_curly_variables(self, recipe):
        """Fill in the {0}, {1}, {2} variables in names in recipe names"""
        job_name = recipe.name
        job_name = job_name.replace("{2}","{1}")

        if "{1}" in job_name:
            try:
                primary_in = recipe.consumed_item_stacks[0]
                source = self._source_convert(primary_in[2])
                input_name = self.item_lookup_service.get_item_name(
                    primary_in[0],source)
            except:
                input_name = "Unknown Item"
                logging.debug(f"Unresolved input variable in job_id: craft_{recipe.id}")
            job_name = job_name.replace("{1}",input_name)
            

        if "{0}" in job_name:
            try:
                primary_out = recipe.crafted_item_stacks[0]
                source = self._source_convert(primary_out[2])
                output_name = self.item_lookup_service.get_item_name(
                    primary_out[0],source)
            except:
                output_name = "Unknown Item"
                logging.debug(f"Unresolved output variable in job_id: craft_{recipe.id}")
            job_name = job_name.replace("{0}",output_name)

        return job_name
    
    def _source_convert(self,type_array):
        """Convert x format type array to 'preferred source' as used by item_lookup_service"""
        if type_array == [1, []]:
            return "cargo_desc"
        elif type_array == [0, []]:
            return "item_desc"
        else:
            logging.error(f"Unrecognized item type array: {type_array}")
    
    def _rarity_convert(self,rare_array):
        """Convert [x, {}] format rarity array to human-readable string."""
        # TODO: It maybe makes sense to roll this into item_lookup_service?
        
        rare_list = [
            "Default",
            "Common",
            "Uncommmon",
            "Rare",
            "Epic",
            "Legendary",
            "Mythic",
        ]
        try:
            return rare_list[rare_array[0]]
        except:
            logging.error(f"Unable to parse rarity array: {rare_array}")

    def _format_input_stacks(self,input_stacks):
        """Format input stacks from a subscription to a table-ready list."""
        job_inputs = []
        for entry in input_stacks:
            source = self._source_convert(entry[2])
            item = self.item_lookup_service.lookup_item_by_id(entry[0],source)
            row = [
                item["name"],
                self._rarity_convert(item["rarity"]),
                ]
            # Calculate expected quantity
            row.append(entry[1]*entry[4])

            # Calculate price window
            window = self._get_price_window(entry[0],entry[2])
            row.append(window)

            # Calculate price to procure materials
            # TODO: Calculate buy price from window
            #price = int(np.ceil((0.05*(window[1]-window[0])) + window[0]))
            price = window[1]
            row.append(price)

            # Calculate row's contribution to overall job value
            row.append(np.round(row[2]*row[4],4))

            job_inputs.append(row)

        # Sort rows by job value
        job_inputs.sort(key=lambda x: x[5], reverse=True)

        return job_inputs
    
    def _format_output_stacks(self,output_stacks):
        """Format output stacks from a subscription to a table-ready list."""
        # Stage 1: Create a structure with id, item_type, and quantity
        # with duplicates from item lists
        first_pass = []
        for entry in output_stacks:
            item_id = entry[0]
            item_type = entry[2]
            source = self._source_convert(item_type)
            item = self.item_lookup_service.lookup_item_by_id(entry[0],source)
            single_output = self._item_list_adder(item,item_type)
            for element in single_output:
                element[2] = entry[1]*element[2]
            first_pass += single_output
        
        # Stage 2: Collaps all duplicates, summing along quantity
        # I'm beyond certain there's a better way to do something like this
        # pandas groupby for example, if pandas weren't so slow.
        # Maybe itertools?
        second_pass = [x[:] for x in first_pass]
        for entry2 in second_pass:
            q_sum = 0
            for entry1 in first_pass:
                if entry1[0]==entry2[0] and entry1[1]==entry2[1]:
                    q_sum += entry1[2]
            entry2[2] = np.round(q_sum,6)

        third_pass = []
        for entry in second_pass:
            if entry not in third_pass:
                third_pass.append(entry)


        # Stage 3: Return structure with list rows ordered by  -
        # name, rarity, quantity, price window, price, and value
        job_outputs = []
        for entry in third_pass:
            item_id = entry[0]
            item_type = entry[1]
            source = self._source_convert(item_type)
            item = self.item_lookup_service.lookup_item_by_id(entry[0],source)

            row = [
                item["name"],
                self._rarity_convert(item["rarity"]),
                entry[2],
            ]

            # Calculate price window
            window = self._get_price_window(item_id,item_type)
            row.append(window)

            # Calculate price to liquidate materials
            # TODO: Better price calculation
            #price = int(np.floor((0.95*(window[1]-window[0])) + window[0]))
            price = window[1]-1
            row.append(price)

            # Calculate row's contribution to overall job value
            row.append(np.round(entry[2]*price,4))

            job_outputs.append(row)

        # Sort rows by job value
        job_outputs.sort(key=lambda x: x[5], reverse=True)

        return job_outputs

    def _item_list_adder(self,item,item_type):
        """
        Given an item_lookup_service output, returns either:
        - A single-entry list describing only itself
        or
        - A multi-entry list describing item list outputs
        """
        item_list_id = item.get("item_list_id", 0)

        if item_list_id == 0:
            # Immediately return items that aren't item lists
            # and all cargos
            return [[item["id"],item_type,1]]
        else:
            # I should really probably be doing all this with dicts or classes,
            # not lists.
            output = []
            item_list = self._item_lists[item_list_id]
            possibilities = item_list.possibilities
            p_sum = sum(p[0] for p in possibilities)

            for possibility in possibilities:
                for entry in possibility[1]:
                    # I highly doubt that CWL would send one item list directly to another.
                    # However, this recursion should handle it if they do.
                    item_type2 = entry[2]
                    source = self._source_convert(item_type2)
                    item2 = self.item_lookup_service.lookup_item_by_id(entry[0],source)

                    single_output = self._item_list_adder(item2,item_type2)
                    for element in single_output:
                        element[2] = possibility[0]*entry[1]*element[2]/p_sum
                    output += single_output
            return output
        
    def _get_price_window(self,item_id,item_type):
        """Given item lookup info, returns a price window (low,high) tuple of existing market orders."""
        if item_type == [0,[]]:
            item_type = 0
        elif item_type == [1,[]]:
            item_type = 1
        else:
            logging.error(f"Unrecognized item, id: {item_id}, type array: {item_type}")


        # TODO: Introduce conditions to allow for supply sale to claim?
        try:
            buy_ids = [b for b in self._buy_orders.values() if b.item_id==item_id]
            buy_types = [b for b in buy_ids if b.item_type==item_type]
            max_buy = max(buy_types, key=lambda x:x.price_threshold).price_threshold
        except:
            # TODO: Allow the user to specify their own preferred fallback value
            max_buy = 0

        # TODO: Introduce conditions to allow for purchase of NPC products
        try:
            sell_ids = [s for s in self._sell_orders.values() if s.item_id==item_id]
            sell_types = [s for s in sell_ids if s.item_type==item_type]
            min_sell = min(sell_types, key=lambda x:x.price_threshold).price_threshold
        except:
            # TODO: Allow the user to specify their own preferred fallback value
            min_sell = int(1e6)
        
        return (max_buy, min_sell)