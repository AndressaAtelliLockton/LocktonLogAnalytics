import unittest
import requests
import sys
import os
import time

class TestStreamlitHealth(unittest.TestCase):

    def setUp(self):
        # URL do servidor de Staging ou Local
        target_url_env = os.environ.get("TARGET_URL")
        
        if target_url_env:
            self.base_url = target_url_env
            print(f"\n[TestStreamlitHealth] Verificando conectividade com: {self.base_url}")
            try:
                requests.get(f"{self.base_url}/health", timeout=3)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                self.skipTest(f"⚠️ Servidor offline ou inacessível em {self.base_url}. Pulando testes de conectividade.")
        else:
             # Auto-discovery
            potential_ports = [80, 8000, 8080, 8501, 8502]
            found = False
            
            # Tenta encontrar o servidor por até 30 segundos
            for _ in range(30):
                for port in potential_ports:
                    url = f"http://localhost:{port}"
                    try:
                        requests.get(f"{url}/health", timeout=1)
                        self.base_url = url
                        print(f"\n[TestStreamlitHealth] Servidor encontrado em: {self.base_url}")
                        found = True
                        break
                    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                        pass
                if found:
                    break
                time.sleep(1)
            
            if not found:
                self.skipTest("⚠️ Servidor offline. Nenhuma porta padrão (80, 8000, 8080, 8501, 8502) respondeu em localhost.")

    def test_streamlit_status(self):
        """Verifica se o servidor Streamlit está acessível e retornando 200 OK."""
        url = f"{self.base_url}/"
        print(f"\nVerificando status do Streamlit em: {url}")
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print("✅ Streamlit está ONLINE e respondendo (200 OK).")
            else:
                self.fail(f"❌ Streamlit respondeu com erro: {response.status_code}")
        except requests.exceptions.ConnectionError as e:
            if "10061" in str(e) or "Connection refused" in str(e):
                self.fail(f"❌ CONEXÃO RECUSADA em {url}.\n"
                          f"   DIAGNÓSTICO: O container está rodando, mas a porta interna mudou.\n"
                          f"   SOLUÇÃO: Verifique se o container está rodando na porta 80 ou defina TARGET_URL.")
            else:
                self.fail(f"❌ Falha de conexão com {url}. O serviço pode estar offline ou bloqueado por firewall.")
        except Exception as e:
            self.fail(f"❌ Erro inesperado: {e}")

    def test_streamlit_health_endpoint(self):
        """Verifica se o endpoint de saúde do sistema (/health) está retornando 'ok'."""
        url = f"{self.base_url}/health"
        print(f"\nVerificando endpoint de saúde: {url}")
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200 and "ok" in response.text.lower():
                print("✅ Endpoint /health retornou 'ok'.")
            else:
                self.fail(f"❌ Endpoint de saúde falhou. Status: {response.status_code}, Resposta: {response.text}")
        except requests.exceptions.ConnectionError as e:
            if "10061" in str(e) or "Connection refused" in str(e):
                self.fail(f"❌ CONEXÃO RECUSADA no Healthcheck.\n"
                          f"   SOLUÇÃO: Verifique se o container está rodando na porta 80 ou defina TARGET_URL.")
            else:
                self.fail(f"❌ Falha de conexão com {url}.")
        except Exception as e:
            self.fail(f"❌ Erro ao acessar {url}: {e}")

if __name__ == '__main__':
    unittest.main()