# Apple Design Redesign — Dashboard IBKR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rediseñar la UI del dashboard Streamlit al estilo Apple (dark mode, materiales translúcidos, tipografía de sistema) sin tocar la lógica de los 8 motores, añadiendo panel resumen ejecutivo e historial de análisis.

**Architecture:** Capa de presentación pura sobre `dashboard_ibkr.py` existente. Tema dark via `.streamlit/config.toml` + CSS global inyectado desde un módulo nuevo `ui_theme.py`. Historial persistido en SQLite con peewee en `analysis_history.py`. Chart engine solo recibe ajustes de paleta. `pipeline.py` y los motores NO se modifican.

**Tech Stack:** Python 3, Streamlit 1.36, peewee 3.17, plotly 5.22, pandas 2.2, unittest (stdlib, sin dependencias nuevas).

**Run/Tests (siempre desde `/Users/matru/Desktop/trading-consultant` con `venv` activado):**
- Tests: `venv/bin/python -m unittest discover -s tests -v`
- Arranque: `venv/bin/python -m streamlit run dashboard_ibkr.py` (headless)
- Smoke: `venv/bin/python scripts/smoke_test.py`

## Global Constraints

- NO modificar: `pipeline.py`, `elliott/`, `regime_detector.py`, `momentum_engine.py`, `smc_engine.py`, `volume_profile.py`, `mtf_analyzer.py`, `scoring_engine.py`, `risk_manager.py`, `ibkr_connector.py`, `config.py`.
- Streamlit fijado en 1.36: selectores CSS deben usar testids disponibles en 1.36 (`stSidebar`, `stMetric`, `stDataFrame`), no los de versiones posteriores.
- No añadir dependencias nuevas a `requirements.txt` (unittest y peewee ya disponibles).
- Envío de órdenes y confirmación manual: sin cambios de semántica.
- Paleta: bg `#0a0a0f`, superficie `#16161c`, superficie-alta `#1c1c22`, texto `#f5f5f7`, texto-suave `#98989d`, acento `#0a84ff`, verde `#30d158`, rojo `#ff453a`, ámbar `#ffd60a`, border `rgba(255,255,255,0.08)`.
- Respetar `prefers-reduced-motion: reduce` en todo CSS animado.

---

### Task 1: Tema dark + CSS global estilo Apple

**Files:**
- Create: `.streamlit/config.toml`
- Create: `ui_theme.py`
- Test: `tests/test_ui_theme.py`

**Interfaces:**
- Produces: `ui_theme.GLOBAL_CSS: str`, `ui_theme.inject_theme() -> None` (llama a `st.markdown(unsafe_allow_html=True)`), `ui_theme.exec_summary_html(...) -> str` (se usa en Task 4), `ui_theme.conn_badge_html(connected: bool, label: str) -> str`.

- [ ] **Step 1: Escribir el test fallido** — crear `tests/test_ui_theme.py`:

```python
import unittest
from unittest import mock
import ui_theme


class TestTheme(unittest.TestCase):
    def test_global_css_has_apple_dark_selectors(self):
        css = ui_theme.GLOBAL_CSS
        for selector in ("stSidebar", "stMetric", "stDataFrame", "prefers-reduced-motion", "backdrop-filter"):
            self.assertIn(selector, css)
        self.assertIn("#0a0a0f", css)
        self.assertIn("#0a84ff", css)

    def test_inject_theme_marks_down_markdown(self):
        st = mock.Mock()
        with mock.patch.dict("sys.modules", {"streamlit": st}):
            import importlib
            ui_theme_mod = importlib.reload(ui_theme)
            ui_theme_mod.inject_theme()
        args = st.markdown.call_args
        self.assertTrue(args.kwargs.get("unsafe_allow_html", args.args[1] if len(args.args) > 1 else False))

    def test_conn_badge_connected(self):
        html = ui_theme.conn_badge_html(True, "Conectado · Paper")
        self.assertIn("Conectado", html)
        self.assertIn("online", html)

    def test_conn_badge_disconnected(self):
        html = ui_theme.conn_badge_html(False, "No conectado")
        self.assertIn("No conectado", html)
        self.assertIn("offline", html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `venv/bin/python -m unittest tests.test_ui_theme -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'ui_theme'`

- [ ] **Step 3: Crear `.streamlit/config.toml`**

```toml
[theme]
base = "dark"
primaryColor = "#0a84ff"
backgroundColor = "#0a0a0f"
secondaryBackgroundColor = "#16161c"
textColor = "#f5f5f7"
font = "sans-serif"
```

- [ ] **Step 4: Crear `ui_theme.py` con el CSS global**

```python
"""
ui_theme.py - Capa de presentación estilo Apple para el dashboard Streamlit.

CSS global inyectado una vez al arranque + helpers de HTML para el resumen
ejecutivo y el badge de conexión. No contiene lógica de negocio; solo
presentación. Selectores pensados para Streamlit 1.36.
"""

GLOBAL_CSS = """
<style>
/* ===== Base ===== */
.stApp { background: #0a0a0f; color: #f5f5f7; }
.block-container { padding-top: 1.8rem; max-width: 1440px; }
html, body, [class*="css"] { font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif; }
h1, h2, h3 { letter-spacing: -0.02em; font-weight: 650; color: #f5f5f7; }
h1 { font-size: 1.7rem; } h2 { font-size: 1.25rem; } h3 { font-size: 1.05rem; }
p, label, [data-testid="stCaptionContainer"], [data-testid="stMarkdownContainer"] p { color: #d5d5da; }
hr { border-color: rgba(255,255,255,0.08); }

/* ===== Sidebar translúcida ===== */
[data-testid="stSidebar"] {
  background: rgba(22,22,28,0.85);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-right: 1px solid rgba(255,255,255,0.06);
}

/* ===== Métricas estilo Apple ===== */
[data-testid="stMetric"] {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 12px;
  padding: 14px 16px;
}
[data-testid="stMetricLabel"] {
  color: #98989d; font-size: 12px; letter-spacing: 0.02em; font-weight: 500;
}
[data-testid="stMetricValue"] {
  color: #f5f5f7; font-size: 28px; font-weight: 600;
  letter-spacing: -0.01em; font-variant-numeric: tabular-nums; line-height: 1.2;
}
[data-testid="stMetricDelta"] { font-size: 12px; font-weight: 500; }

/* ===== Botones ===== */
.stButton button, .stFormSubmitButton button, [data-testid="stDataFrame"] button {
  border-radius: 10px; font-weight: 500;
  transition: transform 100ms ease-out, background-color 150ms ease, border-color 150ms ease;
}
.stButton button:hover, .stFormSubmitButton button:hover { border-color: #0a84ff; }
.stButton button:active, .stFormSubmitButton button:active { transform: scale(0.97); }
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primary"] {
  background: #0a84ff; border: none; color: #fff;
}
.stButton button[kind="primary"]:hover { background: #2a95ff; }

/* ===== Tabs ===== */
.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid rgba(255,255,255,0.08); }
.stTabs [data-baseweb="tab"] {
  font-size: 14px; font-weight: 500; color: #98989d;
  padding: 8px 14px; border-radius: 8px 8px 0 0;
  transition: color 150ms ease, background-color 150ms ease;
}
.stTabs [data-baseweb="tab"]:hover { color: #f5f5f7; background: rgba(255,255,255,0.04); }
.stTabs [aria-selected="true"] { color: #f5f5f7 !important; }
.stTabs [data-baseweb="tab-highlight"] { background-color: #0a84ff; height: 2px; border-radius: 2px; }

/* ===== Inputs / Selects ===== */
[data-baseweb="input"] > div, [data-baseweb="select"] > div {
  background: #1c1c22 !important; border-color: #2c2c33 !important; border-radius: 10px;
}
[data-baseweb="input"]:focus-within > div, [data-baseweb="select"]:focus-within > div {
  border-color: #0a84ff !important;
  box-shadow: 0 0 0 3px rgba(10,132,255,0.22);
}
[data-baseweb="slider"] div[role="slider"] { background: #0a84ff; border-color: #0a84ff; }
[data-testid="stSliderThumbValue"] { color: #f5f5f7; font-variant-numeric: tabular-nums; }

/* ===== Checkbox ===== */
[data-testid="stCheckbox"] label span[role="checkbox"] {
  border-radius: 6px; border-color: #2c2c33;
}

/* ===== Alerts suavizados ===== */
.stAlert {
  border-radius: 12px; border-left: none !important;
  background: rgba(255,255,255,0.04) !important;
  backdrop-filter: blur(10px);
}
.stAlert [data-testid="stAlert"] { padding: 12px 16px; }

/* ===== Tablas (dataframes) ===== */
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; border: 1px solid rgba(255,255,255,0.06); }

/* ===== Expander ===== */
[data-testid="stExpander"] { border-radius: 12px; border-color: rgba(255,255,255,0.08); background: rgba(255,255,255,0.02); }

/* ===== Scrollbar fina macOS ===== */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.25); }

/* ===== Badge de conexión ===== */
.conn-badge {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 5px 12px; border-radius: 999px; font-size: 12px; font-weight: 600;
  letter-spacing: 0.02em;
}
.conn-badge .dot { width: 8px; height: 8px; border-radius: 50%; }
.conn-badge.online { background: rgba(48,209,88,0.14); color: #30d158; border: 1px solid rgba(48,209,88,0.3); }
.conn-badge.online .dot { background: #30d158; animation: pulse-dot 1.6s ease-in-out infinite; }
.conn-badge.offline { background: rgba(255,69,58,0.12); color: #ff453a; border: 1px solid rgba(255,69,58,0.3); }
.conn-badge.offline .dot { background: #ff453a; }
@keyframes pulse-dot { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

/* ===== Resumen ejecutivo (cards) ===== */
.exec-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
  margin-bottom: 12px;
}
@media (max-width: 900px) { .exec-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 560px) { .exec-grid { grid-template-columns: 1fr; } }
.exec-card {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 14px; padding: 16px;
  backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  transition: opacity 200ms ease, transform 200ms ease;
}
.exec-card:hover { transform: translateY(-1px); border-color: rgba(255,255,255,0.12); }
.exec-label { color: #98989d; font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 6px; }
.exec-value { color: #f5f5f7; font-size: 26px; font-weight: 650; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; line-height: 1.15; }
.exec-sub { color: #98989d; font-size: 12px; margin-top: 4px; }
.exec-value.buy { color: #30d158; }
.exec-value.sell { color: #ff453a; }
.exec-value.neutral { color: #ffd60a; }
.exec-chip {
  display: inline-block; padding: 3px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 600; letter-spacing: 0.02em; margin-top: 6px;
}
.exec-chip.warn { background: rgba(255,214,10,0.14); color: #ffd60a; border: 1px solid rgba(255,214,10,0.3); }
.exec-chip.danger { background: rgba(255,69,58,0.14); color: #ff453a; border: 1px solid rgba(255,69,58,0.3); }
.exec-chip.ok { background: rgba(48,209,88,0.14); color: #30d158; border: 1px solid rgba(48,209,88,0.3); }
.exec-progress {
  height: 4px; border-radius: 2px; background: #2c2c33; margin-top: 10px; overflow: hidden;
}
.exec-progress > div {
  height: 100%; border-radius: 2px; background: #0a84ff;
  transition: width 600ms cubic-bezier(0.22, 1, 0.36, 1);
}

/* ===== Reduced motion ===== */
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
}
</style>
"""


def inject_theme() -> None:
    import streamlit as st
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def conn_badge_html(connected: bool, label: str) -> str:
    cls = "online" if connected else "offline"
    return f'<span class="conn-badge {cls}"><span class="dot"></span>{label}</span>'


def _fmt(v, suffix="", prefix=""):
    try:
        return f"{prefix}{v:,.2f}{suffix}"
    except (TypeError, ValueError):
        return "—"


def exec_summary_html(scoring: dict, aw: dict, summary: dict, risk: dict) -> str:
    action = scoring.get("action", "NEUTRAL")
    action_cls = {"BUY": "buy", "SELL": "sell"}.get(action, "neutral")
    score = scoring.get("score", 0)
    precio = summary.get("precio_actual")
    estado = aw.get("state", "—")
    gap = aw.get("gap", 0)
    rr = risk.get("rr1")
    risk_pct = risk.get("risk_pct")
    rr_valid = risk.get("valid_rr")
    rr_cls = "ok" if rr_valid else ("warn" if rr else "warn")
    rr_txt = _fmt(rr) if rr else "—"
    rr_sub = "Válido" if rr_valid else ("Bajo" if rr else "Sin plan")
    dir_txt = "Alcista" if aw.get("is_bullish") is True else ("Bajista" if aw.get("is_bullish") is False else "Neutral")
    dir_cls = {"Alcista": "buy", "Bajista": "sell"}.get(dir_txt, "neutral")

    chips = []
    if aw.get("is_stale"):
        chips.append('<span class="exec-chip danger">STALE · Impulso terminado hace %s velas</span>' % gap)
    if summary.get("regime_block") is not None:
        chips.append('<span class="exec-chip warn">%s</span>' % summary["regime_block"])

    return f"""
<div class="exec-grid">
  <div class="exec-card">
    <div class="exec-label">Score Confluencia</div>
    <div class="exec-value">{score}</div>
    <div class="exec-sub">{scoring.get("confidence_label", "")}</div>
    <div class="exec-progress"><div style="width: {max(0, min(score, 100))}%"></div></div>
  </div>
  <div class="exec-card">
    <div class="exec-label">Veredicto</div>
    <div class="exec-value {action_cls}">{scoring.get("veredicto", "NEUTRAL")}</div>
    <div class="exec-sub">Dirección Elliott: <b>{dir_txt}</b></div>
  </div>
  <div class="exec-card">
    <div class="exec-label">Precio Actual</div>
    <div class="exec-value">{_fmt(precio, prefix="$")}</div>
    <div class="exec-sub">Riesgo {risk_pct:.1f}% al stop</div>
  </div>
  <div class="exec-card">
    <div class="exec-label">Ratio RR</div>
    <div class="exec-value">{rr_txt}</div>
    <div class="exec-sub">{rr_sub}</div>
  </div>
</div>
<div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px;">{"".join(chips)}</div>
"""
```

Nota: `summary["regime_block"]` lo rellena el dashboard (Task 4) al ejecutar el análisis; si no existe, no se muestra chip. El HTML es válido aunque el grid esté vacío.

- [ ] **Step 5: Ejecutar test y verificar que pasa**

Run: `venv/bin/python -m unittest tests.test_ui_theme -v`
Expected: 4 PASS. Si falla `test_inject_theme_marks_down_markdown`, ajustar el assert al mecanismo real de `st.markdown` del mock (verificar que se llama con `unsafe_allow_html=True` de alguna forma).

- [ ] **Step 6: Commit**

```bash
git add .streamlit/config.toml ui_theme.py tests/test_ui_theme.py
git commit -m "feat: add apple dark theme and global css"
```

---

### Task 2: Historial de análisis (SQLite + peewee, TDD)

**Files:**
- Create: `analysis_history.py`
- Create: `tests/test_analysis_history.py`

**Interfaces:**
- Consumes: nada (stdlib + peewee).
- Produces:
  - `analysis_history.ensure_table() -> None`
  - `analysis_history.record_analysis(*, ticker: str, score: float, veredicto: str, action: str, precio: float, rr: float, direccion: str, estado_onda: str, deviation: float, period: str, bar_size: str) -> int` (devuelve id)
  - `analysis_history.recent_analyses(limit: int = 50) -> list[dict]` (desc por timestamp; claves: id, ticker, timestamp (str iso), score, veredicto, action, precio, rr, direccion, estado_onda, deviation, period, bar_size)
  - `analysis_history.load_analysis(record_id: int) -> dict | None`

- [ ] **Step 1: Escribir los tests fallidos** — crear `tests/test_analysis_history.py`:

```python
import os
import tempfile
import unittest

import analysis_history


class TestAnalysisHistory(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        analysis_history.DB_PATH = os.path.join(self._tmp, "test_history.db")
        analysis_history.ensure_table()

    def tearDown(self):
        analysis_history._db.close()
        os.remove(analysis_history.DB_PATH)

    def _record(self, **over):
        base = dict(
            ticker="ONDS", score=72.5, veredicto="Compra en retroceso a zona OB",
            action="BUY", precio=99.25, rr=2.1, direccion="bull",
            estado_onda="FORMING_WAVE_3", deviation=15.0, period="2 Y", bar_size="1 day",
        )
        base.update(over)
        return analysis_history.record_analysis(**base)

    def test_record_and_recent_desc_order(self):
        self._record(ticker="ONDS", score=60)
        self._record(ticker="AAA", score=90)
        recs = analysis_history.recent_analyses()
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0]["ticker"], "AAA")
        self.assertIn("id", recs[0])
        self.assertIn("timestamp", recs[0])

    def test_load_analysis_roundtrip(self):
        rid = self._record(ticker="XYZ", score=55.5, rr=1.3)
        rec = analysis_history.load_analysis(rid)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["ticker"], "XYZ")
        self.assertEqual(rec["score"], 55.5)
        self.assertEqual(rec["action"], "BUY")
        self.assertEqual(rec["deviation"], 15.0)
        self.assertEqual(rec["period"], "2 Y")

    def test_load_missing_returns_none(self):
        self.assertIsNone(analysis_history.load_analysis(999999))

    def test_recent_limit(self):
        for i in range(5):
            self._record(ticker=f"T{i}", score=i)
        recs = analysis_history.recent_analyses(limit=2)
        self.assertEqual(len(recs), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `venv/bin/python -m unittest tests.test_analysis_history -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'analysis_history'`

- [ ] **Step 3: Crear `analysis_history.py`**

```python
"""
analysis_history.py - Persistencia del historial de análisis.

SQLite vía peewee (ya en requirements.txt). Guarda un snapshot por análisis
exitoso para poder comparar evolución del score y recargar un análisis previo
desde el dashboard. Sin dependencias nuevas.
"""
import os

from peewee import SqliteDatabase, Model, CharField, FloatField, DateTimeField
import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analisis_history.db")

_db = SqliteDatabase(DB_PATH)


class AnalysisRecord(Model):
    ticker = CharField()
    timestamp = DateTimeField(default=datetime.datetime.now)
    score = FloatField()
    veredicto = CharField()
    action = CharField()
    precio = FloatField()
    rr = FloatField(null=True)
    direccion = CharField()
    estado_onda = CharField()
    deviation = FloatField()
    period = CharField()
    bar_size = CharField()

    class Meta:
        database = _db


def ensure_table() -> None:
    _db.connect(reuse_if_open=True)
    _db.create_tables([AnalysisRecord])


def record_analysis(*, ticker: str, score: float, veredicto: str, action: str,
                    precio: float, rr: float, direccion: str, estado_onda: str,
                    deviation: float, period: str, bar_size: str) -> int:
    ensure_table()
    rec = AnalysisRecord.create(
        ticker=ticker, score=float(score), veredicto=veredicto, action=action,
        precio=float(precio), rr=rr, direccion=direccion, estado_onda=estado_onda,
        deviation=float(deviation), period=period, bar_size=bar_size,
    )
    return rec.id


def _to_dict(rec: AnalysisRecord) -> dict:
    return {
        "id": rec.id,
        "ticker": rec.ticker,
        "timestamp": rec.timestamp.isoformat(sep=" "),
        "score": rec.score,
        "veredicto": rec.veredicto,
        "action": rec.action,
        "precio": rec.precio,
        "rr": rec.rr,
        "direccion": rec.direccion,
        "estado_onda": rec.estado_onda,
        "deviation": rec.deviation,
        "period": rec.period,
        "bar_size": rec.bar_size,
    }


def recent_analyses(limit: int = 50) -> list:
    ensure_table()
    rows = (AnalysisRecord.select()
            .order_by(AnalysisRecord.timestamp.desc())
            .limit(limit))
    return [_to_dict(r) for r in rows]


def load_analysis(record_id: int) -> dict | None:
    ensure_table()
    try:
        rec = AnalysisRecord.get_by_id(record_id)
    except AnalysisRecord.DoesNotExist:
        return None
    return _to_dict(rec)
```

- [ ] **Step 4: Ejecutar tests y verificar que pasan**

Run: `venv/bin/python -m unittest tests.test_analysis_history -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add analysis_history.py tests/test_analysis_history.py
git commit -m "feat: add analysis history persistence with sqlite"
```

---

### Task 3: Paleta dark en Chart Engine (sin tocar lógica)

**Files:**
- Modify: `chart_engine_v4.py` (solo valores de color/template)
- Test: `tests/test_chart_engine.py`

**Interfaces:**
- Consumes: `ChartEngineV4.plot(df, ticker, elliott_result, fib_levels, fib_extensions, active_wave, smc, volume_prof, risk, show_ob=True, show_fvg=True, show_vp=True)` — firma INALTERADA (Task 4 la llama igual).
- Produces: figura Plotly con paleta dark coherente y fondos transparentes (para integrarse con el fondo `#0a0a0f` del tema).

- [ ] **Step 1: Escribir test de sanity** — crear `tests/test_chart_engine.py`:

```python
import unittest
import numpy as np
import pandas as pd

from chart_engine_v4 import ChartEngineV4


def _synthetic_df(n=300, seed=42):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.uniform(0.1, 1.5, n)
    low = close - rng.uniform(0.1, 1.5, n)
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    df = pd.DataFrame({
        "Open": close, "High": high, "Low": low, "Close": close, "Volume": rng.integers(1e4, 1e6, n),
        "SMA_20": pd.Series(close).rolling(20).mean(), "SMA_50": pd.Series(close).rolling(50).mean(),
    })
    df.index = idx
    return df


class TestChartEngine(unittest.TestCase):
    def test_plot_builds_dark_figure(self):
        df = _synthetic_df()
        fig = ChartEngineV4.plot(
            df, "ONDS",
            elliott_result={"estado": "x"}, fib_levels={0.618: 95.0},
            fib_extensions={1.618: 110.0},
            active_wave={"state": "TEST", "gap": 0, "confidence": 0.7, "is_bullish": True,
                          "base_pivots": [], "reason": "test", "current_price": 100.0},
            smc={"order_blocks": [], "fvg": [], "bos_choch": {}, "liquidity_sweep": {}},
            volume_prof={"poc": 98.0, "vah": 102.0, "val": 96.0},
            risk={"entry": 99.0, "stop": 97.0, "tps": [], "rr1": 2.0},
            show_ob=True, show_fvg=True, show_vp=True,
        )
        # la figura debe construirse sin error y con template dark resuelto
        self.assertIsNotNone(fig.layout.template)
        self.assertEqual(fig.layout.template.layout.paper_bgcolor, "rgba(0,0,0,0)")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar y verificar que pasa** (la figura ya usa plotly_dark; el test valida la firma actual)

Run: `venv/bin/python -m unittest tests.test_chart_engine -v`
Expected: PASS con el código actual.

- [ ] **Step 3: Ajustar paleta dark en `chart_engine_v4.py`** — solo colores, NADA de estructura:

Cambios exactos:
- Línea 21-24 candlesticks: `increasing_line_color='#30d158'`, `decreasing_line_color='#ff453a'`
- Línea 29-33 SMAs: SMA 20 → `'#ff9f0a'`, SMA 50 → `'#64d2ff'`, SMA 200 → `'#bf5af2'` con dash
- Línea 47-48 Elliott: `'#30d158'`
- Línea 59: línea en curso → `'#ffd60a'`
- Línea 65-67 fib retracements: `line_color="rgba(255,255,255,0.35)"`; mantener `line_dash="dot"`
- Línea 71-73 fib extensions: `line_color="rgba(255,214,10,0.8)"`
- Línea 79: OB bull `"rgba(48,209,88,0.12)"`, bear `"rgba(255,69,58,0.12)"`
- Línea 93: FVG bull `"rgba(100,210,255,0.10)"`, bear `"rgba(255,159,10,0.10)"`
- Línea 104-109 POC: `"#64d2ff"`, VAH/VAL `"rgba(100,210,255,0.45)"`
- Línea 113-120 risk: entry `"#f5f5f7"`, stop `"#ff453a"`, TPs `"#30d158"`
- Línea 131: RSI línea `'#64d2ff'`
- Línea 138-145 layout: template `plotly_dark` (ya), añadir `paper_bgcolor='rgba(0,0,0,0)'`, `plot_bgcolor='rgba(0,0,0,0)'`, `font=dict(color='#f5f5f7')`, `xaxis=dict(gridcolor='rgba(255,255,255,0.06)')`, `yaxis=dict(gridcolor='rgba(255,255,255,0.06)')`, height 900 mantenido.

- [ ] **Step 4: Verificar que el test sigue pasando y la figura sigue siendo válida**

Run: `venv/bin/python -m unittest tests.test_chart_engine -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add chart_engine_v4.py tests/test_chart_engine.py
git commit -m "feat: retheme chart engine palette to apple dark"
```

---

### Task 4: Integración en el dashboard

**Files:**
- Modify: `dashboard_ibkr.py`
- Create: `scripts/smoke_test.py`

**Interfaces:**
- Consumes: `ui_theme.inject_theme`, `ui_theme.exec_summary_html`, `ui_theme.conn_badge_html`, `analysis_history.*` (Task 1-2), `ChartEngineV4.plot` (Task 3, firma inalterada).
- Produces: dashboard completo. Bloque de análisis refactorizado a `render_analysis(ticker, period, bar_size, deviation)` para permitir "Cargar" desde historial.

- [ ] **Step 1: Refactor del bloque de análisis**

En `dashboard_ibkr.py`, extraer todo lo que hay entre `with st.spinner(...)` y el final del bloque `analizar_btn` a una función nueva al final del archivo:

```python
def render_analysis(ticker: str, period: str, bar_size: str, deviation: float, ibkr, show_ob, show_fvg, show_vp) -> dict | None:
    """Corre el pipeline completo y pinta resumen, gráfico, niveles y tabs.

    Devuelve el dict 'result' de run_full_analysis (o None si no hay datos)
    para que el llamador pueda guardarlo en el historial.
    """
    with st.spinner(f"Trayendo histórico de {ticker} desde IBKR y analizando en 8 motores..."):
        raw_df = ibkr.get_historical_bars(ticker, duration=period, bar_size=bar_size)
        if raw_df is None or len(raw_df) < 30:
            st.error("IBKR no devolvió suficientes datos. Revisa el ticker o el permiso de mercado de datos delayed.")
            return None
        result = run_full_analysis(raw_df, ticker, deviation, ibkr=ibkr)
        df = result["df"]; summary = result["summary"]; aw = result["active_wave"]
        regime = result["regime"]; momentum = result["momentum"]; smc = result["smc"]
        vol_prof = result["vol_prof"]; mtf = result["mtf"]; risk = result["risk"]
        scoring = result["scoring"]
        st.session_state.last_summary = summary

        # --- Resumen ejecutivo estilo Apple ---
        summary["regime_block"] = regime["reason"] if not regime["tradeable"] else None
        st.markdown(ui_theme.exec_summary_html(scoring, aw, summary, risk), unsafe_allow_html=True)

        # --- Gráfico ---
        fig_v4 = ChartEngineV4.plot(df, ticker, summary['elliott_historico'], summary['fib_levels'],
                                    summary.get('fib_extensions', {}), aw, smc, vol_prof, risk,
                                    show_ob, show_fvg, show_vp)
        st.plotly_chart(fig_v4, use_container_width=True)
        st.caption(f"Razonamiento: {aw['reason']}")

        # --- Niveles (código existente intacto) ---
        st.subheader("📐 Niveles clave: soportes y resistencias (Fibonacci sobre tramo activo)")
        niveles = []
        for k, v in summary['fib_levels'].items():
            niveles.append({"tipo": "Retroceso", "nivel": f"{k*100:.1f}%", "precio": v})
        for k, v in summary.get('fib_extensions', {}).items():
            niveles.append({"tipo": "Extensión", "nivel": f"{k*100:.0f}%", "precio": v})
        if niveles:
            precio_actual = summary['precio_actual']
            is_bull_dir = aw.get('is_bullish')
            filas = []
            for n in niveles:
                dist_pct = (n["precio"] - precio_actual) / precio_actual * 100
                below = n["precio"] < precio_actual
                above = n["precio"] > precio_actual
                if is_bull_dir is None:
                    zona = "🟢 Nivel inferior" if below else ("🔴 Nivel superior" if above else "⚪ En precio actual")
                elif below:
                    zona = "🟢 SOPORTE (a favor de la tendencia alcista)" if is_bull_dir \
                        else "🟡 Nivel inferior (en contra de tendencia bajista, no es señal de compra)"
                elif above:
                    zona = "🔴 RESISTENCIA (objetivo bajista / posible corto)" if not is_bull_dir \
                        else "🟡 Nivel superior (en contra de tendencia alcista, no es señal de venta)"
                else:
                    zona = "⚪ En precio actual"
                filas.append({"Zona": zona, "Tipo Fib": n["tipo"], "Nivel": n["nivel"],
                              "Precio": f"${n['precio']:.2f}", "Distancia": f"{dist_pct:+.2f}%",
                              "_dist_abs": abs(dist_pct)})
            filas.sort(key=lambda r: r["_dist_abs"])
            for f in filas:
                del f["_dist_abs"]
            niveles_df = pd.DataFrame(filas)
            st.dataframe(niveles_df, use_container_width=True, hide_index=True)
            st.caption("Los niveles se etiquetan según la dirección que ya detectó Elliott (arriba), no solo por estar por encima o debajo del precio: un nivel 'a favor' es soporte/resistencia operable, uno 'en contra' es solo estructura a vigilar.")
        else:
            st.info(f"Sin niveles Fibonacci calculados para el tramo activo actual (estado: {aw['state']}).")

        # --- Tabs de análisis (estructura existente) ---
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Desglose Score", "Confluencia", "Riesgo", "MTF", "Elliott Detalle", "Historial"])
        with tab1:
            st.subheader("Por qué este score")
            c1, c2 = st.columns(2)
            with c1:
                st.json(scoring['breakdown'])
                for r in scoring['reasons']:
                    if "+-" in r or "+" in r or "-" in r:
                        if "-" in r and "+" not in r.split("-")[-1]:
                            st.write(f"🔻 {r}")
                        else:
                            st.write(f"✅ {r}")
                    else:
                        st.write(f"• {r}")
            with c2:
                st.markdown(f"**Regime:** {regime['regime']} ADX {regime['adx']:.1f} Chop {regime['choppiness']:.1f}")
                st.markdown(f"**Momentum:** RSI {momentum['rsi']:.1f} | {momentum['mom_state']} | Div: {momentum['divergence']}")
                st.markdown(f"**SMC Trend:** {smc['trend_smc']} | BOS: {len(smc['bos_choch']['bos'])} CHOCH: {len(smc['bos_choch']['choch'])}")
                st.markdown(f"**Vol Profile:** POC ${vol_prof.get('poc','-')} | Dist {vol_prof.get('dist_poc_pct',0):.1f}%")
                st.markdown(f"**MTF:** {mtf['alignment']} | {mtf['reason']}")
        with tab2:
            colA, colB, colC = st.columns(3)
            with colA:
                st.subheader("Regime Filter")
                st.json(regime)
                st.subheader("Momentum & Divergence")
                st.json({k: v for k, v in momentum.items() if k not in ['rsi_series', 'macd_hist_series']})
            with colB:
                st.subheader("SMC - Smart Money")
                st.write(f"**BOS/CHOCH:** {smc['bos_choch']['reason']}")
                st.json(smc['bos_choch'])
                st.write(f"**Liquidity Sweep:** {smc['liquidity_sweep']['reason']}")
                st.json(smc['liquidity_sweep'])
            with colC:
                st.subheader("Volume Profile")
                st.json({k: v for k, v in vol_prof.items() if k != 'histogram'})
                st.subheader("Order Blocks & FVGs")
                st.write("OBs activos:", smc['order_blocks'])
                st.write("FVGs activos:", smc['fvg'])
        with tab3:
            st.subheader("Plan de trade (no es ejecución, es análisis)")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Entry", f"${risk['entry']:.2f}")
            c2.metric("Stop Loss", f"${risk['stop']:.2f}" if risk['stop'] else "-", risk['stop_reason'])
            if risk['tps']:
                c3.metric("TP1", f"${risk['tps'][0]['price']:.2f}", f"RR {risk['rr1']:.2f}" if risk['rr1'] else "")
                if len(risk['tps']) > 1:
                    c4.metric("TP2", f"${risk['tps'][1]['price']:.2f}", f"RR {risk['rr2']:.2f}" if risk['rr2'] else "")
            st.divider()
            if not risk['valid_rr']:
                rr1_txt = f"{risk['rr1']:.2f}" if risk['rr1'] else "0"
                st.warning(f"RR {rr1_txt} bajo (<1.2). Aunque el score sea bueno, el trade no compensa riesgo. Busca entrada más cercana a invalidación.")
            else:
                st.success(f"RR válido {risk['rr1']:.2f} | Riesgo {risk['risk_pct']:.1f}% del precio al stop")
        with tab4:
            st.subheader("Multi-Timeframe Alignment")
            st.json(mtf)
            mtf_df = pd.DataFrame([{"TF": k, "Trend": v['trend'], "Score": v['score'], "SMA20": v.get('sma20', '-'), "SMA200": v.get('sma200', '-'), "Fuente": mtf.get('fuente_datos', {}).get(k, '-')} for k, v in mtf['timeframes'].items()])
            st.dataframe(mtf_df, use_container_width=True)
            if mtf['alignment'] == "BULL_ALIGNED":
                st.success("Todos los timeframes alineados alcistas - alta probabilidad si score diario también es BUY")
            elif mtf['alignment'] == "BEAR_ALIGNED":
                st.error("Todos alineados bajistas")
            elif mtf['alignment'] == "MIXED":
                st.warning("Timeframes mixtos - espera alineación o baja a timeframe menor para entrada")
        with tab5:
            st.subheader("Elliott Detalle v4")
            st.json({"state": aw['state'], "confidence": f"{aw['confidence']:.1%}", "gap": aw.get('gap'),
                      "is_bullish": aw.get('is_bullish'), "reason": aw['reason'],
                      "next_target": aw.get('next_target'), "is_stale": aw.get('is_stale', False)})
            if aw.get('alternatives'):
                st.markdown("**Conteos alternativos:**")
                for alt in aw['alternatives']:
                    st.warning(f"{alt['state']} - Conf {alt['confidence']:.0%}: {alt['reason']}")
        with tab6:
            render_history_tab()
        return result
```

- [ ] **Step 2: Añadir `render_history_tab()` (helper al final del archivo)**

```python
def render_history_tab():
    st.subheader("Historial de análisis")
    recs = analysis_history.recent_analyses(limit=50)
    if not recs:
        st.caption("Aún no hay análisis guardados. Cada análisis exitoso se guarda aquí automáticamente.")
        return
    hist_df = pd.DataFrame([{
        "Ticker": r["ticker"], "Fecha": r["timestamp"], "Score": r["score"],
        "Veredicto": r["veredicto"], "Precio": f"${r['precio']:.2f}",
        "RR": f"{r['rr']:.2f}" if r["rr"] else "-",
        "Dirección": r["direccion"], "Onda": r["estado_onda"],
        "id": r["id"],
    } for r in recs])
    st.dataframe(hist_df.drop(columns=["id"]), use_container_width=True, hide_index=True)
    opciones = {f'{r["ticker"]} | {r["timestamp"]} | Score {r["score"]:.0f} | {r["veredicto"]}': r["id"]
                for r in recs}
    sel = st.selectbox("Cargar un análisis previo", list(opciones.keys()))
    if st.button("Cargar y analizar", type="primary"):
        st.session_state.hist_load = opciones[sel]
        st.rerun()
```

- [ ] **Step 3: Integrar tema, badge y carga de historial en el script principal**

Al inicio del archivo (tras imports y `st.set_page_config`), en orden:

```python
import ui_theme
import analysis_history

analysis_history.ensure_table()

st.set_page_config(page_title="Trading Consultant", layout="wide", page_icon="📈")
ui_theme.inject_theme()
```

Header con badge de conexión (sustituye al `st.title`):

```python
st.markdown(
    '<div style="display:flex; align-items:center; gap:12px; margin-bottom:4px;">'
    '<h1 style="margin:0; font-size:1.7rem; letter-spacing:-0.02em;">Trading Consultant</h1>'
    f'{ui_theme.conn_badge_html(ibkr is not None and ibkr.connected, "Conectado" if ibkr and ibkr.connected else "No conectado")}'
    "</div>",
    unsafe_allow_html=True,
)
st.caption("Análisis multi-motor + operativa manual · IBKR")
```

Sustituir el bloque `analizar_btn` por:

```python
hist_load = st.session_state.pop("hist_load", None)
if hist_load is not None:
    rec = analysis_history.load_analysis(int(hist_load))
    if rec:
        ticker, period, bar_size, deviation = rec["ticker"], rec["period"], rec["bar_size"], rec["deviation"]

auto = st.session_state.pop("auto_analyze", False)
if analizar_btn or auto:
    if not ibkr or not ibkr.connected:
        st.error("Conéctate a IBKR primero (panel izquierdo).")
    else:
        try:
            result = render_analysis(ticker, period, bar_size, deviation, ibkr,
                                     show_ob, show_fvg, show_vp)
            if result:
                analysis_history.record_analysis(
                    ticker=result["summary"].get("ticker", ticker),
                    score=result["scoring"]["score"],
                    veredicto=result["scoring"]["veredicto"],
                    action=result["scoring"]["action"],
                    precio=result["summary"]["precio_actual"],
                    rr=result["risk"].get("rr1"),
                    direccion="bull" if result["active_wave"].get("is_bullish") is True
                              else ("bear" if result["active_wave"].get("is_bullish") is False else "neutral"),
                    estado_onda=result["active_wave"].get("state", "—"),
                    deviation=deviation, period=period, bar_size=bar_size,
                )
        except Exception as e:
            st.error(f"Error trayendo/analizando datos: {e}")
            st.exception(e)
```

Nota: `analizar_btn` es el widget del sidebar; se mantiene tal cual. Para que la carga desde el historial sea de un solo clic, el botón del tab6 establece `st.session_state["hist_load"]` Y `st.session_state["auto_analyze"] = True`, y en el rerun el script sobrescribe ticker/periodo/bar_size/deviation con los del snapshot y dispara el análisis automáticamente (`analizar_btn or auto`).

```python
if st.button("Cargar y analizar", type="primary"):
    st.session_state.hist_load = opciones[sel]
    st.session_state.auto_analyze = True
    st.rerun()
```

- [ ] **Step 4: Crear `scripts/smoke_test.py`** (verificación sin IBKR, datos sintéticos)

```python
"""
Smoke test sin IBKR: genera OHLCV sintético, corre el pipeline completo,
renderiza el HTML del resumen ejecutivo y guarda/recupera un registro de
historial. Verifica que las piezas nuevas (ui_theme + analysis_history)
funcionan de punta a punta con datos realistas.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

import analysis_history
import ui_theme
from pipeline import run_full_analysis


def synthetic_df(n=400, seed=7):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    idx = pd.date_range("2023-06-01", periods=n, freq="D")
    df = pd.DataFrame({
        "Open": close, "High": close + rng.uniform(0.1, 1.5, n),
        "Low": close - rng.uniform(0.1, 1.5, n), "Close": close,
        "Volume": rng.integers(1e4, 1e6, n),
    })
    df.index = idx
    return df


def main():
    # historial en DB temporal
    tmp = tempfile.mkdtemp()
    analysis_history.DB_PATH = os.path.join(tmp, "smoke.db")
    analysis_history.ensure_table()

    result = run_full_analysis(synthetic_df(), "SMK", 15.0, ibkr=None)

    html = ui_theme.exec_summary_html(result["scoring"], result["active_wave"],
                                      result["summary"], result["risk"])
    assert "exec-grid" in html, "resumen ejecutivo no se renderiza"

    rid = analysis_history.record_analysis(
        ticker="SMK", score=result["scoring"]["score"],
        veredicto=result["scoring"]["veredicto"], action=result["scoring"]["action"],
        precio=result["summary"]["precio_actual"], rr=result["risk"].get("rr1"),
        direccion="bull", estado_onda=result["active_wave"].get("state", "—"),
        deviation=15.0, period="2 Y", bar_size="1 day",
    )
    rec = analysis_history.load_analysis(rid)
    assert rec is not None and rec["ticker"] == "SMK", "roundtrip historial falló"
    assert len(analysis_history.recent_analyses()) == 1, "recent_analyses falló"

    print("SMOKE OK: pipeline:", result["scoring"]["score"], "| veredicto:", result["scoring"]["veredicto"],
          "| historial:", rec["id"])


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Ejecutar smoke test**

Run: `venv/bin/python scripts/smoke_test.py`
Expected: `SMOKE OK: pipeline: <score> | veredicto: <...> | historial: 1` (sin excepciones)

- [ ] **Step 6: Ejecutar todos los tests**

Run: `venv/bin/python -m unittest discover -s tests -v`
Expected: 10 PASS (4 ui_theme + 4 history + 2 chart)

- [ ] **Step 7: Commit**

```bash
git add dashboard_ibkr.py scripts/smoke_test.py
git commit -m "feat: integrate apple design exec summary and history tab"
```

---

### Task 5: Verificación final (arranque + lógica intacta)

**Files:**
- Ninguno (solo verificación)

- [ ] **Step 1: Arrancar la app headless y comprobar que no hay errores**

Run:
```bash
venv/bin/python -m streamlit run dashboard_ibkr.py --server.headless true --server.port 8599 &
sleep 12
curl -s -o /dev/null -w "%{http_code}" http://localhost:8599
```
Expected: `200` (y el proceso sin trazas de excepción en la salida)

- [ ] **Step 2: Verificar lógica intacta**

Run: `git diff HEAD~4 --stat -- pipeline.py elliott/ regime_detector.py momentum_engine.py smc_engine.py volume_profile.py mtf_analyzer.py scoring_engine.py risk_manager.py ibkr_connector.py`
Expected: sin salida (ningún motor tocado).

- [ ] **Step 3: Matar el servidor**

Run: `pkill -f "streamlit run dashboard_ibkr.py"` (o matar el PID capturado)

- [ ] **Step 4: Commit final**

```bash
git add -A
git commit -m "chore: final verification of apple design redesign"
```
(Solo si hay cambios pendientes; normalmente vacío.)
