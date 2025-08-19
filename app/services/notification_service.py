"""
Notification service for BitCraft Companion.

Handles showing craft completion notifications with optional sound alerts.
Manages notification settings and coordinates with the notification window.
"""

import logging
import threading
from typing import Dict, Any

# Platform-specific imports (sound handled by Windows natively)
# Native Windows toast notification import
try:
    from win11toast import toast
    NATIVE_TOAST_AVAILABLE = True
except ImportError:
    NATIVE_TOAST_AVAILABLE = False
    # Fallback to custom notification window if win11toast not available
    try:
        from app.ui.components.notification_window import NotificationWindow
    except ImportError:
        NotificationWindow = None


class NotificationService:
    """
    Service for managing craft completion notifications.
    
    Features:
    - Pop-up notifications for passive and active craft completions
    - Optional sound notifications
    - Settings-based control of notification types
    - Auto-dismiss notifications
    """
    
    def __init__(self, main_app):
        """
        Initialize the notification service.
        
        Args:
            main_app: Reference to the main application window
        """
        self.main_app = main_app
        self.settings = self._load_notification_settings()
        
        # Notification bundling system
        self._pending_passive_items = []  # Buffer for items during bundling window
        self._bundling_timer = None
        self.passive_bundling_delay = 2.0  # 2 seconds to wait for more items to bundle
        
        logging.info("NotificationService initialized")
    
    def _load_notification_settings(self) -> Dict[str, Any]:
        """Load notification settings from app configuration."""
        try:
            # Default settings
            default_settings = {
                "notifications": {
                    "passive_crafts_enabled": True,
                    "active_crafts_enabled": True,
                }
            }
            
            return default_settings
            
        except Exception as e:
            logging.error(f"Error loading notification settings: {e}")
            return {
                "notifications": {
                    "passive_crafts_enabled": True,
                    "active_crafts_enabled": True,
                }
            }
    
    def update_settings(self, new_settings: Dict[str, Any]):
        """
        Update notification settings.
        
        Args:
            new_settings: Dictionary with notification setting updates
        """
        try:
            self.settings.update(new_settings)
            logging.info(f"Notification settings updated: {new_settings}")
            
        except Exception as e:
            logging.error(f"Error updating notification settings: {e}")
    
    def show_passive_craft_notification(self, item_name: str, quantity: int = 1):
        """
        Show a notification for completed passive crafting operations with bundling protection.
        Always buffers items and waits for bundling delay to collect multiple completions.
        
        Args:
            item_name: Name of the crafted item
            quantity: Number of items completed
        """
        try:
            if not self.settings.get("notifications", {}).get("passive_crafts_enabled", True):
                return
            
            # Add item to pending buffer
            self._pending_passive_items.append({"name": item_name, "quantity": quantity})
            logging.debug(f"Passive craft notification buffered: {quantity}x {item_name}")
            
            # Cancel existing timer if running and start/restart bundling timer
            if self._bundling_timer:
                self._bundling_timer.cancel()
            
            self._bundling_timer = threading.Timer(self.passive_bundling_delay, self._send_bundled_passive_notification)
            self._bundling_timer.start()
            
        except Exception as e:
            logging.error(f"Error showing passive craft notification: {e}")
    
    def _send_bundled_passive_notification(self):
        """Send bundled notification for all pending passive craft items."""
        try:
            if not self._pending_passive_items:
                return
                
            # Bundle items by name
            item_counts = {}
            for item in self._pending_passive_items:
                item_name = item["name"]
                quantity = item["quantity"]
                item_counts[item_name] = item_counts.get(item_name, 0) + quantity
            
            # Create notification message
            if len(item_counts) == 1:
                # Single item type
                item_name = list(item_counts.keys())[0]
                total_quantity = list(item_counts.values())[0]
                title = "Passive Craft Complete!"
                message = f"{total_quantity}x {item_name} ready!" if total_quantity > 1 else f"{item_name} is ready!"
            else:
                # Multiple item types - create summary
                item_list = []
                total_items = 0
                for item_name, count in item_counts.items():
                    total_items += count
                    if count == 1:
                        item_list.append(item_name)
                    else:
                        item_list.append(f"{count}x {item_name}")
                
                title = "Multiple Crafts Complete!"
                if len(item_list) <= 3:
                    message = f"{', '.join(item_list)} ready!"
                else:
                    first_two = ', '.join(item_list[:2])
                    remaining_types = len(item_list) - 2
                    message = f"{first_two} and {remaining_types} more types ready!"
            
            icon = "🛠️"
            self._show_notification(title, message, icon)
            
            # Log the bundled notification
            item_summary = ", ".join([f"{count}x {name}" for name, count in item_counts.items()])
            logging.info(f"Bundled passive craft notification sent: {item_summary}")
            
            # Clear pending items and timer
            self._pending_passive_items.clear()
            self._bundling_timer = None
            
        except Exception as e:
            logging.error(f"Error sending bundled passive craft notification: {e}")
            # Clear pending items on error to prevent accumulation
            self._pending_passive_items.clear()
            self._bundling_timer = None
    
    def show_active_craft_notification(self, item_name: str, quantity: int = 1):
        """
        Show a notification for completed active crafting operations.
        
        Args:
            item_name: Name of the crafted item
            quantity: Number of items completed
        """
        try:
            if not self.settings.get("notifications", {}).get("active_crafts_enabled", True):
                return
            
            title = "Active Craft Complete!"
            message = f"{quantity}x {item_name} ready!" if quantity > 1 else f"{item_name} is ready!"
            icon = "🔨"
            
            self._show_notification(title, message, icon)
                
            logging.info(f"Active craft notification shown: {quantity}x {item_name}")
            
        except Exception as e:
            logging.error(f"Error showing active craft notification: {e}")
    
    def show_test_notification(self):
        """Show a test notification for settings verification."""
        try:
            title = "Test Notification"
            message = "This is a test craft completion notification!"
            icon = "🧪"
            
            self._show_notification(title, message, icon)
                
            logging.info("Test notification shown")
            
        except Exception as e:
            logging.error(f"Error showing test notification: {e}")
    
    def _show_notification(self, title: str, message: str, icon: str):
        """
        Show the notification using native Windows toasts or fallback to custom window.
        Runs in a separate thread to prevent UI freezing.
        
        Args:
            title: Notification title
            message: Notification message
            icon: Icon/emoji for the notification
        """
        def _show_notification_thread():
            """Thread function to show notification without blocking UI."""
            try:
                if NATIVE_TOAST_AVAILABLE:
                    # Use native Windows toast notification with enhanced visibility
                    toast(
                        title=title,
                        body=message,
                        duration='short',  # 'short' = 7 seconds, 'long' = 25 seconds
                        app_id='BitCraft Companion',
                        # Add audio to make it more noticeable
                        audio={'src': 'ms-winsoundevent:Notification.Default', 'loop': 'false'},
                        # Try to make it stay on screen longer and be more visible
                        scenario='reminder'  # This can help with visibility over games
                    )
                    logging.debug(f"Native toast notification shown: {title}")
                elif NotificationWindow:
                    # Fallback to custom notification window (must run on main thread)
                    # Schedule on main thread using after()
                    if hasattr(self.main_app, 'after'):
                        self.main_app.after(0, lambda: self._show_custom_notification(title, message, icon))
                    else:
                        logging.info(f"NOTIFICATION: {title} - {message}")
                else:
                    # Ultimate fallback - just log the notification
                    logging.info(f"NOTIFICATION: {title} - {message}")
                
            except Exception as e:
                logging.error(f"Error showing notification: {e}")
                # Ultimate fallback - just log the notification
                logging.info(f"NOTIFICATION: {title} - {message}")
        
        # Run notification in a separate daemon thread to prevent UI blocking
        notification_thread = threading.Thread(target=_show_notification_thread, daemon=True)
        notification_thread.start()
    
    def _show_custom_notification(self, title: str, message: str, icon: str):
        """
        Show custom notification window on main thread.
        
        Args:
            title: Notification title
            message: Notification message
            icon: Icon/emoji for the notification
        """
        try:
            if NotificationWindow:
                notification = NotificationWindow(
                    parent=self.main_app,
                    title=title,
                    message=message,
                    icon=icon
                )
                logging.debug(f"Custom notification window shown: {title}")
            else:
                logging.info(f"NOTIFICATION: {title} - {message}")
                
        except Exception as e:
            logging.error(f"Error showing custom notification: {e}")
            logging.info(f"NOTIFICATION: {title} - {message}")
    
    def get_settings(self) -> Dict[str, Any]:
        """
        Get current notification settings.
        
        Returns:
            Dictionary with current notification settings
        """
        return self.settings.copy()