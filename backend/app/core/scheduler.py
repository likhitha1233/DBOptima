#!/usr/bin/env python3
"""
Production-grade Background Data Collection Scheduler
Uses APScheduler for continuous system metrics collection
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
from sqlalchemy import text
from ..core.database import SessionLocal
from ..monitoring.db_monitor import RealDatabaseMonitor
from ..ml.anomaly_detector import anomaly_detector

logger = logging.getLogger(__name__)

class BackgroundDataCollector:
    """Production-grade background data collection system"""
    
    def __init__(self, collection_interval: int = 10):
        self.collection_interval = collection_interval  # seconds
        self.scheduler = BackgroundScheduler()
        self.monitor = RealDatabaseMonitor()
        self.is_running = False
        self.collection_stats = {
            'total_collections': 0,
            'successful_collections': 0,
            'failed_collections': 0,
            'last_collection': None,
            'last_error': None,
            'avg_collection_time': 0.0,
            'start_time': None
        }
        self.collection_times = []
        
        # Configure scheduler
        self.scheduler.add_listener(self._job_executed_listener, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)
        self.scheduler.add_listener(self._job_missed_listener, EVENT_JOB_MISSED)
        
        logger.info(f"BackgroundDataCollector initialized with {collection_interval}s interval")
    
    def _job_executed_listener(self, event):
        """Handle successful job execution"""
        if event.job_id == 'collect_metrics':
            self.collection_stats['successful_collections'] += 1
            self.collection_stats['last_collection'] = datetime.now()
    
    def _job_error_listener(self, event):
        """Handle job execution errors"""
        if event.job_id == 'collect_metrics':
            self.collection_stats['failed_collections'] += 1
            self.collection_stats['last_error'] = str(event.exception)
            logger.error(f"Background collection failed: {event.exception}")
    
    def _job_missed_listener(self, event):
        """Handle missed job executions"""
        if event.job_id == 'collect_metrics':
            logger.warning(f"Background collection missed: {event}")
    
    def collect_system_metrics(self) -> bool:
        """Collect and store system metrics"""
        start_time = time.time()
        
        try:
            # Get system metrics
            system_metrics = self.monitor.get_system_metrics()
            
            if not system_metrics or system_metrics.get('status') == 'error':
                logger.error("Failed to collect system metrics")
                return False
            
            # Extract metrics for storage
            cpu_percent = system_metrics.get('cpu', {}).get('cpu_percent', 0)
            memory_percent = system_metrics.get('memory', {}).get('virtual_percent', 0)
            disk_percent = system_metrics.get('disk', {}).get('disk_percent', 0)
            connections = system_metrics.get('network', {}).get('connections_count', 0)
            queries_per_second = system_metrics.get('queries_per_second', 0)
            slow_queries = system_metrics.get('slow_queries', 0)
            
            # Store in database
            success = self._store_metrics({
                'cpu_usage': cpu_percent,
                'memory_usage': memory_percent,
                'disk_usage': disk_percent,
                'connections': connections,
                'queries_per_second': queries_per_second,
                'slow_queries': slow_queries,
                'timestamp': datetime.now()
            })
            
            if success:
                # Update collection statistics
                collection_time = time.time() - start_time
                self.collection_times.append(collection_time)
                
                # Keep only last 100 collection times for averaging
                if len(self.collection_times) > 100:
                    self.collection_times = self.collection_times[-100:]
                
                self.collection_stats['avg_collection_time'] = sum(self.collection_times) / len(self.collection_times)
                
                logger.debug(f"Metrics collected and stored in {collection_time:.3f}s")
                return True
            else:
                logger.error("Failed to store metrics in database")
                return False
                
        except Exception as e:
            logger.error(f"Error in collect_system_metrics: {e}")
            return False
    
    def _store_metrics(self, metrics_data: Dict[str, Any]) -> bool:
        """Store metrics in database with proper error handling"""
        try:
            with SessionLocal() as db:
                # Insert metrics using parameterized query
                query = text("""
                    INSERT INTO database_metrics 
                    (cpu_usage, memory_usage, disk_usage, connections, 
                     queries_per_second, slow_queries, timestamp)
                    VALUES 
                    (:cpu_usage, :memory_usage, :disk_usage, :connections,
                     :queries_per_second, :slow_queries, :timestamp)
                """)
                
                db.execute(query, metrics_data)
                db.commit()
                
                # Update anomaly detector with new data
                try:
                    current_metrics = {
                        'cpu_usage': metrics_data['cpu_usage'],
                        'memory_usage': metrics_data['memory_usage'],
                        'disk_usage': metrics_data['disk_usage'],
                        'queries_per_second': metrics_data['queries_per_second']
                    }
                    
                    # This will update the rolling window for anomaly detection
                    anomaly_detector.detect_anomalies(current_metrics)
                    
                except Exception as e:
                    logger.warning(f"Failed to update anomaly detector: {e}")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to store metrics: {e}")
            return False
    
    def start(self):
        """Start the background scheduler"""
        if self.is_running:
            logger.warning("Background collector is already running")
            return
        
        try:
            # Add the metrics collection job
            self.scheduler.add_job(
                func=self.collect_system_metrics,
                trigger=IntervalTrigger(seconds=self.collection_interval),
                id='collect_metrics',
                name='System Metrics Collection',
                max_instances=1,
                coalesce=True,
                misfire_grace_time=30
            )
            
            # Start the scheduler
            self.scheduler.start()
            self.is_running = True
            self.collection_stats['start_time'] = datetime.now()
            
            logger.info(f"Background data collection started with {self.collection_interval}s interval")
            
        except Exception as e:
            logger.error(f"Failed to start background collector: {e}")
            raise
    
    def stop(self):
        """Stop the background scheduler"""
        if not self.is_running:
            logger.warning("Background collector is not running")
            return
        
        try:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("Background data collection stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop background collector: {e}")
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Get collector status and statistics"""
        uptime = None
        if self.collection_stats['start_time']:
            uptime = (datetime.now() - self.collection_stats['start_time']).total_seconds()
        
        return {
            'is_running': self.is_running,
            'collection_interval': self.collection_interval,
            'collection_stats': {
                **self.collection_stats,
                'uptime_seconds': uptime,
                'success_rate': (
                    self.collection_stats['successful_collections'] / 
                    max(1, self.collection_stats['total_collections'])
                ) * 100
            },
            'scheduler_info': {
                'jobs_count': len(self.scheduler.get_jobs()),
                'next_run_time': self.scheduler.get_jobs()[0].next_run_time.isoformat() if self.scheduler.get_jobs() else None
            },
            'anomaly_detector_status': {
                'models_trained': sum(anomaly_detector.models_trained.values()),
                'total_models': len(anomaly_detector.models)
            }
        }
    
    def force_collection(self) -> Dict[str, Any]:
        """Force an immediate metrics collection"""
        logger.info("Forcing immediate metrics collection")
        
        start_time = time.time()
        success = self.collect_system_metrics()
        collection_time = time.time() - start_time
        
        return {
            'success': success,
            'collection_time': collection_time,
            'timestamp': datetime.now().isoformat(),
            'stats': self.get_status()
        }
    
    def update_collection_interval(self, new_interval: int):
        """Update the collection interval"""
        if not (5 <= new_interval <= 300):  # 5 seconds to 5 minutes
            raise ValueError("Collection interval must be between 5 and 300 seconds")
        
        if self.is_running:
            # Remove existing job
            try:
                self.scheduler.remove_job('collect_metrics')
            except:
                pass
            
            # Add new job with updated interval
            self.scheduler.add_job(
                func=self.collect_system_metrics,
                trigger=IntervalTrigger(seconds=new_interval),
                id='collect_metrics',
                name='System Metrics Collection',
                max_instances=1,
                coalesce=True,
                misfire_grace_time=30
            )
            
            self.collection_interval = new_interval
            logger.info(f"Updated collection interval to {new_interval} seconds")
        else:
            self.collection_interval = new_interval
            logger.info(f"Collection interval updated to {new_interval} seconds (will take effect on start)")

# Global background collector instance
background_collector = BackgroundDataCollector()

# Context manager for easy start/stop
class BackgroundCollectorManager:
    """Context manager for background collector"""
    
    def __init__(self, collection_interval: int = 10):
        self.collector = BackgroundDataCollector(collection_interval)
    
    def __enter__(self):
        self.collector.start()
        return self.collector
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.collector.stop()

# Initialize and start collector on module import if enabled
def initialize_background_collector():
    """Initialize and start background collector if enabled"""
    enabled = os.getenv('ENABLE_BACKGROUND_COLLECTION', 'true').lower() == 'true'
    
    if enabled:
        try:
            interval = int(os.getenv('COLLECTION_INTERVAL', '10'))
            background_collector.collection_interval = interval
            background_collector.start()
            logger.info(f"Background collector auto-started with {interval}s interval")
        except Exception as e:
            logger.error(f"Failed to auto-start background collector: {e}")
    else:
        logger.info("Background collection disabled via environment variable")

# Auto-start if enabled (commented out for manual control)
# initialize_background_collector()
