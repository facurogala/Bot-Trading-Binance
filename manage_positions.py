"""
Utilidades para gestión manual de posiciones en Binance Futures
Permite cerrar posiciones, cancelar órdenes, ver balance, etc.
"""
import sys
from binance_futures_trader import BinanceFuturesTrader
from dotenv import load_dotenv

load_dotenv()

def show_menu():
    print("\n" + "="*60)
    print("  🎛️ GESTOR DE POSICIONES - BINANCE FUTURES")
    print("="*60)
    print("\n1. 📊 Ver balance")
    print("2. 📈 Ver posiciones abiertas")
    print("3. 📋 Ver órdenes pendientes")
    print("4. ❌ Cerrar una posición")
    print("5. 🗑️ Cancelar todas las órdenes de un símbolo")
    print("6. 🚨 CERRAR TODAS LAS POSICIONES (Emergencia)")
    print("7. 🔄 Ver historial de trades reciente")
    print("0. 🚪 Salir")
    print()

def show_balance(trader):
    """Muestra el balance de la cuenta"""
    print("\n" + "="*60)
    print("  💰 BALANCE DE CUENTA")
    print("="*60 + "\n")
    
    try:
        account = trader.client.futures_account()
        
        # Balance total
        total_wallet = float(account['totalWalletBalance'])
        available = float(account['availableBalance'])
        total_unrealized = float(account['totalUnrealizedProfit'])
        
        print(f"💼 Balance Total: {total_wallet:.2f} USDT")
        print(f"✅ Disponible: {available:.2f} USDT")
        print(f"{'🟢' if total_unrealized >= 0 else '🔴'} PnL No Realizado: {total_unrealized:.2f} USDT")
        print(f"📊 Balance + PnL: {total_wallet + total_unrealized:.2f} USDT")
        
    except Exception as e:
        print(f"❌ Error al obtener balance: {e}")

def show_positions(trader):
    """Muestra las posiciones abiertas"""
    print("\n" + "="*60)
    print("  📈 POSICIONES ABIERTAS")
    print("="*60 + "\n")
    
    try:
        positions = trader.get_open_positions()
        
        if not positions:
            print("✅ No hay posiciones abiertas")
            return []
        
        total_pnl = 0
        
        for i, pos in enumerate(positions, 1):
            pnl = pos['unrealizedProfit']
            pnl_pct = (pnl / (pos['entryPrice'] * pos['quantity'])) * 100
            pnl_emoji = "🟢" if pnl > 0 else "🔴"
            
            print(f"{i}. {pnl_emoji} {pos['symbol']}")
            print(f"   Lado: {pos['side']}")
            print(f"   Cantidad: {pos['quantity']}")
            print(f"   Precio entrada: ${pos['entryPrice']:.4f}")
            print(f"   Leverage: {pos['leverage']}x")
            
            # Stop Loss
            if pos.get('stopLoss'):
                sl_dist = abs(pos['entryPrice'] - pos['stopLoss']) / pos['entryPrice'] * 100
                print(f"   🔴 Stop Loss: ${pos['stopLoss']:.4f} (-{sl_dist:.2f}%)")
            else:
                print(f"   🔴 Stop Loss: No configurado")
            
            # Take Profits
            if pos.get('takeProfits') and len(pos['takeProfits']) > 0:
                for j, tp in enumerate(pos['takeProfits'], 1):
                    tp_dist = abs(tp - pos['entryPrice']) / pos['entryPrice'] * 100
                    print(f"   🟢 TP{j}: ${tp:.4f} (+{tp_dist:.2f}%)")
            else:
                print(f"   🟢 Take Profits: No configurados")
            
            # PnL
            print(f"   {pnl_emoji} PnL: {pnl:+.2f} USDT ({pnl_pct:+.2f}%)")
            print()
            
            total_pnl += pnl
        
        emoji = "🟢" if total_pnl > 0 else "🔴"
        print(f"{emoji} PnL Total: {total_pnl:.2f} USDT")
        
        return positions
        
    except Exception as e:
        print(f"❌ Error al obtener posiciones: {e}")
        return []

def show_open_orders(trader):
    """Muestra las órdenes pendientes"""
    print("\n" + "="*60)
    print("  📋 ÓRDENES PENDIENTES")
    print("="*60 + "\n")
    
    try:
        orders = trader.client.futures_get_open_orders()
        
        if not orders:
            print("✅ No hay órdenes pendientes")
            return
        
        symbols_with_orders = {}
        
        for order in orders:
            symbol = order['symbol']
            if symbol not in symbols_with_orders:
                symbols_with_orders[symbol] = []
            symbols_with_orders[symbol].append(order)
        
        for symbol, symbol_orders in symbols_with_orders.items():
            print(f"📊 {symbol} - {len(symbol_orders)} orden(es):")
            
            for order in symbol_orders:
                order_type = order['type']
                side = order['side']
                
                if order_type == "LIMIT":
                    print(f"   • {side} {order_type} @ {float(order['price']):.4f}")
                elif order_type in ["STOP_MARKET", "TAKE_PROFIT_MARKET"]:
                    print(f"   • {side} {order_type} @ {float(order['stopPrice']):.4f}")
                else:
                    print(f"   • {side} {order_type}")
            
            print()
            
    except Exception as e:
        print(f"❌ Error al obtener órdenes: {e}")

def close_position(trader):
    """Cierra una posición específica"""
    positions = show_positions(trader)
    
    if not positions:
        return
    
    try:
        choice = input("\n¿Qué posición deseas cerrar? (número o 0 para cancelar): ")
        
        if choice == "0":
            print("Operación cancelada")
            return
        
        idx = int(choice) - 1
        
        if idx < 0 or idx >= len(positions):
            print("❌ Número inválido")
            return
        
        pos = positions[idx]
        symbol = pos['symbol']
        
        confirm = input(f"\n⚠️ ¿Confirmas cerrar la posición de {symbol}? (si/no): ")
        
        if confirm.lower() in ['si', 'sí', 's', 'yes', 'y']:
            print(f"\n🔄 Cerrando posición en {symbol}...")
            
            if trader.close_position(symbol):
                print(f"✅ Posición cerrada exitosamente en {symbol}")
            else:
                print(f"❌ No se pudo cerrar la posición")
        else:
            print("Operación cancelada")
            
    except ValueError:
        print("❌ Entrada inválida")
    except Exception as e:
        print(f"❌ Error: {e}")

def cancel_orders(trader):
    """Cancela todas las órdenes de un símbolo"""
    try:
        symbol = input("\n📊 Ingresa el símbolo (ej: BTCUSDT): ").upper().strip()
        
        if not symbol:
            print("Operación cancelada")
            return
        
        confirm = input(f"\n⚠️ ¿Confirmas cancelar TODAS las órdenes de {symbol}? (si/no): ")
        
        if confirm.lower() in ['si', 'sí', 's', 'yes', 'y']:
            print(f"\n🔄 Cancelando órdenes en {symbol}...")
            
            if trader.cancel_all_orders(symbol):
                print(f"✅ Órdenes canceladas en {symbol}")
            else:
                print(f"❌ No se pudieron cancelar las órdenes")
        else:
            print("Operación cancelada")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def close_all_positions(trader):
    """EMERGENCIA: Cierra todas las posiciones"""
    print("\n" + "="*60)
    print("  🚨 ADVERTENCIA - CIERRE DE EMERGENCIA")
    print("="*60)
    print("\nEsto cerrará TODAS las posiciones abiertas inmediatamente")
    
    positions = trader.get_open_positions()
    
    if not positions:
        print("\n✅ No hay posiciones abiertas")
        return
    
    print(f"\n⚠️ Se cerrarán {len(positions)} posición(es):")
    for pos in positions:
        print(f"  - {pos['symbol']}: {pos['side']}")
    
    confirm = input("\n⚠️⚠️⚠️ ¿ESTÁS SEGURO? Escribe 'CERRAR TODO' para confirmar: ")
    
    if confirm == "CERRAR TODO":
        print("\n🔄 Cerrando todas las posiciones...")
        
        closed = 0
        failed = 0
        
        for pos in positions:
            try:
                if trader.close_position(pos['symbol']):
                    print(f"✅ {pos['symbol']} cerrada")
                    closed += 1
                else:
                    print(f"❌ Error al cerrar {pos['symbol']}")
                    failed += 1
            except Exception as e:
                print(f"❌ Error en {pos['symbol']}: {e}")
                failed += 1
        
        print(f"\n📊 Resumen: {closed} cerradas, {failed} fallidas")
    else:
        print("Operación cancelada")

def show_recent_trades(trader):
    """Muestra el historial de trades reciente"""
    print("\n" + "="*60)
    print("  🔄 HISTORIAL DE TRADES RECIENTE")
    print("="*60 + "\n")
    
    try:
        # Obtener posiciones cerradas recientemente (últimos 7 días)
        income = trader.client.futures_income_history(incomeType='REALIZED_PNL', limit=20)
        
        if not income:
            print("No hay trades recientes")
            return
        
        total_pnl = 0
        winning_trades = 0
        losing_trades = 0
        
        print("Últimas 20 operaciones cerradas:\n")
        
        for item in income:
            pnl = float(item['income'])
            symbol = item['symbol']
            time = item['time']
            
            emoji = "🟢" if pnl > 0 else "🔴"
            
            from datetime import datetime
            dt = datetime.fromtimestamp(time / 1000)
            date_str = dt.strftime("%Y-%m-%d %H:%M")
            
            print(f"{emoji} {symbol:12} | {date_str} | {pnl:+8.2f} USDT")
            
            total_pnl += pnl
            if pnl > 0:
                winning_trades += 1
            else:
                losing_trades += 1
        
        total_trades = winning_trades + losing_trades
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        print(f"\n{'='*60}")
        print(f"📊 Estadísticas:")
        print(f"   Total trades: {total_trades}")
        print(f"   Ganadores: {winning_trades} 🟢")
        print(f"   Perdedores: {losing_trades} 🔴")
        print(f"   Win Rate: {win_rate:.1f}%")
        print(f"   PnL Total: {total_pnl:+.2f} USDT {'🟢' if total_pnl >= 0 else '🔴'}")
        
    except Exception as e:
        print(f"❌ Error al obtener historial: {e}")

def main():
    try:
        trader = BinanceFuturesTrader()
    except Exception as e:
        print(f"❌ Error al conectar con Binance: {e}")
        print("\n💡 Asegúrate de tener configuradas tus API Keys en .env")
        return
    
    while True:
        show_menu()
        
        try:
            choice = input("Selecciona una opción: ").strip()
            
            if choice == "0":
                print("\n👋 ¡Hasta luego!")
                break
            elif choice == "1":
                show_balance(trader)
            elif choice == "2":
                show_positions(trader)
            elif choice == "3":
                show_open_orders(trader)
            elif choice == "4":
                close_position(trader)
            elif choice == "5":
                cancel_orders(trader)
            elif choice == "6":
                close_all_positions(trader)
            elif choice == "7":
                show_recent_trades(trader)
            else:
                print("\n❌ Opción inválida")
            
            input("\n[Presiona Enter para continuar...]")
            
        except KeyboardInterrupt:
            print("\n\n👋 ¡Hasta luego!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            input("\n[Presiona Enter para continuar...]")

if __name__ == "__main__":
    main()
