DEFAULT_CUSTOM_METRICS = [
    {
        "id": 1,
        "name": "Erros de Cliente (HTTP 4xx)",
        "regex": r"(status|code|status_code)[:=]\s*(4\d{2})",
        "type": "counter"
    },
    {
        "id": 2,
        "name": "Erros de Servidor (HTTP 5xx)",
        "regex": r"(status|code|status_code)[:=]\s*(5\d{2})",
        "type": "counter"
    },
    {
        "id": 3,
        "name": "Latência da API (ms)",
        "regex": r"(?:duration|time|took|latency|elapsed)[:=]\s*(\d+(?:\.\d+)?)\s*ms",
        "type": "gauge"
    },
    {
        "id": 4,
        "name": "Falhas de Login",
        "regex": r"(login failed|falha de login|authentication failed)",
        "type": "counter"
    },
    {
        "id": 5,
        "name": "Sucessos HTTP (2xx)",
        "regex": r"(status|code|status_code)[:=]\s*(2\d{2})",
        "type": "counter"
    },
    {
        "id": 6,
        "name": "Redirecionamentos HTTP (3xx)",
        "regex": r"(status|code|status_code)[:=]\s*(3\d{2})",
        "type": "counter"
    },
    {
        "id": 7,
        "name": "Timeouts de Requisição",
        "regex": r"\b(timeout|timed out|request timeout)\b",
        "type": "counter"
    },
    {
        "id": 8,
        "name": "Erros de Conexão (Upstream)",
        "regex": r"\b(ECONNREFUSED|ECONNRESET|connection reset|broken pipe)\b",
        "type": "counter"
    },
    {
        "id": 9,
        "name": "Erros de Banco de Dados (SQL)",
        "regex": r"\b(SQLSTATE\[\w+\]|deadlock detected|lock wait timeout|database is locked)\b",
        "type": "counter"
    },
    {
        "id": 10,
        "name": "Latência p95 da API (ms)",
        "regex": r"(?:p95|latency_p95|p95_ms)[:=]\s*(\d+(?:\.\d+)?)\s*ms",
        "type": "gauge"
    },
    {
        "id": 11,
        "name": "Tamanho da Resposta (bytes)",
        "regex": r"(?:response_size|bytes_sent|resp_bytes)[:=]\s*(\d+)",
        "type": "gauge"
    },
    {
        "id": 12,
        "name": "Tamanho da Requisição (bytes)",
        "regex": r"(?:request_size|bytes_received|req_bytes)[:=]\s*(\d+)",
        "type": "gauge"
    },
    {
        "id": 13,
        "name": "Cache Hit",
        "regex": r"\bcache[_\s-]?hit\b",
        "type": "counter"
    },
    {
        "id": 14,
        "name": "Cache Miss",
        "regex": r"\bcache[_\s-]?miss\b",
        "type": "counter"
    },
    {
        "id": 15,
        "name": "Requisições Lentas (Slow Requests)",
        "regex": r"\b(slow request|slow query|lent[aã]o)\b",
        "type": "counter"
    },
    {
        "id": 16,
        "name": "Thread Bloqueada",
        "regex": r"\b(blocked thread|thread blocked|event loop blocked)\b",
        "type": "counter"
    },
    {
        "id": 17,
        "name": "Possível Memory Leak",
        "regex": r"\b(memory leak|leak detected|out of memory)\b",
        "type": "counter"
    },
    {
        "id": 18,
        "name": "Erros de Autorização (HTTP 403)",
        "regex": r"(status|code|status_code)[:=]\s*403",
        "type": "counter"
    },
    {
        "id": 19,
        "name": "Token Inválido ou Expirado",
        "regex": r"(invalid token|token expired|jwt expired|invalid jwt)",
        "type": "counter"
    },
    {
        "id": 20,
        "name": "Retentativas de Requisição (Retry)",
        "regex": r"\b(retry|retrying|tentativa novamente)\b",
        "type": "counter"
    },
    {
        "id": 21,
        "name": "Exceptions Não Tratadas",
        "regex": r"\b(Traceback|Unhandled exception|Exception in thread)\b",
        "type": "counter"
    },
    {
        "id": 22,
        "name": "Reinício de Serviço / Container",
        "regex": r"\b(restarting|container restart|service restart)\b",
        "type": "counter"
    },
    {
        "id": 23,
        "name": "Database Timeout",
        "regex": r"\b(query timeout|db timeout|timeout .* database)\b",
        "type": "counter"
    },
    {
        "id": 24,
        "name": "Falha em API Externa",
        "regex": r"\b(external api .* failed|failed external call|upstream error)\b",
        "type": "counter"
    },
    {
        "id": 25,
        "name": "Erro de Arquivo (FS Error)",
        "regex": r"\b(file not found|no such file|permission denied|ioerror)\b",
        "type": "counter"
    },
    {
        "id": 26,
        "name": "Mensagem Perdida em Fila",
        "regex": r"\b(message lost|failed to consume|queue error)\b",
        "type": "counter"
    },
    {
        "id": 27,
        "name": "Erro de Criptografia",
        "regex": r"\b(ssl error|tls error|crypto error|certificate error)\b",
        "type": "counter"
    },
    {
        "id": 28,
        "name": "Erro de Serialização ou JSON inválido",
        "regex": r"\b(json decode error|invalid json|serialization failed)\b",
        "type": "counter"
    },
    {
        "id": 29,
        "name": "Circuit Breaker Ativado",
        "regex": r"\b(circuit breaker|open circuit)\b",
        "type": "counter"
    },
    {
        "id": 30,
        "name": "Falha em Healthcheck",
        "regex": r"\b(healthcheck failed|health check failed|readiness probe failed|liveness probe failed)\b",
        "type": "counter"
    },
    {
        "id": 31,
        "name": "Erro de DNS",
        "regex": r"\b(dns resolve|could not resolve host|dns error)\b",
        "type": "counter"
    },
    {
        "id": 32,
        "name": "Erro de Cache Corrompido",
        "regex": r"\b(cache corrupted|cache invalid|unable to read cache)\b",
        "type": "counter"
    },
    {
        "id": 33,
        "name": "Rate Limit Excedido",
        "regex": r"\b(rate limit exceeded|too many requests|429)\b",
        "type": "counter"
    },
    {
        "id": 34,
        "name": "Falha em Webhook",
        "regex": r"\b(webhook failed|webhook error|failed to send webhook)\b",
        "type": "counter"
    },
    {
        "id": 35,
        "name": "LexisNexis - Erros Gerais",
        "regex": r"(?i)\b(LexisNexis error|LN error|lexisnexis failed)\b",
        "type": "counter"
    },
    {
        "id": 36,
        "name": "LexisNexis - Falha de Autenticação",
        "regex": r"(?i)\b(lexisnexis.*(auth failed|authentication failed|invalid credentials))\b",
        "type": "counter"
    },
    {
        "id": 37,
        "name": "LexisNexis - Timeout",
        "regex": r"(?i)\b(lexisnexis.*timeout|timeout.*lexisnexis)\b",
        "type": "counter"
    },
    {
        "id": 38,
        "name": "LexisNexis - Dados Inválidos",
        "regex": r"(?i)\b(lexisnexis.*invalid data|lexisnexis.*bad request)\b",
        "type": "counter"
    },
    {
        "id": 39,
        "name": "LexisNexis - Latência (ms)",
        "regex": r"(?i)(lexis_latency|lexis_time|lexis_elapsed)[:=]\s*(\d+(?:\.\d+)?)\s*ms",
        "type": "gauge"
    },
    {
        "id": 40,
        "name": "LexisNexis - Sucessos (2xx)",
        "regex": r"(?i)lexisnexis.*(status|code)[:=]\s*(2\d{2})",
        "type": "counter"
    },
    {
        "id": 41,
        "name": "LexisNexis - Erros (4xx/5xx)",
        "regex": r"(?i)lexisnexis.*(status|code)[:=]\s*([45]\d{2})",
        "type": "counter"
    },
    {
        "id": 42,
        "name": "LexisNexis - Rate Limit Excedido",
        "regex": r"(?i)\b(lexisnexis.*rate limit exceeded|too many requests.*lexisnexis|429.*lexisnexis)\b",
        "type": "counter"
    },
    {
        "id": 43,
        "name": "LexisNexis - Erro de Conexão",
        "regex": r"(?i)\b(lexisnexis.*ECONNREFUSED|lexisnexis.*ECONNRESET|connection reset.*lexisnexis|broken pipe.*lexisnexis)\b",
        "type": "counter"
    },
    {
        "id": 44,
        "name": "LexisNexis - Erro de Resposta Vazia",
        "regex": r"(?i)\b(lexisnexis.*empty response|lexisnexis.*no data returned)\b",
        "type": "counter"
    },
    {
        "id": 45,
        "name": "LexisNexis - Falha na Validação",
        "regex": r"(?i)\b(lexisnexis.*validation failed|lexisnexis.*invalid field)\b",
        "type": "counter"
    }
]