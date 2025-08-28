"""
AsyncUIRenderer for BitCraft Companion.

Provides non-blocking table rendering through chunked processing and progress indication.
Eliminates UI freezing during large dataset operations by yielding control between chunks.
"""

import time
import logging
import threading
from typing import List, Dict, Any, Optional, Callable, Union
from tkinter import ttk
import customtkinter as ctk

from app.ui.themes import get_color


class AsyncRenderOperation:
    """Represents a single async rendering operation that can be cancelled."""
    
    def __init__(self, operation_id: str):
        self.operation_id = operation_id
        self.cancelled = False
        self.start_time = time.time()
        self.progress = 0.0
        self.total_items = 0
        self.processed_items = 0
        
    def cancel(self):
        """Cancel this rendering operation."""
        self.cancelled = True
        
    def update_progress(self, processed: int, total: int):
        """Update progress information."""
        self.processed_items = processed
        self.total_items = total
        self.progress = (processed / total) if total > 0 else 0.0


class AsyncUIRenderer:
    """
    Provides non-blocking UI rendering capabilities for large datasets.
    
    Features:
    - Chunked processing to avoid blocking the UI thread
    - Progress indication for long operations
    - Cancellation support for outdated operations
    - Thread-safe UI updates via tkinter's after() method
    - Differential rendering for performance optimization
    """
    
    def __init__(self, parent_widget, chunk_size: int = 75):
        """
        Initialize the async renderer.
        
        Args:
            parent_widget: The parent UI widget (for scheduling UI updates)
            chunk_size: Number of items to process in each chunk
        """
        self.parent_widget = parent_widget
        self.chunk_size = chunk_size
        self.logger = logging.getLogger(__name__)
        
        # Operation management
        self.current_operations: Dict[str, AsyncRenderOperation] = {}
        self.operation_counter = 0
        
        # Performance tracking
        self.render_stats = {
            'total_operations': 0,
            'cancelled_operations': 0,
            'avg_render_time': 0.0,
            'max_items_rendered': 0
        }
        
    def render_tree_async(
        self,
        tree_widget: ttk.Treeview,
        data: List[Dict[str, Any]], 
        columns: List[str],
        format_row_func: Callable[[Dict[str, Any]], Dict[str, str]],
        progress_callback: Optional[Callable[[float, str], None]] = None,
        completion_callback: Optional[Callable[[int], None]] = None,
        operation_id: Optional[str] = None
    ) -> str:
        """
        Render a tree widget asynchronously with chunked processing.
        
        Args:
            tree_widget: The treeview widget to populate
            data: List of data items to render
            columns: List of column identifiers
            format_row_func: Function to format each data row for display
            progress_callback: Optional callback for progress updates (progress, message)
            completion_callback: Optional callback when rendering completes (total_items)
            operation_id: Optional custom operation ID (auto-generated if None)
            
        Returns:
            Operation ID that can be used to cancel the operation
        """
        # Generate operation ID
        if operation_id is None:
            self.operation_counter += 1
            operation_id = f"render_{self.operation_counter}_{int(time.time() * 1000)}"
        
        # Cancel any existing operation with the same ID
        self.cancel_operation(operation_id)
        
        # Create new operation
        operation = AsyncRenderOperation(operation_id)
        operation.total_items = len(data)
        self.current_operations[operation_id] = operation
        
        self.logger.debug(f"[AsyncRenderer] Starting render operation '{operation_id}' for {len(data)} items")
        
        # Update stats
        self.render_stats['total_operations'] += 1
        if len(data) > self.render_stats['max_items_rendered']:
            self.render_stats['max_items_rendered'] = len(data)
        
        # Start the rendering process
        self._start_chunked_render(
            operation, tree_widget, data, columns, 
            format_row_func, progress_callback, completion_callback
        )
        
        return operation_id
    
    def _start_chunked_render(
        self,
        operation: AsyncRenderOperation,
        tree_widget: ttk.Treeview,
        data: List[Dict[str, Any]],
        columns: List[str],
        format_row_func: Callable[[Dict[str, Any]], Dict[str, str]],
        progress_callback: Optional[Callable[[float, str], None]],
        completion_callback: Optional[Callable[[int], None]]
    ):
        """Start the chunked rendering process."""
        # Clear the tree initially
        self.parent_widget.after(0, lambda: self._clear_tree_safe(tree_widget, operation.operation_id))
        
        # Start chunked processing
        chunk_start = 0
        self._process_chunk(
            operation, tree_widget, data, columns, format_row_func,
            progress_callback, completion_callback, chunk_start
        )
    
    def _process_chunk(
        self,
        operation: AsyncRenderOperation,
        tree_widget: ttk.Treeview,
        data: List[Dict[str, Any]],
        columns: List[str],
        format_row_func: Callable[[Dict[str, Any]], Dict[str, str]],
        progress_callback: Optional[Callable[[float, str], None]],
        completion_callback: Optional[Callable[[int], None]],
        chunk_start: int
    ):
        """Process a single chunk of data."""
        if operation.cancelled:
            self._cleanup_operation(operation.operation_id)
            return
        
        # Calculate chunk boundaries
        chunk_end = min(chunk_start + self.chunk_size, len(data))
        chunk_data = data[chunk_start:chunk_end]
        
        # Process chunk data (off main thread)
        processed_rows = []
        for item in chunk_data:
            if operation.cancelled:
                self._cleanup_operation(operation.operation_id)
                return
                
            try:
                formatted_row = format_row_func(item)
                processed_rows.append(formatted_row)
            except Exception as e:
                self.logger.warning(f"Error formatting row in operation '{operation.operation_id}': {e}")
                continue
        
        # Update progress
        operation.update_progress(chunk_end, len(data))
        
        # Schedule UI update on main thread
        self.parent_widget.after(0, lambda: self._update_tree_chunk(
            tree_widget, processed_rows, columns, operation.operation_id
        ))
        
        # Schedule progress callback if provided
        if progress_callback and not operation.cancelled:
            progress_message = f"Rendering {chunk_end}/{len(data)} items..."
            self.parent_widget.after(1, lambda: progress_callback(operation.progress, progress_message))
        
        # Continue with next chunk or complete
        if chunk_end < len(data) and not operation.cancelled:
            # Schedule next chunk after a brief delay to yield control
            self.parent_widget.after(1, lambda: self._process_chunk(
                operation, tree_widget, data, columns, format_row_func,
                progress_callback, completion_callback, chunk_end
            ))
        else:
            # Rendering complete
            self._complete_operation(operation, completion_callback)
    
    def _clear_tree_safe(self, tree_widget: ttk.Treeview, operation_id: str):
        """Safely clear tree widget on main thread."""
        if operation_id not in self.current_operations or self.current_operations[operation_id].cancelled:
            return
            
        try:
            # Clear all items
            for item in tree_widget.get_children():
                tree_widget.delete(item)
        except Exception as e:
            self.logger.warning(f"Error clearing tree for operation '{operation_id}': {e}")
    
    def _update_tree_chunk(
        self, 
        tree_widget: ttk.Treeview, 
        chunk_rows: List[Dict[str, str]], 
        columns: List[str],
        operation_id: str
    ):
        """Update tree widget with a chunk of processed rows (main thread only)."""
        if operation_id not in self.current_operations or self.current_operations[operation_id].cancelled:
            return
        
        try:
            # Track parent items for hierarchical insertion
            parent_items = {}
            
            # Process rows in order to handle hierarchical data
            for row_data in chunk_rows:
                values = [row_data.get(col, "") for col in columns]
                
                # Extract special fields for advanced rendering
                tags = row_data.get("_tags", ())
                parent_id = row_data.get("_parent_id", "")
                item_key = row_data.get("_item_key", "")
                children = row_data.get("_children", [])
                
                # Handle hierarchical insertion
                if parent_id and parent_id in parent_items:
                    # This is a child item - insert under its parent
                    tree_item_id = tree_widget.insert(parent_items[parent_id], "end", values=values, tags=tags)
                else:
                    # This is a parent/root item - insert at root level
                    tree_item_id = tree_widget.insert("", "end", values=values, tags=tags)
                
                # Store parent reference for child items
                if item_key:
                    parent_items[item_key] = tree_item_id
                
                # Handle immediate children (for complex hierarchical data)
                if children:
                    for child in children:
                        child_values = [child.get(col, "") for col in columns]
                        child_tags = child.get("_tags", ())
                        tree_widget.insert(tree_item_id, "end", values=child_values, tags=child_tags)
                
        except Exception as e:
            self.logger.warning(f"Error updating tree chunk for operation '{operation_id}': {e}")
    
    def _complete_operation(
        self,
        operation: AsyncRenderOperation, 
        completion_callback: Optional[Callable[[int], None]]
    ):
        """Complete a rendering operation."""
        if operation.cancelled:
            self._cleanup_operation(operation.operation_id)
            return
        
        # Calculate performance stats
        render_time = time.time() - operation.start_time
        self._update_performance_stats(render_time)
        
        self.logger.info(f"[AsyncRenderer] Completed operation '{operation.operation_id}' - "
                        f"{operation.total_items} items in {render_time:.3f}s")
        
        # Schedule completion callback
        if completion_callback:
            self.parent_widget.after(0, lambda: completion_callback(operation.total_items))
        
        # Cleanup
        self._cleanup_operation(operation.operation_id)
    
    def cancel_operation(self, operation_id: str) -> bool:
        """
        Cancel a rendering operation.
        
        Args:
            operation_id: ID of the operation to cancel
            
        Returns:
            True if operation was cancelled, False if it didn't exist
        """
        if operation_id in self.current_operations:
            operation = self.current_operations[operation_id]
            operation.cancel()
            self.render_stats['cancelled_operations'] += 1
            self.logger.debug(f"[AsyncRenderer] Cancelled operation '{operation_id}'")
            return True
        return False
    
    def cancel_all_operations(self):
        """Cancel all active rendering operations."""
        operation_ids = list(self.current_operations.keys())
        for operation_id in operation_ids:
            self.cancel_operation(operation_id)
    
    def _cleanup_operation(self, operation_id: str):
        """Clean up a completed or cancelled operation."""
        if operation_id in self.current_operations:
            del self.current_operations[operation_id]
    
    def _update_performance_stats(self, render_time: float):
        """Update performance statistics."""
        total_ops = self.render_stats['total_operations']
        current_avg = self.render_stats['avg_render_time']
        
        # Calculate new average
        self.render_stats['avg_render_time'] = ((current_avg * (total_ops - 1)) + render_time) / total_ops
    
    def get_performance_stats(self) -> Dict[str, Union[int, float]]:
        """Get performance statistics."""
        return self.render_stats.copy()
    
    def is_rendering(self) -> bool:
        """Check if any rendering operations are currently active."""
        return len(self.current_operations) > 0
    
    def get_active_operations(self) -> List[str]:
        """Get list of active operation IDs."""
        return list(self.current_operations.keys())


class ProgressIndicator:
    """Simple progress indicator for async operations."""
    
    def __init__(self, parent_widget, text: str = "Processing..."):
        self.parent_widget = parent_widget
        self.text = text
        self.progress_var = None
        self.progress_bar = None
        self.status_label = None
        self.container = None
        self.visible = False
        
    def show(self):
        """Show the progress indicator."""
        if self.visible:
            return
            
        # Create progress container using grid layout
        self.container = ctk.CTkFrame(self.parent_widget, fg_color="transparent")
        self.container.grid(row=999, column=0, columnspan=10, sticky="ew", padx=5, pady=2)
        
        # Configure grid weights for the container
        self.container.grid_columnconfigure(1, weight=1)
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.container,
            text=self.text,
            font=ctk.CTkFont(size=11),
            text_color=get_color("TEXT_SECONDARY")
        )
        self.status_label.grid(row=0, column=0, sticky="w", padx=(5, 10))
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            self.container,
            width=200,
            height=16,
            progress_color=get_color("STATUS_IN_PROGRESS")
        )
        self.progress_bar.grid(row=0, column=2, sticky="e", padx=(0, 5))
        self.progress_bar.set(0)
        
        self.visible = True
        
    def update(self, progress: float, message: str = None):
        """Update progress (0.0 to 1.0) and optional message."""
        if not self.visible:
            return
            
        if self.progress_bar:
            self.progress_bar.set(progress)
        
        if message and self.status_label:
            self.status_label.configure(text=message)
            
    def hide(self):
        """Hide the progress indicator."""
        if not self.visible:
            return
            
        if self.container:
            self.container.destroy()
            self.container = None
            self.progress_bar = None
            self.status_label = None
            
        self.visible = False