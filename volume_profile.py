"""
Volume Profile Engine
POC, Value Area, y validación de Fibs
"""
import pandas as pd
import numpy as np
from typing import Dict

class VolumeProfileEngine:
    def __init__(self, bins=40):
        self.bins = bins

    def analyze(self, df: pd.DataFrame, lookback=200) -> Dict:
        df_slice = df.tail(lookback) if len(df) > lookback else df
        if 'Volume' not in df_slice.columns or df_slice['Volume'].sum() == 0:
            return {"poc": None, "vah": None, "val": None, "reason": "Sin volumen", "score_mod": 0, "confluence": []}

        price_min = df_slice['Low'].min()
        price_max = df_slice['High'].max()
        if price_min == price_max:
            return {"poc": float(price_min), "vah": None, "val": None, "reason": "Rango nulo", "score_mod": 0, "confluence": []}

        # Crear bins de precio
        bins = np.linspace(price_min, price_max, self.bins)
        vol_profile = np.zeros(len(bins)-1)

        # Para cada vela, distribuir volumen en el rango High-Low
        for _, row in df_slice.iterrows():
            low_idx = np.searchsorted(bins, row['Low'], side='left') - 1
            high_idx = np.searchsorted(bins, row['High'], side='left')
            low_idx = max(0, low_idx)
            high_idx = min(len(vol_profile), high_idx)
            if low_idx >= high_idx:
                continue
            # Distribución uniforme del volumen en ese rango (aprox)
            vol_per_bin = row['Volume'] / (high_idx - low_idx)
            vol_profile[low_idx:high_idx] += vol_per_bin

        # POC = bin con más volumen
        poc_idx = np.argmax(vol_profile)
        poc_price = (bins[poc_idx] + bins[poc_idx+1]) / 2

        # Value Area = 70% del volumen alrededor de POC
        total_vol = vol_profile.sum()
        target_vol = total_vol * 0.7
        # Expandir desde POC
        va_low = poc_idx
        va_high = poc_idx
        va_vol = vol_profile[poc_idx]
        while va_vol < target_vol and (va_low > 0 or va_high < len(vol_profile)-1):
            # expandir al lado con más volumen
            left_vol = vol_profile[va_low-1] if va_low > 0 else 0
            right_vol = vol_profile[va_high+1] if va_high < len(vol_profile)-1 else 0
            if left_vol >= right_vol and va_low > 0:
                va_low -= 1
                va_vol += vol_profile[va_low]
            elif va_high < len(vol_profile)-1:
                va_high += 1
                va_vol += vol_profile[va_high]
            else:
                break

        vah = (bins[va_high] + bins[va_high+1]) / 2 if va_high < len(bins)-1 else bins[-1]
        val = (bins[va_low] + bins[va_low+1]) / 2 if va_low < len(bins)-1 else bins[0]

        curr_price = float(df['Close'].iloc[-1])
        dist_poc = abs(curr_price - poc_price) / curr_price * 100

        # Score: si precio está cerca de POC, es zona de alta liquidez (buena para rebotes)
        score_mod = 0
        reason = f"POC ${poc_price:.2f} dist {dist_poc:.1f}% | VA {val:.2f}-{vah:.2f}"
        if dist_poc < 1.5:
            score_mod = 10
            reason += " - Precio en POC, alta confluencia"
        elif dist_poc < 3:
            score_mod = 5

        # Para confluencia con Fibs, se calculará en scoring_engine
        hist = [{"price": float((bins[i]+bins[i+1])/2), "vol": float(vol_profile[i])} for i in range(len(vol_profile))]

        return {
            "poc": float(poc_price),
            "vah": float(vah),
            "val": float(val),
            "dist_poc_pct": float(dist_poc),
            "histogram": hist,
            "score_mod": score_mod,
            "reason": reason,
            "confluence": []
        }
