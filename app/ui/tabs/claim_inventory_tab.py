import customtkinter as ctk
from tkinter import Menu, ttk
from typing import List, Dict
from app.ui.components.filter_popup import FilterPopup
import logging


class ClaimInventoryTab(ctk.CTkFrame):
    """The tab for displaying claim inventory with expandable rows for multi-container items."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        self.headers = ["Name", "Tier", "Quantity", "Tag", "Containers"]
        self.all_data: List[Dict] = []
        self.filtered_data: List[Dict] = []

        self.sort_column = "Name"
        self.sort_reverse = False
        self.active_filters: Dict[str, set] = {}
        self.clicked_header = None

        self._create_widgets()
        self._create_context_menu()

    def _create_widgets(self):
        """Creates the styled Treeview and its scrollbars."""
        style = ttk.Style()
        style.theme_use("default")

        # Configure the Treeview colors - more subtle and sleek
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

        # Sleeker, more minimal headers
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

        # Style scrollbars BEFORE creating the Treeview to ensure consistency
        style.configure(
            "Vertical.TScrollbar",
            background="#1e2124",
            borderwidth=0,
            arrowcolor="#666",
            troughcolor="#2a2d2e",
            darkcolor="#1e2124",
            lightcolor="#1e2124",
            width=12,
        )
        style.configure(
            "Horizontal.TScrollbar",
            background="#1e2124",
            borderwidth=0,
            arrowcolor="#666",
            troughcolor="#2a2d2e",
            darkcolor="#1e2124",
            lightcolor="#1e2124",
            height=12,
        )

        # Create the Treeview with support for child items
        self.tree = ttk.Treeview(self, columns=self.headers, show="tree headings", style="Treeview")

        # Configure tag for child rows with different styling
        self.tree.tag_configure("child", background="#3a3a3a")

        # Create more subtle, consistent scrollbars
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview, style="Vertical.TScrollbar")
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview, style="Horizontal.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        # Only show horizontal scrollbar when needed
        self.hsb = hsb  # Store reference
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Set up headings and column widths
        column_widths = {
            "Name": 200,
            "Tier": 60,
            "Quantity": 80,
            "Tag": 120,
            "Containers": 240,
        }

        for header in self.headers:
            self.tree.heading(header, text=header, command=lambda h=header: self.sort_by(h), anchor="w")
            self.tree.column(header, width=column_widths.get(header, 150), minwidth=50, anchor="w")

        # Configure the tree column for native expansion - FIXED WIDTH, NOT RESIZABLE
        self.tree.column("#0", width=20, minwidth=20, stretch=False, anchor="center")
        self.tree.heading("#0", text="", anchor="w")

        # Only bind right-click for filtering
        self.tree.bind("<Button-3>", self.show_header_context_menu)

        # Bind configure event to manage horizontal scrollbar visibility
        self.tree.bind("<Configure>", self.on_tree_configure)

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
            return sorted(list(set(str(row.get(header.lower(), "")) for row in self.all_data)))

    def _open_filter_popup(self, header):
        if not self.all_data:
            return

        if header.lower() == "containers":
            unique_values = self._get_filter_data_for_column(header)
            filter_data = [{"containers_display": val} for val in unique_values]
            current_selection = self.active_filters.get(header, set(unique_values))
            FilterPopup(self, header, filter_data, current_selection, self._apply_column_filter, custom_key="containers_display")
        else:
            current_selection = self.active_filters.get(header, {str(row.get(header.lower(), "")) for row in self.all_data})
            FilterPopup(self, header, self.all_data, current_selection, self._apply_column_filter)

    def _apply_column_filter(self, header, selected_values):
        self.active_filters[header] = selected_values
        self.apply_filter()

    def clear_column_filter(self, header):
        if header in self.active_filters:
            del self.active_filters[header]
            self.apply_filter()

    def update_data(self, new_data):
        """Receives new inventory data and converts it to the table format."""

        try:
            data_size = len(new_data) if isinstance(new_data, (dict, list)) else 0
            logging.info(f"[ClaimInventoryTab] Updating data - type: {type(new_data)}, size: {data_size}")

            if isinstance(new_data, dict):
                table_data = []
                for item_name, item_info in new_data.items():
                    table_data.append(
                        {
                            "name": item_name,
                            "tier": item_info.get("tier", 0),
                            "quantity": item_info.get("total_quantity", 0),
                            "tag": item_info.get("tag", ""),
                            "containers": item_info.get("containers", {}),
                        }
                    )
                self.all_data = table_data
                logging.info(f"[ClaimInventoryTab] Successfully processed {len(table_data)} inventory items")
            else:
                self.all_data = new_data if isinstance(new_data, list) else []
                logging.info(f"[ClaimInventoryTab] Set data to list with {len(self.all_data)} items")

            # Apply filter and render table
            self.apply_filter()
            logging.info(f"[ClaimInventoryTab] Data update completed successfully")

        except Exception as e:
            logging.error(f"[ClaimInventoryTab] Error updating data: {e}")
            import traceback

            logging.debug(traceback.format_exc())

    def apply_filter(self):
        """Filters the master data list based on search and column filters."""
        search_term = self.app.search_var.get().lower()
        temp_data = self.all_data[:]

        if self.active_filters:
            for header, values in self.active_filters.items():
                if header.lower() == "containers":
                    temp_data = [row for row in temp_data if self._container_matches_filter(row, values)]
                else:
                    temp_data = [row for row in temp_data if str(row.get(header.lower(), "")) in values]

        if search_term:
            temp_data = [row for row in temp_data if any(search_term in str(cell_value).lower() for cell_value in row.values())]

        self.filtered_data = temp_data
        self.sort_by(self.sort_column, self.sort_reverse)

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

    def sort_by(self, header, reverse=None):
        """Sorts the filtered data and re-renders the table."""
        if self.sort_column == header and reverse is None:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = header
            self.sort_reverse = reverse if reverse is not None else False

        sort_key = self.sort_column.lower()
        is_numeric = sort_key in ["tier", "quantity"]

        self.filtered_data.sort(
            key=lambda x: (float(x.get(sort_key, 0)) if is_numeric else str(x.get(sort_key, "")).lower()),
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
        """Clears and re-populates the Treeview with correct column layout."""

        try:
            logging.debug(f"[ClaimInventoryTab] Starting table render - {len(self.filtered_data)} items")

            # Clear existing rows
            existing_children = self.tree.get_children()
            logging.debug(f"[ClaimInventoryTab] Clearing {len(existing_children)} existing rows")
            self.tree.delete(*existing_children)

            rows_added = 0
            child_rows_added = 0
            for row_data in self.filtered_data:
                item_name = row_data.get("name", "")
                containers = row_data.get("containers", {})

                values = [
                    item_name,
                    str(row_data.get("tier", "")),
                    str(row_data.get("quantity", "")),
                    str(row_data.get("tag", "")),
                    f"{len(containers)} Containers" if len(containers) > 1 else next(iter(containers.keys()), "N/A"),
                ]

                try:
                    if len(containers) > 1:
                        item_id = self.tree.insert("", "end", values=values)
                    else:
                        item_id = self.tree.insert("", "end", text="", values=values, open=False)
                    rows_added += 1

                    if len(containers) > 1:
                        for container_name, quantity in containers.items():
                            child_values = [
                                f"  └─ {item_name}",
                                str(row_data.get("tier", "")),
                                str(quantity),
                                str(row_data.get("tag", "")),
                                container_name,
                            ]
                            self.tree.insert(item_id, "end", text="", values=child_values, tags=("child",))
                            child_rows_added += 1

                except Exception as e:
                    logging.error(f"[ClaimInventoryTab] Error adding row for {item_name}: {e}")

            logging.info(
                f"[ClaimInventoryTab] Table render complete - added {rows_added} main rows, {child_rows_added} child rows"
            )

        except Exception as e:
            logging.error(f"[ClaimInventoryTab] Critical error during table render: {e}")
            import traceback

            logging.debug(traceback.format_exc())
