import json
import logging
import time
from typing import Dict, Optional

from app.core.processors.base_processor import BaseProcessor
from app.models.object_dataclasses import StaminaState, CharacterStatsState


class StaminaProcessor(BaseProcessor):
    """Processor for handling stamina_state and character_stats_state data."""

    def __init__(self, data_queue, services, reference_data):
        super().__init__(data_queue, services, reference_data)

        self._previous_stamina: Dict[int, float] = {}
        self._character_stats: Dict[int, CharacterStatsState] = {}
        self._current_activity_status: Dict[int, str] = {}
        self._last_status_change: Dict[int, float] = {}
        self._persistent_max_stamina: Dict[int, float] = {}

        # Track if stamina has decreased at least once to allow notifications
        self._stamina_has_decreased = False
        self._initial_subscription_received = False

    def get_table_names(self):
        """Return the table names this processor handles."""
        return ["stamina_state", "character_stats_state"]

    def _show_stamina_notification(self, title: str, message: str):
        """Show a stamina notification using the notification service."""
        try:
            data_service = self.services.get("data_service")
            if data_service and hasattr(data_service, "notification_service") and data_service.notification_service:
                data_service.notification_service.show_stamina_notification(title, message)
        except Exception as e:
            logging.error(f"Error showing stamina notification: {e}")

    def process_transaction(self, table_update, reducer_name, timestamp):
        """Process transaction updates for stamina and character stats."""
        table_name = table_update.get("table_name")

        if table_name == "stamina_state":
            self._process_stamina_transaction(table_update, reducer_name, timestamp)
        elif table_name == "character_stats_state":
            self._process_character_stats_transaction(table_update, reducer_name, timestamp)

    def process_subscription(self, table_update):
        """Process subscription updates for stamina and character stats."""
        table_name = table_update.get("table_name")

        if table_name == "stamina_state":
            self._process_stamina_subscription(table_update)
        elif table_name == "character_stats_state":
            self._process_character_stats_subscription(table_update)

    def _process_stamina_transaction(self, table_update, reducer_name, timestamp):
        """Process stamina state transaction updates using UPSERT pattern."""
        updates = table_update.get("updates", [])

        for update in updates:
            inserts = update.get("inserts", [])
            deletes = update.get("deletes", [])

            delete_operations = {}
            insert_operations = {}

            for delete in deletes:
                try:
                    if isinstance(delete, str):
                        data = json.loads(delete)
                    else:
                        data = delete

                    if isinstance(data, list) and len(data) > 0:
                        player_entity_id = data[0]
                        delete_operations[player_entity_id] = data
                except Exception as e:
                    logging.error(f"Error parsing stamina transaction delete: {e}")

            for insert in inserts:
                try:
                    if isinstance(insert, str):
                        data = json.loads(insert)
                    else:
                        data = insert

                    stamina_state = StaminaState.from_array(data)
                    player_entity_id = stamina_state.player_entity_id
                    insert_operations[player_entity_id] = stamina_state
                except Exception as e:
                    logging.error(f"Error parsing stamina transaction insert: {e}")

            for player_entity_id, stamina_state in insert_operations.items():
                self._update_stamina_state(stamina_state, timestamp)

            for player_entity_id in delete_operations:
                if player_entity_id not in insert_operations:
                    self._cleanup_player_data(player_entity_id)

        total_inserts = sum(len(update.get("inserts", [])) for update in updates)
        total_deletes = sum(len(update.get("deletes", [])) for update in updates)
        self._log_transaction_debug("stamina_state", total_inserts, total_deletes, reducer_name)

    def _process_stamina_subscription(self, table_update):
        """Process stamina state subscription updates."""
        updates = table_update.get("updates", [])
        current_time = time.time()
        stamina_records_processed = 0

        for update in updates:
            inserts = update.get("inserts", [])

            for insert in inserts:
                try:
                    if isinstance(insert, str):
                        data = json.loads(insert)
                    else:
                        data = insert

                    stamina_state = StaminaState.from_dict(data)
                    self._update_stamina_state(stamina_state, current_time)
                    stamina_records_processed += 1

                    # Mark that initial subscription has been received
                    self._initial_subscription_received = True

                except Exception as e:
                    logging.error(f"Error processing stamina subscription insert: {e}")

        if stamina_records_processed == 0:
            self._queue_update(
                "activity_status",
                {
                    "player_entity_id": None,
                    "status": "Offline",
                    "stamina_current": 0,
                    "stamina_max": 0,
                    "stamina_percentage": 0.0,
                    "timestamp": current_time,
                },
            )

    def _process_character_stats_transaction(self, table_update, reducer_name, timestamp):
        """Process character stats transaction updates."""
        updates = table_update.get("updates", [])
        total_inserts = 0
        total_deletes = 0

        for update in updates:
            inserts = update.get("inserts", [])
            deletes = update.get("deletes", [])

            for insert in inserts:
                try:
                    if isinstance(insert, str):
                        data = json.loads(insert)
                    else:
                        data = insert

                    stats_state = CharacterStatsState.from_array(data)
                    self._character_stats[stats_state.player_entity_id] = stats_state
                    total_inserts += 1

                    max_stamina = stats_state.get_max_stamina()
                    player_id = stats_state.player_entity_id
                    old_max_stamina = self._persistent_max_stamina.get(player_id, 0)
                    max_stamina_changed = abs(old_max_stamina - max_stamina) > 0.01

                    self._persistent_max_stamina[player_id] = max_stamina

                    if max_stamina_changed and player_id in self._previous_stamina:
                        latest_stamina = self._previous_stamina[player_id]
                        recent_stamina_state = StaminaState(
                            entity_id=player_id, stamina=latest_stamina, last_stamina_decrease_timestamp=0
                        )
                        self._update_stamina_state(recent_stamina_state, timestamp)

                except Exception as e:
                    logging.error(f"Error processing character stats transaction insert: {e}")

            for delete in deletes:
                try:
                    if isinstance(delete, str):
                        data = json.loads(delete)
                    else:
                        data = delete

                    player_entity_id = (
                        data.get("entity_id")
                        if isinstance(data, dict)
                        else delete[0] if isinstance(data, list) and data else None
                    )
                    if player_entity_id and player_entity_id in self._character_stats:
                        del self._character_stats[player_entity_id]
                        total_deletes += 1
                except Exception as e:
                    logging.error(f"Error processing character stats transaction delete: {e}")

        self._log_transaction_debug("character_stats_state", total_inserts, total_deletes, reducer_name)

    def _process_character_stats_subscription(self, table_update):
        """Process character stats subscription updates."""
        updates = table_update.get("updates", [])
        current_time = time.time()

        for update in updates:
            inserts = update.get("inserts", [])

            for insert in inserts:
                try:
                    if isinstance(insert, str):
                        data = json.loads(insert)
                    else:
                        data = insert

                    stats_state = CharacterStatsState.from_dict(data)
                    self._character_stats[stats_state.player_entity_id] = stats_state

                    max_stamina = stats_state.get_max_stamina()
                    player_id = stats_state.player_entity_id
                    self._persistent_max_stamina[player_id] = max_stamina

                    if player_id in self._previous_stamina:
                        latest_stamina = self._previous_stamina[player_id]
                        recent_stamina_state = StaminaState(
                            entity_id=player_id,
                            stamina=latest_stamina,
                            last_stamina_decrease_timestamp=0,
                        )
                        self._update_stamina_state(recent_stamina_state, current_time)

                except Exception as e:
                    logging.error(f"Error processing character stats subscription: {e}")

    def _update_stamina_state(self, stamina_state: StaminaState, timestamp: float):
        """Update stamina state and detect activity status changes."""
        player_id = stamina_state.player_entity_id
        current_stamina = stamina_state.stamina
        max_stamina = self._get_max_stamina_for_player(player_id)
        previous_stamina = self._previous_stamina.get(player_id)

        if current_stamina >= max_stamina:
            new_status = "Idle"
        elif previous_stamina is None:
            new_status = "Resting"
        elif current_stamina < previous_stamina:
            new_status = "Active"
        elif current_stamina > previous_stamina:
            new_status = "Resting"
        else:
            new_status = "Resting"

        self._previous_stamina[player_id] = current_stamina

        old_status = self._current_activity_status.get(player_id)
        status_changed = new_status != old_status

        # Track if stamina has decreased (from transaction updates, not initial subscription)
        if previous_stamina is not None and current_stamina < previous_stamina and self._initial_subscription_received:
            self._stamina_has_decreased = True

        self._current_activity_status[player_id] = new_status
        self._last_status_change[player_id] = timestamp

        self._queue_update(
            "activity_status",
            {
                "player_entity_id": player_id,
                "status": new_status,
                "stamina_current": current_stamina,
                "stamina_max": max_stamina,
                "stamina_percentage": stamina_state.get_percentage(max_stamina),
                "timestamp": timestamp,
                "last_decrease_timestamp": stamina_state.get_timestamp_seconds(),
            },
        )

        if status_changed and old_status == "Resting" and new_status == "Idle":
            # Only send notification if stamina has decreased at least once since initial load
            if self._stamina_has_decreased:
                self._show_stamina_notification("Stamina Recharged", "Your stamina is fully recharged and ready for action!")

    def _get_max_stamina_for_player(self, player_id: int) -> float:
        """Get max stamina for player from persistent storage, character stats cache, or use default."""
        if player_id in self._persistent_max_stamina:
            max_stamina = self._persistent_max_stamina[player_id]
            if max_stamina > 0:
                return float(max_stamina)

        if player_id in self._character_stats:
            stats = self._character_stats[player_id]
            max_stamina = stats.get_max_stamina()
            if max_stamina > 0:
                self._persistent_max_stamina[player_id] = max_stamina
                return float(max_stamina)

        return 300.0

    def _cleanup_player_data(self, player_entity_id: int):
        """Clean up data for a player that was removed."""
        self._previous_stamina.pop(player_entity_id, None)
        self._character_stats.pop(player_entity_id, None)
        self._current_activity_status.pop(player_entity_id, None)
        self._last_status_change.pop(player_entity_id, None)

    def get_player_activity_status(self, player_entity_id: int) -> Optional[str]:
        """Get current activity status for a player."""
        return self._current_activity_status.get(player_entity_id)

    def get_player_stamina_info(self, player_entity_id: int) -> Optional[dict]:
        """Get current stamina info for a player."""
        current_stamina = self._previous_stamina.get(player_entity_id)
        if current_stamina is None:
            return None

        max_stamina = self._get_max_stamina_for_player(player_entity_id)

        return {
            "player_entity_id": player_entity_id,
            "current": current_stamina,
            "max": max_stamina,
            "percentage": (current_stamina / max_stamina * 100.0) if max_stamina > 0 else 0.0,
            "status": self._current_activity_status.get(player_entity_id, "Unknown"),
            "last_update": time.time(),
        }

    def clear_cache(self):
        """Clear cached data when switching claims."""
        pass
