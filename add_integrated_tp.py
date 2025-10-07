"""
Script para añadir Take Profit integrado a posiciones existentes

Este script toma el TP1 de cada posición y lo configura como TP integrado
para que aparezca en la columna "TP/SL" de Binance web.

Mantiene los otros TPs como órdenes separadas.
"""
from binance_futures_trader import BinanceFuturesTrader
from order_reconciler import OrderReconciler

def add_integrated_tp_to_positions():
    """Añade TP integrado a todas las posiciones abiertas"""
    try:
        trader = BinanceFuturesTrader()
        reconciler = OrderReconciler(trader)
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    print("="*60)
    print("🔧 AÑADIENDO TP INTEGRADO A POSICIONES")
    print("="*60)
    
    # Obtener posiciones abiertas
    positions = trader.get_open_positions()
    
    if not positions:
        print("\n⚠️ No hay posiciones abiertas")
        return
    
    print(f"\n📊 Encontradas {len(positions)} posición(es)\n")
    
    for pos in positions:
        symbol = pos['symbol']
        side = pos['side']
        sl_price = pos.get('stopLoss')
        tp_prices = pos.get('takeProfits', [])
        
        print(f"\n{'='*60}")
        print(f"📈 {symbol} - {side}")
        print(f"{'='*60}")
        print(f"   Entry: ${pos['entryPrice']:.5f}")
        print(f"   Cantidad: {pos['quantity']}")
        print(f"   PnL: {pos['unrealizedProfit']:+.2f} USDT")
        
        if sl_price:
            print(f"   🔴 SL actual: ${sl_price:.5f}")
        
        if tp_prices:
            print(f"   🟢 TPs actuales: {len(tp_prices)} órdenes")
            for i, tp in enumerate(tp_prices, 1):
                print(f"      TP{i}: ${tp:.5f}")
            
            # Usar el TP1 como TP integrado
            tp1 = tp_prices[0]
            
            print(f"\n💡 Configurando TP integrado en ${tp1:.5f}...")
            
            # Intentar configurar TP integrado
            success = reconciler.set_position_tp_sl(
                symbol=symbol,
                side=side,
                tp_price=tp1,
                sl_price=sl_price
            )
            
            if success:
                print(f"   ✅ TP integrado configurado")
                print(f"   💡 Ahora debería aparecer en columna TP/SL: {tp1:.5f} / {sl_price:.5f}")
            else:
                print(f"   ℹ️ Método integrado no disponible en esta versión de API")
                print(f"   ℹ️ Las órdenes TP/SL separadas seguirán funcionando correctamente")
        else:
            print(f"   ⚠️ No hay TPs configurados")
    
    print(f"\n{'='*60}")
    print("📊 PROCESO COMPLETADO")
    print(f"{'='*60}\n")
    
    print("💡 NOTA:")
    print("   • Si el método integrado no está disponible, tus órdenes")
    print("     seguirán funcionando correctamente como están")
    print("   • El SL y TPs se ejecutarán automáticamente")
    print("   • La protección es la misma aunque no aparezca en TP/SL column")

if __name__ == '__main__':
    add_integrated_tp_to_positions()
