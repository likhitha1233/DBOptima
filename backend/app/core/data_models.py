"""
Core data models for the database performance optimizer.
"""

from datetime import datetime

class Status(Enum):
    """Status enumeration"""
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"
    PROCESSING = "processing"

@dataclass
class DataSource:
    """Data source information"""
    name: str
    type: str
    connection_string: str
    status: Status

@dataclass
class DataTransformer:
    """Data transformation utilities"""
    source_type: str
    target_type: str
    transformation_rules: Dict[str, Any]

@dataclass
class Recommendation:
    """Base recommendation structure"""
    type: str
    reason: str
    confidence: float
    priority: str
    timestamp: datetime

@dataclass
class QueryMetrics:
    """Query performance metrics"""
    query_text: str
    execution_time: float
    rows_examined: int
    rows_returned: int
    timestamp: datetime
    database_name: str

@dataclass
class SystemMetrics:
    """System performance metrics"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    connections: int
    queries_per_second: float
    slow_queries: int
    timestamp: datetime

@dataclass
class MLPrediction:
    """Machine learning prediction result"""
    resource_type: str
    predicted_value: float
    confidence: float
    model_used: str
    timestamp: datetime
    features_used: List[str]
