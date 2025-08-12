import logging
from typing import Dict, List, Optional


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

    # ========== SUBSCRIPTION QUERIES (Real-time Data Flow) ==========

    def get_subscription_queries(self, user_id: str, claim_id: str) -> List[str]:
        """Get all subscription queries for a claim - matching your DataManager pattern."""
        queries = [
            # ("SELECT * FROM claim_member_state WHERE player_entity_id = '{user_id}';".format(user_id=user_id)),
            ("SELECT * FROM traveler_task_state WHERE player_entity_id = '{user_id}';".format(user_id=user_id)),
            ("SELECT * FROM player_state WHERE entity_id = '{user_id}';".format(user_id=user_id)),
            ("SELECT * FROM building_state WHERE claim_entity_id = '{claim_id}';".format(claim_id=claim_id)),
            ("SELECT * FROM claim_member_state WHERE claim_entity_id = '{claim_id}';".format(claim_id=claim_id)),
            (
                "SELECT claim_state.* "
                "FROM claim_state "
                "JOIN claim_member_state "
                "ON claim_state.entity_id = claim_member_state.claim_entity_id "
                "WHERE claim_member_state.player_entity_id = '{user_id}';".format(user_id=user_id)
            ),
            (
                "SELECT claim_local_state.* "
                "FROM claim_local_state "
                "JOIN claim_member_state ON claim_local_state.entity_id = claim_member_state.claim_entity_id "
                "WHERE claim_member_state.player_entity_id = '{user_id}';".format(user_id=user_id)
            ),
            (
                "SELECT traveler_task_desc.* "
                "FROM traveler_task_desc "
                "JOIN traveler_task_state "
                "ON traveler_task_state.task_id = traveler_task_desc.id "
                "WHERE traveler_task_state.player_entity_id = '{user_id}';".format(user_id=user_id)
            ),
            (
                "SELECT building_nickname_state.* "
                "FROM building_nickname_state "
                "JOIN building_state "
                "ON building_state.entity_id = building_nickname_state.entity_id "
                "WHERE building_state.claim_entity_id = '{claim_id}';".format(claim_id=claim_id)
            ),
            (
                "SELECT inventory_state.* FROM inventory_state "
                "JOIN building_state ON inventory_state.owner_entity_id = building_state.entity_id "
                "WHERE building_state.claim_entity_id = '{claim_id}';".format(claim_id=claim_id)
            ),
            (
                "SELECT progressive_action_state.* "
                "FROM progressive_action_state "
                "JOIN building_state "
                "ON progressive_action_state.building_entity_id = building_state.entity_id "
                "WHERE building_state.claim_entity_id = '{claim_id}';".format(claim_id=claim_id)
            ),
            (
                "SELECT public_progressive_action_state.* "
                "FROM public_progressive_action_state "
                "JOIN building_state "
                "ON public_progressive_action_state.building_entity_id = building_state.entity_id "
                "WHERE building_state.claim_entity_id = '{claim_id}';".format(claim_id=claim_id)
            ),
            (
                "SELECT passive_craft_state.* "
                "FROM passive_craft_state "
                "JOIN building_state ON passive_craft_state.building_entity_id = building_state.entity_id "
                "WHERE building_state.claim_entity_id = '{claim_id}';".format(claim_id=claim_id)
            ),
            (
                "SELECT sell_order_state.* "
                "FROM sell_order_state "
                "WHERE sell_order_state.claim_entity_id = '{claim_id}';".format(claim_id=claim_id)
            ),
            (
                "SELECT character_stats_state.* "
                "FROM character_stats_state "
                "WHERE character_stats_state.entity_id = '{user_id}';".format(user_id=user_id)
            ),
            (
                "SELECT inventory_state.* "
                "FROM inventory_state "
                "WHERE inventory_state.inventory_index = 1 "
                "AND inventory_state.owner_entity_id = '{user_id}';".format(user_id=user_id)
            ),
        ]

        return queries
