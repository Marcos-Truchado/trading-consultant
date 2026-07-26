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
from elliott_trader_pro import ElliottFibonacciStrategy
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
        with st.spinner(f"Trayendo histórico de {ticker} desde IBKR..."):
            try:
                df = ibkr.get_historical_bars(ticker, duration=period, bar_size=bar_size)
                if df is None or len(df) < 30:
                    st.error("IBKR no devolvió suficientes datos. Revisa el ticker o el permiso de mercado de datos delayed.")
                else:
                    engine = ElliottFibonacciStrategy(deviation_pct=deviation)
                    _, summary, fig = engine.analyze_dataframe(df, ticker, deviation=deviation)
                    st.session_state.last_summary = summary
                    aw = summary['active_wave']

                    c1, c2, c3 = st.columns(3)
                    c1.metric("Precio actual (IBKR, delayed)", f"${summary['precio_actual']}")
                    c2.metric("Onda en curso", aw['state'], f"Conf {aw['confidence']:.0%}")
                    c3.metric("Señal", summary['señal'])

                    st.plotly_chart(fig, use_container_width=True)
                    st.caption(f"Razonamiento: {aw['reason']}")
            except Exception as e:
                st.error(f"Error trayendo/analizando datos: {e}")

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
