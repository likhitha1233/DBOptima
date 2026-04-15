"""
FAANG-level Async Utilities
Convert blocking operations to async with proper concurrency
"""

import asyncio
import concurrent.futures
import logging
from typing import Any, Callable, Dict, List, Optional, Coroutine
from functools import wraps, partial
from datetime import datetime
import psutil
import time

logger = logging.getLogger(__name__)

class AsyncExecutor:
    """High-performance async executor with thread pool management"""
    
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) * 4)
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="async_worker"
        )
        self.process_pool = concurrent.futures.ProcessPoolExecutor(
            max_workers=min(4, os.cpu_count() or 1)
        )
    
    async def run_in_thread(self, func: Callable, *args, **kwargs) -> Any:
        """Run synchronous function in thread pool"""
        loop = asyncio.get_event_loop()
        partial_func = partial(func, *args, **kwargs)
        
        try:
            return await loop.run_in_executor(self.thread_pool, partial_func)
        except Exception as e:
            logger.error(f"Thread pool execution failed: {e}")
            raise
    
    async def run_in_process(self, func: Callable, *args, **kwargs) -> Any:
        """Run CPU-intensive function in process pool"""
        loop = asyncio.get_event_loop()
        partial_func = partial(func, *args, **kwargs)
        
        try:
            return await loop.run_in_executor(self.process_pool, partial_func)
        except Exception as e:
            logger.error(f"Process pool execution failed: {e}")
            raise
    
    async def gather_with_concurrency(self, tasks: List[Coroutine], 
                                    max_concurrency: int = None) -> List[Any]:
        """Gather tasks with concurrency limit"""
        max_concurrency = max_concurrency or self.max_workers
        
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def limited_task(task):
            async with semaphore:
                return await task
        
        limited_tasks = [limited_task(task) for task in tasks]
        return await asyncio.gather(*limited_tasks, return_exceptions=True)
    
    async def shutdown(self):
        """Graceful shutdown of executors"""
        self.thread_pool.shutdown(wait=True)
        self.process_pool.shutdown(wait=True)

# Global async executor
async_executor = AsyncExecutor()

def async_to_sync(func: Callable) -> Callable:
    """Decorator to convert async function to sync for compatibility"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an event loop, we can't use run_until_complete
                # This is a limitation - the function should be called from async context
                raise RuntimeError("Cannot call async function from sync context")
            else:
                return loop.run_until_complete(func(*args, **kwargs))
        except Exception as e:
            logger.error(f"Async to sync conversion failed: {e}")
            raise
    return wrapper

def sync_to_async(func: Callable) -> Callable:
    """Decorator to convert sync function to async"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await async_executor.run_in_thread(func, *args, **kwargs)
    return wrapper

class AsyncSystemMonitor:
    """Async system monitoring with concurrent metric collection"""
    
    def __init__(self):
        self.last_metrics = {}
        self.collection_lock = asyncio.Lock()
    
    @sync_to_async
    def get_cpu_usage(self) -> float:
        """Get CPU usage asynchronously"""
        return psutil.cpu_percent(interval=1)
    
    @sync_to_async
    def get_memory_usage(self) -> Dict[str, float]:
        """Get memory usage asynchronously"""
        memory = psutil.virtual_memory()
        return {
            "percent": memory.percent,
            "available_gb": memory.available / (1024**3),
            "used_gb": memory.used / (1024**3),
            "total_gb": memory.total / (1024**3)
        }
    
    @sync_to_async
    def get_disk_usage(self) -> Dict[str, float]:
        """Get disk usage asynchronously"""
        disk = psutil.disk_usage('/')
        return {
            "percent": (disk.used / disk.total) * 100,
            "free_gb": disk.free / (1024**3),
            "used_gb": disk.used / (1024**3),
            "total_gb": disk.total / (1024**3)
        }
    
    @sync_to_async
    def get_network_stats(self) -> Dict[str, int]:
        """Get network statistics asynchronously"""
        net = psutil.net_io_counters()
        return {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv
        }
    
    async def collect_all_metrics(self) -> Dict[str, Any]:
        """Collect all system metrics concurrently"""
        async with self.collection_lock:
            start_time = time.time()
            
            # Run all metric collections concurrently
            tasks = [
                self.get_cpu_usage(),
                self.get_memory_usage(),
                self.get_disk_usage(),
                self.get_network_stats()
            ]
            
            results = await async_executor.gather_with_concurrency(tasks, max_concurrency=4)
            
            cpu_usage, memory_usage, disk_usage, network_stats = results
            
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "cpu": {"cpu_percent": cpu_usage},
                "memory": memory_usage,
                "disk": disk_usage,
                "network": network_stats,
                "collection_time": time.time() - start_time
            }
            
            self.last_metrics = metrics
            return metrics
    
    async def get_last_metrics(self) -> Dict[str, Any]:
        """Get last collected metrics without new collection"""
        async with self.collection_lock:
            return self.last_metrics.copy()

class AsyncDatabaseOperations:
    """Async database operations with connection pooling"""
    
    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory
        self.session_lock = asyncio.Lock()
    
    async def execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute database query asynchronously"""
        async with self.session_lock:
            def _sync_query():
                with self.db_session_factory() as session:
                    result = session.execute(text(query), params or {})
                    return [dict(row._mapping) for row in result.fetchall()]
            
            return await async_executor.run_in_thread(_sync_query)
    
    async def execute_write(self, query: str, params: Dict[str, Any] = None) -> int:
        """Execute write operation asynchronously"""
        async with self.session_lock:
            def _sync_write():
                with self.db_session_factory() as session:
                    result = session.execute(text(query), params or {})
                    session.commit()
                    return result.rowcount
            
            return await async_executor.run_in_thread(_sync_write)
    
    async def batch_insert(self, table: str, data_list: List[Dict[str, Any]]) -> int:
        """Batch insert with async execution"""
        if not data_list:
            return 0
        
        async with self.session_lock:
            def _sync_batch_insert():
                with self.db_session_factory() as session:
                    # Build batch insert query
                    columns = list(data_list[0].keys())
                    placeholders = ", ".join([f":{col}" for col in columns])
                    query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
                    
                    total_rows = 0
                    for data in data_list:
                        result = session.execute(text(query), data)
                        total_rows += result.rowcount
                    
                    session.commit()
                    return total_rows
            
            return await async_executor.run_in_thread(_sync_batch_insert)

class AsyncMLPredictor:
    """Async ML predictions with parallel model execution"""
    
    def __init__(self, enhanced_predictor):
        self.predictor = enhanced_predictor
    
    async def predict_single_resource(self, resource_type: str, features: Dict[str, Any]) -> Dict[str, Any]:
        """Predict single resource asynchronously"""
        def _sync_predict():
            try:
                result = self.predictor.predict_single(resource_type, features)
                return result
            except Exception as e:
                logger.error(f"Prediction failed for {resource_type}: {e}")
                return None
        
        return await async_executor.run_in_thread(_sync_predict)
    
    async def predict_all_resources(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Predict all resources concurrently"""
        resource_types = ["cpu_usage", "memory_usage", "disk_usage"]
        
        # Create prediction tasks for all resources
        tasks = [
            self.predict_single_resource(resource, features) 
            for resource in resource_types
        ]
        
        # Execute all predictions concurrently
        results = await async_executor.gather_with_concurrency(tasks, max_concurrency=3)
        
        # Combine results
        predictions = {}
        for i, resource_type in enumerate(resource_types):
            if results[i] is not None:
                predictions[resource_type] = results[i]
        
        return predictions
    
    async def predict_with_anomaly_detection(self, features: Dict[str, Any] = None) -> Dict[str, Any]:
        """Enhanced prediction with anomaly detection"""
        def _sync_enhanced_predict():
            try:
                return self.predictor.predict_with_anomaly_detection(features)
            except Exception as e:
                logger.error(f"Enhanced prediction failed: {e}")
                return {}
        
        return await async_executor.run_in_thread(_sync_enhanced_predict)

class AsyncCacheManager:
    """Async cache operations with Redis"""
    
    def __init__(self, cache_instance):
        self.cache = cache_instance
    
    async def get_async(self, key: str) -> Optional[Any]:
        """Get value from cache asynchronously"""
        def _sync_get():
            return self.cache.get(key)
        
        return await async_executor.run_in_thread(_sync_get)
    
    async def set_async(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """Set value in cache asynchronously"""
        def _sync_set():
            return self.cache.set(key, value, ttl_seconds)
        
        return await async_executor.run_in_thread(_sync_set)
    
    async def delete_async(self, key: str) -> bool:
        """Delete key from cache asynchronously"""
        def _sync_delete():
            return self.cache.delete(key)
        
        return await async_executor.run_in_thread(_sync_delete)
    
    async def warm_cache_concurrent(self, warm_functions: List[Callable]) -> Dict[str, bool]:
        """Warm cache with concurrent execution"""
        tasks = [async_executor.run_in_thread(func) for func in warm_functions]
        results = await async_executor.gather_with_concurrency(tasks)
        
        return {
            f"function_{i}": bool(result) 
            for i, result in enumerate(results)
        }

class BackgroundTaskManager:
    """Background task management with proper cleanup"""
    
    def __init__(self):
        self.tasks = set()
        self.running = False
    
    async def start_background_task(self, coro: Coroutine, name: str = None) -> asyncio.Task:
        """Start background task with proper tracking"""
        task = asyncio.create_task(coro, name=name)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task
    
    async def run_periodic_task(self, coro_func: Callable, interval_seconds: int, 
                              name: str = None):
        """Run periodic task with proper cleanup"""
        while self.running:
            try:
                start_time = time.time()
                await coro_func()
                execution_time = time.time() - start_time
                
                # Calculate sleep time to maintain interval
                sleep_time = max(0, interval_seconds - execution_time)
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background task {name} failed: {e}")
                await asyncio.sleep(min(60, interval_seconds))  # Wait before retry
    
    async def shutdown_all_tasks(self):
        """Graceful shutdown of all background tasks"""
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        logger.info("All background tasks shutdown complete")

# Global instances
async_system_monitor = AsyncSystemMonitor()
background_task_manager = BackgroundTaskManager()

# Utility functions for common async operations
async def collect_system_metrics_async() -> Dict[str, Any]:
    """Collect system metrics asynchronously"""
    return await async_system_monitor.collect_all_metrics()

async def execute_database_query_async(query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Execute database query asynchronously"""
    from app.core.database import SessionLocal
    db_ops = AsyncDatabaseOperations(SessionLocal)
    return await db_ops.execute_query(query, params)

async def predict_resources_async(features: Dict[str, Any] = None) -> Dict[str, Any]:
    """Predict resources asynchronously"""
    from app.ml.enhanced_predictor import enhanced_predictor
    ml_predictor = AsyncMLPredictor(enhanced_predictor)
    return await ml_predictor.predict_all_resources(features or {})

async def warm_cache_async() -> Dict[str, bool]:
    """Warm cache asynchronously"""
    from app.core.redis_cache import cache_warmer
    cache_mgr = AsyncCacheManager(cache)
    
    warm_functions = [
        cache_warmer.warm_common_metrics,
        cache_warmer.warm_common_predictions
    ]
    
    return await cache_mgr.warm_cache_concurrent(warm_functions)
