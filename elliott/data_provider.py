"""Descarga de histórico OHLCV desde yfinance, con reintentos ante rate limit."""
import time
import random
import pandas as pd
import yfinance as yf

# Sesión con impersonación de navegador para evitar el 429 de Yahoo.
# Requiere: pip install curl_cffi
# Si no está instalada, se cae a la sesión normal de yfinance (más propensa a rate limit).
try:
    from curl_cffi import requests as curl_requests
    _YF_SESSION = curl_requests.Session(impersonate="chrome")
except ImportError:
    _YF_SESSION = None


class MarketDataProvider:
    def __init__(self):
        self.sp500 = []
        self.nasdaq100 = []

    def load_universe(self):
        try:
            sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            tables = pd.read_html(sp500_url)
            self.sp500 = tables[0]['Symbol'].str.replace('.', '-', regex=False).tolist()

            nasdaq_url = "https://en.wikipedia.org/wiki/Nasdaq-100"
            tables = pd.read_html(nasdaq_url)
            for t in tables:
                if 'Ticker' in t.columns:
                    self.nasdaq100 = t['Ticker'].tolist()
                    break
            print(f"Universo cargado: {len(self.sp500)} S&P500, {len(self.nasdaq100)} NASDAQ-100")
        except Exception as e:
            print(f"Advertencia: No se pudo cargar universo completo ({e}), usando modo libre")
            self.sp500 = []
            self.nasdaq100 = []

    def validate_ticker(self, ticker: str) -> bool:
        if not self.sp500:
            return True
        ticker = ticker.upper()
        return ticker in self.sp500 or ticker in self.nasdaq100

    def get_data(self, ticker: str, period: str = "2y", max_retries: int = 5) -> pd.DataFrame:
        print(f"[DATA] Descargando {ticker} - {period}...")
        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                if _YF_SESSION is not None:
                    tk = yf.Ticker(ticker, session=_YF_SESSION)
                else:
                    tk = yf.Ticker(ticker)
                df = tk.history(period=period, auto_adjust=True)

                if df.empty:
                    raise ValueError(f"No se encontró data para {ticker} (respuesta vacía, puede ser ticker inválido)")

                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.dropna(inplace=True)
                return df

            except Exception as e:
                last_err = e
                msg = str(e).lower()
                is_rate_limit = "rate limit" in msg or "429" in msg or "too many requests" in msg
                if is_rate_limit and attempt < max_retries:
                    # backoff exponencial + jitter: 2, 4, 8, 16s (+ ruido)
                    wait = (2 ** attempt) + random.uniform(0, 1.5)
                    print(f"[DATA] Rate limited (intento {attempt}/{max_retries}). Reintentando en {wait:.1f}s...")
                    time.sleep(wait)
                    continue
                elif is_rate_limit:
                    raise ValueError(
                        f"Yahoo Finance te está limitando (rate limit) tras {max_retries} intentos. "
                        f"No es que {ticker} no exista: es que Yahoo está bloqueando la IP/sesión temporalmente. "
                        f"Esperá unos minutos, instalá curl_cffi (pip install curl_cffi) si no la tenés, "
                        f"y evitá correr el script en loop rápido."
                    ) from e
                else:
                    raise

        raise ValueError(f"No se encontró data para {ticker}: {last_err}")
