"""
Pipeline de análisis compartido.

Antes esto estaba duplicado casi línea a línea en app.py y dashboard_ibkr.py:
cada uno instanciaba y corría los 8 motores (Elliott, Regime, Momentum, SMC,
Volume Profile, MTF, Scoring, Risk) por su cuenta. Se decidió mantener solo
el dashboard de IBKR, así que este módulo es ahora la única fuente de verdad
del pipeline -- un cambio en el orden de los motores o en qué se le pasa a
cada uno se hace aquí una vez, no en cada Streamlit app.

run_full_analysis() recibe un DataFrame OHLCV YA DESCARGADO (de IBKR,
yfinance, o cualquier otra fuente con columnas Open/High/Low/Close/Volume e
índice de fechas) para que quien llama decida de dónde vienen los datos.
"""
from typing import Dict, Optional
import pandas as pd

from elliott import ElliottFibonacciStrategy
from regime_detector import RegimeDetector
from momentum_engine import MomentumEngine
from smc_engine import SMCEngine
from volume_profile import VolumeProfileEngine
from mtf_analyzer import MTFAnalyzer
from scoring_engine import ScoringEngine
from risk_manager import RiskManager


def run_full_analysis(df: pd.DataFrame, ticker: str, deviation: float, ibkr=None) -> Dict:
    """
    Corre el pipeline completo de los 8 motores sobre un DataFrame OHLCV.

    ibkr: conector IBKRConnector opcional ya conectado. Se pasa al
    MTFAnalyzer para que las 4 timeframes (1W/1D/4H/1H) usen la misma
    fuente de datos que el resto del dashboard (con fallback automático a
    yfinance si IBKR falla en alguna timeframe puntual).

    Devuelve un dict con todo lo que la UI necesita pintar: df (con
    indicadores ya añadidos), summary/active_wave de Elliott, pivots, y el
    resultado de cada motor (regime, momentum, smc, vol_prof, mtf, risk,
    scoring).
    """
    engine = ElliottFibonacciStrategy(deviation_pct=deviation)
    df, summary, _ = engine.analyze_dataframe(df, ticker, deviation=deviation)

    active_wave = summary['active_wave']
    pivots = engine.zigzag.get_pivots(df)

    regime = RegimeDetector().analyze(df)
    momentum = MomentumEngine().analyze(df)
    smc = SMCEngine().analyze(df, pivots)
    vol_prof = VolumeProfileEngine().analyze(df)
    mtf = MTFAnalyzer().analyze(ticker, deviation=deviation, ibkr=ibkr)
    risk = RiskManager().calculate(df, active_wave, smc, summary.get('fib_extensions', {}), summary['precio_actual'])
    scoring = ScoringEngine().calculate(
        active_wave, regime, momentum, smc, vol_prof, mtf,
        summary['fib_levels'], summary['precio_actual']
    )

    return {
        "df": df,
        "summary": summary,
        "active_wave": active_wave,
        "pivots": pivots,
        "regime": regime,
        "momentum": momentum,
        "smc": smc,
        "vol_prof": vol_prof,
        "mtf": mtf,
        "risk": risk,
        "scoring": scoring,
    }
