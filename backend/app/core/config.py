"""
Centralized Configuration System

This module provides access to configuration loaded from environment variables.
"""

import os

class Settings:
    """Settings class that loads from environment variables"""
    
    def __init__(self):
        pass
    
    @property
    def db_type(self) -> str:
        return os.getenv('DB_TYPE', 'sqlite')
    
    @property
    def db_host(self) -> str:
        return os.getenv('DB_HOST', 'localhost')
    
    @property
    def db_port(self) -> int:
        return int(os.getenv('DB_PORT', '5432'))
    
    @property
    def db_name(self) -> str:
        return os.getenv('DB_NAME', 'dbms_demo.db')
    
    @property
    def db_user(self) -> str:
        return os.getenv('DB_USERNAME', '')
    
    @property
    def db_password(self) -> str:
        return os.getenv('DB_PASSWORD', '')
    
    @property
    def api_host(self) -> str:
        return os.getenv('API_HOST', '0.0.0.0')
    
    @property
    def api_port(self) -> int:
        return int(os.getenv('API_PORT', '8000'))
    
    @property
    def debug(self) -> bool:
        return os.getenv('API_DEBUG', 'false').lower() == 'true'
    
    @property
    def database_url(self) -> str:
        """Generate database URL from configuration with SQLite fallback"""
        db_type = self.db_type.lower()
        
        # Force SQLite for local development if no credentials provided
        if db_type in ['mysql', 'postgresql'] and not self.db_user and not self.db_password:
            print("WARNING: No database credentials provided, falling back to SQLite")
            db_type = 'sqlite'
        
        if db_type == 'sqlite':
            return f"sqlite:///{self.db_name}"
        elif db_type == 'mysql':
            if not self.db_user or not self.db_password:
                raise ValueError("MySQL requires DB_USERNAME and DB_PASSWORD environment variables")
            return f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        elif db_type == 'postgresql':
            if not self.db_user or not self.db_password:
                raise ValueError("PostgreSQL requires DB_USERNAME and DB_PASSWORD environment variables")
            return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    @property
    def cors_origins(self) -> list:
        origins = os.getenv('CORS_ALLOW_ORIGINS', 'http://localhost:3000,http://localhost:8501')
        return [origin.strip() for origin in origins.split(',')]
    
    @property
    def cors_allow_credentials(self) -> bool:
        return os.getenv('CORS_ALLOW_CREDENTIALS', 'true').lower() == 'true'
    
    @property
    def cors_methods(self) -> list:
        methods = os.getenv('CORS_ALLOW_METHODS', 'GET,POST,PUT,DELETE,OPTIONS')
        return [method.strip() for method in methods.split(',')]
    
    @property
    def cors_headers(self) -> list:
        headers = os.getenv('CORS_ALLOW_HEADERS', '*')
        return [header.strip() for header in headers.split(',')]
    
    @property
    def monitoring_interval(self) -> int:
        return int(os.getenv('MONITORING_INTERVAL', '60'))
    
    @property
    def slow_query_threshold(self) -> float:
        return float(os.getenv('SLOW_QUERY_THRESHOLD', '1.0'))
    
    @property
    def model_update_interval(self) -> int:
        return int(os.getenv('MODEL_UPDATE_INTERVAL', '3600'))
    
    def get_section(self, section_name: str) -> dict:
        """Get configuration section (returns empty dict since using env vars)"""
        return {}
    
    @property
    def prediction_horizon(self) -> int:
        return int(os.getenv('PREDICTION_HORIZON', '24'))
    
    @property
    def dashboard_port(self) -> int:
        return int(os.getenv('DASHBOARD_PORT', '8501'))
    
    def get(self, key: str, default=None):
        """Get configuration value using environment variables"""
        # Convert dot notation to env var format
        env_key = key.upper().replace('.', '_')
        return os.getenv(env_key, default)
    
    def get_ml_model_config(self, resource: str):
        """Get ML model configuration for specific resource"""
        # Return default ML config since using env vars
        return {
            'model_type': 'RandomForest',
            'features': ['cpu_usage', 'memory_usage', 'disk_usage'],
            'target': 'performance_score'
        }
    
    def reload(self):
        """Reload configuration (no-op for environment variables)"""

# Global settings instance
settings = Settings()
