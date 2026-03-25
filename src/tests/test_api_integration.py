import unittest
from unittest.mock import patch
import os
import sys
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from io import BytesIO, StringIO

# Adiciona o diretório src ao path para que o app possa ser importado
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importa o app e a função de dependência que carrega a configuração.
from app import app, get_config

# --- Fixtures do Pytest ---

@pytest.fixture(scope="session")
def test_app_client():
    """
    Cria uma instância do TestClient com a dependência de configuração sobrescrita.
    Esta fixture é criada apenas uma vez para toda a sessão de testes.
    """
    # Sobrescreve a dependência `get_config` para usar nossa função de override.
    # Agora, qualquer endpoint que dependa de `get_config` receberá a configuração falsa.
    app.dependency_overrides[get_config] = get_override_config
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear() # Limpa o override após os testes

def get_override_config():
    """Fornece uma configuração falsa para os testes, isolando-os do disco."""
    return {
        "categories": [
            {"name": "Acesso", "keywords": ["GET /api/users"]},
            {"name": "Segurança", "keywords": ["Unauthorized", "login"]},
            {"name": "Performance", "keywords": ["duration", "took", "query took"]},
            {"name": "Aplicação", "keywords": ["database", "Error", "Critical"]}
        ]
    }

# --- Dados de Teste ---
SAMPLE_CSV_CONTENT = """2024-01-01 10:00:00,service-a,"GET /api/users 200 OK duration=50ms"
2024-01-01 10:01:00,service-b,"Error: POST /api/login 401 Unauthorized"
2024-01-01 10:02:00,service-a,"DB query took 150ms"
2024-01-01 10:03:00,service-c,"Critical: database connection timeout detected"
"""

@pytest.fixture(scope="session")
def client_with_data(test_app_client):
    """
    Fornece um TestClient com dados pré-carregados do SAMPLE_CSV_CONTENT.
    Depende da fixture test_app_client.
    """
    csv_file = BytesIO(SAMPLE_CSV_CONTENT.encode('utf-8'))
    response = test_app_client.post("/api/upload-csv", files={'file': ('test.csv', csv_file, 'text/csv')})
    assert response.status_code == 200, f"Fixture setup failed: Could not load test CSV data. Status: {response.status_code}, Detail: {response.text}"
    yield test_app_client

# --- Testes dos Endpoints ---

def test_read_root(test_app_client):
    """Testa se a rota principal (/) retorna a página HTML."""
    response = test_app_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers['content-type']
    assert "<title>Lockton Log Analytics</title>" in response.text

def test_health_check(test_app_client):
    """Testa o endpoint de health check."""
    response = test_app_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_get_data_summary(client_with_data):
    """Testa se o resumo de dados reflete os dados carregados."""
    response = client_with_data.get("/api/data/summary")
    assert response.status_code == 200
    data = response.json()
    assert data['total_logs'] == 4
    assert data['error_count'] == 2  # Error + Critical
    assert data['unique_sources'] == 3

def test_get_logs_with_filter(client_with_data):
    """Testa a filtragem de logs na página de investigação."""
    # Filtra por nível 'Error'
    response = client_with_data.get("/api/data/logs?level=Error")
    assert response.status_code == 200
    data = response.json()
    assert len(data['data']) == 1
    assert data['data'][0]['source'] == 'service-b'

    # Filtra por texto na mensagem
    response = client_with_data.get("/api/data/logs?search=database")
    assert response.status_code == 200
    data = response.json()
    assert len(data['data']) == 1
    assert data['data'][0]['source'] == 'service-c'

@patch('log_analyzer.send_chat_message')
def test_run_ai_analysis(mock_send_chat, client_with_data):
    """Testa o endpoint de análise de IA, mockando a chamada externa."""
    mock_send_chat.return_value = "Esta é uma análise de IA simulada."
    
    response = client_with_data.post("/api/analysis/ai")
    assert response.status_code == 200
    data = response.json()
    
    # Deve analisar os 2 logs de erro do nosso CSV de teste
    assert len(data['analysis']) == 2
    assert data['analysis'][0]['analysis'] == "Esta é uma análise de IA simulada."
    mock_send_chat.assert_called()

@patch('log_analyzer.fetch_logs_from_graylog')
def test_load_from_graylog(mock_fetch_graylog, test_app_client):
    """Testa o carregamento de dados do Graylog, mockando a API do Graylog."""
    mock_df = pd.read_csv(StringIO(SAMPLE_CSV_CONTENT), header=None, names=['timestamp', 'source', 'message'])
    mock_fetch_graylog.return_value = (mock_df, None)
    
    # Seta as variáveis de ambiente necessárias para o endpoint
    os.environ["GRAYLOG_API_URL"] = "http://fake-graylog"
    os.environ["GRAYLOG_USER"] = "fake-user"
    os.environ["GRAYLOG_PASSWORD"] = "token"
    
    response = test_app_client.post("/api/load-graylog")
    assert response.status_code == 200
    assert response.json()['records'] == 4

    # Limpa as variáveis de ambiente
    del os.environ["GRAYLOG_API_URL"]
    del os.environ["GRAYLOG_USER"]
    del os.environ["GRAYLOG_PASSWORD"]

def test_get_api_metrics(client_with_data):
    """Testa a extração de métricas de API."""
    response = client_with_data.get("/api/analysis/api-metrics")
    assert response.status_code == 200
    data = response.json()
    
    assert data['stats']['total'] == 3
    assert data['stats']['success'] == 1
    assert data['stats']['client_error'] == 1
    assert data['stats']['avg_latency'] == 100.0

@patch('log_analyzer.toggle_graylog_alert_schedule')
def test_toggle_alert_schedule(mock_toggle, test_app_client):
    """Testa a ativação/desativação de um alerta."""
    mock_toggle.return_value = ({}, None)

    # Seta as variáveis de ambiente necessárias para o endpoint
    os.environ["GRAYLOG_API_URL"] = "http://fake-graylog"
    os.environ["GRAYLOG_USER"] = "fake-user"
    os.environ["GRAYLOG_PASSWORD"] = "token"
    
    # Testa ativação (PUT)
    response_put = test_app_client.put("/api/alerts/definitions/alert123/schedule")
    assert response_put.status_code == 200
    assert response_put.json()['message'] == "Alerta alert123 ativado."
    mock_toggle.assert_called_with(unittest.mock.ANY, unittest.mock.ANY, unittest.mock.ANY, 'alert123', enable=True)

    # Testa desativação (DELETE)
    response_del = test_app_client.delete("/api/alerts/definitions/alert123/schedule")
    assert response_del.status_code == 200
    assert response_del.json()['message'] == "Alerta alert123 desativado."
    mock_toggle.assert_called_with(unittest.mock.ANY, unittest.mock.ANY, unittest.mock.ANY, 'alert123', enable=False)

    # Limpa as variáveis de ambiente
    del os.environ["GRAYLOG_API_URL"]
    del os.environ["GRAYLOG_USER"]
    del os.environ["GRAYLOG_PASSWORD"]