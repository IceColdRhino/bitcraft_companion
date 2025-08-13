import logging
from typing import List

from ..client.bitcraft_client import BitCraft
from ..models.claim import Claim


class InventoryService:
    """Service class to handle inventory-related operations for a BitCraft claim."""

    def __init__(self, bitcraft_client: BitCraft, claim_instance: Claim):
        """Initializes the InventoryService with its dependencies."""
        self.client = bitcraft_client
        self.claim = claim_instance


    def initialize_full_inventory(self):
        """
        Performs a full, one-time fetch to populate the entire claim and inventory state,
        using the correct, individual query method for each building's inventory.
        """
        claim_id = self.claim.claim_id
        if not claim_id:
            logging.error("Cannot initialize inventory without a claim_id.")
            return

        try:
            logging.info(f"Performing initial full inventory fetch for claim: {claim_id}")
            # 1. Fetch all buildings in the claim
            buildings_query = f"SELECT * FROM building_state WHERE claim_entity_id = '{claim_id}';"
            building_states = self.client.query(buildings_query)
            if not building_states:
                logging.warning(f"No buildings found for claim {claim_id}.")
                self.claim.set_buildings([])
                return

            # 2. Fetch all building nicknames
            nicknames_query = "SELECT * FROM building_nickname_state;"
            building_nicknames = self.client.query(nicknames_query)
            nickname_lookup = {n["entity_id"]: n["nickname"] for n in building_nicknames} if building_nicknames else {}

            # --- FIX: Loop through each building and fetch its inventory individually ---
            enriched_buildings = []
            for building in building_states:
                entity_id = building.get("entity_id")
                if entity_id:
                    # Enrich with nickname
                    building["nickname"] = nickname_lookup.get(entity_id)

                    # Fetch inventory for this specific building using the correct query
                    inventory_query = f"SELECT * FROM inventory_state WHERE owner_entity_id = '{entity_id}';"
                    inventory_data = self.client.query(inventory_query)

                    # The query returns a list, so we take the first element if it exists
                    building["inventory"] = inventory_data[0] if inventory_data else None

                    enriched_buildings.append(building)

            # 5. Set the fully processed buildings on the claim instance
            self.claim.set_buildings(enriched_buildings)
            logging.info(f"Successfully initialized inventory for {len(enriched_buildings)} buildings.")

        except Exception as e:
            logging.error(f"An error occurred during initial inventory fetch: {e}", exc_info=True)

    def parse_inventory_message(self, db_update: dict) -> bool:
        """
        Parses a subscription update and applies changes to the local claim state.
        """
        update_str = str(db_update)
        if "inventory_state" in update_str or "building_state" in update_str:
            logging.info("Inventory-related update received from subscription.")
            # Trigger a full refresh of the inventory data.
            self.initialize_full_inventory()
            return True
        return False
