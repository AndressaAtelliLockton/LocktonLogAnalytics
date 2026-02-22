import streamlit as st
import log_analyzer as lam
import pandas as pd

# Wrapper para cache do processamento de dados (Melhora Performance)
@st.cache_data
def cached_process_log_data(df, config):
    return lam.process_log_data(df, config)

# Wrappers com cache para funções pesadas (Performance)
@st.cache_data
def cached_detect_volume_anomalies(df, z_score_threshold):
    return lam.detect_volume_anomalies(df, z_score_threshold=z_score_threshold)

@st.cache_data
def cached_detect_rare_patterns(df, rarity_threshold):
    return lam.detect_rare_patterns(df, rarity_threshold=rarity_threshold)

@st.cache_data
def cached_group_incidents(df):
    return lam.group_incidents(df)

@st.cache_data
def cached_analyze_security_threats(df):
    return lam.analyze_security_threats(df)

@st.cache_data
def cached_extract_latency_metrics(df):
    return lam.extract_latency_metrics(df)

@st.cache_data
def cached_extract_system_metrics(df):
    return lam.extract_system_metrics(df)

@st.cache_data
def cached_infer_service_dependencies(df):
    return lam.infer_service_dependencies(df)

@st.cache_data
def cached_generate_log_patterns(df):
    return lam.generate_log_patterns(df)

@st.cache_data
def cached_mask_sensitive_data(df):
    return lam.mask_sensitive_data(df)

@st.cache_data
def cached_generate_volume_forecast(df):
    return lam.generate_volume_forecast(df)

@st.cache_data
def cached_detect_log_periodicity(df):
    return lam.detect_log_periodicity(df)

@st.cache_data
def cached_extract_trace_ids(df):
    return lam.extract_trace_ids(df)

@st.cache_data
def cached_detect_bottlenecks(df, threshold_ms):
    return lam.detect_bottlenecks(df, threshold_ms)

@st.cache_data
def cached_generate_stack_trace_metrics(df):
    return lam.generate_stack_trace_metrics(df)

@st.cache_data
def cached_extract_api_metrics(df):
    return lam.extract_api_metrics(df)

@st.cache_data
def cached_extract_cicd_metrics(df):
    """Extrai métricas de CI/CD dos logs (Cacheado)."""
    return lam.extract_cicd_metrics(df)

@st.cache_data
def cached_extract_rum_metrics(df):
    """Extrai métricas de RUM dos logs (Cacheado)."""
    return lam.extract_rum_metrics(df)

@st.cache_data
def cached_prepare_explorer_data(df):
    """Prepara e ordena os dados para o explorador de logs (Cacheado para performance)."""
    if df.empty: return df
    
    priority_map = {'Fail': 0, 'Error': 1, 'Warning': 2, 'Info': 3, 'Debug': 4}
    sorted_df = df.copy()
    sorted_df['priority'] = sorted_df['log_level'].map(priority_map).fillna(5)
    sorted_df = sorted_df.sort_values(by=['priority', 'timestamp'], ascending=[True, False])
    
    # Cria ID único
    sorted_df['log_id'] = sorted_df['timestamp'].astype(str) + "_" + sorted_df['source'] + "_" + sorted_df['message'].str.slice(0, 50)
    return sorted_df