"""
Notification window component for BitCraft Companion.

Shows pop-up notifications for craft completions with auto-dismiss functionality.
Uses Windows default positioning and modern styling.
"""

import logging
import customtkinter as ctk


class NotificationWindow(ctk.CTkToplevel):
    """
    Pop-up notification window for craft completions.
    
    Features:
    - Auto-dismiss after configurable time
    - Modern styling with theme consistency
    - Windows default positioning
    - Smooth appearance with fade-like effect
    - Non-blocking and stays on top
    """
    
    def __init__(self, parent, title: str, message: str, icon: str = "✅", 
                 auto_dismiss_ms: int = 4000):
        """
        Initialize the notification window.
        
        Args:
            parent: Parent window (main app)
            title: Notification title
            message: Notification message
            icon: Icon/emoji to display
            auto_dismiss_ms: Time in milliseconds before auto-dismiss
        """
        super().__init__(parent)
        
        self.parent = parent
        self.auto_dismiss_ms = auto_dismiss_ms
        
        # Configure window properties
        self._setup_window_properties(title)
        
        # Position window using Windows default positioning
        self._position_window()
        
        # Create notification content
        self._create_notification_content(title, message, icon)
        
        # Start auto-dismiss timer
        self._start_auto_dismiss_timer()
        
        # Make window visible and focused
        self._show_notification()
        
        logging.debug(f"Notification window created: {title}")
    
    def _setup_window_properties(self, title: str):
        """Configure basic window properties."""
        try:
            self.title(title)
            self.geometry("320x120")
            self.resizable(False, False)
            
            # Make window stay on top and modal-like
            self.attributes("-topmost", True)
            self.transient(self.parent)
            
            # Remove window decorations for cleaner look (optional)
            # self.overrideredirect(True)  # Uncomment for borderless window
            
            # Prevent window from being closed by user (auto-dismiss only)
            self.protocol("WM_DELETE_WINDOW", self._on_window_close)
            
        except Exception as e:
            logging.error(f"Error setting up notification window properties: {e}")
    
    def _position_window(self):
        """Position window using Windows default positioning."""
        try:
            # Let Windows handle positioning by not setting explicit coordinates
            # This uses the OS default positioning which is usually top-right or center
            # Alternative: we could position it in a corner if needed
            
            # For consistent positioning, we can place it in the top-right corner
            self.update_idletasks()  # Ensure geometry is calculated
            
            # Get screen dimensions
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            
            # Position in top-right corner with some padding
            x = screen_width - 320 - 20  # window width + padding
            y = 50  # Top padding
            
            self.geometry(f"320x120+{x}+{y}")
            
        except Exception as e:
            logging.error(f"Error positioning notification window: {e}")
            # Fallback to center of screen
            self.geometry("320x120")
    
    def _create_notification_content(self, title: str, message: str, icon: str):
        """Create the notification content with modern styling."""
        try:
            # Main container with modern styling
            main_frame = ctk.CTkFrame(
                self,
                fg_color=("#f0f0f0", "#2b2b2b"),
                corner_radius=12,
                border_width=2,
                border_color=("#3B8ED0", "#2980B9")
            )
            main_frame.pack(fill="both", expand=True, padx=8, pady=8)
            
            # Content container
            content_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
            content_frame.pack(fill="both", expand=True, padx=12, pady=12)
            
            # Icon and title row
            header_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
            header_frame.pack(fill="x", pady=(0, 8))
            header_frame.grid_columnconfigure(1, weight=1)
            
            # Icon
            icon_label = ctk.CTkLabel(
                header_frame,
                text=icon,
                font=ctk.CTkFont(size=20),
                width=30
            )
            icon_label.grid(row=0, column=0, padx=(0, 8), sticky="w")
            
            # Title
            title_label = ctk.CTkLabel(
                header_frame,
                text=title,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=("#2b2b2b", "#ffffff")
            )
            title_label.grid(row=0, column=1, sticky="w")
            
            # Close button (X)
            close_button = ctk.CTkButton(
                header_frame,
                text="✕",
                width=20,
                height=20,
                font=ctk.CTkFont(size=12),
                command=self._dismiss_notification,
                fg_color="transparent",
                hover_color=("#dddddd", "#404040"),
                text_color=("#666666", "#cccccc"),
                corner_radius=10
            )
            close_button.grid(row=0, column=2, padx=(8, 0), sticky="e")
            
            # Message
            message_label = ctk.CTkLabel(
                content_frame,
                text=message,
                font=ctk.CTkFont(size=12),
                text_color=("#4a4a4a", "#e0e0e0"),
                wraplength=250,
                justify="left"
            )
            message_label.pack(anchor="w")
            
            # Auto-dismiss countdown (optional visual indicator)
            self.countdown_label = ctk.CTkLabel(
                content_frame,
                text="",
                font=ctk.CTkFont(size=9),
                text_color=("#888888", "#888888")
            )
            self.countdown_label.pack(anchor="e", pady=(4, 0))
            
        except Exception as e:
            logging.error(f"Error creating notification content: {e}")
    
    def _start_auto_dismiss_timer(self):
        """Start the auto-dismiss timer with optional countdown display."""
        try:
            # Schedule dismissal
            self.after(self.auto_dismiss_ms, self._dismiss_notification)
            
            # Optional: Show countdown in seconds
            self._update_countdown(self.auto_dismiss_ms // 1000)
            
        except Exception as e:
            logging.error(f"Error starting auto-dismiss timer: {e}")
    
    def _update_countdown(self, seconds_remaining: int):
        """Update countdown display."""
        try:
            if seconds_remaining > 0:
                self.countdown_label.configure(text=f"Auto-close in {seconds_remaining}s")
                self.after(1000, lambda: self._update_countdown(seconds_remaining - 1))
            else:
                self.countdown_label.configure(text="")
                
        except Exception as e:
            logging.error(f"Error updating countdown: {e}")
    
    def _show_notification(self):
        """Make the notification visible and bring to front."""
        try:
            # Ensure window is visible and focused
            self.deiconify()  # Show window if minimized
            self.lift()       # Bring to front
            self.focus_set()  # Set focus (but don't steal from other apps)
            
        except Exception as e:
            logging.error(f"Error showing notification: {e}")
    
    def _fade_in(self, alpha: float = 0.1):
        """Optional fade-in animation effect."""
        try:
            if alpha <= 1.0:
                self.attributes("-alpha", alpha)
                self.after(50, lambda: self._fade_in(alpha + 0.1))
            else:
                self.attributes("-alpha", 1.0)
                
        except Exception as e:
            logging.error(f"Error in fade-in animation: {e}")
    
    def _dismiss_notification(self):
        """Dismiss the notification window."""
        try:
            logging.debug("Notification dismissed")
            self.destroy()
            
        except Exception as e:
            logging.error(f"Error dismissing notification: {e}")
            try:
                self.destroy()
            except:
                pass
    
    def _on_window_close(self):
        """Handle window close event (same as dismiss)."""
        self._dismiss_notification()