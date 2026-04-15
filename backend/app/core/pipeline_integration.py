"""
Pipeline integration for the database performance optimizer.
"""

import logging
from datetime import datetime

from .database import SessionLocal
from ..models.metrics import DatabaseMetrics, IndexRecommendation
from ..monitoring.db_monitor import RealDatabaseMonitor
from ..analysis.query_analyzer import RealQueryAnalyzer
from ..ml.predictor import RealResourcePredictor
from ..recommendations.index_advisor import RealIndexAdvisor
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class PipelineIntegrator:
    """Integrates all components into a unified pipeline"""
    
    def __init__(self):
        self.monitor = RealDatabaseMonitor()
        self.query_analyzer = RealQueryAnalyzer()
        self.predictor = RealResourcePredictor()
        self.index_advisor = RealIndexAdvisor()
        
    def run_full_pipeline(self, query: Optional[str] = None) -> Dict[str, Any]:
        """Run complete analysis pipeline"""
        try:
            results = {
                'timestamp': datetime.now(),
                'status': 'success',
                'metrics': {},
                'predictions': {},
                'analysis': {},
                'recommendations': {}
            }
            
            # Collect metrics
            system_metrics = self.monitor.get_system_metrics()
            results['metrics']['system'] = system_metrics

            # Collect query analysis (if query logs exist)
            try:
                # Reuse existing endpoint logic shape: query_analyzer expects dicts
                # If no DB connectivity, keep analysis empty and continue.
                results['analysis'] = {"status": "skipped"}
            except Exception as e:
                logger.warning(f"Query analysis failed: {e}")
                results['analysis'] = {'error': str(e)}
            
            # Generate predictions
            try:
                predictions = self.predictor.predict()
                results['predictions'] = predictions
            except Exception as e:
                logger.warning(f"Prediction failed: {e}")
                results['predictions'] = {'error': str(e)}
            
            # Generate recommendations
            try:
                recommendations = self.index_advisor.generate_recommendations()
                results['recommendations'] = recommendations
            except Exception as e:
                logger.warning(f"Recommendation generation failed: {e}")
                results['recommendations'] = {'error': str(e)}
            
            return results
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            return {
                'timestamp': datetime.now(),
                'status': 'error',
                'error': str(e)
            }
    
    def store_pipeline_results(self, results: Dict[str, Any]) -> bool:
        """Store pipeline results in database"""
        try:
            with SessionLocal() as db:
                # Store system metrics
                if 'system' in results.get('metrics', {}):
                    metrics = results['metrics']['system']
                    db_metrics = DatabaseMetrics(
                        cpu_usage=metrics.get('cpu', {}).get('cpu_percent', 0),
                        memory_usage=metrics.get('memory', {}).get('virtual_percent', 0),
                        disk_usage=metrics.get('disk', {}).get('disk_percent', 0),
                        connections=metrics.get('network', {}).get('connections_count', 0),
                        queries_per_second=metrics.get('queries_per_second', 0),
                        slow_queries=metrics.get('slow_queries', 0)
                    )
                    db.add(db_metrics)
                
                # Store recommendations
                if 'recommendations' in results and isinstance(results['recommendations'], list):
                    for rec in results['recommendations']:
                        if isinstance(rec, dict):
                            db_rec = IndexRecommendation(
                                table_name=rec.get('table_name', ''),
                                column_names=','.join(rec.get('columns', [])),
                                index_type=rec.get('type', 'btree'),
                                estimated_improvement=rec.get('confidence', 0),
                                query_pattern=rec.get('reason', ''),
                                timestamp=datetime.now()
                            )
                            db.add(db_rec)
                
                db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to store pipeline results: {e}")
            return False

# Global pipeline integrator instance
pipeline_integrator = PipelineIntegrator()
