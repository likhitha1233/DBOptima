"""
FAANG-level Centralized Error Tracking
Categorize errors (DB, ML, API) with comprehensive logging
"""

import json
import traceback
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
from functools import wraps
from fastapi import Request
import hashlib

class ErrorCategory(Enum):
    """Error categories for classification"""
    DATABASE = "database"
    ML = "ml"
    API = "api"
    CACHE = "cache"
    SECURITY = "security"
    SYSTEM = "system"
    NETWORK = "network"
    VALIDATION = "validation"
    UNKNOWN = "unknown"

class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ErrorEvent:
    """Structured error event"""
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    exception_type: str
    stack_trace: str
    context: Dict[str, Any]
    timestamp: datetime
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    component: Optional[str] = None
    resolved: bool = False
    resolution_notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data["category"] = self.category.value
        data["severity"] = self.severity.value
        data["timestamp"] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ErrorEvent':
        """Create from dictionary"""
        data["category"] = ErrorCategory(data["category"])
        data["severity"] = ErrorSeverity(data["severity"])
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)

class ErrorClassifier:
    """Automatic error classification system"""
    
    def __init__(self):
        self.classification_rules = {
            ErrorCategory.DATABASE: [
                "sqlalchemy", "database", "connection", "timeout", "constraint",
                "integrity", "foreignkey", "operationalerror", "programmingerror"
            ],
            ErrorCategory.ML: [
                "sklearn", "numpy", "pandas", "prediction", "model", "training",
                "feature", "drift", "validation", "cross_validation"
            ],
            ErrorCategory.API: [
                "fastapi", "http", "request", "response", "endpoint", "validation",
                "serialization", "pydantic"
            ],
            ErrorCategory.CACHE: [
                "redis", "cache", "memcached", "timeout", "connection", "key"
            ],
            ErrorCategory.SECURITY: [
                "authentication", "authorization", "jwt", "token", "api_key",
                "forbidden", "unauthorized", "csrf"
            ],
            ErrorCategory.SYSTEM: [
                "os", "filesystem", "disk", "memory", "cpu", "process", "thread"
            ],
            ErrorCategory.NETWORK: [
                "socket", "connection", "timeout", "dns", "http", "urllib"
            ],
            ErrorCategory.VALIDATION: [
                "validate", "invalid", "missing", "required", "format", "range"
            ]
        }
    
    def classify_error(self, exception: Exception, context: Dict[str, Any] = None) -> ErrorCategory:
        """Classify error based on exception and context"""
        exception_str = str(exception).lower()
        exception_type = type(exception).__name__.lower()
        stack_trace = traceback.format_exc().lower()
        
        context_str = ""
        if context:
            context_str = json.dumps(context, default=str).lower()
        
        # Combine all text for analysis
        combined_text = f"{exception_str} {exception_type} {stack_trace} {context_str}"
        
        # Score each category
        category_scores = {}
        for category, keywords in self.classification_rules.items():
            score = 0
            for keyword in keywords:
                if keyword in combined_text:
                    score += 1
            category_scores[category] = score
        
        # Find best match
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            if category_scores[best_category] > 0:
                return best_category
        
        return ErrorCategory.UNKNOWN
    
    def determine_severity(self, exception: Exception, category: ErrorCategory) -> ErrorSeverity:
        """Determine error severity"""
        exception_type = type(exception).__name__
        
        # Critical errors
        if exception_type in ["MemoryError", "SystemExit", "KeyboardInterrupt"]:
            return ErrorSeverity.CRITICAL
        
        # High severity by category
        if category in [ErrorCategory.DATABASE, ErrorCategory.SECURITY]:
            return ErrorSeverity.HIGH
        
        # Medium severity
        if category in [ErrorCategory.ML, ErrorCategory.CACHE, ErrorCategory.SYSTEM]:
            return ErrorSeverity.MEDIUM
        
        # Low severity
        if category in [ErrorCategory.API, ErrorCategory.VALIDATION, ErrorCategory.NETWORK]:
            return ErrorSeverity.LOW
        
        return ErrorSeverity.MEDIUM

class ErrorTracker:
    """Centralized error tracking system"""
    
    def __init__(self, error_log_path: str = "logs/errors"):
        self.error_log_path = Path(error_log_path)
        self.error_log_path.mkdir(parents=True, exist_ok=True)
        self.classifier = ErrorClassifier()
        self.error_events: List[ErrorEvent] = []
        self.error_patterns: Dict[str, List[ErrorEvent]] = {}
        self.max_events = 10000  # Maximum events to keep in memory
        
    def track_error(self, exception: Exception, context: Dict[str, Any] = None,
                   request: Request = None, severity: ErrorSeverity = None) -> str:
        """Track an error event"""
        
        # Generate error ID
        error_hash = self._generate_error_hash(exception, context)
        error_id = f"ERR_{error_hash[:16]}_{int(datetime.now().timestamp())}"
        
        # Classify error
        category = self.classifier.classify_error(exception, context)
        
        # Determine severity
        if severity is None:
            severity = self.classifier.determine_severity(exception, category)
        
        # Create error event
        error_event = ErrorEvent(
            error_id=error_id,
            category=category,
            severity=severity,
            message=str(exception),
            exception_type=type(exception).__name__,
            stack_trace=traceback.format_exc(),
            context=context or {},
            timestamp=datetime.now(),
            request_id=getattr(request.state, 'trace_id', None) if request else None,
            component=context.get('component') if context else None
        )
        
        # Store error event
        self.error_events.append(error_event)
        
        # Add to error patterns
        pattern_key = f"{category.value}_{type(exception).__name__}"
        if pattern_key not in self.error_patterns:
            self.error_patterns[pattern_key] = []
        self.error_patterns[pattern_key].append(error_event)
        
        # Limit memory usage
        if len(self.error_events) > self.max_events:
            self.error_events = self.error_events[-self.max_events:]
        
        # Save to file
        self._save_error_event(error_event)
        
        # Log error
        self._log_error(error_event)
        
        return error_id
    
    def _generate_error_hash(self, exception: Exception, context: Dict[str, Any] = None) -> str:
        """Generate unique hash for error pattern"""
        error_data = {
            "type": type(exception).__name__,
            "message": str(exception)[:200],  # First 200 chars
            "component": context.get('component') if context else None
        }
        
        error_str = json.dumps(error_data, sort_keys=True, default=str)
        return hashlib.md5(error_str.encode()).hexdigest()
    
    def _save_error_event(self, error_event: ErrorEvent):
        """Save error event to file"""
        try:
            # Save to daily log file
            date_str = error_event.timestamp.strftime("%Y-%m-%d")
            log_file = self.error_log_path / f"errors_{date_str}.json"
            
            # Load existing errors
            errors = []
            if log_file.exists():
                with open(log_file, 'r') as f:
                    try:
                        errors = json.load(f)
                    except json.JSONDecodeError:
                        errors = []
            
            # Add new error
            errors.append(error_event.to_dict())
            
            # Keep only last 1000 errors per day
            if len(errors) > 1000:
                errors = errors[-1000:]
            
            # Save to file
            with open(log_file, 'w') as f:
                json.dump(errors, f, indent=2)
                
        except Exception as e:
            logging.error(f"Failed to save error event: {e}")
    
    def _log_error(self, error_event: ErrorEvent):
        """Log error with structured format"""
        log_data = {
            "error_id": error_event.error_id,
            "category": error_event.category.value,
            "severity": error_event.severity.value,
            "message": error_event.message,
            "exception_type": error_event.exception_type,
            "component": error_event.component,
            "request_id": error_event.request_id
        }
        
        if error_event.severity == ErrorSeverity.CRITICAL:
            logging.critical(f"Critical error: {json.dumps(log_data)}")
        elif error_event.severity == ErrorSeverity.HIGH:
            logging.error(f"High severity error: {json.dumps(log_data)}")
        elif error_event.severity == ErrorSeverity.MEDIUM:
            logging.warning(f"Medium severity error: {json.dumps(log_data)}")
        else:
            logging.info(f"Low severity error: {json.dumps(log_data)}")
    
    def get_error_stats(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get error statistics"""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        recent_errors = [
            error for error in self.error_events 
            if error.timestamp >= cutoff_time
        ]
        
        # Count by category
        category_counts = {}
        severity_counts = {}
        component_counts = {}
        
        for error in recent_errors:
            # Category counts
            cat = error.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1
            
            # Severity counts
            sev = error.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            
            # Component counts
            comp = error.component
            if comp:
                component_counts[comp] = component_counts.get(comp, 0) + 1
        
        # Find most common errors
        error_patterns = {}
        for pattern_key, events in self.error_patterns.items():
            recent_pattern_errors = [
                event for event in events 
                if event.timestamp >= cutoff_time
            ]
            if recent_pattern_errors:
                error_patterns[pattern_key] = len(recent_pattern_errors)
        
        most_common_errors = sorted(
            error_patterns.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]
        
        return {
            "total_errors": len(recent_errors),
            "period_hours": hours_back,
            "category_distribution": category_counts,
            "severity_distribution": severity_counts,
            "component_distribution": component_counts,
            "most_common_errors": most_common_errors,
            "error_rate_per_hour": len(recent_errors) / hours_back
        }
    
    def get_error_trends(self, days_back: int = 7) -> Dict[str, Any]:
        """Get error trends over time"""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        daily_errors = {}
        
        for error in self.error_events:
            if error.timestamp >= cutoff_date:
                date_str = error.timestamp.strftime("%Y-%m-%d")
                if date_str not in daily_errors:
                    daily_errors[date_str] = {"total": 0, "by_category": {}}
                
                daily_errors[date_str]["total"] += 1
                
                cat = error.category.value
                daily_errors[date_str]["by_category"][cat] = \
                    daily_errors[date_str]["by_category"].get(cat, 0) + 1
        
        return {
            "period_days": days_back,
            "daily_errors": daily_errors,
            "trend_direction": self._calculate_trend_direction(daily_errors)
        }
    
    def _calculate_trend_direction(self, daily_errors: Dict[str, Any]) -> str:
        """Calculate error trend direction"""
        if len(daily_errors) < 2:
            return "insufficient_data"
        
        dates = sorted(daily_errors.keys())
        counts = [daily_errors[date]["total"] for date in dates]
        
        # Simple trend calculation
        if len(counts) >= 3:
            recent_avg = sum(counts[-3:]) / 3
            earlier_avg = sum(counts[:3]) / 3
            
            if recent_avg > earlier_avg * 1.2:
                return "increasing"
            elif recent_avg < earlier_avg * 0.8:
                return "decreasing"
            else:
                return "stable"
        
        return "insufficient_data"
    
    def resolve_error(self, error_id: str, resolution_notes: str) -> bool:
        """Mark error as resolved"""
        for error in self.error_events:
            if error.error_id == error_id:
                error.resolved = True
                error.resolution_notes = resolution_notes
                
                # Update in file
                self._update_error_in_file(error)
                
                logging.info(f"Error resolved: {error_id}")
                return True
        
        return False
    
    def _update_error_in_file(self, error_event: ErrorEvent):
        """Update error event in file"""
        try:
            date_str = error_event.timestamp.strftime("%Y-%m-%d")
            log_file = self.error_log_path / f"errors_{date_str}.json"
            
            if log_file.exists():
                with open(log_file, 'r') as f:
                    errors = json.load(f)
                
                # Find and update error
                for i, error_data in enumerate(errors):
                    if error_data.get("error_id") == error_event.error_id:
                        errors[i] = error_event.to_dict()
                        break
                
                # Save updated file
                with open(log_file, 'w') as f:
                    json.dump(errors, f, indent=2)
                    
        except Exception as e:
            logging.error(f"Failed to update error in file: {e}")

# Global error tracker
error_tracker = ErrorTracker()

def track_errors(category: str = None, severity: ErrorSeverity = None):
    """Decorator for automatic error tracking"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Extract context
                context = {
                    "function": func.__name__,
                    "module": func.__module__,
                    "category": category,
                    "component": kwargs.get("component", "unknown")
                }
                
                # Try to get request from args
                request = None
                if args and hasattr(args[0], 'request'):
                    request = args[0].request
                
                # Track error
                error_tracker.track_error(e, context, request, severity)
                
                # Re-raise exception
                raise
        
        return wrapper
    return decorator

def handle_api_error(request: Request, exception: Exception) -> str:
    """Handle API errors with tracking"""
    context = {
        "endpoint": request.url.path,
        "method": request.method,
        "component": "api"
    }
    
    error_id = error_tracker.track_error(exception, context, request)
    
    return error_id

def get_error_summary(hours_back: int = 24) -> Dict[str, Any]:
    """Get error summary for monitoring"""
    return error_tracker.get_error_stats(hours_back)

def get_error_dashboard_data() -> Dict[str, Any]:
    """Get comprehensive error dashboard data"""
    return {
        "stats": error_tracker.get_error_stats(24),
        "trends": error_tracker.get_error_trends(7),
        "recent_errors": [
            error.to_dict() for error in 
            sorted(error_tracker.error_events, key=lambda x: x.timestamp, reverse=True)[:50]
        ]
    }
