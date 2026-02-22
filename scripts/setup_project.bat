@echo off
cd /d "%~dp0.."

echo ==========================================
echo    CONFIGURACAO INICIAL DO PROJETO
echo ==========================================
echo.

REM 1. Verifica se o Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado. Instale o Python e adicione ao PATH.
    pause
    exit /b
)

REM 2. Cria o ambiente virtual (.venv) se nao existir
if not exist .venv (
    echo [1/3] Criando ambiente virtual .venv...
    python -m venv .venv
) else (
    echo [1/3] Ambiente virtual ja existe.
)

REM 3. Instala as dependencias
echo [2/3] Instalando bibliotecas do requirements.txt...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

echo.
echo [3/3] Criando arquivo .env de exemplo (se necessario)...
if not exist .env (
    echo GROQ_API_KEY=> .env
    echo GRAYLOG_API_URL=>> .env
    echo TEAMS_WEBHOOK_URL=>> .env
    echo DASHBOARD_URL=http://localhost:8051>> .env
    echo Arquivo .env criado. Configure suas chaves nele!
)

echo.
echo ==========================================
echo    TUDO PRONTO!
echo ==========================================
echo Para iniciar o sistema:
echo   - No CMD: scripts\run_app.bat
echo   - No PowerShell: .\scripts\run_app.bat
pause