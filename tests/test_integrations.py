import unittest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock
import sys

# --- MOCK STREAMLIT GLOBALLY ---
if 'streamlit' not in sys.modules:
    sys.modules['streamlit'] = MagicMock()

# Adiciona o diretório raiz ao sys.path para encontrar o pacote log_analyzer
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from log_analyzer.integrations import format_graylog_table

class TestFormatGraylogTable(unittest.TestCase):

    def test_with_full_pandas_series(self):
        """Testa a formatação com uma Series completa do pandas."""
        data = {
            "command": "run.sh",
            "container_id": "abc123def456",
            "container_name": "web-app-1",
            "created": "2024-01-01T10:00:00Z",
            "gl2_processing_error": None,
            "image_id": "img-xyz",
            "image_name": "webapp:latest",
            "level": 3,
            "LogLevel": "Error",
            "message": "Database connection failed.",
            "source": "server-01",
            "tag": "prod",
            "RequestPath": "/api/users",
            "cpu_valor": 75.5,
            "mem_valor": 80.2
        }
        log_row = pd.Series(data)
        result = format_graylog_table(log_row)
        
        self.assertIn("**container_name**\n`web-app-1`", result)
        self.assertIn("**message**\n`Database connection failed.`", result)
        self.assertIn("**cpu_valor**\n`75.5`", result)
        # Verifica um campo que é None e deve ser N/A
        self.assertIn("**gl2_processing_error**\n`N/A`", result)

    def test_with_dict_and_missing_fields(self):
        """Testa a formatação com um dicionário Python com campos ausentes."""
        log_row = {
            "container_name": "db-replica",
            "message": "Replication lag detected.",
            "level": 4
        }
        result = format_graylog_table(log_row)
        
        self.assertIn("**container_name**\n`db-replica`", result)
        self.assertIn("**message**\n`Replication lag detected.`", result)
        # Verifica se campos ausentes no dicionário são renderizados como N/A
        self.assertIn("**source**\n`N/A`", result)
        self.assertIn("**cpu_valor**\n`N/A`", result)

    def test_with_nan_and_empty_string(self):
        """Testa a formatação com dados ausentes (np.nan) e strings vazias."""
        data = {
            "container_name": "worker-bee",
            "message": "Job completed.",
            "cpu_valor": np.nan,      # Dado ausente como NaN
            "mem_valor": "",          # Dado como string vazia
            "source": "   "           # Dado como string com espaços
        }
        log_row = pd.Series(data)
        result = format_graylog_table(log_row)
        
        self.assertIn("**container_name**\n`worker-bee`", result)
        # Verifica que np.nan é convertido para N/A
        self.assertIn("**cpu_valor**\n`N/A`", result)
        # Verifica que string vazia é convertida para N/A
        self.assertIn("**mem_valor**\n`N/A`", result)
        # Verifica que string com espaços é convertida para N/A
        self.assertIn("**source**\n`N/A`", result)

if __name__ == '__main__':
    unittest.main()