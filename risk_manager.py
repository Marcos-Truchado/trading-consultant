"""
Risk Manager - Calcula Entry, Stop, TPs, RR para el analizador
No ejecuta, solo planifica

Los multiplicadores de ATR, el RR mínimo y los RR de fallback viven en
config.py (RiskConfig) -- puestos a mano, sin validar contra backtest.
"""
import pandas as pd
import numpy as np
from typing import Dict, List
from config import RISK, RiskConfig

class RiskManager:
    def __init__(self, cfg: RiskConfig = RISK):
        self.cfg = cfg
        self.atr_period = cfg.atr_period

    def _calc_atr(self, df: pd.DataFrame):
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(self.atr_period).mean().iloc[-1]

    def calculate(self, df: pd.DataFrame, active_wave: Dict, smc: Dict, fib_extensions: Dict, current_price: float) -> Dict:
        cfg = self.cfg
        # Entry = precio actual (para analizador)
        entry = current_price
        is_bull = active_wave.get('is_bullish')
        state = active_wave.get('state','UNKNOWN')

        # Stop = invalidación de Elliott
        stop = None
        stop_reason = ""
        if state == "FORMING_WAVE_3":
            w2_end = active_wave.get('w2_end')
            if w2_end:
                # Stop bajo W2 + buffer ATR
                atr = self._calc_atr(df)
                buffer = atr * cfg.atr_stop_buffer_mult if not pd.isna(atr) else current_price*0.01
                if is_bull:
                    stop = w2_end[1] - buffer
                    stop_reason = f"Bajo W2 {w2_end[1]:.2f} - buffer ATR {buffer:.2f}"
                else:
                    stop = w2_end[1] + buffer
                    stop_reason = f"Sobre W2 {w2_end[1]:.2f} + buffer"
        elif state == "FORMING_WAVE_5":
            w4_end = active_wave.get('w4_end')
            if w4_end:
                atr = self._calc_atr(df)
                buffer = atr * cfg.atr_stop_buffer_mult if not pd.isna(atr) else current_price*0.01
                if is_bull:
                    stop = w4_end[1] - buffer
                    stop_reason = f"Bajo W4 {w4_end[1]:.2f}"
                else:
                    stop = w4_end[1] + buffer
                    stop_reason = f"Sobre W4 {w4_end[1]:.2f}"
        else:
            # Fallback ATR stop
            atr = self._calc_atr(df)
            if not pd.isna(atr):
                stop = entry - atr*cfg.atr_fallback_stop_mult if is_bull else entry + atr*cfg.atr_fallback_stop_mult
                stop_reason = f"ATR {cfg.atr_fallback_stop_mult}x fallback ({atr:.2f})"
            else:
                stop = entry * (1 - cfg.pct_fallback_stop) if is_bull else entry * (1 + cfg.pct_fallback_stop)
                stop_reason = f"{cfg.pct_fallback_stop:.0%} fallback"

        # TPs desde Fib extensions
        tps = []
        if fib_extensions:
            # Ordenar por distancia
            sorted_ext = sorted(fib_extensions.items(), key=lambda x: abs(x[1]-entry))
            for ext, price in sorted_ext[:3]:
                tps.append({"level": f"Ext {ext*100:.0f}%", "price": float(price)})

        # Si no hay extensiones, usar RR
        if not tps and stop is not None:
            risk = abs(entry - stop)
            sign = 1 if is_bull else -1
            tps = [
                {"level": f"TP1 RR {cfg.tp1_rr}", "price": entry + sign*risk*cfg.tp1_rr},
                {"level": f"TP2 RR {cfg.tp2_rr}", "price": entry + sign*risk*cfg.tp2_rr},
            ]

        # Calcular RR
        rr1 = None
        rr2 = None
        if tps and stop:
            risk = abs(entry - stop)
            if risk > 0:
                rr1 = abs(tps[0]['price'] - entry) / risk if len(tps)>0 else None
                rr2 = abs(tps[1]['price'] - entry) / risk if len(tps)>1 else None

        # Validación: RR mínimo (config.RISK.min_valid_rr)
        valid = rr1 is not None and rr1 >= cfg.min_valid_rr

        return {
            "entry": float(entry),
            "stop": float(stop) if stop else None,
            "stop_reason": stop_reason,
            "tps": tps,
            "rr1": float(rr1) if rr1 else None,
            "rr2": float(rr2) if rr2 else None,
            "valid_rr": valid,
            "risk_pct": abs(entry-stop)/entry*100 if stop else None
        }
