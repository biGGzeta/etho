API_KEY = ''
API_SECRET = ''
SYMBOL = 'ETHUSDT'
LEVERAGE = 10

# Entorno
PAPER_MODE = False   # Simulación: no llama endpoints privados ni coloca órdenes reales
USE_TESTNET = False # Para operar en testnet cuando PAPER_MODE=False y tengas claves de testnet

# Grid settings
GRID_RANGE_MIN = 0.0023   # 6%
GRID_RANGE_MAX = 0.021   # 15%
MIN_GRID_SPACING = 0.0017   # 0.3%
MAX_GRID_SPACING = 0.0051  # 0.75%
ORDER_USDT_SIZE = 10    # Capital por orden (se multiplica por leverage implícitamente)
REBALANCE_SECONDS = 30

# Take profit
MIN_PROFIT_THRESHOLD = 0.003  # 0.30% target base
TP_OFFSET_LOW = (0.25, 0.00025)   # 0.03% y 0.03%
TP_OFFSET_MID = (0.00030, 0.0003)   # 0.05% y 0.05%
TP_OFFSET_HIGH = (0.00035, 0.00035)  # 0.05% y 0.07%

# Fees (ajusta según tu cuenta / VIP / BNB)
MAKER_FEE_RATE = 0.0002
TAKER_FEE_RATE = 0.0004

# SL Global
STOP_LOSS_PERCENTAGE = 0.15  # 15%

# Archivo estado
STATE_FILE = 'data/bot_state.json'

# --- Logging & Alerts ---
LOG_JSON = False
LOG_LEVEL = "INFO"

# Telegram (optional)
TELEGRAM_ENABLED = False
TELEGRAM_TOKEN = ""  # ej. "123456:ABC..."
TELEGRAM_CHAT_ID = ""  # ej. 123456789

# === SCALPING CONFIGURATION ===
try:
    from scalping_config import *
    if SCALP_MODE:
        # Override some settings for scalping
        REBALANCE_SECONDS = SCALP_REBALANCE_SECONDS
        MIN_GRID_SPACING = MIN_GRID_SPACING / 2  # Tighter grid for scalping
        STOP_LOSS_PERCENTAGE = SCALP_TIGHT_SL_PERCENTAGE
        print("[CONFIG] Scalping mode ENABLED - Using optimized settings")
except ImportError:
    SCALP_MODE = False
    print("[CONFIG] Scalping config not found - Using default settings")
