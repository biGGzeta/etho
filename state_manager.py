# state_manager.py
import json
import os
from config import STATE_FILE

EPS = 1e-12  # tolerancia para flotantes muy pequeños

class StateManager:
    def __init__(self):
        # Estado con defaults; se migran claves faltantes si el json es viejo
        self.state = {
            "grids_activados": [],
            "posicion_total": 0.0,   # qty neta LONG viva
            "costo_total": 0.0,      # suma de (qty*precio) viva
            "fees_total": 0.0,
            "fills": [],             # opcional, histórico de fills
            # Gestión de epochs y TP/SL lógicos
            "position_epoch": 0,
            "tp_orders": { "epoch": None, "A": None, "B": None },  # guardamos clientOrderId/price/qty
            "sl_order":  { "epoch": None, "clientOrderId": None, "stopPrice": None }
        }
        self.load_state()
        self._ensure_defaults()

    def _ensure_defaults(self):
        s = self.state
        s.setdefault("grids_activados", [])
        s.setdefault("posicion_total", 0.0)
        s.setdefault("costo_total", 0.0)
        s.setdefault("fees_total", 0.0)
        s.setdefault("fills", [])
        s.setdefault("position_epoch", 0)
        s.setdefault("tp_orders", {"epoch": None, "A": None, "B": None})
        s.setdefault("sl_order", {"epoch": None, "clientOrderId": None, "stopPrice": None})
        self.save_state()

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    self.state = json.load(f)
            except Exception as e:
                print(f"[ERROR] Cargar estado: {e}")

    def save_state(self):
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"[ERROR] Guardar estado: {e}")

    # -------- Epochs -------- #
    def get_epoch(self) -> int:
        return int(self.state.get("position_epoch", 0))

    def _start_new_epoch_if_needed(self, prev_qty: float, new_qty: float):
        """Si pasamos de 0 → >0, arrancamos un nuevo epoch y limpiamos TP/SL previos."""
        if prev_qty <= EPS and new_qty > EPS:
            self.state["position_epoch"] = int(self.state.get("position_epoch", 0)) + 1
            self.state["tp_orders"] = {"epoch": self.state["position_epoch"], "A": None, "B": None}
            self.state["sl_order"]  = {"epoch": self.state["position_epoch"], "clientOrderId": None, "stopPrice": None}

    def _end_epoch_if_flat(self, qty: float):
        """Si volvimos a 0, limpiamos TP/SL; el próximo fill iniciará un nuevo epoch."""
        if qty <= EPS:
            self.state["posicion_total"] = 0.0
            self.state["costo_total"] = 0.0
            # No incrementamos epoch aquí; se incrementa al volver a abrir (en _start_new_epoch_if_needed)
            self.state["tp_orders"] = {"epoch": None, "A": None, "B": None}
            self.state["sl_order"]  = {"epoch": None, "clientOrderId": None, "stopPrice": None}

    # -------- Compras/Ventas (DCA + parciales exactas) -------- #
    def agregar_compra(self, precio: float, cantidad: float, fee: float = 0.0):
        prev_qty = float(self.state["posicion_total"])
        self.state["posicion_total"] = prev_qty + float(cantidad)
        self.state["costo_total"] += float(cantidad) * float(precio)
        self.state["fees_total"] += float(fee)
        self.state["fills"].append({"side": "BUY", "price": precio, "qty": cantidad, "fee": fee})
        # si es nueva apertura (0→>0) arrancamos epoch
        self._start_new_epoch_if_needed(prev_qty, self.state["posicion_total"])
        self.save_state()

    def agregar_venta(self, precio: float, cantidad: float, fee: float = 0.0):
        cantidad = float(cantidad)
        precio = float(precio)
        fee = float(fee)

        qty = float(self.state["posicion_total"])
        if qty <= EPS:
            # nada que reducir; registramos fee y salimos
            self.state["fees_total"] += fee
            self.state["fills"].append({"side": "SELL", "price": precio, "qty": cantidad, "fee": fee})
            self.save_state()
            return

        avg_cost = self.calcular_costo_promedio()
        # Restamos costo proporcional (FIFO promedio)
        reduce_qty = min(qty, cantidad)
        self.state["posicion_total"] = qty - reduce_qty
        self.state["costo_total"] -= reduce_qty * avg_cost
        if self.state["costo_total"] < 0:
            self.state["costo_total"] = 0.0

        self.state["fees_total"] += fee
        self.state["fills"].append({"side": "SELL", "price": precio, "qty": cantidad, "fee": fee})

        # Si quedamos planos, cerramos epoch actual (limpia TP/SL)
        self._end_epoch_if_flat(self.state["posicion_total"])
        self.save_state()

    def calcular_costo_promedio(self) -> float:
        total_qty = float(self.state["posicion_total"])
        if total_qty <= EPS:
            return 0.0
        return float(self.state["costo_total"]) / total_qty

    # -------- TP/SL en estado (opcional, informativo) -------- #
    def update_tp_state(self, epoch: int, A: dict | None, B: dict | None):
        self.state["tp_orders"] = {"epoch": epoch, "A": A, "B": B}
        self.save_state()

    def update_sl_state(self, epoch: int, client_id: str | None, stop_price: float | None):
        self.state["sl_order"] = {"epoch": epoch, "clientOrderId": client_id, "stopPrice": stop_price}
        self.save_state()
