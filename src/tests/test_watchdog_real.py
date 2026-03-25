"""
Teste de integração do AI Watchdog com dados REAIS do Graylog.

Uso:
  # Descobre quais fontes existem no Graylog (passo recomendado antes do teste)
  python tests/test_watchdog_real.py --list-sources

  # Executa o fluxo completo com uma fonte específica (envia alerta real ao Teams)
  python tests/test_watchdog_real.py --source "nome-da-fonte"

  # Executa com múltiplas fontes (separadas por vírgula)
  python tests/test_watchdog_real.py --source "fonte-a,fonte-b"

  # Executa sem enviar ao Teams (apenas valida a busca e a IA)
  python tests/test_watchdog_real.py --source "nome-da-fonte" --dry-run

  # Aumenta a janela de busca para 24 horas (garante encontrar erros reais)
  python tests/test_watchdog_real.py --source "Locksp-swarm4" --range 86400

Requer no .env:
  GRAYLOG_API_URL, GRAYLOG_USER, GRAYLOG_PASSWORD
  GROQ_API_KEY         (opcional — pula análise de IA se ausente)
  TEAMS_WEBHOOK_URL    (opcional — pula envio ao Teams se --dry-run ou ausente)
"""
import os
import sys
import argparse
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env')))
except ImportError:
    pass

import pandas as pd
from src.log_analyzer_lib import integrations as integrations_lib
from src import log_analyzer as lam

# ─────────────────────────────────────────────
# Configuração via .env
# ─────────────────────────────────────────────
GRAYLOG_URL  = os.getenv("GRAYLOG_API_URL")
GRAYLOG_USER = os.getenv("GRAYLOG_USER")
GRAYLOG_PASS = os.getenv("GRAYLOG_PASSWORD", "token")
TEAMS_URL    = os.getenv("TEAMS_WEBHOOK_URL")
GROQ_KEY     = os.getenv("GROQ_API_KEY")

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
PASS_LABEL = "✅ PASSOU"
FAIL_LABEL = "❌ FALHOU"
SKIP_LABEL = "⚠️  IGNORADO"

# Tabela de atalhos para --range (aceita segundos ou palavras-chave)
RANGE_ALIASES = {
    "10m":  600,
    "30m":  1800,
    "1h":   3600,
    "6h":   21600,
    "12h":  43200,
    "24h":  86400,
    "7d":   604800,
}

def parse_range(value: str) -> int:
    """Converte alias (ex: '1h', '24h') ou número inteiro em segundos."""
    if value in RANGE_ALIASES:
        return RANGE_ALIASES[value]
    try:
        seconds = int(value)
        if seconds <= 0:
            raise ValueError
        return seconds
    except ValueError:
        valid = ", ".join(RANGE_ALIASES.keys())
        print(f"\n❌ Valor inválido para --range: '{value}'")
        print(f"   Use segundos (ex: 3600) ou um atalho: {valid}")
        sys.exit(1)

def separator(title):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print('─' * 60)

def abort(msg):
    print(f"\n❌ {msg}")
    sys.exit(1)

def format_range_label(seconds: int) -> str:
    """Formata segundos em string legível para exibição."""
    if seconds < 3600:
        return f"{seconds // 60} minuto(s)"
    if seconds < 86400:
        return f"{seconds // 3600} hora(s)"
    return f"{seconds // 86400} dia(s)"

# ─────────────────────────────────────────────
# Pré-requisito: credenciais do Graylog
# ─────────────────────────────────────────────
def check_prerequisites():
    missing = [v for v, val in {
        "GRAYLOG_API_URL":  GRAYLOG_URL,
        "GRAYLOG_USER":     GRAYLOG_USER,
        "GRAYLOG_PASSWORD": GRAYLOG_PASS,
    }.items() if not val]

    if missing:
        abort(
            f"Variáveis de ambiente obrigatórias não configuradas: {', '.join(missing)}\n"
            "  Configure no .env ou como variáveis de ambiente antes de executar."
        )

# ─────────────────────────────────────────────
# MODO 1: --list-sources
# ─────────────────────────────────────────────
def list_sources():
    separator("DESCOBERTA DE FONTES no Graylog (últimos 60 min)")
    print(f"  Conectando em: {GRAYLOG_URL}")
    print("  Buscando mensagens recentes (query: *)...\n")

    df, err = integrations_lib.fetch_logs_from_graylog(
        GRAYLOG_URL, GRAYLOG_USER, GRAYLOG_PASS,
        query="*",
        relative=3600,
        limit=5000,
        fields="timestamp,source,message"
    )

    if err:
        abort(f"Falha ao conectar no Graylog: {err}")

    if df is None or df.empty:
        print("  Nenhum log encontrado no período. Verifique as credenciais e se o Graylog tem dados.")
        return

    if "source" not in df.columns:
        abort("Coluna 'source' não encontrada na resposta. Verifique os campos retornados pelo Graylog.")

    sources = sorted(df["source"].dropna().unique())
    total   = len(df)

    print(f"  {total} logs encontrados — {len(sources)} fonte(s) única(s):\n")
    for src in sources:
        count = len(df[df["source"] == src])
        print(f"    • {src:<45} ({count} logs)")

    # Verifica configuração atual do .env
    current_sources = os.getenv("WATCHDOG_SOURCES", "")
    if current_sources:
        print(f"\n  🔧 WATCHDOG_SOURCES no .env: {current_sources}")
        configured = {s.strip() for s in current_sources.split(",")}
        nao_encontradas = configured - set(sources)
        if nao_encontradas:
            print(f"  ⚠️  Fontes no .env NÃO encontradas no Graylog: {nao_encontradas}")
            print("     Verifique maiúsculas/minúsculas (case-sensitive).")
        else:
            print("  ✅ Todas as fontes do .env foram encontradas no Graylog.")

    print(f"\n  💡 Próximos passos:")
    print(f'     # Inspecionar sem enviar ao Teams:')
    print(f'     py tests/test_watchdog_real.py --source "{sources[0]}" --range 24h --dry-run')
    print(f'     # Envio real ao Teams:')
    print(f'     py tests/test_watchdog_real.py --source "{sources[0]}" --range 24h')

# ─────────────────────────────────────────────
# MODO 2: --source <nome> [--dry-run] [--range N]
# ─────────────────────────────────────────────
def run_real_watchdog(sources_str: str, dry_run: bool, range_seconds: int):
    sources = [s.strip() for s in sources_str.split(",") if s.strip()]
    if not sources:
        abort("Nenhuma fonte válida fornecida em --source.")

    range_label = format_range_label(range_seconds)
    results     = []

    mode_label = "DRY RUN (sem envio ao Teams)" if dry_run else "ENVIO AO TEAMS ATIVADO"
    separator(f"WATCHDOG COM DADOS REAIS — {mode_label}")
    print(f"  Fontes    : {sources}")
    print(f"  Graylog   : {GRAYLOG_URL}")
    print(f"  Janela    : últimos {range_label} ({range_seconds}s)")
    print(f"  IA (Groq) : {'configurada' if GROQ_KEY else 'NÃO configurada'}")
    print(f"  Teams     : {'configurado' if TEAMS_URL else 'NÃO configurado'}")

    # ── Passo 1: Busca logs críticos no Graylog ───────────────────────────
    separator(f"Passo 1/4 — Busca de logs críticos ({range_label})")

    sources_query = " OR ".join([f'source:"{s}"' for s in sources])
    query = (
        f'(message:"Error" OR message:"Fail" OR message:"Critical" '
        f'OR message:"Fatal" OR message:"Exception" OR level:[0 TO 4]) '
        f'AND ({sources_query})'
    )
    fields = (
        "timestamp,source,message,level,LogLevel,"
        "container_name,image_name,command,RequestPath,cpu_valor,mem_valor"
    )

    print(f"  Query : {query[:120]}...")
    print()

    df_raw, err = integrations_lib.fetch_logs_from_graylog(
        GRAYLOG_URL, GRAYLOG_USER, GRAYLOG_PASS,
        query=query, relative=range_seconds, limit=500, fields=fields
    )

    if err:
        print(f"  {FAIL_LABEL} — {err}")
        results.append(("Busca Graylog", False))
        df_raw = pd.DataFrame()
    elif df_raw is None or df_raw.empty:
        print(f"  {SKIP_LABEL} — Nenhum log crítico nos últimos {range_label} para as fontes informadas.")
        print()
        print("  Diagnóstico:")
        print(f"   • Os serviços estão operando sem erros no período? (normal em ambiente estável)")
        print(f"   • Tente uma janela maior: --range 24h ou --range 7d")
        print(f"   • Confirme as fontes com: py tests/test_watchdog_real.py --list-sources")
        results.append(("Busca Graylog", None))
        df_raw = pd.DataFrame()
    else:
        print(f"  {PASS_LABEL} — {len(df_raw)} log(s) encontrado(s)")
        print(f"\n  Amostra (3 primeiros):")
        for _, row in df_raw.head(3).iterrows():
            ts  = row.get("timestamp", "?")
            src = row.get("source", "?")
            msg = str(row.get("message", ""))[:100]
            print(f"    [{ts}] [{src}] {msg}...")
        results.append(("Busca Graylog", True))

    # ── Passo 2: Classifica por nível de log ──────────────────────────────
    separator("Passo 2/4 — Classificação por nível de log")

    df_watchdog = pd.DataFrame()
    if df_raw.empty:
        print(f"  {SKIP_LABEL} — Sem dados do passo anterior.")
        results.append(("Classificação", None))
    else:
        app_config, _ = lam.load_config()
        df_proc, _    = lam.process_log_data(df_raw, app_config)
        crit_mask     = df_proc["log_level"].isin(["Error", "Fail", "Critical", "Fatal"])
        df_watchdog   = df_raw.loc[df_proc[crit_mask].index].copy()

        # Exibe distribuição completa para diagnóstico
        lvl_all  = df_proc["log_level"].value_counts().to_dict()
        print(f"  Todos os níveis encontrados: {lvl_all}")

        if df_watchdog.empty:
            print(f"\n  {SKIP_LABEL} — Nenhum log classificado como crítico.")
            print("  Os logs existem mas não foram categorizados como Error/Fail/Critical/Fatal.")
            print("  Isso pode indicar que os logs não têm campo 'LogLevel' explícito.")
            print("  Tente o modo --all-levels para incluir todos os níveis no teste.")
            results.append(("Classificação", None))
        else:
            lvl_crit = df_proc.loc[df_proc[crit_mask].index, "log_level"].value_counts().to_dict()
            print(f"  {PASS_LABEL} — {len(df_watchdog)} crítico(s): {lvl_crit}")
            results.append(("Classificação", True))

    # ── Passo 3: Análise da IA ────────────────────────────────────────────
    separator("Passo 3/4 — Análise de IA (Groq)")

    analise_ia = None
    if df_watchdog.empty:
        print(f"  {SKIP_LABEL} — Sem logs críticos para analisar.")
        results.append(("Análise IA", None))
    elif not GROQ_KEY:
        analise_ia = "[GROQ_API_KEY não configurada — análise de IA indisponível]"
        print(f"  {SKIP_LABEL} — {analise_ia}")
        results.append(("Análise IA", None))
    else:
        latest_err = df_watchdog.iloc[0]
        prompt_ia  = (
            "Você é um SRE especialista. Analise este erro de produção e forneça:\n"
            "1. Resumo do problema (1 frase)\n"
            "2. Causa provável (1-2 frases)\n"
            "3. Ação imediata recomendada (1-2 frases)\n\n"
            f"Log: {str(latest_err.get('message', ''))[:800]}"
        )
        try:
            analise_ia = lam.send_chat_message([{"role": "user", "content": prompt_ia}])
            assert isinstance(analise_ia, str) and len(analise_ia) > 20
            print(f"  {PASS_LABEL} — IA respondeu ({len(analise_ia)} chars)")
            print(f"  📝 {analise_ia[:200]}...")
            results.append(("Análise IA", True))
        except Exception as e:
            analise_ia = f"[Erro IA: {e}]"
            print(f"  {FAIL_LABEL} — {e}")
            results.append(("Análise IA", False))

    # ── Passo 4: Monta e envia alerta ─────────────────────────────────────
    separator(f"Passo 4/4 — {'Geração do payload (dry-run)' if dry_run else 'Envio ao Teams'}")

    if df_watchdog.empty:
        print(f"  {SKIP_LABEL} — Sem logs críticos para gerar alerta.")
        results.append(("Envio Teams", None))
    else:
        latest_err   = df_watchdog.iloc[0]
        corpo_tabela = integrations_lib.format_graylog_table(latest_err)
        total        = len(df_watchdog)
        sources_aff  = ", ".join(df_watchdog["source"].dropna().unique()[:5])
        ts_err       = latest_err.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        alert_title = f"🔥 [TESTE REAL] Watchdog IA — {total} erro(s) em {range_label}"
        alert_body  = (
            f"**🕐 Timestamp:** {ts_err}\n\n"
            f"**📦 Fonte(s) afetada(s):** {sources_aff}\n\n"
            f"**⏱ Janela analisada:** últimos {range_label}\n\n"
            f"**🤖 Análise da IA:**\n{analise_ia or '[sem análise]'}\n\n"
            f"---\n\n"
            f"**📋 Detalhes do log mais recente:**\n\n{corpo_tabela}"
        )

        print(f"  Payload  : {len(alert_body)} chars")
        print(f"  Título   : {alert_title}")

        if dry_run:
            print(f"\n  {SKIP_LABEL} — DRY RUN: payload gerado, mas NÃO enviado.")
            print(f"\n  ── Prévia ────────────────────────────────────────────")
            print(f"  {alert_body[:600]}...")
            results.append(("Envio Teams", None))
        elif not TEAMS_URL:
            print(f"\n  {SKIP_LABEL} — TEAMS_WEBHOOK_URL não configurada no .env.")
            results.append(("Envio Teams", None))
        else:
            send_result = integrations_lib.send_webhook_alert(TEAMS_URL, alert_body, title=alert_title)
            ok = hasattr(send_result, "status_code") and send_result.status_code == 200
            if ok:
                print(f"\n  {PASS_LABEL} — HTTP {send_result.status_code}")
                print("  ✔ Verifique o canal do Teams para confirmar a renderização visual.")
            else:
                print(f"\n  {FAIL_LABEL} — {send_result}")
            results.append(("Envio Teams", ok))

    # ── Resumo ─────────────────────────────────────────────────────────────
    separator("RESUMO FINAL")
    all_ok = True
    for label, ok in results:
        if ok is None:
            print(f"  ⚠️   {label:<30} IGNORADO (sem dados no período)")
        elif ok:
            print(f"  ✅  {label:<30} PASSOU")
        else:
            print(f"  ❌  {label:<30} FALHOU")
            all_ok = False

    print()
    if all_ok:
        if all(ok is None for _, ok in results):
            print("ℹ️  Nenhum erro crítico encontrado no período. Sistema operando normalmente.")
            print(f"   Tente ampliar a janela: --range 24h ou --range 7d")
        else:
            print("🏁 Fluxo completo executado com sucesso.")
    else:
        print("🔴 Um ou mais passos falharam. Veja as mensagens acima.")
        sys.exit(1)

# ─────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────
if __name__ == "__main__":
    valid_aliases = ", ".join(RANGE_ALIASES.keys())
    parser = argparse.ArgumentParser(
        description="Teste de integração do AI Watchdog com dados reais do Graylog.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  py tests/test_watchdog_real.py --list-sources\n"
            "  py tests/test_watchdog_real.py --source \"Locksp-swarm4\" --range 24h --dry-run\n"
            "  py tests/test_watchdog_real.py --source \"Locksp-swarm4,locksp-swarm2\" --range 24h\n"
            "  py tests/test_watchdog_real.py --source \"Locksp-swarm4\" --range 86400\n"
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--list-sources", action="store_true",
        help="Lista fontes disponíveis no Graylog (últimos 60 min)"
    )
    group.add_argument(
        "--source", type=str, metavar="FONTES",
        help="Fonte(s) separadas por vírgula. Ex: 'Locksp-swarm4,locksp-swarm2'"
    )
    parser.add_argument(
        "--range", type=str, default="10m", metavar="JANELA",
        help=f"Janela de busca. Segundos ou atalhos: {valid_aliases}. Padrão: 10m"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Gera o payload mas NÃO envia ao Teams"
    )

    args = parser.parse_args()
    check_prerequisites()

    if args.list_sources:
        list_sources()
    else:
        run_real_watchdog(
            sources_str=args.source,
            dry_run=args.dry_run,
            range_seconds=parse_range(args.range)
        )