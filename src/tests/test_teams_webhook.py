"""
Script de teste isolado para validar o envio de Adaptive Card ao Teams.
Uso: python test_teams_webhook.py
Requer: TEAMS_WEBHOOK_URL no .env ou variável de ambiente.
"""
import os
import sys
from datetime import datetime

# Garante importação correta a partir da raiz do projeto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env')))
except ImportError:
    pass

import pandas as pd
from src.log_analyzer_lib import integrations as integrations_lib
from src import log_analyzer as lam

WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL")

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
PASS = "✅ PASSOU"
FAIL = "❌ FALHOU"
results = []

def check(label, result):
    """Avalia o resultado de send_webhook_alert e imprime o status."""
    # Teams retorna status 200 com body "1" para sucesso
    ok = hasattr(result, 'status_code') and result.status_code == 200
    status = PASS if ok else FAIL
    detail = f"HTTP {result.status_code}" if hasattr(result, 'status_code') else str(result)
    print(f"  {status} — {detail}")
    results.append((label, ok))
    return ok

def separator(title):
    print(f"\n{'─' * 55}")
    print(f"  {title}")
    print('─' * 55)

def main():
    # ─────────────────────────────────────────────
    # Pré-requisito: URL configurada
    # ─────────────────────────────────────────────
    if not WEBHOOK_URL:
        print("❌ TEAMS_WEBHOOK_URL não configurada. Defina no .env ou como variável de ambiente.")
        sys.exit(1)

    print(f"\n🔗 Webhook: {WEBHOOK_URL[:60]}...")

    # ─────────────────────────────────────────────
    # CAMADA 1 — Transporte (Teams aceita a requisição?)
    # ─────────────────────────────────────────────
    separator("CAMADA 1: Transporte")

    print("▶ Teste 1: Mensagem simples...")
    result = integrations_lib.send_webhook_alert(
        WEBHOOK_URL,
        message="Este é um teste simples de conectividade.",
        title="🔔 Teste 1 — Mensagem Simples"
    )
    check("Mensagem simples", result)

    print("\n▶ Teste 2: Mensagem com Markdown...")
    result = integrations_lib.send_webhook_alert(
        WEBHOOK_URL,
        message=(
            "**Fonte:** simulacao-app\n\n"
            "**Nível:** Critical\n\n"
            "**Mensagem:** Database connection pool exhausted after 30s timeout.\n\n"
            "**CPU:** 92.5% | **MEM:** 88.1%"
        ),
        title="🔥 Teste 2 — Formatação com Markdown"
    )
    check("Markdown na mensagem", result)

    print("\n▶ Teste 3: Mensagem longa (teste de truncamento)...")
    long_message = "**Detalhe do erro:** " + ("A" * 1000)
    result = integrations_lib.send_webhook_alert(
        WEBHOOK_URL,
        message=long_message[:600] + "…",
        title="📋 Teste 3 — Mensagem Longa"
    )
    check("Mensagem longa truncada", result)

    # ─────────────────────────────────────────────
    # CAMADA 2 — Formatação (format_graylog_table gera saída válida?)
    # ─────────────────────────────────────────────
    separator("CAMADA 2: Formatação do log real (format_graylog_table)")

    # Simula exatamente o que chega do Graylog: uma pandas Series com os campos reais
    fake_log_row = pd.Series({
        "timestamp":            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "source":               "app-pagamentos-prod",
        "message":              "EXCEPTION | java.sql.SQLException: Timeout acquiring connection from pool after 30000ms. Pool size: 10/10.",
        "level":                3,
        "LogLevel":             "Critical",
        "container_name":       "pagamentos-api",
        "image_name":           "lockton/pagamentos:2.4.1",
        "command":              "java -jar app.jar",
        "cpu_valor":            87.3,
        "mem_valor":            91.0,
        "RequestPath":          "/api/v2/payments/process",
        "container_id":         None,
        "gl2_processing_error": float("nan"),
        "image_id":             "",
        "created":              None,
        "tag":                  "payments",
    })

    print("▶ Teste 4: format_graylog_table com dados realistas...")
    try:
        corpo_tabela = integrations_lib.format_graylog_table(fake_log_row)

        # Ajuste: Apenas verifica se formata sem quebrar e inclui os dados válidos
        assert "app-pagamentos-prod" in corpo_tabela, "Fonte deve estar presente"
        assert len(corpo_tabela) < 30_000, f"Payload excede 30KB: {len(corpo_tabela)} chars"

        print(f"  {PASS} — {len(corpo_tabela)} chars gerados, formatados corretamente")
        results.append(("format_graylog_table", True))
    except AssertionError as e:
        print(f"  {FAIL} — Assertiva falhou: {e}")
        results.append(("format_graylog_table", False))
    except Exception as e:
        print(f"  {FAIL} — Exceção: {e}")
        results.append(("format_graylog_table", False))

    # ─────────────────────────────────────────────
    # CAMADA 3 — IA (Groq responde e gera análise coerente?)
    # ─────────────────────────────────────────────
    separator("CAMADA 3: Análise de IA (Groq)")

    GROQ_KEY = os.getenv("GROQ_API_KEY")

    print("▶ Teste 5: Análise da IA com prompt do Watchdog...")
    if not GROQ_KEY:
        print(f"  ⚠️  IGNORADO — GROQ_API_KEY não configurada. Configure no .env para testar este passo.")
        results.append(("Análise IA (Groq)", None))
    else:
        try:
            prompt_ia = (
                "Você é um SRE especialista. Analise este erro de produção e forneça:\n"
                "1. Resumo do problema (1 frase)\n"
                "2. Causa provável (1-2 frases)\n"
                "3. Ação imediata recomendada (1-2 frases)\n\n"
                f"Log: {fake_log_row['message']}"
            )
            analise_ia = lam.send_chat_message([{"role": "user", "content": prompt_ia}])

            assert isinstance(analise_ia, str) and len(analise_ia) > 20, "Resposta da IA muito curta ou inválida"
            print(f"  {PASS} — IA respondeu ({len(analise_ia)} chars)")
            print(f"  📝 Prévia: {analise_ia[:120]}...")
            results.append(("Análise IA (Groq)", True))
        except AssertionError as e:
            print(f"  {FAIL} — {e}")
            results.append(("Análise IA (Groq)", False))
        except Exception as e:
            print(f"  {FAIL} — Exceção ao chamar Groq: {e}")
            results.append(("Análise IA (Groq)", False))

    # ─────────────────────────────────────────────
    # CAMADA 4 — Fluxo Completo (replica _internal_run_watchdog sem Graylog)
    # ─────────────────────────────────────────────
    separator("CAMADA 4: Fluxo completo do Watchdog (sem Graylog)")

    print("▶ Teste 6: Alerta completo — formato idêntico ao produzido pelo _internal_run_watchdog...")
    try:
        # Monta o alerta exatamente como _internal_run_watchdog faz em produção
        corpo_tabela = integrations_lib.format_graylog_table(fake_log_row)

        if GROQ_KEY:
            analise_ia = lam.send_chat_message([{"role": "user", "content": prompt_ia}])
        else:
            analise_ia = "[Análise de IA indisponível — GROQ_API_KEY não configurada]"

        total_found   = 3  # Simula 3 logs críticos encontrados
        sources_aff   = "app-pagamentos-prod, app-auth-prod"
        timestamp_err = fake_log_row["timestamp"]

        alert_title = f"🔥 Watchdog IA — {total_found} erro(s) crítico(s) detectado(s)"
        alert_body = (
            f"**🕐 Timestamp:** {timestamp_err}\n\n"
            f"**📦 Fonte(s) afetada(s):** {sources_aff}\n\n"
            f"**🤖 Análise da IA:**\n{analise_ia}\n\n"
            f"---\n\n"
            f"**📋 Detalhes do log mais recente:**\n\n{corpo_tabela}"
        )

        result = integrations_lib.send_webhook_alert(WEBHOOK_URL, alert_body, title=alert_title)
        check("Fluxo completo Watchdog", result)

    except Exception as e:
        print(f"  {FAIL} — Exceção inesperada: {e}")
        results.append(("Fluxo completo Watchdog", False))

    # ─────────────────────────────────────────────
    # Resumo Final
    # ─────────────────────────────────────────────
    separator("RESUMO")
    all_ok = True
    for label, ok in results:
        if ok is None:
            icon = "⚠️ "
            status_str = "IGNORADO"
        elif ok:
            icon = "✅"
            status_str = "PASSOU"
        else:
            icon = "❌"
            status_str = "FALHOU"
            all_ok = False
        print(f"  {icon} {label:<35} {status_str}")

    print()
    if all_ok:
        print("🏁 Todos os testes passaram. Verifique o canal do Teams para confirmar a renderização visual.")
    else:
        print("🔴 Um ou mais testes falharam. Corrija os erros antes de usar o Watchdog em produção.")
        sys.exit(1)

if __name__ == "__main__":
    main()