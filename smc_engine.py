"""
SMC Engine - Smart Money Concepts
BOS, CHOCH, Order Blocks, Fair Value Gaps, Liquidity Sweeps
Todo visual para el cockpit

Umbrales de score y lookbacks en config.py (SMCConfig) -- sin validar
contra backtest todavía.
"""
import pandas as pd
import numpy as np
from typing import List, Tuple, Dict
from config import SMC, SMCConfig

class SMCEngine:
    def __init__(self, cfg: SMCConfig = SMC):
        self.cfg = cfg

    def _get_pivot_highs_lows(self, df: pd.DataFrame, order=5):
        highs = []
        lows = []
        for i in range(order, len(df)-order):
            if df['High'].iloc[i] == df['High'].iloc[i-order:i+order+1].max():
                highs.append((i, float(df['High'].iloc[i]), df.index[i]))
            if df['Low'].iloc[i] == df['Low'].iloc[i-order:i+order+1].min():
                lows.append((i, float(df['Low'].iloc[i]), df.index[i]))
        return highs, lows

    def find_bos_choch(self, df: pd.DataFrame, pivots: List[Tuple[int,float,str]]):
        # Usa pivotes ZigZag para estructura
        if len(pivots) < 4:
            return {"bos": [], "choch": [], "trend": "UNKNOWN", "score_mod": 0, "reason": "Pocos pivotes"}

        # Determinar tendencia por últimos pivotes
        # Si H más altos y L más altos => BULL
        last_highs = [p for p in pivots if p[2]=='H'][-2:]
        last_lows = [p for p in pivots if p[2]=='L'][-2:]

        bos_events = []
        choch_events = []
        trend = "UNKNOWN"

        if len(last_highs)==2 and len(last_lows)==2:
            hh = last_highs[-1][1] > last_highs[-2][1]
            hl = last_lows[-1][1] > last_lows[-2][1]
            ll = last_lows[-1][1] < last_lows[-2][1]
            lh = last_highs[-1][1] < last_highs[-2][1]

            if hh and hl:
                trend = "BULL"
                bos_events.append({"type": "BOS_BULL", "price": last_highs[-1][1], "idx": last_highs[-1][0], "reason": f"BOS alcista rompe {last_highs[-2][1]:.2f}"})
            elif ll and lh:
                trend = "BEAR"
                bos_events.append({"type": "BOS_BEAR", "price": last_lows[-1][1], "idx": last_lows[-1][0], "reason": f"BOS bajista rompe {last_lows[-2][1]:.2f}"})
            elif (hh and ll) or (lh and hl):
                trend = "CHOCH"
                choch_events.append({"type": "CHOCH", "price": last_highs[-1][1] if hh else last_lows[-1][1], "idx": pivots[-1][0], "reason": "Cambio de carácter - posible reversal"})

        # Score
        # Nota: BULL y BEAR puntúan igual porque el ajuste real de dirección
        # (si este trend SMC alinea con Elliott o no) lo hace scoring_engine
        # comparando contra is_bullish; aquí solo se puntúa "hay estructura
        # clara" vs "no la hay".
        score_mod = 0
        if trend == "BULL":
            score_mod = self.cfg.score_bos_bull
        elif trend == "BEAR":
            score_mod = self.cfg.score_bos_bear
        elif trend == "CHOCH":
            score_mod = self.cfg.score_choch

        return {"bos": bos_events, "choch": choch_events, "trend": trend, "score_mod": score_mod, "reason": f"SMC Trend {trend}"}

    def find_fvg(self, df: pd.DataFrame, lookback=None) -> List[Dict]:
        fvgs = []
        df_slice = df.tail(lookback or self.cfg.fvg_lookback)
        for i in range(1, len(df_slice)-1):
            idx = df_slice.index[i]
            prev_high = df_slice['High'].iloc[i-1]
            prev_low = df_slice['Low'].iloc[i-1]
            curr_high = df_slice['High'].iloc[i]
            curr_low = df_slice['Low'].iloc[i]
            next_high = df_slice['High'].iloc[i+1]
            next_low = df_slice['Low'].iloc[i+1]

            # Bullish FVG: low de vela 3 > high de vela 1
            if next_low > prev_high:
                fvgs.append({
                    "type": "BULL_FVG",
                    "top": float(next_low),
                    "bottom": float(prev_high),
                    "mid": float((next_low + prev_high)/2),
                    "idx": i,
                    "date": str(df_slice.index[i+1]),
                    "mitigated": False
                })
            # Bearish FVG: high de vela 3 < low de vela 1
            if next_high < prev_low:
                fvgs.append({
                    "type": "BEAR_FVG",
                    "top": float(prev_low),
                    "bottom": float(next_high),
                    "mid": float((prev_low + next_high)/2),
                    "idx": i,
                    "date": str(df_slice.index[i+1]),
                    "mitigated": False
                })
        # Solo no mitigados recientes (precio no ha vuelto a entrar)
        recent = []
        last_close = float(df['Close'].iloc[-1])
        for f in fvgs[-6:]:
            if f['type']=="BULL_FVG" and last_close > f['top']:
                f['mitigated']=True
            if f['type']=="BEAR_FVG" and last_close < f['bottom']:
                f['mitigated']=True
            if not f['mitigated']:
                recent.append(f)
        return recent[-4:]

    def find_order_blocks(self, df: pd.DataFrame, lookback=None) -> List[Dict]:
        obs = []
        df_s = df.tail(lookback or self.cfg.ob_lookback)
        min_move = self.cfg.ob_min_move_pct
        for i in range(2, len(df_s)-2):
            # OB alcista: última vela bajista antes de movimiento alcista fuerte
            # simplificado: vela bajista con mecha baja + siguiente vela cierra > 1% arriba
            curr = df_s.iloc[i]
            next_c = df_s.iloc[i+1]
            # Bull OB
            if curr['Close'] < curr['Open'] and next_c['Close'] > curr['High'] * 1.005:
                move = (df_s['Close'].iloc[i+2:i+5].max() - curr['Low']) / curr['Low'] * 100 if i+5 < len(df_s) else 0
                if move > min_move:
                    obs.append({
                        "type": "BULL_OB",
                        "high": float(curr['High']),
                        "low": float(curr['Low']),
                        "date": str(df_s.index[i]),
                        "strength": move
                    })
            # Bear OB
            if curr['Close'] > curr['Open'] and next_c['Close'] < curr['Low'] * 0.995:
                move = (curr['High'] - df_s['Close'].iloc[i+2:i+5].min()) / curr['High'] * 100 if i+5 < len(df_s) else 0
                if move > min_move:
                    obs.append({
                        "type": "BEAR_OB",
                        "high": float(curr['High']),
                        "low": float(curr['Low']),
                        "date": str(df_s.index[i]),
                        "strength": move
                    })
        return obs[-4:]

    def find_liquidity_sweep(self, df: pd.DataFrame) -> Dict:
        # Barrido de liquidez: wick que supera high/low reciente y cierra dentro
        if len(df) < 20:
            return {"sweep": False, "type": "NONE", "reason": ""}
        recent_high = df['High'].tail(20).max()
        recent_low = df['Low'].tail(20).min()
        last = df.iloc[-1]
        prev = df.iloc[-2]

        # Bearish sweep = barre high y cierra abajo
        if prev['High'] > recent_high * 0.999 and last['Close'] < recent_high and last['High'] > recent_high:
            return {"sweep": True, "type": "BEAR_SWEEP", "price": float(recent_high), "reason": f"Barrido de liquidez alcista en {recent_high:.2f} - posible techo onda 5", "score_mod": self.cfg.score_sweep_bear}
        if prev['Low'] < recent_low * 1.001 and last['Close'] > recent_low and last['Low'] < recent_low:
            return {"sweep": True, "type": "BULL_SWEEP", "price": float(recent_low), "reason": f"Barrido de liquidez bajista en {recent_low:.2f} - posible suelo", "score_mod": self.cfg.score_sweep_bull}
        return {"sweep": False, "type": "NONE", "reason": "Sin barridos recientes", "score_mod": 0}

    def analyze(self, df: pd.DataFrame, pivots: List[Tuple[int,float,str]]) -> dict:
        bos_data = self.find_bos_choch(df, pivots)
        fvgs = self.find_fvg(df)
        obs = self.find_order_blocks(df)
        sweep = self.find_liquidity_sweep(df)

        # Confluencia OB + FVG + Fib (se calcula en scoring)
        total_score = bos_data['score_mod'] + sweep['score_mod']
        # Bonus si hay OB sin mitigar cerca de precio actual
        curr_price = float(df['Close'].iloc[-1])
        for ob in obs:
            dist = abs(ob['low'] - curr_price) / curr_price * 100 if ob['type']=='BULL_OB' else abs(ob['high'] - curr_price) / curr_price * 100
            if dist < self.cfg.ob_proximity_pct:
                total_score += self.cfg.score_ob_confluence

        return {
            "bos_choch": bos_data,
            "fvg": fvgs,
            "order_blocks": obs,
            "liquidity_sweep": sweep,
            "trend_smc": bos_data['trend'],
            "score_mod": total_score,
            "reason": f"{bos_data['reason']} | {len(fvgs)} FVGs activos | {len(obs)} OBs | Sweep: {sweep['type']}"
        }
