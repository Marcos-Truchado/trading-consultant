"""
Regime Detector - Filtro ON/OFF para Elliott
Determina si el mercado está en tendencia, rango o alta volatilidad.

Umbrales (ADX 25, Chop 55/61.8, percentil ATR 85, puntos por régimen) en
config.py (RegimeConfig) -- sin validar contra backtest todavía.
"""
import pandas as pd
import numpy as np
from config import REGIME, RegimeConfig

class RegimeDetector:
    def __init__(self, adx_period=14, atr_period=14, chop_period=14, cfg: RegimeConfig = REGIME):
        self.adx_period = adx_period
        self.atr_period = atr_period
        self.chop_period = chop_period
        self.cfg = cfg

    def _calc_atr(self, df: pd.DataFrame):
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(self.atr_period).mean()
        return atr, tr

    def _calc_adx(self, df: pd.DataFrame):
        # Wilder's ADX simplified
        df_temp = df.copy()
        df_temp['H-pH'] = df_temp['High'] - df_temp['High'].shift(1)
        df_temp['pL-L'] = df_temp['Low'].shift(1) - df_temp['Low']
        df_temp['+DM'] = np.where((df_temp['H-pH'] > df_temp['pL-L']) & (df_temp['H-pH'] > 0), df_temp['H-pH'], 0)
        df_temp['-DM'] = np.where((df_temp['pL-L'] > df_temp['H-pH']) & (df_temp['pL-L'] > 0), df_temp['pL-L'], 0)
        
        atr, tr = self._calc_atr(df_temp)
        tr_s = tr.rolling(self.adx_period).mean()
        
        plus_di = 100 * (df_temp['+DM'].rolling(self.adx_period).mean() / tr_s)
        minus_di = 100 * (df_temp['-DM'].rolling(self.adx_period).mean() / tr_s)
        
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, 1)
        adx = dx.rolling(self.adx_period).mean()
        return adx, plus_di, minus_di

    def _calc_choppiness(self, df: pd.DataFrame):
        atr, _ = self._calc_atr(df)
        high = df['High'].rolling(self.chop_period).max()
        low = df['Low'].rolling(self.chop_period).min()
        atr_sum = atr.rolling(self.chop_period).sum()
        chop = 100 * np.log10(atr_sum / (high - low).replace(0, 1)) / np.log10(self.chop_period)
        return chop

    def analyze(self, df: pd.DataFrame) -> dict:
        cfg = self.cfg
        if len(df) < cfg.min_bars:
            return {"regime": "UNKNOWN", "reason": "Pocos datos", "tradeable": False, "score_mod": 0}

        adx, plus_di, minus_di = self._calc_adx(df)
        chop = self._calc_choppiness(df)
        atr, _ = self._calc_atr(df)

        curr_adx = adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 20
        curr_chop = chop.iloc[-1] if not pd.isna(chop.iloc[-1]) else 50
        curr_atr = atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 0
        curr_plus = plus_di.iloc[-1] if not pd.isna(plus_di.iloc[-1]) else 0
        curr_minus = minus_di.iloc[-1] if not pd.isna(minus_di.iloc[-1]) else 0

        # ATR percentil últimos 200 días
        atr_percentile = (atr.tail(200) < curr_atr).mean() * 100 if len(atr) >= 200 else 50

        # Lógica de régimen
        if curr_adx > cfg.adx_trending and curr_chop < cfg.chop_trending_max:
            regime = "TRENDING"
            tradeable = True
            reason = f"Tendencia fuerte ADX {curr_adx:.1f}, Chop {curr_chop:.1f}"
            score_mod = cfg.score_trending
            trend_dir = "BULL" if curr_plus > curr_minus else "BEAR"
        elif curr_chop > cfg.chop_ranging_min:
            regime = "RANGING"
            tradeable = False
            reason = f"Lateral - Chop {curr_chop:.1f} > {cfg.chop_ranging_min}, ADX {curr_adx:.1f}"
            score_mod = cfg.score_ranging
            trend_dir = "NEUTRAL"
        elif atr_percentile > cfg.atr_percentile_high_vol:
            regime = "HIGH_VOL"
            tradeable = True
            reason = f"Alta volatilidad ATR perc {atr_percentile:.0f}%, peligro en Onda 5"
            score_mod = cfg.score_high_vol
            trend_dir = "BULL" if curr_plus > curr_minus else "BEAR"
        else:
            regime = "TRANSITION"
            tradeable = True
            reason = f"Transición ADX {curr_adx:.1f} Chop {curr_chop:.1f}"
            score_mod = cfg.score_transition
            trend_dir = "BULL" if curr_plus > curr_minus else "BEAR"

        return {
            "regime": regime,
            "adx": float(curr_adx),
            "choppiness": float(curr_chop),
            "atr": float(curr_atr),
            "atr_percentile": float(atr_percentile),
            "plus_di": float(curr_plus),
            "minus_di": float(curr_minus),
            "trend_dir": trend_dir,
            "tradeable": tradeable,
            "score_mod": score_mod,
            "reason": reason
        }
