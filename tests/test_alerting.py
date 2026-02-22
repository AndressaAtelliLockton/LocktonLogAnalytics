import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Adiciona o diretório raiz ao path para garantir que imports funcionem
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock do Streamlit
if 'streamlit' not in sys.modules:
    sys.modules['streamlit'] = MagicMock()

from log_analyzer_module import send_webhook_alert

class TestAlerting(unittest.TestCase):

    @patch('requests.post')
    def test_send_teams_alert_success(self, mock_post):
        """Testa o envio bem-sucedido de um alerta para o Microsoft Teams."""
        # Configura o mock para simular uma resposta de sucesso do servidor
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "1" # Resposta padrão do Teams em sucesso
        mock_post.return_value = mock_response

        webhook_url = "https://my-tenant.webhook.office.com/webhookb2/..."
        message = "Este é um log de teste."
        title = "Alerta de Teste"

        # Chama a função
        response = send_webhook_alert(webhook_url, message, title)

        # Verificações
        self.assertEqual(response, mock_response)
        mock_post.assert_called_once()
        
        # Verifica a URL e o payload da chamada
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], webhook_url)
        
        sent_payload = kwargs['json']
        # VERIFICAÇÃO ATUALIZADA: O código agora envia MessageCard para URLs do Teams
        self.assertEqual(sent_payload.get("@type"), "MessageCard", "O payload deveria ser MessageCard.")
        self.assertIn("sections", sent_payload)
        self.assertEqual(sent_payload["sections"][0]["text"], message)

    @patch('requests.post')
    def test_send_teams_alert_http_error(self, mock_post):
        """Testa o tratamento de um erro HTTP (e.g., 404 Not Found) ao enviar alerta."""
        # Configura o mock para simular um erro do servidor
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Webhook not found"
        mock_post.return_value = mock_response

        webhook_url = "https://my-tenant.webhook.office.com/invalid"
        
        # Chama a função
        response = send_webhook_alert(webhook_url, "test message", "Error Test")

        # Verificações
        self.assertEqual(response, mock_response)
        
        # Verifica se a chamada foi feita (sem validar o JSON exato no assert_called_once_with para flexibilidade)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs['json']['@type'], 'MessageCard')

    @patch('requests.post')
    def test_send_alert_request_exception(self, mock_post):
        """Testa o tratamento de uma exceção de rede (e.g., Timeout)."""
        # Configura o mock para levantar uma exceção
        from requests.exceptions import Timeout
        mock_post.side_effect = Timeout("Connection timed out")

        webhook_url = "https://my-tenant.webhook.office.com/timeout"
        
        # Chama a função
        result = send_webhook_alert(webhook_url, "test message", "Exception Test")

        # Verificações
        self.assertIsInstance(result, str)
        self.assertIn("Falha no envio: Connection timed out", result)

if __name__ == '__main__':
    unittest.main()
