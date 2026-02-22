import requests
import time
import sys
import os

# Tenta importar o módulo do sistema para acessar configurações salvas (DB)
try:
    import log_analyzer as lam
except ImportError:
    try:
        import log_analyzer_module as lam
    except ImportError:
        lam = None

def send_teams_alert(webhook_url, title, message):
    """Envia alerta para o Teams em caso de falha."""
    if not webhook_url:
        return

    # Formato MessageCard (Padrão para Connectors do Teams)
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "d9534f",
        "summary": title,
        "sections": [{"activityTitle": title, "text": message, "markdown": True}]
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 200:
            print("🚨 Alerta enviado para o Teams com sucesso.")
        else:
            print(f"⚠️ Falha ao enviar alerta para o Teams: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Erro ao enviar alerta para o Teams: {e}")

def check_url(url, max_retries=12, delay=5):
    """
    Verifica se a URL está acessível.
    Tenta max_retries vezes com intervalo de delay segundos.
    Total de espera padrão: 60 segundos.
    """
    print(f"--- Verificando disponibilidade: {url} ---")
    
    for i in range(max_retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ [SUCESSO] Serviço online! (Status: 200 OK)")
                return True
            else:
                print(f"⚠️ [Tentativa {i+1}/{max_retries}] Status Code: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"⏳ [Tentativa {i+1}/{max_retries}] Conexão recusada (Serviço indisponível ou iniciando)...")
        except Exception as e:
            print(f"❌ [Tentativa {i+1}/{max_retries}] Erro: {e}")
        
        if i < max_retries - 1:
            time.sleep(delay)

    print("❌ [FALHA] O serviço não respondeu corretamente após várias tentativas.")
    return False

if __name__ == "__main__":
    # Define a URL base (padrão Staging ou via ENV ou Auto-discovery)
    target_url_env = os.environ.get("TARGET_URL")
    
    if target_url_env:
        base_url = target_url_env.rstrip('/')
    else:
        # Auto-discovery
        potential_ports = [80, 8000, 8080, 8501, 8502]
        base_url = "http://localhost:80" # Default fallback
        
        for port in potential_ports:
            url = f"http://localhost:{port}"
            try:
                requests.get(f"{url}/health", timeout=1)
                base_url = url
                print(f"ℹ️ Servidor detectado automaticamente em: {base_url}")
                break
            except:
                pass
    
    # Endpoint de Healthcheck do FastAPI/Streamlit
    target_url = f"{base_url}/health"
    
    success = check_url(target_url)
    
    if success:
        sys.exit(0)
    else:
        # Tenta obter URL do Teams: 1. Env Var, 2. Configuração do Sistema (DB)
        webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")
        
        if not webhook_url and lam:
            try:
                # Tenta buscar do banco de dados local (mesma config do Scheduler/Dashboard)
                webhook_url = lam.get_setting("webhook_url")
                if webhook_url:
                    print(f"ℹ️ Usando Webhook do Teams configurado no sistema.")
            except Exception as e:
                print(f"⚠️ Erro ao ler configuração do sistema: {e}")

        if webhook_url:
            send_teams_alert(webhook_url, "❌ Falha no Deploy (Healthcheck)", f"O serviço em **{target_url}** não respondeu após várias tentativas.\n\nVerifique os logs do container ou o status do Docker Swarm.")
        sys.exit(1)