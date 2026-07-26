"""
MTF Analyzer - Multi Timeframe Confluence
Analiza el mismo ticker en 1W, 1D, 4H, 1H para alineación.

Fuente de datos: si se pasa un IBKRConnector ya conectado, usa IBKR para las
4 timeframes (mismos datos/broker que el resto del dashboard). Si no se pasa
ibkr, o IBKR falla para alguna timeframe puntual, cae automáticamente a
yfinance solo para esa timeframe (para no romper el análisis completo por un
timeout puntual de IBKR).
"""
import yfinance as yf
import pandas as pd
from typing import Dict, Optional
import time, random

try:
    from curl_cffi import requests as curl_requests
    _SESSION = curl_requests.Session(impersonate="chrome")
except ImportError:
    _SESSION = None

class MTFAnalyzer:
    def __init__(self, deviation_pct=5.0):
        self.deviation = deviation_pct

    def _get_data_mtf_yf(self, ticker: str, period: str, interval: str):
        for attempt in range(3):
            try:
                tk = yf.Ticker(ticker, session=_SESSION) if _SESSION else yf.Ticker(ticker)
                df = tk.history(period=period, interval=interval, auto_adjust=True)
                if df.empty:
                    return None
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.dropna(inplace=True)
                return df
            except Exception as e:
                if "rate limit" in str(e).lower() or "429" in str(e).lower():
                    time.sleep(2**attempt + random.uniform(0,1))
                    continue
                return None
        return None

    def _get_data_mtf_ibkr(self, ibkr, ticker: str, duration: str, bar_size: str):
        try:
            df = ibkr.get_historical_bars(ticker, duration=duration, bar_size=bar_size)
            if df is None or df.empty:
                return None
            return df
        except Exception:
            return None

    def _quick_trend(self, df: pd.DataFrame) -> Dict:
        # Trend rápido sin Elliott completo: SMA20 vs SMA200 + estructura
        if len(df) < 50:
            return {"trend": "UNKNOWN", "score": 0}
        sma20 = df['Close'].rolling(20).mean().iloc[-1]
        sma200 = df['Close'].rolling(200).mean().iloc[-1] if len(df)>=200 else df['Close'].mean()
        close = df['Close'].iloc[-1]
        # HH/HL simple últimos 20
        highs = df['High'].tail(20)
        lows = df['Low'].tail(20)
        hh = highs.iloc[-1] > highs.iloc[-5]
        hl = lows.iloc[-1] > lows.iloc[-5]
        ll = lows.iloc[-1] < lows.iloc[-5]
        lh = highs.iloc[-1] < highs.iloc[-5]

        if close > sma20 and close > sma200 and hh and hl:
            return {"trend": "BULL", "score": 1, "sma20": float(sma20), "sma200": float(sma200)}
        elif close < sma20 and close < sma200 and ll and lh:
            return {"trend": "BEAR", "score": -1, "sma20": float(sma20), "sma200": float(sma200)}
        else:
            return {"trend": "NEUTRAL", "score": 0, "sma20": float(sma20), "sma200": float(sma200)}

    def analyze(self, ticker: str, deviation: float = 5.0, ibkr=None) -> Dict:
        results = {}
        fuente = {}
        # Config por timeframe: periodo/intervalo para yfinance y duration/barSize para IBKR
        timeframes = {
            "1W": {"yf_period": "2y",  "yf_interval": "1wk", "ibkr_duration": "2 Y", "ibkr_bar": "1W"},
            "1D": {"yf_period": "2y",  "yf_interval": "1d",  "ibkr_duration": "2 Y", "ibkr_bar": "1 day"},
            "4H": {"yf_period": "6mo", "yf_interval": "4h",  "ibkr_duration": "3 M", "ibkr_bar": "4 hours"},
            "1H": {"yf_period": "1mo", "yf_interval": "1h",  "ibkr_duration": "1 M", "ibkr_bar": "1 hour"},
        }

        use_ibkr = ibkr is not None and getattr(ibkr, "connected", False)

        for tf, cfg in timeframes.items():
            df = None
            if use_ibkr:
                df = self._get_data_mtf_ibkr(ibkr, ticker, cfg['ibkr_duration'], cfg['ibkr_bar'])
                fuente[tf] = "IBKR" if df is not None and len(df) >= 30 else "IBKR(sin datos)"

            if df is None or len(df) < 30:
                df_yf = self._get_data_mtf_yf(ticker, cfg['yf_period'], cfg['yf_interval'])
                if df_yf is not None:
                    df = df_yf
                    fuente[tf] = "yfinance (fallback)" if use_ibkr else "yfinance"

            if df is None or len(df) < 30:
                results[tf] = {"trend": "UNKNOWN", "score": 0, "reason": "Sin datos"}
                fuente[tf] = "Sin datos"
                continue
            trend_data = self._quick_trend(df)
            results[tf] = trend_data

        # Alineación
        scores = [v['score'] for v in results.values() if v['trend'] != "UNKNOWN"]
        if not scores:
            alignment = "UNKNOWN"
            align_score = 0
        elif all(s >= 0 for s in scores) and sum(scores) >=2:
            alignment = "BULL_ALIGNED"
            align_score = 20
        elif all(s <= 0 for s in scores) and sum(scores) <= -2:
            alignment = "BEAR_ALIGNED"
            align_score = 20
        elif len(set(scores))==1 and scores[0]==0:
            alignment = "NEUTRAL_ALL"
            align_score = -10
        else:
            alignment = "MIXED"
            align_score = -15

        # Texto
        txt = " | ".join([f"{k}:{v['trend']}" for k,v in results.items()])

        return {
            "timeframes": results,
            "fuente_datos": fuente,
            "alignment": alignment,
            "align_score": align_score,
            "reason": f"MTF {txt} => {alignment}",
            "score_mod": align_score
        }
