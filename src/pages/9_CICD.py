# -*- coding: utf-8 -*-
"""
Módulo para a aba "CI/CD & Pipelines".
"""

import streamlit as st
import altair as alt
from utils.caching import cached_extract_cicd_metrics

def render_page():
    st.title("🚀 CI/CD & Pipelines")
    st.markdown("Monitoramento de performance de builds, testes e deploys (DevOps).")

    if 'filtered_df' not in st.session_state or st.session_state['filtered_df'].empty:
        st.warning("Dados não carregados. Por favor, vá para a página principal e carregue os dados primeiro.")
        return

    filtered_df = st.session_state['filtered_df']
    
    cicd_df = cached_extract_cicd_metrics(filtered_df)
    
    if not cicd_df.empty:
        # KPIs
        total_runs = len(cicd_df)
        success_runs = len(cicd_df[cicd_df['status'] == 'Success'])
        success_rate = (success_runs / total_runs) * 100 if total_runs > 0 else 0
        
        # Duração média apenas de processos finalizados com duração extraída
        durations = cicd_df[cicd_df['duration_s'] > 0]['duration_s']
        avg_duration = durations.mean() if not durations.empty else 0
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total de Execuções", total_runs)
        c2.metric("Taxa de Sucesso", f"{success_rate:.1f}%")
        c3.metric("Duração Média", f"{avg_duration:.1f}s")
        c4.metric("Falhas", total_runs - success_runs, delta_color="inverse")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Status por Estágio")
            status_chart = alt.Chart(cicd_df).mark_bar().encode(
                x=alt.X('stage', title='Estágio'),
                y=alt.Y('count()', title='Qtd'),
                color=alt.Color('status', scale=alt.Scale(domain=['Success', 'Failure', 'In Progress', 'Unknown'], range=['green', 'red', 'blue', 'gray'])),
                tooltip=['stage', 'status', 'count()']
            ).interactive()
            st.altair_chart(status_chart, use_container_width=True)
            
        with col2:
            st.subheader("Duração dos Builds (Boxplot)")
            if not durations.empty:
                dur_chart = alt.Chart(cicd_df[cicd_df['duration_s'] > 0]).mark_boxplot().encode(
                    x=alt.X('stage', title='Estágio'),
                    y=alt.Y('duration_s', title='Duração (s)'),
                    color='stage'
                ).interactive()
                st.altair_chart(dur_chart, use_container_width=True)
        
        st.subheader("Logs de CI/CD Detalhados")
        st.dataframe(cicd_df[['timestamp', 'source', 'stage', 'status', 'duration_s', 'message']], use_container_width=True)
    else:
        st.info("Nenhum log de CI/CD encontrado nos dados atuais.\n\n**Dica:** O sistema procura por termos como `pipeline`, `build`, `deploy` e padrões de duração como `took 45s`.")