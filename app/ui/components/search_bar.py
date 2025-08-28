"""
Reusable SearchBar component for BitCraft Companion.

Provides a consistent search interface with entry field, save/load/clear buttons,
placeholder management, and theme integration that can be used across the application.
"""

import logging
from typing import Optional, Callable

import customtkinter as ctk
from tkinter import messagebox

from app.ui.themes import get_color
from app.ui.components.saved_search_dialog import SaveSearchDialog, LoadSearchDialog


class SearchBarComponent(ctk.CTkFrame):
    """
    Reusable search bar component with entry field and action buttons.
    
    Features:
    - Search entry field with placeholder text
    - Save/Load/Clear search buttons
    - Theme integration and focus management
    - Keyboard shortcuts (Ctrl+Delete, Ctrl+Backspace)
    - Customizable placeholder text and button visibility
    """
    
    def __init__(
        self, 
        parent, 
        placeholder_text: str = "Search...",
        show_save_load: bool = True,
        show_clear: bool = True,
        on_search_change: Optional[Callable] = None
    ):
        """
        Initialize the search bar component.
        
        Args:
            parent: Parent widget
            placeholder_text: Text to show when search field is empty
            show_save_load: Whether to show save/load search buttons
            show_clear: Whether to show clear search button
            on_search_change: Callback function called when search text changes
        """
        super().__init__(parent, fg_color="transparent")
        
        self.placeholder_text = placeholder_text
        self.show_save_load = show_save_load
        self.show_clear = show_clear
        self.on_search_change_callback = on_search_change
        self.is_placeholder_active = False
        
        self.logger = logging.getLogger(__name__)
        
        # Configure grid weights
        self.grid_columnconfigure(0, weight=1)  # Make search field expand
        
        self._create_widgets()
        self._setup_events()
        self._show_placeholder()
    
    def _create_widgets(self):
        """Create the search bar widgets."""
        # Search field with manual placeholder management (match main window)
        self.search_field = ctk.CTkEntry(
            self,
            height=34,  # Match main window height
            placeholder_text="",  # We handle placeholder manually for better control
            font=ctk.CTkFont(size=12),  # Match main window font size
            fg_color=get_color("BACKGROUND_TERTIARY"),
            border_color=get_color("BORDER_DEFAULT"),
            text_color=get_color("TEXT_PRIMARY")
        )
        self.search_field.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        
        current_column = 1
        
        # Save Search button (optional) - Match main window styling
        if self.show_save_load:
            self.save_search_button = ctk.CTkButton(
                self,
                text="Save",
                width=80,  # Match main window width
                height=34,  # Match main window height
                font=ctk.CTkFont(size=11),  # Match main window font size
                fg_color=get_color("BACKGROUND_SECONDARY"),  # Match main window color
                hover_color=get_color("BUTTON_HOVER"),
                corner_radius=8,  # Match main window corner radius
                text_color=get_color("TEXT_PRIMARY"),
                command=self._save_search
            )
            self.save_search_button.grid(row=0, column=current_column, sticky="e", padx=(0, 5))
            current_column += 1
            
            # Load Search button - Match main window styling
            self.load_search_button = ctk.CTkButton(
                self,
                text="Load",
                width=80,  # Match main window width
                height=34,  # Match main window height
                font=ctk.CTkFont(size=11),  # Match main window font size
                fg_color=get_color("BACKGROUND_SECONDARY"),  # Match main window color
                hover_color=get_color("BUTTON_HOVER"),
                corner_radius=8,  # Match main window corner radius
                text_color=get_color("TEXT_PRIMARY"),
                command=self._load_search
            )
            self.load_search_button.grid(row=0, column=current_column, sticky="e", padx=(0, 5))
            current_column += 1
        
        # Clear Search button (optional) - Match main window styling
        if self.show_clear:
            self.clear_search_button = ctk.CTkButton(
                self,
                text="✕ Clear",  # Match main window text with symbol
                width=70,  # Match main window width
                height=34,  # Match main window height
                font=ctk.CTkFont(size=11),  # Match main window font size
                fg_color=get_color("BACKGROUND_SECONDARY"),  # Match main window color
                hover_color=get_color("BUTTON_HOVER"),
                corner_radius=8,  # Match main window corner radius
                text_color=get_color("TEXT_PRIMARY"),
                command=self.clear_search
            )
            self.clear_search_button.grid(row=0, column=current_column, sticky="e")
    
    def _setup_events(self):
        """Set up event bindings for the search field."""
        self.search_field.bind("<FocusIn>", self._on_focus_in)
        self.search_field.bind("<FocusOut>", self._on_focus_out)
        self.search_field.bind("<Button-1>", self._on_click)  # Add click event for immediate placeholder hiding
        self.search_field.bind("<Key>", self._on_key)
        self.search_field.bind("<KeyRelease>", self._on_key_release)
        self.search_field.bind("<Control-Delete>", self._on_ctrl_delete)
        self.search_field.bind("<Control-BackSpace>", self._on_ctrl_backspace)
        self.search_field.bind("<Escape>", self._on_escape)
    
    def _show_placeholder(self):
        """Show placeholder text in search field."""
        if self.search_field.get() == "":
            self.is_placeholder_active = True
            self.search_field.insert(0, self.placeholder_text)
            self.search_field.configure(text_color=get_color("TEXT_DISABLED"))
    
    def _hide_placeholder(self):
        """Hide placeholder text from search field."""
        if self.is_placeholder_active and self.search_field.get() == self.placeholder_text:
            self.is_placeholder_active = False
            self.search_field.delete(0, "end")
            self.search_field.configure(text_color=get_color("TEXT_PRIMARY"))
    
    def _on_focus_in(self, event):
        """Handle search field gaining focus."""
        self._hide_placeholder()
    
    def _on_focus_out(self, event):
        """Handle search field losing focus."""
        if self.search_field.get() == "":
            self._show_placeholder()
    
    def _on_click(self, event):
        """Handle search field being clicked - immediately hide placeholder."""
        self._hide_placeholder()
    
    def _on_key(self, event):
        """Handle key press in search field."""
        if self.is_placeholder_active:
            self._hide_placeholder()
    
    def _on_key_release(self, event):
        """Handle key release in search field."""
        # Debounce search changes
        self.after(10, self._process_search_change)
    
    def _on_ctrl_delete(self, event):
        """Handle Ctrl+Delete to delete word forward."""
        try:
            current_text = self.search_field.get()
            cursor_pos = self.search_field.index("insert")
            
            # Find the end of the current word (next space or end of string)
            delete_end_pos = cursor_pos
            while delete_end_pos < len(current_text) and current_text[delete_end_pos] not in [' ', '\t']:
                delete_end_pos += 1
            
            # Skip any trailing spaces
            while delete_end_pos < len(current_text) and current_text[delete_end_pos] in [' ', '\t']:
                delete_end_pos += 1
            
            if delete_end_pos > cursor_pos:
                self.search_field.delete(cursor_pos, delete_end_pos)
                self._process_search_change()
                
        except Exception as e:
            self.logger.debug(f"Error in Ctrl+Delete handler: {e}")
        
        return "break"  # Prevent default handling
    
    def _on_ctrl_backspace(self, event):
        """Handle Ctrl+Backspace to delete word backward."""
        try:
            current_text = self.search_field.get()
            cursor_pos = self.search_field.index("insert")
            
            # Find the start of the current word (previous space or start of string)
            delete_start_pos = cursor_pos - 1
            while delete_start_pos >= 0 and current_text[delete_start_pos] not in [' ', '\t']:
                delete_start_pos -= 1
            
            # Skip any leading spaces
            while delete_start_pos >= 0 and current_text[delete_start_pos] in [' ', '\t']:
                delete_start_pos -= 1
            
            delete_start_pos += 1  # Move to start of word to delete
            
            if delete_start_pos < cursor_pos:
                self.search_field.delete(delete_start_pos, cursor_pos)
                self._process_search_change()
                
        except Exception as e:
            self.logger.debug(f"Error in Ctrl+Backspace handler: {e}")
        
        return "break"  # Prevent default handling
    
    def _on_escape(self, event):
        """Handle Escape key to clear search field."""
        search_text = self.get_search_text()
        if search_text:
            self.clear_search()
        else:
            # If already empty, clear focus
            self.clear_search()
        
        return "break"  # Prevent default handling
    
    def _process_search_change(self):
        """Process search field changes and trigger callback."""
        if self.on_search_change_callback:
            try:
                self.on_search_change_callback()
            except Exception as e:
                self.logger.error(f"Error in search change callback: {e}")
    
    def _save_search(self):
        """Open save search dialog."""
        current_query = self.get_search_text()
        if not current_query:
            messagebox.showwarning("No Search Query", "Please enter a search query before saving.", parent=self)
            self.search_field.focus()
            return
        
        def on_save_callback(search_id, name, query):
            self.logger.info(f"Search '{name}' saved successfully with ID: {search_id}")
        
        try:
            SaveSearchDialog(self, current_query, on_save_callback)
        except Exception as e:
            self.logger.error(f"Error opening save search dialog: {e}")
            messagebox.showerror("Error", "Failed to open save search dialog.", parent=self)
    
    def _load_search(self):
        """Open load search dialog."""
        def on_load_callback(search_id, name, query):
            self.logger.info(f"Loading search '{name}': {query}")
            self.set_search_text(query)
            self._process_search_change()
        
        try:
            LoadSearchDialog(self, on_load_callback)
        except Exception as e:
            self.logger.error(f"Error opening load search dialog: {e}")
            messagebox.showerror("Error", "Failed to open load search dialog.", parent=self)
    
    def clear_search(self):
        """Clear the search field and trigger change event."""
        self.search_field.delete(0, "end")
        self.is_placeholder_active = False
        self._process_search_change()
        self.search_field.focus()
        self._show_placeholder()
    
    def get_search_text(self) -> str:
        """Get the current search text (excluding placeholder)."""
        if self.is_placeholder_active:
            return ""
        return self.search_field.get()
    
    def set_search_text(self, text: str):
        """Set the search field text and handle placeholder state."""
        self.is_placeholder_active = False
        self.search_field.delete(0, "end")
        
        if text:
            self.search_field.insert(0, text)
            self.search_field.configure(text_color=get_color("TEXT_PRIMARY"))
        else:
            self._show_placeholder()
    
    def set_placeholder_text(self, placeholder: str):
        """Update the placeholder text."""
        old_placeholder = self.placeholder_text
        self.placeholder_text = placeholder
        
        # Update placeholder if it's currently active
        if self.is_placeholder_active and self.search_field.get() == old_placeholder:
            self.search_field.delete(0, "end")
            self.search_field.insert(0, self.placeholder_text)
    
    def focus_search_field(self):
        """Set focus to the search field."""
        self.search_field.focus()
    
    def update_theme_colors(self):
        """Update component colors when theme changes."""
        # Update search field colors
        self.search_field.configure(
            fg_color=get_color("BACKGROUND_TERTIARY"),
            border_color=get_color("BORDER_DEFAULT")
        )
        
        # Update text color based on placeholder state
        if self.is_placeholder_active:
            self.search_field.configure(text_color=get_color("TEXT_DISABLED"))
        else:
            self.search_field.configure(text_color=get_color("TEXT_PRIMARY"))
        
        # Update button colors - Match main window styling
        if self.show_save_load:
            self.save_search_button.configure(
                fg_color=get_color("BACKGROUND_SECONDARY"),
                hover_color=get_color("BUTTON_HOVER"),
                text_color=get_color("TEXT_PRIMARY")
            )
            self.load_search_button.configure(
                fg_color=get_color("BACKGROUND_SECONDARY"),
                hover_color=get_color("BUTTON_HOVER"),
                text_color=get_color("TEXT_PRIMARY")
            )
        
        if self.show_clear:
            self.clear_search_button.configure(
                fg_color=get_color("BACKGROUND_SECONDARY"),  # Match main window
                hover_color=get_color("BUTTON_HOVER"),
                text_color=get_color("TEXT_PRIMARY")
            )