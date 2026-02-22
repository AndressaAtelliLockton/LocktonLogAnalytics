# c:\Users\Andressa.Atelli\Documents\locktonloganalytics\log_analyzer\dependency_analysis.py
# Este arquivo contém funções para análise de dependências entre serviços.

import pandas as pd
import re

IP_PATTERN = re.compile(r'(?<!\d)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?!\d)')
URL_PATTERN = re.compile(r'https?://([\w\-\.]+)(?::\d+)?')
NUM_PATTERN = re.compile(r'\d+')

def infer_service_dependencies(df):
    """Infere dependências entre serviços analisando menções de sources, IPs e URLs nos logs."""
    if df.empty or 'source' not in df.columns: return pd.DataFrame()

    edges = []
    sources = [s for s in df['source'].unique() if isinstance(s, str) and len(s) > 3]
    source_pattern = '|'.join(map(re.escape, sources))
    
    for row in df.itertuples():
        msg = str(row.message)
        # Dependências internas
        if source_pattern:
            for target in re.findall(source_pattern, msg, re.IGNORECASE):
                if row.source != target:
                    edges.append((row.source, target))
        # Dependências externas
        for target in re.findall(IP_PATTERN, msg):
            edges.append((row.source, target))
        for target in re.findall(URL_PATTERN, msg):
            edges.append((row.source, target))
            
    if not edges: return pd.DataFrame()
    return pd.DataFrame(edges, columns=['source', 'target']).value_counts().reset_index(name='count')

def compare_log_datasets(df_main, df_ref):
    """Compara dois DataFrames de logs (atual vs. referência) e retorna as principais diferenças."""
    metrics = {}
    metrics['vol_main'] = len(df_main)
    metrics['vol_ref'] = len(df_ref)
    metrics['vol_delta'] = metrics['vol_main'] - metrics['vol_ref']
    
    err_rate = lambda df: (df[df['log_level'].isin(['Error', 'Fail'])].shape[0] / len(df) * 100) if not df.empty else 0
    metrics['err_rate_main'] = err_rate(df_main)
    metrics['err_rate_ref'] = err_rate(df_ref)
    
    get_sigs = lambda df: set(df['message'].astype(str).str.replace(NUM_PATTERN, '<NUM>', regex=True).unique()) if not df.empty else set()
    sigs_main = get_sigs(df_main[df_main['log_level'].isin(['Error', 'Fail'])])
    sigs_ref = get_sigs(df_ref[df_ref['log_level'].isin(['Error', 'Fail'])])
    metrics['new_error_signatures'] = list(sigs_main - sigs_ref)
    
    return metrics
