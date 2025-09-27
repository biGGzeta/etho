# binance_client.py
from decimal import Decimal, ROUND_DOWN
from binance.client import Client
from config import API_KEY, API_SECRET, SYMBOL, LEVERAGE, USE_TESTNET, PAPER_MODE

class BinanceClient:
    def __init__(self):
        # python-binance: testnet=True para Futures testnet
        # Skip network calls in PAPER_MODE
        if PAPER_MODE:
            print("[INFO] PAPER_MODE - Skipping Binance client initialization")
            self.client = None
            self._ex_info = None
            self._symbol_specs = {}
            # Set default specs for PAPER_MODE
            self._symbol_specs[SYMBOL] = {
                "tickSize": Decimal("0.01"),
                "stepSize": Decimal("0.001"),
                "minQty": Decimal("0.001"),
                "pricePrecision": 2,
                "quantityPrecision": 3,
            }
            return
            
        self.client = Client(API_KEY, API_SECRET, testnet=USE_TESTNET)
        self._ex_info = None
        self._symbol_specs = {}

        # Cargar filtros de símbolo (PRICE_FILTER / LOT_SIZE / precisiones)
        try:
            self._ex_info = self.client.futures_exchange_info()
            for s in self._ex_info.get("symbols", []):
                self._symbol_specs[s["symbol"]] = self._parse_symbol_filters(s)
        except Exception as e:
            print(f"[WARN] No se pudo cargar futures_exchange_info: {e}")

        # Intentar setear leverage (solo si no es PAPER)
        if not PAPER_MODE:
            try:
                # Opcional: forzar modo aislado
                # self.client.futures_change_margin_type(symbol=SYMBOL, marginType="ISOLATED")
                self.client.futures_change_leverage(symbol=SYMBOL, leverage=LEVERAGE)
            except Exception as e:
                print(f"[WARN] No se pudo establecer leverage/margin: {e}")

    # ---------- Exchange filters parsing ---------- #
    def _parse_symbol_filters(self, sym_obj):
        price_filter = next((f for f in sym_obj.get("filters", []) if f["filterType"] == "PRICE_FILTER"), {})
        lot_filter   = next((f for f in sym_obj.get("filters", []) if f["filterType"] == "LOT_SIZE"), {})

        tick_size = price_filter.get("tickSize", "0.01")
        step_size = lot_filter.get("stepSize", "0.001")
        min_qty   = lot_filter.get("minQty", "0.001")

        return {
            "tickSize": Decimal(tick_size),
            "stepSize": Decimal(step_size),
            "minQty": Decimal(min_qty),
            "pricePrecision": sym_obj.get("pricePrecision", 2),
            "quantityPrecision": sym_obj.get("quantityPrecision", 3),
        }

    def _get_specs(self, symbol):
        if symbol in self._symbol_specs:
            return self._symbol_specs[symbol]
        return {
            "tickSize": Decimal("0.01"),
            "stepSize": Decimal("0.001"),
            "minQty": Decimal("0.001"),
            "pricePrecision": 2,
            "quantityPrecision": 3,
        }

    # ---------- Rounding & formatting exactos ---------- #
    @staticmethod
    def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
        if step == 0:
            return value
        return (value // step) * step

    def round_price(self, symbol: str, price: float) -> float:
        specs = self._get_specs(symbol)
        p = Decimal(str(price))
        p = self._floor_to_step(p, specs["tickSize"])
        q_prec = specs["pricePrecision"]
        p = p.quantize(Decimal(10) ** -q_prec, rounding=ROUND_DOWN)
        return float(p)

    def round_qty(self, symbol: str, qty: float) -> float:
        specs = self._get_specs(symbol)
        q = Decimal(str(qty))
        q = self._floor_to_step(q, specs["stepSize"])
        if q < specs["minQty"]:
            q = specs["minQty"]
        q_prec = specs["quantityPrecision"]
        q = q.quantize(Decimal(10) ** -q_prec, rounding=ROUND_DOWN)
        return float(q)

    def format_price(self, symbol: str, price: float) -> str:
        specs = self._get_specs(symbol)
        p = self.round_price(symbol, price)
        return f"{p:.{specs['pricePrecision']}f}"

    def format_qty(self, symbol: str, qty: float) -> str:
        specs = self._get_specs(symbol)
        q = self.round_qty(symbol, qty)
        return f"{q:.{specs['quantityPrecision']}f}"

    # ---------- Wrappers Futures (con PAPER safe) ---------- #
    def futures_create_order(self, **kwargs):
        if PAPER_MODE:
            print(f"[PAPER] futures_create_order {kwargs}")
            return {"paper": True, "request": kwargs}
        return self.client.futures_create_order(**kwargs)

    def futures_cancel_all_open_orders(self, symbol: str):
        if PAPER_MODE:
            print(f"[PAPER] cancel_all_open_orders symbol={symbol}")
            return {"paper": True}
        return self.client.futures_cancel_all_open_orders(symbol=symbol)

    def futures_get_open_orders(self, symbol: str = None):
        if PAPER_MODE:
            return []
        if symbol is None:
            return self.client.futures_get_open_orders()
        return self.client.futures_get_open_orders(symbol=symbol)

    def futures_cancel_order(self, **kwargs):
        if PAPER_MODE:
            print(f"[PAPER] futures_cancel_order {kwargs}")
            return {"paper": True, "request": kwargs}
        return self.client.futures_cancel_order(**kwargs)

    def get_available_balance(self, asset='USDT'):
        if PAPER_MODE:
            return 1000.0
        try:
            acc = self.client.futures_account()
            for a in acc.get("assets", []):
                if a.get("asset") == asset:
                    return float(a.get("availableBalance", 0.0))
        except Exception as e:
            print(f"[WARN] get_available_balance: {e}")
        return 0.0

    # ---------- USER DATA STREAM (USDT-M) ---------- #
    def futures_stream_get_listen_key(self):
        """Devuelve el listenKey (str) para el user stream de Futuros USDT-M."""
        if PAPER_MODE:
            return None
        for name in ("futures_stream_get_listen_key", "futures_get_listen_key"):
            meth = getattr(self.client, name, None)
            if meth:
                resp = meth()
                if isinstance(resp, dict):
                    return resp.get("listenKey")
                return resp
        raise AttributeError("Client no expone futures_stream_get_listen_key/futures_get_listen_key")

    def futures_stream_keepalive(self, listen_key: str):
        if PAPER_MODE or not listen_key:
            return
        for name in ("futures_stream_keepalive", "futures_keepalive_listen_key"):
            meth = getattr(self.client, name, None)
            if meth:
                try:
                    return meth(listenKey=listen_key)
                except TypeError:
                    return meth(listen_key)

    def futures_stream_close(self, listen_key: str):
        if PAPER_MODE or not listen_key:
            return
        for name in ("futures_stream_close", "futures_close_listen_key"):
            meth = getattr(self.client, name, None)
            if meth:
                try:
                    return meth(listenKey=listen_key)
                except TypeError:
                    return meth(listen_key)
