import logging
import time
import hashlib
from typing import Dict, List, Callable, Optional, Any

from app.services.background_processor import BackgroundProcessor


class OptimizedTableMixin:
    """
    Mixin class providing high-performance table optimizations.
    
    Provides:
    - Background processing for heavy operations
    - Smart caching with memory management
    - Debouncing for rapid events
    - Lazy loading for large datasets
    - Differential UI updates
    """

    def __init_optimization__(
        self,
        max_workers: int = 2,
        max_cache_size_mb: int = 50,
        lazy_load_threshold: int = 50,
        debounce_delays: Optional[Dict[str, int]] = None
    ):
        """Initialize optimization features."""
        
        # Background processing (lazy initialization)
        self._background_processor = None
        self._max_workers = max_workers
        self._pending_tasks = {}
        
        # Smart caching
        self._result_cache = {}
        self._cache_keys = {"data_version": 0}
        self._memory_manager = {
            "max_cache_size_mb": max_cache_size_mb,
            "cache_cleanup_threshold": 0.8,
            "item_pool": {},
        }
        
        # Differential updates
        self._ui_item_cache = {}
        self._last_data_hash = {}
        self._tree_needs_full_rebuild = True
        self._last_search_text = ""
        
        # UI performance
        self._debounce_timers = {}
        self._update_pending = False
        self._lazy_load_threshold = lazy_load_threshold
        
        # Configurable debounce delays
        default_delays = {
            "data_update": 50,
            "apply_filter": 150,
            "render_table": 50,
            "scroll_handler": 100
        }
        self._debounce_delays = {**default_delays, **(debounce_delays or {})}

    @property
    def background_processor(self):
        """Lazy initialization of background processor to avoid startup conflicts."""
        if self._background_processor is None:
            try:
                self._background_processor = BackgroundProcessor(max_workers=self._max_workers)
                self._background_processor.set_main_thread_scheduler(self.after)
                logging.debug(f"Background processor initialized for {self.__class__.__name__}")
            except Exception as e:
                logging.error(f"Failed to initialize background processor: {e}")
                # Fallback to None - operations will use synchronous processing
        return self._background_processor

    def _debounce_operation(self, operation_name: str, callback: Callable, *args, **kwargs):
        """Debounce operations to prevent rapid successive calls."""
        delay_ms = self._debounce_delays.get(operation_name, 100)
        
        if operation_name in self._debounce_timers:
            self.after_cancel(self._debounce_timers[operation_name])
        
        self._debounce_timers[operation_name] = self.after(
            delay_ms, 
            lambda: self._execute_debounced_operation(operation_name, callback, *args, **kwargs)
        )

    def _execute_debounced_operation(self, operation_name: str, callback: Callable, *args, **kwargs):
        """Execute a debounced operation and clean up its timer."""
        try:
            self._debounce_timers.pop(operation_name, None)
            callback(*args, **kwargs)
        except Exception as e:
            logging.error(f"Error executing debounced operation {operation_name}: {e}")

    def _submit_background_task(
        self, 
        task_name: str, 
        func: Callable, 
        callback: Callable,
        error_callback: Optional[Callable] = None,
        priority: int = 1,
        *args, 
        **kwargs
    ) -> str:
        """Submit a task to background processing with automatic cancellation."""
        
        # Always use synchronous processing for the first few seconds to avoid startup conflicts
        if not hasattr(self, '_startup_complete') or not self._startup_complete:
            if not hasattr(self, '_startup_time'):
                self._startup_time = time.time()
            
            # Use synchronous processing for first 10 seconds after initialization
            if time.time() - self._startup_time < 10:
                logging.debug(f"Startup phase: using synchronous processing for {task_name}")
                try:
                    result = func(*args, **kwargs)
                    callback(result)
                    return f"startup_sync_{task_name}"
                except Exception as e:
                    if error_callback:
                        error_callback(e)
                    else:
                        self._default_error_callback(e)
                    return f"startup_error_{task_name}"
            else:
                self._startup_complete = True
        
        # Check if background processor is available
        if self.background_processor is None:
            logging.debug(f"Background processor not available, using synchronous processing for {task_name}")
            try:
                result = func(*args, **kwargs)
                callback(result)
                return f"sync_{task_name}"
            except Exception as e:
                if error_callback:
                    error_callback(e)
                else:
                    self._default_error_callback(e)
                return f"sync_error_{task_name}"
        
        if task_name in self._pending_tasks:
            self.background_processor.cancel_task(self._pending_tasks[task_name])
        
        bg_task_id = self.background_processor.submit_task(
            func,
            *args,
            callback=callback,
            error_callback=error_callback or self._default_error_callback,
            priority=priority,
            task_name=task_name,
            **kwargs
        )
        self._pending_tasks[task_name] = bg_task_id
        return bg_task_id

    def _default_error_callback(self, error):
        """Default error handler for background tasks."""
        logging.error(f"Background task failed: {error}")

    def _generate_cache_key(self, operation_type: str, *params) -> str:
        """Generate unique cache key for operations."""
        params_str = "|".join(str(p) for p in params)
        key_str = f"{operation_type}:{params_str}"
        return f"{operation_type}_{hashlib.md5(key_str.encode()).hexdigest()}"

    def _cache_result(self, cache_key: str, data: Any):
        """Cache operation result with timestamp and data version."""
        self._result_cache[cache_key] = {
            "data": data,
            "data_version": self._cache_keys["data_version"],
            "timestamp": time.time(),
        }
        self._cleanup_cache_if_needed()

    def _get_cached_result(self, cache_key: str) -> Optional[Any]:
        """Retrieve cached result if valid."""
        if cache_key in self._result_cache:
            cached = self._result_cache[cache_key]
            if cached["data_version"] == self._cache_keys["data_version"]:
                return cached["data"]
        return None

    def _invalidate_cache(self, pattern: Optional[str] = None):
        """Invalidate cache entries matching pattern, or all if no pattern."""
        if pattern is None:
            self._result_cache.clear()
            logging.debug("Cleared all cache entries")
        else:
            keys_to_remove = [k for k in self._result_cache.keys() if k.startswith(pattern)]
            for key in keys_to_remove:
                del self._result_cache[key]
            logging.debug(f"Cleared {len(keys_to_remove)} cache entries matching {pattern}")

    def _increment_data_version(self):
        """Increment data version to invalidate all caches."""
        self._cache_keys["data_version"] += 1
        self._invalidate_cache()

    def _cleanup_cache_if_needed(self):
        """Clean cache if it exceeds memory limits."""
        cache_size = self._estimate_cache_size()
        max_size = self._memory_manager["max_cache_size_mb"] * 1024 * 1024
        
        if cache_size > max_size * self._memory_manager["cache_cleanup_threshold"]:
            self._cleanup_old_cache_entries()

    def _estimate_cache_size(self) -> int:
        """Estimate memory usage of cache."""
        try:
            import sys
            total_size = 0
            for cached in self._result_cache.values():
                data_size = sys.getsizeof(cached.get("data", []))
                total_size += data_size + 200  # Metadata overhead
            return total_size
        except Exception:
            return 0

    def _cleanup_old_cache_entries(self, max_age_seconds: int = 300, max_entries: int = 50):
        """Remove old cache entries to prevent memory bloat."""
        current_time = time.time()
        keys_to_remove = []
        
        # Remove old entries
        for key, cached in self._result_cache.items():
            if current_time - cached.get("timestamp", 0) > max_age_seconds:
                keys_to_remove.append(key)
        
        # Remove excess entries
        if len(self._result_cache) - len(keys_to_remove) > max_entries:
            remaining = [(k, v) for k, v in self._result_cache.items() if k not in keys_to_remove]
            remaining.sort(key=lambda x: x[1].get("timestamp", 0))
            oldest = remaining[:-max_entries]
            keys_to_remove.extend([k for k, v in oldest])
        
        # Clean up
        for key in keys_to_remove:
            del self._result_cache[key]
        
        if len(self._memory_manager["item_pool"]) > 1000:
            self._memory_manager["item_pool"].clear()
        
        if keys_to_remove:
            logging.debug(f"Cleaned up {len(keys_to_remove)} cache entries")

    def _generate_item_key(self, item_data: Dict) -> str:
        """Generate unique key for tracking items with object pooling."""
        # This should be overridden by subclasses with item-specific logic
        key_parts = tuple(str(item_data.get(field, "")) for field in ["name", "id", "tier"])
        
        if key_parts not in self._memory_manager["item_pool"]:
            self._memory_manager["item_pool"][key_parts] = "|".join(key_parts)
        
        return self._memory_manager["item_pool"][key_parts]

    def _has_data_changed(self, new_data: List[Dict]) -> bool:
        """Optimized change detection with memory-efficient hashing."""
        try:
            if len(new_data) != len(self.all_data):
                return True
            
            # For large datasets, use simpler comparison
            if len(new_data) > 200:
                new_signature = hash(tuple(
                    tuple(item.get(field, "") for field in self._get_comparison_fields())
                    for item in new_data
                ))
                old_signature = getattr(self, "_last_data_signature", None)
                
                if new_signature != old_signature:
                    self._last_data_signature = new_signature
                    return True
                return False
            
            # Detailed comparison for smaller datasets
            new_hash = {}
            for item in new_data:
                key = self._generate_item_key(item)
                item_tuple = tuple(item.get(field, "") for field in self._get_comparison_fields())
                new_hash[key] = hash(item_tuple)
            
            if new_hash != self._last_data_hash:
                self._last_data_hash = new_hash
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"Error checking data changes: {e}")
            return True

    def _get_comparison_fields(self) -> List[str]:
        """Get fields to compare for change detection. Override in subclasses."""
        return ["name", "quantity", "tier"]

    def _render_lazy_loading(self, data: List[Dict]):
        """Render data with lazy loading."""
        self.tree.delete(*self.tree.get_children())
        self._ui_item_cache.clear()
        
        # Calculate visible rows
        try:
            visible_height = self.tree.winfo_height()
            row_height = 24
            visible_rows = max(20, min(100, visible_height // row_height + 10))
        except:
            visible_rows = self._lazy_load_threshold
        
        # Load initial batch
        initial_items = data[:visible_rows]
        for item_data in initial_items:
            self._insert_tree_item(item_data)
        
        # Schedule remaining items
        if len(data) > visible_rows:
            remaining_items = data[visible_rows:]
            self._schedule_lazy_load(remaining_items, batch_size=25)

    def _schedule_lazy_load(self, remaining_items: List[Dict], batch_size: int = 25):
        """Schedule lazy loading of remaining items."""
        if not remaining_items:
            return
        
        batch = remaining_items[:batch_size]
        for item_data in batch:
            self._insert_tree_item(item_data)
        
        if len(remaining_items) > batch_size:
            next_batch = remaining_items[batch_size:]
            self.after(10, lambda: self._schedule_lazy_load(next_batch, batch_size))

    def _insert_tree_item(self, item_data: Dict):
        """Insert item into tree. Must be implemented by subclass."""
        raise NotImplementedError("Subclass must implement _insert_tree_item")

    def _render_differential(self, data: List[Dict]):
        """Render with differential updates."""
        current_items = set()
        current_data_map = {}
        
        for item_data in data:
            item_key = self._generate_item_key(item_data)
            current_items.add(item_key)
            current_data_map[item_key] = item_data
        
        # Remove obsolete items
        cached_items = set(self._ui_item_cache.keys())
        for item_key in cached_items - current_items:
            if item_key in self._ui_item_cache:
                try:
                    self.tree.delete(self._ui_item_cache[item_key])
                except:
                    pass
                del self._ui_item_cache[item_key]
        
        # Add new items
        for item_key in current_items - cached_items:
            self._insert_tree_item(current_data_map[item_key])
        
        # Update existing items
        for item_key in current_items & cached_items:
            self._update_tree_item_if_changed(item_key, current_data_map[item_key])

    def _update_tree_item_if_changed(self, item_key: str, item_data: Dict):
        """Update tree item if changed. Should be implemented by subclass."""
        # Default implementation - subclasses should override for specific update logic
        pass

    def optimization_shutdown(self):
        """Clean shutdown of optimization resources."""
        # Cancel timers
        for timer_id in self._debounce_timers.values():
            try:
                self.after_cancel(timer_id)
            except:
                pass
        self._debounce_timers.clear()
        
        # Shutdown background processor if it was initialized
        if self._background_processor is not None:
            try:
                self._background_processor.shutdown(wait=False)
                logging.debug("Background processor shutdown complete")
            except Exception as e:
                logging.error(f"Error shutting down background processor: {e}")
        
        # Clear caches
        cache_size = len(self._result_cache)
        self._result_cache.clear()
        
        pool_size = len(self._memory_manager.get("item_pool", {}))
        self._memory_manager["item_pool"].clear()
        
        # Clear data structures
        if hasattr(self, "all_data"):
            self.all_data.clear()
        if hasattr(self, "filtered_data"):
            self.filtered_data.clear()
        self._ui_item_cache.clear()
        self._last_data_hash.clear()
        
        logging.debug(f"Optimization shutdown: cleared {cache_size} cache entries, {pool_size} pooled items")
        
        # Force garbage collection
        import gc
        gc.collect()