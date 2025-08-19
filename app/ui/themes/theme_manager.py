"""
Handles theme switching, persistence, and provides a centralized interface
for accessing theme colors throughout the application.
"""
import json
import logging
import os
from typing import Dict, Any, Callable, Optional

from .theme_definitions import AVAILABLE_THEMES, get_default_theme, get_theme_info
from ...core.data_paths import get_user_data_path


class ThemeManager:
    """Singleton theme manager for the application."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ThemeManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.current_theme_name = get_default_theme()
        self.current_theme_colors = None
        self.theme_change_callbacks = []
        self.settings_file = self._get_settings_file_path()
        
        # Load saved theme preference
        self._load_theme_preference()
        self._update_current_colors()
        
        logging.info(f"ThemeManager initialized with theme: {self.current_theme_name}")
    
    def _get_settings_file_path(self) -> str:
        """Get the path to the theme settings file using centralized data paths."""
        try:
            return get_user_data_path("theme_settings.json")
        except Exception as e:
            logging.error(f"Error getting theme settings path: {e}")
            return "theme_settings.json"  # Fallback to current directory
    
    def _load_theme_preference(self):
        """Load the saved theme preference from file."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                    saved_theme = data.get("current_theme", get_default_theme())
                    
                    # Validate the saved theme exists
                    if saved_theme in AVAILABLE_THEMES:
                        self.current_theme_name = saved_theme
                        logging.info(f"Loaded saved theme preference: {saved_theme}")
                    else:
                        logging.warning(f"Invalid saved theme '{saved_theme}', using default")
                        self.current_theme_name = get_default_theme()
        except Exception as e:
            logging.error(f"Error loading theme preference: {e}")
            self.current_theme_name = get_default_theme()
    
    def _save_theme_preference(self):
        """Save the current theme preference to file."""
        try:
            data = {"current_theme": self.current_theme_name}
            with open(self.settings_file, 'w') as f:
                json.dump(data, f, indent=2)
            logging.debug(f"Saved theme preference: {self.current_theme_name}")
        except Exception as e:
            logging.error(f"Error saving theme preference: {e}")
    
    def _update_current_colors(self):
        """Update the current theme colors based on the selected theme."""
        theme_info = get_theme_info(self.current_theme_name)
        self.current_theme_colors = theme_info["colors"]
    
    def get_current_theme_name(self) -> str:
        """Get the name of the current theme."""
        return self.current_theme_name
    
    def get_current_theme_info(self) -> Dict[str, Any]:
        """Get full information about the current theme."""
        return get_theme_info(self.current_theme_name)
    
    def get_available_themes(self) -> Dict[str, Dict[str, Any]]:
        """Get all available themes."""
        return AVAILABLE_THEMES.copy()
    
    def set_theme(self, theme_name: str) -> bool:
        """
        Set the current theme.
        
        Args:
            theme_name: Name of the theme to set
            
        Returns:
            bool: True if theme was changed, False if invalid or same theme
        """
        if theme_name not in AVAILABLE_THEMES:
            logging.error(f"Invalid theme name: {theme_name}")
            return False
        
        if theme_name == self.current_theme_name:
            logging.debug(f"Theme {theme_name} is already active")
            return False
        
        old_theme = self.current_theme_name
        self.current_theme_name = theme_name
        self._update_current_colors()
        
        # Save preference
        self._save_theme_preference()
        
        # Notify all registered callbacks
        self._notify_theme_change(old_theme, theme_name)
        
        logging.info(f"Theme changed from {old_theme} to {theme_name}")
        return True
    
    def get_color(self, color_name: str) -> str:
        """
        Get a color value from the current theme.
        
        Args:
            color_name: Name of the color (e.g., 'BACKGROUND_PRIMARY')
            
        Returns:
            str: Color value or fallback color if not found
        """
        if self.current_theme_colors is None:
            self._update_current_colors()
        
        try:
            return getattr(self.current_theme_colors, color_name)
        except AttributeError:
            logging.warning(f"Color '{color_name}' not found in theme, using fallback")
            # Return a fallback color based on the type
            if "BACKGROUND" in color_name:
                return "#2B2B2B"
            elif "TEXT" in color_name:
                return "#FFFFFF"
            elif "BORDER" in color_name:
                return "#404040"
            else:
                return "#CCCCCC"
    
    def register_theme_change_callback(self, callback: Callable[[str, str], None]):
        """
        Register a callback to be called when theme changes.
        
        Args:
            callback: Function that takes (old_theme, new_theme) as parameters
        """
        if callback not in self.theme_change_callbacks:
            self.theme_change_callbacks.append(callback)
            logging.debug(f"Registered theme change callback: {callback.__name__}")
    
    def unregister_theme_change_callback(self, callback: Callable[[str, str], None]):
        """
        Unregister a theme change callback.
        
        Args:
            callback: The callback function to remove
        """
        if callback in self.theme_change_callbacks:
            self.theme_change_callbacks.remove(callback)
            logging.debug(f"Unregistered theme change callback: {callback.__name__}")
    
    def _notify_theme_change(self, old_theme: str, new_theme: str):
        """Notify all registered callbacks about theme change."""
        for callback in self.theme_change_callbacks:
            try:
                callback(old_theme, new_theme)
            except Exception as e:
                logging.error(f"Error in theme change callback {callback.__name__}: {e}")
    
    def get_theme_colors_dict(self) -> Dict[str, str]:
        """
        Get all colors from the current theme as a dictionary.
        
        Returns:
            Dict[str, str]: Dictionary mapping color names to color values
        """
        if self.current_theme_colors is None:
            self._update_current_colors()
        
        colors = {}
        for attr_name in dir(self.current_theme_colors):
            if not attr_name.startswith('_'):
                colors[attr_name] = getattr(self.current_theme_colors, attr_name)
        
        return colors
    
    def reset_to_default(self) -> bool:
        """
        Reset theme to the default theme.
        
        Returns:
            bool: True if theme was changed, False if already default
        """
        default_theme = get_default_theme()
        return self.set_theme(default_theme)


# Global theme manager instance
_theme_manager_instance: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    """Get the global theme manager instance."""
    global _theme_manager_instance
    if _theme_manager_instance is None:
        _theme_manager_instance = ThemeManager()
    return _theme_manager_instance


def get_color(color_name: str) -> str:
    """
    Convenience function to get a color from the current theme.
    
    Args:
        color_name: Name of the color (e.g., 'BACKGROUND_PRIMARY')
        
    Returns:
        str: Color value
    """
    return get_theme_manager().get_color(color_name)


def set_theme(theme_name: str) -> bool:
    """
    Convenience function to set the current theme.
    
    Args:
        theme_name: Name of the theme to set
        
    Returns:
        bool: True if theme was changed
    """
    return get_theme_manager().set_theme(theme_name)


def register_theme_callback(callback: Callable[[str, str], None]):
    """
    Convenience function to register a theme change callback.
    
    Args:
        callback: Function that takes (old_theme, new_theme) as parameters
    """
    get_theme_manager().register_theme_change_callback(callback)