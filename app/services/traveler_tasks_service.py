import logging
from typing import List, Dict

from ..client.bitcraft_client import BitCraft
from ..models.player import Player


class TravelerTasksService:
    """Service to handle traveler tasks data processing with real-time updates."""

    def __init__(self, bitcraft_client: BitCraft, player_instance: Player, reference_data: dict):
        """Initialize the service with its dependencies."""
        self.client = bitcraft_client
        self.player = player_instance

        # Create combined item lookup from all item sources (for required items formatting)
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

        # Store current tasks data for GUI
        self.current_tasks_data = []

        logging.info(f"TravelerTasksService initialized with {len(self.item_descriptions)} items for required items lookup")


    def get_all_tasks_data_grouped(self) -> List[Dict]:
        """
        Fetches all traveler tasks for the current player and groups them by traveler.
        """
        if not self.player.user_id:
            logging.error("Cannot fetch tasks without player user_id")
            return []

        try:
            logging.info(f"Fetching all traveler tasks for player {self.player.user_id}")

            # Get all task states for this player
            state_query = f"SELECT * FROM traveler_task_state WHERE player_entity_id = '{self.player.user_id}';"
            task_states = self.client.query(state_query)

            if not task_states:
                logging.info("No traveler tasks found for player")
                return []

            # Get all unique task IDs and traveler IDs to fetch descriptions
            task_ids = set()
            traveler_ids = set()
            for task_state in task_states:
                if task_state.get("task_id"):
                    task_ids.add(task_state.get("task_id"))
                if task_state.get("traveler_id"):
                    traveler_ids.add(task_state.get("traveler_id"))

            # Fetch task descriptions from live database
            task_descriptions = {}
            if task_ids:
                for task_id in task_ids:
                    desc_query = f"SELECT * FROM traveler_task_desc WHERE id = {task_id};"
                    desc_results = self.client.query(desc_query)
                    if desc_results and len(desc_results) > 0:
                        task_descriptions[task_id] = desc_results[0]

            # Fetch NPC descriptions from live database
            npc_descriptions = {}
            if traveler_ids:
                for traveler_id in traveler_ids:
                    npc_query = f"SELECT * FROM npc_desc WHERE npc_type = {traveler_id};"
                    npc_results = self.client.query(npc_query)
                    if npc_results and len(npc_results) > 0:
                        npc_descriptions[traveler_id] = npc_results[0]

            # Group tasks by traveler
            traveler_groups = {}

            for task_state in task_states:
                traveler_id = task_state.get("traveler_id")
                task_id = task_state.get("task_id")
                completed = task_state.get("completed", False)
                entity_id = task_state.get("entity_id")

                if not traveler_id or not task_id:
                    continue

                # Get traveler information
                traveler_info = npc_descriptions.get(traveler_id, {})
                traveler_name = traveler_info.get("name", f"Traveler {traveler_id}")

                # Get task information
                task_info = task_descriptions.get(task_id, {})
                task_description = task_info.get("description", f"Task {task_id}")

                # Process required items - both formats for compatibility
                required_items_str = self._format_required_items(task_info.get("required_items", []))
                required_items_detailed = self._format_required_items_detailed(task_info.get("required_items", []))

                # Create task entry with enhanced required items data
                task_entry = {
                    "entity_id": entity_id,
                    "traveler_id": traveler_id,
                    "traveler_name": traveler_name,
                    "task_id": task_id,
                    "task_description": task_description,
                    "required_items": required_items_str,  # String format for backward compatibility
                    "required_items_detailed": required_items_detailed,  # Detailed format for UI
                    "completed": completed,
                    "completion_status": "✅" if completed else "❌",
                }

                # Group by traveler
                if traveler_name not in traveler_groups:
                    traveler_groups[traveler_name] = {
                        "traveler_name": traveler_name,
                        "traveler_id": traveler_id,
                        "tasks": [],
                        "completed_count": 0,
                        "total_count": 0,
                    }

                traveler_groups[traveler_name]["tasks"].append(task_entry)
                traveler_groups[traveler_name]["total_count"] += 1
                if completed:
                    traveler_groups[traveler_name]["completed_count"] += 1

            # Convert to list format for GUI
            grouped_data = []
            for traveler_name, group_data in traveler_groups.items():
                completed = group_data["completed_count"]
                total = group_data["total_count"]

                # Create top-level traveler entry
                traveler_entry = {
                    "traveler": traveler_name,
                    "task": f"{completed} of {total} completed",
                    "required_items": "",  # Empty for parent row
                    "complete": "✅" if completed == total else "❌",
                    "operations": group_data["tasks"],  # Individual tasks as children
                    "is_expandable": True,
                    "expansion_level": 0,
                    "traveler_id": group_data["traveler_id"],
                    "completed_count": completed,
                    "total_count": total,
                }

                grouped_data.append(traveler_entry)

            # Sort by traveler name
            grouped_data.sort(key=lambda x: x.get("traveler", ""))

            self.current_tasks_data = grouped_data
            logging.info(f"Grouped tasks for {len(grouped_data)} travelers")
            return grouped_data

        except Exception as e:
            logging.error(f"Error fetching traveler tasks data: {e}")
            return []

    def _format_required_items(self, required_items: List) -> str:
        """
        Formats the required items list into a readable string.
        This method is now used for backward compatibility, but the main processing
        happens in the UI to split items into separate columns.

        Args:
            required_items: List of [item_id, quantity] pairs

        Returns:
            Formatted string like "Wood x5, Stone x2"
        """
        if not required_items:
            return "No items required"

        try:
            formatted_items = []

            for item_data in required_items:
                if not isinstance(item_data, (list, tuple)) or len(item_data) < 2:
                    continue

                item_id = item_data[0]
                quantity = item_data[1]

                # Get item name
                item_info = self.item_descriptions.get(item_id, {})
                item_name = item_info.get("name", f"Item {item_id}")

                formatted_items.append(f"{item_name} x{quantity}")

            return ", ".join(formatted_items) if formatted_items else "Unknown items"

        except Exception as e:
            logging.error(f"Error formatting required items: {e}")
            return "Error formatting items"

    def _format_required_items_detailed(self, required_items: List) -> List[Dict]:
        """
        Formats the required items into a detailed list with item names, tiers, and tags.
        Args:
            required_items: List of [item_id, quantity] pairs

        Returns:
            List of dictionaries with 'item_name', 'tier', 'quantity', and 'tag' keys
        """
        if not required_items:
            return [{"item_name": "No items required", "tier": 0, "quantity": 0, "tag": ""}]

        try:
            detailed_items = []

            for item_data in required_items:
                if not isinstance(item_data, (list, tuple)) or len(item_data) < 2:
                    continue

                item_id = item_data[0]
                quantity = item_data[1]

                # Get item information including tier
                item_info = self.item_descriptions.get(item_id, {})
                item_name = item_info.get("name", f"Item {item_id}")
                item_tier = item_info.get("tier", 0)  # NEW: Get item tier
                item_tag = item_info.get("tag", "")

                detailed_items.append(
                    {"item_name": item_name, "tier": item_tier, "quantity": quantity, "tag": item_tag}  # NEW: Include tier
                )

            return detailed_items if detailed_items else [{"item_name": "Unknown items", "tier": 0, "quantity": 0, "tag": ""}]

        except Exception as e:
            logging.error(f"Error formatting detailed required items: {e}")
            return [{"item_name": "Error formatting items", "tier": 0, "quantity": 0, "tag": ""}]

    def parse_task_update(self, db_update: dict) -> bool:
        """
        Parses a database update message to check if it's relevant to traveler tasks.
        Returns True if the data was updated and needs GUI refresh.
        """
        try:
            update_str = str(db_update)
            if "traveler_task_state" in update_str:
                logging.info("Received a traveler task update")

                # Check if this update affects our player
                if self.player.user_id and str(self.player.user_id) in update_str:
                    # Refresh the tasks data
                    self.current_tasks_data = self.get_all_tasks_data_grouped()
                    return True

        except Exception as e:
            logging.error(f"Error parsing task update: {e}")

        return False

    def get_current_tasks_data_for_gui(self) -> List[Dict]:
        """Returns the current tasks data formatted for GUI display."""
        return self.current_tasks_data

    def detect_task_completions(self, old_data: List[Dict], new_data: List[Dict]) -> List[Dict]:
        """
        Compares old and new task data to detect newly completed tasks.
        Returns list of completed task information for notifications.
        """
        try:
            completed_tasks = []

            # Create lookup for old completion states
            old_states = {}
            for traveler_group in old_data:
                for task in traveler_group.get("operations", []):
                    task_id = task.get("task_id")
                    if task_id:
                        old_states[task_id] = task.get("completed", False)

            # Check for new completions
            for traveler_group in new_data:
                for task in traveler_group.get("operations", []):
                    task_id = task.get("task_id")
                    if task_id:
                        old_completed = old_states.get(task_id, False)
                        new_completed = task.get("completed", False)

                        # Task was just completed
                        if not old_completed and new_completed:
                            completed_tasks.append(
                                {
                                    "task_description": task.get("task_description", "Unknown Task"),
                                    "traveler_name": task.get("traveler_name", "Unknown Traveler"),
                                    "task_id": task_id,
                                }
                            )

            if completed_tasks:
                logging.info(f"Detected {len(completed_tasks)} newly completed tasks")

            return completed_tasks

        except Exception as e:
            logging.error(f"Error detecting task completions: {e}")
            return []
