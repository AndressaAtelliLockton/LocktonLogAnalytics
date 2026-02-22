# -*- coding: utf-8 -*-
"""
Módulo para gerenciamento do processo de scheduler em background.
"""
import os
import subprocess
import sys
import signal
from datetime import datetime

# --- Constantes ---
SCHEDULER_STATUS_FILE = "scheduler_status.txt"
SCHEDULER_PID_FILE = "scheduler.pid"

# --- Funções do Scheduler ---

def is_scheduler_running():
    """
    Verifica se o processo do scheduler está ativo, checando a existência e validade do PID.
    """
    if not os.path.exists(SCHEDULER_PID_FILE):
        return False
    try:
        with open(SCHEDULER_PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        # Envia um sinal 0 para o processo. Se não houver erro, o processo existe.
        os.kill(pid, 0)
        return True
    except (ValueError, OSError, FileNotFoundError, SystemError):
        # Se o PID não for válido ou o processo não existir, limpa o arquivo de PID.
        if os.path.exists(SCHEDULER_PID_FILE):
            os.remove(SCHEDULER_PID_FILE)
        return False

def get_last_collection_time():
    """
    Lê o timestamp da última coleta bem-sucedida do arquivo de status.
    """
    try:
        with open(SCHEDULER_STATUS_FILE, "r") as f:
            return f.readline().strip() or None
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Erro ao ler status do scheduler: {e}")
        return None

def update_scheduler_status():
    """
    Atualiza o arquivo de status do scheduler com o timestamp atual.
    """
    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(SCHEDULER_STATUS_FILE, "w") as f:
            f.write(now)
        return True
    except Exception as e:
        print(f"Erro ao atualizar status do scheduler: {e}")
        return False

def clear_scheduler_status():
    """
    Remove o arquivo de status, útil ao parar o scheduler.
    """
    try:
        if os.path.exists(SCHEDULER_STATUS_FILE):
            os.remove(SCHEDULER_STATUS_FILE)
        return True
    except Exception as e:
        print(f"Erro ao limpar status do scheduler: {e}")
        return False

def start_scheduler_background():
    """
    Inicia o script 'scheduler.py' como um processo em segundo plano.
    Diferencia a inicialização para Windows e outros sistemas operacionais.
    """
    if is_scheduler_running():
        return False, "O agendador já está em execução."
    
    try:
        cmd = [sys.executable, "scheduler.py"]
        
        if os.name == 'nt': # Windows
            process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else: # Linux/Mac
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
        with open(SCHEDULER_PID_FILE, 'w') as f:
            f.write(str(process.pid))
            
        return True, f"Agendador iniciado (PID: {process.pid})."
    except Exception as e:
        return False, f"Falha ao iniciar agendador: {e}"

def stop_scheduler_background():
    """
    Para o processo do scheduler em execução usando o PID salvo.
    """
    if not os.path.exists(SCHEDULER_PID_FILE):
        return False, "Agendador não parece estar rodando."
    
    try:
        with open(SCHEDULER_PID_FILE, 'r') as f:
            pid = int(f.read().strip())
            
        os.kill(pid, signal.SIGTERM)
        
        if os.path.exists(SCHEDULER_PID_FILE): os.remove(SCHEDULER_PID_FILE)
        if os.path.exists(SCHEDULER_STATUS_FILE): os.remove(SCHEDULER_STATUS_FILE)
            
        return True, "Agendador parado com sucesso."
    except Exception as e:
        if os.path.exists(SCHEDULER_PID_FILE): os.remove(SCHEDULER_PID_FILE)
        return False, f"Erro ao parar agendador (limpeza forçada): {e}"
