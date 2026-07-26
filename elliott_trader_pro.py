"""
Elliott + Fibonacci + Medias Móviles - Trader Pro v3 PREDICTIVO
Autor: Senior Quant Dev
Cambio clave v3:
- Clasificador de onda EN CURSO (no histórica)
- fib_extensions anclado al tramo activo, no a waves[0]/waves[1] fijo
- Probabilidad/confianza + conteos alternativos
- Fix yfinance

Arquitectura:
- MarketDataProvider
- TechnicalIndicators
- ZigZagDetector
- ElliottWaveAnalyzer (histórico + activo)
- FibonacciCalculator
- ActiveWaveClassifier (NUEVO)
- ChartEngine
"""

import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from typing import List, Tuple, Dict, Optional
import argparse
import time
import random

# Sesión con impersonación de navegador para evitar el 429 de Yahoo.
# Requiere: pip install curl_cffi
# Si no está instalada, se cae a la sesión normal de yfinance (más propensa a rate limit).
try:
    from curl_cffi import requests as curl_requests
    _YF_SESSION = curl_requests.Session(impersonate="chrome")
except ImportError:
    _YF_SESSION = None

# ===================== DATA PROVIDER =====================
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

# ===================== INDICATORS =====================
class TechnicalIndicators:
    @staticmethod
    def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
        df['SMA_20'] = df['Close'].rolling(20).mean()
        df['SMA_50'] = df['Close'].rolling(50).mean()
        df['SMA_200'] = df['Close'].rolling(200).mean()
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
        df['EMA_55'] = df['Close'].ewm(span=55, adjust=False).mean()
        df['Golden_Cross'] = (df['SMA_50'] > df['SMA_200']) & (df['SMA_50'].shift(1) <= df['SMA_200'].shift(1))
        df['Death_Cross'] = (df['SMA_50'] < df['SMA_200']) & (df['SMA_50'].shift(1) >= df['SMA_200'].shift(1))
        return df

# ===================== ZIGZAG DETECTOR =====================
class ZigZagDetector:
    def __init__(self, deviation_pct: float = 5.0):
        self.deviation = deviation_pct / 100.0

    def get_pivots(self, df: pd.DataFrame) -> List[Tuple[int, float, str]]:
        closes = df['Close'].values
        pivots = []
        
        last_pivot_idx = 0
        last_pivot_price = closes[0]
        trend = 0

        for i in range(1, len(closes)):
            price = closes[i]
            change = (price - last_pivot_price) / last_pivot_price

            if trend == 0:
                if abs(change) >= self.deviation:
                    trend = 1 if change > 0 else -1
                    pivots.append((0, closes[0], 'L' if trend==1 else 'H'))
                    last_pivot_idx = i
                    last_pivot_price = price
            elif trend == 1:
                if price > last_pivot_price:
                    last_pivot_idx = i
                    last_pivot_price = price
                elif (last_pivot_price - price) / last_pivot_price >= self.deviation:
                    pivots.append((last_pivot_idx, last_pivot_price, 'H'))
                    trend = -1
                    last_pivot_idx = i
                    last_pivot_price = price
            else:
                if price < last_pivot_price:
                    last_pivot_idx = i
                    last_pivot_price = price
                elif (price - last_pivot_price) / last_pivot_price >= self.deviation:
                    pivots.append((last_pivot_idx, last_pivot_price, 'L'))
                    trend = 1
                    last_pivot_idx = i
                    last_pivot_price = price
        
        if len(pivots) > 0 and last_pivot_idx != pivots[-1][0]:
            pivots.append((last_pivot_idx, last_pivot_price, 'H' if trend==1 else 'L'))
        
        return pivots

# ===================== ELLIOTT ANALYZER (HISTÓRICO) =====================
class ElliottWaveAnalyzer:
    def analyze(self, pivots: List[Tuple[int, float, str]], df: pd.DataFrame) -> Dict:
        if len(pivots) < 6:
            return {"valid": False, "reason": "Pocos pivotes (<6) para formar 5 ondas", "waves": [], "pivots_used": []}

        recent = pivots[-12:]
        best_sequence = []
        best_score = -1
        best_report = {}

        for i in range(len(recent)-5):
            seq = recent[i:i+6]
            types = [p[2] for p in seq]
            if not self._is_alternating(types):
                continue
            score, report = self._score_impulse(seq)
            # Penalización por antigüedad: si termina muy atrás, baja score
            gap = (len(df)-1) - seq[-1][0]
            stale_penalty = max(0, gap - 20) * 0.1
            adjusted_score = score - stale_penalty
            if adjusted_score > best_score:
                best_score = adjusted_score
                best_sequence = seq
                best_report = report
                best_report['gap_velas'] = gap
                best_report['is_stale'] = gap > 20

        if best_score < 0:
            return {"valid": False, "reason": "No se encontró patrón alternante", "waves": [], "pivots_used": []}

        waves = []
        for j in range(5):
            start_idx, start_price, _ = best_sequence[j]
            end_idx, end_price, _ = best_sequence[j+1]
            waves.append({
                "num": j+1,
                "start_idx": start_idx,
                "end_idx": end_idx,
                "start_price": start_price,
                "end_price": end_price,
                "change_pct": (end_price-start_price)/start_price*100,
                "bars": end_idx - start_idx
            })
        
        return {
            "valid": best_score >= 2,
            "score": best_score,
            "validation": best_report,
            "waves": waves,
            "pivots_used": best_sequence,
            "gap": best_report.get('gap_velas', 0),
            "is_stale": best_report.get('is_stale', False)
        }

    def _is_alternating(self, types: List[str]) -> bool:
        return all(types[i] != types[i+1] for i in range(len(types)-1))

    def _score_impulse(self, seq: List[Tuple[int,float,str]]) -> Tuple[int, Dict]:
        p = [s[1] for s in seq]
        is_bull = p[0] < p[1]
        if not is_bull:
            p = [-x for x in p]

        w1 = p[1]-p[0]
        w2 = p[2]-p[1]
        w3 = p[3]-p[2]
        w4 = p[4]-p[3]
        w5 = p[5]-p[4]

        score = 0
        report = {}

        rule1 = p[2] > p[0]
        report["R1_Onda2_no_100%"] = rule1
        if rule1: score+=1

        rule2 = not (w3 < w1 and w3 < w5)
        report["R2_Onda3_no_mas_corta"] = rule2
        if rule2: score+=1

        rule3 = p[4] > p[1]
        report["R3_Onda4_no_solapa_Onda1"] = rule3
        if rule3: score+=1

        report["Onda3_extendida"] = w3 > w1*1.618
        report["Fib_Onda2"] = abs(w2)/w1 if w1!=0 else 0

        return score, report

# ===================== NUEVO: CLASIFICADOR DE ONDA EN CURSO =====================
class ActiveWaveClassifier:
    """
    Clasifica EN QUÉ ONDA estamos AHORA mirando los últimos 2-3 pivotes incluyendo el último.
    Resuelve el bug de anclar proyecciones a estructuras viejas.
    """
    
    def _find_correction_extreme(self, pivots: List[Tuple[int,float,str]], p1_pos: int):
        """
        A partir de la posición de p1 (fin de la onda de impulso), recorre los
        pivotes siguientes del lado contrario y devuelve el más extremo de todos.

        Esto es lo que faltaba: antes se asumía que la onda 2/4 era un único
        pivote en V (p2 = pivots[-1], sin más). Si la corrección es compleja
        (W-X-Y, varias piernas, como en tu ejemplo de ONDS), ese primer rebote
        es X, no el fin real de la corrección (Y) -- y todo lo que se ancla a
        ese punto (Fibonacci, target de onda 3) sale mal.

        Si en el camino aparece un pivote del MISMO lado que p1 que rompe ese
        nivel, la onda de impulso original queda invalidada (ya no hay techo/
        suelo válido de onda 1) y se descarta la hipótesis.
        """
        p1 = pivots[p1_pos]
        correction_side = 'L' if p1[2] == 'H' else 'H'
        same_side = p1[2]
        extreme = None
        correction_pivots = []
        for p in pivots[p1_pos+1:]:
            if p[2] == correction_side:
                correction_pivots.append(p)
                if extreme is None or (p[1] < extreme[1] if correction_side == 'L' else p[1] > extreme[1]):
                    extreme = p
            else:
                invalidated = (p[1] > p1[1]) if same_side == 'H' else (p[1] < p1[1])
                if invalidated:
                    return None, []
        return extreme, correction_pivots

    def classify(self, pivots: List[Tuple[int,float,str]], current_price: float, current_idx: int) -> Dict:
        if len(pivots) < 2:
            return self._unknown("Pocos pivotes")
        
        last_pivot = pivots[-1]
        gap = current_idx - last_pivot[0]
        hypotheses = []

        # Helper
        def is_alternating(seq):
            return all(seq[i][2] != seq[i+1][2] for i in range(len(seq)-1))

        # ---- HIPÓTESIS 1: FORMANDO ONDA 3 (onda 2 simple o compleja W-X-Y) ----
        # Se prueba cada posible "fin de onda 1" (p1) en la ventana reciente y,
        # para cada uno, se busca el extremo real de la corrección posterior
        # con _find_correction_extreme -- sea de 1 pivote (ABC en V) o de
        # varios (W-X-Y). Genera una hipótesis por candidato válido; luego se
        # ordenan por confianza como el resto del código ya hacía.
        window = pivots[-10:] if len(pivots) >= 10 else pivots
        offset = len(pivots) - len(window)
        for i in range(len(window)-1):
            p1_pos = offset + i
            if p1_pos == 0:
                continue
            p0 = pivots[p1_pos - 1]
            p1 = pivots[p1_pos]
            if p0[2] == p1[2]:
                continue

            is_bull = p0[2] == 'L' and p1[2] == 'H'
            is_bear = p0[2] == 'H' and p1[2] == 'L'
            if not (is_bull or is_bear):
                continue

            p2, correction_pivots = self._find_correction_extreme(pivots, p1_pos)
            if p2 is None:
                continue

            w1 = abs(p1[1] - p0[1])
            w2 = abs(p1[1] - p2[1])
            ratio = w2 / w1 if w1 != 0 else 0

            # Onda 2 no puede superar el 100% de la onda 1 (si no, invalida el conteo).
            # El rango se abre respecto a la versión anterior (era 0.35-0.85) porque
            # una W-X-Y compleja retrocede con más libertad que una simple onda en V.
            not_broken = (p2[1] > p0[1]) if is_bull else (p2[1] < p0[1])
            if not (0.236 <= ratio <= 1.0 and not_broken):
                continue

            gap_p2 = current_idx - p2[0]
            bounce = (current_price - p2[1])/p2[1]*100 if is_bull else (p2[1]-current_price)/p2[1]*100
            if bounce <= -2:
                continue  # el precio siguió rompiendo: esto ya no es la onda 2

            fib_score = 1 - abs(ratio-0.618)/0.618
            recency = max(0.2, 1 - gap_p2/60)
            is_complex = len(correction_pivots) > 1
            # Las correcciones complejas son más ambiguas de leer con solo zigzag,
            # así que arrancan con algo menos de confianza que una simple en V
            complexity_penalty = 0.1 if is_complex else 0
            conf = max(0.1, min(0.95, (0.5 + fib_score*0.5) * recency - complexity_penalty))

            label = "W-X-Y / corrección compleja" if is_complex else "onda 2 simple"
            hypotheses.append({
                "state": "FORMING_WAVE_3",
                "is_bullish": is_bull,
                "base_pivots": [p0, p1] + correction_pivots,
                "w1_start": p0,
                "w1_end": p1,
                "w2_end": p2,
                "correction_pivots": correction_pivots,
                "is_complex_correction": is_complex,
                "confidence": conf,
                "gap": gap_p2,
                "reason": f"1-2 confirmado ({label}, retra {ratio:.1%}), gap {gap_p2} velas, bounce {bounce:+.1f}%",
                "next_target": "Onda 3",
                "alternatives": []
            })

        # ---- HIPÓTESIS 2: FORMANDO ONDA 4 (tenemos 1-2-3) ----
        if len(pivots) >= 4:
            p0,p1,p2,p3 = pivots[-4], pivots[-3], pivots[-2], pivots[-1]
            if is_alternating([p0,p1,p2,p3]):
                is_bull = p0[2]=='L'
                if (is_bull and p3[1] > p1[1] and p2[1] > p0[1]) or (not is_bull and p3[1] < p1[1] and p2[1] < p0[1]):
                    w1 = abs(p1[1]-p0[1])
                    w3 = abs(p3[1]-p2[1])
                    if w3 > w1*0.8:  # Onda 3 no es la más corta
                        recency = max(0.2, 1 - gap/60)
                        conf = 0.65 * recency
                        hypotheses.append({
                            "state": "FORMING_WAVE_4",
                            "is_bullish": is_bull,
                            "base_pivots": [p0,p1,p2,p3],
                            "w3_start": p2,
                            "w3_end": p3,
                            "confidence": conf,
                            "gap": gap,
                            "reason": f"Onda 3 terminada ({w3:.2f} vs W1 {w1:.2f}), en corrección W4, gap {gap}",
                            "next_target": "Onda 4 (38-50% de W3)"
                        })

        # ---- HIPÓTESIS 3: FORMANDO ONDA 5 (tenemos 1-2-3-4) ----
        if len(pivots) >= 5:
            p0,p1,p2,p3,p4 = pivots[-5:]
            if is_alternating(pivots[-5:]):
                is_bull = p0[2]=='L'
                # Regla 3: Onda 4 no solapa Onda 1
                no_overlap = (p4[1] > p1[1]) if is_bull else (p4[1] < p1[1])
                w3 = abs(p3[1]-p2[1])
                w4 = abs(p3[1]-p4[1])
                ratio_w4 = w4/w3 if w3!=0 else 0
                if no_overlap and 0.15 <= ratio_w4 <= 0.65:
                    recency = max(0.2, 1 - gap/60)
                    conf = 0.7 * recency
                    hypotheses.append({
                        "state": "FORMING_WAVE_5",
                        "is_bullish": is_bull,
                        "base_pivots": [p0,p1,p2,p3,p4],
                        "w1_start": p0,
                        "w1_end": p1,
                        "w4_end": p4,
                        "confidence": conf,
                        "gap": gap,
                        "reason": f"1-4 completadas, W4 retra {ratio_w4:.1%} de W3, sin solape, gap {gap}",
                        "next_target": "Onda 5"
                    })

        # ---- HIPÓTESIS 4: IMPULSO COMPLETO -> CORRECTIVA A-B-C ----
        if len(pivots) >= 6:
            seq = pivots[-6:]
            if is_alternating(seq):
                # Score rápido
                p = [s[1] for s in seq]
                is_bull = p[0] < p[1]
                # Chequeo básico
                if is_bull:
                    valid = seq[2][1] > seq[0][1] and seq[5][1] > seq[3][1] and seq[4][1] > seq[1][1]
                else:
                    valid = seq[2][1] < seq[0][1] and seq[5][1] < seq[3][1] and seq[4][1] < seq[1][1]
                if valid:
                    recency = max(0.1, 1 - gap/40)  # si gap 22, recency 0.45 -> baja confianza, justo lo que querías
                    conf = 0.6 * recency
                    # Si gap >20, marcar como STALE
                    is_stale = gap > 20
                    hypotheses.append({
                        "state": "FORMING_WAVE_A" if not is_stale else "STALE_IMPULSE",
                        "is_bullish": is_bull,
                        "base_pivots": seq,
                        "impulse_start": seq[0],
                        "impulse_end": seq[5],
                        "confidence": conf,
                        "gap": gap,
                        "is_stale": is_stale,
                        "reason": f"Impulso 1-5 completo hace {gap} velas {'(STALE - viejo)' if is_stale else ''}, ahora en correctiva ABC",
                        "next_target": "Corrección A-B-C"
                    })

        # Si no hay patrón activo claro, verificar si hay un impulso histórico STALE (bug original)
        if not hypotheses or max(h['confidence'] for h in hypotheses) < 0.4:
            # Buscar impulso completo que terminó hace >20 velas (tu caso gap 22)
            if len(pivots) >= 6:
                for i in range(len(pivots)-6, -1, -1):
                    seq = pivots[i:i+6]
                    if not all(seq[j][2] != seq[j+1][2] for j in range(5)):
                        continue
                    # Validación rápida impulso
                    is_bull = seq[0][2] == 'L'
                    if is_bull:
                        valid = seq[2][1] > seq[0][1] and seq[4][1] > seq[1][1]
                    else:
                        valid = seq[2][1] < seq[0][1] and seq[4][1] < seq[1][1]
                    if valid:
                        gap_hist = current_idx - seq[-1][0]
                        if gap_hist > 15:
                            return {
                                "state": "STALE_IMPULSE",
                                "is_bullish": is_bull,
                                "base_pivots": seq,
                                "impulse_start": seq[0],
                                "impulse_end": seq[-1],
                                "confidence": max(0.1, 0.6 * (1 - gap_hist/80)),
                                "gap": gap_hist,
                                "is_stale": True,
                                "reason": f"Impulso 1-5 completo hace {gap_hist} velas (STALE - tu bug). Proyección vieja anclada a {seq[0][1]:.0f}->{seq[-1][1]:.0f} irrelevante ahora. Precio actual formó nuevo mínimo no relacionado",
                                "alternatives": hypotheses[:2],
                                "next_target": "Esperar nuevo 1-2"
                            }

        if not hypotheses:
            return self._unknown(f"No hay patrón activo claro, gap {gap}")

        # Ordenar por confianza
        hypotheses.sort(key=lambda x: x['confidence'], reverse=True)
        best = hypotheses[0]
        best['alternatives'] = hypotheses[1:3]  # top 2 alternativas para transparencia
        best['current_price'] = current_price
        best['last_pivot'] = last_pivot
        return best

    def _unknown(self, reason):
        return {
            "state": "UNKNOWN",
            "is_bullish": None,
            "base_pivots": [],
            "confidence": 0.15,
            "gap": 0,
            "reason": reason,
            "alternatives": [],
            "next_target": "Esperar confirmación"
        }

# ===================== FIBONACCI =====================
class FibonacciCalculator:
    LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    EXTENSIONS = [1.0, 1.272, 1.618, 2.0, 2.618]

    @staticmethod
    def get_retracements(wave_end: float, wave_start: float) -> Dict[float, float]:
        """
        0% = wave_end (el extremo recién alcanzado, sin retroceso todavía)
        100% = wave_start (retroceso completo hasta el origen de la onda)
        Funciona igual para ondas alcistas y bajistas: el signo de la resta
        ya captura la dirección, no hace falta un parámetro 'trend' aparte
        (ese parámetro era la causa de que los niveles salieran invertidos
        en ondas bajistas, porque los call-sites pasaban high/low según el
        precio y no según trend, y la rama 'down' asumía lo contrario).
        """
        diff = wave_end - wave_start
        return {level: wave_end - diff*level for level in FibonacciCalculator.LEVELS}

    @staticmethod
    def get_extensions(wave1_start, wave1_end, wave2_end) -> Dict[float, float]:
        w1_size = abs(wave1_end - wave1_start)
        if wave1_end > wave1_start:
            return {ext: wave2_end + w1_size*ext for ext in FibonacciCalculator.EXTENSIONS}
        else:
            return {ext: wave2_end - w1_size*ext for ext in FibonacciCalculator.EXTENSIONS}

# ===================== CHART ENGINE =====================
class ChartEngine:
    @staticmethod
    def plot(df: pd.DataFrame, ticker: str, elliott_result: Dict, fib_levels: Dict, fib_extensions: Dict = None, active_wave: Dict = None):
        fig = go.Figure()

        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'], name="Precio",
            increasing_line_color='#26a69a', decreasing_line_color='#ef5350'
        ))

        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name="SMA 20", line=dict(color='orange', width=1)))
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], name="SMA 50", line=dict(color='blue', width=1.2)))
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_200'], name="SMA 200", line=dict(color='purple', width=1.5, dash='dash')))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_21'], name="EMA 21", line=dict(color='cyan', width=1)))

        # Ondas históricas (gris tenue)
        if elliott_result.get("waves"):
            for w in elliott_result["waves"]:
                start_date = df.index[w["start_idx"]]
                end_date = df.index[w["end_idx"]]
                color = 'rgba(255,255,255,0.2)' if elliott_result.get('is_stale') else 'white'
                fig.add_trace(go.Scatter(
                    x=[start_date, end_date],
                    y=[w["start_price"], w["end_price"]],
                    mode="lines+markers+text",
                    name=f"Onda hist {w['num']}",
                    text=[f"{w['num']-1 if w['num']>1 else 0}", f"{w['num']}"],
                    textposition="top center",
                    line=dict(width=2, color=color, dash='dot'),
                    marker=dict(size=6),
                    showlegend=False
                ))

        # Onda activa (resaltada)
        if active_wave and active_wave.get('base_pivots'):
            bps = active_wave['base_pivots']
            # Si la onda 2/4 es una corrección compleja (W-X-Y), esas piernas
            # se dibujan aparte en naranja para distinguirlas del impulso 1-2
            corr_pivots = active_wave.get('correction_pivots') or []
            n_impulse_legs = len(bps) - len(corr_pivots)
            for i in range(len(bps)-1):
                s_idx, s_price, _ = bps[i]
                e_idx, e_price, _ = bps[i+1]
                is_correction_leg = i >= n_impulse_legs - 1
                if is_correction_leg and corr_pivots:
                    labels = ['W','X','Y','X2','Z']
                    li = i - (n_impulse_legs - 1)
                    label = labels[li] if li < len(labels) else str(li)
                    fig.add_trace(go.Scatter(
                        x=[df.index[s_idx], df.index[e_idx]],
                        y=[s_price, e_price],
                        mode="lines+markers+text",
                        name=f"Corrección ({label})",
                        text=["", f"({label})"],
                        textposition="bottom center",
                        line=dict(width=2, color='orange', dash='dot'),
                        marker=dict(size=7, color='orange'),
                        showlegend=False
                    ))
                else:
                    fig.add_trace(go.Scatter(
                        x=[df.index[s_idx], df.index[e_idx]],
                        y=[s_price, e_price],
                        mode="lines+markers",
                        name=f"Base activa {i+1}",
                        line=dict(width=4, color='#00FF88'),
                        marker=dict(size=10, color='#00FF88')
                    ))
            # Línea punteada hacia precio actual (proyección en curso)
            if len(bps) > 0:
                last_bp = bps[-1]
                fig.add_trace(go.Scatter(
                    x=[df.index[last_bp[0]], df.index[-1]],
                    y=[last_bp[1], active_wave.get('current_price', last_bp[1])],
                    mode="lines",
                    name=f"Tramo en curso -> {active_wave['state']}",
                    line=dict(width=3, color='#FFD700', dash='dash'),
                ))

        if fib_levels:
            for level, price in fib_levels.items():
                fig.add_hline(y=price, line_dash="dot", line_color="gray",
                              annotation_text=f"Fib Ret {level*100:.1f}%: {price:.2f}",
                              annotation_position="right")

        if fib_extensions:
            for ext, price in fib_extensions.items():
                fig.add_hline(y=price, line_dash="dash", line_color="#FFD700",
                              annotation_text=f"Ext {ext*100:.0f}%: {price:.2f} (Conf {active_wave.get('confidence',0):.0%})",
                              annotation_position="left")

        title = f"{ticker} - {active_wave.get('state','UNKNOWN')} | Conf: {active_wave.get('confidence',0):.0%} | Gap: {active_wave.get('gap',0)} velas"
        if elliott_result.get('is_stale'):
            title += " | HISTÓRICO STALE"

        fig.update_layout(
            title=title,
            xaxis_rangeslider_visible=False,
            template="plotly_dark",
            height=850,
            legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center"),
            yaxis_title="Precio $"
        )
        return fig

# ===================== MAIN ENGINE v3 PREDICTIVO =====================
class ElliottFibonacciStrategy:
    def __init__(self, deviation_pct=5.0):
        self.provider = MarketDataProvider()
        self.zigzag = ZigZagDetector(deviation_pct=deviation_pct)
        self.elliott = ElliottWaveAnalyzer()
        self.active_classifier = ActiveWaveClassifier()
        self.fib = FibonacciCalculator()

    def run(self, ticker: str, period="2y", deviation=5.0):
        self.provider.load_universe()
        if not self.provider.validate_ticker(ticker.upper()):
            print(f"Advertencia: {ticker} no está en S&P500/NASDAQ100, pero se analizará igual.")

        df = self.provider.get_data(ticker, period)
        return self.analyze_dataframe(df, ticker, deviation)

    def analyze_dataframe(self, df: pd.DataFrame, ticker: str, deviation: float = 5.0):
        """
        Igual que run(), pero recibe el DataFrame ya construido (columnas
        Open/High/Low/Close/Volume, index de fechas) en vez de descargarlo con
        yfinance. Así el mismo motor de Elliott/Fibonacci sirve tanto para
        datos de Yahoo como para históricos traídos de IBKR u otra fuente.
        """
        self.zigzag.deviation = deviation/100.0
        df = TechnicalIndicators.add_moving_averages(df)

        pivots = self.zigzag.get_pivots(df)
        print(f"[ZIGZAG] {len(pivots)} pivotes encontrados con {deviation}% desviación")

        elliott_result = self.elliott.analyze(pivots, df)
        if elliott_result.get('is_stale'):
            print(f"[WARNING] Mejor patrón histórico STALE - terminó hace {elliott_result.get('gap')} velas, no relevante")

        current_price = float(df['Close'].iloc[-1])
        current_idx = len(df)-1
        sma20 = float(df['SMA_20'].iloc[-1]) if not pd.isna(df['SMA_20'].iloc[-1]) else current_price
        sma200 = float(df['SMA_200'].iloc[-1]) if not pd.isna(df['SMA_200'].iloc[-1]) else current_price

        # ===== NUEVO: CLASIFICADOR DE ONDA EN CURSO =====
        active_wave = self.active_classifier.classify(pivots, current_price, current_idx)
        print(f"[ACTIVE] {active_wave['state']} | Conf {active_wave['confidence']:.0%} | {active_wave['reason']}")

        # ===== FIB ANCLADO AL TRAMO ACTIVO (FIX DEL BUG) =====
        fib_levels = {}
        fib_extensions = {}

        state = active_wave['state']
        is_bull = active_wave.get('is_bullish')

        if state == "FORMING_WAVE_3":
            # Proyecta onda 3 desde onda 1 + fin onda 2 RECIENTE
            w1_start = active_wave['w1_start'][1]
            w1_end = active_wave['w1_end'][1]
            w2_end = active_wave['w2_end'][1]
            fib_extensions = self.fib.get_extensions(w1_start, w1_end, w2_end)
            # Retrocesos de onda 1 para contexto
            fib_levels = self.fib.get_retracements(w1_end, w1_start)

        elif state == "FORMING_WAVE_4":
            # Onda 4 = retroceso de onda 3
            w3_start = active_wave['w3_start'][1]
            w3_end = active_wave['w3_end'][1]
            fib_levels = self.fib.get_retracements(w3_end, w3_start)
            # Objetivo típico W4: 38.2-50% de W3

        elif state == "FORMING_WAVE_5":
            # Onda 5 desde onda 1 + fin onda 4 RECIENTE
            w1_start = active_wave['w1_start'][1]
            w1_end = active_wave['w1_end'][1]
            w4_end = active_wave['w4_end'][1]
            fib_extensions = self.fib.get_extensions(w1_start, w1_end, w4_end)

        elif state in ("FORMING_WAVE_A", "STALE_IMPULSE"):
            # Corrección ABC = retroceso de todo el impulso
            imp_start = active_wave['impulse_start'][1]
            imp_end = active_wave['impulse_end'][1]
            fib_levels = self.fib.get_retracements(imp_end, imp_start)
            # Onda C a veces = 1.0 * onda A
            fib_extensions = {}

        # Señal basada en tramo activo, no en num fijo
        signal, signal_detail = self._generate_signal(active_wave, current_price, sma20, fib_levels)

        summary = {
            "ticker": ticker.upper(),
            "precio_actual": round(current_price,2),
            "tendencia_MA": "Alcista" if sma20 > sma200 else "Bajista",
            "elliott_historico": elliott_result,
            "active_wave": active_wave,  # NUEVO: onda en curso con confianza
            "fib_levels": fib_levels,
            "fib_extensions": fib_extensions,
            "last_pivot": {"price": pivots[-1][1], "type": pivots[-1][2], "gap": active_wave.get('gap',0)} if pivots else {},
            "señal": signal,
            "señal_detalle": signal_detail,
            # Mantener compatibilidad con UI vieja
            "elliott": elliott_result,
        }

        fig = ChartEngine.plot(df, ticker, elliott_result, fib_levels, fib_extensions, active_wave)
        return df, summary, fig

    def _generate_signal(self, active_wave, current_price, sma20, fib_levels):
        state = active_wave['state']
        conf = active_wave['confidence']
        last_pivot = active_wave.get('last_pivot')
        gap = active_wave.get('gap',0)
        is_bull = active_wave.get('is_bullish')
        accion = "COMPRA" if is_bull else "VENTA"

        if state == "FORMING_WAVE_3" and conf > 0.5:
            ruptura = current_price > active_wave['w2_end'][1] * 1.01 and current_price > sma20 if is_bull \
                else current_price < active_wave['w2_end'][1] * 0.99 and current_price < sma20
            if ruptura:
                return f"{accion} - Formando Onda 3 (alta prob)", f"Conf {conf:.0%}, {active_wave['reason']}. Objetivo Ext 1.618"
            else:
                return f"{accion} TEMPRANA - Onda 3 en preparación", f"Conf {conf:.0%}, esperando ruptura de W2"

        elif state == "FORMING_WAVE_5" and conf > 0.5:
            return f"{accion} - Formando Onda 5 (último impulso)", f"Conf {conf:.0%}, {active_wave['reason']}"

        elif state == "FORMING_WAVE_4":
            objetivo = "compra" if is_bull else "venta/corto"
            return "ESPERAR - En corrección Onda 4", f"Buscar {objetivo} en Fib 38-50% de W3. Conf {conf:.0%}"

        elif state in ("FORMING_WAVE_A", "STALE_IMPULSE"):
            if active_wave.get('is_stale'):
                return f"NEUTRAL - Patrón viejo (gap {gap} velas)", f"El impulso 1-5 terminó hace {gap} velas, proyección vieja irrelevante. Conf baja {conf:.0%}. Alternativas: {len(active_wave.get('alternatives',[]))}"
            else:
                return "VENTA / PRECAUCIÓN - En correctiva ABC", f"Impulso completo, ahora corrigiendo. Fib 50-61.8% como soporte"

        elif state == "UNKNOWN":
            return "NEUTRAL - Sin patrón activo claro", active_wave['reason']

        return "NEUTRAL", active_wave['reason']


# ===================== CLI =====================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Elliott + Fibonacci + MAs PREDICTIVO v3")
    parser.add_argument("--ticker", type=str, default="AAPL", help="Ticker ej: AAPL, NVDA, MSFT")
    parser.add_argument("--period", type=str, default="2y", help="1y, 2y, 5y, max")
    parser.add_argument("--deviation", type=float, default=5.0, help="% ZigZag")
    parser.add_argument("--show", action="store_true", help="Abrir gráfico")

    args = parser.parse_args()

    engine = ElliottFibonacciStrategy(deviation_pct=args.deviation)
    df, summary, fig = engine.run(args.ticker, period=args.period, deviation=args.deviation)

    print("\n" + "="*70)
    print(f" RESUMEN PREDICTIVO {summary['ticker']} - v3")
    print("="*70)
    aw = summary['active_wave']
    print(f"Precio: ${summary['precio_actual']} | MA: {summary['tendencia_MA']}")
    print(f"ONDA EN CURSO: {aw['state']} | Confianza: {aw['confidence']:.0%} | Gap: {aw.get('gap',0)} velas")
    print(f"Razón: {aw['reason']}")
    print(f"Alcista: {aw.get('is_bullish')} | Target: {aw.get('next_target')}")
    if aw.get('alternatives'):
        print("\nConteos alternativos (transparencia Elliott):")
        for alt in aw['alternatives']:
            print(f" - {alt['state']} Conf {alt['confidence']:.0%}: {alt['reason']}")
    print(f"\nSeñal: {summary['señal']}")
    print(f"Detalle: {summary['señal_detalle']}")
    print("\nHistórico:")
    print(f" Mejor impulso histórico gap: {summary['elliott_historico'].get('gap')} velas | Stale: {summary['elliott_historico'].get('is_stale')}")
    print("\nFib Retrocesos (anclado a tramo ACTIVO):")
    for lvl, price in summary['fib_levels'].items():
        print(f" {lvl*100:5.1f}% -> ${price:.2f}")
    print("\nFib Extensiones (anclado a tramo ACTIVO):")
    for ext, price in summary.get('fib_extensions', {}).items():
        print(f" {ext*100:.0f}% -> ${price:.2f}")

    if args.show:
        fig.show()
    else:
        fig.write_html(f"{args.ticker}_elliott_v3.html")
        print(f"\nGráfico guardado en {args.ticker}_elliott_v3.html")
