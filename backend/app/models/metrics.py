from sqlalchemy import Column, Integer, Float, DateTime, Text, String, Boolean
from sqlalchemy.sql import func
from ..core.database import Base

class DatabaseMetrics(Base):
    __tablename__ = "database_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    cpu_usage = Column(Float)
    memory_usage = Column(Float)
    disk_usage = Column(Float)
    connections = Column(Integer)
    queries_per_second = Column(Float)
    slow_queries = Column(Integer)
    
    def __repr__(self):
        return f"<DatabaseMetrics(timestamp={self.timestamp}, cpu={self.cpu_usage}%)"

class QueryLog(Base):
    __tablename__ = "query_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    query_text = Column(Text)
    execution_time = Column(Float)  # in milliseconds
    rows_examined = Column(Integer)
    rows_returned = Column(Integer)
    database_name = Column(String(100))
    user = Column(String(50))
    host = Column(String(100))  # This is a data field, not a credential
    is_slow = Column(Boolean, default=False)
    
    def __repr__(self):
        return f"<QueryLog(execution_time={self.execution_time}ms, is_slow={self.is_slow})>"

class IndexRecommendation(Base):
    __tablename__ = "index_recommendations"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    table_name = Column(String(100))
    column_names = Column(String(500))
    index_type = Column(String(50))
    estimated_improvement = Column(Float)
    query_pattern = Column(Text)
    implemented = Column(Boolean, default=False)
    
    def __repr__(self):
        return f"<IndexRecommendation(table={self.table_name}, improvement={self.estimated_improvement}%)"

class PerformancePrediction(Base):
    __tablename__ = "performance_predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    prediction_horizon = Column(Integer)  # hours ahead
    predicted_cpu = Column(Float)
    predicted_memory = Column(Float)
    predicted_disk = Column(Float)
    confidence_score = Column(Float)
    model_version = Column(String(50))
    
    def __repr__(self):
        return f"<PerformancePrediction(horizon={self.prediction_horizon}h, confidence={self.confidence_score})>"
