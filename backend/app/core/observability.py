"""
FAANG-level Observability Stack
Prometheus metrics, structured JSON logging, request tracing
"""

import json
import time
import uuid
import logging
import psutil
from typing import Dict, Any, Optional
from datetime import datetime
from functools import wraps
from fastapi import Request
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import asyncio
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Prometheus Metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'active_connections',
    'Number of active connections'
)

SYSTEM_CPU_USAGE = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage'
)

SYSTEM_MEMORY_USAGE = Gauge(
    'system_memory_usage_percent',
    'System memory usage percentage'
)

SYSTEM_DISK_USAGE = Gauge(
    'system_disk_usage_percent',
    'System disk usage percentage'
)

DATABASE_CONNECTIONS = Gauge(
    'database_connections_active',
    'Active database connections'
)

ML_PREDICTION_COUNT = Counter(
    'ml_predictions_total',
    'Total ML predictions',
    ['model_type', 'prediction_type']
)

ML_PREDICTION_DURATION = Histogram(
    'ml_prediction_duration_seconds',
    'ML prediction duration in seconds',
    ['model_type']
)

CACHE_HIT_RATE = Gauge(
    'cache_hit_rate_percent',
    'Cache hit rate percentage',
    ['cache_type']
)

ERROR_COUNT = Counter(
    'errors_total',
    'Total errors',
    ['error_type', 'component']
)

@dataclass
class TraceContext:
    """Request tracing context"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    start_time: float = None
    tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}
        if self.start_time is None:
            self.start_time = time.time()

class StructuredLogger:
    """Structured JSON logger for production"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.component = name
    
    def _log_structured(self, level: str, message: str, **kwargs):
        """Log structured message"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "component": self.component,
            "message": message,
            **kwargs
        }
        
        # Convert to JSON string
        log_message = json.dumps(log_entry, default=str)
        
        # Log with appropriate level
        if level == "ERROR":
            self.logger.error(log_message)
        elif level == "WARNING":
            self.logger.warning(log_message)
        elif level == "INFO":
            self.logger.info(log_message)
        else:
            self.logger.debug(log_message)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log_structured("INFO", message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log_structured("WARNING", message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log_structured("ERROR", message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log_structured("DEBUG", message, **kwargs)

class RequestTracer:
    """Request tracing with distributed tracing support"""
    
    def __init__(self):
        self.active_traces: Dict[str, TraceContext] = {}
    
    def start_trace(self, request: Request) -> TraceContext:
        """Start tracing a request"""
        # Generate trace ID
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())[:8]
        
        # Check for existing trace headers
        parent_trace_id = request.headers.get("X-Trace-ID")
        parent_span_id = request.headers.get("X-Parent-Span-ID")
        
        # Create trace context
        trace_context = TraceContext(
            trace_id=parent_trace_id or trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            tags={
                "method": request.method,
                "url": str(request.url),
                "user_agent": request.headers.get("User-Agent", ""),
                "remote_addr": request.client.host if request.client else "unknown"
            }
        )
        
        self.active_traces[span_id] = trace_context
        
        return trace_context
    
    def end_trace(self, span_id: str, status_code: int = None):
        """End tracing a request"""
        if span_id in self.active_traces:
            trace_context = self.active_traces[span_id]
            
            # Calculate duration
            duration = time.time() - trace_context.start_time
            
            # Add completion info
            if status_code:
                trace_context.tags["status_code"] = str(status_code)
            
            trace_context.tags["duration_ms"] = f"{duration * 1000:.2f}"
            
            # Log trace completion
            structured_logger.info("Request completed", **{
                "trace_id": trace_context.trace_id,
                "span_id": trace_context.span_id,
                "duration_ms": duration * 1000,
                "status_code": status_code,
                "tags": trace_context.tags
            })
            
            # Remove from active traces
            del self.active_traces[span_id]
    
    def add_span_tag(self, span_id: str, key: str, value: str):
        """Add tag to active span"""
        if span_id in self.active_traces:
            self.active_traces[span_id].tags[key] = value
    
    def create_child_span(self, parent_span_id: str, operation_name: str) -> str:
        """Create child span"""
        if parent_span_id not in self.active_traces:
            return None
        
        parent_trace = self.active_traces[parent_span_id]
        
        child_span_id = str(uuid.uuid4())[:8]
        child_trace = TraceContext(
            trace_id=parent_trace.trace_id,
            span_id=child_span_id,
            parent_span_id=parent_span_id,
            tags={
                "operation": operation_name,
                "parent_operation": parent_trace.tags.get("operation", "unknown")
            }
        )
        
        self.active_traces[child_span_id] = child_trace
        
        return child_span_id

class MetricsCollector:
    """System and application metrics collector"""
    
    def __init__(self):
        self.collection_interval = 30  # seconds
        self.running = False
    
    def collect_system_metrics(self):
        """Collect system metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            SYSTEM_CPU_USAGE.set(cpu_percent)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            SYSTEM_MEMORY_USAGE.set(memory.percent)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            SYSTEM_DISK_USAGE.set(disk_percent)
            
            # Network metrics
            network = psutil.net_io_counters()
            
            structured_logger.info("System metrics collected", **{
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk_percent,
                "network_bytes_sent": network.bytes_sent,
                "network_bytes_recv": network.bytes_recv
            })
            
        except Exception as e:
            structured_logger.error("Failed to collect system metrics", error=str(e))
            ERROR_COUNT.labels(error_type="metrics_collection", component="system").inc()
    
    def collect_application_metrics(self):
        """Collect application-specific metrics"""
        try:
            # Database connections
            from app.core.database import engine
            pool = engine.pool
            
            if hasattr(pool, 'size'):
                active_connections = pool.size() - pool.checkedout()
                DATABASE_CONNECTIONS.set(active_connections)
            
            # Cache metrics
            from app.core.redis_cache import cache
            cache_stats = cache.get_stats()
            
            if cache_stats.get("hit_rate_percent"):
                CACHE_HIT_RATE.labels(cache_type="redis").set(cache_stats["hit_rate_percent"])
            
            structured_logger.info("Application metrics collected", **{
                "database_connections": active_connections if 'active_connections' in locals() else 0,
                "cache_hit_rate": cache_stats.get("hit_rate_percent", 0),
                "cache_total_requests": cache_stats.get("total_requests", 0)
            })
            
        except Exception as e:
            structured_logger.error("Failed to collect application metrics", error=str(e))
            ERROR_COUNT.labels(error_type="metrics_collection", component="application").inc()
    
    async def start_collection(self):
        """Start background metrics collection"""
        self.running = True
        
        while self.running:
            try:
                self.collect_system_metrics()
                self.collect_application_metrics()
                
                await asyncio.sleep(self.collection_interval)
                
            except Exception as e:
                structured_logger.error("Metrics collection error", error=str(e))
                await asyncio.sleep(5)  # Short retry delay
    
    def stop_collection(self):
        """Stop metrics collection"""
        self.running = False

# Global instances
structured_logger = StructuredLogger("observability")
request_tracer = RequestTracer()
metrics_collector = MetricsCollector()

# Middleware functions
def observability_middleware(request: Request, call_next):
    """Main observability middleware"""
    start_time = time.time()
    
    # Start tracing
    trace_context = request_tracer.start_trace(request)
    
    # Add trace ID to request state
    request.state.trace_id = trace_context.trace_id
    request.state.span_id = trace_context.span_id
    
    try:
        # Process request
        response = call_next(request)
        
        # Record metrics
        duration = time.time() - start_time
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code
        ).inc()
        
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        # End tracing
        request_tracer.end_trace(trace_context.span_id, response.status_code)
        
        # Add tracing headers to response
        response.headers["X-Trace-ID"] = trace_context.trace_id
        response.headers["X-Span-ID"] = trace_context.span_id
        
        return response
        
    except Exception as e:
        # Record error metrics
        duration = time.time() - start_time
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=500
        ).inc()
        
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        ERROR_COUNT.labels(
            error_type=type(e).__name__,
            component="api"
        ).inc()
        
        # End tracing with error
        request_tracer.end_trace(trace_context.span_id, 500)
        
        structured_logger.error("Request failed", **{
            "trace_id": trace_context.trace_id,
            "span_id": trace_context.span_id,
            "method": request.method,
            "url": str(request.url),
            "error": str(e),
            "duration_ms": duration * 1000
        })
        
        raise

def trace_operation(operation_name: str):
    """Decorator for tracing operations"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Try to get trace context from request
            span_id = None
            if args and hasattr(args[0], 'request'):
                span_id = getattr(args[0].request.state, 'span_id', None)
            
            if span_id:
                # Create child span
                child_span_id = request_tracer.create_child_span(span_id, operation_name)
                
                try:
                    start_time = time.time()
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    structured_logger.info("Operation completed", **{
                        "operation": operation_name,
                        "trace_id": request_tracer.active_traces[child_span_id].trace_id,
                        "span_id": child_span_id,
                        "duration_ms": duration * 1000,
                        "success": True
                    })
                    
                    return result
                    
                except Exception as e:
                    duration = time.time() - start_time
                    
                    structured_logger.error("Operation failed", **{
                        "operation": operation_name,
                        "trace_id": request_tracer.active_traces[child_span_id].trace_id,
                        "span_id": child_span_id,
                        "duration_ms": duration * 1000,
                        "error": str(e),
                        "success": False
                    })
                    
                    raise
                
                finally:
                    request_tracer.end_trace(child_span_id)
            else:
                # No tracing context available
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator

def log_ml_prediction(model_type: str, prediction_type: str, duration: float, success: bool = True):
    """Log ML prediction metrics"""
    ML_PREDICTION_COUNT.labels(
        model_type=model_type,
        prediction_type=prediction_type
    ).inc()
    
    ML_PREDICTION_DURATION.labels(model_type=model_type).observe(duration)
    
    if not success:
        ERROR_COUNT.labels(
            error_type="prediction_failed",
            component="ml"
        ).inc()

def log_cache_operation(cache_type: str, operation: str, hit: bool = False):
    """Log cache operation metrics"""
    structured_logger.debug("Cache operation", **{
        "cache_type": cache_type,
        "operation": operation,
        "hit": hit
    })

def get_prometheus_metrics() -> str:
    """Get Prometheus metrics"""
    return generate_latest()

def get_tracing_info(request: Request) -> Dict[str, Any]:
    """Get current tracing information"""
    trace_id = getattr(request.state, 'trace_id', None)
    span_id = getattr(request.state, 'span_id', None)
    
    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "active_traces": len(request_tracer.active_traces)
    }

class HealthCheckMetrics:
    """Health check with metrics"""
    
    @staticmethod
    def check_system_health() -> Dict[str, Any]:
        """Check system health"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            health_status = "healthy"
            issues = []
            
            if cpu_percent > 90:
                health_status = "degraded"
                issues.append(f"High CPU usage: {cpu_percent}%")
            
            if memory.percent > 90:
                health_status = "degraded"
                issues.append(f"High memory usage: {memory.percent}%")
            
            if (disk.used / disk.total) * 100 > 95:
                health_status = "unhealthy"
                issues.append(f"Critical disk usage: {(disk.used / disk.total) * 100:.1f}%")
            
            return {
                "status": health_status,
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": (disk.used / disk.total) * 100,
                "issues": issues,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    def check_application_health() -> Dict[str, Any]:
        """Check application health"""
        health_info = {
            "status": "healthy",
            "components": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Check database
        try:
            from app.core.database import test_connection
            db_healthy = test_connection()
            health_info["components"]["database"] = {
                "status": "healthy" if db_healthy else "unhealthy",
                "response_time_ms": 0  # Could be measured
            }
        except Exception as e:
            health_info["components"]["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_info["status"] = "degraded"
        
        # Check cache
        try:
            from app.core.redis_cache import cache
            cache_healthy = cache.health_check()
            cache_stats = cache.get_stats()
            
            health_info["components"]["cache"] = {
                "status": "healthy" if cache_healthy else "unhealthy",
                "hit_rate_percent": cache_stats.get("hit_rate_percent", 0),
                "redis_connected": cache_stats.get("redis_connected", False)
            }
        except Exception as e:
            health_info["components"]["cache"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_info["status"] = "degraded"
        
        # Check ML models
        try:
            from app.ml.enhanced_predictor import enhanced_predictor
            model_info = enhanced_predictor.get_model_info()
            trained_models = sum(1 for info in model_info.values() if info.get('status') != 'not_trained')
            
            health_info["components"]["ml"] = {
                "status": "healthy" if trained_models > 0 else "degraded",
                "trained_models": trained_models,
                "total_models": len(model_info)
            }
        except Exception as e:
            health_info["components"]["ml"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_info["status"] = "degraded"
        
        return health_info
