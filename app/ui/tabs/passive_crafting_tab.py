import logging
from typing import Dict, List

import customtkinter as ctk
from tkinter import Menu, ttk

from app.ui.components.filter_popup import FilterPopup
from app.ui.components.optimized_table_mixin import OptimizedTableMixin
from app.ui.styles import TreeviewStyles
from app.ui.themes import get_color, register_theme_callback
from app.services.search_parser import SearchParser


class PassiveCraftingTab(ctk.CTkFrame, OptimizedTableMixin):
    """The tab for displaying passive crafting status with item-focused, expandable rows."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        
        # Register for theme change notifications
        register_theme_callback(self._on_theme_changed)

        # Updated headers for new job-based format
        self.headers = ["Item", "Tier", "Quantity", "Tag", "Jobs", "Time Remaining", "Crafter", "Building"]
        self.all_data: List[Dict] = []
        self.filtered_data: List[Dict] = []

        self.sort_column = "Item"
        self.sort_reverse = False
        self.active_filters: Dict[str, set] = {}
        
        # Initialize search parser
        self.search_parser = SearchParser()
        self.clicked_header = None

        # Track expansion state for better user experience
        self.auto_expand_on_first_load = False
        self.has_had_first_load = False

        self._create_widgets()
        self._create_context_menu()
        
        # Initialize optimization features after UI is created
        self.__init_optimization__(max_workers=2, max_cache_size_mb=50)

    def _create_widgets(self):
        """Creates the styled Treeview and its scrollbars."""
        style = ttk.Style()
        
        # Apply centralized styling
        TreeviewStyles.apply_treeview_style(style)
        self.v_scrollbar_style, self.h_scrollbar_style = TreeviewStyles.apply_scrollbar_style(style, "PassiveCrafting")

        # Create the Treeview
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
            "Jobs": 60,
            "Time Remaining": 120,
            "Crafter": 90,
            "Building": 200,
        }

        for header in self.headers:
            self.tree.heading(header, text=header, command=lambda h=header: self.sort_by(h), anchor="w")
            self.tree.column(header, width=column_widths.get(header, 100), minwidth=50, anchor="w")

        # Configure the tree column for expansion/collapse
        self.tree.column("#0", width=20, minwidth=20, stretch=False, anchor="center")
        self.tree.heading("#0", text="", anchor="w")

        # Configure event debouncing for better resize performance
        self.resize_timer = None
        self.cached_total_width = None

        # Bind events
        self.tree.bind("<Button-3>", self.show_header_context_menu)
        self.tree.bind("<Configure>", self.on_tree_configure)
        
    
    def _configure_status_tags(self):
        """Configure status-specific tag colors using current theme."""
        self.tree.tag_configure("ready", 
                              background=get_color("TREEVIEW_ALTERNATE"), 
                              foreground=get_color("STATUS_SUCCESS"))
        self.tree.tag_configure("crafting", 
                              background=get_color("TREEVIEW_ALTERNATE"), 
                              foreground=get_color("STATUS_IN_PROGRESS"))
    
    def _on_theme_changed(self, old_theme: str, new_theme: str):
        """Handle theme change by updating colors."""
        # Reapply treeview styling
        style = ttk.Style()
        TreeviewStyles.apply_treeview_style(style)
        
        # Reapply scrollbar styling
        if hasattr(self, 'v_scrollbar_style') and hasattr(self, 'h_scrollbar_style'):
            TreeviewStyles.apply_scrollbar_style(style, "PassiveCrafting")
        
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

        # Create filter values with special handling for different header types
        if header.lower() in ["building", "crafter"]:
            # For building and crafter, extract unique values
            unique_values = set()
            for item in self.all_data:
                # Extract values from both parent and child items
                if header.lower() == "building":
                    value = item.get("building_name", "")
                    unique_values.add(value)
                    # Also add building names from operations (child rows)
                    for operation in item.get("operations", []):
                        unique_values.add(operation.get("building_name", ""))
                elif header.lower() == "crafter":
                    value = item.get("crafter", "")
                    unique_values.add(value)
                    # Also add crafter names from operations (child rows)  
                    for operation in item.get("operations", []):
                        unique_values.add(operation.get("crafter", ""))

            filter_values = sorted(list(unique_values))
        elif header.lower() == "jobs":
            # For Jobs column, create ranges like "1", "2-3", "4-5", "6+"
            job_counts = []
            for item in self.all_data:
                jobs = item.get("total_jobs", 0)
                job_counts.append(jobs)
            
            if job_counts:
                max_jobs = max(job_counts)
                filter_values = []
                for i in range(1, min(max_jobs + 1, 7)):
                    if i == 1:
                        filter_values.append("1")
                    elif i <= 3:
                        filter_values.append(f"{i}")
                    elif i <= 5:
                        if f"{i-1}-{i}" not in [v for v in filter_values if "-" in v]:
                            filter_values.append(f"{i-1}-{i}")
                    else:
                        if "6+" not in filter_values:
                            filter_values.append("6+")
            else:
                filter_values = ["1", "2", "3+"]
        else:
            # Standard filter - extract unique values from the column
            filter_values = sorted(list(set(item.get(header, "") for item in self.all_data)))

        FilterPopup(self, header, filter_values, self.active_filters.get(header, set()), self._apply_filter)

    def _apply_filter(self, header, selected_values):
        if selected_values:
            self.active_filters[header] = selected_values
        else:
            self.active_filters.pop(header, None)  # Remove empty filters
        
        self._apply_all_filters()

    def clear_column_filter(self, header):
        """Clears the filter for a specific column."""
        self.active_filters.pop(header, None)
        self._apply_all_filters()

    def apply_filter(self):
        """Filters the master data list based on search and column filters."""
        search_text = self.app.get_search_text()
        temp_data = self.all_data[:]

        # Apply column filters first
        if self.active_filters:
            filtered_data = []
            for item in temp_data:
                include_item = True
                for filter_header, filter_values in self.active_filters.items():
                    if filter_header.lower() == "building":
                        # Check building names in item and operations
                        building_match = False
                        item_building = item.get("building_name", "")
                        if item_building in filter_values:
                            building_match = True
                        else:
                            # Check operations for building matches
                            for operation in item.get("operations", []):
                                if operation.get("building_name", "") in filter_values:
                                    building_match = True
                                    break
                        if not building_match:
                            include_item = False
                            break
                    elif filter_header.lower() == "crafter":
                        # Check crafter names in item and operations
                        crafter_match = False
                        item_crafter = item.get("crafter", "")
                        if item_crafter in filter_values:
                            crafter_match = True
                        else:
                            # Check operations for crafter matches
                            for operation in item.get("operations", []):
                                if operation.get("crafter", "") in filter_values:
                                    crafter_match = True
                                    break
                        if not crafter_match:
                            include_item = False
                            break
                    else:
                        # Standard field filtering
                        item_value = str(item.get(filter_header.lower(), ""))
                        if item_value not in filter_values:
                            include_item = False
                            break
                
                if include_item:
                    filtered_data.append(item)
            temp_data = filtered_data

        # Apply keyword-based search
        if search_text:
            parsed_query = self.search_parser.parse_search_query(search_text)
            temp_data = [row for row in temp_data if self.search_parser.match_row(row, parsed_query)]

        self.filtered_data = temp_data
        self.sort_by(self.sort_column)

    def _apply_all_filters(self):
        """Apply all active filters to the data."""
        if not self.active_filters:
            self.filtered_data = self.all_data.copy()
        else:
            self.filtered_data = []
            for item in self.all_data:
                include_item = True
                for filter_header, filter_values in self.active_filters.items():
                    if filter_header.lower() == "building":
                        # Check building names in item and operations
                        building_match = False
                        item_building = item.get("building_name", "")
                        if item_building in filter_values:
                            building_match = True
                        else:
                            # Check operations for building matches
                            for operation in item.get("operations", []):
                                if operation.get("building_name", "") in filter_values:
                                    building_match = True
                                    break
                        if not building_match:
                            include_item = False
                            break
                    elif filter_header.lower() == "crafter":
                        # Check crafter names in item and operations
                        crafter_match = False
                        item_crafter = item.get("crafter", "")
                        if item_crafter in filter_values:
                            crafter_match = True
                        else:
                            # Check operations for crafter matches
                            for operation in item.get("operations", []):
                                if operation.get("crafter", "") in filter_values:
                                    crafter_match = True
                                    break
                        if not crafter_match:
                            include_item = False
                            break
                    elif filter_header.lower() == "jobs":
                        # Handle job count filtering with ranges
                        total_jobs = item.get("total_jobs", 0)
                        job_match = False
                        for job_filter in filter_values:
                            if job_filter == "1" and total_jobs == 1:
                                job_match = True
                            elif job_filter == "2" and total_jobs == 2:
                                job_match = True
                            elif job_filter == "3" and total_jobs == 3:
                                job_match = True
                            elif job_filter == "2-3" and 2 <= total_jobs <= 3:
                                job_match = True
                            elif job_filter == "4-5" and 4 <= total_jobs <= 5:
                                job_match = True
                            elif job_filter == "6+" and total_jobs >= 6:
                                job_match = True
                            elif job_filter == "3+" and total_jobs >= 3:
                                job_match = True
                        if not job_match:
                            include_item = False
                            break
                    else:
                        # Standard column filtering
                        item_value = str(item.get(filter_header, ""))
                        if item_value not in filter_values:
                            include_item = False
                            break
                
                if include_item:
                    self.filtered_data.append(item)
        
        # Re-sort filtered data and refresh display
        self._sort_data()
        self._update_display()


    def sort_by(self, column):
        """Sort the data by the specified column."""
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        
        self._sort_data()
        self._update_display()

    def _sort_data(self):
        """Sort the filtered data by the current sort column and direction."""
        if not self.filtered_data:
            return
        
        def get_sort_key(item):
            value = item.get(self.sort_column, "")
            
            # Handle numeric columns
            if self.sort_column in ["Tier", "Quantity"]:
                try:
                    return int(value) if value else 0
                except (ValueError, TypeError):
                    return 0
            elif self.sort_column == "Jobs":
                # Sort by total jobs count
                return item.get("total_jobs", 0)
            else:
                # String sorting
                return str(value).lower()
        
        self.filtered_data.sort(key=get_sort_key, reverse=self.sort_reverse)

    def update_data(self, new_data):
        """Update the tab with new passive crafting data using optimization."""
        self._debounce_operation("data_update", self._process_data_update, new_data)

    def _process_data_update(self, new_data):
        """Process passive crafting data update with background processing for large datasets."""
        try:
            data_size = len(new_data) if new_data else 0
            logging.debug(f"[PassiveCraftingTab] Updating data - {data_size} items")

            # Use background processing for large datasets
            if new_data and len(new_data) > 50:
                self._submit_background_task(
                    "passive_crafting_processing",
                    self._process_passive_data_background,
                    self._on_passive_processing_complete,
                    self._on_passive_processing_error,
                    priority=2,
                    new_data=new_data[:]
                )
            else:
                # Synchronous processing for small datasets
                self._process_passive_data_sync(new_data)

        except Exception as e:
            logging.error(f"[PassiveCraftingTab] Error updating data: {e}")

    def _process_passive_data_background(self, new_data):
        """Background processing for passive crafting data."""
        processed_data = new_data[:] if new_data else []
        return {"processed_data": processed_data}

    def _on_passive_processing_complete(self, result):
        """Callback when background passive crafting processing completes."""
        try:
            processed_data = result["processed_data"]
            self.all_data = processed_data
            logging.info(f"[PassiveCraftingTab] Background processing completed - {len(processed_data)} items")
            
            # Apply current filters to new data
            self._apply_all_filters()
            
            # Auto-expand on first load if enabled
            if not self.has_had_first_load and self.auto_expand_on_first_load and self.filtered_data:
                self.has_had_first_load = True
                self._expand_all_items()
            elif self.has_had_first_load:
                self.has_had_first_load = True
                
        except Exception as e:
            logging.error(f"Error handling background passive crafting processing result: {e}")

    def _on_passive_processing_error(self, error):
        """Callback when background passive crafting processing fails."""
        logging.error(f"Background passive crafting processing failed: {error}")
        # Fallback to synchronous processing
        self._process_passive_data_sync(self._last_raw_data if hasattr(self, '_last_raw_data') else [])

    def _process_passive_data_sync(self, new_data):
        """Synchronous processing for passive crafting data."""
        self.all_data = new_data if new_data else []
        
        # Apply current filters to new data
        self._apply_all_filters()
        
        # Auto-expand on first load if enabled
        if not self.has_had_first_load and self.auto_expand_on_first_load and self.filtered_data:
            self.has_had_first_load = True
            self._expand_all_items()
        elif self.has_had_first_load:
            self.has_had_first_load = True

    def _update_display(self):
        """Update the TreeView display with optimization support."""
        if not self.filtered_data:
            # Clear and show empty message
            self.tree.delete(*self.tree.get_children())
            empty_item = self.tree.insert("", "end", values=["No passive crafts active", "", "", "", "", "", "", ""])
            self.tree.item(empty_item, tags=("empty",))
            return

        # Use lazy loading for large datasets
        if len(self.filtered_data) > self._lazy_load_threshold:
            self._render_lazy_loading(self.filtered_data)
        else:
            # Direct rendering for smaller datasets
            self.tree.delete(*self.tree.get_children())
            self._ui_item_cache.clear()
            
            for item in self.filtered_data:
                self._insert_tree_item(item)

    def _add_item_to_tree(self, item):
        """Add a single item with its operations to the tree."""
        # Determine item-level tag based on time remaining
        item_tag = "ready" if "READY" in item.get("time_remaining", "") else "crafting"
        
        # Create parent item
        item_values = [
            item.get("item", ""),
            item.get("tier", ""),
            item.get("total_quantity", ""),
            item.get("tag", ""),
            f"{item.get('completed_jobs', 0)}/{item.get('total_jobs', 0)}",
            item.get("time_remaining", ""),
            item.get("crafter", ""),
            item.get("building_name", ""),
        ]
        
        parent_id = self.tree.insert("", "end", values=item_values, tags=(item_tag,))
        
        # Add child operations if expandable
        if item.get("is_expandable", False):
            for operation in item.get("operations", []):
                child_tag = "ready" if operation.get("time_remaining", "") == "READY" else "crafting"
                child_values = [
                    "",  # Empty item name for child
                    "",  # Empty tier for child
                    operation.get("quantity", ""),
                    "",  # Empty tag for child
                    "",  # Empty jobs for child
                    operation.get("time_remaining", ""),
                    operation.get("crafter", ""),
                    operation.get("building_name", ""),
                ]
                self.tree.insert(parent_id, "end", values=child_values, tags=("child", child_tag))

    def _expand_all_items(self):
        """Expand all parent items in the tree."""
        def expand_recursive(item_id):
            self.tree.item(item_id, open=True)
            for child_id in self.tree.get_children(item_id):
                expand_recursive(child_id)
        
        for item_id in self.tree.get_children():
            expand_recursive(item_id)

    def destroy(self):
        """Clean up resources when tab is destroyed."""
        try:
            self.optimization_shutdown()
        except Exception as e:
            logging.error(f"Error during optimization shutdown: {e}")
        super().destroy()

    def _get_comparison_fields(self) -> List[str]:
        """Get fields to compare for change detection."""
        return ["item", "tier", "total_quantity", "tag", "total_jobs", "time_remaining", "crafter", "building_name"]

    def _generate_item_key(self, item_data):
        """Generate unique key for passive crafting items."""
        key_tuple = (
            item_data.get("item", "Unknown"),
            item_data.get("tier", 0),
            item_data.get("crafter", ""),
            item_data.get("building_name", "")
        )
        if key_tuple not in self._memory_manager["item_pool"]:
            self._memory_manager["item_pool"][key_tuple] = "|".join(str(x) for x in key_tuple)
        return self._memory_manager["item_pool"][key_tuple]

    def _insert_tree_item(self, item_data):
        """Insert passive crafting item into tree."""
        # Determine item-level tag based on time remaining
        item_tag = "ready" if "READY" in item_data.get("time_remaining", "") else "crafting"
        
        # Create parent item
        item_values = [
            item_data.get("item", ""),
            item_data.get("tier", ""),
            item_data.get("total_quantity", ""),
            item_data.get("tag", ""),
            f"{item_data.get('completed_jobs', 0)}/{item_data.get('total_jobs', 0)}",
            item_data.get("time_remaining", ""),
            item_data.get("crafter", ""),
            item_data.get("building_name", ""),
        ]
        
        parent_id = self.tree.insert("", "end", values=item_values, tags=(item_tag,))
        
        # Add child operations if expandable
        if item_data.get("is_expandable", False):
            for operation in item_data.get("operations", []):
                child_tag = "ready" if operation.get("time_remaining", "") == "READY" else "crafting"
                child_values = [
                    "",  # Empty item name for child
                    "",  # Empty tier for child
                    operation.get("quantity", ""),
                    "",  # Empty tag for child
                    "",  # Empty jobs for child
                    operation.get("time_remaining", ""),
                    operation.get("crafter", ""),
                    operation.get("building_name", ""),
                ]
                self.tree.insert(parent_id, "end", values=child_values, tags=("child", child_tag))

        item_key = self._generate_item_key(item_data)
        self._ui_item_cache[item_key] = parent_id