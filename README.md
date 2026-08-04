# Trading Consultant 📊

Herramienta de análisis técnico en Python/Streamlit que combina **8 motores de confluencia** sobre un ticker para producir un score explicable (0–100), niveles de entrada/stop/TPs y ratio riesgo-beneficio.

Los motores votan por separado y un pipeline único (`pipeline.py`) orquesta la confluencia. No ejecuta órdenes automáticamente: el análisis y la operativa manual están separados a propósito (ver más abajo).

## Motores

| Motor | Qué hace |
|---|---|
| **Elliott + Fibonacci** (`elliott/`) | Clasificador de la onda EN CURSO (no histórica), con proyecciones ancladas al tramo activo y soporte para correcciones complejas (W-X-Y). |
| **Regime Detector** (`regime_detector.py`) | ADX + Choppiness; bloquea señales en mercado lateral. |
| **Momentum Engine** (`momentum_engine.py`) | RSI/MACD y divergencias. |
| **SMC Engine** (`smc_engine.py`) | Order Blocks, Fair Value Gaps, BOS/CHOCH y liquidity sweeps. |
| **Volume Profile** (`volume_profile.py`) | POC y Value Area. |
| **MTF Analyzer** (`mtf_analyzer.py`) | Alineación entre 1W/1D/4H/1H. |
| **Scoring Engine** (`scoring_engine.py`) | Score 0–100 explicable a partir de los motores anteriores. |
| **Risk Manager** (`risk_manager.py`) | Entry, stop, TP1/TP2 y ratio RR. |

## Cómo usarlo

Requisitos: Python 3.10+, ver `requirements.txt` (streamlit, pandas, yfinance, plotly, peewee…).

```bash
pip install -r requirements.txt

# Opción 1 — CLI: análisis rápido de un ticker sin levantar nada
python3 elliott_trader_pro.py --ticker NVDA --period 2y
python3 elliott_trader_pro.py --ticker NVDA --show   # además abre el gráfico

# Opción 2 — Dashboard Streamlit
streamlit run dashboard_ibkr.py
```

### Dashboard IBKR

`dashboard_ibkr.py` trae histórico desde tu cuenta de IBKR (TWS o IB Gateway local con la API habilitada), lo pasa por el pipeline y muestra tu cartera real.

**El análisis nunca dispara una orden**: el score o la lectura de Elliott no envían nada a IBKR. Solo tú, pulsando el botón y marcando la casilla de confirmación, envías una orden (port 4001 = cuenta real, 4002 = paper).

## Estructura

```
trading-consultant/
├── pipeline.py              # orquestador: los 8 motores en orden (única fuente de verdad)
├── elliott/                 # zigzag, clasificador de onda activa, fibonacci, strategy
├── chart_engine_v4.py       # motor de gráficos (paleta Apple dark)
├── dashboard_ibkr.py        # dashboard Streamlit + operativa manual con IBKR
├── ibkr_connector.py        # conexión con TWS/IB Gateway
├── analysis_history.py      # historial de análisis persistente (SQLite)
├── ui_theme.py              # tema global Apple dark
├── config.py                # umbrales y pesos centralizados de todos los motores
├── scripts/smoke_test.py    # smoke test sin IBKR
├── tests/                   # tests unitarios
└── docs/superpowers/        # planes y specs del proyecto
```

## Estado del proyecto

**En desarrollo activo.** La base (8 motores + pipeline + dashboard + historial persistente + tema visual) está funcional y se usa a diario, pero hay dos frentes abiertos:

- **Validación pendiente**: los umbrales y pesos de `config.py` están puestos a mano y nadie los ha validado contra datos históricos todavía. Centralizarlos en un solo archivo es el paso previo para poder barrerlos con un backtest.
- **Backtest del sistema completo**: falta un orquestador de backtest que mida la confluencia de los 8 motores fuera de muestra.

Ese es el siguiente paso natural: convertir la confluencia en algo medible antes de fiarse de ella.
