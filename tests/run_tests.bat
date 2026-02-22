@echo off
cd /d "%~dp0.."
echo ==========================================
echo    EXECUTANDO SUITE DE TESTES AUTOMATIZADOS
echo ==========================================
echo.

echo 0. Verificando Disponibilidade do Ambiente (Porta 8051)...
.venv\Scripts\python.exe tests\check_port_accessibility.py
if %ERRORLEVEL% NEQ 0 goto fail

echo.
echo 1. Testes de Unidade (Integrations)...
.venv\Scripts\python.exe -m unittest tests/test_integrations.py
if %ERRORLEVEL% NEQ 0 goto fail

echo.
echo 2. Testes de Relatorios (PDF)...
.venv\Scripts\python.exe -m unittest tests/test_reporting.py
if %ERRORLEVEL% NEQ 0 goto fail

echo.
echo 3. Testes de Performance...
.venv\Scripts\python.exe -m unittest tests/test_performance.py
if %ERRORLEVEL% NEQ 0 goto fail

echo.
echo 4. Testes de Alerta (Teams)...
.venv\Scripts\python.exe -m unittest tests/test_alerting.py
if %ERRORLEVEL% NEQ 0 goto fail

echo.
echo 5. Simulacao Real do Watchdog (Envio Teams)...
.venv\Scripts\python.exe src\scheduler.py --simulate-watchdog
if %ERRORLEVEL% NEQ 0 goto fail

echo.
echo 6. Teste de Conectividade (Streamlit Staging)...
.venv\Scripts\python.exe -m unittest tests/test_streamlit_health.py
if %ERRORLEVEL% NEQ 0 goto fail

echo.
echo 7. Teste de Acesso Externo (URL Final)...
.venv\Scripts\python.exe -m unittest tests/test_external_access.py
if %ERRORLEVEL% NEQ 0 goto fail

echo.
echo ==========================================
echo    [SUCESSO] TODOS OS TESTES PASSARAM!
echo ==========================================
goto end

:fail
echo.
echo ==========================================
echo    [FALHA] ERROS ENCONTRADOS NOS TESTES
echo ==========================================

:end
pause
