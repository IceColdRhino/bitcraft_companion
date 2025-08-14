import json
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class ClaimLocalState:
    """
    Data class for claim_local_state data from SpacetimeDB.
    Format: [entity_id, supplies, building_maintenance, num_tiles, num_tile_neighbors, location, treasury, xp_gained_since_last_coin_minting, supplies_purchase_threshold, supplies_purchase_price, building_description_id]
    """

    entity_id: int
    supplies: int = 0
    building_maintenance: float = 0.0
    num_tiles: int = 0
    num_tile_neighbors: int = 0
    location: List[int] = None
    treasury: int = 0
    xp_gained_since_last_coin_minting: int = 0
    supplies_purchase_threshold: int = 0
    supplies_purchase_price: float = 0.0
    building_description_id: int = 0

    @classmethod
    def from_array(cls, data: List) -> "ClaimLocalState":
        """
        Create ClaimLocalState from SpacetimeDB array format.
        
        The actual array format appears to be much larger (78-80+ elements) than the original
        11-element format expected. We'll extract the core fields we need from the first elements
        and gracefully handle the variable array size.
        """
        if not isinstance(data, list):
            raise ValueError(f"Invalid claim_local_state array format: expected list, got {type(data)}")
            
        if len(data) < 11:
            raise ValueError(
                f"Invalid claim_local_state array format: expected at least 11 elements, got {len(data)}"
            )

        # Extract known fields from the beginning of the array
        # Based on the original format but handling the actual longer format
        try:
            return cls(
                entity_id=data[0] if len(data) > 0 else 0,
                supplies=data[1] if len(data) > 1 else 0,
                building_maintenance=data[2] if len(data) > 2 else 0.0,
                num_tiles=data[3] if len(data) > 3 else 0,
                num_tile_neighbors=data[4] if len(data) > 4 else 0,
                location=data[5] if len(data) > 5 else None,
                treasury=data[6] if len(data) > 6 else 0,
                xp_gained_since_last_coin_minting=data[7] if len(data) > 7 else 0,
                supplies_purchase_threshold=data[8] if len(data) > 8 else 0,
                supplies_purchase_price=data[9] if len(data) > 9 else 0.0,
                building_description_id=data[10] if len(data) > 10 else 0,
            )
        except (IndexError, TypeError, ValueError) as e:
            # Fallback for any parsing errors - create with minimal data
            return cls(
                entity_id=data[0] if len(data) > 0 and isinstance(data[0], int) else 0,
                supplies=0,
                building_maintenance=0.0,
                num_tiles=0,
                num_tile_neighbors=0,
                location=None,
                treasury=0,
                xp_gained_since_last_coin_minting=0,
                supplies_purchase_threshold=0,
                supplies_purchase_price=0.0,
                building_description_id=0,
            )

    @classmethod
    def from_dict(cls, data: dict) -> "ClaimLocalState":
        """Create ClaimLocalState from SpacetimeDB JSON format."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid claim_local_state format: expected dict, got {type(data)}")

        return cls(
            entity_id=data.get("entity_id", 0),
            supplies=data.get("supplies", 0),
            building_maintenance=data.get("building_maintenance", 0.0),
            num_tiles=data.get("num_tiles", 0),
            num_tile_neighbors=data.get("num_tile_neighbors", 0),
            location=data.get("location"),
            treasury=data.get("treasury", 0),
            xp_gained_since_last_coin_minting=data.get("xp_gained_since_last_coin_minting", 0),
            supplies_purchase_threshold=data.get("supplies_purchase_threshold", 0),
            supplies_purchase_price=data.get("supplies_purchase_price", 0.0),
            building_description_id=data.get("building_description_id", 0),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary format for backward compatibility."""
        return {
            "entity_id": self.entity_id,
            "supplies": self.supplies,
            "building_maintenance": self.building_maintenance,
            "num_tiles": self.num_tiles,
            "num_tile_neighbors": self.num_tile_neighbors,
            "location": self.location,
            "treasury": self.treasury,
            "xp_gained_since_last_coin_minting": self.xp_gained_since_last_coin_minting,
            "supplies_purchase_threshold": self.supplies_purchase_threshold,
            "supplies_purchase_price": self.supplies_purchase_price,
            "building_description_id": self.building_description_id,
        }


@dataclass
class ClaimState:
    """
    Data class for claim_state data from SpacetimeDB.
    JSON format: {"entity_id": int, "owner_player_entity_id": int, "owner_building_entity_id": int, "name": str, "neutral": bool}
    """

    entity_id: int
    owner_player_entity_id: int
    owner_building_entity_id: int
    name: str
    neutral: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "ClaimState":
        """Create ClaimState from SpacetimeDB JSON format."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid claim_state format: expected dict, got {type(data)}")

        required_fields = ["entity_id", "owner_player_entity_id", "owner_building_entity_id", "name"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field '{field}' in claim_state data")

        return cls(
            entity_id=data["entity_id"],
            owner_player_entity_id=data["owner_player_entity_id"],
            owner_building_entity_id=data["owner_building_entity_id"],
            name=data["name"],
            neutral=data.get("neutral", False),
        )

    @classmethod
    def from_json_string(cls, json_str: str) -> "ClaimState":
        """Create ClaimState from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        """Convert to dictionary format for backward compatibility."""
        return {
            "entity_id": self.entity_id,
            "owner_player_entity_id": self.owner_player_entity_id,
            "owner_building_entity_id": self.owner_building_entity_id,
            "name": self.name,
            "neutral": self.neutral,
        }


@dataclass
class TravelerTaskState:
    """
    Data class for traveler_task_state data from SpacetimeDB.
    JSON format: {"entity_id": int, "player_entity_id": int, "traveler_id": int, "task_id": int, "completed": bool}
    """

    entity_id: int
    player_entity_id: int
    traveler_id: int
    task_id: int
    completed: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "TravelerTaskState":
        """Create TravelerTaskState from SpacetimeDB JSON format."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid traveler_task_state format: expected dict, got {type(data)}")

        required_fields = ["entity_id", "player_entity_id", "traveler_id", "task_id"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field '{field}' in traveler_task_state data")

        return cls(
            entity_id=data["entity_id"],
            player_entity_id=data["player_entity_id"],
            traveler_id=data["traveler_id"],
            task_id=data["task_id"],
            completed=data.get("completed", False),
        )

    @classmethod
    def from_json_string(cls, json_str: str) -> "TravelerTaskState":
        """Create TravelerTaskState from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_dict(self, traveler_desc_data: Optional[dict] = None, task_desc_data: Optional[dict] = None) -> dict:
        """Convert to dictionary with flat structure and enriched data"""
        # Start with base task state
        result = {
            "entity_id": self.entity_id,
            "player_entity_id": self.player_entity_id,
            "traveler_id": self.traveler_id,
            "task_id": self.task_id,
            "completed": self.completed,
        }

        # Add traveler information if available
        if traveler_desc_data and self.traveler_id in traveler_desc_data:
            traveler_data = traveler_desc_data[self.traveler_id]
            result.update(
                {
                    "traveler_name": traveler_data.get("name", f"Traveler {self.traveler_id}"),
                    "traveler_npc_type": traveler_data.get("npc_type", self.traveler_id),
                    "traveler_population": traveler_data.get("population", 0),
                    "traveler_speed": traveler_data.get("speed", 0),
                }
            )
        else:
            result.update(
                {
                    "traveler_name": f"Traveler {self.traveler_id}",
                    "traveler_npc_type": self.traveler_id,
                    "traveler_population": 0,
                    "traveler_speed": 0,
                }
            )

        # Add task description information if available
        if task_desc_data and self.task_id in task_desc_data:
            task_data = task_desc_data[self.task_id]
            result.update(
                {
                    "description": task_data.get("description", f"Unknown Task {self.task_id}"),
                    "level_requirement": task_data.get("level_requirement"),
                    "required_items": task_data.get("required_items", []),
                    "rewarded_items": task_data.get("rewarded_items", []),
                    "rewarded_experience": task_data.get("rewarded_experience"),
                }
            )
        else:
            result.update(
                {
                    "description": f"Unknown Task {self.task_id}",
                    "level_requirement": None,
                    "required_items": [],
                    "rewarded_items": [],
                    "rewarded_experience": None,
                }
            )

        # Add completion status
        result["completion_status"] = "completed" if self.completed else "pending"

        return result

    def get_task_info(self, traveler_desc_data: Optional[dict] = None, task_desc_data: Optional[dict] = None) -> dict:
        """Get enriched task information including traveler and task details"""
        info = {"traveler_info": None, "task_info": None, "completion_status": "completed" if self.completed else "pending"}

        # Add traveler information if available
        if traveler_desc_data and self.traveler_id in traveler_desc_data:
            traveler_data = traveler_desc_data[self.traveler_id]
            info["traveler_info"] = {
                "traveler_id": self.traveler_id,
                "npc_type": traveler_data.get("npc_type", 0),
                "name": traveler_data.get("name", f"Unknown Traveler {self.traveler_id}"),
                "population": traveler_data.get("population", 0.0),
                "speed": traveler_data.get("speed", 0),
                "min_time_at_ruin": traveler_data.get("min_time_at_ruin", 0),
                "max_time_at_ruin": traveler_data.get("max_time_at_ruin", 0),
                "prefab_address": traveler_data.get("prefab_address", ""),
                "icon_address": traveler_data.get("icon_address", ""),
                "force_market_mode": traveler_data.get("force_market_mode", False),
                "task_skill_check": traveler_data.get("task_skill_check", ""),
            }
        else:
            info["traveler_info"] = {
                "traveler_id": self.traveler_id,
                "npc_type": 0,
                "name": f"Traveler {self.traveler_id}",
                "population": 0.0,
                "speed": 0,
                "min_time_at_ruin": 0,
                "max_time_at_ruin": 0,
                "prefab_address": "",
                "icon_address": "",
                "force_market_mode": False,
                "task_skill_check": "",
            }

        # Add task information if available
        if task_desc_data and self.task_id in task_desc_data:
            task_data = task_desc_data[self.task_id]
            info["task_info"] = {
                "task_id": self.task_id,
                "name": task_data.get("name", f"Unknown Task {self.task_id}"),
                "description": task_data.get("description", ""),
                "reward_xp": task_data.get("reward_xp", 0),
                "reward_items": task_data.get("reward_items", []),
                "requirements": task_data.get("requirements", []),
                "difficulty": task_data.get("difficulty", "normal"),
            }
        else:
            info["task_info"] = {
                "task_id": self.task_id,
                "name": f"Task {self.task_id}",
                "description": "",
                "reward_xp": 0,
                "reward_items": [],
                "requirements": [],
                "difficulty": "unknown",
            }

        return info


@dataclass
class ClaimMemberState:
    """
    Data class for claim_member_state data from SpacetimeDB.
    JSON format: {"entity_id": int, "claim_entity_id": int, "player_entity_id": int, "user_name": str, "inventory_permission": bool, "build_permission": bool, "officer_permission": bool, "co_owner_permission": bool}
    """

    entity_id: int
    claim_entity_id: int
    player_entity_id: int
    user_name: str
    inventory_permission: bool = False
    build_permission: bool = False
    officer_permission: bool = False
    co_owner_permission: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "ClaimMemberState":
        """Create ClaimMemberState from SpacetimeDB JSON format."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid claim_member_state format: expected dict, got {type(data)}")

        required_fields = ["entity_id", "claim_entity_id", "player_entity_id", "user_name"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field '{field}' in claim_member_state data")

        return cls(
            entity_id=data["entity_id"],
            claim_entity_id=data["claim_entity_id"],
            player_entity_id=data["player_entity_id"],
            user_name=data["user_name"],
            inventory_permission=data.get("inventory_permission", False),
            build_permission=data.get("build_permission", False),
            officer_permission=data.get("officer_permission", False),
            co_owner_permission=data.get("co_owner_permission", False),
        )

    @classmethod
    def from_json_string(cls, json_str: str) -> "ClaimMemberState":
        """Create ClaimMemberState from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        """Convert to dictionary format for backward compatibility."""
        return {
            "entity_id": self.entity_id,
            "claim_entity_id": self.claim_entity_id,
            "player_entity_id": self.player_entity_id,
            "user_name": self.user_name,
            "inventory_permission": self.inventory_permission,
            "build_permission": self.build_permission,
            "officer_permission": self.officer_permission,
            "co_owner_permission": self.co_owner_permission,
        }


@dataclass
class BuildingState:
    """
    Data class for building_state data from SpacetimeDB.
    JSON format: {"entity_id": int, "claim_entity_id": int, "direction_index": int, "building_description_id": int, "constructed_by_player_entity_id": int}
    """

    entity_id: int
    claim_entity_id: int
    direction_index: int
    building_description_id: int
    constructed_by_player_entity_id: int

    @classmethod
    def from_dict(cls, data: dict) -> "BuildingState":
        """Create BuildingState from SpacetimeDB JSON format."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid building_state format: expected dict, got {type(data)}")

        required_fields = [
            "entity_id",
            "claim_entity_id",
            "direction_index",
            "building_description_id",
            "constructed_by_player_entity_id",
        ]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field '{field}' in building_state data")

        return cls(
            entity_id=data["entity_id"],
            claim_entity_id=data["claim_entity_id"],
            direction_index=data["direction_index"],
            building_description_id=data["building_description_id"],
            constructed_by_player_entity_id=data["constructed_by_player_entity_id"],
        )

    @classmethod
    def from_json_string(cls, json_str: str) -> "BuildingState":
        """Create BuildingState from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        """Convert to dictionary format for backward compatibility."""
        return {
            "entity_id": self.entity_id,
            "claim_entity_id": self.claim_entity_id,
            "direction_index": self.direction_index,
            "building_description_id": self.building_description_id,
            "constructed_by_player_entity_id": self.constructed_by_player_entity_id,
        }

    def get_building_info(self, building_desc_data: Optional[dict] = None, building_types_data: Optional[dict] = None) -> dict:
        """
        Get building information enriched with reference data.

        Args:
            building_desc_data: Optional reference data for building descriptions.
                               Should be a dict with building_description_id as key and building info as value.
            building_types_data: Optional reference data for building types.
                                Should be a dict with building_type_id as key and building type info as value.

        Returns:
            Dict with building information, enriched with reference data if provided.
        """
        # Build base building info
        building_info = {
            "entity_id": self.entity_id,
            "claim_entity_id": self.claim_entity_id,
            "direction_index": self.direction_index,
            "building_description_id": self.building_description_id,
            "constructed_by_player_entity_id": self.constructed_by_player_entity_id,
        }

        # Enrich with reference data if available
        if building_desc_data and self.building_description_id in building_desc_data:
            ref_data = building_desc_data[self.building_description_id]
            building_info.update(
                {
                    "building_name": ref_data.get("name", f"Unknown Building {self.building_description_id}"),
                    "building_description": ref_data.get("description", ""),
                    "rested_buff_duration": ref_data.get("rested_buff_duration", 0),
                    "light_radius": ref_data.get("light_radius", 0),
                    "model_asset_name": ref_data.get("model_asset_name", ""),
                    "icon_asset_name": ref_data.get("icon_asset_name", ""),
                    "unenterable": ref_data.get("unenterable", False),
                    "wilderness": ref_data.get("wilderness", False),
                    "max_health": ref_data.get("max_health", 0),
                    "ignore_damage": ref_data.get("ignore_damage", False),
                    "defense_level": ref_data.get("defense_level", 0),
                    "decay": ref_data.get("decay", 0.0),
                    "maintenance": ref_data.get("maintenance", 0.0),
                    "has_action": ref_data.get("has_action", False),
                    "show_in_compendium": ref_data.get("show_in_compendium", False),
                    "is_ruins": ref_data.get("is_ruins", False),
                    "not_deconstructible": ref_data.get("not_deconstructible", False),
                    "functions": ref_data.get("functions", ""),
                    "footprint": ref_data.get("footprint", ""),
                    "build_permission": ref_data.get("build_permission", ""),
                    "interact_permission": ref_data.get("interact_permission", ""),
                }
            )

            # Parse building type information from functions array
            building_type_info = self._parse_building_type_from_functions(ref_data.get("functions", ""), building_types_data)
            building_info.update(building_type_info)
        else:
            # Fallback when no reference data available
            building_info.update(
                {
                    "building_name": f"Building {self.building_description_id}",
                    "building_description": "",
                    "rested_buff_duration": 0,
                    "light_radius": 0,
                    "model_asset_name": "",
                    "icon_asset_name": "",
                    "unenterable": False,
                    "wilderness": False,
                    "max_health": 0,
                    "ignore_damage": False,
                    "defense_level": 0,
                    "decay": 0.0,
                    "maintenance": 0.0,
                    "has_action": False,
                    "show_in_compendium": False,
                    "is_ruins": False,
                    "not_deconstructible": False,
                    "functions": "",
                    "footprint": "",
                    "build_permission": "",
                    "interact_permission": "",
                    # Building type fallbacks
                    "building_type_id": None,
                    "building_type_name": "Unknown",
                    "building_type_category": [],
                    "building_type_actions": [],
                }
            )

        return building_info

    def _parse_building_type_from_functions(self, functions_data, building_types_data: Optional[dict] = None) -> dict:
        """
        Parse building type information from the functions array.

        Args:
            functions_data: The functions field from building description (could be string or parsed array)
            building_types_data: Optional building types reference data

        Returns:
            Dict with building type information
        """
        building_type_info = {
            "building_type_id": None,
            "building_type_name": "Unknown",
            "building_type_category": [],
            "building_type_actions": [],
        }

        # Parse functions data if it's a string
        if isinstance(functions_data, str) and functions_data:
            try:
                import json

                functions_array = json.loads(functions_data)
            except (json.JSONDecodeError, TypeError):
                return building_type_info
        elif isinstance(functions_data, list):
            functions_array = functions_data
        else:
            return building_type_info

        # Extract building type ID from first function entry
        if functions_array and len(functions_array) > 0:
            first_function = functions_array[0]
            if isinstance(first_function, list) and len(first_function) > 0:
                building_type_id = first_function[0]
                building_type_info["building_type_id"] = building_type_id

                # Enrich with building types reference data if available
                if building_types_data and building_type_id in building_types_data:
                    type_ref = building_types_data[building_type_id]
                    building_type_info.update(
                        {
                            "building_type_name": type_ref.get("name", f"Type {building_type_id}"),
                            "building_type_category": type_ref.get("category", []),
                            "building_type_actions": type_ref.get("actions", []),
                        }
                    )
                else:
                    building_type_info["building_type_name"] = f"Type {building_type_id}"

        return building_type_info


@dataclass
class InventoryState:
    """
    Data class for inventory_state data from SpacetimeDB.
    JSON format: {"entity_id": int, "pockets": list, "inventory_index": int, "cargo_index": int, "owner_entity_id": int, "player_owner_entity_id": int}

    Note: The 'pockets' field contains complex nested data representing inventory slots.
    Each pocket has format: [pocket_type, [item_state, [item_id, quantity, [enchantments], [modifiers]]], is_locked]
    """

    entity_id: int
    pockets: List = None
    inventory_index: int = 0
    cargo_index: int = 0
    owner_entity_id: int = 0
    player_owner_entity_id: int = 0

    @classmethod
    def from_array(cls, data: List) -> "InventoryState":
        """Create InventoryState from SpacetimeDB array format."""
        if not isinstance(data, list):
            raise ValueError(f"Invalid inventory_state array format: expected list, got {type(data)}")
        
        if len(data) < 6:
            raise ValueError(f"Invalid inventory_state array format: expected at least 6 elements, got {len(data)}")
        
        return cls(
            entity_id=data[0] if len(data) > 0 else 0,
            pockets=data[1] if len(data) > 1 else [],
            inventory_index=data[2] if len(data) > 2 else 0,
            cargo_index=data[3] if len(data) > 3 else 0,
            owner_entity_id=data[4] if len(data) > 4 else 0,
            player_owner_entity_id=data[5] if len(data) > 5 else 0,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "InventoryState":
        """Create InventoryState from SpacetimeDB JSON format."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid inventory_state format: expected dict, got {type(data)}")

        required_fields = ["entity_id"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field '{field}' in inventory_state data")

        return cls(
            entity_id=data["entity_id"],
            pockets=data.get("pockets", []),
            inventory_index=data.get("inventory_index", 0),
            cargo_index=data.get("cargo_index", 0),
            owner_entity_id=data.get("owner_entity_id", 0),
            player_owner_entity_id=data.get("player_owner_entity_id", 0),
        )

    @classmethod
    def from_json_string(cls, json_str: str) -> "InventoryState":
        """Create InventoryState from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        """Convert to dictionary format for backward compatibility."""
        return {
            "entity_id": self.entity_id,
            "pockets": self.pockets,
            "inventory_index": self.inventory_index,
            "cargo_index": self.cargo_index,
            "owner_entity_id": self.owner_entity_id,
            "player_owner_entity_id": self.player_owner_entity_id,
        }

    def get_items(self, item_desc_data: Optional[dict] = None) -> List[dict]:
        """
        Extract items from pockets in a more usable format.

        Args:
            item_desc_data: Optional reference data for item descriptions.
                           Should be a dict with item_id as key and item info as value.

        Returns:
            List of dicts with item information, enriched with reference data if provided.
        """
        items = []
        if not self.pockets:
            return items

        for i, pocket in enumerate(self.pockets):
            if len(pocket) >= 3:
                pocket_type = pocket[0]
                pocket_content = pocket[1]
                is_locked = pocket[2]

                # Check if pocket has an item (not empty)
                if len(pocket_content) >= 2 and pocket_content[0] == 0:
                    item_data = pocket_content[1]
                    if len(item_data) >= 2:
                        item_id = item_data[0]
                        quantity = item_data[1]
                        enchantments = item_data[2] if len(item_data) > 2 else [0, []]
                        modifiers = item_data[3] if len(item_data) > 3 else [1, []]

                        # Build base item info
                        item_info = {
                            "slot_index": i,
                            "pocket_type": pocket_type,
                            "item_id": item_id,
                            "quantity": quantity,
                            "enchantments": enchantments,
                            "modifiers": modifiers,
                            "is_locked": is_locked,
                        }

                        # Enrich with reference data if available
                        if item_desc_data and item_id in item_desc_data:
                            ref_data = item_desc_data[item_id]
                            item_info.update(
                                {
                                    "item_name": ref_data.get("name", f"Unknown Item {item_id}"),
                                    "item_description": ref_data.get("description", ""),
                                    "volume": ref_data.get("volume", 1),
                                    "durability": ref_data.get("durability", 0),
                                    "convert_to_on_durability_zero": ref_data.get("convert_to_on_durability_zero", None),
                                    "secondary_knowledge_id": ref_data.get("secondary_knowledge_id", None),
                                    "model_asset_name": ref_data.get("model_asset_name", ""),
                                    "icon_asset_name": ref_data.get("icon_asset_name", ""),
                                    "tier": ref_data.get("tier", 1),
                                    "tag": ref_data.get("tag", ""),
                                    "rarity": ref_data.get("rarity", "Common"),
                                    "compendium_entry": ref_data.get("compendium_entry", False),
                                    "item_list_id": ref_data.get("item_list_id", None),
                                }
                            )
                        else:
                            # Fallback when no reference data available
                            item_info.update(
                                {
                                    "item_name": f"Item {item_id}",
                                    "item_description": "",
                                    "volume": 1,
                                    "durability": 0,
                                    "convert_to_on_durability_zero": None,
                                    "secondary_knowledge_id": None,
                                    "model_asset_name": "",
                                    "icon_asset_name": "",
                                    "tier": -2,
                                    "tag": "",
                                    "rarity": "Unknown",
                                    "compendium_entry": False,
                                    "item_list_id": None,
                                }
                            )

                        items.append(item_info)

        return items


@dataclass
class ProgressiveActionState:
    """
    Data class for progressive_action_state data from SpacetimeDB.
    JSON format: {"entity_id": int, "building_entity_id": int, "function_type": int, "progress": int, "recipe_id": int, "craft_count": int, "last_crit_outcome": int, "owner_entity_id": int, "lock_expiration": dict, "preparation": bool}

    Note: The 'lock_expiration' field contains a timestamp object with format: {"__timestamp_micros_since_unix_epoch__": int}
    """

    entity_id: int
    building_entity_id: int
    function_type: int
    progress: int
    recipe_id: int
    craft_count: int
    last_crit_outcome: int
    owner_entity_id: int
    lock_expiration: Optional[dict] = None
    preparation: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "ProgressiveActionState":
        """Create ProgressiveActionState from SpacetimeDB JSON format."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid progressive_action_state format: expected dict, got {type(data)}")

        required_fields = [
            "entity_id",
            "building_entity_id",
            "function_type",
            "progress",
            "recipe_id",
            "craft_count",
            "last_crit_outcome",
            "owner_entity_id",
        ]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field '{field}' in progressive_action_state data")

        return cls(
            entity_id=data["entity_id"],
            building_entity_id=data["building_entity_id"],
            function_type=data["function_type"],
            progress=data["progress"],
            recipe_id=data["recipe_id"],
            craft_count=data["craft_count"],
            last_crit_outcome=data["last_crit_outcome"],
            owner_entity_id=data["owner_entity_id"],
            lock_expiration=data.get("lock_expiration", None),
            preparation=data.get("preparation", False),
        )

    @classmethod
    def from_json_string(cls, json_str: str) -> "ProgressiveActionState":
        """Create ProgressiveActionState from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_array(cls, data: List) -> "ProgressiveActionState":
        """Create ProgressiveActionState from SpacetimeDB array format."""
        if not isinstance(data, list):
            raise ValueError(f"Invalid progressive_action_state array format: expected list, got {type(data)}")
        if len(data) < 8:
            raise ValueError(f"Invalid progressive_action_state array format: expected 8+ elements, got {len(data)}")

        return cls(
            entity_id=data[0],
            building_entity_id=data[1],
            function_type=data[2],
            progress=data[3],
            recipe_id=data[4],
            craft_count=data[5],
            last_crit_outcome=data[6],
            owner_entity_id=data[7],
            lock_expiration=data[8] if len(data) > 8 else None,
            preparation=data[9] if len(data) > 9 else False,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary format for backward compatibility."""
        return {
            "entity_id": self.entity_id,
            "building_entity_id": self.building_entity_id,
            "function_type": self.function_type,
            "progress": self.progress,
            "recipe_id": self.recipe_id,
            "craft_count": self.craft_count,
            "last_crit_outcome": self.last_crit_outcome,
            "owner_entity_id": self.owner_entity_id,
            "lock_expiration": self.lock_expiration,
            "preparation": self.preparation,
        }

    def get_lock_expiration_timestamp(self) -> Optional[int]:
        """
        Extract the lock expiration timestamp in microseconds since unix epoch.

        Returns:
            Timestamp in microseconds, or None if no lock expiration set.
        """
        if self.lock_expiration and "__timestamp_micros_since_unix_epoch__" in self.lock_expiration:
            return self.lock_expiration["__timestamp_micros_since_unix_epoch__"]
        return None

    def get_lock_expiration_seconds(self) -> Optional[float]:
        """
        Extract the lock expiration timestamp in seconds since unix epoch.

        Returns:
            Timestamp in seconds, or None if no lock expiration set.
        """
        micros = self.get_lock_expiration_timestamp()
        if micros is not None:
            return micros / 1_000_000
        return None

    def is_locked(self) -> bool:
        """
        Check if the progressive action is currently locked.

        Returns:
            True if locked (has unexpired lock_expiration), False otherwise.
        """
        import time

        expiration_seconds = self.get_lock_expiration_seconds()
        if expiration_seconds is None:
            return False

        current_time = time.time()
        return current_time < expiration_seconds

    def get_progress_info(self, crafting_recipe_data: Optional[dict] = None, item_desc_data: Optional[dict] = None) -> dict:
        """
        Get progressive action information enriched with recipe data.

        Args:
            crafting_recipe_data: Optional reference data for crafting recipes.
                                 Should be a dict with recipe_id as key and recipe info as value.
            item_desc_data: Optional reference data for item descriptions.
                           Should be a dict with item_id as key and item info as value.

        Returns:
            Dict with progressive action information, enriched with recipe data if provided.
        """
        # Build base progress info
        progress_info = {
            "entity_id": self.entity_id,
            "building_entity_id": self.building_entity_id,
            "function_type": self.function_type,
            "progress": self.progress,
            "recipe_id": self.recipe_id,
            "craft_count": self.craft_count,
            "last_crit_outcome": self.last_crit_outcome,
            "owner_entity_id": self.owner_entity_id,
            "lock_expiration_timestamp": self.get_lock_expiration_timestamp(),
            "lock_expiration_seconds": self.get_lock_expiration_seconds(),
            "is_locked": self.is_locked(),
            "preparation": self.preparation,
        }

        # Enrich with recipe data if available
        if crafting_recipe_data and self.recipe_id in crafting_recipe_data:
            ref_data = crafting_recipe_data[self.recipe_id]

            # Parse time requirement (could be duration)
            time_requirement = ref_data.get("time_requirement", 0)

            progress_info.update(
                {
                    "recipe_name": ref_data.get("name", f"Unknown Recipe {self.recipe_id}"),
                    "time_requirement": time_requirement,
                    "stamina_requirement": ref_data.get("stamina_requirement", 0),
                    "tool_durability_lost": ref_data.get("tool_durability_lost", 0),
                    "building_requirement": ref_data.get("building_requirement", ""),
                    "level_requirements": self._parse_json_field(ref_data.get("level_requirements", "")),
                    "tool_requirements": self._parse_json_field(ref_data.get("tool_requirements", "")),
                    "discovery_triggers": self._parse_json_field(ref_data.get("discovery_triggers", "")),
                    "required_claim_tech_id": ref_data.get("required_claim_tech_id", 0),
                    "full_discovery_score": ref_data.get("full_discovery_score", 0.0),
                    "experience_per_progress": self._parse_json_field(ref_data.get("experience_per_progress", "")),
                    "actions_required": ref_data.get("actions_required", 0),
                    "tool_mesh_index": ref_data.get("tool_mesh_index", 0),
                    "recipe_performance_id": ref_data.get("recipe_performance_id", 0),
                    "required_knowledges": self._parse_json_field(ref_data.get("required_knowledges", "")),
                    "blocking_knowledges": self._parse_json_field(ref_data.get("blocking_knowledges", "")),
                    "hide_without_required_knowledge": ref_data.get("hide_without_required_knowledge", False),
                    "hide_with_blocking_knowledges": ref_data.get("hide_with_blocking_knowledges", False),
                    "allow_use_hands": ref_data.get("allow_use_hands", False),
                    "is_passive": ref_data.get("is_passive", False),
                }
            )

            # Parse and enrich consumed item stacks
            consumed_items = self._parse_item_stacks(ref_data.get("consumed_item_stacks", ""), item_desc_data)
            progress_info["consumed_items"] = consumed_items

            # Parse and enrich crafted item stacks
            crafted_items = self._parse_item_stacks(ref_data.get("crafted_item_stacks", ""), item_desc_data)
            progress_info["crafted_items"] = crafted_items

            # Calculate progress percentage if we have time requirement
            if time_requirement > 0:
                progress_info["progress_percentage"] = min(100.0, (self.progress / time_requirement) * 100.0)
            else:
                progress_info["progress_percentage"] = 0.0
        else:
            # Fallback when no recipe data available
            progress_info.update(
                {
                    "recipe_name": f"Recipe {self.recipe_id}",
                    "time_requirement": 0,
                    "stamina_requirement": 0,
                    "tool_durability_lost": 0,
                    "building_requirement": "",
                    "level_requirements": [],
                    "tool_requirements": [],
                    "consumed_items": [],
                    "crafted_items": [],
                    "discovery_triggers": [],
                    "required_claim_tech_id": 0,
                    "full_discovery_score": 0.0,
                    "experience_per_progress": [],
                    "actions_required": 0,
                    "tool_mesh_index": 0,
                    "recipe_performance_id": 0,
                    "required_knowledges": [],
                    "blocking_knowledges": [],
                    "hide_without_required_knowledge": False,
                    "hide_with_blocking_knowledges": False,
                    "allow_use_hands": False,
                    "is_passive": False,
                    "progress_percentage": 0.0,
                }
            )

        return progress_info

    def _parse_json_field(self, field_value: str) -> list:
        """Parse JSON string fields, return empty list if parsing fails."""
        if not field_value or field_value == "":
            return []

        try:
            import json

            return json.loads(field_value)
        except (json.JSONDecodeError, TypeError):
            return []

    def _parse_item_stacks(self, item_stacks_str: str, item_desc_data: Optional[dict] = None) -> List[dict]:
        """
        Parse item stacks JSON string and enrich with item descriptions.

        Args:
            item_stacks_str: JSON string like "[[4130001, 40, [0, []], 1, 1.0]]"
            item_desc_data: Optional item description reference data

        Returns:
            List of enriched item stack dictionaries
        """
        if not item_stacks_str or item_stacks_str == "":
            return []

        try:
            import json

            item_stacks = item_stacks_str
            # item_stacks = json.loads(item_stacks_str)

            enriched_items = []
            for stack in item_stacks:
                if len(stack) >= 2:
                    item_id = stack[0]
                    quantity = stack[1]
                    enchantments = stack[2] if len(stack) > 2 else [0, []]
                    unknown_field1 = stack[3] if len(stack) > 3 else 1
                    unknown_field2 = stack[4] if len(stack) > 4 else 1.0

                    item_info = {
                        "item_id": item_id,
                        "quantity": quantity,
                        "enchantments": enchantments,
                        "unknown_field1": unknown_field1,
                        "unknown_field2": unknown_field2,
                    }

                    # Enrich with item description if available
                    if item_desc_data and item_id in item_desc_data:
                        item_ref = item_desc_data[item_id]
                        item_info.update(
                            {
                                "item_name": item_ref.get("name", f"Unknown Item {item_id}"),
                                "item_description": item_ref.get("description", ""),
                                "volume": item_ref.get("volume", 1),
                                "durability": item_ref.get("durability", 0),
                                "icon_asset_name": item_ref.get("icon_asset_name", ""),
                                "tier": item_ref.get("tier", 1),
                                "tag": item_ref.get("tag", ""),
                                "rarity": item_ref.get("rarity", "Common"),
                            }
                        )
                    else:
                        item_info.update(
                            {
                                "item_name": f"Item {item_id}",
                                "item_description": "",
                                "volume": 1,
                                "durability": 0,
                                "icon_asset_name": "",
                                "tier": 1,
                                "tag": "",
                                "rarity": "Unknown",
                            }
                        )

                    enriched_items.append(item_info)

            return enriched_items

        except (json.JSONDecodeError, TypeError, IndexError) as e:
            return []


@dataclass
class PublicProgressiveActionState:
    """
    Data class for public_progressive_action_state data from SpacetimeDB.
    JSON format: {"entity_id": int, "building_entity_id": int, "owner_entity_id": int}

    Note: This represents progressive actions that are publicly visible and accepting help from other players.
    """

    entity_id: int
    building_entity_id: int
    owner_entity_id: int

    @classmethod
    def from_dict(cls, data: dict) -> "PublicProgressiveActionState":
        """Create PublicProgressiveActionState from SpacetimeDB JSON format."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid public_progressive_action_state format: expected dict, got {type(data)}")

        required_fields = ["entity_id", "building_entity_id", "owner_entity_id"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field '{field}' in public_progressive_action_state data")

        return cls(
            entity_id=data["entity_id"],
            building_entity_id=data["building_entity_id"],
            owner_entity_id=data["owner_entity_id"],
        )

    @classmethod
    def from_json_string(cls, json_str: str) -> "PublicProgressiveActionState":
        """Create PublicProgressiveActionState from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        """Convert to dictionary format for backward compatibility."""
        return {
            "entity_id": self.entity_id,
            "building_entity_id": self.building_entity_id,
            "owner_entity_id": self.owner_entity_id,
        }

    def get_public_action_info(
        self,
        building_desc_data: Optional[dict] = None,
        crafting_recipe_data: Optional[dict] = None,
    ) -> dict:
        """
        Get public progressive action information enriched with reference data.

        Args:
            building_desc_data: Optional reference data for building descriptions.
            crafting_recipe_data: Optional reference data for crafting recipes.

        Returns:
            Dict with public progressive action information, enriched with reference data if provided.
        """
        # Build base public action info
        action_info = {
            "entity_id": self.entity_id,
            "building_entity_id": self.building_entity_id,
            "owner_entity_id": self.owner_entity_id,
            "is_public": True,  # This is always true for public progressive actions
            "accepts_help": True,  # Public actions accept help from other players
        }

        # Enrich with building data if available
        if building_desc_data and self.building_entity_id in building_desc_data:
            building_data = building_desc_data[self.building_entity_id]
            action_info.update(
                {
                    "building_name": building_data.get("name", f"Unknown Building {self.building_entity_id}"),
                    "building_description": building_data.get("description", ""),
                    "building_has_action": building_data.get("has_action", False),
                }
            )
        else:
            action_info.update(
                {
                    "building_name": f"Building {self.building_entity_id}",
                    "building_description": "",
                    "building_has_action": False,
                }
            )

        return action_info


@dataclass
class PassiveCraftState:
    """Data class for passive crafting state objects from SpacetimeDB"""

    entity_id: int
    owner_entity_id: int
    recipe_id: int
    building_entity_id: int
    building_description_id: int
    timestamp: dict
    status: list
    slot: list

    @classmethod
    def from_dict(cls, data: dict) -> "PassiveCraftState":
        """Create PassiveCraftState from dictionary data"""
        return cls(
            entity_id=data.get("entity_id", 0),
            owner_entity_id=data.get("owner_entity_id", 0),
            recipe_id=data.get("recipe_id", 0),
            building_entity_id=data.get("building_entity_id", 0),
            building_description_id=data.get("building_description_id", 0),
            timestamp=data.get("timestamp", {}),
            status=data.get("status", []),
            slot=data.get("slot", []),
        )

    @classmethod
    def from_json_string(cls, json_str: str) -> "PassiveCraftState":
        """Create PassiveCraftState from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_dict(self, crafting_recipe_data: Optional[list] = None, building_desc_data: Optional[list] = None) -> dict:
        """Convert to dictionary with optional enrichment data"""
        result = {
            "entity_id": self.entity_id,
            "owner_entity_id": self.owner_entity_id,
            "recipe_id": self.recipe_id,
            "building_entity_id": self.building_entity_id,
            "timestamp": self.timestamp,
            "status": self.status,
            "slot": self.slot,
            "craft_info": self.get_craft_info(crafting_recipe_data, building_desc_data),
        }
        return result

    def get_craft_info(self, crafting_recipe_data: Optional[list] = None, building_desc_data: Optional[list] = None) -> dict:
        """Get enriched crafting information including recipe and building details"""
        info = {
            "recipe_info": None,
            "building_info": None,
            "status_info": self._parse_status(),
            "slot_info": self._parse_slot(),
            "timestamp_info": self._parse_timestamp(),
        }

        # Add recipe information if available
        if crafting_recipe_data:
            for key, values in crafting_recipe_data.items():
                if values.get("id") == self.recipe_id:
                    info["recipe_info"] = {
                        "id": values.get("id"),
                        "name": values.get("name", "Unknown Recipe"),
                        "description": values.get("description", ""),
                        "duration_seconds": values.get("duration_seconds", 0),
                        "skill_id": values.get("skill_id"),
                        "building_type_id": values.get("building_type_id"),
                        "inputs": values.get("inputs", []),
                        "outputs": values.get("outputs", []),
                    }
                    break

        # Add building information if available
        if building_desc_data:
            for key, values in building_desc_data.items():
                if values.get("id") == self.building_description_id:
                    info["building_info"] = {
                        "entity_id": values.get("entity_id"),
                        "name": values.get("name", "Unknown Building"),
                        "description": values.get("description", ""),
                        "building_type_id": values.get("building_type_id"),
                        "owner_entity_id": values.get("owner_entity_id"),
                        "claim_entity_id": values.get("claim_entity_id"),
                        "coords": values.get("coords", {}),
                        "created_timestamp": values.get("created_timestamp", {}),
                    }
                    break
        # print(info)
        return info

    def _parse_status(self) -> dict:
        """Parse the status array into meaningful information"""
        if not self.status or len(self.status) < 2:
            return {"status_type": "unknown", "status_value": None}

        status_type = self.status[0]
        status_data = self.status[1]

        status_map = {0: "queued", 1: "in_progress", 2: "completed", 3: "failed", 4: "cancelled"}

        return {"status_type": status_map.get(status_type, f"unknown_{status_type}"), "status_value": status_data}

    def _parse_slot(self) -> dict:
        """Parse the slot array into meaningful information"""
        if not self.slot or len(self.slot) < 2:
            return {"slot_number": None, "slot_data": None}

        return {"slot_number": self.slot[0], "slot_data": self.slot[1]}

    def _parse_timestamp(self) -> dict:
        """Parse timestamp object into readable format"""
        if not self.timestamp:
            return {"timestamp_micros": None, "readable_time": None}

        timestamp_micros = self.timestamp.get("__timestamp_micros_since_unix_epoch__")
        if timestamp_micros:
            # Convert microseconds to seconds for datetime
            timestamp_seconds = timestamp_micros / 1_000_000
            readable_time = datetime.fromtimestamp(timestamp_seconds).isoformat()
            return {"timestamp_micros": timestamp_micros, "readable_time": readable_time}

        return {"timestamp_micros": None, "readable_time": None}


# ==============================================================================
# REFERENCE DATA DATACLASSES
# ==============================================================================
# These dataclasses represent static reference data from BitCraft's database
# that rarely changes but provides essential game information.

@dataclass
class ResourceDesc:
    """Resource description data from resource_desc table."""
    id: int
    name: str
    description: str
    flattenable: bool
    max_health: int
    ignore_damage: bool
    despawn_time: float
    model_asset_name: str
    icon_asset_name: str
    on_destroy_yield: List
    on_destroy_yield_resource_id: int
    spawn_priority: int
    footprint: List
    tier: int
    tag: str
    rarity: List
    compendium_entry: bool
    enemy_params_id: List
    scheduled_respawn_time: float
    not_respawning: bool

    @classmethod
    def from_dict(cls, data: dict) -> "ResourceDesc":
        """Create ResourceDesc from subscription data."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid resource_desc format: expected dict, got {type(data)}")

        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            description=data.get("description", ""),
            flattenable=data.get("flattenable", False),
            max_health=data.get("max_health", 0),
            ignore_damage=data.get("ignore_damage", False),
            despawn_time=data.get("despawn_time", 0.0),
            model_asset_name=data.get("model_asset_name", ""),
            icon_asset_name=data.get("icon_asset_name", ""),
            on_destroy_yield=data.get("on_destroy_yield", []),
            on_destroy_yield_resource_id=data.get("on_destroy_yield_resource_id", 0),
            spawn_priority=data.get("spawn_priority", 1),
            footprint=data.get("footprint", []),
            tier=data.get("tier", 0),
            tag=data.get("tag", ""),
            rarity=data.get("rarity", [0, {}]),
            compendium_entry=data.get("compendium_entry", False),
            enemy_params_id=data.get("enemy_params_id", []),
            scheduled_respawn_time=data.get("scheduled_respawn_time", 0.0),
            not_respawning=data.get("not_respawning", False),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary format for backward compatibility."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "flattenable": self.flattenable,
            "max_health": self.max_health,
            "ignore_damage": self.ignore_damage,
            "despawn_time": self.despawn_time,
            "model_asset_name": self.model_asset_name,
            "icon_asset_name": self.icon_asset_name,
            "on_destroy_yield": self.on_destroy_yield,
            "on_destroy_yield_resource_id": self.on_destroy_yield_resource_id,
            "spawn_priority": self.spawn_priority,
            "footprint": self.footprint,
            "tier": self.tier,
            "tag": self.tag,
            "rarity": self.rarity,
            "compendium_entry": self.compendium_entry,
            "enemy_params_id": self.enemy_params_id,
            "scheduled_respawn_time": self.scheduled_respawn_time,
            "not_respawning": self.not_respawning,
        }

    def get_yield_items(self) -> List[dict]:
        """Parse on_destroy_yield into readable format."""
        items = []
        for yield_data in self.on_destroy_yield:
            if isinstance(yield_data, list) and len(yield_data) >= 2:
                items.append({
                    "item_id": yield_data[0],
                    "quantity": yield_data[1],
                    "rarity_data": yield_data[2] if len(yield_data) > 2 else [0, []],
                    "bonus_data": yield_data[3] if len(yield_data) > 3 else [0, 0]
                })
        return items


@dataclass
class ItemDesc:
    """Item description data from item_desc table."""
    id: int
    name: str
    description: str
    volume: int
    durability: int
    convert_to_on_durability_zero: int
    secondary_knowledge_id: int
    model_asset_name: str
    icon_asset_name: str
    tier: int
    tag: str
    rarity: List
    compendium_entry: bool
    item_list_id: int

    @classmethod
    def from_dict(cls, data: dict) -> "ItemDesc":
        """Create ItemDesc from subscription data."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid item_desc format: expected dict, got {type(data)}")

        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            description=data.get("description", ""),
            volume=data.get("volume", 0),
            durability=data.get("durability", 0),
            convert_to_on_durability_zero=data.get("convert_to_on_durability_zero", 0),
            secondary_knowledge_id=data.get("secondary_knowledge_id", 0),
            model_asset_name=data.get("model_asset_name", ""),
            icon_asset_name=data.get("icon_asset_name", ""),
            tier=data.get("tier", 0),
            tag=data.get("tag", ""),
            rarity=data.get("rarity", [0, {}]),
            compendium_entry=data.get("compendium_entry", False),
            item_list_id=data.get("item_list_id", 0),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary format for backward compatibility."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "volume": self.volume,
            "durability": self.durability,
            "convert_to_on_durability_zero": self.convert_to_on_durability_zero,
            "secondary_knowledge_id": self.secondary_knowledge_id,
            "model_asset_name": self.model_asset_name,
            "icon_asset_name": self.icon_asset_name,
            "tier": self.tier,
            "tag": self.tag,
            "rarity": self.rarity,
            "compendium_entry": self.compendium_entry,
            "item_list_id": self.item_list_id,
        }

    def is_valuable(self) -> bool:
        """Check if item has high tier or rarity."""
        if self.tier >= 6:
            return True
        if isinstance(self.rarity, list) and len(self.rarity) > 0 and self.rarity[0] >= 2:
            return True
        return False


@dataclass
class CargoDesc:
    """Cargo description data from cargo_desc table."""
    id: int
    name: str
    description: str
    volume: int
    secondary_knowledge_id: int
    model_asset_name: str
    icon_asset_name: str
    carried_model_asset_name: str
    pick_up_animation_start: str
    pick_up_animation_end: str
    drop_animation_start: str
    drop_animation_end: str
    pick_up_time: float
    place_time: float
    animator_state: str
    movement_modifier: float
    blocks_path: bool
    on_destroy_yield_cargos: List
    despawn_time: float
    tier: int
    tag: str
    rarity: List
    not_pickupable: bool

    @classmethod
    def from_dict(cls, data: dict) -> "CargoDesc":
        """Create CargoDesc from subscription data."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid cargo_desc format: expected dict, got {type(data)}")

        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            description=data.get("description", ""),
            volume=data.get("volume", 0),
            secondary_knowledge_id=data.get("secondary_knowledge_id", 0),
            model_asset_name=data.get("model_asset_name", ""),
            icon_asset_name=data.get("icon_asset_name", ""),
            carried_model_asset_name=data.get("carried_model_asset_name", ""),
            pick_up_animation_start=data.get("pick_up_animation_start", ""),
            pick_up_animation_end=data.get("pick_up_animation_end", ""),
            drop_animation_start=data.get("drop_animation_start", ""),
            drop_animation_end=data.get("drop_animation_end", ""),
            pick_up_time=data.get("pick_up_time", 0.0),
            place_time=data.get("place_time", 0.0),
            animator_state=data.get("animator_state", ""),
            movement_modifier=data.get("movement_modifier", 0.0),
            blocks_path=data.get("blocks_path", False),
            on_destroy_yield_cargos=data.get("on_destroy_yield_cargos", []),
            despawn_time=data.get("despawn_time", 0.0),
            tier=data.get("tier", 0),
            tag=data.get("tag", ""),
            rarity=data.get("rarity", [0, {}]),
            not_pickupable=data.get("not_pickupable", False),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary format for backward compatibility."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "volume": self.volume,
            "secondary_knowledge_id": self.secondary_knowledge_id,
            "model_asset_name": self.model_asset_name,
            "icon_asset_name": self.icon_asset_name,
            "carried_model_asset_name": self.carried_model_asset_name,
            "pick_up_animation_start": self.pick_up_animation_start,
            "pick_up_animation_end": self.pick_up_animation_end,
            "drop_animation_start": self.drop_animation_start,
            "drop_animation_end": self.drop_animation_end,
            "pick_up_time": self.pick_up_time,
            "place_time": self.place_time,
            "animator_state": self.animator_state,
            "movement_modifier": self.movement_modifier,
            "blocks_path": self.blocks_path,
            "on_destroy_yield_cargos": self.on_destroy_yield_cargos,
            "despawn_time": self.despawn_time,
            "tier": self.tier,
            "tag": self.tag,
            "rarity": self.rarity,
            "not_pickupable": self.not_pickupable,
        }

    def get_handling_info(self) -> dict:
        """Get pickup and placement timing information."""
        return {
            "pick_up_time": self.pick_up_time,
            "place_time": self.place_time,
            "movement_modifier": self.movement_modifier,
            "blocks_path": self.blocks_path,
            "pickupable": not self.not_pickupable,
        }


@dataclass
class BuildingDesc:
    """Building description data from building_desc table."""
    id: int
    functions: List
    name: str
    description: str
    rested_buff_duration: int
    light_radius: int
    model_asset_name: str
    icon_asset_name: str
    unenterable: bool
    wilderness: bool
    footprint: List
    max_health: int
    ignore_damage: bool
    defense_level: int
    decay: float
    maintenance: float
    build_permission: List
    interact_permission: List
    has_action: bool
    show_in_compendium: bool
    is_ruins: bool
    not_deconstructible: bool

    @classmethod
    def from_dict(cls, data: dict) -> "BuildingDesc":
        """Create BuildingDesc from subscription data."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid building_desc format: expected dict, got {type(data)}")

        return cls(
            id=data.get("id", 0),
            functions=data.get("functions", []),
            name=data.get("name", ""),
            description=data.get("description", ""),
            rested_buff_duration=data.get("rested_buff_duration", 0),
            light_radius=data.get("light_radius", 0),
            model_asset_name=data.get("model_asset_name", ""),
            icon_asset_name=data.get("icon_asset_name", ""),
            unenterable=data.get("unenterable", False),
            wilderness=data.get("wilderness", False),
            footprint=data.get("footprint", []),
            max_health=data.get("max_health", -1),
            ignore_damage=data.get("ignore_damage", False),
            defense_level=data.get("defense_level", 0),
            decay=data.get("decay", 0.0),
            maintenance=data.get("maintenance", 0.0),
            build_permission=data.get("build_permission", [0, {}]),
            interact_permission=data.get("interact_permission", [0, {}]),
            has_action=data.get("has_action", False),
            show_in_compendium=data.get("show_in_compendium", False),
            is_ruins=data.get("is_ruins", False),
            not_deconstructible=data.get("not_deconstructible", False),
        )

    def get_building_footprint_size(self) -> tuple:
        """Calculate building dimensions from footprint coordinates."""
        if not self.footprint:
            return (0, 0)

        x_coords = []
        y_coords = []
        for coord in self.footprint:
            if isinstance(coord, list) and len(coord) >= 2:
                x_coords.append(coord[0])
                y_coords.append(coord[1])

        if not x_coords or not y_coords:
            return (0, 0)

        width = max(x_coords) - min(x_coords) + 1
        height = max(y_coords) - min(y_coords) + 1
        return (width, height)

    def to_dict(self) -> dict:
        """Convert to dictionary format for backward compatibility."""
        return {
            "id": self.id,
            "functions": self.functions,
            "name": self.name,
            "description": self.description,
            "rested_buff_duration": self.rested_buff_duration,
            "light_radius": self.light_radius,
            "model_asset_name": self.model_asset_name,
            "icon_asset_name": self.icon_asset_name,
            "unenterable": self.unenterable,
            "wilderness": self.wilderness,
            "footprint": self.footprint,
            "max_health": self.max_health,
            "ignore_damage": self.ignore_damage,
            "defense_level": self.defense_level,
            "decay": self.decay,
            "maintenance": self.maintenance,
            "build_permission": self.build_permission,
            "interact_permission": self.interact_permission,
            "has_action": self.has_action,
            "show_in_compendium": self.show_in_compendium,
            "is_ruins": self.is_ruins,
            "not_deconstructible": self.not_deconstructible,
        }

    def get_function_info(self) -> List[dict]:
        """Parse complex building functions data."""
        parsed_functions = []
        for func in self.functions:
            if isinstance(func, list) and len(func) >= 16:
                parsed_functions.append({
                    "function_type": func[0],
                    "param_1": func[1],
                    "param_2": func[2],
                    "param_3": func[3],
                    "param_4": func[4],
                    "param_5": func[5],
                    "param_6": func[6],
                    "inventory_size": func[7],
                    "cargo_size": func[8],
                    "param_9": func[9],
                    # Additional parameters as needed
                })
        return parsed_functions


@dataclass
class BuildingTypeDesc:
    """Building type description data from building_type_desc table."""
    id: int
    name: str
    category: List
    actions: List

    @classmethod
    def from_dict(cls, data: dict) -> "BuildingTypeDesc":
        """Create BuildingTypeDesc from subscription data."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid building_type_desc format: expected dict, got {type(data)}")

        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            category=data.get("category", [0, {}]),
            actions=data.get("actions", []),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary format for backward compatibility."""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "actions": self.actions,
        }


@dataclass
class CraftingRecipeDesc:
    """Crafting recipe description data from crafting_recipe_desc table."""
    id: int
    name: str
    time_requirement: float
    stamina_requirement: float
    tool_durability_lost: int
    building_requirement: List
    level_requirements: List
    tool_requirements: List
    consumed_item_stacks: List
    discovery_triggers: List
    required_claim_tech_id: int
    full_discovery_score: int
    experience_per_progress: List
    crafted_item_stacks: List
    actions_required: int
    tool_mesh_index: int
    recipe_performance_id: int
    required_knowledges: List
    blocking_knowledges: List
    hide_without_required_knowledge: bool
    hide_with_blocking_knowledges: bool
    allow_use_hands: bool
    is_passive: bool

    @classmethod
    def from_dict(cls, data: dict) -> "CraftingRecipeDesc":
        """Create CraftingRecipeDesc from subscription data."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid crafting_recipe_desc format: expected dict, got {type(data)}")

        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            time_requirement=data.get("time_requirement", 0.0),
            stamina_requirement=data.get("stamina_requirement", 0.0),
            tool_durability_lost=data.get("tool_durability_lost", 0),
            building_requirement=data.get("building_requirement", [0, {}]),
            level_requirements=data.get("level_requirements", []),
            tool_requirements=data.get("tool_requirements", []),
            consumed_item_stacks=data.get("consumed_item_stacks", []),
            discovery_triggers=data.get("discovery_triggers", []),
            required_claim_tech_id=data.get("required_claim_tech_id", 0),
            full_discovery_score=data.get("full_discovery_score", 0),
            experience_per_progress=data.get("experience_per_progress", []),
            crafted_item_stacks=data.get("crafted_item_stacks", []),
            actions_required=data.get("actions_required", 1),
            tool_mesh_index=data.get("tool_mesh_index", 0),
            recipe_performance_id=data.get("recipe_performance_id", 0),
            required_knowledges=data.get("required_knowledges", []),
            blocking_knowledges=data.get("blocking_knowledges", []),
            hide_without_required_knowledge=data.get("hide_without_required_knowledge", False),
            hide_with_blocking_knowledges=data.get("hide_with_blocking_knowledges", False),
            allow_use_hands=data.get("allow_use_hands", False),
            is_passive=data.get("is_passive", False),
        )

    def get_recipe_summary(self) -> dict:
        """Get human-readable recipe requirements and outputs."""
        return {
            "name": self.name,
            "time_required": self.time_requirement,
            "actions_required": self.actions_required,
            "stamina_cost": self.stamina_requirement,
            "inputs": len(self.consumed_item_stacks),
            "outputs": len(self.crafted_item_stacks),
            "is_passive": self.is_passive,
        }

    def to_dict(self) -> dict:
        """Convert to dictionary format for backward compatibility."""
        return {
            "id": self.id,
            "name": self.name,
            "time_requirement": self.time_requirement,
            "stamina_requirement": self.stamina_requirement,
            "tool_durability_lost": self.tool_durability_lost,
            "building_requirement": self.building_requirement,
            "level_requirements": self.level_requirements,
            "tool_requirements": self.tool_requirements,
            "consumed_item_stacks": self.consumed_item_stacks,
            "discovery_triggers": self.discovery_triggers,
            "required_claim_tech_id": self.required_claim_tech_id,
            "full_discovery_score": self.full_discovery_score,
            "experience_per_progress": self.experience_per_progress,
            "crafted_item_stacks": self.crafted_item_stacks,
            "actions_required": self.actions_required,
            "tool_mesh_index": self.tool_mesh_index,
            "recipe_performance_id": self.recipe_performance_id,
            "required_knowledges": self.required_knowledges,
            "blocking_knowledges": self.blocking_knowledges,
            "hide_without_required_knowledge": self.hide_without_required_knowledge,
            "hide_with_blocking_knowledges": self.hide_with_blocking_knowledges,
            "allow_use_hands": self.allow_use_hands,
            "is_passive": self.is_passive,
        }

    def calculate_efficiency(self) -> float:
        """Calculate efficiency as outputs per time unit."""
        if self.time_requirement <= 0:
            return 0.0
        return len(self.crafted_item_stacks) / self.time_requirement


@dataclass
class ClaimTileCost:
    """Claim tile cost data from claim_tile_cost table."""
    tile_count: int
    cost_per_tile: float

    @classmethod
    def from_dict(cls, data: dict) -> "ClaimTileCost":
        """Create ClaimTileCost from subscription data."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid claim_tile_cost format: expected dict, got {type(data)}")

        return cls(
            tile_count=data.get("tile_count", 0),
            cost_per_tile=data.get("cost_per_tile", 0.0),
        )

    @classmethod
    def from_list(cls, data_list: List[dict]) -> List["ClaimTileCost"]:
        """Create list of ClaimTileCost from subscription data."""
        return [cls.from_dict(item) for item in data_list]

    @staticmethod
    def calculate_expansion_cost(cost_tiers: List["ClaimTileCost"], current_tiles: int, target_tiles: int) -> float:
        """Calculate cost for expanding claim from current to target tiles."""
        if target_tiles <= current_tiles:
            return 0.0

        total_cost = 0.0
        tiles_to_expand = target_tiles - current_tiles

        # Find the appropriate cost tier
        for tier in sorted(cost_tiers, key=lambda x: x.tile_count):
            if current_tiles + 1 >= tier.tile_count:
                cost_per_tile = tier.cost_per_tile
            else:
                break

        return tiles_to_expand * cost_per_tile

    def to_dict(self) -> dict:
        """Convert to dictionary format for backward compatibility."""
        return {
            "tile_count": self.tile_count,
            "cost_per_tile": self.cost_per_tile,
        }


@dataclass
class NpcDesc:
    """NPC description data from npc_desc table (formerly traveler_desc)."""
    npc_type: int
    name: str
    population: float
    speed: int
    min_time_at_ruin: int
    max_time_at_ruin: int
    prefab_address: str
    icon_address: str
    force_market_mode: bool
    task_skill_check: List[int]

    @classmethod
    def from_dict(cls, data: dict) -> "NpcDesc":
        """Create NpcDesc from subscription data."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid npc_desc format: expected dict, got {type(data)}")

        return cls(
            npc_type=data.get("npc_type", 0),
            name=data.get("name", ""),
            population=data.get("population", 0.0),
            speed=data.get("speed", 0),
            min_time_at_ruin=data.get("min_time_at_ruin", 0),
            max_time_at_ruin=data.get("max_time_at_ruin", 0),
            prefab_address=data.get("prefab_address", ""),
            icon_address=data.get("icon_address", ""),
            force_market_mode=data.get("force_market_mode", False),
            task_skill_check=data.get("task_skill_check", []),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary format for backward compatibility."""
        return {
            "npc_type": self.npc_type,
            "name": self.name,
            "population": self.population,
            "speed": self.speed,
            "min_time_at_ruin": self.min_time_at_ruin,
            "max_time_at_ruin": self.max_time_at_ruin,
            "prefab_address": self.prefab_address,
            "icon_address": self.icon_address,
            "force_market_mode": self.force_market_mode,
            "task_skill_check": self.task_skill_check,
        }

    def get_skill_requirements(self) -> List[int]:
        """Get list of required skill IDs for this NPC's tasks."""
        return self.task_skill_check.copy() if self.task_skill_check else []



@dataclass
class BuildingFunctionTypeMappingDesc:
    """
    Building function type mapping descriptor for SpacetimeDB building_function_type_mapping_desc table.
    
    Maps type IDs to arrays of description IDs for building function type lookups.
    Replaces the old type_desc_ids SQLite table.
    """
    
    type_id: int
    desc_ids: List[int]
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create instance from dictionary (subscription data)."""
        return cls(
            type_id=data.get("type_id", 0),
            desc_ids=data.get("desc_ids", [])
        )
    
    @classmethod 
    def from_array(cls, data: list):
        """Create instance from array (transaction data)."""
        if not isinstance(data, list) or len(data) < 2:
            raise ValueError(f"BuildingFunctionTypeMappingDesc requires array with at least 2 elements, got: {data}")
            
        return cls(
            type_id=data[0] if len(data) > 0 else 0,
            desc_ids=data[1] if len(data) > 1 else []
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for backward compatibility."""
        return {
            "type_id": self.type_id,
            "desc_ids": self.desc_ids.copy() if self.desc_ids else []
        }
    
    def contains_desc_id(self, desc_id: int) -> bool:
        """Check if a description ID is contained in this mapping."""
        return desc_id in (self.desc_ids or [])
    
    def get_desc_count(self) -> int:
        """Get the number of description IDs in this mapping."""
        return len(self.desc_ids or [])
