from app.api.routes import router

from app.core.config import settings

from app.core.database import initialize_database, create_tables

from app.core.security import add_security_headers

from app.core.scheduler import background_collector

from app.ml.enhanced_predictor import enhanced_predictor

from app.ml.anomaly_detector import anomaly_detector

import logging

import os

import uuid

from datetime import datetime

from dotenv import load_dotenv

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

import uvicorn



# Load environment variables from .env file

load_dotenv()



# Configure logging with environment variables

log_level = os.getenv('LOG_LEVEL', 'INFO')

log_format = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

enable_console = os.getenv('ENABLE_CONSOLE_LOGGING', 'true').lower() == 'true'

enable_file = os.getenv('ENABLE_FILE_LOGGING', 'false').lower() == 'true'



# Configure logging

if enable_console:

    logging.basicConfig(

        level=getattr(logging, log_level),

        format=log_format

    )



logger = logging.getLogger(__name__)



# Initialize database and create tables

try:

    initialize_database()

    # Create all database tables

    create_tables()

    logger.info("Database tables created successfully")

except Exception as e:

    logger.error(f"Database initialization failed: {e}")

app = FastAPI(

    title="AI Database Performance Optimizer Pro",

    description="Production-grade AI-powered database performance monitoring and optimization system with anomaly detection",

    version="2.0.0",

    docs_url="/docs",

    redoc_url="/redoc"

)



# Add CORS middleware with enhanced security

app.add_middleware(

    CORSMiddleware,

    allow_origins=settings.cors_origins,

    allow_credentials=settings.cors_allow_credentials,

    allow_methods=settings.cors_methods,

    allow_headers=settings.cors_headers,

)



# Add security headers middleware

app.middleware("http")(add_security_headers)



# Enhanced startup event

@app.on_event("startup")

async def startup_event():

    """Enhanced startup with ML and background collection initialization"""

    logger.info("Starting AI Database Performance Optimizer Pro...")

    

    try:

        # Initialize database

        initialize_database()

        create_tables()

        logger.info("Database initialized successfully")

        

        # Initialize enhanced ML systems

        logger.info("Initializing enhanced ML systems...")

        

        # Load historical data and train anomaly detector

        try:

            if anomaly_detector.load_historical_data(hours_back=24):

                anomaly_detector.train_models()

                logger.info("Anomaly detection models trained successfully")

            else:

                logger.warning("Insufficient data for anomaly detection, will use rolling statistics only")

        except Exception as e:

            logger.error(f"Failed to initialize anomaly detection: {e}")

        

        # Initialize enhanced predictor

        try:

            model_info = enhanced_predictor.get_model_info()

            trained_models = sum(1 for info in model_info.values() if info.get('status') != 'not_trained')

            logger.info(f"Enhanced ML predictor initialized: {trained_models}/{len(model_info)} models trained")

        except Exception as e:

            logger.error(f"Failed to initialize enhanced predictor: {e}")

        

        # Initialize background data collection

        if os.getenv('ENABLE_BACKGROUND_COLLECTION', 'true').lower() == 'true':

            try:

                collection_interval = int(os.getenv('COLLECTION_INTERVAL', '10'))

                background_collector.collection_interval = collection_interval

                background_collector.start()

                logger.info(f"Background data collection started with {collection_interval}s interval")

            except Exception as e:

                logger.error(f"Failed to start background collection: {e}")

        else:

            logger.info("Background collection disabled")

        

        logger.info("AI Database Performance Optimizer Pro started successfully")

        

    except Exception as e:

        logger.error(f"Startup failed: {e}")

        raise



# Enhanced shutdown event

@app.on_event("shutdown")

async def shutdown_event():

    """Enhanced shutdown with proper cleanup"""

    logger.info("Shutting down AI Database Performance Optimizer Pro...")

    

    try:

        # Stop background collection

        if background_collector.is_running:

            background_collector.stop()

            logger.info("Background data collection stopped")

        

        logger.info("AI Database Performance Optimizer Pro shutdown complete")

        

    except Exception as e:

        logger.error(f"Shutdown error: {e}")



# Include enhanced API routes

app.include_router(router, prefix="/api/v1", tags=["database-performance"])



# Enhanced system status endpoint

@app.get("/system/status")

async def get_system_status():

    """Get comprehensive system status"""

    try:

        # Get background collector status

        collector_status = background_collector.get_status()

        

        # Get ML system status

        model_info = enhanced_predictor.get_model_info()

        anomaly_summary = anomaly_detector.get_anomaly_summary()

        

        return {

            "status": "healthy",

            "version": "2.0.0",

            "timestamp": datetime.now().isoformat(),

            "components": {

                "database": {

                    "status": "connected",

                    "type": "sqlite"  # Could be enhanced to show actual DB type

                },

                "ml_system": {

                    "models_trained": sum(1 for info in model_info.values() if info.get('status') != 'not_trained'),

                    "total_models": len(model_info),

                    "anomaly_detector": {

                        "models_trained": sum(anomaly_summary.get("model_status", {}).values()),

                        "total_models": len(anomaly_summary.get("model_status", {}))

                    }

                },

                "background_collector": collector_status,

                "api": {

                    "status": "running",

                    "endpoints": len(router.routes)

                }

            }

        }

    except Exception as e:

        logger.error(f"System status check failed: {e}")

        return {

            "status": "error",

            "error": str(e),

            "timestamp": datetime.now().isoformat()

        }



# Enhanced health check endpoint

@app.get("/health")

async def enhanced_health_check():

    """Enhanced health check with component status"""

    try:

        # Check database connection

        from app.core.database import test_connection

        db_status = test_connection()

        database_status = "connected" if db_status else "disconnected"

        

        # Check Redis cache status

        try:

            from app.core.redis_cache import cache

            redis_status = cache.health_check()

            cache_status = "working" if redis_status else "failed"

        except Exception as e:

            logger.warning(f"Redis health check failed: {e}")

            cache_status = "failed"

        

        # Check ML model loaded status

        try:

            model_info = enhanced_predictor.get_model_info()

            ml_healthy = any(info.get('status') != 'not_trained' for info in model_info.values())

            ml_model_status = "loaded" if ml_healthy else "not_loaded"

        except Exception as e:

            logger.warning(f"ML model health check failed: {e}")

            ml_model_status = "not_loaded"

        

        # Determine overall status

        overall_status = "ok"

        if not db_status or not redis_status or not ml_healthy:

            overall_status = "degraded"

        if not db_status and not redis_status:

            overall_status = "error"

        

        return {

            "status": overall_status,

            "database": database_status,

            "cache": cache_status,

            "ml_model": ml_model_status

        }

    except Exception as e:

        logger.error(f"Health check failed: {e}")

        return {

            "status": "error",

            "database": "disconnected",

            "cache": "failed",

            "ml_model": "not_loaded"

        }



# Add request logging middleware with performance tracking and UUID tracing

@app.middleware("http")

async def log_requests(request, call_next):

    """Log each API request with performance tracking and request tracing"""

    # Generate unique request ID for tracing

    request_id = str(uuid.uuid4())

    start_time = datetime.now()

    

    # Add request ID to request state for downstream use

    request.state.request_id = request_id

    

    # Log request start with tracing ID

    logger.info(f"API Request START [{request_id}]: {request.method} {request.url.path}")

    

    try:

        # Process request

        response = await call_next(request)

        

        # Calculate response time

        end_time = datetime.now()

        response_time = (end_time - start_time).total_seconds()

        

        # Log response success with performance metrics and tracing ID

        logger.info(f"API Request SUCCESS [{request_id}]: {request.method} {request.url.path} - {response_time:.3f}s - Status: {response.status_code}")

        

        # Add request tracing header

        response.headers["X-Request-ID"] = request_id

        

        # Add performance headers

        response.headers["X-Response-Time"] = f"{response_time:.3f}"

        response.headers["X-Request-ID"] = str(start_time.timestamp())

        

        return response

        

    except Exception as e:

        end_time = datetime.now()

        response_time = (end_time - start_time).total_seconds()

        

        # Log error with performance metrics

        logger.error(f"API Request ERROR: {request.method} {request.url.path} - {response_time:.3f}s - Error: {str(e)}")

        raise



# Root endpoint with system information

@app.get("/")

async def root():

    """Root endpoint with system information"""

    return {

        "name": "AI Database Performance Optimizer Pro",

        "version": "2.0.0",

        "description": "Production-grade AI-powered database performance monitoring and optimization system",

        "features": [

            "Real-time system monitoring",

            "ML-powered anomaly detection",

            "Enhanced predictions with confidence scoring",

            "Advanced query insights",

            "Background data collection",

            "API key authentication",

            "Rate limiting",

            "Time-series analytics"

        ],

        "endpoints": {

            "health": "/health",

            "system_status": "/system/status",

            "api_docs": "/docs",

            "metrics": "/api/v1/metrics",

            "predictions": "/api/v1/predictions",

            "anomaly_status": "/api/v1/anomaly/status",

            "query_insights": "/api/v1/queries/insights",

            "enhanced_metrics": "/api/v1/enhanced/metrics/history"

        },

        "timestamp": datetime.now().isoformat()

    }



# Info endpoint with detailed system information

@app.get("/info")

async def get_info():

    """Get detailed system information"""

    try:

        return {

            "system": {

                "name": "AI Database Performance Optimizer Pro",

                "version": "2.0.0",

                "environment": os.getenv('ENVIRONMENT', 'development'),

                "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",

                "uptime": "N/A"  # Could be enhanced to track actual uptime

            },

            "features": {

                "monitoring": {

                    "real_time": True,

                    "historical_data": True,

                    "background_collection": background_collector.is_running

                },

                "machine_learning": {

                    "anomaly_detection": True,

                    "resource_prediction": True,

                    "confidence_scoring": True,

                    "feature_importance": True

                },

                "security": {

                    "api_key_auth": True,

                    "rate_limiting": True,

                    "security_headers": True

                },

                "analytics": {

                    "time_series": True,

                    "query_insights": True,

                    "performance_metrics": True

                }

            },

            "configuration": {

                "collection_interval": background_collector.collection_interval,

                "rate_limit_per_minute": os.getenv('RATE_LIMIT_PER_MINUTE', '60'),

                "cors_enabled": True,

                "logging_level": os.getenv('LOG_LEVEL', 'INFO')

            },

            "timestamp": datetime.now().isoformat()

        }

    except Exception as e:

        logger.error(f"Info endpoint failed: {e}")

        return {"error": str(e), "timestamp": datetime.now().isoformat()}



if __name__ == "__main__":

    # Enhanced main execution with configuration

    import os

    

    host = os.getenv('API_HOST', '0.0.0.0')

    port = int(os.getenv('API_PORT', '8000'))

    workers = int(os.getenv('API_WORKERS', '1'))

    reload = os.getenv('API_RELOAD', 'false').lower() == 'true'

    

    logger.info(f"Starting AI Database Performance Optimizer Pro on {host}:{port}")

    

    # Run with uvicorn

    uvicorn.run(

        "main:app",

        host=host,

        port=port,

        workers=workers,

        reload=reload,

        log_level=os.getenv('LOG_LEVEL', 'info').lower(),

        access_log=True

    )



@app.get("/")

async def root():

    """Root endpoint"""

    return {

        "message": "AI Database Performance Optimizer API",

        "version": "1.0.0",

        "docs": "/docs",

        "health": "/api/v1/health"

    }



@app.get("/info")

async def info():

    """Application information"""

    return {

        "name": "AI Database Performance Optimizer",

        "description": "AI-powered database performance monitoring and optimization system",

        "version": "1.0.0",

        "database_type": settings.db_type,

        "monitoring_interval": settings.monitoring_interval,

        "slow_query_threshold": settings.slow_query_threshold

    }

