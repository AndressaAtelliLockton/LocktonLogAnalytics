import unittest
import pandas as pd
import time
import sys
import os
from unittest.mock import MagicMock

# Adiciona o diretório raiz ao path para garantir que imports funcionem
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Mock do Streamlit deve ser feito ANTES de importar os módulos do dashboard
# Isso é necessário para interceptar o decorador @st.cache_data e evitar erros de runtime
if 'streamlit' not in sys.modules:
    mock_st = MagicMock()
    def no_cache(func):
        return func
    mock_st.cache_data = no_cache
    sys.modules['streamlit'] = mock_st

# Garante que dashboard.caching seja recarregado para usar o mock acima
# e não um mock global deixado por outros testes (ex: test_dashboard_routing)
if 'dashboard.caching' in sys.modules:
    del sys.modules['dashboard.caching']

# Importa a função a ser testada
from dashboard.caching import cached_prepare_explorer_data

class TestPerformance(unittest.TestCase):

    def test_prepare_explorer_data_speed(self):
        """
        Teste de performance para cached_prepare_explorer_data.
        Verifica se a ordenação e criação de IDs é rápida o suficiente para 50k linhas.
        """
        # Cria um DataFrame grande (50.000 linhas)
        rows = 50000
        df = pd.DataFrame({
            'timestamp': pd.date_range(start='2023-01-01', periods=rows, freq='s'),
            'source': ['source-test'] * rows,
            'message': ['Error: connection timeout in database'] * rows,
            'log_level': ['Error'] * rows
        })
        
        # Mede o tempo de execução
        start_time = time.time()
        result = cached_prepare_explorer_data(df)
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"\n[Performance] cached_prepare_explorer_data com {rows} linhas: {duration:.4f}s")
        
        # Assertivas
        self.assertEqual(len(result), rows)
        self.assertIn('log_id', result.columns)
        self.assertIn('priority', result.columns)
        
        # Limite aceitável: 4.0 segundos (Ajustado para ambientes de CI/CD mais lentos)
        self.assertLess(duration, 4.0, f"A função está muito lenta! Levou {duration:.4f}s para {rows} linhas.")

if __name__ == '__main__':
    unittest.main()