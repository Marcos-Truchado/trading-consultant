"""
Scoring Engine - El cerebro que decide BUY/SELL/HOLD
Convierte 5 motores en un score 0-100 explicable
"""
from typing import Dict, List

class ScoringEngine:
    def __init__(self):
        pass

    def calculate(self, 
                  active_wave: Dict, 
                  regime: Dict, 
                  momentum: Dict, 
                  smc: Dict, 
                  volume: Dict,
                  mtf: Dict,
                  fib_levels: Dict,
                  current_price: float) -> Dict:

        score = 50  # base neutral
        reasons = []
        breakdown = {}

        # 1. Elliott Active Wave (30 pts max)
        aw_state = active_wave.get('state','UNKNOWN')
        aw_conf = active_wave.get('confidence',0)
        is_bull = active_wave.get('is_bullish')
        gap = active_wave.get('gap',0)

        elliott_pts = 0
        if aw_state == "FORMING_WAVE_3" and aw_conf > 0.5:
            elliott_pts = int(15 + aw_conf*15)  # 15-30
            reasons.append(f"Elliott W3 conf {aw_conf:.0%} +{elliott_pts}")
        elif aw_state == "FORMING_WAVE_5" and aw_conf > 0.5:
            elliott_pts = int(10 + aw_conf*10)
            reasons.append(f"Elliott W5 último impulso conf {aw_conf:.0%} +{elliott_pts}")
        elif aw_state == "FORMING_WAVE_4":
            elliott_pts = -5
            reasons.append(f"Elliott en corrección W4 {aw_conf:.0%} -5")
        elif aw_state in ("STALE_IMPULSE",):
            elliott_pts = -30
            reasons.append(f"STALE hace {gap} velas -30")
        elif aw_state == "UNKNOWN":
            elliott_pts = -15
            reasons.append("Sin patrón Elliott claro -15")

        score += elliott_pts
        breakdown['elliott'] = elliott_pts

        # 2. Regime (20 pts)
        regime_pts = regime.get('score_mod',0)
        score += regime_pts
        breakdown['regime'] = regime_pts
        reasons.append(f"Regimen {regime.get('regime')} {regime.get('reason')} {regime_pts:+d}")

        # 3. Momentum / Divergence (20 pts)
        mom_pts = momentum.get('score_mod',0)
        # Ajuste: si divergence es contraria a dirección de Elliott, penaliza fuerte
        div = momentum.get('divergence','NONE')
        if is_bull is not None:
            if is_bull and div == "BEARISH":
                mom_pts -= 15
                reasons.append(f"Divergencia bajista contra W alcista -15")
            elif not is_bull and div == "BULLISH":
                mom_pts -= 15
                reasons.append(f"Divergencia alcista contra W bajista -15")
            elif div != "NONE":
                reasons.append(f"{momentum.get('div_reason')} {mom_pts:+d}")
        score += mom_pts
        breakdown['momentum'] = mom_pts

        # 4. SMC (20 pts)
        smc_pts = smc.get('score_mod',0)
        # Ajuste fino: si SMC trend coincide con Elliott
        smc_trend = smc.get('trend_smc','UNKNOWN')
        if is_bull is not None and smc_trend != "UNKNOWN":
            if (is_bull and smc_trend=="BULL") or (not is_bull and smc_trend=="BEAR"):
                smc_pts += 5
                reasons.append(f"SMC trend {smc_trend} alinea con Elliott +5")
            elif smc_trend=="CHOCH":
                smc_pts -= 10
                reasons.append(f"CHOCH - posible reversal -10")
        score += smc_pts
        breakdown['smc'] = smc_pts
        reasons.append(f"SMC {smc.get('reason')} {smc_pts:+d}")

        # 5. Volume Profile (10 pts)
        vol_pts = volume.get('score_mod',0)
        score += vol_pts
        breakdown['volume'] = vol_pts
        if vol_pts !=0:
            reasons.append(f"Vol Profile {volume.get('reason')} {vol_pts:+d}")

        # 6. MTF (20 pts)
        mtf_pts = mtf.get('score_mod',0)
        score += mtf_pts
        breakdown['mtf'] = mtf_pts
        reasons.append(f"MTF {mtf.get('reason')} {mtf_pts:+d}")

        # Clamp 0-100
        score = max(0, min(100, score))

        # Decisión
        # Dirección base por Elliott
        if is_bull is None:
            action = "HOLD"
            direction = "NEUTRAL"
        else:
            direction = "LONG" if is_bull else "SHORT"

        if score >= 75:
            action = "BUY" if is_bull else "SELL"
            confidence_label = "ALTA"
        elif score >= 60:
            action = "BUY" if is_bull else "SELL"
            confidence_label = "MEDIA"
            # Pero si es W5, degradar a HOLD si score <75
            if aw_state == "FORMING_WAVE_5":
                action = "HOLD"
                confidence_label = "MEDIA-BAJA (W5 riesgosa)"
        elif score >= 45:
            action = "HOLD"
            confidence_label = "BAJA"
        else:
            action = "HOLD"
            confidence_label = "MUY BAJA / NO OPERAR"

        # Si regime no tradeable o STALE, forzar HOLD
        if not regime.get('tradeable', True) or aw_state == "STALE_IMPULSE":
            action = "HOLD"
            confidence_label += " - BLOQUEADO por régimen/STALE"

        return {
            "score": int(score),
            "action": action,
            "direction": direction,
            "confidence_label": confidence_label,
            "active_wave_state": aw_state,
            "is_bullish": is_bull,
            "breakdown": breakdown,
            "reasons": reasons,
            "veredicto": f"{action} {score}/100 - {confidence_label} | {aw_state} {'Alcista' if is_bull else 'Bajista' if is_bull==False else ''}"
        }
