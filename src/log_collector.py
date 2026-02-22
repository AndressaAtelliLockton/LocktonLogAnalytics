import os
import re
import time
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(): pass
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# --- Configuration ---
load_dotenv()

# AJUSTE: No Docker Swarm, usamos o nome do serviço definido na pipeline
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb-staging:8086")
INFLUXDB_TOKEN = os.getenv("DOCKER_INFLUXDB_INIT_ADMIN_TOKEN")
INFLUXDB_ORG = os.getenv("DOCKER_INFLUXDB_INIT_ORG")
INFLUXDB_BUCKET = os.getenv("DOCKER_INFLUXDB_INIT_BUCKET")

LOG_FILE_PATH = "app.log"

LOG_REGEX = re.compile(
    r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - '
    r'(?P<level>\w+) - '
    r'\[(?P<source>[\w-]+)\] - '
    r'(?:\[trace:(?P<trace_id>[\w-]+)\] - )?'
    r'(?P<message>.*?)'
    r'(?: - duration=(?P<duration>\d+)ms)?'
)

# --- Log Parser ---
def parse_log_line(line):
    match = LOG_REGEX.match(line.strip())
    if match:
        data = match.groupdict()
        # Ajuste para garantir timezone UTC
        data['timestamp'] = datetime.strptime(data['timestamp'], '%Y-%m-%d %H:%M:%S,%f').replace(tzinfo=timezone.utc)
        if data['duration']:
            data['duration'] = int(data['duration'])
        return data
    else:
        return {
            'timestamp': datetime.now(timezone.utc),
            'level': 'unknown',
            'source': 'unknown',
            'trace_id': None,
            'message': line.strip(),
            'duration': None
        }

# --- Main Application ---
def main():
    global INFLUXDB_URL
    print(f"Starting log collector connecting to {INFLUXDB_URL}...")

    if not os.path.exists(LOG_FILE_PATH):
        with open(LOG_FILE_PATH, 'w') as f:
            f.write(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S,000")} - INFO - [log-collector] - Log file created.\n')

    with open(LOG_FILE_PATH, 'r') as file:
        file.seek(0, 2)
        
        client = None
        write_api = None

        while True:
            # Lógica de Conexão / Reconexão Persistente
            if client is None:
                try:
                    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
                    if client.ready():
                        print("✅ Connected to InfluxDB successfully!")
                        write_api = client.write_api(write_options=SYNCHRONOUS)
                    else:
                        print("❌ InfluxDB not ready. Retrying in 5s...")
                        client = None
                        time.sleep(5)
                        continue
                except Exception as e:
                    str_e = str(e)

                    # 1. Auto-fallback para localhost se estiver rodando fora do Docker (Erro de DNS)
                    if "influxdb-staging" in INFLUXDB_URL and ("getaddrinfo failed" in str_e or "Name or service not known" in str_e or "Errno -2" in str_e):
                        print("⚠️ Host 'influxdb-staging' não encontrado. Tentando 'localhost:8086' para desenvolvimento local...")
                        INFLUXDB_URL = "http://localhost:8086"
                        client = None
                        time.sleep(1)
                        continue

                    # Se falhar no localhost (desenvolvimento sem InfluxDB), avisa e aguarda mais tempo
                    # Verifica isso ANTES de imprimir o erro genérico para evitar spam
                    if ("localhost" in INFLUXDB_URL or "127.0.0.1" in INFLUXDB_URL) and ("10061" in str_e or "Connection refused" in str_e):
                        print(f"⚠️ InfluxDB local ({INFLUXDB_URL}) não encontrado. O coletor ficará em modo de espera (tentando a cada 60s).")
                        time.sleep(60)
                        continue

                    print(f"❌ Connection error: {e}. Retrying in 5s...")

                    client = None
                    time.sleep(5)
                    continue

            line = file.readline()
            if not line:
                time.sleep(0.5) # Aumentado um pouco para poupar CPU
                continue
            
            parsed_data = parse_log_line(line)

            point = Point("log_entry") \
                .time(parsed_data['timestamp']) \
                .tag("level", parsed_data['level']) \
                .tag("source", parsed_data.get('source', 'unknown')) \
                .field("message", parsed_data['message'])
            
            if parsed_data.get('trace_id'):
                point = point.tag("trace_id", parsed_data['trace_id']) # Tag é melhor que Field para busca
            if parsed_data.get('duration'):
                point = point.field("duration", parsed_data['duration'])

            try:
                write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
            except Exception as e:
                print(f"⚠️ Error writing to InfluxDB: {e}")
                # Verifica se a conexão caiu
                try:
                    if not client.ready():
                        raise Exception("Connection lost")
                except:
                    print("🔄 Connection lost. Reconnecting...")
                    client.close()
                    client = None
                    write_api = None

if __name__ == "__main__":
    main()