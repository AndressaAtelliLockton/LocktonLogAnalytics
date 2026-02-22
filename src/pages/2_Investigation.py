# -*- coding: utf-8 -*-
"""
Módulo para a aba "Investigação Detalhada".
Inclui o explorador de logs, mapa de serviços, comparação de datasets e flame graph.
"""

import streamlit as st
import pandas as pd
import altair as alt
import log_analyzer as lam
from io import StringIO
import re
from pages.ai_assistant import render_ai_analysis_section
from dashboard.caching import (
    cached_generate_log_patterns, 
    cached_extract_trace_ids, 
    cached_infer_service_dependencies, 
    cached_process_log_data, 
    cached_generate_stack_trace_metrics,
    cached_prepare_explorer_data
)

# --- Lógica de Callback para Feedback (Definida aqui para uso em ambos os modos) ---
def handle_feedback(message, score):
    lam.update_ai_feedback(message, score)
    # Pequeno truque para forçar a atualização do estado do botão sem um rerun completo
    st.session_state[f'feedback_score_{message}'] = score

def render_explorer_sub_tab(display_df, raw_df, enable_masking):
    """Renderiza a sub-aba "Explorador de Logs"."""
    st.subheader("🔍 Explorador & Rastreamento Distribuído")
    
    view_mode = st.radio("Modo de Visualização:", ["Patterns (Agrupamento)", "Stream (Lista)"], index=1, horizontal=True, help="Escolha entre ver todos os logs em lista ou agrupados por similaridade.", key="view_mode_2")

    # --- Lógica de Seleção (Patterns ou Stream) ---
    # Os dados do log selecionado serão armazenados aqui para renderização posterior, estabilizando a árvore de renderização.
    selected_log_data = None

    if view_mode == "Patterns (Agrupamento)":
        st.markdown("#### 🧩 Padrões de Log (Clustering)")
        st.write("Agrupamento inteligente de logs similares. Útil para identificar ruído e erros frequentes.")
        
        # Usa display_df (que respeita os filtros globais)
        patterns = cached_generate_log_patterns(display_df).copy()
        
        if not patterns.empty:
            # Ordenação personalizada: Locksp-swarm4 > Locksp-swarm2 > Locksp-swarm1 > Locksp-swarm3 > Outros
            def get_priority(sources):
                if not isinstance(sources, list): return 5
                s_str = " ".join(str(s) for s in sources).lower()
                if "locksp-swarm4" in s_str: return 1
                if "locksp-swarm2" in s_str: return 2
                if "locksp-swarm3" in s_str: return 3
                if "locksp-swarm1" in s_str: return 4
                return 5

            patterns['priority'] = patterns['sources'].apply(get_priority)
            patterns = patterns.sort_values(by=['priority', 'last_seen', 'signature'], ascending=[True, False, True])

            # Extrai sources únicos para o dropdown
            unique_sources = set()
            for src_list in patterns['sources']:
                if isinstance(src_list, list):
                    unique_sources.update(src_list)
            
            options = ["Todas"] + sorted(list(unique_sources))
            # Tenta selecionar Locksp-swarm4 por padrão se existir, senão 0 (Todas)
            default_idx = next((i for i, opt in enumerate(options) if "locksp-swarm4" in str(opt).lower()), 0)
            
            # Garante consistência do filtro de source
            if "pattern_source_filter" in st.session_state and st.session_state.pattern_source_filter not in options:
                del st.session_state.pattern_source_filter

            filter_source = st.selectbox("Filtrar por Origem (Source):", options, index=default_idx, key="pattern_source_filter")

            # Aplica o filtro se não for "Todas"
            if filter_source != "Todas":
                patterns = patterns[patterns['sources'].apply(lambda x: filter_source in x if isinstance(x, list) else False)]

            st.dataframe(
                patterns,
                use_container_width=True,
                column_config={
                    "count": "Contagem",
                    "percent": st.column_config.ProgressColumn("Freq (%)", format="%.2f%%", min_value=0, max_value=100),
                    "signature": "Assinatura do Padrão",
                    "sources": "Origens",
                    "log_level": "Nível",
                    "example_message": "Exemplo",
                    "priority": None, # Oculta a coluna de prioridade
                    "first_seen": None,
                    "last_seen": "Última Ocorrência"
                }
            )
            
            # Seleção de Padrão para Análise
            pattern_options = patterns.apply(
                lambda x: f"[{x['count']}x] {x['log_level']} | {x['signature'][:80]}...", axis=1
            ).tolist()
            
            if pattern_options:
                selected_pattern = st.selectbox(
                    "Selecione um padrão para analisar:", 
                    pattern_options, 
                    key="pattern_log_select"
                )
                p_index = pattern_options.index(selected_pattern)
                
                full_message = patterns.iloc[p_index]['example_message']
                log_timestamp = patterns.iloc[p_index]['first_seen']
                sources_list = patterns.iloc[p_index]['sources']
                log_source = sources_list[0] if isinstance(sources_list, list) and len(sources_list) > 0 else "Unknown"
                
                # Apenas define os dados a serem renderizados, não renderiza ainda
                selected_log_data = {"message": full_message, "timestamp": log_timestamp, "source": log_source, "key_prefix": f"pattern_{p_index}"}
        else:
            st.info("Nenhum padrão encontrado nos logs filtrados.")

    else: # Stream Mode
        st.markdown("#### 🕵️ Rastreamento Distribuído (Distributed Tracing)")
        st.caption("Identificação automática de transações através de Correlation IDs (UUIDs).")
        
        df_with_traces = cached_extract_trace_ids(display_df)
        
        if 'trace_id' in df_with_traces.columns:
            df_with_traces['_has_trace'] = df_with_traces['trace_id'].notna()
            df_with_traces['_is_error'] = df_with_traces['log_level'].isin(['Error', 'Fail', 'Critical', 'Fatal'])
            df_with_traces = df_with_traces.sort_values(by=['_has_trace', '_is_error', 'timestamp'], ascending=[False, False, False]).drop(columns=['_has_trace', '_is_error'])
        
        col_t1, col_t2 = st.columns([3, 1])
        with col_t1:
            correlation_id_input = st.text_input("🔍 Buscar Trace ID:", placeholder="Cole um UUID aqui...", help="Cole um ID de correlação para filtrar a transação completa.")
        
        with col_t2:
            selected_trace_auto = ""
            if 'trace_id' in df_with_traces.columns:
                valid_traces = df_with_traces['trace_id'].dropna()
                if not valid_traces.empty:
                    top_traces = valid_traces.value_counts().head(15).index.tolist()
                    selected_trace_auto = st.selectbox("⚡ Traces Recentes:", [""] + top_traces)
            
            if not selected_trace_auto:
                st.caption("Nenhum Trace ID detectado.")

        correlation_id = correlation_id_input if correlation_id_input else selected_trace_auto
        
        explorer_df = df_with_traces
        
        if correlation_id:
            mask = (explorer_df['trace_id'] == correlation_id) | (explorer_df['message'].astype(str).str.contains(correlation_id, case=False, na=False))
            trace_df = explorer_df[mask].copy()
            
            if not trace_df.empty:
                st.success(f"Transação Encontrada: {len(trace_df)} eventos")
                
                start_time = trace_df['timestamp'].min()
                end_time = trace_df['timestamp'].max()
                duration = (end_time - start_time).total_seconds() * 1000
                services = trace_df['source'].unique()
                errors = len(trace_df[trace_df['log_level'].isin(['Error', 'Fail', 'Critical'])])
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Duração Total", f"{duration:.0f} ms")
                m2.metric("Início", start_time.strftime('%H:%M:%S'))
                m3.metric("Serviços Envolvidos", len(services))
                m4.metric("Erros no Trace", errors, delta="Crítico" if errors > 0 else "Normal", delta_color="inverse")

                st.markdown("#### 🌊 Timeline da Transação (Waterfall)")
                
                base = alt.Chart(trace_df).encode(
                    x=alt.X('timestamp:T', title='Tempo'),
                    y=alt.Y('source', title='Serviço'),
                    color=alt.Color('log_level', scale=alt.Scale(domain=['Info', 'Warning', 'Error', 'Fail'], range=['#36a2eb', '#ffc107', '#ff6384', '#d32f2f'])),
                    tooltip=['timestamp', 'source', 'log_level', 'message']
                )
                chart = base.mark_circle(size=100) + base.mark_line(opacity=0.5)
                st.altair_chart(chart, use_container_width=True)
                
                explorer_df = trace_df
        
        def highlight_critical(row):
            if row['log_level'] in ['Error', 'Fail', 'Critical', 'Fatal']:
                return ['background-color: #660000'] * len(row)
            return [''] * len(row)

        st.dataframe(explorer_df.style.apply(highlight_critical, axis=1), use_container_width=True)

        if not explorer_df.empty:
            st.info("💡 Selecione um log abaixo para análise com IA.")
            
            emoji_map = {'Fail': '🔴', 'Error': '🔴', 'Warning': '🟡', 'Info': '🔵', 'Debug': '⚪'}
            sorted_df = cached_prepare_explorer_data(explorer_df)
            
            items_per_page = st.selectbox("Itens por página:", [10, 20, 50], index=0)

            if 'current_page' not in st.session_state: st.session_state.current_page = 1
            
            total_items = len(sorted_df)
            total_pages = max(1, (total_items - 1) // items_per_page + 1)
            
            if st.session_state.current_page > total_pages: st.session_state.current_page = 1
            
            start_idx = (st.session_state.current_page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            sliced_df = sorted_df.iloc[start_idx:end_idx]
            
            # Usa o índice do DataFrame para garantir unicidade e atualização correta entre páginas
            option_indices = sliced_df.index.tolist()
            
            def format_log_option(idx):
                row = sliced_df.loc[idx]
                return f"{emoji_map.get(row['log_level'], '⚫')} {row['timestamp']} | {row['log_level']} | {row['message'][:80]}..."
            
            if len(sliced_df) > 0:
                selected_index = st.selectbox(
                    "Log para análise:", 
                    option_indices, 
                    format_func=format_log_option, 
                    # Adiciona a página à chave para evitar conflito de estado/buffer entre paginações
                    key=f"stream_log_select_{st.session_state.current_page}"
                )
                
                selected_row = sliced_df.loc[selected_index]
                full_message = selected_row['message']
                log_timestamp = selected_row['timestamp']
                log_source = selected_row['source']
                selected_log_id = selected_row['log_id']
                
                # Apenas define os dados a serem renderizados, não renderiza ainda
                selected_log_data = {"message": full_message, "timestamp": log_timestamp, "source": log_source, "key_prefix": f"stream_{selected_log_id}"}

    # --- Renderização da Seção de IA (ocorre uma única vez, fora dos condicionais) ---
    ai_placeholder = st.empty()

    if selected_log_data:
        with ai_placeholder.container():
            render_ai_analysis_section(
                log_message=selected_log_data["message"],
                log_timestamp=selected_log_data["timestamp"],
                log_source=selected_log_data["source"],
                raw_df=raw_df,
                enable_masking=enable_masking,
                unique_key_prefix=selected_log_data["key_prefix"]
            )
    # Se nenhum log for selecionado, limpa o placeholder
    else:
        ai_placeholder.empty()

def render_map_sub_tab(filtered_df):
    """Renderiza a sub-aba "Mapa de Serviços"."""
    st.header("🗺️ Mapa de Dependências de Serviços")
    st.markdown("Visualização inferida das conexões entre serviços baseada em menções nos logs.")
    
    dependencies = cached_infer_service_dependencies(filtered_df)
    if not dependencies.empty:
        min_conn = st.slider("Mínimo de Conexões (Filtro de Ruído)", min_value=1, max_value=int(dependencies['count'].max()), value=1, help="Aumente para ver apenas as dependências mais fortes e limpar o mapa.")
        
        filtered_deps = dependencies[dependencies['count'] >= min_conn]
        
        col_map, col_data = st.columns([3, 1])
        
        with col_data:
            st.subheader("Dados de Conexão")
            st.dataframe(filtered_deps, use_container_width=True)
        
        with col_map:
            st.subheader("Grafo de Dependência")
            st.caption(f"Exibindo {len(filtered_deps)} conexões.")
            dot = "digraph G {\n"
            dot += "  bgcolor=\"transparent\";\n"
            dot += "  rankdir=LR;\n" 
            dot += "  node [style=filled, fillcolor=\"#4c78a8\", fontcolor=white, shape=box, fontname=\"Arial\", margin=0.2];\n"
            dot += "  edge [color=\"#666666\", fontname=\"Arial\", fontsize=10, arrowsize=0.8];\n"
            
            max_count = filtered_deps['count'].max() if not filtered_deps.empty else 1
            
            for _, row in filtered_deps.iterrows():
                s = row['source'].replace('"', '\\"')
                t = row['target'].replace('"', '\\"')
                w = 1 + (row['count'] / max_count * 4)
                dot += f'  "{s}" -> "{t}" [label="{row["count"]}", penwidth={w}];\n'
            
            dot += "}"
            st.graphviz_chart(dot, use_container_width=True)
    else:
        st.info("Nenhuma dependência clara encontrada nos logs atuais.\n\n**Como funciona:** O sistema procura nomes de outros 'Sources', **Endereços IP** ou **URLs** dentro das mensagens de logs. Isso ajuda a identificar conexões externas e internas.")

def render_diff_sub_tab(filtered_df, config):
    """Renderiza a sub-aba "Comparação (Diff)"."""
    st.header("⚖️ Comparação de Logs (Baseline vs Atual)")
    st.markdown("Compare o arquivo atual com um arquivo de referência (ex: logs de ontem ou de antes do deploy) para identificar regressões.")
    
    ref_file = st.file_uploader("Carregar Arquivo de Referência (CSV)", type="csv")
    if ref_file:
        try:
            stringio_ref = StringIO(ref_file.getvalue().decode("utf-8"))
            df_ref = pd.read_csv(stringio_ref, header=None, names=['timestamp', 'source', 'message'])
            
            with st.spinner("Processando arquivo de referência..."):
                df_ref_proc, _ = cached_process_log_data(df_ref, config)
            
            metrics = lam.compare_log_datasets(filtered_df, df_ref_proc)
            
            col_d1, col_d2, col_d3 = st.columns(3)
            
            col_d1.metric(
                "Volume de Logs", 
                metrics['vol_main'], 
                delta=f"{metrics['vol_delta']} ({metrics['vol_delta']/metrics['vol_ref']*100:.1f}%)" if metrics['vol_ref'] > 0 else None,
                delta_color="inverse"
            )
            
            col_d2.metric(
                "Taxa de Erro", 
                f"{metrics['err_rate_main']:.2f}%",
                delta=f"{metrics['err_rate_delta']:.2f}%",
                delta_color="inverse"
            )
            
            col_d3.metric(
                "Latência Média",
                f"{metrics['lat_main']:.1f} ms",
                delta=f"{metrics['lat_main'] - metrics['lat_ref']:.1f} ms",
                delta_color="inverse"
            )
            
            st.markdown("---")
            st.subheader("🆕 Novos Erros Detectados")
            st.write("Assinaturas de erro que aparecem no arquivo atual mas NÃO existiam na referência.")
            
            new_errors_data = []
            
            if metrics['new_error_signatures']:
                for sig in metrics['new_error_signatures']:
                    st.error(f"Nova Assinatura: {sig}")
                    matches = filtered_df[filtered_df['message'].astype(str).str.contains(re.escape(sig[:20]), regex=False)]
                    if not matches.empty:
                        example_msg = matches.iloc[0]['message']
                        st.code(example_msg)
                        new_errors_data.append({"Assinatura": sig, "Exemplo": example_msg})
                
                if new_errors_data:
                    df_new_errors = pd.DataFrame(new_errors_data)
                    st.download_button(
                        label="📥 Baixar Relatório de Regressão (CSV)",
                        data=df_new_errors.to_csv(index=False).encode('utf-8'),
                        file_name="novos_erros_regressao.csv",
                        mime="text/csv",
                        help="Baixa uma lista contendo apenas os erros que surgiram nesta versão."
                    )
            else:
                st.success("Nenhum tipo de erro novo detectado (Regressão limpa).")
                
        except Exception as e:
            st.error(f"Erro ao processar referência: {e}")
    else:
        st.info("Faça upload de um arquivo CSV de referência para habilitar a comparação.")

def render_flame_graph_sub_tab(filtered_df):
    """Renderiza a sub-aba "Flame Graph"."""
    st.header("🔥 Flame Graph de Erros")
    st.markdown("Visualização agregada dos **Stack Traces** mais frequentes nos logs de erro. Ajuda a identificar qual caminho de código está falhando mais.")
    
    stack_df = cached_generate_stack_trace_metrics(filtered_df)
    if not stack_df.empty:
        chart = alt.Chart(stack_df.head(20)).mark_bar().encode(
            x=alt.X('count:Q', title='Ocorrências'),
            y=alt.Y('stack_trace:N', sort='-x', title='Caminho do Stack Trace (Root -> Leaf)', axis=alt.Axis(labels=False)), # Oculta labels longos
            color=alt.Color('depth:Q', title='Profundidade', scale=alt.Scale(scheme='magma')),
            tooltip=['count', 'depth', 'stack_trace']
        ).properties(height=400, title="Top 20 Caminhos de Erro Mais Frequentes")
        
        st.altair_chart(chart, use_container_width=True)
        
        st.subheader("Detalhamento dos Stacks")
        st.dataframe(stack_df[['count', 'depth', 'stack_trace']], use_container_width=True)
    else:
        st.info("Nenhum stack trace encontrado.")


def render_page():
    """
    Renderiza a aba "Investigação Detalhada" com suas sub-abas.
    """
    st.title("🔍 Investigação Detalhada")

    if 'display_df' not in st.session_state or st.session_state['display_df'].empty:
        st.warning("Dados não carregados. Por favor, vá para a página principal e carregue os dados primeiro.")
        return

    display_df = st.session_state['display_df']
    raw_df = st.session_state['raw_df']
    config = st.session_state['config']
    enable_masking = st.session_state['enable_masking']
    
    subtab_explorer, subtab_map, subtab_diff, subtab_flame = st.tabs([
        "🔎 Explorador de Logs", "🗺️ Mapa de Serviços", "⚖️ Comparação (Diff)", "🔥 Flame Graph"
    ])
    
    with subtab_explorer:
        render_explorer_sub_tab(display_df, raw_df, enable_masking)
        
    with subtab_map:
        render_map_sub_tab(display_df)

    with subtab_diff:
        render_diff_sub_tab(display_df, config)

    with subtab_flame:
        render_flame_graph_sub_tab(display_df)
