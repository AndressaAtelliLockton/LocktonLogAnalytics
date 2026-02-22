# -*- coding: utf-8 -*-
"""
Módulo para a aba "Inteligência & Previsão".
Inclui detecção de anomalias, previsão de volume, simulador de alertas e segurança.
"""

import streamlit as st
import pandas as pd
import altair as alt
import log_analyzer as lam
from dashboard.caching import (
    cached_detect_volume_anomalies, 
    cached_detect_rare_patterns, 
    cached_generate_volume_forecast, 
    cached_detect_log_periodicity, 
    cached_analyze_security_threats, 
    cached_extract_latency_metrics, 
    cached_detect_bottlenecks, 
    cached_group_incidents, 
    cached_mask_sensitive_data
)

def render_ml_sub_tab(filtered_df, time_series_df, z_score_threshold, rarity_threshold, enable_masking):
    """Renderiza a sub-aba "Anomalias (ML)"."""
    st.header("🧠 Detecção de Anomalias (Machine Learning)")
    st.markdown("Esta seção utiliza algoritmos estatísticos para identificar comportamentos fora do padrão.")

    col_vol, col_pat = st.columns(2)
    with col_vol:
        st.subheader("📈 Anomalias de Volume")
        st.write(f"Detecta picos repentinos na quantidade de logs (Z-Score > {z_score_threshold}).")
        
        anomalies_df = cached_detect_volume_anomalies(filtered_df, z_score_threshold)
        if not anomalies_df.empty:
            st.error(f"Foram detectados {len(anomalies_df)} momentos de pico anômalo.")
            st.dataframe(anomalies_df)
            
            # Gráfico de anomalias
            base = alt.Chart(time_series_df).encode(x='timestamp:T')
            line = base.mark_line().encode(y='count:Q')
            points = alt.Chart(anomalies_df).mark_circle(color='red', size=100).encode(
                x='timestamp:T',
                y='count:Q',
                tooltip=['timestamp', 'count']
            )
            st.altair_chart(line + points, use_container_width=True)
            
            # Botão de Exportação de Anomalias
            csv_anomalies = anomalies_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar Anomalias de Volume (CSV)",
                data=csv_anomalies,
                file_name="anomalias_volume.csv",
                mime="text/csv", 
                help="Baixe a lista de anomalias de volume detectadas em formato CSV."
            )
        else:
            st.success("Nenhuma anomalia de volume detectada.")
    
    with col_pat:
        st.subheader("🦄 Padrões Raros (Rare Events)")
        st.write(f"Detecta mensagens de log com estrutura incomum (frequência < {rarity_threshold*100:.2f}%).")
        
        rare_logs_df = cached_detect_rare_patterns(filtered_df, rarity_threshold)
        if not rare_logs_df.empty:
            st.warning(f"Encontrados {len(rare_logs_df)} logs com padrões raros.")
            st.dataframe(rare_logs_df[['timestamp', 'log_level', 'message']])
            
            # Botão de Exportação de Padrões Raros
            csv_rare = rare_logs_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar Logs Raros (CSV)",
                data=csv_rare,
                file_name="logs_raros.csv",
                mime="text/csv",
                help="Baixe a lista de padrões de log raros detectados em formato CSV."
            )
        else:
            st.success("Nenhum padrão raro detectado.")

    st.markdown("---")
    st.subheader("🔍 Análise de Outliers (Tamanho da Mensagem)")
    st.info("Este gráfico ajuda a identificar logs anormalmente longos (ex: stack traces) ou curtos demais.")
    
    # Scatter Plot: Tamanho da Mensagem vs Tempo
    # Otimização: Amostragem se houver muitos pontos
    scatter_data = filtered_df if len(filtered_df) < 2000 else filtered_df.sample(2000)
    
    if not scatter_data.empty:
        scatter_chart = alt.Chart(scatter_data).mark_circle(size=60).encode(
            x=alt.X('timestamp:T', title='Tempo'),
            y=alt.Y('message_length:Q', title='Tamanho da Mensagem (caracteres)'),
            color=alt.Color('log_level', title='Nível'),
            tooltip=['timestamp', 'log_level', 'category', 'message_length', alt.Tooltip('message', title='Mensagem', format='.100s')]
        ).properties(
            title="Dispersão: Tamanho da Mensagem vs Tempo"
        ).interactive()
        
        st.altair_chart(scatter_chart, use_container_width=True)
    else:
        st.info("Sem dados para análise de outliers.")
    
    st.markdown("---")
    st.subheader("🔔 Agrupamento de Incidentes (AIOps)")
    st.write("Agrupa erros similares em incidentes únicos para evitar fadiga de alertas.")
    
    incidents = cached_group_incidents(filtered_df)
    if not incidents.empty:
        if enable_masking:
            incidents['example_message'] = cached_mask_sensitive_data(pd.DataFrame(incidents['example_message'], columns=['message']))['message']
        st.dataframe(incidents, use_container_width=True)
    else:
        st.success("Nenhum incidente agrupável encontrado nos logs filtrados (Níveis: Error, Fail, Critical ou palavras-chave de erro).")

def render_forecast_sub_tab(filtered_df):
    """Renderiza a sub-aba "Previsão (Forecast)"."""
    st.header("🔮 Previsão de Volume (Forecast)")
    st.markdown("Utiliza regressão linear para projetar a tendência do volume de logs para a próxima hora. Útil para **Capacity Planning**.")
    
    forecast_df, trend, slope = cached_generate_volume_forecast(filtered_df)
    if not forecast_df.empty:
        # Métricas
        col_f1, col_f2, col_f3 = st.columns(3)
        
        # Busca segura dos valores (evita erro de index se filtro vazio ou string diferente)
        hist_data = forecast_df[forecast_df['type'] == 'Histórico 📊']
        pred_data = forecast_df[forecast_df['type'].astype(str).str.contains('Previsão', na=False)]
        
        current_vol = hist_data['count'].iloc[-1] if not hist_data.empty else 0
        predicted_vol = pred_data['count'].iloc[-1] if not pred_data.empty else 0
        
        col_f1.metric("Tendência Atual", trend)
        col_f2.metric("Volume Atual (p/ min)", f"{int(current_vol)}")
        col_f3.metric("Previsão (+60 min)", f"{int(predicted_vol)}", delta=f"{int(predicted_vol - current_vol)}")
        
        # Gráfico
        st.subheader("Projeção de Tráfego")
        
        chart_forecast = alt.Chart(forecast_df).mark_line().encode(
            x=alt.X('timestamp:T', title='Tempo'),
            y=alt.Y('count:Q', title='Volume de Logs'),
            color=alt.Color('type', title='Status', scale=alt.Scale(scheme='category20')),
            strokeDash=alt.condition(
                alt.datum.type != 'Histórico 📊',
                alt.value([5, 5]),  # Linha tracejada para previsão
                alt.value([0])      # Linha sólida para histórico
            ),
            tooltip=['timestamp', 'count', 'type']
        ).interactive()
        
        st.altair_chart(chart_forecast, use_container_width=True)
        
        if slope > 0.1:
            st.warning("⚠️ Atenção: Tendência de crescimento acentuada detectada. Verifique se há um início de incidente ou ataque DDoS.")
        elif slope < -0.1:
            st.info("📉 O volume de logs está diminuindo rapidamente.")
    else:
        st.warning("Dados insuficientes para gerar uma previsão confiável.")

    # --- FFT Periodicity ---
    st.markdown("---")
    st.subheader("🔄 Análise de Periodicidade (FFT)")
    st.markdown("Detecta padrões repetitivos (ex: Cron Jobs, Health Checks) analisando o espectro de frequência dos logs.")
    
    periods = cached_detect_log_periodicity(filtered_df)
    
    if periods:
        st.success(f"Detectamos {len(periods)} padrão(ões) cíclico(s) relevante(s).")
        cols = st.columns(len(periods))
        for i, (period, strength) in enumerate(periods):
            with cols[i]:
                st.metric(
                    label=f"Ciclo #{i+1}",
                    value=f"A cada {period:.1f} min",
                    help=f"Força do sinal (Confiança): {strength*100:.1f}%"
                )
    else:
        duration_str = "N/A"
        if not filtered_df.empty and 'timestamp' in filtered_df.columns:
            duration = filtered_df['timestamp'].max() - filtered_df['timestamp'].min()
            duration_minutes = duration.total_seconds() / 60
            duration_str = f"{duration_minutes:.1f} min"
        
        st.info(f"Nenhuma periodicidade clara detectada.\n\n**Diagnóstico:**\n- Duração dos dados: {duration_str}\n- Sinal pode ser aperiódico (sem repetições fixas).")

def render_alerts_sub_tab(filtered_df, enable_masking):
    """Renderiza a sub-aba "Simulador de Alertas"."""
    st.header("🔔 Simulador de Alertas")
    st.markdown("Defina regras personalizadas para verificar quais logs disparariam alertas em um ambiente de produção.")
    
    col_rule1, col_rule2, col_rule3 = st.columns(3)
    
    with col_rule1:
        alert_latency = st.number_input("Regra: Latência Maior que (ms)", min_value=0, value=0, step=50, help="0 para desativar este filtro.", key="alert_latency_3")
    
    with col_rule2:
        alert_keyword = st.text_input("Regra: Contém Palavra-chave", placeholder="Ex: timeout, deadlock", help="Digite uma palavra ou frase que deve estar presente no log para disparar o alerta.")
    
    with col_rule3:
        # Usa raw_df para garantir que todos os níveis apareçam, independente do filtro atual
        raw_df = st.session_state.get('raw_df')
        source_df = raw_df if raw_df is not None and not raw_df.empty else filtered_df
        
        all_levels = sorted(source_df['log_level'].unique())
        default_levels = [lvl for lvl in ['Error', 'Fail', 'Critical', 'Fatal'] if lvl in all_levels]
        alert_levels = st.multiselect("Regra: Níveis de Log", options=all_levels, default=default_levels, help="Selecione quais níveis de log (ex: Error) devem ser considerados para o alerta.")
    
    # Recupera URL configurada (Oculta por segurança)
    webhook_url = lam.get_setting("webhook_url", "")
    if webhook_url:
        st.info("Webhook do Teams configurado para Canal: Alert for Logs.")
    else:
        st.warning("Webhook do Teams não configurado no sistema.")

    # Botões lado a lado
    col_btn_sim, col_btn_test = st.columns([3, 1])

    with col_btn_sim:
        run_sim = st.button("Simular Regras de Alerta", help="Clique para verificar quais logs históricos teriam disparado este alerta com as regras definidas.", use_container_width=True)
    
    with col_btn_test:
        run_test = st.button("📨 Testar Conexão", help="Envia uma mensagem de teste imediata para o Teams configurado.", use_container_width=True)

    if run_sim:
        # Salva URL se preenchida para uso futuro
        if webhook_url:
            lam.save_setting("webhook_url", webhook_url)

        # Se nenhum filtro for aplicado, avisa
        if alert_latency == 0 and not alert_keyword and not alert_levels:
            st.warning("Defina ao menos uma regra para simular.")
        else:
            # Usa filtered_df para simulação no contexto atual
            triggered = lam.simulate_alerts(filtered_df, latency_threshold=alert_latency if alert_latency > 0 else None, keyword=alert_keyword, log_levels=alert_levels)
            
            if not triggered.empty:
                st.error(f"🚨 ALERTA DISPARADO! {len(triggered)} logs correspondem às regras definidas.")
                
                # Aplica mascaramento se estiver ativado
                if enable_masking:
                    triggered_display = lam.mask_sensitive_data(triggered)
                else:
                    triggered_display = triggered

                # Métricas do Alerta
                col_a1, col_a2 = st.columns(2)
                col_a1.metric("Total de Disparos", len(triggered))
                if 'latency_ms' in triggered.columns:
                    max_lat = triggered['latency_ms'].max()
                    col_a2.metric("Latência Máxima Detectada", f"{max_lat} ms")
                
                # Gráfico de linha temporal dos alertas
                st.subheader("Disparos ao Longo do Tempo")
                alert_time_series = triggered.set_index('timestamp').resample('T').size().reset_index(name='count')
                
                alert_chart = alt.Chart(alert_time_series).mark_line(point=True, color='red').encode(
                    x=alt.X('timestamp:T', title='Tempo'),
                    y=alt.Y('count:Q', title='Quantidade de Alertas'),
                    tooltip=['timestamp:T', 'count:Q']
                ).interactive()
                
                st.altair_chart(alert_chart, use_container_width=True)

                # Tabela
                st.dataframe(triggered_display[['timestamp', 'log_level', 'source', 'message']], use_container_width=True)
                
                # Teste de Webhook
                if webhook_url:
                    if st.button("📨 Enviar Alerta de Teste para Webhook"):
                        msg_body = f"Foram detectados {len(triggered)} logs críticos. Latência máx: {triggered.get('latency_ms', pd.Series([0])).max()}ms."
                        response = lam.send_webhook_alert(webhook_url, msg_body)
                        if isinstance(response, str): st.error(response)
                        else: st.success(f"Alerta enviado com sucesso! (Status: {response.status_code})")
            else:
                st.success("✅ Nenhum log dispararia este alerta com as regras atuais.")

    if run_test:
        if webhook_url:
            lam.save_setting("webhook_url", webhook_url)
            response = lam.send_webhook_alert(webhook_url, "Isso é um teste de verificação de conectividade.\n\nSe você recebeu esta mensagem, a integração com o Dashboard de Logs está **OPERACIONAL**! ✅", title="🔔 Teste de Conexão Teams")
            
            if isinstance(response, str):
                st.error(response)
            elif response.status_code != 200:
                st.error(f"Erro {response.status_code}: {response.text}")
            else:
                st.toast("Mensagem de teste enviada!", icon="🚀")
                st.info("Resposta do servidor Teams (código 200 OK):")
                st.code(response.text)
        else:
            st.warning("Por favor, insira uma URL de Webhook válida.")

def render_siem_sub_tab(filtered_df):
    """Renderiza a sub-aba "Segurança (SIEM)"."""
    st.header("🛡️ Análise de Segurança em Tempo Real")
    st.markdown("Monitoramento de IPs suspeitos e ameaças potenciais (Threat Intelligence simulada).")
    
    threats = cached_analyze_security_threats(filtered_df)
    if not threats.empty:
        col_kpi1, col_kpi2 = st.columns(2)
        with col_kpi1:
            st.metric("IPs Críticos", len(threats[threats['status'] == '🔴 Crítico']))
        with col_kpi2:
            st.metric("IPs Suspeitos", len(threats[threats['status'] == '🟡 Suspeito']))
        
        st.subheader("Top IPs por Taxa de Erro")
        st.dataframe(threats)
        
        chart_threat = alt.Chart(threats).mark_circle(size=100).encode(
            x=alt.X('total_logs', title='Volume Total de Logs'),
            y=alt.Y('error_rate', title='Taxa de Erro (0-1)'),
            color='status',
            tooltip=['ip', 'total_logs', 'error_rate', 'status']
        ).interactive()
        st.altair_chart(chart_threat, use_container_width=True)
    else:
        st.info("Nenhum IP detectado nos logs para análise de segurança.")

def render_latency_sub_tab(filtered_df):
    """Renderiza a sub-aba "Performance"."""
    st.header("⏱️ Análise Avançada de Latência")
    st.markdown("Visualização estatística do tempo de resposta extraído dos logs (padrão `duration=Xms`).")
    
    latency_df = cached_extract_latency_metrics(filtered_df)
    if not latency_df.empty:
        # Cálculos Estatísticos
        stats = latency_df['latency_ms'].describe(percentiles=[.5, .9, .95, .99])
        
        # KPIs
        l1, l2, l3, l4 = st.columns(4)
        l1.metric("Média", f"{stats['mean']:.1f} ms")
        l2.metric("P95 (95% dos reqs)", f"{stats['95%']:.1f} ms", help="95% das requisições são mais rápidas que este valor.")
        l3.metric("P99 (Cauda Longa)", f"{stats['99%']:.1f} ms", help="1% das requisições mais lentas (outliers).")
        l4.metric("Máximo", f"{stats['max']:.1f} ms")
        
        st.markdown("---")
        
        col_lat_1, col_lat_2 = st.columns(2)
        
        with col_lat_1:
            st.subheader("Distribuição de Latência (Histograma)")
            hist = alt.Chart(latency_df).mark_bar().encode(
                x=alt.X('latency_ms:Q', bin=alt.Bin(maxbins=30), title='Latência (ms)'),
                y=alt.Y('count()', title='Contagem'),
                tooltip=['count()', alt.Tooltip('latency_ms', bin=True)]
            ).interactive()
            st.altair_chart(hist, use_container_width=True)
            
        with col_lat_2:
            st.subheader("Latência por Origem (Top 10)")
            # Agrupa por source e pega a média e p95
            source_stats = latency_df.groupby('source')['latency_ms'].agg(['mean', 'count', lambda x: x.quantile(0.95)]).reset_index()
            source_stats.columns = ['source', 'mean', 'count', 'p95']
            source_stats = source_stats.sort_values('mean', ascending=False).head(10)
            
            bar_lat = alt.Chart(source_stats).mark_bar().encode(
                x=alt.X('mean:Q', title='Latência Média (ms)'),
                y=alt.Y('source:N', sort='-x', title='Origem'),
                color=alt.Color('mean:Q', scale=alt.Scale(scheme='reds')),
                tooltip=['source', 'mean', 'p95', 'count']
            )
            st.altair_chart(bar_lat, use_container_width=True)

        st.subheader("Evolução Temporal (Scatter Plot)")
        scatter_lat = alt.Chart(latency_df).mark_circle(size=60).encode(
            x='timestamp:T',
            y='latency_ms:Q',
            color=alt.Color('latency_ms', scale=alt.Scale(scheme='turbo')),
            tooltip=['timestamp', 'source', 'latency_ms']
        ).interactive()
        st.altair_chart(scatter_lat, use_container_width=True)
        
        st.markdown("---")
        st.subheader("🐢 Detecção de Gargalos (Bottlenecks)")
        st.markdown("Identificação de serviços ou operações que estão excedendo o tempo limite aceitável.")
        
        bottleneck_threshold = st.number_input("Limiar de Latência para Gargalo (ms)", min_value=100, value=1000, step=100, help="Latências acima deste valor serão consideradas gargalos.", key="bottleneck_threshold_3")
        
        bottlenecks = cached_detect_bottlenecks(filtered_df, bottleneck_threshold)
        
        if not bottlenecks.empty:
            st.error(f"Detectados {len(bottlenecks)} serviços com gargalos de performance (> {bottleneck_threshold}ms).")
            st.dataframe(bottlenecks, use_container_width=True)
            
            # Chart for bottlenecks
            chart_bottleneck = alt.Chart(bottlenecks).mark_bar().encode(
                x=alt.X('avg_latency:Q', title='Latência Média (ms)'),
                y=alt.Y('source:N', sort='-x', title='Serviço'),
                color=alt.Color('slow_count:Q', title='Qtd Ocorrências', scale=alt.Scale(scheme='orangered')),
                tooltip=['source', 'avg_latency', 'max_latency', 'slow_count']
            ).properties(title="Top Gargalos por Latência Média")
            
            st.altair_chart(chart_bottleneck, use_container_width=True)
        else:
            st.success(f"Nenhum gargalo detectado acima de {bottleneck_threshold}ms.")

    else:
        st.info("Nenhum dado de latência encontrado nos logs filtrados. Certifique-se que seus logs contenham padrões como 'duration=100ms' ou 'time=0.5s'.")

def render_page():
    """
    Renderiza a aba "Inteligência & Previsão" com suas sub-abas.
    """
    st.title("🧠 Inteligência & Previsão")

    if 'filtered_df' not in st.session_state or st.session_state['filtered_df'].empty:
        st.warning("Dados não carregados. Por favor, vá para a página principal e carregue os dados primeiro.")
        return

    filtered_df = st.session_state['filtered_df']
    time_series_df = st.session_state['time_series_df']
    z_score_threshold = st.session_state['z_score_threshold']
    rarity_threshold = st.session_state['rarity_threshold']
    enable_masking = st.session_state['enable_masking']
    
    subtab_ml, subtab_forecast, subtab_alerts, subtab_siem, subtab_latency = st.tabs([
        "🧠 Anomalias (ML)", "🔮 Previsão", "🔔 Alertas", "🛡️ Segurança", "⏱️ Performance"
    ])

    with subtab_ml:
        render_ml_sub_tab(filtered_df, time_series_df, z_score_threshold, rarity_threshold, enable_masking)
    with subtab_forecast:
        render_forecast_sub_tab(filtered_df)
    with subtab_alerts:
        render_alerts_sub_tab(filtered_df, enable_masking)
    with subtab_siem:
        render_siem_sub_tab(filtered_df)
    with subtab_latency:
        render_latency_sub_tab(filtered_df)
