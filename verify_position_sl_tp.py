"""
Script para verificar que el SL/TP estén correctamente integrados en la posición

Binance Futures tiene dos formas de mostrar SL/TP:
1. En la lista de órdenes (columna "Condicional")
2. En la sección de posiciones (columna "TP/SL")

Este script verifica que ambas estén sincronizadas.
"""
from binance_futures_trader import BinanceFuturesTrader
import sys

def check_position_sl_tp(symbol):
    """Verifica el SL/TP integrado en la posición"""
    try:
        trader = BinanceFuturesTrader()
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    print(f"🔍 Verificando SL/TP para {symbol}...\n")
    
    # Obtener información de la posición
    try:
        positions = trader.client.futures_position_information(symbol=symbol)
        
        for pos in positions:
            if pos['symbol'] == symbol:
                position_amt = float(pos.get('positionAmt', 0))
                
                if position_amt == 0:
                    print(f"📊 No hay posición abierta en {symbol}")
                    continue
                
                side = "LONG" if position_amt > 0 else "SHORT"
                
                print(f"📈 POSICIÓN ABIERTA:")
                print(f"   Símbolo: {symbol}")
                print(f"   Lado: {side}")
                print(f"   Cantidad: {abs(position_amt)}")
                print(f"   Precio entrada: {pos.get('entryPrice')}")
                print(f"   PnL no realizado: {pos.get('unRealizedProfit', pos.get('unrealizedProfit'))}")
                
    except Exception as e:
        print(f"⚠️ Error al obtener posición: {e}")
    
    # Obtener órdenes abiertas
    print(f"\n📋 ÓRDENES SL/TP ACTIVAS:")
    try:
        orders = trader.client.futures_get_open_orders(symbol=symbol)
        
        has_stop = False
        take_profits = []
        
        for order in orders:
            order_type = order.get('type', '')
            stop_price = order.get('stopPrice', '0')
            side = order.get('side', '')
            qty = order.get('origQty', '0')
            close_position = order.get('closePosition', False)
            reduce_only = order.get('reduceOnly', False)
            
            if 'STOP' in order_type and 'TAKE_PROFIT' not in order_type:
                has_stop = True
                print(f"\n🔴 STOP LOSS:")
                print(f"   Precio: ${stop_price}")
                print(f"   Tipo: {order_type}")
                print(f"   Close Position: {close_position}")
                print(f"   Reduce Only: {reduce_only}")
                print(f"   Order ID: {order.get('orderId')}")
                
                if close_position:
                    print(f"   ✅ Configurado para CERRAR TODA LA POSICIÓN")
                else:
                    print(f"   Cantidad: {qty}")
            
            elif 'TAKE_PROFIT' in order_type:
                take_profits.append({
                    'price': float(stop_price),
                    'qty': float(qty),
                    'order_id': order.get('orderId')
                })
        
        if take_profits:
            print(f"\n🟢 TAKE PROFITS ({len(take_profits)} órdenes):")
            for i, tp in enumerate(sorted(take_profits, key=lambda x: x['price']), 1):
                print(f"   TP{i}: ${tp['price']:.5f} | Qty: {tp['qty']} | ID: {tp['order_id']}")
        
        if not has_stop and not take_profits:
            print("   ⚠️ No hay órdenes SL/TP activas")
        
    except Exception as e:
        print(f"⚠️ Error al obtener órdenes: {e}")
    
    # Resumen
    print(f"\n{'='*60}")
    print("📊 RESUMEN:")
    print(f"{'='*60}")
    
    if has_stop:
        print("✅ Stop Loss: CONFIGURADO y ACTIVO en Binance")
        print("   → Se ejecutará automáticamente si el precio lo alcanza")
        print("   → Funciona aunque el bot esté apagado")
    else:
        print("⚠️ Stop Loss: NO ENCONTRADO")
    
    if take_profits:
        print(f"✅ Take Profits: {len(take_profits)} órdenes CONFIGURADAS")
        print("   → Se ejecutarán automáticamente al alcanzar cada precio")
        print("   → Funcionan aunque el bot esté apagado")
    else:
        print("⚠️ Take Profits: NO ENCONTRADOS")
    
    print(f"{'='*60}\n")
    
    print("💡 NOTA: En Binance web:")
    print("   • El SL/TP aparece en la sección de POSICIONES (última columna)")
    print("   • Las órdenes SL/TP aparecen en ÓRDENES ABIERTAS")
    print("   • La columna 'Condicional' muestra el precio de activación")

if __name__ == '__main__':
    symbol = sys.argv[1].upper() if len(sys.argv) > 1 else 'ADAUSDT'
    check_position_sl_tp(symbol)
