#!/usr/bin/env bash

# Log de inicialização para o Bitbucket mostrar
echo "--- Iniciando Entrypoint do Analytics ---"

# Executa diagnóstico de variáveis de ambiente (Loga o status das chaves)
if [ -f "check_env.py" ]; then
    python check_env.py
fi

# Se o comando for "start-services" (padrão do Dockerfile), inicia a stack completa
if [ "$1" = "start-services" ]; then
    echo "🚀 Iniciando Stack de Serviços..."

    # 1. Inicia Scheduler (Watchdog) em background
    echo "--- Iniciando Scheduler ---"
    python scheduler.py &

    # 2. Inicia Log Collector em background
    echo "--- Iniciando Log Collector ---"
    python log_collector.py &

    # 3. Inicia FastAPI (Backend Interno na porta 8000)
    echo "--- Iniciando FastAPI (Internal :8000) ---"
    python -m uvicorn app:app --host 127.0.0.1 --port 8000 &

    # 4. Inicia Streamlit (Frontend Interno na porta 8502)
    echo "--- Iniciando Streamlit (Internal :8502) ---"
    streamlit run dashboard.py --server.port 8502 --server.headless true --server.address 127.0.0.1 --server.fileWatcherType none --client.showSidebarNavigation false --server.enableCORS false --server.enableXsrfProtection false &

    # 5. Inicia Nginx (Proxy Reverso na porta 80) - Processo Principal
    echo "--- Iniciando Nginx (Public :80) ---"
    exec nginx -g 'daemon off;'
else
    # Permite rodar outros comandos se necessário (ex: debug)
    exec "$@"
fi
exec "$@"
