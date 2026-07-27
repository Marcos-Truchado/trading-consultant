"""Detector de pivotes ZigZag (base para clasificar ondas de Elliott)."""
from typing import List, Tuple
import pandas as pd


class ZigZagDetector:
    def __init__(self, deviation_pct: float = 5.0):
        self.deviation = deviation_pct / 100.0

    def get_pivots(self, df: pd.DataFrame) -> List[Tuple[int, float, str]]:
        closes = df['Close'].values
        pivots = []

        last_pivot_idx = 0
        last_pivot_price = closes[0]
        trend = 0

        for i in range(1, len(closes)):
            price = closes[i]
            change = (price - last_pivot_price) / last_pivot_price

            if trend == 0:
                if abs(change) >= self.deviation:
                    trend = 1 if change > 0 else -1
                    pivots.append((0, closes[0], 'L' if trend == 1 else 'H'))
                    last_pivot_idx = i
                    last_pivot_price = price
            elif trend == 1:
                if price > last_pivot_price:
                    last_pivot_idx = i
                    last_pivot_price = price
                elif (last_pivot_price - price) / last_pivot_price >= self.deviation:
                    pivots.append((last_pivot_idx, last_pivot_price, 'H'))
                    trend = -1
                    last_pivot_idx = i
                    last_pivot_price = price
            else:
                if price < last_pivot_price:
                    last_pivot_idx = i
                    last_pivot_price = price
                elif (price - last_pivot_price) / last_pivot_price >= self.deviation:
                    pivots.append((last_pivot_idx, last_pivot_price, 'L'))
                    trend = 1
                    last_pivot_idx = i
                    last_pivot_price = price

        if len(pivots) > 0 and last_pivot_idx != pivots[-1][0]:
            pivots.append((last_pivot_idx, last_pivot_price, 'H' if trend == 1 else 'L'))

        return pivots
