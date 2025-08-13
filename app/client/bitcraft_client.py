import json
import logging
import os
import re
import socket
import sqlite3
import threading
import time
import uuid

import keyring
import requests
from websockets import Subprotocol
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection, connect

from ..core.data_paths import get_bundled_data_path, get_user_data_path


class BitCraft:
    """BitCraft API client for WebSocket database queries and authentication."""

    SERVICE_NAME = "BitCraftAPI"
    DEFAULT_SUBPROTOCOL = "v1.json.spacetimedb"
    AUTH_API_BASE_URL = "https://api.bitcraftonline.com/authentication"

    def __init__(self):
        self.host = os.getenv("BITCRAFT_SPACETIME_HOST", "bitcraft-early-access.spacetimedb.com")
        self.uri = "{scheme}://{host}/v1/database/{module}/{endpoint}"
        self.proto = Subprotocol(self.DEFAULT_SUBPROTOCOL)
        self.ws_connection: ClientConnection | None = None
        self.module = None
        self.endpoint = None
        self.ws_uri = None
        self.headers = {}
        self.ws_lock = threading.Lock()
        self.subscription_thread = None
        self._stop_subscription = threading.Event()

        # Configure websockets logging to prevent Unicode encoding errors
        self._configure_websocket_logging()

        # Load initial data
        self.load_user_data_from_file()
        self.email = self._get_credential_from_keyring("email")
        self.auth = self._get_credential_from_keyring("authorization_token")

    def _configure_websocket_logging(self):
        """Configure websockets library logging to handle Unicode safely."""
        try:
            # Get the websockets logger
            ws_logger = logging.getLogger("websockets")

            # Create a custom handler that handles Unicode encoding errors
            class SafeStreamHandler(logging.StreamHandler):
                def emit(self, record):
                    try:
                        super().emit(record)
                    except UnicodeEncodeError as e:
                        # Log the error safely without the problematic Unicode characters
                        try:
                            safe_msg = str(record.getMessage()).encode("ascii", "replace").decode("ascii")
                            safe_record = logging.makeLogRecord(
                                {
                                    "name": record.name,
                                    "level": record.levelno,
                                    "msg": f"WebSocket message (Unicode chars replaced): {safe_msg}",
                                    "args": (),
                                }
                            )
                            super().emit(safe_record)
                        except Exception:
                            # Last resort - just log that there was an issue
                            super().emit(
                                logging.makeLogRecord(
                                    {
                                        "name": record.name,
                                        "level": logging.WARNING,
                                        "msg": "WebSocket logging failed due to Unicode encoding issue",
                                        "args": (),
                                    }
                                )
                            )

            # Remove existing handlers and add our safe handler
            for handler in ws_logger.handlers[:]:
                ws_logger.removeHandler(handler)

            safe_handler = SafeStreamHandler()
            safe_handler.setLevel(logging.DEBUG)
            ws_logger.addHandler(safe_handler)
            ws_logger.setLevel(logging.DEBUG)

        except Exception as e:
            logging.warning(f"Failed to configure websockets logging: {e}")

    def query(self, query_string: str) -> list[dict] | None:
        """
        Sends a one-off SQL query over the WebSocket and returns all result rows.

        Args:
            query_string (str): The SQL query to execute.

        Returns:
            A list of dictionaries representing the rows of the result, or None if no data is returned.

        Raises:
            RuntimeError: If the WebSocket connection is not established.
        """
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established")

            message_id = str(uuid.uuid4()).replace("-", "")
            subscribe_message = {
                "OneOffQuery": {
                    "message_id": message_id,
                    "query_string": query_string,
                }
            }

            try:
                self.ws_connection.send(json.dumps(subscribe_message))
                return list(self._receive_one_off_query(message_id))
            except (ConnectionClosed, TimeoutError) as e:
                logging.error(f"Failed to send or receive query due to connection issue: {e}")
                self.close_websocket()
                return None
            except Exception as e:
                logging.error(f"An unexpected error occurred during query: {e}")
                return None

    def _receive_one_off_query(self, message_id: str):
        """Listens for a specific OneOffQueryResponse and yields its rows."""
        if not self.ws_connection:
            raise RuntimeError("WebSocket connection is not established")

        # Set a timeout to avoid blocking indefinitely
        timeout_seconds = 10
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            try:
                msg = self.ws_connection.recv(timeout=1.0)
                data = json.loads(msg)

                if "OneOffQueryResponse" in data and data["OneOffQueryResponse"].get("message_id") == message_id:
                    tables = data["OneOffQueryResponse"].get("tables", [])
                    for table in tables:
                        for row_str in table.get("rows", []):
                            try:
                                yield json.loads(row_str)
                            except json.JSONDecodeError:
                                logging.error(f"Failed to decode JSON from WebSocket row: {row_str[:100]}...")
                    return

                elif "error" in data:
                    logging.error(f"WebSocket error received for message {message_id}: {data['error']}")
                    return

            except TimeoutError:
                continue
            except json.JSONDecodeError:
                logging.error(f"Failed to decode JSON from WebSocket message: {msg[:100]}...")
            except ConnectionClosed:
                logging.error("Connection closed while waiting for query response.")
                return
            except Exception as e:
                logging.error(f"Unexpected error processing WebSocket message: {e}")
                return

        logging.warning(f"Timed out waiting for response to query with message_id: {message_id}")

    def _get_credential_from_keyring(self, key_name: str) -> str | None:
        try:
            credential = keyring.get_password(self.SERVICE_NAME, key_name)
            if credential:
                logging.debug(f"Credential '{key_name}' loaded from keyring.")
            else:
                logging.debug(f"Credential '{key_name}' not found in keyring.")
            return credential
        except keyring.errors.NoKeyringError:
            logging.warning("No keyring backend found. Credentials will not be securely stored.")
            return None
        except Exception as e:
            logging.error(f"Error retrieving '{key_name}' from keyring: {e}")
            return None

    def _set_credential_in_keyring(self, key_name: str, value: str):
        try:
            keyring.set_password(self.SERVICE_NAME, key_name, value)
            logging.debug(f"Credential '{key_name}' stored in keyring.")
        except keyring.errors.NoKeyringError:
            logging.warning("No keyring backend found. Cannot securely store credentials.")
        except Exception as e:
            logging.error(f"Error storing '{key_name}' in keyring: {e}")

    def _delete_credential_from_keyring(self, key_name: str):
        try:
            keyring.delete_password(self.SERVICE_NAME, key_name)
            logging.debug(f"Credential '{key_name}' deleted from keyring.")
        except keyring.errors.NoKeyringError:
            logging.warning("No keyring backend found. Cannot delete credentials.")
        except keyring.errors.PasswordDeleteError:
            logging.warning(f"Credential '{key_name}' not found in keyring to delete.")
        except Exception as e:
            logging.error(f"Error deleting '{key_name}' from keyring: {e}")

    def _load_reference_data(self, table: str) -> list[dict] | None:
        if table == "player_data":
            file_path = get_user_data_path("player_data.json")
            try:
                with open(file_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Error loading player_data.json: {e}")
                return None

        db_path = get_bundled_data_path("data.db")
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
            for row in result:
                for field, value in row.items():
                    if isinstance(value, str) and value.strip():
                        try:
                            row[field] = json.loads(value)
                        except (json.JSONDecodeError, ValueError):
                            pass
            conn.close()
            return result
        except Exception as e:
            logging.error(f"Error loading reference data from DB for table {table}: {e}")
            return None

    def load_full_reference_data(self) -> dict:
        """
        Loads all required reference data tables into a single dictionary.

        Returns:
            dict: Dictionary containing all reference data tables
        """
        reference_tables = [
            "resource_desc",
            "item_desc",
            "cargo_desc",
            "building_desc",
            "type_desc_ids",
            "building_types",
            "crafting_recipe_desc",
            "claim_tile_cost",
            "traveler_desc",
        ]

        reference_data = {}
        for table in reference_tables:
            data = self._load_reference_data(table)
            if data is not None:
                reference_data[table] = data
                logging.info(f"Loaded reference data for table: {table}")
            else:
                logging.warning(f"Failed to load reference data for table: {table}")

        logging.info(f"Loaded reference data for {len(reference_data)} tables")
        return reference_data

    def update_user_data_file(self, key: str, value: str):
        file_path = get_user_data_path("player_data.json")
        data = {}
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            logging.warning("player_data.json not found. Creating a new one.")
        except json.JSONDecodeError:
            logging.warning("player_data.json is malformed. Overwriting with new data.")
            data = {}

        try:
            data[key] = value
            with open(file_path, "w") as f:
                json.dump(data, f, indent=4)
            logging.info(f"User data file updated: {key} in {file_path}")
        except Exception as e:
            logging.error(f"Error writing to player_data.json: {e}")

    def load_user_data_from_file(self):
        try:
            with open(get_user_data_path("player_data.json"), "r") as f:
                data = json.load(f)
                self.email = data.get("email")
                self.region = data.get("region")
                self.player_name = data.get("player_name")
                self.host = data.get("host", self.host)
                logging.info("Non-sensitive user data loaded successfully from file.")
        except FileNotFoundError:
            logging.warning("player_data.json not found. Some user data might be missing.")
            self.email = None
            self.region = None
            self.player_name = None
        except json.JSONDecodeError:
            logging.error("player_data.json is corrupted or empty. Please check the file.")
            self.email = None
            self.region = None
            self.player_name = None

    def fetch_user_id_by_username(self, username: str) -> str | None:
        """
        Fetches the user entity ID for a given username using a one-off query.

        Args:
            username: The player username to look up.

        Returns:
            The user entity ID if found, otherwise None.
        """
        if not username:
            logging.error("Username cannot be empty for fetch_user_id.")
            return None

        # Sanitize username and construct the exact query needed
        sanitized_username = username.lower().replace("'", "''")
        query_string = f"SELECT * FROM player_lowercase_username_state WHERE username_lowercase = '{sanitized_username}';"
        try:
            results = self.query(query_string)

            if results and isinstance(results, list) and len(results) > 0:
                user_id = results[0].get("entity_id")
                if user_id:
                    logging.info(f"Successfully found user ID for {username}: {user_id}")
                    return user_id

            logging.warning(f"Query for username '{username}' returned no results.")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred in fetch_user_id_by_username: {e}")
            return None

    def _is_valid_email(self, email: str) -> bool:
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(email_regex, email) is not None

    def get_access_code(self, email: str) -> bool:
        if not email:
            raise ValueError("Email is required to request an access code.")
        if not self._is_valid_email(email):
            raise ValueError(f"Invalid email format: {email}")
        logging.info(f"Requesting new access code for {email}...")
        encoded_email = requests.utils.quote(email)
        uri = f"{self.AUTH_API_BASE_URL}/request-access-code?email={encoded_email}"
        try:
            response = requests.post(uri)
            response.raise_for_status()
            logging.info("Access Code request was successful! Check your email for the code.")
            return True
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"HTTP error requesting access code: {http_err} - {response.text}")
        except requests.exceptions.RequestException as req_err:
            logging.error(f"Network error requesting access code: {req_err}")
        except Exception as e:
            logging.error(f"An unexpected error occurred during access code request: {e}")
        return False

    def get_authorization_token(self, email: str, access_code: str) -> str | None:
        if not email:
            raise ValueError("Email is required to request an authorization token.")
        if not access_code:
            raise ValueError("Access code is required to request an authorization token.")
        if not self._is_valid_email(email):
            raise ValueError(f"Invalid email format: {email}")
        logging.info("Requesting new authorization token...")
        encoded_email = requests.utils.quote(email)
        uri = f"{self.AUTH_API_BASE_URL}/authenticate?email={encoded_email}&accessCode={access_code}"
        try:
            response = requests.post(uri)
            response.raise_for_status()
            authorization_token = response.json()
            self._set_credential_in_keyring("authorization_token", f"Bearer {authorization_token}")
            self._set_credential_in_keyring("email", email)
            self.auth = f"Bearer {authorization_token}"
            self.email = email
            logging.info(f"Authorization token received! {self.auth[:15]}...")
            return self.auth
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"HTTP error requesting authorization token: {http_err} - {response.text}")
        except requests.exceptions.RequestException as req_err:
            logging.error(f"Network error requesting authorization token: {req_err}")
        except json.JSONDecodeError:
            logging.error("Failed to decode JSON response for authorization token.")
        except Exception as e:
            logging.error(f"An unexpected error occurred during authorization token request: {e}")
        return None

    def authenticate(self, email: str = None, access_code: str = None) -> bool:
        effective_email = email if email is not None else self.email
        if not effective_email:
            logging.error("Authentication failed: Email is required.")
            return False
        if not self._is_valid_email(effective_email):
            logging.error(f"Authentication failed: Invalid email format: {effective_email}")
            return False
        if self.auth and access_code is None:
            logging.info("Authorization token already exists. Assuming authenticated.")
            return True
        if not access_code:
            logging.error("Authentication failed: Access code is required to obtain a new authorization token.")
            return False
        obtained_auth_token = self.get_authorization_token(effective_email, access_code)
        if obtained_auth_token:
            logging.info("Authentication successful!")
            return True
        else:
            logging.error("Authentication failed: Could not obtain authorization token.")
            return False

    def set_host(self, host: str):
        if not host:
            raise ValueError("Host cannot be empty")
        self.host = host
        self.update_user_data_file("host", host)
        logging.info(f"Host set: {host}")

    def set_auth(self, auth: str, email: str = None):
        if not auth:
            raise ValueError("Auth token cannot be empty")
        self.auth = auth
        self._set_credential_in_keyring("authorization_token", auth)
        if email:
            self.email = email
            self._set_credential_in_keyring("email", email)
        logging.info(f"Auth token set: {auth[:15]}...")
        if email:
            logging.info(f"Email stored: {email}")

    def set_region(self, region: str):
        if not region:
            raise ValueError("Region cannot be empty")
        self.module = region
        self.update_user_data_file("region", region)
        logging.info(f"Region set: {region}")

    def set_endpoint(self, endpoint: str = "subscribe"):
        if not endpoint:
            raise ValueError("Endpoint cannot be empty")
        self.endpoint = endpoint
        logging.info(f"Endpoint set: {endpoint}")

    def set_websocket_uri(self):
        if not self.host or not self.module or not self.endpoint:
            raise ValueError("Host, module, and endpoint must be set before building WebSocket URI.")
        if not self.auth:
            raise RuntimeError("Authorization token is not set. Authenticate first.")
        self.ws_uri = self.uri.format(scheme="wss", host=self.host, module=self.module, endpoint=self.endpoint)
        self.headers = {"Authorization": self.auth}
        logging.info(f"WebSocket URI set: {self.ws_uri}")

    def diagnose_connection_issues(self):
        """Comprehensive connection diagnostics."""
        logging.info("=== Connection Diagnostics ===")

        # Check internet connectivity
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=5)
            logging.info("Internet connectivity: OK")
        except Exception as e:
            logging.error(f"Internet connectivity: FAILED - {e}")
            return False

        # Check DNS resolution
        try:
            ip = socket.gethostbyname(self.host)
            logging.info(f"DNS resolution: {self.host} -> {ip}")
        except Exception as e:
            logging.error(f"DNS resolution failed for {self.host}: {e}")
            return False

        # Check HTTP/HTTPS connectivity to the host
        try:
            response = requests.get(f"https://api.bitcraftonline.com/status-get", timeout=10)
            logging.info(f"HTTPS connectivity: {response.status_code}")
        except Exception as e:
            logging.warning(f"HTTPS connectivity test failed: {e}")

        return self.test_server_connectivity()

    def test_server_connectivity(self):
        """Test basic connectivity to the server before attempting WebSocket connection."""

        try:
            # Parse host from ws_uri or use self.host
            host = self.host
            port = 443

            logging.info(f"Testing connectivity to {host}:{port}...")

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                logging.info(f"Successfully connected to {host}:{port}")
                return True
            else:
                logging.error(f"Failed to connect to {host}:{port} (error code: {result})")
                return False

        except socket.gaierror as e:
            logging.error(f"DNS resolution failed for {host}: {e}")
            return False
        except Exception as e:
            logging.error(f"Connectivity test failed: {e}")
            return False

    def connect_websocket_with_retry(self, max_retries=3, base_delay=1.0):
        """Connect to WebSocket with retry logic and exponential backoff."""
        for attempt in range(max_retries):
            try:
                logging.info(f"WebSocket connection attempt {attempt + 1}/{max_retries}")
                self.connect_websocket()
                return

            except Exception as e:
                if attempt == max_retries - 1:
                    logging.error(f"All {max_retries} connection attempts failed")
                    raise

                # Calculate delay with exponential backoff
                delay = base_delay * (2**attempt)
                logging.warning(f"Connection attempt {attempt + 1} failed: {e}")
                logging.info(f"Retrying in {delay} seconds...")

                time.sleep(delay)

    def connect_websocket(self):
        with self.ws_lock:
            if not self.ws_uri:
                raise RuntimeError("WebSocket URI is not set. Call set_websocket_uri() first.")
            if self.ws_connection:
                logging.info("WebSocket connection already exists. Reusing existing connection.")
                return
            try:
                logging.info(f"Attempting to connect to: {self.ws_uri}")
                logging.info(f"Using subprotocol: {self.proto}")
                logging.info(f"Additional headers: {self.headers}")

                # Configure connection with explicit timeouts and error handling
                self.ws_connection = connect(
                    self.ws_uri,
                    additional_headers=self.headers,
                    subprotocols=[self.proto],
                    max_size=None,
                    max_queue=None,
                )

                # Try to receive the first message with a timeout
                try:
                    first_msg = self.ws_connection.recv(timeout=10.0)
                    logging.info(f"Initial WebSocket handshake message: {first_msg[:20]}...")
                    logging.info("WebSocket connection established successfully")
                except TimeoutError:
                    logging.warning("Timeout waiting for initial handshake message, but connection may be valid")

            except Exception as e:
                logging.error(f"Failed to establish WebSocket connection: {e}")
                logging.error(f"Connection details - URI: {self.ws_uri}")
                logging.error(f"Connection details - Headers: {self.headers}")

                # Provide more specific error messages
                error_msg = str(e).lower()
                if "timeout" in error_msg or "timed out" in error_msg:
                    logging.error("Connection timed out. Possible causes:")
                    logging.error("  1. Server is down or unreachable")
                    logging.error("  2. Network/firewall blocking the connection")
                    logging.error("  3. DNS resolution issues")
                elif "connection refused" in error_msg:
                    logging.error("Connection refused. The server may be down.")
                elif "name or service not known" in error_msg or "getaddrinfo failed" in error_msg:
                    logging.error("DNS resolution failed. Check your internet connection.")
                elif "ssl" in error_msg or "certificate" in error_msg:
                    logging.error("SSL/TLS error. Check server certificate or try different connection settings.")

                self.ws_connection = None
                raise

    def close_websocket(self):
        """Enhanced WebSocket closing with timeout handling."""
        logging.info("Closing WebSocket connection...")

        try:
            with self.ws_lock:
                self._stop_subscription.set()

                # Wait for subscription thread with timeout
                if self.subscription_thread and self.subscription_thread.is_alive():
                    logging.info("Waiting for subscription thread to finish...")
                    self.subscription_thread.join(timeout=1.0)  # 1 second timeout

                    if self.subscription_thread.is_alive():
                        logging.warning("Subscription thread did not finish within timeout")

                # Close WebSocket connection
                if self.ws_connection:
                    try:
                        self.ws_connection.close()
                        logging.info("WebSocket connection closed")
                    except Exception as e:
                        logging.warning(f"Error closing WebSocket: {e}")
                    finally:
                        self.ws_connection = None
                else:
                    logging.info("No WebSocket connection to close")

        except Exception as e:
            logging.error(f"Error in close_websocket: {e}")

    def start_subscription_listener(self, queries: list[str], callback: callable):
        """
        Sends a subscription request and starts the background listener thread.
        Replaces any existing subscriptions.
        """
        with self.ws_lock:
            if not self.ws_connection:
                raise RuntimeError("WebSocket connection is not established.")
            if not queries:
                logging.warning("No queries provided for subscription.")
                return

            # Stop existing subscription thread if running but don't send unsubscribe
            if self.subscription_thread and self.subscription_thread.is_alive():
                logging.info("Stopping existing subscription thread...")
                self._stop_subscription.set()
                self.subscription_thread.join(timeout=1.0)

            self._stop_subscription.clear()

            # Send new subscription request (this should replace any existing subscriptions)
            subscribe_message = {"Subscribe": {"request_id": 1, "query_strings": queries}}
            self.ws_connection.send(json.dumps(subscribe_message))
            logging.info(f"Sent subscription request for {len(queries)} queries (replaces any existing subscriptions).")

            # Start the listener thread that will call the callback
            self.subscription_thread = threading.Thread(
                target=self._listen_for_subscription_updates,
                args=(callback,),
                daemon=True,
            )
            self.subscription_thread.start()
            logging.info("Subscription listener thread started.")

    def stop_subscriptions(self):
        """
        Stops current subscriptions without closing the WebSocket connection.
        """
        with self.ws_lock:
            if not self.ws_connection:
                logging.warning("No WebSocket connection to stop subscriptions on.")
                return

            try:
                # Just stop the subscription listener thread, don't send unsubscribe message
                logging.info("Stopping subscription thread...")

                # Stop the subscription listener thread
                self._stop_subscription.set()

                # Wait for subscription thread to finish
                if self.subscription_thread and self.subscription_thread.is_alive():
                    logging.info("Waiting for subscription thread to finish...")
                    self.subscription_thread.join(timeout=2.0)

                    if self.subscription_thread.is_alive():
                        logging.warning("Subscription thread did not finish within timeout")

                self.subscription_thread = None
                logging.info("Subscriptions stopped successfully.")

            except Exception as e:
                logging.error(f"Error stopping subscriptions: {e}")
                raise

    def _listen_for_subscription_updates(self, callback):
        """A dedicated loop for listening to subscription messages."""
        logging.info("Subscription listener thread started.")
        try:
            while not self._stop_subscription.is_set():
                if not self.ws_connection:
                    logging.warning("Subscription listener: WebSocket connection is closed.")
                    break
                try:
                    # Use a timeout to allow the loop to check the stop event
                    msg = self.ws_connection.recv(timeout=1.0)
                    data = json.loads(msg)

                    # Log WebSocket message types for connection diagnostics
                    message_type = list(data.keys())[0] if data else "unknown"
                    logging.debug(f"[BitCraftClient] Received WebSocket message type: {message_type}")

                    # Add detailed logging for specific message types
                    if "TransactionUpdate" in data:
                        reducer_name = data.get("TransactionUpdate", {}).get("reducer_call", {}).get("reducer_name", "unknown")
                        status_keys = list(data.get("TransactionUpdate", {}).get("status", {}).keys())
                        logging.debug(f"[BitCraftClient] TransactionUpdate - Reducer: {reducer_name}, Status: {status_keys}")

                    # Call the DataService callback with the message
                    callback(data)

                except TimeoutError:
                    continue  # No message received, loop again
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to decode JSON from subscription message: {e}")
                except Exception as e:
                    # Handle connection drops or other errors
                    logging.error(f"Error in subscription listener: {e}")
                    break
        finally:
            logging.info("Subscription listener thread stopped.")

    def logout(self):
        try:
            self.close_websocket()
            self._delete_credential_from_keyring("authorization_token")
            self._delete_credential_from_keyring("email")
            self.auth = None
            self.email = None
            logging.info("Successfully logged out. All credentials cleared.")
            return True
        except Exception as e:
            logging.error(f"Error during logout: {e}")
            return False
