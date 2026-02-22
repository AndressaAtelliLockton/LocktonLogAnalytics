# c:\Users\Andressa.Atelli\Documents\locktonloganalytics\log_analyzer\log_parser.py
# Este arquivo contém funções para parsing básico e enriquecimento de logs.

import pandas as pd
import re
import numpy as np
import json

# --- Regex Pré-compiladas para Performance ---
CPF_PATTERN = re.compile(r'\d{3}\.\d{3}\.\d{3}-\d{2}')
EMAIL_PATTERN = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
IP_PATTERN = re.compile(r'(?<!\d)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?!\d)')
NUM_PATTERN = re.compile(r'\d+')
UUID_PATTERN = re.compile(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', re.IGNORECASE)

def process_log_data(df, config):
    """
    Processa um DataFrame de logs, adicionando colunas de categoria, nível de log e tamanho da mensagem.
    """
    if df.empty:
        return pd.DataFrame(columns=['timestamp', 'source', 'message', 'category', 'log_level', 'message_length']), {}

    if not config:
        raise ValueError("Configuração para categorização de logs é inválida.")

    df_proc = df.copy()
    df_proc = df_proc.reset_index(drop=True)
    rename_map = {c: c.lower() for c in df_proc.columns if c.lower() in ['message', 'source', 'timestamp']}
    df_proc.rename(columns=rename_map, inplace=True)
    df_proc['message'] = df_proc['message'].astype(str)
    
    df_proc['message_length'] = df_proc['message'].str.len()
    df_proc['log_level'] = extract_log_level(df_proc)
    df_proc['category'] = categorize_log(df_proc, config)
    
    output_cols = ['timestamp', 'source', 'message', 'category', 'log_level', 'message_length']
    return df_proc[output_cols], df_proc['category'].value_counts().to_dict()

def categorize_log(df, config):
    """
    Categoriza logs com base em keywords e níveis de log definidos no arquivo de configuração.
    """
    categories = pd.Series('Não categorizado', index=df.index)
    if 'categories' not in config:
        return categories

    for cat in config['categories']:
        cat_mask = pd.Series(False, index=df.index)
        if 'log_levels' in cat:
            cat_mask |= df['log_level'].astype(str).str.lower().isin([l.lower() for l in cat['log_levels']])
        if 'keywords' in cat:
            pattern = '|'.join(map(re.escape, cat.get('keywords', [])))
            cat_mask |= df['message'].astype(str).str.contains(pattern, case=False, regex=True, na=False)
        
        categories[cat_mask & (categories == 'Não categorizado')] = cat['name']
    return categories

def extract_log_level(df):
    """
    Extrai o nível de log das mensagens de forma vetorizada para performance.
    """
    levels = pd.Series('Não Identificado', index=df.index)
    extracted = df['message'].astype(str).str.extract(r'(?i)"?LogLevel"?\s*[:=]\s*"?(\w+)"?', expand=False)
    levels[extracted.notna()] = extracted[extracted.notna()]
    
    msg_lower = df['message'].astype(str).str.lower()
    for key, label in {'fail:': 'Fail', 'error:': 'Error', 'warning:': 'Warning'}.items():
        mask = (levels == 'Não Identificado') & msg_lower.str.contains(key, regex=False)
        levels[mask] = label
        
    return levels.astype(str).str.capitalize()

def mask_sensitive_data(df):
    """Ofusca dados sensíveis (CPF, email, IP) para conformidade com LGPD."""
    if df.empty: return df
    df_masked = df.copy()
    msg = df_masked['message'].astype(str)
    msg = msg.str.replace(CPF_PATTERN, '***.***.***-**', regex=True)
    msg = msg.str.replace(EMAIL_PATTERN, '*****@*****.***', regex=True)
    msg = msg.str.replace(IP_PATTERN, '***.***.***.***', regex=True)
    df_masked['message'] = msg
    return df_masked

def parse_log_entry(message):
    """Tenta decodificar uma mensagem de log como JSON, senão a retorna como texto."""
    try:
        return json.loads(message)
    except (json.JSONDecodeError, TypeError):
        return {'message_text': str(message)}

def generate_log_patterns(df):
    """Gera padrões de log para agrupar mensagens similares."""
    if df.empty: return pd.DataFrame()
    
    sigs = df['message'].astype(str).str.replace(NUM_PATTERN, '[NUM]', regex=True)
    sigs = sigs.str.replace(UUID_PATTERN, '[UUID]', regex=True)
    df['signature'] = sigs.str.slice(0, 200)
    
    patterns = df.groupby('signature').agg(
        count=('timestamp', 'size'),
        first_seen=('timestamp', 'min'),
        last_seen=('timestamp', 'max'),
        example_message=('message', 'first'),
        log_level=('log_level', 'first'),
        sources=('source', lambda x: list(set(x)))
    ).reset_index().sort_values('count', ascending=False)
    
    patterns['percent'] = (patterns['count'] / len(df)) * 100
    return patterns