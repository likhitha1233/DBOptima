#!/usr/bin/env python3
"""
Real Data Dashboard with Premium UI - No Fake Data
Combines working logic from original app.py with premium styling
"""

import streamlit as st
import requests
import plotly.graph_objects as go
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
import os

# ---------------- CONFIG ----------------
API_HOST = os.getenv('API_HOST', '127.0.0.1')
API_PORT = os.getenv('API_PORT', '8001')
API_BASE_URL = f"http://{API_HOST}:{API_PORT}/api/v1"

# ---------------- ENHANCED UI IMPORTS ----------------
try:
    from enhanced_ui import (
        display_enhanced_metrics, add_custom_css,
        loading_skeleton, auto_refresh_manager,
        trend_chart_manager, anomaly_alert_manager,
        health_calculator
    )
    ENHANCED_UI_AVAILABLE = True
except ImportError:
    ENHANCED_UI_AVAILABLE = False

# ---------------- LUXURY CSS ----------------
st.set_page_config(
    page_title="Optimizer - AI Database",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=DM+Mono:wght@300;400;500&family=Outfit:wght@300;400;500&display=swap" rel="stylesheet">

<style>
/* Global Reset */
html, body, [class*="css"] {
    font-family: 'Outfit', sans-serif;
    background-color: #080810 !important;
    color: #E8E4DC !important;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
[data-testid="stSidebar"] { display: none; }
[data-testid="collapsedControl"] { display: none; }

/* App Container */
.main .block-container {
    padding: 2.5rem 3.5rem 4rem !important;
    max-width: 1400px !important;
    background: transparent !important;
}

/* Masthead */
.masthead {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    padding-bottom: 2.5rem;
    border-bottom: 1px solid rgba(201, 168, 76, 0.15);
    margin-bottom: 3rem;
}
.masthead-left { display: flex; flex-direction: column; gap: 4px; }
.masthead-badge {
    font-family: 'DM Mono', monospace;
    font-size: 20px;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    color: #C9A84C;
    opacity: 0.9;
    margin-bottom: 8px;
}
.masthead-title {
    font-family: 'Cormorant Garamond', serif;
    font-size: 4rem;
    font-weight: 300;
    letter-spacing: -0.01em;
    color: #F0EDE6;
    line-height: 1;
}
.masthead-title span { color: #C9A84C; font-weight: 500; }
.masthead-time {
    font-family: 'DM Mono', monospace;
    font-size: 22px;
    color: rgba(232, 228, 220, 0.35);
    letter-spacing: 0.12em;
}
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(201, 168, 76, 0.06);
    border: 1px solid rgba(201, 168, 76, 0.2);
    border-radius: 100px;
    padding: 8px 18px;
    font-family: 'DM Mono', monospace;
    font-size: 22px;
    letter-spacing: 0.1em;
    color: #C9A84C;
}
.status-dot {
    width: 12px; height: 12px;
    border-radius: 50%;
    background: #C9A84C;
    box-shadow: 0 0 16px rgba(201,168,76,0.6);
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}

/* KPI Cards */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1.25rem;
    margin-bottom: 2.5rem;
}
.kpi-card {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 1.6rem 1.5rem;
    position: relative;
    overflow: hidden;
    transition: border-color 0.3s, background 0.3s;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(201,168,76,0.35), transparent);
}
.kpi-card:hover {
    border-color: rgba(201,168,76,0.2);
    background: rgba(255,255,255,0.04);
}
.kpi-label {
    font-family: 'DM Mono', monospace;
    font-size: 20px;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: rgba(232,228,220,0.4);
    margin-bottom: 12px;
}
.kpi-value {
    font-family: 'Cormorant Garamond', serif;
    font-size: 4rem;
    font-weight: 500;
    color: #F0EDE6;
    line-height: 1;
}
.kpi-unit {
    font-family: 'DM Mono', monospace;
    font-size: 26px;
    color: rgba(201,168,76,0.7);
    margin-left: 6px;
}
.kpi-delta {
    font-family: 'DM Mono', monospace;
    font-size: 22px;
    margin-top: 10px;
    color: rgba(232,228,220,0.3);
}
.kpi-delta.up { color: rgba(130,200,150,0.7); }
.kpi-delta.down { color: rgba(220,120,100,0.7); }
.kpi-icon {
    position: absolute;
    top: 1.4rem; right: 1.4rem;
    font-size: 1.1rem;
    opacity: 0.15;
}

/* Section Headers */
.section-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 1.5rem;
    margin-top: 2rem;
}
.section-line {
    flex: 1;
    height: 1px;
    background: rgba(255,255,255,0.06);
}
.section-label {
    font-family: 'DM Mono', monospace;
    font-size: 20px;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    color: rgba(232,228,220,0.3);
    white-space: nowrap;
}
.section-accent {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #C9A84C;
    opacity: 0.6;
}

/* Panel */
.panel {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.055);
    border-radius: 20px;
    padding: 2rem;
    position: relative;
    overflow: hidden;
}
.panel::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(201,168,76,0.12), transparent);
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid rgba(255,255,255,0.06) !important;
    gap: 0 !important;
    padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border: none !important;
    color: rgba(232,228,220,0.35) !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 22px !important;
    letter-spacing: 0.18em !important;
    text-transform: uppercase !important;
    padding: 14px 28px !important;
    border-radius: 0 !important;
    transition: color 0.2s !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: rgba(232,228,220,0.65) !important;
    background: rgba(255,255,255,0.02) !important;
}
.stTabs [aria-selected="true"] {
    color: #C9A84C !important;
    border-bottom: 1px solid #C9A84C !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* Override Streamlit components */
[data-testid="stMetric"] {
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid rgba(255,255,255,0.055) !important;
    border-radius: 14px !important;
    padding: 1.2rem 1.4rem !important;
}
[data-testid="stMetricLabel"] {
    font-family: 'DM Mono', monospace !important;
    font-size: 20px !important;
    letter-spacing: 0.2em !important;
    text-transform: uppercase !important;
    color: rgba(232,228,220,0.35) !important;
}
[data-testid="stMetricValue"] {
    font-family: 'Cormorant Garamond', serif !important;
    font-size: 3rem !important;
    color: #F0EDE6 !important;
}

hr {
    border: none !important;
    border-top: 1px solid rgba(255,255,255,0.06) !important;
    margin: 2rem 0 !important;
}

/* Chart sizing */
.stPlotlyChart { 
    background: transparent !important; 
    max-width: 400px !important;
    margin: 0 auto !important;
}

/* Gauge chart container sizing */
.stPlotlyChart div.js-plotly-plot {
    max-width: 350px !important;
    margin: 0 auto !important;
}

/* Bar chart sizing */
.stPlotlyChart svg {
    max-height: 300px !important;
}

/* Column container for charts */
.stColumn > div {
    max-width: 400px !important;
    margin: 0 auto !important;
}

::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(201,168,76,0.2); border-radius: 2px; }

.stAlert {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 12px !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 20px !important;
}

.streamlit-expanderHeader {
    font-family: 'DM Mono', monospace !important;
    font-size: 20px !important;
    letter-spacing: 0.1em !important;
    color: rgba(232,228,220,0.5) !important;
    background: transparent !important;
}

code, pre {
    font-family: 'DM Mono', monospace !important;
    background: rgba(0,0,0,0.4) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    color: rgba(201,168,76,0.85) !important;
    border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)


# ---------------- API ----------------
def make_api_request(endpoint):
    try:
        res = requests.get(f"{API_BASE_URL}/{endpoint}", timeout=5)
        res.raise_for_status()
        return res.json()
    except:
        return None

def check_api_health():
    try:
        return requests.get(f"{API_BASE_URL}/health").status_code == 200
    except:
        return False


# ---------------- UI HELPERS ----------------
def metric_card(title, value):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{title}</div>
        <div class="kpi-value">{value}</div>
    </div>
    """, unsafe_allow_html=True)

def gauge(value, title, color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={'text': title},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': color},
            'steps': [
                {'range': [0, 60], 'color': "#374151"},
                {'range': [60, 85], 'color': "yellow"},
                {'range': [85, 100], 'color': "red"}
            ]
        }
    ))
    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig

def section_header(label):
    st.markdown(f"""
    <div class="section-header">
        <div class="section-accent"></div>
        <span class="section-label">{label}</span>
        <div class="section-line"></div>
    </div>
    """, unsafe_allow_html=True)


# ---------------- MAIN ----------------
def main():
    now = datetime.now()

    # MASTHEAD
    api_ok = check_api_health()
    status_label = "System Online" if api_ok else "API Offline"

    st.markdown(f"""
    <div class="masthead">
        <div class="masthead-left">
            <div class="masthead-badge"> AI Database Performance</div>
            <div class="masthead-title">Query <span>Optimizer</span></div>
            <div class="masthead-time">LAST SYNC - {now.strftime('%A, %d %b %Y  ·  %H:%M:%S')}</div>
        </div>
        <div class="status-pill">
            <div class="status-dot"></div>
            {status_label}
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not api_ok:
        st.markdown("""
        <div class="panel">
            <div class="kpi-label" style="margin-bottom:10px">Connection Error</div>
            <p style="font-family:'Outfit',sans-serif;font-size:14px;color:rgba(232,228,220,0.45);">
                The backend API is not reachable. Start the server to continue.
            </p>
        </div>
        """, unsafe_allow_html=True)
        st.code("uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload")
        return

    # TABS
    tab1, tab2, tab3, tab4 = st.tabs([
        "  Metrics  ", "  ML  ", "  Recommendations  ", "  API  "
    ])

    with tab1:
        display_metrics()

    with tab2:
        display_ml()

    with tab3:
        display_recommendations()

    with tab4:
        display_api()


# ---------------- METRICS ----------------
def display_metrics():
    if ENHANCED_UI_AVAILABLE:
        # Use enhanced UI with all features
        display_enhanced_metrics()
        return
    
    # Fallback to original UI if enhanced not available
    data = make_api_request("metrics")
    if not data:
        st.error("No data from backend API")
        return

    if "data" not in data or "system_metrics" not in data["data"]:
        st.error("Invalid data format from backend")
        return

    system = data["data"]["system_metrics"]

    cpu = system.get("cpu_percent")
    mem = system.get("memory_percent")
    disk = system.get("disk_percent")
    conn = system.get("connections")
    qps = system.get("queries_per_second")
    slow = system.get("slow_queries")
    
    # Validate we have real data
    if cpu is None or mem is None or disk is None:
        st.error("Incomplete system metrics from backend")
        return

    # KPI ROW - Premium styling
    section_header("Key Performance Indicators")
    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("CPU Usage", f"{cpu:.1f}%")
    with c2: metric_card("Memory", f"{mem:.1f}%")
    with c3: metric_card("Disk", f"{disk:.1f}%")
    with c4: metric_card("Connections", str(conn))

    # GAUGES - Premium styling
    section_header("Resource Utilization")
    g1, g2, g3 = st.columns(3)
    g1.plotly_chart(gauge(cpu, "CPU", "#3b82f6"), use_container_width=True)
    g2.plotly_chart(gauge(mem, "Memory", "#10b981"), use_container_width=True)
    g3.plotly_chart(gauge(disk, "Disk", "#f59e0b"), use_container_width=True)

    # DB METRICS - Premium styling
    section_header("Database Activity")
    c1, c2, c3 = st.columns(3)
    c1.metric("Queries/sec", f"{qps:.1f}")
    c2.metric("Slow Queries", slow)
    c3.metric("Active Sessions", conn)

    # BAR CHART - Premium styling
    section_header("System Overview")
    labels = ["CPU", "Memory", "Disk"]
    values = [cpu, mem, disk]

    plt.figure(figsize=(5,2.5))
    bars = plt.bar(labels, values, color=['#3b82f6', '#10b981', '#f59e0b'])
    for bar, val in zip(bars, values):
        plt.text(bar.get_x()+0.2, val+1, f"{val:.1f}%", color='white', fontweight='bold')
    plt.ylim(0,100)
    plt.style.use('dark_background')
    st.pyplot(plt, use_container_width=False)

    # ALERTS - Premium styling
    section_header("System Health")
    if cpu > 80:
        st.error(f"High CPU Usage: {cpu:.1f}%")
    elif mem > 85:
        st.error(f"High Memory Usage: {mem:.1f}%")
    elif disk > 90:
        st.error(f"Disk Critical: {disk:.1f}%")
    else:
        st.success("System Operating Normally")


# ---------------- ML ----------------
def display_ml():
    data = make_api_request("predictions")
    if not data:
        st.error("No ML data from backend")
        return

    if "data" not in data or "predictions" not in data["data"]:
        st.error("Invalid ML data format")
        return

    preds = data["data"]["predictions"]

    # Safe access to predictions
    cpu_pred = preds.get("cpu_usage", {})
    mem_pred = preds.get("memory_usage", {})
    disk_pred = preds.get("disk_usage", {})

    cpu = cpu_pred.get("predicted")
    mem = mem_pred.get("predicted")
    disk = disk_pred.get("predicted")

    if cpu is None or mem is None or disk is None:
        st.error("Incomplete ML prediction data")
        return

    section_header("ML Predictions")
    c1, c2, c3 = st.columns(3)
    c1.metric("Predicted CPU", f"{cpu:.1f}%")
    c2.metric("Predicted Memory", f"{mem:.1f}%")
    c3.metric("Predicted Disk", f"{disk:.1f}%")

    # Show confidence if available
    section_header("Model Confidence")
    c1, c2, c3 = st.columns(3)
    cpu_conf = cpu_pred.get("confidence")
    mem_conf = mem_pred.get("confidence")
    disk_conf = disk_pred.get("confidence")

    if cpu_conf:
        c1.metric("CPU Model", f"{cpu_conf*100:.1f}%")
    if mem_conf:
        c2.metric("Memory Model", f"{mem_conf*100:.1f}%")
    if disk_conf:
        c3.metric("Disk Model", f"{disk_conf*100:.1f}%")


# ---------------- RECOMMENDATIONS ----------------
def display_recommendations():
    data = make_api_request("recommendations/indexes")
    if not data:
        st.error("No recommendations from backend")
        return

    if "data" not in data or not isinstance(data["data"], dict):
        st.error("Invalid recommendation data format")
        return

    recs = data["data"].get("recommendations", [])
    if not isinstance(recs, list):
        recs = []

    if not recs:
        section_header("System Optimization")
        st.info("No recommendations available - system is well optimized")
        return

    section_header("Database Recommendations")
    for r in recs:
        with st.expander(f"{r.get('type', 'Recommendation')} - {r.get('priority', 'Unknown')}"):
            st.write("**Priority:**", r.get("priority", "Unknown"))
            st.write("**Reason:**", r.get("reason", "No reason provided"))
            if r.get("sql_statement"):
                st.write("**SQL Statement:**")
                st.code(r["sql_statement"])


# ---------------- API ----------------
def display_api():
    section_header("API Connection Status")
    
    # Test endpoints
    endpoints = [
        ("Health", "health"),
        ("Metrics", "metrics"),
        ("ML Predictions", "predictions"),
        ("Recommendations", "recommendations/indexes")
    ]
    
    for name, endpoint in endpoints:
        data = make_api_request(endpoint)
        if data:
            st.success(f"**{name}**: Connected")
        else:
            st.error(f"**{name}**: Failed")
    
    section_header("Configuration")
    col1, col2 = st.columns(2)
    col1.metric("API Host", API_HOST)
    col2.metric("API Port", API_PORT)


# ---------------- RUN ----------------
if __name__ == "__main__":
    main()
