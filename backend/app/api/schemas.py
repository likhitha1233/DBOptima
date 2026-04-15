"""
API Request/Response Schemas and Validation
"""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator

class TimeRange(str, Enum):
    """Valid time ranges for queries"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"

class SortOrder(str, Enum):
    """Valid sort orders"""
    ASC = "asc"
    DESC = "desc"

class QueryExplainRequest(BaseModel):
    """Request schema for query explanation"""
    query: str = Field(..., min_length=1, max_length=10000, description="SQL query to explain")
    database: Optional[str] = Field(None, max_length=64, description="Database name")
    
    @field_validator('query')
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError("Query cannot be empty")
        # Basic SQL injection check
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
        query_upper = v.upper()
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                raise ValueError(f"Query contains dangerous keyword: {keyword}")
        return v

class IndexAnalysisRequest(BaseModel):
    """Request schema for index analysis"""
    table_name: str = Field(..., min_length=1, max_length=64, description="Table name to analyze")
    database_name: Optional[str] = Field(None, max_length=64, description="Database name")
    min_queries: int = Field(100, ge=1, le=10000, description="Minimum query count for analysis")
    
    @field_validator('table_name')
    def validate_table_name(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError("Table name can only contain alphanumeric characters, underscores, and hyphens")
        return v

class PredictionRequest(BaseModel):
    """Request schema for custom predictions"""
    hour_of_day: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0-6, 0=Monday)")
    connections: int = Field(..., ge=0, le=10000, description="Number of database connections")
    queries_per_second: int = Field(..., ge=0, le=10000, description="Queries per second")
    slow_queries: int = Field(..., ge=0, le=1000, description="Number of slow queries")
    cpu_lag_1: float = Field(..., ge=0, le=100, description="CPU usage lag 1")
    cpu_lag_2: float = Field(..., ge=0, le=100, description="CPU usage lag 2")
    memory_lag_1: float = Field(..., ge=0, le=100, description="Memory usage lag 1")
    memory_lag_2: float = Field(..., ge=0, le=100, description="Memory usage lag 2")

class MonitoringConfigRequest(BaseModel):
    """Request schema for monitoring configuration"""
    interval_seconds: int = Field(60, ge=10, le=3600, description="Monitoring interval in seconds")
    enable_alerts: bool = Field(True, description="Enable alerts")
    cpu_threshold: float = Field(80.0, ge=0, le=100, description="CPU alert threshold")
    memory_threshold: float = Field(85.0, ge=0, le=100, description="Memory alert threshold")
    disk_threshold: float = Field(90.0, ge=0, le=100, description="Disk alert threshold")

# Response Schemas
class BaseResponse(BaseModel):
    """Base response schema"""
    status: str
    timestamp: datetime = Field(default_factory=datetime.now)

class SuccessResponse(BaseResponse):
    """Success response schema"""
    status: str = "success"

class ErrorResponse(BaseResponse):
    """Error response schema"""
    status: str = "error"
    error: str
    error_type: Optional[str] = None

class MetricsResponse(BaseModel):
    """Metrics response schema"""
    timestamp: datetime
    cpu_usage: float = Field(..., ge=0, le=100)
    memory_usage: float = Field(..., ge=0, le=100)
    disk_usage: float = Field(..., ge=0, le=100)
    connections: int = Field(..., ge=0)
    queries_per_second: float = Field(..., ge=0)
    slow_queries: int = Field(..., ge=0)

class QueryInfo(BaseModel):
    """Query information schema"""
    query_id: Optional[str] = None
    query_text: str
    execution_time: float = Field(..., ge=0)
    rows_examined: int = Field(..., ge=0)
    rows_returned: int = Field(..., ge=0)
    timestamp: datetime
    database: Optional[str] = None

class PredictionResult(BaseModel):
    """Prediction result schema"""
    predicted_usage: float = Field(..., ge=0, le=100)
    confidence: float = Field(..., ge=0, le=1)
    model_type: str
    features_used: List[str]

class IndexRecommendation(BaseModel):
    """Index recommendation schema"""
    table_name: str
    column_name: str
    index_type: str
    estimated_improvement: float = Field(..., ge=0)
    recommendation_score: float = Field(..., ge=0, le=1)
    sql_statement: str

class HealthCheckResponse(BaseModel):
    """Health check response schema"""
    status: str
    timestamp: datetime
    database: Dict[str, Any]
    ml_models: Dict[str, Any]
    monitoring: Dict[str, Any]
    recommendations: Dict[str, Any]

# Validation utility functions
def validate_time_range(hours: int) -> int:
    """Validate time range parameter"""
    if not isinstance(hours, int):
        raise ValueError("Hours must be an integer")
    if hours < 1:
        raise ValueError("Hours must be at least 1")
    if hours > 720:  # Max 30 days
        raise ValueError("Hours cannot exceed 720 (30 days)")
    return hours

def validate_limit(limit: int, default: int = 50, max_limit: int = 1000) -> int:
    """Validate limit parameter"""
    if not isinstance(limit, int):
        raise ValueError("Limit must be an integer")
    if limit < 1:
        raise ValueError("Limit must be at least 1")
    if limit > max_limit:
        raise ValueError(f"Limit cannot exceed {max_limit}")
    return limit

def validate_page(page: int) -> int:
    """Validate page parameter"""
    if not isinstance(page, int):
        raise ValueError("Page must be an integer")
    if page < 1:
        raise ValueError("Page must be at least 1")
    return page

def validate_database_name(db_name: Optional[str]) -> Optional[str]:
    """Validate database name parameter"""
    if db_name is None:
        return None
    
    if not isinstance(db_name, str):
        raise ValueError("Database name must be a string")
    
    if not db_name.strip():
        raise ValueError("Database name cannot be empty")
    
    if len(db_name) > 64:
        raise ValueError("Database name cannot exceed 64 characters")
    
    # Check for valid characters
    if not db_name.replace('_', '').replace('-', '').isalnum():
        raise ValueError("Database name can only contain alphanumeric characters, underscores, and hyphens")
    
    return db_name

def validate_table_name(table_name: str) -> str:
    """Validate table name parameter"""
    if not isinstance(table_name, str):
        raise ValueError("Table name must be a string")
    
    if not table_name.strip():
        raise ValueError("Table name cannot be empty")
    
    if len(table_name) > 64:
        raise ValueError("Table name cannot exceed 64 characters")
    
    # Check for valid characters
    if not table_name.replace('_', '').replace('-', '').isalnum():
        raise ValueError("Table name can only contain alphanumeric characters, underscores, and hyphens")
    
    return table_name

def validate_sort_order(sort_order: Optional[str]) -> Optional[str]:
    """Validate sort order parameter"""
    if sort_order is None:
        return None
    
    if sort_order.lower() not in ['asc', 'desc']:
        raise ValueError("Sort order must be 'asc' or 'desc'")
    
    return sort_order.lower()

def validate_percentage(value: Union[int, float], param_name: str) -> float:
    """Validate percentage values"""
    try:
        float_value = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{param_name} must be a number")
    
    if float_value < 0 or float_value > 100:
        raise ValueError(f"{param_name} must be between 0 and 100")
    
    return float_value

def validate_positive_integer(value: Union[int, str], param_name: str, min_val: int = 0, max_val: Optional[int] = None) -> int:
    """Validate positive integer values"""
    try:
        int_value = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"{param_name} must be an integer")
    
    if int_value < min_val:
        raise ValueError(f"{param_name} must be at least {min_val}")
    
    if max_val is not None and int_value > max_val:
        raise ValueError(f"{param_name} cannot exceed {max_val}")
    
    return int_value

# Custom validation decorators
def validate_query_params(**validators):
    """Decorator to validate query parameters"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Validate each parameter
            for param_name, validator_func in validators.items():
                if param_name in kwargs:
                    try:
                        kwargs[param_name] = validator_func(kwargs[param_name])
                    except ValueError as e:
                        raise HTTPException(status_code=400, detail=str(e))
            return func(*args, **kwargs)
        return wrapper
    return decorator

class ValidationError(Exception):
    """Custom validation error"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)
