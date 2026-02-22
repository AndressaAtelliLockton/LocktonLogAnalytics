import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
import sys
import os

# Adiciona o diretório raiz ao path para garantir que imports funcionem
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Mock subprocess.Popen para evitar iniciar serviços reais (Streamlit, Scheduler) durante a importação/startup do app
with patch('subprocess.Popen'):
    from app import app

class TestMiddlewareLogging(unittest.TestCase):
    
    # Removemos o setUp com self.client fixo para usar context manager nos testes
    pass

    @patch('app.start_system_services', new_callable=AsyncMock)
    @patch('builtins.print')
    def test_log_format(self, mock_startup, mock_print):
        """
        Verifica se o middleware loga a requisição no formato correto:
        🔍 GET /path - status (time ms)
        """
        # Usa TestClient como context manager para garantir ciclo de vida (startup/shutdown)
        with TestClient(app) as client:
            # Faz uma requisição para uma rota existente
            client.get("/env-status")
        
        # Verifica se o print foi chamado
        self.assertTrue(mock_print.called, "O middleware deveria ter chamado print()")
        
        # Procura pelo log específico da requisição
        found = False
        for call in mock_print.call_args_list:
            args, _ = call
            msg = str(args[0])
            # Verifica o prefixo e a estrutura
            if "🔍 GET /env-status - 200" in msg:
                found = True
                # Verifica se contém o tempo em ms (ex: (0.15ms))
                self.assertRegex(msg, r"🔍 GET /env-status - 200 \(\d+\.\d+ms\)")
                break
        
        self.assertTrue(found, "Log de requisição não encontrado ou formato incorreto.")

    @patch('app.start_system_services', new_callable=AsyncMock)
    @patch('builtins.print')
    def test_skip_healthcheck_log(self, mock_startup, mock_print):
        """
        Verifica se requisições para /health são ignoradas pelo logger para evitar spam.
        """
        with TestClient(app) as client:
            client.get("/health")
        
        # Verifica se NENHUM print contendo a rota foi feito
        for call in mock_print.call_args_list:
            args, _ = call
            msg = str(args[0])
            self.assertNotIn("/health", msg, "Healthcheck não deveria ser logado.")

if __name__ == '__main__':
    unittest.main()