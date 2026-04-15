#!/usr/bin/env python3
"""
Production-grade Security Layer
API Key Authentication and Rate Limiting
"""

import os
import time
import hashlib
import logging
from typing import Dict, Optional, Any
from datetime import datetime
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from collections import defaultdict, deque
import redis
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_size: int = 10

class InMemoryRateLimiter:
    """In-memory rate limiter for development/testing"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.requests = defaultdict(lambda: defaultdict(deque))
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
    
    def _cleanup_old_requests(self):
        """Clean up old request records"""
        now = time.time()
        if now - self.last_cleanup < self.cleanup_interval:
            return
        
        current_time = now
        for client_id in list(self.requests.keys()):
            for window in list(self.requests[client_id].keys()):
                requests_queue = self.requests[client_id][window]
                # Remove requests older than the window
                while requests_queue and requests_queue[0] < current_time - window:
                    requests_queue.popleft()
                
                # Remove empty windows
                if not requests_queue:
                    del self.requests[client_id][window]
            
            # Remove empty clients
            if not self.requests[client_id]:
                del self.requests[client_id]
        
        self.last_cleanup = current_time
    
    def is_allowed(self, client_id: str) -> tuple[bool, Dict[str, Any]]:
        """Check if request is allowed"""
        self._cleanup_old_requests()
        
        now = time.time()
        client_requests = self.requests[client_id]
        
        # Check different time windows
        windows = [
            (60, self.config.requests_per_minute, "minute"),
            (3600, self.config.requests_per_hour, "hour"),
            (86400, self.config.requests_per_day, "day")
        ]
        
        for window_size, max_requests, window_name in windows:
            window_requests = client_requests[window_size]
            
            # Remove old requests from this window
            while window_requests and window_requests[0] < now - window_size:
                window_requests.popleft()
            
            # Check if we've exceeded the limit
            if len(window_requests) >= max_requests:
                return False, {
                    "allowed": False,
                    "limit": max_requests,
                    "remaining": 0,
                    "reset_time": int(window_requests[0] + window_size),
                    "window": window_name
                }
        
        # Record this request
        for window_size, _, _ in windows:
            self.requests[client_id][window_size].append(now)
        
        # Calculate remaining requests for the smallest window (minute)
        minute_requests = len(client_requests[60])
        remaining = max(0, self.config.requests_per_minute - minute_requests)
        
        return True, {
            "allowed": True,
            "limit": self.config.requests_per_minute,
            "remaining": remaining,
            "reset_time": int(now + 60),
            "window": "minute"
        }

class RedisRateLimiter:
    """Redis-based rate limiter for production"""
    
    def __init__(self, config: RateLimitConfig, redis_url: str = None):
        self.config = config
        self.redis_client = None
        
        if redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()  # Test connection
                logger.info("Redis rate limiter initialized")
            except Exception as e:
                logger.warning(f"Redis connection failed, falling back to in-memory: {e}")
                self.rate_limiter = InMemoryRateLimiter(config)
        else:
            logger.info("Redis not configured, using in-memory rate limiter")
            self.rate_limiter = InMemoryRateLimiter(config)
    
    def is_allowed(self, client_id: str) -> tuple[bool, Dict[str, Any]]:
        """Check if request is allowed"""
        if self.redis_client:
            return self._redis_is_allowed(client_id)
        else:
            return self.rate_limiter.is_allowed(client_id)
    
    def _redis_is_allowed(self, client_id: str) -> tuple[bool, Dict[str, Any]]:
        """Redis-based rate limiting using sliding window"""
        now = int(time.time())
        window = 60  # 1 minute window
        max_requests = self.config.requests_per_minute
        
        # Use Redis sorted set for sliding window
        key = f"rate_limit:{client_id}"
        
        try:
            # Remove old entries
            self.redis_client.zremrangebyscore(key, 0, now - window)
            
            # Count current requests
            current_requests = self.redis_client.zcard(key)
            
            if current_requests >= max_requests:
                # Get oldest request to calculate reset time
                oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
                reset_time = int(oldest[0][1]) + window if oldest else now + window
                
                return False, {
                    "allowed": False,
                    "limit": max_requests,
                    "remaining": 0,
                    "reset_time": reset_time,
                    "window": "minute"
                }
            
            # Add current request
            self.redis_client.zadd(key, {str(now): now})
            self.redis_client.expire(key, window)
            
            remaining = max_requests - current_requests - 1
            
            return True, {
                "allowed": True,
                "limit": max_requests,
                "remaining": remaining,
                "reset_time": now + window,
                "window": "minute"
            }
            
        except Exception as e:
            logger.error(f"Redis rate limiting failed: {e}")
            # Fallback to in-memory
            return self.rate_limiter.is_allowed(client_id)

class APIKeyAuthenticator:
    """API Key Authentication System"""
    
    def __init__(self):
        self.api_keys = self._load_api_keys()
        self.security = HTTPBearer(auto_error=False)
    
    def _load_api_keys(self) -> Dict[str, Dict[str, Any]]:
        """Load API keys from environment variables"""
        api_keys = {}
        
        # Load from environment variable (comma-separated)
        api_keys_env = os.getenv('API_KEYS', '')
        if api_keys_env:
            for key_string in api_keys_env.split(','):
                key_string = key_string.strip()
                if key_string:
                    key_hash = self._hash_api_key(key_string)
                    api_keys[key_hash] = {
                        'name': 'default',
                        'permissions': ['read', 'write'],
                        'created_at': datetime.now().isoformat(),
                        'last_used': None
                    }
        
        # Load from individual environment variables
        for i in range(1, 10):  # Support API_KEY_1, API_KEY_2, etc.
            key_var = f'API_KEY_{i}'
            key_value = os.getenv(key_var)
            if key_value:
                key_hash = self._hash_api_key(key_value)
                api_keys[key_hash] = {
                    'name': f'key_{i}',
                    'permissions': ['read', 'write'],
                    'created_at': datetime.now().isoformat(),
                    'last_used': None
                }
        
        logger.info(f"Loaded {len(api_keys)} API keys")
        return api_keys
    
    def _hash_api_key(self, api_key: str) -> str:
        """Hash API key for secure storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Validate API key and return key info"""
        if not api_key:
            return None
        
        key_hash = self._hash_api_key(api_key)
        
        if key_hash in self.api_keys:
            key_info = self.api_keys[key_hash].copy()
            key_info['last_used'] = datetime.now().isoformat()
            self.api_keys[key_hash] = key_info
            return key_info
        
        return None
    
    def get_client_id_from_request(self, request: Request) -> str:
        """Extract client ID from request"""
        # Try API key first
        auth_header = request.headers.get('authorization')
        if auth_header and auth_header.startswith('Bearer '):
            api_key = auth_header[7:]  # Remove 'Bearer '
            key_info = self.validate_api_key(api_key)
            if key_info:
                return f"api_key:{key_info['name']}"
        
        # Fallback to IP address
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        
        return f"ip:{client_ip}"

# Global instances
rate_limit_config = RateLimitConfig(
    requests_per_minute=int(os.getenv('RATE_LIMIT_PER_MINUTE', '60')),
    requests_per_hour=int(os.getenv('RATE_LIMIT_PER_HOUR', '1000')),
    requests_per_day=int(os.getenv('RATE_LIMIT_PER_DAY', '10000')),
    burst_size=int(os.getenv('RATE_LIMIT_BURST', '10'))
)

redis_url = os.getenv('REDIS_URL')
rate_limiter = RedisRateLimiter(rate_limit_config, redis_url)
api_key_authenticator = APIKeyAuthenticator()

# FastAPI dependencies
async def get_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(api_key_authenticator.security)
) -> Dict[str, Any]:
    """FastAPI dependency for API key authentication"""
    
    # Skip authentication for health check
    if request.url.path in ['/health', '/', '/info']:
        return {"authenticated": False, "skip": True}
    
    # Check if authentication is disabled (for development)
    if os.getenv('DISABLE_AUTH', 'false').lower() == 'true':
        logger.warning("Authentication disabled - development mode")
        return {"authenticated": True, "name": "dev_mode", "skip": False}
    
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    key_info = api_key_authenticator.validate_api_key(credentials.credentials)
    
    if not key_info:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info(f"API key authenticated: {key_info['name']}")
    return {"authenticated": True, **key_info}

async def rate_limit_check(request: Request) -> Dict[str, Any]:
    """FastAPI dependency for rate limiting"""
    
    # Skip rate limiting for health check
    if request.url.path in ['/health', '/', '/info']:
        return {"allowed": True, "skip": True}
    
    # Check if rate limiting is disabled
    if os.getenv('DISABLE_RATE_LIMIT', 'false').lower() == 'true':
        logger.warning("Rate limiting disabled - development mode")
        return {"allowed": True, "skip": True}
    
    client_id = api_key_authenticator.get_client_id_from_request(request)
    allowed, info = rate_limiter.is_allowed(client_id)
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": str(info["remaining"]),
                "X-RateLimit-Reset": str(info["reset_time"]),
                "Retry-After": str(info["reset_time"] - int(time.time()))
            }
        )
    
    return {"allowed": True, **info}

# Combined dependency for both authentication and rate limiting
async def security_check(
    request: Request,
    api_key_info: Dict[str, Any] = Depends(get_api_key),
    rate_limit_info: Dict[str, Any] = Depends(rate_limit_check)
) -> Dict[str, Any]:
    """Combined security check"""
    
    return {
        "authenticated": api_key_info.get("authenticated", False),
        "rate_limited": rate_limit_info.get("allowed", True),
        "api_key_name": api_key_info.get("name", "anonymous"),
        "client_id": api_key_authenticator.get_client_id_from_request(request),
        "rate_limit_info": rate_limit_info
    }

# Security middleware for adding headers
async def add_security_headers(request: Request, call_next):
    """Add security headers to responses"""
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Add rate limit headers if available
    if hasattr(request.state, 'rate_limit_info'):
        info = request.state.rate_limit_info
        response.headers["X-RateLimit-Limit"] = str(info.get("limit", ""))
        response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", ""))
        response.headers["X-RateLimit-Reset"] = str(info.get("reset_time", ""))
    
    return response
