import pandas as pd
import numpy as np
import warnings
# A biblioteca scikit-learn é necessária para esta função.
# Se não estiver instalada, execute: pip install scikit-learn
from sklearn.linear_model import LinearRegression

# Tenta importar statsmodels para previsões mais avançadas (ARIMA)
try:
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tools.sm_exceptions import ConvergenceWarning
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    ConvergenceWarning = UserWarning # Fallback seguro para o filtro de warnings

def detect_volume_anomalies(df, window=30, threshold=3.0, rule='T'):
    """
    Detecta anomalias de volume em um DataFrame de logs usando o método Z-score com janela móvel.

    Args:
        df (pd.DataFrame): DataFrame de logs com a coluna 'timestamp'.
        window (int): Janela (em número de períodos) para o cálculo da média e desvio padrão móvel.
        threshold (float): Limiar do Z-score para considerar um ponto como anomalia.
        rule (str): Regra de resampling do pandas (ex: 'T' para minuto, 'H' para hora).

    Returns:
        pd.DataFrame: DataFrame contendo os pontos de anomalia com 'timestamp' e 'count'.
    """
    if df is None or df.empty or 'timestamp' not in df.columns:
        return pd.DataFrame()

    # Garante que o timestamp é do tipo datetime
    df_copy = df.copy()
    df_copy['timestamp'] = pd.to_datetime(df_copy['timestamp'], errors='coerce')
    df_copy = df_copy.dropna(subset=['timestamp'])

    if df_copy.empty:
        return pd.DataFrame()

    # Agrupa logs por período de tempo (ex: por minuto) e conta
    volume = df_copy.set_index('timestamp').resample(rule).size().reset_index(name='count')
    
    # Se não houver dados suficientes para a janela, retorna vazio
    if len(volume) < window:
        return pd.DataFrame()

    # Calcula a média e o desvio padrão móveis
    volume['rolling_mean'] = volume['count'].rolling(window=window, center=True, min_periods=1).mean()
    volume['rolling_std'] = volume['count'].rolling(window=window, center=True, min_periods=1).std()

    # Evita divisão por zero. Se std é 0, não há anomalia.
    volume['rolling_std'] = volume['rolling_std'].replace(0, pd.NA)
    volume = volume.dropna(subset=['rolling_std'])

    # Calcula o Z-score
    volume['z_score'] = (volume['count'] - volume['rolling_mean']) / volume['rolling_std']

    # Identifica anomalias
    anomalies = volume[volume['z_score'].abs() > threshold].copy()

    return anomalies[['timestamp', 'count']]

def generate_volume_forecast(df, periods=30, rule='T'):
    """
    Gera uma previsão de volume de logs usando ARIMA (se disponível) ou regressão linear.

    Args:
        df (pd.DataFrame): DataFrame de logs com a coluna 'timestamp'.
        periods (int): Número de períodos futuros para prever.
        rule (str): Regra de resampling do pandas (ex: 'T' para minuto).

    Returns:
        tuple: (pd.DataFrame, str, float)
            - DataFrame com dados históricos e de previsão.
            - String da tendência ('Alta', 'Baixa', 'Estável').
            - Coeficiente (slope) da regressão.
    """
    if df is None or df.empty or 'timestamp' not in df.columns:
        return pd.DataFrame(), "Indisponível", 0.0

    df_copy = df.copy()
    df_copy['timestamp'] = pd.to_datetime(df_copy['timestamp'], errors='coerce')
    df_copy = df_copy.dropna(subset=['timestamp'])

    if len(df_copy) < 2:
        return pd.DataFrame(), "Dados insuficientes", 0.0

    # 1. Agrupar dados por volume
    volume = df_copy.set_index('timestamp').resample(rule).size().reset_index(name='count')
    
    if len(volume) < 2:
        return pd.DataFrame(), "Dados insuficientes", 0.0

    # 2. Preparar dados para regressão (usando um índice numérico simples para o tempo)
    volume['time_index'] = np.arange(len(volume))
    X = volume[['time_index']]
    y = volume['count']

    # 3. Calcular Tendência Linear (usada para o indicador de texto e fallback)
    model_lin = LinearRegression()
    model_lin.fit(X.values, y)
    slope = model_lin.coef_[0]

    # 4. Determinar tendência
    trend = "Estável"
    if slope > 0.1: trend = "Alta"
    elif slope < -0.1: trend = "Baixa"

    # 5. Gerar Previsões (ARIMA ou Linear)
    predictions = None
    
    if STATSMODELS_AVAILABLE and len(y) >= 15:
        # Requer mínimo de dados para evitar warnings de convergência e parâmetros
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning)
                warnings.filterwarnings("ignore", category=ConvergenceWarning)
                
                # ARIMA(5,1,0) para capturar comportamento autoregressivo recente
                # Para sazonalidade real, seria ideal usar SARIMAX se o 'rule' fosse conhecido e fixo (ex: 24h)
                arima_model = ARIMA(y, order=(5, 1, 0))
                arima_result = arima_model.fit()
                predictions = arima_result.forecast(steps=periods)
                predictions = np.array(predictions) # Garante formato numpy
        except Exception:
            # Falha silenciosa no ARIMA, fallback para Linear
            predictions = None

    if predictions is None:
        # Fallback para Regressão Linear
        last_index = volume['time_index'].max()
        future_indices = np.arange(last_index + 1, last_index + 1 + periods).reshape(-1, 1)
        predictions = model_lin.predict(future_indices)

    predictions[predictions < 0] = 0 # Contagem não pode ser negativa

    # 6. Combinar dados históricos e de previsão para o gráfico
    volume['type'] = 'Histórico'
    future_timestamps = pd.to_datetime(volume['timestamp'].max()) + pd.to_timedelta(np.arange(1, periods + 1), unit=rule)
    future_df = pd.DataFrame({'timestamp': future_timestamps, 'count': predictions.round(), 'type': 'Previsão'})
    combined_df = pd.concat([volume[['timestamp', 'count', 'type']], future_df], ignore_index=True)

    return combined_df, trend, slope