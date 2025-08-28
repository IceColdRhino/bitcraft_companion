"""
Search State Manager for BitCraft Companion.

Manages search state per window/tab to provide proper UX where each window
maintains its own search query independently.
"""

import logging
from typing import Dict, Optional


class SearchStateManager:
    """
    Manages search state for different windows/tabs in the application.
    
    Each window or tab can have its own search state that is preserved
    when switching between windows, providing a better user experience.
    """
    
    def __init__(self):
        """Initialize the search state manager."""
        self.logger = logging.getLogger(__name__)
        self._search_states: Dict[str, str] = {}
        
        # Initialize known window states
        self._initialize_default_states()
    
    def _initialize_default_states(self):
        """Initialize default search states for known windows."""
        default_windows = [
            "claim_inventory",
            "passive_crafting", 
            "active_crafting",
            "task_manager",
            "codex"
        ]
        
        for window_id in default_windows:
            self._search_states[window_id] = ""
        
        self.logger.debug(f"Initialized search states for {len(default_windows)} windows")
    
    def save_search_state(self, window_id: str, search_text: str) -> None:
        """
        Save the search state for a specific window.
        
        Args:
            window_id: Unique identifier for the window/tab
            search_text: Current search query text
        """
        if not isinstance(window_id, str):
            self.logger.warning(f"Invalid window_id type: {type(window_id)}")
            return
        
        if not isinstance(search_text, str):
            search_text = str(search_text) if search_text is not None else ""
        
        self._search_states[window_id] = search_text.strip()
        
        self.logger.debug(f"Saved search state for '{window_id}': '{search_text.strip()[:50]}{'...' if len(search_text.strip()) > 50 else ''}'")
    
    def restore_search_state(self, window_id: str) -> str:
        """
        Restore the search state for a specific window.
        
        Args:
            window_id: Unique identifier for the window/tab
            
        Returns:
            The saved search text for this window, or empty string if none
        """
        if not isinstance(window_id, str):
            self.logger.warning(f"Invalid window_id type: {type(window_id)}")
            return ""
        
        search_text = self._search_states.get(window_id, "")
        
        self.logger.debug(f"Restored search state for '{window_id}': '{search_text[:50]}{'...' if len(search_text) > 50 else ''}'")
        
        return search_text
    
    def clear_search_state(self, window_id: str) -> None:
        """
        Clear the search state for a specific window.
        
        Args:
            window_id: Unique identifier for the window/tab
        """
        if not isinstance(window_id, str):
            self.logger.warning(f"Invalid window_id type: {type(window_id)}")
            return
        
        self._search_states[window_id] = ""
        
        self.logger.debug(f"Cleared search state for '{window_id}'")
    
    def has_search_state(self, window_id: str) -> bool:
        """
        Check if a window has any saved search state.
        
        Args:
            window_id: Unique identifier for the window/tab
            
        Returns:
            True if the window has a non-empty search state
        """
        if not isinstance(window_id, str):
            return False
        
        return bool(self._search_states.get(window_id, "").strip())
    
    def get_all_search_states(self) -> Dict[str, str]:
        """
        Get all current search states.
        
        Returns:
            Dictionary of window_id -> search_text mappings
        """
        return self._search_states.copy()
    
    def clear_all_search_states(self) -> None:
        """Clear all search states across all windows."""
        for window_id in self._search_states:
            self._search_states[window_id] = ""
        
        self.logger.info("Cleared all search states")
    
    def get_active_search_windows(self) -> list:
        """
        Get list of windows that have active (non-empty) search states.
        
        Returns:
            List of window_id strings that have active searches
        """
        return [
            window_id for window_id, search_text in self._search_states.items()
            if search_text.strip()
        ]
    
    def register_window(self, window_id: str) -> None:
        """
        Register a new window for search state management.
        
        Args:
            window_id: Unique identifier for the window/tab
        """
        if not isinstance(window_id, str):
            self.logger.warning(f"Invalid window_id type: {type(window_id)}")
            return
        
        if window_id not in self._search_states:
            self._search_states[window_id] = ""
            self.logger.debug(f"Registered new search window: '{window_id}'")
    
    def unregister_window(self, window_id: str) -> None:
        """
        Unregister a window and clear its search state.
        
        Args:
            window_id: Unique identifier for the window/tab
        """
        if not isinstance(window_id, str):
            self.logger.warning(f"Invalid window_id type: {type(window_id)}")
            return
        
        if window_id in self._search_states:
            del self._search_states[window_id]
            self.logger.debug(f"Unregistered search window: '{window_id}'")


# Global search state manager instance
_search_state_manager = None


def get_search_state_manager() -> SearchStateManager:
    """Get the global search state manager instance."""
    global _search_state_manager
    if _search_state_manager is None:
        _search_state_manager = SearchStateManager()
    return _search_state_manager


def save_window_search_state(window_id: str, search_text: str) -> None:
    """Convenience function to save search state."""
    get_search_state_manager().save_search_state(window_id, search_text)


def restore_window_search_state(window_id: str) -> str:
    """Convenience function to restore search state."""
    return get_search_state_manager().restore_search_state(window_id)


def clear_window_search_state(window_id: str) -> None:
    """Convenience function to clear search state."""
    get_search_state_manager().clear_search_state(window_id)