"""
Item Lookup Service for efficient item reference data access.

This service consolidates the item lookup functionality that was previously duplicated
across multiple processors, providing a single source of truth for item data access.
"""

import logging
from typing import Dict, Optional, Tuple, Any, List


class ItemLookupService:
    """
    Service for looking up item, building, and recipe information from reference data.
    
    Handles compound keys to prevent ID conflicts between different item tables
    and provides efficient lookup methods with fallback strategies.
    """

    def __init__(self, reference_data: Dict[str, Any]):
        """
        Initialize the service with reference data.
        
        Args:
            reference_data: Dictionary containing game reference data (items, recipes, buildings, etc.)
        """
        self.reference_data = reference_data
        self._item_lookups: Optional[Dict] = None
        self._building_lookups: Optional[Dict] = None
        self._recipe_lookups: Optional[Dict] = None
        self._initialize_lookups()

    def _initialize_lookups(self):
        """Initialize all lookup caches."""
        self._item_lookups = self._build_item_lookups()
        self._building_lookups = self._build_building_lookups()
        self._recipe_lookups = self._build_recipe_lookups()

    def _build_item_lookups(self) -> Dict:
        """
        Create combined item lookup dictionary from all reference data sources.

        Uses compound keys (item_id, item_name) to prevent ID conflicts between tables.
        Example: item_id 5 can be "Damaged Ancient Gear" OR "Maple Sapling" - both are unique.

        Returns:
            Dictionary mapping (item_id, item_name) to item details and (item_id, table_source) for explicit lookups
        """
        try:
            item_lookups = {}

            # Combine all item reference data with both compound key types
            for data_source in ["resource_desc", "item_desc", "cargo_desc"]:
                items = self.reference_data.get(data_source, [])
                for item in items:
                    item_id = item.get("id")
                    item_name = item.get("name", "")
                    
                    if item_id is not None and item_name:
                        # Primary key: (item_id, item_name) - naturally unique
                        name_key = (item_id, item_name)
                        item_lookups[name_key] = item
                        
                        # Secondary key: (item_id, table_source) - for explicit table lookups
                        table_key = (item_id, data_source)
                        item_lookups[table_key] = item

            return item_lookups

        except Exception as e:
            logging.error(f"ItemLookupService: Error creating item lookups: {e}")
            return {}

    def _build_building_lookups(self) -> Dict:
        """
        Create building lookup dictionary from building_desc reference data.
        
        Returns:
            Dictionary mapping building_description_id to building details
        """
        try:
            building_lookups = {}
            
            buildings = self.reference_data.get("building_desc", [])
            for building in buildings:
                building_id = building.get("id")
                if building_id is not None:
                    building_lookups[building_id] = building
                    
            return building_lookups
            
        except Exception as e:
            logging.error(f"ItemLookupService: Error creating building lookups: {e}")
            return {}

    def _build_recipe_lookups(self) -> Dict:
        """
        Create recipe lookup dictionary from crafting_recipe_desc reference data.
        
        Returns:
            Dictionary mapping recipe_id to recipe details
        """
        try:
            recipe_lookups = {}
            
            recipes = self.reference_data.get("crafting_recipe_desc", [])
            for recipe in recipes:
                recipe_id = recipe.get("id")
                if recipe_id is not None:
                    recipe_lookups[recipe_id] = recipe
                    
            return recipe_lookups
            
        except Exception as e:
            logging.error(f"ItemLookupService: Error creating recipe lookups: {e}")
            return {}

    def lookup_item_by_id(self, item_id: int, table_source: str) -> Optional[Dict]:
        """
        Look up an item by ID and explicit table source.

        Args:
            item_id: The item ID to look up
            table_source: Explicit table source ("item_desc", "cargo_desc", "resource_desc")

        Returns:
            Item details dictionary or None if not found
        """
        try:
            if self._item_lookups is None:
                logging.warning("ItemLookupService: Lookups not initialized")
                return None

            if not table_source:
                raise ValueError("table_source is required for item lookup")

            # Use compound key lookup only
            compound_key = (item_id, table_source)
            return self._item_lookups.get(compound_key)

        except Exception as e:
            logging.error(f"ItemLookupService: Error looking up item {item_id} from {table_source}: {e}")
            return None

    def get_item_name(self, item_id: int, table_source: str) -> str:
        """
        Get the display name for an item.
        
        Args:
            item_id: The item ID to look up
            table_source: Explicit table source ("item_desc", "cargo_desc", "resource_desc")
            
        Returns:
            Item name or "Unknown Item (ID)" if not found
        """
        try:
            item = self.lookup_item_by_id(item_id, table_source)
            if item:
                return item.get("name", f"Unknown Item ({item_id})")
            return f"Unknown Item ({item_id})"
        except Exception as e:
            logging.error(f"ItemLookupService: Error getting item name for {item_id} from {table_source}: {e}")
            return f"Unknown Item ({item_id})"

    def get_item_tier(self, item_id: int, table_source: str) -> int:
        """
        Get the tier for an item.
        
        Args:
            item_id: The item ID to look up
            table_source: Explicit table source ("item_desc", "cargo_desc", "resource_desc")
            
        Returns:
            Item tier or 0 if not found
        """
        try:
            item = self.lookup_item_by_id(item_id, table_source)
            if item:
                return item.get("tier", 0)
            return 0
        except Exception as e:
            logging.error(f"ItemLookupService: Error getting item tier for {item_id} from {table_source}: {e}")
            return 0

    def lookup_item_by_id_and_name(self, item_id: int, item_name: str) -> Optional[Dict]:
        """
        Look up an item by ID and name using natural compound key.

        Args:
            item_id: The item ID to look up
            item_name: The exact item name

        Returns:
            Item details dictionary or None if not found
        """
        try:
            if self._item_lookups is None:
                logging.warning("ItemLookupService: Lookups not initialized")
                return None

            if not item_name:
                logging.warning("ItemLookupService: item_name is required for name-based lookup")
                return None

            # Use compound key lookup with name
            name_key = (item_id, item_name)
            return self._item_lookups.get(name_key)

        except Exception as e:
            logging.error(f"ItemLookupService: Error looking up item {item_id} with name '{item_name}': {e}")
            return None

    def find_items_by_id(self, item_id: int) -> List[Dict]:
        """
        Find all items with the given ID across all tables.
        
        Args:
            item_id: The item ID to search for
            
        Returns:
            List of all items with this ID (may include multiple items from different tables)
        """
        try:
            if self._item_lookups is None:
                return []
            
            items = []
            for key, item_data in self._item_lookups.items():
                # Check both name-based and table-based keys
                if isinstance(key, tuple) and len(key) == 2 and key[0] == item_id:
                    # Avoid duplicates by checking if this item is already in the list
                    if not any(existing['id'] == item_data['id'] and existing['name'] == item_data['name'] for existing in items):
                        items.append(item_data)
            
            return items
        except Exception as e:
            logging.error(f"ItemLookupService: Error finding items with ID {item_id}: {e}")
            return []

    def get_available_sources_for_item(self, item_id: int) -> List[str]:
        """
        Get all available table sources for a given item ID.
        
        Args:
            item_id: The item ID to check
            
        Returns:
            List of table sources that contain this item ID
        """
        try:
            if self._item_lookups is None:
                return []
            
            sources = []
            for source in ["item_desc", "cargo_desc", "resource_desc"]:
                compound_key = (item_id, source)
                if compound_key in self._item_lookups:
                    sources.append(source)
            
            return sources
        except Exception as e:
            logging.error(f"ItemLookupService: Error getting sources for item {item_id}: {e}")
            return []

    def determine_best_source_for_item(self, item_id: int, context_hint: Optional[str] = None) -> str:
        """
        Determine the best table source for an item based on available sources and context.
        
        Args:
            item_id: The item ID to determine source for
            context_hint: Context hint like "cargo", "inventory", "crafting", etc.
            
        Returns:
            Best table source to use ("item_desc", "cargo_desc", "resource_desc")
        """
        try:
            available_sources = self.get_available_sources_for_item(item_id)
            
            if not available_sources:
                # Default to item_desc if no sources found
                return "item_desc"
            
            if len(available_sources) == 1:
                # Only one source available, use it
                return available_sources[0]
            
            # Multiple sources available - use context to decide
            if context_hint == "cargo" and "cargo_desc" in available_sources:
                return "cargo_desc"
            elif context_hint == "resource" and "resource_desc" in available_sources:
                return "resource_desc"
            elif "item_desc" in available_sources:
                # Default preference for item_desc
                return "item_desc"
            else:
                # Fallback to first available source
                return available_sources[0]
                
        except Exception as e:
            logging.error(f"ItemLookupService: Error determining best source for item {item_id}: {e}")
            return "item_desc"

    def get_all_item_names_for_id(self, item_id: int) -> Dict[str, str]:
        """
        Get all available item names for a given ID from all sources.
        
        Args:
            item_id: The item ID to look up
            
        Returns:
            Dictionary mapping table_source to item name
        """
        try:
            names = {}
            for source in ["item_desc", "cargo_desc", "resource_desc"]:
                compound_key = (item_id, source)
                if compound_key in self._item_lookups:
                    item = self._item_lookups[compound_key]
                    names[source] = item.get("name", f"Unknown Item ({item_id})")
            return names
        except Exception as e:
            logging.error(f"ItemLookupService: Error getting all names for item {item_id}: {e}")
            return {}

    def lookup_building_by_id(self, building_id: int) -> Optional[Dict]:
        """
        Look up building information by building description ID.
        
        Args:
            building_id: The building description ID to look up
            
        Returns:
            Building details dictionary or None if not found
        """
        try:
            if self._building_lookups is None:
                logging.warning("ItemLookupService: Building lookups not initialized")
                return None
                
            return self._building_lookups.get(building_id)
            
        except Exception as e:
            logging.error(f"ItemLookupService: Error looking up building {building_id}: {e}")
            return None

    def get_building_name(self, building_id: int) -> str:
        """
        Get the display name for a building.
        
        Args:
            building_id: The building description ID to look up
            
        Returns:
            Building name or "Building (ID)" if not found
        """
        building = self.lookup_building_by_id(building_id)
        if building:
            return building.get("name", f"Building ({building_id})")
        return f"Building ({building_id})"

    def lookup_recipe_by_id(self, recipe_id: int) -> Optional[Dict]:
        """
        Look up recipe information by recipe ID.
        
        Args:
            recipe_id: The recipe ID to look up
            
        Returns:
            Recipe details dictionary or None if not found
        """
        try:
            if self._recipe_lookups is None:
                logging.warning("ItemLookupService: Recipe lookups not initialized")
                return None
                
            return self._recipe_lookups.get(recipe_id)
            
        except Exception as e:
            logging.error(f"ItemLookupService: Error looking up recipe {recipe_id}: {e}")
            return None

    def get_recipe_name(self, recipe_id: int) -> str:
        """
        Get the display name for a recipe.
        
        Args:
            recipe_id: The recipe ID to look up
            
        Returns:
            Recipe name or "Recipe (ID)" if not found
        """
        recipe = self.lookup_recipe_by_id(recipe_id)
        if recipe:
            name = recipe.get("name", f"Recipe ({recipe_id})")
            # Clean up recipe names that have placeholder text
            return name.replace("{0}", "").strip()
        return f"Recipe ({recipe_id})"

    def refresh_lookups(self, new_reference_data: Dict[str, Any]):
        """
        Refresh the lookup cache with new reference data.
        
        Args:
            new_reference_data: Updated reference data
        """
        try:
            self.reference_data = new_reference_data
            self._initialize_lookups()
            
            # Log refresh statistics
            stats = self.get_stats()
            logging.info(f"ItemLookupService: Lookups refreshed - "
                        f"{stats['total_items']} items, {stats['total_buildings']} buildings, "
                        f"{stats['total_recipes']} recipes")
        except Exception as e:
            logging.error(f"ItemLookupService: Error refreshing lookups: {e}")

    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about the lookup cache.
        
        Returns:
            Dictionary with cache statistics
        """
        stats = {
            "total_items": 0,
            "compound_keys": 0,
            "simple_keys": 0,
            "total_buildings": 0,
            "total_recipes": 0,
        }
        
        if self._item_lookups is not None:
            compound_keys = sum(1 for key in self._item_lookups.keys() if isinstance(key, tuple))
            simple_keys = len(self._item_lookups) - compound_keys
            stats.update({
                "total_items": len(self._item_lookups),
                "compound_keys": compound_keys,
                "simple_keys": simple_keys,
            })
            
        if self._building_lookups is not None:
            stats["total_buildings"] = len(self._building_lookups)
            
        if self._recipe_lookups is not None:
            stats["total_recipes"] = len(self._recipe_lookups)
        
        return stats