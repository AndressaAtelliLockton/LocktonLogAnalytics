# c:\Users\Andressa.Atelli\Documents\locktonloganalytics\log_analyzer\metrics_extraction.py
# Este arquivo contém funções para extração de métricas numéricas dos logs.

import pandas as pd
import re
import numpy as np

LATENCY_PATTERN = re.compile(r'(?:duration|time|took)[:=]\s*(\d+(?:\.\d+)?)(?:\s*(ms|s|us|µs))?', re.IGNORECASE)

def extract_latency_metrics(df):
    """Extrai métricas de latência (duration, time, took) das mensagens."""
    if df.empty: return pd.DataFrame()
    work_df = df.reset_index(drop=True)
    extracted = work_df['message'].astype(str).str.extract(LATENCY_PATTERN)
    if extracted.empty: return pd.DataFrame()

    extracted.columns = ['value', 'unit']
    valid = extracted['value'].notna()
    result = work_df.loc[valid, ['timestamp', 'source']].copy()
    result['latency_ms'] = pd.to_numeric(extracted.loc[valid, 'value'], errors='coerce')
    
    # Converte unidades para ms
    result.loc[extracted.loc[valid, 'unit'] == 's', 'latency_ms'] *= 1000
    result.loc[extracted.loc[valid, 'unit'].isin(['us', 'µs']), 'latency_ms'] /= 1000
    
    return result

def detect_bottlenecks(df, threshold_ms=1000):
    """Identifica os serviços ('sources') com as maiores latências médias."""
    latency_df = extract_latency_metrics(df)
    if latency_df.empty: return pd.DataFrame()
    
    slow_logs = latency_df[latency_df['latency_ms'] > threshold_ms]
    if slow_logs.empty: return pd.DataFrame()
    
    return slow_logs.groupby('source').agg(
        slow_count=('latency_ms', 'size'),
        avg_latency=('latency_ms', 'mean'),
        max_latency=('latency_ms', 'max')
    ).reset_index().sort_values('avg_latency', ascending=False)

def generate_stack_trace_metrics(df):
    """Agrega stack traces de logs de erro para identificar os caminhos de código mais problemáticos."""
    error_df = df[df['log_level'].isin(['Error', 'Fail', 'Critical', 'Fatal', 'Warning'])]
    if error_df.empty: return pd.DataFrame()

    stack_pattern = re.compile(r'(File "[^"]+", line \d+)|(at\s+[^\n]+)')
    stack_counts = {}

    for row in error_df.itertuples():
        matches = stack_pattern.findall(str(row.message))
        if matches:
            clean_stack = [m[0] or m[1] for m in matches]
            signature = ";".join(clean_stack)
            stack_counts[signature] = stack_counts.get(signature, 0) + 1
        else:
            signature = f"{row.source};{str(row.message)[:80]}"
            stack_counts[signature] = stack_counts.get(signature, 0) + 1
            
    if not stack_counts: return pd.DataFrame()
    
    data = [{'stack_trace': k, 'count': v, 'depth': k.count(';')} for k, v in stack_counts.items()]
    return pd.DataFrame(data).sort_values('count', ascending=False)

def extract_system_metrics(df):
    """Extrai métricas de sistema (CPU, memória) dos logs."""
    if df.empty: return pd.DataFrame()
    metrics = df.copy()
    metrics = metrics.reset_index(drop=True)
    metrics['cpu'] = metrics['message'].astype(str).str.extract(r'CPU.*?(\d+\.?\d*)', re.IGNORECASE, expand=False).astype(float)
    metrics['memory'] = metrics['message'].astype(str).str.extract(r'Memory.*?(\d+\.?\d*)', re.IGNORECASE, expand=False).astype(float)
    return metrics.dropna(subset=['cpu', 'memory'], how='all')

def extract_api_metrics(df):
    """
    Extrai métricas de chamadas de API (método, endpoint, status) e categoriza os status codes.
    Um status 0 é categorizado como um potencial problema de cliente/rede.
    """
    if df.empty:
        return pd.DataFrame()
    
    work_df = df.reset_index(drop=True)
    pattern = r'(GET|POST|PUT|DELETE)\s+([^\s?]+).*?(?:status.*?(\d{1,3}))?'
    extracted = work_df['message'].astype(str).str.extract(pattern, flags=re.IGNORECASE)
    if extracted.empty:
        return pd.DataFrame()

    result = work_df[['timestamp', 'source']].copy()
    result['method'] = extracted[0].str.upper()
    result['endpoint'] = extracted[1]
    
    status_codes = pd.to_numeric(extracted[2], errors='coerce')
    result['status_code'] = status_codes

    conditions = [
        status_codes == 0,
        status_codes.between(100, 199),
        status_codes.between(200, 299),
        status_codes.between(300, 399),
        status_codes.between(400, 499),
        status_codes.between(500, 599)
    ]
    categories = [
        'Client-Side/Network Issue',
        'Informational',
        'Success',
        'Redirection',
        'Client Error',
        'Server Error'
    ]
    result['status_category'] = np.select(conditions, categories, default='Unknown')
    
    return result.dropna(subset=['method'])
