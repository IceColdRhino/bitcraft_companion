import logging
import time
from typing import Dict, List, Optional
from app.services.reference_cache_service import ReferenceCacheService


class QueryService:
    """
    Centralized query service providing two types of queries:

    1. ONE-OFF QUERIES: Used for initial setup and authentication
       - get_user_by_name(): Initial user lookup
       - get_claim_state(): Claim info for UI display
       - get_claim_local_state(): Claim validation
       - get_user_claims(): Available claims for user
       - get_claim_members(): Legacy method for claim_members_service

    2. SUBSCRIPTION QUERIES: Generate SQL strings for real-time subscriptions
       - get_subscription_queries(): Returns SQL strings for client.start_subscription_listener()

    The subscription pattern is the core architecture:
    - Call get_subscription_queries() once with claim_id and user_id
    - Pass SQL strings to client.start_subscription_listener()
    - Data flows automatically via InitialSubscription/SubscriptionUpdate messages
    """

    def __init__(self, client):
        self.client = client
        self.cache_service = ReferenceCacheService()

    # ========== ONE-OFF QUERIES (Initial Setup & Authentication) ==========

    def get_user_by_name(self, username: str) -> Optional[Dict]:
        sanitized_username = username.lower().replace("'", "''")
        query_string = f"SELECT * FROM player_lowercase_username_state WHERE username_lowercase = '{sanitized_username}';"
        results = self.client.query(query_string)
        return results[0] if results else None

    def get_user_data(self, user_id: str) -> Dict:
        """Get user data including claims and tasks."""
        try:

            query = f"SELECT * FROM user_data WHERE user_id = '{user_id}';"
            results = self.client.query(query)
            return results[0] if results else {}
        except Exception as e:
            logging.error(f"Error fetching user data: {e}")
            return {}

    def get_claim_state(self, claim_id: str) -> Dict:
        """Get complete claim state."""
        try:
            query = "SELECT * FROM claim_state WHERE entity_id = '{claim_id}';".format(claim_id=claim_id)
            results = self.client.query(query)
            return results[0] if results else {}
        except Exception as e:
            logging.error(f"Error fetching claim state: {e}")
            return {}

    def get_claim_local_state(self, claim_id: str) -> Dict:
        """Get complete claim local state."""
        try:
            query = "SELECT * FROM claim_local_state WHERE entity_id = '{claim_id}';".format(claim_id=claim_id)
            results = self.client.query(query)
            return results[0] if results else {}
        except Exception as e:
            logging.error(f"Error fetching claim state: {e}")
            return {}

    def get_user_claims(self, user_id: str) -> List[Dict]:
        """Get all claims for a user."""
        try:

            query = "SELECT * FROM claim_member_state WHERE player_entity_id = '{user_id}';".format(user_id=user_id)
            return self.client.query(query) or []
        except Exception as e:
            logging.error(f"Error fetching user claims: {e}")
            return []

    def get_claim_buildings(self, claim_id: str) -> List[Dict]:
        """Get all buildings for a claim with nicknames."""
        try:
            query = (
                "SELECT building_nickname_state.*, building_state.* "
                "FROM building_nickname_state JOIN building_state "
                "ON building_state.entity_id = building_nickname_state.entity_id "
                "WHERE building_state.claim_entity_id = '{claim_id}';".format(claim_id=claim_id)
            )
            return self.client.query(query) or []
        except Exception as e:
            logging.error(f"Error fetching claim buildings: {e}")
            return []

    def get_claim_members(self, claim_id: str) -> List[Dict]:
        """Get all members of a claim. Still used by claim_members_service."""
        try:
            query = f"SELECT * FROM claim_member_state WHERE claim_entity_id = '{claim_id}';"
            return self.client.query(query) or []
        except Exception as e:
            logging.error(f"Error fetching claim members: {e}")
            return []

    def get_reference_data(self) -> Dict:
        """
        Fetch static reference data via one-off queries with caching.

        Loads game reference tables that rarely change (items, buildings, recipes, etc.)
        using local cache when possible to dramatically reduce startup time.

        Returns:
            Dict: Reference data organized by table name
        """
        load_start_time = time.time()

        # Try to load from cache first
        cached_data = self.cache_service.get_cached_reference_data()
        if cached_data:
            cache_load_time = time.time() - load_start_time
            logging.debug(f"Reference data loaded from cache in {cache_load_time:.3f}s")
            return cached_data

        # Cache miss - fetch from server
        logging.info("Reference cache miss - fetching from server...")

        reference_queries = [
            "SELECT * FROM resource_desc;",
            "SELECT * FROM item_list_desc;",
            "SELECT * FROM item_desc;",
            "SELECT * FROM cargo_desc;",
            "SELECT * FROM building_desc;",
            "SELECT * FROM building_function_type_mapping_desc;",
            "SELECT * FROM building_type_desc;",
            "SELECT * FROM crafting_recipe_desc;",
            "SELECT * FROM extraction_recipe_desc;",
            "SELECT * FROM claim_tile_cost;",
            "SELECT * FROM npc_desc;",
        ]

        reference_data = {}
        total_records = 0

        try:
            for query in reference_queries:
                # Extract table name from query
                table_name = query.split("FROM ")[1].split(";")[0].strip()

                logging.info(f"Loading reference data: {table_name}")
                query_start = time.time()

                try:
                    results = self.client.query(query)
                    query_time = time.time() - query_start

                    reference_data[table_name] = results if results else []

                    record_count = len(reference_data[table_name])
                    total_records += record_count
                    logging.debug(f"Loaded {record_count} records from {table_name} ({query_time:.3f}s)")

                    # Special logging for traveler_task_desc
                    if table_name == "traveler_task_desc":
                        if record_count == 0:
                            logging.warning(f"[QueryService] traveler_task_desc table is empty")
                        else:
                            logging.info(f"[QueryService] Successfully loaded {record_count} traveler task descriptions")

                except Exception as e:
                    logging.error(f"[QueryService] Error loading {table_name}: {e}")
                    reference_data[table_name] = []  # Ensure the table exists even if empty

            total_load_time = time.time() - load_start_time
            logging.info(
                f"Reference data loading completed: {total_records} total records across {len(reference_queries)} tables ({total_load_time:.3f}s)"
            )

            # Cache the data for next time
            self.cache_service.cache_reference_data(reference_data)

        except Exception as e:
            logging.error(f"Error fetching reference data: {e}")
            # Return partial data if some queries succeeded

        return reference_data

    def clear_reference_cache(self) -> bool:
        """
        Clear the reference data cache.

        Useful for forcing a fresh download of reference data or troubleshooting.

        Returns:
            bool: True if cache was cleared successfully
        """
        return self.cache_service.clear_cache()

    def get_cache_info(self) -> Dict:
        """
        Get information about the reference data cache.

        Returns:
            Dict: Cache status, age, size, and validity information
        """
        return self.cache_service.get_cache_info()

    def get_subscription_queries(self, user_id: str, claim_id: str) -> List[str]:
        """
        Get dynamic subscription queries for real-time data flow.

        Static reference data (items, buildings, recipes, etc.) is now loaded
        via get_reference_data() instead of subscriptions for better performance.
        """
        queries = [
            # Dynamic queries that benefit from real-time subscriptions
            # Get traveler tasks for player
            ("SELECT * FROM traveler_task_state WHERE player_entity_id = '{user_id}';".format(user_id=user_id)),
            # Get claim buildings
            ("SELECT * FROM building_state WHERE claim_entity_id = '{claim_id}';".format(claim_id=claim_id)),
            # Get claim members' information
            ("SELECT * FROM claim_member_state WHERE claim_entity_id = '{claim_id}';".format(claim_id=claim_id)),
            # Get player's stamina state
            ("SELECT * FROM stamina_state WHERE entity_id = '{user_id}';".format(user_id=user_id)),
            # Get player's stats
            ("SELECT * FROM character_stats_state WHERE entity_id = '{user_id}';".format(user_id=user_id)),
            # Get player's claim information
            (
                "SELECT claim_state.* "
                "FROM claim_state "
                "JOIN claim_member_state "
                "ON claim_state.entity_id = claim_member_state.claim_entity_id "
                "WHERE claim_member_state.player_entity_id = '{user_id}';".format(user_id=user_id)
            ),
            # Get player's claim local state information
            (
                "SELECT claim_local_state.* "
                "FROM claim_local_state "
                "JOIN claim_member_state ON claim_local_state.entity_id = claim_member_state.claim_entity_id "
                "WHERE claim_member_state.player_entity_id = '{user_id}';".format(user_id=user_id)
            ),
            # Get current traveler task descriptions
            (
                "SELECT traveler_task_desc.* "
                "FROM traveler_task_desc "
                "JOIN traveler_task_state "
                "ON traveler_task_state.task_id = traveler_task_desc.id "
                "WHERE traveler_task_state.player_entity_id = '{user_id}';".format(user_id=user_id)
            ),
            # Get claim building nicknames
            (
                "SELECT building_nickname_state.* "
                "FROM building_nickname_state "
                "JOIN building_state "
                "ON building_state.entity_id = building_nickname_state.entity_id "
                "WHERE building_state.claim_entity_id = '{claim_id}';".format(claim_id=claim_id)
            ),
            # Get claim building inventories
            (
                "SELECT inventory_state.* FROM inventory_state "
                "JOIN building_state ON inventory_state.owner_entity_id = building_state.entity_id "
                "WHERE building_state.claim_entity_id = '{claim_id}';".format(claim_id=claim_id)
            ),
            # Get active crafting state for users in the claim
            (
                "SELECT progressive_action_state.* "
                "FROM progressive_action_state "
                "JOIN building_state "
                "ON progressive_action_state.building_entity_id = building_state.entity_id "
                "WHERE building_state.claim_entity_id = '{claim_id}';".format(claim_id=claim_id)
            ),
            # Get active crafting buildings in claim if accept help is turned on
            (
                "SELECT public_progressive_action_state.* "
                "FROM public_progressive_action_state "
                "JOIN building_state "
                "ON public_progressive_action_state.building_entity_id = building_state.entity_id "
                "WHERE building_state.claim_entity_id = '{claim_id}';".format(claim_id=claim_id)
            ),
            # Get passive crafting state for buildings in the claim
            (
                "SELECT passive_craft_state.* "
                "FROM passive_craft_state "
                "JOIN building_state ON passive_craft_state.building_entity_id = building_state.entity_id "
                "WHERE building_state.claim_entity_id = '{claim_id}';".format(claim_id=claim_id)
            ),
            # Get buy order state for orders placed within the claim
            (
                "SELECT buy_order_state.* "
                "FROM buy_order_state "
                "WHERE buy_order_state.claim_entity_id = '{claim_id}';".format(claim_id=claim_id)
            ),
            # Get sell order state for orders placed within the claim
            (
                "SELECT sell_order_state.* "
                "FROM sell_order_state "
                "WHERE sell_order_state.claim_entity_id = '{claim_id}';".format(claim_id=claim_id)
            ),
            # Get the player's character stats (most importantly, skill speeds)
            (
                "SELECT character_stats_state.* "
                "FROM character_stats_state "
                "WHERE character_stats_state.entity_id = '{user_id}';".format(user_id=user_id)
            ),
            # Get the player's equipped tool state
            (
                "SELECT inventory_state.* "
                "FROM inventory_state "
                "WHERE inventory_state.inventory_index = 1 "
                "AND inventory_state.owner_entity_id = '{user_id}';".format(user_id=user_id)
            ),
        ]

        return queries
