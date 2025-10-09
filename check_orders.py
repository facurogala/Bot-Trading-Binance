"""
🔍 Script para verificar órdenes activas en Binance Futures
Muestra todas las órdenes abiertas (SL, TP, LIMIT, etc.)
"""
import os
from binance_futures_trader import BinanceFuturesTrader
from dotenv import load_dotenv

load_dotenv()

def check_all_orders():
    """Verifica todas las órdenes activas en Binance"""
    
    print("="*60)
    print("🔍 VERIFICACIÓN DE ÓRDENES ACTIVAS EN BINANCE")
    print("="*60)
    
    try:
        # Inicializar trader
        trader = BinanceFuturesTrader()
        
        # Obtener todas las posiciones abiertas
        positions = trader.client.futures_position_information()
        
        print(f"\n📊 POSICIONES ABIERTAS:")
        print("="*60)
        
        active_positions = []
        for pos in positions:
            amt = float(pos.get('positionAmt', 0))
            if amt != 0:
                symbol = pos['symbol']
                side = "LONG" if amt > 0 else "SHORT"
                entry_price = float(pos.get('entryPrice', 0))
                unrealized_pnl = float(pos.get('unRealizedProfit', 0))
                
                active_positions.append(symbol)
                
                print(f"\n🔹 {symbol}")
                print(f"   Lado: {side}")
                print(f"   Cantidad: {abs(amt)}")
                print(f"   Precio entrada: {entry_price}")
                print(f"   PnL no realizado: {unrealized_pnl:.2f} USDT")
        
        if not active_positions:
            print("\n   ℹ️  No hay posiciones abiertas")
        
        # Verificar órdenes activas para cada posición
        print(f"\n{'='*60}")
        print(f"📋 ÓRDENES ACTIVAS (SL/TP):")
        print("="*60)
        
        for symbol in active_positions:
            print(f"\n🔹 {symbol}:")
            
            try:
                orders = trader.client.futures_get_open_orders(symbol=symbol)
                
                if not orders:
                    print(f"   ⚠️  ¡SIN ÓRDENES! Esta posición NO tiene SL ni TP configurados")
                    continue
                
                sl_count = 0
                tp_count = 0
                
                for order in orders:
                    order_type = order.get('type', '')
                    order_id = order.get('orderId', '')
                    side = order.get('side', '')
                    stop_price = order.get('stopPrice', '0')
                    quantity = order.get('origQty', '0')
                    status = order.get('status', '')
                    
                    if 'STOP' in order_type and 'TAKE_PROFIT' not in order_type:
                        sl_count += 1
                        print(f"   🛑 Stop Loss:")
                        print(f"      Order ID: {order_id}")
                        print(f"      Tipo: {order_type}")
                        print(f"      Precio: {stop_price}")
                        print(f"      Estado: {status}")
                    
                    elif 'TAKE_PROFIT' in order_type:
                        tp_count += 1
                        print(f"   🎯 Take Profit {tp_count}:")
                        print(f"      Order ID: {order_id}")
                        print(f"      Tipo: {order_type}")
                        print(f"      Precio: {stop_price}")
                        print(f"      Cantidad: {quantity}")
                        print(f"      Estado: {status}")
                
                # Resumen
                print(f"\n   📊 Resumen para {symbol}:")
                print(f"      Stop Loss: {'✅ ' + str(sl_count) if sl_count > 0 else '❌ 0'}")
                print(f"      Take Profits: {'✅ ' + str(tp_count) if tp_count > 0 else '❌ 0'}")
                
                if sl_count == 0:
                    print(f"      ⚠️⚠️⚠️ ¡ADVERTENCIA! Esta posición NO tiene Stop Loss")
                if tp_count == 0:
                    print(f"      ⚠️ Esta posición NO tiene Take Profits")
                    
            except Exception as e:
                print(f"   ❌ Error al obtener órdenes: {e}")
        
        # Verificar si hay órdenes huérfanas (sin posición asociada)
        print(f"\n{'='*60}")
        print(f"🔍 VERIFICANDO ÓRDENES HUÉRFANAS:")
        print("="*60)
        
        try:
            all_orders = trader.client.futures_get_open_orders()
            
            orphan_orders = [o for o in all_orders if o['symbol'] not in active_positions]
            
            if orphan_orders:
                print(f"\n⚠️  Se encontraron {len(orphan_orders)} orden(es) sin posición asociada:")
                for order in orphan_orders:
                    symbol = order.get('symbol', '')
                    order_type = order.get('type', '')
                    order_id = order.get('orderId', '')
                    print(f"   - {symbol}: {order_type} (ID: {order_id})")
                print(f"\n💡 Considera cancelar estas órdenes manualmente")
            else:
                print(f"\n✅ No se encontraron órdenes huérfanas")
                
        except Exception as e:
            print(f"❌ Error al verificar órdenes huérfanas: {e}")
        
        print(f"\n{'='*60}")
        print(f"✅ Verificación completada")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_all_orders()
