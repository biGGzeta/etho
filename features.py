
from collections import deque
from typing import Optional, Dict
import time
import math

class FeatureEngine:
    def __init__(self, window_secs: int = 120, ema_alpha: float = 0.2):
        self.prices = deque(maxlen=10000)
        self.times = deque(maxlen=10000)
        self.bid_vol = deque(maxlen=1000)
        self.ask_vol = deque(maxlen=1000)
        self.tb_ratio = deque(maxlen=1000)
        self.window_secs = window_secs
        self.ema_alpha = ema_alpha
        self._ema_pressure = None
        self._ema_rise_speed = None
        self._ema_drop_speed = None
        self._ema_bar = None
        self._last_action = "MID"
        self._last_action_ts = 0.0

    def update_from_trade(self, price: float, ts: float):
        self.prices.append(price)
        self.times.append(ts)

    def update_from_depth(self, bid_top: float, ask_top: float):
        self.bid_vol.append(bid_top)
        self.ask_vol.append(ask_top)

    def update_from_tb_ratio(self, r: float):
        self.tb_ratio.append(r)

    def _compute_speed_pct_per_h(self) -> float:
        # velocidad simple: delta% en ventana (hasta window_secs) anualizada a h
        if len(self.prices) < 2:
            return 0.0
        t_now = self.times[-1]
        # buscar precio más antiguo dentro de ventana
        idx = len(self.times) - 1
        while idx > 0 and (t_now - self.times[idx]) < self.window_secs:
            idx -= 1
        p_old = self.prices[max(idx, 0)]
        p_new = self.prices[-1]
        if p_old <= 0:
            return 0.0
        ret = (p_new - p_old) / p_old  # fracción
        # convertir a %/h
        elapsed = max(1.0, self.times[-1] - self.times[max(idx,0)])
        per_sec = ret / elapsed
        return per_sec * 3600 * 100.0  # %/h

    def compute(self) -> Dict[str, float]:
        pressure = 0.0
        if len(self.bid_vol) and len(self.ask_vol):
            pressure = (self.bid_vol[-1] - self.ask_vol[-1])

        bar = 0.0
        if len(self.bid_vol) and len(self.ask_vol) and self.ask_vol[-1] > 0:
            bar = self.bid_vol[-1] / max(1e-9, self.ask_vol[-1])

        tbr = self.tb_ratio[-1] if len(self.tb_ratio) else 0.5

        speed = self._compute_speed_pct_per_h()  # + => sube; - => baja

        # EMA suavizados
        def ema(prev, x):
            a = self.ema_alpha
            return x if prev is None else (a*x + (1-a)*prev)

        ema_pressure = ema(self._ema_pressure, pressure)
        ema_speed = ema(self._ema_rise_speed, speed)  # signo importa
        ema_bar = ema(self._ema_bar, bar)

        self._ema_pressure = ema_pressure
        self._ema_rise_speed = ema_speed
        self._ema_bar = ema_bar

        return {
            "pressure": float(ema_pressure or 0.0),
            "speed_pct_per_h": float(ema_speed or 0.0),
            "bid_ask_ratio": float(ema_bar or 0.0),
            "taker_buy_ratio": float(tbr),
        }
