"""
Dashboard IBKR - Análisis + Operativa MANUAL
=============================================
Trae histórico desde tu propia cuenta IBKR (via TWS/IB Gateway local), lo pasa
por el pipeline de análisis (pipeline.run_full_analysis), y te deja ver tu
cartera real.

La parte de enviar órdenes está separada del análisis a propósito: el score o
la lectura de Elliott NUNCA disparan una orden. Solo tú, pulsando el botón y
marcando la casilla de confirmación, envías algo a IBKR.

Requiere TWS o IB Gateway abierto en tu Mac con la API habilitada.
"""
import streamlit as st
import sys
sys.path.append('.')
import pandas as pd
from pipeline import run_full_analysis
from chart_engine_v4 import ChartEngineV4
from ibkr_connector import IBKRConnector
import ui_theme
import analysis_history

analysis_history.ensure_table()

st.set_page_config(page_title="Trading Consultant", layout="wide", page_icon="📈")
ui_theme.inject_theme()

# Puertos estándar de IBKR. OJO: en IB Gateway 4001 es la cuenta REAL y 4002
# es paper -- justo al revés de lo que uno esperaría. Antes el dashboard
# asumía "4001 = Paper" en el texto de ayuda y en la casilla de confirmación
# de la orden, lo cual era falso y podía hacer pensar que estabas en paper
# estando en real. Se corrige mapeando el puerto explícitamente.
IBKR_PORT_LABELS = {
    7497: "TWS - Paper Trading",
    7496: "TWS - Cuenta REAL",
    4002: "IB Gateway - Paper Trading",
    4001: "IB Gateway - Cuenta REAL",
}


def port_label(port: int) -> str:
    return IBKR_PORT_LABELS.get(int(port), "Puerto no reconocido - verifica en TWS/Gateway si es Paper o Real")


def is_live_port(port: int) -> bool:
    return int(port) in (7496, 4001)


def render_analysis(ticker: str, period: str, bar_size: str, deviation: float, ibkr, show_ob, show_fvg, show_vp):
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
        df = result["df"]
        summary = result["summary"]
        aw = result["active_wave"]
        regime = result["regime"]
        momentum = result["momentum"]
        smc = result["smc"]
        vol_prof = result["vol_prof"]
        mtf = result["mtf"]
        risk = result["risk"]
        scoring = result["scoring"]
        st.session_state.last_summary = summary

        # Resumen ejecutivo estilo Apple
        summary["regime_block"] = regime["reason"] if not regime["tradeable"] else None
        st.markdown(ui_theme.exec_summary_html(scoring, aw, summary, risk), unsafe_allow_html=True)

        # Gráfico Pro v4
        fig_v4 = ChartEngineV4.plot(df, ticker, summary['elliott_historico'], summary['fib_levels'], summary.get('fib_extensions', {}), aw, smc, vol_prof, risk, show_ob, show_fvg, show_vp)
        st.plotly_chart(fig_v4, use_container_width=True)
        st.caption(f"Razonamiento: {aw['reason']}")

        # Soportes (posible zona de compra) / Resistencias (objetivo o venta)
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
                filas.append({
                    "Zona": zona,
                    "Tipo Fib": n["tipo"],
                    "Nivel": n["nivel"],
                    "Precio": f"${n['precio']:.2f}",
                    "Distancia": f"{dist_pct:+.2f}%",
                    "_dist_abs": abs(dist_pct),
                })
            filas.sort(key=lambda r: r["_dist_abs"])
            for f in filas:
                del f["_dist_abs"]
            niveles_df = pd.DataFrame(filas)
            st.dataframe(niveles_df, use_container_width=True, hide_index=True)
            st.caption("Los niveles se etiquetan según la dirección que ya detectó Elliott (arriba), no solo por estar por encima o debajo del precio: un nivel 'a favor' es soporte/resistencia operable, uno 'en contra' es solo estructura a vigilar.")
        else:
            st.info(f"Sin niveles Fibonacci calculados para el tramo activo actual (estado: {aw['state']}).")

        # Tabs de análisis
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
            st.json({
                "state": aw['state'],
                "confidence": f"{aw['confidence']:.1%}",
                "gap": aw.get('gap'),
                "is_bullish": aw.get('is_bullish'),
                "reason": aw['reason'],
                "next_target": aw.get('next_target'),
                "is_stale": aw.get('is_stale', False)
            })
            if aw.get('alternatives'):
                st.markdown("**Conteos alternativos:**")
                for alt in aw['alternatives']:
                    st.warning(f"{alt['state']} - Conf {alt['confidence']:.0%}: {alt['reason']}")

        with tab6:
            render_history_tab()

        return result


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
        st.session_state.auto_analyze = True
        st.rerun()


# ---------------- Conexión ----------------
with st.sidebar:
    st.header("Conexión IBKR")
    host = st.text_input("Host", value="127.0.0.1")
    # localhost, mas tarde lo haré como un sistema distribuido para conectar varias cuentas ajenas
    port = st.number_input("Puerto", value=7497, step=1,
                            help="TWS: 7497 Paper / 7496 Real  |  IB Gateway: 4002 Paper / 4001 Real")
    st.caption(f"Detectado: **{port_label(port)}**")
    if is_live_port(port):
        st.warning("⚠️ Este puerto es de CUENTA REAL, no paper trading.")
    client_id = st.number_input("Client ID", value=1, step=1)

    if "ibkr" not in st.session_state:
        st.session_state.ibkr = None

    if st.button("Conectar", type="primary", use_container_width=True):
        conn = IBKRConnector(host=host, port=int(port), client_id=int(client_id))
        result = conn.connect()
        if result["ok"]:
            st.session_state.ibkr = conn
            st.success(result["msg"])
        else:
            st.session_state.ibkr = None
            st.error(result["msg"])

    if st.session_state.ibkr and st.session_state.ibkr.connected:
        st.success("Conectado")
        if st.button("Desconectar", use_container_width=True):
            st.session_state.ibkr.disconnect()
            st.session_state.ibkr = None
            st.rerun()
    else:
        st.warning("No conectado")

    st.markdown("---")
    ticker = st.text_input("Ticker", value="ONDS").upper()
    period = st.selectbox("Periodo", ["6 M", "1 Y", "2 Y", "5 Y"], index=2)
    bar_size = st.selectbox("Vela", ["1 day", "4 hours", "1 hour"], index=0)
    deviation = st.slider("Sensibilidad ZigZag %", 2.0, 25.0, 15.0, 0.5)
    st.markdown("### Capas visuales")
    show_ob = st.checkbox("Mostrar Order Blocks", value=True)
    show_fvg = st.checkbox("Mostrar Fair Value Gaps", value=True)
    show_vp = st.checkbox("Mostrar Volume Profile POC", value=True)
    analizar_btn = st.button("Analizar desde IBKR", use_container_width=True)

ibkr: IBKRConnector = st.session_state.get("ibkr")

# Header principal con badge de estado de conexión
st.markdown(
    '<div style="display:flex; align-items:center; gap:12px; margin-bottom:4px;">'
    '<h1 style="margin:0; font-size:1.7rem; letter-spacing:-0.02em;">Trading Consultant</h1>'
    f'{ui_theme.conn_badge_html(ibkr is not None and ibkr.connected, "Conectado" if ibkr and ibkr.connected else "No conectado")}'
    "</div>",
    unsafe_allow_html=True,
)
st.caption("Análisis multi-motor + operativa manual · IBKR")

# ---------------- Cuenta real ----------------
if ibkr and ibkr.connected:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Cuenta")
        try:
            summary = ibkr.get_account_summary()
            for k, v in summary.items():
                st.metric(k, f"${float(v):,.2f}")
        except Exception as e:
            st.info(f"Sin datos de cuenta todavía ({e})")
    with col2:
        st.subheader("Posiciones")
        try:
            positions = ibkr.get_positions()
            if positions:
                st.dataframe(positions, use_container_width=True)
            else:
                st.caption("Sin posiciones abiertas")
        except Exception as e:
            st.info(f"Sin datos de posiciones todavía ({e})")

st.divider()

# ---------------- Análisis con datos de IBKR ----------------
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

st.divider()

# ---------------- Operativa MANUAL ----------------
st.subheader("Enviar orden manual")
st.caption(
    "Esto no lee el score ni la señal de Elliott para decidir nada. "
    "Rellenas tú los campos y confirmas tú. Nada se envía solo."
)

if not ibkr or not ibkr.connected:
    st.info("Conéctate a IBKR para poder enviar órdenes.")
else:
    with st.form("orden_manual"):
        oc1, oc2, oc3, oc4 = st.columns(4)
        o_ticker = oc1.text_input("Ticker", value=ticker)
        o_action = oc2.selectbox("Acción", ["BUY", "SELL"])
        o_qty = oc3.number_input("Cantidad", min_value=1, value=1, step=1)
        o_type = oc4.selectbox("Tipo", ["Market", "Limit"])

        o_limit_price = None
        if o_type == "Limit":
            o_limit_price = st.number_input("Precio límite", min_value=0.01, value=1.0, step=0.01)

        modo_cuenta = "⚠️ CUENTA REAL" if is_live_port(port) else "PAPER"
        confirmo = st.checkbox(
            f"Confirmo que quiero enviar esta orden AHORA a {modo_cuenta} "
            f"({port_label(port)}, {host}:{port})"
        )
        enviar = st.form_submit_button("Enviar orden", type="primary", disabled=not confirmo)

        if enviar and confirmo:
            try:
                if o_type == "Market":
                    result = ibkr.place_market_order(o_ticker, o_action, int(o_qty))
                else:
                    result = ibkr.place_limit_order(o_ticker, o_action, int(o_qty), float(o_limit_price))
                st.success(f"Orden enviada. Estado: {result['status']} | ID: {result['order_id']}")
            except Exception as e:
                st.error(f"Error enviando orden: {e}")

