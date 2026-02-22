import unittest
import pandas as pd
import sys
import os

# Adiciona o diretório raiz ao path para garantir que imports funcionem
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from log_analyzer import database as db

class TestDatabaseMemory(unittest.TestCase):
    
    def setUp(self):
        """Executado antes de cada teste: Limpa o banco em memória."""
        db.init_db()

    def test_ingest_logs_success(self):
        """Testa se logs são inseridos corretamente na memória."""
        df = pd.DataFrame({
            'timestamp': ['2024-01-01 10:00:00'],
            'source': ['test-source'],
            'message': ['Test message 1']
        })
        
        # Executa ingestão
        count = db.ingest_logs_to_db(df)
        
        # Verificações
        self.assertEqual(count, 1, "Deveria ter inserido 1 log.")
        
        stored_df = db.get_collected_logs()
        self.assertEqual(len(stored_df), 1, "O banco em memória deveria ter 1 registro.")
        self.assertEqual(stored_df.iloc[0]['message'], 'Test message 1')
        self.assertEqual(stored_df.iloc[0]['source'], 'test-source')

    def test_ingest_deduplication(self):
        """Testa se logs duplicados (mesmo hash) são ignorados."""
        df = pd.DataFrame({
            'timestamp': ['2024-01-01 10:00:00'],
            'source': ['test-source'],
            'message': ['Test message 1']
        })
        
        # Primeira inserção
        db.ingest_logs_to_db(df)
        
        # Segunda inserção (exatamente os mesmos dados)
        count = db.ingest_logs_to_db(df)
        
        self.assertEqual(count, 0, "Deveria retornar 0 pois é duplicado.")
        
        stored_df = db.get_collected_logs()
        self.assertEqual(len(stored_df), 1, "Não deveria ter duplicado o registro na lista.")

    def test_empty_dataframe(self):
        """Testa ingestão de DataFrame vazio."""
        count = db.ingest_logs_to_db(pd.DataFrame())
        self.assertEqual(count, 0)

if __name__ == '__main__':
    unittest.main()