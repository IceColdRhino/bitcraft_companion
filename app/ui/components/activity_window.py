import logging
import os
import re
from datetime import datetime
from typing import Dict, List

import customtkinter as ctk

from app.core.data_paths import get_user_data_path


class ActivityWindow(ctk.CTkToplevel):
    """Popup window displaying recent inventory changes and activity."""

    def __init__(self, parent):
        super().__init__(parent)
        
        self.parent = parent
        self.activity_entries: List[Dict] = []
        self.max_entries = 50  
        self.activity_log_file = None  
        
        self._setup_window()
        self._create_widgets()
        self._setup_activity_log_file()
        self._load_existing_log()

    def _setup_window(self):
        """Configure the activity window."""
        self.title("BitCraft Companion - Activity Log")
        self.geometry("600x400")
        self.minsize(400, 300)
        
        # Center the window on the parent
        self.transient(self.parent)
        
        # Configure grid weights
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Set icon if parent has one
        try:
            if hasattr(self.parent, 'iconbitmap'):
                self.iconbitmap(self.parent.winfo_toplevel().iconbitmap())
        except:
            pass

    def _create_widgets(self):
        """Create the activity window UI components."""
        # Header frame
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header_frame.grid_columnconfigure(0, weight=1)
        
        # Title (removed emoji)
        title_label = ctk.CTkLabel(
            header_frame,
            text="Recent Activity",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w"
        )
        title_label.grid(row=0, column=0, sticky="w")
        
        # Controls frame
        controls_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        controls_frame.grid(row=0, column=1, sticky="e")
        
        # Clear button
        self.clear_button = ctk.CTkButton(
            controls_frame,
            text="Clear All",
            width=80,
            height=30,
            font=ctk.CTkFont(size=11),
            command=self.clear_log,
            fg_color="#D32F2F",
            hover_color="#B71C1C"
        )
        self.clear_button.grid(row=0, column=0)

        # Main content frame
        content_frame = ctk.CTkFrame(self)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)

        # Scrollable text area for activity log
        self.log_textbox = ctk.CTkTextbox(
            content_frame,
            font=ctk.CTkFont(size=11, family="Consolas"),
            wrap="word"
        )
        self.log_textbox.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        
        # Make textbox read-only
        self.log_textbox.configure(state="disabled")
        
        # Initialize with empty state
        self._refresh_display()

    def add_inventory_change(self, item_name: str, previous_qty: int, new_qty: int, change: int, player_name: str = None):
        """Add an inventory change entry to the activity log."""
        timestamp = datetime.now().strftime("%I:%M:%S %p")
        
        if change > 0:
            action_text = f"+{change}"
        else:
            action_text = f"{change}"  # change is already negative
        
        # Include player name in the message if available
        if player_name:
            message = f"{timestamp} [{player_name}] {item_name}: {previous_qty} → {new_qty} ({action_text})"
        else:
            message = f"{timestamp} {item_name}: {previous_qty} → {new_qty} ({action_text})"
        
        entry = {
            "timestamp": timestamp,
            "type": "inventory_change",
            "item_name": item_name,
            "player_name": player_name,
            "message": message
        }
        
        self._add_entry(entry)

    def add_general_activity(self, message: str):
        """Add a general activity entry to the activity log."""
        timestamp = datetime.now().strftime("%I:%M:%S %p")
        
        entry = {
            "timestamp": timestamp,
            "type": "general",
            "message": f"{timestamp} {message}"
        }
        
        self._add_entry(entry)

    def _add_entry(self, entry: Dict):
        """Add an entry to the activity log and update display."""
        self.activity_entries.append(entry)
        
        # Keep only the most recent entries
        if len(self.activity_entries) > self.max_entries:
            self.activity_entries = self.activity_entries[-self.max_entries:]
        
        # Save to file automatically
        self._append_to_log_file(entry)
        
        self._refresh_display()

    def _setup_activity_log_file(self):
        """Set up the activity log file path using the same directory as player_data.json."""
        try:
            # Use the same directory structure as player_data.json
            self.activity_log_file = get_user_data_path("activity.log")
            logging.debug(f"Activity log file set to: {self.activity_log_file}")
            
        except Exception as e:
            logging.error(f"Error setting up activity log file: {e}")
            self.activity_log_file = None

    def _load_existing_log(self):
        """Load the last 50 lines from existing activity.log file."""
        if not self.activity_log_file or not os.path.exists(self.activity_log_file):
            logging.debug("No existing activity log file found")
            return
        
        try:
            with open(self.activity_log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Get last 50 lines (excluding header comments and empty lines)
            recent_lines = [line.strip() for line in lines[-50:] if line.strip() and not line.startswith('#')]
            logging.debug(f"Found {len(lines)} total lines, {len(recent_lines)} recent non-comment lines to process")
            
            # Parse lines back into entries
            loaded_count = 0
            for line in recent_lines:
                # Expected format: "HH:MM:SS AM/PM Item Name: oldqty → newqty (+/-change)"
                # Or fallback for any format - just load as-is
                try:
                    logging.debug(f"Processing log line: {line}")
                    
                    # Try to extract timestamp (look for time pattern)
                    timestamp = "Unknown"
                    
                    # Look for AM or PM pattern to extract timestamp
                    time_pattern = r'(\d{1,2}:\d{2}:\d{2}\s+(AM|PM))'
                    time_match = re.search(time_pattern, line)
                    
                    if time_match:
                        timestamp = time_match.group(1)
                        logging.debug(f"Extracted timestamp: {timestamp}")
                    else:
                        logging.debug(f"No timestamp pattern found in line: {line[:30]}...")
                    
                    entry = {
                        "timestamp": timestamp,
                        "type": "loaded",
                        "message": line
                    }
                    self.activity_entries.append(entry)
                    loaded_count += 1
                    logging.debug(f"Successfully loaded entry {loaded_count}: {line[:50]}...")
                        
                except Exception as parse_error:
                    logging.warning(f"Failed to parse log line: {line[:50]}... Error: {parse_error}")
                    # Still add it as a simple entry
                    entry = {
                        "timestamp": "Unknown",
                        "type": "loaded",
                        "message": line
                    }
                    self.activity_entries.append(entry)
                    loaded_count += 1
            
            # Keep only max_entries
            if len(self.activity_entries) > self.max_entries:
                self.activity_entries = self.activity_entries[-self.max_entries:]
                
            logging.info(f"Loaded {loaded_count} entries from existing activity log file: {self.activity_log_file}")
            
            # Refresh display to show loaded entries
            if loaded_count > 0:
                self._refresh_display()
            
        except Exception as e:
            logging.error(f"Error loading existing activity log: {e}")

    def _append_to_log_file(self, entry: Dict):
        """Append a single entry to the activity log file with rotation."""
        if not self.activity_log_file:
            return
        
        try:
            # Directory is automatically created by get_user_data_path system
            # Check if log rotation is needed
            self._rotate_log_if_needed()
            
            # Append entry to file
            with open(self.activity_log_file, 'a', encoding='utf-8') as f:
                f.write(entry["message"] + "\n")
                
        except Exception as e:
            logging.error(f"Error appending to activity log file: {e}")

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
                
                # Create new log file with header
                with open(self.activity_log_file, 'w', encoding='utf-8') as f:
                    f.write(f"# BitCraft Companion Activity Log\n")
                    f.write(f"# Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"# Previous log rotated to: {os.path.basename(backup_file)}\n\n")
                
                logging.info(f"Created new activity log file: {self.activity_log_file}")
                
        except Exception as e:
            logging.error(f"Error rotating activity log file: {e}")

    def _refresh_display(self):
        """Refresh the activity log display."""
        try:
            self.log_textbox.configure(state="normal")
            self.log_textbox.delete("1.0", "end")
            
            if not self.activity_entries:
                self.log_textbox.insert("end", "No recent activity.\n\nInventory changes will appear here automatically when detected.")
                logging.debug("Activity window display refreshed - no entries to show")
            else:
                # Show most recent entries first
                for entry in reversed(self.activity_entries):
                    self.log_textbox.insert("end", entry["message"] + "\n")
                logging.debug(f"Activity window display refreshed - showing {len(self.activity_entries)} entries")
            
            self.log_textbox.configure(state="disabled")
            
            # Scroll to top to show most recent
            self.log_textbox.see("1.0")
            
        except Exception as e:
            logging.error(f"Error refreshing activity log display: {e}")

    def clear_log(self):
        """Clear all activity log entries and log files."""
        self.activity_entries = []
        self._refresh_display()
        
        # Also clear the log files
        self._clear_log_files()
        
        logging.info("Activity log and files cleared by user")

    def _clear_log_files(self):
        """Clear the activity log files."""
        if not self.activity_log_file:
            return
        
        try:
            # Remove current log file
            if os.path.exists(self.activity_log_file):
                os.remove(self.activity_log_file)
                logging.info(f"Removed activity log file: {self.activity_log_file}")
            
            # Remove backup log file
            backup_file = self.activity_log_file + ".1"
            if os.path.exists(backup_file):
                os.remove(backup_file)
                logging.info(f"Removed activity log backup: {backup_file}")
                
        except Exception as e:
            logging.error(f"Error clearing activity log files: {e}")

    def update_claim_info(self, claim_name: str):
        """Update the displayed claim information (removed - no longer showing claim info)."""
        # Claim info display removed per user request
        pass

    def clear_on_claim_switch(self):
        """Clear activity log when switching claims."""
        self.activity_entries = []
        self.add_general_activity("Switched to new claim - activity log cleared")