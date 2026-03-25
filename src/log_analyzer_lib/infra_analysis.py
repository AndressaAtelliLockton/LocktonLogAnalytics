import pandas as pd
import re

def extract_system_metrics(df):
    """
    Extrai métricas de sistema (CPU, Memória, Disco, Rede) de mensagens de log.
    Desacoplado para facilitar manutenção e garantir resiliência.
    """
    if df is None or df.empty:
        return pd.DataFrame()
        
    metrics_df = df.copy()
    metrics_df = metrics_df.reset_index(drop=True)
    
    # 1. Tenta usar as colunas estruturadas caso o log já venha parseado do Graylog
    if 'cpu_valor' in metrics_df.columns and 'mem_valor' in metrics_df.columns:
        metrics_df['cpu'] = pd.to_numeric(metrics_df['cpu_valor'], errors='coerce')
        metrics_df['memory'] = pd.to_numeric(metrics_df['mem_valor'], errors='coerce')
        metrics_df['disk'] = 0.0
        metrics_df['network'] = 0.0
        
        if not metrics_df['cpu'].isna().all() or not metrics_df['memory'].isna().all():
            return metrics_df[['timestamp', 'source', 'cpu', 'memory', 'disk', 'network']].dropna(subset=['cpu', 'memory'], how='all')

    # 2. Fallback: Expressões Regulares no texto da mensagem
    msg_str = metrics_df['message'].astype(str)
    
    # Regex flexível para capturar (Ex: "CPU: 50%", "memory=1024", "disk usage 80")
    cpu_regex = r'(?:cpu|load|processor)\s*[:=]?\s*(?:usage)?\s*(\d+(?:\.\d+)?)'
    mem_regex = r'(?:memory|mem|ram)\s*[:=]?\s*(?:usage)?\s*(\d+(?:\.\d+)?)'
    disk_regex = r'(?:disk|storage|hdd)\s*[:=]?\s*(?:usage)?\s*(\d+(?:\.\d+)?)'
    net_regex = r'(?:network|net|bw)\s*[:=]?\s*(?:usage)?\s*(\d+(?:\.\d+)?)'
    
    metrics_df['cpu'] = msg_str.str.extract(cpu_regex, flags=re.IGNORECASE, expand=False).astype(float)
    metrics_df['memory'] = msg_str.str.extract(mem_regex, flags=re.IGNORECASE, expand=False).astype(float)
    metrics_df['disk'] = msg_str.str.extract(disk_regex, flags=re.IGNORECASE, expand=False).astype(float)
    metrics_df['network'] = msg_str.str.extract(net_regex, flags=re.IGNORECASE, expand=False).astype(float)
    
    valid_metrics = metrics_df.dropna(subset=['cpu', 'memory', 'disk', 'network'], how='all')
    
    return valid_metrics[['timestamp', 'source', 'cpu', 'memory', 'disk', 'network']]