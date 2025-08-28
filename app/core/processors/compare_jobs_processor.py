"""
Compare jobs processor for handling progressive_action_state table updates.
"""

import re
import json
import time
import logging
import numpy as np
from .base_processor import BaseProcessor
from ...core.data_paths import get_user_data_path
from app.models import (
    CharacterStatsState,
    InventoryState,
    MarketOrderState,
)


class CompareJobsProcessor(BaseProcessor):
    """
    Processes progressive_action_state table updates from SpacetimeDB.

    Handles both real-time transactions and batch subscription updates
    for compare jobs (progressive action) changes.
    """

    def __init__(self, data_queue, services, reference_data):
        """
        Initialize the active crafting processor.

        Args:
            data_queue: Queue for sending processed data to UI
            services: Dict of available services (item_lookup_service, etc.)
            reference_data: Static game data (recipes, items, buildings)

        Instance Variables:
            ...
        """
        super().__init__(data_queue, services, reference_data)

        # Load user id to get currently equipped tools
        try:
            self.user_id = services.get("data_service").user_id
        except:
            self.user_id = None
        
        # Is this even needed? Seems like no?
        # I just copy-pasted it from a different init and changed the variable name...
        self.current_compare_jobs_data = []

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
        Handle [x]_state transactions - LIVE incremental updates.

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

                # Handle buy_order_state transactions
                if table_name == "buy_order_state":
                    # Initialize _buy_orders if it doesn't exist
                    if not hasattr(self, "_buy_orders"):
                        self._buy_orders = {}

                    # Process inserts
                    for insert_str in inserts:
                        try:
                            # Parse the insert data
                            if isinstance(insert_str, str):
                                insert_data = MarketOrderState.from_json_string(insert_str)
                            
                            # TODO: Maybe some more conditions/exceptions here?
                            self._buy_orders[insert_data.entity_id] = insert_data
                        except Exception as e:
                            logging.error(f"Error processing buy order insert: {e}")

                    # Process deletes
                    for delete_str in deletes:
                        try:
                            # Parse the delete data
                            if isinstance(delete_str, str):
                                delete_data = json.loads(delete_str)
                            else:
                                delete_data = delete_str

                            buy_order_entity_id = None
                            if isinstance(delete_data,list) and len(delete_data)==9:
                                buy_order_entity_id = delete_data[0]
                            elif isinstance(delete_data,dict):
                                buy_order_entity_id = delete_data.get("entity_id")
                            else:
                                logging.warning(f"Unexpected buy_order_state delete format: {delete_data}")
                                continue

                            if buy_order_entity_id and buy_order_entity_id in self._buy_orders:
                                del self._buy_orders[buy_order_entity_id]
                        except Exception as e:
                            logging.error(f"Error processing buy order delete: {e}")

                    if inserts or deletes:
                        has_compare_jobs_changes = True

                # Handle sell_order_state transactions
                elif table_name == "sell_order_state":
                    # Initialize _sell_orders if it doesn't exist
                    if not hasattr(self, "_sell_orders"):
                        self._sell_orders = {}

                    # Process inserts
                    for insert_str in inserts:
                        try:
                            # Parse the insert data
                            if isinstance(insert_str, str):
                                insert_data = MarketOrderState.from_json_string(insert_str)

                            # TODO: Maybe some more conditions/exceptions here?
                            self._sell_orders[insert_data.entity_id] = insert_data
                        except Exception as e:
                            logging.error(f"Error processing sell order insert: {e}")

                    # Process deletes
                    for delete_str in deletes:
                        try:
                            # Parse the delete data
                            if isinstance(delete_str, str):
                                delete_data = json.loads(delete_str)
                            else:
                                delete_data = delete_str

                            sell_order_entity_id = None
                            if isinstance(delete_data,list) and len(delete_data)==9:
                                sell_order_entity_id = delete_data[0]
                            elif isinstance(delete_data,dict):
                                sell_order_entity_id = delete_data.get("entity_id")
                            else:
                                logging.warning(f"Unexpected sell_order_state delete format: {delete_data}")
                                continue

                            if sell_order_entity_id and sell_order_entity_id in self._sell_orders:
                                del self._sell_orders[sell_order_entity_id]
                        except Exception as e:
                            logging.error(f"Error processing sell order delete: {e}")

                    if inserts or deletes:
                        has_compare_jobs_changes = True

                # Handle character_stats_state transactions
                # TODO: This is broken, need to fix it
                elif table_name == "character_stats_state":
                    if not hasattr(self, "_character_stats"):
                        self._character_stats = {}

                    # Simply overwrite previous stat block
                    for insert_str in inserts:
                        data = json.loads(insert_str)
                        if data:
                            self._character_stats = CharacterStatsState.from_dict(data).values_to_dict()
                    if inserts or deletes:
                        has_compare_jobs_changes = True

                # TODO: Handle toolbelt-specific inventory_state transactions

                # For other table types, do full refresh if we have changes
                elif inserts or deletes:
                    self._log_transaction_debug("compare jobs", len(inserts), len(deletes), reducer_name)
                    has_compare_jobs_changes = True

            # Send incremental update if we have changes
            if has_compare_jobs_changes:
                logging.info(f"[CompareJobsProcessor] Detected job changes, sending update for table: {table_name}")
                #if table_name == "inventory_state":
                #    # Pass player context for accurate activity tracking
                #    self._send_incremental_inventory_update(reducer_name, timestamp, player_context)
                #else:
                logging.debug(f"Sending full refresh for table: {table_name}")
                self._refresh_jobs()
            else:
                logging.debug(f"[CompareJobsProcessor] No job changes detected for transaction")

        except Exception as e:
            logging.error(f"Error handling compare jobs transaction: {e}")

    def process_subscription(self, table_update):
        """
        Handle various subscription updates.
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

            # Try to send consolidated compare jobs if we have all necessary data
            self._send_compare_jobs_update()

        except Exception as e:
            logging.error(f"Error handling compare jobs subscription: {e}")

    def _refresh_jobs(self):
        """
        Process jobs data from subscription and send to UI.
        Called from transaction updates.
        """
        try:
            # For transaction updates, trigger a refresh if we have subscription data
            #if hasattr(self, "_inventory_data") and self._inventory_data:
            #    self._send_compare_jobs_update()
            #else:
            #    # Send empty data for transaction-only updates
            #empty_jobs_data = {}
            #self._queue_update("compare_jobs_update", empty_jobs_data, {"transaction_update": True})
            self._send_compare_jobs_update()

        except Exception as e:
            logging.error(f"Error processing jobs from transaction: {e}")

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
        try:
            if not hasattr(self,"_character_stats"):
                self._character_stats = {}

            for row in stat_rows:
                self._character_stats = CharacterStatsState.from_dict(row).values_to_dict()
        
        except Exception as e:
            logging.error(f"Error processing character stat data: {e}")

    def _process_toolbelt_data(self, inventory_rows):
        """Process inventory_state data to store toolbelt info"""
        try:
            if not self.user_id:
                logging.warning("Unable to retrieve equipped tools - No user id available.")
                return
            
            if not hasattr(self, "_toolbelt_data"):
                self._toolbelt_data = {}

            tool_descs = self.reference_data.get("tool_desc", [])
            for row in inventory_rows:
                if row["owner_entity_id"]==self.user_id and row["inventory_index"] == 1:
                    inventory_state = InventoryState.from_dict(row)
                    for equipped_tool in inventory_state.get_items():
                        tool_desc = next((tool for tool in tool_descs if tool["item_id"] == equipped_tool["item_id"]), None)
                        if tool_desc:
                            self._toolbelt_data[tool_desc["tool_type"]] = {
                                "level": tool_desc.get("level",1),
                                "power": tool_desc.get("power",1),
                                }
        except Exception as e:
            logging.error(f"Error processing toolbelt data: {e}")

    def _send_compare_jobs_update(self):
        """Send consolidated compare jobs update by combining all cached data."""
        try:
            if not (hasattr(self, "_character_stats") and self._character_stats):
                return
            
            if not (hasattr(self, "_toolbelt_data") and self._toolbelt_data):
                return
            
            # Load current settings for buy/sell strategies
            self.settings = self._load_settings()
            
            # Consolidate compare jobs by job
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
            if self._character_stats:
                craft_speed = self._character_stats.get("crafting_speed",1.0)
            else:
                craft_speed = 1.0
            job_type = "Craft"
            crafting_recipes = self.reference_data.get("crafting_recipe_desc", [])
            for recipe in crafting_recipes:
                job_id = recipe["id"]

                try:
                    primary_out = recipe["crafted_item_stacks"][0]
                    source = self._source_convert(primary_out[2])
                    job_name = self.item_lookup_service.get_item_name(
                        primary_out[0],source)
                except:
                    job_name = "Unknown Item"
                    logging.debug(f"Unresolved output name in job_id: craft_{job_id}")

                long_name = self._replace_curly_variables(recipe)

                job_actions = recipe["actions_required"]
                job_passive = recipe["is_passive"]

                # TODO: Better skill/level handling
                # I would like something more resilient than the simple assumption that
                # the first skill in the list is the only skill in the list
                job_level = self._level_convert(recipe["level_requirements"][0])

                skill = job_level.split(':')[0].lower()
                if self._character_stats:
                    skill_speed = self._character_stats.get(f"{skill}_speed",1.0)
                    skill_power = self._character_stats.get(f"{skill}_power",0.0)
                else:
                    skill_speed = 1.0
                    skill_power = 0.0

                combined_speed = (craft_speed - 1)+skill_speed
                # swing_speed is in [seconds/swing], as in the game
                swing_speed = recipe["time_requirement"]/combined_speed

                # Get tool power for a given craft
                job_tool = recipe["tool_requirements"]
                job_hands = recipe["allow_use_hands"]

                if len(job_tool) > 0 and self._toolbelt_data[job_tool[0][0]]:
                    # Strict tool-required and held instances
                    # TODO: Similar to skills, I want to get rid of the "first is only" assumption.
                    tool_req = job_tool[0]
                    tool_type = tool_req[0]
                    tool_level_req = tool_req[1]
                    tool_power_req = tool_req[2]
                    if self._toolbelt_data[tool_type].get("level",1) < tool_level_req:
                        # Omit jobs from the table for which the user doesn't have the needed tool level
                        continue
                    if self._toolbelt_data[tool_type].get("power",1) < tool_power_req:
                        # Omit jobs from the table for which the user doesn't have the needed tool power
                        continue
                    tool_power = self._toolbelt_data[tool_type].get("power",1)
                elif job_hands:
                    # Fallback hand craft instances
                    # TODO: Check this is actually the correct value
                    tool_power = 1
                elif len(job_tool) == 0 and not job_hands:
                    # This makes no sense. But tool scrapping seems to fall into this bin.
                    tool_power = 1
                else:
                    # If the conditions have reached this point,
                    # the job can't be hand-crafted but the appropriate tool isn't equipped.
                    # Omit the job from the list.
                    continue

                total_power = tool_power + skill_power

                job_actions = recipe["actions_required"]
                total_swings = int(np.ceil(job_actions/total_power))

                job_time = swing_speed*total_swings
                job_stamina = recipe["stamina_requirement"]*total_swings
                job_durability = recipe["tool_durability_lost"]*total_swings

                input_stacks = recipe["consumed_item_stacks"]
                job_inputs = self._format_input_stacks(input_stacks)

                output_stacks = recipe["crafted_item_stacks"]
                job_outputs = self._format_output_stacks(output_stacks)

                try:
                    job_cost = sum(i[5] for i in job_inputs)
                except:
                    logging.debug(f"No input prices detected in input stack {job_inputs} for craft_{job_id}")
                    job_cost = 0
                try:
                    job_gross = sum(o[5] for o in job_outputs)
                except:
                    logging.debug(f"No output prices detected in output stack {job_outputs} for craft_{job_id}")
                    job_gross = 0

                job_profit = job_gross - job_cost
                job_pfm = 60*job_profit/job_time

                job_building = recipe["building_requirement"]
                job_xp = recipe["experience_per_progress"]

                raw_operation = {
                    "job_id": f"craft_{job_id}",
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
                    "total_power": total_power,
                    "swing_speed": swing_speed,
                    "cost": job_cost,
                    "gross": job_gross,
                    "profit": job_profit,
                    "profit_per_min": job_pfm,
                }
                raw_operations.append(raw_operation)

            # Add extraction recipe info to list of raw_operations
            if self._character_stats:
                gather_speed = self._character_stats.get("gathering_speed",1.0)
            else:
                gather_speed = 1.0
            job_type = "Gather"
            extraction_recipes = self.reference_data.get("extraction_recipe_desc", [])
            for recipe in extraction_recipes:
                job_id = recipe["id"]
                # In the current state of the game, I only care about extractions from resources
                # not extractions from cargos
                if recipe["resource_id"]==0 or recipe["cargo_id"]!=0:
                    continue

                resource = self.item_lookup_service.lookup_item_by_id(recipe["resource_id"],"resource_desc")

                job_name = resource["name"]
                long_name = f"{recipe["verb_phrase"]} {job_name}"

                # TODO: Better skill/level handling
                # I would like something more resilient than the simple assumption that
                # the first skill in the list is the only skill in the list
                job_level = self._level_convert(recipe["level_requirements"][0])

                skill = job_level.split(':')[0].lower()
                if self._character_stats:
                    skill_speed = self._character_stats.get(f"{skill}_speed",1.0)
                    skill_power = self._character_stats.get(f"{skill}_power",0.0)
                else:
                    skill_speed = 1.0
                    skill_power = 0.0

                combined_speed = (gather_speed - 1)+skill_speed
                # swing_speed is in [seconds/swing], as in the game
                swing_speed = recipe["time_requirement"]/combined_speed

                # Get actual tool powers
                job_tool = recipe["tool_requirements"]
                job_hands = recipe["allow_use_hands"]

                if len(job_tool) > 0 and self._toolbelt_data[job_tool[0][0]]:
                    # Strict tool-required and held instances
                    # TODO: Similar to skills, I want to get rid of the "first is only" assumption.
                    tool_req = job_tool[0]
                    tool_type = tool_req[0]
                    tool_level_req = tool_req[1]
                    tool_power_req = tool_req[2]
                    if self._toolbelt_data[tool_type].get("level",1) < tool_level_req:
                        # Omit jobs from the table for which the user doesn't have the needed tool level
                        continue
                    if self._toolbelt_data[tool_type].get("power",1) < tool_power_req:
                        # Omit jobs from the table for which the user doesn't have the needed tool power
                        continue
                    tool_power = self._toolbelt_data[tool_type].get("power",1)
                elif job_hands:
                    # Fallback hand gather instances
                    # TODO: Check this is actually the correct value
                    tool_power = 1
                else:
                    # If the conditions have reached this point,
                    # the job can't be hand-gathered but the appropriate tool type isn't equipped.
                    # Omit the job from the list.
                    continue
                total_power = tool_power + skill_power

                # Default node extraction calculation
                job_actions = resource["max_health"]
                total_swings = int(np.ceil(job_actions/total_power))
                job_time = swing_speed*total_swings

                # Manually inject despawn times into specific resource ids,
                # which for some reason incorrectly describe a time of 0.0
                # TODO: This previously lived in object_dataclasses ResourceDesc directly
                # but that stopped working. It'd be better to have this live there so it's
                # a single source of truth
                despawn_inject = {
                    1110003: 0.25,
                    2110003: 0.25,
                    3110003: 0.25,
                    4110003: 0.25,
                    5110003: 0.25,
                    6110003: 0.25,
                    509854054: 0.25,
                    826362353: 0.25,
                    1006230316: 0.25,
                    1141184831: 0.25,
                }
                resource["despawn_time"] = despawn_inject.get(job_id,resource["despawn_time"])

                # Handle nodes that only live for a limited amount of time
                # (such as oceanfish nodes)
                if job_time>resource["despawn_time"]*3600 and resource["despawn_time"]!=0.0:
                    job_time = resource["despawn_time"]*3600
                    total_swings = int(np.floor(job_time/swing_speed))
                    job_actions = total_swings*total_power

                job_stamina = recipe["stamina_requirement"]*total_swings
                job_durability = recipe["tool_durability_lost"]*total_swings


                input_stacks = recipe["consumed_item_stacks"]
                job_inputs = self._format_input_stacks(input_stacks)
                for entry in job_inputs:
                    # Probability of input consumption is (believed to be) on a per-swing basis
                    # so quantity and value fields get multiplied accordingly
                    entry[2] = np.round(total_swings*entry[2],4)
                    entry[5] = np.round(total_swings*entry[5],2)

                output_stacks = recipe["extracted_item_stacks"]
                job_outputs = []
                for prob in output_stacks:
                    p = prob[1]
                    outcome = prob[0][1]
                    series = self._format_output_stacks([outcome])
                    for entry in series:
                        # Probability of output result is on a per-hp basis
                        # so quantity and value fields get multiplied accordingly
                        entry[2] = np.round(p*job_actions*entry[2],4)
                        entry[5] = np.round(p*job_actions*entry[5],2)
                    job_outputs += series
                job_outputs.sort(key=lambda x: x[5], reverse=True)

                try:
                    job_cost = sum(i[5] for i in job_inputs)
                except:
                    job_cost = 0
                try:
                    job_gross = sum(o[5] for o in job_outputs)
                except:
                    job_gross = 0
                job_profit = job_gross - job_cost
                job_pfm = 60*job_profit/job_time

                job_passive = False

                job_building = []
                job_xp = []
                
                raw_operation = {
                    "job_id": f"extract_{job_id}",
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
                    "total_power": total_power,
                    "swing_speed": swing_speed,
                    "cost": job_cost,
                    "gross": job_gross,
                    "profit": job_profit,
                    "profit_per_min": job_pfm,
                }
                raw_operations.append(raw_operation)

            # Special handling of oeanfish chumming
            fish_map = {
                "extract_1110002": "extract_1110003",
                "extract_2110002": "extract_2110003",
                "extract_3110002": "extract_3110003",
                "extract_4110002": "extract_4110003",
                "extract_5110002": "extract_5110003",
                "extract_6110002": "extract_6110003",
                "extract_1205481710": "extract_653449777",
                "extract_1049132649": "extract_1534389193",
                "extract_854631002": "extract_1814132892",
                "extract_809093509": "extract_304798021",
            }
            for key in list(fish_map.keys()):
                try:
                    source = next(r for r in raw_operations if r["job_id"]==key)
                    target = next(r for r in raw_operations if r["job_id"]==fish_map[key])
                    source["time_requirement"] += target["time_requirement"]
                    source["stamina_requirement"] += target["stamina_requirement"]
                    source["tool_durability_lost"] += target["tool_durability_lost"]
                    source["output_stacks"] = target["output_stacks"]
                    source["actions_required"] += target["actions_required"]
                    source["total_power"] = target["total_power"]
                    source["swing_speed"] = target["swing_speed"]
                    source["gross"] = target["gross"]
                    source["profit"] = source["gross"] - source["cost"]
                    source["profit_per_min"] = 60*source["profit"]/source["time_requirement"]
                except:
                    # This exception just catches instances where the tool/level is under what's needed for the job
                    # so the job got omitted and isn't inside raw_operations
                    continue

            # Add conversion recipe info to list of raw_operations
            job_type = "Convert"
            conversion_recipes = self.reference_data.get("item_conversion_recipe_desc", [])
            for recipe in conversion_recipes:
                job_id = recipe["id"]

                job_name = recipe["name"]
                long_name = recipe["name"]

                # Skip all conversion recipes that are named "Resolve %"
                if "Resolve" in job_name:
                    continue

                job_time = recipe["time_cost"]
                job_stamina = recipe["stamina_cost"]

                # Lots of weird formatting to do. Because WHY would the conversion recipe
                # stack format be the same as extraction/crafting formats?
                input_stacks = recipe["input_items"]
                for entry in input_stacks:
                    if len(entry)==4:
                        entry.append(1.0)
                job_inputs = self._format_input_stacks(input_stacks)

                output_stacks = [list(recipe["output_item"][1].values())]
                job_outputs = self._format_output_stacks(output_stacks)

                try:
                    job_cost = sum(i[5] for i in job_inputs)
                except:
                    job_cost = 0
                try:
                    job_gross = sum(o[5] for o in job_outputs)
                except:
                    job_gross = 0
                job_profit = job_gross-job_cost

                # Include an epsilon because there are some recipes with job_time = 0
                job_pfm = (job_profit/(job_time+1e-12))*60

                job_hands = recipe["allow_use_hands"]

                # Conceivably, some of these could change in the future
                # but for the time being...
                job_durability = 0
                job_building = []
                job_level = "Any: 1"
                job_tool = []
                job_xp = []
                job_actions = 1
                job_passive = False
                total_power = 1
                swing_speed = 1

                raw_operation = {
                    "job_id": f"convert_{job_id}",
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
                    "total_power": total_power,
                    "swing_speed": swing_speed,
                    "cost": job_cost,
                    "gross": job_gross,
                    "profit": job_profit,
                    "profit_per_min": job_pfm,
                }
                raw_operations.append(raw_operation)

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
                        "total_power": op["total_power"],
                        "swing_speed": op["swing_speed"],
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
                    "total_power": job_data["total_power"],
                    "swing_speed": job_data["swing_speed"],
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
        if hasattr(self, "_buy_orders"):
            self._buy_orders.clear()

        if hasattr(self, "_sell_orders"):
            self._sell_orders.clear()

    def _replace_curly_variables(self, recipe):
        """Fill in the {0}, {1}, {2} variables in names in recipe names"""
        job_name = recipe["name"]
        job_name = job_name.replace("{2}","{1}")

        if "{1}" in job_name:
            try:
                primary_in = recipe["consumed_item_stacks"][0]
                source = self._source_convert(primary_in[2])
                input_name = self.item_lookup_service.get_item_name(
                    primary_in[0],source)
            except:
                input_name = "Unknown Item"
                logging.debug(f"Unresolved input variable in job_id: craft_{recipe["id"]}")
            job_name = job_name.replace("{1}",input_name)
            

        if "{0}" in job_name:
            try:
                primary_out = recipe["crafted_item_stacks"][0]
                source = self._source_convert(primary_out[2])
                output_name = self.item_lookup_service.get_item_name(
                    primary_out[0],source)
            except:
                output_name = "Unknown Item"
                logging.debug(f"Unresolved output variable in job_id: craft_{recipe["id"]}")
            job_name = job_name.replace("{0}",output_name)

        return job_name
    
    def _source_convert(self,type_array):
        """Convert x format type array to 'preferred source' as used by item_lookup_service"""
        if type_array==[1,[]] or type_array==[1,{}]:
            return "cargo_desc"
        elif type_array==[0,[]] or type_array==[0,{}]:
            return "item_desc"
        else:
            logging.error(f"Unrecognized item type array: {type_array}")

    def _level_convert(self,level_array):
        "Convert [x, y] format level array to human-readable 'skill: level' string"
        skill = self._skill_convert(level_array[0])
        level = level_array[1]
        # On the one hand, I'd like 100 to and 1 to not be next to each other
        # On the other hand, that many leading zeros gives me a headache
        #return f"{skill}: {level:03d}"
        return f"{skill}: {level}"
    
    def _rarity_convert(self,rare_array):
        """Convert [x, {}] format rarity array to human-readable string"""
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

    def _skill_convert(self,skill_id):
        """Convert skill id to human readable skill string"""
        skill_list = {
            1: "Any",
            2: "Forestry",
            3: "Carpentry",
            4: "Masonry",
            5: "Mining",
            6: "Smithing",
            7: "Scholar",
            8: "Leatherworking",
            9: "Hunting",
            10: "Tailoring",
            11: "Farming",
            12: "Fishing",
            13: "Cooking",
            14: "Foraging",
            15: "Construction",
            17: "Taming",
            18: "Slayer",
            19: "Merchanting",
            21: "Sailing",
        }
        try:
            return skill_list[skill_id]
        except:
            logging.error(f"Unrecognized skill id: {skill_id}")

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
            row.append(np.round(entry[1]*entry[4],4))

            # Calculate price window
            window = self._get_price_window(entry[0],entry[2])

            # Calculate price to procure materials
            price = self._get_sale_price(window,"buy")

            # Format window for easier reading:
            window = f"{int(np.round(window[0]))} — {int(np.round(window[1]))}"

            row.append(window)
            row.append(price)

            # Calculate row's contribution to overall job value
            row.append(np.round(row[2]*price,2))

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
            entry2[2] = np.round(q_sum,4)

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
            # Calculate price to liquidate materials
            price = self._get_sale_price(window,"sell")

            # Format window for easier reading:
            window = f"{int(np.round(window[0]))} — {int(np.round(window[1]))}"
            row.append(window)
            row.append(price)

            # Calculate row's contribution to overall job value
            row.append(np.round(entry[2]*price,2))

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
            item_list = next(i for i in self.reference_data.get("item_list_desc", []) if i["id"]==item_list_id)
            possibilities = item_list["possibilities"]
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
        if item_type==[0,[]] or item_type==[0,{}]:
            item_type = 0
        elif item_type==[1,[]] or item_type==[1,{}]:
            item_type = 1
        else:
            logging.error(f"Unrecognized item, id: {item_id}, type array: {item_type}")

        buy_fallback = self.settings.get("market_strategies",{}).get("buy_fallback_value",0)
        sell_fallback = self.settings.get("market_strategies",{}).get("sell_fallback_value",1e6)

        # TODO: Introduce conditions to allow for supply sale to claim?
        try:
            buy_ids = [b for b in self._buy_orders.values() if b.item_id==item_id]
            buy_types = [b for b in buy_ids if b.item_type==item_type]
            max_buy = max(buy_types, key=lambda x:x.price_threshold).price_threshold
        except:
            max_buy = buy_fallback

        try:
            sell_ids = [s for s in self._sell_orders.values() if s.item_id==item_id]
            sell_types = [s for s in sell_ids if s.item_type==item_type]
            min_sell = min(sell_types, key=lambda x:x.price_threshold).price_threshold
        except:
            min_sell = sell_fallback

        # Special handling hard-coding
        # A lot of this could probably be handled with traveler_trade_order_desc, but, alas
        if item_type == 0:
            item = self.item_lookup_service.lookup_item_by_id(item_id,"item_desc")
            if "Recipe: " in item["name"]:
                # Specify that recipes can't be bought or sold
                max_buy=0;  min_sell=0
            elif item_id == 1:
                # Hex coins have a "price" floor and cap
                max_buy=np.max([1,max_buy]);  min_sell = np.min([1,min_sell])
            elif item_id == 4000:
                # Cooling Energy price cap
                min_sell = np.min([min_sell,1000])
            elif item_id == 4001:
                # Warming Energy price cap
                min_sell = np.min([min_sell,2500])
            elif item_id == 4002:
                # Ripped Notes price cap
                min_sell = np.min([min_sell,1000])
            elif item_id == 4003:
                # Shredded Notes price cap
                min_sell = np.min([min_sell,2500])
            elif item_id == 72520590:
                # Heart Wiring price cap
                min_sell = np.min([min_sell,500])
            elif item_id == 148829439:
                # Owl Egg price cap
                min_sell = np.min([min_sell,1000])
            elif item_id == 805422378:
                # Metalworking Flux fixed price (not able to be put on market)
                max_buy=10;  min_sell = 10
            elif item_id == 1009634974:
                # Conductive Frame price cap
                min_sell = np.min([min_sell,10000])
            elif item_id == 1223093023:
                # Hideworking Salt fixed price (not able to be put on market)
                max_buy=10;  min_sell = 10
            elif item_id == 1463057734:
                # Clothmaker's Mordant fixed price (not able to be put on market)
                max_buy=10;  min_sell = 10
            elif item_id == 1763886534:
                # Woodworking Sandpaper fixed price (not able to be put on market)
                max_buy=2;  min_sell = 2
            elif item_id == 1857742253:
                # Brickworking Binding Ash fixed price (not able to be put on market)
                max_buy=10;  min_sell = 10
        elif item_type == 1:
            if item_id == 501736939:
                # Bottomless Sack of Hex Coins price cap
                min_sell = np.min([min_sell,10000])
            elif item_id == 983297878:
                # Fair Sack of Hex Coins price cap
                min_sell = np.min([min_sell,500])
            elif item_id == 1290464936:
                # Small Sack of Hex Coins price cap
                min_sell = np.min([min_sell,100])
            elif item_id == 1955158156:
                # Large Sack of Hex Coins price cap
                min_sell = np.min([min_sell,1000])
        
        return (max_buy, min_sell)
    
    def _get_sale_price(self,price_window,sale_method):
        """Return a transaction price based on the price window, transaction type, and user strategy settings."""
        # This comes across as needlessly verbose and redundant
        # but there's enough small differences in default values, order of operations, and rounding
        # that this seemed simplest at the time.
        try:
            strat = "No Strategy"
            if sale_method == "buy":
                strat = self.settings.get("market_strategies",{}).get("buy_strat_method","undercut")
                if strat == "undercut":
                    value = self.settings.get("market_strategies",{}).get("buy_strat_value",1.0)
                    price = price_window[1]-value
                elif strat == "overbid":
                    value = self.settings.get("market_strategies",{}).get("buy_strat_value",0.0)
                    price = price_window[0]+value
                elif strat == "fractional":
                    value = self.settings.get("market_strategies",{}).get("buy_strat_value",50)
                    price = ((price_window[1]-price_window[0])*value/100.0) + price_window[0]
                else:
                    raise ValueError
                
                price = np.min([price_window[1],price])
                price = np.max([price_window[0],price])
                return int(np.ceil(price))
            elif sale_method == "sell":
                strat = self.settings.get("market_strategies",{}).get("sell_strat_method","fractional")
                if strat == "undercut":
                    value = self.settings.get("market_strategies",{}).get("sell_strat_value",0.0)
                    price = price_window[1]-value
                elif strat == "overbid":
                    value = self.settings.get("market_strategies",{}).get("sell_strat_value",1.0)
                    price = price_window[0]+value
                elif strat == "fractional":
                    value = self.settings.get("market_strategies",{}).get("sell_strat_value",50)
                    price = ((price_window[1]-price_window[0])*value/100.0) + price_window[0]
                else:
                    raise ValueError
                
                price = np.max([price_window[0],price])
                price = np.min([price_window[1],price])
                return int(np.floor(price))
            else:
                raise ValueError
        except:
            logging.error(f"Unable to process {strat} - {sale_method} transaction with price window: {price_window}.")
    
    
    def _load_settings(self):
        """Load settings with default values."""
        # TODO: Remove redundancy
        # Currently, this is just a direct copy-paste from settings_window.py
        # It would be better to reference a single common true method,
        # but I couldn't find a way to call the function from SettingsWindow
        # without instancing a whole new window popup
        try:
            # Default settings structure
            default_settings = {
                "notifications": {
                    "passive_crafts_enabled": True,
                    "passive_crafts_sound": "system_default",
                    "active_crafts_enabled": True,
                    "active_crafts_sound": "system_default",
                    "stamina_recharged_enabled": True,
                    "stamina_recharged_sound": "system_default",
                },
                "market_strategies": {
                    "buy_strat_method": "fractional",
                    "sell_strat_method": "undercut",
                    "buy_strat_value": 5.0,
                    "sell_strat_value": 1.0,
                    "sell_fallback_value": 1000000.0,
                    "buy_fallback_value": 0.0
                    },
                "debug": {"show_test_notification": True},
            }

            # Load from player_data.json
            try:
                file_path = get_user_data_path("player_data.json")
                with open(file_path, "r") as f:
                    player_data = json.load(f)

                # Extract settings from player_data, merge with defaults
                saved_settings = player_data.get("settings", {})
                if saved_settings:
                    # Deep merge: update defaults with saved settings
                    for category, options in saved_settings.items():
                        if category in default_settings and isinstance(options, dict):
                            default_settings[category].update(options)
                        else:
                            default_settings[category] = options

                logging.debug("Settings loaded from player_data.json")

            except FileNotFoundError:
                logging.info("No player_data.json found, using default settings")
            except json.JSONDecodeError:
                logging.warning("player_data.json is malformed, using default settings")
            except Exception as e:
                logging.error(f"Error reading player_data.json: {e}, using defaults")

            return default_settings
        except Exception as e:
            logging.error(f"Error loading settings: {e}")
            return {
                "notifications": {
                    "passive_crafts_enabled": True,
                    "passive_crafts_sound": "system_default",
                    "active_crafts_enabled": True,
                    "active_crafts_sound": "system_default",
                    "stamina_recharged_enabled": True,
                    "stamina_recharged_sound": "system_default",
                },
                "debug": {"show_test_notification": True},
            }