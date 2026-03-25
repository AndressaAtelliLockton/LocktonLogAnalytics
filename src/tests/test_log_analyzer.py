import unittest
from unittest.mock import patch, MagicMock, mock_open
import pandas as pd
import numpy as np
import os
import sys
import json
from datetime import datetime, timedelta
 
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import log_analyzer

class TestLogAnalyzer(unittest.TestCase):

    def setUp(self):
        # DataFrame de exemplo para testes gerais
        self.sample_df = pd.DataFrame({
            'timestamp': ['2023-10-27 10:00:00', '2023-10-27 10:01:00', '2023-10-27 10:02:00'],
            'source': ['app-1', 'db-1', 'web-1'],
            'message': [
                'User login successful', 
                'Connection timeout error', 
                'GET /api/data 200'
            ],
            'log_level': ['Info', 'Error', 'Info']
        })
        
        self.config = {
            'categories': [
                {'name': 'Database', 'keywords': ['timeout', 'connection'], 'log_levels': ['Error']},
                {'name': 'Auth', 'keywords': ['login']},
                {'name': 'API', 'keywords': ['/api/']}
            ]
        }

    # --- 1. Configuração e Utilitários Básicos ---

    def test_load_config_success(self):
        mock_json = json.dumps(self.config)
        with patch("builtins.open", mock_open(read_data=mock_json)):
            with patch("os.path.exists", return_value=True):
                config, error = log_analyzer.load_config("dummy.json")
                self.assertIsNotNone(config)
                self.assertIsNone(error)
                self.assertEqual(config['categories'][0]['name'], 'Database')

    def test_get_setting_env(self):
        with patch.dict(os.environ, {"TEST_KEY": "value_from_env"}):
            self.assertEqual(log_analyzer.get_setting("test_key"), "value_from_env")

    def test_calculate_log_hash(self):
        h1 = log_analyzer.calculate_log_hash("2023-01-01", "src", "msg")
        h2 = log_analyzer.calculate_log_hash("2023-01-01", "src", "msg")
        h3 = log_analyzer.calculate_log_hash("2023-01-02", "src", "msg")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)

    # --- 2. Parsing e Categorização ---

    def test_parse_log_entry_json(self):
        entry = '{"message": "System start", "level": "info"}'
        result = log_analyzer.parse_log_entry(entry)
        self.assertIsInstance(result, dict)
        self.assertEqual(result['message'], "System start")

    def test_parse_log_entry_text(self):
        entry = "Just a plain text log"
        result = log_analyzer.parse_log_entry(entry)
        self.assertEqual(result['message_text'], "Just a plain text log")

    def test_extract_log_level(self):
        self.assertEqual(log_analyzer.extract_log_level({'LogLevel': 'Critical'}), 'Critical')
        self.assertEqual(log_analyzer.extract_log_level({'message_text': 'error: database down'}), 'Error')
        self.assertEqual(log_analyzer.extract_log_level({'message_text': 'info: user action'}), 'Info')
        self.assertEqual(log_analyzer.extract_log_level({'message_text': 'nada consta'}), 'Não Identificado')

    def test_categorize_log(self):
        # Teste por keyword
        cat1 = log_analyzer.categorize_log({'message_text': 'User login failed'}, self.config)
        self.assertEqual(cat1, 'Auth')
        
        # Teste por LogLevel + Keyword (Database requer Error e keyword)
        cat2 = log_analyzer.categorize_log({'message_text': 'Connection timeout', 'LogLevel': 'Error'}, self.config)
        self.assertEqual(cat2, 'Database')

    def test_process_log_data(self):
        df_out, counts = log_analyzer.process_log_data(self.sample_df, self.config)
        
        self.assertIn('category', df_out.columns)
        self.assertIn('message_length', df_out.columns)
        
        # Verifica categorização baseada no setup
        self.assertEqual(df_out.iloc[0]['category'], 'Auth')     # "login"
        self.assertEqual(df_out.iloc[1]['category'], 'Database') # "timeout" + Error
        self.assertEqual(df_out.iloc[2]['category'], 'API')      # "/api/"

    # --- 3. Regex e Extração de Métricas ---

    def test_extract_trace_ids(self):
        df = pd.DataFrame({'message': [
            'TraceId: 4bf92f3577b34da6a3ce929d0e0e4736', 
            'Error in 550e8400-e29b-41d4-a716-446655440000 processing',
            'No trace here'
        ]})
        res = log_analyzer.extract_trace_ids(df)
        self.assertEqual(res.iloc[0]['trace_id'], '4bf92f3577b34da6a3ce929d0e0e4736')
        self.assertEqual(res.iloc[1]['trace_id'], '550e8400-e29b-41d4-a716-446655440000')
        self.assertTrue(pd.isna(res.iloc[2]['trace_id']))

    def test_mask_sensitive_data(self):
        df = pd.DataFrame({'message': [
            'Email: user@example.com sent', 
            'IP: 192.168.0.1 connected',
            'CPF: 123.456.789-00 found'
        ]})
        res = log_analyzer.mask_sensitive_data(df)
        
        self.assertIn('*****@*****.***', res.iloc[0]['message'])
        self.assertIn('***.***.***.***', res.iloc[1]['message'])
        self.assertIn('***.***.***-**', res.iloc[2]['message'])

    def test_extract_latency_metrics(self):
        df = pd.DataFrame({
            'timestamp': [1, 2, 3], 
            'source': ['s', 's', 's'], 
            'message': ['Request took 500ms', 'duration: 1.2s', 'latency=200us']
        })
        res = log_analyzer.extract_latency_metrics(df)
        
        self.assertEqual(res.iloc[0]['latency_ms'], 500.0)
        self.assertEqual(res.iloc[1]['latency_ms'], 1200.0) # 1.2s -> 1200ms
        self.assertEqual(res.iloc[2]['latency_ms'], 0.2)    # 200us -> 0.2ms

    def test_extract_system_metrics(self):
        df = pd.DataFrame({
            'timestamp': [1], 'source': ['s'], 
            'message': ['CPU: 50.5% Memory: 1024MB Disk: 80%']
        })
        res = log_analyzer.extract_system_metrics(df)
        self.assertEqual(res.iloc[0]['cpu'], 50.5)
        self.assertEqual(res.iloc[0]['memory'], 1024.0)
        self.assertEqual(res.iloc[0]['disk'], 80.0)

    def test_extract_api_metrics(self):
        df = pd.DataFrame({
            'timestamp': [1, 2], 'source': ['s', 's'], 
            'message': ['GET /api/users 200 OK', 'POST /login 401 Unauthorized']
        })
        res = log_analyzer.extract_api_metrics(df)
        
        self.assertEqual(res.iloc[0]['method'], 'GET')
        self.assertEqual(res.iloc[0]['endpoint'], '/api/users')
        self.assertEqual(res.iloc[0]['status_code'], '200')
        
        self.assertEqual(res.iloc[1]['method'], 'POST')
        self.assertEqual(res.iloc[1]['status_code'], '401')

    # --- 4. Análise e Detecção ---

    def test_generate_stack_trace_metrics(self):
        df = pd.DataFrame({
            'timestamp': [1], 'source': ['app'], 'log_level': ['Error'],
            'message': ['Exception: File "main.py", line 10, in <module>\nValueError: bad']
        })
        res = log_analyzer.generate_stack_trace_metrics(df)
        self.assertFalse(res.empty)
        self.assertIn('main.py:unknown', res.iloc[0]['stack_trace'])

    # --- 5. Integrações Externas (Mockadas) ---

    @patch('log_analyzer.requests.post')
    def test_send_webhook_alert(self, mock_post):
        mock_post.return_value.status_code = 200
        res = log_analyzer.send_webhook_alert("http://hook", "msg")
        self.assertEqual(res.status_code, 200)
        mock_post.assert_called_once()

    @patch('log_analyzer.Groq')
    def test_analyze_log_with_ai(self, mock_groq):
        # Mock da resposta da API Groq
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        mock_client.chat.completions.create.return_value.choices[0].message.content = "AI Analysis Result"
        
        with patch.dict(os.environ, {"GROQ_API_KEY": "dummy_key"}):
            res = log_analyzer.analyze_log_with_ai("error log message")
            self.assertEqual(res, "AI Analysis Result")

    @patch('log_analyzer.requests.Session')
    def test_fetch_logs_from_graylog(self, mock_session):
        # Mock da resposta JSON do Graylog
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"messages": [{"message": {"timestamp": "2023-01-01 10:00", "source": "src1", "message": "msg1"}}]}
        mock_resp.status_code = 200
        
        # Configura o mock da sessão
        mock_session.return_value.__enter__.return_value.get.return_value = mock_resp
        
        df, err = log_analyzer.fetch_logs_from_graylog("http://api", "user", "pass")
        
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertEqual(df.iloc[0]['message'], 'msg1')
        self.assertIsNone(err)

    # --- 6. Scheduler e Sistema ---

    def test_is_scheduler_running(self):
        # Mock para simular arquivo PID e processo rodando
        with patch("builtins.open", mock_open(read_data="12345")):
            with patch("os.path.exists", return_value=True):
                with patch("os.kill", return_value=None): # os.kill não lança erro = processo existe
                    self.assertTrue(log_analyzer.is_scheduler_running())

    def test_check_api_health(self):
        with patch('log_analyzer.requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            res = log_analyzer.check_api_health("http://google.com")
            self.assertTrue(res['online'])
            self.assertEqual(res['status_code'], 200)

    # --- 7. Relatórios ---
    
    def test_generate_pdf_report_structure(self):
        # Teste básico para garantir que a função roda sem erros com dados vazios/simples
        # Assume que fpdf2 e vl-convert estão instalados (requirements.txt)
        try:
            import fpdf
            import vl_convert
        except ImportError:
            self.skipTest("Bibliotecas de PDF não instaladas")

        df = self.sample_df
        anomalies = pd.DataFrame()
        rare_logs = pd.DataFrame()
        charts = {} # Sem gráficos para simplificar
        
        pdf_bytes, error = log_analyzer.generate_pdf_report(df, anomalies, rare_logs, charts)
        
        if error:
            self.fail(f"Erro ao gerar PDF: {error}")
            
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(len(pdf_bytes) > 0)
        # Verifica cabeçalho PDF (assinatura básica)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

if __name__ == '__main__':
    unittest.main()