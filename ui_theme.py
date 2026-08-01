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
