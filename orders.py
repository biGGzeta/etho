# orders.py
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_LIMIT
from config import SYMBOL, ORDER_USDT_SIZE, LEVERAGE
from utils import get_logger

class OrderManager:
    def __init__(self, client=None, logger=None):
        if client is None:
            from binance_client import BinanceClient
            self.client = BinanceClient()
        else:
            self.client = client
        self.log = logger or get_logger("orders")

    # ---------- helpers ---------- #
    def calcular_cantidad(self, precio: float) -> float:
        qty = (ORDER_USDT_SIZE * LEVERAGE) / float(precio)
        try:
            return self.client.round_qty(SYMBOL, qty)
        except Exception:
            return round(qty, 4)

    def _format_price(self, p: float) -> str:
        return self.client.format_price(SYMBOL, p)

    def _format_qty(self, q: float) -> str:
        return self.client.format_qty(SYMBOL, q)

    # ---------- CRUD ---------- #
    def colocar_orden_limit(self, side: str, precio: float, cantidad: float, client_order_id: str | None = None):
        price_str = self._format_price(precio)
        qty_str   = self._format_qty(cantidad)
        params = {
            "symbol": SYMBOL,
            "side": SIDE_BUY if side.upper() == 'BUY' else SIDE_SELL,
            "type": ORDER_TYPE_LIMIT,
            "timeInForce": 'GTX',
            "price": price_str,
            "quantity": qty_str,
        }
        if side.upper() == 'SELL':
            params["reduceOnly"] = True
        if client_order_id:
            params["newClientOrderId"] = client_order_id

        try:
            res = self.client.futures_create_order(**params)
            self.log.info(f"[ORDEN] {side.upper()} LIMIT GTX @ {price_str} x {qty_str} "
                          f"{'(reduceOnly)' if side.upper()=='SELL' else ''}")
            return res
        except Exception as e:
            self.log.error(f"[ERROR] colocar_orden_limit: {e}")
            return None

    def obtener_ordenes_abiertas(self):
        try:
            return self.client.futures_get_open_orders(SYMBOL)
        except Exception as e:
            self.log.error(f"[ERROR] obtener_ordenes_abiertas: {e}")
            return []

    def cancelar_orden(self, order_id=None, client_order_id: str | None = None):
        kwargs = {"symbol": SYMBOL}
        if order_id is not None:
            kwargs["orderId"] = order_id
        if client_order_id is not None:
            kwargs["origClientOrderId"] = client_order_id
        try:
            return self.client.futures_cancel_order(**kwargs)
        except Exception as e:
            self.log.error(f"[ERROR] cancelar_orden: {e}")

    def cancelar_todas(self):
        try:
            return self.client.futures_cancel_all_open_orders(symbol=SYMBOL)
        except Exception as e:
            self.log.error(f"[ERROR] cancelar_todas: {e}")

    # ---------- TP/SL por epoch ---------- #
    def ensure_take_profits(self, epoch: int, base_price: float, total_qty: float,
                            offsets=(0.0003, 0.0003), price_tol_ticks=0, qty_tol_steps=0):
        """
        Garantiza que existan SOLO los 2 TP del epoch actual:
          - clientOrderId 'TP_{epoch}_A' y 'TP_{epoch}_B'
          - reduceOnly=True, LIMIT GTX
        Limpia TPs de epochs viejos si los encuentra.
        """
        tpA_id = f"TP_{epoch}_A"
        tpB_id = f"TP_{epoch}_B"

        tp1 = float(base_price) * (1 + float(offsets[0]))
        tp2 = float(base_price) * (1 + float(offsets[1]))
        qty_half = float(total_qty) / 2.0

        price1 = float(self.client.round_price(SYMBOL, tp1))
        price2 = float(self.client.round_price(SYMBOL, tp2))
        qty    = float(self.client.round_qty(SYMBOL, qty_half))

        open_orders = self.obtener_ordenes_abiertas()

        # Cancelar TPs de epochs anteriores
        for o in open_orders:
            cid = o.get("clientOrderId") or o.get("origClientOrderId") or ""
            if cid.startswith("TP_") and not cid.startswith(f"TP_{epoch}_"):
                self.cancelar_orden(order_id=o.get("orderId"))

        # Buscar los TPs del epoch
        open_orders = self.obtener_ordenes_abiertas()  # refresco
        foundA = next((o for o in open_orders if (o.get("clientOrderId") or "").upper() == tpA_id.upper()), None)
        foundB = next((o for o in open_orders if (o.get("clientOrderId") or "").upper() == tpB_id.upper()), None)

        def need_replace(order, new_price, new_qty):
            if not order:
                return True
            try:
                op = float(order.get("price"))
                oq = float(order.get("origQty"))
            except Exception:
                return True
            # Reemplazar si precio o qty difieren (sin tolerancias sofisticadas para simplicidad)
            return abs(op - new_price) > 0 or abs(oq - new_qty) > 0

        # A
        if need_replace(foundA, price1, qty):
            if foundA:
                self.cancelar_orden(order_id=foundA.get("orderId"))
            self.colocar_orden_limit('SELL', price1, qty, client_order_id=tpA_id)

        # B
        if need_replace(foundB, price2, qty):
            if foundB:
                self.cancelar_orden(order_id=foundB.get("orderId"))
            self.colocar_orden_limit('SELL', price2, qty, client_order_id=tpB_id)

        return {
            "A": {"clientOrderId": tpA_id, "price": price1, "qty": qty},
            "B": {"clientOrderId": tpB_id, "price": price2, "qty": qty},
        }

    def ensure_stop_loss(self, epoch: int, stop_price: float):
        """
        Garantiza 1 solo SL del epoch actual: clientOrderId 'SL_{epoch}', STOP-MARKET closePosition.
        Limpia SL de epochs viejos si existieran.
        """
        sl_id = f"SL_{epoch}"
        stop = float(self.client.round_price(SYMBOL, stop_price))
        stop_str = self.client.format_price(SYMBOL, stop)

        open_orders = self.obtener_ordenes_abiertas()

        # cancelar SL de epochs anteriores
        for o in open_orders:
            cid = o.get("clientOrderId") or o.get("origClientOrderId") or ""
            t = (o.get("type") or "").upper()
            if cid.startswith("SL_") and not cid.upper().startswith(sl_id.upper()):
                # Si es STOP/STOP_MARKET y no es el actual, cancelamos
                self.cancelar_orden(order_id=o.get("orderId"))

        # buscar SL actual
        open_orders = self.obtener_ordenes_abiertas()
        found = next((o for o in open_orders if (o.get("clientOrderId") or "").upper() == sl_id.upper()), None)

        # Si no está o el stopPrice cambia, reemplazar
        need_new = True
        if found:
            try:
                op = float(found.get("stopPrice", 0.0))
                if abs(op - float(stop)) == 0:
                    need_new = False
            except Exception:
                need_new = True

        if need_new:
            if found:
                self.cancelar_orden(order_id=found.get("orderId"))
            params = {
                "symbol": SYMBOL,
                "side": SIDE_SELL,
                "type": "STOP_MARKET",
                "stopPrice": stop_str,
                "closePosition": True,
                "newClientOrderId": sl_id,
            }
            try:
                res = self.client.futures_create_order(**params)
                self.log.info(f"[SL] STOP-MARKET closePosition @ {stop_str} (id={sl_id})")
                return {"clientOrderId": sl_id, "stopPrice": float(stop)}
            except Exception as e:
                self.log.error(f"[ERROR] ensure_stop_loss: {e}")
                return None

        return {"clientOrderId": sl_id, "stopPrice": float(stop)}


    def place_tp_limit(self, price, quantity, client_id):
        try:
            order = self.client.place_order(
                symbol=self.symbol,
                side="SELL",
                type="LIMIT",
                timeInForce="GTX",
                price=str(price),
                quantity=str(quantity),
                reduceOnly=True,
                newClientOrderId=client_id
            )
            self.log.info(f"TP LIMIT colocado: {order}")
            return order
        except Exception as e:
            self.log.warning(f"No se pudo colocar TP LIMIT: {e}")
            return None
