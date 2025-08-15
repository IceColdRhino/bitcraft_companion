import customtkinter as ctk
import logging
from tkinter import ttk


class JobPopup(ctk.CTkToplevel):
    """A detailed popup window for seeing more info on a specific job."""

    def __init__(self, parent, cell, job_data,):# current_selection, callback, custom_key=None):
        super().__init__(parent)

        self.title(job_data["job"])
        self.geometry("350x500")

        # Make window resizable
        self.resizable(True, True)

        self.table_headers = ["Item",
                              "Rarity",
                              "Quantity",
                              "Price Window",
                              "Sale Price",
                              "Job Value",
                              ]
        self.column_widths = {
            "Item": 100,
            "Rarity": 100,
            "Quantity": 100,
            "Price Window": 100,
            "Sale Price": 100,
            "Job Value": 100,
        }

        self._create_widgets(job_data)

    def _create_widgets(self,job_data):
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



        textbox = ctk.CTkTextbox(self)
        textbox.grid(row=0, column=0)
        text_str = ""
        for key in list(job_data.keys()):
            text_str += f"{key}: {job_data[key]}\n"
        textbox.insert("0.0",text_str)

        self.input_label = ctk.CTkLabel(self,text="Inputs",width=100,height=100)
        self.input_label.grid(row=7,column=0)

        self.input_tree = ttk.Treeview(self,columns=self.table_headers,show="tree headings")
        self.input_tree.grid(row=8,column=0,sticky="s")
        for header in self.table_headers:
            self.input_tree.heading(header, text=header, anchor="w")
            self.input_tree.column(header, width=self.column_widths.get(header, 100), minwidth=50, anchor="w")
        self.input_tree.column("#0", width=20, minwidth=20, stretch=False, anchor="center")
        self.input_tree.heading("#0", text="", anchor="w")
        for entry in job_data["inputs"]:
            self.input_tree.insert("","end", values=entry)

        self.output_label = ctk.CTkLabel(self,text="Outputs",width=100,height=100)
        self.output_label.grid(row=9,column=0)

        self.output_tree = ttk.Treeview(self,columns=self.table_headers,show="tree headings")
        self.output_tree.grid(row=10,column=0,sticky="s")
        for header in self.table_headers:
            self.output_tree.heading(header, text=header, anchor="w")
            self.output_tree.column(header, width=self.column_widths.get(header, 100), minwidth=50, anchor="w")
        self.output_tree.column("#0", width=20, minwidth=20, stretch=False, anchor="center")
        self.output_tree.heading("#0", text="", anchor="w")
        for entry in job_data["outputs"]:
            self.output_tree.insert("","end", values=entry)

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.grid_rowconfigure(4, weight=1)
        self.grid_rowconfigure(5, weight=1)
        self.grid_rowconfigure(6, weight=1)
        self.grid_rowconfigure(7, weight=1)
        self.grid_rowconfigure(8, weight=1)
        self.grid_rowconfigure(9, weight=1)
        self.grid_rowconfigure(10, weight=1)
        self.grid_columnconfigure(0, weight=1)

    # def _create_widgets(self, current_selection):
    #     """Creates all the filter popup widgets."""

    #     # Search section
    #     search_frame = ctk.CTkFrame(self, fg_color="transparent")
    #     search_frame.pack(fill="x", padx=10, pady=(10, 5))

    #     ctk.CTkLabel(search_frame, text="Search:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
    #     self.search_entry = ctk.CTkEntry(
    #         search_frame, textvariable=self.search_var, placeholder_text="Type to filter options...", height=32
    #     )
    #     self.search_entry.pack(fill="x", pady=(5, 0))

    #     # Select/Clear All buttons
    #     select_frame = ctk.CTkFrame(self, fg_color="transparent")
    #     select_frame.pack(fill="x", padx=10, pady=5)

    #     self.select_all_btn = ctk.CTkButton(
    #         select_frame, text="Select All", command=self._select_all, width=100, height=28, font=ctk.CTkFont(size=11)
    #     )
    #     self.select_all_btn.pack(side="left", padx=(0, 5))

    #     self.clear_all_btn = ctk.CTkButton(
    #         select_frame,
    #         text="Clear All",
    #         command=self._clear_all,
    #         width=100,
    #         height=28,
    #         font=ctk.CTkFont(size=11),
    #         fg_color="gray",
    #     )
    #     self.clear_all_btn.pack(side="left")

    #     # Selection count label
    #     self.count_label = ctk.CTkLabel(select_frame, text="", font=ctk.CTkFont(size=10), text_color="#888888")
    #     self.count_label.pack(side="right")

    #     # Scrollable checkbox list
    #     self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="#2a2d2e")
    #     self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=5)

    #     # Create checkboxes for all unique values
    #     self.checkboxes = []
    #     self.visible_checkboxes = []  # Track currently visible checkboxes

    #     for value in self.unique_values:
    #         is_selected = value in current_selection
    #         var = ctk.StringVar(value=value if is_selected else "")

    #         cb = ctk.CTkCheckBox(
    #             self.scrollable_frame, text=value, variable=var, onvalue=value, offvalue="", command=self._update_count_label
    #         )
    #         cb.pack(anchor="w", padx=5, pady=1)

    #         self.check_vars[value] = var
    #         self.checkboxes.append(cb)
    #         self.visible_checkboxes.append(cb)

    #     # Action buttons
    #     btn_frame = ctk.CTkFrame(self, fg_color="transparent")
    #     btn_frame.pack(fill="x", padx=10, pady=10)

    #     self.apply_btn = ctk.CTkButton(
    #         btn_frame, text="Apply", command=self._apply_filters, width=100, fg_color="#1f6aa5", hover_color="#2c7bc7"
    #     )
    #     self.apply_btn.pack(side="right", padx=(5, 0))

    #     cancel_btn = ctk.CTkButton(
    #         btn_frame, text="Cancel", command=self.destroy, width=100, fg_color="gray", hover_color="#666666"
    #     )
    #     cancel_btn.pack(side="right")

    #     # Initial count update
    #     self._update_count_label()

    #     # Bind Enter/Escape keys
    #     self.bind("<Return>", lambda e: self._apply_filters())
    #     self.bind("<Escape>", lambda e: self.destroy())

    # def _on_search(self, *args):
    #     """Filters the visible checkboxes based on search term."""
    #     search_term = self.search_var.get().lower()
    #     self.visible_checkboxes = []

    #     for cb in self.checkboxes:
    #         cb_text = cb.cget("text").lower()
    #         if search_term in cb_text:
    #             cb.pack(anchor="w", padx=5, pady=1)
    #             self.visible_checkboxes.append(cb)
    #         else:
    #             cb.pack_forget()

    #     # Update select/clear all buttons to only affect visible items
    #     self._update_select_buttons()

    # def _select_all(self):
    #     """Selects all currently visible checkboxes."""
    #     for cb in self.visible_checkboxes:
    #         value = cb.cget("text")
    #         self.check_vars[value].set(value)
    #     self._update_count_label()

    # def _clear_all(self):
    #     """Clears all currently visible checkboxes."""
    #     for cb in self.visible_checkboxes:
    #         value = cb.cget("text")
    #         self.check_vars[value].set("")
    #     self._update_count_label()

    # def _update_select_buttons(self):
    #     """Updates the select/clear all button states based on visible items."""
    #     if not self.visible_checkboxes:
    #         self.select_all_btn.configure(state="disabled")
    #         self.clear_all_btn.configure(state="disabled")
    #         return

    #     self.select_all_btn.configure(state="normal")
    #     self.clear_all_btn.configure(state="normal")

    #     # Check if all visible items are selected
    #     visible_selected = sum(1 for cb in self.visible_checkboxes if self.check_vars[cb.cget("text")].get())

    #     if visible_selected == len(self.visible_checkboxes):
    #         self.select_all_btn.configure(text="✓ All Selected", fg_color="#4CAF50")
    #     else:
    #         self.select_all_btn.configure(text="Select All", fg_color="#1f6aa5")

    # def _update_count_label(self):
    #     """Updates the selection count label."""
    #     selected_count = sum(1 for var in self.check_vars.values() if var.get())
    #     total_count = len(self.unique_values)
    #     visible_count = len(self.visible_checkboxes)

    #     if self.search_var.get():
    #         self.count_label.configure(text=f"{selected_count}/{total_count} selected ({visible_count} shown)")
    #     else:
    #         self.count_label.configure(text=f"{selected_count}/{total_count} selected")

    #     self._update_select_buttons()

    # def _apply_filters(self):
    #     """Applies the selected filters and closes the popup."""
    #     selected_values = {value for value, var in self.check_vars.items() if var.get()}

    #     # If nothing is selected, treat as "select all" (Google Sheets behavior)
    #     if not selected_values:
    #         selected_values = set(self.unique_values)

    #     self.callback(self.header, selected_values)
    #     self.destroy()
