import customtkinter as ctk
from app.ui.themes import get_color, register_theme_callback


class FilterPopup(ctk.CTkToplevel):
    """A Google Sheets-style popup window for setting column-specific filters."""

    def __init__(self, parent, header, all_data, current_selection, callback, custom_key=None):
        super().__init__(parent)
        self.title(f"Filter by {header}")
        self.geometry("350x500")
        self.transient(parent)
        self.grab_set()

        # Make window resizable
        self.resizable(True, True)
        
        # Apply theme colors
        self.configure(fg_color=get_color("BACKGROUND_PRIMARY"))
        
        # Store UI components for theme updates
        self.ui_components = {}
        
        # Register for theme change notifications
        register_theme_callback(self._on_theme_changed)

        self.header = header
        self.callback = callback
        self.custom_key = custom_key  # For special handling like containers

        # Ensure all_data is a list before processing
        if custom_key:
            # Use custom key for data extraction
            self.unique_values = sorted(list(set(str(row.get(custom_key, "")) for row in all_data)))
        else:
            # Standard data extraction
            field_name = header.lower().replace(" ", "_")
            self.unique_values = sorted(list(set(str(row.get(field_name, "")) for row in all_data)))

        # If no current selection provided, select all by default (Google Sheets behavior)
        if not current_selection or len(current_selection) == len(self.unique_values):
            current_selection = set(self.unique_values)

        self.check_vars = {}
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search)

        self._create_widgets(current_selection)

        # Focus on search entry for immediate typing
        self.search_entry.focus()

    def _create_widgets(self, current_selection):
        """Creates all the filter popup widgets."""

        # Search section
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=10, pady=(10, 5))

        search_label = ctk.CTkLabel(search_frame, text="Search:", font=ctk.CTkFont(size=12, weight="bold"))
        search_label.pack(anchor="w")
        self.ui_components['search_label'] = search_label
        
        self.search_entry = ctk.CTkEntry(
            search_frame, 
            textvariable=self.search_var, 
            placeholder_text="Type to filter options...", 
            height=32,
            fg_color=get_color("BACKGROUND_TERTIARY"),
            border_color=get_color("BORDER_DEFAULT"),
            text_color=get_color("TEXT_PRIMARY"),
            placeholder_text_color=get_color("TEXT_DISABLED")
        )
        self.search_entry.pack(fill="x", pady=(5, 0))
        self.ui_components['search_entry'] = self.search_entry

        # Select/Clear All buttons
        select_frame = ctk.CTkFrame(self, fg_color="transparent")
        select_frame.pack(fill="x", padx=10, pady=5)

        self.select_all_btn = ctk.CTkButton(
            select_frame, 
            text="Select All", 
            command=self._select_all, 
            width=100, 
            height=28, 
            font=ctk.CTkFont(size=11),
            fg_color=get_color("STATUS_INFO"),
            hover_color=get_color("BUTTON_HOVER"),
            text_color=get_color("TEXT_PRIMARY")
        )
        self.select_all_btn.pack(side="left", padx=(0, 5))
        self.ui_components['select_all_btn'] = self.select_all_btn

        self.clear_all_btn = ctk.CTkButton(
            select_frame,
            text="Clear All",
            command=self._clear_all,
            width=100,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color=get_color("BACKGROUND_SECONDARY"),
            hover_color=get_color("BUTTON_HOVER"),
            text_color=get_color("TEXT_PRIMARY")
        )
        self.clear_all_btn.pack(side="left")
        self.ui_components['clear_all_btn'] = self.clear_all_btn

        # Selection count label
        self.count_label = ctk.CTkLabel(
            select_frame, 
            text="", 
            font=ctk.CTkFont(size=10), 
            text_color=get_color("TEXT_SECONDARY")
        )
        self.count_label.pack(side="right")
        self.ui_components['count_label'] = self.count_label

        # Scrollable checkbox list
        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color=get_color("BACKGROUND_SECONDARY"))
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.ui_components['scrollable_frame'] = self.scrollable_frame

        # Create checkboxes for all unique values
        self.checkboxes = []
        self.visible_checkboxes = []  # Track currently visible checkboxes

        for value in self.unique_values:
            is_selected = value in current_selection
            var = ctk.StringVar(value=value if is_selected else "")

            cb = ctk.CTkCheckBox(
                self.scrollable_frame, text=value, variable=var, onvalue=value, offvalue="", command=self._update_count_label
            )
            cb.pack(anchor="w", padx=5, pady=1)

            self.check_vars[value] = var
            self.checkboxes.append(cb)
            self.visible_checkboxes.append(cb)

        # Action buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)

        self.apply_btn = ctk.CTkButton(
            btn_frame, 
            text="Apply", 
            command=self._apply_filters, 
            width=100, 
            fg_color=get_color("STATUS_SUCCESS"),
            hover_color=get_color("STATUS_SUCCESS"),
            text_color=get_color("TEXT_PRIMARY")
        )
        self.apply_btn.pack(side="right", padx=(5, 0))
        self.ui_components['apply_btn'] = self.apply_btn

        cancel_btn = ctk.CTkButton(
            btn_frame, 
            text="Cancel", 
            command=self.destroy, 
            width=100, 
            fg_color=get_color("BACKGROUND_SECONDARY"),
            hover_color=get_color("BUTTON_HOVER"),
            text_color=get_color("TEXT_PRIMARY")
        )
        cancel_btn.pack(side="right")
        self.ui_components['cancel_btn'] = cancel_btn

        # Initial count update
        self._update_count_label()

        # Bind Enter/Escape keys
        self.bind("<Return>", lambda e: self._apply_filters())
        self.bind("<Escape>", lambda e: self.destroy())

    def _on_search(self, *args):
        """Filters the visible checkboxes based on search term."""
        search_term = self.search_var.get().lower()
        self.visible_checkboxes = []

        for cb in self.checkboxes:
            cb_text = cb.cget("text").lower()
            if search_term in cb_text:
                cb.pack(anchor="w", padx=5, pady=1)
                self.visible_checkboxes.append(cb)
            else:
                cb.pack_forget()

        # Update select/clear all buttons to only affect visible items
        self._update_select_buttons()

    def _select_all(self):
        """Selects all currently visible checkboxes."""
        for cb in self.visible_checkboxes:
            value = cb.cget("text")
            self.check_vars[value].set(value)
        self._update_count_label()

    def _clear_all(self):
        """Clears all currently visible checkboxes."""
        for cb in self.visible_checkboxes:
            value = cb.cget("text")
            self.check_vars[value].set("")
        self._update_count_label()

    def _update_select_buttons(self):
        """Updates the select/clear all button states based on visible items."""
        if not self.visible_checkboxes:
            self.select_all_btn.configure(state="disabled")
            self.clear_all_btn.configure(state="disabled")
            return

        self.select_all_btn.configure(state="normal")
        self.clear_all_btn.configure(state="normal")

        # Check if all visible items are selected
        visible_selected = sum(1 for cb in self.visible_checkboxes if self.check_vars[cb.cget("text")].get())

        if visible_selected == len(self.visible_checkboxes):
            self.select_all_btn.configure(text="✓ All Selected", fg_color=get_color("STATUS_SUCCESS"))
        else:
            self.select_all_btn.configure(text="Select All", fg_color=get_color("STATUS_INFO"))

    def _update_count_label(self):
        """Updates the selection count label."""
        selected_count = sum(1 for var in self.check_vars.values() if var.get())
        total_count = len(self.unique_values)
        visible_count = len(self.visible_checkboxes)

        if self.search_var.get():
            self.count_label.configure(text=f"{selected_count}/{total_count} selected ({visible_count} shown)")
        else:
            self.count_label.configure(text=f"{selected_count}/{total_count} selected")

        self._update_select_buttons()

    def _apply_filters(self):
        """Applies the selected filters and closes the popup."""
        selected_values = {value for value, var in self.check_vars.items() if var.get()}

        # If nothing is selected, treat as "select all" (Google Sheets behavior)
        if not selected_values:
            selected_values = set(self.unique_values)

        self.callback(self.header, selected_values)
        self.destroy()
    
    def _on_theme_changed(self, old_theme: str, new_theme: str):
        """Handle theme change by updating UI colors."""
        try:
            # Update window background
            self.configure(fg_color=get_color("BACKGROUND_PRIMARY"))
            
            # Update all stored UI components
            if 'search_entry' in self.ui_components:
                self.ui_components['search_entry'].configure(
                    fg_color=get_color("BACKGROUND_TERTIARY"),
                    border_color=get_color("BORDER_DEFAULT"),
                    text_color=get_color("TEXT_PRIMARY"),
                    placeholder_text_color=get_color("TEXT_DISABLED")
                )
            
            if 'scrollable_frame' in self.ui_components:
                self.ui_components['scrollable_frame'].configure(
                    fg_color=get_color("BACKGROUND_SECONDARY")
                )
            
            if 'select_all_btn' in self.ui_components:
                self.ui_components['select_all_btn'].configure(
                    fg_color=get_color("STATUS_INFO"),
                    hover_color=get_color("BUTTON_HOVER"),
                    text_color=get_color("TEXT_PRIMARY")
                )
            
            if 'clear_all_btn' in self.ui_components:
                self.ui_components['clear_all_btn'].configure(
                    fg_color=get_color("BACKGROUND_SECONDARY"),
                    hover_color=get_color("BUTTON_HOVER"),
                    text_color=get_color("TEXT_PRIMARY")
                )
            
            if 'apply_btn' in self.ui_components:
                self.ui_components['apply_btn'].configure(
                    fg_color=get_color("STATUS_SUCCESS"),
                    hover_color=get_color("STATUS_SUCCESS"),
                    text_color=get_color("TEXT_PRIMARY")
                )
            
            if 'cancel_btn' in self.ui_components:
                self.ui_components['cancel_btn'].configure(
                    fg_color=get_color("BACKGROUND_SECONDARY"),
                    hover_color=get_color("BUTTON_HOVER"),
                    text_color=get_color("TEXT_PRIMARY")
                )
            
            if 'count_label' in self.ui_components:
                self.ui_components['count_label'].configure(
                    text_color=get_color("TEXT_SECONDARY")
                )
            
            # Update the dynamic select all button state colors
            self._update_select_buttons()
            
        except Exception as e:
            # Silent fail to avoid disrupting the filter popup functionality
            pass
