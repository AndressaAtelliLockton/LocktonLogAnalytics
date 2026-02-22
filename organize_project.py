import os
import shutil
import glob

def organize():
    print("--- Organizando Projeto (Python) ---")
    
    # 1. Cria pastas de destino
    folders = ["src", "scripts", "tests", "config", "logs", "data"]
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"📁 Pasta verificada: {folder}")

    # 2. Arquivos para src/
    to_src = [
        "app.py", "dashboard.py", "scheduler.py", "log_collector.py", 
        "iac_agent.py", "lockton_logo.png", "check_env.py",
        "log_analytics.py", "log_analitics.py"
    ]
    # Pastas para src/
    dirs_to_src = ["pages", "log_analyzer", "log_analytics", "log_analyzer.py"]

    # 3. Identifica scripts de teste (que devem ir para tests/)
    test_bats = ["run_tests.bat", "run_load_test.bat", "run_docker_test.bat"]

    # 4. Arquivos para scripts/ (Exclui testes e o próprio organizador)
    all_bats = glob.glob("*.bat")
    to_scripts = [f for f in all_bats if f not in test_bats and "organize_project" not in f] + glob.glob("*.sh") + ["list_models.py"]

    # 5. Arquivos para tests/
    to_tests = glob.glob("test_*.py") + ["run_tests.py", "locustfile.py", "check_port_accessibility.py", "__init__.py", "manual_alerts"]
    # Adiciona os bats de teste que estão na raiz
    to_tests += [f for f in test_bats if os.path.exists(f)]

    # 6. Arquivos para config/
    to_config = ["nginx.conf", "config.json", "secrets.toml"]

    # 7. Arquivos para logs/
    to_logs = glob.glob("*.log")

    # 8. Arquivos para data/
    to_data = glob.glob("*.db") + glob.glob("*.csv") + glob.glob("*.pid")
    # Move .txt mas mantem requirements.txt na raiz
    txt_files = glob.glob("*.txt")
    to_data += [f for f in txt_files if "requirements.txt" not in f]
    # Move .json mas mantem config.json (ja tratado) e outros configs se houver
    json_files = glob.glob("*.json")
    to_data += [f for f in json_files if f not in to_config]

    # Limpeza de arquivos gerados acidentalmente por scripts .bat
    garbage_files = ["80)"]
    for g in garbage_files:
        if os.path.exists(g):
            try: os.remove(g); print(f"🗑️ Removido arquivo acidental: {g}")
            except: pass

    # Função auxiliar de movimento
    def move_items(items, dest):
        for item in items:
            if os.path.exists(item):
                dest_path = os.path.join(dest, os.path.basename(item))
                try:
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                        print(f"♻️ Substituindo: {dest_path}")
                    shutil.move(item, os.path.join(dest, os.path.basename(item)))
                    print(f"✅ Movido: {item} -> {dest}/")
                except Exception as e:
                    print(f"⚠️ Erro ao mover {item}: {e}")

    print("\nMovendo arquivos da raiz...")
    move_items(to_src, "src")
    move_items(to_tests, "tests")
    move_items(to_config, "config")
    move_items(to_scripts, "scripts")
    move_items(to_logs, "logs")
    move_items(to_data, "data")

    # Renomeia e move log_analyzer_module.py para log_analyzer.py (Correção de Import)
    if os.path.exists("log_analyzer_module.py"):
        try:
            dest_path = os.path.join("src", "log_analyzer.py")
            if os.path.exists(dest_path):
                os.remove(dest_path)
                print(f"♻️ Substituindo: {dest_path}")
            shutil.move("log_analyzer_module.py", dest_path)
            print(f"✅ Renomeado e Movido: log_analyzer_module.py -> src/log_analyzer.py")
        except Exception as e:
            print(f"⚠️ Erro ao mover log_analyzer_module.py: {e}")
    
    # Move diretórios para src
    for d in dirs_to_src:
        if os.path.exists(d):
            try:
                shutil.move(d, os.path.join("src", os.path.basename(d)))
                print(f"✅ Pasta movida: {d} -> src/")
            except Exception as e:
                print(f"⚠️ Erro ao mover pasta {d}: {e}")

    # Renomeia e move a pasta dashboard para utils (Evita conflito com dashboard.py)
    if os.path.exists("dashboard"):
        try:
            dest = os.path.join("src", "utils")
            if os.path.exists(dest): shutil.rmtree(dest)
            shutil.move("dashboard", dest)
            print(f"✅ Pasta movida e renomeada: dashboard -> src/utils/")
        except Exception as e:
            print(f"⚠️ Erro ao mover dashboard: {e}")
    elif os.path.exists(os.path.join("src", "dashboard")):
        try:
            os.rename(os.path.join("src", "dashboard"), os.path.join("src", "utils"))
            print(f"✅ Pasta renomeada: src/dashboard -> src/utils/")
        except Exception as e:
            print(f"⚠️ Erro ao renomear src/dashboard: {e}")

    # --- RESOLUÇÃO DE CONFLITOS (CRÍTICO) ---
    
    # 1. Conflito: Pasta 'log_analyzer' vs Arquivo 'log_analyzer.py'
    log_analyzer_dir = os.path.join("src", "log_analyzer")
    log_analyzer_file = os.path.join("src", "log_analyzer.py")
    
    if os.path.exists(log_analyzer_dir) and os.path.exists(log_analyzer_file):
        print("⚠️ Detectado conflito entre pasta e arquivo 'log_analyzer'.")
        try:
            # Renomeia a pasta para evitar conflito de importação
            new_dir_name = os.path.join("src", "log_analyzer_lib")
            if os.path.exists(new_dir_name): shutil.rmtree(new_dir_name)
            shutil.move(log_analyzer_dir, new_dir_name)
            print(f"✅ Pasta 'log_analyzer' renomeada para 'log_analyzer_lib' para priorizar o módulo.")
        except Exception as e:
            print(f"⚠️ Erro ao resolver conflito log_analyzer: {e}")

    # 2. Garante que utils seja um pacote Python
    utils_init = os.path.join("src", "utils", "__init__.py")
    if os.path.exists(os.path.join("src", "utils")) and not os.path.exists(utils_init):
        with open(utils_init, 'w') as f:
            pass
        print("✅ Criado src/utils/__init__.py")

    # --- MOVER PÁGINAS SOLTAS (RUM, Infra, etc.) ---
    stray_pages = [
        "1_Executive.py", "2_Investigation.py", "3_Intelligence.py", 
        "4_Custom_Metrics.py", "5_RUM.py", "6_Infrastructure.py", 
        "7_API_Monitoring.py", "8_Tools.py", "9_CICD.py"
    ]
    
    pages_dir = os.path.join("src", "pages")
    if not os.path.exists(pages_dir):
        os.makedirs(pages_dir)

    # Cria __init__.py em src/pages se não existir
    pages_init = os.path.join(pages_dir, "__init__.py")
    if not os.path.exists(pages_init):
        with open(pages_init, 'w') as f: pass
        print("✅ Criado src/pages/__init__.py")

    print("\nVerificando páginas soltas na raiz...")
    for page in stray_pages:
        if os.path.exists(page):
            dest_path = os.path.join(pages_dir, page)
            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
                    print(f"♻️ Substituindo versão antiga em src/pages: {page}")
                shutil.move(page, dest_path)
                print(f"✅ Página movida: {page} -> src/pages/")
            except Exception as e:
                print(f"⚠️ Erro ao mover {page}: {e}")

    # --- MOVER CLI ANTIGO (Se existir) ---
    if os.path.exists("log_analyzer.py"):
        # Verifica se é o script CLI (tem argparse) para não mover a lib errada
        try:
            with open("log_analyzer.py", 'r', encoding='utf-8') as f:
                if "argparse" in f.read():
                    dest = os.path.join("scripts", "analyze_logs.py")
                    shutil.move("log_analyzer.py", dest)
                    print(f"✅ CLI movido: log_analyzer.py -> scripts/analyze_logs.py")
        except: pass

    # --- Correção: Move scripts de teste que podem estar em scripts/ para tests/ ---
    print("\nVerificando scripts de teste em locais incorretos...")
    for script in test_bats:
        wrong_path = os.path.join("scripts", script)
        if os.path.exists(wrong_path):
            try:
                shutil.move(wrong_path, os.path.join("tests", script))
                print(f"✅ Corrigido: scripts/{script} -> tests/")
            except Exception as e:
                print(f"⚠️ Erro ao mover {wrong_path}: {e}")

    print("\nOrganização concluída com sucesso!")

if __name__ == "__main__":
    organize()