"""
Script de verificación del sistema de trading automático
Prueba conexión, balance y configuración antes de trading real
"""
import os
from dotenv import load_dotenv
from binance.client import Client
from binance_futures_trader import BinanceFuturesTrader

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def check_env_config():
    """Verifica configuración del archivo .env"""
    print_section("1️⃣ VERIFICANDO CONFIGURACIÓN .ENV")
    
    load_dotenv()
    
    # Telegram
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    telegram_chat = os.getenv("TELEGRAM_CHAT_ID")
    
    print(f"📱 Telegram Token: {'✅ Configurado' if telegram_token else '❌ Falta'}")
    print(f"📱 Telegram Chat ID: {'✅ Configurado' if telegram_chat else '❌ Falta'}")
    
    # Binance
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    if api_key and api_key != "tu_api_key_aqui":
        print(f"🔑 Binance API Key: ✅ Configurado ({api_key[:8]}...)")
    else:
        print(f"🔑 Binance API Key: ❌ Falta o no configurado")
    
    if api_secret and api_secret != "tu_api_secret_aqui":
        print(f"🔑 Binance API Secret: ✅ Configurado ({api_secret[:8]}...)")
    else:
        print(f"🔑 Binance API Secret: ❌ Falta o no configurado")
    
    # Trading config
    auto_trade = os.getenv("AUTO_TRADE_ENABLED", "False")
    leverage = os.getenv("LEVERAGE", "5")
    risk = os.getenv("RISK_PERCENT", "1.0")
    max_pos = os.getenv("MAX_POSITIONS", "3")
    
    print(f"\n⚙️ Auto Trading: {'🤖 ACTIVADO' if auto_trade.lower() == 'true' else '📢 DESACTIVADO (solo alertas)'}")
    print(f"⚙️ Leverage: {leverage}x")
    print(f"⚙️ Riesgo por trade: {risk}%")
    print(f"⚙️ Max posiciones: {max_pos}")
    
    # Validación
    if not api_key or api_key == "tu_api_key_aqui":
        print("\n⚠️ IMPORTANTE: Configura tus API Keys de Binance en .env")
        return False
    
    return True

def check_binance_connection():
    """Verifica conexión con Binance Futures"""
    print_section("2️⃣ PROBANDO CONEXIÓN CON BINANCE FUTURES")
    
    try:
        trader = BinanceFuturesTrader()
        print("✅ Autenticación exitosa con Binance Futures")
        
        # Balance
        balance = trader.get_account_balance()
        print(f"💰 Balance disponible: {balance:.2f} USDT")
        
        if balance < 10:
            print("⚠️ ADVERTENCIA: Balance muy bajo. Recomendado: mínimo $50-100")
        elif balance < 50:
            print("⚠️ Balance bajo. Considera agregar más fondos para trading real")
        else:
            print("✅ Balance adecuado para trading")
        
        return trader, balance
        
    except Exception as e:
        print(f"❌ ERROR: No se pudo conectar con Binance")
        print(f"   Detalle: {e}")
        print("\n💡 Soluciones:")
        print("   1. Verifica que tus API Keys sean correctas")
        print("   2. Asegúrate de habilitar permisos de Futures en Binance")
        print("   3. Revisa que no tengas restricciones de IP")
        return None, 0

def check_open_positions(trader):
    """Muestra posiciones abiertas"""
    print_section("3️⃣ POSICIONES ABIERTAS")
    
    try:
        positions = trader.get_open_positions()
        
        if not positions:
            print("✅ No hay posiciones abiertas actualmente")
        else:
            print(f"📊 Posiciones abiertas: {len(positions)}\n")
            total_pnl = 0
            
            for pos in positions:
                pnl_emoji = "🟢" if pos['unrealizedProfit'] > 0 else "🔴"
                print(f"{pnl_emoji} {pos['symbol']}")
                print(f"   Lado: {pos['side']}")
                print(f"   Cantidad: {pos['quantity']}")
                print(f"   Precio entrada: {pos['entryPrice']}")
                print(f"   PnL: {pos['unrealizedProfit']:.2f} USDT")
                print(f"   Leverage: {pos['leverage']}x")
                print()
                total_pnl += pos['unrealizedProfit']
            
            emoji = "🟢" if total_pnl > 0 else "🔴"
            print(f"{emoji} PnL Total: {total_pnl:.2f} USDT")
            
    except Exception as e:
        print(f"❌ Error al obtener posiciones: {e}")

def check_symbol_info(trader):
    """Prueba obtención de info de símbolos"""
    print_section("4️⃣ PROBANDO INFORMACIÓN DE SÍMBOLOS")
    
    test_symbols = ["BTCUSDT", "ETHUSDT"]
    
    for symbol in test_symbols:
        try:
            info = trader.get_symbol_info(symbol)
            if info:
                print(f"✅ {symbol}")
                print(f"   Precisión precio: {info['pricePrecision']}")
                print(f"   Precisión cantidad: {info['quantityPrecision']}")
            else:
                print(f"⚠️ {symbol}: No se pudo obtener información")
        except Exception as e:
            print(f"❌ {symbol}: Error → {e}")

def calculate_position_example(trader, balance):
    """Muestra ejemplo de cálculo de posición"""
    print_section("5️⃣ EJEMPLO DE CÁLCULO DE POSICIÓN")
    
    if balance < 10:
        print("⚠️ Balance insuficiente para mostrar ejemplo")
        return
    
    # Ejemplo con BTC
    symbol = "BTCUSDT"
    entry_price = 45000.0
    sl_price = 44000.0  # 2.22% de stop loss
    
    print(f"Ejemplo de trade en {symbol}:")
    print(f"  Precio entrada: ${entry_price:,.2f}")
    print(f"  Stop Loss: ${sl_price:,.2f}")
    print(f"  Distancia SL: {((entry_price - sl_price) / entry_price * 100):.2f}%")
    print()
    
    # Calcular tamaño
    try:
        quantity = trader.calculate_position_size(symbol, entry_price, sl_price)
        position_value = quantity * entry_price * trader.leverage
        max_loss = balance * (trader.risk_percent / 100)
        
        print(f"💼 Balance: ${balance:.2f} USDT")
        print(f"⚙️ Leverage: {trader.leverage}x")
        print(f"⚠️ Riesgo configurado: {trader.risk_percent}%")
        print()
        print(f"📊 Tamaño calculado: {quantity:.5f} BTC")
        print(f"💰 Valor nominal: ${position_value:.2f}")
        print(f"🛡️ Pérdida máxima: ${max_loss:.2f}")
        print()
        
        if max_loss / balance > 0.05:
            print("⚠️ ADVERTENCIA: Riesgo superior al 5% por trade")
            print("   Considera reducir RISK_PERCENT en .env")
        else:
            print("✅ Nivel de riesgo apropiado")
            
    except Exception as e:
        print(f"❌ Error al calcular posición: {e}")

def check_watchlist():
    """Verifica que los símbolos en watchlist existan en Binance Futures"""
    print_section("6️⃣ VERIFICANDO WATCHLIST")
    
    from auto_trading_scanner import WATCHLIST
    
    print(f"Verificando {len(WATCHLIST)} símbolos...\n")
    
    client = Client()
    try:
        exchange_info = client.futures_exchange_info()
        valid_symbols = [s['symbol'] for s in exchange_info['symbols'] if s['status'] == 'TRADING']
        
        invalid = []
        for symbol in WATCHLIST:
            if symbol in valid_symbols:
                print(f"✅ {symbol}")
            else:
                print(f"❌ {symbol} - No disponible en Binance Futures")
                invalid.append(symbol)
        
        if invalid:
            print(f"\n⚠️ Símbolos inválidos encontrados: {', '.join(invalid)}")
            print("   Considera removerlos de WATCHLIST en auto_trading_scanner.py")
        else:
            print(f"\n✅ Todos los símbolos son válidos")
            
    except Exception as e:
        print(f"❌ Error al verificar watchlist: {e}")

def show_recommendations():
    """Muestra recomendaciones finales"""
    print_section("7️⃣ RECOMENDACIONES")
    
    load_dotenv()
    auto_trade = os.getenv("AUTO_TRADE_ENABLED", "False").lower() == "true"
    
    if auto_trade:
        print("🤖 TRADING AUTOMÁTICO ACTIVADO")
        print()
        print("⚠️ IMPORTANTE - Antes de ejecutar el bot:")
        print("   1. ✅ Verifica que todos los checks anteriores pasaron")
        print("   2. ✅ Revisa tu configuración de riesgo")
        print("   3. ✅ Asegúrate de tener fondos suficientes")
        print("   4. ✅ Entiende los riesgos del trading con apalancamiento")
        print("   5. ✅ Monitorea las primeras operaciones")
        print()
        print("🚀 Para iniciar el bot:")
        print("   python auto_trading_scanner.py")
    else:
        print("📢 MODO SOLO ALERTAS ACTIVADO")
        print()
        print("✅ Configuración segura para empezar:")
        print("   - El bot detectará señales")
        print("   - Enviará alertas a Telegram")
        print("   - NO ejecutará trades automáticamente")
        print()
        print("🚀 Para iniciar el bot:")
        print("   python auto_trading_scanner.py")
        print()
        print("💡 Cuando estés listo para trading automático:")
        print("   1. Edita .env y cambia AUTO_TRADE_ENABLED=True")
        print("   2. Ajusta LEVERAGE y RISK_PERCENT según tu tolerancia")
        print("   3. Ejecuta nuevamente este script de verificación")

def main():
    print("\n" + "="*60)
    print("  🧪 VERIFICACIÓN DEL SISTEMA DE TRADING AUTOMÁTICO")
    print("="*60)
    
    # Check 1: Configuración
    if not check_env_config():
        print("\n❌ Configuración incompleta. Por favor completa el archivo .env")
        return
    
    # Check 2: Conexión
    trader, balance = check_binance_connection()
    if not trader:
        print("\n❌ No se pudo establecer conexión con Binance")
        print("   Completa la configuración y vuelve a intentar")
        return
    
    # Check 3: Posiciones abiertas
    check_open_positions(trader)
    
    # Check 4: Info de símbolos
    check_symbol_info(trader)
    
    # Check 5: Ejemplo de cálculo
    calculate_position_example(trader, balance)
    
    # Check 6: Watchlist
    check_watchlist()
    
    # Recomendaciones finales
    show_recommendations()
    
    print("\n" + "="*60)
    print("  ✅ VERIFICACIÓN COMPLETADA")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
