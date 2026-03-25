import pandas as pd
import json
import warnings
from pydantic import BaseModel
import os
from groq import Groq
import re
import tempfile
import hashlib
import requests
from requests.auth import HTTPBasicAuth
import io
import sqlite3
import numpy as np
import subprocess
import sys
import signal
from datetime import datetime
import socket
import zlib

try:
    from log_analyzer_lib import cicd_analysis
except ImportError:
    from src.log_analyzer_lib import cicd_analysis

try:
    from log_analyzer_lib import infra_analysis
except ImportError:
    from src.log_analyzer_lib import infra_analysis

# Garante o carregamento das variáveis de ambiente (.env) ao importar este módulo
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Pre-compiled Regex for Performance ---
IP_PATTERN = re.compile(r'(?<!\d)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?!\d)')
LATENCY_PATTERN = re.compile(r'\b(?:duration|time|took|latency|elapsed(?:milliseconds)?|in|after)\b(?:["\']?[:=]\s*["\']?|\s+["\']?)(\d+(?:\.\d+)?)(?:["\']|\s+)?(ms|s|sec|min|us|µs)?', re.IGNORECASE)
LATENCY_PATTERN = re.compile(r'(?:duration|time|took|latency|elapsed(?:milliseconds)?|\bin\b|\bafter\b)(?:["\']?[:=]\s*["\']?|\s+["\']?)(\d+(?:\.\d+)?)(?:["\']|\s+)?(ms|s|sec|min|us|µs)?', re.IGNORECASE)
CPF_PATTERN = re.compile(r'\d{3}\.\d{3}\.\d{3}-\d{2}')
EMAIL_PATTERN = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
NUM_PATTERN = re.compile(r'\d+')
UUID_PATTERN = re.compile(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', re.IGNORECASE)
TRACE_ID_PATTERN = re.compile(r'TraceId["\']?[:=]\s*["\']?([a-f0-9]{32})["\']?', re.IGNORECASE) # Suporte a TraceId W3C/.NET (sem traços) e JSON
SCHEDULER_STATUS_FILE = "scheduler_status.txt"
SCHEDULER_PID_FILE = "scheduler.pid"
URL_PATTERN = re.compile(r'https?://([\w\-\.]+)(?::\d+)?')

# --- Database Functions (Persistence) ---
DB_NAME = 'log_analysis_memory.db'

def init_db():
    """Inicializa o banco de dados (DESATIVADO)."""
    pass


def get_cached_ai_analysis(message):
    """Busca se já existe uma análise para esta mensagem exata."""
    return None


def update_ai_feedback(message, score):
    """Atualiza o feedback (score) da análise da IA."""
    return True

def get_ai_feedback(message):
    """Retorna o feedback atual para uma mensagem."""
    return 0


def save_ai_analysis(message, response, user="System"):
    """Salva a análise da IA no banco de dados."""
    pass


def save_setting(key, value):
    """Salva uma configuração no banco de dados."""
    pass


def get_setting(key, default=""):
    """Recupera uma configuração do banco de dados."""
    # Simplificado: Busca diretamente a variável de ambiente. O padrão é usar nomes em maiúsculas.
    return os.getenv(key.upper(), default)

def get_secret(key, default=""):
    """Recupera um segredo, que é apenas uma variável de ambiente neste contexto."""
    return os.getenv(key.upper(), default)

def get_db_stats():
    """Retorna estatísticas do banco de dados de cache."""
    return {"count": 0, "first": None, "last": None}


def clear_ai_cache():
    """Limpa todo o histórico de cache da IA."""
    return True


def get_all_cached_analyses():
    """Retorna todo o histórico de cache da IA como um DataFrame."""
    return pd.DataFrame()


def calculate_log_hash(timestamp, source, message):
    """Gera hash único para deduplicação de logs."""
    content = f"{timestamp}{source}{message}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def ingest_logs_to_db(df):
    """
    Ingere um DataFrame de logs no banco de dados local (Coleta Centralizada).
    Ignora duplicatas automaticamente para eficiência.
    """
    return 0


def get_collected_logs(limit=50000):
    """Recupera logs armazenados localmente para análise."""
    return pd.DataFrame()


def clean_old_logs(retention_days=30):
    """
    [Pipeline] Política de Retenção: Remove logs mais antigos que X dias.
    Garante eficiência de armazenamento e indexação.
    """
    return 0


def search_logs_in_db(query=None, start_date=None, end_date=None, source=None, limit=10000):
    """
    [Busca Avançada] Realiza queries otimizadas diretamente no banco de dados.
    Permite filtrar grandes volumes de dados sem carregar tudo na memória.
    """
    return pd.DataFrame()


def get_unique_sources_from_db():
    """Retorna lista de sources únicos indexados no banco para filtros rápidos."""
    return []


def is_scheduler_running():
    """Verifica se o processo do scheduler está ativo via PID."""
    if not os.path.exists(SCHEDULER_PID_FILE):
        return False
    try:
        with open(SCHEDULER_PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        # Verifica se o processo ainda existe (funciona em Windows e Linux)
        os.kill(pid, 0)
        return True

    except (ValueError, OSError, FileNotFoundError, SystemError):
        return False


def get_last_collection_time():
    """Obtém o timestamp da última coleta bem-sucedida do arquivo de status."""
    try:
        with open(SCHEDULER_STATUS_FILE, "r") as f:
            timestamp_str = f.readline().strip()
            # Check if the string is empty or whitespace
            if timestamp_str:
                return timestamp_str
            else:
                return None  # or some other appropriate default
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Erro ao ler o arquivo de status do scheduler: {e}")
        return None


def update_scheduler_status():
    """Atualiza o arquivo de status com o timestamp atual."""
    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(SCHEDULER_STATUS_FILE, "w") as f:
            f.write(now)
        return True
    except Exception as e:
        print(f"Erro ao atualizar o arquivo de status do scheduler: {e}")
        return False


def clear_scheduler_status():
    """Remove o arquivo de status, indicando que o scheduler não está rodando."""
    try:
        if os.path.exists(SCHEDULER_STATUS_FILE):
            os.remove(SCHEDULER_STATUS_FILE)
        return True
    except Exception as e:
        print(f"Erro ao remover o arquivo de status do scheduler: {e}")
        return False


def start_scheduler_background():
    """Inicia o scheduler.py em background."""
    if is_scheduler_running():
        return False, "O agendador já está em execução."
    
    try:
        # Determina o comando correto
        cmd = [sys.executable, "scheduler.py"]
        
        if os.name == 'nt': # Windows
            # CREATE_NEW_CONSOLE cria uma nova janela para ver os logs em tempo real
            process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else: # Linux/Mac
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
        with open(SCHEDULER_PID_FILE, 'w') as f:
            f.write(str(process.pid))
            
        return True, f"Agendador iniciado (PID: {process.pid})."
    except Exception as e:
        return False, f"Falha ao iniciar: {e}"


def stop_scheduler_background():
    """Para o processo do scheduler."""
    if not os.path.exists(SCHEDULER_PID_FILE):
        return False, "Agendador não parece estar rodando."
    
    try:
        with open(SCHEDULER_PID_FILE, 'r') as f:
            pid = int(f.read().strip())
            
        # Mata o processo
        os.kill(pid, signal.SIGTERM)
        
        # Limpa arquivos
        if os.path.exists(SCHEDULER_PID_FILE): os.remove(SCHEDULER_PID_FILE)
        if os.path.exists(SCHEDULER_STATUS_FILE): os.remove(SCHEDULER_STATUS_FILE)
            
        return True, "Agendador parado com sucesso."
    except Exception as e:
        # Limpeza forçada se o processo já morreu
        if os.path.exists(SCHEDULER_PID_FILE): os.remove(SCHEDULER_PID_FILE)
        return False, f"Erro ao parar (limpeza forçada): {e}"


# Inicializa o DB ao importar o módulo
init_db()


def load_config(config_path='config.json'):
    """Carrega o arquivo de configuração de forma segura."""
    # Lista de caminhos possíveis para tentar encontrar o config
    possible_paths = [
        config_path,
        os.path.join("config", config_path),
        os.path.join("..", "config", config_path),
        os.path.join(os.path.dirname(__file__), "config.json"),
        os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
    ]

    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config, None
            except json.JSONDecodeError:
                return None, f"Erro: O arquivo '{path}' não é um JSON válido."
            except Exception as e:
                return None, f"Erro inesperado ao ler '{path}': {str(e)}"
    
    return None, f"Erro: Arquivo de configuração '{config_path}' não encontrado em nenhum dos locais esperados."


def parse_log_entry(message):
    """
    Parses a log message, which can be a JSON string or plain text.
    Returns a dictionary with extracted data.
    """
    try:
        return json.loads(message)
    except (json.JSONDecodeError, TypeError):
        return {'message_text': str(message)}


def categorize_log(log_data, config):
    """
    Categorizes the log based on its content and the provided configuration.
    """
    if not config or 'categories' not in config:
        return 'Não configurado'

    text_to_search = ''
    log_level_to_check = ''
    if 'message_text' in log_data:
        text_to_search = log_data['message_text'].lower()
    else:
        text_to_search = (log_data.get('Message', '') + ' ' + log_data.get('Category', '')).lower()
        log_level_to_check = log_data.get('LogLevel', '').lower()

    for category in config['categories']:
        if 'log_levels' in category and log_level_to_check in category['log_levels']:
            return category['name']
        
        if 'keywords' in category:
            for keyword in category['keywords']:
                if keyword.lower() in text_to_search:
                    return category['name']

    return 'Não categorizado'


def extract_log_level(log_data):
    """
    Extrai o nível de log de uma entrada de log.
    """
    if 'LogLevel' in log_data:
        return log_data['LogLevel']
    
    message_text = log_data.get('message_text', '').lower()
    if 'info:' in message_text:
        return 'Info'
    if 'fail:' in message_text:
        return 'Fail'
    if 'error:' in message_text:
        return 'Error'
    if 'debug:' in message_text:
        return 'Debug'
    if 'warning:' in message_text:
        return 'Warning'
        
    return 'Não Identificado'


def process_log_data(df, config):
    """
    Processes a DataFrame of logs, categorizes them, and returns the results.
    Optimized for performance using vectorized operations.
    """
    if df.empty:
        return pd.DataFrame(columns=['timestamp', 'source', 'message', 'category', 'log_level', 'message_length']), {}

    if not config:
        raise ValueError("A configuração para categorização é inválida.")

    # Ensure we are working with a copy to avoid SettingWithCopy warnings on the input df
    # and ensure message is string
    # Normalização de Colunas (Case Insensitive para Message, Source, Timestamp)
    # Garante que funcione mesmo se o CSV vier com "Message" ou "Timestamp" (PascalCase)
    df_proc = df.copy()
    df_proc = df_proc.reset_index(drop=True)
    rename_map = {}
    for col in ['message', 'source', 'timestamp']:
        if col not in df_proc.columns:
            for existing_col in df_proc.columns:
                if existing_col.lower() == col:
                    rename_map[existing_col] = col
                    break
    if rename_map:
        df_proc.rename(columns=rename_map, inplace=True)

    df_proc['message'] = df_proc['message'].astype(str)
    
    # 1. Calculate Message Length (Vectorized)
    df_proc['message_length'] = df_proc['message'].str.len()

    # 2. Extract Log Level (Vectorized)
    # Default
    df_proc['log_level'] = 'Não Identificado'
    
    # Strategy A: Regex for "LogLevel": "Value" (Common in JSON logs)
    log_level_pattern = r'(?i)"?LogLevel"?\s*[:=]\s*"?(\w+)"?'
    extracted_levels = df_proc['message'].astype(str).str.extract(log_level_pattern, expand=False)
    
    if extracted_levels is not None:
        df_proc['log_level'] = extracted_levels.fillna('Não Identificado')

    # Strategy B: Keyword search for those still unidentified
    msg_lower = df_proc['message'].str.lower()
    mask_unknown = df_proc['log_level'] == 'Não Identificado'
    
    keywords_map = {
        'fail:': 'Fail',
        'error:': 'Error',
        'exception': 'Error',
        'critical:': 'Critical',
        'fatal:': 'Fatal',
        'warning:': 'Warning',
        'debug:': 'Debug',
        'info:': 'Info'
    }
    
    for key, label in keywords_map.items():
        mask_hit = mask_unknown & msg_lower.str.contains(re.escape(key), regex=True)
        df_proc.loc[mask_hit, 'log_level'] = label
        mask_unknown = mask_unknown & (~mask_hit)

    # Normalize Log Level casing
    df_proc['log_level'] = df_proc['log_level'].astype(str).str.capitalize()

    # 3. Categorization (Vectorized)
    df_proc['category'] = 'Não categorizado'
    
    if 'categories' in config:
        for cat in config['categories']:
            cat_name = cat['name']
            cat_mask = pd.Series(False, index=df_proc.index)
            
            if 'log_levels' in cat:
                target_levels = [l.lower() for l in cat['log_levels']]
                if target_levels:
                    cat_mask |= df_proc['log_level'].astype(str).str.lower().isin(target_levels)
            
            keywords = cat.get('keywords', [])
            if keywords:
                pattern = '|'.join(map(re.escape, keywords))
                cat_mask |= df_proc['message'].astype(str).str.contains(pattern, case=False, regex=True, na=False)
            
            # Apply category only to rows that are currently 'Não categorizado' (Priority: First match wins)
            update_mask = (df_proc['category'] == 'Não categorizado') & cat_mask
            df_proc.loc[update_mask, 'category'] = cat_name

    # Select and reorder columns
    # Atualizado para preservar colunas de métricas vindas do Graylog (cpu_valor, mem_valor)
    output_cols = ['timestamp', 'source', 'message', 'category', 'log_level', 'message_length']
    
    # Preserva colunas extras se existirem no DF original
    extra_cols = ['cpu_valor', 'mem_valor', 'container_name', 'image_name', 'RequestPath', 'streams', 'tag']
    for col in extra_cols:
        if col in df_proc.columns:
            output_cols.append(col)

    for col in output_cols:
        if col not in df_proc.columns:
            df_proc[col] = None
            
    output_df = df_proc[output_cols]
    category_counts = output_df['category'].value_counts().to_dict()

    return output_df, category_counts



def generate_initial_prompt(log_message):
    """Gera o prompt inicial para análise de logs."""
    return f"""
        Você é um Especialista SRE operando dentro de uma ferramenta de Observabilidade que JÁ POSSUI:
        - Detecção de Anomalias (Machine Learning/Z-Score)
        - Agrupamento de Padrões (Clustering)
        - Extração de Latência
        
        Analise este log do sistema indicado na mensagem:
        {log_message}
        
        Realize uma análise técnica focada em resolução definitiva:

        1. CATEGORIA: (Auditoria, Segurança, Aplicação, Performance, Acesso ou Integridade)
        2. DIAGNÓSTICO: (Integridade, Segurança ou Operacional)
        3. SOLUÇÃO TÉCNICA APLICÁVEL: Apresente a correção exata (código, comando ou configuração) para resolver o problema, simulando o resultado da solução aplicada.
        4. RESULTADOS DA IMPLEMENTAÇÃO (Melhorias Práticas):
           - Logging Estruturado: Gere o JSON estruturado final para este log. Inclua no json o source. Apresente o JSON formatado e indentado dentro de um bloco de código markdown (```json). Não use a palavra "undefined".
           - Monitoramento de Desempenho: Defina a métrica exata e o limiar (threshold) crítico a ser configurado.
           - Documentação: Forneça o texto exato para atualização da Base de Conhecimento (KB).
           - Automação: Escreva a Regex ou Query exata para criar o alerta. Não sugira "implementar ML" ou "clustering", pois a ferramenta já faz isso.

        5. TICKET JIRA (Rascunho):
           Gere um exemplo de ticket para o Jira com base nesta análise, formatado em Markdown, contendo:
           - Título (Resumo do erro)
           - Descrição (O que aconteceu, logs, impacto)
           - Logging Estruturado: Gere o JSON estruturado final para este log. Inclua no json o source. Apresente o JSON formatado e indentado dentro de um bloco de código markdown (```json). Não use a palavra "undefined".
           - Passos para Reprodução (se aplicável)
           - Solução Técnica (Correção a ser aplicada)
           - Prioridade Sugerida

        Se a sua assertividade for menor que 95%, responda apenas: "Baseado no conhecimento atual, como agente de IA, não consigo sugerir uma recomendação que seja eficiente."
        Se a sua assertividade for entre 95% e 100%, mostre o nivel de assertividade e apresente as recomendações.
        
        IMPORTANTE: Se o usuário disser "encerrar" ou algo similar durante a conversa, responda com um resumo consolidado das ações recomendadas (Imediatas e Longo Prazo) discutidas até agora e finalize a interação de forma cordial.

        Responda em Português de forma técnica e clara.
        """

class LogDataForPrompt(BaseModel):
    """Modelo Pydantic para receber os dados do log do frontend para o prompt."""
    timestamp: str
    source: str
    message: str

def generate_chat_system_prompt(log: LogDataForPrompt) -> str:
    """Gera o prompt de sistema para o chat da IA com base em um log específico."""
    return (
        "Você é um assistente SRE especialista. Analise este log:\n"
        f"Timestamp: {log.timestamp}\n"
        f"Source: {log.source}\n"
        f"Message: {log.message}\n\n"
        "Responda de forma técnica e clara."
    )


def send_chat_message(messages, model_name='llama-3.3-70b-versatile'):
    """Envia uma lista de mensagens para a API da Groq e retorna a resposta."""
    api_key = os.environ.get("GROQ_API_KEY") or get_setting("groq_api_key")
    
    if not api_key:
        return "Erro: Chave de API da Groq não encontrada. Configure a variável de ambiente GROQ_API_KEY ou insira na barra lateral."

    client = Groq(api_key=api_key, timeout=30.0) # Timeout de 30s para evitar travamento infinito
    
    try:
        chat_completion = client.chat.completions.create(
            messages=messages,
            model=model_name,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"Erro na análise: {str(e)}"


def analyze_log_with_ai(log_message, model_name='llama-3.3-70b-versatile'):
    """Função wrapper para manter compatibilidade com chamadas antigas."""
    prompt = generate_initial_prompt(log_message)
    messages = [{"role": "user", "content": prompt}]
    return send_chat_message(messages, model_name)


def send_webhook_alert(webhook_url, message, title="🚨 Alerta de Log"):
    """Envia um alerta para Slack/Teams/Discord via Webhook."""
    
    # Detecta se é Microsoft Teams para usar Card Format (mais bonito e com cor)
    if "outlook.office.com" in webhook_url or "webhook.office.com" in webhook_url:
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "0076D7",
            "summary": title,
            "sections": [{
                "activityTitle": title,
                "text": message,
                "markdown": True
            }]
        }
    else:
        # Fallback para Slack/Discord (Texto simples)
        payload = {
            "text": f"*{title}*\n{message}"
        }
        
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response
    except Exception as e:
        return f"Falha no envio: {str(e)}"


def analyze_critical_logs_with_ai(df, model='llama-3.3-70b-versatile'):
    """
    Analyzes logs categorized as 'Aplicação (erro/exceção)' with an AI model.
    """
    critical_logs = df[df['category'] == 'Aplicação (erro/exceção)']
    
    if critical_logs.empty:
        return ["Nenhum log crítico para analisar com IA."]

    ai_analyses = []
    for index, row in critical_logs.iterrows():
        log_message = row['message']
        ai_analysis = analyze_log_with_ai(log_message, model)
        ai_analyses.append({
            "timestamp": row['timestamp'],
            "log_message": log_message,
            "ai_analysis": ai_analysis
        })
        
    return ai_analyses


def extract_trace_ids(df):
    """
    Extrai IDs de rastreamento (UUIDs) das mensagens de log.
    Retorna o DataFrame com uma nova coluna 'trace_id'.
    """
    if df.empty:
        return df
    
    # Reset index to avoid alignment issues
    df = df.reset_index(drop=True)
    
    # Use .values to avoid index alignment issues with duplicate indices
    uuid_extract = df['message'].astype(str).str.extract(UUID_PATTERN, expand=False)
    w3c_extract = df['message'].astype(str).str.extract(TRACE_ID_PATTERN, expand=False)
    
    # Combine using numpy where to handle conditional logic without index alignment risks
    df['trace_id'] = np.where(uuid_extract.notna(), uuid_extract.values, w3c_extract.values)
    
    return df


def calculate_file_hash(file_content):
    """Calcula o hash SHA-256 do arquivo para garantir integridade (WORM/Auditoria)."""
    return hashlib.sha256(file_content).hexdigest()


def mask_sensitive_data(df):
    """
    Ofuscação dinâmica de dados sensíveis (LGPD).
    Mascará CPFs, E-mails e IPs.
    """
    df_masked = df.copy()
    # Vectorized replacements
    series = df_masked['message'].astype(str)
    series = series.str.replace(CPF_PATTERN, '***.***.***-**', regex=True)
    series = series.str.replace(EMAIL_PATTERN, '*****@*****.***', regex=True)
    series = series.str.replace(IP_PATTERN, '***.***.***.***', regex=True)
    df_masked['message'] = series
    return df_masked


def extract_latency_metrics(df):
    """
    Tenta extrair métricas de latência (ex: 'duration=50ms') dos logs.
    Log-to-Metrics.
    """
    # Vectorized extraction
    work_df = df.reset_index(drop=True)
    extracted = work_df['message'].astype(str).str.extract(LATENCY_PATTERN)
    extracted.columns = ['value', 'unit']
    
    valid_mask = extracted['value'].notna()
    if not valid_mask.any():
        return pd.DataFrame()
        
    result = work_df.loc[valid_mask, ['timestamp', 'source']].copy()
    result['latency_ms'] = extracted.loc[valid_mask, 'value'].astype(float)
    
    # Convert seconds to ms
    s_mask = extracted.loc[valid_mask, 'unit'] == 's'
    result.loc[s_mask, 'latency_ms'] *= 1000
    
    # Convert microseconds to ms
    us_mask = extracted.loc[valid_mask, 'unit'].isin(['us', 'µs'])
    result.loc[us_mask, 'latency_ms'] /= 1000
    
    return result


def detect_bottlenecks(df, threshold_ms=1000):
    """
    Identifica gargalos de performance baseados em latência.
    Retorna um DataFrame com os endpoints/sources mais lentos.
    """
    latency_df = extract_latency_metrics(df)
    if latency_df.empty:
        return pd.DataFrame()

    # Filtra logs acima do threshold
    slow_logs = latency_df[latency_df['latency_ms'] > threshold_ms]
    
    if slow_logs.empty:
        return pd.DataFrame()

    # Agrupa por source para identificar ofensores frequentes
    bottlenecks = slow_logs.groupby('source').agg(
        slow_count=('latency_ms', 'count'),
        avg_latency=('latency_ms', 'mean'),
        max_latency=('latency_ms', 'max'),
        p95_latency=('latency_ms', lambda x: x.quantile(0.95))
    ).reset_index()
    
    return bottlenecks.sort_values('avg_latency', ascending=False)


def generate_stack_trace_metrics(df):
    """
    Analisa logs de erro para extrair e agregar stack traces para visualização tipo Flame Graph.
    Retorna um DataFrame com 'stack_trace', 'count' e 'depth'.
    """
    # Filtra logs de erro e Warning (ampliando escopo para capturar traces em warnings)
    error_df = df[df['log_level'].isin(['Error', 'Fail', 'Critical', 'Fatal', 'Warning'])]
    
    if error_df.empty:
        return pd.DataFrame()

    # Regex para capturar linhas de stack trace (Python e Java/Generic)
    # Python: File "...", line X, in method
    # Java: at package.Class.method(...)
    # Otimizado para lidar com quebras de linha e variações
    # ATUALIZADO: Mais permissivo para capturar 'at ...' no meio de linhas e caminhos genéricos (file:line)
    stack_pattern = re.compile(r'(File "[^"]+", line \d+)|(?:^|\s)(at\s+[^\r\n]+)|(\b[\w\-\.\/]+\.\w+:\d+\b)', re.MULTILINE | re.IGNORECASE)
    
    stack_counts = {}
    
    # Itera sobre as linhas para ter acesso ao 'source' para o fallback
    for row in error_df.itertuples(index=False):
        msg = getattr(row, 'message', '')
        source = getattr(row, 'source', 'Unknown')
        msg_str = str(msg).replace('\\n', '\n').replace('\\r', '')
        
        matches = stack_pattern.findall(msg_str)
        if matches:
            clean_stack = []
            is_java = False
            for m in matches:
                # m é tupla ('File...', 'at...', 'generic...')
                py_match = m[0]
                java_match = m[1]
                generic_match = m[2] if len(m) > 2 else ""

                if py_match: # Python
                    parts = py_match.split(',')
                    if len(parts) >= 2:
                        # Extrai arquivo
                        file_part = parts[0].split('"')[1]
                        filename = file_part.split('/')[-1].split('\\')[-1]
                        # Extrai método
                        method = "unknown"
                        if len(parts) >= 3 and " in " in parts[2]:
                            method = parts[2].split(" in ")[1].strip()
                        clean_stack.append(f"{filename}:{method}")

                elif java_match: # Java/Net
                    is_java = True
                    content = java_match.strip()
                    if content.lower().startswith('at '):
                        content = content[3:].strip()
                    
                    # Tenta pegar apenas o método (antes do parenteses)
                    if '(' in content:
                        method_part = content.split('(')[0].strip()
                    else:
                        method_part = content
                    
                    clean_stack.append(method_part)
                
                elif generic_match:
                    clean_stack.append(generic_match.strip())
            
            if clean_stack:
                # Java imprime o topo da pilha primeiro (onde quebrou), Flame Graph espera Raiz -> Folha
                if is_java:
                    clean_stack = clean_stack[::-1]
                
                signature = ";".join(clean_stack)
                if signature:
                    stack_counts[signature] = stack_counts.get(signature, 0) + 1
        else:
            # FALLBACK: Se não encontrar stack trace, usa a mensagem agrupada como "trace"
            # Isso garante que o gráfico mostre a distribuição de erros mesmo sem traces formais
            # Limpa números e UUIDs para agrupar mensagens similares
            clean_msg = re.sub(r'\d+', '<NUM>', msg_str)
            clean_msg = re.sub(r'([a-f0-9-]{36})', '<UUID>', clean_msg)
            short_msg = clean_msg.strip()[:80] # Limita tamanho
            
            if short_msg:
                # Cria hierarquia artificial: Source -> Mensagem
                signature = f"{source};{short_msg}"
                stack_counts[signature] = stack_counts.get(signature, 0) + 1
                
    if not stack_counts:
        return pd.DataFrame()
        
    data = [{'stack_trace': k, 'count': v, 'depth': len(k.split(';'))} for k, v in stack_counts.items()]
    return pd.DataFrame(data).sort_values('count', ascending=False)


def extract_system_metrics(df):
    """
    Extrai métricas de sistema (CPU, Memória, Disco, Rede) de mensagens de log.
    """
    if df.empty:
        return pd.DataFrame()
        
    # 1. Extração baseada em Regex (Comportamento legado para texto livre)
    base_df = infra_analysis.extract_system_metrics(df)
    
    # 2. Extração baseada em colunas estruturadas do Graylog (cpu_valor, mem_valor)
    structured_df = pd.DataFrame()
    has_cpu = 'cpu_valor' in df.columns
    has_mem = 'mem_valor' in df.columns
    
    if has_cpu or has_mem:
        mask = pd.Series(False, index=df.index)
        if has_cpu:
            mask = mask | pd.to_numeric(df['cpu_valor'], errors='coerce').notna()
        if has_mem:
            mask = mask | pd.to_numeric(df['mem_valor'], errors='coerce').notna()
            
        if mask.any():
            structured_df = df.loc[mask, ['timestamp', 'source']].copy()
            structured_df['cpu'] = pd.to_numeric(df.loc[mask, 'cpu_valor'] if has_cpu else 0, errors='coerce').fillna(0)
            structured_df['memory'] = pd.to_numeric(df.loc[mask, 'mem_valor'] if has_mem else 0, errors='coerce').fillna(0)
            structured_df['disk'] = 0.0 # Disco geralmente não vem estruturado nesses logs
            
    # 3. Mescla e unifica os resultados
    if not structured_df.empty:
        if not base_df.empty:
            # Concatena e agrupa tirando o valor máximo para mesclar atributos da mesma linha de log
            combined = pd.concat([base_df, structured_df], ignore_index=True)
            for col in ['cpu', 'memory', 'disk']:
                if col not in combined.columns:
                    combined[col] = 0.0
            return combined.groupby(['timestamp', 'source'], as_index=False).max()
        return structured_df
        
    return base_df


def extract_api_metrics(df):
    """
    Extrai métricas de API (Método, Status, Endpoint, Latência) dos logs.
    Prioriza campos estruturados (ex: colunas 'latency_ms', 'status_code') e
    faz fallback para parsing de regex na coluna 'message' se não encontrados.
    """
    if df.empty:
        return pd.DataFrame()

    work_df = df.reset_index(drop=True).copy() # Use copy to avoid SettingWithCopyWarning

    # --- Inicializa DataFrame de resultado ---
    base_cols = ['timestamp', 'source']
    for col in ['message', 'log_level', 'category', 'streams']:
        if col in work_df.columns:
            base_cols.append(col)
    result = work_df[base_cols].copy()

    # --- 1. Extração de Latência (Prioriza coluna existente) ---
    result['latency_ms'] = np.nan
    # Tenta usar colunas numéricas existentes primeiro
    latency_col_candidates = ['latency_ms', 'duration', 'took', 'elapsed_ms']
    for col in latency_col_candidates:
        if col in work_df.columns and pd.api.types.is_numeric_dtype(work_df[col]):
            # Preenche apenas onde ainda é NaN (permite mesclar colunas diferentes)
            result['latency_ms'] = result['latency_ms'].fillna(work_df[col])
    
    # Fallback: Se ainda existem valores nulos, tenta regex na mensagem (apenas nas linhas faltantes)
    missing_lat_mask = result['latency_ms'].isna()
    if missing_lat_mask.any():
        df_str = work_df.loc[missing_lat_mask, 'message'].astype(str)
        extracted_latency = df_str.str.extract(LATENCY_PATTERN)
        
        if not extracted_latency.empty:
            extracted_latency.columns = ['value', 'unit']
            valid_mask = extracted_latency['value'].notna()
            
            if valid_mask.any():
                # Mapeia de volta para o índice original
                valid_lat = extracted_latency[valid_mask]
                values = pd.to_numeric(valid_lat['value'], errors='coerce')
                units = valid_lat['unit'].str.lower().fillna('ms')
                
                conditions = [units.isin(['s', 'sec']), units == 'min', units.isin(['us', 'µs'])]
                choices = [values * 1000, values * 60000, values / 1000]
                
                converted_values = np.select(conditions, choices, default=values)
                result.loc[valid_lat.index, 'latency_ms'] = converted_values

    # --- 2. Extração de Status Code (Prioriza coluna) ---
    result['status_code'] = None
    if 'status_code' in work_df.columns:
        result['status_code'] = work_df['status_code']
    elif 'http_status_code' in work_df.columns:
        result['status_code'] = work_df['http_status_code']
    else: # Fallback para regex
        status_pattern = r'(?:^|\s|status(?:_?code)?["\']?[:=]\s*["\']?)([1-5]\d{2})(?:["\']?[\s,}]|$)'
        extracted_status = work_df['message'].astype(str).str.extract(status_pattern, flags=re.IGNORECASE)
        if not extracted_status.empty:
            result['status_code'] = extracted_status[0]

    # --- 3. Extração de Método e Endpoint (Prioriza colunas) ---
    result['method'] = None
    result['endpoint'] = None
    
    # Prioridade 1: Colunas explícitas
    if 'http_method' in work_df.columns:
        result['method'] = work_df['http_method']
    if 'http_path' in work_df.columns:
        result['endpoint'] = work_df['http_path']
    elif 'RequestPath' in work_df.columns: # Fallback para outro nome comum
        result['endpoint'] = work_df['RequestPath']

    # Prioridade 2: Fallback para Regex se método ou endpoint não foram encontrados
    if result['method'].isna().any() or result['endpoint'].isna().any():
        method_path_pattern = r'(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+([^\s?]+)'
        request_path_pattern = r'RequestPath["\']?[:=]\s*["\']?([^\s,"]+)["\']?'
        
        df_str = work_df['message'].astype(str)
        extracted_mp = df_str.str.extract(method_path_pattern, flags=re.IGNORECASE)
        extracted_rp = df_str.str.extract(request_path_pattern, flags=re.IGNORECASE)

        # Preenche apenas os que estão faltando (NaN)
        if not extracted_mp.empty:
            result['method'] = result['method'].fillna(extracted_mp[0].str.upper())
            result['endpoint'] = result['endpoint'].fillna(extracted_mp[1])
        
        # Fallback final para RequestPath dentro da mensagem
        if not extracted_rp.empty:
            mask_rp = result['endpoint'].isna() & extracted_rp[0].notna()
            result.loc[mask_rp, 'endpoint'] = extracted_rp.loc[mask_rp, 0]
            # Se o método ainda for nulo para esses, classifica como RPC
            result.loc[mask_rp & result['method'].isna(), 'method'] = 'RPC'

    # Retorna linhas que possuam métricas relevantes (Método, Endpoint, Status ou Latência)
    # Evita descartar logs que tenham latência mas falharam na detecção do método
    relevant_mask = (
        result['method'].notna() | 
        result['endpoint'].notna() | 
        result['status_code'].notna() | 
        result['latency_ms'].notna()
    )
    result = result[relevant_mask].copy()

    # Preenche defaults para permitir agrupamentos
    result['method'] = result['method'].fillna('UNKNOWN')
    result['endpoint'] = result['endpoint'].fillna('UNKNOWN')

    return result


def extract_cicd_metrics(df):
    """
    Extrai métricas de CI/CD (Pipelines, Builds, Deploys) dos logs.
    Procura por padrões como 'Pipeline status: success', 'Build duration: 120s'.
    """
    return cicd_analysis.extract_cicd_metrics(df)


def analyze_security_threats(df):
    """Análise simples de segurança (SIEM). Extrai IPs e verifica volume de erros."""
    if df.empty:
        return pd.DataFrame()
        
    # Vectorized IP extraction
    work_df = df.reset_index(drop=True)
    ips_series = work_df['message'].astype(str).str.findall(IP_PATTERN)
    exploded = ips_series.explode()
    
    # Filtra valores vazios ou nulos
    exploded = exploded[exploded.notna() & (exploded != "")]
    
    if exploded.empty:
        return pd.DataFrame()
        
    sec_df = work_df.loc[exploded.index, ['timestamp', 'log_level', 'source']].copy()
    sec_df['ip'] = exploded.values
    
    # Normaliza níveis de log e define lista de erros
    sec_df['log_level'] = sec_df['log_level'].astype(str).str.capitalize()
    error_levels = ['Error', 'Fail', 'Critical', 'Fatal']
        
    ip_stats = sec_df.groupby('ip').agg(
        total_logs=('timestamp', 'count'), 
        error_count=('log_level', lambda x: x.isin(error_levels).sum())
    ).reset_index()
    
    ip_stats['error_rate'] = ip_stats['error_count'] / ip_stats['total_logs']
    ip_stats['status'] = ip_stats.apply(lambda x: '🔴 Crítico' if x['error_rate'] > 0.5 and x['total_logs'] > 5 else ('🟡 Suspeito' if x['error_rate'] > 0.2 else '🟢 Normal'), axis=1)
    return ip_stats.sort_values('error_count', ascending=False)


def simulate_alerts(df, latency_threshold=None, keyword=None, log_levels=None):
    """
    Simula regras de alerta baseadas em latência, palavras-chave e nível de log.
    Retorna o DataFrame filtrado com os logs que disparariam o alerta.
    """
    triggered_logs = df.copy()
    
    # 1. Filtro por Nível de Log
    if log_levels:
        triggered_logs = triggered_logs[triggered_logs['log_level'].isin(log_levels)]
        
    # 2. Filtro por Palavra-chave
    if keyword:
        triggered_logs = triggered_logs[triggered_logs['message'].astype(str).str.contains(keyword, case=False, na=False)]
        
    # 3. Filtro por Latência
    if latency_threshold is not None and latency_threshold > 0:
        # Reutiliza lógica de extração de latência linha a linha
        def get_latency(msg):
            match = LATENCY_PATTERN.search(str(msg))
            if match:
                value = float(match.group(1))
                unit = match.group(2)
                if unit == 's': value *= 1000
                elif unit in ['us', 'µs']: value /= 1000
                return value
            return -1 # Valor negativo para indicar que não tem latência
            
        # Aplica a extração e filtra
        triggered_logs['latency_ms'] = triggered_logs['message'].apply(get_latency)
        triggered_logs = triggered_logs[triggered_logs['latency_ms'] > latency_threshold]
        
    return triggered_logs


def generate_log_patterns(df):
    """
    Agrupa logs em padrões (Patterns).
    Identifica ruído e agrupa mensagens que variam apenas em IDs/Números.
    """
    if df.empty:
        return pd.DataFrame()

    df_patterns = df.copy()
    
    # Vectorized masking
    sigs = df_patterns['message'].astype(str)
    sigs = sigs.str.replace(NUM_PATTERN, '[NUM]', regex=True)
    sigs = sigs.str.replace(UUID_PATTERN, '[UUID]', regex=True)
    sigs = sigs.str.replace(IP_PATTERN, '[IP]', regex=True)
    sigs = sigs.str.replace(EMAIL_PATTERN, '[EMAIL]', regex=True)
    df_patterns['signature'] = sigs.str.slice(0, 200)
    
    patterns = df_patterns.groupby('signature').agg(
        count=('timestamp', 'count'),
        first_seen=('timestamp', 'min'),
        last_seen=('timestamp', 'max'),
        example_message=('message', 'first'),
        log_level=('log_level', 'first'),
        sources=('source', lambda x: list(set(x)))
    ).reset_index().sort_values(['count', 'first_seen'], ascending=[False, True])
    
    patterns['percent'] = (patterns['count'] / len(df)) * 100
    return patterns


def infer_service_dependencies(df):
    """
    Infere dependências (arestas) entre serviços (nós) procurando nomes de sources, IPs e Domínios nas mensagens.
    Retorna um DataFrame com 'source', 'target', 'count'.
    """
    if df.empty or 'source' not in df.columns:
        return pd.DataFrame()

    # OTIMIZAÇÃO: Priority Sampling se o dataset for muito grande (>50k)
    # Mantém todos os logs de erro (Error/Fail) e faz a amostragem apenas nos logs Info.
    limit = 50000
    working_df = df
    
    if len(df) > limit:
        priority_mask = df['log_level'].isin(['Error', 'Fail', 'Critical', 'Fatal'])
        priority_df = df[priority_mask]
        other_df = df[~priority_mask]
        
        if len(priority_df) >= limit:
            working_df = priority_df.sample(limit)
        else:
            working_df = pd.concat([priority_df, other_df.sample(limit - len(priority_df))])

    # Reset index to avoid shape mismatch in vectorized operations
    working_df = working_df.reset_index(drop=True)

    all_edges_list = []

    # 1. Internal Dependencies (Source Names)
    known_sources = [s for s in df['source'].unique() if isinstance(s, str) and len(s) > 3] # Ignora sources muito curtos (ruído)
    if known_sources:
        source_map = {s.lower(): s for s in known_sources}
        sorted_sources = sorted(source_map.keys(), key=len, reverse=True)
        pattern = re.compile('|'.join(map(re.escape, sorted_sources)), re.IGNORECASE)

        matches = working_df['message'].astype(str).str.findall(pattern)
        exploded = matches.explode().dropna()
        
        if not exploded.empty:
            canonical_targets = exploded.str.lower().map(source_map)
            edges = pd.DataFrame({
                'source': working_df.loc[canonical_targets.index, 'source'].values,
                'target': canonical_targets.values
            })
            edges = edges[edges['source'] != edges['target']]
            all_edges_list.append(edges)

    # 2. External Dependencies (IPs)
    # OTIMIZAÇÃO: Filtra mensagens que possuem dígitos antes de aplicar regex de IP
    ip_mask = working_df['message'].astype(str).str.contains(r'\d', regex=True)
    ip_matches = working_df.loc[ip_mask, 'message'].astype(str).str.findall(IP_PATTERN)
    ip_exploded = ip_matches.explode().dropna()
    
    if not ip_exploded.empty:
        ip_edges = pd.DataFrame({
            'source': working_df.loc[ip_exploded.index, 'source'].values,
            'target': ip_exploded.values
        })
        ip_edges = ip_edges[ip_edges['source'] != ip_edges['target']]
        all_edges_list.append(ip_edges)

    # 3. External Dependencies (URLs/Domains)
    # OTIMIZAÇÃO: Filtra mensagens com 'http' antes de extrair
    url_mask = working_df['message'].astype(str).str.contains(r'http', case=False, regex=True)
    url_matches = working_df.loc[url_mask, 'message'].astype(str).str.findall(URL_PATTERN)
    url_exploded = url_matches.explode().dropna()
    
    if not url_exploded.empty:
        url_edges = pd.DataFrame({
            'source': working_df.loc[url_exploded.index, 'source'].values,
            'target': url_exploded.values
        })
        url_edges = url_edges[url_edges['source'] != url_edges['target']]
        all_edges_list.append(url_edges)

    if not all_edges_list:
        return pd.DataFrame(columns=['source', 'target', 'count'])

    all_edges = pd.concat(all_edges_list, ignore_index=True)
    
    counts = all_edges.groupby(['source', 'target']).size().reset_index(name='count')
    return counts.sort_values('count', ascending=False).head(100)


def compare_log_datasets(df_main, df_ref):
    """
    Compara o dataset atual (df_main) com um de referência (df_ref).
    Retorna um dicionário com métricas comparativas.
    """
    metrics = {}
    
    # 1. Volume Total
    metrics['vol_main'] = len(df_main)
    metrics['vol_ref'] = len(df_ref)
    metrics['vol_delta'] = len(df_main) - len(df_ref)
    
    # 2. Taxa de Erro
    def get_error_rate(df):
        if df.empty: return 0.0
        errs = len(df[df['log_level'].isin(['Error', 'Fail'])])
        return (errs / len(df)) * 100
        
    metrics['err_rate_main'] = get_error_rate(df_main)
    metrics['err_rate_ref'] = get_error_rate(df_ref)
    metrics['err_rate_delta'] = metrics['err_rate_main'] - metrics['err_rate_ref']
    
    # 3. Latência Média (se disponível)
    def get_avg_latency(df):
        lat = extract_latency_metrics(df)
        if lat.empty: return 0.0
        return lat['latency_ms'].mean()

    metrics['lat_main'] = get_avg_latency(df_main)
    metrics['lat_ref'] = get_avg_latency(df_ref)
    
    # 4. Novos Erros
    # Gera assinaturas para ambos
    def get_sigs(df):
        if df.empty: return set()
        # Reutiliza lógica de regex simples para assinatura
        sigs = df['message'].astype(str).str.replace(NUM_PATTERN, '<NUM>', regex=True)
        sigs = sigs.str.replace(UUID_PATTERN, '<UUID>', regex=True)
        return set(sigs.unique())

    sigs_main = get_sigs(df_main[df_main['log_level'].isin(['Error', 'Fail'])])
    sigs_ref = get_sigs(df_ref[df_ref['log_level'].isin(['Error', 'Fail'])])
    
    metrics['new_error_signatures'] = list(sigs_main - sigs_ref)
    
    return metrics


def generate_rca_prompt(df):
    """Gera um prompt para análise de causa raiz (RCA) baseada em um conjunto de logs."""
    
    # OTIMIZAÇÃO 1: Foco no presente e limite de volume para performance
    # Garante ordenação por timestamp (mais recente primeiro)
    if 'timestamp' in df.columns and not df.empty:
        df_sorted = df.sort_values('timestamp', ascending=False)
    else:
        df_sorted = df

    # Reduzido de 10k para 3k para garantir resposta rápida na UI
    if len(df_sorted) > 3000:
        working_df = df_sorted.head(3000).copy()
    else:
        working_df = df_sorted.copy()

    # 1. Tenta filtrar por Nível de Log explícito
    target_levels = ['Error', 'Fail', 'Critical', 'Fatal']
    error_df = working_df[working_df['log_level'].isin(target_levels)]
    
    # 2. Se tiver poucos erros explícitos (< 3), expande a busca para Warnings e palavras-chave
    if len(error_df) < 3:
        # Regex para capturar erros comuns mesmo em logs Info/Warning
        # Otimização: Busca apenas nos primeiros 500 chars para velocidade
        keyword_mask = working_df['message'].astype(str).str.slice(0, 500).str.contains(r'error|fail|exception|timeout|deadlock|refused|denied|fatal', case=False, regex=True)
        # Inclui Warnings na busca expandida
        expanded_mask = working_df['log_level'].isin(target_levels + ['Warning']) | keyword_mask
        error_df = working_df[expanded_mask]
    
    if error_df.empty:
        return None
        
    # OTIMIZAÇÃO 2: Limita a quantidade de erros para geração de padrões (Regex Pesado)
    # Reduzido de 500 para 100 para acelerar o processamento e reduzir tokens do prompt
    if len(error_df) > 100:
        error_df = error_df.head(100)

    total_errors = len(error_df)
    sources = list(error_df['source'].unique())[:5] # Top 5 sources afetados
    
    # Garante que timestamp é datetime para calcular janela
    if not pd.api.types.is_datetime64_any_dtype(error_df['timestamp']):
        error_df['timestamp'] = pd.to_datetime(error_df['timestamp'], errors='coerce')
    
    min_t = error_df['timestamp'].min()
    max_t = error_df['timestamp'].max()
    
    # Gera padrões dos erros para resumir o problema
    patterns = generate_log_patterns(error_df).head(7)
    patterns_summary = []
    for _, row in patterns.iterrows():
        sig = row['signature'].replace('\n', ' ').strip()[:150]
        patterns_summary.append(f"- [{row['count']}x] {sig} (Origens: {row['sources']})")
    
    patterns_text = "\n".join(patterns_summary)
    
    prompt = f"""
    Atue como um SRE Principal liderando uma War Room.
    Analise os seguintes padrões de erro extraídos de um incidente em andamento para determinar a Causa Raiz.
    
    METADADOS DO INCIDENTE:
    - Total de Erros: {total_errors}
    - Janela de Tempo: {min_t} até {max_t}
    - Sistemas Afetados: {sources}
    
    TOP PADRÕES DE ERRO IDENTIFICADOS:
    {patterns_text}
    
    ANÁLISE SOLICITADA:
    1. **Correlação:** Existe uma relação causal entre esses erros? (Ex: O erro A causou o erro B?)
    2. **Hipótese de Causa Raiz:** Qual é a causa mais provável? (Infraestrutura, Código, Banco de Dados, Terceiros?)
    3. **Plano de Ação:** Liste 3 passos técnicos imediatos para validar sua hipótese e mitigar o problema.
    
    Seja conciso, direto e técnico. Use formatação Markdown.
    """
    return prompt


def fetch_logs_from_graylog(api_url, username, password, query="*", relative=300, limit=1000, fields="timestamp,source,message"):
    """
    Busca logs usando a Service Account locktonlogs.
    username: Deve receber o seu TOKEN (15es7cbj...)
    password: Deve receber a string fixa "token"
    """
    # Limpeza de segurança para evitar espaços invisíveis ao copiar/colar
    api_url = api_url.strip().rstrip('/')
    if not api_url.endswith('/api'):
        api_url += '/api'
        
    endpoint = f"{api_url}/search/universal/relative"
    
    params = {
        "query": query,
        "range": str(relative),
        "fields": fields,
        "limit": limit 
    }
    
    try:
        # Desabilita avisos de SSL (importante para o ambiente interno da Lockton)
        requests.packages.urllib3.disable_warnings()
        
        with requests.Session() as session:
            session.auth = HTTPBasicAuth(username.strip(), password.strip())
            session.verify = False
            # Alterado para 'application/json' para obter dados mais ricos, incluindo streams.
            session.headers.update({"Accept": "application/json"})

            response = session.get(
                endpoint,
                params=params,
                timeout=30
            )
        
        response.raise_for_status()
        
        data = response.json()
        messages = data.get("messages", [])

        if not messages:
            return pd.DataFrame(), None

        # Extrai o conteúdo de cada mensagem e cria um DataFrame
        log_list = [m.get("message", {}) for m in messages]
        df = pd.DataFrame(log_list)

        # Remove a coluna _id do MongoDB, que não é útil para a análise
        if '_id' in df.columns:
            df = df.drop(columns=['_id'])

        return df, None
        
    except Exception as e:
        error_msg = str(e)
        if "getaddrinfo failed" in error_msg or "NameResolutionError" in error_msg:
            return None, f"Erro de DNS/Rede: Não foi possível encontrar o servidor Graylog. Verifique se você está conectado à VPN ou se a URL está correta. Detalhes: {error_msg}"
        return None, f"Erro na conexão: {error_msg}"

def get_graylog_node_id(api_url, username, password="token"):
    """
    Busca o Node ID do cluster Graylog via API.
    Útil para filtros gl2_source_node.
    """
    if not api_url or not username:
        return None

    api_url = api_url.strip().rstrip('/')
    if not api_url.endswith('/api'):
        api_url += '/api'
        
    endpoint = f"{api_url}/cluster/nodes"
    
    try:
        requests.packages.urllib3.disable_warnings()
        
        response = requests.get(
            endpoint,
            auth=HTTPBasicAuth(username, password),
            headers={"Accept": "application/json"},
            verify=False,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'nodes' in data and len(data['nodes']) > 0:
                return data['nodes'][0]['node_id']
        
        return None
    except Exception as e:
        print(f"Erro ao buscar Node ID: {e}")
        return None

def get_graylog_system_stats(username, password, endpoint, base_url):
    """
    Busca estatísticas de endpoints de sistema do Graylog.
    Endpoints úteis: /system/throughput, /system/journal, /cluster/nodes, /system/lbstatus
    """
    if not base_url or not username:
        return None

    api_url = base_url.strip().rstrip('/')
    if not api_url.endswith('/api'):
        api_url += '/api'
        
    # Garante que o endpoint comece com /
    if not endpoint.startswith('/'):
        endpoint = '/' + endpoint
        
    full_url = f"{api_url}{endpoint}"
    
    try:
        requests.packages.urllib3.disable_warnings()
        
        response = requests.get(
            full_url,
            auth=HTTPBasicAuth(username, password),
            headers={"Accept": "application/json"},
            verify=False,
            timeout=10
        )
        
        response.raise_for_status() # Lança exceção para status 4xx/5xx
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"Erro HTTP ao buscar stats ({full_url}): {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        print(f"Erro genérico ao buscar stats ({full_url}): {e}")
        return None

def call_graylog_api(method, endpoint, base_url, username, password, json_body=None):
    """
    Generic function to make authenticated API calls to Graylog (GET, POST, PUT, DELETE).
    """
    if not base_url or not username:
        return None, "Credenciais da API do Graylog não configuradas."

    api_url = base_url.strip().rstrip('/')
    if not api_url.endswith('/api'):
        api_url += '/api'
        
    if not endpoint.startswith('/'):
        endpoint = '/' + endpoint
        
    full_url = f"{api_url}{endpoint}"
    
    try:
        requests.packages.urllib3.disable_warnings()
        
        with requests.Session() as session:
            session.auth = HTTPBasicAuth(username.strip(), password.strip())
            session.verify = False
            session.headers.update({"Accept": "application/json", "X-Requested-By": "log-analyzer"})

            response = session.request(
                method=method.upper(),
                url=full_url,
                json=json_body,
                timeout=20
            )
        
        response.raise_for_status()
        # Some successful calls (like DELETE) might not return a body
        if response.status_code == 204 or not response.content:
            return {}, None
        
        return response.json(), None
        
    except requests.exceptions.HTTPError as e:
        error_text = e.response.text
        try:
            error_json = e.response.json()
            error_msg = error_json.get("message", error_text)
        except json.JSONDecodeError:
            error_msg = error_text
        return None, f"Erro na API Graylog: {e.response.status_code} - {error_msg}"
    except Exception as e:
        return None, f"Erro de conexão com a API Graylog: {e}"

def get_graylog_cluster_nodes(api_url, username, password):
    """Busca a lista de nós e seus IDs no cluster Graylog."""
    if not api_url or not username:
        return []
    
    api_url = api_url.strip().rstrip('/')
    if not api_url.endswith('/api'):
        api_url += '/api'
        
    endpoint = f"{api_url}/cluster"
    
    try:
        requests.packages.urllib3.disable_warnings()
        response = requests.get(
            endpoint,
            auth=HTTPBasicAuth(username.strip(), password.strip()),
            headers={"Accept": "application/json"},
            verify=False,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        nodes = data.get("nodes", [])
        # Retorna apenas nós que estão vivos
        alive_nodes = [node for node in nodes if node.get('is_alive')]
        return alive_nodes
    except Exception as e:
        print(f"Erro ao buscar nós do cluster: {e}")
        return []

def get_graylog_streams_with_throughput(api_url, username, password):
    """
    Busca streams ativas e combina com seus dados de throughput.
    """
    if not api_url or not username:
        return [], "Credenciais da API do Graylog não configuradas."

    # 1. Buscar todas as streams ativas
    streams_data = get_graylog_system_stats(username, password, "/streams/enabled", api_url)
    if streams_data is None:
        return [], "Falha ao buscar streams do Graylog. Verifique a conexão e permissões."
    
    # 2. Throughput por stream (Removido chamada inválida /streams/throughput que causava 404)
    throughput_map = {}

    # 3. Combinar os dados
    combined_streams = []
    for stream in streams_data.get("streams", []):
        stream_id = stream.get("id")
        stream_throughput = throughput_map.get(stream_id, 0)
        
        stream['throughput'] = stream_throughput
        combined_streams.append(stream)
        
    return sorted(combined_streams, key=lambda x: x.get('throughput', 0), reverse=True), None

def get_graylog_stream_details(api_url, username, password, stream_id):
    """
    Busca detalhes e regras de uma stream específica.
    """
    # A função call_graylog_api já lida com erros, então podemos simplificar.
    details, err1 = call_graylog_api('GET', f"/streams/{stream_id}", api_url, username, password)
    if err1:
        return None, f"Falha ao buscar detalhes da stream: {err1}"

    rules, err2 = call_graylog_api('GET', f"/streams/{stream_id}/rules", api_url, username, password)
    if err2:
        return None, f"Falha ao buscar regras da stream: {err2}"

    # Combina os resultados em um único objeto para o frontend
    details['rules'] = rules.get('stream_rules', [])
    return details, None

def get_graylog_alert_definitions(api_url, username, password):
    """Busca todas as definições de alerta (regras) do Graylog."""
    return call_graylog_api('GET', "/events/definitions", api_url, username, password)

def get_graylog_triggered_alerts(api_url, username, password):
    """Busca os alertas disparados recentemente."""
    # Usamos o paginated para ter mais controle, mas por simplicidade pegamos a primeira página
    return call_graylog_api('GET', "/streams/alerts/paginated?page=1&per_page=50", api_url, username, password)

def toggle_graylog_alert_schedule(api_url, username, password, alert_id, enable):
    """Ativa ou desativa o agendamento de um alerta."""
    method = 'PUT' if enable else 'DELETE'
    endpoint = f"/events/definitions/{alert_id}/schedule"
    return call_graylog_api(method, endpoint, api_url, username, password)

def execute_graylog_alert_test(api_url, username, password, alert_id):
    """Executa a verificação de um alerta manualmente."""
    endpoint = f"/events/definitions/{alert_id}/execute"
    return call_graylog_api('POST', endpoint, api_url, username, password)

def test_log_parsing(api_url, username, password, raw_message):
    """Testa o parsing de uma mensagem raw no Graylog usando o endpoint /messages/parse."""
    endpoint = "/messages/parse"
    payload = {
        "message": raw_message,
        "codec": "json",
        "config": {},
        "gelf": False,
        "raw": True
    }
    return call_graylog_api('POST', endpoint, api_url, username, password, json_body=payload)

def fetch_infrastructure_metrics_from_graylog(api_url, username, password):
    """
    Busca métricas de infraestrutura (CPU, Memória, etc.) diretamente do nó Graylog conectado.
    Esta é uma abordagem mais confiável do que extrair de logs.
    """
    # Busca as métricas usando os endpoints corretos para o nó conectado
    os_stats = get_graylog_system_stats(username, password, endpoint="/system/stats/os", base_url=api_url)
    
    # Se não conseguir pegar nem o OS stats, provavelmente não há conexão.
    if not os_stats:
        return pd.DataFrame(), "Não foi possível buscar estatísticas do sistema do nó Graylog. Verifique a URL da API e as permissões do token."

    jvm_stats = get_graylog_system_stats(username, password, endpoint="/system/stats/jvm", base_url=api_url)
    fs_stats = get_graylog_system_stats(username, password, endpoint="/system/stats/fs", base_url=api_url)
    journal_stats = get_graylog_system_stats(username, password, endpoint="/system/journal", base_url=api_url)
    lb_status = get_graylog_system_stats(username, password, endpoint="/system/lbstatus", base_url=api_url)

    all_metrics = []
    now = datetime.now().isoformat()
    hostname = os_stats.get("node_id", get_host_from_url(api_url))

    # Processa as métricas
    cpu_usage_percent = 0
    if os_stats and "os" in os_stats:
        cpu_cores = os_stats["os"].get("processors", 1)
        load_1m = os_stats["os"].get("load_average", {}).get("1m", 0.0)
        cpu_usage_percent = (load_1m / cpu_cores) * 100 if cpu_cores > 0 else 0

    mem_usage_percent = 0
    if jvm_stats and "jvm" in jvm_stats:
        heap_used = jvm_stats["jvm"].get("memory", {}).get("heap", {}).get("used_bytes", 0)
        heap_max = jvm_stats["jvm"].get("memory", {}).get("heap", {}).get("max_bytes", 1)
        mem_usage_percent = (heap_used / heap_max) * 100 if heap_max > 0 else 0

    disk_usage_percent = 0
    if fs_stats and "fs" in fs_stats and "total" in fs_stats["fs"]:
        total_bytes = fs_stats["fs"]["total"].get("total_in_bytes", 1)
        free_bytes = fs_stats["fs"]["total"].get("free_in_bytes", 0)
        disk_usage_percent = ((total_bytes - free_bytes) / total_bytes) * 100 if total_bytes > 0 else 0
    
    journal_uncommitted = journal_stats.get("uncommitted_entries", 0) if journal_stats else 0
    node_lb_status = lb_status.get("status", "UNKNOWN").upper() if lb_status else "UNKNOWN"

    all_metrics.append({
        "timestamp": now, 
        "source": hostname, 
        "cpu": round(cpu_usage_percent, 2), 
        "memory": round(mem_usage_percent, 2), 
        "disk": round(disk_usage_percent, 2),
        "journal_uncommitted": journal_uncommitted,
        "lb_status": node_lb_status
    })
            
    return pd.DataFrame(all_metrics), None

def get_host_from_url(url):
    """Extrai o hostname de uma URL (ex: http://graylog:9000/api -> graylog)."""
    if not url: return "127.0.0.1"
    try:
        # Remove protocol
        if "://" in url:
            url = url.split("://")[1]
        # Remove path
        if "/" in url:
            url = url.split("/")[0]
        # Remove port
        if ":" in url:
            url = url.split(":")[0]
        return url
    except:
        return "127.0.0.1"

def send_gelf_message(host, port, short_message, full_message=None, level=1, extra_fields=None, source_name=None):
    """Envia uma mensagem no formato GELF via UDP (com compressão zlib)."""
    try:
        gelf_data = {
            "version": "1.1",
            "host": source_name if source_name else socket.gethostname(),
            "short_message": short_message,
            "full_message": full_message if full_message else short_message,
            "level": level,
            "timestamp": datetime.now().timestamp()
        }
        
        if extra_fields:
            for k, v in extra_fields.items():
                # GELF exige que campos extras comecem com _
                key = f"_{k}" if not k.startswith("_") else k
                gelf_data[key] = v

        # Serializa e Comprime (ZLIB)
        payload = json.dumps(gelf_data).encode('utf-8')
        compressed_payload = zlib.compress(payload)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(compressed_payload, (host, int(port)))
        sock.close()
        return True, None
    except Exception as e:
        return False, str(e)

def send_jira_automation_webhook(webhook_url, summary, description, email="dashboard@lockton.com", survey_link="", attachments=None, api_key=None):
    """Envia dados para um Webhook de Automação do Jira."""
    
    if webhook_url:
        webhook_url = webhook_url.strip()

    # Correção Automática: Jira Automation exige o token na URL (?token=XYZ).
    # Se o usuário passou o token via api_key mas esqueceu de por na URL, ajustamos aqui.
    if "token=" not in webhook_url and api_key:
        separator = "&" if "?" in webhook_url else "?"
        webhook_url = f"{webhook_url}{separator}token={api_key}"

    payload = {
        "webhookData": {
            "Summary": summary,
            "Description": description,
            "Email": email,
            "SurveyLink": survey_link,
            "Attachment": attachments if attachments else []
        }
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["X-Api-Key"] = api_key
        
    try:
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        
        if response.status_code not in [200, 201, 202]:
            return None, f"Erro {response.status_code}: {response.text}"
            
        return {"status": "success"}, None
    except Exception as e:
        return None, str(e)


def get_context_logs(df, target_timestamp, source, window_seconds=300):
    """
    Recupera logs do mesmo source em uma janela de tempo ao redor do evento (Contexto).
    """
    if df.empty:
        return pd.DataFrame()
        
    # Garante datetime
    df_ctx = df.copy()
    df_ctx['timestamp'] = pd.to_datetime(df_ctx['timestamp'], errors='coerce')
    target_ts = pd.to_datetime(target_timestamp)
    
    # Filtra por source e janela de tempo (+/- 5 min por padrão)
    start_time = target_ts - pd.Timedelta(seconds=window_seconds)
    end_time = target_ts + pd.Timedelta(seconds=window_seconds)
    
    # Filtra logs do mesmo source dentro da janela
    context = df_ctx[
        (df_ctx['source'] == source) & 
        (df_ctx['timestamp'] >= start_time) & 
        (df_ctx['timestamp'] <= end_time)
    ]
    return context.sort_values('timestamp')


def generate_pdf_report(df, anomalies, rare_logs, charts_dict, ai_analyses=None):
    """
    Gera um relatório PDF contendo estatísticas, gráficos e anomalias.
    Requer: pip install fpdf vl-convert-python
    """
    try:
        from fpdf import FPDF
        import vl_convert as vlc
    except ImportError:
        return None, "Bibliotecas 'fpdf' ou 'vl-convert-python' não instaladas. Instale-as para gerar o PDF."

    class PDF(FPDF):
        def header(self):
            # Adiciona Logo se existir (lockton_logo.png na raiz)
            logo_path = "lockton_logo.png"
            if os.path.exists(logo_path):
                self.image(logo_path, 10, 8, 33) # x, y, w
                self.set_font('Arial', 'B', 15)
                self.cell(0, 10, 'Relatorio de Analise de Logs', 0, 1, 'C')
                self.ln(12)
            else:
                self.set_font('Arial', 'B', 15)
                self.cell(0, 10, 'Relatorio de Analise de Logs', 0, 1, 'C')
                self.ln(5)
        
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # 1. Resumo Estatístico
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "1. Resumo Estatistico", 0, 1)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, f"Total de Logs: {len(df)}", 0, 1)
    
    counts = df['log_level'].value_counts()
    dist_text = ", ".join([f"{k}: {v}" for k, v in counts.items()])
    pdf.multi_cell(0, 10, f"Distribuicao: {dist_text}")
    pdf.ln(5)

    # 2. Gráficos
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "2. Visualizacoes", 0, 1)
    
    for title, chart in charts_dict.items():
        if chart:
            pdf.set_font("Arial", 'I', 10)
            pdf.cell(0, 10, title, 0, 1)
            try:
                # Converte Altair para PNG usando vl-convert
                png_data = vlc.vegalite_to_png(chart.to_json())
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(png_data)
                    tmp_path = tmp.name
                
                pdf.image(tmp_path, x=10, w=90)
                os.unlink(tmp_path) # Remove arquivo temporário
            except Exception as e:
                pdf.cell(0, 10, f"Erro ao renderizar grafico: {str(e)}", 0, 1)
            pdf.ln(5)

    # 3. Anomalias
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "3. Anomalias Detectadas", 0, 1)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, "Anomalias de Volume:", 0, 1)
    pdf.set_font("Arial", size=10)
    
    if not anomalies.empty:
        pdf.cell(0, 10, f"Total detectado: {len(anomalies)}", 0, 1)
        for idx, row in anomalies.head(20).iterrows(): # Limita a 20 para não estourar o PDF
            pdf.cell(0, 10, f"- {row['timestamp']}: {row['count']} logs", 0, 1)
    else:
        pdf.cell(0, 10, "Nenhuma anomalia de volume detectada.", 0, 1)

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, "Padroes Raros:", 0, 1)
    pdf.set_font("Arial", size=10)

    if not rare_logs.empty:
        pdf.cell(0, 10, f"Total detectado: {len(rare_logs)}", 0, 1)
        for idx, row in rare_logs.head(10).iterrows():
            msg_preview = row['message'][:80] + "..."
            pdf.cell(0, 10, f"- [{row['log_level']}] {msg_preview}", 0, 1)
    else:
        pdf.cell(0, 10, "Nenhum padrao raro detectado.", 0, 1)

    # 4. Análise de IA (Erros Críticos)
    if ai_analyses:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "4. Analise de IA (Erros Criticos)", 0, 1)
        
        for analysis in ai_analyses:
            pdf.set_font("Arial", 'B', 10)
            ts = str(analysis.get('timestamp', 'N/A'))
            pdf.cell(0, 10, f"Timestamp: {ts}", 0, 1)
            
            pdf.set_font("Arial", 'I', 9)
            # Sanitização básica para fontes padrão do FPDF (Latin-1)
            msg = str(analysis.get('log_message', ''))[:200].replace('\n', ' ').encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 5, f"Log: {msg}...")
            
            pdf.ln(2)
            pdf.set_font("Arial", size=9)
            ai_text = str(analysis.get('ai_analysis', '')).replace('**', '').replace('##', '').encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 5, f"Analise: {ai_text}")
            pdf.ln(5)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)

    # fpdf2 retorna bytes diretamente via output()
    return bytes(pdf.output()), None

# --- FUNÇÕES DE MÉTRICAS CUSTOMIZADAS ---

def save_metric_definition(name, regex, metric_type="counter", threshold=0.0):
    """Salva uma nova definição de métrica customizada."""
    return True, "Métrica salva em memória (não persistida)."


def get_metric_definitions():
    """Retorna todas as métricas configuradas."""
    return pd.DataFrame()


def delete_metric_definition(metric_id):
    """Remove uma métrica e seus dados históricos."""
    pass


def extract_and_save_metrics(df):
    """
    Processa um DataFrame de logs, aplica as regex das métricas ativas 
    e salva os valores encontrados no banco.
    """
    return 0


def get_metric_history(metric_id, days=7):
    """Recupera histórico de uma métrica para gráficos."""
    return pd.DataFrame()


# --- FUNÇÕES RUM (REAL USER MONITORING) ---

def extract_rum_metrics(df):
    """
    Extrai métricas de RUM (Real User Monitoring) e Erros JS dos logs.
    Suporta padrões como:
    - "RUM: metric=LCP value=1200"
    - "Frontend Error: ReferenceError is not defined"
    """
    if df.empty:
        return pd.DataFrame()

    rum_data = []
    
    # 1. Web Vitals (LCP, FID, CLS, INP)
    # Regex flexível para capturar métricas de performance frontend
    # Ex: "LCP: 2.5s", "metric=CLS value=0.1", "FCP=100ms"
    vitals_pattern = re.compile(r'(LCP|FID|CLS|FCP|TTFB|INP)\s*[:=]\s*(\d+(?:\.\d+)?)', re.IGNORECASE)
    
    # 2. Erros JavaScript
    # Ex: "Uncaught TypeError", "ReferenceError", "React Error"
    js_error_pattern = re.compile(r'(TypeError|ReferenceError|SyntaxError|RangeError|URIError|React Error)', re.IGNORECASE)

    for _, row in df.iterrows():
        msg = str(row['message'])
        
        # Extrai Vitals
        vitals = vitals_pattern.findall(msg)
        for name, value in vitals:
            rum_data.append({
                'timestamp': row['timestamp'],
                'type': 'vital',
                'name': name.upper(),
                'value': float(value),
                'details': msg[:50]
            })
            
        # Extrai Erros JS
        js_errors = js_error_pattern.findall(msg)
        for err in js_errors:
            rum_data.append({
                'timestamp': row['timestamp'],
                'type': 'js_error',
                'name': err,
                'value': 1,
                'details': msg
            })
            
    return pd.DataFrame(rum_data)

def run_synthetic_check(name, url):
    """
    Executa uma verificação sintética (ping HTTP) e registra o resultado.
    """
    try:
        start = datetime.now()
        response = requests.get(url, timeout=10)
        duration = (datetime.now() - start).total_seconds() * 1000
        
        status = "SUCCESS" if response.status_code == 200 else f"FAILURE ({response.status_code})"
        message = f"SYNTHETIC | Check: {name} | URL: {url} | Status: {status} | Duration: {duration:.2f}ms"
        
    except Exception as e:
        message = f"SYNTHETIC | Check: {name} | URL: {url} | Status: ERROR | Error: {str(e)}"

    # Cria DataFrame para ingestão
    df = pd.DataFrame([{
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "source": "Synthetic-Monitor",
        "message": message
    }])
    
    # Ingestão usando a função existente
    ingest_logs_to_db(df)

def check_api_health(url, timeout=5):
    """
    Realiza um Health Check (GET) em uma URL externa para verificar se o serviço está online.
    Retorna um dicionário com o status da conexão.
    """
    try:
        start = datetime.now()
        response = requests.get(url, timeout=timeout)
        latency = (datetime.now() - start).total_seconds() * 1000
        
        return {
            "online": 200 <= response.status_code < 300,
            "status_code": response.status_code,
            "latency_ms": round(latency, 2),
            "error": None
        }
    except Exception as e:
        return {
            "online": False,
            "status_code": 0,
            "latency_ms": 0,
            "error": str(e)
        }

def format_graylog_table(row):
    """
    Formata uma linha de log (Series/Dict) em uma tabela Markdown para alertas do Teams.
    Chamado pelo scheduler.py ao detectar erro crítico.
    """
    try:
        # Seleciona campos relevantes para o alerta
        fields = {
            "Timestamp": str(row.get('timestamp', 'N/A')),
            "Source": str(row.get('source', 'N/A')),
            "Level": str(row.get('log_level', row.get('level', 'N/A'))),
            "Container": str(row.get('container_name', 'N/A')),
            "Message": str(row.get('message', ''))
        }
        
        md_table = "| Campo | Valor |\n|---|---|\n"
        for k, v in fields.items():
            md_table += f"| **{k}** | {v} |\n"
            
        return md_table
    except Exception as e:
        return f"Erro ao formatar tabela: {e}"

def save_to_disk(): pass
def load_from_disk(): pass

def compute_api_stats(api_df):
    """
    Calcula estatísticas agregadas a partir de um DataFrame de métricas de API.
    """
    if api_df.empty:
        return {
            "stats": {"total": 0, "success": 0, "client_error": 0, "server_error": 0, "avg_latency": 0},
            "status_counts": [],
            "method_counts": [],
            "top_endpoints": [],
            "slowest_endpoints": []
        }
    
    # Stats
    total = len(api_df)
    s_codes = pd.to_numeric(api_df['status_code'], errors='coerce').fillna(0)
    
    # Estatísticas de latência
    valid_latency = api_df['latency_ms'].dropna()
    avg_latency = round(valid_latency.mean(), 2) if not valid_latency.empty else 0
    
    stats = {
        "total": total,
        "success": int(((s_codes >= 200) & (s_codes < 300)).sum()),
        "client_error": int(((s_codes >= 400) & (s_codes < 500)).sum()),
        "server_error": int(((s_codes >= 500) & (s_codes < 600)).sum()),
        "avg_latency": avg_latency
    }
    
    # Agregações para Gráficos
    df = api_df.copy()
    df['status_code'] = df['status_code'].fillna('Unknown')
    
    status_counts = df['status_code'].value_counts().reset_index(name='count').rename(columns={'index': 'code', 'status_code': 'code'})
    method_counts = df['method'].value_counts().reset_index(name='count').rename(columns={'index': 'method', 'method': 'method'})
    top_endpoints = df['endpoint'].value_counts().head(10).reset_index(name='count').rename(columns={'index': 'endpoint', 'endpoint': 'endpoint'})
    
    # Nova agregação: Endpoints mais lentos (baseado no P95)
    slowest_endpoints = pd.DataFrame()
    if 'latency_ms' in api_df.columns and not api_df['latency_ms'].dropna().empty:
        slowest_endpoints = df.groupby('endpoint').agg(
            p95_latency=('latency_ms', lambda x: x.quantile(0.95)),
            avg_latency=('latency_ms', 'mean'),
            max_latency=('latency_ms', 'max'),
            count=('latency_ms', 'count')
        ).reset_index().sort_values('p95_latency', ascending=False).head(5)
        
        # Arredonda valores para uma resposta mais limpa
        for col in ['p95_latency', 'avg_latency', 'max_latency']:
            slowest_endpoints[col] = slowest_endpoints[col].round(2)

        # Adiciona o log representativo (mais lento) para cada endpoint (para exibir no modal ao clicar)
        slowest_logs = []
        for ep in slowest_endpoints['endpoint']:
            ep_logs = df[df['endpoint'] == ep]
            if not ep_logs.empty and 'latency_ms' in ep_logs.columns:
                valid_latencies = ep_logs['latency_ms'].dropna()
                if not valid_latencies.empty:
                    slowest_idx = valid_latencies.idxmax()
                    row = ep_logs.loc[slowest_idx]
                    slowest_logs.append({
                        "timestamp": str(row.get('timestamp', '')),
                        "source": str(row.get('source', '')),
                        "log_level": str(row.get('log_level', 'Info')),
                        "category": str(row.get('category', 'API')),
                        "message": str(row.get('message', ''))
                    })
                else:
                    slowest_logs.append({})
            else:
                slowest_logs.append({})
                
        slowest_endpoints['slowest_log'] = slowest_logs

    return {
        "stats": stats,
        "status_counts": status_counts.to_dict(orient='records'),
        "method_counts": method_counts.to_dict(orient='records'),
        "top_endpoints": top_endpoints.to_dict(orient='records'),
        "slowest_endpoints": slowest_endpoints.fillna(0).to_dict(orient='records')
    }

def compute_data_summary(df):
    """
    Calcula o resumo dos dados para o dashboard (Volume, Erros, Sources).
    Desacoplado da API para facilitar testes e reutilização.
    """
    if df is None or df.empty:
        return {
            "total_logs": 0,
            "error_count": 0,
            "error_rate": 0,
            "unique_sources": 0
        }

    total_logs = len(df)
    
    # Contagem rápida de erros
    error_count = 0
    if 'log_level' in df.columns:
        error_count = int(df['log_level'].isin(['Error', 'Fail', 'Critical', 'Fatal']).sum())
        
    error_rate = round((error_count / total_logs * 100), 2) if total_logs > 0 else 0
    unique_sources = int(df['source'].nunique()) if 'source' in df.columns else 0
    
    return {
        "total_logs": total_logs,
        "error_count": error_count,
        "error_rate": error_rate,
        "unique_sources": unique_sources
    }

def compute_volume_series(df):
    """
    Calcula apenas a série temporal de volume (Gráfico).
    Separado para otimização de performance.
    """
    if df is None or df.empty:
        return {"time_series_volume": []}
    
    # Time Series com Amostragem Adaptativa (Fix para lentidão externa)
    time_series = []
    if 'timestamp' in df.columns:
        # Conversão segura e tratamento de NA
        ts_data = pd.to_datetime(df['timestamp'], errors='coerce').dropna()
        
        if not ts_data.empty:
            duration = ts_data.max() - ts_data.min()
            
            # Seleciona granularidade baseada na duração total para otimizar payload
            if duration > pd.Timedelta(days=60): rule = 'D'     # > 2 meses: Diário
            elif duration > pd.Timedelta(days=7): rule = '4H'   # > 1 semana: 4 horas
            elif duration > pd.Timedelta(days=2): rule = '1H'   # > 2 dias: 1 hora
            elif duration > pd.Timedelta(hours=12): rule = '15T'# > 12h: 15 min
            elif duration > pd.Timedelta(hours=1): rule = 'T'   # > 1h: 1 min
            else: rule = '10S'                                  # < 1h: 10 seg
            
            ts_counts = ts_data.groupby(ts_data.dt.floor(rule)).size().reset_index(name='count')
            ts_counts['timestamp'] = ts_counts['timestamp'].astype(str)
            time_series = ts_counts.to_dict(orient='records')

    return {"time_series_volume": time_series}