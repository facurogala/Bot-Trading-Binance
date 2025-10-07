"""
Script de diagnóstico rápido para inspeccionar posiciones y órdenes en Binance Futures

Uso:
  python debug_orders.py [SYMBOL]

Ejemplo:
  python debug_orders.py ADAUSDT

El script mostrará:
 - Información de la posición (positionAmt, entryPrice, unrealizedProfit)
 - Órdenes abiertas para el símbolo (JSON completo)
 - Resumen legible por orden: type, side, price, stopPrice, origQty, executedQty, status, reduceOnly, closePosition, timeInForce
 - Para cada orderId, intentará obtener detalles con futures_get_order

Esto ayuda a identificar si:
 - La orden de entrada fue llenada (positionAmt != 0)
 - Las órdenes TP/SL existen en Binance y sus flags/quantities
 - Si las órdenes TP/SL tienen quantity=0 o no están configuradas correctamente
"""
import sys
import os
from binance_futures_trader import BinanceFuturesTrader
import json


def pretty(obj):
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except Exception:
        return str(obj)


def main():
    symbol = sys.argv[1].upper() if len(sys.argv) > 1 else 'ADAUSDT'

    try:
        trader = BinanceFuturesTrader()
    except Exception as e:
        print(f"❌ Error inicializando trader: {e}")
        return

    print(f"🔎 Debug para: {symbol}\n")

    # Posición
    try:
        print("-- Posiciones (futures_position_information para el símbolo)")
        positions = trader.client.futures_position_information(symbol=symbol)
        print(pretty(positions))
    except Exception as e:
        print(f"⚠️ Error al obtener position_information: {e}")

    # Órdenes abiertas para el símbolo
    try:
        print("\n-- Órdenes abiertas para el símbolo (futures_get_open_orders(symbol=...))")
        orders = trader.client.futures_get_open_orders(symbol=symbol)
        print(pretty(orders))

        if orders:
            print("\n-- Resumen legible por orden:")
            for o in orders:
                print("-"*80)
                print(f"orderId: {o.get('orderId')}")
                print(f"  type: {o.get('type')}")
                print(f"  side: {o.get('side')}")
                print(f"  price: {o.get('price')}")
                print(f"  stopPrice: {o.get('stopPrice')}")
                print(f"  origQty: {o.get('origQty') or o.get('quantity')}")
                print(f"  executedQty: {o.get('executedQty')}")
                print(f"  status: {o.get('status')}")
                print(f"  reduceOnly: {o.get('reduceOnly')}")
                print(f"  closePosition: {o.get('closePosition')}")
                print(f"  timeInForce: {o.get('timeInForce')}")

                # Intentar obtener detalles por orderId
                try:
                    detail = trader.client.futures_get_order(symbol=symbol, orderId=o.get('orderId'))
                    print("  detalle order:")
                    print(pretty(detail))
                except Exception as e:
                    print(f"  (no se pudo obtener detalle de orderId {o.get('orderId')}: {e})")

    except Exception as e:
        print(f"⚠️ Error al obtener órdenes abiertas: {e}")

    # Órdenes abiertas globales (sin filtrar por símbolo)
    try:
        print("\n-- Órdenes abiertas (futures_get_open_orders sin símbolo - todas las órdenes abiertas en la cuenta)")
        all_open = trader.client.futures_get_open_orders()
        print(pretty(all_open))
    except Exception as e:
        print(f"⚠️ Error al obtener todas las órdenes abiertas: {e}")

    # Órdenes históricas (futures_get_all_orders) para el símbolo
    try:
        print("\n-- Órdenes históricas (futures_get_all_orders) - últimas 50")
        historical = trader.client.futures_get_all_orders(symbol=symbol, limit=50)
        print(pretty(historical))
    except Exception as e:
        print(f"⚠️ Error al obtener órdenes históricas: {e}")

    # Posiciones abiertas según helper
    try:
        print("\n-- Posiciones abiertas (helper get_open_positions)")
        open_pos = trader.get_open_positions()
        print(pretty(open_pos))
    except Exception as e:
        print(f"⚠️ Error al obtener open_positions helper: {e}")


if __name__ == '__main__':
    main()
