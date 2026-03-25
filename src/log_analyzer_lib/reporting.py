# -*- coding: utf-8 -*-
"""
Módulo para geração de relatórios (PDF).
"""
import os
import tempfile

def generate_pdf_report(df, anomalies, rare_logs, charts_dict, ai_analyses=None):
    """
    Gera um relatório PDF contendo estatísticas, gráficos e anomalias.
    Requer: pip install fpdf vl-convert-python
    """
    try:
        from fpdf import FPDF
        import vl_convert as vlc
    except ImportError:
        return None, "Bibliotecas 'fpdf' ou 'vl-convert-python' não instaladas. Instale-as para gerar o PDF."

    class PDF(FPDF):
        def header(self):
            # Adiciona Logo se existir (lockton_logo.png na raiz)
            logo_path = "lockton_logo.png"
            if os.path.exists(logo_path):
                self.image(logo_path, 10, 8, 33) # x, y, w
                self.set_font('Arial', 'B', 15)
                self.cell(0, 10, 'Relatorio de Analise de Logs', 0, 1, 'C')
                self.ln(12)
            else:
                self.set_font('Arial', 'B', 15)
                self.cell(0, 10, 'Relatorio de Analise de Logs', 0, 1, 'C')
                self.ln(5)
        
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # 1. Resumo Estatístico
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "1. Resumo Estatistico", 0, 1)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, f"Total de Logs: {len(df)}", 0, 1)
    
    if 'log_level' in df.columns:
        counts = df['log_level'].value_counts()
        dist_text = ", ".join([f"{k}: {v}" for k, v in counts.items()])
        pdf.multi_cell(0, 10, f"Distribuicao: {dist_text}")
    pdf.ln(5)

    # 2. Gráficos
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "2. Visualizacoes", 0, 1)
    
    for title, chart in charts_dict.items():
        if chart:
            pdf.set_font("Arial", 'I', 10)
            pdf.cell(0, 10, title, 0, 1)
            try:
                # Converte Altair para PNG usando vl-convert
                png_data = vlc.vegalite_to_png(chart.to_json())
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(png_data)
                    tmp_path = tmp.name
                
                pdf.image(tmp_path, x=10, w=90)
                os.unlink(tmp_path) # Remove arquivo temporário
            except Exception as e:
                pdf.cell(0, 10, f"Erro ao renderizar grafico: {str(e)}", 0, 1)
            pdf.ln(5)

    # 3. Anomalias
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "3. Anomalias Detectadas", 0, 1)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, "Anomalias de Volume:", 0, 1)
    pdf.set_font("Arial", size=10)
    
    if not anomalies.empty:
        pdf.cell(0, 10, f"Total detectado: {len(anomalies)}", 0, 1)
        for idx, row in anomalies.head(20).iterrows(): # Limita a 20 para não estourar o PDF
            pdf.cell(0, 10, f"- {row['timestamp']}: {row['count']} logs", 0, 1)
    else:
        pdf.cell(0, 10, "Nenhuma anomalia de volume detectada.", 0, 1)

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, "Padroes Raros:", 0, 1)
    pdf.set_font("Arial", size=10)

    if not rare_logs.empty:
        pdf.cell(0, 10, f"Total detectado: {len(rare_logs)}", 0, 1)
        for idx, row in rare_logs.head(10).iterrows():
            msg_preview = row.get('message', '')[:80] + "..."
            level = row.get('log_level', 'Unknown')
            pdf.cell(0, 10, f"- [{level}] {msg_preview}", 0, 1)
    else:
        pdf.cell(0, 10, "Nenhum padrao raro detectado.", 0, 1)

    # 4. Análise de IA (Erros Críticos)
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

    # fpdf2 retorna bytes diretamente via output()
    return bytes(pdf.output()), None