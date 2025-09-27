# scalping_orders.py
"""
Gestión de órdenes optimizada para scalping con colocación y cancelación rápida
"""
import time
from typing import List, Dict, Optional
from orders import OrderManager
from config import SYMBOL


class ScalpingOrderManager(OrderManager):
    """
    Extensión de OrderManager optimizada para scalping con funcionalidades adicionales
    """
    
    def __init__(self, client=None, logger=None):
        super().__init__(client, logger)
        self.active_scalp_orders = {}  # Track scalping orders with timestamps
        self.last_order_cleanup = 0
        self.order_timeout = getattr(__import__('scalping_config'), 'SCALP_ORDER_TIMEOUT_SECONDS', 180)
        
    async def place_scalp_orders_batch(self, levels: List[float], signal: str) -> Dict:
        """
        Coloca múltiples órdenes de scalping de forma optimizada
        """
        results = {"success": 0, "failed": 0, "orders": []}
        current_time = time.time()
        
        # Cleanup old orders first
        await self.cleanup_stale_orders()
        
        for price in levels:
            try:
                qty = self.calcular_cantidad(price)
                client_id = f"scalp_{signal}_{int(current_time)}_{price}"
                
                # Place order
                result = self.colocar_orden_limit('BUY', price, qty, client_id)
                
                if result:
                    # Track the order
                    self.active_scalp_orders[client_id] = {
                        'price': price,
                        'qty': qty,
                        'signal': signal,
                        'timestamp': current_time,
                        'order_id': result.get('orderId')
                    }
                    results["orders"].append(result)
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                self.log.error(f"Error placing scalp order at {price}: {e}")
                results["failed"] += 1
                
        return results
    
    async def cleanup_stale_orders(self) -> int:
        """
        Cancela órdenes que han estado activas demasiado tiempo sin ejecutarse
        """
        if time.time() - self.last_order_cleanup < 30:  # Cleanup every 30 seconds
            return 0
            
        cancelled = 0
        current_time = time.time()
        stale_orders = []
        
        # Find stale orders
        for client_id, order_info in self.active_scalp_orders.items():
            if current_time - order_info['timestamp'] > self.order_timeout:
                stale_orders.append(client_id)
        
        # Cancel stale orders
        for client_id in stale_orders:
            try:
                order_info = self.active_scalp_orders[client_id]
                result = self.cancelar_orden(client_order_id=client_id)
                if result:
                    cancelled += 1
                    self.log.info(f"Cancelled stale scalp order: {client_id}")
                
                # Remove from tracking
                del self.active_scalp_orders[client_id]
                
            except Exception as e:
                self.log.warning(f"Failed to cancel stale order {client_id}: {e}")
        
        self.last_order_cleanup = current_time
        return cancelled
    
    def place_scalp_tp_orders(self, position_size: float, avg_price: float) -> Dict:
        """
        Coloca órdenes de take profit escalonadas específicas para scalping
        """
        try:
            from scalping_config import SCALP_TP_LEVELS
        except ImportError:
            SCALP_TP_LEVELS = [(1.0, 0.0015)]  # Default: 100% at 0.15%
        
        results = {"orders": [], "total_qty": 0}
        current_time = time.time()
        
        for ratio, tp_percentage in SCALP_TP_LEVELS:
            tp_qty = position_size * ratio
            tp_price = avg_price * (1 + tp_percentage)
            
            try:
                client_id = f"scalp_tp_{int(current_time)}_{tp_price}"
                result = self.colocar_orden_limit('SELL', tp_price, tp_qty, client_id)
                
                if result:
                    results["orders"].append(result)
                    results["total_qty"] += tp_qty
                    
                    # Track TP order
                    self.active_scalp_orders[client_id] = {
                        'price': tp_price,
                        'qty': tp_qty,
                        'signal': 'SCALP_TP',
                        'timestamp': current_time,
                        'order_id': result.get('orderId')
                    }
                    
            except Exception as e:
                self.log.error(f"Error placing scalp TP at {tp_price}: {e}")
        
        return results
    
    def get_scalp_orders_summary(self) -> Dict:
        """
        Obtiene un resumen de las órdenes de scalping activas
        """
        buy_orders = []
        sell_orders = []
        tp_orders = []
        
        for client_id, order_info in self.active_scalp_orders.items():
            if 'scalp_tp' in client_id:
                tp_orders.append(order_info)
            elif order_info.get('signal') in ['SCALP_UP', 'SCALP_DOWN', 'MOMENTUM_UP', 'MOMENTUM_DOWN']:
                buy_orders.append(order_info)
            else:
                sell_orders.append(order_info)
        
        return {
            'total_orders': len(self.active_scalp_orders),
            'buy_orders': len(buy_orders),
            'sell_orders': len(sell_orders),
            'tp_orders': len(tp_orders),
            'oldest_order_age': max([time.time() - o['timestamp'] for o in self.active_scalp_orders.values()]) if self.active_scalp_orders else 0
        }