# c:\Users\Andressa.Atelli\Documents\locktonloganalytics\log_analyzer\__init__.py

"""
Log Analyzer Package
"""

from .ai import (
    generate_initial_prompt,
    send_chat_message,
    analyze_log_with_ai,
    generate_rca_prompt,
    analyze_critical_logs_with_ai
)

from .database import (
    save_ai_analysis,
    clear_ai_cache,
    get_db_stats,
    update_ai_feedback,
    get_ai_feedback,
    get_cached_ai_analysis,
    save_setting,
    get_setting,
    save_metric_definition,
    get_metric_definitions,
    delete_metric_definition,
    get_metric_history,
    ingest_logs_to_db,
    search_logs_in_db,
    get_unique_sources_from_db,
    get_rum_stats,
    get_all_cached_analyses,
    save_to_disk,
    load_from_disk
)

from .integrations import (
    send_jira_automation_webhook,
    fetch_logs_from_graylog,
    send_webhook_alert,
    calculate_file_hash,
    send_gelf_message,
    get_host_from_url,
    get_graylog_node_id,
    get_graylog_system_stats,
    format_graylog_table
)

from .log_parser import (
    process_log_data,
    categorize_log,
    extract_log_level,
    mask_sensitive_data,
    generate_log_patterns,
    parse_log_entry
)

from .anomaly_detection import (
    detect_volume_anomalies,
    detect_rare_patterns,
    group_incidents,
    generate_volume_forecast,
    detect_log_periodicity
)

from .metrics_extraction import (
    extract_latency_metrics,
    detect_bottlenecks,
    generate_stack_trace_metrics,
    extract_system_metrics,
    extract_api_metrics
)

from .security_analysis import (
    analyze_security_threats
)

from .simulation import (
    simulate_alerts,
    run_synthetic_check
)

from .dependency_analysis import (
    infer_service_dependencies,
    compare_log_datasets
)

from .trace_analysis import (
    extract_trace_ids
)

from .scheduler_utils import (
    is_scheduler_running,
    start_scheduler_background,
    stop_scheduler_background,    
    get_last_collection_time
)

from .reporting import (
    generate_pdf_report
)

from .utils import (
    load_config,
    get_context_logs,
    get_secret
)