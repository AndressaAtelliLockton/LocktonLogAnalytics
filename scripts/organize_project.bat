@echo off
echo ==========================================
echo    ORGANIZANDO ESTRUTURA DO PROJETO
echo ==========================================
echo.

REM 1. Cria as pastas
if not exist src mkdir src
if not exist scripts mkdir scripts
if not exist tests mkdir tests
if not exist config mkdir config

REM 2. Move Codigo Fonte para src/
echo [1/4] Movendo codigo fonte para src/...
move app.py src\ >nul 2>&1
move dashboard.py src\ >nul 2>&1
move scheduler.py src\ >nul 2>&1
move log_collector.py src\ >nul 2>&1
move log_analyzer_module.py src\ >nul 2>&1
move iac_agent.py src\ >nul 2>&1
move lockton_logo.png src\ >nul 2>&1

REM Move pastas inteiras (requer robocopy ou move simples se nao existirem no destino)
if exist pages move pages src\ >nul 2>&1
if exist dashboard move dashboard src\ >nul 2>&1
if exist log_analyzer move log_analyzer src\ >nul 2>&1

REM 3. Move Scripts para scripts/
echo [2/4] Movendo scripts para scripts/...
move *.bat scripts\ >nul 2>&1
move *.sh scripts\ >nul 2>&1
REM O proprio script de organizacao deve ficar na raiz por enquanto ou se mover no final

REM 4. Move Testes para tests/
echo [3/4] Movendo testes para tests/...
move test_*.py tests\ >nul 2>&1
move run_tests.py tests\ >nul 2>&1
move locustfile.py tests\ >nul 2>&1
move check_port_accessibility.py tests\ >nul 2>&1

REM 5. Move Config para config/
echo [4/4] Movendo configuracoes para config/...
move nginx.conf config\ >nul 2>&1

REM Devolve este script para a raiz caso tenha sido movido pelo *.bat
if exist scripts\organize_project.bat move scripts\organize_project.bat . >nul 2>&1

echo.
echo ==========================================
echo    ORGANIZACAO CONCLUIDA!
echo ==========================================
echo.
echo A nova estrutura e:
echo   /src      -> Codigo da aplicacao (Python)
echo   /scripts  -> Scripts de execucao (.bat, .sh)
echo   /tests    -> Testes unitarios e de carga
echo   /config   -> Arquivos de configuracao (Nginx)
pause