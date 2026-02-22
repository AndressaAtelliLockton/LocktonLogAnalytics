@echo off
cd /d "%~dp0.."

echo ==========================================
echo    INICIANDO AGENTE DE IA (IAC SUPPORT)
echo ==========================================
echo.

REM Verifica ambiente virtual
if not exist .venv (
    echo [ERRO] Ambiente virtual nao encontrado.
    echo Por favor, execute setup_project.bat primeiro.
    pause
    exit /b
)

REM Permite que o usuário digite o problema ou use o padrão
echo Descreva o problema de infraestrutura (Deixe em branco para usar o exemplo padrao):
echo Exemplo padrao: "Ao rodar a pipeline no servidor ele dá acesso negado, mas a porta externa está aberta"
echo.
set /p ISSUE="> "

if "%ISSUE%"=="" set ISSUE=Ao rodar a pipeline no servidor ele dá acesso negado, mas a porta externa está aberta

echo.
echo Executando analise...
.venv\Scripts\python.exe src\iac_agent.py "%ISSUE%"

pause