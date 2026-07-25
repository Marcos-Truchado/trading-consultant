"""
MTF Analyzer - Multi Timeframe Confluence
Analiza el mismo ticker en 1W, 1D, 4H para alineación
"""
import yfinance as yf
import pandas as pd
from typing import Dict
import time, random

try:
    from curl_cffi import requests as curl_requests
    _SESSION = curl_requests.Session(impersonate="chrome")
except ImportError:
    _SESSION = None

class MTFAnalyzer:
    def __init__(self, deviation_pct=5.0):
        self.deviation = deviation_pct

    def _get_data_mtf(self, ticker: str, period: str, interval: str):
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

    def analyze(self, ticker: str, deviation: float = 5.0) -> Dict:
        results = {}
        # Definición de timeframes: usamos periodos que Yahoo permite
        timeframes = {
            "1W": {"period": "2y", "interval": "1wk"},
            "1D": {"period": "2y", "interval": "1d"},
            "4H": {"period": "6mo", "interval": "4h"},
            "1H": {"period": "1mo", "interval": "1h"},
        }

        for tf, cfg in timeframes.items():
            df = self._get_data_mtf(ticker, cfg['period'], cfg['interval'])
            if df is None or len(df) < 30:
                results[tf] = {"trend": "UNKNOWN", "score": 0, "reason": "Sin datos"}
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
            "alignment": alignment,
            "align_score": align_score,
            "reason": f"MTF {txt} => {alignment}",
            "score_mod": align_score
        }
