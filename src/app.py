import os
import pandas as pd
import re
import httpx
import shutil
import time
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form
import asyncio
from typing import Optional, List, Dict, Any, Union
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from datetime import datetime
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from io import StringIO
from fastapi import Depends
try:
    import log_analyzer as lam
except ImportError:
    from src import log_analyzer as lam
import numpy as np

# Importa o módulo refatorado de detecção de anomalias
try:
    from log_analyzer_lib import anomaly_detection
except ImportError:
    from src.log_analyzer_lib import anomaly_detection

try:
    from default_metrics import DEFAULT_CUSTOM_METRICS
except ImportError:
    from src.default_metrics import DEFAULT_CUSTOM_METRICS

# Carrega variáveis de ambiente do .env
try:
    from dotenv import load_dotenv
    # Busca o .env na raiz do projeto (um nível acima de /src)
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    load_dotenv(env_path)
except ImportError:
    print("dotenv não instalado, pulando carregamento de .env")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia os eventos de startup e shutdown da aplicação."""
    # --- Startup ---
    get_config() # Pré-carrega a configuração no cache do app.state

    # Verifica se as variáveis de ambiente essenciais estão presentes no startup.
    # O código que as utiliza (os.getenv) irá lê-las diretamente do ambiente.
    # A lógica anterior de carregar segredos era redundante.
    required_vars = ["GRAYLOG_API_URL", "GRAYLOG_USER", "GRAYLOG_PASSWORD", "GROQ_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        # Em um ambiente de produção, isso ajuda a diagnosticar problemas de configuração rapidamente.
        print(f"AVISO: As seguintes variáveis de ambiente críticas estão faltando: {', '.join(missing_vars)}")

    yield
    # --- Shutdown ---
    # (Nenhuma ação de shutdown necessária no momento)

app = FastAPI(
    title="Lockton Log Analytics",
    description="API para análise e visualização de logs.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# --- Configuração de Diretórios e Migração Automática ---
base_dir = os.path.dirname(__file__)
static_path = os.path.join(base_dir, "static")
templates_path = os.path.join(base_dir, "templates")

# Garante estrutura de pastas
os.makedirs(static_path, exist_ok=True)
os.makedirs(templates_path, exist_ok=True)
os.makedirs(os.path.join(templates_path, "partials"), exist_ok=True)

# Monta o diretório 'static' para servir arquivos estáticos (Imagens, CSS, JS)
app.mount("/static", StaticFiles(directory=static_path), name="static")
templates = Jinja2Templates(directory=templates_path)

# --- Estado Global (Simples) ---
# Em produção, considere usar um cache mais robusto como Redis
# Para este exemplo, vamos manter os dataframes em memória.
app.state.raw_df = None
app.state.display_df = None
app.state.last_filters = None # Cache para os filtros aplicados
app.state.config = None # Cache para a configuração
# Pré-popula com métricas comuns para facilitar o uso inicial a partir do arquivo default_metrics.py
app.state.custom_metrics = DEFAULT_CUSTOM_METRICS.copy()

class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]

class LoadTestRequest(BaseModel):
    url: str
    requests: int = 100
    concurrency: int = 10
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    body: Optional[Any] = None

class AdvancedLoadTestRequest(BaseModel):
    url: str
    duration_seconds: int = 30
    concurrency: int = 10
    ramp_up_seconds: int = 0
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    body: Optional[Any] = None

class ParseRequest(BaseModel):
    raw_message: str


# --- Modelos para Agregação do Graylog ---
class AggregationRequest(BaseModel):
    query: str = Field(default="*", description="A query string para a busca. Ex: 'http_response_code:>=400'")
    timerange_type: str = Field(default="relative", description="Tipo de time range: 'relative' ou 'absolute'")
    timerange_range: int = Field(default=3600, description="Para 'relative', o tempo em segundos a partir de agora.")
    search_types: List[Dict[str, Any]] = Field(description="Lista de definições de agregação para o Graylog.")

class AggregationResponse(BaseModel):
    results: Dict[str, Any] = Field(description="Um dicionário contendo os resultados de cada agregação solicitada.")
    execution_time_ms: int = Field(description="Tempo que o Graylog levou para executar a busca, em milissegundos.")

# --- Endpoints da API ---

def get_config() -> Union[Dict, None]:
    """
    Dependency function to load and cache the application configuration.
    This allows for easier testing by overriding this dependency.
    """
    if not hasattr(app.state, 'config') or app.state.config is None:
        config, error_msg = lam.load_config()
        if error_msg:
            print(f"AVISO: {error_msg}")
            app.state.config = {} # Cache an empty dict on failure
        else:
            app.state.config = config
    
    if not app.state.config: # If it's an empty dict from a failed load
        return None
    return app.state.config

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve a página principal da aplicação (index.html)."""
    return templates.TemplateResponse(request, "index.html")

@app.get("/health", tags=["Health"])
def health_check():
    """Verificação de saúde usada pelo Docker HEALTHCHECK."""
    return {"status": "ok"}

@app.post("/api/upload-csv")
async def upload_csv(file: UploadFile = File(...), config: dict = Depends(get_config)):
    """Endpoint para fazer upload de um arquivo CSV de logs."""
    if file.content_type != 'text/csv':
        raise HTTPException(status_code=400, detail="Tipo de arquivo inválido. Por favor, envie um CSV.")
    
    if not config:
        raise HTTPException(status_code=500, detail="Erro ao processar o arquivo: A configuração para categorização é inválida.")

    try:
        contents = await file.read()
        string_io = StringIO(contents.decode('utf-8'))
        df = pd.read_csv(string_io, header=None, names=['timestamp', 'source', 'message'])
        
        # Processa e armazena o dataframe
        raw_df, _ = lam.process_log_data(df, config)
        app.state.raw_df = raw_df
        app.state.display_df = None # Invalida o cache de filtro
        
        return {"filename": file.filename, "records": len(raw_df), "message": "Arquivo processado com sucesso."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar o arquivo: {e}")

@app.post("/api/load-graylog")
async def load_from_graylog(query: str = "*", range_seconds: int = 300, limit: int = 10000, config: dict = Depends(get_config)):
    """Endpoint para buscar logs da API do Graylog."""
    api_url = os.getenv("GRAYLOG_API_URL")
    user = os.getenv("GRAYLOG_USER")
    password = os.getenv("GRAYLOG_PASSWORD")

    if not all([api_url, user, password]):
        raise HTTPException(status_code=400, detail="Credenciais do Graylog não configuradas no ambiente.")

    if not config:
        raise HTTPException(status_code=500, detail="Erro ao processar o arquivo: A configuração para categorização é inválida.")

    try:
        df, error = lam.fetch_logs_from_graylog(api_url, user, password, query, range_seconds, limit)
        if error:
            raise HTTPException(status_code=500, detail=f"Erro ao buscar logs do Graylog: {error}")
        
        if df is None or df.empty:
            return {"records": 0, "message": "Nenhum log encontrado no Graylog para os critérios."}

        # Processa e armazena o dataframe
        raw_df, _ = lam.process_log_data(df, config)
        app.state.raw_df = raw_df
        app.state.display_df = None # Invalida o cache de filtro
        
        return {"records": len(raw_df), "message": f"{len(raw_df)} logs carregados do Graylog."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/logs/aggregate", response_model=AggregationResponse, tags=["Graylog Advanced"])
async def get_log_aggregations(request: AggregationRequest):
    """
    Executa uma busca com agregações no Graylog para popular gráficos e tabelas.

    Este endpoint permite construir visualizações complexas (gráficos de série temporal,
    tabelas de valores, etc.) com uma única chamada, de forma similar ao Grafana.
    """
    # Esta função interna encapsula a lógica de chamada da API
    async def execute_aggregation_search(req: AggregationRequest) -> dict:
        GRAYLOG_API_URL = os.getenv("GRAYLOG_API_URL")
        GRAYLOG_USER = os.getenv("GRAYLOG_USER")
        GRAYLOG_PASSWORD = os.getenv("GRAYLOG_PASSWORD")

        if not all([GRAYLOG_API_URL, GRAYLOG_USER, GRAYLOG_PASSWORD]):
            raise HTTPException(status_code=400, detail="Credenciais do Graylog não configuradas no ambiente.")

        graylog_payload = {
            "query": {"type": "elasticsearch", "query_string": req.query},
            "timerange": {"type": req.timerange_type, "range": req.timerange_range},
            "search_types": req.search_types,
        }

        search_url = f"{GRAYLOG_API_URL}/views/search/sync"
        auth = (GRAYLOG_USER, GRAYLOG_PASSWORD)
        headers = {"X-Requested-By": "LogAnalyticsDashboard"}

        async with httpx.AsyncClient(auth=auth, headers=headers) as client:
            try:
                response = await client.post(search_url, json=graylog_payload, timeout=30.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                print(f"Error calling Graylog API: {e.response.text}")
                raise HTTPException(status_code=e.response.status_code, detail=f"Error from Graylog API: {e.response.text}")
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                raise HTTPException(status_code=500, detail="Internal server error while contacting Graylog.")

    graylog_result = await execute_aggregation_search(request)

    return AggregationResponse(
        results=graylog_result.get("results", {}),
        execution_time_ms=graylog_result.get("execution", {}).get("duration", 0)
    )

# --- Graylog Monitoring Endpoints ---

def get_graylog_credentials():
    """Helper to get Graylog credentials from environment variables."""
    url = os.getenv("GRAYLOG_API_URL")
    user = os.getenv("GRAYLOG_USER")
    password = os.getenv("GRAYLOG_PASSWORD")
    if not all([url, user, password]):
        raise HTTPException(status_code=400, detail="Credenciais do Graylog não configuradas no ambiente.")
    return url, user, password

@app.get("/api/streams", summary="Lista streams e seu throughput", tags=["Graylog Monitoring"])
async def get_streams_status():
    """
    Retorna uma lista de todas as streams ativas do Graylog, 
    combinadas com suas métricas de throughput (mensagens por segundo).
    """
    url, user, password = get_graylog_credentials()
    
    streams, err = lam.get_graylog_streams_with_throughput(url, user, password)
    
    if err:
        raise HTTPException(status_code=500, detail=err)
        
    return {"streams": streams}

@app.get("/api/streams/{stream_id}/details", summary="Get details and rules for a specific stream", tags=["Graylog Monitoring"])
async def get_stream_details(stream_id: str):
    url, user, password = get_graylog_credentials()
    details, err = lam.get_graylog_stream_details(url, user, password, stream_id)
    if err:
        raise HTTPException(status_code=500, detail=err)
    return details

@app.get("/api/alerts/definitions", summary="Lista todas as regras de alerta", tags=["Graylog Monitoring"])
async def get_alert_definitions():
    url, user, password = get_graylog_credentials()
    data, err = lam.get_graylog_alert_definitions(url, user, password)
    if err:
        raise HTTPException(status_code=500, detail=err)
    return data

@app.get("/api/alerts/triggered", summary="Lista os alertas disparados recentemente", tags=["Graylog Monitoring"])
async def get_triggered_alerts():
    url, user, password = get_graylog_credentials()
    data, err = lam.get_graylog_triggered_alerts(url, user, password)
    if err:
        raise HTTPException(status_code=500, detail=err)
    return data

@app.put("/api/alerts/definitions/{alert_id}/schedule", summary="Ativa um alerta", tags=["Graylog Monitoring"])
async def enable_alert_schedule(alert_id: str):
    url, user, password = get_graylog_credentials()
    _, err = lam.toggle_graylog_alert_schedule(url, user, password, alert_id, enable=True)
    if err:
        raise HTTPException(status_code=500, detail=err)
    return {"status": "success", "message": f"Alerta {alert_id} ativado."}

@app.delete("/api/alerts/definitions/{alert_id}/schedule", summary="Desativa um alerta", tags=["Graylog Monitoring"])
async def disable_alert_schedule(alert_id: str):
    url, user, password = get_graylog_credentials()
    _, err = lam.toggle_graylog_alert_schedule(url, user, password, alert_id, enable=False)
    if err:
        raise HTTPException(status_code=500, detail=err)
    return {"status": "success", "message": f"Alerta {alert_id} desativado."}

@app.get("/api/data/summary")
def get_data_summary():
    """Retorna um resumo dos dados carregados (para a Visão Executiva)."""
    # Lógica desacoplada para o log_analyzer.py para otimização e manutenção
    return lam.compute_data_summary(app.state.raw_df)

@app.get("/api/data/volume-series")
def get_volume_series():
    """Retorna dados da série temporal de volume (desacoplado para performance)."""
    # Processamento pesado isolado em endpoint dedicado
    return lam.compute_volume_series(app.state.raw_df)

@app.get("/api/data/filters")
async def get_filters():
    """Retorna as opções de filtro disponíveis (Levels e Sources).
    
    - Levels são derivados dos dados atualmente carregados.
    - Sources são buscados diretamente do Graylog para uma lista completa.
    """
    # Levels são derivados dos dados atualmente carregados na memória
    levels = []
    if app.state.raw_df is not None:
        levels = sorted([str(x) for x in app.state.raw_df['log_level'].unique() if pd.notna(x)])
    
    # Sources são buscados do Graylog para garantir uma lista completa (últimas 24h)
    sources = []
    try:
        api_url = os.getenv("GRAYLOG_API_URL")
        user = os.getenv("GRAYLOG_USER")
        password = os.getenv("GRAYLOG_PASSWORD")

        if all([api_url, user, password]):
            # Sanitiza a URL base para evitar erros de 404 por malformação
            api_url = api_url.strip().rstrip('/')
            if not api_url.endswith('/api'):
                api_url += '/api'

            # Use the simpler 'terms' endpoint which is more robust
            search_url = f"{api_url}/search/universal/relative/terms"
            params = {
                "query": "*",
                "range": 86400, # 24 hours
                "field": "source",
                "limit": 500
            }

            auth = (user, password)
            headers = {"Accept": "application/json", "X-Requested-By": "LogAnalyticsDashboard"}

            async with httpx.AsyncClient(auth=auth, headers=headers) as client:
                response = await client.get(search_url, params=params, timeout=20.0)
                response.raise_for_status()
                result = response.json()
                
                if "terms" in result:
                    sources = sorted(result["terms"].keys())

    except httpx.HTTPStatusError as e:
        if e.response.status_code != 404: # Ignora 404 silenciosamente (fallback local)
            print(f"AVISO: Erro HTTP ao buscar filters do Graylog: {e}")
    except Exception as e:
        # Silencia erros genéricos de conexão na inicialização para não poluir o log
        if app.state.raw_df is not None:
            sources = sorted([str(x) for x in app.state.raw_df['source'].unique() if pd.notna(x)])

    return {"levels": levels, "sources": sources}

def get_filtered_dataframe(
    search: Optional[str] = None,
    level: Optional[str] = None,
    source: Optional[str] = None
) -> pd.DataFrame:
    """
    Retorna um DataFrame filtrado, usando um cache em `app.state` para performance.
    A filtragem (operação lenta) só é executada se os filtros mudarem.
    """
    if app.state.raw_df is None:
        return pd.DataFrame()

    current_filters = {
        "search": search,
        "level": level,
        "source": source
    }

    # Se os filtros mudaram ou o cache está inválido, refiltra.
    if app.state.display_df is None or app.state.last_filters != current_filters:
        df = app.state.raw_df
        
        if level and level != "Todos":
            df = df[df['log_level'] == level]
        if source and source != "Todos":
            df = df[df['source'] == source]
        if search:
            # Esta é a operação lenta que estamos otimizando
            df = df[df['message'].str.contains(search, case=False, na=False)]
        
        app.state.display_df = df
        app.state.last_filters = current_filters
    
    return app.state.display_df

@app.get("/api/data/logs")
def get_logs(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    level: Optional[str] = None,
    source: Optional[str] = None
):
    """Retorna logs paginados e filtrados."""
    df = get_filtered_dataframe(search, level, source)
    
    if df.empty:
        return {"data": [], "total": 0, "page": page, "pages": 0}

    total_records = len(df)
    total_pages = (total_records + limit - 1) // limit
    
    # Paginação
    start = (page - 1) * limit
    end = start + limit
    
    paginated_df = df.iloc[start:end].fillna("")
    
    return {
        "data": paginated_df.to_dict(orient='records'),
        "total": total_records,
        "page": page,
        "pages": total_pages
    }

@app.get("/api/data/export")
async def export_logs_to_csv(
    search: Optional[str] = None,
    level: Optional[str] = None,
    source: Optional[str] = None
):
    """Exporta os logs filtrados para um arquivo CSV."""
    if app.state.raw_df is None:
        raise HTTPException(status_code=404, detail="Nenhum dado carregado para exportar.")
    
    df = app.state.raw_df.copy()
    
    # Aplica os mesmos filtros da busca
    if level and level != "Todos":
        df = df[df['log_level'] == level]
    if source and source != "Todos":
        df = df[df['source'] == source]
    if search:
        df = df[df['message'].str.contains(search, case=False, na=False)]
        
    if df.empty:
        return Response(content="Nenhum dado para exportar com os filtros aplicados.", media_type="text/plain", status_code=204)

    # Gera o CSV em memória
    output = StringIO()
    df.to_csv(output, index=False)
    csv_content = output.getvalue()
    output.close()
    
    headers = {'Content-Disposition': 'attachment; filename="logs_export.csv"'}
    return Response(content=csv_content, media_type="text/csv", headers=headers)

@app.post("/api/analysis/ai")
def run_ai_analysis():
    """Executa análise de IA nos logs críticos (Síncrono para threadpool)."""
    if app.state.raw_df is None:
        return {"analysis": []}
    
    df = app.state.raw_df
    # Filtra erros críticos
    critical_df = df[df['log_level'].isin(['Error', 'Fail', 'Critical', 'Fatal'])]
    
    if critical_df.empty:
        return {"analysis": []}
        
    # Ordena por timestamp decrescente para pegar os mais recentes
    if 'timestamp' in critical_df.columns:
        critical_df = critical_df.sort_values('timestamp', ascending=False)

    # Limita aos top 3 para economizar tokens e tempo
    critical_df = critical_df.head(3)
    
    analyses = []
    for _, row in critical_df.iterrows():
        # Chama a função existente no log_analyzer
        analysis = lam.analyze_log_with_ai(row['message'])
        analyses.append({
            "timestamp": row['timestamp'],
            "message": row['message'],
            "analysis": analysis
        })
        
    return {"analysis": analyses}

@app.post("/api/analysis/initial-prompt", response_model=dict)
async def get_initial_prompt(log_data: lam.LogDataForPrompt):
    """
    Gera e retorna o prompt inicial do sistema para o chat da IA.
    """
    prompt = lam.generate_chat_system_prompt(log_data)
    return {"prompt": prompt}

@app.post("/api/analysis/chat")
async def chat_endpoint(request: ChatRequest):
    """Endpoint para chat interativo com a IA."""
    response = lam.send_chat_message(request.messages)
    return {"response": response}

@app.get("/api/analysis/forecast")
def get_forecast(periods: int = 30):
    """Gera previsão de volume de logs."""
    if app.state.raw_df is None:
        return {"trend": "neutral", "slope": 0, "data": []}
        
    df, trend, slope = anomaly_detection.generate_volume_forecast(app.state.raw_df, periods=periods)
    
    # Converte timestamp para string para serialização JSON
    if not df.empty:
        df['timestamp'] = df['timestamp'].astype(str)
    
    return {
        "trend": trend,
        "slope": slope,
        "data": df.to_dict(orient='records') if not df.empty else []
    }

@app.get("/api/analysis/anomalies")
def get_anomalies():
    """Detecta anomalias de volume."""
    if app.state.raw_df is None:
        return {"anomalies": []}
        
    anomalies = anomaly_detection.detect_volume_anomalies(app.state.raw_df)
    if not anomalies.empty:
        anomalies['timestamp'] = anomalies['timestamp'].astype(str)
    
    return {"anomalies": anomalies.to_dict(orient='records') if not anomalies.empty else []}

@app.get("/api/analysis/patterns")
def get_log_patterns(
    search: Optional[str] = None,
    level: Optional[str] = None,
    source: Optional[str] = None
):
    """Gera padrões de log (clustering) baseados nos filtros atuais."""
    df = get_filtered_dataframe(search, level, source)

    if df.empty:
        return {"patterns": []}
        
    patterns_df = lam.generate_log_patterns(df)
    
    # Converte timestamps para string
    if not patterns_df.empty:
        patterns_df['first_seen'] = patterns_df['first_seen'].astype(str)
        patterns_df['last_seen'] = patterns_df['last_seen'].astype(str)
        
    return {"patterns": patterns_df.to_dict(orient='records')}

@app.get("/api/analysis/security")
def get_security_threats():
    """Analisa ameaças de segurança (IPs suspeitos)."""
    if app.state.raw_df is None:
        return {"threats": []}
        
    threats_df = lam.analyze_security_threats(app.state.raw_df)
    return {"threats": threats_df.to_dict(orient='records') if not threats_df.empty else []}

@app.get("/api/analysis/dependencies")
def get_service_dependencies(
    search: Optional[str] = None,
    level: Optional[str] = None,
    source: Optional[str] = None
):
    """Retorna dependências de serviços (Service Map)."""
    if app.state.raw_df is None:
        return {"edges": []}
    
    df = app.state.raw_df.copy()
    
    # Aplica filtros
    if level and level != "Todos":
        df = df[df['log_level'] == level]
    if source and source != "Todos":
        df = df[df['source'] == source]
    if search:
        df = df[df['message'].str.contains(search, case=False, na=False)]
        
    if df.empty:
        return {"edges": []}
        
    dependencies = lam.infer_service_dependencies(df)
    return {"edges": dependencies.to_dict(orient='records')}

@app.get("/api/analysis/traces")
def get_traces_list(
    search: Optional[str] = None,
    level: Optional[str] = None,
    source: Optional[str] = None
):
    """Retorna lista de traces encontrados nos logs filtrados."""
    if app.state.raw_df is None:
        return {"traces": []}
    
    df = app.state.raw_df.copy()
    
    # Aplica filtros
    if level and level != "Todos":
        df = df[df['log_level'] == level]
    if source and source != "Todos":
        df = df[df['source'] == source]
    if search:
        df = df[df['message'].str.contains(search, case=False, na=False)]
        
    if df.empty:
        return {"traces": []}

    # Extrai Trace IDs
    df = lam.extract_trace_ids(df)
    
    if 'trace_id' not in df.columns:
        return {"traces": []}
        
    # Filtra apenas linhas com trace_id
    traces_df = df.dropna(subset=['trace_id'])
    
    if traces_df.empty:
        return {"traces": []}

    # Agregação
    summary = traces_df.groupby('trace_id').agg(
        start_time=('timestamp', 'min'),
        end_time=('timestamp', 'max'),
        count=('timestamp', 'count'),
        error_count=('log_level', lambda x: x.isin(['Error', 'Fail', 'Critical', 'Fatal']).sum())
    ).reset_index()
    
    # Calcula duração
    summary['duration_ms'] = (pd.to_datetime(summary['end_time']) - pd.to_datetime(summary['start_time'])).dt.total_seconds() * 1000
    
    # Ordena por mais recente e limita
    summary = summary.sort_values('start_time', ascending=False).head(50)
    
    # Formata para JSON
    summary['start_time'] = summary['start_time'].astype(str)
    summary['end_time'] = summary['end_time'].astype(str)
    
    return {"traces": summary.to_dict(orient='records')}

@app.get("/api/analysis/trace/{trace_id}")
def get_trace_details(trace_id: str):
    """Retorna detalhes de um trace específico (Gantt)."""
    if app.state.raw_df is None:
        return {"events": []}
        
    # Busca em todo o dataset (sem filtros) para pegar a transação completa
    df = app.state.raw_df
    
    # Otimização: Filtra linhas que contêm o ID antes de extrair (Regex é pesado)
    mask = df['message'].astype(str).str.contains(trace_id, case=False, na=False)
    potential_df = df[mask].copy()
    
    if potential_df.empty:
        raise HTTPException(status_code=404, detail="Trace ID não encontrado.")
        
    potential_df = lam.extract_trace_ids(potential_df)
    trace_df = potential_df[potential_df['trace_id'] == trace_id].copy()
    
    # Extrai latência para o gráfico de Gantt
    trace_df = lam.extract_latency_metrics(trace_df)
    # Se extract_latency_metrics retornou apenas colunas limitadas, precisamos mesclar ou garantir colunas
    # A função original retorna timestamp, source, latency_ms. Vamos assumir que queremos todas as colunas.
    # Simplificação: Recalcula latência aqui para garantir que temos 'message' e 'log_level'
    latency_pattern = r'(?:duration|time|took|latency|elapsed)[:=]\s*(\d+(?:\.\d+)?)(?:\s*(ms|s|sec|min|us|µs))?'
    extracted = trace_df['message'].astype(str).str.extract(latency_pattern, flags=re.IGNORECASE)
    
    trace_df['duration_ms'] = 0.0
    if not extracted.empty:
        vals = pd.to_numeric(extracted[0], errors='coerce').fillna(0)
        units = extracted[1].str.lower().fillna('ms')
        vals.loc[units == 's'] *= 1000
        vals.loc[units.isin(['us', 'µs'])] /= 1000
        trace_df['duration_ms'] = vals

    # Prepara eventos para o frontend
    events = []
    for _, row in trace_df.iterrows():
        ts = pd.to_datetime(row['timestamp'])
        dur = row['duration_ms'] if row['duration_ms'] > 0 else 50 # Mínimo visual 50ms
        start = ts - pd.Timedelta(milliseconds=dur)
        
        events.append({
            "source": row['source'],
            "message": row['message'][:100],
            "start": start.isoformat(),
            "end": ts.isoformat(),
            "duration": dur,
            "status": "Error" if row['log_level'] in ['Error', 'Fail', 'Critical', 'Fatal'] else "Success"
        })
        
    return {"events": events}

@app.get("/api/data/context")
def get_context_logs_endpoint(
    timestamp: str,
    source: str,
    window: int = 300
):
    """Retorna logs vizinhos (contexto) para um dado timestamp e source."""
    if app.state.raw_df is None:
        return {"logs": []}
    
    try:
        context_df = lam.get_context_logs(app.state.raw_df, timestamp, source, window_seconds=window)
        
        if context_df.empty:
            return {"logs": []}
            
        # Converte timestamp para string para serialização JSON
        context_df['timestamp'] = context_df['timestamp'].astype(str)
        
        return {"logs": context_df.to_dict(orient='records')}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar contexto: {str(e)}")

@app.post("/api/metrics/test")
async def test_metric_regex(regex: str = Form(...)):
    """Testa uma regex contra os logs carregados."""
    if app.state.raw_df is None:
         return {"count": 0, "preview": []}
    
    try:
        # Valida regex
        re.compile(regex)
        
        df = app.state.raw_df
        # Busca matches
        matches = df[df['message'].astype(str).str.contains(regex, regex=True, na=False)]
        count = len(matches)
        
        preview = []
        if count > 0:
            # Pega os top 5 para preview
            for _, row in matches.head(5).iterrows():
                found = re.findall(regex, str(row['message']))
                preview.append({
                    "timestamp": str(row['timestamp']),
                    "message": row['message'],
                    "matches": found
                })
                
        return {"count": count, "preview": preview}
    except re.error:
        raise HTTPException(status_code=400, detail="Expressão Regular inválida.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/metrics")
def list_metrics():
    """Lista métricas customizadas."""
    return app.state.custom_metrics

@app.post("/api/metrics")
def add_metric(name: str = Form(...), regex: str = Form(...), metric_type: str = Form(...)):
    """Adiciona uma nova métrica."""
    # Lógica de ID robusta para evitar duplicatas ao adicionar/remover métricas
    if app.state.custom_metrics:
        new_id = max(m['id'] for m in app.state.custom_metrics) + 1
    else:
        new_id = 1
        
    metric = {
        "id": new_id,
        "name": name,
        "regex": regex,
        "type": metric_type
    }
    app.state.custom_metrics.append(metric)
    return metric

@app.delete("/api/metrics/{metric_id}")
def remove_metric(metric_id: int):
    """Remove uma métrica."""
    app.state.custom_metrics = [m for m in app.state.custom_metrics if m['id'] != metric_id]
    return {"status": "success"}

@app.get("/api/metrics/{metric_id}/data")
async def get_metric_data(
    metric_id: int,
    search: Optional[str] = None,
    level: Optional[str] = None,
    source: Optional[str] = None
):
    """Retorna dados históricos de uma métrica específica."""
    if app.state.raw_df is None:
        return {"labels": [], "values": [], "stats": {}}
    
    # Encontra a métrica
    metric = next((m for m in app.state.custom_metrics if m['id'] == metric_id), None)
    if not metric:
        raise HTTPException(status_code=404, detail="Métrica não encontrada.")
        
    df = app.state.raw_df.copy()
    
    # Aplica filtros globais para consistência
    if level and level != "Todos":
        df = df[df['log_level'] == level]
    if source and source != "Todos":
        df = df[df['source'] == source]
    if search:
        df = df[df['message'].str.contains(search, case=False, na=False)]
        
    if df.empty:
        return {"labels": [], "values": [], "stats": {}}

    try:
        # Extrai valores usando regex
        pattern = re.compile(metric['regex'])
        
        def extract_val(msg):
            match = pattern.search(str(msg))
            if match:
                try:
                    return float(match.group(1))
                except (ValueError, IndexError):
                    return None
            return None

        df['metric_value'] = df['message'].apply(extract_val)
        metric_df = df.dropna(subset=['metric_value']).sort_values('timestamp')
        
        if metric_df.empty:
             return {"labels": [], "values": [], "stats": {}}
             
        # Estatísticas
        stats = {
            "mean": round(metric_df['metric_value'].mean(), 2),
            "max": metric_df['metric_value'].max(),
            "min": metric_df['metric_value'].min(),
            "count": len(metric_df)
        }
        
        # Limita pontos para o gráfico não ficar pesado (downsampling simples)
        if len(metric_df) > 500:
            metric_df = metric_df.iloc[::len(metric_df)//500]
            
        return {
            "labels": metric_df['timestamp'].astype(str).tolist(),
            "values": metric_df['metric_value'].tolist(),
            "stats": stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar métrica: {e}")

@app.get("/api/analysis/rum")
def get_rum_metrics():
    """Extrai métricas de RUM (Web Vitals e Erros JS)."""
    if app.state.raw_df is None:
        return {"vitals": [], "errors": [], "error_details": []}
    
    # Usa a função existente no log_analyzer
    rum_df = lam.extract_rum_metrics(app.state.raw_df)
    
    if rum_df.empty:
        return {"vitals": [], "errors": [], "error_details": []}
    
    # Processa Web Vitals (Média por métrica)
    vitals_df = rum_df[rum_df['type'] == 'vital']
    vitals_agg = []
    if not vitals_df.empty:
        # Agrupa por nome e calcula média
        vitals_agg = vitals_df.groupby('name')['value'].mean().reset_index().to_dict(orient='records')

    # Processa Erros JS (Contagem e Detalhes)
    errors_df = rum_df[rum_df['type'] == 'js_error']
    errors_agg = []
    error_details = []
    if not errors_df.empty:
        # Contagem para o gráfico
        errors_agg = errors_df['name'].value_counts().reset_index()
        errors_agg.columns = ['name', 'count']
        errors_agg = errors_agg.to_dict(orient='records')
        
        # Detalhes para a tabela (Top 50 mais recentes)
        # Converte timestamp para string para serialização
        details_df = errors_df[['timestamp', 'name', 'details']].sort_values('timestamp', ascending=False).head(50)
        details_df['timestamp'] = details_df['timestamp'].astype(str)
        error_details = details_df.to_dict(orient='records')

    return {
        "vitals": vitals_agg,
        "errors": errors_agg,
        "error_details": error_details
    }

@app.get("/api/analysis/infrastructure")
async def get_infrastructure_metrics():
    """Busca métricas de infraestrutura diretamente dos nós do Graylog."""
    api_url = os.getenv("GRAYLOG_API_URL")
    user = os.getenv("GRAYLOG_USER")
    password = os.getenv("GRAYLOG_PASSWORD")

    if not all([api_url, user, password]):
        raise HTTPException(status_code=400, detail="Credenciais do Graylog não configuradas no ambiente.")

    all_metrics_data = []

    # 1. MÉTRICAS DAS APLICAÇÕES (Extraídas dos logs via nova lógica desacoplada)
    if app.state.raw_df is not None and not app.state.raw_df.empty:
        try:
            app_infra_df = lam.extract_system_metrics(app.state.raw_df)
            if not app_infra_df.empty:
                # Substitui Infinity e NaN por 0 para evitar o erro JSON "Out of range float"
                app_infra_df = app_infra_df.replace([np.inf, -np.inf], 0).fillna(0)
                
                for _, row in app_infra_df.iterrows():
                    all_metrics_data.append({
                        "timestamp": str(row['timestamp']),
                        "source": f"[App] {row['source']}",
                        "cpu": float(row.get('cpu', 0)),
                        "memory": float(row.get('memory', 0)),
                        "disk": float(row.get('disk', 0)),
                        "lb_status": "ALIVE",
                        "journal_uncommitted": 0
                    })
        except Exception as e:
            print(f"AVISO: Erro ao extrair métricas de infraestrutura dos logs: {e}")

    # 2. MÉTRICAS DO SERVIDOR GRAYLOG (API)
    # Métricas chave para uma visão geral da saúde do sistema
    key_metrics = [
        "jvm.cpu.load",
        "jvm.memory.heap.used",
        "jvm.memory.heap.max",
        "org.graylog2.journal.size",
        "org.graylog2.throughput.input",
        "org.graylog2.throughput.output",
        "org.graylog2.journal.uncommitted-entries"
    ]
    payload = {"metrics": key_metrics}
    url = f"{api_url}/cluster/metrics/multiple"
    auth = (user, password)
    headers = {"X-Requested-By": "LogAnalyticsDashboard"}

    try:
        async with httpx.AsyncClient(auth=auth, headers=headers) as client:
            response = await client.post(url, json=payload, timeout=15.0)
            response.raise_for_status()
            data = response.json()

            # Verificação de robustez: garante que a resposta é um dicionário
            if not isinstance(data, dict):
                print(f"AVISO: Resposta inesperada da API do Graylog. Esperava um dicionário, recebeu {type(data)}.")
                return {"data": []}

            # Processa as métricas do cluster Graylog para a estrutura esperada pelo frontend
            grouped_metrics = {}
            for node_id, node_data in data.items():
                timestamp = datetime.utcnow().isoformat() + "Z"
                if node_id not in grouped_metrics:
                    grouped_metrics[node_id] = {
                        "timestamp": timestamp, "source": f"[Graylog] {node_id[:8]}", 
                        "cpu": 0, "memory": 0, "disk": 0, "journal_uncommitted": 0, "lb_status": "ALIVE"
                    }
                
                for metric in node_data.get("metrics", []):
                    name = metric.get("full_name")
                    val = metric.get("metric", {}).get("value", 0)
                    if name == "jvm.cpu.load":
                        grouped_metrics[node_id]["cpu"] = val * 100
                    elif name == "jvm.memory.heap.used":
                        grouped_metrics[node_id]["_mem_used"] = val
                    elif name == "jvm.memory.heap.max":
                        grouped_metrics[node_id]["_mem_max"] = val
                    elif name == "org.graylog2.journal.uncommitted-entries":
                        grouped_metrics[node_id]["journal_uncommitted"] = val
            
            for node_id, metrics in grouped_metrics.items():
                if "_mem_max" in metrics and metrics["_mem_max"] > 0:
                    metrics["memory"] = (metrics.get("_mem_used", 0) / metrics["_mem_max"]) * 100
                metrics.pop("_mem_used", None)
                metrics.pop("_mem_max", None)
                all_metrics_data.append(metrics)
    except httpx.HTTPStatusError as e:
        error_message = f"Falha ao comunicar com o Graylog (HTTP {e.response.status_code}). Verifique as credenciais, permissões e a URL da API."
        print(f"AVISO: {error_message} Detalhe: {e.response.text}")
        return {"data": [], "error": error_message}
    except httpx.RequestError as e:
        error_message = f"Erro de rede ao tentar acessar o Graylog em {e.request.url}. Verifique a conectividade do container."
        print(f"AVISO: {error_message}")
        return {"data": [], "error": error_message}
    except Exception as e:
        error_message = "Ocorreu um erro inesperado ao processar as métricas de infraestrutura."
        print(f"AVISO: {error_message} Detalhe: {e}")
        return {"data": [], "error": error_message}

    return {"data": all_metrics_data, "error": None}

@app.get("/api/analysis/api-metrics")
def get_api_metrics(
    method: Optional[str] = None,
    status_code: Optional[str] = None,
    search: Optional[str] = None,
    source: Optional[str] = None,
    stream_id: Optional[str] = None
):
    """
    Extrai e filtra métricas de API (Status, Métodos, Endpoints).
    Esta função agora aceita filtros para uso na página de Monitoramento de API.
    """
    if app.state.raw_df is None:
        # Retorna uma estrutura vazia para o frontend não quebrar
        return lam.compute_api_stats(pd.DataFrame())

    # 1. Extrai todas as métricas de API dos logs brutos
    api_df = lam.extract_api_metrics(app.state.raw_df)
    
    # Filtro por Stream (novo)
    if stream_id and stream_id != "Todos":
        if 'streams' in api_df.columns and api_df['streams'].notna().any():
            mask = api_df['streams'].apply(lambda s: isinstance(s, list) and stream_id in s)
            api_df = api_df[mask]

    # 2. Aplica filtros
    if source and source != "Todos":
        api_df = api_df[api_df['source'] == source]
    if method and method != "Todos":
        api_df = api_df[api_df['method'].str.upper() == method.upper()]
    if status_code and status_code != "Todos":
        if status_code.endswith('xx'):
            family = int(status_code[0])
            s_codes = pd.to_numeric(api_df['status_code'], errors='coerce').fillna(0)
            api_df = api_df[(s_codes >= family * 100) & (s_codes < (family + 1) * 100)]
        else:
            api_df = api_df[api_df['status_code'] == status_code]
    if search:
        api_df = api_df[api_df['endpoint'].str.contains(search, case=False, na=False)]

    # 3. Processa os dados (já filtrados) para obter as agregações
    return lam.compute_api_stats(api_df)

@app.get("/api/analysis/cicd")
def get_cicd_metrics():
    """Extrai métricas de CI/CD (Pipelines, Builds, Deploys)."""
    if app.state.raw_df is None:
        return {
            "stats": {"total": 0, "success_rate": 0, "avg_duration": 0},
            "status_counts": [],
            "stage_duration": [],
            "recent_builds": []
        }
    
    cicd_df = lam.extract_cicd_metrics(app.state.raw_df)
    
    if cicd_df.empty:
        return {
            "stats": {"total": 0, "success_rate": 0, "avg_duration": 0},
            "status_counts": [],
            "stage_duration": [],
            "recent_builds": []
        }
    
    # Stats
    total = len(cicd_df)
    success_count = len(cicd_df[cicd_df['status'] == 'Success'])
    success_rate = round((success_count / total * 100), 1) if total > 0 else 0
    
    avg_dur_raw = cicd_df['duration_s'].mean()
    avg_duration = round(avg_dur_raw, 2) if pd.notna(avg_dur_raw) else 0.0
    
    # Charts
    # Garante nomes de colunas consistentes
    status_counts = cicd_df['status'].value_counts().reset_index(name='count')
    status_counts.columns = ['status', 'count']
    
    stage_duration = cicd_df.groupby('stage')['duration_s'].mean().reset_index(name='avg_duration')
    # Tratamento para NaN nas agregações de estágio
    stage_duration['avg_duration'] = stage_duration['avg_duration'].fillna(0).round(2)
    
    # Recent Builds
    recent = cicd_df.sort_values('timestamp', ascending=False).head(20)
    recent['timestamp'] = recent['timestamp'].astype(str)
    
    return {
        "stats": {"total": total, "success_rate": success_rate, "avg_duration": avg_duration},
        "status_counts": status_counts.to_dict(orient='records'),
        "stage_duration": stage_duration.to_dict(orient='records'),
        "recent_builds": recent.to_dict(orient='records')
    }

@app.post("/api/analysis/rca")
async def run_rca_analysis(
    search: Optional[str] = Form(None),
    level: Optional[str] = Form(None),
    source: Optional[str] = Form(None)
):
    """Executa Análise de Causa Raiz (RCA) nos logs filtrados."""
    if app.state.raw_df is None:
        return {"result": "Nenhum dado carregado para análise."}
    
    df = app.state.raw_df.copy()
    
    # Aplica filtros (mesma lógica de get_logs para garantir consistência com o que o usuário vê)
    if level and level != "Todos":
        df = df[df['log_level'] == level]
    if source and source != "Todos":
        df = df[df['source'] == source]
    if search:
        df = df[df['message'].str.contains(search, case=False, na=False)]
        
    if df.empty:
        return {"result": "Não há logs suficientes com os filtros atuais para gerar uma RCA."}

    # Gera prompt e chama LLM
    prompt = lam.generate_rca_prompt(df)
    if not prompt:
        return {"result": "Não foram encontrados padrões de erro suficientes (Logs Críticos ou Warnings) para análise."}
        
    response = lam.send_chat_message([{"role": "user", "content": prompt}])
    return {"result": response}

@app.post("/api/tools/load-test", tags=["Tools"])
async def run_load_test(params: LoadTestRequest):
    """Executa um teste de carga simples em um endpoint."""
    
    # Limites para evitar abuso
    if params.requests > 5000:
        raise HTTPException(status_code=400, detail="O número máximo de requisições é 5000.")
    if params.concurrency > 50:
        raise HTTPException(status_code=400, detail="A concorrência máxima é 50.")

    async def single_request(client: httpx.AsyncClient):
        start_time = datetime.now()
        try:
            # Adiciona o header X-Requested-By para compatibilidade com a própria API
            req_headers = params.headers or {}
            if "X-Requested-By" not in req_headers:
                req_headers["X-Requested-By"] = "LogAnalyticsLoadTester"

            response = await client.request(
                method=params.method,
                url=params.url,
                headers=req_headers,
                json=params.body,
                timeout=20.0
            )
            latency = (datetime.now() - start_time).total_seconds() * 1000
            return {"status_code": response.status_code, "latency_ms": latency, "error": None}
        except Exception as e:
            latency = (datetime.now() - start_time).total_seconds() * 1000
            return {"status_code": 0, "latency_ms": latency, "error": str(e)}

    semaphore = asyncio.Semaphore(params.concurrency)
    
    async def concurrent_request(client):
        async with semaphore:
            return await single_request(client)

    total_start_time = datetime.now()
    
    async with httpx.AsyncClient() as client:
        tasks = [concurrent_request(client) for _ in range(params.requests)]
        results = await asyncio.gather(*tasks)
        
    total_duration_s = (datetime.now() - total_start_time).total_seconds()

    # Processar resultados
    latencies = [r['latency_ms'] for r in results]
    status_codes = [r['status_code'] for r in results]
    
    success_count = sum(1 for s in status_codes if 200 <= s < 400)
    
    status_dist = {}
    for s in status_codes:
        status_dist[s] = status_dist.get(s, 0) + 1

    return {
        "total_requests": params.requests,
        "concurrency": params.concurrency,
        "total_duration_seconds": round(total_duration_s, 2),
        "requests_per_second": round(params.requests / total_duration_s if total_duration_s > 0 else 0, 2),
        "average_latency_ms": round(sum(latencies) / len(latencies) if latencies else 0, 2),
        "min_latency_ms": round(min(latencies) if latencies else 0, 2),
        "max_latency_ms": round(max(latencies) if latencies else 0, 2),
        "success_count": success_count,
        "error_count": params.requests - success_count,
        "status_code_distribution": status_dist
    }

@app.post("/api/tools/advanced-load-test", tags=["Tools"])
async def run_advanced_load_test(params: AdvancedLoadTestRequest):
    """Executa um teste de carga avançado, baseado em duração e com estatísticas detalhadas."""
    
    # Limites para evitar abuso
    if params.duration_seconds > 300: # 5 minutos
        raise HTTPException(status_code=400, detail="A duração máxima do teste é de 300 segundos.")
    if params.concurrency > 100:
        raise HTTPException(status_code=400, detail="A concorrência máxima é 100.")
    if params.ramp_up_seconds > params.duration_seconds:
        raise HTTPException(status_code=400, detail="O tempo de ramp-up não pode ser maior que a duração total do teste.")

    results_queue = asyncio.Queue()
    stop_event = asyncio.Event()
    worker_tasks = []

    async def worker(client: httpx.AsyncClient):
        req_headers = params.headers or {}
        if "X-Requested-By" not in req_headers:
            req_headers["X-Requested-By"] = "LogAnalyticsLoadTester"
            
        while not stop_event.is_set():
            start_time = time.monotonic()
            try:
                response = await client.request(
                    method=params.method,
                    url=params.url,
                    headers=req_headers,
                    json=params.body,
                    timeout=20.0
                )
                latency = (time.monotonic() - start_time) * 1000
                await results_queue.put({"status_code": response.status_code, "latency_ms": latency, "error": None})
            except Exception as e:
                latency = (time.monotonic() - start_time) * 1000
                await results_queue.put({"status_code": 0, "latency_ms": latency, "error": str(e)})

    async def spawner(client: httpx.AsyncClient):
        """Inicia workers gradualmente se houver ramp-up."""
        if params.ramp_up_seconds > 0 and params.concurrency > 1:
            delay = params.ramp_up_seconds / params.concurrency
            for _ in range(params.concurrency):
                if stop_event.is_set():
                    break
                worker_tasks.append(asyncio.create_task(worker(client)))
                await asyncio.sleep(delay)
        else:
            for _ in range(params.concurrency):
                worker_tasks.append(asyncio.create_task(worker(client)))

    # Inicia os workers
    async with httpx.AsyncClient() as client:
        # Inicia o spawner que vai criar os workers
        spawner_task = asyncio.create_task(spawner(client))

        # Roda pelo tempo definido a partir do início do teste
        await asyncio.sleep(params.duration_seconds)

        # Para os workers
        stop_event.set()
        
        # Garante que o spawner terminou (caso duration < ramp_up) e espera os workers
        await spawner_task
        if worker_tasks:
            await asyncio.wait(worker_tasks, timeout=5.0)

    # Coleta e processa os resultados
    results = []
    while not results_queue.empty():
        results.append(results_queue.get_nowait())
        
    if not results:
        return {"total_requests": 0, "message": "Nenhuma requisição foi completada no tempo definido."}

    latencies = [r['latency_ms'] for r in results]
    status_codes = [r['status_code'] for r in results]
    
    success_count = sum(1 for s in status_codes if 200 <= s < 400)
    
    status_dist = {str(s): status_codes.count(s) for s in set(status_codes)}

    return {
        "total_requests": len(results),
        "concurrency": params.concurrency,
        "total_duration_seconds": params.duration_seconds,
        "requests_per_second": round(len(results) / params.duration_seconds if params.duration_seconds > 0 else 0, 2),
        "average_latency_ms": round(np.mean(latencies), 2) if latencies else 0,
        "p50_latency_ms": round(np.percentile(latencies, 50), 2) if latencies else 0,
        "p95_latency_ms": round(np.percentile(latencies, 95), 2) if latencies else 0,
        "p99_latency_ms": round(np.percentile(latencies, 99), 2) if latencies else 0,
        "success_count": success_count,
        "error_count": len(results) - success_count,
        "status_code_distribution": status_dist
    }

# --- Estado Global para o Webhook Catcher ---
if not hasattr(app.state, 'webhook_logs'):
    app.state.webhook_logs = []

@app.api_route("/api/tools/webhook-catcher/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"], tags=["Tools"])
async def webhook_catcher(request: Request, path: str):
    """Endpoint curinga que captura qualquer requisição enviada para ele (Estilo Request Catcher)."""
    body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            body = await request.json()
        except Exception:
            try:
                body = (await request.body()).decode("utf-8")
            except Exception:
                body = "<binary data>"
    
    log_entry = {
        "id": int(time.time() * 1000),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "method": request.method,
        "path": f"/{path}",
        "query_params": dict(request.query_params),
        "headers": dict(request.headers),
        "body": body,
        "client": request.client.host if request.client else "unknown"
    }
    
    # Adiciona no topo da lista, mantendo o limite dos últimos 50 disparos
    app.state.webhook_logs.insert(0, log_entry)
    app.state.webhook_logs = app.state.webhook_logs[:50]
    
    return {"status": "received", "message": "Webhook captured successfully."}

@app.get("/api/tools/webhook-catcher-logs", tags=["Tools"])
def get_webhook_logs():
    """Retorna as requisições capturadas pelo webhook catcher."""
    return {"logs": getattr(app.state, 'webhook_logs', [])}

@app.delete("/api/tools/webhook-catcher-logs", tags=["Tools"])
def clear_webhook_logs():
    """Limpa o histórico do webhook catcher."""
    app.state.webhook_logs = []
    return {"status": "cleared"}

@app.post("/api/integrations/jira/create")
async def create_jira_ticket(
    summary: str = Form(...),
    description: str = Form(...),
    email: str = Form(...),
    webhook_url: Optional[str] = Form(None),
    api_token: Optional[str] = Form(None)
):
    """Cria um ticket no Jira via Webhook."""
    # Tenta pegar do env se não vier no form (prioridade para o form se o usuário sobrescrever)
    final_webhook = webhook_url or os.getenv("JIRA_WEBHOOK_URL")
    final_token = api_token or os.getenv("JIRA_API_KEY")
    
    if not final_webhook:
         raise HTTPException(status_code=400, detail="URL do Webhook do Jira não configurada.")

    headers = {}
    if final_token:
        headers["X-Automation-Webhook-Token"] = final_token

    # Limpa a descrição para remover prefixos de teste como (teste) e caracteres especiais como #.
    cleaned_description = description.replace('#', '')

    payload = {
        "data": {
            "summary": summary,
            "description": cleaned_description,
            "attachment":[],
            "surveyLink": "Lockton Log Analytics: " + "http://10.130.0.20:8051/",
            "email": "Ticket criado por: " + email,
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(final_webhook, json=payload, headers=headers, timeout=20.0)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Erro no Jira ({e.response.status_code}): {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao comunicar com o Jira: {str(e)}")
        
    return {"message": "Ticket criado com sucesso!"}

@app.post("/api/tools/parse-log", tags=["Tools"])
async def parse_raw_log(request: ParseRequest):
    """Testa o parsing de uma mensagem de log raw no Graylog."""
    url, user, password = get_graylog_credentials()
    
    data, err = lam.test_log_parsing(url, user, password, request.raw_message)
    
    if err:
        raise HTTPException(status_code=500, detail=err)
    
    return data

@app.post("/api/alerts/definitions/{alert_id}/execute", summary="Testa um alerta manualmente", tags=["Graylog Monitoring"])
async def execute_alert_test(alert_id: str):
    url, user, password = get_graylog_credentials()
    data, err = lam.execute_graylog_alert_test(url, user, password, alert_id)
    if err:
        raise HTTPException(status_code=500, detail=err)
    return data