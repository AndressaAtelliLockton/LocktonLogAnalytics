# -*- coding: utf-8 -*-
"""
Módulo para a aba "RUM (Real User Monitoring)".
"""

import streamlit as st
import altair as alt
from utils.caching import cached_extract_rum_metrics

def render_page():
    """
    Renderiza a aba "RUM (Real User Monitoring)".
    """
    st.title("🌐 RUM (Frontend)")
    st.markdown("Métricas de experiência do usuário final (Core Web Vitals, Erros JS).")

    if 'filtered_df' not in st.session_state or st.session_state['filtered_df'].empty:
        st.warning("Dados não carregados. Por favor, vá para a página principal e carregue os dados primeiro.")
        return

    filtered_df = st.session_state['filtered_df']
    
    rum_df = cached_extract_rum_metrics(filtered_df)
    
    if not rum_df.empty:
        rum_type = st.radio("Tipo de Visão", ["Web Vitals (Performance)", "Erros JavaScript"], horizontal=True)
        
        if "Web Vitals" in rum_type:
            vitals = rum_df[rum_df['type'] == 'vital']
            if not vitals.empty:
                st.subheader("Distribuição de Performance (Core Web Vitals)")
                chart = alt.Chart(vitals).mark_boxplot().encode(
                    x=alt.X('name:N', title='Métrica'),
                    y=alt.Y('value:Q', title='Valor'),
                    color='name:N',
                    tooltip=['name', 'value', 'timestamp']
                ).interactive()
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("Nenhum dado de Web Vitals encontrado (ex: LCP, CLS, FID).")
                
        elif "Erros JavaScript" in rum_type:
            js_errs = rum_df[rum_df['type'] == 'js_error']
            if not js_errs.empty:
                st.subheader("Top Erros de Frontend")
                err_counts = js_errs['name'].value_counts().reset_index()
                err_counts.columns = ['name', 'count']
                st.bar_chart(err_counts.set_index('name'))
                
                with st.expander("Ver Detalhes dos Erros"):
                    st.dataframe(js_errs[['timestamp', 'name', 'details']], use_container_width=True)
            else:
                st.success("Nenhum erro de JavaScript detectado nos logs.")
    else:
        st.info("Nenhum dado de RUM encontrado nos logs atuais.\n\n**Dica:** O sistema procura por padrões como `LCP: 1.2s` ou `TypeError: ...`.")
