# scalping_config.py
"""
Configuración específica para scalping que complementa config.py
"""

# === CONFIGURACIÓN DE SCALPING ===
SCALP_MODE = True  # Enable scalping features

# Gestión de riesgo para scalping
SCALP_MAX_POSITION_RATIO = 0.6  # Máximo 60% del balance en posición de scalping
SCALP_QUICK_TP_PERCENTAGE = 0.0015  # 0.15% para take profit rápido
SCALP_TIGHT_SL_PERCENTAGE = 0.008   # 0.8% stop loss más ajustado
SCALP_MAX_CONCURRENT_ORDERS = 25    # Máximo número de órdenes concurrentes

# Timing optimizado para scalping
SCALP_REBALANCE_SECONDS = 10        # Rebalance cada 10 segundos
SCALP_ORDER_TIMEOUT_SECONDS = 180   # Cancel órdenes no ejecutadas después de 3 min
SCALP_SIGNAL_COOLDOWN_SECONDS = 15  # Cooldown entre señales de scalping

# Filtros de calidad para scalping
SCALP_MIN_VOLUME_24H = 50000000     # Volumen mínimo 24h en USDT
SCALP_MIN_SPREAD_PERCENTAGE = 0.0001 # Spread mínimo para operar (0.01%)
SCALP_MAX_SPREAD_PERCENTAGE = 0.01   # Spread máximo para operar (1%)

# Configuración de grid específica para scalping
SCALP_GRID_LEVELS_NEAR_PRICE = 5    # Niveles muy cerca del precio actual
SCALP_GRID_DENSITY_MULTIPLIER = 1.5  # Multiplicador de densidad de grid
SCALP_GRID_PRICE_BUFFER = 0.0005    # Buffer de precio para evitar fills inmediatos

# Configuración de take profit escalonado para scalping
SCALP_TP_LEVELS = [
    (0.3, 0.0010),  # 30% de posición al 0.10%
    (0.4, 0.0015),  # 40% de posición al 0.15%  
    (0.3, 0.0025),  # 30% de posición al 0.25%
]

# Monitoreo y alertas
SCALP_PROFIT_TARGET_DAILY = 0.02    # Target diario 2%
SCALP_MAX_LOSS_DAILY = 0.01         # Máxima pérdida diaria 1%
SCALP_ALERT_ON_BIG_MOVES = True     # Alertar en movimientos grandes