import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
import sys
import os
from prometheus_client import CONTENT_TYPE_LATEST

# Adiciona o diretório raiz ao path para garantir que imports funcionem
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import app

class TestMetricsEndpoint(unittest.TestCase):

    @patch('app.start_system_services', new_callable=AsyncMock)
    def test_metrics_content_type(self, mock_startup):
        """
        Verifica se o endpoint /metrics retorna o Content-Type correto para o Prometheus.
        """
        # Usa TestClient como context manager para garantir que eventos de startup (mockados) rodem
        # O mock_startup impede que o app tente iniciar Streamlit/Scheduler e espere 30s
        with TestClient(app) as client:
            response = client.get("/metrics")
            
            self.assertEqual(response.status_code, 200, "O endpoint /metrics deveria retornar status 200")
            
            # Verifica se o Content-Type é exatamente o que o Prometheus espera
            # Geralmente: text/plain; version=0.0.4; charset=utf-8
            self.assertEqual(
                response.headers["content-type"], 
                CONTENT_TYPE_LATEST, 
                f"Content-Type incorreto. Esperado: {CONTENT_TYPE_LATEST}, Recebido: {response.headers['content-type']}"
            )
            
            # Verifica se as métricas definidas no app.py estão presentes
            self.assertIn("http_requests_total", response.text)
            self.assertIn("http_request_duration_seconds", response.text)

if __name__ == '__main__':
    unittest.main()