import os
import sys

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from log_analyzer import send_webhook_alert

def main():
    print("--- 📨 Teste Manual de Envio para Teams ---")
    
    url = os.environ.get("TEAMS_WEBHOOK_URL")
    if not url:
        print("⚠️  Variável TEAMS_WEBHOOK_URL não encontrada.")
        url = input("👉 Cole a URL do Webhook do Teams aqui: ").strip()
    
    if url:
        print(f"\nEnviando mensagem de teste para: {url[:30]}...")
        response = send_webhook_alert(url, "Esta é uma mensagem de teste real enviada via script manual.\n\nSe você está lendo isso, o formato MessageCard está funcionando! ✅", title="🔔 Teste Manual de Conectividade")
        
        if hasattr(response, 'status_code'):
            print(f"✅ Resultado: {response.status_code} {response.reason}")
            if response.status_code == 200:
                print("🚀 Sucesso! Verifique o canal do Teams.")
            else:
                print(f"❌ Erro: {response.text}")
        else:
            print(f"❌ Falha: {response}")
    else:
        print("Operação cancelada.")

if __name__ == "__main__":
    main()