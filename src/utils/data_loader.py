# c:\Users\Andressa.Atelli\Documents\locktonloganalytics\dashboard\data_loader.py
# Este arquivo contém a lógica para carregar dados de diferentes fontes
# (InfluxDB, CSV, API Graylog, Banco de dados local) com base na seleção do usuário.

import streamlit as st
import pandas as pd
import log_analyzer as lam
from influxdb_client import InfluxDBClient
import os
import time
from io import StringIO

def load_data(data_source, auto_refresh):
    """
    Carrega os dados da fonte selecionada pelo usuário.

    Args:
        data_source (str): A fonte de dados selecionada ('InfluxDB', 'Upload CSV', etc.).
        auto_refresh (bool): Flag para indicar se a busca de dados deve ser automática.

    Returns:
        pd.DataFrame or None: O DataFrame carregado ou None se nenhum dado for carregado.
    """
    df = None
    
    # --- INFLUXDB CONFIGURATION ---
    INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb-staging:8086")
    INFLUXDB_TOKEN = os.getenv("DOCKER_INFLUXDB_INIT_ADMIN_TOKEN")
    INFLUXDB_ORG = os.getenv("DOCKER_INFLUXDB_INIT_ORG")
    INFLUXDB_BUCKET = os.getenv("DOCKER_INFLUXDB_INIT_BUCKET")

    # --- GRAYLOG CONFIGURATION ---
    GRAYLOG_API_URL = lam.get_secret("GRAYLOG_API_URL", "")
    GRAYLOG_USER = lam.get_secret("GRAYLOG_USER", "")
    GRAYLOG_PASSWORD = lam.get_secret("GRAYLOG_PASSWORD", "")

    if data_source == "InfluxDB (Real-time)":
        st.subheader("⚡️ Logs em Tempo Real do InfluxDB")
        if 'streaming' not in st.session_state:
            st.session_state.streaming = False

        log_levels = ["INFO", "WARNING", "ERROR", "DEBUG", "unknown"]
        selected_levels = st.sidebar.multiselect("Nível do Log", options=log_levels, default=log_levels)
        search_query_realtime = st.sidebar.text_input("Buscar na mensagem", key="search_realtime")

        def query_influxdb(client, levels, search_term, time_range="-15m"):
            query_api = client.query_api()
            level_filters = [f'r.level == "{level}"' for level in levels]
            level_filter_str = " or ".join(level_filters)
            
            query = f'''
            from(bucket: "{INFLUXDB_BUCKET}")
              |> range(start: {time_range})
              |> filter(fn: (r) => r._measurement == "log_entry")
            '''
            if level_filter_str:
                query += f'|> filter(fn: (r) => {level_filter_str})'
            if search_term:
                search_term_escaped = search_term.replace('', '').replace('"', '"')
                query += f'|> filter(fn: (r) => r._field == "message" and r._value =~ /(?i){search_term_escaped}/)'
            query += '|> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value") |> keep(columns: ["_time", "level", "message"]) |> sort(columns: ["_time"], desc: true)'
            
            try:
                result = query_api.query_data_frame(query=query, org=INFLUXDB_ORG)
                if isinstance(result, list):
                    result = pd.concat(result, ignore_index=True) if result else pd.DataFrame()
                if not result.empty:
                    result['source'] = 'influxdb'
                    result.rename(columns={'_time': 'timestamp'}, inplace=True)
                    return result[['timestamp', 'level', 'message', 'source']]
                return pd.DataFrame(columns=['timestamp', 'level', 'message', 'source'])
            except Exception as e:
                st.error(f"Erro ao consultar InfluxDB: {e}")
                return pd.DataFrame()

        col1, col2 = st.columns(2)
        if col1.button("Parar Stream" if st.session_state.streaming else "Iniciar Stream"):
            st.session_state.streaming = not st.session_state.streaming
            st.rerun()
        if col2.button("📸 Snapshot & Analisar"):
            client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
            snapshot_df = query_influxdb(client, selected_levels, search_query_realtime)
            if not snapshot_df.empty:
                st.session_state['snapshot_df'] = snapshot_df
                st.session_state['data_source'] = 'Snapshot'
                st.success(f"{len(snapshot_df)} logs capturados. Trocando para a aba de análise.")
                time.sleep(2); st.rerun()
            else:
                st.warning("Nenhum log encontrado no snapshot.")

        if st.session_state.streaming:
            placeholder = st.empty()
            client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
            while st.session_state.streaming:
                with placeholder.container():
                    df_influx = query_influxdb(client, selected_levels, search_query_realtime, time_range="-5m")
                    # ... (UI de streaming) ...
                    st.dataframe(df_influx)
                    time.sleep(5)

    elif data_source == "Snapshot":
        st.success("Analisando snapshot de dados do InfluxDB.")
        df = st.session_state.get('snapshot_df')

    elif data_source == "Upload CSV":
        uploaded_file = st.file_uploader("Escolha um arquivo CSV", type="csv")
        if uploaded_file is not None:
            try:
                file_bytes = uploaded_file.getvalue()
                file_hash = lam.calculate_file_hash(file_bytes)
                st.sidebar.success(f"🔒 Integridade Verificada (SHA-256):
{file_hash[:10]}...{file_hash[-10:]}")
                stringio = StringIO(file_bytes.decode("utf-8"))
                df = pd.read_csv(stringio, header=None, names=['timestamp', 'source', 'message'])
                st.success("Arquivo CSV carregado com sucesso!")
            except Exception as e:
                st.error(f"Erro ao ler arquivo: {e}")

    elif data_source == "Base Local (Histórico)":
        st.sidebar.markdown("### 🗄️ Busca Avançada")
        db_sources = lam.get_unique_sources_from_db()
        filter_source = st.sidebar.selectbox("Filtrar por Origem", ["Todos"] + db_sources)
        search_query = st.sidebar.text_input("Conteúdo (Palavra-chave)", placeholder="Ex: error AND timeout")
        col_d1, col_d2 = st.sidebar.columns(2)
        start_date = col_d1.date_input("Data Início", pd.to_datetime("today").date())
        end_date = col_d2.date_input("Data Fim", pd.to_datetime("today").date())
        limit_local = st.sidebar.number_input("Limite", 1000, 100000, 10000)
        
        if st.sidebar.button("🔍 Buscar na Base"):
            with st.spinner("Buscando no banco de dados..."):
                df = lam.search_logs_in_db(query=search_query, start_date=start_date, end_date=end_date, source=filter_source, limit=limit_local)
                if df.empty: st.warning("Nenhum log encontrado.")
                else: st.success(f"{len(df)} logs recuperados.")

    elif data_source == "API Graylog":
        st.sidebar.markdown("### 🔌 Conexão Graylog")
        if not GRAYLOG_API_URL or not GRAYLOG_USER:
            st.sidebar.error("Credenciais do Graylog não configuradas.")
        
        gl_query = st.sidebar.text_input("Query (Lucene)", "*")
        gl_range = st.sidebar.number_input("Janela (segundos)", value=300)
        gl_limit = st.sidebar.number_input("Limite de Logs", 10, 1000, 100)
        
        btn_search = st.sidebar.button("📥 Buscar Logs")
        if auto_refresh != st.session_state.get('auto_refresh', False):
            lam.save_setting("auto_refresh", str(auto_refresh))
            st.session_state['auto_refresh'] = auto_refresh

        now = time.time()
        if 'last_fetch_ts' not in st.session_state: st.session_state['last_fetch_ts'] = now
        timer_expired = auto_refresh and (now - st.session_state['last_fetch_ts'] >= 300)

        if btn_search or timer_expired:
            st.session_state['last_fetch_ts'] = now
            with st.spinner("Conectando ao Graylog..."):
                df_api, error = lam.fetch_logs_from_graylog(GRAYLOG_API_URL, GRAYLOG_USER, GRAYLOG_PASSWORD, gl_query, relative=gl_range, limit=gl_limit)
                if error: st.error(error)
                else:
                    st.session_state['graylog_data'] = df_api
                    st.success(f"Conectado! {len(df_api)} logs prontos.")
                    with st.spinner("Salvando na base local..."):
                        count = lam.ingest_logs_to_db(df_api)
                        if count > 0: st.toast(f"{count} logs processados.", icon="💾")
        
        if 'graylog_data' in st.session_state:
            df = st.session_state.get('graylog_data')
            if st.sidebar.button("🗑️ Limpar Dados"):
                del st.session_state['graylog_data']
                st.cache_data.clear(); st.rerun()

    return df
