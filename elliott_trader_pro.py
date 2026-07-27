"""
CLI para probar el motor Elliott + Fibonacci sobre un ticker suelto,
sin levantar Streamlit.

La lógica real vive en el paquete elliott/ (data provider, zigzag,
clasificador de onda activa, Fibonacci). Este archivo se mantiene en la
raíz y con el mismo nombre solo para no romper el import que ya usan
pipeline.py y dashboard_ibkr.py:

    from elliott_trader_pro import ElliottFibonacciStrategy
"""
import argparse

from elliott import ElliottFibonacciStrategy
from chart_engine_v4 import ChartEngineV4

# Motores opcionales para el gráfico completo en modo --show / CLI.
# Si el CLI se usa solo, no hace falta que fallen: se usan dicts vacíos.
_EMPTY_SMC = {"order_blocks": [], "fvg": []}
_EMPTY_VOL = {}
_EMPTY_RISK = {}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Elliott + Fibonacci + MAs PREDICTIVO v3")
    parser.add_argument("--ticker", type=str, default="AAPL", help="Ticker ej: AAPL, NVDA, MSFT")
    parser.add_argument("--period", type=str, default="2y", help="1y, 2y, 5y, max")
    parser.add_argument("--deviation", type=float, default=5.0, help="% ZigZag")
    parser.add_argument("--show", action="store_true", help="Abrir gráfico")

    args = parser.parse_args()

    engine = ElliottFibonacciStrategy(deviation_pct=args.deviation)
    df, summary, _ = engine.run(args.ticker, period=args.period, deviation=args.deviation)

    print("\n" + "=" * 70)
    print(f" RESUMEN PREDICTIVO {summary['ticker']} - v3")
    print("=" * 70)
    aw = summary['active_wave']
    print(f"Precio: ${summary['precio_actual']} | MA: {summary['tendencia_MA']}")
    print(f"ONDA EN CURSO: {aw['state']} | Confianza: {aw['confidence']:.0%} | Gap: {aw.get('gap',0)} velas")
    print(f"Razón: {aw['reason']}")
    print(f"Alcista: {aw.get('is_bullish')} | Target: {aw.get('next_target')}")
    if aw.get('alternatives'):
        print("\nConteos alternativos (transparencia Elliott):")
        for alt in aw['alternatives']:
            print(f" - {alt['state']} Conf {alt['confidence']:.0%}: {alt['reason']}")
    print(f"\nSeñal: {summary['señal']}")
    print(f"Detalle: {summary['señal_detalle']}")
    print("\nHistórico:")
    print(f" Mejor impulso histórico gap: {summary['elliott_historico'].get('gap')} velas | Stale: {summary['elliott_historico'].get('is_stale')}")
    print("\nFib Retrocesos (anclado a tramo ACTIVO):")
    for lvl, price in summary['fib_levels'].items():
        print(f" {lvl*100:5.1f}% -> ${price:.2f}")
    print("\nFib Extensiones (anclado a tramo ACTIVO):")
    for ext, price in summary.get('fib_extensions', {}).items():
        print(f" {ext*100:.0f}% -> ${price:.2f}")

    if args.show:
        fig = ChartEngineV4.plot(
            df, args.ticker, summary['elliott_historico'], summary['fib_levels'],
            summary.get('fib_extensions', {}), aw, _EMPTY_SMC, _EMPTY_VOL, _EMPTY_RISK
        )
        fig.write_html(f"{args.ticker}_elliott_v3.html")
        print(f"\nGráfico guardado en {args.ticker}_elliott_v3.html (solo Elliott/Fib, sin SMC/Volume/Risk -- eso corre en el dashboard)")
