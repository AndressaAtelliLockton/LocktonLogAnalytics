import sys
import os
import argparse

# Adiciona o diretório atual ao path para garantir importação correta dos módulos locais
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    import log_analyzer as lam
except ImportError:
    print("❌ Erro: Módulo 'log_analyzer' não encontrado.")
    print("Certifique-se de ter rodado o script de organização (organize_project.py).")
    sys.exit(1)

def run_iac_agent(issue_description):
    print("\n==========================================")
    print("   🕵️  AGENTE DE IA PARA IAC & DEVOPS")
    print("==========================================\n")
    
    print(f"📝 Analisando problema: \"{issue_description}\"\n")
    
    # 1. Definição do System Prompt (Persona)
    system_prompt = """
    Você é um Engenheiro SRE/DevOps Sênior especializado em Infraestrutura como Código (IAC), Pipelines CI/CD e Redes.
    Sua missão é diagnosticar problemas complexos de infraestrutura com base em descrições curtas.

    Ao analisar o problema do usuário:
    1.  **Análise de Causa Raiz:** Explique tecnicamente o que pode estar acontecendo. Foque em contradições (ex: porta aberta vs acesso negado).
    2.  **Hipóteses Técnicas:** Liste pelo menos 3 causas prováveis (ex: Bind Address incorreto, Firewall de Aplicação, Permissões de Usuário, Erro de Protocolo).
    3.  **Plano de Ação (Troubleshooting):** Forneça comandos práticos para validar cada hipótese (PowerShell para Windows, Bash para Linux).
    4.  **Solução Sugerida:** Se possível, sugira a correção no código (Terraform, Dockerfile, YAML de Pipeline).

    Responda em Português, utilizando formatação Markdown para facilitar a leitura (negrito, blocos de código).
    Seja direto e técnico.
    """

    # 2. Definição do User Prompt (Contexto Específico)
    user_prompt = f"""
    Estou com um incidente na minha infraestrutura e preciso de ajuda.

    DESCRIÇÃO DO PROBLEMA:
    "{issue_description}"

    CONTEXTO ADICIONAL:
    - O erro ocorre durante a execução de uma pipeline (CI/CD).
    - O servidor de destino parece estar online (porta externa responde).
    - O erro reportado é "Acesso Negado" ou similar.

    Por favor, me dê um diagnóstico completo e passos para resolver.
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    print("⏳ Consultando a Inteligência Artificial (Groq)...")
    
    # 3. Chamada à API via módulo existente
    try:
        response = lam.send_chat_message(messages)
        
        print("\n" + "-"*50)
        print("💡 DIAGNÓSTICO DO AGENTE:")
        print("-"*50)
        print(response)
        print("-"*50 + "\n")
        
    except Exception as e:
        print(f"\n❌ Falha ao conectar com o Agente de IA: {e}")
        print("Verifique se a chave GROQ_API_KEY está configurada no arquivo .env")

if __name__ == "__main__":
    # Captura argumentos da linha de comando ou usa o default do problema relatado
    parser = argparse.ArgumentParser(description='Agente de IA para Troubleshooting de IAC')
    parser.add_argument('issue', nargs='*', help='Descrição do problema')
    args = parser.parse_args()
    
    default_issue = "Ao rodar a pipeline no servidor ele dá acesso negado, mas a porta externa está aberta"
    
    issue_text = " ".join(args.issue) if args.issue else default_issue
    
    run_iac_agent(issue_text)