import time
from collections import deque
from typing import Optional, Union, Dict, List

# === CONFIGURACIÓN GLOBAL ===
COOLDOWN_MS = 5000
TRADE_WINDOW_MS = 2000  # Ventana para analizar trades recientes
MAX_HISTORY_LEN = 300
REDONDEO_GRID = 2  # Número de decimales para los niveles del grid

# Umbrales ajustables
FREQ_THRESHOLD = 25
VOLUME_THRESHOLD = 15.0
SUPPORT_VOLUME_THRESHOLD = 100.0
CALMA_FREQ_THRESHOLD = 5
CALMA_VOLUME_THRESHOLD = 1.0

# Estado global
trade_history = deque(maxlen=MAX_HISTORY_LEN)
_last_dump_ts = 0
_last_support_ts = 0


def analizar_trade(trade_msg: Dict) -> Optional[str]:
    """
    Procesa un mensaje de trade y evalúa si hay señal de mercado ('DUMP', 'CALMA', o None).
    """
    try:
        price = float(trade_msg.get('p') or 0)
        qty = float(trade_msg.get('q') or 0)
        ts = int(trade_msg.get('T') or 0)
        is_sell = bool(trade_msg.get('m'))
    except Exception:
        return None

    trade_history.append({'price': price, 'qty': qty, 'timestamp': ts, 'sell': is_sell})
    return evaluar_senales()


def evaluar_senales(freq_threshold=FREQ_THRESHOLD, vol_threshold=VOLUME_THRESHOLD) -> Optional[str]:
    """
    Evalúa las últimas operaciones para determinar si hay señal de 'DUMP' o 'CALMA'.
    """
    global _last_dump_ts

    if not trade_history:
        return None

    now = trade_history[-1]['timestamp']

    # Limpieza activa de datos muy antiguos (opcional pero recomendado)
    activos = [t for t in trade_history if now - t['timestamp'] <= 5000]
    trade_history.clear()
    trade_history.extend(activos)

    recientes = [t for t in activos if now - t['timestamp'] <= TRADE_WINDOW_MS]
    if not recientes:
        return None

    ventas = [t for t in recientes if t['sell']]
    vol_ventas = sum(t['qty'] for t in ventas)
    freq = len(recientes) / (TRADE_WINDOW_MS / 1000)  # trades por segundo

    

    if freq > freq_threshold and vol_ventas > vol_threshold:
        if now - _last_dump_ts > COOLDOWN_MS:
            _last_dump_ts = now
            print("[SEÑAL] DUMP detectado.")
            return 'DUMP'

    if freq < CALMA_FREQ_THRESHOLD and vol_ventas < CALMA_VOLUME_THRESHOLD:
        print("[SEÑAL] CALMA detectada.")
        return 'CALMA'

    return None


def analizar_depth(depth_msg: Dict) -> Optional[Dict[str, Union[str, float]]]:
    """
    Procesa un mensaje de profundidad de mercado para detectar soporte fuerte.
    """
    global _last_support_ts

    bids = depth_msg.get('b') or []
    if not bids:
        return None

    top5_vol = 0.0
    top_bid_price = 0.0

    for i, b in enumerate(bids[:5]):
        try:
            p = float(b[0])
            q = float(b[1])
            top5_vol += q
            if i == 0:
                top_bid_price = p
        except Exception:
            continue

    now = int(time.time() * 1000)

    if top5_vol > SUPPORT_VOLUME_THRESHOLD and now - _last_support_ts > COOLDOWN_MS:
        _last_support_ts = now
        print(f"[SEÑAL] SOPORTE detectado. Precio: {top_bid_price}, Volumen: {top5_vol}")
        return {'tipo': 'SOPORTE', 'precio': top_bid_price, 'volumen': top5_vol}

    return None


def recomendar_spacing(signal: Union[str, Dict], min_spacing: float, max_spacing: float) -> float:
    return _ajustar_por_senal(signal, min_spacing, max_spacing)


def recomendar_rango(signal: Union[str, Dict], min_range: float, max_range: float) -> float:
    return _ajustar_por_senal(signal, min_range, max_range)


def _ajustar_por_senal(signal: Union[str, Dict], minimo: float, maximo: float) -> float:
    """
    Ajusta spacing o rango según la señal recibida.
    """
    if signal == 'DUMP':
        return maximo
    if isinstance(signal, dict) and signal.get('tipo') == 'SOPORTE':
        return minimo
    return (minimo + maximo) / 2.0


def construir_grid(precio_actual: float, spacing: float, range_down: float) -> List[float]:
    """
    Construye un grid de precios descendente desde el precio actual.
    """
    niveles = []
    limite = precio_actual * (1 - range_down)
    nivel = 1

    while True:
        p = precio_actual * (1 - spacing * nivel)
        if p < limite:
            break
        niveles.append(round(p, REDONDEO_GRID))
        nivel += 1
        if nivel > 15:
            break

    return sorted(set(niveles), reverse=True)
