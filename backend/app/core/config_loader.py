import os
import yaml
import logging
import re

logger = logging.getLogger(__name__)

class ConfigLoader:
    """Centralized configuration loader with YAML and environment variable support"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config_data: Dict[str, Any] = {}
        self._load_configuration()
    
    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        # Try multiple locations for config file
        possible_paths = [
            "config/config.yaml",
            "config.yaml",
            "../config/config.yaml",
            "../../config/config.yaml"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Fallback to current directory
        return "config.yaml"
    
    def _load_configuration(self):
        """Load configuration from YAML file and environment variables"""
        try:
            # Load environment variables from .env file
            load_dotenv()
            
            # Load YAML configuration
            self.config_data = self._load_yaml_config()
            
            # Substitute environment variables in YAML
            self._substitute_env_vars()
            
            # Override with environment variables
            self._override_with_env_vars()
            
            # Validate configuration
            self._validate_configuration()
            
            logger.info(f"Configuration loaded from {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _load_yaml_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                return config or {}
        except FileNotFoundError:
            logger.warning(f"Config file not found: {self.config_path}. Using defaults.")
            return self._get_default_config()
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML config: {e}")
            raise
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration when YAML file is not found"""
        return {
            "database": {
                "type": os.getenv("DB_TYPE", "mysql"),
                "host": os.getenv("DB_HOST", "localhost"),
                "port": int(os.getenv("DB_PORT", "3306")),
                "name": os.getenv("DB_NAME", "database"),
                "user": os.getenv("DB_USER", "root"),
                "password": os.getenv("DB_PASSWORD", ""),
                "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
                "echo": os.getenv("DB_ECHO", "False").lower() == "true"
            },
            "api": {
                "host": "0.0.0.0",
                "port": 8000,
                "debug": False,
                "title": "AI Database Performance Optimizer",
                "version": "1.0.0"
            },
            "monitoring": {
                "interval_seconds": 60,
                "slow_query_threshold_ms": 1000,
                "metrics_retention_days": 30
            },
            "ml": {
                "model_update_interval_seconds": 3600,
                "prediction_horizon_hours": 24,
                "min_training_samples": 50
            },
            "dashboard": {
                "port": 8501,
                "title": "AI Database Performance Optimizer"
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "enable_console_logging": True,
                "enable_file_logging": False
            }
        }
    
    def _substitute_env_vars(self):
        """Substitute ${VAR:default} patterns in configuration values"""
        def substitute_recursive(obj):
            if isinstance(obj, dict):
                return {k: substitute_recursive(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [substitute_recursive(item) for item in obj]
            elif isinstance(obj, str):
                return self._substitute_env_string(obj)
            else:
                return obj
        
        self.config_data = substitute_recursive(self.config_data)
    
    def _substitute_env_string(self, text: str) -> str:
        """Substitute environment variables in a string"""
        # Pattern: ${VAR:default}
        pattern = r'\$\{([^}:]+):?([^}]*)\}'
        
        def replace_match(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) is not None else ""
            env_value = os.getenv(var_name, default_value)
            return env_value
        
        return re.sub(pattern, replace_match, text)
    
    def _override_with_env_vars(self):
        """Override configuration with environment variables"""
        env_mappings = {
            # Database
            "DB_TYPE": ("database", "type"),
            "DB_HOST": ("database", "host"),
            "DB_PORT": ("database", "port"),
            "DB_NAME": ("database", "name"),
            "DB_USER": ("database", "user"),
            "DB_PASSWORD": ("database", "password"),
            "DB_POOL_SIZE": ("database", "pool_size"),
            
            # API
            "API_HOST": ("api", "host"),
            "API_PORT": ("api", "port"),
            "API_DEBUG": ("api", "debug"),
            
            # Monitoring
            "MONITORING_INTERVAL": ("monitoring", "interval_seconds"),
            "SLOW_QUERY_THRESHOLD": ("monitoring", "slow_query_threshold_ms"),
            
            # ML
            "ML_MODEL_UPDATE_INTERVAL": ("ml", "model_update_interval_seconds"),
            "ML_PREDICTION_HORIZON": ("ml", "prediction_horizon_hours"),
            "ML_MIN_TRAINING_SAMPLES": ("ml", "min_training_samples"),
            
            # Dashboard
            "DASHBOARD_PORT": ("dashboard", "port"),
            
            # Logging
            "LOG_LEVEL": ("logging", "level"),
            "LOG_FILE": ("logging", "file"),
            
            # Security
            "JWT_SECRET_KEY": ("security", "jwt_secret_key"),
            
            # Performance
            "CACHE_TTL": ("performance", "cache_ttl_seconds"),
            "MAX_CONCURRENT_REQUESTS": ("performance", "max_concurrent_requests")
        }
        
        for env_var, (section, key) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert string to appropriate type
                converted_value = self._convert_env_value(value)
                self._set_nested_value(section, key, converted_value)
                logger.debug(f"Override {section}.{key} with env var {env_var}")
    
    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable string to appropriate type"""
        # Boolean conversion
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Integer conversion
        try:
            return int(value)
        except ValueError:
            pass
        
        # Float conversion
        try:
            return float(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def _set_nested_value(self, section: str, key: str, value: Any):
        """Set nested configuration value"""
        if section not in self.config_data:
            self.config_data[section] = {}
        self.config_data[section][key] = value
    
    def _validate_configuration(self):
        """Validate configuration values"""
        required_sections = ['database', 'api', 'monitoring']
        
        for section in required_sections:
            if section not in self.config_data:
                raise ValueError(f"Required configuration section '{section}' is missing")
        
        # Validate database configuration
        db_config = self.config_data['database']
        required_db_fields = ['type', 'host', 'port', 'name', 'user']
        for field in required_db_fields:
            if field not in db_config or db_config[field] is None:
                raise ValueError(f"Required database field '{field}' is missing or null")
        
        # Validate database type
        if db_config['type'] not in ['mysql', 'postgresql']:
            raise ValueError(f"Unsupported database type: {db_config['type']}")
        
        # Validate port numbers
        api_port = self.config_data['api'].get('port', 8000)
        db_port = db_config.get('port', 3306)
        dashboard_port = self.config_data.get('dashboard', {}).get('port', 8501)
        
        port_validations = [
            ('API', api_port),
            ('Database', db_port), 
            ('Dashboard', dashboard_port)
        ]
        
        for port_name, port_value in port_validations:
            # Convert string to int if needed
            if isinstance(port_value, str):
                try:
                    port_value = int(port_value)
                except ValueError:
                    raise ValueError(f"Invalid {port_name} port: {port_value} (must be a number)")
            
            # Debug logging
            logger.debug(f"Validating {port_name} port: {port_value} (type: {type(port_value)})")
            
            if not isinstance(port_value, int) or port_value < 1 or port_value > 65535:
                raise ValueError(f"Invalid {port_name} port: {port_value}. Must be between 1 and 65535")
        
        # Validate monitoring interval
        monitoring_interval = self.config_data['monitoring'].get('interval_seconds', 60)
        if isinstance(monitoring_interval, str):
            try:
                monitoring_interval = int(monitoring_interval)
            except ValueError:
                raise ValueError(f"Invalid monitoring interval: {monitoring_interval} (must be a number)")
        
        if not isinstance(monitoring_interval, int) or monitoring_interval < 1:
            raise ValueError(f"Invalid monitoring interval: {monitoring_interval}")
        
        logger.info("Configuration validation passed")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'database.host')"""
        keys = key.split('.')
        value = self.config_data
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section"""
        return self.config_data.get(section, {})
    
    def get_database_url(self) -> str:
        """Generate database URL from configuration"""
        db_config = self.get_section('database')
        db_type = db_config['type']
        
        if db_type == 'mysql':
            return (
                f"mysql+pymysql://{db_config['user']}:{db_config['password']}"
                f"@{db_config['host']}:{db_config['port']}/{db_config['name']}"
            )
        elif db_type == 'postgresql':
            return (
                f"postgresql://{db_config['user']}:{db_config['password']}"
                f"@{db_config['host']}:{db_config['port']}/{db_config['name']}"
            )
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    def get_cors_origins(self) -> list:
        """Get CORS allowed origins"""
        cors_config = self.get_section('cors')
        return cors_config.get('allow_origins', ['*'])
    
    def get_cors_methods(self) -> list:
        """Get CORS allowed methods"""
        cors_config = self.get_section('cors')
        return cors_config.get('allow_methods', ['*'])
    
    def get_cors_headers(self) -> list:
        """Get CORS allowed headers"""
        cors_config = self.get_section('cors')
        return cors_config.get('allow_headers', ['*'])
    
    def is_cors_credentials_allowed(self) -> bool:
        """Check if CORS credentials are allowed"""
        cors_config = self.get_section('cors')
        return cors_config.get('allow_credentials', False)
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return self.get_section('logging')
    
    def get_ml_model_config(self, resource: str) -> Dict[str, Any]:
        """Get ML model configuration for specific resource"""
        ml_config = self.get_section('ml')
        return ml_config.get('models', {}).get(resource, {})
    
    def reload(self):
        """Reload configuration from file"""
        logger.info("Reloading configuration...")
        self._load_configuration()
    
    def to_dict(self) -> Dict[str, Any]:
        """Return entire configuration as dictionary"""
        return self.config_data.copy()

# Global configuration instance
config_loader = ConfigLoader()
