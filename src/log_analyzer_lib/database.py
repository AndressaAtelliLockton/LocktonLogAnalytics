# -*- coding: utf-8 -*-
"""
Módulo para todas as interações com o banco de dados SQLite.
"""
import hashlib
import pandas as pd
from datetime import datetime
import os
import re
import json
import zlib
import socket
import warnings
import json

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Constantes do Módulo ---
DB_FILE = 'log_analysis_data.json'

# --- Estruturas em Memória (Globais) ---
_AI_CACHE = {}          # message_hash -> {data}
_SETTINGS = {}          # key -> value
_COLLECTED_LOGS = []    # List of dicts
_LOG_HASHES = set()     # Set of hashes for deduplication
_METRIC_DEFINITIONS = {} # id -> {definition}
_METRIC_VALUES = []     # List of {metric_id, timestamp, value}
_RUM_EVENTS = []        # List of {timestamp, url, type, ...}
_METRIC_ID_COUNTER = 1

# --- Funções de Banco de Dados (Persistência) ---

def init_db():
    """
    Inicializa as estruturas em memória e carrega dados do disco se existirem.
    """
    global _AI_CACHE, _SETTINGS, _COLLECTED_LOGS, _LOG_HASHES, _METRIC_DEFINITIONS, _METRIC_VALUES, _RUM_EVENTS, _METRIC_ID_COUNTER
    _AI_CACHE = {}
    _SETTINGS = {}
    _COLLECTED_LOGS = []
    _LOG_HASHES = set()
    _METRIC_DEFINITIONS = {}
    _METRIC_VALUES = []
    _RUM_EVENTS = []
    _METRIC_ID_COUNTER = 1
    
    load_from_disk()

def save_to_disk():
    """Salva o estado atual da memória em um arquivo JSON."""
    data = {
        "ai_cache": _AI_CACHE,
        "settings": _SETTINGS,
        "collected_logs": _COLLECTED_LOGS,
        "metric_definitions": _METRIC_DEFINITIONS,
        "metric_values": _METRIC_VALUES,
        "rum_events": _RUM_EVENTS,
        "metric_id_counter": _METRIC_ID_COUNTER
    }
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, default=str, indent=2)
        print(f"✅ Dados salvos em {DB_FILE}")
        return True
    except Exception as e:
        print(f"❌ Erro ao salvar dados em disco: {e}")
        return False

def load_from_disk():
    """Carrega o estado do arquivo JSON para a memória."""
    global _AI_CACHE, _SETTINGS, _COLLECTED_LOGS, _LOG_HASHES, _METRIC_DEFINITIONS, _METRIC_VALUES, _RUM_EVENTS, _METRIC_ID_COUNTER
    
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _AI_CACHE = data.get("ai_cache", {})
                _SETTINGS = data.get("settings", {})
                _COLLECTED_LOGS = data.get("collected_logs", [])
                _LOG_HASHES = {l['log_hash'] for l in _COLLECTED_LOGS}
                _METRIC_DEFINITIONS = {int(k): v for k, v in data.get("metric_definitions", {}).items()}
                _METRIC_VALUES = data.get("metric_values", [])
                _RUM_EVENTS = data.get("rum_events", [])
                _METRIC_ID_COUNTER = data.get("metric_id_counter", 1)
            print(f"✅ Dados carregados de {DB_FILE} ({len(_COLLECTED_LOGS)} logs)")
        except Exception as e:
            print(f"⚠️ Erro ao carregar dados do disco: {e}")

def get_cached_ai_analysis(message):
    """Busca no cache uma análise de IA para uma mensagem específica."""
    msg_hash = calculate_log_hash("", "", str(message))
    entry = _AI_CACHE.get(msg_hash)
    return entry['ai_response'] if entry else None

def update_ai_feedback(message, score):
    """Atualiza o score de feedback (útil/não útil) para uma análise da IA."""
    msg_hash = calculate_log_hash("", "", str(message))
    if msg_hash in _AI_CACHE:
        _AI_CACHE[msg_hash]['feedback_score'] = score
        return True
    return False

def get_ai_feedback(message):
    """Recupera o score de feedback de uma análise de IA."""
    msg_hash = calculate_log_hash("", "", str(message))
    entry = _AI_CACHE.get(msg_hash)
    return entry['feedback_score'] if entry else 0

def save_ai_analysis(message, response, user="System"):
    """Salva o resultado de uma análise da IA no banco de dados para cache."""
    msg_hash = calculate_log_hash("", "", str(message))
    _AI_CACHE[msg_hash] = {
        'original_message': str(message),
        'ai_response': response,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'requested_by': user,
        'feedback_score': 0
    }

def save_setting(key, value):
    """Salva um par chave-valor nas configurações do banco de dados."""
    _SETTINGS[key] = str(value)
    save_to_disk()

def get_setting(key, default=""):
    """
    Recupera uma configuração.
    Prioridade: Memória -> Variáveis de Ambiente.
    """
    val = _SETTINGS.get(key)
    if val is not None:
        return val
    return os.environ.get(key.upper(), default)

def get_db_stats():
    """Retorna estatísticas sobre o cache da IA."""
    if not _AI_CACHE:
        return {"count": 0, "first": None, "last": None}
    
    timestamps = [e['timestamp'] for e in _AI_CACHE.values()]
    return {
        "count": len(_AI_CACHE),
        "first": min(timestamps) if timestamps else None,
        "last": max(timestamps) if timestamps else None
    }

def clear_ai_cache():
    """Limpa completamente a tabela de cache da IA."""
    _AI_CACHE.clear()
    return True

def get_all_cached_analyses():
    """Retorna todo o histórico de análises da IA como um DataFrame."""
    if not _AI_CACHE:
        return pd.DataFrame()
    return pd.DataFrame(list(_AI_CACHE.values()))

def calculate_log_hash(timestamp, source, message):
    """Gera um hash MD5 para uma entrada de log para deduplicação."""
    content = f"{timestamp}{source}{message}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def ingest_logs_to_db(df):
    """
    Ingestão de logs em memória.
    """
    if df.empty:
        return 0
    
    count = 0
    # Garante que as colunas existam
    if 'timestamp' not in df.columns: df['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if 'source' not in df.columns: df['source'] = 'Unknown'
    if 'message' not in df.columns: df['message'] = ''

    for _, row in df.iterrows():
        ts = str(row['timestamp'])
        src = str(row['source'])
        msg = str(row['message'])
        log_hash = calculate_log_hash(ts, src, msg)
        
        if log_hash not in _LOG_HASHES:
            _LOG_HASHES.add(log_hash)
            _COLLECTED_LOGS.append({
                'log_hash': log_hash,
                'timestamp': ts,
                'source': src,
                'message': msg,
                'ingested_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            count += 1
    
    # Processa métricas e RUM nos novos logs
    if count > 0:
        extract_and_save_metrics(df)
        extract_rum_data(df)
        
    return count

def get_collected_logs(limit=50000):
    """Recupera os logs mais recentes do banco de dados local."""
    if not _COLLECTED_LOGS:
        return pd.DataFrame()
    
    # Retorna os últimos 'limit' logs
    return pd.DataFrame(_COLLECTED_LOGS[-limit:])

def clean_old_logs(retention_days=30):
    """Remove logs e dados de métricas/RUM mais antigos que o período de retenção."""
    # Implementação simplificada: Limpa se a lista ficar muito grande (> 100k)
    global _COLLECTED_LOGS, _LOG_HASHES
    if len(_COLLECTED_LOGS) > 100000:
        removed = len(_COLLECTED_LOGS) - 50000
        _COLLECTED_LOGS = _COLLECTED_LOGS[-50000:]
        _LOG_HASHES = {l['log_hash'] for l in _COLLECTED_LOGS}
        return removed
    return 0

def search_logs_in_db(query=None, start_date=None, end_date=None, source=None, limit=10000):
    """
    Realiza uma busca avançada na lista de logs em memória.
    """
    if not _COLLECTED_LOGS:
        return pd.DataFrame()
    
    df = pd.DataFrame(_COLLECTED_LOGS)
    
    # Filtros
    if source and source != "Todos":
        df = df[df['source'] == source]
    
    if query:
        df = df[df['message'].str.contains(query, case=False, na=False)]
        
    if start_date:
        df = df[pd.to_datetime(df['timestamp']) >= pd.to_datetime(start_date)]
        
    if end_date:
        # Ajusta para o final do dia
        end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        df = df[pd.to_datetime(df['timestamp']) <= end_dt]
        
    return df.tail(limit)

def get_unique_sources_from_db():
    """Retorna uma lista de 'sources' únicos do banco para uso em filtros."""
    if not _COLLECTED_LOGS:
        return []
    return sorted(list(set(l['source'] for l in _COLLECTED_LOGS)))

def save_metric_definition(name, regex, metric_type="counter", threshold=0.0):
    """Salva uma nova definição de métrica customizada no banco."""
    global _METRIC_ID_COUNTER
    metric_id = _METRIC_ID_COUNTER
    _METRIC_DEFINITIONS[metric_id] = {
        'id': metric_id,
        'name': name,
        'regex': regex,
        'type': metric_type,
        'threshold': threshold
    }
    _METRIC_ID_COUNTER += 1
    return True, "Métrica salva em memória."

def get_metric_definitions():
    """Retorna todas as definições de métricas customizadas como um DataFrame."""
    if not _METRIC_DEFINITIONS:
        return pd.DataFrame()
    return pd.DataFrame(list(_METRIC_DEFINITIONS.values()))

def delete_metric_definition(metric_id):
    """Remove uma definição de métrica e todos os seus dados históricos."""
    if metric_id in _METRIC_DEFINITIONS:
        del _METRIC_DEFINITIONS[metric_id]
        # Remove valores associados
        global _METRIC_VALUES
        _METRIC_VALUES = [v for v in _METRIC_VALUES if v['metric_id'] != metric_id]

def extract_and_save_metrics(df):
    """
    Processa um DataFrame de logs e extrai valores de métricas.
    """
    if df.empty or not _METRIC_DEFINITIONS:
        return 0
    
    count = 0
    for m_id, m_def in _METRIC_DEFINITIONS.items():
        regex = m_def['regex']
        m_type = m_def['type']
        
        extracted = df['message'].astype(str).str.extract(regex, flags=re.IGNORECASE, expand=False)
        valid = extracted.notna()
        
        if valid.any():
            matches = df.loc[valid, ['timestamp']].copy()
            if m_type == 'gauge':
                matches['value'] = pd.to_numeric(extracted[valid], errors='coerce').fillna(0)
            else:
                matches['value'] = 1.0
            
            for _, row in matches.iterrows():
                _METRIC_VALUES.append({
                    'metric_id': m_id,
                    'timestamp': row['timestamp'],
                    'value': row['value']
                })
                count += 1
    return count

def get_metric_history(metric_id, days=7):
    """Recupera o histórico de valores de uma métrica para visualização."""
    if not _METRIC_VALUES:
        return pd.DataFrame()
    
    values = [v for v in _METRIC_VALUES if v['metric_id'] == metric_id]
    return pd.DataFrame(values)

def extract_rum_data(df):
    """
    Extrai dados de RUM (Simples).
    """
    if df.empty: return 0
    
    # Regex simples para capturar vitals (LCP=123)
    rum_pattern = r'(LCP|CLS|INP|FID)[:=]\s*(\d+(?:\.\d+)?)'
    extracted = df['message'].astype(str).str.extractall(rum_pattern)
    
    count = 0
    for idx, row in extracted.iterrows():
        # idx[0] é o index do log original
        log_idx = idx[0]
        if log_idx in df.index:
            ts = df.loc[log_idx, 'timestamp']
            _RUM_EVENTS.append({
                'timestamp': ts,
                'type': 'vital',
                'name': row[0],
                'value': float(row[1]),
                'url': 'Unknown'
            })
            count += 1
    return count

def get_rum_stats(days=7):
    """Recupera estatísticas de RUM do banco de dados."""
    if not _RUM_EVENTS:
        return pd.DataFrame()
    return pd.DataFrame(_RUM_EVENTS)
