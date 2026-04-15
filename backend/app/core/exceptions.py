"""
Custom exceptions for the AI Database Performance Optimizer
"""

class DatabaseOptimizerException(Exception):
    """Base exception for all database optimizer errors"""
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

class DatabaseConnectionError(DatabaseOptimizerException):
    """Raised when database connection fails"""
    def __init__(self, message: str, db_type: str = None, port: int = None, config_key: str = None, config_value: str = None):
        super().__init__(message, "DB_CONNECTION_ERROR")
        self.db_type = db_type
        self.port = port
        self.config_key = config_key
        self.config_value = config_value

class DatabaseQueryError(DatabaseOptimizerException):
    """Raised when database query fails"""
    def __init__(self, message: str, query: str = None, error: str = None):
        super().__init__(message, "DB_QUERY_ERROR")
        self.query = query
        self.original_error = error

class ConfigurationError(DatabaseOptimizerException):
    """Raised when configuration is invalid or missing"""
    def __init__(self, message: str, config_key: str = None, config_value: str = None):
        super().__init__(message, "CONFIG_ERROR")
        self.config_key = config_key
        self.config_value = config_value

class ValidationError(DatabaseOptimizerException):
    """Raised when input validation fails"""
    def __init__(self, message: str, field: str = None, value: str = None):
        super().__init__(message, "VALIDATION_ERROR")
        self.field = field
        self.value = value

class InsufficientDataError(DatabaseOptimizerException):
    """Raised when there's insufficient data for operations"""
    def __init__(self, message: str, required: int = None, available: int = None):
        super().__init__(message, "INSUFFICIENT_DATA")
        self.required = required
        self.available = available

class ModelTrainingError(DatabaseOptimizerException):
    """Raised when ML model training fails"""
    def __init__(self, message: str, model_type: str = None, resource: str = None):
        super().__init__(message, "MODEL_TRAINING_ERROR")
        self.model_type = model_type
        self.resource = resource

class PredictionError(DatabaseOptimizerException):
    """Raised when ML prediction fails"""
    def __init__(self, message: str, resource: str = None, model_available: bool = None):
        super().__init__(message, "PREDICTION_ERROR")
        self.resource = resource
        self.model_available = model_available

class QueryAnalysisError(DatabaseOptimizerException):
    """Raised when query analysis fails"""
    def __init__(self, message: str, query: str = None, analysis_type: str = None):
        super().__init__(message, "QUERY_ANALYSIS_ERROR")
        self.query = query
        self.analysis_type = analysis_type

class IndexRecommendationError(DatabaseOptimizerException):
    """Raised when index recommendation fails"""
    def __init__(self, message: str, table: str = None, analysis_failed: bool = None):
        super().__init__(message, "INDEX_RECOMMENDATION_ERROR")
        self.table = table
        self.analysis_failed = analysis_failed

class RecommendationEngineError(DatabaseOptimizerException):
    """Raised when recommendation engine operations fail"""
    def __init__(self, message: str, operation: str = None, table: str = None):
        super().__init__(message, "RECOMMENDATION_ENGINE_ERROR")
        self.operation = operation
        self.table = table

class MonitoringError(DatabaseOptimizerException):
    """Raised when monitoring operations fail"""
    def __init__(self, message: str, metric_type: str = None, timestamp: str = None):
        super().__init__(message, "MONITORING_ERROR")
        self.metric_type = metric_type
        self.timestamp = timestamp

class ReportingError(DatabaseOptimizerException):
    """Raised when reporting operations fail"""
    def __init__(self, message: str, report_type: str = None, date_range: str = None):
        super().__init__(message, "REPORTING_ERROR")
        self.report_type = report_type
        self.date_range = date_range

class ExternalServiceError(DatabaseOptimizerException):
    """Raised when external service calls fail"""
    def __init__(self, message: str, service: str = None, endpoint: str = None):
        super().__init__(message, "EXTERNAL_SERVICE_ERROR")
        self.service = service
        self.endpoint = endpoint
