# bot.py
import asyncio
import time

from websocket_listener import WebSocketManager
from binance_client import BinanceClient
from orders import OrderManager
from state_manager import StateManager
from utils import get_logger
import strategy

from config import (
    SYMBOL, MIN_GRID_SPACING, MAX_GRID_SPACING,
    GRID_RANGE_MIN, GRID_RANGE_MAX, REBALANCE_SECONDS,
    MIN_PROFIT_THRESHOLD, TP_OFFSET_LOW, TP_OFFSET_MID, TP_OFFSET_HIGH,
    STOP_LOSS_PERCENTAGE, PAPER_MODE, MAKER_FEE_RATE,
    ORDER_USDT_SIZE,
)

# --- [MODIFICADO] Nuevas constantes para la estrategia de ROI ---
# Define el Retorno Sobre la Inversión (margen) que deseas obtener.
# 3% se escribe como 0.03
ROI_DESEADO = 0.03

# Define el apalancamiento que estás utilizando en tu cuenta de futuros.
# Es MUY IMPORTANTE que este valor coincida con tu configuración en Binance.
LEVERAGE = 10


class GridBot:
    def __init__(self):
        self.log = get_logger("bot")
        self.client = BinanceClient()
        
        # Use scalping order manager if scalping mode is enabled
        try:
            from config import SCALP_MODE
            if SCALP_MODE:
                from scalping_orders import ScalpingOrderManager
                self.orders = ScalpingOrderManager(client=self.client, logger=self.log)
                print(f"[INFO] Using ScalpingOrderManager for optimized scalping")
            else:
                self.orders = OrderManager(client=self.client, logger=self.log)
        except ImportError:
            self.orders = OrderManager(client=self.client, logger=self.log)
            
        self.state = StateManager()

        self.last_price = None
        self.last_signal = None
        self.current_spacing = (MIN_GRID_SPACING + MAX_GRID_SPACING) / 2
        self.current_range = (GRID_RANGE_MIN + GRID_RANGE_MAX) / 2
        self._last_rebalance = 0
        self._scalp_mode = getattr(self, '_check_scalp_mode', lambda: False)()

        env = 'TEST' if getattr(self.client.client, 'testnet', False) else 'PROD'
        scalp_status = "SCALP" if self._scalp_mode else "GRID"
        print(f"[INFO] PAPER_MODE={'ON' if PAPER_MODE else 'OFF'} | ENV={env} | Mode={scalp_status} | Symbol={SYMBOL}")
        print(f"[ESTRATEGIA] TP configurado para un {ROI_DESEADO*100}% de ROI con apalancamiento x{LEVERAGE}")
    
    def _check_scalp_mode(self):
        """Check if scalping mode is enabled"""
        try:
            from config import SCALP_MODE
            return SCALP_MODE
        except ImportError:
            return False
    
    def _is_scalping_signal(self):
        """Check if current signal is a scalping signal"""
        return self.last_signal in ['SCALP_DOWN', 'SCALP_UP', 'MOMENTUM_DOWN', 'MOMENTUM_UP']

    # ------------------ Handlers de WS ------------------ #
    async def procesar_trade(self, msg):
        sig = strategy.analizar_trade(msg)
        if sig:
            self.last_signal = sig
            # Handle different signal types
            if sig == 'DUMP':
                print("[ESTRATEGIA] Caída rápida detectada → spacing MAX")
            elif sig == 'SCALP_DOWN':
                print("[ESTRATEGIA] Micro-dump detectado → grid denso para scalping")
            elif sig == 'SCALP_UP':
                print("[ESTRATEGIA] Micro-pump detectado → grid cercano para entrada rápida")
            elif sig == 'MOMENTUM_DOWN':
                print("[ESTRATEGIA] Momentum bajista → aprovechar caída")
            elif sig == 'MOMENTUM_UP':
                print("[ESTRATEGIA] Momentum alcista → entrada conservadora")
            elif sig == 'CALMA':
                print("[ESTRATEGIA] Mercado en calma → grid balanceado")

        # precio last de trade
        try:
            self.last_price = float(msg.get('p') or self.last_price or 0)
        except Exception:
            pass

        await self._rebalance_si_corresponde()

    async def procesar_depth(self, msg):
        soporte = strategy.analizar_depth(msg)
        if soporte:
            self.last_signal = soporte
            print(f"[ESTRATEGIA] Soporte detectado en {soporte['precio']} (vol {round(soporte['volumen'], 3)}) → spacing MIN")
        await self._rebalance_si_corresponde()

    async def procesar_ticker(self, msg):
        # MiniTicker tiene 'c' (close)
        try:
            price = float(msg.get('c'))
            self.last_price = price
        except Exception:
            pass
        await self._rebalance_si_corresponde()

    async def procesar_user(self, msg):
        # futures ORDER_TRADE_UPDATE
        try:
            if msg.get('e') != 'ORDER_TRADE_UPDATE':
                return
            o = msg.get('o', {})
            s = o.get('S')  # SIDE
            X = o.get('X')  # current order status
            avg_price = float(o.get('ap') or 0)      # average price
            last_filled_qty = float(o.get('l') or 0) # last filled qty
            commission = float(o.get('n') or 0)

            # Sólo procesamos fills
            if last_filled_qty > 0 and X in ('PARTIALLY_FILLED', 'FILLED'):
                if s == 'BUY':
                    self.state.agregar_compra(avg_price, last_filled_qty, fee=commission)
                elif s == 'SELL':
                    self.state.agregar_venta(avg_price, last_filled_qty, fee=commission)

                await self.colocar_tp_y_sl_si_corresponde()
        except Exception as e:
            print(f"[USER] error parse: {e}")

    # ------------------ Core de rebalance ------------------ #
    async def _rebalance_si_corresponde(self):
        now = time.time()
        if self.last_price is None:
            return
        
        # Rebalance más frecuente para señales de scalping
        rebalance_delay = REBALANCE_SECONDS
        if self.last_signal in ['SCALP_DOWN', 'SCALP_UP', 'MOMENTUM_DOWN', 'MOMENTUM_UP']:
            rebalance_delay = REBALANCE_SECONDS // 3  # 3x más rápido para scalping
        elif self.last_signal == 'DUMP':
            rebalance_delay = REBALANCE_SECONDS // 2  # 2x más rápido para dumps
            
        if now - self._last_rebalance < rebalance_delay:
            return

        # Recomendar spacing y rango según señal
        self.current_spacing = strategy.recomendar_spacing(self.last_signal, MIN_GRID_SPACING, MAX_GRID_SPACING)
        self.current_range = strategy.recomendar_rango(self.last_signal, GRID_RANGE_MIN, GRID_RANGE_MAX)

        # Usar grid de scalping si tenemos señales de scalping/momentum
        if self.last_signal in ['SCALP_DOWN', 'SCALP_UP', 'MOMENTUM_DOWN', 'MOMENTUM_UP', 'CALMA']:
            niveles = strategy.construir_grid_scalping(self.last_price, self.last_signal, 
                                                     self.current_spacing, self.current_range)
            grid_type = "SCALP"
        else:
            niveles = strategy.construir_grid(self.last_price, self.current_spacing, self.current_range)
            grid_type = "REGULAR"

        # Cap por margen disponible
        niveles = await self._cap_por_margen(niveles)

        self._last_rebalance = now
        if not niveles:
            return

        print(f"[{grid_type}] Rebalance spacing={round(self.current_spacing*100,2)}% "
              f"range={round(self.current_range*100,2)}% niveles={len(niveles)}")

        if PAPER_MODE:
            for p in niveles[:6]:
                qty = self.orders.calcular_cantidad(p)
                print(f"[PAPER][BUY] LIMIT {p} x {qty}")
            return

        # ✅ Use scalping batch orders for scalping signals, regular grid otherwise
        try:
            if hasattr(self.orders, "reconcile_grid") and not self._is_scalping_signal():
                stats = self.orders.reconcile_grid(niveles)
                print(f"[GRID] reconcile: {stats}")
            elif hasattr(self.orders, "place_scalp_orders_batch") and self._is_scalping_signal():
                # Use scalping batch order placement
                result = await self.orders.place_scalp_orders_batch(niveles, str(self.last_signal))
                print(f"[SCALP] batch orders: {result['success']} success, {result['failed']} failed")
            else:
                # Fallback to standard order placement
                self.orders.cancelar_todas()
                for p in niveles:
                    qty = self.orders.calcular_cantidad(p)
                    self.orders.colocar_orden_limit('BUY', p, qty)
        except Exception as e:
            print(f"[GRID] error al rearmar: {e}")

        await self.colocar_tp_y_sl_si_corresponde()

    async def _cap_por_margen(self, niveles: list[float]) -> list[float]:
        # Conservador: asume que todas podrían llenarse a la vez
        if PAPER_MODE:
            return niveles[:20]
        try:
            avail = self.client.get_available_balance()
            if avail <= 0:
                return niveles[:5]
            max_orders = int(float(avail) // float(ORDER_USDT_SIZE))
            if max_orders <= 0:
                max_orders = 1
            return niveles[:max_orders]
        except Exception:
            return niveles[:10]

    # ------------------ TP/SL Lógica ------------------ #

    def _tp_threshold_neto(self):
        """
        [MODIFICADO] Calcula el umbral de TP para lograr un ROI deseado sobre el margen.
        La fórmula convierte el ROI sobre el capital al porcentaje de movimiento
        de precio necesario para alcanzarlo, según el apalancamiento.
        Ej: 3% ROI con 10x leverage -> 0.3% de movimiento de precio.
        """
        # El threshold de precio es el ROI deseado dividido por el apalancamiento
        price_threshold = ROI_DESEADO / LEVERAGE

        # Sumamos las comisiones de ida (compra) y vuelta (venta) para que el ROI sea neto.
        # Asumimos que la venta será una orden MAKER (límite), por lo que usamos la misma tasa.
        fees_ida_y_vuelta = MAKER_FEE_RATE * 2

        # El umbral final es el movimiento de precio necesario + cobertura de comisiones
        return price_threshold + fees_ida_y_vuelta


    async def colocar_tp_y_sl_si_corresponde(self):
        """
        [CORREGIDO] Esta función ahora coloca/actualiza el TP y SL siempre que
        hay una posición abierta, en lugar de esperar a que el precio alcance el objetivo.
        """
        pos = float(self.state.state.get('posicion_total', 0.0))
        if pos <= 0 or self.last_price is None:
            # Si no hay posición, puedes añadir una lógica para cancelar TPs/SLs huérfanos
            # self.orders.cancel_all_tp_sl()
            return

        avg = self.state.calcular_costo_promedio()
        threshold = self._tp_threshold_neto()
        if threshold is None:
            return

        target_base = avg * (1 + threshold)
        epoch = self.state.get_epoch()

        # --- Lógica de SL (sin cambios) ---
        # SL siempre se actualiza al costo promedio actual de la posición
        sl_price = avg * (1 - STOP_LOSS_PERCENTAGE)
        sl_state = self.orders.ensure_stop_loss(epoch, sl_price)
        if sl_state:
            self.state.update_sl_state(epoch, sl_state.get("clientOrderId"), sl_state.get("stopPrice"))

        # --- Lógica de TP (CORREGIDA) ---
        # Se eliminó la condición `if self.last_price >= target_base:`.
        # Ahora, las órdenes de TP se colocan/actualizan en cada llamada,
        # esperando pacientemente a que el precio las alcance.

        # Offsets según volatilidad (sin cambios)
        if self.current_spacing <= 0.001:
            offsets = TP_OFFSET_LOW
        elif self.current_spacing <= 0.003:
            offsets = TP_OFFSET_MID
        else:
            offsets = TP_OFFSET_HIGH

        # Llamamos directamente a la función para asegurar los TPs
        tp_state = self.orders.ensure_take_profits(epoch, target_base, pos, offsets=offsets)
        if tp_state:
            self.state.update_tp_state(epoch, tp_state.get("A"), tp_state.get("B"))


    # ------------------ Main loop ------------------ #
    async def run(self):
        ws = WebSocketManager()

        async def handler(msg, tipo):
            try:
                if tipo == 'TRADE':
                    await self.procesar_trade(msg)
                elif tipo == 'DEPTH':
                    await self.procesar_depth(msg)
                elif tipo == 'TICKER':
                    await self.procesar_ticker(msg)
                elif tipo == 'USER':
                    await self.procesar_user(msg)
            except Exception as e:
                print(f"[ERROR] Handler {tipo}: {e}")

        await ws.start_all(handler)

if __name__ == "__main__":
    print("[BOT] Iniciando ETH Grid Bot Dinámico...")
    bot = GridBot()
    asyncio.run(bot.run())