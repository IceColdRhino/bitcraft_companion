"""
Active crafting processor for handling progressive_action_state table updates.

SpacetimeDB Table Structures:
----------------------------

progressive_action_state:
    entity_id: int - Unique identifier for the crafting action
    building_entity_id: int - ID of the building where crafting occurs
    function_type: int - Type of crafting function
    progress: int - Current progress value
    recipe_id: int - ID of the recipe being crafted
    craft_count: int - Number of items being crafted
    last_crit_outcome: int - Last critical success outcome
    owner_entity_id: int - ID of the player performing the craft
    lock_expiration: list - Timestamp when craft lock expires
    preparation: bool - Whether craft is in preparation phase

public_progressive_action_state:
    entity_id: int - Unique identifier
    building_entity_id: int - ID of building accepting help
    owner_entity_id: int - ID of the craft owner

building_state:
    entity_id: int - Unique building identifier
    building_description_id: int - Type of building
    claim_entity_id: int - ID of claim containing the building

building_nickname_state:
    entity_id: int - Building ID this nickname applies to
    nickname: str - Custom name for the building

claim_member_state:
    claim_entity_id: int - ID of the claim
    player_entity_id: int - ID of the player member
    user_name: str - Display name of the player
"""

import re
import json
import logging
from .base_processor import BaseProcessor
from app.models import ProgressiveActionState, PublicProgressiveActionState, BuildingState, ClaimMemberState


class ActiveCraftingProcessor(BaseProcessor):
    """
    Processes active crafting data from SpacetimeDB for real-time UI updates.

    This processor handles multiple SpacetimeDB tables to provide comprehensive
    active crafting information including:
    - Progressive crafting operations and their progress
    - Buildings accepting help (public_progressive_action_state)
    - Building names and locations
    - Player assistance detection and tracking

    Architecture:
    - Transaction processing: Real-time incremental updates for live progress
    - Subscription processing: Batch updates for initial data loading
    - Data consolidation: Combines all sources into hierarchical UI format
    - Assistant detection: Tracks players helping with accept-help crafts

    Data Flow:
    1. SpacetimeDB → process_transaction/process_subscription
    2. Raw data → _process_*_data methods (using data classes)
    3. Cached data → _consolidate_active_crafting
    4. UI format → _format_crafting_for_ui
    5. UI update → active_crafting_update message
    """

    def __init__(self, data_queue, services, reference_data):
        """
        Initialize the active crafting processor.

        Args:
            data_queue: Queue for sending processed data to UI
            services: Dict of available services (item_lookup_service, etc.)
            reference_data: Static game data (recipes, items, buildings)

        Instance Variables:
            current_active_crafting_data: Last sent UI data for progress tracking
            _progressive_action_data: Dict[int, dict] - Active crafts by entity_id
            _public_actions: Set[int] - Progressive action entity IDs accepting help
            _building_data: Dict[int, dict] - Building info by entity_id
            _building_nicknames: Dict[int, str] - Custom building names
            _claim_members: Dict[str, str] - Player names by player_entity_id
        """
        super().__init__(data_queue, services, reference_data)
        self.current_active_crafting_data = []

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

        Processes real-time active crafting progress changes without full refresh.
        """
        try:
            table_name = table_update.get("table_name", "")
            updates = table_update.get("updates", [])

            # Track if we need to send updates
            has_active_crafting_changes = False

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
                        else:
                            # This is a new insert
                            recipe_id = insert_data.get("recipe_id", 0)
                            progress = insert_data.get("progress", 0)

                        has_active_crafting_changes = True

                    # Handle standalone deletes (completions)
                    for entity_id in delete_operations:
                        if entity_id not in insert_operations:
                            # This is a standalone delete (completion/claimed)
                            if entity_id in self._progressive_action_data:
                                del self._progressive_action_data[entity_id]

                            delete_data = delete_operations[entity_id]
                            recipe_id = delete_data.get("recipe_id", 0)

                            # Notification is triggered when item becomes READY, not when claimed

                            has_active_crafting_changes = True

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
                            progressive_action_entity_id = None
                            building_entity_id = None
                            
                            if isinstance(insert_data, list) and len(insert_data) >= 3:
                                # Array format: [entity_id, building_entity_id, owner_entity_id]
                                progressive_action_entity_id = insert_data[0]  # entity_id is the progressive action ID
                                building_entity_id = insert_data[1]  # building_entity_id for reference
                            elif isinstance(insert_data, dict):
                                # Object format: {"entity_id": value, "building_entity_id": value}
                                progressive_action_entity_id = insert_data.get("entity_id")
                                building_entity_id = insert_data.get("building_entity_id")
                            else:
                                logging.warning(f"Unexpected public_progressive_action_state insert format: {insert_data}")
                                continue

                            if progressive_action_entity_id:
                                self._public_actions.add(progressive_action_entity_id)

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
                            progressive_action_entity_id = None
                            
                            if isinstance(delete_data, list) and len(delete_data) >= 3:
                                # Array format: [entity_id, building_entity_id, owner_entity_id]
                                progressive_action_entity_id = delete_data[0]  # entity_id is the progressive action ID
                            elif isinstance(delete_data, dict):
                                # Object format: {"entity_id": value}
                                progressive_action_entity_id = delete_data.get("entity_id")
                            else:
                                logging.warning(f"Unexpected public_progressive_action_state delete format: {delete_data}")
                                continue

                            if progressive_action_entity_id and progressive_action_entity_id in self._public_actions:
                                self._public_actions.remove(progressive_action_entity_id)
                        except Exception as e:
                            logging.warning(f"Failed to parse public_progressive_action_state delete, skipping: {e}")
                            logging.error(f"Error processing public action delete: {e}")

                    if inserts or deletes:
                        has_active_crafting_changes = True

                # For other table types, do full refresh if we have changes
                elif inserts or deletes:
                    has_active_crafting_changes = True

            # Send incremental update for progressive_action_state and public_progressive_action_state, full refresh for others
            if has_active_crafting_changes:
                if table_name in ["progressive_action_state", "public_progressive_action_state"]:
                    self._send_incremental_active_crafting_update(reducer_name, timestamp)
                else:
                    logging.debug(f"Sending full refresh for table: {table_name}")
                    self._refresh_active_crafting()

        except Exception as e:
            logging.error(f"Error handling active crafting transaction: {e}")

    def process_subscription(self, table_update):
        """
        Handle progressive_action_state, building_state, building_nickname_state, and claim_member_state subscription updates.
        Cache all data and combine them for consolidated active crafting.
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

            # Try to send consolidated active crafting if we have all necessary data
            self._send_active_crafting_update()

        except Exception as e:
            logging.error(f"Error handling active crafting subscription: {e}")

    def _process_progressive_action_data(self, action_rows):
        """Process progressive_action_state data using data classes."""
        try:
            if not hasattr(self, "_progressive_action_data"):
                self._progressive_action_data = {}

            for row in action_rows:
                try:
                    # Create ProgressiveActionState data class instance
                    progressive_action = ProgressiveActionState(**row)

                    # Store using entity_id as key, converting back to dict for compatibility
                    self._progressive_action_data[progressive_action.entity_id] = {
                        "entity_id": progressive_action.entity_id,
                        "building_entity_id": progressive_action.building_entity_id,
                        "function_type": progressive_action.function_type,
                        "progress": progressive_action.progress,
                        "recipe_id": progressive_action.recipe_id,
                        "craft_count": progressive_action.craft_count,
                        "last_crit_outcome": progressive_action.last_crit_outcome,
                        "owner_entity_id": progressive_action.owner_entity_id,
                        "lock_expiration": progressive_action.lock_expiration,
                        "preparation": progressive_action.preparation,
                    }
                except Exception as row_error:
                    logging.warning(f"Failed to process progressive_action_state row, using fallback: {row_error}")
                    # Try fallback parsing for essential fields
                    try:
                        entity_id = row.get("entity_id")
                        building_entity_id = row.get("building_entity_id")
                        if entity_id and building_entity_id:
                            self._progressive_action_data[entity_id] = {
                                "entity_id": entity_id,
                                "building_entity_id": building_entity_id,
                                "function_type": row.get("function_type", 0),
                                "progress": row.get("progress", 0),
                                "owner_entity_id": row.get("owner_entity_id", 0),
                            }
                        else:
                            logging.warning(f"Progressive action row missing critical fields: {row}")
                    except Exception:
                        logging.warning(f"Cannot parse progressive action row at all, skipping: {row}")
                    continue

        except Exception as e:
            logging.error(f"Error processing progressive action data: {e}")

    def _process_public_progressive_action_data(self, public_action_rows):
        """Process public_progressive_action_state data using data classes."""
        try:
            if not hasattr(self, "_public_actions"):
                self._public_actions = set()
            else:
                self._public_actions.clear()

            for row in public_action_rows:
                try:
                    # Create PublicProgressiveActionState data class instance
                    public_action = PublicProgressiveActionState(**row)
                    # Track the progressive action entity ID, not the building ID
                    self._public_actions.add(public_action.entity_id)
                except Exception as row_error:
                    logging.warning(f"Failed to process public_progressive_action_state row, using fallback: {row_error}")
                    # Try fallback parsing
                    try:
                        entity_id = row.get("entity_id")
                        if entity_id:
                            self._public_actions.add(entity_id)
                        else:
                            logging.warning(f"Public action row missing entity_id: {row}")
                    except Exception:
                        logging.warning(f"Cannot parse public action row at all, skipping: {row}")
                    continue

        except Exception as e:
            logging.error(f"Error processing public progressive action data: {e}")

    def _process_building_data(self, building_rows):
        """Process building_state data using data classes."""
        try:
            if not hasattr(self, "_building_data"):
                self._building_data = {}

            for row in building_rows:
                try:
                    # Create BuildingState data class instance
                    building = BuildingState(**row)

                    # Store using entity_id as key, converting back to dict for compatibility
                    self._building_data[building.entity_id] = {
                        "building_description_id": building.building_description_id,
                        "claim_entity_id": building.claim_entity_id,
                        "entity_id": building.entity_id,
                    }
                except Exception as row_error:
                    logging.debug(f"Failed to process building row: {row_error}")
                    continue

        except Exception as e:
            logging.error(f"Error processing building data: {e}")

    def _process_building_nickname_data(self, nickname_rows):
        """Process building_nickname_state data using data classes."""
        try:
            if not hasattr(self, "_building_nicknames"):
                self._building_nicknames = {}

            for row in nickname_rows:
                try:
                    # Process building nickname data directly (no dataclass available yet)
                    entity_id = row.get("entity_id")
                    nickname = row.get("nickname")
                    if entity_id and nickname:
                        self._building_nicknames[entity_id] = nickname
                except Exception as row_error:
                    logging.debug(f"Failed to process building nickname row: {row_error}")
                    continue

        except Exception as e:
            logging.error(f"Error processing building nickname data: {e}")

    def _process_claim_member_data(self, member_rows):
        """Process claim_member_state data using data classes."""
        try:
            if not hasattr(self, "_claim_members"):
                self._claim_members = {}

            for row in member_rows:
                try:
                    # Create ClaimMemberState data class instance
                    member = ClaimMemberState(**row)
                    self._claim_members[str(member.player_entity_id)] = member.user_name
                except Exception as row_error:
                    logging.debug(f"Failed to process claim member row: {row_error}")
                    continue

        except Exception as e:
            logging.error(f"Error processing claim member data: {e}")

    def _send_active_crafting_update(self):
        """Send consolidated active crafting update by combining all cached data."""
        try:
            if not (hasattr(self, "_progressive_action_data") and self._progressive_action_data):
                return

            if not (hasattr(self, "_building_data") and self._building_data):
                return

            # Building nicknames are optional
            if not hasattr(self, "_building_nicknames"):
                self._building_nicknames = {}

            # Consolidate active crafting by item
            consolidated_crafting = self._consolidate_active_crafting()

            # Convert dictionary to list format for UI
            crafting_list = self._format_crafting_for_ui(consolidated_crafting)

            # Store current data for progress tracking
            self.current_active_crafting_data = crafting_list

            # Send to UI
            self._queue_update("active_crafting_update", crafting_list)

        except Exception as e:
            logging.error(f"Error sending active crafting update: {e}")

    def _consolidate_active_crafting(self):
        """
        Consolidate active crafting data into 3-level hierarchy: Item -> Crafter -> Building/Progress.

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

            # Use shared item lookup service
            recipe_lookup = {r["id"]: r for r in self.reference_data.get("crafting_recipe_desc", [])}
            building_desc_lookup = {b["id"]: b["name"] for b in self.reference_data.get("building_desc", [])}

            # Process each active crafting operation to extract individual items
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

                # Check if this progressive action accepts help
                accepts_help = "Yes" if hasattr(self, "_public_actions") and action_id in self._public_actions else "No"

                # Get crafter name
                crafter_name = self._get_player_name(owner_id)
                if crafter_name == f"Player {owner_id}":
                    logging.warning(f"Player name not found for ID {owner_id}, using fallback display name")

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

                            # Look up item details using shared lookup service with preferred source
                            preferred_source = self._determine_preferred_item_source(recipe_info)
                            item_info = self.item_lookup_service.lookup_item_by_id(item_id, preferred_source)
                            item_name = (
                                item_info.get("name", f"Unknown Item {item_id}") if item_info else f"Unknown Item {item_id}"
                            )
                            item_tier = item_info.get("tier", 0) if item_info else 0
                            item_tag = item_info.get("tag", "") if item_info else ""
                        else:
                            logging.warning(f"Invalid item_stack format in recipe {recipe_id}: {item_stack} - skipping item")
                            continue

                        # Create raw operation
                        raw_operation = {
                            "item_name": item_name,
                            "tier": item_tier,
                            "quantity": total_quantity,
                            "tag": item_tag,
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

                except Exception as e:
                    logging.warning(f"Failed to process progressive action {action_id}, skipping from UI: {e}")
                    logging.error(f"Exception processing action {action_id}: {e}")
                    continue

            # Now build the 3-level hierarchy
            return self._build_hierarchy(raw_operations)

        except Exception as e:
            logging.error(f"Error consolidating active crafting: {e}")
            return {}

    def _build_hierarchy(self, raw_operations):
        """
        Build 3-level hierarchy from raw operations: Item -> Crafter -> Building/Progress.

        Args:
            raw_operations: List of individual active crafting operations

        Returns:
            Dictionary with hierarchical structure for UI
        """
        try:
            hierarchy = {}

            # Group by item name first (Level 1)
            for op in raw_operations:
                item_name = op["item_name"]

                if item_name not in hierarchy:
                    hierarchy[item_name] = {
                        "tier": op["tier"],
                        "tag": op["tag"],
                        "total_quantity": 0,
                        "crafters": {},  # Level 2: crafter data
                        "unique_crafters": set(),
                        "unique_buildings": set(),
                        "accept_help_values": set(),  # Track all accept help values
                    }

                # Add to item totals
                hierarchy[item_name]["total_quantity"] += op["quantity"]
                hierarchy[item_name]["unique_crafters"].add(op["crafter"])
                hierarchy[item_name]["unique_buildings"].add(op["building_name"])
                hierarchy[item_name]["accept_help_values"].add(op["accept_help"])

                # Group by crafter (Level 2)
                crafter = op["crafter"]
                if crafter not in hierarchy[item_name]["crafters"]:
                    hierarchy[item_name]["crafters"][crafter] = {
                        "total_quantity": 0,
                        "buildings": {},  # Level 3: building/progress data
                        "unique_buildings": set(),
                        "accept_help_values": set(),  # Track accept help values for this crafter
                    }

                # Add to crafter totals
                hierarchy[item_name]["crafters"][crafter]["total_quantity"] += op["quantity"]
                hierarchy[item_name]["crafters"][crafter]["unique_buildings"].add(op["building_name"])
                hierarchy[item_name]["crafters"][crafter]["accept_help_values"].add(op["accept_help"])

                # Group by building + progress (Level 3)
                building_progress_key = f"{op['building_name']}|{op['remaining_effort']}"
                if building_progress_key not in hierarchy[item_name]["crafters"][crafter]["buildings"]:
                    hierarchy[item_name]["crafters"][crafter]["buildings"][building_progress_key] = {
                        "building_name": op["building_name"],
                        "remaining_effort": op["remaining_effort"],
                        "progress_value": op["progress_value"],
                        "accept_help": op["accept_help"],
                        "quantity": 0,
                        "operations": [],
                    }

                # Add to building/progress group
                hierarchy[item_name]["crafters"][crafter]["buildings"][building_progress_key]["quantity"] += op["quantity"]
                hierarchy[item_name]["crafters"][crafter]["buildings"][building_progress_key]["operations"].append(op)

            # Convert to UI format
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
            hierarchy: The 3-level hierarchy structure

        Returns:
            Dictionary formatted for UI display
        """
        try:
            formatted = {}

            for item_name, item_data in hierarchy.items():
                # Since we're using flat rows now, just create individual operation entries
                operations = []

                for crafter_name, crafter_data in item_data["crafters"].items():
                    for building_progress_key, building_data in crafter_data["buildings"].items():
                        # Each building/progress combination becomes its own operation
                        for operation in building_data["operations"]:
                            operations.append(
                                {
                                    "item": operation["item_name"],
                                    "tier": operation["tier"],
                                    "quantity": operation["quantity"],
                                    "tag": operation["tag"],
                                    "remaining_effort": operation["remaining_effort"],
                                    "accept_help": operation["accept_help"],
                                    "crafter": operation["crafter"],
                                    "building_name": operation["building_name"],
                                    "is_expandable": False,
                                    "expansion_level": 0,
                                }
                            )

                # Create a simple entry that contains all the individual operations
                formatted[item_name] = {
                    "item": item_name,
                    "tier": item_data["tier"],
                    "total_quantity": item_data["total_quantity"],
                    "tag": item_data["tag"],
                    "remaining_effort": "Multiple",  # Not used in flat display
                    "accept_help": "Mixed",  # Not used in flat display
                    "crafter": "Multiple",  # Not used in flat display
                    "building_name": "Multiple",  # Not used in flat display
                    "operations": operations,
                    "is_expandable": True,  # Always expandable to show individual operations
                    "expansion_level": 0,
                }

            return formatted

        except Exception as e:
            logging.error(f"Error formatting hierarchy for UI: {e}")
            return {}

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

    def _format_crafting_for_ui(self, consolidated_crafting):
        """
        Convert consolidated crafting dictionary to list format expected by UI.

        Args:
            consolidated_crafting: Dictionary with items consolidated by name

        Returns:
            List of item groups with operations for expandable UI
        """
        try:
            formatted_list = []

            for item_name, item_data in consolidated_crafting.items():
                # Keep all the properly formatted data from _format_hierarchy_for_ui
                formatted_list.append(item_data)

            # Sort by item name for consistent display
            formatted_list.sort(key=lambda x: x.get("item", "").lower())

            return formatted_list

        except Exception as e:
            logging.error(f"Error formatting crafting for UI: {e}")
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

    def _refresh_active_crafting(self):
        """
        Legacy method for compatibility with transaction processing.
        """
        try:
            self._send_active_crafting_update()
        except Exception as e:
            logging.error(f"Error refreshing active crafting: {e}")

    def _parse_progressive_action_state(self, data_str):
        """
        Parse progressive_action_state from SpacetimeDB transaction format using data class.

        Args:
            data_str: Raw transaction data from SpacetimeDB

        Returns:
            Dict representation of ProgressiveActionState or None if parsing fails
        """
        try:
            # Parse JSON string to list first
            data = json.loads(data_str)
            progressive_action = ProgressiveActionState.from_array(data)
            if progressive_action:
                return {
                    "entity_id": progressive_action.entity_id,
                    "building_entity_id": progressive_action.building_entity_id,
                    "function_type": progressive_action.function_type,
                    "progress": progressive_action.progress,
                    "recipe_id": progressive_action.recipe_id,
                    "craft_count": progressive_action.craft_count,
                    "last_crit_outcome": progressive_action.last_crit_outcome,
                    "owner_entity_id": progressive_action.owner_entity_id,
                    "lock_expiration": progressive_action.lock_expiration,
                    "preparation": progressive_action.preparation,
                }
            return None
        except Exception as e:
            logging.debug(f"Failed to parse progressive_action_state: {e}")
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

    def _send_incremental_active_crafting_update(self, reducer_name, timestamp):
        """
        Send incremental active crafting update without full refresh.
        """
        try:
            # Get fresh active crafting data using existing consolidation logic
            consolidated_crafting = self._consolidate_active_crafting()

            # Convert dictionary to list format for UI (same as regular update)
            crafting_list = self._format_crafting_for_ui(consolidated_crafting)

            if crafting_list:
                # Store current data for progress tracking
                self.current_active_crafting_data = crafting_list

                # Send targeted update with incremental flag
                self._queue_update(
                    "active_crafting_update",
                    crafting_list,
                    changes={"type": "incremental", "source": "live_transaction", "reducer": reducer_name},
                    timestamp=timestamp,
                )

        except Exception as e:
            logging.error(f"Error sending incremental active crafting update: {e}")

    def clear_cache(self):
        """Clear cached active crafting data when switching claims."""
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
                            item_info = self.item_lookup_service.lookup_item_by_id(item_id)

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
