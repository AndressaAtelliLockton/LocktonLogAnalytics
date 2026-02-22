@echo off
cd /d "%~dp0.."

echo ==========================================
echo    TESTE LOCAL COM DOCKER (8051 -^> 80)
echo ==========================================
echo.

REM Verifica se o Docker esta rodando
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] O Docker Desktop nao esta rodando!
    echo Por favor, abra o aplicativo "Docker Desktop" e aguarde ele iniciar.
    pause
    exit /b
)

echo 1. Construindo a imagem (simulando pipeline)...
docker build -f Dockerfile -t lockton-staging .
if %errorlevel% neq 0 (
    echo [ERRO] Falha no build. Verifique o Dockerfile.
    pause
    exit /b
)

echo.
echo 2. Rodando container...
echo    Acesse no navegador: http://10.130.0.20:8051
echo    (Para parar: Ctrl+C)
echo.
docker run --rm -p 8051:80 -e EXTERNAL_PORT=8051 --env-file .env --name lockton-local-test lockton-staging