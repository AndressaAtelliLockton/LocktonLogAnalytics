# -*- coding: utf-8 -*-
"""
Módulo para a aba "Infraestrutura".
"""

import streamlit as st
import log_analyzer as lam
from utils.caching import cached_extract_system_metrics
import altair as alt
import pandas as pd

def render_page():
    """
    Renderiza a aba "Infraestrutura" com métricas de CPU, memória, etc.
    """
    st.title("🖥️ Infraestrutura")
    st.markdown("Extração de métricas de hardware a partir de logs textuais (ex: `CPU: 50%`).")

    if 'filtered_df' not in st.session_state or st.session_state['filtered_df'].empty:
        st.warning("Dados não carregados. Por favor, vá para a página principal e carregue os dados primeiro.")
        return

    filtered_df = st.session_state['filtered_df']
    GRAYLOG_API_URL = st.session_state['GRAYLOG_API_URL']
    GRAYLOG_USER = st.session_state['GRAYLOG_USER']
    GRAYLOG_PASSWORD = st.session_state['GRAYLOG_PASSWORD']
    GRAYLOG_NODE_ID = st.session_state['GRAYLOG_NODE_ID']
    
    if GRAYLOG_API_URL and GRAYLOG_USER:
        QUERY_METRICAS = f"gl2_source_input:{GRAYLOG_NODE_ID}"

        # 1. Busca os logs com os novos campos criados pelos Extratores
        df_logs, err = lam.fetch_logs_from_graylog(
            api_url=GRAYLOG_API_URL, 
            username=GRAYLOG_USER, 
            password=GRAYLOG_PASSWORD, 
            query=QUERY_METRICAS, 
            relative=300,
            fields="timestamp,source,message,cpu_valor,mem_valor"
        )

        if df_logs is not None and not df_logs.empty:
            # Garante que timestamp é datetime
            df_logs['timestamp'] = pd.to_datetime(df_logs['timestamp'], errors='coerce')
            df_logs = df_logs.sort_values(by='timestamp', ascending=False)

            # Garante que as colunas existam para evitar erros
            if 'cpu_valor' not in df_logs.columns: df_logs['cpu_valor'] = 0
            if 'mem_valor' not in df_logs.columns: df_logs['mem_valor'] = 0

            # Garante que as colunas sejam numéricas e preenche vazios com 0
            df_logs['cpu_valor'] = pd.to_numeric(df_logs['cpu_valor'], errors='coerce').fillna(0)
            df_logs['mem_valor'] = pd.to_numeric(df_logs['mem_valor'], errors='coerce').fillna(0)
            
            cpu_atual = df_logs['cpu_valor'].iloc[0]
            mem_atual = df_logs['mem_valor'].iloc[0]
            
            col1, col2 = st.columns(2)
            col1.metric("Processamento (CPU)", f"{cpu_atual}%")
            col2.metric("Memória RAM", f"{mem_atual}%")
            
            # O gráfico agora terá valores válidos para plotar
            st.write("### Evolução de Recursos")
            st.line_chart(df_logs.set_index('timestamp')[['cpu_valor', 'mem_valor']])
            
            with st.expander("🔍 Debug: Ver Dados Brutos (Graylog API)"):
                st.caption("Estes são os dados exatos retornados pela API do Graylog para esta aba.")
                st.dataframe(df_logs)
                
                st.markdown("### 📝 Log Puro (Raw Text)")
                st.text(df_logs.to_string(index=False))
        else:
            st.warning(f"⚠️ Nenhuma métrica encontrada para o input {GRAYLOG_NODE_ID}. Verifique o tráfego no Graylog.")
    
    st.markdown("---")

    # Análise baseada nos logs já carregados
    infra_df = cached_extract_system_metrics(filtered_df)
    
    if not infra_df.empty:
        # Alertas de Infraestrutura (CPU & Memória)
        if not infra_df['cpu'].isna().all():
            max_cpu = infra_df['cpu'].max()
            if max_cpu > 90:
                st.error(f"🔥 **ALERTA CRÍTICO:** A CPU atingiu **{max_cpu:.1f}%**! Verifique a saúde do servidor.", icon="🚨")

        if not infra_df['memory'].isna().all():
            max_mem = infra_df['memory'].max()
            if max_mem > 90:
                st.warning(f"⚠️ **ALERTA DE MEMÓRIA:** O uso de memória atingiu **{max_mem:.1f}%** (Menos de 10% livre).", icon="💾")

        # KPIs de Resumo
        col_i1, col_i2, col_i3, col_i4 = st.columns(4)
        
        with col_i1:
            if not infra_df['cpu'].isna().all():
                st.metric("CPU Máxima", f"{infra_df['cpu'].max():.1f}%", help="Pico de uso de CPU registrado nos logs.")
        with col_i2:
            if not infra_df['memory'].isna().all():
                st.metric("Memória Média", f"{infra_df['memory'].mean():.0f}", help="Média dos valores de memória encontrados.")
        with col_i3:
            if not infra_df['disk'].isna().all():
                st.metric("Disco Máximo", f"{infra_df['disk'].max():.1f}%")
        with col_i4:
            st.metric("Amostras", len(infra_df), help="Quantidade de logs contendo métricas de infraestrutura.")

        st.markdown("---")

        # Gráficos Dinâmicos
        metrics_map = {
            'cpu': 'CPU (%)',
            'memory': 'Memória (Valor Bruto)',
            'disk': 'Disco (%)',
            'network': 'Rede (Valor Bruto)'
        }

        for metric_col, metric_label in metrics_map.items():
            if not infra_df[metric_col].isna().all():
                st.subheader(f"Evolução: {metric_label}")
                chart = alt.Chart(infra_df.dropna(subset=[metric_col])).mark_line(point=True).encode(
                    x='timestamp:T',
                    y=alt.Y(f'{metric_col}:Q', title=metric_label),
                    color='source',
                    tooltip=['timestamp', 'source', alt.Tooltip(f'{metric_col}:Q', title=metric_label)]
                ).interactive()
                st.altair_chart(chart, use_container_width=True)
        
        # --- Monitoramento de Containers (Docker/K8s) ---
        if 'container_name' in filtered_df.columns:
            st.markdown("---")
            st.subheader("📦 Monitoramento de Containers")
            
            # Filtra logs que têm nome de container
            containers_df = filtered_df.dropna(subset=['container_name'])
            
            if not containers_df.empty:
                container_stats = containers_df.groupby('container_name').agg(
                    log_count=('message', 'count'),
                    error_count=('log_level', lambda x: x.isin(['Error', 'Fail', 'Critical']).sum())
                ).reset_index().sort_values('log_count', ascending=False)
                
                st.dataframe(container_stats, use_container_width=True)
            else:
                st.info("Nenhum dado de container identificado nos logs (campo 'container_name').")
    else:
        st.warning("Nenhuma métrica de infraestrutura encontrada nos logs atuais.")
        st.info("💡 **Dica:** Verifique se a origem **Local-Agent** está selecionada no filtro 'Source'.\n\nSeus logs devem conter padrões como: `CPU: 45%`, `Memory: 2048`, `Disk: 80%`.")
