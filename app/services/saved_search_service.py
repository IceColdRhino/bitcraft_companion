"""
Saved Search Service for BitCraft Companion.

Manages persistence of user-defined search queries with names and metadata.
Stores searches in saved_searches.json in the user data directory.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pathlib import Path

from app.core.data_paths import get_user_data_path


class SavedSearchService:
    """Service for managing saved search queries."""
    
    def __init__(self):
        """Initialize the saved search service."""
        self.logger = logging.getLogger(__name__)
        self.file_path = get_user_data_path("saved_searches.json")
        self._searches: Dict[str, Dict] = {}
        self._load_searches()
    
    def _load_searches(self) -> None:
        """Load saved searches from the JSON file."""
        try:
            if Path(self.file_path).exists():
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    searches_list = data.get('searches', [])
                    
                    # Convert list to dict keyed by ID for easier management
                    self._searches = {search['id']: search for search in searches_list}
                    self.logger.info(f"Loaded {len(self._searches)} saved searches")
            else:
                self.logger.info("No saved searches file found, starting with empty collection")
                self._searches = {}
        except Exception as e:
            self.logger.error(f"Error loading saved searches: {e}")
            self._searches = {}
    
    def _save_searches(self) -> bool:
        """Save searches to the JSON file."""
        try:
            # Convert dict back to list format for JSON storage
            searches_list = list(self._searches.values())
            
            # Sort by last_used descending, then by created descending
            searches_list.sort(key=lambda x: (
                x.get('last_used', x.get('created', '')),
                x.get('created', '')
            ), reverse=True)
            
            data = {'searches': searches_list}
            
            # Ensure the directory exists
            Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"Saved {len(searches_list)} searches to {self.file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving searches: {e}")
            return False
    
    def save_search(self, name: str, query: str) -> Optional[str]:
        """
        Save a new search query.
        
        Args:
            name: Display name for the search
            query: The search query string
            
        Returns:
            Search ID if successful, None if failed
        """
        if not name or not name.strip():
            self.logger.warning("Cannot save search with empty name")
            return None
        
        if not query or not query.strip():
            self.logger.warning("Cannot save search with empty query")
            return None
        
        # Check if name already exists
        existing_search = self.get_search_by_name(name.strip())
        if existing_search:
            self.logger.warning(f"Search with name '{name.strip()}' already exists")
            return None
        
        search_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        search_data = {
            'id': search_id,
            'name': name.strip(),
            'query': query.strip(),
            'created': now,
            'last_used': now
        }
        
        self._searches[search_id] = search_data
        
        if self._save_searches():
            self.logger.info(f"Saved search '{name}' with query '{query}'")
            return search_id
        else:
            # Remove from memory if save failed
            self._searches.pop(search_id, None)
            return None
    
    def get_all_searches(self) -> List[Dict]:
        """
        Get all saved searches.
        
        Returns:
            List of search dictionaries sorted by last_used (most recent first)
        """
        searches = list(self._searches.values())
        
        # Sort by last_used descending, then by created descending
        searches.sort(key=lambda x: (
            x.get('last_used', x.get('created', '')),
            x.get('created', '')
        ), reverse=True)
        
        return searches
    
    def get_search_by_id(self, search_id: str) -> Optional[Dict]:
        """
        Get a search by its ID.
        
        Args:
            search_id: The search ID
            
        Returns:
            Search data dictionary or None if not found
        """
        return self._searches.get(search_id)
    
    def get_search_by_name(self, name: str) -> Optional[Dict]:
        """
        Get a search by its name.
        
        Args:
            name: The search name
            
        Returns:
            Search data dictionary or None if not found
        """
        name_lower = name.lower().strip()
        for search in self._searches.values():
            if search['name'].lower() == name_lower:
                return search
        return None
    
    def use_search(self, search_id: str) -> Optional[str]:
        """
        Mark a search as used (updates last_used timestamp) and return its query.
        
        Args:
            search_id: The search ID
            
        Returns:
            Search query string or None if not found
        """
        search = self._searches.get(search_id)
        if not search:
            self.logger.warning(f"Search with ID '{search_id}' not found")
            return None
        
        # Update last_used timestamp
        search['last_used'] = datetime.now(timezone.utc).isoformat()
        
        # Save the updated data
        self._save_searches()
        
        self.logger.debug(f"Used search '{search['name']}': {search['query']}")
        return search['query']
    
    def delete_search(self, search_id: str) -> bool:
        """
        Delete a saved search.
        
        Args:
            search_id: The search ID to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        search = self._searches.get(search_id)
        if not search:
            self.logger.warning(f"Cannot delete search with ID '{search_id}' - not found")
            return False
        
        search_name = search['name']
        del self._searches[search_id]
        
        if self._save_searches():
            self.logger.info(f"Deleted search '{search_name}'")
            return True
        else:
            # Restore if save failed
            self._searches[search_id] = search
            return False
    
    def update_search_name(self, search_id: str, new_name: str) -> bool:
        """
        Update the name of a saved search.
        
        Args:
            search_id: The search ID
            new_name: The new name for the search
            
        Returns:
            True if updated successfully, False otherwise
        """
        if not new_name or not new_name.strip():
            self.logger.warning("Cannot update search with empty name")
            return False
        
        search = self._searches.get(search_id)
        if not search:
            self.logger.warning(f"Cannot update search with ID '{search_id}' - not found")
            return False
        
        # Check if new name conflicts with existing search
        existing_search = self.get_search_by_name(new_name.strip())
        if existing_search and existing_search['id'] != search_id:
            self.logger.warning(f"Cannot update search name to '{new_name.strip()}' - name already exists")
            return False
        
        old_name = search['name']
        search['name'] = new_name.strip()
        
        if self._save_searches():
            self.logger.info(f"Updated search name from '{old_name}' to '{new_name.strip()}'")
            return True
        else:
            # Restore if save failed
            search['name'] = old_name
            return False
    
    def get_search_count(self) -> int:
        """Get the total number of saved searches."""
        return len(self._searches)
    
    def clear_all_searches(self) -> bool:
        """
        Clear all saved searches.
        
        Returns:
            True if cleared successfully, False otherwise
        """
        backup = self._searches.copy()
        self._searches.clear()
        
        if self._save_searches():
            self.logger.info("Cleared all saved searches")
            return True
        else:
            # Restore if save failed
            self._searches = backup
            return False