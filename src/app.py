# app.py
import sys
import subprocess
import asyncio
import os
import httpx

# Tenta carregar variáveis de ambiente de um arquivo .env (Desenvolvimento Local)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import aiohttp
import time
from fastapi import FastAPI, Request, WebSocket, Response
from fastapi.responses import StreamingResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI()

# --- Métricas Prometheus ---
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP Requests", ["method", "endpoint", "status_code"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "HTTP Request Duration", ["method", "endpoint"])

# Cliente HTTP Global para o Proxy (Evita fechar conexões prematuramente)
HTTP_CLIENT = None

# Middleware de Logging de Requisições
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    
    # Ignora healthcheck e metrics para não poluir logs e métricas
    if not request.url.path.endswith("/health") and not request.url.path.endswith("_stcore/health") and not request.url.path.endswith("/metrics"):
        # Registra métricas (convertendo ms para segundos para o padrão Prometheus)
        REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path, status_code=response.status_code).inc()
        REQUEST_LATENCY.labels(method=request.method, endpoint=request.url.path).observe(process_time / 1000)
        
        print(f"🔍 {request.method} {request.url.path} - {response.status_code} ({process_time:.2f}ms)")
    return response

# Armazena referências aos processos em background para monitoramento
service_processes = {
    "streamlit": None,
    "scheduler": None,
    "collector": None
}

# Configurações Internas
STREAMLIT_PORT = 8502
STREAMLIT_URL = f"http://127.0.0.1:{STREAMLIT_PORT}"
STREAMLIT_WS_URL = f"ws://127.0.0.1:{STREAMLIT_PORT}/_stcore/stream"

from contextlib import asynccontextmanager

async def start_system_services():
    """Inicia Streamlit, Scheduler e Collector quando o FastAPI sobe."""
    # Se estiver rodando via Docker (gerenciado pelo entrypoint.sh), não inicia subprocessos aqui
    if os.getenv("ORCHESTRATOR") == "docker":
        print("--- Modo Docker detectado: Subprocessos gerenciados pelo Entrypoint ---")
        return

    print(f"--- Iniciando Streamlit na porta {STREAMLIT_PORT} ---")

    cmd = [
        sys.executable, "-m", "streamlit", "run", "dashboard.py",
        "--server.port", str(STREAMLIT_PORT),
        "--server.headless", "true",
        "--server.address", "127.0.0.1",
        "--server.fileWatcherType", "none",
        "--client.showSidebarNavigation", "false",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false",
        "--server.enableWebsocketCompression", "false"
    ]
    # Inicia o processo sem bloquear o Uvicorn
    service_processes["streamlit"] = subprocess.Popen(cmd)

    # Inicia o Scheduler (Watchdog & Alertas)
    print("--- Iniciando Scheduler (Watchdog) ---")
    service_processes["scheduler"] = subprocess.Popen([sys.executable, "scheduler.py"])

    # Inicia o Log Collector (InfluxDB)
    print("--- Iniciando Log Collector ---")
    # O coletor possui lógica de retry; se falhar 10x, ele encerra o processo.
    # O status abaixo refletirá isso.
    service_processes["collector"] = subprocess.Popen([sys.executable, "log_collector.py"])
    
    # Aguarda o Streamlit estar pronto (Healthcheck interno)
    async with httpx.AsyncClient() as client:
        for i in range(30):
            try:
                await client.get(f"{STREAMLIT_URL}/_stcore/health")
                print("--- Streamlit detectado e pronto! ---")
                
                # Log de ajuda para o usuário (especialmente em dev local)
                ext_port = os.getenv("EXTERNAL_PORT")
                if ext_port:
                    print(f"\n🚀 APLICAÇÃO DISPONÍVEL EM: http://localhost:{ext_port}")
                    print(f"⚠️  (Ignore a URL http://127.0.0.1:{STREAMLIT_PORT} exibida pelo Streamlit acima)\n")
                return
            except Exception:
                await asyncio.sleep(1)
    print("AVISO: Streamlit demorou para responder, mas o proxy continuará tentando.")

# ✅ 2. Lifespan chama a função — sem @app.on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    global HTTP_CLIENT
    # Inicializa o cliente global com timeout maior para evitar quedas em cargas pesadas
    HTTP_CLIENT = httpx.AsyncClient(base_url=STREAMLIT_URL, follow_redirects=True, timeout=120.0)
    
    await start_system_services()
    yield
    
    # Fecha o cliente corretamente ao desligar o app
    if HTTP_CLIENT:
        await HTTP_CLIENT.aclose()
    
    # Garante que subprocessos sejam mortos
    for proc in service_processes.values():
        if proc and proc.poll() is None:
            proc.terminate()

# ✅ 3. App criado com lifespan
app = FastAPI(lifespan=lifespan)

# 1. Proxy WebSocket (Crucial para o funcionamento do Streamlit)
@app.websocket("/_stcore/stream")
async def websocket_proxy(ws_client: WebSocket):
    await ws_client.accept()

    # Repassa apenas os Cookies para manter a sessão do Streamlit
    # Headers como Origin/Host são ignorados para evitar bloqueios de segurança
    headers = {}
    if "cookie" in ws_client.headers:
        headers["Cookie"] = ws_client.headers["cookie"]
    
    try:
        async with aiohttp.ClientSession() as session:
            # Conecta ao backend do Streamlit usando aiohttp
            # compress=False: Desativa compressão para evitar conflitos
            # autoping=True: Responde automaticamente aos pings do Streamlit
            async with session.ws_connect(
                STREAMLIT_WS_URL, 
                headers=headers, 
                compress=False, 
                autoping=True
            ) as ws_server:
                
                # Tarefa: Cliente (Browser) -> Streamlit
                async def client_to_server():
                    try:
                        while True:
                            message = await ws_client.receive()
                            
                            if message["type"] == "websocket.disconnect":
                                print("🔌 WS: Browser desconectou.")
                                await ws_server.close()
                                break
                            
                            if "text" in message:
                                await ws_server.send_str(message["text"])
                            elif "bytes" in message:
                                await ws_server.send_bytes(message["bytes"])
                    except Exception as e:
                        print(f"❌ WS Client->Server Error: {e}")

                # Tarefa: Streamlit -> Cliente (Browser)
                async def server_to_client():
                    try:
                        async for msg in ws_server:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await ws_client.send_text(msg.data)
                            elif msg.type == aiohttp.WSMsgType.BINARY:
                                await ws_client.send_bytes(msg.data)
                            elif msg.type == aiohttp.WSMsgType.CLOSE:
                                print("🔌 WS: Streamlit fechou a conexão.")
                                await ws_client.close()
                                break
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                print(f"❌ WS: Erro no socket do Streamlit: {ws_server.exception()}")
                                break
                    except Exception as e:
                        print(f"❌ WS Server->Client Error: {e}")

                # Gerencia as tarefas: se uma cair, cancela a outra
                done, pending = await asyncio.wait(
                    [asyncio.create_task(client_to_server()), asyncio.create_task(server_to_client())],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
            
    except Exception as e:
        print(f"Erro no Proxy WebSocket (aiohttp): {e}")
    finally:
        try:
            await ws_client.close()
        except:
            pass

# Rota de Diagnóstico de Variáveis de Ambiente
@app.get("/env-status")
async def env_status():
    """Verifica se as variáveis críticas estão carregadas (mascaradas)."""
    critical_vars = [
        "GROQ_API_KEY", "JIRA_WEBHOOK_URL", "JIRA_API_KEY",
        "GRAYLOG_API_URL", "GRAYLOG_USER", "GRAYLOG_PASSWORD",
        "TEAMS_WEBHOOK_URL"
    ]
    
    status = {}
    missing = []
    
    for var in critical_vars:
        val = os.environ.get(var)
        if not val:
            status[var] = "❌ AUSENTE"
            missing.append(var)
        else:
            masked = f"{val[:4]}...{val[-2:]}" if len(val) > 6 else "******"
            status[var] = f"✅ Carregada ({masked})"

    # --- Verificação de Conectividade com Graylog ---
    graylog_url = os.environ.get("GRAYLOG_API_URL")
    graylog_user = os.environ.get("GRAYLOG_USER")
    graylog_pass = os.environ.get("GRAYLOG_PASSWORD")
    
    graylog_check = "N/A"
    
    if graylog_url and graylog_user and graylog_pass:
        try:
            # Normaliza URL (garante /api no final)
            base_url = graylog_url.strip().rstrip('/')
            if not base_url.endswith('/api'):
                base_url += '/api'
            
            async with httpx.AsyncClient(verify=False, timeout=3.0) as client:
                resp = await client.get(f"{base_url}/system/lbstatus", auth=(graylog_user, graylog_pass))
                if resp.status_code == 200:
                    graylog_check = f"✅ ONLINE (Status: {resp.json().get('status', 'OK')})"
                else:
                    graylog_check = f"❌ ERRO {resp.status_code}"
        except Exception as e:
            graylog_check = f"❌ FALHA: {str(e)}"
            
    # --- Verificação de Conectividade com InfluxDB ---
    influx_url = os.environ.get("INFLUXDB_URL", "http://influxdb-staging:8086")
    influx_check = "N/A"
    
    if influx_url:
        try:
            base_url = influx_url.strip().rstrip('/')
            async with httpx.AsyncClient(timeout=3.0) as client:
                # Endpoint padrão de health do InfluxDB 2.x
                resp = await client.get(f"{base_url}/health")
                if resp.status_code == 200:
                    # O Influx retorna JSON com status: "pass"
                    data = resp.json()
                    status_msg = data.get("status", "OK")
                    influx_check = f"✅ ONLINE ({status_msg})"
                else:
                    influx_check = f"❌ ERRO {resp.status_code}"
        except Exception as e:
            influx_check = f"❌ FALHA: {str(e)}"

    # --- Status dos Processos em Background ---
    services_status = {}
    for name, proc in service_processes.items():
        if proc is None:
            services_status[name] = "❌ NÃO INICIADO"
        elif proc.poll() is None:
            services_status[name] = f"✅ RODANDO (PID: {proc.pid})"
        else:
            services_status[name] = f"❌ PARADO (Exit Code: {proc.returncode})"

    return {
        "status": "ERROR" if missing else "OK", 
        "details": status, 
        "graylog_connectivity": graylog_check,
        "influxdb_connectivity": influx_check,
        "background_services": services_status
    }

# Rota de Métricas (Prometheus)
@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Rota de Healthcheck (Liveness Probe)
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# --- Redirecionamentos de URL Amigáveis ---
@app.get("/executive")
async def redirect_dashboard(): return RedirectResponse(url="/?page=executive")

@app.get("/investigation")
async def redirect_investigation(): return RedirectResponse(url="/?page=investigation")

@app.get("/intelligence")
async def redirect_intelligence(): return RedirectResponse(url="/?page=intelligence")

@app.get("/custom-metrics")
async def redirect_custom_metrics(): return RedirectResponse(url="/?page=custom-metrics")

@app.get("/rum")
async def redirect_rum(): return RedirectResponse(url="/?page=rum")

@app.get("/infrastructure")
async def redirect_infrastructure(): return RedirectResponse(url="/?page=infrastructure")

@app.get("/api-monitoring")
async def redirect_api_monitoring(): return RedirectResponse(url="/?page=api-monitoring")

@app.get("/tools")
async def redirect_tools(): return RedirectResponse(url="/?page=tools")

# --- Arquivos Estáticos ---
# Monta a pasta 'static' para servir CSS/JS/Imagens em /static (se existir)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve o favicon.ico na raiz
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    if os.path.exists("favicon.ico"):
        return FileResponse("favicon.ico")
    return Response(status_code=204) # Retorna No Content se não existir

# 2. Proxy HTTP Genérico (Catch-All)
# Captura /, /static, /_stcore/health, etc.
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def proxy_http(request: Request, path: str):
    # Usa o cliente global que não é fechado ao final da função
    client = HTTP_CLIENT
    
    url = request.url.path
    
    if request.url.query:
        url += "?" + request.url.query

    # Remove headers que podem causar conflito no proxy
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)

    try:
        rp_req = client.build_request(
            request.method,
            url,
            headers=headers,
            content=await request.body()
        )
        # Envia a requisição mantendo o stream aberto
        rp_resp = await client.send(rp_req, stream=True)
        
        # Gerador assíncrono que garante o fechamento da resposta após o stream
        async def stream_response():
            try:
                async for chunk in rp_resp.aiter_raw():
                    yield chunk
            finally:
                await rp_resp.aclose()
        
        return StreamingResponse(
            stream_response(),
            status_code=rp_resp.status_code,
            headers=dict(rp_resp.headers),
            background=None
        )
    except Exception as e:
        return Response(f"Erro de conexão com o Dashboard: {e}", status_code=502)