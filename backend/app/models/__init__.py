"""
Database Models Package - DEPRECATED
Use models/metrics.py for canonical model definitions
This file kept for backward compatibility only
"""

# Import canonical models from metrics.py
from .metrics import DatabaseMetrics, QueryLog, IndexRecommendation, PerformancePrediction
from .user import User

# Create alias for backward compatibility
SystemMetrics = DatabaseMetrics  # Alias for any imports using old name
MLPredictions = None  # Not used - placeholder
Recommendations = None  # Not used - placeholder

# Re-export canonical models
__all__ = ['DatabaseMetrics', 'QueryLog', 'IndexRecommendation', 'PerformancePrediction', 'User', 'SystemMetrics']
