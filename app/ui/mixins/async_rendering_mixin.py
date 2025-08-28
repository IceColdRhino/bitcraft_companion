"""
AsyncRenderingMixin for BitCraft Companion.

Provides async rendering capabilities that can be mixed into any tab class.
Eliminates UI blocking during large dataset operations through chunked processing.

CRITICAL THREADING NOTE:
- Data processing happens asynchronously in background threads
- All UI operations (tree insertion, widget updates) happen synchronously on main thread
- This mixin handles the async/sync boundary safely via completion callbacks
"""

import time
import logging
from typing import List, Dict, Any, Optional, Callable
from tkinter import ttk

from app.ui.components.async_ui_renderer import AsyncUIRenderer, ProgressIndicator


class AsyncRenderingMixin:
    """
    Mixin class that provides async rendering capabilities for tab classes.
    
    ASYNC/SYNC ARCHITECTURE:
    - Background threads: Data formatting and preparation (NO UI operations)
    - Main thread: All UI operations (tree insertion, widget updates, layout)
    - Automatic threshold-based switching between sync and async processing
    
    Classes that use this mixin should:
    1. Call _setup_async_rendering() during initialization
    2. Use _render_tree_async() instead of direct tree population
    3. Optionally override _should_use_async_rendering() for custom logic
    4. Implement _format_row_for_display() for row formatting
    
    THREAD SAFETY:
    All UI operations are guaranteed to happen on the main thread via completion callbacks.
    """
    
    def _setup_async_rendering(self, chunk_size: int = 75, enable_progress: bool = True):
        """
        Set up async rendering capabilities.
        
        Args:
            chunk_size: Number of items to process in each chunk
            enable_progress: Whether to show progress indicators
        """
        self.async_renderer = AsyncUIRenderer(self, chunk_size)
        self.enable_progress = enable_progress
        self.progress_indicator = None
        self.async_rendering_enabled = True  # Can be toggled via settings
        
        # Performance thresholds
        self.async_threshold = 50  # Use async rendering for datasets larger than this
        self.progress_threshold = 100  # Show progress indicator for datasets larger than this
        
        # Smart update features
        self.visibility_based_updates = True  # Pause updates when tab not visible
        self.update_debounce_delay = 100  # Milliseconds to debounce rapid updates
        self.pending_update_timer = None
        self.update_queue = []
        
        self.logger = logging.getLogger(__name__)
        
    def _should_use_async_rendering(self, data_size: int) -> bool:
        """
        Determine if async rendering should be used based on data size and settings.
        
        Args:
            data_size: Number of items to render
            
        Returns:
            True if async rendering should be used
        """
        return (
            hasattr(self, 'async_rendering_enabled') and 
            self.async_rendering_enabled and 
            data_size >= self.async_threshold
        )
        
    def _should_show_progress(self, data_size: int) -> bool:
        """
        Determine if progress indicator should be shown.
        
        Args:
            data_size: Number of items to render
            
        Returns:
            True if progress indicator should be shown
        """
        return (
            hasattr(self, 'enable_progress') and
            self.enable_progress and
            data_size >= self.progress_threshold
        )
    
    def _render_tree_async(
        self,
        tree_widget: ttk.Treeview,
        data: List[Dict[str, Any]], 
        columns: List[str],
        format_row_func: Optional[Callable[[Dict[str, Any]], Dict[str, str]]] = None,
        completion_callback: Optional[Callable[[int], None]] = None,
        operation_name: str = "render"
    ) -> Optional[str]:
        """
        Render tree data using async rendering if appropriate.
        
        THREAD SAFETY:
        - Small datasets: Rendered synchronously on main thread
        - Large datasets: Data formatted in background, UI updated on main thread
        - All tree widget operations are guaranteed to happen on main thread
        
        Args:
            tree_widget: The treeview widget to populate (main thread only)
            data: List of data items to render
            columns: List of column identifiers
            format_row_func: Function to format each data row (uses _format_row_for_display if None)
            completion_callback: Optional callback when rendering completes (main thread)
            operation_name: Name for this operation (for logging/debugging)
            
        Returns:
            Operation ID if async rendering was used, None if sync rendering was used
        """
        if not hasattr(self, 'async_renderer'):
            self._setup_async_rendering()
        
        data_size = len(data)
        
        # Use format function or default to class method
        if format_row_func is None:
            if hasattr(self, '_format_row_for_display'):
                format_row_func = self._format_row_for_display
            else:
                # Fallback to identity function
                format_row_func = lambda row: {col: str(row.get(col, "")) for col in columns}
        
        # Determine rendering approach
        use_async = self._should_use_async_rendering(data_size)
        show_progress = self._should_show_progress(data_size)
        
        if use_async:
            return self._render_async_with_progress(
                tree_widget, data, columns, format_row_func, 
                completion_callback, operation_name, show_progress
            )
        else:
            # Use synchronous rendering for small datasets
            self._render_sync(tree_widget, data, columns, format_row_func)
            if completion_callback:
                completion_callback(data_size)
            return None
    
    def _render_async_with_progress(
        self,
        tree_widget: ttk.Treeview,
        data: List[Dict[str, Any]], 
        columns: List[str],
        format_row_func: Callable[[Dict[str, Any]], Dict[str, str]],
        completion_callback: Optional[Callable[[int], None]],
        operation_name: str,
        show_progress: bool
    ) -> str:
        """Render with async processing and optional progress indication."""
        
        # Set up progress indicator
        if show_progress:
            self._show_progress_indicator(f"Loading {operation_name}...")
        
        # Create completion wrapper that handles progress cleanup
        def wrapped_completion_callback(item_count: int):
            if show_progress:
                self._hide_progress_indicator()
            
            if completion_callback:
                completion_callback(item_count)
                
            self.logger.debug(f"[AsyncRendering] Completed {operation_name} - {item_count} items")
        
        # Progress callback for updates
        progress_callback = None
        if show_progress:
            progress_callback = self._update_progress_indicator
        
        # Start async rendering
        operation_id = self.async_renderer.render_tree_async(
            tree_widget=tree_widget,
            data=data,
            columns=columns,
            format_row_func=format_row_func,
            progress_callback=progress_callback,
            completion_callback=wrapped_completion_callback,
            operation_id=f"{operation_name}_{int(time.time() * 1000)}"
        )
        
        self.logger.info(f"[AsyncRendering] Started {operation_name} async render - {len(data)} items (ID: {operation_id})")
        return operation_id
    
    def _render_sync(
        self,
        tree_widget: ttk.Treeview,
        data: List[Dict[str, Any]], 
        columns: List[str],
        format_row_func: Callable[[Dict[str, Any]], Dict[str, str]]
    ):
        """Fallback synchronous rendering for small datasets."""
        start_time = time.time()
        
        # Clear existing items
        for item in tree_widget.get_children():
            tree_widget.delete(item)
        
        # Insert new items
        for row_data in data:
            try:
                formatted_row = format_row_func(row_data)
                values = [formatted_row.get(col, "") for col in columns]
                tags = formatted_row.get("_tags", ())
                tree_widget.insert("", "end", values=values, tags=tags)
            except Exception as e:
                self.logger.warning(f"Error formatting row during sync render: {e}")
                continue
        
        render_time = time.time() - start_time
        self.logger.debug(f"[AsyncRendering] Completed sync render - {len(data)} items in {render_time:.3f}s")
    
    def _show_progress_indicator(self, message: str):
        """Show progress indicator."""
        if not hasattr(self, 'progress_indicator') or self.progress_indicator is None:
            self.progress_indicator = ProgressIndicator(self, message)
        
        self.progress_indicator.show()
    
    def _update_progress_indicator(self, progress: float, message: str):
        """Update progress indicator."""
        if hasattr(self, 'progress_indicator') and self.progress_indicator:
            self.progress_indicator.update(progress, message)
    
    def _hide_progress_indicator(self):
        """Hide progress indicator."""
        if hasattr(self, 'progress_indicator') and self.progress_indicator:
            self.progress_indicator.hide()
    
    def _cancel_async_rendering(self, operation_id: Optional[str] = None):
        """
        Cancel async rendering operations.
        
        Args:
            operation_id: Specific operation to cancel, or None to cancel all
        """
        if not hasattr(self, 'async_renderer'):
            return
            
        if operation_id:
            cancelled = self.async_renderer.cancel_operation(operation_id)
            if cancelled:
                self.logger.debug(f"[AsyncRendering] Cancelled operation: {operation_id}")
        else:
            self.async_renderer.cancel_all_operations()
            self.logger.debug(f"[AsyncRendering] Cancelled all operations")
        
        # Hide progress indicator if active
        if hasattr(self, 'progress_indicator') and self.progress_indicator:
            self.progress_indicator.hide()
    
    def _is_async_rendering_active(self) -> bool:
        """Check if any async rendering operations are currently active."""
        return (
            hasattr(self, 'async_renderer') and 
            self.async_renderer.is_rendering()
        )
    
    def _get_async_rendering_stats(self) -> Dict[str, Any]:
        """Get async rendering performance statistics."""
        if hasattr(self, 'async_renderer'):
            return self.async_renderer.get_performance_stats()
        return {}
    
    def _configure_async_rendering(
        self,
        enabled: bool = True,
        chunk_size: int = 75,
        async_threshold: int = 50,
        progress_threshold: int = 100
    ):
        """
        Configure async rendering parameters.
        
        Args:
            enabled: Whether async rendering is enabled
            chunk_size: Number of items to process per chunk
            async_threshold: Minimum dataset size to use async rendering
            progress_threshold: Minimum dataset size to show progress indicator
        """
        self.async_rendering_enabled = enabled
        
        if hasattr(self, 'async_renderer'):
            self.async_renderer.chunk_size = chunk_size
            
        self.async_threshold = async_threshold
        self.progress_threshold = progress_threshold
        
        self.logger.debug(f"[AsyncRendering] Configured - enabled: {enabled}, chunk: {chunk_size}, "
                         f"async_threshold: {async_threshold}, progress_threshold: {progress_threshold}")
    
    def _is_tab_visible(self) -> bool:
        """
        Check if the current tab is visible/active.
        
        Returns:
            True if tab is visible and updates should proceed
        """
        try:
            # Check if this widget is mapped (visible)
            if hasattr(self, 'winfo_viewable') and not self.winfo_viewable():
                return False
                
            # Check if the tab is the active tab in parent (if it's a tab)
            if hasattr(self, 'master') and hasattr(self.master, 'active_tab_name'):
                if hasattr(self, '_tab_name'):
                    return self.master.active_tab_name == self._tab_name
                    
            return True
            
        except Exception as e:
            self.logger.debug(f"Error checking tab visibility: {e}")
            return True  # Default to visible if we can't determine
            
    def _render_tree_debounced(
        self,
        tree_widget: ttk.Treeview,
        data: List[Dict[str, Any]], 
        columns: List[str],
        format_row_func: Optional[Callable[[Dict[str, Any]], Dict[str, str]]] = None,
        completion_callback: Optional[Callable[[int], None]] = None,
        operation_name: str = "render"
    ):
        """
        Render tree data with debouncing to handle rapid consecutive updates.
        
        Args:
            Same as _render_tree_async
        """
        # Cancel pending update timer
        if self.pending_update_timer:
            self.after_cancel(self.pending_update_timer)
            self.pending_update_timer = None
            
        # Store update parameters
        update_params = {
            'tree_widget': tree_widget,
            'data': data,
            'columns': columns,
            'format_row_func': format_row_func,
            'completion_callback': completion_callback,
            'operation_name': operation_name
        }
        
        # Check visibility if enabled
        if self.visibility_based_updates and not self._is_tab_visible():
            self.logger.debug(f"[AsyncRendering] Deferring {operation_name} update - tab not visible")
            self.update_queue = [update_params]  # Store latest update
            return None
            
        # Schedule debounced update
        self.pending_update_timer = self.after(
            self.update_debounce_delay,
            lambda: self._execute_debounced_update(update_params)
        )
        
        return f"debounced_{operation_name}_{int(time.time() * 1000)}"
        
    def _execute_debounced_update(self, update_params: Dict):
        """Execute a debounced update."""
        self.pending_update_timer = None
        
        return self._render_tree_async(
            tree_widget=update_params['tree_widget'],
            data=update_params['data'],
            columns=update_params['columns'],
            format_row_func=update_params['format_row_func'],
            completion_callback=update_params['completion_callback'],
            operation_name=update_params['operation_name']
        )
        
    def _handle_tab_visibility_change(self, is_visible: bool):
        """
        Handle tab visibility changes.
        
        Args:
            is_visible: True if tab became visible, False if hidden
        """
        if is_visible and self.update_queue:
            # Process queued update when tab becomes visible
            update_params = self.update_queue.pop()
            self.logger.debug(f"[AsyncRendering] Processing queued update - tab became visible")
            self._execute_debounced_update(update_params)

    # Cleanup method that should be called when the tab is destroyed
    def _cleanup_async_rendering(self):
        """Clean up async rendering resources."""
        # Cancel pending timers
        if hasattr(self, 'pending_update_timer') and self.pending_update_timer:
            self.after_cancel(self.pending_update_timer)
            self.pending_update_timer = None
            
        # Clear update queue
        if hasattr(self, 'update_queue'):
            self.update_queue.clear()
            
        if hasattr(self, 'async_renderer'):
            self.async_renderer.cancel_all_operations()
        
        if hasattr(self, 'progress_indicator') and self.progress_indicator:
            self.progress_indicator.hide()
            self.progress_indicator = None