# -*- coding: utf-8 -*-
"""
Módulo para integrações com serviços externos como Graylog, Jira e webhooks.
"""
import requests
import os
from requests.auth import HTTPBasicAuth
import pandas as pd
import io
import socket
import zlib
import json
import hashlib
from datetime import datetime

def format_graylog_table(log_row):
    """Formata uma linha de log para exibição em tabela no Webhook (Teams/Slack)."""
    # Lista de campos baseada na configuração do Graylog
    labels = [
        "command", "container_id", "container_name", "created", 
        "gl2_processing_error", "image_id", "image_name", 
        "level", "LogLevel", "message", "source", "tag", "RequestPath",
        "cpu_valor", "mem_valor"
    ]
    
    output = []
    for label in labels:
        # Tratamento seguro para Pandas Series ou Dict
        if isinstance(log_row, pd.Series):
            valor = log_row[label] if label in log_row.index and pd.notna(log_row[label]) else "N/A"
        else:
            valor = log_row.get(label, "N/A")
            
        if pd.isna(valor) or str(valor).strip() == "":
            valor = "N/A"
            
        # Formatação: Label em negrito, Valor em nova linha com bloco de código
        output.append(f"**{label}**\n`{valor}`")
    
    return "\n\n".join(output)

def send_webhook_alert(webhook_url, message, title="🚨 Alerta de Log"):
    """
    Envia um alerta formatado para Microsoft Teams ou um webhook genérico (Slack/Discord).
    """
    if not webhook_url:
        return "URL do webhook não fornecida."

    # Lógica ajustada: Assume Teams (MessageCard) como padrão, a menos que seja Slack/Discord
    # Isso garante que URLs de Power Automate ou domínios customizados do Teams funcionem.
    if not any(domain in webhook_url for domain in ["slack.com", "discord.com", "discordapp.com"]):
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "d9534f",
            "summary": title,
            "sections": [{"activityTitle": title, "text": message, "markdown": True}]
        }
    else:
        payload = {"text": f"*{title}*\n{message}"}
        
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        return f"Falha no envio do webhook: {e}"

def fetch_logs_from_graylog(api_url, username, password, query="*", relative=300, limit=1000, fields="timestamp,source,message"):
    """
    Busca logs da API do Graylog usando uma conta de serviço (token).
    """
    if not api_url:
        return None, "URL da API do Graylog não configurada."

    api_url = api_url.strip().rstrip('/') + ('/api' if not api_url.endswith('/api') else '')
    endpoint = f"{api_url}/search/universal/relative"
    
    params = {"query": query, "range": str(relative), "fields": fields, "limit": limit}
    
    try:
        requests.packages.urllib3.disable_warnings()
        with requests.Session() as session:
            session.auth = HTTPBasicAuth(username.strip(), password.strip())
            session.verify = False
            response = session.get(endpoint, params=params, headers={"Accept": "text/csv"}, timeout=30)
        response.raise_for_status()
        return pd.read_csv(io.StringIO(response.text)) if response.text.strip() else pd.DataFrame(), None
    except requests.exceptions.RequestException as e:
        return None, f"Erro de conexão com Graylog: {e}"

def get_graylog_node_id(api_url, username, password="token"):
    """Busca o Node ID de um cluster Graylog."""
    if not api_url or not username: return None
    api_url = api_url.strip().rstrip('/') + ('/api' if not api_url.endswith('/api') else '')
    endpoint = f"{api_url}/cluster/nodes"
    
    try:
        requests.packages.urllib3.disable_warnings()
        response = requests.get(endpoint, auth=HTTPBasicAuth(username, password), headers={"Accept": "application/json"}, verify=False, timeout=10)
        if response.status_code == 200:
            return response.json().get('nodes', [{}])[0].get('node_id')
        return None
    except requests.exceptions.RequestException:
        return None

def send_gelf_message(host, port, short_message, full_message=None, level=1, extra_fields=None, source_name=None):
    """Envia uma mensagem formatada em GELF via UDP."""
    try:
        gelf_data = {
            "version": "1.1", "host": source_name or socket.gethostname(),
            "short_message": short_message, "full_message": full_message or short_message,
            "level": level, "timestamp": datetime.now().timestamp(),
        }
        if extra_fields:
            gelf_data.update({f"_{k}": v for k, v in extra_fields.items()})
        payload = zlib.compress(json.dumps(gelf_data).encode('utf-8'))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(payload, (host, int(port)))
        return True, None
    except Exception as e:
        return False, str(e)

def get_host_from_url(url):
    """Extrai o hostname de uma URL."""
    if not url: return "127.0.0.1"
    try:
        return url.split("://")[1].split("/")[0].split(":")[0]
    except:
        return "127.0.0.1"

def calculate_file_hash(file_content):
    """Calcula o hash SHA-256 de um conteúdo de arquivo."""
    return hashlib.sha256(file_content).hexdigest()

def send_jira_automation_webhook(webhook_url, summary, description, email="dashboard@lockton.com", survey_link="http://10.130.0.20:8051/", attachments=None, api_key=None):
    """Envia dados para um webhook de automação do Jira."""
    if not webhook_url: return None, "URL do webhook do Jira não fornecida."
    webhook_url = webhook_url.strip()
    
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-Automation-Webhook-Token"] = api_key

    # Limpa a descrição para remover prefixos de teste como (teste) e caracteres especiais como #.
    cleaned_description = description.replace('#', '').replace('(teste)', '')

    payload = {"data": {
        "Summary": summary, "Description": cleaned_description, "Email": email,
        "surveyLink": survey_link, "Attachment": attachments or []
    }}
    
    try:
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        return {"status": "success"}, None
    except requests.exceptions.RequestException as e:
        return None, f"Erro ao enviar para o webhook do Jira: {e}"

def get_graylog_system_stats(api_url, username, password, endpoint="/system/lbstatus"):
    """
    Busca estatísticas de endpoints de sistema do Graylog.
    Endpoints úteis: /system/throughput, /system/journal, /cluster/nodes, /system/lbstatus
    """
    if not api_url or not username:
        return None

    api_url = api_url.strip().rstrip('/')
    if not api_url.endswith('/api'):
        api_url += '/api'
    if not endpoint.startswith('/'):
        endpoint = '/' + endpoint
    full_url = f"{api_url}{endpoint}"
    
    try:
        requests.packages.urllib3.disable_warnings()
        response = requests.get(
            full_url, auth=HTTPBasicAuth(username, password),
            headers={"Accept": "application/json"}, verify=False, timeout=10
        )
        return response.json() if response.status_code == 200 else None
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar stats ({endpoint}): {e}")
        return None