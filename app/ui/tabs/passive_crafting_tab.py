import customtkinter as ctk
import logging
from tkinter import Menu, ttk
from typing import List, Dict
from app.ui.components.filter_popup import FilterPopup


class PassiveCraftingTab(ctk.CTkFrame):
    """The tab for displaying passive crafting status with item-focused, expandable rows."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        # Updated headers for new job-based format
        self.headers = ["Item", "Tier", "Quantity", "Tag", "Jobs", "Time Remaining", "Crafter", "Building"]
        self.all_data: List[Dict] = []
        self.filtered_data: List[Dict] = []

        self.sort_column = "Item"
        self.sort_reverse = False
        self.active_filters: Dict[str, set] = {}
        self.clicked_header = None

        # Track expansion state for better user experience
        self.auto_expand_on_first_load = False
        self.has_had_first_load = False

        # Removed complex entity mapping - using simple full refresh approach

        self._create_widgets()
        self._create_context_menu()

    def _create_widgets(self):
        """Creates the styled Treeview and its scrollbars."""
        style = ttk.Style()
        style.theme_use("default")

        # Configure the Treeview colors
        style.configure(
            "Treeview",
            background="#2a2d2e",
            foreground="white",
            fieldbackground="#343638",
            borderwidth=0,
            rowheight=28,
            relief="flat",
        )
        style.map("Treeview", background=[("selected", "#1f6aa5")])

        # Configure headers
        style.configure(
            "Treeview.Heading",
            background="#1e2124",
            foreground="#e0e0e0",
            font=("Segoe UI", 11, "normal"),
            padding=(8, 6),
            relief="flat",
            borderwidth=0,
        )
        style.map("Treeview.Heading", background=[("active", "#2c5d8f")])

        # Create unique style names to prevent conflicts
        self.v_scrollbar_style = "PassiveCrafting.Vertical.TScrollbar"
        self.h_scrollbar_style = "PassiveCrafting.Horizontal.TScrollbar"
        
        # Configure custom scrollbar styles
        style.configure(
            self.v_scrollbar_style,
            background="#1e2124",
            borderwidth=0,
            arrowcolor="#666",
            troughcolor="#2a2d2e",
            darkcolor="#1e2124",
            lightcolor="#1e2124",
            width=12,
        )
        style.configure(
            self.h_scrollbar_style,
            background="#1e2124",
            borderwidth=0,
            arrowcolor="#666",
            troughcolor="#2a2d2e",
            darkcolor="#1e2124",
            lightcolor="#1e2124",
            height=12,
        )
        
        # Configure state-specific scrollbar colors to prevent grey appearance when inactive
        style.map(
            self.v_scrollbar_style,
            background=[
                ("active", "#1e2124"),      # Hover state
                ("pressed", "#1e2124"),     # Click/drag state  
                ("disabled", "#1e2124"),    # No scroll needed state
                ("!active", "#1e2124")      # Normal state
            ],
            troughcolor=[
                ("active", "#2a2d2e"),
                ("pressed", "#2a2d2e"), 
                ("disabled", "#2a2d2e"),
                ("!active", "#2a2d2e")
            ],
            arrowcolor=[
                ("active", "#666"),
                ("pressed", "#666"),
                ("disabled", "#666"), 
                ("!active", "#666")
            ]
        )
        style.map(
            self.h_scrollbar_style,
            background=[
                ("active", "#1e2124"),
                ("pressed", "#1e2124"),
                ("disabled", "#1e2124"),
                ("!active", "#1e2124")
            ],
            troughcolor=[
                ("active", "#2a2d2e"),
                ("pressed", "#2a2d2e"),
                ("disabled", "#2a2d2e"),
                ("!active", "#2a2d2e")
            ],
            arrowcolor=[
                ("active", "#666"),
                ("pressed", "#666"),
                ("disabled", "#666"),
                ("!active", "#666")
            ]
        )

        # Create the Treeview
        self.tree = ttk.Treeview(self, columns=self.headers, show="tree headings", style="Treeview")

        # Configure tags for different status colors based on time remaining
        self.tree.tag_configure("ready", background="#2d4a2d", foreground="#4CAF50")  # Green for ready
        self.tree.tag_configure("crafting", background="#3d3d2d", foreground="#FFA726")  # Orange for crafting
        self.tree.tag_configure("empty", background="#2a2d2e", foreground="#888888")  # Gray for empty
        self.tree.tag_configure("child", background="#3a3a3a")

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
            "Jobs": 80,
            "Time Remaining": 120,
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
        self.header_context_menu = Menu(self, tearoff=0, background="#2a2d2e", foreground="white", activebackground="#1f6aa5")
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
        if header.lower() in ["building", "crafter"]:
            unique_values = self._get_filter_data_for_expandable_column(header)
            filter_data = [{f"{header.lower()}_display": val} for val in unique_values]
            current_selection = self.active_filters.get(header, set(unique_values))
            FilterPopup(
                self, header, filter_data, current_selection, self._apply_column_filter, custom_key=f"{header.lower()}_display"
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
                    building = operation.get("building", "")
                    crafter = operation.get("crafter", "")
                    if building and crafter:
                        unique_values.add(f"{building} (by {crafter})")
                elif header.lower() == "crafter":
                    # For crafter, just the crafter name
                    crafter = operation.get("crafter", "")
                    if crafter:
                        unique_values.add(crafter)

        return sorted(list(unique_values))

    def _apply_column_filter(self, header, selected_values):
        self.active_filters[header] = selected_values
        self.apply_filter()

    def clear_column_filter(self, header):
        if header in self.active_filters:
            del self.active_filters[header]
            self.apply_filter()

    def update_data(self, new_data):
        """Receives new crafting data (already item-focused and grouped)."""
        if isinstance(new_data, list):
            self.all_data = new_data
        else:
            self.all_data = []

        # Apply filter and render immediately
        self.apply_filter()

    def _get_most_urgent_time(self, time_list):
        """Get the most urgent (shortest) time from a list of time strings."""
        if not time_list:
            return "Unknown"

        # Filter out empty/unknown times
        valid_times = [t for t in time_list if t and t not in ["", "Unknown", "Error"]]
        if not valid_times:
            return "Unknown"

        # If any are READY, that's the most urgent
        if "READY" in valid_times:
            return "READY"

        # Convert times to seconds for comparison
        times_in_seconds = []
        for time_str in valid_times:
            seconds = self._time_to_seconds(time_str)
            if seconds is not None and seconds >= 0:
                times_in_seconds.append((seconds, time_str))

        if not times_in_seconds:
            return valid_times[0]  # Fallback to first valid time

        # Return the shortest time (most urgent)
        shortest = min(times_in_seconds, key=lambda x: x[0])
        return shortest[1]


    def apply_filter(self):
        """Filters the master data list based on search and column filters."""
        search_term = self.app.search_var.get().lower()
        temp_data = self.all_data[:]

        if self.active_filters:
            for header, values in self.active_filters.items():
                if header.lower() in ["building", "crafter"]:
                    temp_data = [row for row in temp_data if self._expandable_column_matches_filter(row, header, values)]
                else:
                    field_name = header.lower().replace(" ", "_")
                    temp_data = [row for row in temp_data if str(row.get(field_name, "")) in values]

        if search_term:
            temp_data = [row for row in temp_data if self._row_matches_search(row, search_term)]

        self.filtered_data = temp_data
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
                building = operation.get("building", "")
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

        return False

    def _row_matches_search(self, row, search_term):
        """Checks if a row matches the search term, including operation data."""
        # Check main row data
        main_fields = ["item", "tag", "time_remaining", "crafter", "building"]
        # main_fields = ["item", "recipe", "time_remaining", "crafter", "building"]
        for field in main_fields:
            if search_term in str(row.get(field, "")).lower():
                return True

        # Check individual operation data
        operations = row.get("operations", [])
        for operation in operations:
            operation_fields = ["item_name", "tag", "time_remaining", "crafter", "building"]
            # operation_fields = ["item_name", "recipe", "time_remaining", "crafter", "building"]
            for field in operation_fields:
                if search_term in str(operation.get(field, "")).lower():
                    return True

        return False

    def sort_by(self, header, reverse=None):
        """Sorts the filtered data and re-renders the table."""
        if self.sort_column == header and reverse is None:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = header
            self.sort_reverse = reverse if reverse is not None else False

        sort_key = self.sort_column.lower().replace(" ", "_")

        # Special sorting for time remaining - convert to seconds for proper numerical sorting
        if sort_key == "time_remaining":

            def time_sort_key(x):
                time_str = str(x.get(sort_key, ""))
                if time_str == "READY":
                    return 0
                elif time_str in ["Empty", "Error", "N/A", "Unknown"]:
                    return 999999
                else:
                    return self._time_to_seconds(time_str)

            self.filtered_data.sort(key=time_sort_key, reverse=self.sort_reverse)
        elif sort_key == "jobs":
            # Special sorting for jobs column using completed_jobs and total_jobs keys
            def jobs_sort_key(x):
                completed_jobs = x.get("completed_jobs", 0)
                total_jobs = x.get("total_jobs", 1)
                
                try:
                    # Convert to numbers if they're strings
                    completed = int(completed_jobs) if completed_jobs is not None else 0
                    total = int(total_jobs) if total_jobs is not None else 1
                    
                    # Calculate completion ratio
                    completion_ratio = completed / total if total > 0 else 0
                    return (completion_ratio, total)
                except (ValueError, TypeError, ZeroDivisionError):
                    return (0, 0)
            
            self.filtered_data.sort(key=jobs_sort_key, reverse=self.sort_reverse)
        elif sort_key in ["tier", "quantity"]:
            # Numeric sorting with mixed type handling and correct data keys
            def safe_numeric_sort_key(x):
                # Use correct data key for quantity
                if sort_key == "quantity":
                    value = x.get("total_quantity", 0)
                else:
                    value = x.get(sort_key, 0)
                
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return 0  # Default for non-numeric values
            
            self.filtered_data.sort(
                key=safe_numeric_sort_key,
                reverse=self.sort_reverse,
            )
        else:
            # String sorting with correct data key mapping
            def string_sort_key(x):
                # Use correct data key for building
                if sort_key == "building":
                    value = x.get("building_name", "")
                else:
                    value = x.get(sort_key, "")
                
                return str(value).lower()
            
            self.filtered_data.sort(
                key=string_sort_key,
                reverse=self.sort_reverse,
            )

        self.update_header_sort_indicators()
        self.render_table()

    def _time_to_seconds(self, time_str):
        """Convert time string like '2h 30m 15s' to total seconds."""
        if not time_str or time_str in ["READY", "Empty", "Error", "N/A", "Unknown"]:
            return 0 if time_str == "READY" else 999999

        total_seconds = 0
        try:
            # Remove ~ prefix if present
            time_str = time_str.replace("~", "")

            # Parse formats like "2h 30m 15s", "30m 15s", "15s"
            parts = time_str.split()
            for part in parts:
                if "h" in part:
                    total_seconds += int(part.replace("h", "")) * 3600
                elif "m" in part:
                    total_seconds += int(part.replace("m", "")) * 60
                elif "s" in part:
                    total_seconds += int(part.replace("s", ""))
        except:
            return 999999  # Put parsing errors at the end

        return total_seconds

    def update_header_sort_indicators(self):
        """Updates the arrows on column headers."""
        for header in self.headers:
            text = header
            if self.sort_column == header:
                text += " ↓" if not self.sort_reverse else " ↑"
            filter_indicator = " 🔎" if header in self.active_filters else ""
            self.tree.heading(header, text=text + filter_indicator)

    def render_table(self):
        """Renders the hierarchical crafting data with mandatory two-level expansion, preserving expansion state."""
        # Save current expansion state before clearing (unless it's the first load)
        is_first_load = not self.has_had_first_load

        if self.has_had_first_load:
            expanded_items = self._save_expansion_state()
        else:
            expanded_items = set()
            self.has_had_first_load = True

        # Clear the tree
        self.tree.delete(*self.tree.get_children())

        for row_data in self.filtered_data:
            item_name = row_data.get("item", "Unknown Item")
            tier = row_data.get("tier", 0)
            quantity = row_data.get("total_quantity", 0)
            tag = row_data.get("tag", "empty")
            time_remaining = row_data.get("time_remaining", "Unknown")
            crafter = row_data.get("crafter", "Unknown")
            building = row_data.get("building_name", "Unknown")

            # New job completion counter
            completed_jobs = row_data.get("completed_jobs", 0)
            total_jobs = row_data.get("total_jobs", 1)
            jobs_display = f"{completed_jobs}/{total_jobs}"

            operations = row_data.get("operations", [])
            is_expandable = row_data.get("is_expandable", False)
            expansion_level = row_data.get("expansion_level", 0)

            # Create a unique identifier for this row to track expansion state
            row_id = f"{item_name}|{tier}|{tag}|{crafter}"

            # Prepare main row values with new Jobs column
            values = [item_name, str(tier), str(quantity), tag, jobs_display, time_remaining, crafter, building]

            # Determine tag based on time remaining
            visual_tag = self._get_time_tag(time_remaining)

            if is_expandable and operations:
                # Create expandable parent row
                parent_id = self.tree.insert("", "end", values=values, tags=(visual_tag,))

                # Determine if this item should be expanded
                should_expand = False
                if is_first_load and self.auto_expand_on_first_load:
                    # Auto-expand on first load
                    should_expand = True
                elif not is_first_load and row_id in expanded_items:
                    # Previously expanded (only check this after first load)
                    should_expand = True

                # Process child operations
                for child_data in operations:
                    self._render_child_row(parent_id, child_data, 1, row_id, expanded_items, is_first_load)

                # Apply expansion state
                if should_expand:
                    self.tree.item(parent_id, open=True)
            else:
                # Non-expandable row or no operations
                self.tree.insert("", "end", values=values, tags=(visual_tag,))

    def _save_expansion_state(self):
        """Save the current expansion state of all tree items."""
        expanded_items = set()

        def check_item(item_id):
            # Get the item's values to create identifier
            values = self.tree.item(item_id, "values")
            if values and len(values) >= 7:
                # Create identifier from item, tier, tag, crafter (new format)
                # Remove indentation from item name for child rows
                item_name = values[0].replace("  └─ ", "").replace("    └─ ", "").strip()
                item_identifier = f"{item_name}|{values[1]}|{values[3]}|{values[6]}"

                # If this item is expanded, save its identifier
                if self.tree.item(item_id, "open"):
                    expanded_items.add(item_identifier)

                # Check children recursively
                for child_id in self.tree.get_children(item_id):
                    check_item(child_id)

        # Check all top-level items
        for item_id in self.tree.get_children():
            check_item(item_id)

        return expanded_items

    def _render_child_row(self, parent_id, child_data, level, parent_row_id=None, expanded_items=None, is_first_load=False):
        """
        Renders a child row, potentially with its own children for second-level expansion.

        Args:
            parent_id: The parent tree item ID
            child_data: The child data dictionary
            level: Expansion level (1 for first level, 2 for second level)
            parent_row_id: The identifier of the parent row for expansion tracking
            expanded_items: Set of previously expanded item identifiers
            is_first_load: Whether this is the first time loading data
        """
        if expanded_items is None:
            expanded_items = set()

        # Extract child data
        item_name = child_data.get("item", child_data.get("item_name", "Unknown Item"))
        tier = child_data.get("tier", 0)
        quantity = child_data.get("quantity", 0)
        tag = child_data.get("tag", "empty")
        time_remaining = child_data.get("time_remaining", "Unknown")
        crafter = child_data.get("crafter", "Unknown")
        building = child_data.get("building_name", child_data.get("building", "Unknown"))
        is_expandable = child_data.get("is_expandable", False)
        child_operations = child_data.get("operations", [])

        # Create indentation based on level
        indent = "  " + "  " * (level - 1) + "└─ "
        indented_item_name = f"{indent}{item_name}"

        # Create identifier for this child row for expansion tracking
        child_row_id = f"{item_name}|{tier}|{tag}|{crafter}"
        if level > 1:
            child_row_id += f"|{building}"

        # Child rows don't show job completion (only individual jobs)
        jobs_display = "-"

        # Prepare child values with Jobs column
        child_values = [indented_item_name, str(tier), str(quantity), tag, jobs_display, time_remaining, crafter, building]

        # Determine tag
        child_tag = self._get_time_tag(time_remaining)

        # Insert the child row
        if is_expandable and child_operations:
            # This child has its own children (second level expansion)
            child_id = self.tree.insert(parent_id, "end", values=child_values, tags=("child", child_tag))

            # Removed complex entity mapping logic

            # Determine if this child should be expanded
            should_expand_child = False
            if is_first_load and self.auto_expand_on_first_load:
                # Auto-expand on first load
                should_expand_child = True
            elif not is_first_load and child_row_id in expanded_items:
                # Previously expanded
                should_expand_child = True

            # Add grandchildren (second level)
            for grandchild_data in child_operations:
                self._render_child_row(child_id, grandchild_data, level + 1, child_row_id, expanded_items, is_first_load)

            # Apply expansion state for this child
            if should_expand_child:
                self.tree.item(child_id, open=True)
        else:
            # Leaf node - no further expansion
            child_id = self.tree.insert(parent_id, "end", values=child_values, tags=("child", child_tag))

            # Removed complex entity mapping logic

    def _get_time_tag(self, time_remaining):
        """Determines the appropriate tag for color coding based on time remaining."""
        if time_remaining == "READY":
            return "ready"
        elif time_remaining not in ["Empty", "Unknown", "Error", "N/A"]:
            return "crafting"
        else:
            return "empty"
