#!/usr/bin/env python3
"""
Production-grade Anomaly Detection System
Uses rolling statistics and Isolation Forest for real-time anomaly detection
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any
from dataclasses import dataclass
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text
from ..core.database import SessionLocal

logger = logging.getLogger(__name__)

@dataclass
class AnomalyResult:
    """Anomaly detection result"""
    is_anomaly: bool
    anomaly_score: float
    reason: str
    metric_name: str
    current_value: float
    threshold: float
    timestamp: datetime
    confidence: float

class RealTimeAnomalyDetector:
    """Production-grade real-time anomaly detection"""
    
    def __init__(self, window_size: int = 50, contamination: float = 0.1):
        self.window_size = window_size
        self.contamination = contamination
        
        # Rolling statistics parameters
        self.rolling_std_multiplier = 2.5  # Standard deviations for anomaly threshold
        self.min_samples_for_detection = 10
        
        # Isolation Forest models for each metric
        self.models = {
            'cpu_usage': IsolationForest(contamination=contamination, random_state=42),
            'memory_usage': IsolationForest(contamination=contamination, random_state=42),
            'disk_usage': IsolationForest(contamination=contamination, random_state=42),
            'queries_per_second': IsolationForest(contamination=contamination, random_state=42)
        }
        
        # Scalers for each metric
        self.scalers = {
            'cpu_usage': StandardScaler(),
            'memory_usage': StandardScaler(),
            'disk_usage': StandardScaler(),
            'queries_per_second': StandardScaler()
        }
        
        # Historical data cache
        self.historical_data = {
            'cpu_usage': [],
            'memory_usage': [],
            'disk_usage': [],
            'queries_per_second': []
        }
        
        # Model training status
        self.models_trained = {metric: False for metric in self.models.keys()}
        
        logger.info(f"AnomalyDetector initialized with window_size={window_size}")
    
    def load_historical_data(self, hours_back: int = 24) -> bool:
        """Load historical data for model training"""
        try:
            with SessionLocal() as db:
                cutoff_time = datetime.now() - timedelta(hours=hours_back)
                
                # Get historical metrics
                query = text("""
                    SELECT timestamp, cpu_usage, memory_usage, disk_usage, 
                           queries_per_second, slow_queries
                    FROM database_metrics 
                    WHERE timestamp > :cutoff_time
                    ORDER BY timestamp ASC
                """)
                
                result = db.execute(query, {"cutoff_time": cutoff_time})
                rows = result.fetchall()
                
                if len(rows) < self.min_samples_for_detection:
                    logger.warning(f"Insufficient historical data: {len(rows)} samples")
                    return False
                
                # Load data into cache
                for row in rows:
                    timestamp = row[0]
                    self.historical_data['cpu_usage'].append((timestamp, float(row[1]) or 0.0))
                    self.historical_data['memory_usage'].append((timestamp, float(row[2]) or 0.0))
                    self.historical_data['disk_usage'].append((timestamp, float(row[3]) or 0.0))
                    self.historical_data['queries_per_second'].append((timestamp, float(row[4]) or 0.0))
                
                # Keep only recent data in cache
                for metric in self.historical_data:
                    if len(self.historical_data[metric]) > self.window_size * 2:
                        self.historical_data[metric] = self.historical_data[metric][-self.window_size * 2:]
                
                logger.info(f"Loaded {len(rows)} historical samples for anomaly detection")
                return True
                
        except Exception as e:
            logger.error(f"Failed to load historical data: {e}")
            return False
    
    def train_models(self) -> bool:
        """Train Isolation Forest models on historical data"""
        try:
            trained_count = 0
            
            for metric_name in self.models.keys():
                data_points = self.historical_data[metric_name]
                
                if len(data_points) < self.min_samples_for_detection:
                    logger.warning(f"Insufficient data for {metric_name}: {len(data_points)} samples")
                    continue
                
                # Extract values (ignore timestamps for training)
                values = np.array([point[1] for point in data_points]).reshape(-1, 1)
                
                # Train scaler
                self.scalers[metric_name].fit(values)
                
                # Scale data
                scaled_values = self.scalers[metric_name].transform(values)
                
                # Train Isolation Forest
                self.models[metric_name].fit(scaled_values)
                
                self.models_trained[metric_name] = True
                trained_count += 1
                
                logger.info(f"Trained anomaly detection model for {metric_name} on {len(values)} samples")
            
            if trained_count == 0:
                logger.error("No models trained due to insufficient data")
                return False
            
            logger.info(f"Successfully trained {trained_count}/{len(self.models)} anomaly detection models")
            return True
            
        except Exception as e:
            logger.error(f"Failed to train anomaly detection models: {e}")
            return False
    
    def detect_rolling_anomalies(self, current_metrics: Dict[str, float]) -> List[AnomalyResult]:
        """Detect anomalies using rolling statistics"""
        anomalies = []
        
        for metric_name, current_value in current_metrics.items():
            if metric_name not in self.historical_data:
                continue
            
            # Add current value to history
            self.historical_data[metric_name].append((datetime.now(), current_value))
            
            # Keep window size limited
            if len(self.historical_data[metric_name]) > self.window_size:
                self.historical_data[metric_name] = self.historical_data[metric_name][-self.window_size:]
            
            # Need minimum data for rolling statistics
            if len(self.historical_data[metric_name]) < self.min_samples_for_detection:
                continue
            
            # Calculate rolling statistics
            values = [point[1] for point in self.historical_data[metric_name]]
            values_array = np.array(values)
            
            rolling_mean = np.mean(values_array)
            rolling_std = np.std(values_array)
            
            # Calculate Z-score
            if rolling_std > 0:
                z_score = abs(current_value - rolling_mean) / rolling_std
                
                # Check if anomaly
                if z_score > self.rolling_std_multiplier:
                    anomaly = AnomalyResult(
                        is_anomaly=True,
                        anomaly_score=z_score,
                        reason=f"{metric_name} spiked {z_score:.1f} standard deviations from rolling mean",
                        metric_name=metric_name,
                        current_value=current_value,
                        threshold=rolling_mean + (self.rolling_std_multiplier * rolling_std),
                        timestamp=datetime.now(),
                        confidence=min(0.95, z_score / self.rolling_std_multiplier)
                    )
                    anomalies.append(anomaly)
            
        return anomalies
    
    def detect_isolation_forest_anomalies(self, current_metrics: Dict[str, float]) -> List[AnomalyResult]:
        """Detect anomalies using Isolation Forest"""
        anomalies = []
        
        for metric_name, current_value in current_metrics.items():
            if not self.models_trained.get(metric_name, False):
                continue
            
            try:
                # Prepare feature vector
                feature_vector = np.array([[current_value]])
                
                # Scale features
                scaled_features = self.scalers[metric_name].transform(feature_vector)
                
                # Predict anomaly (-1 for anomaly, 1 for normal)
                prediction = self.models[metric_name].predict(scaled_features)[0]
                anomaly_score = self.models[metric_name].decision_function(scaled_features)[0]
                
                # Convert to positive anomaly score (lower = more anomalous)
                anomaly_score = abs(anomaly_score)
                
                if prediction == -1:  # Anomaly detected
                    # Get historical context
                    historical_values = [point[1] for point in self.historical_data[metric_name]]
                    if historical_values:
                        historical_mean = np.mean(historical_values)
                        deviation_percent = abs(current_value - historical_mean) / historical_mean * 100
                    else:
                        deviation_percent = 0
                    
                    anomaly = AnomalyResult(
                        is_anomaly=True,
                        anomaly_score=anomaly_score,
                        reason=f"{metric_name} detected as anomaly by Isolation Forest (deviation: {deviation_percent:.1f}%)",
                        metric_name=metric_name,
                        current_value=current_value,
                        threshold=historical_mean if historical_values else current_value,
                        timestamp=datetime.now(),
                        confidence=min(0.95, anomaly_score * 2)
                    )
                    anomalies.append(anomaly)
                    
            except Exception as e:
                logger.error(f"Error in Isolation Forest detection for {metric_name}: {e}")
                continue
        
        return anomalies
    
    def detect_anomalies(self, current_metrics: Dict[str, float]) -> Dict[str, Any]:
        """Main anomaly detection method combining both approaches"""
        try:
            # Ensure models are trained
            if not any(self.models_trained.values()):
                if not self.load_historical_data():
                    logger.warning("Could not load historical data, using rolling statistics only")
                else:
                    self.train_models()
            
            # Detect anomalies using both methods
            rolling_anomalies = self.detect_rolling_anomalies(current_metrics)
            isolation_anomalies = self.detect_isolation_forest_anomalies(current_metrics)
            
            # Combine and deduplicate anomalies
            all_anomalies = rolling_anomalies + isolation_anomalies
            
            # Remove duplicates (same metric detected by both methods)
            seen_metrics = set()
            unique_anomalies = []
            for anomaly in all_anomalies:
                if anomaly.metric_name not in seen_metrics:
                    unique_anomalies.append(anomaly)
                    seen_metrics.add(anomaly.metric_name)
            
            # Sort by anomaly score
            unique_anomalies.sort(key=lambda x: x.anomaly_score, reverse=True)
            
            return {
                'has_anomalies': len(unique_anomalies) > 0,
                'anomaly_count': len(unique_anomalies),
                'anomalies': [
                    {
                        'metric': anomaly.metric_name,
                        'is_anomaly': anomaly.is_anomaly,
                        'score': round(anomaly.anomaly_score, 3),
                        'reason': anomaly.reason,
                        'current_value': round(anomaly.current_value, 2),
                        'threshold': round(anomaly.threshold, 2),
                        'confidence': round(anomaly.confidence, 3),
                        'timestamp': anomaly.timestamp.isoformat()
                    }
                    for anomaly in unique_anomalies
                ],
                'detection_methods': {
                    'rolling_statistics': len(rolling_anomalies),
                    'isolation_forest': len(isolation_anomalies),
                    'models_trained': sum(self.models_trained.values()),
                    'total_models': len(self.models)
                },
                'data_quality': {
                    'samples_in_window': {
                        metric: len(self.historical_data.get(metric, []))
                        for metric in self.models.keys()
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return {
                'has_anomalies': False,
                'error': str(e),
                'anomalies': []
            }
    
    def get_anomaly_summary(self, hours_back: int = 1) -> Dict[str, Any]:
        """Get summary of recent anomalies"""
        try:
            # This would typically query an anomalies table
            # For now, return current state
            return {
                'recent_anomalies': [],
                'anomaly_trends': {},
                'model_status': self.models_trained,
                'data_points_trained_on': {
                    metric: len(self.historical_data.get(metric, []))
                    for metric in self.models.keys()
                }
            }
        except Exception as e:
            logger.error(f"Failed to get anomaly summary: {e}")
            return {'error': str(e)}

# Global anomaly detector instance
anomaly_detector = RealTimeAnomalyDetector()
