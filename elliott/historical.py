"""Analizador de Elliott sobre pivotes HISTÓRICOS (mejor impulso 1-5 encontrado)."""
from typing import List, Tuple, Dict
import pandas as pd


class ElliottWaveAnalyzer:
    def analyze(self, pivots: List[Tuple[int, float, str]], df: pd.DataFrame) -> Dict:
        if len(pivots) < 6:
            return {"valid": False, "reason": "Pocos pivotes (<6) para formar 5 ondas", "waves": [], "pivots_used": []}

        recent = pivots[-12:]
        best_sequence = []
        best_score = -1
        best_report = {}

        for i in range(len(recent) - 5):
            seq = recent[i:i + 6]
            types = [p[2] for p in seq]
            if not self._is_alternating(types):
                continue
            score, report = self._score_impulse(seq)
            # Penalización por antigüedad: si termina muy atrás, baja score
            gap = (len(df) - 1) - seq[-1][0]
            stale_penalty = max(0, gap - 20) * 0.1
            adjusted_score = score - stale_penalty
            if adjusted_score > best_score:
                best_score = adjusted_score
                best_sequence = seq
                best_report = report
                best_report['gap_velas'] = gap
                best_report['is_stale'] = gap > 20

        if best_score < 0:
            return {"valid": False, "reason": "No se encontró patrón alternante", "waves": [], "pivots_used": []}

        waves = []
        for j in range(5):
            start_idx, start_price, _ = best_sequence[j]
            end_idx, end_price, _ = best_sequence[j + 1]
            waves.append({
                "num": j + 1,
                "start_idx": start_idx,
                "end_idx": end_idx,
                "start_price": start_price,
                "end_price": end_price,
                "change_pct": (end_price - start_price) / start_price * 100,
                "bars": end_idx - start_idx
            })

        return {
            "valid": best_score >= 2,
            "score": best_score,
            "validation": best_report,
            "waves": waves,
            "pivots_used": best_sequence,
            "gap": best_report.get('gap_velas', 0),
            "is_stale": best_report.get('is_stale', False)
        }

    def _is_alternating(self, types: List[str]) -> bool:
        return all(types[i] != types[i + 1] for i in range(len(types) - 1))

    def _score_impulse(self, seq: List[Tuple[int, float, str]]) -> Tuple[int, Dict]:
        p = [s[1] for s in seq]
        is_bull = p[0] < p[1]
        if not is_bull:
            p = [-x for x in p]

        w1 = p[1] - p[0]
        w3 = p[3] - p[2]
        w5 = p[5] - p[4]

        score = 0
        report = {}

        rule1 = p[2] > p[0]
        report["R1_Onda2_no_100%"] = rule1
        if rule1:
            score += 1

        rule2 = not (w3 < w1 and w3 < w5)
        report["R2_Onda3_no_mas_corta"] = rule2
        if rule2:
            score += 1

        rule3 = p[4] > p[1]
        report["R3_Onda4_no_solapa_Onda1"] = rule3
        if rule3:
            score += 1

        report["Onda3_extendida"] = w3 > w1 * 1.618
        report["Fib_Onda2"] = abs(p[2] - p[1]) / w1 if w1 != 0 else 0

        return score, report
