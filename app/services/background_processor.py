"""
Background Processing Service

Provides background thread processing for heavy operations to prevent UI blocking.
Handles data consolidation, filtering, sorting, and other CPU-intensive tasks.
"""

import logging
import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass


@dataclass
class BackgroundTask:
    """Represents a background task with callback and error handling."""

    task_id: str
    func: Callable
    args: tuple
    kwargs: dict
    callback: Optional[Callable] = None
    error_callback: Optional[Callable] = None
    priority: int = 1  # Lower numbers = higher priority


class BackgroundProcessor:
    """
    Manages background processing of heavy operations to keep UI responsive.

    Features:
    - Thread pool for concurrent processing
    - Priority-based task queuing
    - Automatic result callbacks to UI thread
    - Error handling and recovery
    - Performance monitoring
    """

    def __init__(self, max_workers: int = 3):
        """
        Initialize the background processor.

        Args:
            max_workers: Maximum number of background worker threads
        """
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.task_queue = queue.PriorityQueue()
        self.active_tasks: Dict[str, Future] = {}
        self.task_counter = 0

        # Performance tracking
        self.task_stats = {"completed": 0, "failed": 0, "total_time": 0.0, "avg_time": 0.0}

        # Worker thread for task dispatching
        self.dispatcher_thread = threading.Thread(target=self._task_dispatcher, daemon=True)
        self.running = True
        self.dispatcher_thread.start()

        logging.debug(f"BackgroundProcessor initialized with {max_workers} workers")

    def submit_task(
        self,
        func: Callable,
        *args,
        callback: Optional[Callable] = None,
        error_callback: Optional[Callable] = None,
        priority: int = 1,
        task_name: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Submit a task for background processing.

        Args:
            func: Function to execute in background
            *args: Arguments for the function
            callback: Function to call with result (runs in main thread)
            error_callback: Function to call on error (runs in main thread)
            priority: Task priority (lower = higher priority)
            task_name: Optional name for task identification
            **kwargs: Keyword arguments for the function

        Returns:
            str: Task ID for tracking
        """
        self.task_counter += 1
        task_id = task_name or f"task_{self.task_counter}"

        task = BackgroundTask(
            task_id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            callback=callback,
            error_callback=error_callback,
            priority=priority,
        )

        # Add to priority queue (priority, creation_order, task)
        self.task_queue.put((priority, self.task_counter, task))

        logging.debug(f"Submitted background task: {task_id} (priority: {priority})")
        return task_id

    def _task_dispatcher(self):
        """Background thread that dispatches tasks to the thread pool."""
        while self.running:
            try:
                # Get next task from priority queue (blocks if empty)
                priority, order, task = self.task_queue.get(timeout=1.0)

                if not self.running:
                    break

                # Submit to thread pool
                future = self.executor.submit(self._execute_task, task)
                self.active_tasks[task.task_id] = future

                logging.debug(f"Dispatched task: {task.task_id}")

            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"Error in task dispatcher: {e}")

    def _execute_task(self, task: BackgroundTask) -> Any:
        """Execute a single task and handle callbacks."""
        start_time = time.time()
        task_id = task.task_id

        try:
            logging.debug(f"Executing background task: {task_id}")

            # Execute the actual task
            result = task.func(*task.args, **task.kwargs)

            # Calculate performance metrics
            execution_time = time.time() - start_time
            self._update_stats(execution_time, success=True)

            logging.debug(f"Background task completed: {task_id} ({execution_time:.3f}s)")

            # Schedule callback in main thread if provided
            if task.callback:
                self._schedule_main_thread_callback(task.callback, result)

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            self._update_stats(execution_time, success=False)

            logging.error(f"Background task failed: {task_id} ({execution_time:.3f}s) - {e}")

            # Schedule error callback in main thread if provided
            if task.error_callback:
                self._schedule_main_thread_callback(task.error_callback, e)

            raise

        finally:
            # Clean up active task tracking
            self.active_tasks.pop(task_id, None)

    def _schedule_main_thread_callback(self, callback: Callable, result: Any):
        """Schedule a callback to run in the main thread."""
        # Use the main thread scheduler if available
        if hasattr(self, "main_thread_scheduler") and self.main_thread_scheduler:
            try:
                # Use after_idle to schedule callback properly for Tkinter
                self.main_thread_scheduler(0, lambda: callback(result))
            except Exception as e:
                logging.error(f"Error scheduling main thread callback: {e}")
                # Fallback: call directly (not thread-safe but functional)
                try:
                    callback(result)
                except Exception as e2:
                    logging.error(f"Error in fallback callback: {e2}")
        else:
            # Fallback: call directly (not thread-safe but functional)
            try:
                callback(result)
            except Exception as e:
                logging.error(f"Error in background task callback: {e}")

    def set_main_thread_scheduler(self, scheduler: Callable):
        """
        Set the main thread scheduler function.

        Args:
            scheduler: Function that schedules a callback to run in the main thread
        """
        self.main_thread_scheduler = scheduler
        logging.debug("Main thread scheduler configured for background processor")

    def _update_stats(self, execution_time: float, success: bool):
        """Update performance statistics."""
        if success:
            self.task_stats["completed"] += 1
        else:
            self.task_stats["failed"] += 1

        self.task_stats["total_time"] += execution_time
        total_tasks = self.task_stats["completed"] + self.task_stats["failed"]

        if total_tasks > 0:
            self.task_stats["avg_time"] = self.task_stats["total_time"] / total_tasks

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending or running task.

        Args:
            task_id: ID of task to cancel

        Returns:
            bool: True if task was cancelled successfully
        """
        if task_id in self.active_tasks:
            future = self.active_tasks[task_id]
            return future.cancel()
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            **self.task_stats,
            "active_tasks": len(self.active_tasks),
            "queued_tasks": self.task_queue.qsize(),
            "max_workers": self.max_workers,
        }

    def shutdown(self, wait: bool = True, timeout: float = 30.0):
        """
        Shutdown the background processor.

        Args:
            wait: Whether to wait for running tasks to complete
            timeout: Maximum time to wait for shutdown (used for dispatcher thread only)
        """
        logging.info("Shutting down BackgroundProcessor...")

        self.running = False

        if wait:
            # Wait for executor to finish current tasks (no timeout parameter supported in older Python)
            self.executor.shutdown(wait=True)
        else:
            # Cancel all pending tasks
            for future in self.active_tasks.values():
                future.cancel()
            self.executor.shutdown(wait=False)

        # Wait for dispatcher thread to finish with timeout
        if self.dispatcher_thread.is_alive():
            self.dispatcher_thread.join(timeout=5.0)

        logging.info("BackgroundProcessor shutdown complete")


# Utility functions for common background operations
def background_data_consolidation(
    processor: BackgroundProcessor,
    inventory_data: Dict,
    building_data: Dict,
    callback: Callable,
    error_callback: Optional[Callable] = None,
) -> str:
    """
    Submit inventory data consolidation to background processing.

    Args:
        processor: BackgroundProcessor instance
        inventory_data: Raw inventory data
        building_data: Building reference data
        callback: Function to call with consolidated result
        error_callback: Function to call on error

    Returns:
        str: Task ID
    """

    def consolidate():
        # This would contain the actual consolidation logic
        # For now, returning the original data
        return inventory_data

    return processor.submit_task(
        consolidate, callback=callback, error_callback=error_callback, priority=1, task_name="inventory_consolidation"
    )


def background_data_filtering(
    processor: BackgroundProcessor,
    data: List[Dict],
    filter_func: Callable,
    callback: Callable,
    error_callback: Optional[Callable] = None,
) -> str:
    """
    Submit data filtering to background processing.

    Args:
        processor: BackgroundProcessor instance
        data: Data to filter
        filter_func: Function that returns True for items to keep
        callback: Function to call with filtered result
        error_callback: Function to call on error

    Returns:
        str: Task ID
    """

    def filter_data():
        start_time = time.time()
        result = [item for item in data if filter_func(item)]
        filter_time = time.time() - start_time

        logging.debug(f"Background filtering: {len(data)} -> {len(result)} items ({filter_time:.3f}s)")
        return result

    return processor.submit_task(
        filter_data, callback=callback, error_callback=error_callback, priority=2, task_name="data_filtering"
    )


def background_data_sorting(
    processor: BackgroundProcessor,
    data: List[Dict],
    sort_key: str,
    reverse: bool,
    callback: Callable,
    error_callback: Optional[Callable] = None,
) -> str:
    """
    Submit data sorting to background processing.

    Args:
        processor: BackgroundProcessor instance
        data: Data to sort
        sort_key: Key to sort by
        reverse: Whether to sort in reverse order
        callback: Function to call with sorted result
        error_callback: Function to call on error

    Returns:
        str: Task ID
    """

    def sort_data():
        start_time = time.time()
        is_numeric = sort_key in ["tier", "quantity"]

        result = sorted(
            data, key=lambda x: (float(x.get(sort_key, 0)) if is_numeric else str(x.get(sort_key, "")).lower()), reverse=reverse
        )

        sort_time = time.time() - start_time
        logging.debug(f"Background sorting: {len(data)} items by {sort_key} ({sort_time:.3f}s)")
        return result

    return processor.submit_task(
        sort_data, callback=callback, error_callback=error_callback, priority=2, task_name="data_sorting"
    )
