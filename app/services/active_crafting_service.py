import time
from typing import Dict, List
import logging
import threading
from ..client.bitcraft_client import BitCraft
from ..models.claim import Claim


class ActiveCraftingService:
    """Service to handle active crafting status and data processing with real-time progress tracking."""

    def __init__(self, bitcraft_client: BitCraft, claim_instance: Claim, reference_data: dict):
        """Initialize the service with its dependencies."""
        self.client = bitcraft_client
        self.claim = claim_instance

        # Reference data
        self.crafting_recipes = {r["id"]: r for r in reference_data.get("crafting_recipe_desc", [])}
        self.building_desc = {b["id"]: b for b in reference_data.get("building_desc", [])}

        # Combined item lookup
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

        # Store current active crafting data
        self.current_active_crafting_data = []

        # Real-time progress tracking
        self.progress_timer_thread = None
        self.progress_timer_stop_event = threading.Event()
        self.ui_update_callback = None


    def get_all_active_crafting_data_enhanced(self) -> List[Dict]:
        """
        Fetches all active crafting operations from progressive_action_state table.
        Returns flat data (no grouping) formatted for GUI display.
        """
        if not self.claim.claim_id:
            logging.error("Cannot fetch active crafting data without a claim_id")
            return []

        try:

            # Get claim members for filtering
            claim_members_query = f"SELECT * FROM claim_member_state WHERE claim_entity_id = '{self.claim.claim_id}';"
            claim_members = self.client.query(claim_members_query)

            if not claim_members:
                logging.warning("No claim members found")
                return []

            claim_member_ids = set()
            user_lookup = {}
            for member in claim_members:
                player_id = member.get("player_entity_id")
                user_name = member.get("user_name")
                if player_id:
                    claim_member_ids.add(player_id)
                    user_lookup[player_id] = user_name or f"User {player_id}"

            # Get buildings that support active crafting
            buildings_query = f"SELECT * FROM building_state WHERE claim_entity_id = '{self.claim.claim_id}';"
            buildings = self.client.query(buildings_query)

            if not buildings:
                logging.warning("No buildings found for active crafting")
                return []

            # Get building nicknames
            nicknames_query = "SELECT * FROM building_nickname_state;"
            building_nicknames = self.client.query(nicknames_query)
            nickname_lookup = {n["entity_id"]: n["nickname"] for n in building_nicknames} if building_nicknames else {}

            # Filter to active crafting capable buildings
            active_crafting_buildings = []
            for building in buildings:
                building_desc_id = building.get("building_description_id")
                if self._building_supports_active_crafting(building_desc_id):
                    building_info = {
                        "entity_id": building.get("entity_id"),
                        "building_description_id": building_desc_id,
                        "building_name": self.building_desc.get(building_desc_id, {}).get("name", "Unknown Building"),
                        "display_name": nickname_lookup.get(building.get("entity_id"))
                        or self.building_desc.get(building_desc_id, {}).get("name", "Unknown Building"),
                        "nickname": nickname_lookup.get(building.get("entity_id")),
                    }
                    active_crafting_buildings.append(building_info)

            if not active_crafting_buildings:
                logging.info("No active crafting capable buildings found")
                return []

            # Get progressive action states (active crafting)
            active_crafting_operations = []
            for building_info in active_crafting_buildings:
                building_id = building_info["entity_id"]

                progressive_query = f"SELECT * FROM progressive_action_state WHERE building_entity_id = '{building_id}';"
                progressive_states = self.client.query(progressive_query)

                if not progressive_states:
                    continue

                for action_state in progressive_states:
                    owner_entity_id = action_state.get("owner_entity_id")

                    # Filter to claim members only
                    if owner_entity_id not in claim_member_ids:
                        continue

                    crafting_entry = self._format_progressive_action_entry_flat(action_state, building_info, user_lookup)
                    if crafting_entry:
                        active_crafting_operations.append(crafting_entry)

            return active_crafting_operations

        except Exception as e:
            logging.error(f"Error fetching progressive action data: {e}")
            return []

    def _format_progressive_action_entry_flat(self, action_state: Dict, building_info: Dict, user_lookup: Dict) -> Dict:
        """Format a single progressive_action_state entry as a flat row (no grouping)."""
        try:
            # Extract basic fields
            recipe_id = action_state.get("recipe_id")
            owner_entity_id = action_state.get("owner_entity_id")
            current_progress = action_state.get("progress", 0)
            craft_count = action_state.get("craft_count", 1)
            function_type = action_state.get("function_type")

            # Determine accept_help by checking public_progressive_action_state
            accept_help = False
            try:
                public_rows = self.client.query("SELECT * FROM public_progressive_action_state;")
                if public_rows:
                    # Build a set of tuples for fast lookup
                    public_keys = set(
                        (row.get("entity_id"), row.get("building_entity_id"), row.get("owner_entity_id")) for row in public_rows
                    )
                    key = (
                        action_state.get("entity_id"),
                        action_state.get("building_entity_id"),
                        action_state.get("owner_entity_id"),
                    )
                    if key in public_keys:
                        accept_help = True
            except Exception as e:
                logging.warning(f"Error checking public_progressive_action_state for accept_help: {e}")

            # Try to find preparation field
            preparation = False
            for field_name in ["preparation", "preparing", "is_preparing"]:
                if field_name in action_state:
                    preparation = bool(action_state[field_name])
                    break

            lock_expiration = action_state.get("lock_expiration", {})

            # Get recipe information
            recipe_info = self.crafting_recipes.get(recipe_id, {})
            recipe_name = recipe_info.get("name", f"Recipe {recipe_id}")
            actions_required = recipe_info.get("actions_required", 100)

            # Extract item being crafted
            crafted_item_name = "Unknown Item"
            crafted_item_tier = 0

            crafted_item_stacks = recipe_info.get("crafted_item_stacks", [])
            if crafted_item_stacks and len(crafted_item_stacks) > 0:
                first_item = crafted_item_stacks[0]
                if isinstance(first_item, (list, tuple)) and len(first_item) >= 1:
                    item_id = first_item[0]
                    if item_id in self.item_descriptions:
                        item_info = self.item_descriptions[item_id]
                        crafted_item_name = item_info.get("name", f"Item {item_id}")
                        crafted_item_tier = item_info.get("tier", 0)

            # Get crafter name
            crafter_name = user_lookup.get(owner_entity_id, f"User {owner_entity_id}")

            # Calculate total progress needed
            total_progress_needed = actions_required * craft_count
            progress_display = f"{current_progress}/{total_progress_needed}"

            # Determine status with proper logic
            session_expired = False
            if current_progress >= total_progress_needed:
                status = "Ready to Claim"
            else:
                # Check if session is expired
                if lock_expiration:
                    expiration_micros = lock_expiration.get("__timestamp_micros_since_unix_epoch__", 0)
                    if expiration_micros:
                        current_micros = time.time() * 1_000_000
                        if current_micros > expiration_micros:
                            session_expired = True

                if session_expired:
                    status = "Paused"
                elif preparation:
                    status = "Crafting"
                    # status = "Preparing"
                else:
                    status = "Paused"

            # Building display name
            building_display = building_info["display_name"]

            return {
                "item_name": crafted_item_name,
                "tier": crafted_item_tier,
                "quantity": craft_count,
                "recipe": recipe_name,
                "progress": progress_display,
                "current_progress": current_progress,
                "total_progress": total_progress_needed,
                "status": status,
                "accept_help": "Yes" if accept_help else "No",
                "crafter": crafter_name,
                "building": building_display,
                "is_completed": current_progress >= total_progress_needed,
                "is_paused": session_expired or status == "Paused",
                "function_type": function_type,
                "raw_action_state": action_state,
            }

        except Exception as e:
            logging.error(f"Error formatting progressive action entry: {e}")
            return None

    def _building_supports_active_crafting(self, building_desc_id: int) -> bool:
        """Check if a building supports active crafting."""
        if not building_desc_id or building_desc_id not in self.building_desc:
            return False

        building_name = self.building_desc[building_desc_id].get("name", "").lower()
        return "station" in building_name  # Generic catch-all for now

    def start_progress_tracking(self, ui_update_callback):
        """Start real-time progress tracking for active crafting."""
        if self.progress_timer_thread and self.progress_timer_thread.is_alive():
            logging.warning("Progress tracking already running")
            return

        self.ui_update_callback = ui_update_callback
        self.progress_timer_stop_event.clear()

        self.progress_timer_thread = threading.Thread(target=self._progress_tracking_loop, daemon=True)
        self.progress_timer_thread.start()
        logging.info("Started active crafting progress tracking")

    def stop_progress_tracking(self):
        """Stop the progress tracking thread."""
        logging.info("Stopping active crafting progress tracking...")

        try:
            if self.progress_timer_thread:
                self.progress_timer_stop_event.set()

                if self.progress_timer_thread.is_alive():
                    self.progress_timer_thread.join(timeout=1.0)

                    if self.progress_timer_thread.is_alive():
                        logging.warning("Progress tracking thread did not finish within timeout")
                    else:
                        logging.info("Progress tracking thread finished cleanly")

                self.progress_timer_thread = None

        except Exception as e:
            logging.error(f"Error stopping progress tracking: {e}")
        finally:
            logging.info("Active crafting progress tracking stopped")

    def _progress_tracking_loop(self):
        """Background thread for tracking active crafting progress."""
        while not self.progress_timer_stop_event.is_set():
            try:
                current_time = time.time()

                if self.ui_update_callback and self.current_active_crafting_data:
                    self.ui_update_callback(
                        {
                            "type": "active_crafting_progress_update",
                            "data": self.current_active_crafting_data,
                            "timestamp": current_time,
                        }
                    )

                time.sleep(3.0)

            except Exception as e:
                logging.error(f"Error in progress tracking loop: {e}")
                time.sleep(5.0)

    def get_current_active_crafting_data_for_gui(self) -> List[Dict]:
        """Returns current active crafting data for GUI display."""
        return self.current_active_crafting_data
