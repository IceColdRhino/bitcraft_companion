import sys
import customtkinter as ctk
import queue
import logging
import time
from tkinter import messagebox
from typing import Dict
import os
import threading
from PIL import Image

from app.core.data_service import DataService
from app.ui.components.claim_info_header import ClaimInfoHeader
from app.ui.tabs.claim_inventory_tab import ClaimInventoryTab
from app.ui.tabs.passive_crafting_tab import PassiveCraftingTab
from app.ui.tabs.traveler_tasks_tab import TravelerTasksTab
from app.ui.tabs.active_crafting_tab import ActiveCraftingTab
from app.ui.tabs.compare_jobs_tab import CompareJobsTab


class ShutdownDialog(ctk.CTkToplevel):
    """A small dialog shown during application shutdown to indicate progress."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Closing BitCraft Companion")
        self.geometry("350x120")
        self.resizable(False, False)

        # Make it modal and stay on top
        self.transient(parent)
        self.grab_set()
        self.attributes("-topmost", True)

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (350 // 2)
        y = (self.winfo_screenheight() // 2) - (120 // 2)
        self.geometry(f"350x120+{x}+{y}")

        # Remove window controls (user can't close this manually)
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        # Create content
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Status label
        self.status_label = ctk.CTkLabel(main_frame, text="Closing application...", font=ctk.CTkFont(size=14, weight="bold"))
        self.status_label.pack(pady=(10, 5))

        # Progress label
        self.progress_label = ctk.CTkLabel(
            main_frame, text="Stopping services and saving data", font=ctk.CTkFont(size=11), text_color="#888888"
        )
        self.progress_label.pack(pady=(0, 10))

        # Progress bar (indeterminate)
        self.progress_bar = ctk.CTkProgressBar(main_frame, mode="indeterminate")
        self.progress_bar.pack(fill="x", padx=20)
        self.progress_bar.start()

    def update_status(self, message: str):
        """Update the progress message."""
        try:
            self.progress_label.configure(text=message)
            self.update()
        except:
            pass


class MainWindow(ctk.CTk):
    """Main application window with modular tab system and responsive shutdown."""

    def __init__(self, data_service: DataService):
        super().__init__()
        logging.info("Initializing main application window")

        # Log window geometry and display info
        try:
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            logging.debug(f"Screen dimensions: {screen_width}x{screen_height}")
        except Exception as e:
            logging.debug(f"Error getting screen dimensions: {e}")

        self.title("Bitcraft Companion")
        self.geometry("900x600")
        logging.debug("Main window geometry set to 900x600")

        # Set minimum window size to prevent UI elements from becoming inaccessible
        # Width: 300px (dropdown) + 100px (settings) + 80px (logout) + 70px (quit) + 80px (padding) = 630px
        # Height: 80px (header) + 45px (tabs) + 50px (search) + 300px (content) + 45px (margins) = 520px
        self.minsize(650, 520)
        logging.debug("Minimum window size set to 650x520")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self.data_service = data_service

        # Initialize notification service with this app instance
        self.data_service.set_main_app(self)
        self.tabs: Dict[str, ctk.CTkFrame] = {}
        self.tab_buttons: Dict[str, ctk.CTkButton] = {}
        self.active_tab_name = None

        # Shutdown tracking
        self.is_shutting_down = False
        self.shutdown_dialog = None

        # Resize performance optimization
        self.is_resizing = False
        self.resize_timer = None

        # Create the claim info header
        logging.debug("Creating claim info header")
        self.claim_info = ClaimInfoHeader(self, self)
        self.claim_info.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        # Create tab button frame with tab-like styling
        logging.debug("Creating tab button frame")
        self.tab_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tab_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 0))

        # Create search section
        logging.debug("Creating search section")
        self._create_search_section()

        # Track loading state
        self.is_loading = True
        self.expected_data_types = {"inventory", "crafting", "active_crafting", "tasks", "claim_info"}
        self.received_data_types = set()
        logging.debug(f"Loading state initialized - expecting data types: {self.expected_data_types}")

        # Create tab content area with modern styling
        logging.debug("Creating tab content area")
        self.tab_content_area = ctk.CTkFrame(
            self, fg_color=("#2b2b2b", "#1e1e1e"), border_width=2, border_color=("#404040", "#505050"), corner_radius=12
        )
        self.tab_content_area.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.tab_content_area.grid_columnconfigure(0, weight=1)
        self.tab_content_area.grid_rowconfigure(0, weight=1)

        # Create loading overlay
        logging.debug("Creating loading overlay")
        self.loading_overlay = self._create_loading_overlay()

        # Initialize tabs and UI
        logging.debug("Initializing tabs and UI components")
        self._create_tabs()
        self._create_tab_buttons()
        self.show_tab("Claim Inventory")

        # Ensure loading overlay is visible on top and lock tab buttons
        # Just show the overlay and set initial state
        logging.info(f"[LOADING STATE] Showing initial loading overlay")
        self.loading_overlay.grid(row=0, column=0, sticky="nsew")
        self.loading_overlay.tkraise()
        self._set_tab_buttons_state("disabled")

        # Start loading animation
        if hasattr(self, "loading_indicator"):
            self._start_loading_animation()

        # Start data processing with enhanced timer support and resize detection
        logging.debug("Starting data processing loop with enhanced timer support")
        self.after(100, self.process_data_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.bind("<Configure>", self._on_window_configure)

    def _on_window_configure(self, event):
        """Handles window configure events to detect resize operations for performance optimization."""
        # Only handle configure events for the main window itself
        if event.widget != self:
            return

        # Cancel previous resize timer
        if self.resize_timer:
            self.after_cancel(self.resize_timer)

        # Mark as resizing and schedule resize completion detection
        if not self.is_resizing:
            self.is_resizing = True
            logging.debug("Window resize started - optimizing performance")

        # Schedule resize completion detection
        self.resize_timer = self.after(300, self._on_resize_complete)

    def _on_resize_complete(self):
        """Called when resize operation appears to be complete."""
        self.is_resizing = False
        self.resize_timer = None
        logging.debug("Window resize completed - resuming normal performance")

    def _set_tab_buttons_state(self, state: str):
        """Enable or disable all tab buttons."""
        for btn in self.tab_buttons.values():
            btn.configure(state=state)

        # Start data processing with enhanced timer support
        self.after(100, self.process_data_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_search_section(self):
        """Creates the search section with label, field, and clear button."""
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=8)
        search_frame.grid_columnconfigure(1, weight=1)  # Make search field expand

        # Search label
        search_label = ctk.CTkLabel(
            search_frame, text="Search:", font=ctk.CTkFont(size=12, weight="normal"), text_color="#cccccc"
        )
        search_label.grid(row=0, column=0, padx=(0, 8), sticky="w")

        # Search variable and field
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.on_search_change)

        self.search_field = ctk.CTkEntry(
            search_frame,
            textvariable=self.search_var,
            placeholder_text="🔍 Type to search items...",
            height=34,
            font=ctk.CTkFont(size=12),
            fg_color=("#2a2d2e", "#343638"),
            border_color=("#404040", "#505050"),
            text_color=("#ffffff", "#f0f0f0"),
            placeholder_text_color=("#888888", "#999999"),
            corner_radius=8,
        )
        self.search_field.grid(row=0, column=1, sticky="ew", padx=(0, 8))

        # Clear button with modern styling
        self.clear_button = ctk.CTkButton(
            search_frame,
            text="✕ Clear",
            command=self.clear_search,
            width=70,
            height=34,
            font=ctk.CTkFont(size=11),
            fg_color=("#666666", "#707070"),
            hover_color=("#777777", "#808080"),
            corner_radius=8,
            text_color=("#ffffff", "#f0f0f0"),
        )
        self.clear_button.grid(row=0, column=2, sticky="e")

    def clear_search(self):
        """Clears the search field."""
        self.search_var.set("")
        self.search_field.focus()  # Return focus to search field

    def _create_loading_overlay(self):
        """Creates a clean, text-based loading overlay."""
        overlay = ctk.CTkFrame(self.tab_content_area, fg_color="#2b2b2b")
        overlay.grid(row=0, column=0, sticky="nsew")
        overlay.grid_columnconfigure(0, weight=1)
        overlay.grid_rowconfigure(0, weight=1)

        # Create loading content frame
        loading_frame = ctk.CTkFrame(overlay, fg_color="transparent")
        loading_frame.grid(row=0, column=0)

        # Main loading title with modern styling
        self.loading_title = ctk.CTkLabel(loading_frame, text="", font=ctk.CTkFont(size=24, weight="bold"), text_color="#3B8ED0")
        self.loading_title.pack(pady=(0, 20))

        # Animated loading indicator (will be updated with dots)
        self.loading_indicator = ctk.CTkLabel(loading_frame, text="●●●", font=ctk.CTkFont(size=18), text_color="#1F6AA5")
        self.loading_indicator.pack(pady=(0, 15))

        # Loading message with better formatting
        self.loading_message = ctk.CTkLabel(
            loading_frame,
            text="Connecting to game server and fetching your claim data",
            font=ctk.CTkFont(size=13),
            text_color="#CCCCCC",
        )
        self.loading_message.pack()

        # Start the loading animation
        self._start_loading_animation()

        return overlay

    def _start_loading_animation(self):
        """Starts the loading dots animation."""
        logging.debug("Starting loading animation")
        self.loading_animation_state = 0
        self._animate_loading_dots()

    def _animate_loading_dots(self):
        """Animates the loading dots with a cycling pattern."""
        if not hasattr(self, "is_loading") or not self.is_loading:
            return

        try:
            # Skip animation updates during resize for better performance
            if not self.is_resizing:
                dot_patterns = ["●○○", "●●○", "●●●", "○●●", "○○●", "○○○"]
                if hasattr(self, "loading_indicator"):
                    pattern = dot_patterns[self.loading_animation_state % len(dot_patterns)]
                    self.loading_indicator.configure(text=pattern)
                    self.loading_animation_state += 1

            # Adaptive animation frequency: slower during resize
            interval = 600 if self.is_resizing else 300
            self.after(interval, self._animate_loading_dots)
        except Exception as e:
            logging.error(f"Error in loading animation: {e}")

    def show_loading(self, reset_data_tracking=True):
        """Shows the loading overlay with minimum display time for better UX."""
        logging.info(f"[LOADING STATE] Showing loading overlay - reset_data_tracking: {reset_data_tracking}")
        self.is_loading = True
        if reset_data_tracking:
            self.received_data_types = set()  # Reset data tracking when showing loading for claim switch
        self.loading_start_time = time.time()
        self.loading_overlay.grid(row=0, column=0, sticky="nsew")
        self.loading_overlay.tkraise()
        self._set_tab_buttons_state("disabled")

        # Restart animation
        if hasattr(self, "loading_indicator"):
            self._start_loading_animation()

    def hide_loading(self):
        """Hides the loading overlay with minimum display time."""
        if not self.is_loading:
            return

        # Ensure minimum display time of 1 second for better UX
        if hasattr(self, "loading_start_time"):
            elapsed = time.time() - self.loading_start_time
            min_display_time = 1.0

            if elapsed < min_display_time:
                remaining = int((min_display_time - elapsed) * 1000)
                self.after(remaining, self._actually_hide_loading)
                return

        self._actually_hide_loading()

    def _actually_hide_loading(self):
        """Actually hides the loading overlay."""
        logging.info(f"[LOADING STATE] Hiding loading overlay - data types received: {self.received_data_types}")
        self.is_loading = False
        self.loading_overlay.grid_remove()
        self._set_tab_buttons_state("normal")

    def _create_tabs(self):
        """Creates all tab instances using the modular tab classes."""

        tab_classes = {
            "Claim Inventory": ClaimInventoryTab,
            "Passive Crafting": PassiveCraftingTab,
            "Active Crafting": ActiveCraftingTab,
            "Traveler's Tasks": TravelerTasksTab,
            "Compare Jobs": CompareJobsTab,
        }

        for name, TabClass in tab_classes.items():
            tab = TabClass(self.tab_content_area, app=self)
            tab.grid(row=0, column=0, sticky="nsew")
            self.tabs[name] = tab
            logging.info(f"Created tab: {name}")

    def _create_tab_buttons(self):
        """Creates the tab navigation buttons with modern styling."""
        for i, name in enumerate(self.tabs.keys()):
            btn = ctk.CTkButton(
                self.tab_frame,
                text=name,
                width=140,
                height=38,
                corner_radius=10,
                border_width=2,
                border_color="#404040",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="transparent",
                text_color=("#cccccc", "#e0e0e0"),
                hover_color=("#3a3a3a", "#454545"),
                command=lambda n=name: self.show_tab(n),
            )
            btn.grid(row=0, column=i, padx=(0 if i == 0 else 4, 0), pady=(0, 2), sticky="w")
            self.tab_buttons[name] = btn

    def show_tab(self, tab_name):
        """Shows the specified tab and updates button states with enhanced visual feedback."""
        if self.active_tab_name == tab_name:
            return

        self.active_tab_name = tab_name
        self.tabs[tab_name].tkraise()

        # Update button appearances with modern styling
        for i, (name, button) in enumerate(self.tab_buttons.items()):
            if name == tab_name:
                # Active tab with subtle gradient effect
                button.configure(
                    fg_color=("#3B8ED0", "#2980B9"),
                    text_color="white",
                    border_color="#3B8ED0",
                    hover_color=("#2E7BB8", "#1A5A8A"),
                )
            else:
                # Inactive tab with improved contrast
                button.configure(
                    fg_color="transparent",
                    text_color=("#cccccc", "#e0e0e0"),
                    border_color="#404040",
                    hover_color=("#3a3a3a", "#454545"),
                )

        # Apply current search filter to the new tab
        self.on_search_change()
        logging.info(f"Switched to tab: {tab_name}")

    def on_search_change(self, *args):
        """Applies search filter to the currently active tab."""
        if self.active_tab_name and hasattr(self.tabs[self.active_tab_name], "apply_filter"):
            self.tabs[self.active_tab_name].apply_filter()

    def _check_all_data_loaded(self):
        """Check if all expected data types have been received and hide loading if so."""
        if self.is_loading and self.received_data_types >= self.expected_data_types:
            logging.info(f"All initial data loaded: {self.received_data_types}")
            self.hide_loading()

    def _celebrate_task_completions(self, completed_tasks):
        """
        Celebrate completed tasks with visual feedback.

        Args:
            completed_tasks: List of completed task information
        """
        try:
            if not completed_tasks:
                return

            # Log celebratory message
            count = len(completed_tasks)
            logging.info(f"{count} task(s) completed!")

            # Update window title briefly to show completion
            original_title = self.title()
            if count == 1:
                task_name = completed_tasks[0].get("task_description", "Task")[:30]
                self.title(f"Task completed: {task_name}... - {original_title}")
            else:
                self.title(f"{count} tasks completed! - {original_title}")

            # Reset title after 3 seconds
            self.after(3000, lambda: self.title(original_title))

            # Log each completion
            for task in completed_tasks:
                task_desc = task.get("task_description", "Unknown Task")
                traveler_name = task.get("traveler_name", "Unknown Traveler")
                logging.info(f"Completed: {task_desc} for {traveler_name}")

        except Exception as e:
            logging.error(f"Error celebrating task completions: {e}")

    def _celebrate_completions(self, completed_items):
        """
        Celebrate completed crafting items with visual/audio feedback.

        Args:
            completed_items: List of completed crafting operations
        """
        try:
            if not completed_items:
                return

            # Log celebratory message
            count = len(completed_items)
            logging.info(f"{count} crafting operation(s) completed!")

            # Update window title briefly
            original_title = self.title()
            self.title(f"{count} items ready! - {original_title}")

            # Reset title after 3 seconds
            self.after(3000, lambda: self.title(original_title))

        except Exception as e:
            logging.error(f"Error celebrating completions: {e}")

    def show_completion_notification(self, item_name: str, quantity: int = 1):
        """
        Show a brief notification for completed items.

        Args:
            item_name: Name of the completed item
            quantity: Number of items completed
        """
        try:
            # Create a simple notification window
            notification = ctk.CTkToplevel(self)
            notification.title("Crafting Complete!")
            notification.geometry("300x100")
            notification.attributes("-topmost", True)

            # Center it on the main window
            self.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() // 2) - 150
            y = self.winfo_y() + 100
            notification.geometry(f"300x100+{x}+{y}")

            # Add notification content
            if quantity == 1:
                message = f"{item_name} is ready!"
            else:
                message = f"{quantity}x {item_name} ready!"

            label = ctk.CTkLabel(notification, text=message, font=ctk.CTkFont(size=14, weight="bold"), text_color="#4CAF50")
            label.pack(expand=True)

            # Auto-close after 3 seconds
            notification.after(3000, notification.destroy)

        except Exception as e:
            logging.error(f"Error showing completion notification: {e}")

    def on_closing(self):
        """
        ENHANCED: Responsive shutdown with immediate UI feedback.
        Shows shutdown dialog immediately while cleanup happens in background.
        """
        if self.is_shutting_down:
            return  # Already shutting down

        logging.info("[MainWindow] Closing application...")
        self.is_shutting_down = True

        try:
            # STEP 1: Immediately hide main window and show shutdown dialog
            self.withdraw()  # Hide main window instantly

            # Show shutdown dialog
            self.shutdown_dialog = ShutdownDialog(self)

            # STEP 2: Start background shutdown process
            def background_shutdown():
                try:
                    # Update dialog
                    self.shutdown_dialog.update_status("Stopping real-time services...")

                    # Stop the data service
                    if hasattr(self, "data_service") and self.data_service:
                        logging.info("[MainWindow] Stopping data service...")
                        self.data_service.stop()

                    # Stop task refresh timer
                    if hasattr(self, "claim_info") and self.claim_info:
                        logging.info("[MainWindow] Stopping task refresh timer...")
                        self.claim_info.stop_task_refresh_timer()

                    self.shutdown_dialog.update_status("Saving data...")

                    # Give services a moment to clean up
                    import time

                    time.sleep(0.2)

                    self.shutdown_dialog.update_status("Finalizing shutdown...")

                    # Schedule UI cleanup on main thread
                    self.after(0, self._finish_shutdown)

                except Exception as e:
                    logging.error(f"[MainWindow] Error during background shutdown: {e}")
                    # Still try to finish shutdown
                    self.after(0, self._finish_shutdown)

            # Start background shutdown in a separate thread
            shutdown_thread = threading.Thread(target=background_shutdown, daemon=True)
            shutdown_thread.start()

        except Exception as e:
            logging.error(f"[MainWindow] Error starting shutdown: {e}")
            # Fallback to immediate shutdown
            self._finish_shutdown()

    def _finish_shutdown(self):
        """Complete the shutdown process on the main thread."""
        try:
            logging.info("[MainWindow] Finalizing application shutdown...")

            # Close shutdown dialog
            if self.shutdown_dialog:
                try:
                    self.shutdown_dialog.destroy()
                except:
                    pass

            # Destroy main window
            logging.info("[MainWindow] Destroying window...")
            self.destroy()

        except Exception as e:
            logging.error(f"[MainWindow] Error during final shutdown: {e}")
            try:
                self.destroy()
            except:
                pass
        finally:
            # Ensure we exit
            try:
                self.quit()
            except:
                pass
            sys.exit(0)

    def switch_to_claim(self, claim_id: str):
        """
        Initiates a claim switch operation.

        Args:
            claim_id: The claim ID to switch to
        """
        try:
            if not self.data_service or not hasattr(self.data_service, "switch_claim"):
                logging.error("Data service does not support claim switching")
                return

            logging.info(f"Initiating claim switch to: {claim_id}")

            # Start the claim switch process
            self.data_service.switch_claim(claim_id)

        except Exception as e:
            logging.error(f"Error initiating claim switch: {e}")
            messagebox.showerror("Claim Switch Error", f"Failed to switch claims: {str(e)}")

    def _handle_claim_switching_message(self, msg_data):
        """
        Handles the claim_switching message from DataService.
        Shows loading overlay and clears tab data.
        """
        try:
            status = msg_data.get("status")
            claim_name = msg_data.get("claim_name", "Unknown Claim")
            message = msg_data.get("message", f"Switching to {claim_name}...")

            if status == "loading":
                # Clear all tab data first
                self._clear_all_tab_data()

                # Show loading overlay with claim switch message
                custom_message = f"Switching to {claim_name}... One moment please"
                self.show_loading_with_message(custom_message)

                # Update header for switching state
                self.claim_info.set_claim_switching(True, message)

                # Disable tab buttons during switch
                self._set_tab_buttons_state("disabled")

                logging.info(f"Claim switching started: {claim_name}")

        except Exception as e:
            logging.error(f"Error handling claim switching message: {e}")

    def _clear_all_tab_data(self):
        """
        Clears data from all tabs to show empty state during claim switching.
        """
        try:
            if "Claim Inventory" in self.tabs:
                self.tabs["Claim Inventory"].update_data({})

            if "Passive Crafting" in self.tabs:
                self.tabs["Passive Crafting"].update_data([])

            if "Active Crafting" in self.tabs:
                self.tabs["Active Crafting"].update_data([])

            if "Traveler's Tasks" in self.tabs:
                self.tabs["Traveler's Tasks"].update_data([])

            if "Compare Jobs" in self.tabs:
                self.tabs["Compare Jobs"].update_data([])

        except Exception as e:
            logging.error(f"Error clearing tab data: {e}")

    def _handle_claim_switched_message(self, msg_data):
        """
        Handles the claim_switched message from DataService.
        Hides loading overlay and updates with new claim data.
        """
        try:
            status = msg_data.get("status")
            claim_id = msg_data.get("claim_id")
            claim_name = msg_data.get("claim_name", "Unknown Claim")
            claim_info = msg_data.get("claim_info", {})

            if status == "success":
                # Update header with new claim info first
                self.claim_info.handle_claim_switch_complete(claim_id, claim_name)
                self.claim_info.update_claim_data(claim_info)

                # Re-enable tab buttons
                self._set_tab_buttons_state("normal")

                logging.info(f"Claim switch completed successfully: {claim_name}")

                # Brief success notification in title bar
                original_title = self.title()
                self.title(f"✓ Switched to {claim_name} - {original_title}")
                self.after(3000, lambda: self.title(original_title))
            else:
                # Handle switch failure
                error_msg = msg_data.get("error", "Unknown error during claim switch")
                self._handle_claim_switch_error(error_msg)

        except Exception as e:
            logging.error(f"Error handling claim switched message: {e}")
            self._handle_claim_switch_error(str(e))

    def _handle_claim_switch_error(self, error_message: str):
        """
        Handles errors during claim switching.
        """
        try:
            # Hide loading overlay
            self.hide_loading()

            # Update header to clear switching state
            self.claim_info.handle_claim_switch_error(error_message)

            # Re-enable tab buttons
            self._set_tab_buttons_state("normal")

            # Show error message
            messagebox.showerror("Claim Switch Failed", f"Failed to switch claims:\n{error_message}")

            logging.error(f"Claim switch failed: {error_message}")

        except Exception as e:
            logging.error(f"Error handling claim switch error: {e}")

    def _handle_claims_list_update(self, msg_data):
        """
        Handles the claims_list_update message from DataService.

        Args:
            msg_data: Message data containing available claims
        """
        try:
            claims = msg_data.get("claims", [])
            current_claim_id = msg_data.get("current_claim_id")

            # Initialize header with available claims (this fixes the loading issue)
            self.claim_info.initialize_with_claims(claims, current_claim_id)

            logging.info(f"Updated available claims: {len(claims)} claims, current: {current_claim_id}")

        except Exception as e:
            logging.error(f"Error handling claims list update: {e}")

    def _handle_player_state_update(self, msg_data):
        """
        Handles the player_state_update message from TasksProcessor.
        Updates the task refresh countdown in the claim info header.

        Args:
            msg_data: Message data containing player state information
        """
        try:
            traveler_tasks_expiration = msg_data.get("traveler_tasks_expiration", 0)
            is_initial_subscription = msg_data.get("is_initial_subscription", False)
            source = msg_data.get("source", "unknown")
            reducer_name = msg_data.get("reducer_name", "")

            logging.debug(
                f"[MainWindow] Player state update: expiration={traveler_tasks_expiration}, source={source}, is_initial={is_initial_subscription}, reducer={reducer_name}"
            )

            if traveler_tasks_expiration > 0:
                # Update the claim info header with the expiration time and context
                self.claim_info.update_task_refresh_expiration(
                    traveler_tasks_expiration,
                    is_initial_subscription=is_initial_subscription,
                    source=source,
                )

        except Exception as e:
            logging.error(f"Error handling player state update: {e}")

    def _handle_traveler_task_timer_update(self, msg_data):
        """
        Handles traveler_task_timer_update messages from TasksProcessor one-off queries.
        Updates the task refresh countdown in the claim info header.

        Args:
            msg_data: Message data containing traveler task timer information
        """
        try:
            traveler_tasks_expiration = msg_data.get("traveler_tasks_expiration", 0)
            is_initial = msg_data.get("is_initial", False)
            source = msg_data.get("source", "unknown")
            query_type = msg_data.get("query_type", "unknown")

            logging.debug(
                f"[MainWindow] Traveler task timer update: expiration={traveler_tasks_expiration}, "
                f"source={source}, query_type={query_type}, is_initial={is_initial}"
            )

            if traveler_tasks_expiration > 0:
                # Update the claim info header with the timer
                self.claim_info.update_task_refresh_expiration(
                    traveler_tasks_expiration,
                    is_initial_subscription=is_initial,  # Keep the same parameter name for compatibility
                    source=source,
                )
                logging.debug(f"[MainWindow] Task timer updated in claim info header")
            else:
                logging.warning(f"[MainWindow] Received invalid timer expiration: {traveler_tasks_expiration}")

        except Exception as e:
            logging.error(f"Error handling traveler task timer update: {e}")

    def process_data_queue(self):
        """Enhanced data queue processing that handles claim switching messages."""
        try:
            message_count = 0
            while not self.data_service.data_queue.empty():
                message = self.data_service.data_queue.get_nowait()
                message_count += 1
                msg_type = message.get("type")
                msg_data = message.get("data")

                # Log data type and size for debugging
                data_size = len(msg_data) if isinstance(msg_data, (dict, list)) else "unknown"
                logging.debug(f"Processing message {message_count}: {msg_type} (data size: {data_size})")

                if msg_type == "inventory_update":
                    if "Claim Inventory" in self.tabs:
                        start_time = time.time()

                        # Log inventory data details for debugging
                        data_size = len(msg_data) if isinstance(msg_data, dict) else "unknown"
                        logging.debug(f"Processing inventory update: {data_size} items, loading state: {self.is_loading}")

                        self.tabs["Claim Inventory"].update_data(msg_data)
                        update_time = time.time() - start_time
                        logging.debug(f"Inventory tab update took {update_time:.3f}s")

                        # Track that we've received inventory data
                        if self.is_loading:
                            self.received_data_types.add("inventory")
                            logging.info(
                                f"[LOADING STATE] Received inventory data - progress: {self.received_data_types}/{self.expected_data_types}"
                            )
                            self._check_all_data_loaded()
                        else:
                            logging.debug(f"Inventory update processed while not in loading state")

                elif msg_type == "crafting_update":
                    if "Passive Crafting" in self.tabs:
                        start_time = time.time()
                        self.tabs["Passive Crafting"].update_data(msg_data)
                        update_time = time.time() - start_time
                        logging.debug(f"Crafting tab update took {update_time:.3f}s")

                        # Check for completion celebrations
                        changes = message.get("changes", {})
                        if changes.get("crafting_completed"):
                            self._celebrate_completions(changes["crafting_completed"])

                        # Track that we've received crafting data
                        if self.is_loading:
                            self.received_data_types.add("crafting")
                            logging.debug(f"Received crafting data - progress: {self.received_data_types}")
                            self._check_all_data_loaded()

                elif msg_type == "active_crafting_update":
                    if "Active Crafting" in self.tabs:
                        start_time = time.time()
                        self.tabs["Active Crafting"].update_data(msg_data)
                        update_time = time.time() - start_time
                        logging.debug(f"Active crafting tab update took {update_time:.3f}s")

                        # Track that we've received active crafting data
                        if self.is_loading:
                            self.received_data_types.add("active_crafting")
                            logging.debug(f"Received active crafting data - progress: {self.received_data_types}")
                            self._check_all_data_loaded()

                elif msg_type == "timer_update":
                    if "Passive Crafting" in self.tabs:
                        self.tabs["Passive Crafting"].update_data(msg_data)

                elif msg_type == "crafting_timer_update":
                    if "Passive Crafting" in self.tabs:
                        # Lightweight timer update - only update time values
                        self.tabs["Passive Crafting"].update_timer_only(msg_data or {})

                elif msg_type == "tasks_update":
                    logging.debug(
                        f"MAIN WINDOW: Processing tasks_update with {len(msg_data) if isinstance(msg_data, list) else 'invalid'} items"
                    )
                    if "Traveler's Tasks" in self.tabs:
                        self.tabs["Traveler's Tasks"].update_data(msg_data)

                        # Check for task completions
                        changes = message.get("changes", {})
                        if changes.get("completed_tasks"):
                            self._celebrate_task_completions(changes["completed_tasks"])

                        # Track that we've received tasks data
                        if self.is_loading:
                            self.received_data_types.add("tasks")
                            self._check_all_data_loaded()
                    else:
                        logging.warning("MAIN WINDOW: Traveler's Tasks tab not found for tasks_update")

                elif msg_type == "compare_jobs_update":
                    if "Compare Jobs" in self.tabs:
                        start_time = time.time()
                        self.tabs["Compare Jobs"].update_data(msg_data)
                        update_time = time.time() - start_time
                        logging.debug(f"Compare jobs tab update took {update_time:.3f}s")

                        # Track that we've received active crafting data
                        if self.is_loading:
                            self.received_data_types.add("compare jobs")
                            logging.debug(f"Received compare jobs data - progress: {self.received_data_types}")
                            self._check_all_data_loaded()
                
                elif msg_type == "claim_info_update":
                    self.claim_info.update_claim_data(msg_data)

                    # Track that we've received claim info data
                    if self.is_loading:
                        self.received_data_types.add("claim_info")
                        self._check_all_data_loaded()

                elif msg_type == "claim_switching":
                    self._handle_claim_switching_message(msg_data)

                elif msg_type == "claim_switched":
                    self._handle_claim_switched_message(msg_data)

                elif msg_type == "claims_list_update":
                    self._handle_claims_list_update(msg_data)

                elif msg_type == "player_state_update":
                    self._handle_player_state_update(msg_data)

                elif msg_type == "traveler_task_timer_update":
                    self._handle_traveler_task_timer_update(msg_data)

                elif msg_type == "reference_data_loaded":
                    pass

                elif msg_type == "error":
                    messagebox.showerror("Error", msg_data)
                    logging.error(f"Error message displayed: {msg_data}")

                    # Hide loading on error
                    if self.is_loading:
                        self.hide_loading()

                else:
                    logging.warning(f"Unknown message type received: {msg_type}")

        except queue.Empty:
            pass
        except Exception as e:
            logging.error(f"Error processing data queue: {e}")
        finally:
            # Adaptive update frequency: slower during resize for better performance
            interval = 250 if self.is_resizing else 100
            self.after(interval, self.process_data_queue)

    def show_loading_with_message(self, message: str):
        """
        Shows the loading overlay with a custom image and message for claim switching.
        """
        # Update loading message
        self.loading_message.configure(text=message)

        # Ensure the loading image is visible (it's already loaded in _create_loading_overlay)
        # The existing image will show during claim switching

        # Show loading overlay
        self.show_loading()

        # Clear tab data so tables are empty
        self._clear_all_tab_data()

    def update_loading_message(self, message: str):
        """
        Updates the loading message without changing loading state.

        Args:
            message: New loading message
        """
        if self.is_loading:
            self.loading_message.configure(text=message)

    def _check_all_data_loaded(self):
        """
        Check if all expected data types have been received and hide loading if so.
        Only hides loading if we're not in the middle of a claim switch.
        """
        logging.debug(
            f"[LOADING STATE] Checking data completeness - is_loading: {self.is_loading}, received: {self.received_data_types}, expected: {self.expected_data_types}"
        )

        if self.is_loading and self.received_data_types >= self.expected_data_types:
            # Only hide loading if we have actual data and not switching claims
            claim_switching = getattr(self.claim_info, "claim_switching", False)
            logging.info(f"[LOADING STATE] All data received! Claim switching: {claim_switching}")

            if not claim_switching:
                logging.info(f"[LOADING STATE] Hiding loading overlay - all initial data loaded: {self.received_data_types}")
                self.hide_loading()
            else:
                logging.info(f"[LOADING STATE] Not hiding loading overlay - claim switch in progress")
        else:
            missing_types = self.expected_data_types - self.received_data_types
            logging.debug(f"[LOADING STATE] Still waiting for data types: {missing_types}")

    def _reset_loading_state_for_switch(self):
        """Resets loading state for a new claim switch."""
        self.is_loading = True
        self.received_data_types = set()

    def get_current_claim_info(self) -> dict:
        """Returns current claim information for debugging."""
        if hasattr(self.data_service, "get_current_claim_info"):
            return self.data_service.get_current_claim_info()
        return {}
