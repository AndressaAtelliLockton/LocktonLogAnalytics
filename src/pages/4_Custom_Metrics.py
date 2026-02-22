# -*- coding: utf-8 -*-
"""
Módulo para a aba "Métricas Customizadas".
"""

import streamlit as st
import log_analyzer as lam
import altair as alt
import pandas as pd
import re

def render_page():
    """
    Renderiza a aba "Métricas Customizadas".
    """
    st.title("📈 Métricas Customizadas")
    st.markdown("Crie e visualize métricas numéricas extraídas de logs via Regex.")

    if 'filtered_df' not in st.session_state or st.session_state['filtered_df'].empty:
        st.warning("Dados não carregados. Por favor, vá para a página principal e carregue os dados primeiro.")
        return

    filtered_df = st.session_state['filtered_df']
    
    # 1. Definição de Novas Métricas
    with st.expander("➕ Nova Métrica", expanded=False):
        with st.form(key="new_metric_form_4"):
            col_m1, col_m2, col_m3 = st.columns([2, 3, 1])
            m_name = col_m1.text_input("Nome da Métrica", placeholder="Ex: TempoProcessamento")
            m_regex = col_m2.text_input("Regex de Extração", placeholder="Ex: processing_time=(\d+)", help="Use parênteses () para capturar o valor numérico.")
            m_type = col_m3.selectbox("Tipo", ["gauge", "counter"], help="Gauge: Valor numérico variável (ex: latência). Counter: Contagem de ocorrências (valor=1).")
            
            if st.form_submit_button("Salvar Métrica"):
                if m_name and m_regex:
                    # Salva na sessão do Streamlit (já que não temos DB persistente ativo)
                    if 'custom_metrics_defs' not in st.session_state:
                        st.session_state['custom_metrics_defs'] = []
                    
                    st.session_state['custom_metrics_defs'].append({"name": m_name, "regex": m_regex, "type": m_type})
                    success, msg = True, f"Métrica '{m_name}' adicionada com sucesso!"
                    
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("Preencha nome e regex.")

    # 2. Visualização de Métricas
    metrics_list = st.session_state.get('custom_metrics_defs', [])
    
    if metrics_list:
        # Seletor de Métrica para Visualizar
        metric_names = [m['name'] for m in metrics_list]
        selected_metric_name = st.selectbox(
            "Selecione a Métrica para visualizar:", 
            metric_names
        )
        
        if selected_metric_name:
            metric_def = next(m for m in metrics_list if m['name'] == selected_metric_name)
            
            # Botão de Exclusão
            col_del, _ = st.columns([1, 5])
            if col_del.button("🗑️ Excluir Métrica", key=f"del_{selected_metric_name}"):
                st.session_state['custom_metrics_defs'] = [m for m in metrics_list if m['name'] != selected_metric_name]
                st.success("Métrica removida.")
                st.rerun()

            # --- Processamento Dinâmico ---
            # Aplica o Regex no DataFrame atual
            try:
                pattern = re.compile(metric_def['regex'])
                
                def extract_val(msg):
                    match = pattern.search(str(msg))
                    return float(match.group(1)) if match else None

                hist_df = filtered_df[['timestamp', 'message']].copy()
                hist_df['value'] = hist_df['message'].apply(extract_val)
                hist_df = hist_df.dropna(subset=['value'])
                
            except Exception as e:
                st.error(f"Erro ao aplicar Regex: {e}")
                hist_df = pd.DataFrame()
            
            if not hist_df.empty:
                st.subheader(f"Evolução: {selected_metric_name}")
                
                # Gráfico
                chart = alt.Chart(hist_df).mark_line(point=True).encode(
                    x=alt.X('timestamp:T', title='Tempo'),
                    y=alt.Y('value:Q', title='Valor'),
                    tooltip=['timestamp', 'value']
                ).interactive()
                st.altair_chart(chart, use_container_width=True)
                
                # Estatísticas
                st.write(f"**Média:** {hist_df['value'].mean():.2f} | **Máx:** {hist_df['value'].max()} | **Min:** {hist_df['value'].min()}")
            else:
                st.info(f"Nenhum log correspondeu ao regex `{metric_def['regex']}` nos dados filtrados.")
    else:
        st.info("Nenhuma métrica customizada definida.")
