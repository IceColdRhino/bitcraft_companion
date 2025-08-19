"""
Saved Search Dialog components for BitCraft Companion.

Provides modal dialogs for saving and loading/managing saved search queries.
"""

import logging
from typing import Optional, Callable

import customtkinter as ctk
from tkinter import messagebox

from app.services.saved_search_service import SavedSearchService
from app.ui.themes import get_color


class SaveSearchDialog(ctk.CTkToplevel):
    """Modal dialog for saving a new search query."""
    
    def __init__(self, parent, current_query: str, on_save_callback: Optional[Callable] = None):
        """
        Initialize the save search dialog.
        
        Args:
            parent: Parent window
            current_query: The current search query to save
            on_save_callback: Optional callback function called after successful save
        """
        super().__init__(parent)
        
        self.logger = logging.getLogger(__name__)
        self.current_query = current_query
        self.on_save_callback = on_save_callback
        self.saved_search_service = SavedSearchService()
        
        self._setup_window()
        self._create_widgets()
        self._center_on_parent()
        
        # Focus on name entry
        self.name_entry.focus()
    
    def _setup_window(self):
        """Configure the dialog window."""
        self.title("Save Search")
        self.geometry("420x200")
        self.resizable(False, False)
        
        # Make modal
        self.transient(self.master)
        self.grab_set()
        
        # Configure styling
        self.configure(fg_color=get_color("BACKGROUND_PRIMARY"))
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_widgets(self):
        """Create and layout the dialog widgets."""
        # Main frame with padding
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=25, pady=25)
        
        # Name input with proper height and spacing
        name_label = ctk.CTkLabel(
            main_frame,
            text="Save search as:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=get_color("TEXT_PRIMARY"),
            anchor="w"
        )
        name_label.pack(fill="x", pady=(0, 5))
        
        self.name_entry = ctk.CTkEntry(
            main_frame,
            height=40,
            font=ctk.CTkFont(size=13),
            fg_color=get_color("BACKGROUND_SECONDARY"),
            border_color=get_color("BORDER_DEFAULT"),
            text_color=get_color("TEXT_PRIMARY"),
            placeholder_text="Enter a descriptive name for this search..."
        )
        self.name_entry.pack(fill="x", pady=(0, 25))
        self.name_entry.bind("<Return>", lambda e: self._save_search())
        
        # Buttons frame with proper spacing
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x")
        
        # Cancel button
        self.cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=self._on_close,
            width=100,
            height=40,
            font=ctk.CTkFont(size=12),
            fg_color=get_color("BACKGROUND_SECONDARY"),
            hover_color=get_color("BUTTON_HOVER"),
            text_color=get_color("TEXT_PRIMARY"),
            border_width=1,
            border_color=get_color("BORDER_DEFAULT")
        )
        self.cancel_button.pack(side="right", padx=(15, 0))
        
        # Save button
        self.save_button = ctk.CTkButton(
            button_frame,
            text="Save",
            command=self._save_search,
            width=100,
            height=40,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=get_color("STATUS_SUCCESS"),
            hover_color=get_color("STATUS_READY"),
            text_color="white"
        )
        self.save_button.pack(side="right")
    
    def _center_on_parent(self):
        """Center the dialog on its parent window."""
        self.update_idletasks()
        
        parent = self.master
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()
        
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        
        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
    
    def _save_search(self):
        """Save the search with the entered name."""
        name = self.name_entry.get().strip()
        
        if not name:
            messagebox.showerror("Invalid Name", "Please enter a name for the search.", parent=self)
            self.name_entry.focus()
            return
        
        if not self.current_query.strip():
            messagebox.showerror("Invalid Query", "Cannot save an empty search query.", parent=self)
            return
        
        # Check if name already exists
        existing_search = self.saved_search_service.get_search_by_name(name)
        if existing_search:
            messagebox.showerror("Name Exists", f"A search named '{name}' already exists. Please choose a different name.", parent=self)
            self.name_entry.focus()
            self.name_entry.select_range(0, "end")
            return
        
        # Save the search
        search_id = self.saved_search_service.save_search(name, self.current_query)
        if search_id:
            messagebox.showinfo("Search Saved", f"Search '{name}' has been saved successfully!", parent=self)
            
            # Call callback if provided
            if self.on_save_callback:
                self.on_save_callback(search_id, name, self.current_query)
            
            self._on_close()
        else:
            messagebox.showerror("Save Failed", "Failed to save the search. Please try again.", parent=self)
    
    def _on_close(self):
        """Handle dialog close."""
        self.grab_release()
        self.destroy()


class LoadSearchDialog(ctk.CTkToplevel):
    """Modal dialog for loading and managing saved search queries."""
    
    def __init__(self, parent, on_load_callback: Optional[Callable] = None):
        """
        Initialize the load search dialog.
        
        Args:
            parent: Parent window
            on_load_callback: Optional callback function called when a search is loaded
        """
        super().__init__(parent)
        
        self.logger = logging.getLogger(__name__)
        self.on_load_callback = on_load_callback
        self.saved_search_service = SavedSearchService()
        self.selected_search_id = None
        
        self._setup_window()
        self._create_widgets()
        self._load_searches()
        self._center_on_parent()
    
    def _setup_window(self):
        """Configure the dialog window."""
        self.title("Load Saved Search")
        self.geometry("600x500")
        self.resizable(True, True)
        
        # Make modal
        self.transient(self.master)
        self.grab_set()
        
        # Configure styling
        self.configure(fg_color=get_color("BACKGROUND_PRIMARY"))
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_widgets(self):
        """Create and layout the dialog widgets."""
        # Main frame
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = ctk.CTkLabel(
            main_frame,
            text="Saved Search Queries",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=get_color("TEXT_PRIMARY")
        )
        title_label.pack(pady=(0, 15))
        
        # Search list frame
        list_frame = ctk.CTkFrame(main_frame, fg_color=get_color("BACKGROUND_SECONDARY"))
        list_frame.pack(fill="both", expand=True, pady=(0, 15))
        
        # Search list with scrollbar
        self.search_listbox = ctk.CTkScrollableFrame(
            list_frame,
            fg_color="transparent"
        )
        self.search_listbox.pack(fill="both", expand=True, padx=15, pady=15)
        
        # No searches message (initially hidden)
        self.no_searches_label = ctk.CTkLabel(
            list_frame,
            text="No saved searches found.\nCreate some searches to see them here!",
            font=ctk.CTkFont(size=14),
            text_color=get_color("TEXT_DISABLED")
        )
        
        # Buttons frame
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x")
        
        # Close button
        self.close_button = ctk.CTkButton(
            button_frame,
            text="Close",
            command=self._on_close,
            width=100,
            height=35,
            font=ctk.CTkFont(size=12),
            fg_color=get_color("BACKGROUND_SECONDARY"),
            hover_color=get_color("BUTTON_HOVER"),
            text_color=get_color("TEXT_PRIMARY")
        )
        self.close_button.pack(side="right", padx=(10, 0))
        
        # Load button
        self.load_button = ctk.CTkButton(
            button_frame,
            text="Load Search",
            command=self._load_selected_search,
            width=120,
            height=35,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=get_color("STATUS_SUCCESS"),
            hover_color=get_color("STATUS_READY"),
            text_color="white",
            state="disabled"
        )
        self.load_button.pack(side="right")
    
    def _load_searches(self):
        """Load and display all saved searches."""
        searches = self.saved_search_service.get_all_searches()
        
        # Clear existing items
        for widget in self.search_listbox.winfo_children():
            widget.destroy()
        
        if not searches:
            self.no_searches_label.pack(fill="both", expand=True, padx=15, pady=50)
            return
        else:
            self.no_searches_label.pack_forget()
        
        # Create search items
        for search in searches:
            self._create_search_item(search)
    
    def _create_search_item(self, search: dict):
        """Create a search item widget."""
        item_frame = ctk.CTkFrame(
            self.search_listbox,
            fg_color=get_color("BACKGROUND_PRIMARY"),
            corner_radius=8
        )
        item_frame.pack(fill="x", pady=5)
        
        # Main content frame
        content_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        # Name and date row
        header_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 5))
        
        name_label = ctk.CTkLabel(
            header_frame,
            text=search['name'],
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=get_color("TEXT_PRIMARY"),
            anchor="w"
        )
        name_label.pack(side="left", fill="x", expand=True)
        
        # Format date
        try:
            from datetime import datetime
            last_used = datetime.fromisoformat(search.get('last_used', search.get('created', '')).replace('Z', '+00:00'))
            date_str = last_used.strftime("%Y-%m-%d %H:%M")
        except:
            date_str = "Unknown"
        
        date_label = ctk.CTkLabel(
            header_frame,
            text=f"Last used: {date_str}",
            font=ctk.CTkFont(size=10),
            text_color=get_color("TEXT_DISABLED")
        )
        date_label.pack(side="right")
        
        # Query preview
        query_label = ctk.CTkLabel(
            content_frame,
            text=search['query'],
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=get_color("TEXT_ACCENT"),
            anchor="w",
            wraplength=500
        )
        query_label.pack(fill="x", pady=(0, 10))
        
        # Buttons frame
        buttons_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        buttons_frame.pack(fill="x")
        
        # Load button
        load_btn = ctk.CTkButton(
            buttons_frame,
            text="Load",
            command=lambda s=search: self._load_search(s),
            width=80,
            height=30,
            font=ctk.CTkFont(size=11),
            fg_color=get_color("STATUS_SUCCESS"),
            hover_color=get_color("STATUS_READY"),
            text_color="white"
        )
        load_btn.pack(side="right", padx=(5, 0))
        
        # Delete button
        delete_btn = ctk.CTkButton(
            buttons_frame,
            text="Delete",
            command=lambda s=search: self._delete_search(s),
            width=80,
            height=30,
            font=ctk.CTkFont(size=11),
            fg_color=get_color("STATUS_ERROR"),
            hover_color=get_color("STATUS_ERROR"),
            text_color="white"
        )
        delete_btn.pack(side="right")
    
    def _load_search(self, search: dict):
        """Load a specific search."""
        query = self.saved_search_service.use_search(search['id'])
        if query:
            if self.on_load_callback:
                self.on_load_callback(search['id'], search['name'], query)
            self._on_close()
        else:
            messagebox.showerror("Load Failed", "Failed to load the selected search.", parent=self)
    
    def _delete_search(self, search: dict):
        """Delete a specific search after confirmation."""
        result = messagebox.askyesno(
            "Delete Search",
            f"Are you sure you want to delete the search '{search['name']}'?\n\nThis action cannot be undone.",
            parent=self
        )
        
        if result:
            if self.saved_search_service.delete_search(search['id']):
                messagebox.showinfo("Search Deleted", f"Search '{search['name']}' has been deleted.", parent=self)
                self._load_searches()  # Refresh the list
            else:
                messagebox.showerror("Delete Failed", "Failed to delete the search. Please try again.", parent=self)
    
    def _load_selected_search(self):
        """Load the currently selected search."""
        # This method is kept for potential future use with different selection model
        pass
    
    def _center_on_parent(self):
        """Center the dialog on its parent window."""
        self.update_idletasks()
        
        parent = self.master
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()
        
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        
        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
    
    def _on_close(self):
        """Handle dialog close."""
        self.grab_release()
        self.destroy()