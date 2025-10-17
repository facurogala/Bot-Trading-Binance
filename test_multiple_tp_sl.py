"""
🧪 Test de creación de múltiples Take Profits y Stop Loss
Este script verifica que se crean correctamente múltiples TPs y SL en Binance
"""
import os
from binance_futures_trader import BinanceFuturesTrader
from dotenv import load_dotenv

load_dotenv()

def test_order_creation(symbol: str = None):
    """Test de creación de órdenes con múltiples TPs"""
    
    print("="*60)
    print("🧪 TEST: Creación de múltiples Take Profits y Stop Loss")
    print("="*60)
    
    try:
        # Inicializar trader
        trader = BinanceFuturesTrader(context="test_multiple_tp_sl")
        
        # Si no se proporciona símbolo, permitir elegir
        if not symbol:
            print("\n💰 MONEDAS DISPONIBLES PARA TEST:")
            print("="*60)
            
            test_symbols = {
                "1": {"symbol": "WOOUSDT", "name": "WOO", "desc": "Bajo precio, ideal para test"},
                "2": {"symbol": "GALAUSDT", "name": "GALA", "desc": "Gaming token, volátil"},
                "3": {"symbol": "DOGEUSDT", "name": "DOGE", "desc": "Meme coin popular"},
                "4": {"symbol": "TRXUSDT", "name": "TRX", "desc": "Bajo precio, alta liquidez"},
                "5": {"symbol": "XRPUSDT", "name": "XRP", "desc": "Top coin, mucha liquidez"},
                "6": {"symbol": "ADAUSDT", "name": "ADA", "desc": "Cardano, estable"},
                "7": {"symbol": "MATICUSDT", "name": "MATIC", "desc": "Polygon, L2 popular"},
                "8": {"symbol": "DOTUSDT", "name": "DOT", "desc": "Polkadot"},
                "9": {"symbol": "LINKUSDT", "name": "LINK", "desc": "Chainlink, oráculos"},
                "0": {"symbol": "CUSTOM", "name": "CUSTOM", "desc": "Ingresar manualmente"}
            }
            
            for key, info in test_symbols.items():
                print(f"   {key}. {info['name']:8} - {info['desc']}")
            
            choice = input("\n👉 Elige una opción (1-9, 0 para custom): ")
            
            if choice == "0":
                symbol = input("   Ingresa el símbolo (ej: BTCUSDT): ").upper()
                if not symbol.endswith("USDT"):
                    symbol += "USDT"
            elif choice in test_symbols:
                symbol = test_symbols[choice]["symbol"]
            else:
                print("❌ Opción inválida, usando WOO por defecto")
                symbol = "WOOUSDT"
        
        print(f"\n📊 Obteniendo precio actual de {symbol}...")
        ticker = trader.client.futures_symbol_ticker(symbol=symbol)
        current_price = float(ticker['price'])
        print(f"   Precio actual: {current_price}")
        
        # Configurar una señal SHORT de ejemplo
        side = "SHORT"
        entry_price = current_price
        
        # Calcular SL y TPs para SHORT
        sl_price = entry_price * 1.02  # SL 2% arriba (para SHORT)
        tp_prices = [
            entry_price * 0.99,  # TP1: -1%
            entry_price * 0.98,  # TP2: -2%
            entry_price * 0.97   # TP3: -3%
        ]
        
        print(f"\n📋 Configuración del test:")
        print(f"   Lado: {side}")
        print(f"   Entry: {entry_price}")
        print(f"   SL: {sl_price} (+2%)")
        print(f"   TP1: {tp_prices[0]} (-1%)")
        print(f"   TP2: {tp_prices[1]} (-2%)")
        print(f"   TP3: {tp_prices[2]} (-3%)")
        
        # Preguntar confirmación
        print(f"\n⚠️  Este test abrirá una posición REAL en {symbol}")
        print(f"   Asegúrate de estar en TESTNET o de tener fondos suficientes")
        
        testnet = os.getenv("TESTNET", "False").lower() == "true"
        if testnet:
            print(f"\n🧪 Modo: TESTNET (seguro para probar)")
        else:
            print(f"\n💰 Modo: PRODUCCIÓN (¡SE USARÁ DINERO REAL!)")
        
        confirm = input("\n¿Continuar con el test? (si/no): ")
        if confirm.lower() != "si":
            print("❌ Test cancelado")
            return
        
        # Ejecutar la orden
        print(f"\n🚀 Abriendo posición de prueba...")
        result = trader.open_position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_prices=tp_prices,
            force_market=True  # Usar orden market para test rápido
        )
        
        if result:
            print(f"\n{'='*60}")
            print(f"✅ TEST EXITOSO")
            print(f"{'='*60}")
            print(f"\n📊 Resumen:")
            print(f"   Symbol: {result['symbol']}")
            print(f"   Side: {result['side']}")
            print(f"   Quantity: {result['quantity']}")
            print(f"   Entry: {result['entry_price']}")
            print(f"   SL: {result['sl_price']}")
            print(f"   TPs: {result['tp_prices']}")
            print(f"\n📋 Órdenes creadas:")
            print(f"   Entry Order: {result['entry_order'].get('orderId')}")
            if result.get('sl_order'):
                print(f"   SL Order: {result['sl_order'].get('orderId')}")
            else:
                print(f"   ❌ SL Order: NO CREADA")
            
            print(f"\n   Take Profits:")
            for i, tp_order in enumerate(result['tp_orders'], 1):
                print(f"      TP{i}: {tp_order.get('orderId')} @ {result['tp_prices'][i-1]}")
            
            if len(result['tp_orders']) < len(tp_prices):
                print(f"\n   ⚠️ ADVERTENCIA: Solo se crearon {len(result['tp_orders'])}/{len(tp_prices)} TPs")
            
            # Instrucciones para cerrar
            print(f"\n{'='*60}")
            print(f"🔧 Para cerrar esta posición de prueba:")
            print(f"{'='*60}")
            print(f"1. Ve a Binance Futures")
            print(f"2. Busca la posición en {symbol}")
            print(f"3. Cierra la posición manualmente")
            print(f"   O espera a que se ejecute el SL/TP")
            print(f"\nAlternativamente, ejecuta:")
            print(f"   trader.close_position('{symbol}')")
            
        else:
            print(f"\n❌ TEST FALLIDO: No se pudo abrir la posición")
            
    except Exception as e:
        print(f"\n❌ Error en el test: {e}")
        import traceback
        traceback.print_exc()

def test_multiple_symbols():
    """Test con múltiples símbolos en secuencia"""
    
    print("\n" + "="*60)
    print("🔄 TEST MÚLTIPLE: Varias monedas en secuencia")
    print("="*60)
    
    symbols = input("\nIngresa símbolos separados por coma (ej: WOO,GALA,DOGE) o deja vacío para usar [WOO, GALA, TRX]: ")
    
    if symbols.strip():
        symbol_list = [s.strip().upper() + "USDT" if not s.strip().upper().endswith("USDT") else s.strip().upper() 
                      for s in symbols.split(",")]
    else:
        symbol_list = ["WOOUSDT", "GALAUSDT", "TRXUSDT"]
    
    print(f"\n📋 Se probarán {len(symbol_list)} símbolos: {', '.join(symbol_list)}")
    
    confirm = input("\n¿Continuar? (si/no): ")
    if confirm.lower() != "si":
        print("❌ Test cancelado")
        return
    
    results = []
    
    for i, symbol in enumerate(symbol_list, 1):
        print(f"\n{'='*60}")
        print(f"🔄 TEST {i}/{len(symbol_list)}: {symbol}")
        print(f"{'='*60}")
        
        try:
            result = test_order_creation(symbol=symbol)
            results.append({"symbol": symbol, "success": result is not None, "result": result})
            
            if i < len(symbol_list):
                print(f"\n⏳ Esperando 3 segundos antes del siguiente test...")
                import time
                time.sleep(3)
                
        except Exception as e:
            print(f"\n❌ Error en {symbol}: {e}")
            results.append({"symbol": symbol, "success": False, "result": None})
    
    # Resumen final
    print(f"\n{'='*60}")
    print(f"📊 RESUMEN DE TESTS MÚLTIPLES")
    print(f"{'='*60}\n")
    
    success_count = sum(1 for r in results if r["success"])
    
    for result in results:
        status = "✅" if result["success"] else "❌"
        print(f"{status} {result['symbol']}")
    
    print(f"\n📈 Éxito: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
    
    if success_count == len(results):
        print("\n🎉 ¡Todos los tests fueron exitosos!")
    elif success_count > 0:
        print(f"\n⚠️ {len(results) - success_count} test(s) fallaron")
    else:
        print("\n❌ Todos los tests fallaron")


if __name__ == "__main__":
    import sys
    
    print("\n🧪 SCRIPT DE TEST - Múltiples TP y SL")
    print("="*60)
    print("1. Test con una moneda (elegir del menú)")
    print("2. Test con múltiples monedas en secuencia")
    print("3. Test rápido con WOO (default)")
    print("="*60)
    
    if len(sys.argv) > 1:
        # Modo CLI: python test_multiple_tp_sl.py WOOUSDT
        symbol = sys.argv[1].upper()
        if not symbol.endswith("USDT"):
            symbol += "USDT"
        print(f"\n💡 Modo CLI: Testeando {symbol}")
        test_order_creation(symbol=symbol)
    else:
        # Modo interactivo
        choice = input("\n👉 Elige una opción (1/2/3): ")
        
        if choice == "1":
            test_order_creation()
        elif choice == "2":
            test_multiple_symbols()
        elif choice == "3":
            print("\n💡 Test rápido con WOO")
            test_order_creation(symbol="WOOUSDT")
        else:
            print("❌ Opción inválida, usando test con menú")
            test_order_creation()
