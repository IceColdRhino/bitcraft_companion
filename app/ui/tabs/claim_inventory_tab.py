import logging
import time
import traceback
from typing import Dict, List, Any

import customtkinter as ctk
from tkinter import Menu, ttk

from app.ui.components.filter_popup import FilterPopup
from app.ui.components.optimized_table_mixin import OptimizedTableMixin
from app.ui.mixins.async_rendering_mixin import AsyncRenderingMixin
from app.ui.styles import TreeviewStyles
from app.ui.themes import get_color, register_theme_callback
from app.services.search_parser import SearchParser


class ClaimInventoryTab(ctk.CTkFrame, OptimizedTableMixin, AsyncRenderingMixin):
    """
    The tab for displaying claim inventory with expandable rows for multi-container items.

    THREADING MODEL:
    - Background processing: Data transformation, filtering, sorting (large datasets)
    - Main thread: All UI operations, tree rendering, layout management
    - Uses .grid() layout manager exclusively (never mix with .pack())
    """

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        # Register for theme change notifications
        register_theme_callback(self._on_theme_changed)

        self.headers = ["Item", "Tier", "Quantity", "Tag", "Containers"]
        self.all_data: List[Dict] = []
        self.filtered_data: List[Dict] = []

        self.sort_column = "Item"
        self.sort_reverse = False
        self.active_filters: Dict[str, set] = {}
        self.clicked_header = None

        # Initialize search parser
        self.search_parser = SearchParser()
        
        # Search text change detection to prevent unnecessary re-filtering
        self._last_search_text = ""

        # Change tracking for inventory quantities
        self.previous_quantities: Dict[str, int] = {}
        self.quantity_changes: Dict[str, int] = {}

        # Container-level change tracking
        self.previous_container_quantities: Dict[str, Dict[str, int]] = {}  # item_name -> {container: quantity}
        self.container_quantity_changes: Dict[str, Dict[str, int]] = {}  # item_name -> {container: change}

        # Time-based change tracking for fading
        self.change_timestamps: Dict[str, float] = {}  # item_name -> timestamp
        self.container_change_timestamps: Dict[str, Dict[str, float]] = {}  # item_name -> {container: timestamp}

        self._create_widgets()
        self._create_context_menu()

        # Initialize optimization features after UI is created
        self.__init_optimization__(max_workers=2, max_cache_size_mb=75)

        # Initialize async rendering with inventory specific settings
        self._setup_async_rendering(chunk_size=75, enable_progress=False)  # Larger chunks for simpler inventory data

        # Configure thresholds for claim inventory (typically 505+ items)
        self._configure_async_rendering(
            enabled=True,
            chunk_size=75,
            async_threshold=50,  # Use async for medium datasets
            progress_threshold=150,  # Show progress for large datasets
        )

        # Track current async operation for cancellation
        self.current_render_operation = None

        # Tab identification for visibility checks
        self._tab_name = "Claim Inventory"

    def _format_row_for_display(self, row_data: Dict) -> Dict[str, str]:
        """Format an inventory item for async display rendering with hierarchical support."""
        item_name = row_data.get("name", "")
        containers = row_data.get("containers", {})
        base_quantity = row_data.get("quantity", 0)

        # Format quantity with change indicators
        quantity_display = self._format_quantity_with_change(item_name, base_quantity)

        # Generate tags for quantity changes
        tags = []
        if item_name in self.quantity_changes:
            change = self.quantity_changes[item_name]
            if change > 0:
                tags.append("quantity_increase")
            elif change < 0:
                tags.append("quantity_decrease")

        # Base row data
        formatted_row = {
            "Item": item_name,
            "Tier": str(row_data.get("tier", "")),
            "Quantity": quantity_display,
            "Tag": str(row_data.get("tag", "")),
            "Containers": f"{len(containers)} Containers" if len(containers) > 1 else next(iter(containers.keys()), "N/A"),
            "_tags": tuple(tags),
        }

        # Add hierarchical data for multi-container items
        if len(containers) > 1:
            # Add unique identifier for this parent item
            formatted_row["_item_key"] = self._generate_item_key(row_data)

            # Create child entries for each container
            children = []
            for container_name, container_quantity in containers.items():
                container_quantity_display = self._format_quantity_with_change(item_name, container_quantity, container_name)

                # Generate tags for container-level changes
                container_tags = []
                if item_name in self.container_quantity_changes and container_name in self.container_quantity_changes[item_name]:
                    change = self.container_quantity_changes[item_name][container_name]
                    if change > 0:
                        container_tags.append("quantity_increase")
                    elif change < 0:
                        container_tags.append("quantity_decrease")

                children.append(
                    {
                        "Item": "",  # Empty for child rows
                        "Tier": "",
                        "Quantity": container_quantity_display,
                        "Tag": "",
                        "Containers": container_name,
                        "_tags": tuple(container_tags),
                    }
                )

            formatted_row["_children"] = children

        return formatted_row

    def _create_widgets(self):
        """Creates the styled Treeview and its scrollbars."""
        style = ttk.Style()

        # Apply centralized styling
        TreeviewStyles.apply_treeview_style(style)
        self.v_scrollbar_style, self.h_scrollbar_style = TreeviewStyles.apply_scrollbar_style(style, "ClaimInventory")

        # Create the Treeview with support for child items
        self.tree = ttk.Treeview(self, columns=self.headers, show="tree headings", style="Treeview")

        # Apply common tree tags
        TreeviewStyles.configure_tree_tags(self.tree)

        # Configure tags for quantity changes
        self._configure_change_tags()

        # Create scrollbars with unique styles
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview, style=self.v_scrollbar_style)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview, style=self.h_scrollbar_style)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        # Only show horizontal scrollbar when needed
        self.hsb = hsb  # Store reference
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Set up headings and initial column widths
        self._setup_column_headers()

        # Auto-resize columns when window resizes
        self.bind("<Configure>", self._on_resize)

        # Configure the tree column for native expansion - FIXED WIDTH, NOT RESIZABLE
        self.tree.column("#0", width=20, minwidth=20, stretch=False, anchor="center")
        self.tree.heading("#0", text="", anchor="w")

        # Only bind right-click for filtering
        self.tree.bind("<Button-3>", self.show_header_context_menu)

        # Bind configure event to manage horizontal scrollbar visibility
        self.tree.bind("<Configure>", self.on_tree_configure)

    def _configure_change_tags(self):
        """Configure quantity change tag colors using current theme."""
        self.tree.tag_configure("quantity_increase", foreground=get_color("ACTIVITY_INCREASE"))
        self.tree.tag_configure("quantity_decrease", foreground=get_color("ACTIVITY_DECREASE"))

    def _on_theme_changed(self, old_theme: str, new_theme: str):
        """Handle theme change by updating colors."""
        # Reapply treeview styling
        style = ttk.Style()
        TreeviewStyles.apply_treeview_style(style)

        # Reapply scrollbar styling
        if hasattr(self, "v_scrollbar_style") and hasattr(self, "h_scrollbar_style"):
            TreeviewStyles.apply_scrollbar_style(style, "ClaimInventory")

        TreeviewStyles.configure_tree_tags(self.tree)

        # Reconfigure change tags with new theme colors
        self._configure_change_tags()

    def on_tree_configure(self, event):
        """Manages horizontal scrollbar visibility based on content width."""
        total_width = sum(self.tree.column(col, "width") for col in ["#0"] + list(self.headers))
        widget_width = self.tree.winfo_width()

        if total_width > widget_width:
            self.hsb.grid(row=1, column=0, sticky="ew")
        else:
            self.hsb.grid_remove()

    def _create_context_menu(self):
        """Creates the right-click menu for column headers."""
        menu_config = TreeviewStyles.get_menu_style_config()
        self.header_context_menu = Menu(self, **menu_config)
        self.header_context_menu.add_command(label="Filter by...", command=lambda: self._open_filter_popup(self.clicked_header))
        self.header_context_menu.add_command(label="Clear Filter", command=lambda: self.clear_column_filter(self.clicked_header))

    def show_header_context_menu(self, event):
        """Identifies the clicked header and displays the context menu."""
        region = self.tree.identify("region", event.x, event.y)
        if region == "heading":
            column_id = self.tree.identify_column(event.x)
            self.clicked_header = self.tree.column(column_id, "id")
            self.header_context_menu.tk_popup(event.x_root, event.y_root)

    def _get_filter_data_for_column(self, header):
        """Gets the appropriate data for filtering based on the column."""
        if header.lower() == "containers":
            unique_containers = set()
            for row in self.all_data:
                containers = row.get("containers", {})
                if len(containers) == 1:
                    unique_containers.update(containers.keys())
                elif len(containers) > 1:
                    unique_containers.add(f"{len(containers)} Containers")
            return sorted(list(unique_containers))
        else:
            # Map header names to data keys
            header_to_key = {"Item": "name"}
            data_key = header_to_key.get(header, header.lower())
            return sorted(list(set(str(row.get(data_key, "")) for row in self.all_data)))

    def _open_filter_popup(self, header):
        if not self.all_data:
            return

        if header.lower() == "containers":
            unique_values = self._get_filter_data_for_column(header)
            filter_data = [{"containers_display": val} for val in unique_values]
            current_selection = self.active_filters.get(header, set(unique_values))
            FilterPopup(self, header, filter_data, current_selection, self._apply_column_filter, custom_key="containers_display")
        else:
            # Map header names to data keys
            header_to_key = {"Item": "name"}
            data_key = header_to_key.get(header, header.lower())
            current_selection = self.active_filters.get(header, {str(row.get(data_key, "")) for row in self.all_data})
            FilterPopup(self, header, self.all_data, current_selection, self._apply_column_filter)

    def _apply_column_filter(self, header, selected_values):
        self.active_filters[header] = selected_values
        self.apply_filter()

    def clear_column_filter(self, header):
        if header in self.active_filters:
            del self.active_filters[header]
            self.apply_filter()

    def update_data(self, new_data):
        """Receives new inventory data and processes it with optimization."""
        self._debounce_operation("data_update", self._process_data_update, new_data)

    def _process_data_update(self, new_data):
        """Process inventory data update with background processing for large datasets."""
        try:
            if isinstance(new_data, dict) and len(new_data) > 100:

                self._submit_background_task(
                    "inventory_processing",
                    self._process_inventory_data_background,
                    self._on_inventory_processing_complete,
                    self._on_inventory_processing_error,
                    priority=2,
                    new_data=new_data.copy(),
                    previous_quantities=self.previous_quantities.copy(),
                    previous_container_quantities=self.previous_container_quantities.copy(),
                )
            else:
                self._process_inventory_data_sync(new_data)

        except Exception as e:
            logging.error(f"[ClaimInventoryTab] Error updating data: {e}")

    def _process_inventory_data_background(self, new_data, previous_quantities, previous_container_quantities):
        """Background processing for inventory data transformation."""
        table_data = []
        current_quantities = {}
        current_container_quantities = {}

        for item_name, item_info in new_data.items():
            quantity = item_info.get("total_quantity", 0)
            containers = item_info.get("containers", {})

            current_quantities[item_name] = quantity
            current_container_quantities[item_name] = containers.copy()

            table_data.append(
                {
                    "name": item_name,
                    "tier": item_info.get("tier", 0),
                    "quantity": quantity,
                    "tag": item_info.get("tag", ""),
                    "containers": containers,
                }
            )

        return {
            "table_data": table_data,
            "current_quantities": current_quantities,
            "current_container_quantities": current_container_quantities,
        }

    def _on_inventory_processing_complete(self, result):
        """Callback when background inventory processing completes."""
        try:
            table_data = result["table_data"]
            current_quantities = result["current_quantities"]
            current_container_quantities = result["current_container_quantities"]

            # Calculate quantity changes
            self._calculate_quantity_changes(current_quantities, current_container_quantities)

            # Store raw data - formatting happens during rendering
            self.all_data = table_data
            logging.info(f"[ClaimInventoryTab] Background processing completed - {len(table_data)} items (with hierarchy)")

            # Notify MainWindow that data loading completed (for loading overlay detection)
            if hasattr(self.app, "is_loading") and self.app.is_loading:
                if hasattr(self.app, "received_data_types"):
                    self.app.received_data_types.add("inventory")
                    if hasattr(self.app, "_check_all_data_loaded"):
                        self.app._check_all_data_loaded()

            self.apply_filter()

        except Exception as e:
            logging.error(f"Error handling background inventory processing result: {e}")

    def _on_inventory_processing_error(self, error):
        """Callback when background inventory processing fails."""
        logging.error(f"Background inventory processing failed: {error}")
        self._process_inventory_data_sync(self._last_raw_data if hasattr(self, "_last_raw_data") else {})

    def _process_inventory_data_sync(self, new_data):
        """Synchronous processing for inventory data."""
        if isinstance(new_data, dict):
            table_data = []
            current_quantities = {}
            current_container_quantities = {}

            for item_name, item_info in new_data.items():
                quantity = item_info.get("total_quantity", 0)
                containers = item_info.get("containers", {})

                current_quantities[item_name] = quantity
                current_container_quantities[item_name] = containers.copy()

                table_data.append(
                    {
                        "name": item_name,
                        "tier": item_info.get("tier", 0),
                        "quantity": quantity,
                        "tag": item_info.get("tag", ""),
                        "containers": containers,
                    }
                )

            # Calculate quantity changes
            self._calculate_quantity_changes(current_quantities, current_container_quantities)

            # Store raw data - formatting happens during rendering
            self.all_data = table_data
            logging.info(f"[ClaimInventoryTab] Successfully processed {len(table_data)} inventory items (with hierarchy)")
        else:
            self.all_data = new_data if isinstance(new_data, list) else []
            logging.info(f"[ClaimInventoryTab] Set data to list with {len(self.all_data)} items")

        # Apply filter and render table
        self.apply_filter()
        logging.info(f"[ClaimInventoryTab] Data update completed successfully")

    def _calculate_quantity_changes(self, current_quantities, current_container_quantities):
        """Calculate changes in item quantities since last update."""
        current_time = time.time()

        # Calculate total quantity changes
        for item_name, current_qty in current_quantities.items():
            if item_name in self.previous_quantities:
                previous_qty = self.previous_quantities[item_name]
                change = current_qty - previous_qty
                if change != 0:
                    # Update change for this specific item (overwrites previous change for same item)
                    self.quantity_changes[item_name] = change
                    self.change_timestamps[item_name] = current_time
                    logging.debug(f"[ClaimInventoryTab] {item_name}: {previous_qty} -> {current_qty} ({change:+d})")

                    # Log to activity window if available
                    self._log_inventory_change(item_name, previous_qty, current_qty, change)

        # Calculate container-level changes
        for item_name, current_containers in current_container_quantities.items():
            if item_name in self.previous_container_quantities:
                previous_containers = self.previous_container_quantities[item_name]

                # Initialize container changes for this item if needed
                if item_name not in self.container_quantity_changes:
                    self.container_quantity_changes[item_name] = {}
                if item_name not in self.container_change_timestamps:
                    self.container_change_timestamps[item_name] = {}

                # Check each container for changes
                all_containers = set(current_containers.keys()) | set(previous_containers.keys())
                for container_name in all_containers:
                    current_container_qty = current_containers.get(container_name, 0)
                    previous_container_qty = previous_containers.get(container_name, 0)
                    container_change = current_container_qty - previous_container_qty

                    if container_change != 0:
                        # Update change for this specific item+container
                        self.container_quantity_changes[item_name][container_name] = container_change
                        self.container_change_timestamps[item_name][container_name] = current_time
                        logging.debug(
                            f"[ClaimInventoryTab] CONTAINER CHANGE: {item_name} in {container_name}: {previous_container_qty} -> {current_container_qty} ({container_change:+d})"
                        )
                    else:
                        # Remove any existing change for containers that didn't actually change
                        if container_name in self.container_quantity_changes.get(item_name, {}):
                            del self.container_quantity_changes[item_name][container_name]
                            logging.debug(
                                f"[ClaimInventoryTab] CLEARED CONTAINER CHANGE: {item_name} in {container_name} (no actual change)"
                            )
                        if container_name in self.container_change_timestamps.get(item_name, {}):
                            del self.container_change_timestamps[item_name][container_name]

                # Clean up empty dictionaries for this item
                if not self.container_quantity_changes.get(item_name, {}):
                    self.container_quantity_changes.pop(item_name, None)
                if not self.container_change_timestamps.get(item_name, {}):
                    self.container_change_timestamps.pop(item_name, None)

        # Clean up expired changes (older than 10 minutes)
        self._cleanup_expired_changes(current_time)

        # Update previous quantities for next comparison
        self.previous_quantities = current_quantities.copy()
        self.previous_container_quantities = current_container_quantities.copy()

    def _cleanup_expired_changes(self, current_time):
        """Remove changes older than 10 minutes."""
        expire_time = 10 * 60  # 10 minutes in seconds

        # Clean up total quantity changes
        expired_items = [item for item, timestamp in self.change_timestamps.items() if current_time - timestamp > expire_time]
        for item in expired_items:
            self.quantity_changes.pop(item, None)
            self.change_timestamps.pop(item, None)

        # Clean up container-specific changes
        for item_name in list(self.container_change_timestamps.keys()):
            expired_containers = [
                container
                for container, timestamp in self.container_change_timestamps[item_name].items()
                if current_time - timestamp > expire_time
            ]
            for container in expired_containers:
                if item_name in self.container_quantity_changes:
                    self.container_quantity_changes[item_name].pop(container, None)
                self.container_change_timestamps[item_name].pop(container, None)

            # Remove empty dictionaries
            if not self.container_change_timestamps[item_name]:
                self.container_change_timestamps.pop(item_name, None)
                self.container_quantity_changes.pop(item_name, None)

    def _format_quantity_with_change(self, item_name, base_quantity, container_name=None):
        """Format quantity display with change indicator if applicable."""
        # For container rows (child rows)
        if container_name:
            # Only show change if this specific container actually changed
            if item_name in self.container_quantity_changes and container_name in self.container_quantity_changes[item_name]:
                change = self.container_quantity_changes[item_name][container_name]
                if change > 0:
                    return f"{base_quantity} (+{change})"
                else:
                    return f"{base_quantity} ({change})"
            # If this container didn't change, show no change indicator
            return str(base_quantity)

        # For parent rows (total quantities)
        if item_name in self.quantity_changes:
            change = self.quantity_changes[item_name]
            if change > 0:
                return f"{base_quantity} (+{change})"
            else:
                return f"{base_quantity} ({change})"
        return str(base_quantity)

    def _get_change_info(self, item_name, container_name=None):
        """Get change information for styling. Returns (has_change, change_amount, is_increase)"""
        # For container rows (child rows)
        if container_name:
            # Only return change info if this specific container actually changed
            if item_name in self.container_quantity_changes and container_name in self.container_quantity_changes[item_name]:
                change = self.container_quantity_changes[item_name][container_name]
                return True, change, change > 0
            # If this container didn't change, return no change info
            return False, 0, False

        # For parent rows (total quantities)
        if item_name in self.quantity_changes:
            change = self.quantity_changes[item_name]
            return True, change, change > 0

        return False, 0, False

    def _log_inventory_change(self, item_name: str, previous_qty: int, new_qty: int, change: int):
        """Log inventory change to activity window if available."""
        try:
            # Try to get the actual player who made the change from the inventory processor
            player_name = None
            if hasattr(self.app, "data_service") and self.app.data_service:
                inventory_processor = None
                for processor in self.app.data_service.processors:
                    if hasattr(processor, "get_player_for_recent_change"):
                        inventory_processor = processor
                        break

                if inventory_processor:
                    # Get the player entity ID who made the recent change
                    player_entity_id = inventory_processor.get_player_for_recent_change()
                    if player_entity_id:
                        # Resolve entity ID to player name
                        player_name = inventory_processor._get_player_name(player_entity_id)
                        logging.debug(f"Resolved inventory change to player: {player_name} (entity_id: {player_entity_id})")
                    else:
                        logging.debug(f"Could not determine player for inventory change of {item_name}")

            # Log to background activity logger
            if hasattr(self.app, "activity_logger"):
                self.app.activity_logger.log_inventory_change(item_name, previous_qty, new_qty, change, player_name)

            # Also log to activity window if it's open
            if hasattr(self.app, "activity_window") and self.app.activity_window and self.app.activity_window.winfo_exists():
                self.app.activity_window.add_inventory_change(item_name, previous_qty, new_qty, change, player_name)
        except Exception as e:
            logging.error(f"Error logging inventory change to activity window: {e}")

    def apply_filter(self):
        """Filters the master data list based on search and column filters."""
        search_text = self.app.get_search_text()
        
        # Track search text changes for future optimizations (don't return early)
        self._last_search_text = search_text

        # Use background processing for large datasets
        background_processor = self._get_background_processor()
        if background_processor and len(self.all_data) > 500:  # Use background for large datasets
            # Submit filtering to background thread
            background_processor.submit_task(
                self._filter_data_background,
                self.all_data[:],
                search_text,
                self.active_filters.copy(),
                callback=self._on_filter_completed,
                error_callback=self._on_filter_error,
                priority=2,
                task_name="table_filtering",
            )
        else:
            # Synchronous filtering for small datasets
            self._filter_data_sync(search_text)

    def _get_background_processor(self):
        """Get the background processor from the main app's data service."""
        try:
            if hasattr(self.app, "data_service") and self.app.data_service:
                return self.app.data_service.background_processor
        except Exception as e:
            logging.debug(f"Could not access background processor: {e}")
        return None

    def _filter_data_background(self, all_data, search_text, active_filters):
        """Background thread filtering operation - works with raw inventory data."""
        temp_data = all_data[:]

        # Apply column filters first (work with raw data field names)
        if active_filters:
            for header, values in active_filters.items():
                if header.lower() == "containers":
                    temp_data = [row for row in temp_data if self._container_matches_filter(row, values)]
                else:
                    # Map header names to raw data keys
                    header_to_key = {"Item": "name", "Tier": "tier", "Quantity": "quantity", "Tag": "tag"}
                    data_key = header_to_key.get(header, header.lower())
                    temp_data = [row for row in temp_data if str(row.get(data_key, "")) in values]

        # Apply advanced search using SearchParser (work with raw data)
        if search_text:
            parsed_query = self.search_parser.parse_search_query(search_text)
            temp_data = [row for row in temp_data if self.search_parser.match_row(row, parsed_query)]

        return temp_data

    def _filter_data_sync(self, search_text):
        """Synchronous filtering operation - works with raw inventory data."""
        temp_data = self.all_data[:]

        # Apply column filters first (work with raw data field names)
        if self.active_filters:
            for header, values in self.active_filters.items():
                if header.lower() == "containers":
                    temp_data = [row for row in temp_data if self._container_matches_filter(row, values)]
                else:
                    # Map header names to raw data keys
                    header_to_key = {"Item": "name", "Tier": "tier", "Quantity": "quantity", "Tag": "tag"}
                    data_key = header_to_key.get(header, header.lower())
                    temp_data = [row for row in temp_data if str(row.get(data_key, "")) in values]

        # Apply advanced search using SearchParser (work with raw data)
        if search_text:
            parsed_query = self.search_parser.parse_search_query(search_text)
            temp_data = [row for row in temp_data if self.search_parser.match_row(row, parsed_query)]

        self.filtered_data = temp_data
        self.sort_by(self.sort_column, self.sort_reverse)

    def _on_filter_completed(self, filtered_data):
        """Callback when background filtering completes."""
        try:
            self.filtered_data = filtered_data
            # Sort the data synchronously since it's already filtered
            header_to_key = {"Item": "name"}
            sort_key = header_to_key.get(self.sort_column, self.sort_column.lower())
            is_numeric = sort_key in ["tier", "quantity"]

            self.filtered_data.sort(
                key=lambda x: (float(x.get(sort_key, 0)) if is_numeric else str(x.get(sort_key, "")).lower()),
                reverse=self.sort_reverse,
            )

            self.render_table()
            self.update_header_sort_indicators()
            logging.debug(f"[ClaimInventoryTab] Background filtering completed - {len(filtered_data)} items")
        except Exception as e:
            logging.error(f"Error handling background filter result: {e}")

    def _on_filter_error(self, error):
        """Callback when background filtering fails."""
        logging.error(f"Background filtering failed: {error}")
        self._filter_data_sync(self.app.get_search_text())

    def _container_matches_filter(self, row, selected_values):
        """Checks if a row matches the container filter."""
        containers = row.get("containers", {})

        if len(containers) == 1:
            container_name = next(iter(containers.keys()), "")
            return container_name in selected_values
        elif len(containers) > 1:
            locations_text = f"{len(containers)} Containers"
            return locations_text in selected_values

        return False

    def _container_matches_formatted_filter(self, formatted_row, selected_values):
        """Checks if a formatted row matches the container filter."""
        containers_display = formatted_row.get("Containers", "")
        return containers_display in selected_values

    def _row_matches_formatted_search(self, formatted_row, search_term):
        """Check if formatted row matches search term."""
        # Search in main display fields
        searchable_fields = ["Item", "Tier", "Quantity", "Tag", "Containers"]
        for field in searchable_fields:
            if search_term in str(formatted_row.get(field, "")).lower():
                return True

        # Also search in child containers if they exist
        children = formatted_row.get("_children", [])
        for child in children:
            for field in searchable_fields:
                if search_term in str(child.get(field, "")).lower():
                    return True

        return False


    def sort_by(self, header, reverse=None):
        """Sorts the filtered data and re-renders the table."""
        if self.sort_column == header and reverse is None:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = header
            self.sort_reverse = reverse if reverse is not None else False

        # Use background processing for large datasets
        background_processor = self._get_background_processor()
        if background_processor and len(self.filtered_data) > 500:  # Use background for large datasets
            # Submit sorting to background thread
            background_processor.submit_task(
                self._sort_data_background,
                self.filtered_data[:],
                self.sort_column,
                self.sort_reverse,
                callback=self._on_sort_completed,
                error_callback=self._on_sort_error,
                priority=2,
                task_name="table_sorting",
            )
        else:
            # Synchronous sorting for small datasets
            self._sort_data_sync()

    def _sort_data_background(self, data_to_sort, sort_column, sort_reverse):
        """Background thread sorting operation."""
        # Map header names to data keys
        header_to_key = {"Item": "name"}
        sort_key = header_to_key.get(sort_column, sort_column.lower())
        is_numeric = sort_key in ["tier", "quantity"]

        sorted_data = sorted(
            data_to_sort,
            key=lambda x: (float(x.get(sort_key, 0)) if is_numeric else str(x.get(sort_key, "")).lower()),
            reverse=sort_reverse,
        )
        return sorted_data

    def _sort_data_sync(self):
        """Synchronous sorting operation."""
        header_to_key = {"Item": "name"}
        sort_key = header_to_key.get(self.sort_column, self.sort_column.lower())
        is_numeric = sort_key in ["tier", "quantity"]

        self.filtered_data.sort(
            key=lambda x: (float(x.get(sort_key, 0)) if is_numeric else str(x.get(sort_key, "")).lower()),
            reverse=self.sort_reverse,
        )
        self.render_table()
        self.update_header_sort_indicators()

    def _on_sort_completed(self, sorted_data):
        """Callback when background sorting completes."""
        try:
            self.filtered_data = sorted_data
            self.render_table()
            self.update_header_sort_indicators()
        except Exception as e:
            logging.error(f"Error handling background sort result: {e}")

    def _on_sort_error(self, error):
        """Callback when background sorting fails."""
        logging.error(f"Background sorting failed: {error}")
        self._sort_data_sync()

    def update_header_sort_indicators(self):
        """Updates the arrows on column headers."""
        for header in self.headers:
            text = header
            if self.sort_column == header:
                text += " ↓" if not self.sort_reverse else " ↑"
            filter_indicator = " 🔎" if header in self.active_filters else ""
            self.tree.heading(header, text=text + filter_indicator)

    def render_table(self):
        """Renders table with optimization support for large datasets."""
        try:
            logging.debug(f"[ClaimInventoryTab] Starting table render - {len(self.filtered_data)} items")

            self._render_direct(self.filtered_data)

            logging.debug(f"[ClaimInventoryTab] Table render complete")

        except Exception as e:
            logging.error(f"[ClaimInventoryTab] Critical error during table render: {e}")
            logging.debug(traceback.format_exc())

    def _render_direct(self, data):
        """Render inventory data using async rendering for better performance."""
        # Cancel any existing render operation
        if self.current_render_operation:
            self._cancel_async_rendering(self.current_render_operation)
            self.current_render_operation = None

        if not data:
            # Clear and show empty message
            self.tree.delete(*self.tree.get_children())
            empty_item = self.tree.insert("", "end", values=["No items in claim inventory", "", "", "", ""])
            self.tree.item(empty_item, tags=("empty",))
            return

        def completion_callback(item_count: int):
            """Called when async rendering completes."""
            self.current_render_operation = None
            logging.debug(f"[ClaimInventoryTab] Async rendering completed - {item_count} items")

        # Start async rendering with proper formatting
        self.current_render_operation = self._render_tree_async(
            tree_widget=self.tree,
            data=data,
            columns=self.headers,
            format_row_func=self._format_row_for_display,
            completion_callback=completion_callback,
            operation_name="claim_inventory",
        )

    def _setup_column_headers(self):
        """Set up column headers and initial widths."""
        # Define base widths and scaling factors
        base_widths = {
            "Item": 200,
            "Tier": 60,
            "Quantity": 100,
            "Tag": 120,
            "Containers": 240,
        }

        for header in self.headers:
            self.tree.heading(header, text=header, command=lambda h=header: self.sort_by(h), anchor="w")
            width = base_widths.get(header, 150)
            self.tree.column(header, width=width, minwidth=max(50, width // 3), anchor="w")

    def _on_resize(self, event):
        """Handle window resize to adjust column widths."""
        if event.widget != self:
            return

        # Small delay to avoid excessive resize events
        if hasattr(self, "_resize_timer"):
            self.after_cancel(self._resize_timer)
        self._resize_timer = self.after(100, self._adjust_column_widths)

    def _adjust_column_widths(self):
        """Automatically adjust column widths based on available space and content."""
        try:
            if not hasattr(self, "tree"):
                return

            available_width = self.tree.winfo_width() - 40  # Account for scrollbar and padding
            if available_width < 100:  # Not ready yet
                return

            # Calculate total minimum width needed
            min_widths = {
                "Item": 150,
                "Tier": 50,
                "Quantity": 80,
                "Tag": 100,
                "Containers": 180,
            }

            total_min_width = sum(min_widths.values())

            if available_width > total_min_width:
                # We have extra space to distribute
                extra_space = available_width - total_min_width

                # Distribute extra space proportionally, favoring Item and Containers
                distribution = {
                    "Item": 0.35,  # 35% of extra space
                    "Tier": 0.05,  # 5% of extra space
                    "Quantity": 0.15,  # 15% of extra space
                    "Tag": 0.15,  # 15% of extra space
                    "Containers": 0.30,  # 30% of extra space
                }

                for header in self.headers:
                    base_width = min_widths[header]
                    extra_width = int(extra_space * distribution[header])
                    final_width = base_width + extra_width
                    self.tree.column(header, width=final_width)
            else:
                # Use minimum widths
                for header in self.headers:
                    self.tree.column(header, width=min_widths[header])

        except Exception as e:
            logging.debug(f"Error adjusting column widths: {e}")

    def destroy(self):
        """Clean up resources when tab is destroyed."""
        try:
            # Cancel any active async rendering operations
            if hasattr(self, "current_render_operation") and self.current_render_operation:
                self._cancel_async_rendering(self.current_render_operation)

            # Clean up async rendering resources
            self._cleanup_async_rendering()

            # Clean up optimization resources
            self.optimization_shutdown()
        except Exception as e:
            logging.error(f"Error during tab cleanup: {e}")
        super().destroy()

    def _get_comparison_fields(self) -> List[str]:
        """Get fields to compare for change detection."""
        return ["name", "tier", "quantity", "tag", "containers"]

    def _generate_item_key(self, item_data):
        """Generate unique key for inventory items."""
        key_tuple = (
            item_data.get("name", "Unknown"),
            item_data.get("tier", 0),
        )
        if key_tuple not in self._memory_manager["item_pool"]:
            self._memory_manager["item_pool"][key_tuple] = "|".join(str(x) for x in key_tuple)
        return self._memory_manager["item_pool"][key_tuple]

    def _insert_tree_item(self, item_data):
        """Insert inventory item into tree."""
        item_name = item_data.get("name", "Unknown Item")
        tier = item_data.get("tier", 0)
        quantity = item_data.get("quantity", 0)
        tag = item_data.get("tag", "")
        containers = item_data.get("containers", {})

        quantity_display = self._format_quantity_with_change(item_name, quantity)

        values = [
            item_name,
            str(tier),
            quantity_display,
            tag,
            f"{len(containers)} Containers" if len(containers) > 1 else next(iter(containers.keys()), "N/A"),
        ]

        tags = []
        if item_name in self.quantity_changes:
            change = self.quantity_changes[item_name]
            if change > 0:
                tags.append("quantity_increase")
            elif change < 0:
                tags.append("quantity_decrease")

        if len(containers) > 1:
            item_id = self.tree.insert("", "end", values=values, tags=tags)
            for container_name, container_quantity in containers.items():
                container_quantity_display = self._format_quantity_with_change(item_name, container_quantity, container_name)
                container_values = ["", "", container_quantity_display, "", container_name]

                container_tags = []
                if item_name in self.container_quantity_changes and container_name in self.container_quantity_changes[item_name]:
                    change = self.container_quantity_changes[item_name][container_name]
                    if change > 0:
                        container_tags.append("quantity_increase")
                    elif change < 0:
                        container_tags.append("quantity_decrease")

                self.tree.insert(item_id, "end", values=container_values, tags=container_tags)
        else:
            item_id = self.tree.insert("", "end", values=values, tags=tags)

        item_key = self._generate_item_key(item_data)
        self._ui_item_cache[item_key] = item_id
