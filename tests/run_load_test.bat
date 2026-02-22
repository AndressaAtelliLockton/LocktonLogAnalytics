@echo off
cd /d "%~dp0.."
echo ==========================================
echo    INICIANDO TESTE DE CARGA (LOCUST)
echo ==========================================
echo.
echo Acesse http://localhost:8089 no seu navegador para iniciar o teste.
echo Target Host sugerido:
echo   - Docker Local / Staging: http://localhost:8051
echo   - Dev Local (run_app.bat): http://localhost:8000
echo.
.venv\Scripts\python.exe -m locust -f tests\locustfile.py