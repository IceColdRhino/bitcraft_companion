"""
Tasks processor for handling traveler_task_state table updates.
"""

import json
import logging
import threading
import time
from datetime import datetime

from app.models import TravelerTaskState
from .base_processor import BaseProcessor


class TasksProcessor(BaseProcessor):
    """
    Processes traveler_task_state table updates from SpacetimeDB.

    Handles both real-time transactions and batch subscription updates
    for traveler task changes.
    """

    def __init__(self, data_queue, services, reference_data):
        """Initialize TasksProcessor with proper cache setup."""
        super().__init__(data_queue, services, reference_data)

        # Initialize task caches to ensure they exist for transactions
        self._task_states = {}
        self._task_descriptions = {}
        self._player_state = {}

        # Reset buffering to handle race conditions during task resets
        self._reset_in_progress = False
        self._reset_timestamp = None
        self._reset_tables_updated = set()
        self._buffered_ui_update = False

        # Task timer data from traveler_task_loop_timer
        self._task_timer_data = {}

        # Exponential backoff retry mechanism for task timer failures
        self._retry_count = 0
        self._max_retries = 5
        self._base_delay = 5  # seconds
        self._max_delay = 60  # seconds
        self._retry_timer = None
        self._retry_in_progress = False

    def get_table_names(self):
        """Return list of table names this processor handles."""
        return ["traveler_task_state", "traveler_task_desc", "player_state"]

    def process_transaction(self, table_update, reducer_name, timestamp):
        """
        Handle traveler_task_state transactions.

        Process incremental changes and update cached data without wiping UI.
        """
        try:
            table_name = table_update.get("table_name", "")
            updates = table_update.get("updates", [])

            # Track if we need to refresh UI
            data_changed = False
            completed_tasks = []

            for update in updates:
                inserts = update.get("inserts", [])
                deletes = update.get("deletes", [])

                if inserts or deletes:
                    logging.debug(f"TASK TRANSACTION: {len(inserts)} inserts, {len(deletes)} deletes - {reducer_name}")
                    data_changed = True

                    # Handle different table types
                    if table_name == "traveler_task_state":
                        self._process_task_state_transaction(update, completed_tasks)
                    elif table_name == "traveler_task_desc":
                        self._process_task_desc_transaction(update)
                    elif table_name == "player_state":
                        self._process_player_state_transaction(update, reducer_name)

            # Log task completions with safe encoding
            for completed_task in completed_tasks:
                logging.debug(f"[TasksProcessor] Task {completed_task['task_id']} completed via {completed_task['reducer_name']}")

            # Check if this looks like a reset (large number of operations)
            total_operations = sum(len(update.get("inserts", [])) + len(update.get("deletes", [])) for update in updates)
            if total_operations >= 10:  # Reset threshold
                self._handle_reset_start(table_name)

            # Only refresh UI if data actually changed and we have cached data to send
            if data_changed:
                self._refresh_tasks(table_name)

        except Exception as e:
            logging.error(f"Error handling tasks transaction: {e}")

    def process_subscription_with_context(self, table_update, is_initial=False):
        """
        Handle subscription updates with context about whether it's InitialSubscription.
        This allows us to distinguish between InitialSubscription and regular SubscriptionUpdate.
        """
        # Store the context for use in processing methods
        self._current_subscription_context = {"is_initial": is_initial}
        try:
            # Call the regular subscription processing
            self.process_subscription(table_update)
        finally:
            # Clean up context
            self._current_subscription_context = None

    def process_subscription(self, table_update):
        """
        Handle traveler_task_state, traveler_task_desc, and player_state subscription updates.
        Cache all data types and combine them for UI.
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
                logging.debug(f"No rows in {table_name} subscription update")
                return

            logging.debug(f"TASK SUBSCRIPTION: Processing {len(table_rows)} rows from {table_name}")

            # Handle different table types
            if table_name == "traveler_task_state":
                self._process_task_state_data(table_rows)
            elif table_name == "traveler_task_desc":
                self._process_task_desc_data(table_rows)
            elif table_name == "player_state":
                self._process_player_state_data(table_rows)

            # Try to send formatted tasks if we have both data types
            self._send_tasks_update()

        except Exception as e:
            logging.error(f"Error handling tasks subscription: {e}")

    def _refresh_tasks(self, table_name=None):
        """
        Send current cached tasks data to UI instead of wiping it.
        Called during transactions to update UI without losing data.
        """
        try:
            # Check if we should buffer this update during a reset
            if self._reset_in_progress:
                if table_name:
                    self._reset_tables_updated.add(table_name)
                    logging.debug(f"TASK RESET: Table {table_name} updated, buffering UI refresh")

                # Check if reset is complete (both key tables updated)
                if "traveler_task_state" in self._reset_tables_updated and "traveler_task_desc" in self._reset_tables_updated:
                    logging.debug("TASK RESET: Both task tables updated, completing reset")
                    self._complete_reset()
                    return
                else:
                    # Mark that we need to update UI once reset completes
                    self._buffered_ui_update = True
                    logging.debug(f"TASK RESET: Buffering update, waiting for remaining tables")
                    return

            # Check for timeout during reset
            if self._reset_in_progress and self._reset_timestamp:
                time_since_reset = time.time() - self._reset_timestamp
                if time_since_reset > 1.0:  # 1 second timeout
                    logging.warning(f"TASK RESET: Timeout after {time_since_reset:.3f}s, forcing UI update")
                    self._complete_reset()
                    return

            # Normal UI refresh (not during reset)
            self._do_ui_refresh()

        except Exception as e:
            logging.error(f"Error refreshing tasks: {e}")

    def _process_task_state_data(self, task_state_rows):
        """
        Process traveler_task_state data to store task assignments with traveler info.
        """
        try:
            if not hasattr(self, "_task_states") or self._task_states is None:
                self._task_states = {}

            for row in task_state_rows:
                try:
                    # Create TravelerTaskState dataclass instance
                    task_state = TravelerTaskState.from_dict(row)

                    # Store using entity_id as key (unique per task assignment) instead of task_id
                    # This fixes the Rumbagh 4-task issue where multiple entity_ids had same task_id
                    self._task_states[task_state.entity_id] = {
                        "entity_id": task_state.entity_id,
                        "player_entity_id": task_state.player_entity_id,
                        "traveler_id": task_state.traveler_id,
                        "task_id": task_state.task_id,  # Include task_id for task description lookup
                        "completed": task_state.completed,
                    }
                except (ValueError, TypeError) as e:
                    logging.debug(f"Failed to process task state row: {e}")
                    continue

        except Exception as e:
            logging.error(f"Error processing task state data: {e}")
        
        self._send_tasks_update()

    def _process_task_desc_data(self, task_desc_rows):
        """
        Process traveler_task_desc data to store task descriptions.
        """
        try:
            if not hasattr(self, "_task_descriptions") or self._task_descriptions is None:
                self._task_descriptions = {}

            for row in task_desc_rows:
                task_id = row.get("id")
                if task_id:
                    self._task_descriptions[task_id] = {
                        "description": row.get("description", f"Task {task_id}"),
                        "level_requirement": row.get("level_requirement", {}),
                        "required_items": row.get("required_items", []),
                        "rewarded_items": row.get("rewarded_items", []),
                        "rewarded_experience": row.get("rewarded_experience", {}),
                    }

        except Exception as e:
            logging.error(f"Error processing task description data: {e}")

    def _process_player_state_data(self, player_state_rows):
        """
        Process player_state data (kept for compatibility but timer now comes from traveler_task_loop_timer).
        """
        try:
            if not hasattr(self, "_player_state") or self._player_state is None:
                self._player_state = {}

            for row in player_state_rows:
                try:
                    entity_id = row.get("entity_id")
                    if entity_id:
                        # Note: PlayerActionState dataclass exists but player_state table structure
                        # doesn't match it directly. Keep existing logic for now.
                        self._player_state[entity_id] = {
                            "traveler_tasks_expiration": row.get("traveler_tasks_expiration", 0),
                        }
                        logging.debug(f"[TasksProcessor] Cached player_state for entity {entity_id}")
                except Exception as e:
                    logging.debug(f"Failed to process player state row: {e}")
                    continue

        except Exception as e:
            logging.error(f"Error processing player state data: {e}")

    def _send_tasks_update(self):
        """
        Send tasks update by combining state and description data.
        """
        try:
            if not (hasattr(self, "_task_states") and self._task_states):
                return

            if not (hasattr(self, "_task_descriptions") and self._task_descriptions):
                logging.warning(f"[TasksProcessor] Task descriptions not available. Has descriptions: {hasattr(self, '_task_descriptions')}, Count: {len(self._task_descriptions) if hasattr(self, '_task_descriptions') else 0}")
                return

            # Format task data using cached data
            formatted_tasks = self._format_combined_task_data()

            # Send to UI
            self._queue_update("tasks_update", formatted_tasks)

        except Exception as e:
            logging.error(f"Error sending tasks update: {e}")

    def _format_combined_task_data(self):
        """
        Format task data by combining task states and descriptions with traveler names.

        Returns:
            Formatted task data grouped by traveler for UI
        """
        try:
            # Get traveler reference data
            traveler_names = self._get_traveler_names()

            # Group tasks by traveler
            travelers = {}

            # Combine task state and description data
            # Now iterating by entity_id (unique task instances) instead of task_id (task types)
            for entity_id, task_state in self._task_states.items():
                task_id = task_state.get("task_id", 0)  # Get task_id from task_state for description lookup
                task_desc = self._task_descriptions.get(task_id, {})
                traveler_id = task_state.get("traveler_id", 0)

                if traveler_id not in travelers:
                    traveler_name = traveler_names.get(traveler_id, f"Traveler {traveler_id}")
                    travelers[traveler_id] = {
                        "traveler_id": traveler_id,
                        "traveler": traveler_name,
                        "operations": [],
                        "entity_ids_seen": set(),  # Track unique entity IDs to prevent real duplicates
                    }

                # Check for duplicate entity_id for this traveler (should never happen but good safety check)
                if entity_id in travelers[traveler_id]["entity_ids_seen"]:
                    traveler_name = traveler_names.get(traveler_id, f"Traveler {traveler_id}")
                    safe_traveler_name = str(traveler_name).encode("ascii", "replace").decode("ascii")
                    logging.warning(
                        f"[TasksProcessor] DUPLICATE ENTITY DETECTED: {safe_traveler_name} has duplicate entity_id {entity_id}"
                    )
                    continue  # Skip duplicate entity (should be rare)

                travelers[traveler_id]["entity_ids_seen"].add(entity_id)

                # Parse required items with item details from reference data
                required_items_formatted = self._format_required_items(task_desc.get("required_items", []))

                # Combine state and description data in the format the tab expects
                task_completed = task_state.get("completed", False)
                task_info = {
                    "task_id": task_id,
                    "entity_id": entity_id,  # Use the entity_id we're iterating over
                    "task_description": task_desc.get("description", f"Task {task_id}"),
                    "status": "✅" if task_completed else "❌",
                    "level_requirement": task_desc.get("level_requirement", {}),
                    "required_items_detailed": required_items_formatted,
                    "rewarded_items": task_desc.get("rewarded_items", []),
                    "rewarded_experience": task_desc.get("rewarded_experience", {}),
                }
                travelers[traveler_id]["operations"].append(task_info)

            # Add completion counts and status for each traveler
            for traveler_data in travelers.values():
                operations = traveler_data["operations"]
                completed_count = sum(1 for op in operations if op.get("status") == "✅")
                total_count = len(operations)
                traveler_name = traveler_data.get("traveler", "Unknown")

                traveler_data["completed_count"] = completed_count
                traveler_data["total_count"] = total_count
                traveler_data["complete"] = "✅" if completed_count == total_count else "❌"

                traveler_data.pop("entity_ids_seen", None)

                # Safe logging without Unicode characters to prevent encoding issues
                completion_status_str = "complete" if completed_count == total_count else "incomplete"
                # Ensure traveler name is safely encoded for logging
                safe_traveler_name = str(traveler_name).encode("ascii", "replace").decode("ascii") if traveler_name else "Unknown"
                logging.debug(
                    f"[TasksProcessor] Traveler {safe_traveler_name}: {completed_count}/{total_count} tasks {completion_status_str}"
                )

            return list(travelers.values())

        except Exception as e:
            logging.error(f"Error formatting combined task data: {e}")
            return {"active_tasks": [], "pending_tasks": [], "completed_tasks": []}

    def _get_traveler_names(self):
        """
        Get traveler names from reference data.

        Returns:
            Dictionary mapping traveler_id to traveler_name
        """
        try:
            traveler_names = {}

            # Get traveler data from reference data (passed to processor)
            traveler_data = self.reference_data.get("npc_desc", [])
            if traveler_data:
                for traveler in traveler_data:
                    npc_type = traveler.get("npc_type")
                    name = traveler.get("name")
                    if npc_type and name:
                        traveler_names[npc_type] = name
            else:
                logging.warning("No traveler reference data found")

            return traveler_names

        except Exception as e:
            logging.error(f"Error getting traveler names: {e}")
            return {}

    def _format_required_items(self, required_items_raw):
        """
        Format required items list with item details from reference data.

        Args:
            required_items_raw: Raw required items list like [[1170001, 10, [0, []], [0, 0]]]

        Returns:
            List of formatted required items with names, tiers, tags
        """
        try:
            if not required_items_raw:
                return []

            # Use shared item lookup service
            formatted_items = []

            for item_raw in required_items_raw:
                if isinstance(item_raw, list) and len(item_raw) >= 2:
                    item_id = item_raw[0]
                    quantity = item_raw[1]

                    # Look up item details using shared lookup service
                    # Use best source determination for task items
                    table_source = self.item_lookup_service.determine_best_source_for_item(item_id, "inventory")
                    item_info = self.item_lookup_service.lookup_item_by_id(item_id, table_source)
                    item_name = item_info.get("name", f"Unknown Item {item_id}") if item_info else f"Unknown Item {item_id}"
                    item_tier = item_info.get("tier", 0) if item_info else 0
                    item_tag = item_info.get("tag", "") if item_info else ""

                    formatted_item = {
                        "item_id": item_id,
                        "item_name": item_name,
                        "quantity": quantity,
                        "tier": item_tier,
                        "tag": item_tag,
                    }
                    formatted_items.append(formatted_item)

            return formatted_items

        except Exception as e:
            logging.error(f"Error formatting required items: {e}")
            return []


    def _validate_task_data(self, entity_id, player_entity_id, traveler_id, task_id, completed):
        """
        Validate parsed task transaction data.

        Args:
            entity_id: Entity ID (should be a number)
            player_entity_id: Player entity ID (should be a number)
            traveler_id: Traveler ID (should be a number)
            task_id: Task ID (should be a number)
            completed: Completion status (should be boolean)

        Returns:
            bool: True if data is valid, False otherwise
        """
        try:
            # Check if required fields are present and have correct types
            if entity_id is None or not isinstance(entity_id, (int, float)):
                logging.debug(f"[TasksProcessor] Invalid entity_id: {entity_id} ({type(entity_id)})")
                return False

            if player_entity_id is None or not isinstance(player_entity_id, (int, float)):
                logging.debug(f"[TasksProcessor] Invalid player_entity_id: {player_entity_id} ({type(player_entity_id)})")
                return False

            if traveler_id is None or not isinstance(traveler_id, (int, float)):
                logging.debug(f"[TasksProcessor] Invalid traveler_id: {traveler_id} ({type(traveler_id)})")
                return False

            if task_id is None or not isinstance(task_id, (int, float)):
                logging.debug(f"[TasksProcessor] Invalid task_id: {task_id} ({type(task_id)})")
                return False

            if not isinstance(completed, bool):
                logging.debug(f"[TasksProcessor] Invalid completed status: {completed} ({type(completed)})")
                return False

            return True

        except Exception as e:
            logging.error(f"Error validating task data: {e}")
            return False

    def _handle_reset_start(self, table_name):
        """
        Handle the start of a task reset sequence.
        """
        try:
            if not self._reset_in_progress:
                logging.debug(f"TASK RESET: Detected reset starting with table {table_name}")
                self._reset_in_progress = True
                self._reset_timestamp = time.time()
                self._reset_tables_updated.clear()
                self._buffered_ui_update = False

            # Add this table to the updated set
            if table_name:
                self._reset_tables_updated.add(table_name)

        except Exception as e:
            logging.error(f"Error handling reset start: {e}")

    def _complete_reset(self):
        """
        Complete the reset sequence and refresh UI.
        """
        try:
            logging.debug("TASK RESET: Completing reset and refreshing UI")

            # Clear reset state
            self._reset_in_progress = False
            self._reset_timestamp = None
            self._reset_tables_updated.clear()

            # Perform the UI refresh if it was buffered
            if self._buffered_ui_update:
                self._buffered_ui_update = False
                self._do_ui_refresh()

        except Exception as e:
            logging.error(f"Error completing reset: {e}")

    def _do_ui_refresh(self):
        """
        Actually perform the UI refresh (extracted from original _refresh_tasks).
        """
        try:
            has_task_states = hasattr(self, "_task_states") and self._task_states
            has_task_descriptions = hasattr(self, "_task_descriptions") and self._task_descriptions


            # Send current cached task data if we have task states (descriptions can be fetched if missing)
            if has_task_states:
                # Only proceed if we have task descriptions (should come from subscriptions)
                if has_task_descriptions:
                    formatted_tasks = self._format_combined_task_data()
                    logging.debug(f"TASK UI UPDATE: Sending {len(formatted_tasks)} travelers to UI")
                    self._queue_update("tasks_update", formatted_tasks, {"transaction_update": True})
                    logging.debug("Refreshed tasks UI with cached data")
                else:
                    logging.warning("TASK REFRESH: Missing task descriptions")
            else:
                # Only send empty data if we truly have no cached data
                logging.warning(f"TASK REFRESH BLOCKED: task_states={has_task_states}, task_descriptions={has_task_descriptions}")

        except Exception as e:
            logging.error(f"Error in UI refresh: {e}")

    def clear_cache(self):
        """Clear cached tasks data when switching claims."""
        super().clear_cache()

        # Clear claim-specific cached data
        if hasattr(self, "_task_states"):
            self._task_states.clear()

        if hasattr(self, "_task_descriptions"):
            self._task_descriptions.clear()

        if hasattr(self, "_player_state"):
            self._player_state.clear()

        # Clear reset state
        self._reset_in_progress = False
        self._reset_timestamp = None
        self._reset_tables_updated.clear()
        self._buffered_ui_update = False

        # Clear timer data
        if hasattr(self, "_task_timer_data"):
            self._task_timer_data.clear()

        # Reset timer state for new claim
        self._current_task_expiration = 0

    def _process_task_state_transaction(self, update, completed_tasks):
        """
        Process traveler_task_state transaction update.
        """
        try:
            inserts = update.get("inserts", [])
            deletes = update.get("deletes", [])

            # Collect all deletes and inserts by entity_id to handle replacements properly
            # Changed from task_id to entity_id to match the new storage method
            entity_deletes = {}
            entity_inserts = {}

            # Parse deletes first
            for delete_str in deletes:
                try:

                    if isinstance(delete_str, str):
                        delete_data = json.loads(delete_str)
                    else:
                        delete_data = list(delete_str)

                    if isinstance(delete_data, list) and len(delete_data) >= 5:
                        entity_id = delete_data[0] if len(delete_data) > 0 else None  # entity_id is first field
                        task_id = delete_data[3] if len(delete_data) > 3 else None  # task_id for logging
                        if entity_id:
                            entity_deletes[entity_id] = delete_data
                            logging.debug(f"[TasksProcessor] Collected delete for entity_id={entity_id}, task_id={task_id}")

                except Exception as e:
                    logging.warning(f"Error parsing task transaction delete: {e}")

            # Parse inserts
            for insert_str in inserts:
                try:

                    if isinstance(insert_str, str):
                        task_data = json.loads(insert_str)
                    else:
                        task_data = list(insert_str)

                    if isinstance(task_data, list) and len(task_data) >= 5:
                        entity_id = task_data[0] if len(task_data) > 0 else None  # entity_id is first field
                        task_id = task_data[3] if len(task_data) > 3 else None  # task_id for logging
                        if entity_id:
                            entity_inserts[entity_id] = task_data
                            logging.debug(f"[TasksProcessor] Collected insert for entity_id={entity_id}, task_id={task_id}")

                except Exception as e:
                    logging.warning(f"Error parsing task transaction insert: {e}")

            # Process as replacements (delete + insert = update) or pure operations
            all_entity_ids = set(entity_deletes.keys()) | set(entity_inserts.keys())

            for entity_id in all_entity_ids:
                has_delete = entity_id in entity_deletes
                has_insert = entity_id in entity_inserts

                if has_delete and has_insert:
                    # Update task with new data
                    task_data = entity_inserts[entity_id]
                    entity_id_from_data = task_data[0] if len(task_data) > 0 else None
                    player_entity_id = task_data[1] if len(task_data) > 1 else None
                    traveler_id = task_data[2] if len(task_data) > 2 else None
                    task_id = task_data[3] if len(task_data) > 3 else None
                    completed = task_data[4] if len(task_data) > 4 else False

                    logging.debug(
                        f"[TasksProcessor] REPLACEMENT for entity_id={entity_id}, task_id={task_id}: completed={completed}"
                    )

                    # Validate parsed data
                    if not self._validate_task_data(entity_id_from_data, player_entity_id, traveler_id, task_id, completed):
                        logging.warning(f"[TasksProcessor] Invalid replacement data, skipping: entity_id={entity_id}")
                        continue

                    # Update cached task state using entity_id as key
                    if hasattr(self, "_task_states"):
                        old_completed = self._task_states.get(entity_id, {}).get("completed", False)

                        self._task_states[entity_id] = {
                            "entity_id": entity_id_from_data,
                            "player_entity_id": player_entity_id,
                            "traveler_id": traveler_id,
                            "task_id": task_id,
                            "completed": completed,
                        }

                        # Detect newly completed tasks
                        if not old_completed and completed:
                            completed_tasks.append(
                                {"task_id": task_id, "traveler_id": traveler_id, "reducer_name": "task_update"}
                            )

                elif has_insert and not has_delete:
                    # New task
                    task_data = entity_inserts[entity_id]
                    entity_id_from_data = task_data[0] if len(task_data) > 0 else None
                    player_entity_id = task_data[1] if len(task_data) > 1 else None
                    traveler_id = task_data[2] if len(task_data) > 2 else None
                    task_id = task_data[3] if len(task_data) > 3 else None
                    completed = task_data[4] if len(task_data) > 4 else False

                    logging.debug(f"[TasksProcessor] NEW TASK entity_id={entity_id}, task_id={task_id}: completed={completed}")

                    # Validate and add new task
                    if self._validate_task_data(entity_id_from_data, player_entity_id, traveler_id, task_id, completed):
                        if hasattr(self, "_task_states"):
                            self._task_states[entity_id] = {
                                "entity_id": entity_id_from_data,
                                "player_entity_id": player_entity_id,
                                "traveler_id": traveler_id,
                                "task_id": task_id,
                                "completed": completed,
                            }

                elif has_delete and not has_insert:
                    # Remove task completely
                    delete_data = entity_deletes[entity_id]
                    task_id = delete_data[3] if len(delete_data) > 3 else None  # Get task_id for logging
                    logging.debug(f"[TasksProcessor] DELETE entity_id={entity_id}, task_id={task_id}")
                    if hasattr(self, "_task_states") and entity_id in self._task_states:
                        del self._task_states[entity_id]

        except Exception as e:
            logging.error(f"Error processing task state transaction: {e}")

    def _process_task_desc_transaction(self, update):
        """
        Process traveler_task_desc transaction update.
        """
        try:
            inserts = update.get("inserts", [])
            deletes = update.get("deletes", [])

            # Collect all deletes and inserts by task_id
            desc_deletes = {}
            desc_inserts = {}

            # Parse deletes first
            for delete_str in deletes:
                try:

                    if isinstance(delete_str, str):
                        delete_data = json.loads(delete_str)
                    else:
                        delete_data = list(delete_str)

                    if isinstance(delete_data, list) and len(delete_data) >= 1:
                        task_id = delete_data[0] if len(delete_data) > 0 else None  # id is first field
                        if task_id:
                            desc_deletes[task_id] = delete_data
                            logging.debug(f"[TasksProcessor] Collected desc delete for task_id={task_id}")

                except Exception as e:
                    logging.warning(f"Error parsing task desc transaction delete: {e}")

            # Parse inserts
            for insert_str in inserts:
                try:

                    if isinstance(insert_str, str):
                        desc_data = json.loads(insert_str)
                    else:
                        desc_data = dict(insert_str)

                    # Handle both dict and list formats
                    if isinstance(desc_data, dict):
                        task_id = desc_data.get("id")
                    elif isinstance(desc_data, list) and len(desc_data) >= 1:
                        task_id = desc_data[0]
                    else:
                        continue

                    if task_id:
                        desc_inserts[task_id] = desc_data
                        logging.debug(f"[TasksProcessor] Collected desc insert for task_id={task_id}")

                except Exception as e:
                    logging.warning(f"Error parsing task desc transaction insert: {e}")

            # Process descriptions
            all_desc_ids = set(desc_deletes.keys()) | set(desc_inserts.keys())

            for task_id in all_desc_ids:
                has_delete = task_id in desc_deletes
                has_insert = task_id in desc_inserts

                if has_delete and has_insert:
                    # Update description
                    desc_data = desc_inserts[task_id]
                    logging.debug(f"[TasksProcessor] DESC REPLACEMENT for task_id={task_id}")
                    self._update_task_description_cache(task_id, desc_data)

                elif has_insert and not has_delete:
                    # New description
                    desc_data = desc_inserts[task_id]
                    logging.debug(f"[TasksProcessor] NEW DESC for task_id={task_id}")
                    self._update_task_description_cache(task_id, desc_data)

                elif has_delete and not has_insert:
                    # Remove description
                    logging.debug(f"[TasksProcessor] DELETE DESC for task_id={task_id}")
                    if hasattr(self, "_task_descriptions") and task_id in self._task_descriptions:
                        del self._task_descriptions[task_id]

        except Exception as e:
            logging.error(f"Error processing task desc transaction: {e}")

    def _update_task_description_cache(self, task_id, desc_data):
        """
        Update task description cache with new data.
        """
        try:
            if not hasattr(self, "_task_descriptions"):
                self._task_descriptions = {}

            if isinstance(desc_data, dict):
                self._task_descriptions[task_id] = {
                    "description": desc_data.get("description", f"Task {task_id}"),
                    "level_requirement": desc_data.get("level_requirement", {}),
                    "required_items": desc_data.get("required_items", []),
                    "rewarded_items": desc_data.get("rewarded_items", []),
                    "rewarded_experience": desc_data.get("rewarded_experience", {}),
                }
            else:
                # Fallback for list format - create basic entry
                self._task_descriptions[task_id] = {
                    "description": f"Task {task_id}",
                    "level_requirement": {},
                    "required_items": [],
                    "rewarded_items": [],
                    "rewarded_experience": {},
                }

        except Exception as e:
            logging.error(f"Error updating task description cache for task {task_id}: {e}")

    def _process_player_state_transaction(self, update, reducer_name):
        """
        Process player_state transaction update.
        Handles real-time updates to traveler_tasks_expiration from transaction messages.
        """
        try:
            inserts = update.get("inserts", [])
            deletes = update.get("deletes", [])

            logging.debug(
                f"[TasksProcessor] PLAYER_STATE TRANSACTION: {len(inserts)} inserts, {len(deletes)} deletes - {reducer_name}"
            )

            for insert_str in inserts:
                try:

                    if isinstance(insert_str, str):
                        player_data = json.loads(insert_str)
                    else:
                        player_data = dict(insert_str)

                    entity_id = player_data.get("entity_id")
                    traveler_tasks_expiration = player_data.get("traveler_tasks_expiration", 0)

                    if entity_id and traveler_tasks_expiration > 0:
                        # Update cached player state
                        if not hasattr(self, "_player_state"):
                            self._player_state = {}

                        self._player_state[entity_id] = {
                            "traveler_tasks_expiration": traveler_tasks_expiration,
                        }

                        current_time = time.time()
                        time_diff = current_time - traveler_tasks_expiration
                        hours_old = time_diff / 3600

                        expiration_readable = datetime.fromtimestamp(traveler_tasks_expiration).strftime("%Y-%m-%d %H:%M:%S")
                        current_readable = datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S")

                        logging.debug(f"[TasksProcessor] TasksProcessor TRANSACTION player_state:")
                        logging.debug(f"[TasksProcessor]   Entity ID: {entity_id}")
                        logging.debug(f"[TasksProcessor]   Raw expiration: {traveler_tasks_expiration}")
                        logging.debug(f"[TasksProcessor]   Expiration time: {expiration_readable}")
                        logging.debug(f"[TasksProcessor]   Current time: {current_readable}")
                        logging.debug(
                            f"[TasksProcessor]   Age: {hours_old:.2f} hours {'(STALE!)' if hours_old > 4.5 else '(fresh)'}"
                        )
                        logging.debug(f"[TasksProcessor]   Reducer: {reducer_name}")

                        logging.debug(
                            f"[TasksProcessor] TRANSACTION - Updated player_state expiration: {traveler_tasks_expiration} via {reducer_name}"
                        )

                        # Send transaction-based update to UI
                        self._queue_update(
                            "player_state_update",
                            {
                                "traveler_tasks_expiration": traveler_tasks_expiration,
                                "is_initial_subscription": False,
                                "source": "transaction",
                                "reducer_name": reducer_name,
                            },
                        )

                except Exception as e:
                    logging.warning(f"Error parsing player state transaction insert: {e}")

        except Exception as e:
            logging.error(f"Error processing player state transaction: {e}")

    def load_initial_task_data(self):
        """
        Load initial task timer data using one-off query.
        Called during processor initialization.
        """
        try:
            self.load_task_timer_data(is_initial=True)
            logging.debug("[TasksProcessor] Loaded initial task timer data")

        except Exception as e:
            logging.error(f"[TasksProcessor] Error loading initial task timer data: {e}")
            # Start retry mechanism for critical initial data
            self._start_retry_timer(is_initial=True)

    def load_task_timer_data(self, is_initial=False):
        """
        Load task timer data using one-off query.

        Args:
            is_initial: True if this is the initial load at startup
        """
        try:
            client = self.services.get("client") if self.services else None
            if not client:
                logging.warning("[TasksProcessor] No client available for timer query")
                return

            query_type = "initial" if is_initial else "refresh"
            logging.debug(f"[TasksProcessor] Querying task timer data ({query_type})")

            # Query the traveler_task_loop_timer table
            query_string = "SELECT * FROM traveler_task_loop_timer;"
            results = client.query(query_string)

            if results:
                # Process the results same way as subscription data
                self._process_timer_query_results(results, query_type)
                # Reset retry counter on successful query
                self._reset_retry()

            else:
                logging.warning(f"[TasksProcessor] No results from timer query ({query_type})")
                # Start retry if no results received
                self._start_retry_timer(is_initial)

        except Exception as e:
            logging.error(f"[TasksProcessor] Error querying task timer data: {e}")
            # Start retry mechanism on failure
            self._start_retry_timer(is_initial)

    def _process_timer_query_results(self, results, query_type):
        """
        Process timer query results and send updates to UI.

        Args:
            results: Query results from traveler_task_loop_timer
            query_type: String describing the type of query for logging
        """
        try:
            for row in results:
                scheduled_id = row.get("scheduled_id")
                scheduled_at = row.get("scheduled_at")

                if scheduled_at and isinstance(scheduled_at, list) and len(scheduled_at) > 1:
                    # Extract timestamp from format: [1, {"__timestamp_micros_since_unix_epoch__": 1754913600048146}]
                    timestamp_data = scheduled_at[1]
                    if isinstance(timestamp_data, dict):
                        timestamp_micros = timestamp_data.get("__timestamp_micros_since_unix_epoch__", 0)
                        if timestamp_micros:
                            # Convert microseconds to seconds
                            expiration_time = timestamp_micros / 1_000_000

                            # Store timer data
                            self._task_timer_data[scheduled_id] = expiration_time
                            self._current_task_expiration = expiration_time

                            current_time = time.time()
                            time_diff = expiration_time - current_time

                            logging.debug(
                                f"[TasksProcessor] Task timer from query ({query_type}): "
                                f"scheduled_id={scheduled_id}, expires in {time_diff:.1f}s"
                            )

                            # Send traveler task timer update to UI
                            timer_data = {
                                "traveler_tasks_expiration": expiration_time,
                                "source": f"one_off_query_{query_type}",
                                "query_type": query_type,
                                "is_initial": (query_type == "initial"),
                            }

                            logging.debug(f"[TasksProcessor] Sending traveler task timer update: {timer_data}")
                            self._queue_update("traveler_task_timer_update", timer_data)

        except Exception as e:
            logging.error(f"[TasksProcessor] Error processing timer query results: {e}")

    def _start_retry_timer(self, is_initial=False):
        """
        Start exponential backoff retry timer for task data loading.

        Args:
            is_initial: True if this is a retry for initial data loading
        """
        if self._retry_in_progress:
            return  # Already retrying

        if self._retry_count >= self._max_retries:
            logging.error(f"[TasksProcessor] Max retries ({self._max_retries}) reached for task timer data")
            self._send_retry_failed_notification()
            return

        # Calculate exponential backoff delay
        delay = min(self._base_delay * (2**self._retry_count), self._max_delay)
        self._retry_count += 1
        self._retry_in_progress = True

        logging.warning(
            f"[TasksProcessor] Starting retry {self._retry_count}/{self._max_retries} in {delay}s for task timer data"
        )

        # Send retry status to UI
        self._send_retry_status(delay, is_initial)

        # Schedule retry
        self._retry_timer = threading.Timer(delay, self._execute_retry, args=[is_initial])
        self._retry_timer.start()

    def _execute_retry(self, is_initial=False):
        """Execute the retry attempt."""
        try:
            self._retry_in_progress = False
            logging.debug(f"[TasksProcessor] Executing retry {self._retry_count}/{self._max_retries} for task timer data")
            self.load_task_timer_data(is_initial)

        except Exception as e:
            logging.error(f"[TasksProcessor] Retry attempt failed: {e}")
            self._retry_in_progress = False
            # Will trigger another retry if within max retries

    def _reset_retry(self):
        """Reset retry mechanism on successful operation."""
        if self._retry_count > 0:
            logging.debug(f"[TasksProcessor] Task timer data loaded successfully after {self._retry_count} retries")

        self._retry_count = 0
        self._retry_in_progress = False

        if self._retry_timer:
            self._retry_timer.cancel()
            self._retry_timer = None

    def _send_retry_status(self, delay, is_initial):
        """Send retry status to UI for display."""
        retry_data = {
            "status": "retrying",
            "retry_count": self._retry_count,
            "max_retries": self._max_retries,
            "delay": delay,
            "is_initial": is_initial,
            "message": f"Retrying in {delay}s... (attempt {self._retry_count}/{self._max_retries})",
        }

        self._queue_update("traveler_task_retry_status", retry_data)

    def _send_retry_failed_notification(self):
        """Send notification that all retries have failed."""
        failure_data = {
            "status": "failed",
            "retry_count": self._retry_count,
            "max_retries": self._max_retries,
            "message": f"Failed to load task data after {self._max_retries} attempts",
        }

        self._queue_update("traveler_task_retry_status", failure_data)
