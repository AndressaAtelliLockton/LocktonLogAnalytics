# -*- coding: utf-8 -*-
"""
Módulo de funções utilitárias diversas.
"""
import json
import pandas as pd
import os

try:
    import streamlit as st
except ImportError:
    st = None

def get_secret(key, default=""):
    """Recupera segredos de variáveis de ambiente ou Streamlit secrets."""
    # 1. Environment Variable (Prioridade para Docker/Produção)
    if key in os.environ:
        return os.environ[key]
        
    # 2. Streamlit Secrets (Fallback para Desenvolvimento Local)
    if st is not None:
        try:
            return st.secrets.get(key, default)
        except Exception:
            # Em produção (Docker), o arquivo secrets.toml não existe, então ignoramos o erro.
            pass
    return default

def load_config(config_path='config.json'):
    """Carrega o arquivo de configuração JSON de forma segura."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, f"Erro: Arquivo de configuração '{config_path}' não encontrado."
    except json.JSONDecodeError:
        return None, f"Erro: Arquivo '{config_path}' não é um JSON válido."
    except Exception as e:
        return None, f"Erro inesperado ao carregar config: {e}"

def get_context_logs(df, target_timestamp, source, window_seconds=300):
    """
    Recupera logs do mesmo source em uma janela de tempo ao redor do evento (Contexto).
    """
    if df.empty:
        return pd.DataFrame()
    
    # OTIMIZAÇÃO: Filtra por source primeiro para reduzir drasticamente o volume de dados
    # antes de realizar operações custosas como cópia e conversão de data.
    df_source = df[df['source'] == source]
    
    if df_source.empty:
        return pd.DataFrame()
        
    # Trabalha com uma cópia apenas do subconjunto
    df_ctx = df_source.copy()
    df_ctx['timestamp'] = pd.to_datetime(df_ctx['timestamp'], errors='coerce')
    target_ts = pd.to_datetime(target_timestamp)
    
    # Filtra por source e janela de tempo (+/- 5 min por padrão)
    start_time = target_ts - pd.Timedelta(seconds=window_seconds)
    end_time = target_ts + pd.Timedelta(seconds=window_seconds)
    
    # Filtra logs dentro da janela (source já foi filtrado)
    context = df_ctx[(df_ctx['timestamp'] >= start_time) & (df_ctx['timestamp'] <= end_time)]
    return context.sort_values('timestamp')
