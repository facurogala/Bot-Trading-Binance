"""
Script rápido para cerrar posición de ADAUSDT y crear SL/TP manualmente

Uso:
  python fix_adausdt_position.py
"""
from binance_futures_trader import BinanceFuturesTrader
from order_reconciler import OrderReconciler

def main():
    symbol = "ADAUSDT"
    
    print("="*60)
    print(f"🔧 FIX: Añadir SL/TP a posición existente en {symbol}")
    print("="*60)
    
    try:
        trader = BinanceFuturesTrader()
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    # Ver posición actual
    print(f"\n📊 Verificando posición...")
    positions = trader.get_open_positions()
    
    target_pos = None
    for pos in positions:
        if pos['symbol'] == symbol:
            target_pos = pos
            break
    
    if not target_pos:
        print(f"❌ No hay posición abierta en {symbol}")
        return
    
    print(f"\n✅ Posición encontrada:")
    print(f"   Side: {target_pos['side']}")
    print(f"   Cantidad: {target_pos['quantity']}")
    print(f"   Precio entrada: ${target_pos['entryPrice']:.5f}")
    print(f"   PnL actual: {target_pos['unrealizedProfit']:+.2f} USDT")
    
    # Calcular SL/TP sugeridos
    entry = target_pos['entryPrice']
    side = target_pos['side']
    qty = target_pos['quantity']
    
    # SL a 2% de distancia
    sl_dist = 0.02
    if side == "LONG":
        sl_price = entry * (1 - sl_dist)
        tp1 = entry * (1 + sl_dist)
        tp2 = entry * (1 + sl_dist * 1.5)
        tp3 = entry * (1 + sl_dist * 2)
    else:
        sl_price = entry * (1 + sl_dist)
        tp1 = entry * (1 - sl_dist)
        tp2 = entry * (1 - sl_dist * 1.5)
        tp3 = entry * (1 - sl_dist * 2)
    
    print(f"\n📈 Niveles sugeridos (2% risk):")
    print(f"   🔴 SL: ${sl_price:.5f}")
    print(f"   🟢 TP1: ${tp1:.5f} (R:R 1:1)")
    print(f"   🟢 TP2: ${tp2:.5f} (R:R 1.5:1)")
    print(f"   🟢 TP3: ${tp3:.5f} (R:R 2:1)")
    
    print(f"\n📋 Opciones:")
    print(f"1. Crear SL/TP con niveles sugeridos")
    print(f"2. Cerrar posición inmediatamente")
    print(f"3. Cancelar")
    
    choice = input("\nElige opción (1/2/3): ").strip()
    
    if choice == "1":
        print(f"\n🔄 Creando SL/TP...")
        
        reconciler = OrderReconciler(trader)
        
        # Crear órdenes
        sl_order, tp_orders = reconciler.ensure_orders_exist(
            symbol=symbol,
            side=side,
            quantity=qty,
            sl_price=sl_price,
            tp_prices=[tp1, tp2, tp3],
            max_retries=3
        )
        
        if sl_order and len(tp_orders) > 0:
            print(f"\n✅ SL/TP creados exitosamente!")
            print(f"   SL Order: {sl_order.get('orderId')}")
            for i, tp in enumerate(tp_orders, 1):
                print(f"   TP{i} Order: {tp.get('orderId')}")
            
            # Verificar
            print(f"\n🔍 Verificando en Binance...")
            import subprocess
            import sys
            subprocess.run([sys.executable, "debug_orders.py", symbol])
        else:
            print(f"⚠️ No se pudieron crear todas las órdenes")
            print(f"   SL: {'✅' if sl_order else '❌'}")
            print(f"   TPs: {len(tp_orders)}/3")
    
    elif choice == "2":
        confirm = input(f"\n⚠️ ¿Cerrar posición en {symbol}? (si/no): ")
        if confirm.lower() in ['si', 's', 'yes', 'y']:
            print(f"\n🔄 Cerrando posición...")
            if trader.close_position(symbol):
                print(f"✅ Posición cerrada")
            else:
                print(f"❌ Error al cerrar")
        else:
            print("Cancelado")
    
    else:
        print("❌ Cancelado")

if __name__ == '__main__':
    main()
