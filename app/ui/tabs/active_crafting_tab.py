import logging
import time
from typing import Dict, List

import customtkinter as ctk
from tkinter import Menu, ttk

from app.ui.components.filter_popup import FilterPopup
from app.ui.components.optimized_table_mixin import OptimizedTableMixin
from app.ui.mixins.async_rendering_mixin import AsyncRenderingMixin
from app.ui.styles import TreeviewStyles
from app.ui.themes import get_color, register_theme_callback
from app.services.search_parser import SearchParser


class ActiveCraftingTab(ctk.CTkFrame, OptimizedTableMixin, AsyncRenderingMixin):
    """The tab for displaying active crafting status with item-focused, expandable rows."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        register_theme_callback(self._on_theme_changed)

        self.headers = ["Item", "Tier", "Quantity", "Tag", "Remaining Effort", "Accept Help", "Crafter", "Building"]
        self.all_data: List[Dict] = []
        self.filtered_data: List[Dict] = []

        self.sort_column = "Item"
        self.sort_reverse = False
        self.active_filters: Dict[str, set] = {}

        self.search_parser = SearchParser()
        self.clicked_header = None
        # Search text change detection to prevent unnecessary re-filtering
        self._last_search_text = ""

        self._create_widgets()
        self._create_context_menu()

        # Initialize optimization features after UI is created
        self.__init_optimization__(max_workers=2, max_cache_size_mb=50)

        # Initialize async rendering with active crafting specific settings
        self._setup_async_rendering(chunk_size=60, enable_progress=True)  # Medium chunks for active crafting data

        # Configure thresholds for active crafting (variable dataset size)
        self._configure_async_rendering(
            enabled=True,
            chunk_size=60,
            async_threshold=40,  # Use async for medium datasets
            progress_threshold=100,  # Show progress for larger datasets
        )

        # Track current async operation for cancellation
        self.current_render_operation = None

        # Tab identification for visibility checks
        self._tab_name = "Active Crafting"

    def _create_widgets(self):
        """Creates the styled Treeview and its scrollbars."""
        style = ttk.Style()

        # Apply centralized styling
        TreeviewStyles.apply_treeview_style(style)
        self.v_scrollbar_style, self.h_scrollbar_style = TreeviewStyles.apply_scrollbar_style(style, "ActiveCrafting")

        # Create the Treeview with tree structure support
        self.tree = ttk.Treeview(self, columns=self.headers, show="tree headings", style="Treeview")

        # Apply common tree tags and configure custom status tags
        TreeviewStyles.configure_tree_tags(self.tree)
        self._configure_status_tags()

        # Create scrollbars with unique styles
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview, style=self.v_scrollbar_style)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview, style=self.h_scrollbar_style)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.hsb = hsb
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Set up headings and column widths
        column_widths = {
            "Item": 180,
            "Tier": 50,
            "Quantity": 70,
            "Tag": 70,
            "Remaining Effort": 120,
            "Accept Help": 90,
            "Crafter": 90,
            "Building": 200,
        }

        for header in self.headers:
            self.tree.heading(header, text=header, command=lambda h=header: self.sort_by(h), anchor="w")
            self.tree.column(header, width=column_widths.get(header, 100), minwidth=50, anchor="w")

        # Configure the tree column
        self.tree.column("#0", width=20, minwidth=20, stretch=False, anchor="center")
        self.tree.heading("#0", text="", anchor="w")

        # Configure event debouncing for better resize performance
        self.resize_timer = None
        self.cached_total_width = None

        # Bind events
        self.tree.bind("<Button-3>", self.show_header_context_menu)
        self.tree.bind("<Configure>", self.on_tree_configure)
        self.tree.bind("<MouseWheel>", self._on_scroll)
        self.tree.bind("<Button-4>", self._on_scroll)
        self.tree.bind("<Button-5>", self._on_scroll)

    def _configure_status_tags(self):
        """Configure status-specific tag colors using current theme."""
        self.tree.tag_configure("ready", background=get_color("TREEVIEW_ALTERNATE"), foreground=get_color("STATUS_SUCCESS"))
        self.tree.tag_configure(
            "crafting", background=get_color("TREEVIEW_ALTERNATE"), foreground=get_color("STATUS_IN_PROGRESS")
        )
        self.tree.tag_configure("preparing", background=get_color("TREEVIEW_ALTERNATE"), foreground=get_color("TEXT_ACCENT"))

    def _on_theme_changed(self, old_theme: str, new_theme: str):
        """Handle theme change by updating colors."""
        # Reapply treeview styling
        style = ttk.Style()
        TreeviewStyles.apply_treeview_style(style)

        # Reapply scrollbar styling
        if hasattr(self, "v_scrollbar_style") and hasattr(self, "h_scrollbar_style"):
            TreeviewStyles.apply_scrollbar_style(style, "ActiveCrafting")

        TreeviewStyles.configure_tree_tags(self.tree)

        # Reconfigure status tags with new theme colors
        self._configure_status_tags()

    def on_tree_configure(self, event):
        """Manages horizontal scrollbar visibility with debouncing for smooth resize."""
        # Cancel previous timer if it exists
        if self.resize_timer:
            self.after_cancel(self.resize_timer)

        # Schedule the actual configure handling with debouncing
        self.resize_timer = self.after(150, self._handle_tree_configure)

    def _handle_tree_configure(self):
        """Actual handler for tree configure events."""
        try:
            total_width = sum(self.tree.column(col, "width") for col in ["#0"] + list(self.headers))
            widget_width = self.tree.winfo_width()

            # Only update if width actually changed to avoid unnecessary operations
            if self.cached_total_width != total_width:
                self.cached_total_width = total_width

                if total_width > widget_width:
                    self.hsb.grid(row=1, column=0, sticky="ew")
                else:
                    self.hsb.grid_remove()
        except Exception as e:
            logging.error(f"Error in tree configure handler: {e}")
        finally:
            self.resize_timer = None

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

    def _open_filter_popup(self, header):
        if not self.all_data:
            return

        # Handle special cases for filters
        if header.lower() in ["building", "crafter", "accept help"]:
            unique_values = self._get_filter_data_for_expandable_column(header)
            filter_data = [{f"{header.lower().replace(' ', '_')}_display": val} for val in unique_values]
            current_selection = self.active_filters.get(header, set(unique_values))
            FilterPopup(
                self,
                header,
                filter_data,
                current_selection,
                self._apply_column_filter,
                custom_key=f"{header.lower().replace(' ', '_')}_display",
            )
        else:
            field_name = header.lower().replace(" ", "_")
            current_selection = self.active_filters.get(header, {str(row.get(field_name, "")) for row in self.all_data})
            FilterPopup(self, header, self.all_data, current_selection, self._apply_column_filter)

    def _get_filter_data_for_expandable_column(self, header):
        """Gets unique values for expandable columns (Building/Crafter) including individual operations."""
        unique_values = set()

        for row in self.all_data:
            # Add the summary value
            summary_value = row.get(header.lower(), "")
            if summary_value:
                unique_values.add(summary_value)

            # Add individual operation values
            operations = row.get("operations", [])
            for operation in operations:
                if header.lower() == "building":
                    # For building, include building + crafter info
                    building = operation.get("building_name", "")
                    crafter = operation.get("crafter", "")
                    if building and crafter:
                        unique_values.add(f"{building} (by {crafter})")
                elif header.lower() == "crafter":
                    # For crafter, just the crafter name
                    crafter = operation.get("crafter", "")
                    if crafter:
                        unique_values.add(crafter)
                elif header.lower() == "accept help":
                    # For accept help, just the accept help value
                    accept_help = operation.get("accept_help", "")
                    if accept_help:
                        unique_values.add(accept_help)

        return sorted(list(unique_values))

    def _apply_column_filter(self, header, selected_values):
        self.active_filters[header] = selected_values
        self._tree_needs_full_rebuild = True
        self._clear_filter_caches()
        self.apply_filter()

    def clear_column_filter(self, header):
        if header in self.active_filters:
            del self.active_filters[header]
            self._tree_needs_full_rebuild = True
            self._clear_filter_caches()
            self.apply_filter()

    def update_data(self, new_data):
        """Receives new active crafting data and processes it with debouncing."""
        self._debounce_operation("data_update", self._process_data_update, new_data)

    def _process_data_update(self, new_data):
        """Process the data update after debouncing."""
        if isinstance(new_data, list):
            self._submit_background_task(
                "data_flattening", self._flatten_active_crafting_data, self._on_data_flattened, self._on_data_error, 1, new_data
            )
        else:
            if self.all_data:
                self.all_data = []
                self.apply_filter()

    def _on_data_flattened(self, new_flattened_data):
        """Callback when data flattening is complete."""
        self._pending_tasks.pop("data_flattening", None)

        if self._has_data_changed(new_flattened_data):
            self.all_data = new_flattened_data
            self._increment_data_version()

            # Notify MainWindow that data loading completed (for loading overlay detection)
            if hasattr(self.app, "is_loading") and self.app.is_loading:
                if hasattr(self.app, "received_data_types"):
                    self.app.received_data_types.add("active_crafting")
                    logging.info(f"[ActiveCraftingTab] Notified MainWindow of active crafting data completion")
                    if hasattr(self.app, "_check_all_data_loaded"):
                        self.app._check_all_data_loaded()

            self.apply_filter()

    def _on_data_error(self, error):
        """Callback when data processing fails."""
        self._pending_tasks.pop("data_flattening", None)
        logging.error(f"Background data processing failed: {error}")

    def _flatten_active_crafting_data(self, hierarchical_data):
        """
        Converts hierarchical active crafting data into flat list of individual operations.

        Args:
            hierarchical_data: List of item groups with nested operations

        Returns:
            List of individual active crafting operations
        """
        flattened = []

        try:
            for item_group in hierarchical_data:
                operations = item_group.get("operations", [])

                # If there are no operations, create a single row from the group data
                if not operations:
                    flattened.append(
                        {
                            "item": item_group.get("item", "Unknown Item"),
                            "tier": item_group.get("tier", 0),
                            "quantity": item_group.get("total_quantity", 0),
                            "tag": item_group.get("tag", "empty"),
                            "remaining_effort": item_group.get("remaining_effort", "Unknown"),
                            "accept_help": item_group.get("accept_help", "Unknown"),
                            "crafter": item_group.get("crafter", "Unknown"),
                            "building": item_group.get("building_name", "Unknown"),
                        }
                    )
                else:
                    # Create individual rows for each operation
                    for operation in operations:
                        flattened.append(
                            {
                                "item": operation.get("item", operation.get("item_name", item_group.get("item", "Unknown Item"))),
                                "tier": operation.get("tier", item_group.get("tier", 0)),
                                "quantity": operation.get("quantity", operation.get("craft_count", 1)),
                                "tag": operation.get("tag", item_group.get("tag", "empty")),
                                "remaining_effort": operation.get("remaining_effort", "Unknown"),
                                "accept_help": operation.get("accept_help", "Unknown"),
                                "crafter": operation.get("crafter", "Unknown"),
                                "building": operation.get("building_name", operation.get("building", "Unknown")),
                            }
                        )

        except Exception as e:
            logging.error(f"Error flattening active crafting data: {e}")

        return flattened

    def _generate_item_key(self, operation_data):
        """Generate a unique key for an operation with optimized string handling."""
        # Use tuple for faster hashing, convert to string only when needed
        key_tuple = (
            operation_data.get("item", "Unknown"),
            operation_data.get("tier", 0),
            operation_data.get("crafter", "Unknown"),
            operation_data.get("building", "Unknown"),
        )
        # Cache string representation
        if key_tuple not in self._memory_manager["item_pool"]:
            self._memory_manager["item_pool"][key_tuple] = "|".join(str(x) for x in key_tuple)
        return self._memory_manager["item_pool"][key_tuple]

    def _has_data_changed(self, new_data):
        """Optimized data change detection with memory-efficient hashing."""
        try:
            # Quick length check first
            if len(new_data) != len(self.all_data):
                return True

            # Use more memory-efficient comparison for large datasets
            if len(new_data) > 200:
                # For large datasets, use a simpler hash of the entire dataset
                new_data_signature = hash(
                    tuple(
                        (op.get("item", ""), op.get("tier", 0), op.get("quantity", 0), op.get("remaining_effort", ""))
                        for op in new_data
                    )
                )
                old_data_signature = getattr(self, "_last_data_signature", None)

                if new_data_signature != old_data_signature:
                    self._last_data_signature = new_data_signature
                    return True
                return False

            # For smaller datasets, use detailed per-item comparison
            new_hash = {}
            for operation in new_data:
                key = self._generate_item_key(operation)
                # Create optimized hash from display-relevant fields only
                data_tuple = (
                    operation.get("item", ""),
                    operation.get("tier", 0),
                    operation.get("quantity", 0),
                    operation.get("remaining_effort", ""),
                    operation.get("accept_help", ""),
                    operation.get("crafter", ""),
                    operation.get("building", ""),
                )
                new_hash[key] = hash(data_tuple)

            # Compare with previous hash
            if new_hash != self._last_data_hash:
                self._last_data_hash = new_hash
                return True

            return False

        except Exception as e:
            logging.error(f"Error checking data changes: {e}")
            return True  # Assume changed on error to be safe

    def apply_filter(self):
        """Filters the master data list with debouncing to prevent excessive processing."""
        # Debounce filter operations to prevent excessive processing during rapid changes
        self._debounce_operation("apply_filter", self._process_apply_filter)

    def _process_apply_filter(self):
        """Actually apply filters after debouncing."""
        search_text = self.app.get_search_text()

        # Check if search text changed - if so, trigger full rebuild
        if search_text != self._last_search_text:
            self._tree_needs_full_rebuild = True
            self._last_search_text = search_text

        # Generate cache key for current filter state
        filter_cache_key = self._generate_filter_cache_key(search_text, self.active_filters)

        # Check if we have cached results
        if filter_cache_key in self._result_cache:
            cached_result = self._result_cache[filter_cache_key]
            if cached_result["data_version"] == self._cache_keys["data_version"]:
                logging.debug(f"Using cached filter results for {len(cached_result['data'])} items")
                self.filtered_data = cached_result["data"]
                self._debounce_operation("sort_after_filter", self.sort_by, self.sort_column, self.sort_reverse)
                return

        task_id = "data_filtering"

        # Cancel any pending filtering task
        if task_id in self._pending_tasks:
            self.background_processor.cancel_task(self._pending_tasks[task_id])

        # Submit background filtering task
        bg_task_id = self.background_processor.submit_task(
            self._apply_filters_background,
            self.all_data,
            search_text,
            self.active_filters,
            callback=lambda data: self._on_filtering_complete(data, filter_cache_key),
            error_callback=self._on_filtering_error,
            priority=1,
            task_name=task_id,
        )
        self._pending_tasks[task_id] = bg_task_id

    def _apply_filters_background(self, data, search_text, active_filters):
        """Apply all filters in background thread."""
        temp_data = data[:]

        # Apply column filters first
        if active_filters:
            for header, values in active_filters.items():
                if header.lower() in ["building", "crafter", "accept help"]:
                    temp_data = [row for row in temp_data if self._expandable_column_matches_filter(row, header, values)]
                else:
                    field_name = header.lower().replace(" ", "_")
                    temp_data = [row for row in temp_data if str(row.get(field_name, "")) in values]

        # Apply keyword-based search
        if search_text:
            parsed_query = self.search_parser.parse_search_query(search_text)
            temp_data = [row for row in temp_data if self.search_parser.match_row(row, parsed_query)]

        return temp_data

    def _on_filtering_complete(self, filtered_data, cache_key):
        """Callback when filtering is complete."""
        self._pending_tasks.pop("data_filtering", None)

        # Cache the filtered results
        self._result_cache[cache_key] = {
            "data": filtered_data,
            "data_version": self._cache_keys["data_version"],
            "timestamp": time.time(),
        }

        # Clean old cache entries to prevent memory bloat
        self._cleanup_old_cache_entries()

        self.filtered_data = filtered_data
        self.sort_by(self.sort_column, self.sort_reverse)

    def _on_filtering_error(self, error):
        """Callback when filtering fails."""
        self._pending_tasks.pop("data_filtering", None)
        logging.error(f"Background filtering failed: {error}")
        # Fallback: apply basic filtering without search to prevent total failure
        self.filtered_data = self.all_data[:]
        self.sort_by(self.sort_column, self.sort_reverse)

    def _expandable_column_matches_filter(self, row, header, selected_values):
        """Checks if a row matches the filter for expandable columns (Building/Crafter)."""
        # Check summary value
        summary_value = row.get(header.lower(), "")
        if summary_value in selected_values:
            return True

        # Check individual operation values
        operations = row.get("operations", [])
        for operation in operations:
            if header.lower() == "building":
                # For building, check building + crafter combination
                building = operation.get("building_name", "")
                crafter = operation.get("crafter", "")
                if building and crafter:
                    display_name = f"{building} (by {crafter})"
                    if display_name in selected_values:
                        return True
            elif header.lower() == "crafter":
                # For crafter, just check crafter name
                crafter = operation.get("crafter", "")
                if crafter in selected_values:
                    return True
            elif header.lower() == "accept help":
                # For accept help, check accept help value
                accept_help = operation.get("accept_help", "")
                if accept_help in selected_values:
                    return True

        return False

    def _row_matches_search(self, operation_data, search_term):
        """Check if individual operation data matches the search term."""
        # Check main fields in the flattened operation data
        searchable_fields = ["item", "tag", "remaining_effort", "accept_help", "crafter", "building"]
        for field in searchable_fields:
            if search_term in str(operation_data.get(field, "")).lower():
                return True

        # Check tier and quantity as strings
        if search_term in str(operation_data.get("tier", "")).lower():
            return True
        if search_term in str(operation_data.get("quantity", "")).lower():
            return True

        return False

    def sort_by(self, header, reverse=None):
        """Sorts the filtered data in background with caching and re-renders the table."""
        if self.sort_column == header and reverse is None:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = header
            self.sort_reverse = reverse if reverse is not None else False

        sort_key = self.sort_column.lower().replace(" ", "_")

        # Sorting changes the order, so we need a full rebuild
        self._tree_needs_full_rebuild = True

        # Generate cache key for current sort state
        sort_cache_key = self._generate_sort_cache_key(self.filtered_data, sort_key, self.sort_reverse)

        # Check if we have cached sorted results
        if sort_cache_key in self._result_cache:
            cached_result = self._result_cache[sort_cache_key]
            if cached_result["data_version"] == self._cache_keys["data_version"]:
                logging.debug(f"Using cached sort results for {len(cached_result['data'])} items")
                self.filtered_data = cached_result["data"]
                self.render_table()
                self.update_header_sort_indicators()
                return

        task_id = "data_sorting"

        # Cancel any pending sorting task
        if task_id in self._pending_tasks:
            self.background_processor.cancel_task(self._pending_tasks[task_id])

        # Submit background sorting task
        bg_task_id = self.background_processor.submit_task(
            self._sort_data_background,
            self.filtered_data,
            sort_key,
            self.sort_reverse,
            callback=lambda data: self._on_sorting_complete(data, sort_cache_key),
            error_callback=self._on_sorting_error,
            priority=1,
            task_name=task_id,
        )
        self._pending_tasks[task_id] = bg_task_id

    def _sort_data_background(self, data, sort_key, sort_reverse):
        """Sort data in background thread."""
        data_copy = data[:]

        # Special sorting for remaining effort - handle READY, numeric values with commas
        if sort_key == "remaining_effort":

            def progress_sort_key(x):
                progress_str = str(x.get(sort_key, "")).strip()

                # Handle "READY" - should sort first (0 remaining effort)
                if progress_str.upper() == "READY":
                    return 0

                # Handle "Preparation" - should sort last as it hasn't started
                if progress_str.lower() == "preparation":
                    return 999999

                # Handle numeric values (possibly with commas like "5,696")
                try:
                    # Remove commas and convert to int
                    numeric_value = int(progress_str.replace(",", ""))
                    return numeric_value
                except ValueError:
                    pass

                # Handle fraction format like "current/total"
                if "/" in progress_str:
                    try:
                        parts = progress_str.split("/")
                        if len(parts) == 2:
                            current = int(parts[0].replace(",", ""))
                            total = int(parts[1].replace(",", ""))
                            if total > 0:
                                # Return remaining effort (total - current)
                                return total - current
                            else:
                                return 0
                    except ValueError:
                        pass

                # Handle percentage format
                if "%" in progress_str:
                    try:
                        percentage = int(progress_str.replace("%", ""))
                        # Convert percentage to remaining effort (100% = 0 remaining)
                        return 100 - percentage
                    except ValueError:
                        pass

                # Unknown formats sort to middle
                return 500000

            data_copy.sort(key=progress_sort_key, reverse=sort_reverse)
        elif sort_key in ["tier", "quantity"]:
            # Numeric sorting with mixed type handling
            def safe_numeric_sort_key(x):
                value = x.get(sort_key, 0)
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return 0  # Default for non-numeric values

            data_copy.sort(
                key=safe_numeric_sort_key,
                reverse=sort_reverse,
            )
        else:
            # String sorting
            data_copy.sort(
                key=lambda x: str(x.get(sort_key, "")).lower(),
                reverse=sort_reverse,
            )

        return data_copy

    def _on_sorting_complete(self, sorted_data, cache_key):
        """Callback when sorting is complete."""
        self._pending_tasks.pop("data_sorting", None)

        # Cache the sorted results
        self._result_cache[cache_key] = {
            "data": sorted_data,
            "data_version": self._cache_keys["data_version"],
            "timestamp": time.time(),
        }

        # Clean old cache entries to prevent memory bloat
        self._cleanup_old_cache_entries()

        self.filtered_data = sorted_data
        self.render_table()
        self.update_header_sort_indicators()

    def _on_sorting_error(self, error):
        """Callback when sorting fails."""
        self._pending_tasks.pop("data_sorting", None)
        logging.error(f"Background sorting failed: {error}")
        # Fallback: render without sorting to prevent total failure
        self.render_table()
        self.update_header_sort_indicators()

    def update_header_sort_indicators(self):
        """Updates the arrows on column headers."""
        for header in self.headers:
            text = header
            if self.sort_column == header:
                text += " ↓" if not self.sort_reverse else " ↑"
            filter_indicator = " 🔎" if header in self.active_filters else ""
            self.tree.heading(header, text=text + filter_indicator)

    def render_table(self):
        """Render the active crafting data with lazy loading and differential updates."""
        # Debounce render operations to prevent excessive UI updates
        self._debounce_operation("render_table", self._process_render_table)

    def _process_render_table(self):
        """Actually render the table after debouncing."""
        try:
            # Prevent rendering if update is already pending
            if self._update_pending:
                return

            self._update_pending = True

            # Check if we need a full rebuild or can do incremental updates
            if self._tree_needs_full_rebuild or not self._ui_item_cache:
                logging.debug(f"Active crafting: Full rebuild with lazy loading for {len(self.filtered_data)} items")
                self._render_table_lazy()
                self._tree_needs_full_rebuild = False
            else:
                logging.debug(f"Active crafting: Differential update for {len(self.filtered_data)} items")
                self._render_table_differential()

        except Exception as e:
            logging.error(f"Error in render_table: {e}")
            # Fall back to lazy render on error
            self._render_table_lazy()
            self._tree_needs_full_rebuild = False
        finally:
            self._update_pending = False

    def _render_table_lazy(self):
        """Enhanced rendering using async processing for large datasets."""
        # Clear the tree and cache
        self.tree.delete(*self.tree.get_children())
        self._ui_item_cache.clear()

        # Use async rendering for better performance with large datasets
        def completion_callback(operation_id=None, stats=None):
            logging.debug(f"[ActiveCraftingTab] Completed async rendering of {len(self.filtered_data)} items")

        # Start async rendering
        self.current_render_operation = self._render_tree_async(
            tree_widget=self.tree,
            data=self.filtered_data,
            columns=self.headers,
            format_row_func=self._format_row_for_display,
            completion_callback=completion_callback,
            operation_name="active_crafting",
        )

    def _schedule_lazy_load(self, remaining_items, batch_size=25):
        """Schedule lazy loading of remaining items in batches."""
        if not remaining_items:
            return

        # Load next batch
        batch = remaining_items[:batch_size]
        for operation_data in batch:
            self._insert_tree_item(operation_data)

        # Schedule next batch with small delay to keep UI responsive
        if len(remaining_items) > batch_size:
            next_batch = remaining_items[batch_size:]
            self.after(10, lambda: self._schedule_lazy_load(next_batch, batch_size))

    def _render_table_differential(self):
        """Differential update - only modify changed items."""
        # Create set of current filtered items
        current_items = set()
        current_data_map = {}

        for operation_data in self.filtered_data:
            item_key = self._generate_item_key(operation_data)
            current_items.add(item_key)
            current_data_map[item_key] = operation_data

        # Find items to remove (in UI but not in current data)
        cached_items = set(self._ui_item_cache.keys())
        items_to_remove = cached_items - current_items

        # Remove obsolete items
        for item_key in items_to_remove:
            if item_key in self._ui_item_cache:
                tree_item_id = self._ui_item_cache[item_key]
                try:
                    self.tree.delete(tree_item_id)
                except:
                    pass  # Item may have already been deleted
                del self._ui_item_cache[item_key]

        # Find items to add (in current data but not in UI)
        items_to_add = current_items - cached_items

        # Add new items
        for item_key in items_to_add:
            operation_data = current_data_map[item_key]
            self._insert_tree_item(operation_data)

        # Update existing items (check for changes in displayed values)
        items_to_update = current_items & cached_items
        for item_key in items_to_update:
            operation_data = current_data_map[item_key]
            self._update_tree_item_if_changed(item_key, operation_data)

    def _insert_tree_item(self, operation_data):
        """Insert a new item into the tree and cache."""
        # Extract data for the operation
        item_name = operation_data.get("item", "Unknown Item")
        tier = operation_data.get("tier", 0)
        quantity = operation_data.get("quantity", 0)
        tag = operation_data.get("tag", "empty")
        remaining_effort = operation_data.get("remaining_effort", "Unknown")
        accept_help = operation_data.get("accept_help", "Unknown")
        crafter = operation_data.get("crafter", "Unknown")
        building = operation_data.get("building", "Unknown")

        # Prepare row values
        values = [item_name, str(tier), str(quantity), tag, remaining_effort, accept_help, crafter, building]

        # Determine tag based on progress for styling
        progress_tag = self._get_progress_tag(remaining_effort)

        # Insert into tree
        tree_item_id = self.tree.insert("", "end", values=values, tags=(progress_tag,))

        # Cache the tree item ID for future updates
        item_key = self._generate_item_key(operation_data)
        self._ui_item_cache[item_key] = tree_item_id

    def _update_tree_item_if_changed(self, item_key, operation_data):
        """Update a tree item only if its displayed values have changed."""
        try:
            tree_item_id = self._ui_item_cache[item_key]

            # Get current values from tree
            current_values = self.tree.item(tree_item_id, "values")

            # Generate new values
            item_name = operation_data.get("item", "Unknown Item")
            tier = operation_data.get("tier", 0)
            quantity = operation_data.get("quantity", 0)
            tag = operation_data.get("tag", "empty")
            remaining_effort = operation_data.get("remaining_effort", "Unknown")
            accept_help = operation_data.get("accept_help", "Unknown")
            crafter = operation_data.get("crafter", "Unknown")
            building = operation_data.get("building", "Unknown")

            new_values = [item_name, str(tier), str(quantity), tag, remaining_effort, accept_help, crafter, building]

            # Only update if values actually changed
            if list(current_values) != new_values:
                self.tree.item(tree_item_id, values=new_values)

                # Update tags if needed
                progress_tag = self._get_progress_tag(remaining_effort)
                self.tree.item(tree_item_id, tags=(progress_tag,))

        except Exception as e:
            # Item may have been deleted, remove from cache and re-insert
            if item_key in self._ui_item_cache:
                del self._ui_item_cache[item_key]
            self._insert_tree_item(operation_data)

    def _get_progress_tag(self, progress):
        """Determines the appropriate tag for color coding based on progress."""
        progress_str = str(progress).lower()

        if progress_str == "ready":
            return "ready"
        else:
            # Map both crafting and preparing states to crafting (avoids flickering)
            return "crafting"

    def shutdown(self):
        """Clean shutdown of tab resources."""
        # Cancel any pending async operations
        if hasattr(self, "current_render_operation") and self.current_render_operation:
            self._cancel_render_operation(self.current_render_operation)

        # Clean up async rendering resources
        self._cleanup_async_rendering()

        # Shutdown optimization features
        self.optimization_shutdown()

    def _generate_filter_cache_key(self, search_text, active_filters):
        """Generate a unique cache key for filter state."""
        import hashlib

        # Create a deterministic string representation of filter state
        filter_str = f"search:{search_text}|filters:{sorted(active_filters.items())}"
        return f"filter_{hashlib.md5(filter_str.encode()).hexdigest()}"

    def _generate_sort_cache_key(self, data, sort_key, sort_reverse):
        """Generate a unique cache key for sort state."""
        import hashlib

        # Use data hash + sort parameters for cache key
        data_hash = hash(tuple(id(item) for item in data))  # Fast identity-based hash
        sort_str = f"data:{data_hash}|sort:{sort_key}|reverse:{sort_reverse}"
        return f"sort_{hashlib.md5(sort_str.encode()).hexdigest()}"

    def _clear_result_caches(self):
        """Clear all result caches when data changes."""
        self._result_cache.clear()
        logging.debug("Cleared all result caches due to data change")

    def _clear_filter_caches(self):
        """Clear only filter-related caches when filters change."""
        filter_keys = [key for key in self._result_cache.keys() if key.startswith("filter_")]
        for key in filter_keys:
            del self._result_cache[key]
        logging.debug(f"Cleared {len(filter_keys)} filter caches")

    def _cleanup_old_cache_entries(self, max_age_seconds=300, max_entries=50):
        """Advanced memory management with size-based cleanup."""
        import time
        import sys

        current_time = time.time()
        keys_to_remove = []

        # Calculate current cache size
        cache_size_estimate = self._estimate_cache_size()
        max_cache_size_bytes = self._memory_manager["max_cache_size_mb"] * 1024 * 1024

        # If cache is too large, be more aggressive with cleanup
        if cache_size_estimate > max_cache_size_bytes * self._memory_manager["cache_cleanup_threshold"]:
            max_age_seconds = max_age_seconds * 0.5  # Reduce max age
            max_entries = max_entries * 0.7  # Reduce max entries
            logging.debug(f"Aggressive cache cleanup triggered (cache size: {cache_size_estimate / 1024 / 1024:.1f}MB)")

        # Remove entries older than max_age_seconds
        for key, cache_entry in self._result_cache.items():
            if current_time - cache_entry.get("timestamp", 0) > max_age_seconds:
                keys_to_remove.append(key)

        # If still too many entries, remove oldest ones
        if len(self._result_cache) - len(keys_to_remove) > max_entries:
            remaining_items = [(k, v) for k, v in self._result_cache.items() if k not in keys_to_remove]
            remaining_items.sort(key=lambda x: x[1].get("timestamp", 0))

            # Keep only the newest max_entries
            oldest_to_remove = remaining_items[: -int(max_entries)]
            keys_to_remove.extend([k for k, v in oldest_to_remove])

        # Remove identified keys
        for key in keys_to_remove:
            del self._result_cache[key]

        # Clean up item pool if it gets too large
        if len(self._memory_manager["item_pool"]) > 1000:
            self._memory_manager["item_pool"].clear()
            logging.debug("Cleared item pool to free memory")

        if keys_to_remove:
            logging.debug(
                f"Cleaned up {len(keys_to_remove)} old cache entries, estimated freed memory: {self._estimate_freed_memory(keys_to_remove):.1f}KB"
            )

    def _estimate_cache_size(self):
        """Estimate the memory usage of the result cache."""
        try:
            import sys

            total_size = 0
            for cache_entry in self._result_cache.values():
                # Rough estimate: data size + metadata
                data_size = sys.getsizeof(cache_entry.get("data", []))
                total_size += data_size + 200  # Add overhead for metadata
            return total_size
        except Exception:
            return 0

    def _estimate_freed_memory(self, removed_keys):
        """Estimate memory freed by removing cache entries."""
        return len(removed_keys) * 10  # Rough estimate: 10KB per entry

    def _on_scroll(self, event):
        """Handle scroll events for potential lazy loading expansion."""
        # Debounce scroll events to prevent excessive processing
        self._debounce_operation("scroll_handler", self._process_scroll_event, event)

    def _process_scroll_event(self, event):
        """Process scroll events to potentially load more items."""
        try:
            # Get current scroll position
            top_fraction = self.tree.yview()[0]
            bottom_fraction = self.tree.yview()[1]

            total_items = len(self.filtered_data)
            visible_items = len(self.tree.get_children())

            # If we're near the bottom and haven't loaded all items, load more
            if bottom_fraction > 0.8 and visible_items < total_items:
                remaining_start = visible_items
                remaining_end = min(total_items, remaining_start + 50)

                batch_items = self.filtered_data[remaining_start:remaining_end]
                for operation_data in batch_items:
                    self._insert_tree_item(operation_data)

                logging.debug(f"Lazy loaded {len(batch_items)} more items ({visible_items} -> {len(self.tree.get_children())})")

        except Exception as e:
            logging.error(f"Error processing scroll event: {e}")

    def _format_row_for_display(self, item: Dict) -> Dict[str, str]:
        """Format active crafting data for display in the tree."""
        # Apply progress tag for styling
        progress_tag = self._get_progress_tag(item.get("remaining_effort", "Unknown"))

        return {
            "Item": item.get("item", "Unknown Item"),
            "Tier": str(item.get("tier", 0)),
            "Quantity": str(item.get("quantity", 0)),
            "Tag": item.get("tag", "empty"),
            "Remaining Effort": item.get("remaining_effort", "Unknown"),
            "Accept Help": item.get("accept_help", "Unknown"),
            "Crafter": item.get("crafter", "Unknown"),
            "Building": item.get("building", "Unknown"),
            "_tags": (progress_tag,),  # Special field for tree item tags
        }

    def _get_comparison_fields(self) -> List[str]:
        """Get fields to compare for change detection."""
        return ["item", "tier", "quantity", "remaining_effort", "accept_help", "crafter", "building"]

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
