"""
Reference Data Caching Service

Provides persistent caching for reference data (items, buildings, recipes, etc.)
to dramatically reduce startup time from 4.4s to <1s.
"""

import json
import logging
import os
import time
from typing import Dict, Optional
from pathlib import Path


class ReferenceCacheService:
    """
    Manages local caching of reference data with version tracking and TTL.
    
    Reduces startup time by caching reference data locally and only re-downloading
    when the cache is stale or invalid.
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the reference cache service.
        
        Args:
            cache_dir: Directory to store cache files (defaults to app cache directory)
        """
        self.cache_dir = Path(cache_dir) if cache_dir else self._get_default_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.cache_file = self.cache_dir / "reference_data_cache.json"
        self.metadata_file = self.cache_dir / "reference_cache_metadata.json"
        
        # Cache settings
        self.cache_ttl = 24 * 60 * 60  # 24 hours in seconds
        self.cache_version = "1.0"  # Increment when cache format changes
        
        logging.debug(f"ReferenceCacheService initialized - cache dir: {self.cache_dir}")
    
    def _get_default_cache_dir(self) -> Path:
        """Get the default cache directory."""
        if os.name == 'nt':  # Windows
            cache_base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        else:  # Unix-like
            cache_base = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
        
        return cache_base / 'BitCraftCompanion' / 'reference_cache'
    
    def get_cached_reference_data(self) -> Optional[Dict]:
        """
        Get cached reference data if valid.
        
        Returns:
            Dict: Cached reference data if valid, None if cache miss/invalid
        """
        try:
            # Check if cache files exist
            if not self.cache_file.exists() or not self.metadata_file.exists():
                logging.debug("Reference cache files not found")
                return None
            
            # Load metadata to check validity
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # Validate cache version
            if metadata.get('cache_version') != self.cache_version:
                logging.info(f"Reference cache version mismatch: {metadata.get('cache_version')} != {self.cache_version}")
                return None
            
            # Check TTL
            cached_time = metadata.get('timestamp', 0)
            current_time = time.time()
            age = current_time - cached_time
            
            if age > self.cache_ttl:
                logging.info(f"Reference cache expired: {age:.1f}s > {self.cache_ttl}s")
                return None
            
            # Load cached data
            cache_start = time.time()
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                reference_data = json.load(f)
            cache_load_time = time.time() - cache_start
            
            # Validate data structure
            if not self._validate_cache_data(reference_data):
                logging.warning("Reference cache data validation failed")
                return None
            
            total_records = sum(len(table_data) for table_data in reference_data.values())
            logging.debug(f"Reference cache HIT - loaded {total_records} records from cache ({cache_load_time:.3f}s)")
            
            return reference_data
            
        except Exception as e:
            logging.warning(f"Error loading reference cache: {e}")
            return None
    
    def cache_reference_data(self, reference_data: Dict) -> bool:
        """
        Cache reference data to disk.
        
        Args:
            reference_data: Reference data dictionary to cache
            
        Returns:
            bool: True if caching succeeded, False otherwise
        """
        try:
            if not reference_data:
                logging.warning("No reference data to cache")
                return False
            
            cache_start = time.time()
            
            # Validate data before caching
            if not self._validate_cache_data(reference_data):
                logging.error("Reference data validation failed - not caching")
                return False
            
            # Save reference data
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(reference_data, f, separators=(',', ':'))  # Compact JSON
            
            # Save metadata
            metadata = {
                'timestamp': time.time(),
                'cache_version': self.cache_version,
                'table_count': len(reference_data),
                'total_records': sum(len(table_data) for table_data in reference_data.values())
            }
            
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            cache_time = time.time() - cache_start
            logging.debug(f"Reference data cached successfully - {metadata['total_records']} records ({cache_time:.3f}s)")
            
            return True
            
        except Exception as e:
            logging.error(f"Error caching reference data: {e}")
            return False
    
    def _validate_cache_data(self, reference_data: Dict) -> bool:
        """
        Validate cached reference data structure.
        
        Args:
            reference_data: Data to validate
            
        Returns:
            bool: True if data is valid, False otherwise
        """
        try:
            if not isinstance(reference_data, dict):
                return False
            
            # Expected reference tables
            expected_tables = {
                'resource_desc', 'item_desc', 'cargo_desc', 'building_desc',
                'building_function_type_mapping_desc', 'building_type_desc',
                'crafting_recipe_desc', 'claim_tile_cost', 'npc_desc'
            }
            
            # Check that we have the core tables
            core_tables = {'item_desc', 'building_desc', 'crafting_recipe_desc'}
            if not core_tables.issubset(reference_data.keys()):
                logging.warning(f"Missing core reference tables: {core_tables - reference_data.keys()}")
                return False
            
            # Check that each table has reasonable data
            for table_name, table_data in reference_data.items():
                if not isinstance(table_data, list):
                    logging.warning(f"Table {table_name} is not a list")
                    return False
                
                # Core tables should have substantial data
                if table_name in core_tables and len(table_data) < 100:
                    logging.warning(f"Core table {table_name} has too few records: {len(table_data)}")
                    return False
            
            return True
            
        except Exception as e:
            logging.warning(f"Cache validation error: {e}")
            return False
    
    def clear_cache(self) -> bool:
        """
        Clear the reference data cache.
        
        Returns:
            bool: True if cache was cleared successfully
        """
        try:
            files_removed = 0
            
            if self.cache_file.exists():
                self.cache_file.unlink()
                files_removed += 1
            
            if self.metadata_file.exists():
                self.metadata_file.unlink()
                files_removed += 1
            
            logging.info(f"Reference cache cleared - {files_removed} files removed")
            return True
            
        except Exception as e:
            logging.error(f"Error clearing reference cache: {e}")
            return False
    
    def get_cache_info(self) -> Dict:
        """
        Get information about the current cache state.
        
        Returns:
            Dict: Cache information including age, size, validity
        """
        info = {
            'cache_exists': False,
            'cache_valid': False,
            'cache_age_hours': None,
            'table_count': 0,
            'total_records': 0,
            'cache_size_mb': 0
        }
        
        try:
            if self.cache_file.exists() and self.metadata_file.exists():
                info['cache_exists'] = True
                
                # Get file size
                cache_size = self.cache_file.stat().st_size
                info['cache_size_mb'] = cache_size / (1024 * 1024)
                
                # Load metadata
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # Calculate age
                cached_time = metadata.get('timestamp', 0)
                age_seconds = time.time() - cached_time
                info['cache_age_hours'] = age_seconds / 3600
                
                # Check validity
                version_valid = metadata.get('cache_version') == self.cache_version
                ttl_valid = age_seconds <= self.cache_ttl
                info['cache_valid'] = version_valid and ttl_valid
                
                info['table_count'] = metadata.get('table_count', 0)
                info['total_records'] = metadata.get('total_records', 0)
        
        except Exception as e:
            logging.debug(f"Error getting cache info: {e}")
        
        return info