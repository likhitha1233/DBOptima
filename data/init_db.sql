-- Database initialization script for demo
-- Simple database schema for DBMS monitoring system

-- Create database if it doesn't exist
CREATE DATABASE IF NOT EXISTS dbms_demo;

-- Use the database (PostgreSQL syntax)
\c dbms_demo;

-- System metrics table
CREATE TABLE IF NOT EXISTS system_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cpu_percent FLOAT,
    memory_percent FLOAT,
    disk_percent FLOAT,
    connections INTEGER,
    queries_per_second FLOAT,
    slow_queries INTEGER
);

-- Query logs table
CREATE TABLE IF NOT EXISTS query_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    query_text TEXT,
    execution_time FLOAT,
    rows_examined INTEGER,
    rows_returned INTEGER,
    is_slow BOOLEAN DEFAULT FALSE
);

-- Index recommendations table
CREATE TABLE IF NOT EXISTS index_recommendations (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    table_name VARCHAR(100),
    column_names TEXT,
    recommendation_type VARCHAR(50),
    confidence_score FLOAT
);

-- Insert sample data for demo
INSERT INTO system_metrics (cpu_percent, memory_percent, disk_percent, connections, queries_per_second, slow_queries)
VALUES 
    (25.5, 45.2, 30.1, 50, 120.5, 3),
    (28.3, 47.8, 31.2, 52, 125.3, 2),
    (22.1, 43.5, 29.8, 48, 118.7, 1),
    (30.2, 48.9, 32.1, 55, 132.4, 4),
    (26.8, 46.1, 30.5, 51, 122.8, 2);

INSERT INTO query_logs (query_text, execution_time, rows_examined, rows_returned, is_slow)
VALUES 
    ('SELECT * FROM users WHERE id = 1', 15.2, 1000, 1, FALSE),
    ('SELECT * FROM orders o JOIN customers c ON o.customer_id = c.id', 1250.5, 50000, 250, TRUE),
    ('UPDATE products SET price = price * 1.1', 45.3, 10000, 100, FALSE),
    ('SELECT COUNT(*) FROM transactions WHERE created_at > ''2024-01-01''', 89.7, 25000, 1, FALSE),
    ('DELETE FROM logs WHERE created_at < ''2023-01-01''', 2340.2, 500000, 45000, TRUE);

INSERT INTO index_recommendations (table_name, column_names, recommendation_type, confidence_score)
VALUES 
    ('orders', 'customer_id', 'INDEX', 0.85),
    ('users', 'email', 'UNIQUE INDEX', 0.92),
    ('products', 'category_id', 'INDEX', 0.78),
    ('transactions', 'created_at', 'INDEX', 0.81),
    ('logs', 'created_at', 'INDEX', 0.75);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON system_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_query_logs_timestamp ON query_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_query_logs_slow ON query_logs(is_slow);
CREATE INDEX IF NOT EXISTS idx_recommendations_table ON index_recommendations(table_name);

-- Grant permissions (adjust as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO dbms_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO dbms_user;
