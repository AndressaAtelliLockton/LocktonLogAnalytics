import pandas as pd
import argparse
import log_analyzer_module as lam

def main():
    """
    Função principal para executar a análise de logs via linha de comando.
    """
    parser = argparse.ArgumentParser(description='Analisa e categoriza logs de um arquivo CSV do Graylog.')
    parser.add_argument('file_path', help='O caminho para o arquivo CSV de logs de entrada.')
    parser.add_argument('-o', '--output', default='analysis_result.csv', help='O caminho para o arquivo CSV de saída.')
    parser.add_argument('-c', '--config', default='config.json', help='O caminho para o arquivo de configuração JSON.')
    parser.add_argument('--analyze-errors', action='store_true', help='Ativa a análise de logs de erro com IA (Groq).')
    
    args = parser.parse_args()

    # 1. Load Config - Ajustado para receber os DOIS valores (config e error_msg)
    config, error_msg = lam.load_config(args.config)
    if error_msg:
        print(f"Aviso: {error_msg}")
        # Se não houver config, paramos por aqui
        if config is None:
            return

    # 2. Read Input CSV
    try:
        # Lendo o CSV. Se o seu arquivo não tiver cabeçalho, header=None está correto.
        df = pd.read_csv(args.file_path, header=None, names=['timestamp', 'source', 'message'])
    except FileNotFoundError:
        print(f"Erro: O arquivo '{args.file_path}' não foi encontrado.")
        return
    except Exception as e:
        print(f"Ocorreu um erro ao ler o arquivo CSV de entrada: {e}")
        return

    # 3. Process Data
    try:
        output_df, category_counts = lam.process_log_data(df, config)
    except Exception as e:
        print(f"Erro durante o processamento: {e}")
        return

    # 4. Save results
    try:
        output_df.to_csv(args.output, index=False, quoting=1)
        print(f"Análise salva com sucesso em '{args.output}'")
    except Exception as e:
        print(f"Ocorreu um erro ao salvar o arquivo de saída: {e}")

    # 5. Print summary
    print("\n--- Resumo da Análise ---")
    print(f"Total de logs processados: {len(output_df)}")
    if category_counts:
        for category, count in sorted(category_counts.items()):
            print(f"- {category}: {count}")
    print("--------------------------")

    # 6. Analyze errors with AI if requested
    if args.analyze_errors:
        print("\n--- Análise de Erros com IA ---")

        ai_analyses = lam.analyze_critical_logs_with_ai(output_df)
        
        if isinstance(ai_analyses, list) and len(ai_analyses) > 0:
            for analysis in ai_analyses:
                print(f"\n[+] Log de {analysis.get('timestamp', 'N/A')}:")
                print(f"    Mensagem: {analysis.get('log_message', 'Sem mensagem')}")
                print(f"    Análise IA: {analysis.get('ai_analysis', 'Sem análise')}")
        else:
            print("Nenhum erro crítico encontrado para análise ou erro na conexão com a IA.")
        print("---------------------------------")

if __name__ == '__main__':
    main()