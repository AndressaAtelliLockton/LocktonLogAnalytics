#!/usr/bin/env bash

echo "--- Iniciando Entrypoint do Analytics ---"

if [ -f "check_env.py" ]; then
  python check_env.py
fi

if [ "$1" = "start-services" ]; then
  echo "🚀 Iniciando Stack Completa..."

  # 1. Scheduler
  echo "--- Scheduler ---"
  python scheduler.py &

  # 2. Log Collector
  echo "--- Log Collector ---"
  python log_collector.py &

  # REMOVIDO: bloco do Streamlit

  # 3. FastAPI/Uvicorn (processo principal)
  echo "--- FastAPI (80) ---"
  exec gunicorn -k uvicorn.workers.UvicornWorker -w 4 app:app --bind 0.0.0.0:80

else
  exec "$@"
fi


