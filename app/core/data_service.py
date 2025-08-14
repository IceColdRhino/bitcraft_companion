import logging
import queue
import threading
import time

from .message_router import MessageRouter
from .processors import InventoryProcessor, CraftingProcessor, TasksProcessor, ClaimsProcessor, ActiveCraftingProcessor, CompareJobsProcessor, ReferenceDataProcessor
from .utils import ItemLookupService
from ..services.notification_service import NotificationService
from ..services.claim_service import ClaimService
from ..client.query_service import QueryService
from ..models.claim import Claim


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

        self.user_id = None
        self.username = None
        self.claim = None
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
            if reference_data is None:
                return

            if not self._setup_services_and_processors(reference_data):
                return

            if not self._start_subscriptions():
                return

            total_startup_time = time.time() - thread_start_time
            logging.info(f"BitCraft Companion ready! Startup completed in {total_startup_time:.1f}s")
            logging.info("Monitoring for game data updates...")

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
            logging.info(f"Authenticating user {username[:3]}***...")

            if not self.client.authenticate(username, password):
                logging.error("Authentication failed")
                logging.warning("Authentication failed - check credentials or account status")
                self.data_queue.put(
                    {"type": "connection_status", "data": {"status": "failed", "reason": "Authentication failed"}}
                )
                return False

            auth_time = time.time() - auth_start
            logging.debug(f"[DEBUG] Authentication completed in {auth_time:.3f}s")
            return True

        except Exception as e:
            logging.error(f"Authentication error: {e}")
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
            logging.debug(f"[DEBUG] Connection configured for region: {region}")

            # Test basic connectivity first
            logging.info("Testing server connectivity...")
            if not self.client.test_server_connectivity():
                # Run full diagnostics if basic connectivity fails
                logging.debug("[DEBUG] Running connection diagnostics...")
                self.client.diagnose_connection_issues()

                error_msg = "Server connectivity test failed. Check your internet connection and try again."
                logging.warning("Unable to reach BitCraft servers - check network connectivity or server status")
                logging.error(error_msg)
                self.data_queue.put({"type": "connection_status", "data": {"status": "failed", "reason": error_msg}})
                return False

            # Connect WebSocket with retry logic
            ws_start = time.time()
            logging.info("Connecting to BitCraft servers...")
            self.client.connect_websocket_with_retry(max_retries=3, base_delay=2.0)
            ws_time = time.time() - ws_start
            logging.debug(f"[DEBUG] WebSocket connection established in {ws_time:.3f}s")
            self.data_queue.put({"type": "connection_status", "data": {"status": "connected"}})
            return True

        except Exception as e:
            logging.error(f"Connection failed: {e}")
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
            # Set player info directly
            self.username = player_name
            logging.debug(f"[DEBUG] Player name set: {player_name}")

            # Reference data is now loaded via subscriptions through ReferenceDataProcessor
            logging.info("Reference data will be loaded via subscriptions")

            # Get user ID
            user_start = time.time()
            logging.info(f"Finding player: {player_name}")
            user_id = self.client.fetch_user_id_by_username(player_name)
            if not user_id:
                logging.error(f"Could not find player: {player_name}")
                logging.warning(f"Player '{player_name}' not found in database - check spelling or account status")
                self.data_queue.put({"type": "error", "data": f"Could not find player: {player_name}"})
                return None, None, None
            self.user_id = user_id
            user_time = time.time() - user_start
            logging.debug(f"[DEBUG] User ID retrieved in {user_time:.3f}s")

            # Initialize claim manager
            logging.debug("[DEBUG] Initializing claim manager")
            query_service = QueryService(self.client)
            self.claim_manager = ClaimService(self.client, query_service)

            # Fetch all claims for the user using query service
            claims_start = time.time()
            logging.info("Loading your claims...")
            all_claims = self.claim_manager.fetch_all_user_claims(self.user_id)
            if not all_claims:
                logging.error(f"No claims found for player: {player_name}")
                logging.warning(f"Player '{player_name}' has no accessible claims - may not be a member of any claims")
                self.data_queue.put({"type": "error", "data": f"No claims found for player: {player_name}"})
                return None, None, None

            claims_time = time.time() - claims_start
            logging.info(f"Found {len(all_claims)} claims")
            logging.debug(f"[DEBUG] Claims loaded in {claims_time:.3f}s")

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

            logging.info(f"Setting active claim: {current_claim.get('name', 'Unknown')}")
            self.claim = Claim()
            self.claim.claim_id = current_claim["entity_id"]

            return {}, all_claims, current_claim  # Empty dict for backward compatibility

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
            # Note: TravelerTasksService was removed - TasksProcessor handles all traveler task functionality

            # Initialize shared utilities
            item_lookup_service = ItemLookupService(reference_data)
            logging.debug(f"[DataService] ItemLookupService initialized with {item_lookup_service.get_stats()}")

            # Initialize processors and message router (subscription-based architecture only)
            services = {
                "claim_manager": self.claim_manager,
                "client": self.client,
                "claim": self.claim,
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
                ReferenceDataProcessor(self.data_queue, services, reference_data),
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

            if not self.claim.claim_id or not self.user_id:
                logging.warning("[DataService] No claim ID or user ID available for subscriptions")
                return

            # Use query service to get all subscription queries
            query_service = QueryService(self.client)
            all_subscriptions = query_service.get_subscription_queries(self.user_id, self.claim.claim_id)

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
            self.claim = Claim()
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

            if not self.user_id:
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
            if not self.user_id:
                logging.warning("No user ID available for claims refresh")
                return False

            if not self.claim_manager:
                logging.warning("Claim manager not available for refresh")
                return False

            # Refresh claims using the claim service
            updated_claims = self.claim_manager.refresh_user_claims(self.user_id)

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
