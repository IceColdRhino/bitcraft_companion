"""
Item Lookup Service for efficient item reference data access.

This service consolidates the item lookup functionality that was previously duplicated
across multiple processors, providing a single source of truth for item data access.
"""

import logging
from typing import Dict, Optional, Tuple, Any


class ItemLookupService:
    """
    Service for looking up item information from reference data.
    
    Handles compound keys to prevent ID conflicts between different item tables
    and provides efficient lookup methods with fallback strategies.
    """

    def __init__(self, reference_data: Dict[str, Any]):
        """
        Initialize the service with reference data.
        
        Args:
            reference_data: Dictionary containing game reference data (items, recipes, etc.)
        """
        self.reference_data = reference_data
        self._item_lookups: Optional[Dict] = None
        self._initialize_lookups()

    def _initialize_lookups(self):
        """Initialize the item lookup cache."""
        self._item_lookups = self._build_item_lookups()

    def _build_item_lookups(self) -> Dict:
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

            logging.debug(f"ItemLookupService: Built lookups for {len(item_lookups)} items")
            return item_lookups

        except Exception as e:
            logging.error(f"ItemLookupService: Error creating item lookups: {e}")
            return {}

    def lookup_item_by_id(self, item_id: int, preferred_source: Optional[str] = None) -> Optional[Dict]:
        """
        Smart item lookup that handles both compound keys and simple keys.

        Args:
            item_id: The item ID to look up
            preferred_source: Preferred table source ("item_desc", "cargo_desc", "resource_desc")

        Returns:
            Item details dictionary or None if not found
        """
        try:
            if self._item_lookups is None:
                logging.warning("ItemLookupService: Lookups not initialized")
                return None

            # Try preferred source first if specified
            if preferred_source:
                compound_key = (item_id, preferred_source)
                if compound_key in self._item_lookups:
                    return self._item_lookups[compound_key]

            # Try simple item_id lookup (uses priority system)
            if item_id in self._item_lookups:
                return self._item_lookups[item_id]

            # Try all compound keys if simple lookup failed
            for source in ["item_desc", "cargo_desc", "resource_desc"]:
                compound_key = (item_id, source)
                if compound_key in self._item_lookups:
                    return self._item_lookups[compound_key]

            return None

        except Exception as e:
            logging.error(f"ItemLookupService: Error looking up item {item_id}: {e}")
            return None

    def get_item_name(self, item_id: int, preferred_source: Optional[str] = None) -> str:
        """
        Get the display name for an item.
        
        Args:
            item_id: The item ID to look up
            preferred_source: Preferred table source
            
        Returns:
            Item name or "Unknown Item (ID)" if not found
        """
        item = self.lookup_item_by_id(item_id, preferred_source)
        if item:
            return item.get("name", f"Unknown Item ({item_id})")
        return f"Unknown Item ({item_id})"

    def get_item_tier(self, item_id: int, preferred_source: Optional[str] = None) -> int:
        """
        Get the tier for an item.
        
        Args:
            item_id: The item ID to look up
            preferred_source: Preferred table source
            
        Returns:
            Item tier or 0 if not found
        """
        item = self.lookup_item_by_id(item_id, preferred_source)
        if item:
            return item.get("tier", 0)
        return 0

    def refresh_lookups(self, new_reference_data: Dict[str, Any]):
        """
        Refresh the lookup cache with new reference data.
        
        Args:
            new_reference_data: Updated reference data
        """
        try:
            self.reference_data = new_reference_data
            self._initialize_lookups()
            logging.info("ItemLookupService: Lookups refreshed successfully")
        except Exception as e:
            logging.error(f"ItemLookupService: Error refreshing lookups: {e}")

    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about the lookup cache.
        
        Returns:
            Dictionary with cache statistics
        """
        if self._item_lookups is None:
            return {"total_items": 0, "compound_keys": 0, "simple_keys": 0}
            
        compound_keys = sum(1 for key in self._item_lookups.keys() if isinstance(key, tuple))
        simple_keys = len(self._item_lookups) - compound_keys
        
        return {
            "total_items": len(self._item_lookups),
            "compound_keys": compound_keys,
            "simple_keys": simple_keys
        }