"""
Notification service for BitCraft Companion.

Handles showing craft completion notifications with custom sound alerts.
Manages notification settings and coordinates with the sound service.
"""

import logging
import threading
from typing import Dict, Any, List

# Native Windows toast notification import
try:
    from win11toast import toast
    NATIVE_TOAST_AVAILABLE = True
except ImportError:
    NATIVE_TOAST_AVAILABLE = False
    
try:
    from app.services.sound_service import SoundService
except ImportError as e:
    logging.error(f"Failed to import SoundService: {e}")
    SoundService = None


class NotificationService:
    """
    Service for managing craft completion notifications.
    
    Features:
    - Pop-up notifications for passive and active craft completions
    - Custom sound notifications with user selection
    - Settings-based control of notification types and sounds
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
        
        try:
            self.sound_service = SoundService() if SoundService else None
            if not self.sound_service:
                logging.warning("SoundService not available - sounds will be disabled")
        except Exception as e:
            logging.error(f"SoundService initialization failed: {e}")
            self.sound_service = None
        
        self._pending_passive_items = []
        self._bundling_timer = None
        self.passive_bundling_delay = 2.0
        
        logging.info("NotificationService initialized")
    
    def _load_notification_settings(self) -> Dict[str, Any]:
        """Load notification settings from app configuration."""
        try:
            # Default settings with sound preferences
            default_settings = {
                "notifications": {
                    "passive_crafts_enabled": True,
                    "passive_crafts_sound": "system_default",
                    "active_crafts_enabled": True,
                    "active_crafts_sound": "system_default",
                    "stamina_recharged_enabled": True,
                    "stamina_recharged_sound": "system_default",
                }
            }
            
            return default_settings
            
        except Exception as e:
            logging.error(f"Error loading notification settings: {e}")
            return {
                "notifications": {
                    "passive_crafts_enabled": True,
                    "passive_crafts_sound": "system_default",
                    "active_crafts_enabled": True,
                    "active_crafts_sound": "system_default",
                    "stamina_recharged_enabled": True,
                    "stamina_recharged_sound": "system_default",
                }
            }
    
    def update_settings(self, new_settings: Dict[str, Any]):
        """
        Update notification settings with deep merge.
        
        Args:
            new_settings: Dictionary with notification setting updates
        """
        try:
            for key, value in new_settings.items():
                if key in self.settings and isinstance(self.settings[key], dict) and isinstance(value, dict):
                    self.settings[key].update(value)
                else:
                    self.settings[key] = value
            
            logging.debug(f"Notification settings updated: {new_settings}")
            
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
            
            self._pending_passive_items.append({"name": item_name, "quantity": quantity})
            
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
                
            item_counts = {}
            for item in self._pending_passive_items:
                item_name = item["name"]
                quantity = item["quantity"]
                item_counts[item_name] = item_counts.get(item_name, 0) + quantity
            if len(item_counts) == 1:
                item_name = list(item_counts.keys())[0]
                total_quantity = list(item_counts.values())[0]
                title = "Passive Craft Complete!"
                message = f"{total_quantity}x {item_name} ready!" if total_quantity > 1 else f"{item_name} is ready!"
            else:
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
            sound_file = self.settings.get("notifications", {}).get("passive_crafts_sound", "system_default")
            self._show_notification(title, message, icon, sound_file)
            
            item_summary = ", ".join([f"{count}x {name}" for name, count in item_counts.items()])
            logging.debug(f"Bundled passive craft notification sent: {item_summary}")
            
            self._pending_passive_items.clear()
            self._bundling_timer = None
            
        except Exception as e:
            logging.error(f"Error sending bundled passive craft notification: {e}")
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
            sound_file = self.settings.get("notifications", {}).get("active_crafts_sound", "system_default")
            
            self._show_notification(title, message, icon, sound_file)
            logging.debug(f"Active craft notification shown: {quantity}x {item_name}")
            
        except Exception as e:
            logging.error(f"Error showing active craft notification: {e}")
    
    def show_stamina_notification(self, title: str, message: str):
        """
        Show a notification for stamina events.
        
        Args:
            title: Notification title
            message: Notification message
        """
        try:
            if not self.settings.get("notifications", {}).get("stamina_recharged_enabled", True):
                return
            
            icon = "⚡"
            sound_file = self.settings.get("notifications", {}).get("stamina_recharged_sound", "system_default")
            self._show_notification(title, message, icon, sound_file)
            logging.debug(f"Stamina notification shown: {title}")
            
        except Exception as e:
            logging.error(f"Error showing stamina notification: {e}")
    
    def show_test_notification(self):
        """Show a test notification for settings verification."""
        try:
            title = "Test Notification"
            message = "This is a test craft completion notification!"
            icon = "🧪"
            
            self._show_notification(title, message, icon, "notification.wav")
            logging.debug("Test notification shown")
            
        except Exception as e:
            logging.error(f"Error showing test notification: {e}")
    
    def show_test_passive_craft_notification(self):
        """Show a test passive craft notification using current passive craft settings."""
        try:
            if not self.settings.get("notifications", {}).get("passive_crafts_enabled", True):
                logging.debug("Passive craft notifications disabled - skipping test")
                return
            
            title = "Passive Craft Complete!"
            message = "Your Iron Ingots are ready!"
            icon = "🛠️"
            sound_file = self.settings.get("notifications", {}).get("passive_crafts_sound", "system_default")
            
            self._show_notification(title, message, icon, sound_file)
            logging.debug(f"Test passive craft notification shown with sound: {sound_file}")
            
        except Exception as e:
            logging.error(f"Error showing test passive craft notification: {e}")
    
    def show_test_active_craft_notification(self):
        """Show a test active craft notification using current active craft settings."""
        try:
            if not self.settings.get("notifications", {}).get("active_crafts_enabled", True):
                logging.debug("Active craft notifications disabled - skipping test")
                return
            
            title = "Active Craft Complete!"
            message = "Your Wooden Plank is ready!"
            icon = "🔨"
            sound_file = self.settings.get("notifications", {}).get("active_crafts_sound", "system_default")
            
            self._show_notification(title, message, icon, sound_file)
            logging.debug(f"Test active craft notification shown with sound: {sound_file}")
            
        except Exception as e:
            logging.error(f"Error showing test active craft notification: {e}")
    
    def show_test_stamina_notification(self):
        """Show a test stamina notification using current stamina settings."""
        try:
            if not self.settings.get("notifications", {}).get("stamina_recharged_enabled", True):
                logging.debug("Stamina notifications disabled - skipping test")
                return
            
            title = "Stamina Recharged!"
            message = "Your stamina is fully restored!"
            icon = "⚡"
            sound_file = self.settings.get("notifications", {}).get("stamina_recharged_sound", "system_default")
            
            self._show_notification(title, message, icon, sound_file)
            logging.debug(f"Test stamina notification shown with sound: {sound_file}")
            
        except Exception as e:
            logging.error(f"Error showing test stamina notification: {e}")
    
    def _show_notification(self, title: str, message: str, icon: str, sound_file: str = None):
        """
        Show the notification using native Windows toasts with custom sound playback.
        Runs in a separate thread to prevent UI freezing.
        
        Args:
            title: Notification title
            message: Notification message
            icon: Icon/emoji for the notification
            sound_file: Sound file to play (optional)
        """
        def _show_notification_thread():
            """Thread function to show notification without blocking UI."""
            try:
                # Play custom sound if specified and available (not system default or none)
                if sound_file and sound_file != "none" and sound_file != "system_default":
                    if self.sound_service:
                        self.sound_service.play_sound(sound_file)
                    else:
                        logging.debug("Custom sound requested but SoundService not available")
                
                if NATIVE_TOAST_AVAILABLE:
                    # Determine audio settings
                    audio_settings = None
                    if not sound_file or sound_file == "system_default":
                        # Use system default sound
                        audio_settings = {'src': 'ms-winsoundevent:Notification.Default', 'loop': 'false'}
                    elif sound_file == "none":
                        # Silent notification
                        audio_settings = {'silent': 'true'}
                    else:
                        # Custom sound file - we played it above, so silence the system notification
                        audio_settings = {'silent': 'true'}
                    
                    # Use native Windows toast notification
                    toast(
                        title=title,
                        body=message,
                        duration='short',  # 'short' = 7 seconds, 'long' = 25 seconds
                        app_id='BitCraft Companion',
                        audio=audio_settings,
                        scenario='reminder'  # This can help with visibility over games
                    )
                    logging.debug(f"Native toast notification shown: {title}")
                else:
                    # Fallback - just log the notification
                    logging.info(f"NOTIFICATION: {title} - {message}")
                
            except Exception as e:
                logging.error(f"Error showing notification: {e}")
                # Ultimate fallback - just log the notification
                logging.info(f"NOTIFICATION: {title} - {message}")
        
        # Run notification in a separate daemon thread to prevent UI blocking
        notification_thread = threading.Thread(target=_show_notification_thread, daemon=True)
        notification_thread.start()
    
    def get_available_sounds(self) -> List[str]:
        """
        Get list of available sound files for notifications.
        
        Returns:
            List of sound filenames
        """
        if self.sound_service:
            return self.sound_service.get_available_sounds()
        else:
            return []
    
    def get_sound_display_name(self, filename: str) -> str:
        """
        Get friendly display name for a sound file.
        
        Args:
            filename: Sound filename
            
        Returns:
            Friendly display name
        """
        if self.sound_service:
            return self.sound_service.get_sound_display_name(filename)
        return filename or "None (Silent)"
    
    def test_sound(self, filename: str):
        """
        Test play a sound file.
        
        Args:
            filename: Sound filename to test
        """
        if self.sound_service and filename and filename != "none":
            self.sound_service.test_sound(filename)
    
    def cleanup(self):
        """Clean up notification service resources."""
        try:
            if self._bundling_timer:
                self._bundling_timer.cancel()
                self._bundling_timer = None
            
            if self.sound_service:
                self.sound_service.cleanup()
                
        except Exception as e:
            logging.error(f"Error during notification service cleanup: {e}")
    
    def get_settings(self) -> Dict[str, Any]:
        """
        Get current notification settings.
        
        Returns:
            Dictionary with current notification settings
        """
        return self.settings.copy()