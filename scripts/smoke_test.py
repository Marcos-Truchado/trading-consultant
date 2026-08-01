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
    analysis_history._db.initialize(analysis_history.SqliteDatabase(
        os.path.join(tmp, "smoke.db")))
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
