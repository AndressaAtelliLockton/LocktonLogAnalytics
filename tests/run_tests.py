import unittest
import os
import sys

# Adiciona o diretório atual ao path para garantir que os imports funcionem
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def run_all_tests():
    print("--- 🧪 Iniciando Execução de Todos os Testes ---")
    
    # Descobre todos os arquivos test_*.py no diretório atual
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # Executa os testes
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\n✅ Todos os testes passaram com sucesso!")
        sys.exit(0)
    else:
        print("\n❌ Alguns testes falharam.")
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()