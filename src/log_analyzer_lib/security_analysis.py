# c:\Users\Andressa.Atelli\Documents\locktonloganalytics\log_analyzer\security_analysis.py
# Este arquivo contém funções para análise de segurança dos logs.

import pandas as pd
import re

IP_PATTERN = re.compile(r'(?<!\d)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?!\d)')

def analyze_security_threats(df):
    """Analisa logs em busca de IPs com alta taxa de erro, indicando possíveis ameaças."""
    if df.empty: return pd.DataFrame()
    
    # Reset index to avoid shape mismatch if df has duplicate indices
    work_df = df.reset_index(drop=True)
    ips = work_df['message'].astype(str).str.findall(IP_PATTERN).explode().dropna()
    if ips.empty: return pd.DataFrame()

    sec_df = work_df.loc[ips.index].copy()
    sec_df['ip'] = ips.values
    
    stats = sec_df.groupby('ip').agg(
        total_logs=('timestamp', 'size'),
        error_count=('log_level', lambda x: x.isin(['Error', 'Fail']).sum())
    ).reset_index()
    stats['error_rate'] = stats['error_count'] / stats['total_logs']
    
    def classify_status(row):
        if row['error_rate'] > 0.5 and row['total_logs'] > 5: return '🔴 Crítico'
        if row['error_rate'] > 0.2: return '🟡 Suspeito'
        return '🟢 Normal'
    stats['status'] = stats.apply(classify_status, axis=1)
    
    return stats.sort_values('error_count', ascending=False)
