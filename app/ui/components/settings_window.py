import json
import logging
import os
import sys
import toml
import webbrowser

import customtkinter as ctk
from tkinter import messagebox

from ...core.data_paths import get_user_data_path
from app.services.notification_service import NotificationService
from app.ui.themes import get_theme_manager, get_theme_names, get_theme_info, get_color, register_theme_callback


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.parent = parent

        # Window configuration - narrower and taller
        self.title("Settings")
        self.geometry("450x500")
        self.resizable(False, False)

        # Make window modal and stay on top
        self.transient(parent)
        self.grab_set()
        self.attributes("-topmost", True)

        # Center on parent window
        self._center_on_parent()

        # Handle window closing
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Load current settings
        self.settings = self._load_settings()

        # Initialize notification service for test notifications
        self.notification_service = NotificationService(self.app)

        # Get version information
        self.version_info = self._get_version_info()

        # Store UI component references for theme updates
        self.card_frames = []
        self.ui_components = {}

        # Register for theme change notifications
        register_theme_callback(self._on_theme_changed)

        # Apply current theme
        self.configure(fg_color=get_color("BACKGROUND_PRIMARY"))

        # Create UI
        self._create_widgets()

        logging.info("Settings window opened")

    def _center_on_parent(self):
        """Center the settings window on the parent window."""
        try:
            self.update_idletasks()

            # Get parent window position and size
            parent_x = self.parent.winfo_x()
            parent_y = self.parent.winfo_y()
            parent_width = self.parent.winfo_width()
            parent_height = self.parent.winfo_height()

            # Get our window size
            window_width = 450
            window_height = 500

            # Calculate center position
            x = parent_x + (parent_width - window_width) // 2
            y = parent_y + (parent_height - window_height) // 2

            self.geometry(f"{window_width}x{window_height}+{x}+{y}")

        except Exception as e:
            logging.error(f"Error centering settings window: {e}")

    def _get_version_info(self):
        """Get version information from pyproject.toml."""
        try:
            # Try to read from pyproject.toml
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            toml_path = os.path.join(project_root, "pyproject.toml")

            if os.path.exists(toml_path):
                with open(toml_path, "r", encoding="utf-8") as f:
                    data = toml.load(f)
                    return data.get("tool", {}).get("poetry", {}).get("version", "Unknown")
            else:
                return "Development Build"

        except Exception as e:
            logging.error(f"Error reading version info: {e}")
            return "Unknown"

    def _create_card_section(self, parent, title):
        """Create a card-style section container."""
        # Create card container with background and border
        card_frame = ctk.CTkFrame(
            parent,
            fg_color=get_color("BACKGROUND_SECONDARY"),
            corner_radius=8,
            border_width=1,
            border_color=get_color("BORDER_DEFAULT"),
        )
        card_frame.pack(fill="x", pady=(0, 15), padx=10)

        # Store reference for theme updates
        self.card_frames.append(card_frame)

        # Card content with proper padding
        content_frame = ctk.CTkFrame(card_frame, fg_color="transparent")
        content_frame.pack(fill="x", padx=15, pady=15)

        # Section header inside card
        header_label = ctk.CTkLabel(content_frame, text=title, font=ctk.CTkFont(size=14, weight="bold"), anchor="w")
        header_label.pack(anchor="w", pady=(0, 10))

        return content_frame

    def _create_widgets(self):
        """Create the settings interface with improved UX."""
        # Main scrollable container
        self.main_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Configure grid for left alignment
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Account Section
        account_content = self._create_card_section(self.main_frame, "Account")
        self._create_account_section(account_content)

        # Data Management Section
        data_content = self._create_card_section(self.main_frame, "Data Management")
        self._create_data_management_section(data_content)

        # Notifications Section
        notifications_content = self._create_card_section(self.main_frame, "Notifications")
        self._create_notifications_section(notifications_content)

        # Theme Section
        theme_content = self._create_card_section(self.main_frame, "Theme")
        self._create_theme_section(theme_content)

        # About Section
        about_content = self._create_card_section(self.main_frame, "About")
        self._create_about_section(about_content)

        # Close button at bottom
        self.close_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.close_frame.pack(fill="x", padx=20, pady=(10, 20))

        self.close_button = ctk.CTkButton(
            self.close_frame,
            text="Close",
            command=self._on_closing,
            width=100,
            height=32,
            fg_color=get_color("STATUS_INFO"),
            hover_color=get_color("BUTTON_HOVER"),
        )
        self.close_button.pack(side="right")

    def _create_account_section(self, parent):
        """Create the account management section."""
        # Logout button - fixed width, left aligned
        self.logout_button = ctk.CTkButton(
            parent,
            text="Logout",
            command=self._logout,
            width=200,
            height=36,
            anchor="w",
            fg_color=get_color("STATUS_ERROR"),
            hover_color=get_color("STATUS_ERROR"),
        )
        self.logout_button.pack(anchor="w", pady=(0, 8))

    def _create_data_management_section(self, parent):
        """Create the data management section."""
        # Refresh button - fixed width, left aligned
        self.refresh_button = ctk.CTkButton(
            parent,
            text="Refresh Data",
            command=self._refresh_data,
            width=200,
            height=36,
            anchor="w",
            fg_color=get_color("STATUS_INFO"),
            hover_color=get_color("BUTTON_HOVER"),
        )
        self.refresh_button.pack(anchor="w", pady=(0, 8))

        # Export button - fixed width, left aligned
        self.export_button = ctk.CTkButton(
            parent,
            text="Export Data",
            command=self._export_data,
            width=200,
            height=36,
            anchor="w",
            fg_color=get_color("STATUS_SUCCESS"),
            hover_color=get_color("STATUS_SUCCESS"),
        )
        self.export_button.pack(anchor="w", pady=(0, 8))

    def _create_notifications_section(self, parent):
        """Create the notifications section."""

        # Passive crafts toggle
        self.passive_crafts_var = ctk.BooleanVar(value=self.settings.get("notifications", {}).get("passive_crafts_enabled", True))
        passive_switch = ctk.CTkSwitch(
            parent,
            text="Passive Craft Notifications",
            variable=self.passive_crafts_var,
            command=self._on_setting_change,
            font=ctk.CTkFont(size=13),
        )
        passive_switch.pack(fill="x", anchor="w", pady=(0, 8))

        # Active crafts toggle
        self.active_crafts_var = ctk.BooleanVar(value=self.settings.get("notifications", {}).get("active_crafts_enabled", True))
        active_switch = ctk.CTkSwitch(
            parent,
            text="Active Craft Notifications",
            variable=self.active_crafts_var,
            command=self._on_setting_change,
            font=ctk.CTkFont(size=13),
        )
        active_switch.pack(fill="x", anchor="w", pady=(0, 15))

        # Test notification button (modular)
        if self.settings.get("debug", {}).get("show_test_notification", True):
            self.test_button = ctk.CTkButton(
                parent,
                text="Test Notification",
                command=self._test_notification,
                width=180,
                height=32,
                fg_color=get_color("STATUS_INFO"),
                hover_color=get_color("BUTTON_HOVER"),
            )
            self.test_button.pack(anchor="w", pady=(0, 8))

    def _create_theme_section(self, parent):
        """Create the theme selection section."""

        # Theme description
        desc_label = ctk.CTkLabel(
            parent,
            text="Choose your preferred color scheme and accessibility options:",
            font=ctk.CTkFont(size=12),
            text_color=("gray60", "gray40"),
            anchor="w",
        )
        desc_label.pack(fill="x", pady=(0, 10))

        # Get current theme and available themes
        theme_manager = get_theme_manager()
        current_theme = theme_manager.get_current_theme_name()
        available_themes = get_theme_names()

        # Theme selection dropdown
        self.theme_var = ctk.StringVar(value=current_theme)

        # Create readable theme names for display
        theme_display_names = []
        self.theme_name_mapping = {}

        for theme_name in available_themes:
            theme_info = get_theme_info(theme_name)
            display_name = theme_info["name"]
            theme_display_names.append(display_name)
            self.theme_name_mapping[display_name] = theme_name

        # Set current display value
        current_display_name = get_theme_info(current_theme)["name"]
        self.theme_var.set(current_display_name)

        theme_dropdown = ctk.CTkOptionMenu(
            parent,
            variable=self.theme_var,
            values=theme_display_names,
            command=self._on_theme_change,
            width=300,
            height=32,
            font=ctk.CTkFont(size=13),
        )
        theme_dropdown.pack(fill="x", pady=(0, 10))

    def _create_about_section(self, parent):
        """Create the about section with version and debug info."""

        # Version info
        version_label = ctk.CTkLabel(parent, text=f"Version: {self.version_info}", font=ctk.CTkFont(size=13), anchor="w")
        version_label.pack(fill="x", pady=(0, 5))

        # Developer link
        developer_label = ctk.CTkLabel(
            parent,
            text="Developer: https://github.com/Hatchet-Jackk",
            font=ctk.CTkFont(size=13),
            text_color=get_color("TEXT_ACCENT"),
            anchor="w",
            cursor="hand2",
        )
        developer_label.pack(fill="x", pady=(0, 15))
        developer_label.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/Hatchet-Jackk"))

        # Debug information header
        debug_header = ctk.CTkLabel(parent, text="Debug Information:", font=ctk.CTkFont(size=14, weight="bold"), anchor="w")
        debug_header.pack(fill="x", pady=(0, 5))

        # Get debug info from app
        debug_info = self._get_debug_info()

        # Player info
        player_label = ctk.CTkLabel(
            parent,
            text=f"Player: {debug_info.get('player', 'Unknown')}",
            font=ctk.CTkFont(size=12),
            text_color=("gray60", "gray40"),
            anchor="w",
        )
        player_label.pack(fill="x", pady=(0, 2))

        # Region info
        region_label = ctk.CTkLabel(
            parent,
            text=f"Region: {debug_info.get('region', 'Unknown')}",
            font=ctk.CTkFont(size=12),
            text_color=("gray60", "gray40"),
            anchor="w",
        )
        region_label.pack(fill="x", pady=(0, 2))

        # Claims info
        claims_label = ctk.CTkLabel(
            parent,
            text=f"Claims loaded: {debug_info.get('claims_count', 0)}",
            font=ctk.CTkFont(size=12),
            text_color=("gray60", "gray40"),
            anchor="w",
        )
        claims_label.pack(fill="x", pady=(0, 2))

    def _get_debug_info(self):
        """Get debug information from the app."""
        try:
            debug_info = {}

            # Get player name
            if hasattr(self.app, "data_service") and self.app.data_service:
                client = self.app.data_service.client
                debug_info["player"] = getattr(client, "player_name", "Unknown")
                debug_info["region"] = getattr(client, "region", "Unknown")

            # Get claims count
            if hasattr(self.app, "claim_info") and self.app.claim_info:
                claims = getattr(self.app.claim_info, "available_claims", [])
                debug_info["claims_count"] = len(claims)
            else:
                debug_info["claims_count"] = 0

            return debug_info

        except Exception as e:
            logging.error(f"Error getting debug info: {e}")
            return {"player": "Error", "region": "Error", "claims_count": 0}

    def _load_settings(self):
        """Load settings with default values."""
        try:
            # Default settings structure
            default_settings = {
                "notifications": {
                    "passive_crafts_enabled": True,
                    "active_crafts_enabled": True,
                },
                "debug": {"show_test_notification": True},
            }

            # Load from player_data.json
            try:
                file_path = get_user_data_path("player_data.json")
                with open(file_path, "r") as f:
                    player_data = json.load(f)

                # Extract settings from player_data, merge with defaults
                saved_settings = player_data.get("settings", {})
                if saved_settings:
                    # Deep merge: update defaults with saved settings
                    for category, options in saved_settings.items():
                        if category in default_settings and isinstance(options, dict):
                            default_settings[category].update(options)
                        else:
                            default_settings[category] = options

                logging.info("Settings loaded from player_data.json")

            except FileNotFoundError:
                logging.info("No player_data.json found, using default settings")
            except json.JSONDecodeError:
                logging.warning("player_data.json is malformed, using default settings")
            except Exception as e:
                logging.error(f"Error reading player_data.json: {e}, using defaults")

            return default_settings

        except Exception as e:
            logging.error(f"Error loading settings: {e}")
            return {
                "notifications": {"passive_crafts_enabled": True, "active_crafts_enabled": True},
                "debug": {"show_test_notification": True},
            }

    def _save_settings(self):
        """Save settings to persistent storage."""
        try:
            # Update settings based on UI state (only if UI components exist)
            if hasattr(self, "passive_crafts_var") and hasattr(self, "active_crafts_var"):
                self.settings["notifications"]["passive_crafts_enabled"] = self.passive_crafts_var.get()
                self.settings["notifications"]["active_crafts_enabled"] = self.active_crafts_var.get()
            else:
                logging.warning("Settings UI components not yet initialized, skipping UI state update")

            # Send updated settings to notification service
            if (
                hasattr(self.app, "data_service")
                and self.app.data_service
                and hasattr(self.app.data_service, "notification_service")
            ):
                self.app.data_service.notification_service.update_settings(self.settings)
                logging.info(f"Settings sent to notification service: {self.settings['notifications']}")
            else:
                logging.warning("Could not access notification service to update settings")

            # Save to player_data.json
            try:
                file_path = get_user_data_path("player_data.json")

                # Load existing player data or create new
                player_data = {}
                try:
                    with open(file_path, "r") as f:
                        player_data = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    pass  # Start with empty dict if file doesn't exist or is corrupted

                # Update settings section
                player_data["settings"] = self.settings

                # Write back to file
                with open(file_path, "w") as f:
                    json.dump(player_data, f, indent=4)

                logging.info("Settings saved to player_data.json")

            except Exception as e:
                logging.error(f"Error saving to player_data.json: {e}")

        except Exception as e:
            logging.error(f"Error saving settings: {e}")

    def _on_setting_change(self):
        """Called when any setting changes."""
        self._save_settings()
        logging.info("Settings updated")

    def _on_theme_change(self, selected_display_name):
        """Handle theme selection change."""
        try:
            # Get the actual theme name from the display name
            theme_name = self.theme_name_mapping.get(selected_display_name)
            if not theme_name:
                logging.error(f"Invalid theme display name: {selected_display_name}")
                return

            # Apply the theme
            theme_manager = get_theme_manager()
            success = theme_manager.set_theme(theme_name)

            if success:
                logging.info(f"Theme changed to: {theme_name}")
            else:
                logging.warning(f"Failed to change theme to: {theme_name}")

        except Exception as e:
            logging.error(f"Error changing theme: {e}")

    def _refresh_data(self):
        """Trigger comprehensive data refresh (reference data + current claim data)."""
        try:
            # Disable button during refresh
            self.refresh_button.configure(state="disabled", text="Refreshing...")

            # Request comprehensive data refresh from the data service
            logging.info("[Settings] Refresh data button clicked - starting comprehensive refresh process")
            if hasattr(self.app, "data_service") and self.app.data_service:
                logging.debug("[Settings] DataService found - calling refresh_all_data()")
                success = self.app.data_service.refresh_all_data()
                if success:
                    logging.info("[Settings] Comprehensive data refresh completed successfully")
                    # Show success message briefly
                    self.refresh_button.configure(text="Refreshed!")
                    self.after(1000, lambda: self.refresh_button.configure(state="normal", text="Refresh Data"))
                else:
                    logging.warning("[Settings] Comprehensive data refresh failed")
                    self.refresh_button.configure(text="Refresh failed")
                    self.after(2000, lambda: self.refresh_button.configure(state="normal", text="Refresh Data"))
            else:
                logging.error("[Settings] Data service not available for data refresh")
                self.refresh_button.configure(text="Service unavailable")
                self.after(2000, lambda: self.refresh_button.configure(state="normal", text="Refresh Data"))

        except Exception as e:
            logging.error(f"Error triggering data refresh: {e}")
            messagebox.showerror("Refresh Error", f"Failed to refresh data: {e}")
            # Re-enable button on error
            self.refresh_button.configure(state="normal", text="Refresh Data")

    def _export_data(self):
        """Trigger data export."""
        try:
            if hasattr(self.app, "claim_info") and self.app.claim_info:
                # Call the existing export method in the claim_info_header
                self.app.claim_info._export_data()
                logging.info("Data export triggered from settings")
            else:
                logging.error("Claim info not available for data export")
                messagebox.showerror("Export Error", "Unable to access claim information for export")

        except Exception as e:
            logging.error(f"Error triggering data export: {e}")
            messagebox.showerror("Export Error", f"Failed to export data: {e}")

    def _test_notification(self):
        """Show a test notification."""
        try:
            # Update notification service settings from UI (if UI components exist)
            if hasattr(self, "passive_crafts_var") and hasattr(self, "active_crafts_var"):
                notification_settings = {
                    "passive_crafts_enabled": self.passive_crafts_var.get(),
                    "active_crafts_enabled": self.active_crafts_var.get(),
                }
            else:
                # Use default settings if UI not initialized
                notification_settings = {
                    "passive_crafts_enabled": True,
                    "active_crafts_enabled": True,
                }
            self.notification_service.update_settings(notification_settings)

            # Show test notification
            self.notification_service.show_test_notification()
            logging.info("Test notification triggered from settings")

        except Exception as e:
            logging.error(f"Error showing test notification: {e}")
            messagebox.showerror("Test Error", f"Failed to show test notification: {e}")

    def _on_closing(self):
        """Handle window closing."""
        try:
            self._save_settings()
            self.destroy()
            logging.info("Settings window closed")

        except Exception as e:
            logging.error(f"Error closing settings window: {e}")
            self.destroy()

    def _logout(self):
        """Logs out the user with confirmation dialog."""
        try:
            # Show confirmation dialog
            result = messagebox.askyesno(
                "Confirm Logout",
                "Logging out will clear your stored credentials and you'll need to re-authenticate.\n\nAre you sure you want to continue?",
                icon="warning",
            )

            if not result:  # User clicked "No" or closed dialog
                logging.info("Logout cancelled by user")
                return

            # Perform logout
            logging.info("User initiated logout from settings window")

            if hasattr(self.app, "data_service") and self.app.data_service:
                # Clear credentials using the data service client
                if hasattr(self.app.data_service, "client"):
                    if self.app.data_service.client.logout():
                        messagebox.showinfo("Logout Successful", "You have been logged out. The application will now close.")
                        # Close the application
                        self._quit_application()
                    else:
                        messagebox.showerror("Logout Error", "Failed to logout. See logs for details.")
                else:
                    messagebox.showerror("Logout Error", "Unable to access authentication system.")
            else:
                messagebox.showerror("Logout Error", "Unable to access data service.")

        except Exception as e:
            logging.error(f"Error during logout: {e}")
            messagebox.showerror("Logout Error", f"An error occurred during logout:\n{str(e)}")

    def _quit_application(self):
        """Quits the application."""
        try:
            logging.info("User initiated application quit from settings window")

            # Close settings window first
            self.destroy()

            # Call the main window's closing method
            if hasattr(self.app, "on_closing"):
                self.app.on_closing()
            else:
                # Fallback: try to close the root window
                self.app.quit()

        except Exception as e:
            logging.error(f"Error quitting application: {e}")
            try:
                self.app.quit()
            except:
                sys.exit(0)

    def _on_theme_changed(self, old_theme: str, new_theme: str):
        """Handle theme change by updating colors."""
        try:
            # Update window background
            self.configure(fg_color=get_color("BACKGROUND_PRIMARY"))

            # Update main scrollable frame background (forces scrollbar refresh)
            if hasattr(self, "main_frame"):
                self.main_frame.configure(fg_color="transparent")

            # Update close frame background
            if hasattr(self, "close_frame"):
                self.close_frame.configure(fg_color="transparent")

            # Update all card frames
            for card_frame in self.card_frames:
                card_frame.configure(fg_color=get_color("BACKGROUND_SECONDARY"), border_color=get_color("BORDER_DEFAULT"))

            # Update all buttons with theme colors
            self.close_button.configure(fg_color=get_color("STATUS_INFO"), hover_color=get_color("BUTTON_HOVER"))

            self.logout_button.configure(fg_color=get_color("STATUS_ERROR"), hover_color=get_color("STATUS_ERROR"))

            self.refresh_button.configure(fg_color=get_color("STATUS_INFO"), hover_color=get_color("BUTTON_HOVER"))

            self.export_button.configure(fg_color=get_color("STATUS_SUCCESS"), hover_color=get_color("STATUS_SUCCESS"))

            if hasattr(self, "test_button"):
                self.test_button.configure(fg_color=get_color("STATUS_INFO"), hover_color=get_color("BUTTON_HOVER"))

            # Force a visual refresh of the entire window
            self.update_idletasks()

            logging.debug(f"Settings window theme changed from {old_theme} to {new_theme}")

        except Exception as e:
            logging.error(f"Error updating settings window theme: {e}")
