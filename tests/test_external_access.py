import unittest
import requests
import os
import time

class TestExternalAccess(unittest.TestCase):
    
    def setUp(self):
        # URL externa padrão. Se TARGET_URL não for definida, tenta descobrir.
        target_url_env = os.environ.get("TARGET_URL")
        
        if target_url_env:
            self.base_url = target_url_env
            print(f"\n[TestExternalAccess] Verificando conectividade com: {self.base_url}")
            try:
                requests.get(f"{self.base_url}/health", timeout=3)
            except requests.exceptions.ConnectionError:
                self.skipTest(f"⚠️ Servidor offline em {self.base_url}. Pulando testes de integração externa.")
        else:
            # Auto-discovery de portas comuns
            potential_ports = [80, 8000, 8080, 8501, 8502]
            found = False
            
            # Tenta encontrar o servidor por até 30 segundos (aguarda startup do container)
            for _ in range(30):
                for port in potential_ports:
                    url = f"http://localhost:{port}"
                    try:
                        requests.get(f"{url}/health", timeout=1)
                        self.base_url = url
                        print(f"\n[TestExternalAccess] Servidor encontrado em: {self.base_url}")
                        found = True
                        break
                    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                        pass
                if found:
                    break
                time.sleep(1)
            
            if not found:
                self.skipTest("⚠️ Servidor offline. Nenhuma porta padrão (80, 8000, 8080, 8501, 8502) respondeu em localhost.")

    def test_healthcheck_endpoint(self):
        """Verifica se o endpoint de healthcheck (/health) está respondendo 200 OK."""
        url = f"{self.base_url}/health"
        try:
            response = requests.get(url, timeout=10)
            self.assertEqual(response.status_code, 200, f"Healthcheck falhou. Status: {response.status_code}")
            self.assertIn("ok", response.text.lower(), f"Conteúdo inesperado no healthcheck: {response.text}")
            print("✅ Healthcheck OK")
        except requests.exceptions.ConnectionError:
            self.fail(f"❌ Falha de conexão: Não foi possível alcançar {url}")
        except requests.exceptions.Timeout:
            self.fail(f"❌ Timeout: O servidor demorou muito para responder em {url}")

    def test_main_dashboard_load(self):
        """Verifica se a página principal do Dashboard carrega corretamente."""
        try:
            response = requests.get(self.base_url, timeout=10)
            self.assertEqual(response.status_code, 200, f"Dashboard inacessível. Status: {response.status_code}")
            self.assertIn("text/html", response.headers.get("Content-Type", ""), "O retorno não é HTML válido.")
            print("✅ Dashboard Load OK")
        except Exception as e:
            self.fail(f"❌ Erro ao acessar Dashboard: {e}")

    def test_env_status_endpoint(self):
        """Verifica se a rota de diagnóstico /env-status retorna o JSON esperado."""
        url = f"{self.base_url}/env-status"
        print(f"\nVerificando rota de diagnóstico: {url}")
        try:
            response = requests.get(url, timeout=10)
            self.assertEqual(response.status_code, 200, f"Rota /env-status falhou. Status: {response.status_code}")
            
            data = response.json()
            self.assertIn("status", data, "JSON de resposta não contém a chave 'status'")
            self.assertIn("details", data, "JSON de resposta não contém a chave 'details'")
            self.assertIn("graylog_connectivity", data, "JSON de resposta não contém a chave 'graylog_connectivity'")
            self.assertIn("influxdb_connectivity", data, "JSON de resposta não contém a chave 'influxdb_connectivity'")
            self.assertIn("background_services", data, "JSON de resposta não contém a chave 'background_services'")
            
            print(f"✅ Env Status OK (Status: {data['status']})")
        except Exception as e:
            self.fail(f"❌ Erro ao acessar ou validar {url}: {e}")

    def test_url_redirects(self):
        """Verifica se as URLs amigáveis (/executive, /investigation) redirecionam corretamente."""
        redirects = {
            "/executive": "/?page=executive",
            "/investigation": "/?page=investigation",
            "/intelligence": "/?page=intelligence",
            "/custom-metrics": "/?page=custom-metrics",
            "/rum": "/?page=rum",
            "/infrastructure": "/?page=infrastructure",
            "/api-monitoring": "/?page=api-monitoring",
            "/tools": "/?page=tools"
        }
        
        for path, expected_query in redirects.items():
            url = f"{self.base_url}{path}"
            try:
                response = requests.get(url, allow_redirects=False, timeout=5)
                self.assertEqual(response.status_code, 307, f"Rota {path} não redirecionou (Status: {response.status_code})")
                self.assertTrue(response.headers['location'].endswith(expected_query), f"Rota {path} redirecionou para local incorreto: {response.headers['location']}")
                print(f"✅ Redirecionamento {path} -> {expected_query} OK")
            except Exception as e:
                self.fail(f"❌ Erro ao testar redirecionamento {path}: {e}")

if __name__ == '__main__':
    unittest.main()