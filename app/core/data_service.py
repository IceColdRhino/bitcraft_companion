import logging
import queue
import threading
import time

from .message_router import MessageRouter
from .processors import InventoryProcessor, CraftingProcessor, TasksProcessor, ClaimsProcessor, ActiveCraftingProcessor, CompareJobsProcessor
from .utils import ItemLookupService
from ..services.notification_service import NotificationService
from ..client.query_service import QueryService
from ..models.player import Player
from ..models.claim import Claim
from ..services.inventory_service import InventoryService
from ..services.passive_crafting_service import PassiveCraftingService
from ..services.traveler_tasks_service import TravelerTasksService
from ..services.active_crafting_service import ActiveCraftingService
from ..services.compare_jobs_service import CompareJobsService
from ..services.claim_service import ClaimService


class DataService:
    """
    Manages the connection to the game client, handles data subscriptions,
    and passes data to the GUI via a thread-safe queue.

    Refactored to use MessageRouter and focused data processors while
    preserving the exact same interface and subscription patterns.
    """

    def __init__(self):
        # Import BitCraft lazily to avoid circular dependency with core.__init__.py
        from ..client.bitcraft_client import BitCraft
        
        # Instantiate the client immediately to load saved user data
        self.client = BitCraft()

        self.player = None
        self.claim = None
        self.inventory_service = None
        self.passive_crafting_service = None
        self.traveler_tasks_service = None
        self.active_crafting_service = None
        self.compare_jobs_service = None
        self.claim_manager = None
        self.current_subscriptions = []

        # Notification service
        self.notification_service = None
        self.main_app = None

        # Message router and processors
        self.message_router = None
        self.processors = []

        self.data_queue = queue.Queue()
        self._stop_event = threading.Event()
        self.service_thread = None

    def set_main_app(self, main_app):
        """Set the main app reference and initialize notification service."""
        self.main_app = main_app
        self.notification_service = NotificationService(main_app)

    def start(self, username, password, region, player_name):
        """Starts the data fetching thread with user credentials."""
        if self.service_thread and self.service_thread.is_alive():
            logging.warning("DataService is already running.")
            return

        self._stop_event.clear()
        self.service_thread = threading.Thread(target=self._run, args=(username, password, region, player_name), daemon=True)
        self.service_thread.start()

    def stop(self):
        """Stop the data service and clean up resources."""
        logging.info("Stopping DataService...")

        try:
            self._stop_event.set()

            if hasattr(self, "processors"):
                for processor in self.processors:
                    if hasattr(processor, "stop_real_time_timer"):
                        logging.info(f"Stopping timer for {processor.__class__.__name__}...")
                        processor.stop_real_time_timer()

            if self.claim_manager:
                logging.info("Saving claims cache...")
                self.claim_manager._save_claims_cache()

            # Close WebSocket connection with timeout
            if self.client:
                logging.info("Closing WebSocket connection...")
                try:
                    self.client.close_websocket()
                except Exception as e:
                    logging.warning(f"Error closing WebSocket: {e}")

            # Wait for service thread to finish with timeout
            if self.service_thread and self.service_thread.is_alive():
                logging.info("Waiting for service thread to finish...")
                self.service_thread.join(timeout=2.0)

                if self.service_thread.is_alive():
                    logging.warning("Service thread did not finish within timeout")
                else:
                    logging.info("Service thread finished cleanly")

        except Exception as e:
            logging.error(f"Error during DataService stop: {e}")

    def _run(self, username, password, region, player_name):
        """
        Main thread function - refactored for improved maintainability.

        Orchestrates the initialization process through focused methods:
        """
        thread_start_time = time.time()
        logging.info(f"[DataService] Starting service thread for player: {player_name}")

        try:
            if not self._authenticate_user(username, password):
                return

            if not self._establish_connection(region):
                return

            reference_data, all_claims, current_claim = self._initialize_player_and_claims(player_name)
            if not reference_data:
                return

            if not self._setup_services_and_processors(reference_data):
                return

            if not self._start_subscriptions():
                return

            total_startup_time = time.time() - thread_start_time
            logging.info(f"[DataService] Service ready! Total startup time: {total_startup_time:.3f}s")
            logging.info("[DataService] Monitoring for data updates...")

            # Keep thread alive
            while not self._stop_event.is_set():
                time.sleep(1)

        except Exception as e:
            logging.error(f"[DataService] Error in data thread: {e}", exc_info=True)
            self.data_queue.put({"type": "error", "data": f"Connection error: {e}"})
        finally:
            if self.client:
                self.client.close_websocket()
            logging.info("[DataService] Thread stopped and connection closed.")

    def _authenticate_user(self, username, password):
        """
        Authenticate user credentials with the BitCraft API.

        Args:
            username: User's login username
            password: User's login password

        Returns:
            bool: True if authentication succeeded, False otherwise
        """
        try:
            auth_start = time.time()
            logging.debug(f"[DataService] Starting authentication for {username[:3]}***")

            if not self.client.authenticate(username, password):
                logging.error("[DataService] Authentication failed")
                self.data_queue.put(
                    {"type": "connection_status", "data": {"status": "failed", "reason": "Authentication failed"}}
                )
                return False

            auth_time = time.time() - auth_start
            logging.debug(f"[DataService] Authentication completed in {auth_time:.3f}s")
            return True

        except Exception as e:
            logging.error(f"[DataService] Authentication error: {e}")
            self.data_queue.put(
                {"type": "connection_status", "data": {"status": "failed", "reason": f"Authentication error: {e}"}}
            )
            return False

    def _establish_connection(self, region):
        """
        Establish WebSocket connection to the game servers.

        Args:
            region: Game region to connect to

        Returns:
            bool: True if connection succeeded, False otherwise
        """
        try:
            # Set region and connection details
            self.client.set_region(region)
            self.client.set_endpoint("subscribe")
            self.client.set_websocket_uri()
            logging.debug(f"[DataService] Connection configured for region: {region}")

            # Test basic connectivity first
            logging.debug("[DataService] Testing server connectivity...")
            if not self.client.test_server_connectivity():
                # Run full diagnostics if basic connectivity fails
                logging.debug("[DataService] Running connection diagnostics...")
                self.client.diagnose_connection_issues()

                error_msg = "Server connectivity test failed. Check your internet connection and try again."
                logging.error(f"[DataService] {error_msg}")
                self.data_queue.put({"type": "connection_status", "data": {"status": "failed", "reason": error_msg}})
                return False

            # Connect WebSocket with retry logic
            ws_start = time.time()
            logging.debug("[DataService] Attempting WebSocket connection with retry")
            self.client.connect_websocket_with_retry(max_retries=3, base_delay=2.0)
            ws_time = time.time() - ws_start
            logging.debug(f"[DataService] WebSocket connection established in {ws_time:.3f}s")
            self.data_queue.put({"type": "connection_status", "data": {"status": "connected"}})
            return True

        except Exception as e:
            logging.error(f"[DataService] WebSocket connection failed after retries: {e}")
            self.data_queue.put({"type": "connection_status", "data": {"status": "failed", "reason": str(e)}})
            return False

    def _initialize_player_and_claims(self, player_name):
        """
        Initialize player instance and fetch all user claims.

        Args:
            player_name: Name of the player to initialize

        Returns:
            tuple: (reference_data, all_claims, current_claim) or (None, None, None) on failure
        """
        try:
            # Set player
            self.player = Player(player_name)
            logging.debug(f"[DataService] Player instance created: {player_name}")

            # Load reference data
            ref_start = time.time()
            logging.debug("[DataService] Loading game reference data")
            reference_data = self.client.load_full_reference_data()
            if not reference_data:
                logging.error("[DataService] Failed to load game reference data")
                self.data_queue.put({"type": "error", "data": "Failed to load game reference data"})
                return None, None, None

            ref_time = time.time() - ref_start
            logging.debug(f"[DataService] Reference data loaded in {ref_time:.3f}s")

            # Get user ID
            user_start = time.time()
            logging.debug(f"[DataService] Fetching user ID for {player_name}")
            user_id = self.client.fetch_user_id_by_username(player_name)
            if not user_id:
                logging.error(f"[DataService] Could not retrieve user ID for {player_name}.")
                self.data_queue.put({"type": "error", "data": f"Could not find player: {player_name}"})
                return None, None, None
            self.player.user_id = user_id
            user_time = time.time() - user_start
            logging.debug(f"[DataService] User ID retrieved in {user_time:.3f}s")

            # Initialize claim manager
            logging.debug("[DataService] Initializing claim manager")
            query_service = QueryService(self.client)
            self.claim_manager = ClaimService(self.client, query_service)

            # Fetch all claims for the user using query service
            claims_start = time.time()
            logging.debug(f"[DataService] Fetching claims for user {user_id}")
            all_claims = self.claim_manager.fetch_all_user_claims(user_id)
            if not all_claims:
                logging.error(f"[DataService] No claims found for user {player_name}.")
                self.data_queue.put({"type": "error", "data": f"No claims found for player: {player_name}"})
                return None, None, None

            claims_time = time.time() - claims_start
            logging.info(f"[DataService] Found {len(all_claims)} claims in {claims_time:.3f}s")

            # Standardize claim keys for UI compatibility
            for claim in all_claims:
                # Add both key formats for backward compatibility
                if "entity_id" in claim and "claim_id" not in claim:
                    claim["claim_id"] = claim["entity_id"]
                if "name" in claim and "claim_name" not in claim:
                    claim["claim_name"] = claim["name"]

            # Set up claim manager with all claims
            self.claim_manager.set_available_claims(all_claims)

            # Send claims list to UI
            self.data_queue.put(
                {
                    "type": "claims_list_update",
                    "data": {"claims": all_claims, "current_claim_id": self.claim_manager.current_claim_id},
                }
            )

            # Initialize claim instance with current claim
            current_claim = self.claim_manager.get_current_claim()
            if not current_claim:
                self.data_queue.put({"type": "error", "data": "No current claim available"})
                return None, None, None

            logging.info(f"[DataService] Setting active claim: {current_claim.get('name', 'Unknown')}")
            self.claim = Claim(
                client=self.client,
                reference_data=reference_data,
            )
            self.claim.claim_id = current_claim["entity_id"]

            return reference_data, all_claims, current_claim

        except Exception as e:
            logging.error(f"[DataService] Error initializing player and claims: {e}")
            self.data_queue.put({"type": "error", "data": f"Player/claims initialization error: {e}"})
            return None, None, None

    def _setup_services_and_processors(self, reference_data):
        """
        Initialize all services, processors, and message routing.

        Args:
            reference_data: Game reference data dictionary

        Returns:
            bool: True if setup succeeded, False otherwise
        """
        try:
            # Initialize services for processors
            inventory_service = InventoryService(bitcraft_client=self.client, claim_instance=self.claim)
            passive_crafting_service = PassiveCraftingService(
                bitcraft_client=self.client,
                claim_instance=self.claim,
                reference_data=reference_data,
            )
            traveler_tasks_service = TravelerTasksService(
                bitcraft_client=self.client,
                player_instance=self.player,
                reference_data=reference_data,
            )
            active_crafting_service = ActiveCraftingService(
                bitcraft_client=self.client,
                claim_instance=self.claim,
                reference_data=reference_data,
            )
            compare_jobs_service = CompareJobsService(
                bitcraft_client=self.client,
                claim_instance=self.claim,
                reference_data=reference_data,
            )

            # Store service references for cleanup
            self.inventory_service = inventory_service
            self.passive_crafting_service = passive_crafting_service
            self.traveler_tasks_service = traveler_tasks_service
            self.active_crafting_service = active_crafting_service
            self.compare_jobs_service = compare_jobs_service

            # Initialize shared utilities
            item_lookup_service = ItemLookupService(reference_data)
            logging.debug(f"[DataService] ItemLookupService initialized with {item_lookup_service.get_stats()}")

            # Initialize processors and message router (subscription-based architecture only)
            services = {
                "claim_manager": self.claim_manager,
                "client": self.client,
                "claim": self.claim,
                "inventory_service": inventory_service,
                "passive_crafting_service": passive_crafting_service,
                "traveler_tasks_service": traveler_tasks_service,
                "active_crafting_service": active_crafting_service,
                "compare_jobs_service": compare_jobs_service,
                "item_lookup_service": item_lookup_service,
                "data_service": self,
            }

            self.processors = [
                InventoryProcessor(self.data_queue, services, reference_data),
                CraftingProcessor(self.data_queue, services, reference_data),
                TasksProcessor(self.data_queue, services, reference_data),
                ClaimsProcessor(self.data_queue, services, reference_data),
                ActiveCraftingProcessor(self.data_queue, services, reference_data),
                CompareJobsProcessor(self.data_queue, services, reference_data),
            ]

            self.message_router = MessageRouter(self.processors, self.data_queue)

            # Start real-time timers in processors
            for processor in self.processors:
                # Start timer for crafting processor (passive crafting)
                if hasattr(processor, "start_real_time_timer"):
                    processor.start_real_time_timer(self._handle_timer_update)

            return True

        except Exception as e:
            logging.error(f"[DataService] Error setting up services and processors: {e}")
            self.data_queue.put({"type": "error", "data": f"Services setup error: {e}"})
            return False

    def _start_subscriptions(self):
        """
        Start data subscriptions for the current claim.

        Returns:
            bool: True if subscriptions started successfully, False otherwise
        """
        try:
            setup_start = time.time()
            logging.info("[DataService] Setting up data subscriptions...")
            self._setup_subscriptions_for_current_claim()
            setup_time = time.time() - setup_start
            logging.debug(f"[DataService] Subscriptions setup completed in {setup_time:.3f}s")
            return True

        except Exception as e:
            logging.error(f"[DataService] Error starting subscriptions: {e}")
            self.data_queue.put({"type": "error", "data": f"Subscriptions setup error: {e}"})
            return False

    def _handle_timer_update(self, timer_data):
        """Handle real-time timer updates from the crafting service"""
        try:
            self.data_queue.put(timer_data)
        except Exception as e:
            logging.error(f"Error handling timer update: {e}")

    def _setup_subscriptions_for_current_claim(self, context="startup"):
        """
        Sets up subscriptions for the currently active claim using query service.
        All data comes through subscriptions - no one-off queries.

        Args:
            context: "startup" for initial app startup, "refresh" for claim refresh
        """
        try:
            logging.debug("[DataService] _setup_subscriptions_for_current_claim() called")

            if not self.claim.claim_id or not self.player.user_id:
                logging.warning("[DataService] No claim ID or user ID available for subscriptions")
                return

            # Use query service to get all subscription queries
            query_service = QueryService(self.client)
            all_subscriptions = query_service.get_subscription_queries(self.player.user_id, self.claim.claim_id)

            logging.debug(f"[DataService] Generated {len(all_subscriptions)} subscription queries")
            for i, query in enumerate(all_subscriptions):
                logging.debug(f"[DataService] Subscription {i+1}: {query[:50]}...")

            # Start subscriptions - route to message router
            if all_subscriptions:
                logging.debug("[DataService] Starting subscription listener with message router")
                self.client.start_subscription_listener(all_subscriptions, self.message_router.handle_message)
                self.current_subscriptions = all_subscriptions
                logging.info(f"[DataService] Started {len(all_subscriptions)} subscriptions for claim {self.claim.claim_id}")
            else:
                logging.warning("[DataService] No subscription queries generated")

        except Exception as e:
            logging.error(f"[DataService] Error setting up subscriptions: {e}")

    # Preserve existing methods that UI depends on
    def get_current_claim_info(self) -> dict:
        """Returns current claim information for UI updates."""
        if self.claim_manager and self.claim:
            current_claim = self.claim_manager.get_current_claim()
            if current_claim:
                return {
                    "claim_id": current_claim["claim_id"],
                    "claim_name": current_claim["claim_name"],
                    "treasury": self.claim.treasury,
                    "supplies": self.claim.supplies,
                    "tile_count": self.claim.size,
                    "available_claims": self.claim_manager.get_all_claims(),
                }
        return {}

    def switch_claim(self, claim_id):
        """Switch to a different claim - preserve existing interface."""
        try:
            if not claim_id:
                logging.warning("No claim ID provided for switch")
                return False

            # Get new claim data for UI messaging
            new_claim_data = self.claim_manager.get_claim_by_id(claim_id)
            if not new_claim_data:
                logging.error(f"Claim {claim_id} not found in available claims")
                return False

            # Notify UI that claim switching is starting
            claim_name = new_claim_data.get("claim_name") or new_claim_data.get("name", "Unknown Claim")
            self.data_queue.put(
                {"type": "claim_switching", "data": {"status": "loading", "claim_name": claim_name, "claim_id": claim_id}}
            )

            # Save current claim state
            if self.claim_manager:
                self.claim_manager._save_claims_cache()

            # Clear processor caches to prevent data contamination
            logging.info("Clearing processor caches for claim switch...")
            for processor in self.processors:
                try:
                    processor.clear_cache()
                except Exception as e:
                    logging.warning(f"Error clearing cache in {processor.__class__.__name__}: {e}")

            # Switch to new claim (we'll implement set_current_claim method)
            self.claim_manager.set_current_claim(claim_id)

            # Update claim instance
            reference_data = self.client.load_full_reference_data()
            self.claim = Claim(
                client=self.client,
                reference_data=reference_data,
            )
            self.claim.claim_id = claim_id

            # Update processor services with new claim
            services = {
                "claim_manager": self.claim_manager,
                "client": self.client,
                "claim": self.claim,
            }

            for processor in self.processors:
                processor.services = services
                processor.claim = self.claim

            # Restart subscriptions for new claim (this automatically replaces existing subscriptions)
            self._setup_subscriptions_for_current_claim(context="claim_switch")

            # Notify UI that claim switching completed successfully
            self.data_queue.put(
                {
                    "type": "claim_switched",
                    "data": {
                        "status": "success",
                        "claim_id": claim_id,
                        "claim_name": claim_name,
                        "claim_info": {
                            "name": claim_name,
                            "treasury": getattr(self.claim, "treasury", 0),
                            "supplies": getattr(self.claim, "supplies", 0),
                            "tile_count": getattr(self.claim, "size", 0),
                        },
                    },
                }
            )

            logging.info(f"Successfully switched to claim: {claim_name}")
            return True

        except Exception as e:
            logging.error(f"Error switching claims: {e}")
            # Notify UI of error
            self.data_queue.put({"type": "claim_switched", "data": {"status": "error", "error": str(e)}})
            return False

    def refresh_current_claim_data(self):
        """Refresh all data for the current claim by restarting subscriptions."""
        try:
            logging.debug("[DataService] refresh_current_claim_data() called")

            if not self.claim or not self.claim.claim_id:
                logging.warning("[DataService] No current claim available for data refresh")
                return False

            if not self.player or not self.player.user_id:
                logging.warning("[DataService] No user ID available for data refresh")
                return False

            logging.info(f"[DataService] Refreshing data for current claim: {self.claim.claim_id}")

            # Clear all processor caches to ensure fresh data
            if hasattr(self, "message_router") and self.message_router:
                logging.debug("[DataService] Clearing all processor caches before refresh")
                self.message_router.clear_all_processor_caches()
                logging.debug("[DataService] Processor caches cleared successfully")
            else:
                logging.warning("[DataService] No message router available for cache clearing")

            # Restart subscriptions for current claim (this will fetch all fresh data)
            logging.debug("[DataService] Restarting subscriptions for fresh data")
            self._setup_subscriptions_for_current_claim(context="refresh")
            logging.debug("[DataService] Subscriptions restarted successfully")

            logging.info("[DataService] Current claim data refresh completed successfully")
            return True

        except Exception as e:
            logging.error(f"[DataService] Error refreshing current claim data: {e}")
            return False

    def refresh_claims_list(self):
        """Refresh the list of available claims for the current user."""
        try:
            if not self.player or not self.player.user_id:
                logging.warning("No user ID available for claims refresh")
                return False

            if not self.claim_manager:
                logging.warning("Claim manager not available for refresh")
                return False

            # Refresh claims using the claim service
            updated_claims = self.claim_manager.refresh_user_claims(self.player.user_id)

            if updated_claims:
                # Standardize claim keys for UI compatibility
                for claim in updated_claims:
                    # Add both key formats for backward compatibility
                    if "entity_id" in claim and "claim_id" not in claim:
                        claim["claim_id"] = claim["entity_id"]
                    if "name" in claim and "claim_name" not in claim:
                        claim["claim_name"] = claim["name"]

                # Send updated claims list to UI
                self.data_queue.put(
                    {
                        "type": "claims_list_update",
                        "data": {"claims": updated_claims, "current_claim_id": self.claim_manager.current_claim_id},
                    }
                )
                logging.info(f"Claims list refreshed: {len(updated_claims)} claims")
                return True
            else:
                logging.warning("No claims found during refresh")
                return False

        except Exception as e:
            logging.error(f"Error refreshing claims list: {e}")
            return False
