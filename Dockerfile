# Usa uma imagem base leve do Python 3.10
FROM python:3.10

# Define variáveis de ambiente para evitar arquivos .pyc e logs de buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Placeholder para versão da aplicação (Substituído pela Pipeline)
ENV APP_VERSION=YYZ

# Informa ao app.py que o gerenciamento de processos é feito pelo Docker/Entrypoint
ENV ORCHESTRATOR=docker

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Instala dependências do sistema necessárias para compilação e curl para healthcheck
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    nginx \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Configuração de OpenSSL (Padrão Lockton - Extraído do modelo .NET)
# Garante que o container use os Ciphers de segurança exigidos pela infraestrutura
RUN printf "openssl_conf = default_conf\n\n[default_conf]\nssl_conf = ssl_sect\n\n[ssl_sect]\nsystem_default = system_default_sect\n\n[system_default_sect]\nCipherString = ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-SHA384:ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384:ECDHE-RSA-AES128-SHA256" > /etc/ssl/openssl.cnf

# Configuração do Nginx
COPY config/nginx.conf /etc/nginx/nginx.conf
COPY config/config.json /app/config.json

# Script de inicialização que carrega secrets do Docker (Convertido para Unix)
COPY scripts/entrypoint.sh /entrypoint.sh
RUN dos2unix /entrypoint.sh && chmod +x /entrypoint.sh

# Copia o arquivo de requisitos primeiro (para aproveitar o cache do Docker)
COPY requirements.txt .

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código do projeto para dentro do container
COPY src/ .

# Expõe a porta padrão do Streamlit
EXPOSE 80

# Verifica se a aplicação está saudável
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 CMD curl --fail http://localhost:80/health || exit 1

# Comando para iniciar a aplicação quando o container rodar
ENTRYPOINT ["/entrypoint.sh"]
CMD ["start-services"]
