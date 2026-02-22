# c:\Users\Andressa.Atelli\Documents\locktonloganalytics\log_analyzer\simulation.py
# Este arquivo contém funções para simulação de alertas.

import pandas as pd
import requests
from datetime import datetime
from .metrics_extraction import extract_latency_metrics
from .database import ingest_logs_to_db

def simulate_alerts(df, latency_threshold=None, keyword=None, log_levels=None):
    """Simula a dispração de alertas com base em um conjunto de regras."""
    alerts = df.copy()
    if log_levels:
        alerts = alerts[alerts['log_level'].isin(log_levels)]
    if keyword:
        alerts = alerts[alerts['message'].astype(str).str.contains(keyword, case=False, na=False)]
    if latency_threshold:
        latencies = extract_latency_metrics(alerts)
        if not latencies.empty:
            alerts = alerts.join(latencies.set_index(alerts.index)) # Join preserves original df structure
            alerts = alerts[alerts['latency_ms'] > latency_threshold]
    return alerts

def run_synthetic_check(name, url):
    """Executa um check sintético (ping HTTP) e ingere o resultado como um log."""
    try:
        start = datetime.now()
        response = requests.get(url, timeout=10)
        duration = (datetime.now() - start).total_seconds() * 1000
        status = f"SUCCESS ({response.status_code})"
    except Exception as e:
        status = f"ERROR"
        duration = -1
        
    message = f"SYNTHETIC | Check: {name} | URL: {url} | Status: {status} | Duration: {duration:.0f}ms"
    df = pd.DataFrame([{"timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "source": "Synthetic-Monitor", "message": message}])
    ingest_logs_to_db(df)
