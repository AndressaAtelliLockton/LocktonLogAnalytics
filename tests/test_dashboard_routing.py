import unittest
from unittest.mock import MagicMock
import sys
import os
import importlib.util

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Mock de módulos que podem causar efeitos colaterais na importação do dashboard.py
if 'streamlit' not in sys.modules:
    sys.modules['streamlit'] = MagicMock()
if 'dashboard.caching' not in sys.modules:
    sys.modules['dashboard.caching'] = MagicMock()
if 'log_analyzer' not in sys.modules:
    sys.modules['log_analyzer'] = MagicMock()

# Carrega o dashboard.py como um módulo para testar a função isolada
# Usamos importlib para evitar conflitos se existir uma pasta chamada 'dashboard'
spec = importlib.util.spec_from_file_location("dashboard_script", "dashboard.py")
dashboard = importlib.util.module_from_spec(spec)
sys.modules["dashboard_script"] = dashboard
spec.loader.exec_module(dashboard)

class TestDashboardRouting(unittest.TestCase):

    def setUp(self):
        # Configuração simulada igual à do dashboard.py
        self.page_options = [
            "Visão Executiva", 
            "Investigação Detalhada",
            "Inteligência & Previsão",
            "Métricas Customizadas"
        ]
        self.page_slugs = {
            "Visão Executiva": "home",
            "Investigação Detalhada": "investigation",
            "Inteligência & Previsão": "intelligence",
            "Métricas Customizadas": "custom-metrics"
        }

    def test_resolve_valid_slug(self):
        """Testa se um slug válido (ex: ?page=investigation) retorna o índice correto."""
        query_params = {"page": "investigation"}
        index = dashboard.resolve_page_index(query_params, self.page_slugs, self.page_options)
        self.assertEqual(index, 1, "Deveria retornar índice 1 para 'Investigação Detalhada'")

    def test_resolve_default_empty(self):
        """Testa se a falta de slug retorna o índice 0 (Padrão)."""
        query_params = {}
        index = dashboard.resolve_page_index(query_params, self.page_slugs, self.page_options)
        self.assertEqual(index, 0, "Deveria retornar índice 0 quando não há parâmetros")

    def test_resolve_invalid_slug(self):
        """Testa se um slug desconhecido retorna o índice 0 (Fallback)."""
        query_params = {"page": "pagina-inexistente-404"}
        index = dashboard.resolve_page_index(query_params, self.page_slugs, self.page_options)
        self.assertEqual(index, 0, "Deveria retornar índice 0 para slug inválido")

if __name__ == '__main__':
    unittest.main()