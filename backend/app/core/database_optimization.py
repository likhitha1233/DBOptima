"""
FAANG-level Database Performance Optimization
Indexing strategy, query optimization, execution time logging
"""

import logging
import time
from typing import Dict, Any, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class QueryPerformanceMetrics:
    """Query performance tracking"""
    query: str
    execution_time: float
    rows_affected: int
    timestamp: datetime
    cache_hit: bool = False

class DatabaseOptimizer:
    """Production-grade database optimization"""
    
    def __init__(self, engine: Engine):
        self.engine = engine
        self.query_log: List[QueryPerformanceMetrics] = []
        self.slow_query_threshold = 1.0  # seconds
        self.max_log_entries = 1000
    
    def create_optimal_indexes(self, db: Session) -> Dict[str, bool]:
        """Create optimal indexes for performance"""
        index_results = {}
        
        try:
            # Indexes for database_metrics table
            index_results["metrics_timestamp"] = self._create_index(
                db, "database_metrics", "timestamp", "idx_metrics_timestamp"
            )
            
            index_results["metrics_timestamp_cpu"] = self._create_composite_index(
                db, "database_metrics", ["timestamp", "cpu_usage"], "idx_metrics_timestamp_cpu"
            )
            
            index_results["metrics_timestamp_memory"] = self._create_composite_index(
                db, "database_metrics", ["timestamp", "memory_usage"], "idx_metrics_timestamp_memory"
            )
            
            # Indexes for query_logs table
            index_results["query_logs_timestamp"] = self._create_index(
                db, "query_logs", "timestamp", "idx_query_logs_timestamp"
            )
            
            index_results["query_logs_execution_time"] = self._create_index(
                db, "query_logs", "execution_time", "idx_query_logs_execution_time"
            )
            
            index_results["query_logs_database_timestamp"] = self._create_composite_index(
                db, "query_logs", ["database_name", "timestamp"], "idx_query_logs_db_timestamp"
            )
            
            # Indexes for performance_predictions table
            index_results["predictions_timestamp"] = self._create_index(
                db, "performance_predictions", "timestamp", "idx_predictions_timestamp"
            )
            
            index_results["predictions_resource_timestamp"] = self._create_composite_index(
                db, "performance_predictions", ["resource_type", "timestamp"], "idx_predictions_resource_timestamp"
            )
            
            # Indexes for index_recommendations table
            index_results["recommendations_timestamp"] = self._create_index(
                db, "index_recommendations", "timestamp", "idx_recommendations_timestamp"
            )
            
            index_results["recommendations_priority_timestamp"] = self._create_composite_index(
                db, "index_recommendations", ["priority", "timestamp"], "idx_recommendations_priority_timestamp"
            )
            
            # Indexes for model_registry table
            index_results["model_registry_name_version"] = self._create_composite_index(
                db, "model_registry", ["model_name", "version"], "idx_model_registry_name_version"
            )
            
            index_results["model_registry_created_at"] = self._create_index(
                db, "model_registry", "created_at", "idx_model_registry_created_at"
            )
            
            logger.info(f"Database indexes created: {sum(index_results.values())}/{len(index_results)} successful")
            
        except Exception as e:
            logger.error(f"Index creation failed: {e}")
            index_results = {k: False for k in index_results.keys()}
        
        return index_results
    
    def _create_index(self, db: Session, table: str, column: str, index_name: str) -> bool:
        """Create single column index"""
        try:
            sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column})"
            db.execute(text(sql))
            db.commit()
            logger.debug(f"Created index: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create index {index_name}: {e}")
            return False
    
    def _create_composite_index(self, db: Session, table: str, columns: List[str], index_name: str) -> bool:
        """Create composite index"""
        try:
            columns_str = ", ".join(columns)
            sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({columns_str})"
            db.execute(text(sql))
            db.commit()
            logger.debug(f"Created composite index: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create composite index {index_name}: {e}")
            return False
    
    def analyze_query_performance(self, db: Session, query: str, params: Dict[str, Any] = None) -> QueryPerformanceMetrics:
        """Analyze query performance with execution time logging"""
        start_time = time.time()
        
        try:
            # Execute query with EXPLAIN ANALYZE for performance analysis
            explain_query = f"EXPLAIN ANALYZE {query}"
            
            explain_start = time.time()
            result = db.execute(text(explain_query), params or {})
            explain_time = time.time() - explain_start
            
            # Execute actual query
            actual_start = time.time()
            actual_result = db.execute(text(query), params or {})
            rows_affected = actual_result.rowcount
            actual_time = time.time() - actual_start
            
            total_time = time.time() - start_time
            
            # Log performance metrics
            metrics = QueryPerformanceMetrics(
                query=query,
                execution_time=total_time,
                rows_affected=rows_affected,
                timestamp=datetime.now(),
                cache_hit=False
            )
            
            self._log_query_performance(metrics)
            
            return metrics
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Query performance analysis failed: {e}")
            
            # Log failed query
            metrics = QueryPerformanceMetrics(
                query=query,
                execution_time=execution_time,
                rows_affected=0,
                timestamp=datetime.now(),
                cache_hit=False
            )
            
            self._log_query_performance(metrics)
            raise
    
    def _log_query_performance(self, metrics: QueryPerformanceMetrics):
        """Log query performance metrics"""
        self.query_log.append(metrics)
        
        # Keep log size manageable
        if len(self.query_log) > self.max_log_entries:
            self.query_log = self.query_log[-self.max_log_entries:]
        
        # Log slow queries
        if metrics.execution_time > self.slow_query_threshold:
            logger.warning(
                f"Slow query detected: {metrics.execution_time:.3f}s, "
                f"rows: {metrics.rows_affected}, query: {metrics.query[:100]}..."
            )
        
        # Log performance metrics periodically
        if len(self.query_log) % 100 == 0:
            avg_time = sum(q.execution_time for q in self.query_log[-100:]) / 100
            logger.info(f"Average query time (last 100): {avg_time:.3f}s")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""
        if not self.query_log:
            return {"message": "No query performance data available"}
        
        recent_queries = self.query_log[-100:]  # Last 100 queries
        
        execution_times = [q.execution_time for q in recent_queries]
        slow_queries = [q for q in recent_queries if q.execution_time > self.slow_query_threshold]
        
        return {
            "total_queries": len(self.query_log),
            "recent_queries": len(recent_queries),
            "avg_execution_time": sum(execution_times) / len(execution_times),
            "min_execution_time": min(execution_times),
            "max_execution_time": max(execution_times),
            "slow_query_count": len(slow_queries),
            "slow_query_percentage": (len(slow_queries) / len(recent_queries)) * 100,
            "slow_query_threshold": self.slow_query_threshold,
            "total_rows_affected": sum(q.rows_affected for q in recent_queries),
            "oldest_query_time": self.query_log[0].timestamp.isoformat(),
            "newest_query_time": self.query_log[-1].timestamp.isoformat()
        }
    
    def optimize_slow_queries(self, db: Session) -> List[str]:
        """Identify and suggest optimizations for slow queries"""
        optimizations = []
        
        slow_queries = [q for q in self.query_log if q.execution_time > self.slow_query_threshold]
        
        for query in slow_queries[-10:]:  # Last 10 slow queries
            suggestions = self._analyze_query_for_optimization(query.query)
            if suggestions:
                optimizations.append({
                    "query": query.query[:100] + "...",
                    "execution_time": query.execution_time,
                    "suggestions": suggestions
                })
        
        return optimizations
    
    def _analyze_query_for_optimization(self, query: str) -> List[str]:
        """Analyze a query and suggest optimizations"""
        suggestions = []
        query_lower = query.lower()
        
        # Check for missing WHERE clauses
        if "select" in query_lower and "where" not in query_lower:
            suggestions.append("Consider adding WHERE clause to limit results")
        
        # Check for SELECT *
        if "select *" in query_lower:
            suggestions.append("Replace SELECT * with specific columns")
        
        # Check for missing indexes (simplified)
        if "order by" in query_lower and "limit" not in query_lower:
            suggestions.append("Consider adding LIMIT to ORDER BY queries")
        
        # Check for subqueries that could be JOINs
        if query_lower.count("select") > 1:
            suggestions.append("Consider converting subqueries to JOINs")
        
        # Check for LIKE without wildcards
        if "like" in query_lower and "%" not in query:
            suggestions.append("LIKE without wildcards could use = instead")
        
        return suggestions
    
    @contextmanager
    def query_timing_context(self, query_name: str = "unnamed"):
        """Context manager for timing query execution"""
        start_time = time.time()
        try:
            yield
        finally:
            execution_time = time.time() - start_time
            
            metrics = QueryPerformanceMetrics(
                query=query_name,
                execution_time=execution_time,
                rows_affected=0,
                timestamp=datetime.now(),
                cache_hit=False
            )
            
            self._log_query_performance(metrics)
    
    def cleanup_old_performance_logs(self, days_to_keep: int = 7):
        """Clean up old performance logs"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        original_count = len(self.query_log)
        self.query_log = [q for q in self.query_log if q.timestamp > cutoff_date]
        
        cleaned_count = original_count - len(self.query_log)
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old performance log entries")

class QueryOptimizer:
    """Query optimization utilities"""
    
    @staticmethod
    def optimize_timestamp_range_query(base_table: str, timestamp_column: str = "timestamp", 
                                     hours_back: int = 24) -> tuple[str, Dict[str, Any]]:
        """Optimize timestamp range queries"""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        # Optimized query with proper index usage
        query = f"""
        SELECT * FROM {base_table}
        WHERE {timestamp_column} > :cutoff_time
        ORDER BY {timestamp_column} DESC
        LIMIT 1000
        """
        
        params = {"cutoff_time": cutoff_time}
        
        return query, params
    
    @staticmethod
    def optimize_aggregation_query(table: str, group_columns: List[str], 
                                  agg_columns: Dict[str, str], 
                                  timestamp_column: str = "timestamp",
                                  hours_back: int = 24) -> tuple[str, Dict[str, Any]]:
        """Optimize aggregation queries"""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        # Build SELECT clause with aggregations
        select_parts = []
        for col in group_columns:
            select_parts.append(col)
        
        for col, agg_func in agg_columns.items():
            select_parts.append(f"{agg_func}({col}) as {col}_{agg_func.lower()}")
        
        # Build WHERE clause
        where_clause = f"WHERE {timestamp_column} > :cutoff_time"
        
        # Build GROUP BY clause
        group_by_clause = f"GROUP BY {', '.join(group_columns)}"
        
        query = f"""
        SELECT {', '.join(select_parts)}
        FROM {table}
        {where_clause}
        {group_by_clause}
        ORDER BY {timestamp_column} DESC
        LIMIT 500
        """
        
        params = {"cutoff_time": cutoff_time}
        
        return query, params
    
    @staticmethod
    def optimize_pagination_query(table: str, order_column: str = "timestamp",
                                 limit: int = 100, offset: int = 0) -> tuple[str, Dict[str, Any]]:
        """Optimize pagination queries"""
        
        query = f"""
        SELECT * FROM {table}
        ORDER BY {order_column} DESC
        LIMIT :limit OFFSET :offset
        """
        
        params = {"limit": limit, "offset": offset}
        
        return query, params

# Global database optimizer instance
db_optimizer: Optional[DatabaseOptimizer] = None

def initialize_database_optimizer(engine: Engine) -> DatabaseOptimizer:
    """Initialize the database optimizer"""
    global db_optimizer
    db_optimizer = DatabaseOptimizer(engine)
    return db_optimizer

def get_database_optimizer() -> Optional[DatabaseOptimizer]:
    """Get the database optimizer instance"""
    return db_optimizer
