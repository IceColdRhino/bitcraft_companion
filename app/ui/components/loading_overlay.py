"""
Loading overlay component for BitCraft Companion.

Displays a loading image with message during data operations.
"""

import os
import customtkinter as ctk
from tkinter import PhotoImage
import logging

class LoadingOverlay(ctk.CTkToplevel):
    """
    Loading overlay that displays over the main window during operations.
    
    Features:
    - Static loading image display
    - Customizable loading message
    - Modal overlay behavior
    - Automatic positioning over parent
    """
    
    def __init__(self, parent, message="Loading..."):
        """
        Initialize the loading overlay.
        
        Args:
            parent: Parent window to overlay
            message: Loading message to display
        """
        super().__init__(parent)
        
        self.parent = parent
        self.message = message
        
        # Configure window properties
        self._setup_window_properties()
        
        # Position overlay over parent
        self._position_overlay()
        
        # Create loading content
        self._create_loading_content()
        
        # Make overlay modal
        self._setup_modal_behavior()
    
    def _setup_window_properties(self):
        """Configure basic window properties."""
        try:
            self.title("Loading")
            self.geometry("200x150")
            self.resizable(False, False)
            
            # Remove window decorations for clean overlay look
            self.overrideredirect(True)
            
            # Make window stay on top
            self.attributes("-topmost", True)
            self.transient(self.parent)
            
            # Prevent window from being closed
            self.protocol("WM_DELETE_WINDOW", lambda: None)
            
        except Exception as e:
            logging.error(f"Error setting up loading window properties: {e}")
    
    def _position_overlay(self):
        """Position overlay in center of parent window."""
        try:
            # Update parent to get current geometry
            self.parent.update_idletasks()
            
            # Get parent window position and size
            parent_x = self.parent.winfo_x()
            parent_y = self.parent.winfo_y()
            parent_width = self.parent.winfo_width()
            parent_height = self.parent.winfo_height()
            
            # Calculate center position
            overlay_width = 200
            overlay_height = 150
            x = parent_x + (parent_width - overlay_width) // 2
            y = parent_y + (parent_height - overlay_height) // 2
            
            self.geometry(f"{overlay_width}x{overlay_height}+{x}+{y}")
            
        except Exception as e:
            logging.error(f"Error positioning loading overlay: {e}")
    
    def _create_loading_content(self):
        """Create the loading content with image and message."""
        try:
            # Main container
            main_frame = ctk.CTkFrame(self, fg_color="#2a2d2e", corner_radius=8)
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Try to load loading image
            loading_image = self._load_loading_image()
            
            if loading_image:
                # Image label
                image_label = ctk.CTkLabel(main_frame, image=loading_image, text="")
                image_label.pack(pady=(20, 10))
            
            # Message label
            message_label = ctk.CTkLabel(
                main_frame,
                text=self.message,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#ffffff"
            )
            message_label.pack(pady=(0, 20))
            
        except Exception as e:
            logging.error(f"Error creating loading content: {e}")
    
    def _load_loading_image(self):
        """Load the loading.png image."""
        try:
            # Get path to loading image
            current_dir = os.path.dirname(os.path.abspath(__file__))
            images_dir = os.path.join(os.path.dirname(current_dir), "images")
            loading_path = os.path.join(images_dir, "loading.png")
            
            if os.path.exists(loading_path):
                # Load and resize image appropriately
                image = PhotoImage(file=loading_path)
                
                # Scale image if too large (optional resize)
                # For now, use image as-is
                return image
            else:
                logging.warning(f"Loading image not found at: {loading_path}")
                return None
                
        except Exception as e:
            logging.error(f"Error loading loading image: {e}")
            return None
    
    def _setup_modal_behavior(self):
        """Setup modal behavior to block interaction with parent."""
        try:
            # Grab all events
            self.grab_set()
            
            # Focus on overlay
            self.focus_set()
            
        except Exception as e:
            logging.error(f"Error setting up modal behavior: {e}")
    
    def update_message(self, new_message):
        """Update the loading message."""
        try:
            self.message = new_message
            # Find and update message label
            for child in self.winfo_children():
                if isinstance(child, ctk.CTkFrame):
                    for grandchild in child.winfo_children():
                        if isinstance(grandchild, ctk.CTkLabel) and grandchild.cget("text") == self.message:
                            grandchild.configure(text=new_message)
                            break
        except Exception as e:
            logging.error(f"Error updating loading message: {e}")
    
    def close_overlay(self):
        """Close the loading overlay."""
        try:
            self.grab_release()
            self.destroy()
        except Exception as e:
            logging.error(f"Error closing loading overlay: {e}")