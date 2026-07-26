"""
Dashboard IBKR - Análisis + Operativa MANUAL
=============================================
Trae histórico desde tu propia cuenta IBKR (via TWS/IB Gateway local), lo pasa
por el motor Elliott/Fibonacci, y te deja ver tu cartera real.

La parte de enviar órdenes está separada del análisis a propósito: el score o
la lectura de Elliott NUNCA disparan una orden. Solo tú, pulsando el botón y
marcando la casilla de confirmación, envías algo a IBKR.

Requiere TWS o IB Gateway abierto en tu Mac con la API habilitada.
"""
import streamlit as st
import sys
sys.path.append('.')
import pandas as pd
from elliott_trader_pro import ElliottFibonacciStrategy
from regime_detector import RegimeDetector
from momentum_engine import MomentumEngine
from smc_engine import SMCEngine
from volume_profile import VolumeProfileEngine
from mtf_analyzer import MTFAnalyzer
from scoring_engine import ScoringEngine
from risk_manager import RiskManager
from chart_engine_v4 import ChartEngineV4
from ibkr_connector import IBKRConnector

st.set_page_config(page_title="Dashboard IBKR", layout="wide")
st.title("Dashboard IBKR - Análisis + Operativa Manual")

# ---------------- Conexión ----------------
with st.sidebar:
    st.header("Conexión IBKR")
    host = st.text_input("Host", value="127.0.0.1") 
    # localhost, mas tarde lo haré como un sistema distribuido para conectar varias cuentas ajenas
    port = st.number_input("Puerto", value=4001, step=1,
                            help="4001 = Paper Trading | 4001 = Real | 4002/4001 = IB Gateway")
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
if analizar_btn:
    if not ibkr or not ibkr.connected:
        st.error("Conéctate a IBKR primero (panel izquierdo).")
    else:
        with st.spinner(f"Trayendo histórico de {ticker} desde IBKR y analizando en 6 motores..."):
            try:
                df = ibkr.get_historical_bars(ticker, duration=period, bar_size=bar_size)
                if df is None or len(df) < 30:
                    st.error("IBKR no devolvió suficientes datos. Revisa el ticker o el permiso de mercado de datos delayed.")
                else:
                    # 1. Elliott base (idéntico motor que app.py, pero con datos de IBKR)
                    engine = ElliottFibonacciStrategy(deviation_pct=deviation)
                    df, summary, _ = engine.analyze_dataframe(df, ticker, deviation=deviation)
                    st.session_state.last_summary = summary
                    aw = summary['active_wave']
                    pivots = engine.zigzag.get_pivots(df)  # recalculamos para SMC, igual que app.py

                    # 2. Mismos 6 motores que app.py (antes NO se ejecutaban aquí -> por
                    # eso faltaban soportes/resistencias y demás datos frente a app.py)
                    regime = RegimeDetector().analyze(df)
                    momentum = MomentumEngine().analyze(df)
                    smc = SMCEngine().analyze(df, pivots)
                    vol_prof = VolumeProfileEngine().analyze(df)
                    mtf = MTFAnalyzer().analyze(ticker, deviation=deviation, ibkr=ibkr)
                    risk = RiskManager().calculate(df, aw, smc, summary.get('fib_extensions', {}), summary['precio_actual'])
                    scoring = ScoringEngine().calculate(aw, regime, momentum, smc, vol_prof, mtf, summary['fib_levels'], summary['precio_actual'])

                    # 3. Veredicto principal
                    st.divider()
                    col_score, col_ver, col_conf = st.columns([1, 2, 1])
                    with col_score:
                        st.metric("SCORE CONFLUENCIA", f"{scoring['score']}/100", delta=f"{scoring['confidence_label']}")
                    with col_ver:
                        if scoring['action'] == "BUY":
                            st.success(f"### VEREDICTO: {scoring['veredicto']}")
                        elif scoring['action'] == "SELL":
                            st.error(f"### VEREDICTO: {scoring['veredicto']}")
                        else:
                            st.warning(f"### ⏸ VEREDICTO: {scoring['veredicto']}")
                        st.caption(f"Dirección Elliott: {'Alcista' if aw.get('is_bullish') else 'Bajista' if aw.get('is_bullish')==False else 'Neutral'} | Estado: {aw['state']} | Gap: {aw.get('gap',0)} velas")
                    with col_conf:
                        st.metric("Precio Actual (IBKR, delayed)", f"${summary['precio_actual']}", f"{risk['risk_pct']:.1f}% riesgo" if risk['risk_pct'] else "")
                        st.metric("RR", f"{risk['rr1']:.2f}" if risk['rr1'] else "-", "Válido" if risk['valid_rr'] else "Bajo")

                    if aw.get('is_stale'):
                        st.error(f"STALE: Impulso terminó hace {aw.get('gap')} velas. No operar, esperar nuevo 1-2.")
                    if not regime['tradeable']:
                        st.error(f"REGIMEN BLOQUEA: {regime['reason']}")

                    # 4. Gráfico Pro v4 (antes se usaba el ChartEngine viejo sin SMC/VP/Risk)
                    fig_v4 = ChartEngineV4.plot(df, ticker, summary['elliott_historico'], summary['fib_levels'], summary.get('fib_extensions', {}), aw, smc, vol_prof, risk, show_ob, show_fvg, show_vp)
                    st.plotly_chart(fig_v4, use_container_width=True)
                    st.caption(f"Razonamiento: {aw['reason']}")

                    # 5. Soportes (posible zona de compra) / Resistencias (objetivo o venta)
                    st.subheader("📐 Niveles clave: soportes y resistencias (Fibonacci sobre tramo activo)")
                    niveles = []
                    for k, v in summary['fib_levels'].items():
                        niveles.append({"tipo": "Retroceso", "nivel": f"{k*100:.1f}%", "precio": v})
                    for k, v in summary.get('fib_extensions', {}).items():
                        niveles.append({"tipo": "Extensión", "nivel": f"{k*100:.0f}%", "precio": v})

                    if niveles:
                        precio_actual = summary['precio_actual']
                        filas = []
                        for n in niveles:
                            dist_pct = (n["precio"] - precio_actual) / precio_actual * 100
                            if n["precio"] < precio_actual:
                                zona = "🟢 SOPORTE (posible compra)"
                            elif n["precio"] > precio_actual:
                                zona = "🔴 RESISTENCIA (objetivo / posible venta)"
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
                        st.caption("Soportes = posibles zonas de entrada en compra si el precio corrige hacia ahí. Resistencias = objetivos de toma de beneficio o posible zona de venta/cortocircuito.")
                    else:
                        st.info(f"Sin niveles Fibonacci calculados para el tramo activo actual (estado: {aw['state']}).")

                    # 6. Tabs de análisis (idénticos a app.py)
                    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Desglose Score", "Confluencia", "Riesgo", "MTF", "Elliott Detalle"])

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

        confirmo = st.checkbox(
            f"Confirmo que quiero enviar esta orden AHORA a {'PAPER' if int(port)==4001 else 'CUENTA REAL'} "
            f"({host}:{port})"
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
