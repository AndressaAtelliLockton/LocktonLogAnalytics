# -*- coding: utf-8 -*-
"""
Módulo para geração de relatórios.
"""

import os
import tempfile
from datetime import datetime

def generate_pdf_report(df, anomalies, rare_logs, charts_dict, ai_analyses=None):
    """
    Gera um relatório em PDF com estatísticas, gráficos (convertidos de Altair) e anomalias.
    """
    try:
        from fpdf import FPDF
        import vl_convert as vlc
    except ImportError:
        return None, "Dependências para PDF não instaladas. Use: pip install fpdf2 vl-convert-python"

    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, 'Relatório de Análise de Logs', 0, 1, 'C')
            self.ln(5)
        
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    
    # Seção 1: Resumo
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "1. Resumo Estatístico", 0, 1)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, f"Total de Logs Analisados: {len(df)}", 0, 1)
    if not df.empty:
        counts = df['log_level'].value_counts()
        pdf.multi_cell(0, 10, f"Distribuição por Nível: {', '.join([f'{k}: {v}' for k, v in counts.items()])}")
    pdf.ln(5)

    # Seção 2: Gráficos
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "2. Visualizações", 0, 1)
    for title, chart in charts_dict.items():
        if chart:
            pdf.set_font("Arial", 'I', 10)
            pdf.cell(0, 10, title, 0, 1)
            try:
                png_data = vlc.vegalite_to_png(chart.to_json())
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(png_data)
                    pdf.image(tmp.name, x=10, w=90)
                os.unlink(tmp.name)
            except Exception as e:
                pdf.cell(0, 10, f"Erro ao renderizar gráfico: {e}", 0, 1)
            pdf.ln(5)

    # Seção 3: Anomalias
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "3. Anomalias Detectadas", 0, 1)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, "Picos de Volume:", 0, 1)
    pdf.set_font("Arial", size=10)
    if not anomalies.empty:
        for _, row in anomalies.head(10).iterrows():
            pdf.cell(0, 10, f"- {row['timestamp']}: {row['count']} logs", 0, 1)
    else:
        pdf.cell(0, 10, "Nenhum pico de volume detectado.", 0, 1)
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, "Padrões Raros:", 0, 1)
    pdf.set_font("Arial", size=10)
    if not rare_logs.empty:
        for _, row in rare_logs.head(5).iterrows():
            pdf.multi_cell(0, 10, f"- [{row['log_level']}] {row['message'][:100]}...")
    else:
        pdf.cell(0, 10, "Nenhum padrão raro detectado.", 0, 1)

    # Seção 4: Análise de IA (Erros Críticos)
    if ai_analyses:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "4. Analise de IA (Erros Criticos)", 0, 1)
        
        for analysis in ai_analyses:
            pdf.set_font("Arial", 'B', 10)
            ts = str(analysis.get('timestamp', 'N/A'))
            pdf.cell(0, 10, f"Timestamp: {ts}", 0, 1)
            
            pdf.set_font("Arial", 'I', 9)
            # Sanitização básica para fontes padrão do FPDF (Latin-1)
            msg = str(analysis.get('log_message', ''))[:200].replace('\n', ' ').encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 5, f"Log: {msg}...")
            
            pdf.ln(2)
            pdf.set_font("Arial", size=9)
            ai_text = str(analysis.get('ai_analysis', '')).replace('**', '').replace('##', '').encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 5, f"Analise: {ai_text}")
            pdf.ln(5)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)

    # Gera o output. FPDF 1.7.x retorna string, FPDF2 retorna bytearray.
    pdf_content = pdf.output()
    if isinstance(pdf_content, str):
        return pdf_content.encode('latin-1'), None
    return bytes(pdf_content), None
