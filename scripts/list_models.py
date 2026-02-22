import os
from groq import Groq

def main():
    api_key = os.environ.get("GROQ_API_KEY")
    
    if not api_key:
        print("Erro: Chave de API da Groq não encontrada. Configure a variável de ambiente GROQ_API_KEY.")
        return

    client = Groq(api_key=api_key)

    print("--- Modelos Disponíveis na Groq ---")
    try:
        models = client.models.list()
        for model in models.data:
            print(f"Modelo: {model.id} | Dono: {model.owned_by}")
    except Exception as e:
        print(f"Erro ao listar modelos: {e}")

if __name__ == "__main__":
    main()
