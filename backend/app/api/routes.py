from datetime import datetime, timedelta

import logging

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.orm import Session

from sqlalchemy import text

from typing import Dict, Optional, Any

from concurrent.futures import ThreadPoolExecutor

from app.core.database import get_db, SessionLocal

from app.core.security import security_check

from app.monitoring.db_monitor import RealDatabaseMonitor

from app.analysis.query_analyzer import RealQueryAnalyzer

from app.ml.predictor import RealResourcePredictor

from app.ml.enhanced_predictor import enhanced_predictor

from app.ml.anomaly_detector import anomaly_detector

from app.recommendations.index_advisor import RealIndexAdvisor

from app.core.pipeline_integration import pipeline_integrator

from .schemas import (

    QueryExplainRequest, IndexAnalysisRequest, validate_time_range,

    validate_limit, validate_database_name

)



logger = logging.getLogger(__name__)



router = APIRouter()



# Initialize components

monitor = RealDatabaseMonitor()

analyzer = RealQueryAnalyzer()

predictor = RealResourcePredictor()

advisor = RealIndexAdvisor()



# Non-blocking ML predictions executor

ml_executor = ThreadPoolExecutor(max_workers=2)



def degraded_response(reason: str, prediction: Any = None, additional_data: Dict = None) -> Dict[str, Any]:

    """Standardized degraded mode response - VERY IMPORTANT"""

    response = {

        "status": "degraded",

        "reason": reason,

        "prediction": prediction,

        "timestamp": datetime.now().isoformat()

    }

    

    if additional_data:

        response.update(additional_data)

    

    return response



@router.get("/pipeline/run")

async def run_pipeline(sample_query: Optional[str] = None) -> Dict[str, Any]:

    """Run complete pipeline and return integrated data"""

    try:

        # Use pipeline integrator for end-to-end data flow

        result = pipeline_integrator.run_full_pipeline(sample_query)

        

        if result.get('status') == 'success':

            return {

                "status": "success",

                "data": result.get('pipeline_data', {}),

                "components": result.get('components', {}),

                "execution_time": result.get('execution_time', 0)

            }

        else:

            return {

                "status": "error",

                "error": result.get('error', 'Unknown pipeline error'),

                "timestamp": datetime.now().isoformat()

            }

        

    except Exception as e:

        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {str(e)}")



@router.get("/metrics")

async def get_current_metrics(

    security_info: Dict[str, Any] = Depends(security_check)

) -> Dict[str, Any]:

    """Get current database performance metrics with anomaly detection"""

    try:

        request_id = str(uuid.uuid4())

        logger.info(f"[{request_id}] Request received: Collecting metrics for client: {security_info.get('api_key_name', 'anonymous')}")

        

        # Get real system metrics with timeout protection

        try:

            system_metrics = monitor.get_system_metrics()

            logger.info("Real system metrics collected successfully")

        except Exception as e:

            logger.error(f"Failed to collect system metrics: {e}")

            raise HTTPException(status_code=500, detail=f"System metrics collection failed: {str(e)}")

        

        # Try to get database metrics (may fail without database)

        try:

            db_metrics = monitor.get_database_metrics()

            logger.info("Database metrics collected successfully")

        except Exception as e:

            logger.warning(f"Database metrics failed: {e}")

            db_metrics = {

                "status": "error",

                "error": str(e),

                "message": "Database not configured or not connected"

            }

        

        # Handle case where no real metrics available (never return fake "success")

        if not system_metrics or ('cpu' not in system_metrics and 'cpu_percent' not in system_metrics):

            logger.warning("No real system metrics available, returning degraded response")

            return degraded_response(
                "monitoring_unavailable",
                prediction=None,
                additional_data={
                    "data": {
                        "system_metrics": None,
                        "database_metrics": db_metrics,
                        "timestamp": datetime.now().isoformat(),
                        "data_source": "monitoring_unavailable"
                    }
                }
            )

        

        # Flatten nested metrics structure for API response

        flattened_metrics = {

            "cpu_percent": system_metrics.get('cpu', {}).get('cpu_percent', 0),

            "memory_percent": system_metrics.get('memory', {}).get('virtual_percent', 0),

            "disk_percent": system_metrics.get('disk', {}).get('disk_percent', 0),

            "connections": system_metrics.get('network', {}).get('connections_count', 0),

            "queries_per_second": system_metrics.get('queries_per_second', 0),

            "slow_queries": system_metrics.get('slow_queries', 0),

            "timestamp": system_metrics.get('timestamp', datetime.now().isoformat()),

            "collection_time": system_metrics.get('collection_time', 0),

            "data_source": system_metrics.get('data_source', 'psutil_monitoring')

        }

        

        # Perform anomaly detection on current metrics

        current_metrics_for_anomaly = {

            'cpu_usage': flattened_metrics['cpu_percent'],

            'memory_usage': flattened_metrics['memory_percent'],

            'disk_usage': flattened_metrics['disk_percent'],

            'queries_per_second': flattened_metrics['queries_per_second']

        }

        

        anomaly_results = anomaly_detector.detect_anomalies(current_metrics_for_anomaly)

        

        return {

            "status": "success",

            "data": {

                "system_metrics": flattened_metrics,

                "database_metrics": db_metrics,

                "anomaly_detection": anomaly_results,

                "timestamp": datetime.now().isoformat(),

                "data_source": "real_system_monitoring",

                "client_info": {

                    "authenticated": security_info.get("authenticated", False),

                    "api_key_name": security_info.get("api_key_name", "anonymous")

                }

            }

        }

        

    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"Metrics endpoint failed: {e}")

        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")



@router.get("/metrics/history")

async def get_metrics_history(

    hours: int = Query(default=24, ge=1, le=720, description="Hours of history to retrieve (1-720)"),

    db: Session = Depends(get_db)

) -> Dict[str, Any]:

    """Get historical metrics"""

    try:

        # Validate input

        hours = validate_time_range(hours)

        

        cutoff_time = datetime.now() - timedelta(hours=hours)

        

        # Parameterized query - SQL injection safe

        query = text("""

            SELECT 

                timestamp,

                cpu_usage,

                memory_usage,

                disk_usage,

                connections,

                queries_per_second,

                slow_queries

            FROM database_metrics 

            WHERE timestamp > :cutoff_time

            ORDER BY timestamp ASC

        """)

        

        result = db.execute(query, {"cutoff_time": cutoff_time})

        

        metrics = []

        for row in result:

            metrics.append({

                "timestamp": row[0].isoformat(),

                "cpu_usage": row[1],

                "memory_usage": row[2],

                "disk_usage": row[3],

                "connections": row[4],

                "queries_per_second": row[5],

                "slow_queries": row[6]

            })

        

        return {

            "status": "success",

            "data": metrics,

            "count": len(metrics)

        }

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))



@router.get("/queries/slow")

async def get_slow_queries(

    limit: int = Query(default=50, ge=1, le=1000, description="Maximum number of queries to return (1-1000)"),

    hours: int = Query(default=24, ge=1, le=168, description="Hours of history to search (1-168)"),

    db: Session = Depends(get_db)

) -> Dict[str, Any]:

    """Get slow queries"""

    try:

        # Validate inputs

        limit = validate_limit(limit, default=50, max_limit=1000)

        hours = validate_time_range(hours)

        

        cutoff_time = datetime.now() - timedelta(hours=hours)

        

        # Parameterized query - SQL injection safe

        query = text("""

            SELECT 

                query_text,

                execution_time,

                rows_examined,

                rows_returned,

                database_name,

                timestamp,

                user,

                host

            FROM query_logs 

            WHERE is_slow = True 

            AND timestamp > :cutoff_time

            ORDER BY execution_time DESC

            LIMIT :limit

        """)

        

        result = db.execute(query, {"cutoff_time": cutoff_time, "limit": limit})

        

        queries = []

        for row in result:

            queries.append({

                "query_text": row[0],

                "execution_time": row[1],

                "rows_examined": row[2],

                "rows_returned": row[3],

                "database_name": row[4],

                "timestamp": row[5].isoformat(),

                "user": row[6],

                "host": row[7]

            })

        

        return {

            "status": "success",

            "data": queries,

            "count": len(queries)

        }

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))



@router.get("/queries/analysis")

async def get_query_analysis(

    hours: int = Query(default=24, ge=1, le=168, description="Hours of history to analyze (1-168)"),

    db: Session = Depends(get_db)

) -> Dict[str, Any]:

    """Get query analysis summary"""

    try:

        # Validate input

        hours = validate_time_range(hours)

        

        cutoff_time = datetime.now() - timedelta(hours=hours)

        

        # Parameterized query - SQL injection safe

        query = text("""

            SELECT 

                query_text,

                execution_time,

                rows_examined,

                rows_returned,

                database_name,

                is_slow,

                timestamp

            FROM query_logs 

            WHERE timestamp > :cutoff_time

        """)

        

        result = db.execute(query, {"cutoff_time": cutoff_time})

        

        queries = []

        for row in result:

            queries.append({

                "query_text": row[0],

                "execution_time": row[1],

                "rows_examined": row[2],

                "rows_returned": row[3],

                "database_name": row[4],

                "is_slow": row[5],

                "timestamp": row[6]

            })

        

        analysis = analyzer.analyze_query_patterns(queries)

        

        return {

            "status": "success",

            "data": analysis

        }

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))



@router.post("/queries/explain")

async def explain_query(

    query_request: QueryExplainRequest,

    db: Session = Depends(get_db)

) -> Dict[str, Any]:

    """Explain query execution plan"""

    try:

        # Pydantic validation handles input validation automatically

        query = query_request.query

        database = query_request.database

        

        execution_plan = analyzer.get_query_execution_plan(query)

        optimizations = analyzer.suggest_query_optimizations(query, execution_plan)

        

        return {

            "status": "success",

            "data": {

                "execution_plan": execution_plan,

                "optimizations": optimizations

            }

        }

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))

@router.get("/predictions")
async def get_resource_predictions(

    hours_ahead: int = Query(default=24, ge=1, le=168, description="Hours ahead for prediction (1-168)"),

    security_info: Dict[str, Any] = Depends(security_check),

    db: Session = Depends(get_db)

) -> Dict[str, Any]:

    """Get enhanced resource usage predictions with anomaly detection"""

    

    try:

        logger.info(f"Generating enhanced predictions for client: {security_info.get('api_key_name', 'anonymous')}")

        

        # Validate input

        hours_ahead = validate_time_range(hours_ahead)

        

        # Use enhanced predictor with anomaly detection (NON-BLOCKING)

        try:

            # NON-BLOCKING: Submit ML prediction to thread pool

            future = ml_executor.submit(enhanced_predictor.predict_with_anomaly_detection)

            

            # Get result with timeout fallback

            try:

                predictions = future.result(timeout=2)  # 2 second timeout

            except Exception:

                logger.warning("ML prediction timeout, using fallback")

                return degraded_response("ml_timeout", None)

            

            if not predictions:

                logger.error("No predictions generated by enhanced predictor")

                return degraded_response("ml_no_predictions", None, {

                    "error": "Enhanced prediction system unavailable"

                })

                

        except Exception as e:

            logger.error(f"Enhanced prediction failed: {e}")

            return degraded_response("ml_failure", None, {

                "error": f"Enhanced prediction failed: {str(e)}"

            })

        

        # Format predictions for API response

        formatted_predictions = {}

        for resource, prediction_result in predictions.items():

            formatted_predictions[resource] = {

                "predicted_usage": round(prediction_result.predicted_usage, 2),

                "confidence": round(prediction_result.confidence, 3),

                "trend": prediction_result.trend,

                "anomaly_detected": prediction_result.anomaly_detected,

                "anomaly_info": prediction_result.anomaly_info,

                "feature_importance": prediction_result.feature_importance,

                "prediction_horizon": prediction_result.prediction_horizon,

                "model_version": prediction_result.model_version,

                "training_samples": prediction_result.training_samples

            }

        

        # Get model information

        model_info = enhanced_predictor.get_model_info()

        

        return {

            "status": "success",

            "data": {

                "predictions": formatted_predictions,

                "model_info": model_info,

                "prediction_horizon": hours_ahead,

                "timestamp": datetime.now().isoformat(),

                "data_source": "enhanced_ml_predictions",

                "client_info": {

                    "authenticated": security_info.get("authenticated", False),

                    "api_key_name": security_info.get("api_key_name", "anonymous")

                }

            }

        }

    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"Unexpected error in predictions endpoint: {e}")

        return {

            "status": "error",

            "error": f"Unexpected error: {str(e)}",

            "error_type": "unexpected_error",

            "timestamp": datetime.now().isoformat()

        }



@router.get("/enhanced/metrics/history")

async def get_enhanced_metrics_history(

    hours: int = Query(default=24, ge=1, le=168, description="Hours of history to retrieve (1-168)"),

    security_info: Dict[str, Any] = Depends(security_check),

    db: Session = Depends(get_db)

):

    """Get enhanced time-series metrics with anomaly detection"""

    try:

        # Validate input

        hours = validate_time_range(hours)

        

        cutoff_time = datetime.now() - timedelta(hours=hours)

        

        # Enhanced query with more data points for time-series

        query = text("""

            SELECT 

                timestamp,

                cpu_usage,

                memory_usage,

                disk_usage,

                connections,

                queries_per_second,

                slow_queries

            FROM database_metrics 

            WHERE timestamp > :cutoff_time

            ORDER BY timestamp ASC

        """)

        

        result = db.execute(query, {"cutoff_time": cutoff_time})

        

        metrics = []

        for row in result:

            metrics.append({

                "timestamp": row[0].isoformat(),

                "cpu_usage": row[1],

                "memory_usage": row[2],

                "disk_usage": row[3],

                "connections": row[4],

                "queries_per_second": row[5],

                "slow_queries": row[6]

            })

        

        # Perform anomaly detection on historical data

        anomalies_in_period = []

        if metrics:

            for metric_point in metrics:

                current_metrics = {

                    'cpu_usage': metric_point['cpu_usage'],

                    'memory_usage': metric_point['memory_usage'],

                    'disk_usage': metric_point['disk_usage'],

                    'queries_per_second': metric_point['queries_per_second']

                }

                

                anomaly_result = anomaly_detector.detect_anomalies(current_metrics)

                if anomaly_result.get('has_anomalies'):

                    anomalies_in_period.append({

                        "timestamp": metric_point['timestamp'],

                        "anomalies": anomaly_result['anomalies']

                    })

        

        return {

            "status": "success",

            "data": {

                "metrics": metrics,

                "anomalies": anomalies_in_period,

                "period_hours": hours,

                "total_points": len(metrics),

                "anomaly_count": len(anomalies_in_period),

                "data_quality": {

                    "expected_points": hours * 6,  # Assuming 10-minute intervals

                    "actual_points": len(metrics),

                    "completeness": len(metrics) / (hours * 6) if hours > 0 else 0

                }

            },

            "client_info": {

                "authenticated": security_info.get("authenticated", False),

                "api_key_name": security_info.get("api_key_name", "anonymous")

            }

        }

    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"Enhanced metrics history failed: {e}")

        raise HTTPException(status_code=500, detail=str(e))



@router.get("/queries/insights")

async def get_query_insights(

    hours_back: int = Query(default=24, ge=1, le=168, description="Hours of history to analyze (1-168)"),

    security_info: Dict[str, Any] = Depends(security_check),

    db: Session = Depends(get_db)

):

    """Get advanced database query insights"""

    try:

        # Validate input

        hours_back = validate_time_range(hours_back)

        

        cutoff_time = datetime.now() - timedelta(hours=hours_back)

        

        # Get comprehensive query analysis

        insights_query = text("""

            SELECT 

                query_text,

                execution_time,

                rows_examined,

                rows_returned,

                database_name,

                timestamp,

                user,

                host,

                COUNT(*) as frequency,

                AVG(execution_time) as avg_execution_time,

                MAX(execution_time) as max_execution_time,

                SUM(rows_examined) as total_rows_examined,

                SUM(rows_returned) as total_rows_returned

            FROM query_logs 

            WHERE timestamp > :cutoff_time

            AND query_text IS NOT NULL

            AND query_text != ''

            GROUP BY 

                LEFT(query_text, 200),

                database_name,

                user,

                host

            HAVING COUNT(*) >= 1

            ORDER BY frequency DESC, avg_execution_time DESC

            LIMIT 100

        """)

        

        result = db.execute(insights_query, {"cutoff_time": cutoff_time})

        

        insights = []

        slow_queries = []

        frequent_queries = []

        inefficient_queries = []

        

        for row in result:

            query_insight = {

                "query_text": row[0][:200] + "..." if len(row[0]) > 200 else row[0],

                "execution_time": float(row[1]),

                "rows_examined": int(row[2]) if row[2] else 0,

                "rows_returned": int(row[3]) if row[3] else 0,

                "database_name": row[4] or 'unknown',

                "timestamp": row[5].isoformat() if row[5] else None,

                "user": row[6] or 'unknown',

                "host": row[7] or 'unknown',

                "frequency": int(row[8]),

                "avg_execution_time": float(row[9]),

                "max_execution_time": float(row[10]),

                "total_rows_examined": int(row[11]) if row[11] else 0,

                "total_rows_returned": int(row[12]) if row[12] else 0,

                "efficiency_ratio": (int(row[3]) if row[3] else 0) / (int(row[2]) if row[2] and row[2] > 0 else 1)

            }

            

            insights.append(query_insight)

            

            # Categorize queries

            if query_insight["avg_execution_time"] > 1.0:  # Slow queries

                slow_queries.append(query_insight)

            

            if query_insight["frequency"] > 10:  # Frequent queries

                frequent_queries.append(query_insight)

            

            if query_insight["efficiency_ratio"] < 0.1:  # Inefficient queries

                inefficient_queries.append(query_insight)

        

        # Calculate summary statistics

        total_queries = len(insights)

        avg_execution_time = sum(q["avg_execution_time"] for q in insights) / total_queries if total_queries > 0 else 0

        total_frequency = sum(q["frequency"] for q in insights)

        

        return {

            "status": "success",

            "data": {

                "summary": {

                    "total_unique_queries": total_queries,

                    "total_executions": total_frequency,

                    "avg_execution_time": round(avg_execution_time, 3),

                    "analysis_period_hours": hours_back,

                    "slow_query_count": len(slow_queries),

                    "frequent_query_count": len(frequent_queries),

                    "inefficient_query_count": len(inefficient_queries)

                },

                "top_slow_queries": sorted(slow_queries, key=lambda x: x["avg_execution_time"], reverse=True)[:10],

                "top_frequent_queries": sorted(frequent_queries, key=lambda x: x["frequency"], reverse=True)[:10],

                "top_inefficient_queries": sorted(inefficient_queries, key=lambda x: x["efficiency_ratio"])[:10],

                "all_insights": insights

            },

            "client_info": {

                "authenticated": security_info.get("authenticated", False),

                "api_key_name": security_info.get("api_key_name", "anonymous")

            }

        }

    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"Query insights failed: {e}")

        raise HTTPException(status_code=500, detail=str(e))



@router.get("/anomaly/status")

async def get_anomaly_status(

    security_info: Dict[str, Any] = Depends(security_check)

):

    """Get current anomaly detection status and summary"""

    try:

        # Get anomaly detector summary

        anomaly_summary = anomaly_detector.get_anomaly_summary()

        

        # Get current metrics for immediate anomaly check

        try:

            system_metrics = monitor.get_system_metrics()

            current_metrics = {

                'cpu_usage': system_metrics.get('cpu', {}).get('cpu_percent', 0),

                'memory_usage': system_metrics.get('memory', {}).get('virtual_percent', 0),

                'disk_usage': system_metrics.get('disk', {}).get('disk_percent', 0),

                'queries_per_second': system_metrics.get('queries_per_second', 0)

            }

            

            current_anomalies = anomaly_detector.detect_anomalies(current_metrics)

            

        except Exception as e:

            logger.error(f"Failed to get current metrics for anomaly check: {e}")

            current_anomalies = {"has_anomalies": False, "error": str(e)}

        

        return {

            "status": "success",

            "data": {

                "current_anomalies": current_anomalies,

                "anomaly_summary": anomaly_summary,

                "detector_status": {

                    "models_trained": anomaly_summary.get("model_status", {}),

                    "data_points_available": anomaly_summary.get("data_points_trained_on", {}),

                    "detection_methods": {

                        "rolling_statistics": True,

                        "isolation_forest": any(anomaly_summary.get("model_status", {}).values())

                    }

                }

            },

            "client_info": {

                "authenticated": security_info.get("authenticated", False),

                "api_key_name": security_info.get("api_key_name", "anonymous")

            }

        }

    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"Anomaly status failed: {e}")

        raise HTTPException(status_code=500, detail=str(e))



@router.get("/predictions/history")

async def get_prediction_history(

    hours: int = Query(default=168, ge=1, le=720, description="Hours of history to retrieve (1-720)"),

    db: Session = Depends(get_db)

):

    """Get historical predictions"""

    try:

        # Validate input

        hours = validate_time_range(hours)

        

        cutoff_time = datetime.now() - timedelta(hours=hours)

        

        # Parameterized query - SQL injection safe

        query = text("""

            SELECT 

                timestamp,

                prediction_horizon,

                predicted_cpu,

                predicted_memory,

                predicted_disk,

                confidence_score,

                model_version

            FROM performance_predictions 

            WHERE timestamp > :cutoff_time

            ORDER BY timestamp DESC

        """)

        

        result = db.execute(query, {"cutoff_time": cutoff_time})

        

        predictions = []

        for row in result:

            predictions.append({

                "timestamp": row[0].isoformat(),

                "prediction_horizon": row[1],

                "predicted_cpu": row[2],

                "predicted_memory": row[3],

                "predicted_disk": row[4],

                "confidence_score": row[5],

                "model_version": row[6]

            })

        

        return {

            "status": "success",

            "data": predictions,

            "count": len(predictions)

        }

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))



@router.get("/recommendations/indexes")

async def get_index_recommendations(

    hours_back: int = Query(default=24, ge=1, le=168, description="Hours of history to analyze (1-168)"),

    db: Session = Depends(get_db)

):

    """Get index recommendations based on real system metrics"""

    try:

        logger.info("Generating rule-based recommendations from real system metrics...")

        

        # Validate input

        hours_back = validate_time_range(hours_back)

        

        # Get current system metrics

        try:

            system_metrics = monitor.get_system_metrics()

            logger.info("System metrics collected for recommendations")

        except Exception as e:

            logger.error(f"Failed to get system metrics: {e}")

            raise HTTPException(status_code=500, detail=f"Failed to collect system metrics: {str(e)}")

        

        # Extract key metrics from nested structure

        cpu_usage = float(system_metrics.get('cpu', {}).get('cpu_percent', 0))

        memory_usage = float(system_metrics.get('memory', {}).get('virtual_percent', 0))

        disk_usage = float(system_metrics.get('disk', {}).get('disk_percent', 0))

        connections = int(system_metrics.get('network', {}).get('connections_count', 0))

        slow_queries = int(system_metrics.get('slow_queries', 0))

        queries_per_second = int(system_metrics.get('queries_per_second', 0))

        

        logger.info(f"Metrics for recommendations: CPU={cpu_usage}%, Memory={memory_usage}%, Slow Queries={slow_queries}")

        

        # Generate rule-based recommendations

        recommendations = []

        

        # CPU-based recommendations

        if cpu_usage > 80:

            recommendations.append({

                "type": "index_optimization",

                "reason": f"High CPU usage detected ({cpu_usage:.1f}%). Adding proper indexes can reduce CPU load.",

                "confidence": min(0.9, 0.5 + (cpu_usage - 80) * 0.05),

                "priority": "high",

                "action": "Create indexes on frequently queried columns"

            })

        elif cpu_usage > 60:

            recommendations.append({

                "type": "query_optimization",

                "reason": f"Elevated CPU usage ({cpu_usage:.1f}%). Consider optimizing slow queries.",

                "confidence": 0.7,

                "priority": "medium",

                "action": "Review and optimize query execution plans"

            })

        

        # Memory-based recommendations

        if memory_usage > 85:

            recommendations.append({

                "type": "caching",

                "reason": f"High memory usage ({memory_usage:.1f}%). Implement caching to reduce memory pressure.",

                "confidence": min(0.9, 0.6 + (memory_usage - 85) * 0.04),

                "priority": "high",

                "action": "Implement query result caching and connection pooling"

            })

        elif memory_usage > 70:

            recommendations.append({

                "type": "memory_optimization",

                "reason": f"Moderate memory usage ({memory_usage:.1f}%). Monitor memory-intensive operations.",

                "confidence": 0.6,

                "priority": "low",

                "action": "Optimize memory allocation and reduce unnecessary data loading"

            })

        

        # Slow query recommendations

        if slow_queries > 10:

            recommendations.append({

                "type": "query_analysis",

                "reason": f"High number of slow queries ({slow_queries}). Immediate optimization required.",

                "confidence": min(0.95, 0.7 + slow_queries * 0.02),

                "priority": "critical",

                "action": "Analyze and optimize slow queries, add missing indexes"

            })

        elif slow_queries > 5:

            recommendations.append({

                "type": "index_review",

                "reason": f"Moderate slow query count ({slow_queries}). Review indexing strategy.",

                "confidence": 0.7,

                "priority": "medium",

                "action": "Review existing indexes and query patterns"

            })

        

        # Connection-based recommendations

        if connections > 200:

            recommendations.append({

                "type": "connection_pooling",

                "reason": f"High connection count ({connections}). Implement connection pooling.",

                "confidence": 0.8,

                "priority": "high",

                "action": "Configure connection pooling and optimize connection lifecycle"

            })

        

        # Query volume recommendations

        if queries_per_second > 100:

            recommendations.append({

                "type": "performance_tuning",

                "reason": f"High query volume ({queries_per_second} QPS). Consider database tuning.",

                "confidence": 0.75,

                "priority": "medium",

                "action": "Optimize database configuration for high throughput"

            })

        

        # Disk usage recommendations

        if disk_usage > 90:

            recommendations.append({

                "type": "storage_optimization",

                "reason": f"High disk usage ({disk_usage:.1f}%). Implement data archiving.",

                "confidence": 0.8,

                "priority": "high",

                "action": "Archive old data and implement data retention policies"

            })

        

        # Always provide at least one recommendation if none were generated

        if not recommendations:

            recommendations.append({

                "type": "monitoring",

                "reason": "System metrics are within acceptable ranges. Continue monitoring.",

                "confidence": 0.5,

                "priority": "info",

                "action": "Maintain current monitoring and optimization practices"

            })

        

        logger.info(f"Generated {len(recommendations)} recommendations")

        

        return {

            "status": "success",

            "data": recommendations,

            "count": len(recommendations),

            "analysis_status": "success",

            "queries_analyzed": slow_queries,

            "metrics_analyzed": {

                "cpu_usage": cpu_usage,

                "memory_usage": memory_usage,

                "disk_usage": disk_usage,

                "connections": connections,

                "slow_queries": slow_queries,

                "queries_per_second": queries_per_second

            },

            "data_source": "rule_based_analysis"

        }

    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"Recommendations endpoint failed: {e}")

        raise HTTPException(status_code=500, detail=str(e))



@router.post("/recommendations/analyze")

async def analyze_indexes(

    analysis_request: IndexAnalysisRequest,

    db: Session = Depends(get_db)

):

    """Analyze specific table for index recommendations"""

    try:

        # Pydantic validation handles input validation automatically

        table_name = analysis_request.table_name

        database_name = analysis_request.database_name

        min_queries = analysis_request.min_queries

        

        analysis = advisor.analyze_query_workload_for_table(table_name, database_name, min_queries)

        

        return {

            "status": "success",

            "data": analysis,

            "queries_analyzed": analysis.get('queries_analyzed', 0),

            "tables_analyzed": analysis.get('tables_analyzed', 0),

            "recommendations_count": len(analysis.get('recommendations', []))

        }

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))



@router.get("/indexes/existing")

async def get_existing_indexes(

    database_name: Optional[str] = Query(default=None, max_length=64, description="Database name to filter indexes"),

    db: Session = Depends(get_db)

):

    """Get existing indexes"""

    try:

        # Validate input

        database_name = validate_database_name(database_name)

        

        indexes = advisor.get_existing_indexes(database_name)

        

        return {

            "status": "success",

            "data": indexes

        }

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))



@router.get("/indexes/utilization")

async def get_index_utilization(

    database_name: Optional[str] = Query(default=None, max_length=64, description="Database name to filter utilization"),

    db: Session = Depends(get_db)

):

    """Get index utilization statistics"""

    try:

        # Validate input

        database_name = validate_database_name(database_name)

        

        # Check for SQL injection patterns

        dangerous_chars = ["'", '"', ';', '--', '/*', '*/', 'DROP', 'DELETE']

        db_name_upper = database_name.upper()

        for char in dangerous_chars:

            if char in db_name_upper:

                raise HTTPException(status_code=400, detail="Invalid database name")

        

        utilization = advisor.check_index_utilization(database_name)

        

        return {

            "status": "success",

            "data": utilization

        }

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))



@router.post("/monitoring/start")

async def start_monitoring():

    """Start monitoring service"""

    try:

        # Get monitoring summary

        summary = monitor.get_monitoring_summary()

        

        return {

            "status": "success",

            "data": summary,

            "message": "Monitoring data collected"

        }

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))



def _test_database_config() -> Dict[str, Any]:

    """Test database configuration"""

    try:

        from ..core.config import settings

        

        db_config = settings.get_section('database')

        safe_config = db_config.copy()

        if 'password' in safe_config:

            safe_config['password'] = '***' if safe_config['password'] else '(empty)'

        

        try:

            db_url = settings.database_url

            safe_url = db_url.replace(safe_config.get('password', ''), '***')

        except Exception as e:

            safe_url = f"Error: {e}"

        

        return {

            "status": "checked",

            "config": safe_config,

            "database_url": safe_url

        }

    except Exception as e:

        return {"error": str(e)}



def _test_database_connection() -> Dict[str, Any]:

    """Test database connection"""

    try:

        from ..core.config import settings

        

        connection_status = "not_configured"

        connection_details = {}

        db_config = settings.get_section('database')

        

        if SessionLocal is not None:

            try:

                with SessionLocal() as db:

                    # Test basic query

                    result = db.execute(text("SELECT 1 as test"))

                    test_value = result.fetchone()[0]

                    

                    if test_value == 1:

                        connection_status = "connected"

                        connection_details = {

                            "test_query": "SELECT 1",

                            "result": test_value,

                            "status": "success"

                        }

                    else:

                        connection_status = "failed"

                        connection_details = {

                            "test_query": "SELECT 1",

                            "result": test_value,

                            "status": "unexpected_result"

                        }

                        

                    # Test database-specific query

                    connection_details.update(_test_database_version(db, db_config))

                            

                    

            except Exception as e:

                connection_status = "failed"

                connection_details["error"] = str(e)

        

        return {

            "status": connection_status,

            "details": connection_details

        }

    except Exception as e:
        return {
            "status": "error",
            "details": {"error": str(e), "error_type": type(e).__name__},
            "timestamp": datetime.now().isoformat()
        }



def _test_database_version(db, db_config: Dict) -> Dict[str, Any]:

    """Test database version retrieval"""
    db_type = (db_config or {}).get("type")
    if not db_type:
        return {}

    try:
        if db_type == "mysql":
            result = db.execute(text("SELECT VERSION()"))
        elif db_type == "postgresql":
            result = db.execute(text("SELECT version()"))
        else:
            return {}

        row = result.fetchone()
        return {"database_version": row[0] if row else None}
    except Exception as e:
        return {"database_version_error": str(e), "error_type": type(e).__name__}



@router.get("/test/database/simple")

async def simple_database_test():

    """Simple database connection test"""

    try:

        if SessionLocal is None:

            return {

                "status": "failed",

                "message": "Database not initialized",

                "timestamp": datetime.now().isoformat()

            }

        

        try:

            with SessionLocal() as db:

                result = db.execute(text("SELECT 1"))

                test_value = result.fetchone()[0]

                

                return {

                    "status": "success",

                    "message": "Database connection successful",

                    "test_result": test_value,

                    "timestamp": datetime.now().isoformat()

                }

        except Exception as e:

            return {

                "status": "failed",

                "message": f"Database connection failed: {str(e)}",

                "timestamp": datetime.now().isoformat()

            }

                

    except Exception as e:

        return {

            "status": "error",

            "message": f"Test error: {str(e)}",

            "timestamp": datetime.now().isoformat()

        }



@router.get("/dashboard/summary")

async def get_dashboard_summary(db: Session = Depends(get_db)):

    """Get summary data for dashboard"""

    try:

        # Get current metrics

        current_metrics = monitor.get_system_metrics()

        db_metrics = monitor.get_database_metrics()

        

        # Get recent slow queries count - Parameterized query

        cutoff_time = datetime.now() - timedelta(hours=24)

        

        slow_query_count_query = text("""

            SELECT COUNT(*) FROM query_logs 

            WHERE is_slow = True 

            AND timestamp > :cutoff_time

        """)

        

        result = db.execute(slow_query_count_query, {"cutoff_time": cutoff_time})

        slow_queries_today = result.fetchone()[0]

        

        # Get total queries today - Parameterized query

        total_query_count_query = text("""

            SELECT COUNT(*) FROM query_logs 

            WHERE timestamp > :cutoff_time

        """)

        

        result = db.execute(total_query_count_query, {"cutoff_time": cutoff_time})

        total_queries_today = result.fetchone()[0]

        

        # Get integrated pipeline data

        try:

            # Run full pipeline for comprehensive dashboard data

            pipeline_data = pipeline_integrator.run_full_pipeline()

            

            # Extract component data for dashboard

            system_metrics = pipeline_data.get('metrics', {}).get('system', {})

            database_metrics = pipeline_data.get('metrics', {}).get('database', {})

            query_metrics = pipeline_data.get('metrics', {}).get('queries', {})

            ml_predictions = pipeline_data.get('predictions', {})

            recommendations = pipeline_data.get('recommendations', [])

            

            # Format predictions for dashboard

            latest_prediction = {}

            if ml_predictions and 'ml_prediction' in ml_predictions:

                pred_data = ml_predictions['ml_prediction']

                latest_prediction = {

                    'cpu_usage': {

                        'predicted_usage': pred_data.get('cpu_prediction', 0.0),

                        'confidence': pred_data.get('cpu_confidence', 0.0),

                        'model_type': pred_data.get('model_versions', {}).get('cpu', 'unknown')

                    },

                    'memory_usage': {

                        'predicted_usage': pred_data.get('memory_prediction', 0.0),

                        'confidence': pred_data.get('memory_confidence', 0.0),

                        'model_type': pred_data.get('model_versions', {}).get('memory', 'unknown')

                    },

                    'disk_usage': {

                        'predicted_usage': pred_data.get('disk_prediction', 0.0),

                        'confidence': pred_data.get('disk_confidence', 0.0),

                        'model_type': pred_data.get('model_versions', {}).get('disk', 'unknown')

                    }

                }

                        

        except Exception as e:

            logger.error(f"Failed to get pipeline data for dashboard: {e}")

            # Hard fail into degraded state (no hardcoded predictions)
            system_metrics = {}
            database_metrics = {}
            query_metrics = {}
            ml_predictions = {}
            recommendations = []
            latest_prediction = {}

        

        # Get recommendations summary

        recommendations_summary = advisor.get_recommendations_summary()

        

        summary = {

            "current_metrics": {**current_metrics, **db_metrics},

            "query_stats": {

                "slow_queries_today": slow_queries_today,

                "total_queries_today": total_queries_today,

                "slow_query_percentage": (slow_queries_today / total_queries_today * 100) if total_queries_today > 0 else 0

            },

            "predictions": latest_prediction,

            "recommendations": recommendations_summary

        }

        

        if not latest_prediction:
            return degraded_response(
                "pipeline_unavailable_for_dashboard",
                prediction=None,
                additional_data={"data": summary}
            )

        return {"status": "success", "data": summary}

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))



@router.get("/queries/top")

async def get_top_queries(

    limit: int = Query(default=10, ge=1, le=100, description="Maximum number of queries to return (1-100)"),

    hours: int = Query(default=24, ge=1, le=168, description="Hours of history to analyze (1-168)"),

    sort_by: str = Query(default="execution_time", description="Sort by field (execution_time, rows_examined, rows_returned, timestamp)"),

    db: Session = Depends(get_db)

):

    """Get top resource-intensive queries"""

    try:

        # Validate inputs

        limit = validate_limit(limit, default=10, max_limit=100)

        hours = validate_time_range(hours)

        

        # Validate sort_by parameter

        valid_sort_fields = ["execution_time", "rows_examined", "rows_returned", "timestamp"]

        if sort_by not in valid_sort_fields:

            raise HTTPException(

                status_code=400, 

                detail=f"sort_by must be one of: {', '.join(valid_sort_fields)}"

            )

        

        cutoff_time = datetime.now() - timedelta(hours=hours)

        

        query_template = f"""

            SELECT 

                query_text,

                execution_time,

                rows_examined,

                rows_returned,

                database_name,

                timestamp,

                user,

                host,

                is_slow

            FROM query_logs 

            WHERE timestamp > :cutoff_time

            ORDER BY {sort_by} DESC

            LIMIT :limit

        """

        query = text(query_template)

        

        result = db.execute(query, {"cutoff_time": cutoff_time, "limit": limit})

        

        queries = []

        for row in result:

            queries.append({

                "query_text": row[0],

                "execution_time": row[1],

                "rows_examined": row[2],

                "rows_returned": row[3],

                "database_name": row[4],

                "timestamp": row[5].isoformat(),

                "user": row[6],

                "host": row[7],

                "is_slow": row[8]

            })

        

        return {

            "status": "success",

            "data": queries,

            "count": len(queries),

            "sort_by": sort_by,

            "hours": hours

        }

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))



@router.get("/metrics/summary")

async def get_metrics_summary(

    hours: int = Query(default=24, ge=1, le=168, description="Hours of history to summarize (1-168)"),

    db: Session = Depends(get_db)

):

    """Get metrics summary statistics"""

    try:

        # Validate input

        hours = validate_time_range(hours)

        

        cutoff_time = datetime.now() - timedelta(hours=hours)

        

        # Parameterized query for aggregated metrics

        query = text("""

            SELECT 

                AVG(cpu_usage) as avg_cpu,

                MAX(cpu_usage) as max_cpu,

                MIN(cpu_usage) as min_cpu,

                AVG(memory_usage) as avg_memory,

                MAX(memory_usage) as max_memory,

                MIN(memory_usage) as min_memory,

                AVG(disk_usage) as avg_disk,

                MAX(disk_usage) as max_disk,

                MIN(disk_usage) as min_disk,

                AVG(connections) as avg_connections,

                MAX(connections) as max_connections,

                AVG(queries_per_second) as avg_qps,

                MAX(queries_per_second) as max_qps,

                COUNT(*) as sample_count

            FROM database_metrics 

            WHERE timestamp > :cutoff_time

        """)

        

        result = db.execute(query, {"cutoff_time": cutoff_time})

        row = result.fetchone()

        

        if row and row[12] > 0:  # sample_count > 0

            summary = {

                "cpu": {

                    "average": float(row[0]) if row[0] else 0,

                    "maximum": float(row[1]) if row[1] else 0,

                    "minimum": float(row[2]) if row[2] else 0

                },

                "memory": {

                    "average": float(row[3]) if row[3] else 0,

                    "maximum": float(row[4]) if row[4] else 0,

                    "minimum": float(row[5]) if row[5] else 0

                },

                "disk": {

                    "average": float(row[6]) if row[6] else 0,

                    "maximum": float(row[7]) if row[7] else 0,

                    "minimum": float(row[8]) if row[8] else 0

                },

                "connections": {

                    "average": float(row[9]) if row[9] else 0,

                    "maximum": float(row[10]) if row[10] else 0

                },

                "queries_per_second": {

                    "average": float(row[11]) if row[11] else 0,

                    "maximum": float(row[12]) if row[12] else 0

                },

                "sample_count": row[13],

                "hours_analyzed": hours

            }

        else:

            summary = {

                "error": "No data found for the specified time range",

                "hours_analyzed": hours

            }

        

        return {

            "status": "success",

            "data": summary

        }

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))



@router.get("/ping")

async def ping():

    """Simple ping endpoint for testing"""

    return {

        "status": "success",

        "message": "pong",

        "timestamp": datetime.now().isoformat()

    }



@router.get("/health")

async def health_check():

    """Health check endpoint - returns system, database, and ML status"""

    try:

        

        # Check database health

        try:

            from ..core.database import health_check as db_health_check

            db_health = db_health_check()

            db_status = "healthy" if db_health.get('status') == 'healthy' else "unhealthy"

            db_message = db_health.get('message', 'Unknown')

        except Exception as e:

            db_status = "error"

            db_message = str(e)

        

        # Check ML predictor status

        try:

            predictor = RealResourcePredictor()

            # Try to generate features to test ML pipeline

            features = predictor.generate_features_from_metrics()

            ml_status = "healthy"

            ml_message = "ML pipeline operational"

        except Exception as e:

            ml_status = "error"

            ml_message = str(e)

        

        # Check monitoring status

        try:

            monitor = RealDatabaseMonitor()

            metrics = monitor.get_system_metrics()

            monitoring_status = "healthy"

            monitoring_message = "System monitoring operational"

        except Exception as e:

            monitoring_status = "error"

            monitoring_message = str(e)

        

        # Overall system status

        overall_status = "healthy"

        if db_status == "error" or ml_status == "error" or monitoring_status == "error":

            overall_status = "degraded"

        

        return {

            "status": overall_status,

            "timestamp": datetime.now().isoformat(),

            "components": {

                "database": {

                    "status": db_status,

                    "message": db_message

                },

                "ml": {

                    "status": ml_status,

                    "message": ml_message

                },

                "monitoring": {

                    "status": monitoring_status,

                    "message": monitoring_message

                }

            }

        }

    except Exception as e:

        return {

            "status": "error",

            "timestamp": datetime.now().isoformat(),

            "error": str(e)

        }



@router.get("/metrics/last-records")

async def get_last_metrics_records(db: Session = Depends(get_db)):

    """Get last 10 records from database_metrics table"""

    try:

        query = text("""

            SELECT cpu_usage, memory_usage, disk_usage, connections, 

                   queries_per_second, slow_queries, timestamp

            FROM database_metrics 

            ORDER BY timestamp DESC 

            LIMIT 10

        """)

        

        result = db.execute(query)

        rows = result.fetchall()

        

        records = []

        for row in rows:

            records.append({

                "cpu_usage": float(row[0]) if row[0] else 0,

                "memory_usage": float(row[1]) if row[1] else 0,

                "disk_usage": float(row[2]) if row[2] else 0,

                "connections": int(row[3]) if row[3] else 0,

                "queries_per_second": float(row[4]) if row[4] else 0,

                "slow_queries": int(row[5]) if row[5] else 0,

                "timestamp": row[6].isoformat() if row[6] else None

            })

        

        return {

            "status": "success",

            "data": {

                "records": records,

                "count": len(records)

            }

        }

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))

