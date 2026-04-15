"""
Request Validation Middleware
FAANG-level input validation and sanitization
"""

import re
import logging
from typing import Dict, Any
from fastapi import Request, HTTPException
from pydantic import BaseModel, validator

logger = logging.getLogger(__name__)

class SafeQueryValidator(BaseModel):
    """Safe query parameter validation"""
    
    @validator('limit')
    def validate_limit(cls, v):
        if v is not None and (v < 1 or v > 1000):
            raise ValueError("Limit must be between 1 and 1000")
        return v
    
    @validator('offset')
    def validate_offset(cls, v):
        if v is not None and v < 0:
            raise ValueError("Offset must be non-negative")
        return v
    
    @validator('hours')
    def validate_hours(cls, v):
        if v is not None and (v < 1 or v > 168):
            raise ValueError("Hours must be between 1 and 168")
        return v

class SQLIdentifierValidator:
    """SQL identifier whitelist validation"""
    
    # Whitelist of allowed table and column names
    ALLOWED_TABLES = {
        'database_metrics', 'query_logs', 'index_recommendations', 
        'performance_predictions', 'model_registry'
    }
    
    ALLOWED_COLUMNS = {
        'id', 'timestamp', 'cpu_usage', 'memory_usage', 'disk_usage',
        'connections', 'queries_per_second', 'slow_queries', 'query_text',
        'execution_time', 'rows_examined', 'rows_returned', 'database_name',
        'user', 'host', 'confidence', 'predicted_usage', 'trend',
        'anomaly_detected', 'feature_importance', 'model_version'
    }
    
    @classmethod
    def validate_table_name(cls, table_name: str) -> str:
        """Validate table name against whitelist"""
        if not table_name or table_name not in cls.ALLOWED_TABLES:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid table name: {table_name}"
            )
        return table_name
    
    @classmethod
    def validate_column_name(cls, column_name: str) -> str:
        """Validate column name against whitelist"""
        if not column_name or column_name not in cls.ALLOWED_COLUMNS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid column name: {column_name}"
            )
        return column_name
    
    @classmethod
    def validate_order_by(cls, order_by: str) -> str:
        """Validate ORDER BY clause"""
        if not order_by:
            return "timestamp DESC"
        
        # Check if it's a valid column with optional direction
        parts = order_by.split()
        if len(parts) > 2:
            raise HTTPException(status_code=400, detail="Invalid ORDER BY clause")
        
        column = parts[0]
        direction = parts[1].upper() if len(parts) == 2 else "DESC"
        
        cls.validate_column_name(column)
        
        if direction not in ["ASC", "DESC"]:
            raise HTTPException(status_code=400, detail="Invalid sort direction")
        
        return f"{column} {direction}"

class RequestValidator:
    """Comprehensive request validation"""
    
    @staticmethod
    def validate_json_size(request: Request) -> None:
        """Validate JSON request size"""
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(status_code=413, detail="JSON payload too large")
    
    @staticmethod
    def validate_headers(request: Request) -> None:
        """Validate request headers"""
        # Check for suspicious headers
        suspicious_headers = [
            'x-forwarded-for', 'x-real-ip', 'x-originating-ip',
            'x-cluster-client-ip', 'x-forwarded-host'
        ]
        
        for header in suspicious_headers:
            if header in request.headers:
                value = request.headers[header]
                if len(value) > 200 or not re.match(r'^[\w\.\-:,\s]+$', value):
                    logger.warning(f"Suspicious header detected: {header}={value}")
                    raise HTTPException(status_code=400, detail="Invalid header format")
    
    @staticmethod
    def validate_path_params(request: Request) -> None:
        """Validate path parameters"""
        path_params = request.path_params
        
        for key, value in path_params.items():
            if not isinstance(value, str):
                continue
            
            # Check for SQL injection patterns
            sql_patterns = [
                r'(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b)',
                r'(--|#|\/\*|\*\/)',
                r'(\b(OR|AND)\s+\d+\s*=\s*\d+)',
                r'(\b(OR|AND)\s+\'\w+\'\s*=\s*\'\w+\')'
            ]
            
            for pattern in sql_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    logger.warning(f"SQL injection attempt detected in path param: {key}={value}")
                    raise HTTPException(status_code=400, detail="Invalid path parameter")
    
    @staticmethod
    def sanitize_query_params(query_params: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize query parameters"""
        sanitized = {}
        
        for key, value in query_params.items():
            if not isinstance(value, str):
                sanitized[key] = value
                continue
            
            # Remove potential XSS
            value = re.sub(r'<[^>]*>', '', value)
            
            # Remove potential SQL injection
            value = re.sub(r'(\'|\"|;|--|\/\*|\*\/)', '', value)
            
            # Check length
            if len(value) > 100:
                logger.warning(f"Query parameter too long: {key}={len(value)} chars")
                raise HTTPException(status_code=400, detail="Parameter too long")
            
            sanitized[key] = value
        
        return sanitized

async def validation_middleware(request: Request, call_next):
    """Comprehensive validation middleware"""
    try:
        # Validate headers
        RequestValidator.validate_headers(request)
        
        # Validate path parameters
        RequestValidator.validate_path_params(request)
        
        # Validate JSON size for POST/PUT requests
        if request.method in ["POST", "PUT", "PATCH"]:
            RequestValidator.validate_json_size(request)
        
        # Sanitize query parameters
        if request.query_params:
            sanitized_params = RequestValidator.sanitize_query_params(dict(request.query_params))
            # Update request with sanitized params (this is a simplified approach)
            request._query_params = sanitized_params
        
        response = await call_next(request)
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation middleware error: {e}")
        raise HTTPException(status_code=400, detail="Request validation failed")

# Safe query builder utility
class SafeQueryBuilder:
    """Safe SQL query builder with whitelist validation"""
    
    def __init__(self):
        self.validator = SQLIdentifierValidator()
    
    def build_select_query(self, table: str, columns: list = None, 
                          where_clause: str = None, order_by: str = None,
                          limit: int = None, offset: int = None) -> tuple[str, Dict[str, Any]]:
        """Build safe SELECT query"""
        
        # Validate table name
        self.validator.validate_table_name(table)
        
        # Validate columns
        if columns is None:
            select_columns = "*"
        else:
            validated_columns = []
            for col in columns:
                self.validator.validate_column_name(col)
                validated_columns.append(col)
            select_columns = ", ".join(validated_columns)
        
        # Build base query
        query = f"SELECT {select_columns} FROM {table}"
        params = {}
        
        # Add WHERE clause (must be parameterized)
        if where_clause:
            query += f" WHERE {where_clause}"
        
        # Add ORDER BY
        if order_by:
            validated_order = self.validator.validate_order_by(order_by)
            query += f" ORDER BY {validated_order}"
        
        # Add LIMIT and OFFSET
        if limit:
            query += " LIMIT :limit"
            params["limit"] = limit
        
        if offset:
            query += " OFFSET :offset"
            params["offset"] = offset
        
        return query, params
