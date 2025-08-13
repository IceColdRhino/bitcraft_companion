import customtkinter as ctk
import logging
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import openpyxl
from openpyxl.styles import Font, Alignment
from datetime import datetime
import os
from app.ui.components.settings_window import SettingsWindow


class ClaimInfoHeader(ctk.CTkFrame):
    """
    Header widget displaying claim information including name, treasury, supplies,
    and time remaining until supplies are depleted based on tile count.
    """

    def __init__(self, master, app):
        super().__init__(master, fg_color="#1a1a1a", corner_radius=8)
        self.app = app

        # Add claim management attributes
        self.available_claims = []
        self.current_claim_id = None
        self.claim_switching = False

        # Initialize data
        self.claim_name = "Loading..."
        self.treasury = 0
        self.supplies = 0
        self.tile_count = 0
        self.supplies_per_hour = 0
        self.time_remaining = "Calculating..."
        self.traveler_tasks_expiration = None
        self.task_refresh_time = "Unknown"

        # Load tile cost data from the app's data service
        self.tile_cost_lookup = {}
        self._load_tile_cost_data()

        self._create_widgets()

    def _load_tile_cost_data(self):
        """Load claim tile cost data for supplies calculation."""
        try:
            if hasattr(self.app, "data_service") and self.app.data_service and hasattr(self.app.data_service, "client"):
                client = self.app.data_service.client
                tile_cost_data = client._load_reference_data("claim_tile_cost")

                if tile_cost_data:
                    # Create lookup table: tile_count -> cost_per_tile
                    for entry in tile_cost_data:
                        tile_count = entry.get("tile_count", 0)
                        cost_per_tile = entry.get("cost_per_tile", 0.0)
                        self.tile_cost_lookup[tile_count] = cost_per_tile
                    logging.info(f"Loaded {len(self.tile_cost_lookup)} tile cost entries")
                else:
                    logging.warning("No tile cost data found")
        except Exception as e:
            logging.error(f"Error loading tile cost data: {e}")
            self.tile_cost_lookup = {1: 0.01, 1001: 0.0125}  # fallback values

    def _calculate_supplies_per_hour(self, tile_count):
        """
        Calculate total supplies consumption per hour based on tile count and cost_per_tile.
        """
        if not tile_count or tile_count <= 0:
            return 0.0

        sorted_tile_counts = sorted(self.tile_cost_lookup.keys())
        if tile_count in self.tile_cost_lookup:
            cost_per_tile = self.tile_cost_lookup[tile_count]
        elif tile_count <= sorted_tile_counts[0]:
            cost_per_tile = self.tile_cost_lookup[sorted_tile_counts[0]]
        elif tile_count >= sorted_tile_counts[-1]:
            cost_per_tile = self.tile_cost_lookup[sorted_tile_counts[-1]]
        else:
            # Use the largest tile_count less than or equal to the current tile_count
            lower_tiles = max(t for t in sorted_tile_counts if t <= tile_count)
            cost_per_tile = self.tile_cost_lookup[lower_tiles]
        return tile_count * cost_per_tile

    def _create_widgets(self):
        """Creates and arranges the header widgets."""
        # Configure grid weights
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        # Left side - Claim information
        self._create_claim_info_section()

    def _create_claim_info_section(self):
        """Creates the left side claim information display with CTkOptionMenu dropdown."""
        claim_frame = ctk.CTkFrame(self, fg_color="transparent")
        claim_frame.grid(row=0, column=0, sticky="w", padx=15, pady=10)

        # Create frame for dropdown and refresh button
        dropdown_frame = ctk.CTkFrame(claim_frame, fg_color="transparent")
        dropdown_frame.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        # IMPROVED: Use CTkOptionMenu instead of custom dropdown
        self.claim_dropdown = ctk.CTkOptionMenu(
            dropdown_frame,
            values=["Loading..."],
            command=self._on_claim_selected,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ffffff",
            fg_color=("#2b2b2b", "#3a3a3a"),
            button_color=("#404040", "#505050"),
            button_hover_color=("#505050", "#606060"),
            dropdown_fg_color=("#2a2d2e", "#3a3a3a"),
            dropdown_hover_color=("#1f6aa5", "#2c7bc7"),
            dropdown_text_color="#ffffff",
            corner_radius=8,
            anchor="w",
            state="disabled",  # Start disabled
            height=40,
            width=300,
        )
        self.claim_dropdown.grid(row=0, column=0, sticky="w", padx=(0, 10))

        # Add settings button
        self.settings_button = ctk.CTkButton(
            dropdown_frame,
            text="Settings",
            width=100,
            height=40,
            font=ctk.CTkFont(size=12),
            command=self._open_settings,
            fg_color=("#404040", "#505050"),
            hover_color=("#5a5a5a", "#707070"),
            text_color="#ffffff",
            corner_radius=8,
            border_width=0,
        )
        self.settings_button.grid(row=0, column=1, sticky="w", padx=(2, 12))

        # Add tooltip to settings button
        self._add_tooltip(self.settings_button, "Open settings window to manage app preferences and data operations")

        # Add logout button
        self.logout_button = ctk.CTkButton(
            dropdown_frame,
            text="Logout",
            width=80,
            height=40,
            font=ctk.CTkFont(size=12),
            command=self._logout,
            fg_color=("#FF6B35", "#E55100"),
            hover_color=("#E55100", "#BF360C"),
            text_color="#ffffff",
            corner_radius=8,
        )
        self.logout_button.grid(row=0, column=2, sticky="w", padx=(0, 10))

        # Add quit button
        self.quit_button = ctk.CTkButton(
            dropdown_frame,
            text="Quit",
            width=70,
            height=40,
            font=ctk.CTkFont(size=12),
            command=self._quit_application,
            fg_color=("#D32F2F", "#B71C1C"),
            hover_color=("#B71C1C", "#8B0000"),
            text_color="#ffffff",
            corner_radius=8,
        )
        self.quit_button.grid(row=0, column=3, sticky="w")

        # Create info row with treasury, supplies, and supplies run out
        info_frame = ctk.CTkFrame(claim_frame, fg_color="transparent")
        info_frame.grid(row=1, column=0, sticky="w")

        # Treasury with icon
        treasury_frame = self._create_enhanced_info_item(info_frame, "💰 Treasury", "0", "#FFD700")
        treasury_frame.grid(row=0, column=0, padx=(0, 20))
        self.treasury_value_label = treasury_frame.winfo_children()[1]

        # Supplies with icon
        supplies_frame = self._create_enhanced_info_item(info_frame, "⚡ Supplies", "0", "#4CAF50")
        supplies_frame.grid(row=0, column=1, padx=(0, 20))
        self.supplies_value_label = supplies_frame.winfo_children()[1]

        # Supplies Run Out with icon
        supplies_runout_frame = self._create_enhanced_info_item(info_frame, "⏱️ Depletes In", "Calculating...", "#FF9800")
        supplies_runout_frame.grid(row=0, column=2, padx=(0, 20))
        self.supplies_runout_label = supplies_runout_frame.winfo_children()[1]

        # Add tooltip to supplies run out label
        self._add_tooltip(self.supplies_runout_label, "This value is approximate and may not exactly match in-game.")

        # Task Refresh with icon
        task_refresh_frame = self._create_enhanced_info_item(info_frame, "🔄 Task Refresh", "Unknown", "#9C27B0")
        task_refresh_frame.grid(row=0, column=3)
        self.task_refresh_label = task_refresh_frame.winfo_children()[1]

        # Add tooltip to task refresh label
        self._add_tooltip(self.task_refresh_label, "Time until traveler tasks refresh with new assignments.")

    def _create_enhanced_info_item(self, parent, label_text, value_text, color):
        """Creates an enhanced label-value pair with better styling."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")

        # Label with better styling
        label = ctk.CTkLabel(frame, text=label_text, font=ctk.CTkFont(size=11, weight="normal"), text_color="#b0b0b0")
        label.grid(row=0, column=0, sticky="w")

        # Value with enhanced styling
        value = ctk.CTkLabel(frame, text=value_text, font=ctk.CTkFont(size=14, weight="bold"), text_color=color)
        value.grid(row=1, column=0, sticky="w", pady=(2, 0))

        return frame

    def _add_tooltip(self, widget, text):
        """Adds a tooltip with delay to prevent hover interference."""
        tooltip = None
        tooltip_timer = None

        def show_tooltip():
            nonlocal tooltip
            if tooltip is None:  # Only create if not already created
                try:
                    # Position tooltip away from button edges to prevent interference
                    x = widget.winfo_rootx() + widget.winfo_width() // 2 - 50
                    y = widget.winfo_rooty() + widget.winfo_height() + 5

                    tooltip = tk.Toplevel(widget)
                    tooltip.wm_overrideredirect(True)
                    tooltip.wm_geometry(f"+{x}+{y}")

                    # Ensure tooltip doesn't capture mouse events
                    tooltip.attributes("-topmost", True)
                    tooltip.lift()

                    label = tk.Label(
                        tooltip,
                        text=text,
                        background="#333333",
                        foreground="#ffffff",
                        borderwidth=1,
                        relief="solid",
                        font=("Arial", 9),
                    )
                    label.pack(ipadx=6, ipady=3)
                except Exception:
                    # If tooltip creation fails, just ignore
                    pass

        def on_enter(event):
            nonlocal tooltip_timer
            # Cancel any existing timer
            if tooltip_timer:
                widget.after_cancel(tooltip_timer)
            # Show tooltip after delay to prevent immediate interference
            tooltip_timer = widget.after(400, show_tooltip)

        def on_leave(event):
            nonlocal tooltip, tooltip_timer
            # Cancel pending tooltip
            if tooltip_timer:
                widget.after_cancel(tooltip_timer)
                tooltip_timer = None
            # Destroy existing tooltip
            if tooltip:
                try:
                    tooltip.destroy()
                except Exception:
                    pass
                tooltip = None

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def _on_claim_selected(self, selected_claim_name: str):
        """
        Handles claim selection from the CTkOptionMenu dropdown.
        """
        if self.claim_switching:
            return

        # Find the claim ID from the selected name (handle both key formats)
        for claim in self.available_claims:
            claim_name = claim.get("claim_name") or claim.get("name")
            if claim_name == selected_claim_name:
                claim_id = claim.get("claim_id") or claim.get("entity_id")

                # Only switch if it's different from current
                if claim_id != self.current_claim_id:
                    logging.info(f"User selected claim: {selected_claim_name} ({claim_id})")

                    # Start claim switching
                    self.set_claim_switching(True, f"Switching to {selected_claim_name}...")

                    # Notify the main app to perform the switch
                    if hasattr(self.app, "switch_to_claim"):
                        self.app.switch_to_claim(claim_id)
                    else:
                        logging.error("Main app does not support claim switching")
                        self.set_claim_switching(False)
                break

    def update_claim_data(self, claim_data):
        """
        Updates the header with new claim information.
        """
        try:
            # Update stored values
            self.claim_name = claim_data.get("name", "Unknown Claim")
            self.treasury = claim_data.get("treasury", 0)
            self.supplies = claim_data.get("supplies", 0)
            self.tile_count = claim_data.get("tile_count", 0)

            # Calculate supplies per hour based on tile count
            self.supplies_per_hour = self._calculate_supplies_per_hour(self.tile_count)

            # Update UI labels
            if not self.claim_switching:
                self._update_dropdown_selection()

            self.treasury_value_label.configure(text=f"{self.treasury:,}")
            self.supplies_value_label.configure(text=f"{self.supplies:,}")

            # Calculate and update supplies run out time
            self._update_supplies_runout()

        except Exception as e:
            logging.error(f"Error updating claim data in header: {e}")

    def _update_supplies_runout(self):
        """Calculates and updates the time until supplies run out based on tile count."""
        try:
            if self.supplies_per_hour <= 0:
                self.time_remaining = "N/A"
                color = "#cccccc"
            elif self.supplies <= 0:
                self.time_remaining = "Depleted"
                color = "#f44336"
            else:
                total_seconds = int(self.supplies * 3600 / self.supplies_per_hour)
                days = total_seconds // 86400
                hours = (total_seconds % 86400) // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60

                if total_seconds < 1800:  # less than 30 minutes
                    self.time_remaining = f"{minutes}m {seconds}s"
                    color = "#f44336"  # Red for urgent
                elif days == 0 and hours == 0:
                    self.time_remaining = f"{minutes}m"
                    color = "#f44336"
                elif days == 0:
                    self.time_remaining = f"{hours}h {minutes}m"
                    color = "#FF9800"  # Orange for warning
                elif days < 7:
                    self.time_remaining = f"{days}d {hours}h {minutes}m"
                    color = "#FFC107"  # Amber for caution
                else:
                    self.time_remaining = f"{days}d {hours}h {minutes}m"
                    color = "#4CAF50"  # Green for safe

            # Update the label with appropriate color
            self.supplies_runout_label.configure(text=self.time_remaining, text_color=color)

        except Exception as e:
            logging.error(f"Error calculating supplies run out time: {e}")
            self.time_remaining = "Error"
            self.supplies_runout_label.configure(text=self.time_remaining, text_color="#f44336")

    def refresh_supplies_runout(self):
        """Manually refresh the supplies run out calculation (for periodic updates)."""
        self._update_supplies_runout()

    def _open_settings(self):
        """Opens the settings window."""
        try:
            # Create and show the settings window
            settings_window = SettingsWindow(self.app, self.app)

            logging.info("Settings window opened from header")

        except Exception as e:
            logging.error(f"Error opening settings window: {e}")
            messagebox.showerror("Settings Error", f"Failed to open settings:\n{str(e)}")

    def _reset_refresh_button(self):
        """Reset the refresh button to its normal state."""
        # This method is no longer needed since refresh button was removed
        pass

    def update_available_claims(self, claims_list: list, current_claim_id: str = None):
        """
        Updates the list of available claims using CTkOptionMenu.
        """
        self.available_claims = claims_list
        if current_claim_id:
            self.current_claim_id = current_claim_id

        # Extract claim names for the dropdown (handle both key formats)
        claim_names = [claim.get("claim_name") or claim.get("name", "Unknown Claim") for claim in claims_list]

        # Update dropdown state and values based on available claims
        if len(claims_list) > 1:
            # Multiple claims - enable dropdown
            self.claim_dropdown.configure(values=claim_names, state="normal")

            # Set current selection (handle both key formats)
            current_claim_name = None
            for claim in claims_list:
                claim_entity_id = claim.get("entity_id") or claim.get("claim_id")
                if claim_entity_id == current_claim_id:
                    current_claim_name = claim.get("claim_name") or claim.get("name")
                    break

            if current_claim_name:
                self.claim_dropdown.set(current_claim_name)
                self.claim_name = current_claim_name

        elif len(claims_list) == 1:
            # Single claim - show name but disable interaction
            single_claim = claims_list[0]
            claim_name = single_claim.get("claim_name") or single_claim.get("name", "Unknown Claim")
            self.claim_dropdown.configure(values=[claim_name], state="disabled")
            self.claim_dropdown.set(claim_name)
            self.current_claim_id = single_claim.get("entity_id") or single_claim.get("claim_id")
            self.claim_name = claim_name

        else:
            # No claims - show error state
            self.claim_dropdown.configure(values=["No Claims Available"], state="disabled")
            self.claim_dropdown.set("No Claims Available")

        logging.info(f"Updated available claims: {len(claims_list)} claims, current: {current_claim_id}")

    def _update_dropdown_selection(self):
        """Updates the dropdown to show the current claim name."""
        if self.available_claims and not self.claim_switching:
            # Find current claim name and update dropdown (handle both key formats)
            for claim in self.available_claims:
                claim_entity_id = claim.get("entity_id") or claim.get("claim_id")
                if claim_entity_id == self.current_claim_id:
                    claim_name = claim.get("claim_name") or claim.get("name")
                    self.claim_dropdown.set(claim_name)
                    break

    def set_claim_switching(self, switching: bool, message: str = ""):
        """
        Sets the claim switching state. Instead of showing loading in dropdown,
        this signals the main app to show the loading overlay.
        """
        self.claim_switching = switching

        if switching:
            # Disable dropdown during switching
            self.claim_dropdown.configure(state="disabled")

            # Notify main app to show loading overlay with custom message
            if hasattr(self.app, "show_loading_with_message"):
                self.app.show_loading_with_message(message)

        else:
            # Re-enable dropdown and restore normal state
            if len(self.available_claims) > 1:
                self.claim_dropdown.configure(state="normal")
            else:
                self.claim_dropdown.configure(state="disabled")

            # Notify main app to hide loading overlay
            if hasattr(self.app, "hide_loading"):
                self.app.hide_loading()

            # Restore proper selection
            self._update_dropdown_selection()

    def handle_claim_switch_complete(self, claim_id: str, claim_name: str):
        """
        Handles the completion of a claim switch operation.
        """
        self.current_claim_id = claim_id
        self.claim_name = claim_name

        # End switching state
        self.set_claim_switching(False)

        # Update dropdown selection
        self._update_dropdown_selection()

        logging.info(f"Claim switch completed: {claim_name}")

    def handle_claim_switch_error(self, error_message: str):
        """
        Handles errors during claim switching.
        """
        # End switching state
        self.set_claim_switching(False)

        logging.error(f"Claim switch error: {error_message}")

    def get_claims_summary(self) -> str:
        """Returns a summary of available claims for debugging."""
        if not self.available_claims:
            return "No claims available"

        current_name = "None"
        if self.current_claim_id:
            for claim in self.available_claims:
                if claim["claim_id"] == self.current_claim_id:
                    current_name = claim["claim_name"]
                    break

        return f"{len(self.available_claims)} claims, current: {current_name}, switching: {self.claim_switching}"

    def initialize_with_claims(self, claims_list: list, current_claim_id: str = None):
        """
        Initializes the header with the claims list on first load.
        """
        try:
            self.update_available_claims(claims_list, current_claim_id)

            # If we have a current claim, update the display
            if current_claim_id:
                current_claim = None
                for claim in claims_list:
                    if claim["entity_id"] == current_claim_id:
                        current_claim = claim
                        break

                if current_claim:
                    # Update header with initial claim data
                    self.update_claim_data(
                        {
                            "name": current_claim["name"],
                            "treasury": current_claim.get("treasury", 0),
                            "supplies": current_claim.get("supplies", 0),
                            "tile_count": current_claim.get("tile_count", 0),
                        }
                    )

            logging.info(f"Header initialized with {len(claims_list)} claims")

        except Exception as e:
            logging.error(f"Error initializing header with claims: {e}")

    def update_task_refresh_expiration(
        self,
        expiration_time: int,
        is_initial_subscription: bool = False,
        source: str = "unknown",
    ):
        """
        Updates the traveler tasks expiration time and starts countdown.

        Args:
            expiration_time: Seconds since Unix epoch when tasks refresh
            is_initial_subscription: True if this data came from InitialSubscription
            source: Source of the update (subscription, transaction)
        """
        try:
            logging.debug(
                f"[ClaimInfoHeader] Timer update: expiration={expiration_time}, is_initial={is_initial_subscription}, source={source}"
            )

            # Update expiration time - always accept the new value
            self.traveler_tasks_expiration = expiration_time

            # Mark the source of this update for timer logic
            self._last_update_source = source
            self._from_initial_subscription = is_initial_subscription

            self._update_task_refresh_countdown()

            # Start periodic updates if not already running
            if not hasattr(self, "_task_refresh_timer_running"):
                self._task_refresh_timer_running = True
                self._schedule_task_refresh_update()

        except Exception as e:
            logging.error(f"Error updating task refresh expiration: {e}")

    def _update_task_refresh_countdown(self):
        """Calculates and updates the task refresh countdown."""
        try:
            if self.traveler_tasks_expiration is None:
                self.task_refresh_time = "Loading..."
                color = "#9C27B0"
            else:
                current_time_seconds = time.time()
                time_diff_seconds = self.traveler_tasks_expiration - current_time_seconds

                if time_diff_seconds <= 0:
                    # Timer expired - tasks are refreshing, wait for server to provide new expiration
                    import datetime

                    current_dt = datetime.datetime.fromtimestamp(current_time_seconds)
                    expiration_dt = datetime.datetime.fromtimestamp(self.traveler_tasks_expiration)

                    # Check how long we've been in expired state
                    expired_duration = abs(time_diff_seconds)

                    if expired_duration < 60:  # Less than 1 minute - show refreshing
                        self.task_refresh_time = "Refreshing..."
                        color = "#FF9800"  # Orange for activity/refreshing state
                    else:  # More than 1 minute - show waiting for server
                        logging.warning(
                            f"Task refresh timer expired over 1 minute ago: current={current_dt}, expiration={expiration_dt}, expired_for={expired_duration:.1f}s - waiting for server"
                        )
                        self.task_refresh_time = "Waiting for server..."
                        color = "#9E9E9E"  # Gray for waiting/inactive state

                    self.task_refresh_label.configure(text=self.task_refresh_time, text_color=color)
                    return

                # Continue with normal countdown display logic...
                total_seconds = int(time_diff_seconds)
                days = total_seconds // 86400
                hours = (total_seconds % 86400) // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60

                # Format display based on time remaining - show largest relevant units
                if total_seconds < 60:  # less than 1 minute - show seconds only
                    self.task_refresh_time = f"{seconds}s"
                    color = "#FF5722"  # Red for very soon
                elif total_seconds < 1800:  # less than 30 minutes - show minutes and seconds
                    self.task_refresh_time = f"{minutes}m {seconds}s"
                    color = "#FF9800"  # Orange for soon
                elif total_seconds < 3600:  # less than 1 hour - show minutes only
                    self.task_refresh_time = f"{minutes}m"
                    color = "#FF9800"  # Orange for soon
                elif days == 0 and hours > 0:  # same day with hours - show hours and minutes
                    self.task_refresh_time = f"{hours}h {minutes}m"
                    color = "#FFC107"  # Amber for today
                elif days > 0:  # more than a day - show days and hours
                    self.task_refresh_time = f"{days}d {hours}h"
                    color = "#9C27B0"  # Purple for future
                else:  # fallback
                    self.task_refresh_time = f"{hours}h {minutes}m"
                    color = "#FFC107"

            # Update the label with appropriate color
            self.task_refresh_label.configure(text=self.task_refresh_time, text_color=color)

        except Exception as e:
            logging.error(f"Error calculating task refresh countdown: {e}")
            self.task_refresh_time = "Error"
            self.task_refresh_label.configure(text=self.task_refresh_time, text_color="#f44336")

    def _schedule_task_refresh_update(self):
        """Schedules the next task refresh countdown update."""
        try:
            # Update every second for accurate countdown
            self.after(1000, self._periodic_task_refresh_update)
        except Exception as e:
            logging.error(f"Error scheduling task refresh update: {e}")

    def _periodic_task_refresh_update(self):
        """Periodic update method for task refresh countdown."""
        try:
            if hasattr(self, "_task_refresh_timer_running") and self._task_refresh_timer_running:
                self._update_task_refresh_countdown()
                self._schedule_task_refresh_update()
        except Exception as e:
            logging.error(f"Error in periodic task refresh update: {e}")

    def stop_task_refresh_timer(self):
        """Stops the task refresh countdown timer."""
        try:
            if hasattr(self, "_task_refresh_timer_running"):
                self._task_refresh_timer_running = False
        except Exception as e:
            logging.error(f"Error stopping task refresh timer: {e}")

    def _request_fresh_player_state(self):
        """
        Request fresh player_state data to get updated traveler_tasks_expiration.
        This is called when the timer hits 0 to detect task refresh.
        """
        try:
            # Access the data service through the main app to request fresh data
            if hasattr(self.app, "data_service") and self.app.data_service:

                # As a fallback, schedule a check in 30 seconds to see if data has updated
                self.after(30000, self._check_for_updated_expiration)
            else:
                logging.warning("Cannot request fresh player state - no data service available")
        except Exception as e:
            logging.error(f"Error requesting fresh player state: {e}")

    def _check_for_updated_expiration(self):
        """
        Check if the expiration time has been updated (indicating tasks refreshed).
        This is a fallback method when we can't directly request fresh data.
        """
        try:
            # This method is called periodically to check if we need to refresh player state
            # when tasks might be refreshing (no longer needed with improved logic)
            pass
        except Exception as e:
            logging.error(f"Error checking for updated expiration: {e}")

    def _export_data(self):
        """Exports all table data to an Excel file using native file dialog."""
        try:
            # Generate default filename
            claim_name = self.claim_name.replace(" ", "_").replace("/", "-") if self.claim_name else "Unknown_Claim"
            claim_id = self.current_claim_id if self.current_claim_id else "unknown"
            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"{claim_name}_{claim_id}_{date_str}.xlsx"

            # Show file save dialog
            file_path = filedialog.asksaveasfilename(
                title="Export Claim Data",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                initialfile=default_filename,
            )

            if not file_path:
                logging.info("Export cancelled by user")
                return

            # Create workbook
            workbook = openpyxl.Workbook()

            # Remove default sheet
            default_sheet = workbook.active
            workbook.remove(default_sheet)

            # Export each tab's data
            tabs_data = self._get_all_tabs_data()

            for tab_name, tab_data in tabs_data.items():
                if tab_data:
                    self._create_excel_sheet(workbook, tab_name, tab_data)

            # Add claim info sheet
            self._create_claim_info_sheet(workbook)

            # Save the workbook
            workbook.save(file_path)

            # Show success message
            messagebox.showinfo("Export Successful", f"Data exported successfully to:\n{os.path.basename(file_path)}")

            logging.info(f"Data exported to: {file_path}")

        except Exception as e:
            logging.error(f"Error exporting data: {e}")
            messagebox.showerror("Export Error", f"Failed to export data:\n{str(e)}")

    def _get_all_tabs_data(self):
        """Retrieves data from all tabs in the main application."""
        tabs_data = {}

        try:
            if hasattr(self.app, "tabs"):
                for tab_name, tab_instance in self.app.tabs.items():
                    if hasattr(tab_instance, "filtered_data"):
                        # Get filtered data from each tab
                        data = tab_instance.filtered_data
                        if data:
                            tabs_data[tab_name] = {"headers": getattr(tab_instance, "headers", []), "data": data}

        except Exception as e:
            logging.error(f"Error getting tabs data: {e}")

        return tabs_data

    def _create_excel_sheet(self, workbook, tab_name, tab_data):
        """Creates an Excel sheet for a specific tab's data."""
        try:
            sheet = workbook.create_sheet(title=tab_name)
            headers = tab_data.get("headers", [])
            data = tab_data.get("data", [])

            if not headers or not data:
                return

            # Write headers
            for col_idx, header in enumerate(headers, 1):
                cell = sheet.cell(row=1, column=col_idx, value=header)
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center")

            # Write data
            for row_idx, row_data in enumerate(data, 2):
                for col_idx, header in enumerate(headers, 1):
                    # Get value based on header name (convert to lowercase and replace spaces with underscores)
                    header_key = header.lower().replace(" ", "_").replace("'", "")

                    # Handle special cases for different tab structures
                    if tab_name == "Traveler's Tasks":
                        value = self._get_traveler_task_value(row_data, header)
                    else:
                        value = row_data.get(header_key, row_data.get(header.lower(), ""))

                    # Convert to string for Excel
                    sheet.cell(row=row_idx, column=col_idx, value=str(value))

            # Auto-adjust column widths
            for column in sheet.columns:
                max_length = 0
                column = list(column)
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                sheet.column_dimensions[column[0].column_letter].width = adjusted_width

        except Exception as e:
            logging.error(f"Error creating Excel sheet for {tab_name}: {e}")

    def _get_traveler_task_value(self, row_data, header):
        """Gets the correct value for traveler tasks data structure."""
        try:
            if header == "Traveler":
                return row_data.get("traveler", "")
            elif header == "Item":
                # For parent rows, show completion summary
                operations = row_data.get("operations", [])
                if operations:
                    completed = row_data.get("completed_count", 0)
                    total = row_data.get("total_count", 0)
                    return f"Tasks ({completed}/{total} completed)"
                return row_data.get("item", "")
            elif header == "Completed":
                return row_data.get("completed", "")
            elif header == "Status":
                return row_data.get("status", "")
            else:
                # For other fields, check operations if main row doesn't have it
                value = row_data.get(header.lower().replace(" ", "_"), "")
                if not value:
                    operations = row_data.get("operations", [])
                    if operations:
                        # Get from first operation
                        return operations[0].get(header.lower().replace(" ", "_"), "")
                return value
        except Exception as e:
            logging.error(f"Error getting traveler task value: {e}")
            return ""

    def _create_claim_info_sheet(self, workbook):
        """Creates a sheet with claim information."""
        try:
            sheet = workbook.create_sheet(title="Claim Info")

            # Claim information
            claim_info = [
                ["Claim Name", self.claim_name],
                ["Claim ID", self.current_claim_id or "Unknown"],
                ["Treasury", f"{self.treasury:,}"],
                ["Supplies", f"{self.supplies:,}"],
                ["Tile Count", str(self.tile_count)],
                ["Supplies per Hour", f"{self.supplies_per_hour:.3f}"],
                ["Time Until Depletion", self.time_remaining],
                ["Task Refresh Time", self.task_refresh_time],
                ["Export Date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ]

            for row_idx, (label, value) in enumerate(claim_info, 1):
                sheet.cell(row=row_idx, column=1, value=label).font = Font(bold=True)
                sheet.cell(row=row_idx, column=2, value=str(value))

            # Auto-adjust column widths
            sheet.column_dimensions["A"].width = 20
            sheet.column_dimensions["B"].width = 30

        except Exception as e:
            logging.error(f"Error creating claim info sheet: {e}")

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
            logging.info("User initiated logout from main window")

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
            logging.info("User initiated application quit from header")

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
                import sys

                sys.exit(0)
