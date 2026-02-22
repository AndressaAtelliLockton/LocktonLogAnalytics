import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import sys
import os

# --- MOCK STREAMLIT GLOBALLY ---
if 'streamlit' not in sys.modules:
    sys.modules['streamlit'] = MagicMock()

# Adiciona o diretório raiz ao path para importar o pacote log_analyzer
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# CORREÇÃO: Importar do log_analyzer_module, onde a função está definida
from log_analyzer_module import generate_pdf_report

class TestReporting(unittest.TestCase):

    def test_generate_pdf_report_success(self):
        """
        Testa a geração de PDF simulando que as dependências (fpdf, vl_convert) estão instaladas.
        Verifica se o fluxo constrói o PDF e processa os gráficos corretamente.
        """
        
        # Mocks para as bibliotecas externas
        mock_fpdf_module = MagicMock()
        mock_vlc_module = MagicMock()
        
        # Configura o comportamento da classe FPDF
        # Mock da instância do PDF para verificar chamadas de métodos (add_page, cell, etc.)
        mock_pdf_instance = MagicMock()
        
        # Classe Mock para substituir FPDF e suportar herança corretamente
        class MockFPDF:
            def __init__(self, *args, **kwargs): pass
            def add_page(self, *args, **kwargs): 
                mock_pdf_instance.add_page(*args, **kwargs)
                # Simula comportamento do FPDF chamando header
                if hasattr(self, 'header'):
                    self.header()
            def set_font(self, *args, **kwargs): mock_pdf_instance.set_font(*args, **kwargs)
            def cell(self, *args, **kwargs): mock_pdf_instance.cell(*args, **kwargs)
            def ln(self, *args, **kwargs): mock_pdf_instance.ln(*args, **kwargs)
            def multi_cell(self, *args, **kwargs): mock_pdf_instance.multi_cell(*args, **kwargs)
            def image(self, *args, **kwargs): mock_pdf_instance.image(*args, **kwargs)
            def page_no(self): return 1
            def set_y(self, *args, **kwargs): mock_pdf_instance.set_y(*args, **kwargs)
            # Simula output retornando bytes (comportamento esperado do fpdf2)
            def output(self, *args, **kwargs): return b"PDF_BINARY_DATA_SIMULATED"

        # Substitui a classe FPDF pelo nosso Mock
        mock_fpdf_module.FPDF = MockFPDF
        
        # Simula a conversão de gráfico do vl-convert (retorna bytes de imagem)
        mock_vlc_module.vegalite_to_png.return_value = b"FAKE_PNG_IMAGE"

        # Patching sys.modules para injetar os mocks quando a função tentar importar
        # Patching os.path.exists para garantir que o teste do logo funcione
        with patch.dict(sys.modules, {'fpdf': mock_fpdf_module, 'vl_convert': mock_vlc_module}), \
             patch('os.path.exists') as mock_exists:
            
            # Configura para simular que o logo existe
            mock_exists.return_value = True

            # --- Dados de Teste ---
            df = pd.DataFrame({'log_level': ['Error', 'Info', 'Warning'], 'message': ['Err1', 'Info1', 'Warn1']})
            anomalies = pd.DataFrame({'timestamp': ['2023-01-01 10:00'], 'count': [50]})
            rare_logs = pd.DataFrame({'log_level': ['Error'], 'message': ['Rare Error Pattern']})
            
            # Mock de um gráfico Altair (precisa ter o método to_json)
            mock_chart = MagicMock()
            mock_chart.to_json.return_value = '{"vega": "lite"}'
            charts_dict = {"Volume Chart": mock_chart}

            # --- Execução ---
            pdf_bytes, error = generate_pdf_report(df, anomalies, rare_logs, charts_dict, ai_analyses=[])

            # --- Verificações ---
            self.assertIsNone(error, f"A função retornou erro: {error}")
            self.assertIsNotNone(pdf_bytes)
            self.assertEqual(pdf_bytes, b"PDF_BINARY_DATA_SIMULATED")
            
            # Verifica chamadas essenciais no PDF
            mock_pdf_instance.add_page.assert_called()
            mock_pdf_instance.cell.assert_called()
            
            # Verifica se a imagem (logo) foi adicionada (pois mock_exists=True)
            # O código do header chama self.image("lockton_logo.png", ...)
            mock_pdf_instance.image.assert_called()
            
            # Verifica se tentou converter o gráfico
            mock_vlc_module.vegalite_to_png.assert_called_with('{"vega": "lite"}')

if __name__ == '__main__':
    unittest.main()