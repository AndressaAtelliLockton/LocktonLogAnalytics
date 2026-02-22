# -*- coding: utf-8 -*-
"""
Módulo para a aba "Visão Executiva".
Foca em KPIs de alto nível, gráficos de tendência e saúde geral do sistema.
"""

import streamlit as st
import pandas as pd
import altair as alt
from dashboard.caching import cached_extract_latency_metrics

def render_page():
    """
    Renderiza a página "Visão Executiva" com gráficos e KPIs.
    """
    st.title("📊 Visão Executiva")

    # Check if data is loaded
    if 'filtered_df' not in st.session_state or st.session_state['filtered_df'].empty:
        st.warning("Dados não carregados. Por favor, vá para a página principal e carregue os dados primeiro.")
        return

    filtered_df = st.session_state['filtered_df']
    time_series_df = st.session_state['time_series_df']
    category_counts = st.session_state['category_counts']
    
    # --- Time Series Chart ---
    st.subheader("Volume de Logs (Timeline)")
    
    # Otimização de Performance: Limite rígido de pontos para renderização
    MAX_POINTS = 500
    if len(time_series_df) > MAX_POINTS:
        step = int(len(time_series_df) / MAX_POINTS)
        if step < 1: step = 1
        st.caption(f"⚠️ Exibindo dados otimizados (Amostragem: 1/{step}) para performance.")
        chart_data = time_series_df.iloc[::step]
    else:
        chart_data = time_series_df

    if not chart_data.empty:
        # Gráfico interativo com tooltips avançados
        base = alt.Chart(chart_data).encode(x=alt.X('timestamp:T', title='Tempo'))

        # Área principal
        area = base.mark_area(line=True, opacity=0.5).encode(
            y=alt.Y('count:Q', title='Logs')
        )

        # Seletor para interação (nearest point)
        nearest = alt.selection_point(nearest=True, on='mouseover', fields=['timestamp'], empty=False)

        # Pontos invisíveis para capturar o hover
        selectors = base.mark_point().encode(
            y='count:Q',
            opacity=alt.value(0),
        ).add_params(nearest)

        # Ponto destacado e Texto com valor
        points = base.mark_point(filled=True, color='red').encode(
            y='count:Q',
            opacity=alt.condition(nearest, alt.value(1), alt.value(0))
        )
        text = base.mark_text(align='left', dx=5, dy=-5).encode(
            y='count:Q',
            text=alt.condition(nearest, 'count:Q', alt.value(' '))
        )

        # Linha vertical (Rule) com Tooltip
        rule = base.mark_rule(color='gray').encode(
            opacity=alt.condition(nearest, alt.value(1), alt.value(0)),
            tooltip=[
                alt.Tooltip('timestamp:T', title='Horário', format='%H:%M:%S'),
                alt.Tooltip('count:Q', title='Qtd Logs')
            ]
        ).transform_filter(nearest)

        line_chart = alt.layer(area, selectors, points, rule, text).properties(height=200)
        
        st.altair_chart(line_chart, use_container_width=True)
    else:
        st.info("Sem dados de volume para exibir no período selecionado.")

    # --- Visualizações ---
    st.subheader("Visualizações")

    # Prepare data for charts
    category_df = pd.DataFrame(list(category_counts.items()), columns=['category', 'count'])
    
    log_level_counts = filtered_df['log_level'].value_counts().reset_index()
    log_level_counts.columns = ['log_level', 'count']

    # Charts
    if not category_df.empty:
        pie_chart = alt.Chart(category_df).mark_arc().encode(
            theta=alt.Theta(field="count", type="quantitative"),
            color=alt.Color(field="category", type="nominal"),
            tooltip=['category', 'count']
        ).properties(
            title='Distribuição de Categorias'
        )
    else:
        pie_chart = None

    if not log_level_counts.empty:
        bar_chart = alt.Chart(log_level_counts).mark_bar().encode(
            x=alt.X('log_level', sort='-y', title='Nível do Log'),
            y=alt.Y('count', title='Contagem'),
            color='log_level',
            tooltip=['log_level', 'count']
        ).properties(
            title='Distribuição de Níveis de Log'
        )
    else:
        bar_chart = None
    
    with st.expander("ℹ️ Entenda os Gráficos (Clique para abrir)"):
        st.markdown("""
        **Distribuição de Categorias (Pizza):** Mostra quais tipos de eventos são mais frequentes (ex: Segurança, Performance). Útil para saber onde focar a atenção.
        
        **Distribuição de Níveis (Barras):** Mostra a gravidade dos logs. **Error/Fail** são críticos, **Warning** são avisos e **Info/Debug** são apenas informativos.
        """)
    col1, col2 = st.columns(2)
    with col1:
        if pie_chart:
            st.altair_chart(pie_chart, use_container_width=True)
        else:
            st.info("Sem dados de categorias.")
    with col2:
        if bar_chart:
            st.altair_chart(bar_chart, use_container_width=True)
        else:
            st.info("Sem dados de níveis de log.")

    # --- Heatmap ---
    st.subheader("Mapa de Calor (Heatmap) Temporal")
    st.info("Este gráfico mostra a densidade de logs por Hora do Dia vs Data (Mensal). Áreas mais escuras indicam maior atividade.")
    
    heatmap_df = filtered_df.copy()
    if not heatmap_df.empty:
        heatmap_df['hour'] = heatmap_df['timestamp'].dt.hour
        # Visão Mensal: Agrupa por Dia/Mês para mostrar evolução no mês
        heatmap_df['day_label'] = heatmap_df['timestamp'].dt.strftime('%d/%m')
        heatmap_df['date_sort'] = heatmap_df['timestamp'].dt.date
        
        heatmap_data = heatmap_df.groupby(['date_sort', 'day_label', 'hour']).size().reset_index(name='count')
        # Verifica a amplitude dos dados para decidir a granularidade
        min_ts = heatmap_df['timestamp'].min()
        max_ts = heatmap_df['timestamp'].max()
        duration_hours = (max_ts - min_ts).total_seconds() / 3600

        if duration_hours <= 24:
            # Visão Detalhada (Intra-day): Minuto vs Hora
            heatmap_df['minute'] = heatmap_df['timestamp'].dt.minute
            heatmap_data = heatmap_df.groupby(['hour', 'minute']).size().reset_index(name='count')
            
            heatmap = alt.Chart(heatmap_data).mark_rect().encode(
                x=alt.X('minute:O', title='Minuto (0-59)'),
                y=alt.Y('hour:O', title='Hora do Dia'),
                color=alt.Color('count:Q', title='Qtd Logs', scale=alt.Scale(scheme='yelloworangered')),
                tooltip=['hour', 'minute', 'count']
            ).properties(title="Densidade (Minuto a Minuto)")
        else:
            # Visão Histórica (Mensal): Hora vs Data
            heatmap = alt.Chart(heatmap_data).mark_rect().encode(
                x=alt.X('hour:O', title='Hora do Dia'),
                y=alt.Y('day_label:O', title='Data', sort=alt.EncodingSortField(field="date_sort", order="ascending")),
                color=alt.Color('count:Q', title='Qtd Logs', scale=alt.Scale(scheme='yelloworangered')),
                tooltip=['day_label', 'hour', 'count']
            ).properties(title="Densidade Histórica (Hora x Dia)")
        
        st.altair_chart(heatmap, use_container_width=True)
    else:
        st.info("Sem dados para gerar o mapa de calor.")
    
    # --- Negócio & Saúde (Incorporado) ---
    st.markdown("---")
    st.header("💼 Dashboards de Saúde e Negócio")
    st.markdown("Transformando logs em métricas de ouro (Golden Signals).")
    
    col_lat, col_err, col_traf = st.columns(3)
    
    # Traffic & Error Rate
    traffic = len(filtered_df)
    error_count = len(filtered_df[filtered_df['log_level'].isin(['Error', 'Fail'])])
    error_rate = (error_count / traffic) * 100 if traffic > 0 else 0
    
    col_traf.metric("Tráfego (Total Logs)", traffic)
    col_err.metric("Taxa de Erros", f"{error_rate:.2f}%")
    
    # Latency (Log-to-Metrics)
    latency_df = cached_extract_latency_metrics(filtered_df)
    if not latency_df.empty:
        avg_latency = latency_df['latency_ms'].mean()
        col_lat.metric("Latência Média Estimada", f"{avg_latency:.1f} ms")
        
        st.subheader("Latência ao Longo do Tempo")
        lat_chart = alt.Chart(latency_df).mark_line(point=True).encode(
            x='timestamp:T',
            y=alt.Y('latency_ms:Q', title='Latência (ms)'),
            color='source',
            tooltip=['timestamp', 'latency_ms', 'source']
        ).interactive()
        st.altair_chart(lat_chart, use_container_width=True)
    else:
        col_lat.metric("Latência", "N/A", help="Nenhum log com padrão 'duration=Xms' encontrado.")
