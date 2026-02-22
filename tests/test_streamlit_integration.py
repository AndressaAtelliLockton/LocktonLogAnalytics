import unittest
from streamlit.testing.v1 import AppTest
import sys
import os

# Adiciona o diretório raiz ao path para garantir que imports funcionem
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

class TestStreamlitIntegration(unittest.TestCase):
    def setUp(self):
        self.script_path = "dashboard.py"

    def test_routing_investigation_tab(self):
        """
        Verifica se acessar ?page=investigation seleciona a aba correta.
        """
        # Inicializa o AppTest apontando para o dashboard.py
        at = AppTest.from_file(self.script_path)
        
        # Simula o parâmetro na URL antes de rodar o script
        at.query_params["page"] = "investigation"
        
        # Executa o app (simulação headless)
        at.run(timeout=10)
        
        # Verifica se não houve erro de execução (ex: import error, syntax error)
        self.assertFalse(at.exception, f"O app falhou com exceção: {at.exception}")
        
        # Verifica se o parâmetro foi mantido após a execução.
        # No dashboard.py, se o menu selecionar a opção correta, ele reafirma o query_param.
        # Se a lógica falhasse, o menu cairia no default (0) e mudaria o param para 'executive'.
        self.assertEqual(at.query_params["page"][0], "investigation")

    def test_routing_default_redirect(self):
        """
        Verifica se acessar a raiz (sem params) redireciona para a aba padrão (home).
        """
        at = AppTest.from_file(self.script_path)
        at.run(timeout=10)
        
        self.assertFalse(at.exception)
        
        # O comportamento esperado é que o dashboard defina page=executive para a aba padrão
        self.assertEqual(at.query_params["page"][0], "executive")

    def test_routing_invalid_slug(self):
        """
        Verifica se um slug inválido cai no fallback (executive).
        """
        at = AppTest.from_file(self.script_path)
        at.query_params["page"] = "slug-que-nao-existe"
        at.run(timeout=10)
        
        self.assertFalse(at.exception)
        
        # Deve reverter para a aba padrão (executive)
        self.assertEqual(at.query_params["page"][0], "executive ")

if __name__ == '__main__':
    unittest.main()