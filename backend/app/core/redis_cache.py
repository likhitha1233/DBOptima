"""
FAANG-level Redis Caching Layer
TTL-based caching with invalidation and fallback
"""

import os
import json
import pickle
import logging
import hashlib
from typing import Any, Optional, Dict, Callable
from datetime import datetime, timedelta
from functools import wraps
import redis
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CacheConfig:
    """Cache configuration"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ssl: bool = False
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    retry_on_timeout: bool = True
    health_check_interval: int = 30

class RedisCache:
    """Production-grade Redis cache with fallback"""
    
    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        self.redis_client = None
        self.in_memory_cache = {}
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "fallback_hits": 0
        }
        self._connect()
    
    def _connect(self) -> bool:
        """Connect to Redis with fallback"""
        try:
            self.redis_client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                ssl=self.config.ssl,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                retry_on_timeout=self.config.retry_on_timeout,
                health_check_interval=self.config.health_check_interval,
                decode_responses=False  # Handle binary data
            )
            
            # Test connection
            self.redis_client.ping()
            logger.info("Redis connected successfully")
            return True
            
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self.redis_client = None
            logger.warning("Using in-memory cache fallback")
            return False
    
    def _generate_cache_key(self, prefix: str, args: tuple, kwargs: dict) -> str:
        """Generate consistent cache key"""
        # Create a deterministic key from function arguments
        key_data = {
            "prefix": prefix,
            "args": args,
            "kwargs": sorted(kwargs.items())
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if self.redis_client:
                # Try Redis first
                data = self.redis_client.get(key)
                if data:
                    self.cache_stats["hits"] += 1
                    return pickle.loads(data)
                else:
                    self.cache_stats["misses"] += 1
                    return None
            else:
                # Fallback to in-memory
                if key in self.in_memory_cache:
                    cache_item = self.in_memory_cache[key]
                    if datetime.now() < cache_item["expires_at"]:
                        self.cache_stats["fallback_hits"] += 1
                        return cache_item["data"]
                    else:
                        # Expired, remove it
                        del self.in_memory_cache[key]
                
                self.cache_stats["misses"] += 1
                return None
                
        except Exception as e:
            self.cache_stats["errors"] += 1
            logger.error(f"Cache get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """Set value in cache with TTL"""
        try:
            if self.redis_client:
                # Use Redis
                data = pickle.dumps(value)
                return self.redis_client.setex(key, ttl_seconds, data)
            else:
                # Fallback to in-memory
                expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
                self.in_memory_cache[key] = {
                    "data": value,
                    "expires_at": expires_at
                }
                
                # Cleanup old entries periodically
                self._cleanup_in_memory_cache()
                return True
                
        except Exception as e:
            self.cache_stats["errors"] += 1
            logger.error(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            if self.redis_client:
                return bool(self.redis_client.delete(key))
            else:
                # Fallback to in-memory
                if key in self.in_memory_cache:
                    del self.in_memory_cache[key]
                    return True
                return False
                
        except Exception as e:
            self.cache_stats["errors"] += 1
            logger.error(f"Cache delete error: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern"""
        try:
            if self.redis_client:
                keys = self.redis_client.keys(pattern)
                if keys:
                    return self.redis_client.delete(*keys)
                return 0
            else:
                # Fallback to in-memory
                keys_to_delete = []
                for key in self.in_memory_cache:
                    if pattern.replace("*", "") in key:
                        keys_to_delete.append(key)
                
                for key in keys_to_delete:
                    del self.in_memory_cache[key]
                
                return len(keys_to_delete)
                
        except Exception as e:
            self.cache_stats["errors"] += 1
            logger.error(f"Cache delete pattern error: {e}")
            return 0
    
    def _cleanup_in_memory_cache(self):
        """Clean up expired in-memory cache entries"""
        now = datetime.now()
        expired_keys = []
        
        for key, cache_item in self.in_memory_cache.items():
            if now >= cache_item["expires_at"]:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.in_memory_cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (self.cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.cache_stats,
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2),
            "redis_connected": self.redis_client is not None,
            "in_memory_cache_size": len(self.in_memory_cache)
        }
    
    def health_check(self) -> bool:
        """Check cache health"""
        try:
            if self.redis_client:
                self.redis_client.ping()
                return True
            else:
                return len(self.in_memory_cache) >= 0  # Always true for in-memory
        except:
            return False

# TTL configurations for different data types (optimized for 60-120 seconds)
CACHE_TTL = {
    "metrics": 90,           # 1.5 minutes
    "predictions": 120,     # 2 minutes
    "recommendations": 110,  # ~2 minutes
    "query_insights": 100,  # ~1.5 minutes
    "anomaly_status": 80,   # ~1.5 minutes
    "system_status": 60,    # 1 minute
}

# Initialize cache
try:
    cache_config = CacheConfig(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=int(os.getenv('REDIS_DB', 0)),
        password=os.getenv('REDIS_PASSWORD'),
        ssl=os.getenv('REDIS_SSL', 'false').lower() == 'true'
    )
    cache = RedisCache(cache_config)
    logger.info("Redis cache initialized")
except Exception as e:
    cache = RedisCache()  # Use default config with in-memory fallback
    logger.error(f"Redis cache initialization failed: {e}")

def cached(ttl_seconds: int = 300, key_prefix: str = "", invalidate_on: list = None):
    """Decorator for caching function results"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            prefix = key_prefix or f"{func.__module__}.{func.__name__}"
            cache_key = cache._generate_cache_key(prefix, args, kwargs)
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl_seconds)
            
            return result
        
        # Add cache management methods
        wrapper.invalidate_cache = lambda: cache.delete_pattern(f"{key_prefix or func.__module__}.{func.__name__}:*")
        wrapper.get_cache_stats = lambda: cache.get_stats()
        
        return wrapper
    return decorator

def invalidate_cache_pattern(pattern: str) -> int:
    """Invalidate cache entries matching pattern"""
    return cache.delete_pattern(pattern)

# Specific cache invalidation functions
def invalidate_metrics_cache():
    """Invalidate all metrics-related cache"""
    return invalidate_cache_pattern("metrics:*")

def invalidate_predictions_cache():
    """Invalidate all predictions-related cache"""
    return invalidate_cache_pattern("predictions:*")

def invalidate_recommendations_cache():
    """Invalidate all recommendations-related cache"""
    return invalidate_cache_pattern("recommendations:*")

def invalidate_all_cache():
    """Invalidate all application cache"""
    return invalidate_cache_pattern("*")

# Automatic cache invalidation for data changes
def invalidate_on_data_insert(data_type: str, affected_resources: list = None):
    """Invalidate cache when new data is inserted"""
    invalidation_patterns = []
    
    if data_type == "metrics":
        # Invalidate metrics-related cache
        invalidation_patterns.extend([
            "metrics:*",
            "system_status:*",
            "anomaly_status:*"
        ])
    
    elif data_type == "predictions":
        # Invalidate predictions-related cache
        invalidation_patterns.extend([
            "predictions:*",
            "app.monitoring.db_monitor.get_system_metrics:*",
            "app.ml.enhanced_predictor.predict_with_anomaly_detection:*"
        ])
    
    elif data_type == "recommendations":
        # Invalidate recommendations cache
        invalidation_patterns.extend([
            "recommendations:*",
            "query_insights:*"
        ])
    
    elif data_type == "all":
        # Invalidate everything
        return invalidate_all_cache()
    
    # Add resource-specific patterns if specified
    if affected_resources:
        for resource in affected_resources:
            invalidation_patterns.append(f"*{resource}*")
    
    # Execute invalidation
    total_invalidated = 0
    for pattern in invalidation_patterns:
        total_invalidated += invalidate_cache_pattern(pattern)
    
    logger.info(f"Invalidated {total_invalidated} cache entries for {data_type} data insertion")
    return total_invalidated

# Decorator for automatic cache invalidation
def auto_invalidate_on_insert(data_type: str, resources: list = None):
    """Decorator that invalidates cache when function modifies data"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Execute the function
            result = func(*args, **kwargs)
            
            # Invalidate cache after successful execution
            try:
                invalidate_on_data_insert(data_type, resources)
            except Exception as e:
                logger.error(f"Failed to invalidate cache after {func.__name__}: {e}")
            
            return result
        return wrapper
    return decorator

# Cache warming functions with automatic invalidation
async def warm_metrics_cache():
    """Warm up metrics cache with common queries"""
    try:
        from app.monitoring.db_monitor import RealDatabaseMonitor
        monitor = RealDatabaseMonitor()
        
        # Cache common metrics with optimized TTL
        metrics = monitor.get_system_metrics()
        cache.set("metrics:current", metrics, CACHE_TTL["metrics"])
        
        logger.info(f"Metrics cache warmed (TTL: {CACHE_TTL['metrics']}s)")
    except Exception as e:
        logger.error(f"Failed to warm metrics cache: {e}")

async def warm_predictions_cache():
    """Warm up predictions cache"""
    try:
        from app.ml.enhanced_predictor import enhanced_predictor
        
        predictions = enhanced_predictor.predict_with_anomaly_detection()
        cache.set("predictions:current", predictions, CACHE_TTL["predictions"])
        
        logger.info(f"Predictions cache warmed (TTL: {CACHE_TTL['predictions']}s)")
    except Exception as e:
        logger.error(f"Failed to warm predictions cache: {e}")

# Automatic cache invalidation on data changes
def auto_invalidate_on_new_data(data_inserted: bool = False, data_type: str = "metrics"):
    """Automatically invalidate cache when new data is detected"""
    if data_inserted:
        logger.info(f"New {data_type} data detected, invalidating relevant cache")
        return invalidate_on_data_insert(data_type)
    return 0

# Enhanced cache decorator with auto-invalidation
def cached_with_invalidation(ttl_seconds: int = 90, key_prefix: str = "", invalidate_on_insert: str = None):
    """Enhanced decorator with automatic cache invalidation"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            prefix = key_prefix or f"{func.__module__}.{func.__name__}"
            cache_key = cache._generate_cache_key(prefix, args, kwargs)
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            
            # Use optimized TTL if not specified
            actual_ttl = ttl_seconds
            if ttl_seconds == 90:  # Default TTL
                # Determine appropriate TTL based on function name/prefix
                if "metrics" in prefix.lower():
                    actual_ttl = CACHE_TTL["metrics"]
                elif "prediction" in prefix.lower():
                    actual_ttl = CACHE_TTL["predictions"]
                elif "recommendation" in prefix.lower():
                    actual_ttl = CACHE_TTL["recommendations"]
                elif "query" in prefix.lower():
                    actual_ttl = CACHE_TTL["query_insights"]
                elif "anomaly" in prefix.lower():
                    actual_ttl = CACHE_TTL["anomaly_status"]
                elif "system" in prefix.lower():
                    actual_ttl = CACHE_TTL["system_status"]
            
            cache.set(cache_key, result, actual_ttl)
            
            return result
        
        # Add cache management methods
        wrapper.invalidate_cache = lambda: cache.delete_pattern(f"{key_prefix or func.__module__}.{func.__name__}:*")
        wrapper.get_cache_stats = lambda: cache.get_stats()
        
        # Add auto-invalidation if specified
        if invalidate_on_insert:
            wrapper.auto_invalidate = lambda: invalidate_on_data_insert(invalidate_on_insert)
        
        return wrapper
    return decorator

# Background cache management
class CacheManager:
    """Background cache management and optimization"""
    
    def __init__(self):
        self.cache = cache
        self.last_cleanup = datetime.now()
    
    async def background_cleanup(self):
        """Background cleanup of expired cache entries"""
        try:
            if not self.cache.redis_client:
                self.cache._cleanup_in_memory_cache()
                self.last_cleanup = datetime.now()
                logger.debug("In-memory cache cleanup completed")
        except Exception as e:
            logger.error(f"Background cache cleanup failed: {e}")
    
    async def background_warming(self):
        """Background cache warming"""
        try:
            await warm_metrics_cache()
            await warm_predictions_cache()
            logger.info("Background cache warming completed")
        except Exception as e:
            logger.error(f"Background cache warming failed: {e}")
    
    def get_cache_health(self) -> Dict[str, Any]:
        """Get comprehensive cache health information"""
        stats = self.cache.get_stats()
        health = self.cache.health_check()
        
        return {
            "healthy": health,
            "stats": stats,
            "last_cleanup": self.last_cleanup.isoformat(),
            "redis_connected": self.cache.redis_client is not None
        }

cache_manager = CacheManager()
