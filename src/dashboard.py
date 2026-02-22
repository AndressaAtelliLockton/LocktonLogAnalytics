import streamlit as st
import pandas as pd
import log_analyzer as lam
from io import StringIO
import altair as alt
import re
import time
import os
import asyncio
from streamlit_option_menu import option_menu
import importlib

from utils.caching import (
    cached_process_log_data,
    cached_extract_latency_metrics,
    cached_detect_volume_anomalies,
    cached_mask_sensitive_data,
    cached_detect_rare_patterns,
    cached_extract_system_metrics,
    cached_extract_rum_metrics
)

# Carrega variáveis de ambiente locais se possível
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def resolve_page_index(query_params, page_slugs, page_options):
    """
    Determina o índice da página ativa com base nos parâmetros da URL.
    """
    default_index = 0
    try:
        current_slug = query_params.get("page")
        if current_slug:
            # Busca reversa: slug -> nome da página
            for name, slug in page_slugs.items():
                if slug == current_slug:
                    if name in page_options:
                        default_index = page_options.index(name)
                    break
    except Exception:
        pass
    return default_index

def main():
    st.set_page_config(
        page_title="Lockton Analytics",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Oculta o menu de navegação nativo da sidebar e ajusta layout para tela cheia
    st.markdown("""
        <style>
            /* Oculta a navegação nativa (redundante com o menu superior) */
            [data-testid="stSidebarNav"] {display: none !important;}

            /* Ajusta o container principal para ocupar toda a largura da tela */
            .block-container {
                max-width: 100% !important;
                padding-top: 3rem;
                padding-right: 1rem;
                padding-left: 1rem;
                padding-bottom: 1rem;
            }
        </style>
        <script>
            // Observer para garantir que o menu seja ocultado assim que renderizado (evita FOUC)
            const observer = new MutationObserver((mutations) => {
                const nav = document.querySelector('[data-testid="stSidebarNav"]');
                if (nav) {
                    nav.style.display = 'none';
                }
            });
            observer.observe(document.body, { childList: true, subtree: true });
        </script>
    """, unsafe_allow_html=True)

    # --- Menu de Navegação ---
    
    # Definição das páginas e seus slugs para URL
    page_options = [
        "Visão Executiva", 
        "Investigação Detalhada",
        "Inteligência & Previsão",
        "Métricas Customizadas",
        "RUM (Frontend)",
        "Infraestrutura",
        "Monitoramento de API",
        "Ferramentas Técnicas",
        "CI/CD & Pipelines"
    ]
    
    page_slugs = {
        "Visão Executiva": "home",
        "Investigação Detalhada": "investigation",
        "Inteligência & Previsão": "intelligence",
        "Métricas Customizadas": "custom-metrics",
        "RUM (Frontend)": "rum",
        "Infraestrutura": "infrastructure",
        "Monitoramento de API": "api-monitoring",
        "Ferramentas Técnicas": "tools",
        "CI/CD & Pipelines": "cicd"
    }

    # Recupera a aba atual da URL (se existir) para definir o índice inicial
    default_index = resolve_page_index(st.query_params, page_slugs, page_options)

    with st.container():
        selected = option_menu(
            menu_title=None,
            options=page_options,
            icons=[
                "📊", 
                "🔍",
                "🧠",
                "📈",
                "🌐",
                "🖥️",
                "📡",
                "🛠️",
                "🚀"
            ],
            menu_icon="cast",
            default_index=default_index,
            orientation="horizontal",
        )

    # Atualiza a URL com a seleção atual
    if selected in page_slugs:
        st.query_params["page"] = page_slugs[selected]

    # --- Carregamento e Filtro de Dados na Sidebar ---
    with st.sidebar:
        if os.path.exists("lockton_logo.png"):
            st.image("lockton_logo.png", width=80)

        st.title("🤖 Analisador de Logs")
        st.header("Configurações")

        # --- CONFIGURAÇÃO DE SEGREDOS (JIRA & GRAYLOG) ---
        # Prioriza Variáveis de Ambiente (.env/Docker), fallback para secrets.toml (Legado)
        JIRA_WEBHOOK_URL = os.getenv("JIRA_WEBHOOK_URL") or lam.get_secret("JIRA_WEBHOOK_URL", "")
        JIRA_API_KEY = os.getenv("JIRA_API_KEY") or lam.get_secret("JIRA_API_KEY", "")
        GRAYLOG_API_URL = os.getenv("GRAYLOG_API_URL") or lam.get_secret("GRAYLOG_API_URL", "")
        GRAYLOG_USER = os.getenv("GRAYLOG_USER") or lam.get_secret("GRAYLOG_USER", "")
        GRAYLOG_PASSWORD = os.getenv("GRAYLOG_PASSWORD") or lam.get_secret("GRAYLOG_PASSWORD", "")
        GROQ_API_KEY = os.getenv("GROQ_API_KEY") or lam.get_secret("GROQ_API_KEY", "")
        DASHBOARD_URL = os.getenv("DASHBOARD_URL") or lam.get_secret("DASHBOARD_URL", "http://10.130.0.20:8051")
        GRAYLOG_NODE_ID = os.getenv("GRAYLOG_NODE_ID") or lam.get_secret("GRAYLOG_NODE_ID", "615f69241b5dfd3535699150")

        if GROQ_API_KEY and "GROQ_API_KEY" not in os.environ:
            os.environ["GROQ_API_KEY"] = GROQ_API_KEY

        if GRAYLOG_API_URL: lam.save_setting("graylog_url", GRAYLOG_API_URL)
        if GRAYLOG_USER: lam.save_setting("graylog_user", GRAYLOG_USER)
        if GRAYLOG_PASSWORD: lam.save_setting("graylog_pass", GRAYLOG_PASSWORD)
        if DASHBOARD_URL: lam.save_setting("dashboard_url", DASHBOARD_URL)
        if DASHBOARD_URL: st.caption(f"🔗 URL Externa: {DASHBOARD_URL}")

        config, error_msg = lam.load_config()
        if error_msg:
            st.error(error_msg)
            config = {}

        st.subheader("📂 Fonte de Dados")
        data_source = st.radio("Origem", ["Upload CSV", "API Graylog", "Base Local (Histórico)"], index=1, help="Escolha a fonte dos logs.")
        auto_refresh = st.checkbox("🔄 Atualização Automática (5 min)", value=st.session_state.get('auto_refresh', True), help="Atualiza os dados automaticamente a cada 5 minutos.")
        
        df = st.session_state.get('df')
        
        # Lógica para auto-load e refresh
        now = time.time()
        should_load = False

        if 'last_load_time' not in st.session_state:
            st.session_state.last_load_time = 0

        # Auto-load na primeira vez
        if data_source == "API Graylog" and not st.session_state.get('initial_load_done'):
            should_load = True
            st.session_state.initial_load_done = True
            
        # Refresh a cada 5 minutos
        if auto_refresh and (now - st.session_state.last_load_time > 300):
            should_load = True

        # Botão manual
        if data_source == "API Graylog" and st.button("📥 Buscar Logs"):
            should_load = True

        if should_load and data_source == "API Graylog":
            with st.spinner("Conectando ao Graylog..."):
                df, _ = lam.fetch_logs_from_graylog(GRAYLOG_API_URL, GRAYLOG_USER, GRAYLOG_PASSWORD, "*", 300, 100)
                st.session_state.last_load_time = now
                st.session_state['df'] = df
                st.rerun()

        if data_source == "Upload CSV":
            uploaded_file = st.file_uploader("Escolha um arquivo CSV", type="csv")
            if uploaded_file:
                stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
                df = pd.read_csv(stringio, header=None, names=['timestamp', 'source', 'message'])
                st.session_state['df'] = df
        elif data_source == "Base Local (Histórico)":
            st.warning("Busca em base local ainda não implementada.")

    # --- Processamento e Armazenamento em Cache ---
    if df is not None:
        raw_df, _ = cached_process_log_data(df, config)
        
        with st.sidebar:
            st.subheader("🔍 Filtros Globais")
            all_sources = sorted(raw_df['source'].unique())
            selected_sources = st.multiselect("Source", all_sources, default=all_sources)
            
            all_levels = sorted(raw_df['log_level'].unique())
            selected_log_levels = st.multiselect("Log Level", all_levels, default=all_levels)

            enable_masking = st.checkbox("🛡️ Mascarar Dados", value=True)
            
        filtered_df = raw_df[
            (raw_df['source'].isin(selected_sources)) &
            (raw_df['log_level'].isin(selected_log_levels))
        ]
        display_df = cached_mask_sensitive_data(filtered_df.copy()) if enable_masking else filtered_df.copy()

        filtered_df['timestamp'] = pd.to_datetime(filtered_df['timestamp'])
        
        # Opções de Exportação na Sidebar (após filtros)
        with st.sidebar:
            st.markdown("---")
            st.subheader("📄 Exportação")
            
            if st.checkbox("Habilitar Relatório PDF"):
                include_ai = st.checkbox("Incluir Análise IA (Erros Críticos)", value=False, help="Analisa os top 5 erros críticos com IA e inclui no PDF. Pode aumentar o tempo de geração.")
                
                with st.spinner("Preparando PDF..."):
                    # Prepara dados para o relatório
                    anomalies = cached_detect_volume_anomalies(filtered_df, 3.0)
                    rare_logs = cached_detect_rare_patterns(filtered_df, 0.01)
                    
                    # Gera gráfico simples para o PDF
                    if not filtered_df.empty and 'timestamp' in filtered_df.columns:
                        chart_data = filtered_df.set_index('timestamp').resample('T').size().reset_index(name='count')
                        vol_chart = alt.Chart(chart_data).mark_line().encode(x='timestamp:T', y='count:Q').properties(title="Volume de Logs")
                        charts = {"Volume de Logs": vol_chart}
                    else:
                        charts = {}

                    # Análise de IA sob demanda
                    ai_analyses = []
                    if include_ai:
                        with st.spinner("Consultando IA para o relatório..."):
                            ai_analyses = lam.analyze_critical_logs_with_ai(filtered_df)

                    pdf_bytes, pdf_err = lam.generate_pdf_report(filtered_df, anomalies, rare_logs, charts, ai_analyses)
                
                if pdf_bytes:
                    st.download_button(label="📥 Baixar Relatório PDF", data=pdf_bytes, file_name="relatorio_analise.pdf", mime="application/pdf")
                elif pdf_err:
                    st.error(f"Erro PDF: {pdf_err}")

        st.session_state['filtered_df'] = filtered_df
        st.session_state['display_df'] = display_df
        st.session_state['raw_df'] = raw_df
        st.session_state['config'] = config
        st.session_state['JIRA_WEBHOOK_URL'] = JIRA_WEBHOOK_URL
        st.session_state['JIRA_API_KEY'] = JIRA_API_KEY
        st.session_state['DASHBOARD_URL'] = DASHBOARD_URL
        st.session_state['GRAYLOG_API_URL'] = GRAYLOG_API_URL
        st.session_state['GRAYLOG_USER'] = GRAYLOG_USER
        st.session_state['GRAYLOG_PASSWORD'] = GRAYLOG_PASSWORD
        st.session_state['GRAYLOG_NODE_ID'] = GRAYLOG_NODE_ID
        st.session_state['enable_masking'] = enable_masking
        ts_df = filtered_df.dropna(subset=['timestamp'])
        if not ts_df.empty:
            min_ts, max_ts = ts_df['timestamp'].min(), ts_df['timestamp'].max()
            duration = (max_ts - min_ts).total_seconds()
            if duration < 3600: rule = 'T'
            elif duration < 86400: rule = '5T'
            else: rule = 'H'
            time_series_df = ts_df.set_index('timestamp').resample(rule).size().reset_index(name='count')
        else:
            time_series_df = pd.DataFrame(columns=['timestamp', 'count'])
        st.session_state['time_series_df'] = time_series_df
        st.session_state['category_counts'] = filtered_df['category'].value_counts().to_dict()
        st.session_state['z_score_threshold'] = 3.0
        st.session_state['rarity_threshold'] = 0.01

        # --- Renderização da Página Selecionada ---
        page_files = {
            "Visão Executiva": "1_Executive",
            "Investigação Detalhada": "2_Investigation",
            "Inteligência & Previsão": "3_Intelligence",
            "Métricas Customizadas": "4_Custom_Metrics",
            "RUM (Frontend)": "5_RUM",
            "Infraestrutura": "6_Infrastructure",
            "Monitoramento de API": "7_API_Monitoring",
            "Ferramentas Técnicas": "8_Tools",
            "CI/CD & Pipelines": "9_CICD"
        }

        if selected in page_files:
            module_name = f"pages.{page_files[selected]}"
            try:
                page_module = importlib.import_module(module_name)
                page_module.render_page()
            except ImportError:
                st.error(f"Página '{selected}' não encontrada. Verifique o arquivo 'pages/{page_files[selected]}.py'.")
        else:
            st.info("Selecione uma página no menu acima para começar.")
    else:
        st.info("Por favor, carregue os dados na barra lateral para começar a análise.")


if __name__ == "__main__":
    main()
