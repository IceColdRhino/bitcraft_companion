"""
Pytest configuration and shared fixtures for BitCraft Companion tests.

Provides mock objects, test data, and utilities for testing the core
message processing, client connections, and business logic.
"""

import pytest
import queue
import threading
import json
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List, Any


# ========== MOCK CLASSES ==========

class MockBitCraftClient:
    """Mock BitCraft client for testing without real connections."""
    
    def __init__(self):
        self.authenticated = False
        self.connected = False
        self.player_name = "TestPlayer"
        self.region = "test-region"
        self.query_responses = {}
        self.subscription_listener = None
        self.subscription_thread = None
        self._stop_subscription = Mock()
        self.ws_lock = threading.Lock()
        
        # Additional attributes expected by tests
        self.auth = None
        self.email = None
        self.ws_connection = None
        self.headers = {}
        
    def authenticate(self, username: str = None, password: str = None) -> bool:
        # Support different authentication patterns
        if username and password:
            self.authenticated = username == "testuser" and password == "testpass"
        elif username:  # Email-based auth
            self.authenticated = True
            self.email = username
            self.auth = "Bearer test_token"
        else:
            self.authenticated = False
        return self.authenticated
        
    def set_region(self, region: str):
        self.region = region
        
    def set_endpoint(self, endpoint: str):
        self.endpoint = endpoint
        
    def set_websocket_uri(self):
        self.ws_uri = f"ws://{self.region}/test"
        
    def connect_websocket(self):
        if not self.authenticated:
            raise ConnectionError("Not authenticated")
        self.connected = True
        
    def close_websocket(self):
        self.connected = False
        
    def query(self, query_string: str) -> List[Dict]:
        """Return mock query responses based on query string."""
        return self.query_responses.get(query_string, [])
        
    def start_subscription_listener(self, queries: List[str], callback):
        """Mock subscription listener."""
        self.subscription_listener = {
            "queries": queries,
            "callback": callback
        }
        
    def test_server_connectivity(self) -> bool:
        """Mock server connectivity test."""
        return True
        
    def connect_websocket_with_retry(self, max_retries=3, base_delay=1.0):
        """Mock WebSocket connection with retry."""
        self.connect_websocket()
        
    def stop_subscriptions(self):
        """Mock stop subscriptions."""
        self.subscription_listener = None
        
    def load_full_reference_data(self) -> Dict:
        """Return mock reference data."""
        return get_mock_reference_data()
        
    def fetch_user_id_by_username(self, username: str) -> str:
        """Return mock user ID."""
        return "test-user-id-123" if username == "TestPlayer" else None


class MockProcessor:
    """Mock processor for testing MessageRouter."""
    
    def __init__(self, table_names: List[str]):
        self._table_names = table_names
        self.processed_transactions = []
        self.processed_subscriptions = []
        self.data_queue = None
        self.services = {}
        self.reference_data = {}
        
    def get_table_names(self) -> List[str]:
        return self._table_names
        
    def process_transaction(self, table_update: Dict, reducer_name: str, timestamp: float):
        self.processed_transactions.append({
            "table_update": table_update,
            "reducer_name": reducer_name,
            "timestamp": timestamp
        })
        
    def process_subscription(self, table_update: Dict):
        self.processed_subscriptions.append(table_update)
        
    def clear_cache(self):
        pass


# ========== FIXTURE DATA ==========

def get_mock_reference_data() -> Dict[str, Any]:
    """Generate mock reference data for testing, including ID conflicts for testing resolution."""
    return {
        "item_desc": [
            {"id": 1, "name": "Wood", "tier": 0, "tag": "Material"},
            {"id": 2, "name": "Iron Ore", "tier": 1, "tag": "Ore"},
            {"id": 3, "name": "Iron Bar", "tier": 2, "tag": "Metal"},
            # Conflicting ID 3001 - should show as "Ancient Journal Page #2" when no cargo heuristics match
            {"id": 3001, "name": "Ancient Journal Page #2", "tier": 0, "tag": "Journal Page"},
            # Conflicting ID 1001 - regular item
            {"id": 1001, "name": "Iron Sword", "tier": 2, "tag": "Weapon"}
        ],
        "cargo_desc": [
            # Conflicting ID 3001 - should be chosen for cargo due to "chunk" heuristic
            {"id": 3001, "name": "Pyrelite Ore Chunk", "tier": 2, "tag": "Ore Chunk"},
            # Conflicting ID 1001 - should be chosen due to "package" heuristic  
            {"id": 1001, "name": "Supply Package", "tier": 1, "tag": "Supplies"},
            # Non-conflicting cargo items
            {"id": 4001, "name": "Materials Crate", "tier": 1, "tag": "Cargo"},
            {"id": 4002, "name": "Equipment Bundle", "tier": 2, "tag": "Bundle"}
        ],
        "resource_desc": [
            {"id": 10, "name": "Stone", "tier": 0, "tag": "Stone"},
            {"id": 11, "name": "Coal", "tier": 1, "tag": "Fuel"},
            # Conflicting ID 2001 - should be chosen when no other preferences
            {"id": 2001, "name": "Oak Wood", "tier": 0, "tag": "Wood"}
        ],
        "crafting_recipe_desc": [
            {
                "id": 100,
                "name": "Iron Bar Recipe",
                "actions_required": 50,
                "crafted_item_stacks": [[3, 1]]  # Iron Bar x1
            },
            {
                "id": 101, 
                "name": "Supply Package Recipe",
                "actions_required": 25,
                "crafted_item_stacks": [[1001, 1]]  # Supply Package x1 - should use cargo_desc
            }
        ],
        "building_desc": [
            {"id": 200, "name": "Smelting Station"},
            {"id": 201, "name": "Crafting Station"}
        ]
    }


def get_mock_spacetime_messages() -> Dict[str, Any]:
    """Generate mock SpacetimeDB messages for testing."""
    return {
        "transaction_update": {
            "TransactionUpdate": {
                "status": {
                    "Committed": {
                        "tables": [
                            {
                                "table_name": "inventory_state",
                                "inserts": [
                                    {"entity_id": "inv-1", "item_id": 1, "quantity": 10}
                                ],
                                "deletes": []
                            }
                        ]
                    }
                },
                "reducer_call": {
                    "reducer_name": "add_item"
                },
                "timestamp": {
                    "__timestamp_micros_since_unix_epoch__": 1640995200000000
                }
            }
        },
        "subscription_update": {
            "SubscriptionUpdate": {
                "database_update": {
                    "tables": [
                        {
                            "table_name": "inventory_state",
                            "inserts": [
                                {"entity_id": "inv-1", "item_id": 1, "quantity": 10},
                                {"entity_id": "inv-2", "item_id": 2, "quantity": 5}
                            ],
                            "deletes": []
                        }
                    ]
                }
            }
        },
        "initial_subscription": {
            "InitialSubscription": {
                "database_update": {
                    "tables": [
                        {
                            "table_name": "inventory_state",
                            "inserts": [
                                {"entity_id": "inv-1", "item_id": 1, "quantity": 10}
                            ],
                            "deletes": []
                        },
                        {
                            "table_name": "passive_craft_state",
                            "inserts": [
                                {
                                    "entity_id": "craft-1",
                                    "recipe_id": 100,
                                    "completion_time": {"__timestamp_micros_since_unix_epoch__": 1640995200000000}
                                }
                            ],
                            "deletes": []
                        }
                    ]
                }
            }
        }
    }


def get_mock_claim_data() -> Dict[str, Any]:
    """Generate mock claim data for testing."""
    return {
        "claims": [
            {
                "entity_id": "claim-1",
                "claim_id": "claim-1",
                "name": "Test Claim 1",
                "claim_name": "Test Claim 1"
            },
            {
                "entity_id": "claim-2", 
                "claim_id": "claim-2",
                "name": "Test Claim 2",
                "claim_name": "Test Claim 2"
            }
        ],
        "claim_members": [
            {
                "claim_entity_id": "claim-1",
                "player_entity_id": "test-user-id-123",
                "user_name": "TestPlayer"
            },
            {
                "claim_entity_id": "claim-1",
                "player_entity_id": "other-user-id",
                "user_name": "OtherPlayer"
            }
        ]
    }


# ========== PYTEST FIXTURES ==========

@pytest.fixture(autouse=True)
def prevent_real_file_writes():
    """Prevent tests from writing to real player_data.json but allow mocking."""
    # Only mock the file path to redirect writes to a safe location
    with patch('app.core.data_paths.get_user_data_path', return_value='/tmp/test_player_data.json'):
        yield


@pytest.fixture
def mock_bitcraft_client():
    """Provide a mock BitCraft client."""
    return MockBitCraftClient()


@pytest.fixture
def mock_data_queue():
    """Provide a mock data queue."""
    return queue.Queue()


@pytest.fixture
def mock_reference_data():
    """Provide mock reference data."""
    return get_mock_reference_data()


@pytest.fixture
def mock_spacetime_messages():
    """Provide mock SpacetimeDB messages."""
    return get_mock_spacetime_messages()


@pytest.fixture
def mock_claim_data():
    """Provide mock claim data."""
    return get_mock_claim_data()


@pytest.fixture
def mock_services(mock_bitcraft_client):
    """Provide mock services dictionary."""
    return {
        "client": mock_bitcraft_client,
        "claim": Mock(),
        "claim_manager": Mock(),
        "inventory_service": Mock(),
        "passive_crafting_service": Mock(),
        "traveler_tasks_service": Mock(),
        "active_crafting_service": Mock(),
        "data_service": Mock()
    }


@pytest.fixture
def mock_processors():
    """Provide mock processors for testing."""
    return [
        MockProcessor(["inventory_state"]),
        MockProcessor(["passive_craft_state", "traveler_task_state"]),
        MockProcessor(["claim_state"])
    ]


@pytest.fixture
def mock_player():
    """Provide a mock player instance."""
    player = Mock()
    player.user_id = "test-user-id-123" 
    player.player_name = "TestPlayer"
    return player


@pytest.fixture
def mock_claim():
    """Provide a mock claim instance."""
    claim = Mock()
    claim.claim_id = "claim-1"
    claim.treasury = 1000
    claim.supplies = 500
    claim.size = 25
    return claim


# ========== UTILITY FUNCTIONS ==========

def setup_mock_query_responses(client: MockBitCraftClient, claim_data: Dict):
    """Setup mock query responses for common queries."""
    client.query_responses.update({
        "SELECT * FROM claim_member_state WHERE claim_entity_id = 'claim-1';": claim_data["claim_members"],
        "SELECT * FROM player_lowercase_username_state WHERE username_lowercase = 'testplayer';": [
            {"entity_id": "test-user-id-123", "username": "TestPlayer"}
        ],
        "SELECT * FROM claim_state WHERE entity_id = 'claim-1';": [
            {"entity_id": "claim-1", "name": "Test Claim 1"}
        ]
    })


def create_test_message_router(processors, data_queue):
    """Create a MessageRouter instance for testing."""
    from app.core.message_router import MessageRouter
    return MessageRouter(processors, data_queue)


def trigger_subscription_callback(client: MockBitCraftClient, message: Dict):
    """Trigger the subscription callback with a test message."""
    if client.subscription_listener and client.subscription_listener["callback"]:
        client.subscription_listener["callback"](message)