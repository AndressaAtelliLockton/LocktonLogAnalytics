@echo off
cd /d "%~dp0.."

echo ==========================================
echo    INICIANDO SERVIDOR FASTAPI (WEBSOCKET)
echo ==========================================

if not exist .venv (
    echo [AVISO] Ambiente virtual nao encontrado. Executando configuracao inicial...
    call setup_project.bat
    if not exist .venv (
        echo [ERRO] Falha na configuracao. Verifique os erros acima.
        pause
        exit /b
    )
)

cd src
..\.venv\Scripts\python.exe -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
if %errorlevel% neq 0 pause