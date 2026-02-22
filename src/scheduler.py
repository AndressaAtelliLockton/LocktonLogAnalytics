import time
import log_analyzer as lam
from datetime import datetime
import psutil
import hashlib
import pandas as pd
import requests
import sys
import logging
import os
import subprocess
import signal

# Configuração de Logging via Variável de Ambiente
LOG_LEVEL = os.getenv("SCHEDULER_LOG_LEVEL", "INFO").upper()

# Configura logging para arquivo e console
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("scheduler.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Scheduler")

# Handler para salvar dados ao encerrar o container (SIGTERM/SIGINT)
def shutdown_handler(signum, frame):
    logger.info(f"Recebido sinal de parada ({signum}). Salvando dados em disco...")
    lam.save_to_disk()
    logger.info("Dados salvos. Encerrando Scheduler.")
    sys.exit(0)

def run_scheduler():
    logger.info("--- Watchdog de Observabilidade (IA Proativa) ---")
    
    # Controle de spam para alertas de infraestrutura (Graylog Offline)
    last_graylog_alert_time = 0
    ALERT_COOLDOWN = int(lam.get_setting("ALERT_COOLDOWN", 3600)) # 1 hora em segundos
    
    # Controle de recuperação do Watchdog (Erros Críticos)
    watchdog_in_error_state = False
    last_watchdog_error_time = 0
    WATCHDOG_RECOVERY_WINDOW = int(lam.get_setting("WATCHDOG_RECOVERY_WINDOW", 600))
    
    # Controle de alerta do Log Collector
    last_collector_alert_time = 0
    
    while True:
        try:
            # Recarrega configurações do disco para pegar atualizações da UI (ex: Webhook URL)
            lam.load_from_disk()
            
            agora = datetime.now()
            logger.info("Iniciando Ciclo de Rastreamento (Watchdog Global)...")

            # 1. HARDWARE
            # interval=1 garante leitura precisa (evita 0.0 na primeira chamada)
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory().percent
            dsk = psutil.disk_usage('/').percent
            infra_msg = f"METRIC | CPU: {cpu}% | Memory: {mem}% | Disk: {dsk}%"
            
            lam.ingest_logs_to_db(pd.DataFrame([{"log_hash": hashlib.md5(f"{agora}infra".encode()).hexdigest(), 
                                               "timestamp": agora.strftime('%Y-%m-%d %H:%M:%S'), "source": "Local-Agent", "message": infra_msg}]))

            # 1.1 ENVIO PARA GRAYLOG (Input MetricasHardware - UDP 12201)
            # Envia as métricas coletadas para o input GELF configurado no Graylog
            # Ajuste: Usa o host configurado na API URL ou fallback seguro
            api_url_env = lam.get_setting("GRAYLOG_API_URL", "")
            gl_host = lam.get_host_from_url(api_url_env) if api_url_env else "graylog.lockton.com.br"
            port = 12201

            logger.debug(f"Tentando conexão UDP para {gl_host}:{port}...")
            lam.send_gelf_message(gl_host, port, infra_msg, extra_fields={"cpu": cpu, "memory": mem, "disk": dsk}, source_name="Local-Agent")

            # 2. LOGS & IA WATCHDOG
            # Ajuste: Chaves atualizadas para coincidir com Variáveis de Ambiente (DB removido)
            # Tenta chaves de ambiente (UPPER) e chaves salvas pela UI (lower)
            url = lam.get_setting("GRAYLOG_API_URL") or lam.get_setting("graylog_url")
            user = lam.get_setting("GRAYLOG_USER") or lam.get_setting("graylog_user")
            password = lam.get_setting("GRAYLOG_PASSWORD") or lam.get_setting("graylog_pass") or "token"
            webhook_url = lam.get_setting("TEAMS_WEBHOOK_URL") or lam.get_setting("webhook_url")
            dash_url = lam.get_setting("DASHBOARD_URL") or lam.get_setting("dashboard_url") or "http://localhost:8502"
            
            if not webhook_url:
                logger.warning("Aviso: URL do Webhook não configurada. Alertas não serão enviados.")
            else:
                logger.info("Webhook configurado: (Oculto por segurança)")
            
            # Busca Node ID dinamicamente (opcional, para debug ou filtros futuros)
            node_id = lam.get_graylog_node_id(url, user, password)
            if node_id:
                logger.info(f"Conectado ao Graylog Node: {node_id}")
            
            # Só tenta buscar métricas se a URL do Graylog estiver configurada
            if url:
                # Buscamos os logs que contenham a mensagem 'METRIC' que você definiu no código
                query = "message:\"METRIC\"" 
                df_metricas, err = lam.fetch_logs_from_graylog(url, user, password, query=query, relative=300, fields="timestamp,source,message,cpu_valor,mem_valor")
                
                if df_metricas is not None and not df_metricas.empty:
                    # Persiste logs recuperados para gerar métricas históricas no Dashboard
                    lam.ingest_logs_to_db(df_metricas)

                    logger.debug("\n--- DADOS RECEBIDOS DO GRAYLOG (METRICAS) ---")
                    logger.debug(df_metricas.to_string())
                    logger.debug("---------------------------------------------\n")

                    # O Graylog pode retornar os campos como 'cpu', 'memory', 'disk' 
                    # ou com prefixo customizado. Verifique as colunas disponíveis:
                    logger.debug(f"Colunas encontradas: {df_metricas.columns.tolist()}")
                    
                    # Pegamos o dado mais recente (primeira linha)
                    cpu_atual = df_metricas['cpu_valor'].iloc[0] if 'cpu_valor' in df_metricas.columns else 0
                    mem_atual = df_metricas['mem_valor'].iloc[0] if 'mem_valor' in df_metricas.columns else 0
                    dsk_atual = 0 # Disk não mapeado na nova query
                    
                    logger.info(f"Métricas Graylog: CPU {cpu_atual}% | MEM {mem_atual}% | DISK {dsk_atual}%")

            # 2.1 WATCHDOG DE ERROS
            # Monitora erros críticos e inclui metadados de container/graylog
            # Query global: Captura erros de TODAS as origens (incluindo swarm2, swarm4)
            # Critério: Nível de log baixo (0-4) OU palavras-chave de erro na mensagem
            query_watchdog = "(message:\"Error\" OR message:\"Fail\" OR message:\"Critical\" OR message:\"Fatal\" OR message:\"Exception\" OR level:[0 TO 4])"
            
            # Solicita campos explícitos para garantir que a tabela do alerta tenha todas as colunas formatadas igual ao teste
            if url:
                df_watchdog_raw, err = lam.fetch_logs_from_graylog(url, user, password, query=query_watchdog, relative=300, fields="timestamp,source,message,level,LogLevel,container_id,container_name,image_id,image_name,command,created,gl2_processing_error,tag,RequestPath,cpu_valor,mem_valor")
            else:
                df_watchdog_raw, err = None, "URL não configurada"
                logger.info("Watchdog ignorado (URL do Graylog não configurada).")
            
            if err:
                if url: # Só loga erro se a URL existir mas falhar
                    logger.error(f"Erro ao buscar logs do Watchdog: {err}")
                df_watchdog = pd.DataFrame()
            elif df_watchdog_raw is not None and not df_watchdog_raw.empty:
                # Processa os logs usando a mesma lógica do Dashboard para garantir consistência (Extrai LogLevel do JSON, etc)
                config, _ = lam.load_config()
                df_proc, _ = lam.process_log_data(df_watchdog_raw, config)
                
                # Filtra apenas os críticos reais baseados na normalização
                crit_indices = df_proc[df_proc['log_level'].isin(['Error', 'Fail', 'Critical', 'Fatal'])].index
                df_watchdog = df_watchdog_raw.loc[crit_indices]
            else:
                df_watchdog = pd.DataFrame()

            if not df_watchdog.empty:
                # Marca que estamos em estado de erro
                watchdog_in_error_state = True
                last_watchdog_error_time = time.time()
                
                # Salva logs críticos no banco para análise posterior
                logger.warning(f"Watchdog: {len(df_watchdog)} logs suspeitos encontrados.")
                lam.ingest_logs_to_db(df_watchdog)

                logger.debug("\n--- DADOS RECEBIDOS DO GRAYLOG (WATCHDOG) ---")
                logger.debug(df_watchdog.to_string())
                logger.debug("---------------------------------------------\n")

                if webhook_url:
                    logger.info("Erros Críticos Detectados! Acionando IA Watchdog...")
                    latest_err = df_watchdog.iloc[0]
                    
                    # Formata tabela com campos específicos do container/graylog
                    corpo_tabela = lam.format_graylog_table(latest_err)
                    
                    # Análise IA
                    prompt_ia = f"Resuma este erro e sugira uma solução técnica breve: {latest_err['message']}"
                    analise_ia = lam.send_chat_message([{"role": "user", "content": prompt_ia}])
                    
                    final_alert = f"**IA Insight:** {analise_ia}\n\n---\n{corpo_tabela}\n\nVer no Dashboard"
                    
                    send_err = lam.send_webhook_alert(webhook_url, final_alert, title="🔥 Watchdog IA detectou falha")
                    if isinstance(send_err, str):
                        logger.error(f"Falha ao enviar alerta para o Teams: {send_err}")
                    else:
                        logger.info(f"Alerta enviado com sucesso para o Teams. (Status: {send_err.status_code})")
            else:
                logger.info(f"Nenhum log crítico encontrado neste ciclo. (Query: {query_watchdog})")
                
                # Lógica de Recuperação: Se estava em erro e passou o tempo de silêncio, avisa que resolveu
                if watchdog_in_error_state:
                    if (time.time() - last_watchdog_error_time) > WATCHDOG_RECOVERY_WINDOW:
                        if webhook_url:
                            logger.info("Watchdog: Sistema recuperado. Enviando alerta de resolução.")
                            lam.send_webhook_alert(webhook_url, "✅ O Watchdog não detectou novos erros críticos nos últimos 10 minutos. O incidente parece ter sido mitigado.", title="✅ Incidente Resolvido (Watchdog)")
                        
                        watchdog_in_error_state = False

            # 3. SYNTHETICS
            lam.run_synthetic_check("Google", "https://www.google.com")
            
            # 4. GRAYLOG HEALTH (Monitoramento do Cluster)
            # Verifica Throughput e Status do Load Balancer usando os endpoints sugeridos
            if url:
                graylog_alive = False
                
                throughput = lam.get_graylog_system_stats(url, user, password, "/system/throughput")
                if throughput:
                    in_rate = throughput.get('throughput', 0)
                    logger.info(f"Graylog Throughput: {in_rate} msg/s")
                    graylog_alive = True
                
                lb_status = lam.get_graylog_system_stats(url, user, password, "/system/lbstatus")
                if lb_status:
                    status = lb_status.get('status', 'UNKNOWN')
                    logger.info(f"Graylog LB Status: {status}")
                    graylog_alive = True
                    
                    # Alerta se o status não for saudável (ALIVE é o padrão do Graylog)
                    if status not in ["ALIVE", "OK"]:
                        if webhook_url:
                            if (time.time() - last_graylog_alert_time) > ALERT_COOLDOWN:
                                lam.send_webhook_alert(webhook_url, f"⚠️ O Healthcheck do Graylog retornou status: **{status}**.", title="⚠️ Graylog Unhealthy")
                                last_graylog_alert_time = time.time()
                            else:
                                logger.warning("Alerta de Graylog Unhealthy suprimido (Cooldown ativo).")
                    else:
                        # Se estava em estado de alerta (last_graylog_alert_time > 0), envia recuperação
                        if last_graylog_alert_time > 0:
                            if webhook_url:
                                lam.send_webhook_alert(webhook_url, f"✅ O Graylog voltou a responder (Status: {status}).", title="✅ Graylog Recuperado")
                            logger.info("Graylog recuperado. Resetando cooldown.")

                        # Reseta o timer se o serviço estiver saudável, permitindo novo alerta imediato se cair novamente
                        last_graylog_alert_time = 0
                else:
                    # Se falhar o LB Status, verifica se o throughput funcionou
                    if graylog_alive:
                        logger.warning("Graylog LB Status: Indisponível (Endpoint não respondeu), mas API parece online.")
                    else:
                        logger.error("Graylog Status: FALHA DE CONEXÃO (API Inacessível)")
                        if webhook_url:
                            if (time.time() - last_graylog_alert_time) > ALERT_COOLDOWN:
                                lam.send_webhook_alert(webhook_url, f"❌ O Scheduler não conseguiu conectar na API do Graylog ({url}).", title="🚨 Graylog Offline")
                                last_graylog_alert_time = time.time()
                            else:
                                logger.warning("Alerta de Graylog Offline suprimido (Cooldown ativo).")

            # 5. LOG COLLECTOR HEALTH CHECK
            # Verifica se o processo log_collector.py está rodando
            collector_running = False
            for proc in psutil.process_iter(['cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline:
                        # Verifica se algum argumento contém 'log_collector.py'
                        if any('log_collector.py' in arg for arg in cmdline):
                            collector_running = True
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            if not collector_running:
                logger.error("CRITICAL: O processo log_collector.py não foi encontrado!")
                
                # Tentativa de Reinício Automático
                try:
                    logger.info("🔄 Tentando reiniciar o log_collector.py automaticamente...")
                    subprocess.Popen([sys.executable, "log_collector.py"])
                except Exception as e:
                    logger.error(f"❌ Falha ao reiniciar log_collector.py: {e}")

                if webhook_url:
                    if (time.time() - last_collector_alert_time) > ALERT_COOLDOWN:
                        lam.send_webhook_alert(webhook_url, "❌ O processo **log_collector.py** parou de rodar. O Scheduler tentou reiniciá-lo automaticamente.", title="🚨 Log Collector Reiniciado")
                        last_collector_alert_time = time.time()
                    else:
                        logger.warning("Alerta de Log Collector Parado suprimido (Cooldown ativo).")
            elif last_collector_alert_time > 0:
                if webhook_url:
                    lam.send_webhook_alert(webhook_url, "✅ O processo **log_collector.py** foi detectado em execução novamente.", title="✅ Log Collector Recuperado")
                logger.info("Log Collector recuperado. Resetando cooldown.")
                last_collector_alert_time = 0

            logger.info("Ciclo concluído com sucesso.")
            
        except Exception as e:
            logger.exception(f"Erro: {e}")
            
        time.sleep(300)

if __name__ == "__main__":
    # Registra os sinais de encerramento do Docker/OS
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    if "--test-webhook" in sys.argv:
        logger.info("--- Teste de Webhook (Teams) ---")
        webhook_url = lam.get_setting("TEAMS_WEBHOOK_URL")
        if not webhook_url:
            logger.error("Erro: URL do Webhook não configurada (ENV: TEAMS_WEBHOOK_URL).")
        else:
            logger.info("Enviando mensagem de teste para o Teams...")
            err = lam.send_webhook_alert(webhook_url, "Esta é uma mensagem de teste enviada pelo Scheduler.", title="🔔 Teste de Conexão Scheduler")
            
            if isinstance(err, str):
                logger.error(f"Falha no envio: {err}")
                sys.exit(1)
            else:
                logger.info(f"Mensagem enviada com sucesso! (Status: {err.status_code})")
    elif "--simulate-watchdog" in sys.argv:
        logger.info("--- Simulação de Watchdog (Teste Completo) ---")
        webhook_url = lam.get_setting("TEAMS_WEBHOOK_URL")
        
        if not webhook_url:
            logger.error("Erro: URL do Webhook não configurada.")
        else:
            logger.info("1. Gerando log crítico simulado...")
            # Cria um DataFrame falso imitando o retorno do Graylog
            fake_data = {
                "timestamp": [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                "source": ["Simulacao-Teste"],
                "message": ["EXCEPTION | Critical database connection timeout detected in production DB."],
                "level": [3],
                "LogLevel": ["Critical"],
                "container_name": ["postgres-prod"],
                "image_name": ["postgres:13-alpine"],
                "command": ["docker-entrypoint.sh"],
                "cpu_valor": [85.5],
                "mem_valor": [92.1],
                "RequestPath": ["/api/v1/transaction/process"]
            }
            df_fake = pd.DataFrame(fake_data)
            latest_err = df_fake.iloc[0]
            
            logger.info("2. Formatando tabela e consultando IA...")
            corpo_tabela = lam.format_graylog_table(latest_err)
            analise_ia = lam.send_chat_message([{"role": "user", "content": f"Resuma este erro de teste: {latest_err['message']}"}])
            
            final_alert = f"**[TESTE SIMULADO] IA Insight:** {analise_ia}\n\n---\n{corpo_tabela}\n\nVer no Dashboard"
            
            logger.info("3. Enviando alerta para o Teams...")
            err = lam.send_webhook_alert(webhook_url, final_alert, title="🔥 Watchdog Simulado")
            
            if isinstance(err, str):
                logger.error(f"Falha no envio: {err}")
                sys.exit(1)
            else:
                logger.info(f"Simulação concluída! (Status: {err.status_code}) Verifique seu Teams.")
    else:
        run_scheduler()