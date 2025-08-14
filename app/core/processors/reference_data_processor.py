"""
Reference data processor for handling reference table subscriptions.

Processes static game data tables (resource_desc, item_desc, etc.) from SpacetimeDB
to replace SQLite-based reference data loading.
"""

import logging
from .base_processor import BaseProcessor
from app.models import (
    ResourceDesc, ItemDesc, CargoDesc, BuildingDesc, BuildingTypeDesc,
    CraftingRecipeDesc, ClaimTileCost, NpcDesc, BuildingFunctionTypeMappingDesc
)


class ReferenceDataProcessor(BaseProcessor):
    """
    Processes reference data table subscriptions from SpacetimeDB.
    
    Handles static game data tables that provide reference information
    for items, buildings, recipes, and other game entities.
    """

    def __init__(self, data_queue, services, reference_data):
        super().__init__(data_queue, services, reference_data)
        
        # Cache for processed reference data
        self._reference_cache = {}
        
        # Get ItemLookupService for refreshing when reference data updates
        self._item_lookup_service = services.get("item_lookup_service")
        
        # Mapping of table names to dataclass types
        self._table_dataclass_map = {
            "resource_desc": ResourceDesc,
            "item_desc": ItemDesc, 
            "cargo_desc": CargoDesc,
            "building_desc": BuildingDesc,
            "building_type_desc": BuildingTypeDesc,
            "crafting_recipe_desc": CraftingRecipeDesc,
            "claim_tile_cost": ClaimTileCost,
            "npc_desc": NpcDesc,
            "building_function_type_mapping_desc": BuildingFunctionTypeMappingDesc,
        }

    def get_table_names(self):
        """Return list of reference data table names this processor handles."""
        return list(self._table_dataclass_map.keys())

    def process_transaction(self, table_update, reducer_name, timestamp):
        """
        Process reference data transactions.
        
        Reference data is typically static, so transactions are rare.
        When they occur, we update our cached reference data.
        """
        try:
            table_name = table_update.get("table_name", "")
            updates = table_update.get("updates", [])
            
            if table_name not in self._table_dataclass_map:
                return
                
            dataclass_type = self._table_dataclass_map[table_name]
            
            # Process updates to reference data
            for update in updates:
                inserts = update.get("inserts", [])
                deletes = update.get("deletes", [])
                
                # Process inserts/updates
                for insert_str in inserts:
                    try:
                        # Try to parse using the appropriate dataclass
                        reference_item = dataclass_type.from_array(insert_str)
                        if reference_item:
                            # Update cache with new/updated reference data
                            if table_name not in self._reference_cache:
                                self._reference_cache[table_name] = []
                            
                            # Replace existing item or add new one
                            self._update_cache_item(table_name, reference_item)
                            
                            logging.debug(f"Updated {table_name} reference data: {getattr(reference_item, 'name', getattr(reference_item, 'id', 'unknown'))}")
                            
                    except Exception as e:
                        logging.debug(f"Failed to parse {table_name} transaction: {e}")
                        
                # Process deletes (remove from cache)
                for delete_str in deletes:
                    try:
                        # Parse the delete to get the entity ID
                        import json
                        delete_data = json.loads(delete_str)
                        entity_id = delete_data.get("id") or delete_data.get("entity_id")
                        
                        if entity_id and table_name in self._reference_cache:
                            self._reference_cache[table_name] = [
                                item for item in self._reference_cache[table_name]
                                if getattr(item, 'id', None) != entity_id and 
                                   getattr(item, 'entity_id', None) != entity_id
                            ]
                            
                            logging.debug(f"Removed {table_name} reference data: {entity_id}")
                            
                    except Exception as e:
                        logging.debug(f"Failed to process {table_name} delete: {e}")
            
            # Notify services that reference data has changed
            self._notify_reference_data_update(table_name)
            
        except Exception as e:
            logging.error(f"Error processing {table_name} transaction: {e}")

    def process_subscription(self, table_update):
        """
        Process reference data subscription updates.
        
        Loads initial reference data when subscriptions are established.
        """
        try:
            table_name = table_update.get("table_name", "")
            
            if table_name not in self._table_dataclass_map:
                return
                
            dataclass_type = self._table_dataclass_map[table_name]
            table_rows = []
            
            # Extract rows from subscription update
            for update in table_update.get("updates", []):
                for insert_str in update.get("inserts", []):
                    try:
                        import json
                        row_data = json.loads(insert_str)
                        table_rows.append(row_data)
                    except json.JSONDecodeError:
                        logging.debug(f"Failed to parse {table_name} subscription row")
                        
            if not table_rows:
                return
                
            # Process all reference data rows
            reference_items = []
            failed_count = 0
            
            for row in table_rows:
                try:
                    # Create dataclass instance from dictionary
                    reference_item = dataclass_type.from_dict(row)
                    if reference_item:
                        reference_items.append(reference_item)
                    else:
                        failed_count += 1
                except Exception as e:
                    logging.debug(f"Failed to create {table_name} dataclass from row: {e}")
                    failed_count += 1
            
            # Store in cache
            self._reference_cache[table_name] = reference_items
            
            # Update the main reference_data dictionary for backward compatibility
            # Convert dataclasses back to dictionaries for existing code
            self.reference_data[table_name] = [item.to_dict() for item in reference_items]
            
            logging.info(f"Loaded {len(reference_items)} {table_name} items")
            
            if failed_count > 0:
                logging.warning(f"Failed to parse {failed_count} {table_name} rows")
            
            # Notify services that reference data is available
            self._notify_reference_data_loaded(table_name, len(reference_items))
            
        except Exception as e:
            logging.error(f"Error processing {table_name} subscription: {e}")

    def _update_cache_item(self, table_name, new_item):
        """Update or add an item in the reference cache."""
        if table_name not in self._reference_cache:
            self._reference_cache[table_name] = []
            
        cache = self._reference_cache[table_name]
        item_id = getattr(new_item, 'id', None) or getattr(new_item, 'entity_id', None)
        
        # Find and replace existing item, or append new one
        for i, existing_item in enumerate(cache):
            existing_id = getattr(existing_item, 'id', None) or getattr(existing_item, 'entity_id', None)
            if existing_id == item_id:
                cache[i] = new_item
                return
                
        # Item not found, add it
        cache.append(new_item)

    def _notify_reference_data_update(self, table_name):
        """Notify that reference data has been updated."""
        try:
            # Update the main reference_data dictionary for backward compatibility
            if table_name in self._reference_cache:
                self.reference_data[table_name] = [
                    item.to_dict() for item in self._reference_cache[table_name]
                ]
            
            # Notify UI of reference data change
            self._queue_update(
                "reference_data_update", 
                {
                    "table": table_name,
                    "count": len(self._reference_cache.get(table_name, [])),
                    "type": "update"
                }
            )
            
            # Refresh ItemLookupService when key lookup tables are updated
            if table_name in ["item_desc", "building_desc", "crafting_recipe_desc"] and self._item_lookup_service:
                self._item_lookup_service.refresh_lookups(self.reference_data)
            
        except Exception as e:
            logging.error(f"Error notifying reference data update for {table_name}: {e}")

    def _notify_reference_data_loaded(self, table_name, count):
        """Notify that reference data has been initially loaded."""
        try:
            # Notify UI of reference data loading
            self._queue_update(
                "reference_data_loaded", 
                {
                    "table": table_name,
                    "count": count
                }
            )
            
            # Refresh ItemLookupService when we have key lookup tables
            if table_name in ["item_desc", "building_desc", "crafting_recipe_desc"] and self._item_lookup_service:
                self._item_lookup_service.refresh_lookups(self.reference_data)
            
        except Exception as e:
            logging.error(f"Error notifying reference data loaded for {table_name}: {e}")

    def get_reference_items(self, table_name):
        """
        Get cached reference items for a table as dataclass instances.
        
        Args:
            table_name: Name of the reference table
            
        Returns:
            List of dataclass instances, or empty list if not cached
        """
        return self._reference_cache.get(table_name, [])

    def get_reference_item_by_id(self, table_name, item_id):
        """
        Get a specific reference item by ID.
        
        Args:
            table_name: Name of the reference table
            item_id: ID of the item to find
            
        Returns:
            Dataclass instance or None if not found
        """
        items = self._reference_cache.get(table_name, [])
        for item in items:
            if (getattr(item, 'id', None) == item_id or 
                getattr(item, 'entity_id', None) == item_id):
                return item
        return None

    def clear_cache(self):
        """Clear reference data cache (usually not needed for reference data)."""
        super().clear_cache()
        # Reference data is global and doesn't need clearing on claim switch
        logging.debug("Reference data cache retained (global data)")