# -*- coding: utf-8 -*-
"""
Módulo para a aba "Monitoramento de API".
"""

import streamlit as st
from dashboard.caching import cached_extract_api_metrics
import altair as alt

def render_page():
    """
    Renderiza a aba "Monitoramento de API".
    """
    st.title("📡 Monitoramento de API")
    st.markdown("Análise de requisições HTTP, endpoints e códigos de status.")

    if 'filtered_df' not in st.session_state or st.session_state['filtered_df'].empty:
        st.warning("Dados não carregados. Por favor, vá para a página principal e carregue os dados primeiro.")
        return

    filtered_df = st.session_state['filtered_df']
    
    api_df = cached_extract_api_metrics(filtered_df)
    
    if not api_df.empty:
        total_reqs = len(api_df)
        success_reqs = len(api_df[api_df['status_code'].astype(str).str.startswith('2', na=False)])
        client_errs = len(api_df[api_df['status_code'].astype(str).str.startswith('4', na=False)])
        server_errs = len(api_df[api_df['status_code'].astype(str).str.startswith('5', na=False)])
        network_errs = len(api_df[api_df['status_code'].astype(str).str.startswith('0', na=False)])
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Requisições", total_reqs)
        c2.metric("Sucesso (2xx)", success_reqs)
        c3.metric("Erros Cliente (4xx)", client_errs)
        c4.metric("Erros Servidor (5xx)", server_errs)
        c5.metric("Rede/CORS (0)", network_errs, help="Status 0 indica bloqueio por CORS ou falha de rede no cliente.")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Códigos de Status")
            status_counts = api_df['status_code'].fillna('N/A').value_counts().reset_index()
            chart_status = alt.Chart(status_counts).mark_arc(innerRadius=50).encode(
                theta="count", color="status_code"
            )
            st.altair_chart(chart_status, use_container_width=True)
            
        with col2:
            st.subheader("Métodos HTTP")
            method_counts = api_df['method'].value_counts().reset_index()
            chart_method = alt.Chart(method_counts).mark_bar().encode(
                x=alt.X('method', sort='-y'), y='count', color='method'
            )
            st.altair_chart(chart_method, use_container_width=True)
            
        st.subheader("Top Endpoints Mais Acessados")
        endpoint_counts = api_df['endpoint'].value_counts().head(15).reset_index()
        chart_endpoints = alt.Chart(endpoint_counts).mark_bar().encode(
            x=alt.X('count'), y=alt.Y('endpoint', sort='-x')
        )
        st.altair_chart(chart_endpoints, use_container_width=True)
        
        with st.expander("Ver Dados Detalhados de API"):
            st.dataframe(api_df, use_container_width=True)
    else:
        st.info("Nenhum padrão de API (Método HTTP + Endpoint) encontrado nos logs filtrados.\n\nO sistema procura por padrões como `GET /api/v1/users` ou `POST /login`.")
