# c:\Users\Andressa.Atelli\Documents\locktonloganalytics\log_analyzer	race_analysis.py
# Este arquivo contém funções para análise de traces distribuídos.

import pandas as pd
import re
import numpy as np

UUID_PATTERN = re.compile(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', re.IGNORECASE)
TRACE_ID_PATTERN = re.compile(r'TraceId[:=]\s*([a-f0-9]{32})', re.IGNORECASE)

def extract_trace_ids(df):
    """Extrai Trace IDs (UUIDs ou W3C) das mensagens para rastreamento distribuído."""
    if df.empty: return df
    
    df = df.reset_index(drop=True)
    
    uuid_extract = df['message'].astype(str).str.extract(UUID_PATTERN, expand=False)
    w3c_extract = df['message'].astype(str).str.extract(TRACE_ID_PATTERN, expand=False)
    
    df['trace_id'] = np.where(uuid_extract.notna(), uuid_extract.values, w3c_extract.values)
    return df
