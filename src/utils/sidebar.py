# c:\Users\Andressa.Atelli\Documents\locktonloganalytics\dashboard\sidebar.py
# Este arquivo contém a lógica para renderizar a barra lateral (sidebar) do dashboard.

import streamlit as st
import pandas as pd
import log_analyzer as lam
import time

def render_data_source_selector():
    """
    Renderiza os seletores da fonte de dados na barra lateral.
    Esta função deve ser chamada ANTES do carregamento dos dados.

    Returns:
        tuple: Uma tupla contendo (data_source, auto_refresh).
    """
    st.sidebar.title("Configurações")
    st.sidebar.subheader("📂 Fonte de Dados")
    
    data_source_options = ["InfluxDB (Real-time)", "Upload CSV", "API Graylog", "Base Local (Histórico)"]
    if 'snapshot_df' in st.session_state:
        data_source_options.insert(1, "Snapshot")

    default_index = 0
    if 'data_source' in st.session_state and st.session_state['data_source'] in data_source_options:
        default_index = data_source_options.index(st.session_state['data_source'])

    data_source = st.sidebar.radio("Origem", data_source_options, index=default_index, help="Escolha a fonte dos logs.")
    st.session_state['data_source'] = data_source
    
    if 'auto_refresh' not in st.session_state:
        saved_auto_refresh = lam.get_setting("auto_refresh", "False") == "True"
        st.session_state['auto_refresh'] = saved_auto_refresh
    
    auto_refresh = st.sidebar.checkbox("🔄 Atualização Automática (5 min)", value=st.session_state.get('auto_refresh', True), help="Atualiza os dados da API Graylog a cada 5 minutos.")
    
    return data_source, auto_refresh

def render_filters_sidebar(raw_df):
    """
    Renderiza os filtros e controles da barra lateral que dependem dos dados carregados.
    Esta função deve ser chamada DEPOIS do carregamento dos dados.

    Args:
        raw_df (pd.DataFrame): O DataFrame processado para popular os filtros.

    Returns:
        dict: Um dicionário com os valores dos filtros e configurações.
    """
    sidebar_config = {}

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Configurações de Análise")
    sidebar_config['z_score_threshold'] = st.sidebar.slider("Sensibilidade de Volume", 1.0, 10.0, 3.0, 0.5)
    sidebar_config['rarity_threshold'] = st.sidebar.slider("Limiar de Raridade (%)", 0.001, 0.1, 0.01, 0.001, "%.3f")
    sidebar_config['enable_auto_alerts'] = st.sidebar.checkbox("🔔 Alertas Automáticos (Swarm)", value=True)

    st.sidebar.markdown("---")
    st.sidebar.subheader("🧠 Memória da IA")
    db_stats = lam.get_db_stats()
    st.sidebar.caption(f"Itens em Cache: {db_stats['count']}")
    if st.sidebar.button("Limpar Memória IA"):
        lam.clear_ai_cache()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("⏰ Status do Agendador")
    if not lam.is_scheduler_running():
        success, _ = lam.start_scheduler_background()
        if success:
            st.toast("Agendador iniciado.", icon="🚀")
            time.sleep(2); st.rerun()
    if lam.is_scheduler_running():
        st.sidebar.success("Agendador Ativo", icon="✅")
        if st.sidebar.button("🛑 Parar Coleta"):
            lam.stop_scheduler_background(); st.rerun()
    else:
        st.sidebar.error("Agendador Inativo", icon="⚠️")
    st.sidebar.caption(f"Última Coleta: {lam.get_last_collection_time() or 'N/A'}")

    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Filtros Globais")
    
    all_sources = sorted(raw_df['source'].unique()) if 'source' in raw_df else []
    sidebar_config['selected_sources'] = st.sidebar.multiselect("Source", all_sources, default=all_sources)
    
    all_categories = sorted(raw_df['category'].unique()) if 'category' in raw_df else []
    sidebar_config['selected_categories'] = st.sidebar.multiselect("Category", all_categories, default=all_categories)
    
    all_levels = sorted(raw_df['log_level'].unique()) if 'log_level' in raw_df else []
    sidebar_config['selected_log_levels'] = st.sidebar.multiselect("Log Level", all_levels, default=all_levels)
    
    sidebar_config['global_search'] = st.sidebar.text_input("Busca Global")
    sidebar_config['enable_masking'] = st.sidebar.checkbox("🛡️ Mascarar Dados", value=True)

    return sidebar_config