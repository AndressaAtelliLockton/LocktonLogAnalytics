# -*- coding: utf-8 -*-
"""
Módulo para todas as interações com modelos de IA (Groq).
"""
import os
from groq import Groq
from . import database as db
from . import log_parser as analysis

def generate_initial_prompt(log_message):
    """
    Cria o prompt inicial detalhado para a análise de um log pela IA.
    Instrui o modelo a agir como um SRE e a fornecer uma resposta estruturada.
    """
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
        3. SOLUÇÃO TÉCNICA APLICÁVEL: Apresente a correção exata (código, comando ou configuração) para resolver o problema.
        4. RESULTADOS DA IMPLEMENTAÇÃO (Melhorias Práticas):
           - Logging Estruturado: Gere o JSON estruturado final para este log.
           - Monitoramento de Desempenho: Defina a métrica exata e o limiar (threshold) crítico a ser configurado.
           - Documentação: Forneça o texto exato para atualização da Base de Conhecimento (KB).
           - Automação: Escreva a Regex ou Query exata para criar o alerta.

        5. TICKET JIRA (Rascunho):
           Gere um exemplo de ticket para o Jira com base nesta análise, formatado em Markdown.
        
        Responda em Português de forma técnica e clara.
        """

def send_chat_message(messages, model_name='llama-3.3-70b-versatile'):
    """
    Envia uma lista de mensagens para a API da Groq e retorna a resposta do modelo.
    """
    api_key = os.environ.get("GROQ_API_KEY") or db.get_setting("groq_api_key")
    
    if not api_key:
        return "Erro: Chave de API da Groq não configurada."

    client = Groq(api_key=api_key, timeout=30.0)
    
    try:
        chat_completion = client.chat.completions.create(
            messages=messages,
            model=model_name,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"Erro na comunicação com a API da Groq: {str(e)}"

def analyze_log_with_ai(log_message, model_name='llama-3.3-70b-versatile'):
    """
    Função de conveniência para analisar uma única mensagem de log com a IA.
    """
    prompt = generate_initial_prompt(log_message)
    messages = [{"role": "user", "content": prompt}]
    return send_chat_message(messages, model_name)

def generate_rca_prompt(df):
    """
    Gera um prompt para Análise de Causa Raiz (RCA) com base em um DataFrame de logs de erro.
    """
    # Foca nos logs mais recentes e de maior severidade
    error_df = df[df['log_level'].isin(['Error', 'Fail', 'Critical', 'Fatal'])].copy()
    if len(error_df) < 3:
        error_df = df[df['log_level'].isin(['Error', 'Fail', 'Critical', 'Fatal', 'Warning'])].copy()
    
    if error_df.empty:
        return None
        
    # Limita a quantidade de dados para performance e custo de tokens
    error_df = error_df.sort_values('timestamp', ascending=False).head(100)

    # Gera um resumo dos padrões de erro
    patterns = analysis.generate_log_patterns(error_df).head(7)
    if patterns.empty:
        return None

    patterns_summary = "\n".join([f"- [{row['count']}x] {row['signature']}" for _, row in patterns.iterrows()])
    
    prompt = f"""
    Atue como um SRE Principal em uma sala de guerra de incidente.
    Analise os seguintes padrões de erro para determinar a Causa Raiz.
    
    Resumo do Incidente:
    - Total de Erros Analisados: {len(error_df)}
    - Janela de Tempo: {error_df['timestamp'].min()} a {error_df['timestamp'].max()}
    - Sistemas Afetados: {list(error_df['source'].unique())}
    
    Padrões de Erro Principais:
    {patterns_summary}
    
    Sua Análise:
    1. **Correlação:** Há uma relação causal entre os erros?
    2. **Hipótese de Causa Raiz:** Qual a causa provável (Código, Infra, BD, etc.)?
    3. **Plano de Ação Imediato:** Liste 3 passos técnicos para validar a hipótese e mitigar.
    """
    return prompt

def analyze_critical_logs_with_ai(df, model_name='llama-3.3-70b-versatile'):
    """
    Filtra logs críticos de um DataFrame e analisa cada um com a IA.
    Retorna uma lista de dicionários com a análise de cada log.
    """
    # Heuristic for identifying critical log levels or categories from the processed dataframe.
    # It's assumed 'log_level' or 'category' column exists.
    
    critical_markers = ['error', 'fail', 'critical', 'fatal', 'warning', 'unknown', 'uncategorized']
    
    # Prefer 'log_level' but fall back to 'category'
    column_to_check = None
    if 'log_level' in df.columns:
        column_to_check = 'log_level'
    elif 'category' in df.columns:
        column_to_check = 'category'

    if not column_to_check:
        return []

    # Ensure the target column is of string type for .str accessor
    df[column_to_check] = df[column_to_check].astype(str)

    critical_df = df[df[column_to_check].str.lower().isin(critical_markers)]

    if critical_df.empty:
        return []

    analyses = []
    # Limit number of analyses to avoid long waits and high costs.
    for _, row in critical_df.head(5).iterrows():
        log_message = row['message']
        ai_analysis = analyze_log_with_ai(log_message, model_name)
        
        analyses.append({
            'timestamp': row['timestamp'],
            'log_message': log_message,
            'ai_analysis': ai_analysis
        })
        
    return analyses
