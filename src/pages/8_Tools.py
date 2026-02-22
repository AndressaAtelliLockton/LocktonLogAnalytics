# -*- coding: utf-8 -*-
"""
Módulo para a aba "Ferramentas Técnicas".
"""

import streamlit as st
import log_analyzer as lam
import re
import time

def render_page():
    """
    Renderiza a aba "Ferramentas Técnicas" com Regex Sandbox e RCA.
    """
    st.title("🛠️ Ferramentas Técnicas")
    
    if 'filtered_df' not in st.session_state or st.session_state['filtered_df'].empty:
        st.warning("Dados não carregados. Por favor, vá para a página principal e carregue os dados primeiro.")
        return

    filtered_df = st.session_state['filtered_df']
    JIRA_WEBHOOK_URL = st.session_state['JIRA_WEBHOOK_URL']
    JIRA_API_KEY = st.session_state['JIRA_API_KEY']

    # --- Regex Sandbox ---
    st.header("🧪 Regex Sandbox")
    st.markdown("Teste expressões regulares em tempo real nos seus logs para criar filtros ou extrair métricas.")
    
    regex_input = st.text_input("Expressão Regular (Regex)", value=r"(?i)error", help="Digite sua regex aqui. Ex: \d{3} para encontrar números de 3 dígitos.", key="regex_input_8")
    
    if regex_input:
        try:
            # Busca em todo o dataset filtrado usando vetorização (mais rápido e abrangente)
            match_mask = filtered_df['message'].astype(str).str.contains(regex_input, regex=True, na=False)
            total_matches = match_mask.sum()
            
            st.write(f"Encontrado em **{total_matches}** logs (de {len(filtered_df)} filtrados).")
            
            if total_matches > 0:
                # Pega os primeiros 20 matches para exibir a extração detalhada
                preview_df = filtered_df[match_mask].head(20).copy()
                
                def find_matches(text):
                    return re.findall(regex_input, str(text))
                    
                preview_df['matches'] = preview_df['message'].apply(find_matches)
                st.dataframe(preview_df[['timestamp', 'message', 'matches']], use_container_width=True)
            else:
                st.warning("Nenhum match encontrado nos logs filtrados.")
                
        except Exception as e:
            st.error(f"Regex Inválido: {e}")
            
    # --- Análise de Causa Raiz (RCA) ---
    st.markdown("---")
    st.subheader("🕵️ Análise de Causa Raiz (RCA)")
    st.info("A IA analisará o conjunto de erros filtrados para identificar correlações e sugerir a origem do incidente.")
    
    # Inicializa estado para RCA se não existir
    if "rca_result" not in st.session_state:
        st.session_state.rca_result = None

    if st.button("Gerar Diagnóstico de Incidente (RCA)", help="Envia um resumo dos erros atuais para a IA diagnosticar o problema global."):
        start_time = time.time()
        rca_prompt = lam.generate_rca_prompt(filtered_df)
        if rca_prompt:
            with st.spinner("Correlacionando eventos e gerando hipóteses..."):
                # Chama a IA (sem cache de hash simples, pois o contexto é dinâmico)
                response = lam.send_chat_message([{"role": "user", "content": rca_prompt}])
                st.session_state.rca_result = response
            
            elapsed = time.time() - start_time
            st.success(f"Diagnóstico gerado em {elapsed:.2f} segundos.")
        else:
            st.warning("Não foram encontrados indícios suficientes de erro (Logs Críticos, Warnings ou palavras-chave de falha) nos dados filtrados para gerar uma RCA.")
            st.session_state.rca_result = None
    
    # Exibe o resultado persistido
    if st.session_state.rca_result:
        st.markdown(st.session_state.rca_result)
        if st.button("Limpar Diagnóstico"):
            st.session_state.rca_result = None
            st.rerun()

    # --- Testes de Integração (Main Area) ---
    st.markdown("---")
    st.subheader("🛠️ Testes de Integração")
    st.info("Valide a conexão com o Jira enviando um ticket de teste.")
    
    # Inicializa estado para input manual se falhar
    if "jira_manual_mode" not in st.session_state:
        st.session_state.jira_manual_mode = False

    if st.button("Testar Integração Jira (Webhook)"):
        if not JIRA_WEBHOOK_URL:
            st.error("URL do Webhook não configurada nos Secrets/ENV.")
            st.session_state.jira_manual_mode = True
        else:
            with st.spinner("Enviando teste para o Jira (Configuração Padrão)..."):
                res, err = lam.send_jira_automation_webhook(
                    JIRA_WEBHOOK_URL,
                    summary="[TESTE] Validação de Conexão Jira",
                    description="Este ticket foi gerado para validar a integração entre o Dashboard de Logs e o Jira Automation.\n\nSe você está lendo isso, a conexão está funcionando! ✅",
                    email="admin@lockton.com",
                    api_key=JIRA_API_KEY
                )
                if err:
                    st.error(f"Falha na configuração automática: {err}")
                    if "Missing token" in str(err):
                        st.warning("💡 Dica: O Jira retornou 'Missing token'. Verifique se a URL do Webhook contém o parâmetro `?token=...` no final.")
                    st.session_state.jira_manual_mode = True
                else:
                    st.success("Ticket de teste enviado com sucesso! Verifique o projeto no Jira.")
                    st.session_state.jira_manual_mode = False

    # Se falhar, mostra campos manuais vazios
    if st.session_state.jira_manual_mode:
        st.warning("A conexão automática falhou. Insira as credenciais manualmente para testar:")
        manual_url = st.text_input("URL do Webhook", key="jira_manual_url")
        manual_key = st.text_input("Token / API Key (Opcional)", key="jira_manual_key")
        
        if st.button("Testar Manualmente"):
            if not manual_url:
                st.error("Insira a URL.")
            else:
                with st.spinner("Enviando teste manual..."):
                    res, err = lam.send_jira_automation_webhook(
                        manual_url,
                        summary="[TESTE] Validação Manual Jira",
                        description="Teste manual de integração.",
                        email="admin@lockton.com",
                        api_key=manual_key
                    )
                    if err:
                        st.error(f"Falha: {err}")
                    else:
                        st.success("Ticket manual enviado com sucesso!")
