
from typing import Dict
from config import POLICY_THRESHOLDS, THRESHOLDS_JSON, SPACING_MIN, SPACING_MID, SPACING_MAX, RANGE_MIN, RANGE_MID, RANGE_MAX, TP_IMMEDIATE_ROI
import json
import os

ACTIONS = ("COMPRESS_MIN", "MID", "EXPAND_MAX")

def load_thresholds() -> Dict:
    thr = dict(POLICY_THRESHOLDS)
    if THRESHOLDS_JSON and os.path.exists(THRESHOLDS_JSON):
        try:
            with open(THRESHOLDS_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
                # permitir sobreescritura directa si las keys coinciden
                for k, v in data.items():
                    if isinstance(v, (int, float)) and k in thr:
                        thr[k] = v
        except Exception:
            pass
    return thr

def decide(features: Dict[str, float], thr: Dict) -> Dict:
    pressure = features.get("pressure", 0.0)
    bar = features.get("bid_ask_ratio", 1.0)
    speed = features.get("speed_pct_per_h", 0.0)
    tbr = features.get("taker_buy_ratio", 0.5)

    # reglas OR simples
    expand = (pressure <= thr["pressure_expand"]) or (bar <= thr["bar_expand"]) or (speed <= -thr["drop_speed_p80"]) or (tbr <= thr["tb_ratio_expand"])
    compress = (pressure >= thr["pressure_compress"]) or (bar >= thr["bar_compress"]) or (speed >= thr["rise_speed_p80"]) or (tbr >= thr["tb_ratio_compress"])

    if expand and not compress:
        action = "EXPAND_MAX"
        spacing = SPACING_MAX
        grid_range = RANGE_MAX
    elif compress and not expand:
        action = "COMPRESS_MIN"
        spacing = SPACING_MIN
        grid_range = RANGE_MIN
    else:
        action = "MID"
        spacing = SPACING_MID
        grid_range = RANGE_MID

    return {
        "action": action,
        "spacing": spacing,
        "grid_range": grid_range,
        "tp_roi": TP_IMMEDIATE_ROI.get(action, TP_IMMEDIATE_ROI["MID"]),
    }
