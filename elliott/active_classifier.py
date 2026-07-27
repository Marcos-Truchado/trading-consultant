"""
Clasificador de onda EN CURSO (no histórica).

Mira los últimos 2-3 pivotes incluyendo el último y decide en qué onda
estamos AHORA. Resuelve el bug de anclar proyecciones (Fibonacci, targets)
a estructuras viejas ya terminadas.
"""
from typing import List, Tuple, Dict


class ActiveWaveClassifier:

    def _find_correction_extreme(self, pivots: List[Tuple[int, float, str]], p1_pos: int):
        """
        A partir de la posición de p1 (fin de la onda de impulso), recorre los
        pivotes siguientes del lado contrario y devuelve el más extremo de todos.

        Esto es lo que faltaba: antes se asumía que la onda 2/4 era un único
        pivote en V (p2 = pivots[-1], sin más). Si la corrección es compleja
        (W-X-Y, varias piernas), ese primer rebote es X, no el fin real de la
        corrección (Y) -- y todo lo que se ancla a ese punto (Fibonacci,
        target de onda 3) sale mal.

        Si en el camino aparece un pivote del MISMO lado que p1 que rompe ese
        nivel, la onda de impulso original queda invalidada (ya no hay techo/
        suelo válido de onda 1) y se descarta la hipótesis.
        """
        p1 = pivots[p1_pos]
        correction_side = 'L' if p1[2] == 'H' else 'H'
        same_side = p1[2]
        extreme = None
        correction_pivots = []
        for p in pivots[p1_pos + 1:]:
            if p[2] == correction_side:
                correction_pivots.append(p)
                if extreme is None or (p[1] < extreme[1] if correction_side == 'L' else p[1] > extreme[1]):
                    extreme = p
            else:
                invalidated = (p[1] > p1[1]) if same_side == 'H' else (p[1] < p1[1])
                if invalidated:
                    return None, []
        return extreme, correction_pivots

    def classify(self, pivots: List[Tuple[int, float, str]], current_price: float, current_idx: int) -> Dict:
        if len(pivots) < 2:
            return self._unknown("Pocos pivotes")

        last_pivot = pivots[-1]
        gap = current_idx - last_pivot[0]
        hypotheses = []

        def is_alternating(seq):
            return all(seq[i][2] != seq[i + 1][2] for i in range(len(seq) - 1))

        # ---- HIPÓTESIS 1: FORMANDO ONDA 3 (onda 2 simple o compleja W-X-Y) ----
        # Se prueba cada posible "fin de onda 1" (p1) en la ventana reciente y,
        # para cada uno, se busca el extremo real de la corrección posterior
        # con _find_correction_extreme -- sea de 1 pivote (ABC en V) o de
        # varios (W-X-Y). Genera una hipótesis por candidato válido.
        window = pivots[-10:] if len(pivots) >= 10 else pivots
        offset = len(pivots) - len(window)
        for i in range(len(window) - 1):
            p1_pos = offset + i
            if p1_pos == 0:
                continue
            p0 = pivots[p1_pos - 1]
            p1 = pivots[p1_pos]
            if p0[2] == p1[2]:
                continue

            is_bull = p0[2] == 'L' and p1[2] == 'H'
            is_bear = p0[2] == 'H' and p1[2] == 'L'
            if not (is_bull or is_bear):
                continue

            p2, correction_pivots = self._find_correction_extreme(pivots, p1_pos)
            if p2 is None:
                continue

            w1 = abs(p1[1] - p0[1])
            w2 = abs(p1[1] - p2[1])
            ratio = w2 / w1 if w1 != 0 else 0

            # Onda 2 no puede superar el 100% de la onda 1 (si no, invalida el conteo).
            # Rango 0.236-1.0 (más abierto que una V simple porque una W-X-Y
            # compleja retrocede con más libertad).
            not_broken = (p2[1] > p0[1]) if is_bull else (p2[1] < p0[1])
            if not (0.236 <= ratio <= 1.0 and not_broken):
                continue

            gap_p2 = current_idx - p2[0]
            bounce = (current_price - p2[1]) / p2[1] * 100 if is_bull else (p2[1] - current_price) / p2[1] * 100
            if bounce <= -2:
                continue  # el precio siguió rompiendo: esto ya no es la onda 2

            fib_score = 1 - abs(ratio - 0.618) / 0.618
            recency = max(0.2, 1 - gap_p2 / 60)
            is_complex = len(correction_pivots) > 1
            # Las correcciones complejas son más ambiguas de leer con solo zigzag,
            # así que arrancan con algo menos de confianza que una simple en V
            complexity_penalty = 0.1 if is_complex else 0
            conf = max(0.1, min(0.95, (0.5 + fib_score * 0.5) * recency - complexity_penalty))

            label = "W-X-Y / corrección compleja" if is_complex else "onda 2 simple"
            hypotheses.append({
                "state": "FORMING_WAVE_3",
                "is_bullish": is_bull,
                "base_pivots": [p0, p1] + correction_pivots,
                "w1_start": p0,
                "w1_end": p1,
                "w2_end": p2,
                "correction_pivots": correction_pivots,
                "is_complex_correction": is_complex,
                "confidence": conf,
                "gap": gap_p2,
                "reason": f"1-2 confirmado ({label}, retra {ratio:.1%}), gap {gap_p2} velas, bounce {bounce:+.1f}%",
                "next_target": "Onda 3",
                "alternatives": []
            })

        # ---- HIPÓTESIS 2: FORMANDO ONDA 4 (tenemos 1-2-3) ----
        if len(pivots) >= 4:
            p0, p1, p2, p3 = pivots[-4], pivots[-3], pivots[-2], pivots[-1]
            if is_alternating([p0, p1, p2, p3]):
                is_bull = p0[2] == 'L'
                if (is_bull and p3[1] > p1[1] and p2[1] > p0[1]) or (not is_bull and p3[1] < p1[1] and p2[1] < p0[1]):
                    w1 = abs(p1[1] - p0[1])
                    w3 = abs(p3[1] - p2[1])
                    if w3 > w1 * 0.8:  # Onda 3 no es la más corta
                        recency = max(0.2, 1 - gap / 60)
                        conf = 0.65 * recency
                        hypotheses.append({
                            "state": "FORMING_WAVE_4",
                            "is_bullish": is_bull,
                            "base_pivots": [p0, p1, p2, p3],
                            "w3_start": p2,
                            "w3_end": p3,
                            "confidence": conf,
                            "gap": gap,
                            "reason": f"Onda 3 terminada ({w3:.2f} vs W1 {w1:.2f}), en corrección W4, gap {gap}",
                            "next_target": "Onda 4 (38-50% de W3)"
                        })

        # ---- HIPÓTESIS 3: FORMANDO ONDA 5 (tenemos 1-2-3-4) ----
        if len(pivots) >= 5:
            p0, p1, p2, p3, p4 = pivots[-5:]
            if is_alternating(pivots[-5:]):
                is_bull = p0[2] == 'L'
                # Regla 3: Onda 4 no solapa Onda 1
                no_overlap = (p4[1] > p1[1]) if is_bull else (p4[1] < p1[1])
                w3 = abs(p3[1] - p2[1])
                w4 = abs(p3[1] - p4[1])
                ratio_w4 = w4 / w3 if w3 != 0 else 0
                if no_overlap and 0.15 <= ratio_w4 <= 0.65:
                    recency = max(0.2, 1 - gap / 60)
                    conf = 0.7 * recency
                    hypotheses.append({
                        "state": "FORMING_WAVE_5",
                        "is_bullish": is_bull,
                        "base_pivots": [p0, p1, p2, p3, p4],
                        "w1_start": p0,
                        "w1_end": p1,
                        "w4_end": p4,
                        "confidence": conf,
                        "gap": gap,
                        "reason": f"1-4 completadas, W4 retra {ratio_w4:.1%} de W3, sin solape, gap {gap}",
                        "next_target": "Onda 5"
                    })

        # ---- HIPÓTESIS 4: IMPULSO COMPLETO -> CORRECTIVA A-B-C ----
        if len(pivots) >= 6:
            seq = pivots[-6:]
            if is_alternating(seq):
                p = [s[1] for s in seq]
                is_bull = p[0] < p[1]
                if is_bull:
                    valid = seq[2][1] > seq[0][1] and seq[5][1] > seq[3][1] and seq[4][1] > seq[1][1]
                else:
                    valid = seq[2][1] < seq[0][1] and seq[5][1] < seq[3][1] and seq[4][1] < seq[1][1]
                if valid:
                    recency = max(0.1, 1 - gap / 40)  # si gap 22, recency 0.45 -> baja confianza
                    conf = 0.6 * recency
                    is_stale = gap > 20
                    hypotheses.append({
                        "state": "FORMING_WAVE_A" if not is_stale else "STALE_IMPULSE",
                        "is_bullish": is_bull,
                        "base_pivots": seq,
                        "impulse_start": seq[0],
                        "impulse_end": seq[5],
                        "confidence": conf,
                        "gap": gap,
                        "is_stale": is_stale,
                        "reason": f"Impulso 1-5 completo hace {gap} velas {'(STALE - viejo)' if is_stale else ''}, ahora en correctiva ABC",
                        "next_target": "Corrección A-B-C"
                    })

        # Si no hay patrón activo claro, verificar si hay un impulso histórico STALE
        if not hypotheses or max(h['confidence'] for h in hypotheses) < 0.4:
            if len(pivots) >= 6:
                for i in range(len(pivots) - 6, -1, -1):
                    seq = pivots[i:i + 6]
                    if not all(seq[j][2] != seq[j + 1][2] for j in range(5)):
                        continue
                    is_bull = seq[0][2] == 'L'
                    if is_bull:
                        valid = seq[2][1] > seq[0][1] and seq[4][1] > seq[1][1]
                    else:
                        valid = seq[2][1] < seq[0][1] and seq[4][1] < seq[1][1]
                    if valid:
                        gap_hist = current_idx - seq[-1][0]
                        if gap_hist > 15:
                            return {
                                "state": "STALE_IMPULSE",
                                "is_bullish": is_bull,
                                "base_pivots": seq,
                                "impulse_start": seq[0],
                                "impulse_end": seq[-1],
                                "confidence": max(0.1, 0.6 * (1 - gap_hist / 80)),
                                "gap": gap_hist,
                                "is_stale": True,
                                "reason": f"Impulso 1-5 completo hace {gap_hist} velas (STALE). Proyección vieja anclada a {seq[0][1]:.0f}->{seq[-1][1]:.0f} irrelevante ahora. Precio actual formó nuevo mínimo no relacionado",
                                "alternatives": hypotheses[:2],
                                "next_target": "Esperar nuevo 1-2"
                            }

        if not hypotheses:
            return self._unknown(f"No hay patrón activo claro, gap {gap}")

        # Ordenar por confianza
        hypotheses.sort(key=lambda x: x['confidence'], reverse=True)
        best = hypotheses[0]
        best['alternatives'] = hypotheses[1:3]  # top 2 alternativas para transparencia
        best['current_price'] = current_price
        best['last_pivot'] = last_pivot
        return best

    def _unknown(self, reason):
        return {
            "state": "UNKNOWN",
            "is_bullish": None,
            "base_pivots": [],
            "confidence": 0.15,
            "gap": 0,
            "reason": reason,
            "alternatives": [],
            "next_target": "Esperar confirmación"
        }
