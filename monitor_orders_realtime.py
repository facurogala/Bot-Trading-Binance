"""
👁️ Monitor en tiempo real de órdenes SL/TP
Muestra el estado de las órdenes cada X segundos
"""
import os
import time
from datetime import datetime
from binance_futures_trader import BinanceFuturesTrader
from dotenv import load_dotenv

load_dotenv()

def monitor_orders_realtime(interval: int = 10, duration: int = 300):
    """
    Monitorea órdenes en tiempo real
    
    Args:
        interval: Segundos entre cada actualización (default: 10)
        duration: Duración total del monitoreo en segundos (default: 300 = 5 min)
    """
    
    print("="*80)
    print("👁️ MONITOR EN TIEMPO REAL DE ÓRDENES SL/TP")
    print("="*80)
    print(f"Intervalo: {interval}s | Duración: {duration}s ({duration//60} minutos)")
    print(f"Presiona Ctrl+C para detener\n")
    
    try:
        trader = BinanceFuturesTrader(context="monitor_orders_realtime")
        start_time = time.time()
        iteration = 0
        
        while True:
            iteration += 1
            elapsed = time.time() - start_time
            
            if elapsed > duration:
                print(f"\n⏰ Monitoreo completado ({duration}s)")
                break
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            print(f"\n{'='*80}")
            print(f"🔄 Actualización #{iteration} - {timestamp}")
            print(f"{'='*80}")
            
            # Obtener posiciones abiertas
            positions = trader.client.futures_position_information()
            
            active_symbols = []
            for pos in positions:
                amt = float(pos.get('positionAmt', 0))
                if amt != 0:
                    active_symbols.append({
                        'symbol': pos['symbol'],
                        'side': 'LONG' if amt > 0 else 'SHORT',
                        'amt': abs(amt),
                        'entry': float(pos['entryPrice']),
                        'pnl': float(pos['unRealizedProfit'])
                    })
            
            if not active_symbols:
                print("ℹ️  No hay posiciones abiertas")
            else:
                print(f"\n📊 {len(active_symbols)} posición(es) abierta(s):\n")
                
                for pos_data in active_symbols:
                    symbol = pos_data['symbol']
                    
                    # Obtener precio actual
                    ticker = trader.client.futures_symbol_ticker(symbol=symbol)
                    current_price = float(ticker['price'])
                    
                    # Calcular % PnL
                    entry = pos_data['entry']
                    if pos_data['side'] == 'LONG':
                        pnl_pct = ((current_price / entry) - 1) * 100
                    else:
                        pnl_pct = ((entry / current_price) - 1) * 100
                    
                    pnl_icon = "🟢" if pos_data['pnl'] > 0 else "🔴" if pos_data['pnl'] < 0 else "⚪"
                    
                    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    print(f"🔹 {symbol} - {pos_data['side']}")
                    print(f"   Cantidad: {pos_data['amt']}")
                    print(f"   Entry: {entry} | Actual: {current_price}")
                    print(f"   PnL: {pnl_icon} {pos_data['pnl']:.2f} USDT ({pnl_pct:+.2f}%)")
                    
                    # Obtener órdenes activas
                    orders = trader.client.futures_get_open_orders(symbol=symbol)
                    
                    if not orders:
                        print(f"   ⚠️⚠️⚠️ ¡SIN PROTECCIÓN! No hay SL ni TP")
                        continue
                    
                    sl_orders = []
                    tp_orders = []
                    
                    for order in orders:
                        order_type = order.get('type', '')
                        if 'STOP' in order_type and 'TAKE_PROFIT' not in order_type:
                            sl_orders.append(order)
                        elif 'TAKE_PROFIT' in order_type:
                            tp_orders.append(order)
                    
                    # Mostrar SL
                    if sl_orders:
                        sl = sl_orders[0]
                        sl_price = float(sl['stopPrice'])
                        sl_dist_pct = abs((sl_price / current_price) - 1) * 100
                        print(f"\n   🛑 Stop Loss:")
                        print(f"      Precio: {sl_price} ({-sl_dist_pct:.2f}% del actual)")
                        print(f"      ID: {sl['orderId']}")
                    else:
                        print(f"\n   ❌ Stop Loss: NO configurado")
                    
                    # Mostrar TPs
                    if tp_orders:
                        print(f"\n   🎯 Take Profits ({len(tp_orders)}):")
                        for i, tp in enumerate(tp_orders, 1):
                            tp_price = float(tp['stopPrice'])
                            tp_qty = float(tp['origQty'])
                            tp_dist_pct = abs((tp_price / current_price) - 1) * 100
                            
                            direction = "+" if pos_data['side'] == "LONG" else "-"
                            print(f"      TP{i}: {tp_price} ({direction}{tp_dist_pct:.2f}%) | Qty: {tp_qty} | ID: {tp['orderId']}")
                    else:
                        print(f"\n   ❌ Take Profits: NO configurados")
            
            # Esperar hasta la próxima actualización
            print(f"\n⏳ Próxima actualización en {interval}s...")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print(f"\n\n⏹️  Monitoreo detenido por el usuario")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def monitor_single_symbol(symbol: str, interval: int = 5, duration: int = 180):
    """
    Monitorea un símbolo específico con más detalle
    
    Args:
        symbol: Símbolo a monitorear (ej: WOOUSDT)
        interval: Segundos entre actualizaciones
        duration: Duración total en segundos
    """
    
    print("="*80)
    print(f"👁️ MONITOR DETALLADO: {symbol}")
    print("="*80)
    print(f"Intervalo: {interval}s | Duración: {duration}s")
    print(f"Presiona Ctrl+C para detener\n")
    
    try:
        trader = BinanceFuturesTrader(context="monitor_orders_realtime")
        start_time = time.time()
        iteration = 0
        
        prev_price = None
        
        while True:
            iteration += 1
            elapsed = time.time() - start_time
            
            if elapsed > duration:
                print(f"\n⏰ Monitoreo completado")
                break
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Obtener precio actual
            ticker = trader.client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            
            # Calcular cambio de precio
            if prev_price:
                price_change = ((current_price / prev_price) - 1) * 100
                arrow = "📈" if price_change > 0 else "📉" if price_change < 0 else "➡️"
            else:
                price_change = 0
                arrow = "➡️"
            
            prev_price = current_price
            
            # Obtener posición
            positions = trader.client.futures_position_information(symbol=symbol)
            position = None
            for pos in positions:
                amt = float(pos.get('positionAmt', 0))
                if amt != 0:
                    position = pos
                    break
            
            print(f"\n{timestamp} #{iteration} {arrow} Precio: {current_price} ({price_change:+.3f}%)")
            
            if not position:
                print(f"   ℹ️  Sin posición abierta en {symbol}")
                print(f"   ⏳ Esperando {interval}s...")
                time.sleep(interval)
                continue
            
            # Datos de posición
            amt = float(position['positionAmt'])
            side = 'LONG' if amt > 0 else 'SHORT'
            entry = float(position['entryPrice'])
            pnl = float(position['unRealizedProfit'])
            
            if side == 'LONG':
                pnl_pct = ((current_price / entry) - 1) * 100
            else:
                pnl_pct = ((entry / current_price) - 1) * 100
            
            pnl_icon = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
            
            print(f"   📊 {side} | Entry: {entry} | PnL: {pnl_icon} {pnl:+.2f} USDT ({pnl_pct:+.2f}%)")
            
            # Verificar órdenes
            orders = trader.client.futures_get_open_orders(symbol=symbol)
            
            sl_count = sum(1 for o in orders if 'STOP' in o['type'] and 'TAKE_PROFIT' not in o['type'])
            tp_count = sum(1 for o in orders if 'TAKE_PROFIT' in o['type'])
            
            if sl_count > 0 and tp_count > 0:
                print(f"   ✅ Protegido: {sl_count} SL + {tp_count} TP(s)")
            elif sl_count > 0:
                print(f"   ⚠️  Solo SL configurado ({tp_count} TPs)")
            elif tp_count > 0:
                print(f"   ⚠️  Solo TPs configurados, ¡SIN SL!")
            else:
                print(f"   ❌ ¡SIN PROTECCIÓN!")
            
            print(f"   ⏳ Esperando {interval}s...")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print(f"\n\n⏹️  Monitoreo detenido")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    print("\n👁️ MONITOR DE ÓRDENES EN TIEMPO REAL")
    print("="*80)
    print("1. Monitorear todas las posiciones (actualización cada 10s)")
    print("2. Monitorear un símbolo específico (actualización cada 5s)")
    print("="*80)
    
    choice = input("\nElige una opción (1/2): ")
    
    if choice == "1":
        duration_input = input("Duración en minutos (default: 5): ")
        duration = int(duration_input) * 60 if duration_input else 300
        monitor_orders_realtime(interval=10, duration=duration)
    
    elif choice == "2":
        symbol = input("Ingresa el símbolo (ej: WOOUSDT): ").upper()
        duration_input = input("Duración en minutos (default: 3): ")
        duration = int(duration_input) * 60 if duration_input else 180
        monitor_single_symbol(symbol, interval=5, duration=duration)
    
    else:
        print("❌ Opción inválida")
