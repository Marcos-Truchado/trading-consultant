import streamlit as st
import sys
sys.path.append('.')
from elliott_trader_pro import ElliottFibonacciStrategy
import pandas as pd

st.set_page_config(page_title="Elliott v4 Predictivo", layout="wide", page_icon="🔮")

st.title("🔮 Elliott v4 - Predictor de Siguiente Onda")

with st.sidebar:
    st.header("⚙️ Configuración")
    ticker = st.text_input("Ticker (ej: AAPL, NVDA, MSFT, TSLA)", value="AAPL").upper()
    period = st.selectbox("Periodo", ["1y", "2y", "5y", "max"], index=2)
    deviation = st.slider("Sensibilidad ZigZag %", 2.0, 25.0, 5.0, 0.5)
    st.markdown("---")
    run_btn = st.button("🚀 Predecir siguiente onda", type="primary", use_container_width=True)

if run_btn:
    with st.spinner(f"Analizando {ticker}... clasificando onda en curso"):
        try:
            engine = ElliottFibonacciStrategy(deviation_pct=deviation)
            df, summary, fig = engine.run(ticker, period=period, deviation=deviation)
            aw = summary['active_wave']
            
            # Métricas superiores
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Precio Actual", f"${summary['precio_actual']}")
            col2.metric("Onda en Curso", aw['state'], f"Conf {aw['confidence']:.0%}")
            col3.metric("Gap", f"{aw.get('gap',0)} velas", "STALE!" if aw.get('is_stale') else "Activo")
            col4.metric("Tendencia MA", summary['tendencia_MA'])
            col5.metric("Próximo Target", aw.get('next_target','-'))

            # Alerta STALE - tu bug reportado
            if aw.get('is_stale') or summary['elliott_historico'].get('is_stale'):
                st.error(f"⚠️ PATRÓN VIEJO DETECTADO: El mejor impulso 1-5 terminó hace {aw.get('gap', summary['elliott_historico'].get('gap'))} velas. Proyección vieja anclada a estructura irrelevante. No usar para trading. Esperar nuevo 1-2.")

            st.plotly_chart(fig, use_container_width=True)

            # Señal principal con confianza
            if "COMPRA" in summary['señal']:
                st.success(f"**Señal:** {summary['señal']} | Confianza {aw['confidence']:.0%} | {summary.get('señal_detalle','')}")
            elif "VENTA" in summary['señal']:
                st.error(f"**Señal:** {summary['señal']} | Confianza {aw['confidence']:.0%} | {summary.get('señal_detalle','')}")
            else:
                st.info(f"**Señal:** {summary['señal']} | Confianza {aw['confidence']:.0%} | {summary.get('señal_detalle','')}")

            st.markdown(f"**Razonamiento:** {aw['reason']}")
            if aw.get('is_bullish') is not None:
                st.markdown(f"**Dirección:** {'🟢 Alcista' if aw['is_bullish'] else '🔴 Bajista'}")

            c1, c2, c3 = st.columns(3)
            with c1:
                st.subheader(" Onda en Curso - Clasificador")
                st.json({
                    "state": aw['state'],
                    "confidence": f"{aw['confidence']:.1%}",
                    "gap_velas": aw.get('gap'),
                    "is_bullish": aw.get('is_bullish'),
                    "base_pivots": [(p[0], f"${p[1]:.2f}", p[2]) for p in aw.get('base_pivots',[])],
                    "next_target": aw.get('next_target'),
                    "is_stale": aw.get('is_stale', False)
                })
                if aw.get('alternatives'):
                    st.markdown("**Conteos alternativos (Elliott real tiene múltiples lecturas):**")
                    for alt in aw['alternatives']:
                        st.warning(f"{alt['state']} - Conf {alt['confidence']:.0%}: {alt['reason']}")

                st.subheader("📜 Histórico (para contexto, no para trading si STALE)")
                eh = summary['elliott_historico']
                st.write(f"Score: {eh.get('score')} | Gap: {eh.get('gap')} | Stale: {eh.get('is_stale')}")
                if eh.get('validation'):
                    for k,v in eh['validation'].items():
                        st.write(f"{'✅' if v else '❌'} {k}: {v}")

            with c2:
                st.subheader("📐 Fib Retrocesos (anclado a tramo ACTIVO)")
                st.caption("No a impulso viejo de hace 1 mes")
                if summary['fib_levels']:
                    fib_df = pd.DataFrame([{"Nivel": f"{k*100:.1f}%", "Precio": f"${v:.2f}", "Distancia": f"{(v-summary['precio_actual'])/summary['precio_actual']*100:+.2f}%"} for k,v in summary['fib_levels'].items()])
                    st.dataframe(fib_df, use_container_width=True)
                else:
                    st.info("Sin retrocesos para este estado (ej: formando W3 usa extensiones)")

            with c3:
                st.subheader("🎯 Fib Extensiones (anclado a tramo ACTIVO)")
                st.caption("Proyección de SIGUIENTE onda, no de onda pasada")
                if summary.get('fib_extensions'):
                    ext_df = pd.DataFrame([{"Ext": f"{k*100:.0f}%", "Objetivo": f"${v:.2f}", "Upside": f"{(v-summary['precio_actual'])/summary['precio_actual']*100:+.2f}%", "Conf": f"{aw['confidence']:.0%}"} for k,v in summary['fib_extensions'].items()])
                    st.dataframe(ext_df, use_container_width=True)
                    st.markdown(f"""
                    **Predicción v4:**
                    - Si estamos en **{aw['state']}**, y la lectura es correcta (conf {aw['confidence']:.0%}),
                    - El objetivo de **{aw.get('next_target')}** cae en rango Ext 1.272-1.618
                    - **Riesgo:** Si el conteo alternativo es válido, objetivo cambia
                    """)
                else:
                    st.warning("Sin extensiones - estado es correctivo, usar retrocesos")

            st.divider()
            st.code(f"""SMA20: {df['SMA_20'].iloc[-1]:.2f}
SMA50: {df['SMA_50'].iloc[-1]:.2f}
SMA200: {df['SMA_200'].iloc[-1]:.2f}
Último pivote: {summary.get('last_pivot',{})}
Activo: {aw['state']} gap {aw.get('gap')} velas conf {aw['confidence']:.0%}
""")

        except Exception as e:
            st.error(f"Error: {e}")
            st.exception(e)
else:
    st.image("https://upload.wikimedia.org/wikipedia/commons/0/0e/Elliott_wave_principle.png", caption="Elliott - ahora detectamos EN QUÉ ONDA ESTAMOS, no dónde estuvimos")
