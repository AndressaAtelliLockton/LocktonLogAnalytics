#!/bin/bash

# Garante que o script pare se houver erro
set -e

echo "=========================================="
echo "   INICIANDO AGENTE DE IA (LINUX/DOCKER)"
echo "=========================================="

# Garante que estamos no diretório do script
cd "$(dirname "$0")"

# Define o problema padrão se não for passado argumento via linha de comando
# Se estiver rodando na pipeline, você pode passar o erro como argumento
ISSUE="${1:-Ao rodar a pipeline no servidor ele dá acesso negado, mas a porta externa está aberta}"

echo "📝 Executando análise para: $ISSUE"

# Executa o Python (assume que o python está no PATH do container/pipeline)
python3 iac_agent.py "$ISSUE"