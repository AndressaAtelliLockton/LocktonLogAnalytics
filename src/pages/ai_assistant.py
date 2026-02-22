# -*- coding: utf-8 -*-
"""
Módulo para renderizar a seção de Análise de IA, o chat interativo e a integração com o Jira.
"""

import streamlit as st
import log_analyzer as lam
import re
import os

def extract_jira_section(text):
    """
    Extrai e limpa a seção "TICKET JIRA" da resposta da IA para preencher
    o formulário de criação de ticket. Remove textos indesejados, rodapés,
    e instruções de prompt que possam ter vazado na resposta.
    """
    if not text: return ""
    # Regex para encontrar o cabeçalho "5. TICKET JIRA (Rascunho):" ou variações
    # Atualizado para incluir o título e suportar formatação Markdown (**Title**)
    match = re.search(r"(?:5\.\s*)?TICKET JIRA \(Rascunho\)(?:\*\*)?:?\s*", text, re.IGNORECASE)
    if match:
        # Retorna a partir do início do match para incluir o título
        content = text[match.start():].strip()
    else:
        content = text

    # --- Lógica de Corte ---
    # Encontra a linha da Prioridade e garante que o texto termine logo após o valor dela.
    # Isso remove rodapés, assinaturas da IA ou instruções de prompt vazadas.
    priority_match = re.search(r"(Prioridade Sugerida.*?)(?:\n|$)", content, re.IGNORECASE)
    
    if priority_match:
        # Pega o índice onde termina a linha da "Prioridade Sugerida"
        cutoff_index = priority_match.end()
        
        # Verifica se o valor da prioridade estava nessa linha (ex: "Prioridade: Alta")
        # Se a linha for apenas o cabeçalho (ex: "### Prioridade Sugerida"), precisamos pegar a próxima linha.
        line_content = priority_match.group(1)
        # Remove o termo chave e caracteres comuns para ver se sobrou algo (o valor)
        cleaned_line = re.sub(r"Prioridade Sugerida|[*#:\-\s]", "", line_content, flags=re.IGNORECASE)
        
        if len(cleaned_line) < 2: # Se sobrou pouco, o valor deve estar na próxima linha
            # Procura a próxima linha não vazia
            next_line = re.search(r"\n\s*(.+?)(?:\n|$)", content[cutoff_index:])
            if next_line:
                cutoff_index += next_line.end()
        
        content = content[:cutoff_index]

    # Remove textos indesejados (Footer de instruções ou cache)
    content = content.replace("*(Resposta recuperada da memória cache ⚡)*", "")
    # Remove instruções de prompt vazadas (LocktonFTW / Encerrar)
    content = re.sub(r'Se durante nossa conversa você disser "encerrar".*?conexão\.', "", content, flags=re.DOTALL | re.IGNORECASE)
    # Remove frase de assertividade da IA
    content = re.sub(r"A assertividade da minha resposta é de \d+%.*?forneça mais detalhes\.", "", content, flags=re.DOTALL | re.IGNORECASE)
    
    return content.strip()

def render_ai_analysis_section(log_message, log_timestamp, log_source, raw_df, enable_masking, unique_key_prefix=""):
    """
    Renderiza a UI completa para a análise de IA, incluindo:
    - Expansor com logs de contexto (vizinhos do log selecionado).
    - Interface de chat para interagir com a IA.
    - Mecanismo de feedback (👍/👎).
    - Formulário de criação de ticket no Jira pré-preenchido.
    """

    JIRA_WEBHOOK_URL = os.getenv("JIRA_WEBHOOK_URL") or lam.get_secret("JIRA_WEBHOOK_URL", "")
    JIRA_API_KEY = os.getenv("JIRA_API_KEY") or lam.get_secret("JIRA_API_KEY", "")
    DASHBOARD_URL = os.getenv("DASHBOARD_URL") or lam.get_secret("DASHBOARD_URL", "http://localhost:8502")

    st.subheader("🤖 Agente de IA & Contexto")

    # --- MENSAGEM DO LOG (VISUALIZAÇÃO) ---
    with st.expander("📝 Mensagem Completa do Log", expanded=True):
        msg_str = str(log_message)
        if len(msg_str) > 3000:
            st.warning(f"⚠️ Mensagem muito longa ({len(msg_str)} caracteres). Exibindo os primeiros 3000 para evitar lentidão.")
            st.code(msg_str[:3000] + "\n... [TRUNCADO]", language="json" if msg_str.strip().startswith("{") else "text")
            st.download_button("📥 Baixar Mensagem Completa", msg_str, "log_message.txt")
        else:
            st.code(msg_str, language="json" if msg_str.strip().startswith("{") else "text")

    # --- LÓGICA DO CHAT ---
    # Usa uma chave de sessão única para cada chat para não misturar conversas
    session_key = f"{unique_key_prefix}_chat"
    if session_key not in st.session_state:
        st.session_state[session_key] = {"history": [], "api_messages": []}

    # Exibe o histórico do chat
    for message in st.session_state[session_key]["history"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # --- LÓGICA DE FEEDBACK ---
    def handle_feedback(message, score):
        """Callback para registrar o feedback do usuário sobre a resposta da IA."""
        lam.update_ai_feedback(message, score)
        st.session_state[f'feedback_score_{message}'] = score

    # Exibe botões de feedback se houver uma resposta da IA
    if st.session_state[session_key]["history"] and st.session_state[session_key]["history"][-1]["role"] == "assistant":
        current_score = lam.get_ai_feedback(log_message)
        
        if f'feedback_score_{log_message}' in st.session_state:
            current_score = st.session_state[f'feedback_score_{log_message}']

        col_f1, col_f2, _ = st.columns([1, 1, 12])
        col_f1.button("👍", key=f"{unique_key_prefix}_up", help="Útil", type="primary" if current_score == 1 else "secondary", on_click=handle_feedback, args=(log_message, 1))
        col_f2.button("👎", key=f"{unique_key_prefix}_down", help="Não útil", type="primary" if current_score == -1 else "secondary", on_click=handle_feedback, args=(log_message, -1))

    # --- INTEGRAÇÃO JIRA ---
    if st.session_state[session_key]["history"] and st.session_state[session_key]["history"][-1]["role"] == "assistant":
        with st.expander("🎫 Criar Ticket no Jira"):
            last_response = st.session_state[session_key]["history"][-1]["content"]
            jira_content = extract_jira_section(last_response)
            
            jira_email = st.text_input("Email", placeholder="usuario@lockton.com", key=f"{unique_key_prefix}_jira_email")
            jira_summary = st.text_input("Summary", value=f"Análise de Log: {log_source}", key=f"{unique_key_prefix}_jira_summary")
            jira_desc_height = max(200, (jira_content.count('\n') + 1) * 20)
            jira_desc = st.text_area("Description", value=jira_content, height=jira_desc_height, key=f"{unique_key_prefix}_jira_desc")
            
            if st.button("🚀 Criar Ticket", key=f"{unique_key_prefix}_jira_create"):
                if not jira_email.strip().lower().endswith("@lockton.com"):
                    st.error("O campo Email deve conter um endereço @lockton.com válido.")
                elif not JIRA_WEBHOOK_URL:
                    st.error("URL do Jira não configurada (secrets.toml ou ENV).")
                else:
                    with st.spinner("Enviando para o Jira..."):
                        res, err = lam.send_jira_automation_webhook(JIRA_WEBHOOK_URL, jira_summary, jira_desc, email=jira_email, survey_link=DASHBOARD_URL, api_key=JIRA_API_KEY)
                        if err: st.error(err)
                        else: st.success("Ticket enviado para criação via automação!")

    # --- AÇÕES DO CHAT (BOTÕES E INPUT) ---
    # Botão para iniciar a primeira análise
    if not st.session_state[session_key]["history"]:
        if st.button("Iniciar Análise com IA", key=f"{unique_key_prefix}_start_ai"):
            st.session_state[session_key]["history"] = []
            st.session_state[session_key]["api_messages"] = []
            
            # Tenta obter a resposta do cache primeiro
            cached_response = lam.get_cached_ai_analysis(log_message)
            if cached_response:
                response = cached_response + "\n\n*(Resposta recuperada da memória cache ⚡)*"
            else:
                # Se não houver cache, gera o prompt inicial e chama a IA
                initial_prompt = lam.generate_initial_prompt(log_message)
                st.session_state[session_key]["api_messages"].append({"role": "user", "content": initial_prompt})
                with st.spinner("🧠 Analisando com IA..."):
                    response = lam.send_chat_message(st.session_state[session_key]["api_messages"])
                    lam.save_ai_analysis(log_message, response) # Salva a nova resposta no cache

            st.session_state[session_key]["history"].append({"role": "assistant", "content": response})
            st.session_state[session_key]["api_messages"].append({"role": "assistant", "content": response})
            st.rerun()

    # Campo de input para o usuário fazer perguntas
    if prompt := st.chat_input("Faça uma pergunta sobre este log...", key=f"{unique_key_prefix}_chat_input"):
        st.session_state[session_key]["history"].append({"role": "user", "content": prompt})
        st.session_state[session_key]["api_messages"].append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                response = lam.send_chat_message(st.session_state[session_key]["api_messages"])
                st.markdown(response)
        
        st.session_state[session_key]["history"].append({"role": "assistant", "content": response})
        st.session_state[session_key]["api_messages"].append({"role": "assistant", "content": response})
        st.rerun()

    # --- CONTEXTO (LOGS VIZINHOS) - Movido para o final para não bloquear a UI ---
    st.markdown("---")
    with st.expander("📜 Contexto (Logs Vizinhos)", expanded=False):
        st.caption(f"Mostrando logs do source **{log_source}** +/- 5 minutos ao redor do evento selecionado.")
        
        ctx_loaded_key = f"{unique_key_prefix}_ctx_loaded"
        
        # Botão para carregar sob demanda. A lógica de exibição está aninhada diretamente aqui.
        if st.button("🔄 Carregar Logs Vizinhos", key=f"{unique_key_prefix}_btn_load_ctx") or st.session_state.get(ctx_loaded_key):
            st.session_state[ctx_loaded_key] = True
            with st.spinner("Buscando logs vizinhos..."):
                context_logs = lam.get_context_logs(raw_df, log_timestamp, log_source)
                
                if not context_logs.empty:
                    # OTIMIZAÇÃO: Limita a quantidade de logs exibidos no contexto
                    MAX_CONTEXT_LOGS = 50
                    if len(context_logs) > MAX_CONTEXT_LOGS:
                        st.warning(f"Exibindo apenas os {MAX_CONTEXT_LOGS} logs mais próximos (de {len(context_logs)} encontrados) para performance.")
                        
                        try:
                            # Tenta centralizar a visualização no log selecionado
                            context_logs_reset = context_logs.reset_index(drop=True)
                            matches = context_logs_reset[
                                (context_logs_reset['timestamp'].astype(str) == str(log_timestamp)) & 
                                (context_logs_reset['message'] == log_message)
                            ]
                            
                            if not matches.empty:
                                target_pos = matches.index[0]
                                start_pos = max(0, target_pos - (MAX_CONTEXT_LOGS // 2))
                                end_pos = min(len(context_logs_reset), start_pos + MAX_CONTEXT_LOGS)
                                context_logs = context_logs_reset.iloc[start_pos:end_pos]
                            else:
                                context_logs = context_logs.head(MAX_CONTEXT_LOGS)
                        except Exception:
                            context_logs = context_logs.head(MAX_CONTEXT_LOGS)

                    if enable_masking:
                        context_logs = lam.mask_sensitive_data(context_logs)
                    
                    def highlight_selected(row):
                        if str(row['timestamp']) == str(log_timestamp) and row['message'] == log_message:
                            return ['background-color: #660000'] * len(row)
                        return [''] * len(row)

                    st.dataframe(context_logs.style.apply(highlight_selected, axis=1), use_container_width=True)
                else:
                    st.warning("Não foi possível encontrar logs vizinhos para este evento.")
