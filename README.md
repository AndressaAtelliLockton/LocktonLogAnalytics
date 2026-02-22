# 📊 Lockton Log Analytics (SRE Platform)

![Version](https://img.shields.io/badge/version-2.0-blue) ![Python](https://img.shields.io/badge/python-3.10-green) ![Docker](https://img.shields.io/badge/docker-ready-blue) ![License](https://img.shields.io/badge/license-Proprietary-red)

**Lockton Log Analytics** is a comprehensive observability platform designed to centralize logs, metrics, and traces. It leverages Artificial Intelligence (Llama 3 via Groq) to automate root cause analysis (RCA) and provide actionable insights for SRE and DevOps teams.

This system bridges the gap between raw logs and business intelligence, offering features comparable to enterprise solutions like Datadog and Grafana, but tailored for Lockton's specific needs.

---

##  Key Features

### 1. 🧠 **AI-Powered Intelligence**
- **Automated RCA:** The system correlates errors and generates a Root Cause Analysis hypothesis automatically.
- **Error Diagnosis:** Instant AI explanation for critical logs and exceptions.
- **Anomaly Detection:** Statistical algorithms (Z-Score) to detect volume spikes and rare log patterns.

### 2. 🖥️ **Infrastructure Monitoring**
- **Host Metrics:** CPU, Memory, Disk, and Network usage extraction from logs.
- **Container Insights:** Monitoring of Docker/Kubernetes containers (volume, errors per container).
- **Health Checks:** Real-time status of internal components (Graylog, InfluxDB).

### 3. 🌐 **RUM (Real User Monitoring)**
- **Core Web Vitals:** Extraction of LCP, FID, and CLS metrics directly from frontend logs.
- **JavaScript Errors:** Aggregation and analysis of client-side exceptions.

### 4. 🚀 **CI/CD & Pipelines**
- **Pipeline Visibility:** Monitor build durations, success rates, and failure stages.
- **Regression Testing:** Compare current logs against a baseline to detect new errors after deployments.

### 5. 📡 **API & APM**
- **Latency Analysis:** Distribution histograms, P95/P99 percentiles, and bottleneck detection.
- **Traffic Analysis:** Breakdown by HTTP methods, Status Codes (2xx, 4xx, 5xx), and Top Endpoints.
- **Distributed Tracing:** Correlation of logs via Trace IDs (UUID/W3C).

### 6. 🛡️ **Security (SIEM)**
- **Threat Detection:** Identification of suspicious IPs based on error rates.
- **Data Masking:** Automatic obfuscation of sensitive data (CPF, Email, IP) for LGPD compliance.

### 7. 📈 **Custom Metrics & Forecasting**
- **Regex Metrics:** Create custom counters and gauges from log patterns without coding.
- **Volume Forecasting:** Predict log volume trends for the next hour using Holt-Winters/Linear Regression.

### 8. 🔔 **Alerting & Reporting**
- **Smart Alerts:** Simulations for latency and error thresholds.
- **Integrations:** Webhook integration with Microsoft Teams.
- **PDF Reports:** One-click generation of executive reports with charts and AI insights.

---

## ️ Architecture

The system is built on a modern, containerized stack:

- **Frontend:** Streamlit (Python) for interactive dashboards.
- **Backend:** FastAPI (Python) for high-performance API and WebSocket handling.
- **Proxy:** Nginx for robust routing and WebSocket management.
- **AI Engine:** Groq API (Llama 3) for cognitive tasks.
- **Data Sources:** Graylog (API), InfluxDB (Time-series), and CSV Uploads.

---

## ️ Installation & Setup

### Option A: Docker (Recommended)
Ensure Docker Desktop is running.

1. **Build & Run:**
   ```bash
   ./tests/run_docker_test.bat
   ```
2. **Access:**
   Open http://10.130.0.20:8051

### Option B: Local Development
Requires Python 3.10+.

1. **Setup Environment:**
   ```bash
   ./scripts/setup_project.bat
   ```
2. **Configure Secrets:**
   Edit the `.env` file with your API keys (Groq, Graylog, Teams).
3. **Run Application:**
   ```bash
   ./scripts/run_app.bat
   ```
4. **Access:**
   Open http://localhost:8000

---

## 📂 Project Structure

- `src/`: Application source code (`app.py`, `dashboard.py`, `scheduler.py`, `log_analyzer.py`, `pages/`).
- `scripts/`: Operational scripts (`setup_project.bat`, `run_app.bat`).
- `tests/`: Test suites and execution scripts (`run_tests.bat`, `run_docker_test.bat`).
- `config/`: Configuration files (`nginx.conf`, `config.json`).
- `logs/`: Application logs.
- `data/`: Local database and data files.

---

⭐⭐⭐ **Developed for Lockton Brasil** ⭐⭐⭐