# c:\Users\Andressa.Atelli\Documents\locktonloganalytics\log_analyzer\anomaly_detection.py
# Este arquivo contém funções para detecção de anomalias nos logs.

import pandas as pd
import numpy as np
import re

NUM_PATTERN = re.compile(r'\d+')
UUID_PATTERN = re.compile(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', re.IGNORECASE)

def detect_volume_anomalies(df, time_window='1min', z_score_threshold=3):
    """
    Detecta picos anômalos no volume de logs usando o método Z-Score.
    """
    if 'timestamp' not in df.columns or df.empty: return pd.DataFrame()
    
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    volume = df.set_index('timestamp').resample(time_window).size()
    mean = volume.rolling(window=60, min_periods=1).mean()
    std = volume.rolling(window=60, min_periods=1).std()
    z_scores = (volume - mean) / std.replace(0, 1) # Evita divisão por zero
    
    return volume[z_scores > z_score_threshold].reset_index(name='count')

def detect_rare_patterns(df, rarity_threshold=0.01):
    """
    Identifica padrões de log que ocorrem com baixa frequência, um sinal de anomalia.
    """
    if df.empty: return pd.DataFrame()
    df = df.copy()
    df['pattern_signature'] = df['message'].astype(str).str.replace(NUM_PATTERN, '<NUM>', regex=True).str.slice(0, 100)
    counts = df['pattern_signature'].value_counts(normalize=True)
    rare_sigs = counts[counts < rarity_threshold].index
    return df[df['pattern_signature'].isin(rare_sigs)].drop(columns=['pattern_signature'])

def group_incidents(df):
    """Agrupa logs de erro similares em 'incidentes' para análise de causa raiz."""
    if df.empty: return pd.DataFrame()
    
    error_df = df[df['log_level'].isin(['Error', 'Fail', 'Critical', 'Fatal'])].copy()
    if error_df.empty: return pd.DataFrame()

    sigs = error_df['message'].astype(str).str.replace(NUM_PATTERN, '<NUM>', regex=True)
    error_df['signature'] = sigs.str.replace(UUID_PATTERN, '<UUID>', regex=True).str.slice(0, 150)
    
    return error_df.groupby('signature').agg(
        count=('timestamp', 'size'),
        first_seen=('timestamp', 'min'),
        last_seen=('timestamp', 'max'),
        example_message=('message', 'first'),
        sources=('source', lambda x: list(set(x))[:3])
    ).reset_index().sort_values('count', ascending=False)

def generate_volume_forecast(df, periods=60):
    """
    Gera uma previsão de volume de logs usando Holt-Winters ou Regressão Linear.
    """
    if df.empty or 'timestamp' not in df.columns:
        return pd.DataFrame(), "Dados insuficientes", 0

    # Garante datetime
    temp_df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(temp_df['timestamp']):
        temp_df['timestamp'] = pd.to_datetime(temp_df['timestamp'], errors='coerce')
    
    temp_df = temp_df.dropna(subset=['timestamp'])

    # Resample adaptativo
    duration_sec = (temp_df['timestamp'].max() - temp_df['timestamp'].min()).total_seconds()
    rule = '1S' if duration_sec < 60 else ('10S' if duration_sec < 300 else 'T')

    df_hist = temp_df.set_index('timestamp').resample(rule).size().reset_index(name='count')
    
    if len(df_hist) < 2:
        return pd.DataFrame(), "Dados insuficientes", 0

    # --- TENTATIVA 1: Holt-Winters ---
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        if rule == 'T' and len(df_hist) >= 5:
            ts_data = df_hist.set_index('timestamp')['count'].asfreq('T', fill_value=0)
            seasonal_periods = 60 if len(ts_data) > 120 else None
            model = ExponentialSmoothing(ts_data, trend='add', seasonal='add' if seasonal_periods else None, seasonal_periods=seasonal_periods).fit()
            forecast_values = model.forecast(periods)
            
            future_dates = [ts_data.index[-1] + pd.Timedelta(minutes=i+1) for i in range(periods)]
            df_forecast = pd.DataFrame({'timestamp': future_dates, 'count': forecast_values.values, 'type': 'Previsão (Holt-Winters) 🔮'})
            df_hist['type'] = 'Histórico 📊'
            
            m = (forecast_values.iloc[-1] - ts_data.iloc[-1]) / (periods * 60)
            trend = "Crescente 📈" if m > 0.05 else ("Decrescente 📉" if m < -0.05 else "Estável ➡️")
            return pd.concat([df_hist[['timestamp', 'count', 'type']], df_forecast]), trend, m
    except:
        pass

    # --- TENTATIVA 2: Regressão Linear ---
    df_hist['time_sec'] = df_hist['timestamp'].astype(np.int64) // 10**9
    X, y = df_hist['time_sec'].values, df_hist['count'].values
    m, b = np.polyfit(X, y, 1)

    last_time = df_hist['timestamp'].max()
    future_dates = [last_time + pd.Timedelta(minutes=i+1) for i in range(periods)]
    future_secs = np.array([t.timestamp() for t in future_dates])
    future_counts = np.maximum(m * future_secs + b, 0)

    df_forecast = pd.DataFrame({'timestamp': future_dates, 'count': future_counts, 'type': 'Previsão (Linear) 🔮'})
    df_hist['type'] = 'Histórico 📊'
    
    trend = "Crescente 📈" if m > 0.05 else ("Decrescente 📉" if m < -0.05 else "Estável ➡️")
    return pd.concat([df_hist[['timestamp', 'count', 'type']], df_forecast]), trend, m

def detect_log_periodicity(df):
    """
    Usa FFT (Fast Fourier Transform) para detectar periodicidade no volume de logs.
    """
    if df.empty or 'timestamp' not in df.columns: return []

    temp_df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(temp_df['timestamp']):
        temp_df['timestamp'] = pd.to_datetime(temp_df['timestamp'], errors='coerce')
    temp_df = temp_df.dropna(subset=['timestamp'])
    
    duration_sec = (temp_df['timestamp'].max() - temp_df['timestamp'].min()).total_seconds()
    rule, d_val = ('5S', 5.0/60.0) if duration_sec < 300 else ('T', 1.0)

    ts = temp_df.set_index('timestamp').resample(rule).size()
    N = len(ts)
    if N < 3: return []
        
    data = ts.values - np.mean(ts.values)
    fft_spectrum = np.fft.rfft(data)
    fft_freqs = np.fft.rfftfreq(N, d=d_val)
    magnitude = np.abs(fft_spectrum)
    
    # Filtra frequências muito baixas
    mask = fft_freqs > (2.0 / N)
    magnitude = magnitude[mask]
    fft_freqs = fft_freqs[mask]
    
    if len(magnitude) == 0: return []
    if magnitude.max() > 0: magnitude /= magnitude.max()
    
    peaks = []
    for i in range(1, len(magnitude)-1):
        if magnitude[i] > magnitude[i-1] and magnitude[i] > magnitude[i+1]:
            if magnitude[i] > 0.15:
                peaks.append((1.0 / fft_freqs[i], magnitude[i]))
    
    peaks.sort(key=lambda x: x[1], reverse=True)
    return peaks[:3]
