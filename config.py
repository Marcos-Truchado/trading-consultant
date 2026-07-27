"""
Config central de umbrales y pesos usados por el ScoringEngine, RiskManager
y los motores de confluencia (Regime, SMC, Volume Profile).

Antes estos números estaban hardcodeados dentro de cada motor (75/60/45 en
scoring_engine, RR mínimo 1.2 en risk_manager, +15/-30 en regime_detector,
±10 en smc_engine...). Nadie los ha validado contra datos históricos todavía
-- son pesos puestos a mano. Centralizarlos aquí no los hace "correctos",
pero es lo que permite en el futuro barrerlos con un backtest en vez de
tener que tocar 6 archivos distintos cada vez que se prueba un valor nuevo.
"""
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ScoringConfig:
    # Score base neutral del que parte el ScoringEngine
    base_score: int = 50

    # Umbrales de decisión BUY/SELL/HOLD sobre el score final (0-100)
    threshold_high: int = 75     # score >= esto -> BUY/SELL confianza ALTA
    threshold_medium: int = 60   # score >= esto -> BUY/SELL confianza MEDIA
    threshold_low: int = 45      # score >= esto -> HOLD confianza BAJA (si no, MUY BAJA)

    # Puntos por estado de onda activa de Elliott
    elliott_wave3_base: int = 15       # + hasta 15 más según confianza (15-30 total)
    elliott_wave3_conf_mult: int = 15
    elliott_wave5_base: int = 10       # + hasta 10 más según confianza (10-20 total)
    elliott_wave5_conf_mult: int = 10
    elliott_wave4_penalty: int = -5
    elliott_stale_penalty: int = -30
    elliott_unknown_penalty: int = -15

    # Ajuste por divergencia de momentum contraria a la dirección de Elliott
    divergence_against_penalty: int = -15

    # Ajuste SMC: bonus si el trend SMC coincide con Elliott, penalización en CHOCH
    smc_alignment_bonus: int = 5
    smc_choch_penalty: int = -10


@dataclass
class RiskConfig:
    atr_period: int = 14
    atr_stop_buffer_mult: float = 0.5   # buffer sobre el stop = ATR * este multiplicador
    atr_fallback_stop_mult: float = 2.0  # si no hay onda activa clara, stop = entry -/+ ATR*mult
    pct_fallback_stop: float = 0.03      # si no hay ni ATR, stop = entry -/+ 3%
    min_valid_rr: float = 1.2            # RR por debajo de esto se marca como inválido
    tp1_rr: float = 1.5                  # fallback TP1 si no hay extensiones Fibonacci
    tp2_rr: float = 2.5                  # fallback TP2 si no hay extensiones Fibonacci


@dataclass
class RegimeConfig:
    min_bars: int = 100
    adx_trending: float = 25.0
    chop_trending_max: float = 55.0
    chop_ranging_min: float = 61.8
    atr_percentile_high_vol: float = 85.0
    score_trending: int = 15
    score_ranging: int = -30
    score_high_vol: int = -10
    score_transition: int = 0


@dataclass
class SMCConfig:
    pivot_order: int = 5           # velas a cada lado para considerar un pivote local
    fvg_lookback: int = 50
    ob_lookback: int = 60
    ob_min_move_pct: float = 2.0   # movimiento mínimo tras la vela para validar un Order Block
    ob_proximity_pct: float = 3.0  # distancia máx. al precio actual para dar bonus de confluencia
    score_bos_bull: int = 15
    score_bos_bear: int = 15
    score_choch: int = -5
    score_sweep_bear: int = -10
    score_sweep_bull: int = 10
    score_ob_confluence: int = 10


@dataclass
class VolumeProfileConfig:
    bins: int = 40
    lookback: int = 200
    value_area_pct: float = 0.7
    dist_poc_high_conf_pct: float = 1.5
    dist_poc_medium_conf_pct: float = 3.0
    score_poc_close: int = 10
    score_poc_medium: int = 5


# Instancias por defecto -- los motores las importan directamente.
# Si en algún momento se quiere barrer valores desde un backtest, se
# construyen instancias alternativas de estos dataclasses ahí sin tocar
# el motor en sí.
SCORING = ScoringConfig()
RISK = RiskConfig()
REGIME = RegimeConfig()
SMC = SMCConfig()
VOLUME_PROFILE = VolumeProfileConfig()
