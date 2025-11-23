"""
Performance and Scalability Utilities
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Dict, Any, List, Optional, Callable, TypeVar, Generic
from datetime import datetime, timedelta
from functools import wraps
import threading
import weakref

from .utils import log_info
from .monitoring import structured_log

monitor = structured_log(__name__)

T = TypeVar('T')


class TTLCache(Generic[T]):
    """Time-based cache with TTL (Time To Live) support"""

    def __init__(self, default_ttl: int = 3600, max_size: int = 1000):
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
        self._cleanup_thread = None
        self._running = True

        # Start background cleanup
        self._start_cleanup_thread()

    def _start_cleanup_thread(self):
        """Start background thread for cache cleanup"""
        def cleanup_worker():
            while self._running:
                try:
                    time.sleep(300)  # Clean up every 5 minutes
                    self._cleanup_expired()
                except Exception as e:
                    monitor.error(f"Cache cleanup error: {str(e)}")

        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()

    def _cleanup_expired(self):
        """Remove expired entries from cache"""
        with self.lock:
            current_time = datetime.now()
            expired_keys = []

            for key, entry in self.cache.items():
                if current_time > entry['expires_at']:
                    expired_keys.append(key)

            for key in expired_keys:
                del self.cache[key]

            if expired_keys:
                monitor.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    def _get_cache_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        # Convert args and kwargs to a stable string representation
        key_data = {
            'args': args,
            'kwargs': sorted(kwargs.items()) if kwargs else []
        }
        key_string = json.dumps(key_data, default=str, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()

    def get(self, key: str) -> Optional[T]:
        """Get value from cache"""
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                if datetime.now() <= entry['expires_at']:
                    monitor.debug(f"Cache hit for key: {key[:8]}...")
                    return entry['value']
                else:
                    # Expired, remove it
                    del self.cache[key]
            return None

    def set(self, key: str, value: T, ttl: Optional[int] = None):
        """Set value in cache with TTL"""
        with self.lock:
            # Enforce max size by removing oldest entries
            if len(self.cache) >= self.max_size:
                # Remove 10% of entries (oldest first)
                entries_to_remove = int(self.max_size * 0.1)
                sorted_entries = sorted(self.cache.items(),
                                      key=lambda x: x[1]['created_at'])

                for key_to_remove, _ in sorted_entries[:entries_to_remove]:
                    del self.cache[key_to_remove]

                monitor.debug(f"Removed {entries_to_remove} entries due to cache size limit")

            ttl_seconds = ttl if ttl is not None else self.default_ttl
            expires_at = datetime.now() + timedelta(seconds=ttl_seconds)

            self.cache[key] = {
                'value': value,
                'expires_at': expires_at,
                'created_at': datetime.now(),
                'ttl': ttl_seconds
            }

            monitor.debug(f"Cached value for key: {key[:8]}... (TTL: {ttl_seconds}s)")

    def invalidate(self, key: str):
        """Remove specific key from cache"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                monitor.debug(f"Invalidated cache key: {key[:8]}...")

    def clear(self):
        """Clear all cache entries"""
        with self.lock:
            self.cache.clear()
            monitor.info("Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            total_entries = len(self.cache)
            expired_entries = sum(1 for entry in self.cache.values()
                                if datetime.now() > entry['expires_at'])

            return {
                'total_entries': total_entries,
                'expired_entries': expired_entries,
                'active_entries': total_entries - expired_entries,
                'max_size': self.max_size,
                'default_ttl': self.default_ttl
            }

    def stop(self):
        """Stop the cache cleanup thread"""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=1)


def cached(ttl: Optional[int] = None, key_func: Optional[Callable] = None):
    """Decorator for caching function results"""
    def decorator(func):
        cache = TTLCache()

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = cache._get_cache_key(func.__name__, *args, **kwargs)

            # Check cache first
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function
            result = func(*args, **kwargs)

            # Cache result
            cache.set(cache_key, result, ttl)

            return result

        # Add cache management methods to the function
        wrapper.cache = cache
        wrapper.clear_cache = cache.clear
        wrapper.invalidate_cache = cache.invalidate

        return wrapper
    return decorator


class AsyncTaskManager:
    """Manage async tasks with concurrency control and error handling"""

    def __init__(self, max_concurrent: int = 5, timeout: float = 300.0):
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.monitor = structured_log(__name__)

    async def execute_with_semaphore(self, coro, *args, **kwargs):
        """Execute coroutine with concurrency control"""
        async with self.semaphore:
            try:
                return await asyncio.wait_for(coro(*args, **kwargs), timeout=self.timeout)
            except asyncio.TimeoutError:
                self.monitor.error(f"Task timed out after {self.timeout}s")
                raise
            except Exception as e:
                self.monitor.error(f"Task failed: {str(e)}")
                raise

    async def execute_batch(self, tasks: List[Callable], *args, **kwargs) -> List[Any]:
        """Execute multiple tasks concurrently with error handling"""
        async def execute_single_task(task_func):
            try:
                if asyncio.iscoroutinefunction(task_func):
                    return await self.execute_with_semaphore(task_func, *args, **kwargs)
                else:
                    # Run sync function in thread pool
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, task_func, *args, **kwargs)
            except Exception as e:
                self.monitor.error(f"Batch task failed: {str(e)}")
                return {"error": str(e), "task": task_func.__name__}

        # Execute all tasks concurrently
        results = await asyncio.gather(
            *[execute_single_task(task) for task in tasks],
            return_exceptions=True
        )

        # Handle exceptions in results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.monitor.error(f"Task {i} raised exception: {str(result)}")
                processed_results.append({"error": str(result), "task_index": i})
            else:
                processed_results.append(result)

        return processed_results


class MemoryManager:
    """Manage memory usage for large codebases and responses"""

    def __init__(self, max_memory_mb: int = 500):
        self.max_memory_mb = max_memory_mb
        self.current_memory_mb = 0
        self.objects: Dict[str, weakref.ref] = {}
        self.monitor = structured_log(__name__)

    def track_object(self, obj_id: str, obj: Any):
        """Track an object for memory management"""
        # Remove dead references
        self._cleanup_dead_refs()

        # Estimate object size (rough approximation)
        obj_size = self._estimate_size(obj)

        if self.current_memory_mb + obj_size > self.max_memory_mb:
            self._evict_objects(obj_size)

        # Check if object is weakly referenceable
        try:
            self.objects[obj_id] = weakref.ref(obj, lambda ref: self._on_object_death(obj_id))
        except TypeError:
            # Object not weakly referenceable (e.g., dict, list), track size only
            self.objects[obj_id] = None
            self.monitor.debug(f"Object {obj_id} not weakly referenceable, tracking size only")

        self.current_memory_mb += obj_size

        self.monitor.debug(f"Tracking object {obj_id}: {obj_size}MB (total: {self.current_memory_mb:.1f}MB)")

    def untrack_object(self, obj_id: str):
        """Stop tracking an object"""
        if obj_id in self.objects:
            # Try to get the object to estimate size for removal
            obj_ref = self.objects[obj_id]
            obj = obj_ref() if obj_ref is not None else None

            if obj:
                obj_size = self._estimate_size(obj)
                self.current_memory_mb = max(0, self.current_memory_mb - obj_size)

            del self.objects[obj_id]
            self.monitor.debug(f"Untracked object {obj_id}")

    def _estimate_size(self, obj: Any) -> float:
        """Roughly estimate object size in MB"""
        try:
            if isinstance(obj, str):
                return len(obj.encode('utf-8')) / (1024 * 1024)
            elif isinstance(obj, (list, tuple)):
                return sum(self._estimate_size(item) for item in obj)
            elif isinstance(obj, dict):
                return sum(self._estimate_size(k) + self._estimate_size(v) for k, v in obj.items())
            elif hasattr(obj, '__dict__'):
                return self._estimate_size(obj.__dict__)
            else:
                # Default estimate
                return 0.001  # 1KB
        except:
            return 0.001

    def _evict_objects(self, required_space: float):
        """Evict objects to free up space"""
        self.monitor.info(f"Evicting objects to free {required_space:.1f}MB")

        # Simple LRU eviction - remove oldest objects
        objects_to_evict = []
        space_freed = 0

        for obj_id, obj_ref in list(self.objects.items())[:10]:  # Check first 10
            obj = obj_ref() if obj_ref is not None else None
            if obj:
                obj_size = self._estimate_size(obj)
                objects_to_evict.append((obj_id, obj_size))
                space_freed += obj_size

                if space_freed >= required_space:
                    break

        # Evict the selected objects
        for obj_id, obj_size in objects_to_evict:
            self.untrack_object(obj_id)
            self.monitor.debug(f"Evicted object {obj_id}: {obj_size:.1f}MB")

    def _cleanup_dead_refs(self):
        """Remove dead weak references"""
        dead_refs = [obj_id for obj_id, ref in self.objects.items() if ref is not None and ref() is None]
        for obj_id in dead_refs:
            del self.objects[obj_id]

        if dead_refs:
            self.monitor.debug(f"Cleaned up {len(dead_refs)} dead references")

    def _on_object_death(self, obj_id: str):
        """Callback when tracked object is garbage collected"""
        if obj_id in self.objects:
            # We can't estimate size here since object is gone
            # Just remove from tracking
            del self.objects[obj_id]
            self.monitor.debug(f"Object {obj_id} was garbage collected")

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics"""
        self._cleanup_dead_refs()

        return {
            "current_memory_mb": self.current_memory_mb,
            "max_memory_mb": self.max_memory_mb,
            "tracked_objects": len(self.objects),
            "memory_utilization_percent": (self.current_memory_mb / self.max_memory_mb) * 100
        }


class BatchProcessor:
    """Process multiple items in batches for better performance"""

    def __init__(self, batch_size: int = 10, max_concurrent_batches: int = 3):
        self.batch_size = batch_size
        self.max_concurrent_batches = max_concurrent_batches
        self.task_manager = AsyncTaskManager(max_concurrent=max_concurrent_batches)
        self.monitor = structured_log(__name__)

    async def process_batch(self, items: List[Any], processor_func: Callable,
                          *args, **kwargs) -> List[Any]:
        """Process items in batches"""
        if not items:
            return []

        # Split into batches
        batches = [items[i:i + self.batch_size]
                  for i in range(0, len(items), self.batch_size)]

        self.monitor.info(f"Processing {len(items)} items in {len(batches)} batches of size {self.batch_size}")

        # Create batch processing tasks
        async def process_single_batch(batch):
            batch_results = []
            for item in batch:
                try:
                    result = await processor_func(item, *args, **kwargs)
                    batch_results.append(result)
                except Exception as e:
                    self.monitor.error(f"Failed to process item: {str(e)}")
                    batch_results.append({"error": str(e), "item": item})
            return batch_results

        # Process all batches concurrently
        batch_tasks = [process_single_batch(batch) for batch in batches]
        batch_results = await self.task_manager.execute_batch(batch_tasks)

        # Flatten results
        all_results = []
        for batch_result in batch_results:
            if isinstance(batch_result, list):
                all_results.extend(batch_result)
            else:
                all_results.append(batch_result)

        self.monitor.info(f"Completed batch processing: {len(all_results)} results")
        return all_results


# Global instances
response_cache = TTLCache(default_ttl=3600, max_size=500)  # 1 hour TTL, 500 items
task_manager = AsyncTaskManager(max_concurrent=5)
memory_manager = MemoryManager(max_memory_mb=500)
batch_processor = BatchProcessor(batch_size=10, max_concurrent_batches=3)


def get_response_cache() -> TTLCache:
    """Get the global response cache"""
    return response_cache


def get_task_manager() -> AsyncTaskManager:
    """Get the global task manager"""
    return task_manager


def get_memory_manager() -> MemoryManager:
    """Get the global memory manager"""
    return memory_manager


def get_batch_processor() -> BatchProcessor:
    """Get the global batch processor"""
    return batch_processor