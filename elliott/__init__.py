"""
Paquete elliott/ — motor Elliott + Fibonacci dividido por responsabilidad.

Antes todo esto vivía en un único elliott_trader_pro.py de 820 líneas
(data provider, indicadores, zigzag, Elliott histórico + activo, Fibonacci,
chart engine y CLI mezclados). Se separó en:

  data_provider.py     -> MarketDataProvider (descarga yfinance + reintentos)
  indicators.py         -> TechnicalIndicators (medias móviles)
  zigzag.py              -> ZigZagDetector
  historical.py          -> ElliottWaveAnalyzer (mejor impulso histórico 1-5)
  active_classifier.py   -> ActiveWaveClassifier (onda EN CURSO, el core predictivo)
  fibonacci.py           -> FibonacciCalculator
  strategy.py            -> ElliottFibonacciStrategy (orquesta todo lo anterior)

El ChartEngine viejo (duplicado de chart_engine_v4.ChartEngineV4, sin SMC/
Volume Profile/Risk) se eliminó: la generación de gráficos ya no es
responsabilidad de este motor, la hace pipeline.py con ChartEngineV4.
"""
from .strategy import ElliottFibonacciStrategy
from .data_provider import MarketDataProvider
from .indicators import TechnicalIndicators
from .zigzag import ZigZagDetector
from .historical import ElliottWaveAnalyzer
from .active_classifier import ActiveWaveClassifier
from .fibonacci import FibonacciCalculator

__all__ = [
    "ElliottFibonacciStrategy",
    "MarketDataProvider",
    "TechnicalIndicators",
    "ZigZagDetector",
    "ElliottWaveAnalyzer",
    "ActiveWaveClassifier",
    "FibonacciCalculator",
]
