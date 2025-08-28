"""
Tab Context Manager for BitCraft Companion.

Manages tab-specific search contexts and states, allowing different tabs
within a window to maintain independent search states.
"""

import logging
from typing import Dict, Optional, Callable


class TabContextManager:
    """
    Manages tab-specific search contexts within a window.
    
    Handles switching between tabs, preserving search state per tab,
    and managing tab-specific configurations like placeholder text.
    """
    
    def __init__(self, base_window_id: str):
        """
        Initialize the tab context manager.
        
        Args:
            base_window_id: Base identifier for the window (e.g., "main", "codex")
        """
        self.logger = logging.getLogger(__name__)
        self.base_window_id = base_window_id
        self.current_tab = None
        self.tab_configs = {}  # tab_name -> configuration dict
        
        # Callbacks for tab switching events
        self.on_tab_switch_callbacks = []
        
        self.logger.debug(f"Initialized TabContextManager for '{base_window_id}'")
    
    def register_tab(self, tab_name: str, placeholder_text: str = None, **config):
        """
        Register a new tab with the context manager.
        
        Args:
            tab_name: Name of the tab (e.g., "inventory", "crafting")
            placeholder_text: Tab-specific placeholder text for search
            **config: Additional tab-specific configuration options
        """
        if not isinstance(tab_name, str):
            self.logger.warning(f"Invalid tab_name type: {type(tab_name)}")
            return
        
        self.tab_configs[tab_name] = {
            'placeholder_text': placeholder_text or f"Search {tab_name}...",
            'window_id': f"{self.base_window_id}_{tab_name}",
            **config
        }
        
        self.logger.debug(f"Registered tab '{tab_name}' with window ID '{self.tab_configs[tab_name]['window_id']}'")
    
    def switch_to_tab(self, tab_name: str) -> Dict:
        """
        Switch to a different tab context.
        
        Args:
            tab_name: Name of the tab to switch to
            
        Returns:
            Dict containing tab configuration
        """
        if not isinstance(tab_name, str):
            self.logger.warning(f"Invalid tab_name type: {type(tab_name)}")
            return {}
        
        if tab_name not in self.tab_configs:
            self.logger.warning(f"Tab '{tab_name}' not registered in context manager")
            # Auto-register with default config
            self.register_tab(tab_name)
        
        old_tab = self.current_tab
        self.current_tab = tab_name
        tab_config = self.tab_configs[tab_name]
        
        # Trigger callbacks
        for callback in self.on_tab_switch_callbacks:
            try:
                callback(old_tab, tab_name, tab_config)
            except Exception as e:
                self.logger.error(f"Error in tab switch callback: {e}")
        
        self.logger.debug(f"Switched from '{old_tab}' to '{tab_name}' (ID: {tab_config['window_id']})")
        return tab_config
    
    def get_current_tab_config(self) -> Dict:
        """
        Get configuration for the currently active tab.
        
        Returns:
            Dict containing current tab configuration
        """
        if self.current_tab and self.current_tab in self.tab_configs:
            return self.tab_configs[self.current_tab]
        return {}
    
    def get_current_window_id(self) -> str:
        """
        Get the search window ID for the currently active tab.
        
        Returns:
            Window ID string for current tab
        """
        config = self.get_current_tab_config()
        return config.get('window_id', f"{self.base_window_id}_default")
    
    def get_current_placeholder(self) -> str:
        """
        Get the placeholder text for the currently active tab.
        
        Returns:
            Placeholder text string for current tab
        """
        config = self.get_current_tab_config()
        return config.get('placeholder_text', "Search...")
    
    def register_tab_switch_callback(self, callback: Callable):
        """
        Register a callback to be called when tabs are switched.
        
        Args:
            callback: Function to call with (old_tab, new_tab, tab_config) parameters
        """
        if callback not in self.on_tab_switch_callbacks:
            self.on_tab_switch_callbacks.append(callback)
            self.logger.debug("Registered tab switch callback")
    
    def unregister_tab_switch_callback(self, callback: Callable):
        """
        Unregister a tab switch callback.
        
        Args:
            callback: Function to remove from callbacks list
        """
        if callback in self.on_tab_switch_callbacks:
            self.on_tab_switch_callbacks.remove(callback)
            self.logger.debug("Unregistered tab switch callback")
    
    def get_all_tab_window_ids(self) -> list:
        """
        Get all window IDs for registered tabs.
        
        Returns:
            List of window ID strings
        """
        return [config['window_id'] for config in self.tab_configs.values()]
    
    def cleanup(self):
        """Clean up resources and callbacks."""
        self.on_tab_switch_callbacks.clear()
        self.tab_configs.clear()
        self.current_tab = None
        self.logger.debug(f"Cleaned up TabContextManager for '{self.base_window_id}'")


# Global registry for tab context managers
_tab_context_managers: Dict[str, TabContextManager] = {}


def get_tab_context_manager(base_window_id: str) -> TabContextManager:
    """
    Get or create a tab context manager for a window.
    
    Args:
        base_window_id: Base identifier for the window
        
    Returns:
        TabContextManager instance
    """
    if base_window_id not in _tab_context_managers:
        _tab_context_managers[base_window_id] = TabContextManager(base_window_id)
    
    return _tab_context_managers[base_window_id]


def cleanup_tab_context_manager(base_window_id: str):
    """
    Clean up and remove a tab context manager.
    
    Args:
        base_window_id: Base identifier for the window
    """
    if base_window_id in _tab_context_managers:
        _tab_context_managers[base_window_id].cleanup()
        del _tab_context_managers[base_window_id]