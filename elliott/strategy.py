"""
ElliottFibonacciStrategy: orquesta data provider, zigzag, indicadores,
clasificador de onda activa y Fibonacci sobre un ticker o un DataFrame ya
descargado (IBKR, yfinance, o cualquier otra fuente OHLCV).

Nota de diseño: este motor YA NO genera gráficos. Antes tenía un ChartEngine
propio, desactualizado y duplicado de chart_engine_v4.ChartEngineV4 (sin SMC,
Volume Profile ni Risk). Graficar es responsabilidad de la capa de
presentación (pipeline.py / dashboard), no del motor de análisis.
"""
from typing import Dict
import pandas as pd

from .data_provider import MarketDataProvider
from .indicators import TechnicalIndicators
from .zigzag import ZigZagDetector
from .historical import ElliottWaveAnalyzer
from .active_classifier import ActiveWaveClassifier
from .fibonacci import FibonacciCalculator


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

        Devuelve (df, summary, None) -- el tercer valor se mantiene por
        compatibilidad con el código que hace `df, summary, _ = engine.run(...)`.
        """
        self.zigzag.deviation = deviation / 100.0
        df = TechnicalIndicators.add_moving_averages(df)

        pivots = self.zigzag.get_pivots(df)
        print(f"[ZIGZAG] {len(pivots)} pivotes encontrados con {deviation}% desviación")

        elliott_result = self.elliott.analyze(pivots, df)
        if elliott_result.get('is_stale'):
            print(f"[WARNING] Mejor patrón histórico STALE - terminó hace {elliott_result.get('gap')} velas, no relevante")

        current_price = float(df['Close'].iloc[-1])
        current_idx = len(df) - 1
        sma20 = float(df['SMA_20'].iloc[-1]) if not pd.isna(df['SMA_20'].iloc[-1]) else current_price
        sma200 = float(df['SMA_200'].iloc[-1]) if not pd.isna(df['SMA_200'].iloc[-1]) else current_price

        # ===== CLASIFICADOR DE ONDA EN CURSO =====
        active_wave = self.active_classifier.classify(pivots, current_price, current_idx)
        print(f"[ACTIVE] {active_wave['state']} | Conf {active_wave['confidence']:.0%} | {active_wave['reason']}")

        # ===== FIB ANCLADO AL TRAMO ACTIVO =====
        fib_levels = {}
        fib_extensions = {}

        state = active_wave['state']

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
            fib_extensions = {}

        # Señal basada en tramo activo, no en num fijo
        signal, signal_detail = self._generate_signal(active_wave, current_price, sma20)

        summary = {
            "ticker": ticker.upper(),
            "precio_actual": round(current_price, 2),
            "tendencia_MA": "Alcista" if sma20 > sma200 else "Bajista",
            "elliott_historico": elliott_result,
            "active_wave": active_wave,
            "fib_levels": fib_levels,
            "fib_extensions": fib_extensions,
            "last_pivot": {"price": pivots[-1][1], "type": pivots[-1][2], "gap": active_wave.get('gap', 0)} if pivots else {},
            "señal": signal,
            "señal_detalle": signal_detail,
            # Mantener compatibilidad con UI vieja
            "elliott": elliott_result,
        }

        return df, summary, None

    def _generate_signal(self, active_wave, current_price, sma20):
        state = active_wave['state']
        conf = active_wave['confidence']
        gap = active_wave.get('gap', 0)
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
                return f"NEUTRAL - Patrón viejo (gap {gap} velas)", f"El impulso 1-5 terminó hace {gap} velas, proyección vieja irrelevante. Conf baja {conf:.0%}. Alternativas: {len(active_wave.get('alternatives', []))}"
            else:
                return "VENTA / PRECAUCIÓN - En correctiva ABC", "Impulso completo, ahora corrigiendo. Fib 50-61.8% como soporte"

        elif state == "UNKNOWN":
            return "NEUTRAL - Sin patrón activo claro", active_wave['reason']

        return "NEUTRAL", active_wave['reason']
