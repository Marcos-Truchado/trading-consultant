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
        # la figura debe construirse sin error, con template dark y fondo transparente
        self.assertEqual(fig.layout.template.layout.paper_bgcolor, "rgb(17,17,17)")
        self.assertEqual(fig.layout.paper_bgcolor, "rgba(0,0,0,0)")
        self.assertEqual(fig.layout.plot_bgcolor, "rgba(0,0,0,0)")


if __name__ == "__main__":
    unittest.main()
