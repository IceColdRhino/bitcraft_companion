import customtkinter as ctk
import logging
import numpy as np
from tkinter import Menu, ttk
from typing import List, Dict
from app.ui.components.filter_popup import FilterPopup
from app.ui.components.job_popup import JobPopup


class CompareJobsTab(ctk.CTkFrame):
    """The tab for displaying active crafting status with item-focused, expandable rows."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        self.headers = ["Job",
                        "Time",
                        "Stamina",
                        "Effort",
                        "Cost",
                        "Gross",
                        "Profit",
                        "Profit Per Min",
                        "Passive"]
        self.all_data: List[Dict] = []
        self.filtered_data: List[Dict] = []

        self.sort_column = "Profit Per Min"
        self.sort_reverse = True
        self.active_filters: Dict[str, set] = {}
        self.clicked_header = None

        self._create_widgets()
        self._create_context_menu()
        self._create_job_context_menu()

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
        self.v_scrollbar_style = "CompareJobs.Vertical.TScrollbar"
        self.h_scrollbar_style = "CompareJobs.Horizontal.TScrollbar"

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
                ("active", "#1e2124"),  # Hover state
                ("pressed", "#1e2124"),  # Click/drag state
                ("disabled", "#1e2124"),  # No scroll needed state
                ("!active", "#1e2124"),  # Normal state
            ],
            troughcolor=[("active", "#2a2d2e"), ("pressed", "#2a2d2e"), ("disabled", "#2a2d2e"), ("!active", "#2a2d2e")],
            arrowcolor=[("active", "#666"), ("pressed", "#666"), ("disabled", "#666"), ("!active", "#666")],
        )
        style.map(
            self.h_scrollbar_style,
            background=[("active", "#1e2124"), ("pressed", "#1e2124"), ("disabled", "#1e2124"), ("!active", "#1e2124")],
            troughcolor=[("active", "#2a2d2e"), ("pressed", "#2a2d2e"), ("disabled", "#2a2d2e"), ("!active", "#2a2d2e")],
            arrowcolor=[("active", "#666"), ("pressed", "#666"), ("disabled", "#666"), ("!active", "#666")],
        )

        # Create the Treeview with tree structure support
        self.tree = ttk.Treeview(self, columns=self.headers, show="tree headings", style="Treeview")

        # Configure tags for different progress colors based on active crafting status
        self.tree.tag_configure("Profitable", background="#2d4a2d", foreground="#4CAF50")
        self.tree.tag_configure("Profit-Neutral", background="#3d3d2d", foreground="#FFA726")
        self.tree.tag_configure("Unprofitable", background="#3d2d2d", foreground="#AF4C4C")

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
            "Job": 100,
            "Time": 100,
            "Stamina": 100,
            "Effort": 100,
            "Cost": 100,
            "Gross": 100,
            "Profit": 100,
            "Profit Per Min": 100,
            "Passive": 50,
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
        self.tree.bind("<Button-3>", self.show_context_menu)
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

    def _create_job_context_menu(self):
        """Creates the right-click menu for individual jobs."""
        self.job_context_menu = Menu(self, tearoff=0, background="#2a2d2e", foreground="white", activebackground="#1f6aa5")
        self.job_context_menu.add_command(label="See Job Details", command=lambda: self._open_job_popup(self.clicked_row))

    def _create_context_menu(self):
        """Creates the right-click menu for column headers."""
        self.header_context_menu = Menu(self, tearoff=0, background="#2a2d2e", foreground="white", activebackground="#1f6aa5")
        self.header_context_menu.add_command(label="Filter by...", command=lambda: self._open_filter_popup(self.clicked_header))
        self.header_context_menu.add_command(label="Clear Filter", command=lambda: self.clear_column_filter(self.clicked_header))

    def show_context_menu(self, event):
        """Identifies the clicked header and displays the context menu."""
        region = self.tree.identify("region", event.x, event.y)
        if region == "heading":
            column_id = self.tree.identify_column(event.x)
            self.clicked_header = self.tree.column(column_id, "id")
            self.header_context_menu.tk_popup(event.x_root, event.y_root)
        elif region == "cell":
            row_id = self.tree.identify('item', event.x, event.y)
            self.clicked_row = self.tree.item(row_id)
            self.job_context_menu.tk_popup(event.x_root, event.y_root)

    def _open_job_popup(self, cell):
        job_id = cell["tags"][0]
        job_data = next(filter(lambda x: x["job_id"] == job_id, self.all_data), None)
        JobPopup(
            self,
            cell,
            job_data,
        )

    def _open_filter_popup(self, header):
        if not self.all_data:
            return

        # Handle special cases for filters
        if header.lower() in ["building", "crafter"]:
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

        return sorted(list(unique_values))

    def _apply_column_filter(self, header, selected_values):
        self.active_filters[header] = selected_values
        self.apply_filter()

    def clear_column_filter(self, header):
        if header in self.active_filters:
            del self.active_filters[header]
            self.apply_filter()

    def update_data(self, new_data):
        """Receives new compare jobs data and flattens it into individual operations."""
        if isinstance(new_data, list):
            # Flatten hierarchical data into individual operations
            self.all_data = self._flatten_compare_jobs_data(new_data)

        else:
            self.all_data = []

        self.apply_filter()

    def _flatten_compare_jobs_data(self, hierarchical_data):
        """
        Converts hierarchical compare jobs data into flat list of individual operations.

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
                            "job_id":item_group.get("job_id","Unknown"),
                            "job":item_group.get("job","Unknown"),
                            "time":item_group.get("time","Unknown"),
                            "stamina":item_group.get("stamina","Unknown"),
                            "durability_cost":item_group.get("durability_cost","Unknown"),
                            "building":item_group.get("building","Unknown"),
                            "skill":item_group.get("skill","Unknown"),
                            "tool":item_group.get("tool","Unknown"),
                            "inputs":item_group.get("inputs","Unknown"),
                            "xp":item_group.get("xp","Unknown"),
                            "outputs":item_group.get("outputs","Unknown"),
                            "effort":item_group.get("effort","Unknown"),
                            "use_hands": item_group.get("use_hands","Unknown"),
                            "passive": item_group.get("passive","Unknown"),
                            "cost": item_group.get("cost","Unknown"),
                            "gross": item_group.get("gross","Unknown"),
                            "profit": item_group.get("profit","Unknown"),
                            "profit_per_min": item_group.get("profit_per_min","Unknown")
                        }
                    )
                else:
                    # Create individual rows for each operation
                    for operation in operations:
                        flattened.append(
                            {
                                "job_id":operation.get("job_id","Unknown"),
                                "job":operation.get("job","Unknown"),
                                "time":operation.get("time","Unknown"),
                                "stamina":operation.get("stamina","Unknown"),
                                "durability_cost": operation.get("durability_cost","Unknown"),
                                "building": operation.get("building","Unknown"),
                                "skill": operation.get("skill","Unknown"),
                                "tool": operation.get("tool","Unknown"),
                                "inputs": operation.get("inputs","Unknown"),
                                "xp": operation.get("xp","Unknown"),
                                "outputs": operation.get("outputs","Unknown"),
                                "effort": operation.get("effort", "Unknown"),
                                "use_hands": operation.get("use_hands","Unknown"),
                                "passive": operation.get("passive","Unknown"),
                                "cost": operation.get("cost","Unknown"),
                                "gross": operation.get("gross","Unknown"),
                                "profit": operation.get("profit","Unknown"),
                                "profit_per_min": operation.get("profit_per_min","Unknown")
                            }
                        )

        except Exception as e:
            logging.error(f"Error flattening active crafting data: {e}")

        return flattened

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

        return False

    def _row_matches_search(self, operation_data, search_term):
        """Check if individual operation data matches the search term."""
        # Check main fields in the flattened operation data
        searchable_fields = ["job",
                             ]
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
        """Sorts the filtered data and re-renders the table."""
        if self.sort_column == header and reverse is None:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = header
            self.sort_reverse = reverse if reverse is not None else False

        sort_key = self.sort_column.lower().replace(" ", "_")

        if sort_key in ["time", "stamina", "effort", "passive",
                        "cost", "gross", "profit", "profit_per_min"]:
            # Numeric sorting
            self.filtered_data.sort(
                key=lambda x: float(x.get(sort_key, 0)),
                reverse=self.sort_reverse,
            )
        else:
            # String sorting
            self.filtered_data.sort(
                key=lambda x: str(x.get(sort_key, "")).lower(),
                reverse=self.sort_reverse,
            )

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
        """Render the active crafting data as individual flat rows."""
        # Clear the tree
        self.tree.delete(*self.tree.get_children())

        for operation_data in self.filtered_data:
            # Extract data for each individual operation
            id = operation_data.get("job_id","Unknown")
            job = operation_data.get("job","Unknown")
            time = np.round(operation_data.get("time","Unknown"),2)
            stamina = np.round(operation_data.get("stamina","Unknown"),2)
            durability = operation_data.get("durability_cost","Unknown")
            building = operation_data.get("building","Unknown")
            level = operation_data.get("skill","Unknown")
            tool = operation_data.get("tool","Unknown")
            inputs = operation_data.get("inputs","Unknown")
            xp = operation_data.get("xp","Unknown")
            outputs = operation_data.get("outputs","Unknown")
            effort = operation_data.get("effort","Unknown")
            hands = operation_data.get("use_hands","Unknown")
            passive = operation_data.get("passive","Unknown")
            cost = operation_data.get("cost","Unknown")
            gross = operation_data.get("gross","Unknown")
            profit = operation_data.get("profit","Unknown")
            profit_per_min = np.round(operation_data.get("profit_per_min","Unknown"),2)

            # Prepare row values
            values = [job,
                      time,
                      stamina,
                      effort,
                      cost,
                      gross,
                      profit,
                      profit_per_min,
                      passive,
                      # Above the comment will be displayed in header-order in table
                      # Below the comment will be hidden until popup
                      durability,
                      building,
                      level,
                      tool,
                      inputs,
                      xp,
                      outputs,
                      hands,
                      ]

            # Give tag to item id
            id_tag = id

            # Determine tag based on profitability for styling
            if profit > 0:
                profit_tag = "Profitable"
            elif profit < 0:
                profit_tag = "Unprofitable"
            else:
                profit_tag = "Profit-Neutral"

            # Insert as a simple flat row
            self.tree.insert("", "end", values=values, tags=(id_tag,profit_tag))

    def _get_progress_tag(self, progress):
        """Determines the appropriate tag for color coding based on progress."""
        progress_str = str(progress).lower()

        if progress_str == "ready":
            return "ready"
        else:
            return "crafting"
