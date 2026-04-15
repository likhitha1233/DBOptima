"""
Production-safe database configuration with SQLite fallback.

This module provides database operations with automatic fallback to SQLite
for demo purposes and production-safe configuration via environment variables.
"""

import os
import logging
import time
import threading
from contextlib import contextmanager
from functools import lru_cache, wraps
from sqlalchemy import create_engine, text, event
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings
from .exceptions import DatabaseConnectionError, DatabaseQueryError
from .error_handler import handle_errors

logger = logging.getLogger(__name__)

# =================== CIRCUIT BREAKER ===================
# Simple in-memory circuit breaker for database calls

class DatabaseCircuitBreaker:
    """Simple circuit breaker for database operations"""
    
    def __init__(self, failure_threshold=3, recovery_timeout=30, call_timeout=3):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.call_timeout = call_timeout
        
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.lock = threading.Lock()
    
    def __call__(self, func):
        """Decorator to wrap database calls"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self.lock:
                # Check if circuit is open and recovery timeout has passed
                if self.state == "OPEN":
                    if time.time() - self.last_failure_time > self.recovery_timeout:
                        self.state = "HALF_OPEN"
                        logger.info("Circuit breaker transitioning to HALF_OPEN")
                    else:
                        raise DatabaseConnectionError("Circuit breaker is OPEN - database calls blocked")
            
            try:
                # Execute with timeout
                start_time = time.time()
                
                def execute_with_timeout():
                    return func(*args, **kwargs)
                
                # Simple timeout implementation
                result = None
                timeout_thread = threading.Thread(target=lambda: setattr(wrapper, '_result', execute_with_timeout()))
                timeout_thread.daemon = True
                timeout_thread.start()
                timeout_thread.join(timeout=self.call_timeout)
                
                if timeout_thread.is_alive():
                    raise DatabaseConnectionError(f"Database call timeout after {self.call_timeout} seconds")
                
                result = getattr(wrapper, '_result', None)
                
                # Success - reset circuit breaker
                with self.lock:
                    if self.state != "CLOSED":
                        self.state = "CLOSED"
                        self.failure_count = 0
                        logger.info("Circuit breaker reset to CLOSED")
                
                return result
                
            except Exception as e:
                with self.lock:
                    self.failure_count += 1
                    self.last_failure_time = time.time()
                    
                    if self.failure_count >= self.failure_threshold:
                        self.state = "OPEN"
                        logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")
                
                raise e
        
        return wrapper

# Global circuit breaker instance
db_circuit_breaker = DatabaseCircuitBreaker(
    failure_threshold=3,    # 3 failures trigger circuit breaker
    recovery_timeout=30,    # 30 seconds cooldown
    call_timeout=3          # 3 seconds max per call
)

# =================== END CIRCUIT BREAKER ===================

# Database configuration with environment variable support
def get_database_config():
    """Get database configuration with environment variable support and SQLite fallback"""
    # Environment variables only - no hardcoded credentials
    db_type = os.getenv('DB_TYPE', 'sqlite')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = int(os.getenv('DB_PORT', '5432'))
    db_name = os.getenv('DB_NAME', 'dbms_demo.db')
    db_username = os.getenv('DB_USERNAME', '')  # No default credentials
    db_password = os.getenv('DB_PASSWORD', '')  # No default credentials
    
    config_file_enabled = os.getenv('USE_CONFIG_DB', 'false').lower() == 'true'
    
    if config_file_enabled:
        try:
            config_db = settings.get_section('database')
            if config_db:
                db_type = config_db.get('type', db_type)
                db_host = config_db.get('host', db_host)
                db_port = config_db.get('port', db_port)
                db_name = config_db.get('name', db_name)
                db_username = config_db.get('username', db_username)
                db_password = config_db.get('password', db_password)
        except:
            pass
    
    # STRICT: never silently fall back to SQLite for a requested server DB.
    # If the user wants SQLite, they must set DB_TYPE=sqlite explicitly.
    if db_type in ['postgresql', 'mysql'] and (not db_username or not db_password):
        raise DatabaseConnectionError(
            "DB_TYPE requires DB_USERNAME and DB_PASSWORD (refusing SQLite fallback)",
            db_type=db_type
        )
    
    # Default to SQLite if unsupported type
    if db_type not in ['postgresql', 'mysql', 'sqlite']:
        logger.warning(f"Unsupported database type '{db_type}', falling back to SQLite")
        db_type = 'sqlite'
        db_name = 'dbms_demo.db'
    
    return {
        'type': db_type,
        'host': db_host,
        'port': db_port,
        'name': db_name,
        'username': db_username,
        'password': db_password,
        'pool_size': 10,
        'max_overflow': 20,
        'pool_timeout': 30,
        'pool_recycle': 3600,
        'echo': False,
        'echo_pool': False,
        'connect_timeout': 10,
        'read_timeout': 30,
        'write_timeout': 30,
        'max_retries': 3,
        'retry_delay': 1
    }

db_config = get_database_config()

# Global engine variable (will be initialized with error handling)
engine = None
SessionLocal = None
Base = declarative_base()

# Performance metrics
db_metrics = {
    'query_count': 0,
    'cache_hits': 0,
    'cache_misses': 0,
    'total_query_time': 0.0,
    'connection_count': 0,
    'active_connections': 0
}
metrics_lock = threading.Lock()

class DatabaseMetrics:
    """Track database performance metrics"""
    
    def __init__(self):
        self.query_times = []
        self.lock = threading.Lock()
        self.start_time = time.time()
    
    def record_query(self, query: str, duration: float, cached: bool = False):
        """Record query execution time"""
        with self.lock:
            self.query_times.append({
                'query': query[:100],  # Truncate for memory
                'duration': duration,
                'cached': cached,
                'timestamp': time.time()
            })
            
            # Keep only last 1000 queries
            if len(self.query_times) > 1000:
                self.query_times = self.query_times[-1000:]
            
            # Update global metrics
            global db_metrics
            db_metrics['query_count'] += 1
            db_metrics['total_query_time'] += duration
            if cached:
                db_metrics['cache_hits'] += 1
            else:
                db_metrics['cache_misses'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        with self.lock:
            if not self.query_times:
                return {}
            
            durations = [q['duration'] for q in self.query_times]
            cached_queries = [q for q in self.query_times if q['cached']]
            
            return {
                'total_queries': len(self.query_times),
                'cached_queries': len(cached_queries),
                'cache_hit_rate': len(cached_queries) / len(self.query_times),
                'avg_query_time': sum(durations) / len(durations),
                'min_query_time': min(durations),
                'max_query_time': max(durations),
                'queries_per_second': len(self.query_times) / (time.time() - self.start_time)
            }

# Global metrics instance
db_metrics_tracker = DatabaseMetrics()

def initialize_database():
    """Initialize database engine with error handling and optimization"""
    global engine, SessionLocal
    
    try:
        # Log database configuration
        db_type = db_config['type']
        db_name = db_config['name']
        
        if db_type == 'sqlite':
            logger.info(f"Initializing SQLite database: {db_name}")
        else:
            logger.info(f"Initializing {db_type} database: {db_name}@{db_config['host']}:{db_config['port']}")
        
        # Validate configuration
        _validate_database_config()
        
        # Create engine with retry logic
        engine = _create_engine_with_retry()
        
        # Test connection
        if not _test_connection_with_retry():
            raise DatabaseConnectionError(
                "Failed to establish database connection after multiple attempts",
                db_type=db_config.get('type'),
                port=db_config.get('port')
            )
        
        # Create session factory
        SessionLocal = sessionmaker(
            autocommit=False, 
            autoflush=False, 
            bind=engine
        )
        
        # Create tables automatically
        try:
            from ..models import create_tables as create_db_tables
            create_db_tables()
        except ImportError:
            # Fallback to basic table creation
            create_tables()
        
        logger.info(f"Database initialized successfully - Type: {db_type}, Name: {db_name}")
        return True
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise DatabaseConnectionError(
            f"Database initialization failed: {str(e)}",
            db_type=db_config.get('type'),
            port=db_config.get('port')
        )

def _validate_database_config():
    """Validate database configuration"""
    # All required fields should be present from get_database_config()
    required_fields = ['type', 'host', 'port', 'name', 'username', 'password']
    
    # Validate port number
    try:
        port = int(db_config['port'])
        if not (1 <= port <= 65535):
            raise DatabaseConnectionError(
                f"Invalid port number: {port}. Must be between 1 and 65535",
                config_key='port'
            )
    except ValueError:
        raise DatabaseConnectionError(
            f"Port must be a number, got: {db_config['port']}",
            config_key='port'
        )
    
    # Validate database type
    supported_types = ['postgresql', 'mysql', 'sqlite']
    if db_config['type'] not in supported_types:
        raise DatabaseConnectionError(
            f"Unsupported database type: {db_config['type']}",
            db_type=db_config['type'],
            supported_types=supported_types
        )

def _create_engine_with_retry():
    """Create database engine with retry logic and optimization"""
    global engine
    max_retries = db_config.get('max_retries', 3)
    retry_delay = db_config.get('retry_delay', 1)
    
    for attempt in range(max_retries):
        try:
            # Build database URL
            db_url = _build_database_url()
            
            # Engine configuration for performance
            engine_kwargs = {
                'poolclass': QueuePool,
                'pool_size': db_config.get('pool_size', 10),
                'max_overflow': db_config.get('max_overflow', 20),
                'pool_timeout': db_config.get('pool_timeout', 30),
                'pool_recycle': db_config.get('pool_recycle', 3600),
                'pool_pre_ping': True,
                'echo': db_config.get('echo', False),
                'echo_pool': db_config.get('echo_pool', False),
                'connect_args': {}
            }
            
            # Database-specific connection arguments
            if db_config['type'] == 'sqlite':
                # SQLite doesn't support connection timeouts
                engine_kwargs['connect_args'] = {}
            else:
                # MySQL/PostgreSQL support connection timeouts
                engine_kwargs['connect_args'] = {
                    'connect_timeout': db_config.get('connect_timeout', 10),
                    'read_timeout': db_config.get('read_timeout', 30),
                    'write_timeout': db_config.get('write_timeout', 30)
                }
            
            # Database-specific optimizations
            if db_config['type'] == 'mysql':
                try:
                    # Try to import MySQL driver
                    engine_kwargs['connect_args'].update({
                        'charset': 'utf8mb4',
                        'autocommit': False
                    })
                except ImportError:
                    # Fallback to mysql-connector-python or raise error
                    try:
                        engine_kwargs['connect_args'].update({
                            'charset': 'utf8mb4',
                            'autocommit': False
                        })
                    except ImportError:
                        raise DatabaseConnectionError(
                            "MySQL driver not installed. Install pymysql or mysql-connector-python",
                            db_type='mysql'
                        )
            elif db_config['type'] == 'postgresql':
                try:
                    # Try to import PostgreSQL driver
                    engine_kwargs['connect_args'].update({
                        'application_name': 'dbms_monitoring'
                    })
                except ImportError:
                    raise DatabaseConnectionError(
                        "PostgreSQL driver not installed. Install psycopg2",
                        db_type='postgresql'
                    )
            
            engine = create_engine(db_url, **engine_kwargs)
            
            # Add event listeners for metrics
            _setup_event_listeners(engine)
            
            return engine
            
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Engine creation attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}")
                time.sleep(retry_delay)
            else:
                raise DatabaseConnectionError(
                    f"Failed to create database engine after {max_retries} attempts: {str(e)}",
                    db_type=db_config.get('type'),
                    port=db_config.get('port')
                )

def _build_database_url():
    """Build database URL from configuration"""
    db_type = db_config['type']
    host = db_config['host']
    port = db_config['port']
    name = db_config['name']
    username = db_config['username']
    password = db_config['password']
    
    if db_type == 'sqlite':
        return f"sqlite:///{name}"
    
    return (
        f"{db_type}://"
        f"{username}:{password}"
        f"@{host}:{port}/{name}"
    )

def _setup_event_listeners(engine):
    """Setup event listeners for performance monitoring"""
    
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        context._query_start_time = time.time()
    
    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if hasattr(context, '_query_start_time'):
            duration = time.time() - context._query_start_time
            db_metrics_tracker.record_query(statement, duration, cached=False)

def _test_connection_with_retry():
    """Test database connection with retry logic"""
    max_retries = db_config.get('max_retries', 3)
    retry_delay = db_config.get('retry_delay', 1)
    
    for attempt in range(max_retries):
        try:
            with engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                result.fetchone()
                logger.info("Database connection test successful")
                return True
                
        except (OperationalError, InterfaceError) as e:
            if attempt < max_retries - 1:
                logger.warning(f"Connection test attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}")
                time.sleep(retry_delay)
            else:
                raise DatabaseConnectionError(
                    f"Database connection failed: {str(e)}",
                    db_type=db_config.get('type'),
                    port=db_config.get('port')
                )
        except SQLAlchemyError as e:
            raise DatabaseQueryError(
                f"Database query failed: {str(e)}",
                query="SELECT 1",
                error=str(e)
            )
    
    return False

@handle_errors(
    context="database.get_db",
    fallback_value=None,
    user_message="Database session unavailable"
)
@db_circuit_breaker
def get_db():
    """Database dependency for FastAPI with error handling"""
    if SessionLocal is None:
        raise DatabaseConnectionError("Database not initialized")
    
    db = SessionLocal()
    try:
        # Update connection metrics
        with metrics_lock:
            db_metrics['connection_count'] += 1
            db_metrics['active_connections'] += 1
        
        yield db
    finally:
        # Update connection metrics
        with metrics_lock:
            db_metrics['active_connections'] -= 1
        db.close()

@contextmanager
@db_circuit_breaker
def get_db_session():
    """Context manager for database sessions"""
    if SessionLocal is None:
        raise DatabaseConnectionError("Database not initialized")
    
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

@lru_cache(maxsize=128)
def get_table_schema(table_name: str) -> Dict[str, Any]:
    """Get table schema with caching"""
    try:
        with engine.connect() as conn:
            if db_config['type'] == 'postgresql':
                result = conn.execute(text("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = :table_name
                    ORDER BY ordinal_position
                """), {"table_name": table_name})
            elif db_config['type'] == 'mysql':
                result = conn.execute(text("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = :table_name
                    ORDER BY ordinal_position
                """), {"table_name": table_name})
            else:
                return {}
            
            columns = {}
            for row in result:
                columns[row[0]] = {
                    'type': row[1],
                    'nullable': row[2] == 'YES',
                    'default': row[3]
                }
            
            return {
                'table_name': table_name,
                'columns': columns,
                'column_count': len(columns)
            }
            
    except Exception as e:
        logger.error(f"Failed to get schema for table {table_name}: {e}")
        return {}

def get_database_stats() -> Dict[str, Any]:
    """Get comprehensive database statistics"""
    stats = {
        'performance': db_metrics_tracker.get_stats(),
        'connections': {
            'total': db_metrics['connection_count'],
            'active': db_metrics['active_connections'],
            'pool_size': db_config.get('pool_size', 10),
            'max_overflow': db_config.get('max_overflow', 20)
        },
        'queries': {
            'total': db_metrics['query_count'],
            'cache_hits': db_metrics['cache_hits'],
            'cache_misses': db_metrics['cache_misses'],
            'cache_hit_rate': (
                db_metrics['cache_hits'] / max(db_metrics['query_count'], 1)
            )
        }
    }
    
    # Add engine-specific stats if available
    if engine and hasattr(engine.pool, 'size'):
        pool = engine.pool
        stats['pool'] = {
            'size': pool.size(),
            'checked_in': pool.checkedin(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow(),
            'invalid': pool.invalid()
        }
    
    return stats

def create_tables():
    """Create all database tables with error handling"""
    if engine is None:
        raise DatabaseConnectionError("Database engine not initialized")
    
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error("Failed to create database tables: %s", str(e))
        raise DatabaseConnectionError(
            f"Failed to create database tables: {str(e)}"
        )

def drop_tables():
    """Drop all database tables (use with caution)"""
    if engine is None:
        raise DatabaseConnectionError("Database engine not initialized")
    
    try:
        Base.metadata.drop_all(bind=engine)
        logger.warning("All database tables dropped")
        return True
    except Exception as e:
        logger.error("Failed to drop database tables: %s", str(e))
        raise DatabaseConnectionError(
            f"Failed to drop database tables: {str(e)}"
        )

@db_circuit_breaker
def health_check() -> Dict[str, Any]:
    """Perform database health check"""
    try:
        start_time = time.time()
        
        # Test basic connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        connection_time = time.time() - start_time
        
        # Get performance stats
        stats = get_database_stats()
        
        # Determine health status
        health_status = "healthy"
        issues = []
        
        if connection_time > 1.0:
            health_status = "degraded"
            issues.append(f"Slow connection: {connection_time:.2f}s")
        
        if stats['queries']['cache_hit_rate'] < 0.5:
            if health_status == "healthy":
                health_status = "degraded"
            issues.append(f"Low cache hit rate: {stats['queries']['cache_hit_rate']:.2%}")
        
        if stats['connections']['active'] > stats['connections']['pool_size'] * 0.8:
            health_status = "degraded"
            issues.append(f"High connection pool usage: {stats['connections']['active']}/{stats['connections']['pool_size']}")
        
        return {
            'status': health_status,
            'connection_time': connection_time,
            'stats': stats,
            'issues': issues,
            'timestamp': time.time()
        }
        
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': time.time()
        }

@handle_errors(
    context="database.test_connection",
    fallback_value=False,
    user_message="Database connection test failed"
)
@db_circuit_breaker
def test_connection():
    """Test database connection with comprehensive error handling"""
    if engine is None:
        logger.error("Database engine not initialized")
        return False
    
    try:
        with engine.connect() as connection:
            # Test basic query
            result = connection.execute(text("SELECT 1"))
            result.fetchone()
            
            # Test database-specific query
            db_type = db_config.get('type')
            if db_type == 'mysql':
                result = connection.execute(text("SELECT VERSION()"))
            elif db_type == 'postgresql':
                result = connection.execute(text("SELECT version()"))
            
            version_info = result.fetchone()[0] if result.fetchone() else "Unknown"
            logger.info(f"Database connection successful - {db_type} v{version_info}")
            return True
            
    except OperationalError as e:
        logger.error(f"Database operational error: {e}")
        return False
    except InterfaceError as e:
        logger.error(f"Database interface error: {e}")
        return False
    except SQLAlchemyError as e:
        logger.error(f"Database SQL error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected database error: {e}")
        return False

@db_circuit_breaker
def execute_query_with_retry(query: str, params: dict = None, max_attempts: int = 3):
    """Execute database query with retry logic and error handling"""
    if engine is None:
        raise DatabaseConnectionError("Database not initialized")
    
    @retry_on_failure(max_attempts=max_attempts, delay=1.0)
    def _execute_query():
        try:
            with engine.connect() as connection:
                if params:
                    result = connection.execute(text(query), params)
                else:
                    result = connection.execute(text(query))
                
                # Handle different result types
                if result.returns_rows:
                    return result.fetchall()
                else:
                    return result.rowcount
                    
        except OperationalError as e:
            raise DatabaseConnectionError(f"Database connection lost: {str(e)}")
        except SQLAlchemyError as e:
            raise DatabaseQueryError(f"Query execution failed: {str(e)}", query=query)
    
    return _execute_query()

def get_database_info():
    """Get comprehensive database information"""
    if engine is None:
        return {"status": "error", "message": "Database not initialized"}
    
    try:
        with engine.connect() as connection:
            db_type = db_config.get('type')
            info = {
                "status": "connected",
                "type": db_type,
                "host": db_config.get('host'),
                "port": db_config.get('port'),
                "database": db_config.get('name'),
                "pool_size": db_config.get('pool_size'),
                "max_overflow": db_config.get('max_overflow')
            }
            
            # Get version info
            try:
                if db_type == 'mysql':
                    result = connection.execute(text("SELECT VERSION()"))
                elif db_type == 'postgresql':
                    result = connection.execute(text("SELECT version()"))
                
                version = result.fetchone()
                if version:
                    info["version"] = version[0]
            except Exception as e:
                logger.warning(f"Could not get database version: {e}")
                info["version"] = "Unknown"
            
            # Get connection pool info
            try:
                pool = engine.pool
                info["pool"] = {
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "invalid": pool.invalid()
                }
            except Exception as e:
                logger.warning(f"Could not get pool info: {e}")
            
            return info
            
    except Exception as e:
        logger.error(f"Error getting database info: {e}")
        return {
            "status": "error",
            "message": str(e),
            "type": db_config.get('type'),
            "host": db_config.get('host')
        }

def create_tables():
    """Create all database tables"""
    if engine is None:
        logger.error("Database engine not initialized - cannot create tables")
        return False
    
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        return False

# SQLite fallback removed - use proper configuration-driven initialization
