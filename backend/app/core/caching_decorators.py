"""
FAANG-level Caching Decorators
Specialized decorators for different API endpoints
"""

import json
import logging
from functools import wraps
from typing import Callable
from .redis_cache import cache, CACHE_TTL, invalidate_cache_pattern

logger = logging.getLogger(__name__)

def cache_metrics(ttl_seconds: int = None):
    """Cache decorator specifically for metrics endpoints"""
    ttl = ttl_seconds or CACHE_TTL["metrics"]
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key specific to metrics
            cache_key = f"metrics:{_generate_args_hash(args, kwargs)}"
            
            # Try cache first
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute and cache
            result = func(*args, **kwargs)
            
            # Only cache successful results
            if isinstance(result, dict) and result.get("status") == "success":
                cache.set(cache_key, result, ttl)
            
            return result
        
        # Add cache invalidation method
        wrapper.invalidate_cache = lambda: invalidate_cache_pattern("metrics:*")
        return wrapper
    return decorator

def cache_predictions(ttl_seconds: int = None):
    """Cache decorator specifically for predictions endpoints"""
    ttl = ttl_seconds or CACHE_TTL["predictions"]
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key specific to predictions
            cache_key = f"predictions:{_generate_args_hash(args, kwargs)}"
            
            # Try cache first
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute and cache
            result = func(*args, **kwargs)
            
            # Only cache successful results with valid predictions
            if isinstance(result, dict) and result.get("status") == "success":
                if result.get("data", {}).get("predictions"):
                    cache.set(cache_key, result, ttl)
            
            return result
        
        # Add cache invalidation method
        wrapper.invalidate_cache = lambda: invalidate_cache_pattern("predictions:*")
        return wrapper
    return decorator

def cache_recommendations(ttl_seconds: int = None):
    """Cache decorator specifically for recommendations endpoints"""
    ttl = ttl_seconds or CACHE_TTL["recommendations"]
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key specific to recommendations
            cache_key = f"recommendations:{_generate_args_hash(args, kwargs)}"
            
            # Try cache first
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute and cache
            result = func(*args, **kwargs)
            
            # Only cache successful results with recommendations
            if isinstance(result, dict) and result.get("status") == "success":
                if result.get("data", {}).get("recommendations"):
                    cache.set(cache_key, result, ttl)
            
            return result
        
        # Add cache invalidation method
        wrapper.invalidate_cache = lambda: invalidate_cache_pattern("recommendations:*")
        return wrapper
    return decorator

def cache_query_insights(ttl_seconds: int = None):
    """Cache decorator specifically for query insights endpoints"""
    ttl = ttl_seconds or CACHE_TTL["query_insights"]
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key specific to query insights
            cache_key = f"query_insights:{_generate_args_hash(args, kwargs)}"
            
            # Try cache first
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute and cache
            result = func(*args, **kwargs)
            
            # Only cache successful results
            if isinstance(result, dict) and result.get("status") == "success":
                cache.set(cache_key, result, ttl)
            
            return result
        
        # Add cache invalidation method
        wrapper.invalidate_cache = lambda: invalidate_cache_pattern("query_insights:*")
        return wrapper
    return decorator

def cache_anomaly_status(ttl_seconds: int = None):
    """Cache decorator specifically for anomaly status endpoints"""
    ttl = ttl_seconds or CACHE_TTL["anomaly_status"]
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key specific to anomaly status
            cache_key = f"anomaly_status:{_generate_args_hash(args, kwargs)}"
            
            # Try cache first
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute and cache
            result = func(*args, **kwargs)
            
            # Only cache successful results
            if isinstance(result, dict) and result.get("status") == "success":
                cache.set(cache_key, result, ttl)
            
            return result
        
        # Add cache invalidation method
        wrapper.invalidate_cache = lambda: invalidate_cache_pattern("anomaly_status:*")
        return wrapper
    return decorator

def cache_system_status(ttl_seconds: int = None):
    """Cache decorator specifically for system status endpoints"""
    ttl = ttl_seconds or CACHE_TTL["system_status"]
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key specific to system status
            cache_key = f"system_status:{_generate_args_hash(args, kwargs)}"
            
            # Try cache first
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute and cache
            result = func(*args, **kwargs)
            
            # Always cache system status (even if not successful)
            if isinstance(result, dict):
                cache.set(cache_key, result, ttl)
            
            return result
        
        # Add cache invalidation method
        wrapper.invalidate_cache = lambda: invalidate_cache_pattern("system_status:*")
        return wrapper
    return decorator

def invalidate_on_new_data(data_types: list = None):
    """Decorator to invalidate cache when new data is added"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Invalidate relevant caches if operation was successful
            if isinstance(result, dict) and result.get("status") == "success":
                data_types = data_types or []
                
                for data_type in data_types:
                    if data_type == "metrics":
                        invalidate_cache_pattern("metrics:*")
                    elif data_type == "predictions":
                        invalidate_cache_pattern("predictions:*")
                    elif data_type == "recommendations":
                        invalidate_cache_pattern("recommendations:*")
                    elif data_type == "all":
                        invalidate_cache_pattern("*")
            
            return result
        return wrapper
    return decorator

def _generate_args_hash(args: tuple, kwargs: dict) -> str:
    """Generate hash from function arguments for cache key"""
    import hashlib
    
    # Convert args and kwargs to a hashable representation
    args_data = []
    
    # Handle positional arguments
    for arg in args:
        if isinstance(arg, (dict, list, tuple)):
            args_data.append(json.dumps(arg, sort_keys=True, default=str))
        else:
            args_data.append(str(arg))
    
    # Handle keyword arguments
    kwargs_data = {}
    for key, value in kwargs.items():
        if isinstance(value, (dict, list, tuple)):
            kwargs_data[key] = json.dumps(value, sort_keys=True, default=str)
        else:
            kwargs_data[key] = str(value)
    
    # Create combined data
    combined_data = {
        "args": args_data,
        "kwargs": sorted(kwargs_data.items())
    }
    
    # Generate hash
    data_str = json.dumps(combined_data, sort_keys=True)
    return hashlib.md5(data_str.encode()).hexdigest()[:16]

# Smart cache invalidation based on data changes
class SmartCacheInvalidator:
    """Intelligent cache invalidation based on data relationships"""
    
    def __init__(self):
        self.invalidation_rules = {
            "new_metrics": ["metrics:*", "predictions:*", "recommendations:*"],
            "new_predictions": ["predictions:*"],
            "new_recommendations": ["recommendations:*"],
            "model_retrain": ["predictions:*", "recommendations:*"],
            "anomaly_detected": ["anomaly_status:*", "metrics:*", "predictions:*"]
        }
    
    def invalidate_on_event(self, event_type: str) -> int:
        """Invalidate cache based on event type"""
        patterns = self.invalidation_rules.get(event_type, [])
        total_invalidated = 0
        
        for pattern in patterns:
            total_invalidated += invalidate_cache_pattern(pattern)
        
        logger.info(f"Cache invalidation for {event_type}: {total_invalidated} keys removed")
        return total_invalidated
    
    def invalidate_metrics_dependent(self):
        """Invalidate all metrics-dependent caches"""
        return self.invalidate_on_event("new_metrics")
    
    def invalidate_ml_dependent(self):
        """Invalidate all ML-dependent caches"""
        return self.invalidate_on_event("model_retrain")

# Global invalidator instance
cache_invalidator = SmartCacheInvalidator()

# Cache warming utilities
class CacheWarmer:
    """Utility for warming up cache with common queries"""
    
    @staticmethod
    async def warm_common_metrics():
        """Warm up common metrics queries"""
        try:
            from app.monitoring.db_monitor import RealDatabaseMonitor
            monitor = RealDatabaseMonitor()
            
            # Current metrics
            current_metrics = monitor.get_system_metrics()
            cache.set("metrics:current", current_metrics, CACHE_TTL["metrics"])
            
            # Historical metrics for common time ranges
            for hours in [1, 6, 24]:
                historical_key = f"metrics:historical:{hours}h"
                # This would typically query historical data
                cache.set(historical_key, {"status": "success", "data": {}}, CACHE_TTL["metrics"])
            
            logger.info("Common metrics cache warmed")
        except Exception as e:
            logger.error(f"Failed to warm metrics cache: {e}")
    
    @staticmethod
    async def warm_common_predictions():
        """Warm up common predictions"""
        try:
            from app.ml.enhanced_predictor import enhanced_predictor
            
            predictions = enhanced_predictor.predict_with_anomaly_detection()
            cache.set("predictions:current", predictions, CACHE_TTL["predictions"])
            
            logger.info("Common predictions cache warmed")
        except Exception as e:
            logger.error(f"Failed to warm predictions cache: {e}")
    
    @staticmethod
    async def warm_all():
        """Warm up all common cache entries"""
        await CacheWarmer.warm_common_metrics()
        await CacheWarmer.warm_common_predictions()
        logger.info("All common cache entries warmed")

cache_warmer = CacheWarmer()
