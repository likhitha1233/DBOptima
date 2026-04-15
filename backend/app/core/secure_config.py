"""
FAANG-level Secure Configuration Management
Environment-based config with validation and encryption
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from cryptography.fernet import Fernet
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """Secure database configuration"""
    host: str
    port: int
    name: str
    username: str
    password: str
    ssl_mode: str = "require"
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600

@dataclass
class RedisConfig:
    """Redis configuration for caching and rate limiting"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ssl: bool = False
    max_connections: int = 100

@dataclass
class SecurityConfig:
    """Security configuration"""
    secret_key: str
    api_key_rotation_days: int = 30
    session_timeout_minutes: int = 60
    max_request_size_mb: int = 10
    allowed_origins: list = None
    enable_audit_logging: bool = True

@dataclass
class MLConfig:
    """ML model configuration"""
    model_registry_path: str
    training_data_retention_days: int = 90
    model_validation_threshold: float = 0.7
    drift_detection_threshold: float = 0.1
    retraining_interval_hours: int = 24

class SecureConfigManager:
    """FAANG-level configuration management with encryption"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)
        
        # Load configurations
        self.db_config = self._load_database_config()
        self.redis_config = self._load_redis_config()
        self.security_config = self._load_security_config()
        self.ml_config = self._load_ml_config()
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for sensitive data"""
        key_file = self.config_dir / ".encryption_key"
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            # Set secure permissions
            os.chmod(key_file, 0o600)
            return key
    
    def _encrypt_value(self, value: str) -> str:
        """Encrypt sensitive value"""
        return self.cipher_suite.encrypt(value.encode()).decode()
    
    def _decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt sensitive value"""
        return self.cipher_suite.decrypt(encrypted_value.encode()).decode()
    
    def _load_database_config(self) -> DatabaseConfig:
        """Load database configuration from environment or encrypted file"""
        config_file = self.config_dir / "database.enc"
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                encrypted_data = json.load(f)
            
            return DatabaseConfig(
                host=self._decrypt_value(encrypted_data['host']),
                port=int(self._decrypt_value(encrypted_data['port'])),
                name=self._decrypt_value(encrypted_data['name']),
                username=self._decrypt_value(encrypted_data['username']),
                password=self._decrypt_value(encrypted_data['password']),
                ssl_mode=self._decrypt_value(encrypted_data.get('ssl_mode', 'require')),
                pool_size=int(self._decrypt_value(encrypted_data.get('pool_size', '10'))),
                max_overflow=int(self._decrypt_value(encrypted_data.get('max_overflow', '20'))),
                pool_timeout=int(self._decrypt_value(encrypted_data.get('pool_timeout', '30'))),
                pool_recycle=int(self._decrypt_value(encrypted_data.get('pool_recycle', '3600')))
            )
        else:
            # Load from environment variables
            return DatabaseConfig(
                host=os.getenv('DB_HOST', 'localhost'),
                port=int(os.getenv('DB_PORT', '5432')),
                name=os.getenv('DB_NAME', 'dbms_monitoring'),
                username=os.getenv('DB_USERNAME', 'postgres'),
                password=os.getenv('DB_PASSWORD', ''),
                ssl_mode=os.getenv('DB_SSL_MODE', 'require'),
                pool_size=int(os.getenv('DB_POOL_SIZE', '10')),
                max_overflow=int(os.getenv('DB_MAX_OVERFLOW', '20')),
                pool_timeout=int(os.getenv('DB_POOL_TIMEOUT', '30')),
                pool_recycle=int(os.getenv('DB_POOL_RECYCLE', '3600'))
            )
    
    def _load_redis_config(self) -> RedisConfig:
        """Load Redis configuration"""
        return RedisConfig(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_DB', 0)),
            password=os.getenv('REDIS_PASSWORD'),
            ssl=os.getenv('REDIS_SSL', 'false').lower() == 'true',
            max_connections=int(os.getenv('REDIS_MAX_CONNECTIONS', 100))
        )
    
    def _load_security_config(self) -> SecurityConfig:
        """Load security configuration"""
        secret_key = os.getenv('SECRET_KEY')
        if not secret_key:
            secret_key = Fernet.generate_key().decode()
            logger.warning("Generated new secret key - set SECRET_KEY env var for production")
        
        allowed_origins = os.getenv('ALLOWED_ORIGINS', '*').split(',')
        allowed_origins = [origin.strip() for origin in allowed_origins]
        
        return SecurityConfig(
            secret_key=secret_key,
            api_key_rotation_days=int(os.getenv('API_KEY_ROTATION_DAYS', '30')),
            session_timeout_minutes=int(os.getenv('SESSION_TIMEOUT_MINUTES', '60')),
            max_request_size_mb=int(os.getenv('MAX_REQUEST_SIZE_MB', '10')),
            allowed_origins=allowed_origins,
            enable_audit_logging=os.getenv('ENABLE_AUDIT_LOGGING', 'true').lower() == 'true'
        )
    
    def _load_ml_config(self) -> MLConfig:
        """Load ML configuration"""
        return MLConfig(
            model_registry_path=os.getenv('MODEL_REGISTRY_PATH', 'models'),
            training_data_retention_days=int(os.getenv('TRAINING_DATA_RETENTION_DAYS', '90')),
            model_validation_threshold=float(os.getenv('MODEL_VALIDATION_THRESHOLD', '0.7')),
            drift_detection_threshold=float(os.getenv('DRIFT_DETECTION_THRESHOLD', '0.1')),
            retraining_interval_hours=int(os.getenv('RETRAINING_INTERVAL_HOURS', '24'))
        )
    
    def save_database_config(self, config: DatabaseConfig):
        """Save encrypted database configuration"""
        encrypted_data = {
            'host': self._encrypt_value(config.host),
            'port': self._encrypt_value(str(config.port)),
            'name': self._encrypt_value(config.name),
            'username': self._encrypt_value(config.username),
            'password': self._encrypt_value(config.password),
            'ssl_mode': self._encrypt_value(config.ssl_mode),
            'pool_size': self._encrypt_value(str(config.pool_size)),
            'max_overflow': self._encrypt_value(str(config.max_overflow)),
            'pool_timeout': self._encrypt_value(str(config.pool_timeout)),
            'pool_recycle': self._encrypt_value(str(config.pool_recycle))
        }
        
        config_file = self.config_dir / "database.enc"
        with open(config_file, 'w') as f:
            json.dump(encrypted_data, f, indent=2)
        
        # Set secure permissions
        os.chmod(config_file, 0o600)
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate all configurations"""
        validation_results = {
            "database": self._validate_database_config(),
            "redis": self._validate_redis_config(),
            "security": self._validate_security_config(),
            "ml": self._validate_ml_config()
        }
        
        return validation_results
    
    def _validate_database_config(self) -> Dict[str, Any]:
        """Validate database configuration"""
        issues = []
        
        if not self.db_config.host:
            issues.append("Database host is required")
        
        if not self.db_config.username:
            issues.append("Database username is required")
        
        if not self.db_config.password:
            issues.append("Database password is required")
        
        if self.db_config.pool_size < 1 or self.db_config.pool_size > 100:
            issues.append("Database pool size must be between 1 and 100")
        
        return {"valid": len(issues) == 0, "issues": issues}
    
    def _validate_redis_config(self) -> Dict[str, Any]:
        """Validate Redis configuration"""
        issues = []
        
        if self.redis_config.port < 1 or self.redis_config.port > 65535:
            issues.append("Redis port must be between 1 and 65535")
        
        if self.redis_config.max_connections < 1:
            issues.append("Redis max connections must be positive")
        
        return {"valid": len(issues) == 0, "issues": issues}
    
    def _validate_security_config(self) -> Dict[str, Any]:
        """Validate security configuration"""
        issues = []
        
        if len(self.security_config.secret_key) < 32:
            issues.append("Secret key must be at least 32 characters")
        
        if self.security_config.api_key_rotation_days < 1:
            issues.append("API key rotation days must be positive")
        
        if self.security_config.max_request_size_mb < 1 or self.security_config.max_request_size_mb > 100:
            issues.append("Max request size must be between 1MB and 100MB")
        
        return {"valid": len(issues) == 0, "issues": issues}
    
    def _validate_ml_config(self) -> Dict[str, Any]:
        """Validate ML configuration"""
        issues = []
        
        if not os.path.exists(self.ml_config.model_registry_path):
            try:
                os.makedirs(self.ml_config.model_registry_path, exist_ok=True)
            except Exception as e:
                issues.append(f"Cannot create model registry path: {e}")
        
        if self.ml_config.model_validation_threshold < 0 or self.ml_config.model_validation_threshold > 1:
            issues.append("Model validation threshold must be between 0 and 1")
        
        return {"valid": len(issues) == 0, "issues": issues}
    
    def get_database_url(self) -> str:
        """Get database connection URL"""
        if self.db_config.host == "localhost":
            return f"sqlite:///./{self.db_config.name}.db"
        else:
            return (
                f"postgresql://{self.db_config.username}:{self.db_config.password}"
                f"@{self.db_config.host}:{self.db_config.port}/{self.db_config.name}"
            )

# Initialize secure configuration
secure_config = SecureConfigManager()

# Validate configuration on startup
validation_results = secure_config.validate_config()
for component, result in validation_results.items():
    if not result["valid"]:
        logger.error(f"Configuration validation failed for {component}: {result['issues']}")
    else:
        logger.info(f"Configuration validation passed for {component}")
