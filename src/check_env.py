import os
import sys

# Tenta carregar variáveis de ambiente de um arquivo .env (Desenvolvimento Local)
try:
    from dotenv import load_dotenv
    load_dotenv()
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False

# Lista de variáveis críticas para o funcionamento do sistema
CRITICAL_VARS = [
    "GROQ_API_KEY",
    "JIRA_WEBHOOK_URL",
    "JIRA_API_KEY",
    "GRAYLOG_API_URL",
    "GRAYLOG_USER",
    "GRAYLOG_PASSWORD",
    "TEAMS_WEBHOOK_URL",
    "DASHBOARD_URL",
    "WATCHDOG_SOURCES", # Fontes para o Watchdog IA monitorar, separadas por vírgula. Ex: "servidor1,servidor2"
    "INFLUXDB_URL",
    "DOCKER_INFLUXDB_INIT_ADMIN_TOKEN",
    "DOCKER_INFLUXDB_INIT_ORG",
    "DOCKER_INFLUXDB_INIT_BUCKET"
]

def main():
    print("--- 🔍 Diagnóstico de Variáveis de Ambiente ---")
    
    if os.path.exists(".env"):
        print("✅ Arquivo .env detectado.")
        if not HAS_DOTENV:
            print("⚠️  Biblioteca 'python-dotenv' não instalada. O arquivo .env não será lido automaticamente.")
            print("   Execute: pip install python-dotenv")
    else:
        print("ℹ️  Arquivo .env não encontrado. Assumindo execução via Pipeline CI/CD ou Docker (Variáveis de Sistema).")

    missing_count = 0
    
    for var in CRITICAL_VARS:
        value = os.environ.get(var)
        if not value:
            print(f"❌ {var}: AUSENTE")
            missing_count += 1
        else:
            # Limpeza básica de aspas que podem vir do .env se não for parseado corretamente
            clean_val = value.strip('"').strip("'")
            # Mascara o valor para segurança (exibe apenas início e fim)
            masked = f"{clean_val[:4]}...{clean_val[-2:]}" if len(clean_val) > 6 else "******"
            print(f"✅ {var}: Carregada ({masked})")
            
    # Checagens opcionais ou com valor default
    influx = os.environ.get("INFLUXDB_URL", "Usa Default (http://influxdb-staging:8086)")
    print(f"ℹ️  INFLUXDB_URL: {influx}")

    print("-" * 40)
    if missing_count > 0:
        print(f"⚠️  ATENÇÃO: {missing_count} variáveis críticas não foram detectadas.")
        print("   Verifique o arquivo .env ou as configurações do Docker/Pipeline.")
    else:
        print("🚀 Todas as variáveis críticas estão presentes.")

if __name__ == "__main__":
    main()