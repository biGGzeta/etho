import time
from collections import deque
from typing import Optional, Union, Dict, List

# === CONFIGURACIÓN GLOBAL ===
COOLDOWN_MS = 2000  # Reducido para scalping más reactivo
TRADE_WINDOW_MS = 1000  # Ventana más corta para detección rápida
MAX_HISTORY_LEN = 500  # Más historia para mejor análisis
REDONDEO_GRID = 2  # Número de decimales para los niveles del grid

# Umbrales ajustables para scalping
FREQ_THRESHOLD = 20  # Más sensible para detectar actividad antes
VOLUME_THRESHOLD = 10.0  # Umbral más bajo para reaccionar más rápido
SUPPORT_VOLUME_THRESHOLD = 80.0  # Más sensible para soporte
CALMA_FREQ_THRESHOLD = 3  # Detecta calma más rápido
CALMA_VOLUME_THRESHOLD = 0.5  # Umbral más bajo para calma

# === NUEVOS PARÁMETROS PARA SCALPING ===
SCALP_WINDOW_MS = 500  # Ventana ultra corta para scalping
MOMENTUM_THRESHOLD = 0.0005  # 0.05% cambio de precio para momentum
RAPID_TRADES_THRESHOLD = 15  # Número de trades en ventana corta para señal rápida
MICRO_DUMP_VOLUME = 5.0  # Volumen mínimo para micro-dumps
PRICE_VELOCITY_THRESHOLD = 0.001  # Velocidad de cambio de precio para scalping

# Estado global
trade_history = deque(maxlen=MAX_HISTORY_LEN)
_last_dump_ts = 0
_last_support_ts = 0
_last_momentum_ts = 0
_last_scalp_signal_ts = 0
_price_history = deque(maxlen=50)  # Para tracking de momentum


def analizar_trade(trade_msg: Dict) -> Optional[str]:
    """
    Procesa un mensaje de trade y evalúa si hay señal de mercado 
    ('DUMP', 'CALMA', 'SCALP_UP', 'SCALP_DOWN', 'MOMENTUM' o None).
    """
    try:
        price = float(trade_msg.get('p') or 0)
        qty = float(trade_msg.get('q') or 0)
        ts = int(trade_msg.get('T') or 0)
        is_sell = bool(trade_msg.get('m'))
    except Exception:
        return None

    # Agregar al historial de trades
    trade_history.append({'price': price, 'qty': qty, 'timestamp': ts, 'sell': is_sell})
    
    # Agregar al historial de precios para momentum
    _price_history.append({'price': price, 'timestamp': ts})
    
    # Evaluar señales regulares primero
    regular_signal = evaluar_senales()
    if regular_signal:
        return regular_signal
    
    # Evaluar señales de scalping más rápidas
    scalp_signal = evaluar_senales_scalping()
    if scalp_signal:
        return scalp_signal
        
    # Evaluar momentum
    momentum_signal = evaluar_momentum()
    return momentum_signal


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


def evaluar_senales_scalping() -> Optional[str]:
    """
    Evalúa señales específicas de scalping con ventanas de tiempo más cortas
    y umbrales más sensibles.
    """
    global _last_scalp_signal_ts
    
    if not trade_history:
        return None
    
    now = trade_history[-1]['timestamp']
    
    # Ventana ultra corta para scalping
    scalp_trades = [t for t in trade_history if now - t['timestamp'] <= SCALP_WINDOW_MS]
    if len(scalp_trades) < 3:
        return None
    
    # Detectar actividad rápida de trading
    if len(scalp_trades) >= RAPID_TRADES_THRESHOLD:
        ventas_rapidas = [t for t in scalp_trades if t['sell']]
        compras_rapidas = [t for t in scalp_trades if not t['sell']]
        
        vol_ventas = sum(t['qty'] for t in ventas_rapidas)
        vol_compras = sum(t['qty'] for t in compras_rapidas)
        
        # Micro-dump detectado
        if vol_ventas > MICRO_DUMP_VOLUME and vol_ventas > vol_compras * 1.5:
            if now - _last_scalp_signal_ts > COOLDOWN_MS // 2:  # Cooldown más corto
                _last_scalp_signal_ts = now
                print("[SEÑAL] SCALP_DOWN detectado - micro dump")
                return 'SCALP_DOWN'
        
        # Micro-pump detectado  
        elif vol_compras > MICRO_DUMP_VOLUME and vol_compras > vol_ventas * 1.5:
            if now - _last_scalp_signal_ts > COOLDOWN_MS // 2:
                _last_scalp_signal_ts = now
                print("[SEÑAL] SCALP_UP detectado - micro pump")
                return 'SCALP_UP'
    
    return None


def evaluar_momentum() -> Optional[str]:
    """
    Evalúa el momentum de precio para detectar oportunidades de scalping
    basadas en velocidad de cambio de precio.
    """
    global _last_momentum_ts
    
    if len(_price_history) < 10:
        return None
    
    now = _price_history[-1]['timestamp']
    recent_prices = [p for p in _price_history if now - p['timestamp'] <= SCALP_WINDOW_MS * 2]
    
    if len(recent_prices) < 5:
        return None
    
    # Calcular velocidad de cambio de precio
    price_start = recent_prices[0]['price']
    price_end = recent_prices[-1]['price']
    time_diff = (recent_prices[-1]['timestamp'] - recent_prices[0]['timestamp']) / 1000.0
    
    if time_diff <= 0:
        return None
    
    price_change = (price_end - price_start) / price_start
    velocity = abs(price_change) / time_diff
    
    # Detectar momentum fuerte
    if velocity > PRICE_VELOCITY_THRESHOLD and now - _last_momentum_ts > COOLDOWN_MS // 3:
        _last_momentum_ts = now
        direction = "UP" if price_change > 0 else "DOWN"
        print(f"[SEÑAL] MOMENTUM_{direction} detectado - velocidad: {velocity:.6f}")
        return f'MOMENTUM_{direction}'
    
    return None


def recomendar_spacing(signal: Union[str, Dict], min_spacing: float, max_spacing: float) -> float:
    return _ajustar_por_senal(signal, min_spacing, max_spacing)


def recomendar_rango(signal: Union[str, Dict], min_range: float, max_range: float) -> float:
    return _ajustar_por_senal(signal, min_range, max_range)


def _ajustar_por_senal(signal: Union[str, Dict], minimo: float, maximo: float) -> float:
    """
    Ajusta spacing o rango según la señal recibida, incluyendo señales de scalping.
    """
    if signal == 'DUMP':
        return maximo
    elif isinstance(signal, dict) and signal.get('tipo') == 'SOPORTE':
        return minimo
    elif signal in ['SCALP_DOWN', 'MOMENTUM_DOWN']:
        # Para señales de caída, aumentar spacing para aprovechar la caída
        return maximo * 0.8  # 80% del máximo para scalping
    elif signal in ['SCALP_UP', 'MOMENTUM_UP']:
        # Para señales de subida, spacing mínimo para entrar rápido
        return minimo
    elif signal == 'CALMA':
        # En calma, spacing medio-bajo para posicionarse
        return minimo + (maximo - minimo) * 0.3
    
    # Default: spacing medio
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


def construir_grid_scalping(precio_actual: float, signal: str, spacing: float, range_down: float) -> List[float]:
    """
    Construye un grid optimizado para scalping con órdenes más cercanas al precio actual
    y adaptado según la señal de mercado.
    """
    niveles = []
    
    if signal in ['SCALP_DOWN', 'MOMENTUM_DOWN']:
        # Para caídas, crear más niveles cerca del precio actual
        limite = precio_actual * (1 - range_down * 1.2)  # Rango más amplio
        max_niveles = 20  # Más niveles para aprovechar la caída
        spacing_multiplier = 0.7  # Spacing más denso
    elif signal in ['SCALP_UP', 'MOMENTUM_UP']:
        # Para subidas, menos niveles y más cercanos
        limite = precio_actual * (1 - range_down * 0.6)  # Rango más corto
        max_niveles = 8  # Pocos niveles, cerca del precio
        spacing_multiplier = 0.5  # Muy cerca del precio
    elif signal == 'CALMA':
        # En calma, grid balanceado
        limite = precio_actual * (1 - range_down * 0.8)
        max_niveles = 12
        spacing_multiplier = 0.8
    else:
        # Default: usar grid normal
        return construir_grid(precio_actual, spacing, range_down)
    
    nivel = 1
    spacing_ajustado = spacing * spacing_multiplier
    
    while len(niveles) < max_niveles:
        p = precio_actual * (1 - spacing_ajustado * nivel)
        if p < limite:
            break
        niveles.append(round(p, REDONDEO_GRID))
        nivel += 1
        
        # Aumentar spacing gradualmente para distribuir mejor
        spacing_ajustado *= 1.1
    
    return sorted(set(niveles), reverse=True)
