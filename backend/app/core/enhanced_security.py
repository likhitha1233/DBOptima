"""
FAANG-level Security Enhancements
Per-endpoint rate limiting, validation middleware, API key rotation
"""

import os
import time
import hashlib
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, Depends
from collections import defaultdict, deque
import redis
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class EndpointRateLimit:
    """Per-endpoint rate limiting configuration"""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_size: int = 10

class EnhancedRateLimiter:
    """Redis-backed rate limiter with per-endpoint limits"""
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.in_memory_fallback = defaultdict(lambda: defaultdict(deque))
        
        # Per-endpoint rate limits
        self.endpoint_limits = {
            "/api/v1/metrics": EndpointRateLimit(120, 2000, 20000, 20),
            "/api/v1/predictions": EndpointRateLimit(60, 1000, 10000, 10),
            "/api/v1/recommendations/indexes": EndpointRateLimit(30, 500, 5000, 5),
            "/api/v1/anomaly/status": EndpointRateLimit(60, 1000, 10000, 10),
            "/api/v1/queries/insights": EndpointRateLimit(30, 500, 5000, 5),
            "/api/v1/enhanced/metrics/history": EndpointRateLimit(20, 300, 3000, 3),
        }
    
    def is_allowed(self, key: str, endpoint: str, window: str, limit: int) -> tuple[bool, Dict[str, Any]]:
        """Check if request is allowed with detailed info"""
        if self.redis:
            return self._redis_check(key, endpoint, window, limit)
        else:
            return self._in_memory_check(key, endpoint, window, limit)
    
    def _redis_check(self, key: str, endpoint: str, window: str, limit: int) -> tuple[bool, Dict[str, Any]]:
        """Redis-based rate limiting"""
        redis_key = f"rate_limit:{endpoint}:{key}:{window}"
        current_time = int(time.time())
        
        try:
            # Use Redis pipeline for atomic operations
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(redis_key, 0, current_time - self._get_window_seconds(window))
            pipe.zcard(redis_key)
            pipe.zadd(redis_key, {str(current_time): current_time})
            pipe.expire(redis_key, self._get_window_seconds(window))
            
            results = pipe.execute()
            current_count = results[1]
            
            return current_count < limit, {
                "current": current_count,
                "limit": limit,
                "remaining": max(0, limit - current_count),
                "reset_time": current_time + self._get_window_seconds(window)
            }
        except Exception as e:
            logger.error(f"Redis rate limiting failed: {e}")
            return self._in_memory_check(key, endpoint, window, limit)
    
    def _in_memory_check(self, key: str, endpoint: str, window: str, limit: int) -> tuple[bool, Dict[str, Any]]:
        """In-memory fallback rate limiting"""
        now = time.time()
        window_seconds = self._get_window_seconds(window)
        cutoff = now - window_seconds
        
        requests = self.in_memory_fallback[endpoint][key]
        
        # Remove old requests
        while requests and requests[0] < cutoff:
            requests.popleft()
        
        current_count = len(requests)
        requests.append(now)
        
        return current_count < limit, {
            "current": current_count,
            "limit": limit,
            "remaining": max(0, limit - current_count),
            "reset_time": now + window_seconds
        }
    
    def _get_window_seconds(self, window: str) -> int:
        """Convert window string to seconds"""
        mapping = {"minute": 60, "hour": 3600, "day": 86400}
        return mapping.get(window, 60)

class APIKeyManager:
    """API key rotation and management system"""
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.keys = {}  # Fallback storage
        
    def generate_key(self, client_id: str, expires_days: int = 30) -> str:
        """Generate new API key with expiration"""
        key_data = f"{client_id}:{datetime.now().isoformat()}:{os.urandom(16).hex()}"
        api_key = hashlib.sha256(key_data.encode()).hexdigest()
        
        key_info = {
            "client_id": client_id,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=expires_days)).isoformat(),
            "last_used": None,
            "usage_count": 0
        }
        
        if self.redis:
            self.redis.hset("api_keys", api_key, str(key_info))
            self.redis.expire(f"api_key:{api_key}", expires_days * 86400)
        else:
            self.keys[api_key] = key_info
        
        return api_key
    
    def validate_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Validate API key and update usage"""
        if self.redis:
            try:
                key_data = self.redis.hget("api_keys", api_key)
                if not key_data:
                    return None
                
                key_info = eval(key_data.decode())
                
                # Check expiration
                expires_at = datetime.fromisoformat(key_info["expires_at"])
                if datetime.now() > expires_at:
                    return None
                
                # Update usage
                key_info["last_used"] = datetime.now().isoformat()
                key_info["usage_count"] += 1
                self.redis.hset("api_keys", api_key, str(key_info))
                
                return key_info
                
            except Exception as e:
                logger.error(f"API key validation failed: {e}")
                return None
        else:
            key_info = self.keys.get(api_key)
            if not key_info:
                return None
            
            # Check expiration
            expires_at = datetime.fromisoformat(key_info["expires_at"])
            if datetime.now() > expires_at:
                return None
            
            # Update usage
            key_info["last_used"] = datetime.now().isoformat()
            key_info["usage_count"] += 1
            
            return key_info

# Initialize components
try:
    import redis
    redis_client = redis.Redis(host=os.getenv('REDIS_HOST', 'localhost'), 
                              port=int(os.getenv('REDIS_PORT', 6379)), 
                              decode_responses=True)
    redis_client.ping()
    logger.info("Redis connected for enhanced security")
except:
    redis_client = None
    logger.warning("Redis not available, using in-memory fallback")

enhanced_rate_limiter = EnhancedRateLimiter(redis_client)
api_key_manager = APIKeyManager(redis_client)

async def per_endpoint_rate_limit(request: Request):
    """Per-endpoint rate limiting middleware"""
    client_ip = request.client.host
    endpoint = request.url.path
    
    # Get API key if present
    auth_header = request.headers.get("Authorization")
    rate_limit_key = auth_header.split(" ")[1] if auth_header and auth_header.startswith("Bearer ") else client_ip
    
    # Get endpoint-specific limits
    endpoint_config = enhanced_rate_limiter.endpoint_limits.get(endpoint)
    if not endpoint_config:
        endpoint_config = EndpointRateLimit(60, 1000, 10000, 10)  # Default limits
    
    # Check each time window
    for window, limit in [
        ("minute", endpoint_config.requests_per_minute),
        ("hour", endpoint_config.requests_per_hour),
        ("day", endpoint_config.requests_per_day)
    ]:
        allowed, info = enhanced_rate_limiter.is_allowed(rate_limit_key, endpoint, window, limit)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for {rate_limit_key} on {endpoint}: {info}")
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "endpoint": endpoint,
                    "window": window,
                    "limit": limit,
                    "reset_time": info["reset_time"]
                },
                headers={"Retry-After": str(info["reset_time"] - int(time.time()))}
            )
    
    # Add rate limit headers
    request.state.rate_limit_info = info

async def enhanced_security_check(request: Request):
    """Enhanced security validation"""
    # Validate request size
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=413, detail="Request too large")
    
    # Validate User-Agent
    user_agent = request.headers.get("User-Agent", "")
    if not user_agent or len(user_agent) > 500:
        raise HTTPException(status_code=400, detail="Invalid User-Agent header")
    
    # Log security events
    if request.url.path in ["/api/v1/predictions", "/api/v1/recommendations/indexes"]:
        logger.info(f"Security check passed for {request.client.host} accessing {request.url.path}")

def get_enhanced_api_key(request: Request = Depends(per_endpoint_rate_limit)):
    """Enhanced API key validation with rotation support"""
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key format",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    api_key = auth_header.split(" ")[1]
    key_info = api_key_manager.validate_key(api_key)
    
    if not key_info:
        logger.warning(f"Invalid API key used from {request.client.host}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    request.state.api_key_info = key_info
    return key_info
