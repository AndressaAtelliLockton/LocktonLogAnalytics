import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import importlib
import logging
import pandas as pd

# Adiciona o diretório raiz ao path para garantir que imports funcionem
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import scheduler

class TestSchedulerConfig(unittest.TestCase):
    
    @patch('scheduler.psutil.cpu_percent')
    @patch('scheduler.lam.get_setting')
    def test_watchdog_recovery_window_env_var(self, mock_get_setting, mock_cpu):
        """
        Verifica se o Scheduler lê corretamente a variável de ambiente WATCHDOG_RECOVERY_WINDOW.
        """
        # Configura o mock do get_setting para retornar um valor simulado
        # O scheduler chama get_setting para várias chaves. 
        # Vamos garantir que quando pedir WATCHDOG_RECOVERY_WINDOW, retorne "300".
        def side_effect(key, default=None):
            if key == "WATCHDOG_RECOVERY_WINDOW":
                return "300" # Simula valor do ENV (5 minutos)
            return default

        mock_get_setting.side_effect = side_effect
        
        # Configura o mock do psutil para lançar uma exceção e interromper o loop infinito do scheduler
        # Usa KeyboardInterrupt pois o scheduler captura Exception genérica, mas não BaseException
        mock_cpu.side_effect = KeyboardInterrupt("Stop Scheduler Loop")
        
        # Executa o scheduler e espera a interrupção
        try:
            scheduler.run_scheduler()
        except KeyboardInterrupt:
            pass
        
        # Verificações
        # 1. Verifica se get_setting foi chamado com a chave correta e o default 600
        mock_get_setting.assert_any_call("WATCHDOG_RECOVERY_WINDOW", 600)
        
        print("✅ Teste: Scheduler solicitou WATCHDOG_RECOVERY_WINDOW corretamente.")

    @patch('scheduler.psutil.cpu_percent')
    @patch('scheduler.lam.get_setting')
    def test_alert_cooldown_env_var(self, mock_get_setting, mock_cpu):
        """
        Verifica se o Scheduler lê corretamente a variável de ambiente ALERT_COOLDOWN.
        """
        def side_effect(key, default=None):
            if key == "ALERT_COOLDOWN":
                return "1800" # Simula valor do ENV (30 minutos)
            return default

        mock_get_setting.side_effect = side_effect
        mock_cpu.side_effect = KeyboardInterrupt("Stop Scheduler Loop")
        
        try:
            scheduler.run_scheduler()
        except KeyboardInterrupt:
            pass
        
        mock_get_setting.assert_any_call("ALERT_COOLDOWN", 3600)
        print("✅ Teste: Scheduler solicitou ALERT_COOLDOWN corretamente.")

    @patch.dict(os.environ, {"SCHEDULER_LOG_LEVEL": "DEBUG"})
    def test_scheduler_log_level_env_var(self):
        """
        Verifica se o nível de log do Scheduler é configurado corretamente via ENV.
        """
        # Recarrega o módulo para processar a nova variável de ambiente
        importlib.reload(scheduler)
        
        # Verifica se a variável interna capturou o valor correto
        self.assertEqual(scheduler.LOG_LEVEL, "DEBUG")
        
        print("✅ Teste: Scheduler Log Level (DEBUG) lido corretamente.")

    @patch('scheduler.subprocess.Popen')
    @patch('scheduler.time.sleep')
    @patch('scheduler.psutil')
    @patch('scheduler.lam')
    def test_log_collector_stopped_alert(self, mock_lam, mock_psutil, mock_sleep, mock_popen):
        """
        Verifica se o Scheduler envia alerta quando log_collector.py não está rodando.
        """
        # Configurações do Mock LAM
        def get_setting_side_effect(key, default=None):
            if key == "TEAMS_WEBHOOK_URL":
                return "http://webhook.test"
            if key in ["ALERT_COOLDOWN", "WATCHDOG_RECOVERY_WINDOW"]:
                return 600
            return default
        
        mock_lam.get_setting.side_effect = get_setting_side_effect
        mock_lam.fetch_logs_from_graylog.return_value = (pd.DataFrame(), None)
        mock_lam.get_graylog_system_stats.return_value = {}
        
        # Configurações do Mock PSUTIL (Hardware)
        mock_psutil.cpu_percent.return_value = 10
        mock_psutil.virtual_memory.return_value.percent = 50
        mock_psutil.disk_usage.return_value.percent = 40
        
        # Simula processos rodando, NENHUM sendo log_collector.py
        mock_process1 = MagicMock()
        mock_process1.info = {'cmdline': ['python', 'other_script.py']}
        # O scheduler itera sobre o retorno de process_iter
        mock_psutil.process_iter.return_value = [mock_process1]

        # Interrompe o loop ao chamar sleep (fim do ciclo)
        mock_sleep.side_effect = KeyboardInterrupt("Stop Loop")
        
        # Executa
        try:
            scheduler.run_scheduler()
        except KeyboardInterrupt:
            pass
        
        # Verificações
        mock_lam.send_webhook_alert.assert_any_call(
            "http://webhook.test", 
            "❌ O processo **log_collector.py** parou de rodar. O Scheduler tentou reiniciá-lo automaticamente.", 
            title="🚨 Log Collector Reiniciado"
        )
        
        # Verifica se tentou reiniciar
        mock_popen.assert_called_once()
        print("✅ Teste: Alerta de Log Collector Parado disparado corretamente.")

    @patch('scheduler.time.sleep')
    @patch('scheduler.psutil')
    @patch('scheduler.lam')
    def test_watchdog_alert_trigger(self, mock_lam, mock_psutil, mock_sleep):
        """
        Verifica se o Watchdog detecta logs críticos e envia alerta.
        """
        # Config mocks
        def get_setting_side_effect(key, default=None):
            if key == "TEAMS_WEBHOOK_URL":
                return "http://webhook.test"
            if key in ["ALERT_COOLDOWN", "WATCHDOG_RECOVERY_WINDOW"]:
                return 600
            if key in ["GRAYLOG_API_URL", "GRAYLOG_USER", "GRAYLOG_PASSWORD"]:
                return "dummy"
            return default
        mock_lam.get_setting.side_effect = get_setting_side_effect
        
        # Mock graylog stats to avoid "Graylog Unhealthy" alert side-effect
        mock_lam.get_graylog_system_stats.return_value = {'status': 'ALIVE', 'throughput': 100}
        
        # Mock hardware stats to avoid errors
        mock_psutil.cpu_percent.return_value = 10
        mock_psutil.virtual_memory.return_value.percent = 50
        mock_psutil.disk_usage.return_value.percent = 40
        
        # Mock process iter to avoid log collector alert
        mock_proc = MagicMock()
        mock_proc.info = {'cmdline': ['python', 'log_collector.py']}
        mock_psutil.process_iter.return_value = [mock_proc]

        # Mock Graylog response with a critical log
        critical_log = pd.DataFrame({
            'timestamp': ['2024-01-01 12:00:00'],
            'source': ['prod-db'],
            'message': ['Critical connection failure'],
            'level': [3],
            'LogLevel': ['Critical'],
            'container_name': ['db-1'],
            'image_name': ['postgres'],
            'command': ['run'],
            'cpu_valor': [0],
            'mem_valor': [0],
            'RequestPath': ['/']
        })
        
        # fetch_logs_from_graylog returns (df, error)
        # First call is metrics (empty), Second call is watchdog (critical log)
        mock_lam.fetch_logs_from_graylog.side_effect = [
            (pd.DataFrame(), None), # Metrics
            (critical_log, None)    # Watchdog
        ]
        
        # Configura o mock do load_config para retornar uma tupla (config, erro)
        mock_lam.load_config.return_value = ({}, None)
        
        # Mock process_log_data to return the log as Critical
        # It returns (df, counts)
        mock_lam.process_log_data.return_value = (pd.DataFrame({
            'log_level': ['Critical'],
            'message': ['Critical connection failure']
        }, index=critical_log.index), {}) # Ensure index matches for .loc filtering
        
        mock_lam.format_graylog_table.return_value = "| Table |"
        mock_lam.send_chat_message.return_value = "AI Analysis"
        
        # Stop loop
        mock_sleep.side_effect = KeyboardInterrupt("Stop Loop")

        try:
            scheduler.run_scheduler()
        except KeyboardInterrupt:
            pass

        # Assert alert sent
        mock_lam.send_webhook_alert.assert_any_call(
            "http://webhook.test", 
            "**IA Insight:** AI Analysis\n\n---\n| Table |\n\nVer no Dashboard", 
            title="🔥 Watchdog IA detectou falha"
        )
        print("✅ Teste: Watchdog disparou alerta corretamente.")

if __name__ == '__main__':
    unittest.main()