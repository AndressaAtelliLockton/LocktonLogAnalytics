# Estágio 1: Builder - Instala dependências e ferramentas de compilação
FROM python:3.10 as builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependências de compilação para pacotes científicos
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    gfortran \
    libblas-dev \
    liblapack-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Cria "wheels" para as dependências, o que acelera a instalação no próximo estágio
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt


# Estágio 2: Final - Imagem de produção, menor e mais segura
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ORCHESTRATOR=docker
ENV APP_VERSION=YYZ

# Cria um usuário e grupo não-root para rodar a aplicação
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

# Instala apenas as dependências de execução
RUN apt-get update && apt-get install -y curl dos2unix && rm -rf /var/lib/apt/lists/*

# OpenSSL custom
RUN printf "openssl_conf = default_conf\n\n[default_conf]\nssl_conf = ssl_sect\n\n[ssl_sect]\nsystem_default = system_default_sect\n\n[system_default_sect]\nCipherString = ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-SHA384:ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384:ECDHE-RSA-AES128-SHA256" > /etc/ssl/openssl.cnf

# Copia e instala as dependências a partir dos wheels pré-compilados
COPY --from=builder /app/wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt

# Copia os arquivos da aplicação
COPY config/config.json /app/config.json
COPY scripts/entrypoint.sh /entrypoint.sh
RUN dos2unix /entrypoint.sh && chmod +x /entrypoint.sh
COPY src/ .

RUN chown -R app:app /app
USER app

EXPOSE 80
EXPOSE 443

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD curl --fail http://localhost:80/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["start-services"]
