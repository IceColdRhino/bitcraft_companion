"""
Activity logging service for BitCraft Companion.

Provides background activity logging that works independently of the UI activity window.
This ensures inventory changes and other activities are always logged, even when the
activity window is not open.
"""

import logging
import os
from datetime import datetime
from typing import Dict, List

from ..core.data_paths import get_user_data_path


class ActivityLogger:
    """Background activity logging service."""

    def __init__(self):
        self.activity_log_file = None
        self.max_entries = 50
        self._setup_log_file()

    def _setup_log_file(self):
        """Set up the activity log file path."""
        try:
            self.activity_log_file = get_user_data_path("activity.log")
            logging.debug(f"Activity logger file set to: {self.activity_log_file}")
        except Exception as e:
            logging.error(f"Error setting up activity log file: {e}")
            self.activity_log_file = None

    def log_inventory_change(self, item_name: str, previous_qty: int, new_qty: int, change: int, player_name: str = None):
        """Log an inventory change to the activity log."""
        timestamp = datetime.now().strftime("%I:%M:%S %p")

        if change > 0:
            action_text = f"+{change}"
        else:
            action_text = f"{change}"  # change is already negative

        # Include player name in the message if available
        if player_name:
            message = f"{timestamp} [{player_name}] {item_name}: {previous_qty} -> {new_qty} ({action_text})"
        else:
            message = f"{timestamp} {item_name}: {previous_qty} -> {new_qty} ({action_text})"

        self._write_to_log(message)
        logging.debug(f"Activity logged: {message}")

    def log_general_activity(self, message: str):
        """Log a general activity message."""
        timestamp = datetime.now().strftime("%I:%M:%S %p")
        formatted_message = f"{timestamp} {message}"
        self._write_to_log(formatted_message)
        logging.debug(f"Activity logged: {formatted_message}")

    def _write_to_log(self, message: str):
        """Write a message to the activity log file."""
        if not self.activity_log_file:
            return

        try:
            # Check if log rotation is needed
            self._rotate_log_if_needed()

            # Append message to file
            with open(self.activity_log_file, "a", encoding="utf-8") as f:
                f.write(message + "\n")

        except Exception as e:
            logging.error(f"Error writing to activity log file: {e}")

    def _rotate_log_if_needed(self):
        """Rotate log file if it exceeds 5MB. Keep only current and 1 backup."""
        if not self.activity_log_file or not os.path.exists(self.activity_log_file):
            return

        try:
            # Check current file size
            file_size = os.path.getsize(self.activity_log_file)
            max_size = 5 * 1024 * 1024  # 5MB in bytes

            if file_size >= max_size:
                # Create backup filename
                backup_file = self.activity_log_file + ".1"

                # Remove old backup if it exists (keep only 2 files total)
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                    logging.info(f"Removed old activity log backup: {backup_file}")

                # Move current file to backup
                os.rename(self.activity_log_file, backup_file)
                logging.info(f"Rotated activity log: {self.activity_log_file} -> {backup_file}")

        except Exception as e:
            logging.error(f"Error rotating activity log: {e}")

    def get_recent_entries(self, max_entries: int = None) -> List[str]:
        """Get recent entries from the activity log file."""
        if max_entries is None:
            max_entries = self.max_entries

        if not self.activity_log_file or not os.path.exists(self.activity_log_file):
            return []

        try:
            with open(self.activity_log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # Return last N lines, stripped of newlines
                return [line.rstrip("\n") for line in lines[-max_entries:]]
        except Exception as e:
            logging.error(f"Error reading activity log: {e}")
            return []
