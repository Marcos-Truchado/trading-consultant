import streamlit as st
import sys
sys.path.append('.')
from elliott_trader_pro import ElliottFibonacciStrategy
from regime_detector import RegimeDetector
from momentum_engine import MomentumEngine
from smc_engine import SMCEngine
from volume_profile import VolumeProfileEngine
from mtf_analyzer import MTFAnalyzer
from scoring_engine import ScoringEngine
from risk_manager import RiskManager
from chart_engine_v4 import ChartEngineV4
import pandas as pd

st.set_page_config(page_title="Elliott v4 Cockpit", layout="wide", page_icon="🧠")

st.markdown("**No es un bot. Es tu copiloto: metes un ticker y te dice si comprar/vender/HOLD con score 0-100, confluencias y riesgo calculado.**")

with st.sidebar:
    st.header("⚙️ Configuración")
    ticker = st.text_input("Ticker (ej: AAPL, NVDA, MSFT, TSLA, WYFI)", value="AAPL").upper()
    period = st.selectbox("Periodo base (Diario)", ["1y", "2y", "5y", "max"], index=1)
    deviation = st.slider("Sensibilidad ZigZag %", 2.0, 25.0, 5.0, 0.5)
    st.markdown("### Capas visuales")
    show_ob = st.checkbox("Mostrar Order Blocks", value=True)
    show_fvg = st.checkbox("Mostrar Fair Value Gaps", value=True)
    show_vp = st.checkbox("Mostrar Volume Profile POC", value=True)
    st.markdown("---")
    st.caption("v4 Novedades:\n- Regime Filter (ADX/Chop)\n- SMC BOS/CHOCH/FVG/OB\n- Volume Profile POC/VA\n- RSI Divergence\n- MTF 1W/1D/4H/1H\n- Score 0-100\n- Risk Engine")
    run_btn = st.button("🚀 Analizar ticker", type="primary", use_container_width=True)

if run_btn:
    with st.spinner(f"Analizando {ticker} en 6 motores..."):
        try:
            # 1. Elliott base (tu v3)
            engine = ElliottFibonacciStrategy(deviation_pct=deviation)
            df, summary, _ = engine.run(ticker, period=period, deviation=deviation)
            aw = summary['active_wave']
            pivots = engine.zigzag.get_pivots(df)  # recalculamos para SMC

            # 2. Nuevos motores
            regime = RegimeDetector().analyze(df)
            momentum = MomentumEngine().analyze(df)
            smc = SMCEngine().analyze(df, pivots)
            vol_prof = VolumeProfileEngine().analyze(df)
            mtf = MTFAnalyzer().analyze(ticker, deviation=deviation)
            risk = RiskManager().calculate(df, aw, smc, summary.get('fib_extensions',{}), summary['precio_actual'])
            scoring = ScoringEngine().calculate(aw, regime, momentum, smc, vol_prof, mtf, summary['fib_levels'], summary['precio_actual'])

            # 3. Veredicto principal 
            # METER COLORES (queda mas claro, no me se el comando de streamlit para poner color a texto)
            st.divider()
            col_score, col_ver, col_conf = st.columns([1,2,1])
            with col_score:
                st.metric("SCORE CONFLUENCIA", f"{scoring['score']}/100", delta=f"{scoring['confidence_label']}")
            with col_ver:
                if scoring['action'] == "BUY":
                    st.success(f"### VEREDICTO: {scoring['veredicto']}")
                elif scoring['action'] == "SELL":
                    st.error(f"### VEREDICTO: {scoring['veredicto']}")
                else:
                    st.warning(f"### ⏸VEREDICTO: {scoring['veredicto']}")
                st.caption(f"Dirección Elliott: {'Alcista' if aw.get('is_bullish') else 'Bajista' if aw.get('is_bullish')==False else 'Neutral'} | Estado: {aw['state']} | Gap: {aw.get('gap',0)} velas")
            with col_conf:
                st.metric("Precio Actual", f"${summary['precio_actual']}", f"{risk['risk_pct']:.1f}% riesgo" if risk['risk_pct'] else "")
                st.metric("RR", f"{risk['rr1']:.2f}" if risk['rr1'] else "-", "Válido" if risk['valid_rr'] else "Bajo")

            if aw.get('is_stale'):
                st.error(f"STALE: Impulso terminó hace {aw.get('gap')} velas. No operar, esperar nuevo 1-2.")
            if not regime['tradeable']:
                st.error(f"REGIMEN BLOQUEA: {regime['reason']}")

            # 4. Gráfico Pro v4
            fig_v4 = ChartEngineV4.plot(df, ticker, summary['elliott_historico'], summary['fib_levels'], summary.get('fib_extensions',{}), aw, smc, vol_prof, risk, show_ob, show_fvg, show_vp)
            st.plotly_chart(fig_v4, use_container_width=True)

            # 5. Tabs de análisis
            tab1, tab2, tab3, tab4, tab5 = st.tabs([" Desglose Score", "Confluencia", "Riesgo", "MTF", "Elliott Detalle"])

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
                    st.json({k: v for k,v in momentum.items() if k not in ['rsi_series','macd_hist_series']})
                with colB:
                    st.subheader("SMC - Smart Money")
                    st.write(f"**BOS/CHOCH:** {smc['bos_choch']['reason']}")
                    st.json(smc['bos_choch'])
                    st.write(f"**Liquidity Sweep:** {smc['liquidity_sweep']['reason']}")
                    st.json(smc['liquidity_sweep'])
                with colC:
                    st.subheader("Volume Profile")
                    st.json({k:v for k,v in vol_prof.items() if k!='histogram'})
                    if vol_prof.get('histogram'):
                        st.caption(f"POC es donde más volumen se negoció en últimos 200 días. Si coincide con Fib 61.8% = soporte/resistencia institucional.")
                    st.subheader("Order Blocks & FVGs")
                    st.write("OBs activos:", smc['order_blocks'])
                    st.write("FVGs activos:", smc['fvg'])

            with tab3:
                st.subheader("Plan de trade (no es ejecución, es análisis)")
                c1,c2,c3,c4 = st.columns(4)
                c1.metric("Entry", f"${risk['entry']:.2f}")
                c2.metric("Stop Loss", f"${risk['stop']:.2f}" if risk['stop'] else "-", risk['stop_reason'])
                if risk['tps']:
                    c3.metric("TP1", f"${risk['tps'][0]['price']:.2f}", f"RR {risk['rr1']:.2f}" if risk['rr1'] else "")
                    if len(risk['tps'])>1:
                        c4.metric("TP2", f"${risk['tps'][1]['price']:.2f}", f"RR {risk['rr2']:.2f}" if risk['rr2'] else "")
                st.divider()
                if not risk['valid_rr']:
                    st.warning(f"⚠️ RR {risk['rr1']:.2f if risk['rr1'] else 0} bajo (<1.2). Aunque el score sea bueno, el trade no compensa riesgo. Busca entrada más cercana a invalidación.")
                else:
                    st.success(f"✅ RR válido {risk['rr1']:.2f} | Riesgo {risk['risk_pct']:.1f}% del precio al stop")

                st.markdown("**Fibs ancladas a tramo ACTIVO (fix v4):**")
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    if summary['fib_levels']:
                        fib_df = pd.DataFrame([{"Nivel": f"{k*100:.1f}%", "Precio": f"${v:.2f}", "Dist": f"{(v-summary['precio_actual'])/summary['precio_actual']*100:+.2f}%"} for k,v in summary['fib_levels'].items()])
                        st.dataframe(fib_df, use_container_width=True)
                with col_f2:
                    if summary.get('fib_extensions'):
                        ext_df = pd.DataFrame([{"Ext": f"{k*100:.0f}%", "Precio": f"${v:.2f}", "Upside": f"{(v-summary['precio_actual'])/summary['precio_actual']*100:+.2f}%"} for k,v in summary['fib_extensions'].items()])
                        st.dataframe(ext_df, use_container_width=True)

            with tab4:
                st.subheader("Multi-Timeframe Alignment")
                st.json(mtf)
                # Tabla visual
                mtf_df = pd.DataFrame([{"TF": k, "Trend": v['trend'], "Score": v['score'], "SMA20": v.get('sma20','-'), "SMA200": v.get('sma200','-')} for k,v in mtf['timeframes'].items()])
                st.dataframe(mtf_df, use_container_width=True)
                if mtf['alignment'] == "BULL_ALIGNED":
                    st.success("Tdos los timeframes alineados alcistas - alta probabilidad si score diario también es BUY")
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
                    "base_pivots": [(p[0], f"${p[1]:.2f}", p[2]) for p in aw.get('base_pivots',[])],
                    "next_target": aw.get('next_target'),
                    "is_stale": aw.get('is_stale', False)
                })
                if aw.get('alternatives'):
                    st.markdown("**Conteos alternativos:**")
                    for alt in aw['alternatives']:
                        st.warning(f"{alt['state']} - Conf {alt['confidence']:.0%}: {alt['reason']}")

            st.divider()
        except Exception as e:
            st.error(f"Error: {e}")
            st.exception(e)
else:
    st.info("👈 Configura ticker y dale a Analizar. Ejemplo: prueba con AAPL, NVDA, TSLA")
    st.markdown("""

    **6 motores nuevos:**
    1. **Regime Detector**: ADX + Choppiness. Si está lateral, te bloquea.
    2. **Momentum Engine**: RSI Divergence. Detecta onda 5 fallida.
    3. **SMC Engine**: BOS/CHOCH, Order Blocks, FVGs, Liquidity Sweeps. Dibuja donde está el dinero inteligente.
    4. **Volume Profile**: POC + Value Area. Valida si tu Fib coincide con zona institucional.
    5. **MTF Analyzer**: 1W/1D/4H/1H alineación. No compras si diario alcista pero semanal bajista.
    6. **Scoring + Risk**: Score 0-100 explicable + Entry/SL/TP y RR.

    **Resultado:** Pasas de `Señal: COMPRA TEMPRANA` a `BUY 82/100 - W3 conf 75% + BOS alcista + RSI sin divergencia + POC coincide + MTF alineado | Entry $182.3 SL $175.1 RR 2.4`
    """)
