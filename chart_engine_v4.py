"""
Chart Engine v4 - Gráfico Pro con SMC, Volume Profile, Fibs, Elliott
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Dict, List

class ChartEngineV4:
    @staticmethod
    def plot(df: pd.DataFrame, ticker: str, elliott_result: Dict, fib_levels: Dict, 
             fib_extensions: Dict, active_wave: Dict, smc: Dict, volume_prof: Dict, 
             risk: Dict, show_ob=True, show_fvg=True, show_vp=True):

        # Figura con 2 filas: precio + RSI
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            row_heights=[0.8, 0.2], vertical_spacing=0.05,
                            subplot_titles=(f"{ticker} - {active_wave.get('state','')} | Score MTF", "RSI 14"))

        # Candles
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'], name="Precio",
            increasing_line_color='#30d158', decreasing_line_color='#ff453a'
        ), row=1, col=1)

        # SMAs
        if 'SMA_20' in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name="SMA 20", line=dict(color='#ff9f0a', width=1)), row=1, col=1)
        if 'SMA_50' in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], name="SMA 50", line=dict(color='#64d2ff', width=1.2)), row=1, col=1)
        if 'SMA_200' in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_200'], name="SMA 200", line=dict(color='#bf5af2', width=1.2, dash='dash')), row=1, col=1)

        # Onda activa resaltada
        if active_wave and active_wave.get('base_pivots'):
            bps = active_wave['base_pivots']
            for i in range(len(bps)-1):
                s_idx, s_price, _ = bps[i]
                e_idx, e_price, _ = bps[i+1]
                if s_idx < len(df) and e_idx < len(df):
                    fig.add_trace(go.Scatter(
                        x=[df.index[s_idx], df.index[e_idx]],
                        y=[s_price, e_price],
                        mode="lines+markers",
                        name=f"Elliott {i+1}",
                        line=dict(width=4, color='#30d158'),
                        marker=dict(size=10, color='#30d158'),
                        showlegend=False
                    ), row=1, col=1)
            # Línea a precio actual
            if len(bps)>0 and bps[-1][0] < len(df):
                last_bp = bps[-1]
                fig.add_trace(go.Scatter(
                    x=[df.index[last_bp[0]], df.index[-1]],
                    y=[last_bp[1], active_wave.get('current_price', last_bp[1])],
                    mode="lines",
                    name=f"En curso {active_wave['state']}",
                    line=dict(width=3, color='#ffd60a', dash='dash'),
                ), row=1, col=1)

        # Fib Retracements
        if fib_levels:
            for level, price in fib_levels.items():
                fig.add_hline(y=price, line_dash="dot", line_color="rgba(255,255,255,0.35)",
                              annotation_text=f"Ret {level*100:.1f}% {price:.2f}",
                              annotation_position="right", row=1, col=1)

        # Fib Extensions
        if fib_extensions:
            for ext, price in fib_extensions.items():
                fig.add_hline(y=price, line_dash="dash", line_color="rgba(255,214,10,0.8)",
                              annotation_text=f"Ext {ext*100:.0f}% {price:.2f}",
                              annotation_position="left", row=1, col=1)

        # SMC: Order Blocks
        if show_ob and smc.get('order_blocks'):
            for ob in smc['order_blocks']:
                color = "rgba(48,209,88,0.12)" if ob['type']=="BULL_OB" else "rgba(255,69,58,0.12)"
                # Buscar fecha
                try:
                    # ob date es string, lo convertimos a posición aproximada: usar últimos 60
                    # Para simplificar, dibujar como hline con ancho
                    fig.add_hrect(y0=ob['low'], y1=ob['high'], fillcolor=color, line_width=0,
                                  annotation_text=f"OB {ob['type'][-4:]}", annotation_position="top left",
                                  row=1, col=1)
                except Exception:
                    pass

        # SMC: FVGs
        if show_fvg and smc.get('fvg'):
            for fvg in smc['fvg']:
                color = "rgba(100,210,255,0.10)" if fvg['type']=="BULL_FVG" else "rgba(255,159,10,0.10)"
                try:
                    fig.add_hrect(y0=fvg['bottom'], y1=fvg['top'], fillcolor=color, line_width=0,
                                  annotation_text=f"FVG", annotation_position="bottom right",
                                  row=1, col=1)
                except Exception:
                    pass

        # Volume Profile POC
        if show_vp and volume_prof.get('poc'):
            poc = volume_prof['poc']
            fig.add_hline(y=poc, line_dash="solid", line_color="#64d2ff", line_width=2,
                          annotation_text=f"POC {poc:.2f}", annotation_position="left", row=1, col=1)
            if volume_prof.get('vah'):
                fig.add_hline(y=volume_prof['vah'], line_dash="dot", line_color="rgba(100,210,255,0.45)", row=1, col=1)
            if volume_prof.get('val'):
                fig.add_hline(y=volume_prof['val'], line_dash="dot", line_color="rgba(100,210,255,0.45)", row=1, col=1)

        # Risk: Entry, Stop, TPs
        if risk.get('entry'):
            fig.add_hline(y=risk['entry'], line_color="#f5f5f7", line_width=1.5,
                          annotation_text=f"ENTRY {risk['entry']:.2f}", row=1, col=1)
        if risk.get('stop'):
            fig.add_hline(y=risk['stop'], line_color="#ff453a", line_width=2,
                          annotation_text=f"STOP {risk['stop']:.2f} | {risk.get('stop_reason','')}", row=1, col=1)
        for tp in risk.get('tps',[])[:2]:
            fig.add_hline(y=tp['price'], line_color="#30d158", line_width=1.5, line_dash="dash",
                          annotation_text=f"{tp['level']} {tp['price']:.2f}", row=1, col=1)

        # RSI subplot
        # RSI lo calculamos rápido aquí si no viene
        try:
            closes = df['Close']
            delta = closes.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, 0.001)
            rsi = 100 - (100 / (1 + rs))
            fig.add_trace(go.Scatter(x=df.index, y=rsi, name="RSI", line=dict(color='#64d2ff')), row=2, col=1)
            fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)
            fig.add_hline(y=50, line_dash="dot", line_color="gray", row=2, col=1)
        except Exception:
            pass

        fig.update_layout(
            title=f"{ticker} - {active_wave.get('state','')} | Gap {active_wave.get('gap',0)} | Conf {active_wave.get('confidence',0):.0%}",
            xaxis_rangeslider_visible=False,
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#f5f5f7'),
            xaxis=dict(gridcolor='rgba(255,255,255,0.06)'),
            yaxis=dict(gridcolor='rgba(255,255,255,0.06)'),
            height=900,
            legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center"),
            yaxis_title="Precio $"
        )
        return fig
