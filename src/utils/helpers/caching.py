# c:\Users\Andressa.Atelli\Documents\locktonloganalytics\dashboard\helpers\caching.py
# Este arquivo centraliza todas as funções que utilizam o cache do Streamlit (@st.cache_data).
# O uso de cache é uma otimização de performance crucial para evitar a re-execução 
# de funções de processamento pesado a cada interação do usuário no dashboard.

import streamlit as st
import log_analyzer as lam

# Wrapper para cache do processamento de dados (Melhora Performance)
@st.cache_data
def cached_process_log_data(df, config):
    """
    Processa os dados brutos de log, aplicando parsing e enriquecimento.
    O resultado é cacheado para evitar reprocessamento.
    """
    return lam.process_log_data(df, config)

# Wrappers com cache para funções pesadas de análise (Performance)
@st.cache_data
def cached_detect_volume_anomalies(df, z_score_threshold):
    """
    Detecta anomalias de volume nos logs usando o método Z-score.
    Cacheado para performance.
    """
    return lam.detect_volume_anomalies(df, z_score_threshold=z_score_threshold)

@st.cache_data
def cached_detect_rare_patterns(df, rarity_threshold):
    """
    Encontra padrões de log que ocorrem com baixa frequência.
    Cacheado para performance.
    """
    return lam.detect_rare_patterns(df, rarity_threshold=rarity_threshold)

@st.cache_data
def cached_group_incidents(df):
    """
    Agrupa logs de erro similares em incidentes únicos.
    Cacheado para performance.
    """
    return lam.group_incidents(df)

@st.cache_data
def cached_analyze_security_threats(df):
    """
    Analisa os logs em busca de potenciais ameaças de segurança, como IPs com alta taxa de erro.
    Cacheado para performance.
    """
    return lam.analyze_security_threats(df)

@st.cache_data
def cached_extract_latency_metrics(df):
    """
    Extrai métricas de latência (tempo de resposta) das mensagens de log.
    Cacheado para performance.
    """
    return lam.extract_latency_metrics(df)

@st.cache_data
def cached_extract_system_metrics(df):
    """
    Extrai métricas de sistema (CPU, memória) das mensagens de log.
    Cacheado para performance.
    """
    return lam.extract_system_metrics(df)

@st.cache_data
def cached_infer_service_dependencies(df):
    """
    Infere as dependências entre serviços com base nas mensagens de log.
    Cacheado para performance.
    """
    return lam.infer_service_dependencies(df)

@st.cache_data
def cached_generate_log_patterns(df):
    """
    Gera padrões (templates) de log a partir das mensagens, agrupando logs similares.
    Cacheado para performance.
    """
    return lam.generate_log_patterns(df)

@st.cache_data
def cached_mask_sensitive_data(df):
    """
    Mascarada dados sensíveis (LGPD) como CPFs, e-mails e IPs.
    Cacheado para performance.
    """
    return lam.mask_sensitive_data(df)

@st.cache_data
def cached_generate_volume_forecast(df):
    """
    Gera uma previsão de volume de logs para o futuro próximo.
    Cacheado para performance.
    """
    return lam.generate_volume_forecast(df)

@st.cache_data
def cached_detect_log_periodicity(df):
    """
    Detecta padrões de periodicidade nos logs usando FFT.
    Cacheado para performance.
    """
    return lam.detect_log_periodicity(df)

@st.cache_data
def cached_extract_trace_ids(df):
    """
    Extrai IDs de rastreamento (trace IDs) das mensagens para correlação.
    Cacheado para performance.
    """
    return lam.extract_trace_ids(df)

@st.cache_data
def cached_detect_bottlenecks(df, threshold_ms):
    """
    Detecta gargalos de performance, analisando latências acima de um limiar.
    Cacheado para performance.
    """
    return lam.detect_bottlenecks(df, threshold_ms)

@st.cache_data
def cached_generate_stack_trace_metrics(df):
    """
    Extrai e métricas de stack traces de logs de erro.
    Cacheado para performance.
    """
    return lam.generate_stack_trace_metrics(df)

@st.cache_data
def cached_extract_api_metrics(df):
    """
    Extrai métricas de chamadas de API das mensagens de log.
    Cacheado para performance.
    """
    return lam.extract_api_metrics(df)
