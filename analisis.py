import time
import json
import threading
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque
from websocket import WebSocketApp

SYMBOL = 'ethusdt'
MIN_QTY = 0.1

# Historiales
trade_history = deque(maxlen=3000)
depth_history = deque(maxlen=3000)

# CSV
trade_csv = f'{SYMBOL}_trades.csv'
depth_csv = f'{SYMBOL}_depth.csv'

# Inicializar CSV
pd.DataFrame(columns=['timestamp', 'price', 'qty', 'sell']).to_csv(trade_csv, index=False)
pd.DataFrame(columns=['timestamp', 'top_bid_price', 'top5_volume', 'last_price']).to_csv(depth_csv, index=False)

def guardar_trade(trade):
    pd.DataFrame([trade]).to_csv(trade_csv, mode='a', header=False, index=False)

def guardar_depth(depth):
    pd.DataFrame([depth]).to_csv(depth_csv, mode='a', header=False, index=False)

def manejar_trade(_, message):
    msg = json.loads(message)
    price = float(msg['p'])
    qty = float(msg['q'])
    ts = int(msg['T'])
    is_sell = bool(msg['m'])
    if qty < MIN_QTY:
        return
    trade = {'timestamp': ts, 'price': price, 'qty': qty, 'sell': is_sell}
    trade_history.append(trade)
    guardar_trade(trade)

def manejar_depth(_, message):
    msg = json.loads(message)
    bids = msg.get('b') or []
    top5_vol = 0.0
    top_bid_price = 0.0
    for i, b in enumerate(bids[:5]):
        try:
            p = float(b[0]); q = float(b[1])
            top5_vol += q
            if i == 0:
                top_bid_price = p
        except:
            continue
    ts = int(time.time() * 1000)
    last_price = trade_history[-1]['price'] if trade_history else top_bid_price
    depth = {
        'timestamp': ts,
        'top_bid_price': top_bid_price,
        'top5_volume': top5_vol,
        'last_price': last_price
    }
    depth_history.append(depth)
    guardar_depth(depth)

def iniciar_websockets():
    url_trade = f"wss://stream.binance.com:9443/ws/{SYMBOL}@trade"
    url_depth = f"wss://stream.binance.com:9443/ws/{SYMBOL}@depth5@100ms"
    ws_trade = WebSocketApp(url_trade, on_message=manejar_trade)
    ws_depth = WebSocketApp(url_depth, on_message=manejar_depth)
    threading.Thread(target=ws_trade.run_forever, daemon=True).start()
    threading.Thread(target=ws_depth.run_forever, daemon=True).start()

# Gráfico en vivo
def main():
    iniciar_websockets()
    fig, axs = plt.subplots(3, 1, figsize=(10, 8))
    plt.tight_layout()

    def actualizar(frame):
        if len(trade_history) < 10 or len(depth_history) < 10:
            return

        df_trades = pd.DataFrame(trade_history)
        df_depth = pd.DataFrame(depth_history)
        df_trades['timestamp'] = pd.to_datetime(df_trades['timestamp'], unit='ms')
        df_depth['timestamp'] = pd.to_datetime(df_depth['timestamp'], unit='ms')
        df_trades.set_index('timestamp', inplace=True)
        df_depth.set_index('timestamp', inplace=True)

        freq = df_trades.resample('1s').size()
        vol_ventas = df_trades[df_trades['sell'] == True]['qty'].resample('1Min').sum()
        vol_depth = df_depth['top5_volume'].resample('1Min').mean()

        axs[0].clear(); axs[1].clear(); axs[2].clear()

        if len(freq) > 1:
            freq.plot(ax=axs[0], title='Frecuencia de trades por segundo')
            axs[0].axhline(y=15, color='red', linestyle='--', label='Umbral freq > 15')
            axs[0].legend()
        else:
            axs[0].set_title('Frecuencia de trades por segundo')
            axs[0].text(0.5, 0.5, 'Esperando más datos...', ha='center')

        if len(vol_ventas) > 1:
            vol_ventas.plot(ax=axs[1], title='Volumen vendido por minuto')
            axs[1].axhline(y=10, color='orange', linestyle='--', label='Umbral vol > 10')
            axs[1].legend()
        else:
            axs[1].set_title('Volumen vendido por minuto')
            axs[1].text(0.5, 0.5, 'Esperando más datos...', ha='center')

        if len(vol_depth) > 1:
            vol_depth.plot(ax=axs[2], title='Volumen promedio en top 5 bids')
            axs[2].axhline(y=100, color='green', linestyle='--', label='Umbral bids > 100')
            axs[2].legend()
        else:
            axs[2].set_title('Volumen promedio en top 5 bids')
            axs[2].text(0.5, 0.5, 'Esperando más datos...', ha='center')

    ani = FuncAnimation(fig, actualizar, interval=5000, cache_frame_data=False)
    plt.show()

if __name__ == "__main__":
    main()
