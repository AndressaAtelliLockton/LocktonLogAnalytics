import time
from locust import HttpUser, task, between, events
import websocket

class StreamlitProxyUser(HttpUser):
    # Aguarda entre 1 e 3 segundos entre as tarefas (simula tempo de leitura do usuário)
    wait_time = between(1, 3)

    @task(3)
    def load_homepage(self):
        """Testa o carregamento da página principal (Proxy HTTP)"""
        self.client.get("/")

    @task(1)
    def check_health(self):
        """Testa o endpoint de healthcheck"""
        self.client.get("/health")

    @task(1)
    def test_websocket_handshake(self):
        """Testa a conexão WebSocket (Proxy WS)"""
        start_time = time.time()
        try:
            # Constrói a URL do WebSocket baseada no host configurado no Locust
            scheme = "wss" if self.host.startswith("https") else "ws"
            # Remove protocolo http/https para montar a url ws/wss
            host_clean = self.host.split("://")[-1].rstrip('/')
            ws_url = f"{scheme}://{host_clean}/_stcore/stream"

            # Tenta estabelecer conexão (Handshake)
            # Se o proxy FastAPI estiver funcionando, a conexão deve abrir e fechar sem erro
            ws = websocket.create_connection(ws_url, timeout=5)
            ws.close()
            
            # Reporta sucesso ao Locust
            events.request.fire(
                request_type="WEBSOCKET",
                name="Handshake",
                response_time=int((time.time() - start_time) * 1000),
                response_length=0,
            )
        except Exception as e:
            # Reporta falha ao Locust
            events.request.fire(
                request_type="WEBSOCKET",
                name="Handshake",
                response_time=int((time.time() - start_time) * 1000),
                response_length=0,
                exception=e,
            )