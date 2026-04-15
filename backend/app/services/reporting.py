import json
import logging
from datetime import datetime, timedelta
from ..core.database import SessionLocal

logger = logging.getLogger(__name__)

class ReportingService:
    def __init__(self):
        pass
    
    def generate_daily_report(self, date: datetime = None) -> Dict:
        """Generate daily performance report"""
        if date is None:
            date = datetime.now().date()
        
        try:
            with SessionLocal() as db:
                # Get metrics for the day
                start_time = datetime.combine(date, datetime.min.time())
                end_time = start_time + timedelta(days=1)
                
                report = {
                    "report_type": "daily",
                    "date": date.isoformat(),
                    "generated_at": datetime.now().isoformat(),
                    "summary": self._get_daily_summary(db, start_time, end_time),
                    "metrics": self._get_daily_metrics(db, start_time, end_time),
                    "slow_queries": self._get_daily_slow_queries(db, start_time, end_time),
                    "recommendations": self._get_daily_recommendations(db, start_time, end_time),
                    "predictions": self._get_daily_predictions(db, start_time, end_time)
                }
                
                return report
                
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")
            return {"error": str(e)}
    
    def _get_daily_summary(self, db: Session, start_time: datetime, end_time: datetime) -> Dict:
        """Get daily summary statistics"""
        try:
            # Get total queries
            total_queries_query = text("""
                SELECT COUNT(*) FROM query_logs 
                WHERE timestamp >= :start_time AND timestamp < :end_time
            """)
            total_queries_result = db.execute(total_queries_query, {
                'start_time': start_time,
                'end_time': end_time
            })
            total_queries = total_queries_result.fetchone()[0]
            
            # Get slow queries
            slow_queries_query = text("""
                SELECT COUNT(*) FROM query_logs 
                WHERE is_slow = True 
                AND timestamp >= :start_time AND timestamp < :end_time
            """)
            slow_queries_result = db.execute(slow_queries_query, {
                'start_time': start_time,
                'end_time': end_time
            })
            slow_queries = slow_queries_result.fetchone()[0]
            
            # Get average metrics
            metrics_query = text("""
                SELECT 
                    AVG(cpu_usage) as avg_cpu,
                    MAX(cpu_usage) as max_cpu,
                    AVG(memory_usage) as avg_memory,
                    MAX(memory_usage) as max_memory,
                    AVG(disk_usage) as avg_disk,
                    MAX(disk_usage) as max_disk,
                    AVG(connections) as avg_connections,
                    MAX(connections) as max_connections
                FROM database_metrics 
                WHERE timestamp >= :start_time AND timestamp < :end_time
            """)
            metrics_result = db.execute(metrics_query, {
                'start_time': start_time,
                'end_time': end_time
            })
            metrics = metrics_result.fetchone()
            
            # Get top slow query
            top_slow_query = text("""
                SELECT query_text, execution_time
                FROM query_logs 
                WHERE is_slow = True 
                AND timestamp >= :start_time AND timestamp < :end_time
                ORDER BY execution_time DESC
                LIMIT 1
            """)
            top_slow_result = db.execute(top_slow_query, {
                'start_time': start_time,
                'end_time': end_time
            })
            top_slow = top_slow_result.fetchone()
            
            summary = {
                "total_queries": total_queries,
                "slow_queries": slow_queries,
                "slow_query_percentage": (slow_queries / total_queries * 100) if total_queries > 0 else 0,
                "avg_cpu": round(metrics[0] or 0, 2),
                "max_cpu": round(metrics[1] or 0, 2),
                "avg_memory": round(metrics[2] or 0, 2),
                "max_memory": round(metrics[3] or 0, 2),
                "avg_disk": round(metrics[4] or 0, 2),
                "max_disk": round(metrics[5] or 0, 2),
                "avg_connections": round(metrics[6] or 0, 2),
                "max_connections": round(metrics[7] or 0, 2),
                "top_slow_query": {
                    "query": top_slow[0] if top_slow else None,
                    "execution_time": top_slow[1] if top_slow else 0
                }
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting daily summary: {e}")
            return {}
    
    def _get_daily_metrics(self, db: Session, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Get hourly metrics for the day"""
        try:
            query = text("""
                SELECT 
                    DATE_TRUNC('hour', timestamp) as hour,
                    AVG(cpu_usage) as avg_cpu,
                    AVG(memory_usage) as avg_memory,
                    AVG(disk_usage) as avg_disk,
                    AVG(connections) as avg_connections,
                    AVG(queries_per_second) as avg_qps,
                    SUM(slow_queries) as total_slow_queries
                FROM database_metrics 
                WHERE timestamp >= :start_time AND timestamp < :end_time
                GROUP BY DATE_TRUNC('hour', timestamp)
                ORDER BY hour
            """)
            result = db.execute(query, {
                'start_time': start_time,
                'end_time': end_time
            })
            
            metrics = []
            for row in result:
                metrics.append({
                    "hour": row[0].isoformat(),
                    "avg_cpu": round(row[1] or 0, 2),
                    "avg_memory": round(row[2] or 0, 2),
                    "avg_disk": round(row[3] or 0, 2),
                    "avg_connections": round(row[4] or 0, 2),
                    "avg_qps": round(row[5] or 0, 2),
                    "total_slow_queries": row[6] or 0
                })
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting daily metrics: {e}")
            return []
    
    def _get_daily_slow_queries(self, db: Session, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Get top slow queries for the day"""
        try:
            query = text("""
                SELECT 
                    query_text,
                    AVG(execution_time) as avg_time,
                    MAX(execution_time) as max_time,
                    COUNT(*) as frequency,
                    AVG(rows_examined) as avg_rows_examined,
                    database_name
                FROM query_logs 
                WHERE is_slow = True 
                AND timestamp >= :start_time AND timestamp < :end_time
                GROUP BY query_text, database_name
                ORDER BY avg_time DESC
                LIMIT 10
            """)
            result = db.execute(query, {
                'start_time': start_time,
                'end_time': end_time
            })
            
            slow_queries = []
            for row in result:
                slow_queries.append({
                    "query_text": row[0],
                    "avg_execution_time": round(row[1] or 0, 2),
                    "max_execution_time": round(row[2] or 0, 2),
                    "frequency": row[3],
                    "avg_rows_examined": round(row[4] or 0, 2),
                    "database_name": row[5]
                })
            
            return slow_queries
            
        except Exception as e:
            logger.error(f"Error getting daily slow queries: {e}")
            return []
    
    def _get_daily_recommendations(self, db: Session, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Get index recommendations for the day"""
        try:
            query = text("""
                SELECT 
                    table_name,
                    column_names,
                    index_type,
                    estimated_improvement,
                    query_pattern,
                    timestamp
                FROM index_recommendations 
                WHERE timestamp >= :start_time AND timestamp < :end_time
                ORDER BY estimated_improvement DESC
                LIMIT 5
            """)
            result = db.execute(query, {
                'start_time': start_time,
                'end_time': end_time
            })
            
            recommendations = []
            for row in result:
                recommendations.append({
                    "table_name": row[0],
                    "column_names": row[1],
                    "index_type": row[2],
                    "estimated_improvement": round(row[3] or 0, 2),
                    "query_pattern": row[4],
                    "timestamp": row[5].isoformat()
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting daily recommendations: {e}")
            return []
    
    def _get_daily_predictions(self, db: Session, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Get predictions made during the day"""
        try:
            result = db.execute(text("""
                SELECT 
                    timestamp,
                    prediction_horizon,
                    predicted_cpu,
                    predicted_memory,
                    predicted_disk,
                    confidence_score
                FROM performance_predictions 
                WHERE timestamp >= :start_time AND timestamp < :end_time
                ORDER BY timestamp DESC
                LIMIT 5
            """), {"start_time": start_time, "end_time": end_time})
            
            predictions = []
            for row in result:
                predictions.append({
                    "timestamp": row[0].isoformat(),
                    "prediction_horizon": row[1],
                    "predicted_cpu": round(row[2] or 0, 2),
                    "predicted_memory": round(row[3] or 0, 2),
                    "predicted_disk": round(row[4] or 0, 2),
                    "confidence_score": round(row[5] or 0, 2)
                })
            
            return predictions
            
        except Exception as e:
            logger.error(f"Error getting daily predictions: {e}")
            return []
    
    def generate_weekly_report(self, start_date: datetime = None) -> Dict:
        """Generate weekly performance report"""
        if start_date is None:
            start_date = datetime.now().date() - timedelta(days=7)
        
        end_date = start_date + timedelta(days=7)
        
        try:
            with SessionLocal() as db:
                report = {
                    "report_type": "weekly",
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "generated_at": datetime.now().isoformat(),
                    "summary": self._get_weekly_summary(db, start_date, end_date),
                    "daily_breakdown": self._get_weekly_daily_breakdown(db, start_date, end_date),
                    "trends": self._get_weekly_trends(db, start_date, end_date),
                    "top_issues": self._get_weekly_top_issues(db, start_date, end_date)
                }
                
                return report
                
        except Exception as e:
            logger.error(f"Error generating weekly report: {e}")
            return {"error": str(e)}
    
    def _get_weekly_summary(self, db: Session, start_date: datetime.date, end_date: datetime.date) -> Dict:
        """Get weekly summary statistics"""
        try:
            start_time = datetime.combine(start_date, datetime.min.time())
            end_time = datetime.combine(end_date, datetime.min.time())
            
            # Total queries for the week
            total_queries_result = db.execute(text("""
                SELECT COUNT(*) FROM query_logs 
                WHERE timestamp >= :start_time AND timestamp < :end_time
            """), {"start_time": start_time, "end_time": end_time})
            total_queries = total_queries_result.fetchone()[0]
            
            # Slow queries for the week
            slow_queries_result = db.execute(text("""
                SELECT COUNT(*) FROM query_logs 
                WHERE is_slow = True 
                AND timestamp >= :start_time AND timestamp < :end_time
            """), {"start_time": start_time, "end_time": end_time})
            slow_queries = slow_queries_result.fetchone()[0]
            
            # Peak resource usage
            peak_result = db.execute(text("""
                SELECT 
                    MAX(cpu_usage) as peak_cpu,
                    MAX(memory_usage) as peak_memory,
                    MAX(disk_usage) as peak_disk,
                    MAX(connections) as peak_connections
                FROM database_metrics 
                WHERE timestamp >= :start_time AND timestamp < :end_time
            """), {"start_time": start_time, "end_time": end_time})
            peak = peak_result.fetchone()
            
            # Average resource usage
            avg_result = db.execute(text("""
                SELECT 
                    AVG(cpu_usage) as avg_cpu,
                    AVG(memory_usage) as avg_memory,
                    AVG(disk_usage) as avg_disk,
                    AVG(connections) as avg_connections
                FROM database_metrics 
                WHERE timestamp >= :start_time AND timestamp < :end_time
            """), {"start_time": start_time, "end_time": end_time})
            avg = avg_result.fetchone()
            
            summary = {
                "total_queries": total_queries,
                "slow_queries": slow_queries,
                "slow_query_percentage": (slow_queries / total_queries * 100) if total_queries > 0 else 0,
                "peak_cpu": round(peak[0] or 0, 2),
                "peak_memory": round(peak[1] or 0, 2),
                "peak_disk": round(peak[2] or 0, 2),
                "peak_connections": peak[3] or 0,
                "avg_cpu": round(avg[0] or 0, 2),
                "avg_memory": round(avg[1] or 0, 2),
                "avg_disk": round(avg[2] or 0, 2),
                "avg_connections": round(avg[3] or 0, 2)
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting weekly summary: {e}")
            return {}
    
    def _get_weekly_daily_breakdown(self, db: Session, start_date: datetime.date, end_date: datetime.date) -> List[Dict]:
        """Get daily breakdown for the week"""
        daily_breakdown = []
        
        current_date = start_date
        while current_date < end_date:
            daily_report = self.generate_daily_report(current_date)
            if "error" not in daily_report:
                daily_breakdown.append({
                    "date": current_date.isoformat(),
                    "summary": daily_report["summary"]
                })
            current_date += timedelta(days=1)
        
        return daily_breakdown
    
    def _get_weekly_trends(self, db: Session, start_date: datetime.date, end_date: datetime.date) -> Dict:
        """Analyze weekly trends"""
        try:
            start_time = datetime.combine(start_date, datetime.min.time())
            end_time = datetime.combine(end_date, datetime.min.time())
            
            # Resource usage trends
            resource_trends_result = db.execute(text("""
                SELECT 
                    DATE(timestamp) as date,
                    AVG(cpu_usage) as avg_cpu,
                    AVG(memory_usage) as avg_memory,
                    AVG(disk_usage) as avg_disk,
                    AVG(connections) as avg_connections
                FROM database_metrics 
                WHERE timestamp >= :start_time AND timestamp < :end_time
                GROUP BY DATE(timestamp)
                ORDER BY date
            """), {"start_time": start_time, "end_time": end_time})
            
            resource_trends = []
            for row in resource_trends_result:
                resource_trends.append({
                    "date": row[0].isoformat(),
                    "avg_cpu": round(row[1] or 0, 2),
                    "avg_memory": round(row[2] or 0, 2),
                    "avg_disk": round(row[3] or 0, 2),
                    "avg_connections": round(row[4] or 0, 2)
                })
            
            # Query volume trends
            query_trends_result = db.execute(text("""
                SELECT 
                    DATE(timestamp) as date,
                    COUNT(*) as total_queries,
                    SUM(CASE WHEN is_slow = True THEN 1 ELSE 0 END) as slow_queries
                FROM query_logs 
                WHERE timestamp >= :start_time AND timestamp < :end_time
                GROUP BY DATE(timestamp)
                ORDER BY date
            """), {"start_time": start_time, "end_time": end_time})
            
            query_trends = []
            for row in query_trends_result:
                query_trends.append({
                    "date": row[0].isoformat(),
                    "total_queries": row[1],
                    "slow_queries": row[2],
                    "slow_query_percentage": (row[2] / row[1] * 100) if row[1] > 0 else 0
                })
            
            return {
                "resource_trends": resource_trends,
                "query_trends": query_trends
            }
            
        except Exception as e:
            logger.error(f"Error getting weekly trends: {e}")
            return {}
    
    def _get_weekly_top_issues(self, db: Session, start_date: datetime.date, end_date: datetime.date) -> List[Dict]:
        """Get top performance issues for the week"""
        try:
            start_time = datetime.combine(start_date, datetime.min.time())
            end_time = datetime.combine(end_date, datetime.min.time())
            
            # Top slow queries
            slow_queries_result = db.execute(text("""
                SELECT 
                    query_text,
                    AVG(execution_time) as avg_time,
                    COUNT(*) as frequency,
                    database_name
                FROM query_logs 
                WHERE is_slow = True 
                AND timestamp >= :start_time AND timestamp < :end_time
                GROUP BY query_text, database_name
                ORDER BY avg_time DESC
                LIMIT 5
            """), {"start_time": start_time, "end_time": end_time})
            
            top_slow_queries = []
            for row in slow_queries_result:
                top_slow_queries.append({
                    "query_text": row[0],
                    "avg_execution_time": round(row[1] or 0, 2),
                    "frequency": row[2],
                    "database_name": row[3]
                })
            
            # Peak usage periods
            peak_periods_result = db.execute(text("""
                SELECT 
                    DATE_TRUNC('hour', timestamp) as hour,
                    cpu_usage,
                    memory_usage,
                    disk_usage,
                    connections
                FROM database_metrics 
                WHERE timestamp >= :start_time AND timestamp < :end_time
                AND (cpu_usage > 80 OR memory_usage > 80 OR disk_usage > 80)
                ORDER BY cpu_usage DESC, memory_usage DESC
                LIMIT 10
            """), {"start_time": start_time, "end_time": end_time})
            
            peak_periods = []
            for row in peak_periods_result:
                peak_periods.append({
                    "hour": row[0].isoformat(),
                    "cpu_usage": round(row[1] or 0, 2),
                    "memory_usage": round(row[2] or 0, 2),
                    "disk_usage": round(row[3] or 0, 2),
                    "connections": row[4] or 0
                })
            
            return {
                "top_slow_queries": top_slow_queries,
                "peak_usage_periods": peak_periods
            }
            
        except Exception as e:
            logger.error(f"Error getting weekly top issues: {e}")
            return {}
    
    def export_report_to_json(self, report: Dict, filepath: str):
        """Export report to JSON file"""
        try:
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f"Report exported to {filepath}")
        except Exception as e:
            logger.error(f"Error exporting report: {e}")
    
    def export_report_to_csv(self, report: Dict, filepath: str):
        """Export report data to CSV file"""
        try:
            if report["report_type"] == "daily":
                # Export metrics
                if "metrics" in report:
                    df_metrics = pd.DataFrame(report["metrics"])
                    df_metrics.to_csv(f"{filepath}_metrics.csv", index=False)
                
                # Export slow queries
                if "slow_queries" in report:
                    df_slow = pd.DataFrame(report["slow_queries"])
                    df_slow.to_csv(f"{filepath}_slow_queries.csv", index=False)
            
            logger.info(f"Report data exported to {filepath}")
        except Exception as e:
            logger.error(f"Error exporting report to CSV: {e}")
    
    def schedule_reports(self, report_type: str, schedule: str, recipients: List[str]):
        """Schedule automated reports"""
        logger.info(f"Scheduling {report_type} reports with schedule: {schedule}")
        logger.info(f"Recipients: {recipients}")
        
        # In a real implementation, this would:
        # 1. Create scheduled tasks
        # 2. Set up email notifications
        # 3. Store schedule configuration in database
