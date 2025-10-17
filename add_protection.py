"""
🛡️ Script para agregar SL/TP a posiciones existentes sin protección
Útil para posiciones abiertas que no tienen Stop Loss o Take Profits configurados
"""
import os
from binance_futures_trader import BinanceFuturesTrader
from dotenv import load_dotenv

load_dotenv()

def add_protection_to_position(symbol: str, manual_sl: float = None, manual_tps: list = None):
    """
    Agrega SL y TPs a una posición existente
    
    Args:
        symbol: Símbolo de la posición (ej: WOOUSDT)
        manual_sl: Precio del SL (opcional, se calcula automáticamente si no se provee)
        manual_tps: Lista de precios de TPs (opcional, se calculan automáticamente)
    """
    
    print("="*60)
    print(f"🛡️ AGREGANDO PROTECCIÓN A POSICIÓN EXISTENTE: {symbol}")
    print("="*60)
    
    try:
        trader = BinanceFuturesTrader(context="add_protection")
        
        # Obtener información de la posición
        positions = trader.client.futures_position_information(symbol=symbol)
        
        position = None
        for pos in positions:
            amt = float(pos.get('positionAmt', 0))
            if amt != 0:
                position = pos
                break
        
        if not position:
            print(f"❌ No se encontró una posición abierta en {symbol}")
            return
        
        # Datos de la posición
        position_amt = float(position['positionAmt'])
        side = "LONG" if position_amt > 0 else "SHORT"
        quantity = abs(position_amt)
        entry_price = float(position['entryPrice'])
        
        print(f"\n📊 Posición encontrada:")
        print(f"   Símbolo: {symbol}")
        print(f"   Lado: {side}")
        print(f"   Cantidad: {quantity}")
        print(f"   Precio entrada: {entry_price}")
        
        # Verificar órdenes existentes
        existing_orders = trader.client.futures_get_open_orders(symbol=symbol)
        
        has_sl = False
        has_tp = False
        
        for order in existing_orders:
            order_type = order.get('type', '')
            if 'STOP' in order_type and 'TAKE_PROFIT' not in order_type:
                has_sl = True
            elif 'TAKE_PROFIT' in order_type:
                has_tp = True
        
        print(f"\n🔍 Estado actual de protección:")
        print(f"   Stop Loss: {'✅ Configurado' if has_sl else '❌ NO configurado'}")
        print(f"   Take Profits: {'✅ Configurados' if has_tp else '❌ NO configurados'}")
        
        if has_sl and has_tp:
            print(f"\n✅ Esta posición ya tiene SL y TP configurados")
            return
        
        # Calcular SL y TPs si no se proporcionaron
        if not manual_sl:
            # SL automático: 2% del precio de entrada
            if side == "LONG":
                manual_sl = entry_price * 0.98  # 2% abajo para LONG
            else:
                manual_sl = entry_price * 1.02  # 2% arriba para SHORT
            print(f"\n💡 SL calculado automáticamente: {manual_sl:.6f} (2% del entry)")
        
        if not manual_tps:
            # TPs automáticos
            if side == "LONG":
                manual_tps = [
                    entry_price * 1.015,  # TP1: +1.5%
                    entry_price * 1.025,  # TP2: +2.5%
                    entry_price * 1.040   # TP3: +4.0%
                ]
            else:
                manual_tps = [
                    entry_price * 0.985,  # TP1: -1.5%
                    entry_price * 0.975,  # TP2: -2.5%
                    entry_price * 0.960   # TP3: -4.0%
                ]
            print(f"💡 TPs calculados automáticamente:")
            for i, tp in enumerate(manual_tps, 1):
                pct = ((tp / entry_price) - 1) * 100
                print(f"   TP{i}: {tp:.6f} ({pct:+.2f}%)")
        
        print(f"\n⚠️  Se configurará:")
        print(f"   Stop Loss: {manual_sl}")
        print(f"   Take Profits: {manual_tps}")
        
        confirm = input("\n¿Continuar? (si/no): ")
        if confirm.lower() != "si":
            print("❌ Operación cancelada")
            return
        
        # Obtener información del símbolo
        symbol_info = trader.get_symbol_info(symbol)
        price_precision = symbol_info['pricePrecision'] if symbol_info else 2
        
        # Crear Stop Loss si no existe
        if not has_sl:
            print(f"\n🛑 Creando Stop Loss...")
            sl_side = "SELL" if side == "LONG" else "BUY"
            sl_price = round(manual_sl, price_precision)
            
            try:
                sl_order = trader.client.futures_create_order(
                    symbol=symbol,
                    side=sl_side,
                    type="STOP_MARKET",
                    stopPrice=sl_price,
                    closePosition=True
                )
                print(f"✅ Stop Loss creado: ID {sl_order['orderId']} @ {sl_price}")
            except Exception as e:
                print(f"❌ Error creando Stop Loss: {e}")
        
        # Crear Take Profits si no existen
        if not has_tp:
            print(f"\n🎯 Creando {len(manual_tps)} Take Profits...")
            
            tp_side = "SELL" if side == "LONG" else "BUY"
            tp_quantity = quantity / len(manual_tps)
            
            # Ajustar por LOT_SIZE
            if symbol_info:
                for f in symbol_info['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        step_size = float(f['stepSize'])
                        tp_quantity = trader.round_step_size(tp_quantity, step_size)
                        break
            
            for i, tp_price in enumerate(manual_tps, 1):
                # Último TP toma el resto
                if i == len(manual_tps):
                    use_qty = quantity - (tp_quantity * (len(manual_tps) - 1))
                else:
                    use_qty = tp_quantity
                
                tp_price_rounded = round(tp_price, price_precision)
                
                try:
                    tp_order = trader.client.futures_create_order(
                        symbol=symbol,
                        side=tp_side,
                        type="TAKE_PROFIT_MARKET",
                        stopPrice=tp_price_rounded,
                        quantity=use_qty,
                        reduceOnly=True
                    )
                    print(f"✅ TP{i} creado: ID {tp_order['orderId']} @ {tp_price_rounded} | Qty: {use_qty}")
                except Exception as e:
                    print(f"❌ Error creando TP{i}: {e}")
        
        print(f"\n{'='*60}")
        print(f"✅ Protección agregada exitosamente a {symbol}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def protect_all_positions():
    """Agrega protección a todas las posiciones abiertas sin SL/TP"""
    
    print("="*60)
    print("🛡️ PROTEGIENDO TODAS LAS POSICIONES SIN SL/TP")
    print("="*60)
    
    try:
        trader = BinanceFuturesTrader(context="add_protection")
        
        # Obtener todas las posiciones
        positions = trader.client.futures_position_information()
        
        unprotected = []
        
        for pos in positions:
            amt = float(pos.get('positionAmt', 0))
            if amt != 0:
                symbol = pos['symbol']
                
                # Verificar si tiene órdenes
                orders = trader.client.futures_get_open_orders(symbol=symbol)
                
                has_sl = any('STOP' in o.get('type', '') and 'TAKE_PROFIT' not in o.get('type', '') for o in orders)
                has_tp = any('TAKE_PROFIT' in o.get('type', '') for o in orders)
                
                if not has_sl or not has_tp:
                    unprotected.append(symbol)
        
        if not unprotected:
            print(f"\n✅ Todas las posiciones están protegidas")
            return
        
        print(f"\n⚠️  Se encontraron {len(unprotected)} posición(es) sin protección:")
        for symbol in unprotected:
            print(f"   - {symbol}")
        
        confirm = input(f"\n¿Agregar protección automática a todas? (si/no): ")
        if confirm.lower() != "si":
            print("❌ Operación cancelada")
            return
        
        for symbol in unprotected:
            print(f"\n{'='*60}")
            add_protection_to_position(symbol)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    print("\n🛡️ SCRIPT DE PROTECCIÓN DE POSICIONES")
    print("="*60)
    print("1. Proteger una posición específica")
    print("2. Proteger todas las posiciones sin SL/TP")
    print("="*60)
    
    choice = input("\nElige una opción (1/2): ")
    
    if choice == "1":
        symbol = input("Ingresa el símbolo (ej: WOOUSDT): ").upper()
        add_protection_to_position(symbol)
    elif choice == "2":
        protect_all_positions()
    else:
        print("❌ Opción inválida")
