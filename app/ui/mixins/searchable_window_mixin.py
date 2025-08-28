"""
SearchableWindowMixin for BitCraft Companion.

Provides search functionality that can be mixed into any window class.
Integrates SearchParser, SavedSearchService, search filtering logic,
and per-window search state management.
"""

import logging
from typing import Dict, List, Any, Optional, Callable
from abc import ABC, abstractmethod

from app.services.search_parser import SearchParser
from app.services.search_state_manager import get_search_state_manager
from app.services.tab_context_manager import get_tab_context_manager
from app.ui.components.search_bar import SearchBarComponent


class SearchableWindowMixin:
    """
    Mixin class that provides search functionality for windows.
    
    Classes that use this mixin should:
    1. Implement _get_searchable_data() to return data to search through
    2. Implement _apply_search_filter(filtered_data) to update UI with filtered results
    3. Call _setup_search() during initialization
    4. Optionally override _get_search_field_aliases() for custom field mappings
    """
    
    def _setup_search(
        self,
        container_widget,
        placeholder_text: str = "Search...",
        show_save_load: bool = True,
        show_clear: bool = True,
        custom_field_aliases: Optional[Dict[str, List[str]]] = None,
        window_id: str = "default",
        tab_context_config: Optional[Dict] = None
    ):
        """
        Set up search functionality for the window.
        
        Args:
            container_widget: Widget to pack the search bar into
            placeholder_text: Placeholder text for search field
            show_save_load: Whether to show save/load buttons
            show_clear: Whether to show clear button
            custom_field_aliases: Custom field aliases for SearchParser
            window_id: Unique identifier for this window's search state
            tab_context_config: Optional dict with tab configuration:
                {
                    'base_window_id': 'main',  # Base window identifier
                    'tabs': {
                        'inventory': {'placeholder': 'Search inventory...'},
                        'crafting': {'placeholder': 'Search crafting...'}
                    }
                }
        """
        self.logger = logging.getLogger(__name__)
        
        # Initialize search components
        self.search_parser = SearchParser()
        self.window_id = window_id
        self.search_state_manager = get_search_state_manager()
        self.filtered_data = []
        self.container_widget = container_widget
        
        # Tab context management
        self.tab_context_config = tab_context_config
        self.tab_context_manager = None
        if tab_context_config:
            base_id = tab_context_config.get('base_window_id', window_id)
            self.tab_context_manager = get_tab_context_manager(base_id)
            
            # Register tabs with context manager
            tabs_config = tab_context_config.get('tabs', {})
            for tab_name, tab_config in tabs_config.items():
                self.tab_context_manager.register_tab(
                    tab_name, 
                    placeholder_text=tab_config.get('placeholder', placeholder_text)
                )
            
            # Register for tab switch events
            self.tab_context_manager.register_tab_switch_callback(self._on_tab_switch)
            
            # Register all tab window IDs with search state manager
            for tab_window_id in self.tab_context_manager.get_all_tab_window_ids():
                self.search_state_manager.register_window(tab_window_id)
        else:
            # Register this window with the search state manager (traditional behavior)
            self.search_state_manager.register_window(self.window_id)
        
        # Add custom field aliases if provided
        if custom_field_aliases:
            self.search_parser.FIELD_ALIASES.update(custom_field_aliases)
        
        # Create search bar component
        self.search_bar = SearchBarComponent(
            container_widget,
            placeholder_text=placeholder_text,
            show_save_load=show_save_load,
            show_clear=show_clear,
            on_search_change=self._on_search_change
        )
        
        # Restore search state for this window
        self._restore_search_state()
        
        # Apply initial search state - but be defensive about timing
        try:
            self._apply_search_filter()
        except Exception as e:
            self.logger.debug(f"Initial search filter failed, will retry: {e}")
            # Retry after brief delay if initial application fails
            self.container_widget.after(500, lambda: self._safe_apply_search_filter())
    
    def _safe_apply_search_filter(self):
        """Safely apply search filter with error handling."""
        try:
            self._apply_search_filter()
        except Exception as e:
            self.logger.warning(f"Delayed search filter application failed: {e}")
    
    def _on_tab_switch(self, old_tab: str, new_tab: str, tab_config: Dict):
        """
        Handle tab switching when using tab context management.
        
        Args:
            old_tab: Previously active tab name
            new_tab: Newly active tab name  
            tab_config: Configuration for the new tab
        """
        if not hasattr(self, 'search_bar'):
            return
            
        try:
            # Save search state for old tab
            if old_tab:
                old_window_id = f"{self.tab_context_manager.base_window_id}_{old_tab}"
                current_search = self.search_bar.get_search_text()
                self.search_state_manager.save_search_state(old_window_id, current_search)
            
            # Update current window ID
            self.window_id = tab_config.get('window_id')
            
            # Restore search state for new tab
            saved_search = self.search_state_manager.restore_search_state(self.window_id)
            if saved_search:
                self.search_bar.set_search_text(saved_search)
            else:
                self.search_bar.clear_search()
            
            # Update placeholder text
            placeholder = tab_config.get('placeholder_text', "Search...")
            self.search_bar.set_placeholder_text(placeholder)
            
            # Reapply search filter with new context
            self._apply_search_filter()
            
            self.logger.debug(f"Switched search context from '{old_tab}' to '{new_tab}'")
            
        except Exception as e:
            self.logger.error(f"Error handling tab switch: {e}")
    
    def switch_tab_context(self, tab_name: str):
        """
        Switch to a different tab context (for manual tab switching).
        
        Args:
            tab_name: Name of the tab to switch to
        """
        if self.tab_context_manager:
            self.tab_context_manager.switch_to_tab(tab_name)
        else:
            self.logger.warning("No tab context manager configured for search")
    
    def get_current_window_id(self) -> str:
        """
        Get the current effective window ID (considers tab contexts).
        
        Returns:
            Current window ID string
        """
        if self.tab_context_manager:
            return self.tab_context_manager.get_current_window_id()
        return self.window_id
    
    def _on_search_change(self):
        """Handle search text changes."""
        try:
            new_search_text = self.search_bar.get_search_text()
            
            # Save search state for current window (may be tab-specific)
            current_window_id = self.get_current_window_id()
            self.search_state_manager.save_search_state(current_window_id, new_search_text)
            
            # Apply search filter
            self._apply_search_filter()
                
        except Exception as e:
            self.logger.error(f"Error processing search change: {e}")
    
    def _apply_search_filter(self):
        """Apply search filter to data and update UI."""
        try:
            # Get searchable data from the implementing class
            all_data = self._get_searchable_data()
            
            # Get current search text from the current window's state
            current_window_id = self.get_current_window_id()
            current_search_text = self.search_state_manager.restore_search_state(current_window_id)
            
            if not current_search_text:
                # No search - show all data
                self.filtered_data = all_data
            else:
                # Parse search query and filter data
                parsed_query = self.search_parser.parse_search_query(current_search_text)
                self.filtered_data = [
                    item for item in all_data 
                    if self.search_parser.match_row(item, parsed_query)
                ]
            
            # Update UI with filtered results
            self._update_ui_with_filtered_data(self.filtered_data)
            
        except Exception as e:
            self.logger.error(f"Error applying search filter: {e}")
            # Fallback to showing all data
            self.filtered_data = self._get_searchable_data()
            self._update_ui_with_filtered_data(self.filtered_data)
    
    def get_search_text(self) -> str:
        """Get the current search text."""
        if hasattr(self, 'search_bar'):
            return self.search_bar.get_search_text()
        return ""
    
    def set_search_text(self, text: str):
        """Set the search text and trigger filtering."""
        if hasattr(self, 'search_bar'):
            self.search_bar.set_search_text(text)
            self._on_search_change()
    
    def clear_search(self):
        """Clear the search and show all data."""
        if hasattr(self, 'search_bar'):
            self.search_bar.clear_search()
    
    def focus_search(self):
        """Set focus to the search field."""
        if hasattr(self, 'search_bar'):
            self.search_bar.focus_search_field()
    
    def set_search_placeholder(self, placeholder: str):
        """Update the search placeholder text."""
        if hasattr(self, 'search_bar'):
            self.search_bar.set_placeholder_text(placeholder)
    
    def update_search_theme(self):
        """Update search bar theme colors."""
        if hasattr(self, 'search_bar'):
            self.search_bar.update_theme_colors()
    
    def _restore_search_state(self):
        """Restore the search state for this window."""
        if hasattr(self, 'search_bar') and hasattr(self, 'search_state_manager'):
            current_window_id = self.get_current_window_id()
            saved_search = self.search_state_manager.restore_search_state(current_window_id)
            if saved_search:
                self.search_bar.set_search_text(saved_search)
    
    def _save_current_search_state(self):
        """Save the current search state for this window."""
        if hasattr(self, 'search_bar') and hasattr(self, 'search_state_manager'):
            current_search = self.search_bar.get_search_text()
            current_window_id = self.get_current_window_id()
            self.search_state_manager.save_search_state(current_window_id, current_search)
    
    def _clear_window_search_state(self):
        """Clear the search state for this window only."""
        if hasattr(self, 'search_state_manager'):
            current_window_id = self.get_current_window_id()
            self.search_state_manager.clear_search_state(current_window_id)
            if hasattr(self, 'search_bar'):
                self.search_bar.clear_search()
    
    # Abstract methods that implementing classes must override
    
    @abstractmethod
    def _get_searchable_data(self) -> List[Dict[str, Any]]:
        """
        Return the data to search through.
        
        Should return a list of dictionaries where each dict represents
        a searchable item with string/numeric field values.
        
        Returns:
            List of dictionaries representing searchable items
        """
        pass
    
    @abstractmethod  
    def _update_ui_with_filtered_data(self, filtered_data: List[Dict[str, Any]]):
        """
        Update the UI to display filtered search results.
        
        Args:
            filtered_data: List of items that match the current search query
        """
        pass
    
    # Optional methods that can be overridden for customization
    
    def _get_search_field_aliases(self) -> Dict[str, List[str]]:
        """
        Return custom field aliases for this window's search.
        
        Override this method to provide window-specific search field mappings.
        
        Returns:
            Dictionary mapping search field names to actual data field names
        """
        return {}
    
    def _preprocess_search_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Preprocess raw data before search filtering.
        
        Override this method to transform data before search processing
        (e.g., flatten nested structures, add computed fields, etc.)
        
        Args:
            raw_data: Raw data from _get_searchable_data()
            
        Returns:
            Processed data ready for search filtering
        """
        return raw_data
    
    def _postprocess_search_results(self, filtered_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Postprocess filtered search results before UI update.
        
        Override this method to modify search results after filtering
        (e.g., sorting, grouping, adding display fields, etc.)
        
        Args:
            filtered_data: Filtered data from search processing
            
        Returns:
            Final data ready for UI display
        """
        return filtered_data


class SearchableTabMixin(SearchableWindowMixin):
    """
    Specialized version of SearchableWindowMixin for tab components.
    
    Provides additional functionality specific to tabs that are part of
    a larger tabbed interface.
    """
    
    def _setup_search_for_tab(
        self,
        container_widget,
        placeholder_text: str = "Search...",
        show_save_load: bool = False,  # Usually tabs don't need save/load
        show_clear: bool = True,
        custom_field_aliases: Optional[Dict[str, List[str]]] = None
    ):
        """
        Set up search functionality optimized for tab usage.
        
        Args:
            container_widget: Widget to pack the search bar into
            placeholder_text: Placeholder text for search field
            show_save_load: Whether to show save/load buttons (usually False for tabs)
            show_clear: Whether to show clear button
            custom_field_aliases: Custom field aliases for SearchParser
        """
        self._setup_search(
            container_widget=container_widget,
            placeholder_text=placeholder_text,
            show_save_load=show_save_load,
            show_clear=show_clear,
            custom_field_aliases=custom_field_aliases
        )
    
    def refresh_search_results(self):
        """
        Refresh search results (useful when tab data changes).
        
        Call this method when the underlying data changes to refresh
        search results without changing the search query.
        """
        self._apply_search_filter()