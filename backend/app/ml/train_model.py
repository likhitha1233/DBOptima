#!/usr/bin/env python3
"""
Real ML Training on Database Logs
Trains machine learning model on actual database metrics
"""

import os
import sys
import pandas as pd
from sklearn.linear_model import LinearRegression
import joblib

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.database import SessionLocal, Base, engine
from app.models.metrics import DatabaseMetrics

def train_model():
    """Train ML model on real database metrics"""
    print("Training ML model on real database logs...")
    
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    print("Database tables created/verified")
    
    db = SessionLocal()
    try:
        # Get all database metrics
        data = db.query(DatabaseMetrics).all()
        
        print(f"Found {len(data)} records in database")
        
        if len(data) < 100:
            raise ValueError(f"Insufficient real data for training: found {len(data)} records, need at least 100 records. Please collect more real database metrics before training.")
        
        # Convert to DataFrame
        df = pd.DataFrame([{
            "cpu": d.cpu_usage,
            "memory": d.memory_usage,
            "disk": d.disk_usage,
            "connections": d.connections,
            "queries_per_second": d.queries_per_second,
            "slow_queries": d.slow_queries
        } for d in data])
        
        print(f"Training data shape: {df.shape}")
        print(f"Features: CPU ({df['cpu'].mean():.1f}%), Memory ({df['memory'].mean():.1f}%), Disk ({df['disk'].mean():.1f}%)")
        
        # Prepare features and target
        X = df[["cpu", "memory", "connections", "queries_per_second", "slow_queries"]]
        y = df["disk"]
        
        # Train model
        model = LinearRegression()
        model.fit(X, y)
        
        # Save model
        model_path = os.path.join(os.path.dirname(__file__), "model.pkl")
        joblib.dump(model, model_path)
        
        print(f"Model trained and saved to {model_path}")
        print(f"Model R² score: {model.score(X, y):.3f}")
        
        # Test prediction
        test_data = [[50.0, 75.0, 10, 25.0, 2]]
        prediction = model.predict(test_data)
        print(f"Test prediction (CPU=50%, Memory=75%, Connections=10, QPS=25, Slow=2): Disk usage = {prediction[0]:.1f}%")
        
        print("Model trained on REAL data successfully!")
        return True
        
    except Exception as e:
        print(f"Error training model: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = train_model()
    if success:
        print("ML training completed successfully!")
    else:
        print("ML training failed!")
        sys.exit(1)
