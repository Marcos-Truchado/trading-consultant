"""
Momentum Engine - RSI / MACD Divergence
El mejor filtro para onda 5 fallida
"""
import pandas as pd
import numpy as np
from typing import List, Dict

class MomentumEngine:
    def __init__(self, rsi_period=14):
        self.rsi_period = rsi_period

    def _rsi(self, closes: pd.Series):
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.rsi_period).mean()
        rs = gain / loss.replace(0, 0.001)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _macd(self, closes: pd.Series):
        ema12 = closes.ewm(span=12, adjust=False).mean()
        ema26 = closes.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        return macd, signal, hist

    def _find_lows(self, series: pd.Series, order=5) -> List[int]:
        # pivotes locales mínimos
        lows = []
        for i in range(order, len(series)-order):
            if series.iloc[i] == series.iloc[i-order:i+order+1].min():
                lows.append(i)
        return lows[-10:]  # últimos 10

    def _find_highs(self, series: pd.Series, order=5) -> List[int]:
        highs = []
        for i in range(order, len(series)-order):
            if series.iloc[i] == series.iloc[i-order:i+order+1].max():
                highs.append(i)
        return highs[-10:]

    def analyze(self, df: pd.DataFrame) -> dict:
        closes = df['Close']
        rsi = self._rsi(closes)
        macd, macd_signal, macd_hist = self._macd(closes)

        curr_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
        curr_macd = float(macd.iloc[-1]) if not pd.isna(macd.iloc[-1]) else 0
        curr_hist = float(macd_hist.iloc[-1]) if not pd.isna(macd_hist.iloc[-1]) else 0

        # Divergencia
        divergence = "NONE"
        div_strength = 0
        div_reason = "Sin divergencia clara"

        price_lows = self._find_lows(closes, order=5)
        rsi_lows = self._find_lows(rsi, order=5)
        price_highs = self._find_highs(closes, order=5)
        rsi_highs = self._find_highs(rsi, order=5)

        # Bullish divergence: precio hace LL, RSI hace HL
        if len(price_lows) >= 2 and len(rsi_lows) >= 2:
            # tomar los 2 últimos lows que estén cerca en tiempo
            pl1, pl2 = price_lows[-2], price_lows[-1]
            # buscar rsi lows cercanos a esos índices (+-3)
            rl1 = min(rsi_lows, key=lambda x: abs(x-pl1)) if rsi_lows else None
            rl2 = min(rsi_lows, key=lambda x: abs(x-pl2)) if rsi_lows else None
            if rl1 is not None and rl2 is not None and abs(pl1-rl1) <=5 and abs(pl2-rl2) <=5:
                price_ll = closes.iloc[pl2] < closes.iloc[pl1]
                rsi_hl = rsi.iloc[rl2] > rsi.iloc[rl1]
                if price_ll and rsi_hl and rsi.iloc[rl2] < 40:
                    divergence = "BULLISH"
                    div_strength = 20
                    div_reason = f"Bullish Div: Precio LL {closes.iloc[pl1]:.2f}->{closes.iloc[pl2]:.2f} pero RSI HL {rsi.iloc[rl1]:.1f}->{rsi.iloc[rl2]:.1f}"

        # Bearish divergence: precio HH, RSI LH
        if len(price_highs) >= 2 and len(rsi_highs) >= 2:
            ph1, ph2 = price_highs[-2], price_highs[-1]
            rh1 = min(rsi_highs, key=lambda x: abs(x-ph1)) if rsi_highs else None
            rh2 = min(rsi_highs, key=lambda x: abs(x-ph2)) if rsi_highs else None
            if rh1 is not None and rh2 is not None and abs(ph1-rh1) <=5 and abs(ph2-rh2) <=5:
                price_hh = closes.iloc[ph2] > closes.iloc[ph1]
                rsi_lh = rsi.iloc[rh2] < rsi.iloc[rh1]
                if price_hh and rsi_lh and rsi.iloc[rh2] > 60:
                    divergence = "BEARISH"
                    div_strength = -20
                    div_reason = f"Bearish Div: Precio HH {closes.iloc[ph1]:.2f}->{closes.iloc[ph2]:.2f} pero RSI LH {rsi.iloc[rh1]:.1f}->{rsi.iloc[rh2]:.1f}"

        # Estado momentum
        if curr_rsi > 70:
            mom_state = "OVERBOUGHT"
        elif curr_rsi < 30:
            mom_state = "OVERSOLD"
        elif curr_hist > 0 and curr_macd > 0:
            mom_state = "BULL_MOMENTUM"
        elif curr_hist < 0 and curr_macd < 0:
            mom_state = "BEAR_MOMENTUM"
        else:
            mom_state = "NEUTRAL"

        return {
            "rsi": float(curr_rsi),
            "macd": float(curr_macd),
            "macd_hist": float(curr_hist),
            "mom_state": mom_state,
            "divergence": divergence,
            "div_strength": div_strength,
            "div_reason": div_reason,
            "score_mod": div_strength,
            "rsi_series": rsi,  # para gráfico
            "macd_hist_series": macd_hist
        }
