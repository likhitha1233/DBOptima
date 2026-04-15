"""
FAANG-level Safe Query Builder
Eliminates ALL dynamic SQL risks with strict whitelist validation
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SafeQueryBuilder:
    """SQL injection-proof query builder with whitelist validation"""
    
    # STRICT WHITELISTS - Only allow these exact identifiers
    ALLOWED_TABLES = {
        'database_metrics',
        'query_logs', 
        'index_recommendations',
        'performance_predictions',
        'model_registry',
        'anomaly_logs'
    }
    
    ALLOWED_COLUMNS = {
        # database_metrics
        'id', 'timestamp', 'cpu_usage', 'memory_usage', 'disk_usage',
        'connections', 'queries_per_second', 'slow_queries',
        
        # query_logs
        'id', 'timestamp', 'query_text', 'execution_time', 'rows_examined',
        'rows_returned', 'database_name', 'user', 'host',
        
        # index_recommendations
        'id', 'timestamp', 'table_name', 'index_name', 'recommendation_type',
        'priority', 'confidence', 'sql_statement',
        
        # performance_predictions
        'id', 'timestamp', 'resource_type', 'predicted_usage', 'confidence',
        'trend', 'model_version', 'feature_importance',
        
        # model_registry
        'id', 'model_name', 'version', 'created_at', 'performance_metrics',
        'training_samples', 'model_path',
        
        # anomaly_logs
        'id', 'timestamp', 'anomaly_type', 'severity', 'description',
        'metrics_data', 'detection_method'
    }
    
    # Allowed aggregate functions
    ALLOWED_AGGREGATES = {
        'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'STDDEV', 'VARIANCE'
    }
    
    # Allowed comparison operators
    ALLOWED_OPERATORS = {
        '=', '!=', '<', '>', '<=', '>=', 'LIKE', 'ILIKE', 'IN', 'NOT IN'
    }
    
    def __init__(self):
        self.query_cache = {}
    
    def validate_table_name(self, table_name: str) -> str:
        """Validate table name against strict whitelist"""
        if not table_name or table_name not in self.ALLOWED_TABLES:
            raise ValueError(f"Table '{table_name}' not in allowed tables: {self.ALLOWED_TABLES}")
        return table_name
    
    def validate_column_name(self, column_name: str) -> str:
        """Validate column name against strict whitelist"""
        if not column_name or column_name not in self.ALLOWED_COLUMNS:
            raise ValueError(f"Column '{column_name}' not in allowed columns: {self.ALLOWED_COLUMNS}")
        return column_name
    
    def validate_aggregate(self, aggregate: str) -> str:
        """Validate aggregate function"""
        if not aggregate or aggregate.upper() not in self.ALLOWED_AGGREGATES:
            raise ValueError(f"Aggregate '{aggregate}' not allowed: {self.ALLOWED_AGGREGATES}")
        return aggregate.upper()
    
    def validate_operator(self, operator: str) -> str:
        """Validate comparison operator"""
        if not operator or operator.upper() not in self.ALLOWED_OPERATORS:
            raise ValueError(f"Operator '{operator}' not allowed: {self.ALLOWED_OPERATORS}")
        return operator.upper()
    
    def validate_order_by(self, order_by: str) -> str:
        """Validate ORDER BY clause - only whitelist columns allowed"""
        if not order_by:
            return "timestamp DESC"
        
        # Split by comma for multiple columns
        parts = order_by.split(',')
        validated_parts = []
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Check for direction
            tokens = part.split()
            if len(tokens) > 2:
                raise ValueError(f"Invalid ORDER BY part: {part}")
            
            column = tokens[0]
            direction = tokens[1].upper() if len(tokens) == 2 else "DESC"
            
            # Validate column
            self.validate_column_name(column)
            
            # Validate direction
            if direction not in ["ASC", "DESC"]:
                raise ValueError(f"Invalid sort direction: {direction}")
            
            validated_parts.append(f"{column} {direction}")
        
        return ", ".join(validated_parts)
    
    def build_safe_select(self, 
                          table: str,
                          columns: Optional[List[str]] = None,
                          where_conditions: Optional[Dict[str, Any]] = None,
                          order_by: Optional[str] = None,
                          limit: Optional[int] = None,
                          offset: Optional[int] = None) -> Tuple[str, Dict[str, Any]]:
        """Build completely safe SELECT query"""
        
        # Validate table
        validated_table = self.validate_table_name(table)
        
        # Validate and build columns
        if columns is None:
            select_clause = "*"
        else:
            validated_columns = []
            for col in columns:
                # Handle aggregate functions: COUNT(column_name)
                if '(' in col and ')' in col:
                    parts = col.split('(')
                    if len(parts) != 2:
                        raise ValueError(f"Invalid column format: {col}")
                    
                    aggregate = parts[0]
                    column_name = parts[1].rstrip(')')
                    
                    validated_aggregate = self.validate_aggregate(aggregate)
                    validated_column = self.validate_column_name(column_name)
                    validated_columns.append(f"{validated_aggregate}({validated_column})")
                else:
                    validated_columns.append(self.validate_column_name(col))
            
            select_clause = ", ".join(validated_columns)
        
        # Build base query
        query = f"SELECT {select_clause} FROM {validated_table}"
        params = {}
        
        # Build WHERE clause with parameterized queries
        if where_conditions:
            where_clauses = []
            for column, value in where_conditions.items():
                validated_column = self.validate_column_name(column)
                
                if isinstance(value, dict):
                    # Handle operators like {"column": {"op": ">", "value": 100}}
                    operator = self.validate_operator(value.get("op", "="))
                    param_value = value.get("value")
                    param_name = f"param_{len(params)}"
                    
                    where_clauses.append(f"{validated_column} {operator} :{param_name}")
                    params[param_name] = param_value
                elif isinstance(value, (list, tuple)):
                    # Handle IN clauses
                    if len(value) == 0:
                        raise ValueError("IN clause cannot be empty")
                    
                    param_names = []
                    for i, item in enumerate(value):
                        param_name = f"param_{len(params)}"
                        param_names.append(f":{param_name}")
                        params[param_name] = item
                    
                    where_clauses.append(f"{validated_column} IN ({', '.join(param_names)})")
                else:
                    # Simple equality
                    param_name = f"param_{len(params)}"
                    where_clauses.append(f"{validated_column} = :{param_name}")
                    params[param_name] = value
            
            if where_clauses:
                query += f" WHERE {' AND '.join(where_clauses)}"
        
        # Add ORDER BY
        if order_by:
            validated_order = self.validate_order_by(order_by)
            query += f" ORDER BY {validated_order}"
        
        # Add LIMIT and OFFSET
        if limit is not None:
            if limit < 1 or limit > 10000:
                raise ValueError("LIMIT must be between 1 and 10000")
            query += f" LIMIT :limit"
            params["limit"] = limit
        
        if offset is not None:
            if offset < 0:
                raise ValueError("OFFSET must be non-negative")
            query += f" OFFSET :offset"
            params["offset"] = offset
        
        return query, params
    
    def build_safe_insert(self, table: str, data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Build completely safe INSERT query"""
        
        validated_table = self.validate_table_name(table)
        
        if not data:
            raise ValueError("INSERT data cannot be empty")
        
        # Validate all columns
        validated_columns = []
        param_names = []
        params = {}
        
        for column, value in data.items():
            validated_column = self.validate_column_name(column)
            validated_columns.append(validated_column)
            
            param_name = f"param_{len(params)}"
            param_names.append(f":{param_name}")
            params[param_name] = value
        
        column_list = ", ".join(validated_columns)
        param_list = ", ".join(param_names)
        
        query = f"INSERT INTO {validated_table} ({column_list}) VALUES ({param_list})"
        return query, params
    
    def build_safe_update(self, 
                          table: str,
                          set_data: Dict[str, Any],
                          where_conditions: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]:
        """Build completely safe UPDATE query"""
        
        validated_table = self.validate_table_name(table)
        
        if not set_data:
            raise ValueError("UPDATE data cannot be empty")
        
        # Build SET clause
        set_clauses = []
        params = {}
        
        for column, value in set_data.items():
            validated_column = self.validate_column_name(column)
            param_name = f"param_{len(params)}"
            set_clauses.append(f"{validated_column} = :{param_name}")
            params[param_name] = value
        
        query = f"UPDATE {validated_table} SET {', '.join(set_clauses)}"
        
        # Build WHERE clause
        if where_conditions:
            where_clauses = []
            for column, value in where_conditions.items():
                validated_column = self.validate_column_name(column)
                param_name = f"param_{len(params)}"
                where_clauses.append(f"{validated_column} = :{param_name}")
                params[param_name] = value
            
            query += f" WHERE {' AND '.join(where_clauses)}"
        
        return query, params
    
    def build_safe_delete(self, 
                          table: str,
                          where_conditions: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Build completely safe DELETE query"""
        
        validated_table = self.validate_table_name(table)
        
        if not where_conditions:
            raise ValueError("DELETE requires WHERE conditions for safety")
        
        # Build WHERE clause
        where_clauses = []
        params = {}
        
        for column, value in where_conditions.items():
            validated_column = self.validate_column_name(column)
            param_name = f"param_{len(params)}"
            where_clauses.append(f"{validated_column} = :{param_name}")
            params[param_name] = value
        
        query = f"DELETE FROM {validated_table} WHERE {' AND '.join(where_clauses)}"
        return query, params
    
    def build_metrics_query(self, hours_back: int = 24) -> Tuple[str, Dict[str, Any]]:
        """Pre-built safe query for metrics with time filtering"""
        
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        query, params = self.build_safe_select(
            table="database_metrics",
            where_conditions={
                "timestamp": {"op": ">", "value": cutoff_time}
            },
            order_by="timestamp DESC",
            limit=1000
        )
        
        return query, params
    
    def build_query_insights(self, hours_back: int = 24) -> Tuple[str, Dict[str, Any]]:
        """Pre-built safe query for query insights"""
        
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        query, params = self.build_safe_select(
            table="query_logs",
            columns=["COUNT(*) as total_queries", "AVG(execution_time) as avg_time", "MAX(execution_time) as max_time"],
            where_conditions={
                "timestamp": {"op": ">", "value": cutoff_time},
                "execution_time": {"op": ">", "value": 0}
            }
        )
        
        return query, params
    
    def execute_safe_query(self, db: Session, query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute safe query with proper error handling"""
        
        try:
            result = db.execute(text(query), params)
            rows = result.fetchall()
            
            # Convert to list of dictionaries
            return [dict(row._mapping) for row in rows]
            
        except Exception as e:
            logger.error(f"Safe query execution failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise

# Global safe query builder instance
safe_query_builder = SafeQueryBuilder()
