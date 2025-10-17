"""
✅ CHECKLIST VISUAL - Verificación del Sistema de Múltiples TP/SL
Ejecuta este script para verificar que todo está configurado correctamente
"""
import os
from binance_futures_trader import BinanceFuturesTrader
from dotenv import load_dotenv

load_dotenv()

def check_icon(condition, success_msg, fail_msg):
    """Muestra un icono de check o error según la condición"""
    if condition:
        print(f"✅ {success_msg}")
        return True
    else:
        print(f"❌ {fail_msg}")
        return False

def check_system():
    """Verifica todos los componentes del sistema"""
    
    print("\n" + "="*80)
    print("✅ CHECKLIST DEL SISTEMA - Múltiples TP/SL")
    print("="*80 + "\n")
    
    all_ok = True
    
    # ===== 1. VARIABLES DE ENTORNO =====
    print("📋 1. VERIFICANDO VARIABLES DE ENTORNO")
    print("-" * 80)
    
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    telegram_chat = os.getenv("TELEGRAM_CHAT_ID")
    testnet = os.getenv("TESTNET", "False").lower() == "true"
    auto_trade = os.getenv("AUTO_TRADE_ENABLED", "False").lower() == "true"
    
    all_ok &= check_icon(
        api_key and len(api_key) > 20,
        "BINANCE_API_KEY configurada",
        "BINANCE_API_KEY no encontrada o inválida"
    )
    
    all_ok &= check_icon(
        api_secret and len(api_secret) > 20,
        "BINANCE_API_SECRET configurada",
        "BINANCE_API_SECRET no encontrada o inválida"
    )
    
    check_icon(
        telegram_token,
        "TELEGRAM_TOKEN configurado",
        "TELEGRAM_TOKEN no configurado (opcional)"
    )
    
    check_icon(
        telegram_chat,
        "TELEGRAM_CHAT_ID configurado",
        "TELEGRAM_CHAT_ID no configurado (opcional)"
    )
    
    if testnet:
        print(f"🧪 Modo: TESTNET (seguro para probar)")
    else:
        print(f"💰 Modo: PRODUCCIÓN (¡dinero real!)")
    
    if auto_trade:
        print(f"🤖 Trading automático: ACTIVADO")
    else:
        print(f"⏸️  Trading automático: DESACTIVADO")
    
    # ===== 2. CONEXIÓN CON BINANCE =====
    print(f"\n📋 2. VERIFICANDO CONEXIÓN CON BINANCE")
    print("-" * 80)
    
    try:
        trader = BinanceFuturesTrader(context="verify_system")
        all_ok &= check_icon(True, "Conexión establecida correctamente", "")
    except Exception as e:
        all_ok &= check_icon(False, "", f"Error de conexión: {e}")
        print("\n❌ No se puede continuar sin conexión a Binance")
        return False
    
    # ===== 3. BALANCE =====
    print(f"\n📋 3. VERIFICANDO BALANCE")
    print("-" * 80)
    
    try:
        balance = trader.get_account_balance()
        all_ok &= check_icon(
            balance > 0,
            f"Balance disponible: {balance:.2f} USDT",
            "Balance es 0 USDT"
        )
        
        if testnet and balance > 10000:
            print(f"   💡 En testnet tienes fondos ilimitados virtuales")
        elif not testnet and balance < 50:
            print(f"   ⚠️  Balance bajo para trading real")
            
    except Exception as e:
        all_ok &= check_icon(False, "", f"Error al obtener balance: {e}")
    
    # ===== 4. POSICIONES ACTUALES =====
    print(f"\n📋 4. VERIFICANDO POSICIONES ABIERTAS")
    print("-" * 80)
    
    try:
        positions = trader.client.futures_position_information()
        active_positions = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
        
        if active_positions:
            print(f"📊 {len(active_positions)} posición(es) abierta(s):")
            
            for pos in active_positions:
                symbol = pos['symbol']
                amt = float(pos['positionAmt'])
                side = "LONG" if amt > 0 else "SHORT"
                pnl = float(pos['unRealizedProfit'])
                
                print(f"\n   🔹 {symbol} - {side}")
                print(f"      PnL: {pnl:+.2f} USDT")
                
                # Verificar órdenes SL/TP
                orders = trader.client.futures_get_open_orders(symbol=symbol)
                
                has_sl = any('STOP' in o['type'] and 'TAKE_PROFIT' not in o['type'] for o in orders)
                has_tp = any('TAKE_PROFIT' in o['type'] for o in orders)
                tp_count = sum(1 for o in orders if 'TAKE_PROFIT' in o['type'])
                
                if has_sl and has_tp:
                    check_icon(True, f"Protegido: 1 SL + {tp_count} TP(s)", "")
                elif has_sl:
                    check_icon(False, "", "Solo tiene SL, sin TPs")
                    all_ok = False
                elif has_tp:
                    check_icon(False, "", "Solo tiene TPs, ¡SIN SL!")
                    all_ok = False
                else:
                    check_icon(False, "", "¡SIN PROTECCIÓN! (sin SL ni TP)")
                    all_ok = False
        else:
            print(f"ℹ️  No hay posiciones abiertas (OK)")
            
    except Exception as e:
        print(f"⚠️  Error al verificar posiciones: {e}")
    
    # ===== 5. ARCHIVOS DEL SISTEMA =====
    print(f"\n📋 5. VERIFICANDO ARCHIVOS DEL SISTEMA")
    print("-" * 80)
    
    required_files = [
        "binance_futures_trader.py",
        "auto_trading_scanner.py",
        "auto_trading_scanner_haack.py",
        "order_reconciler.py",
        "trading_database.py",
        "check_orders.py",
        "test_multiple_tp_sl.py",
        "add_protection.py",
        "monitor_orders_realtime.py"
    ]
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    for file in required_files:
        file_path = os.path.join(base_path, file)
        exists = os.path.exists(file_path)
        check_icon(
            exists,
            f"{file}",
            f"{file} no encontrado"
        )
        if not exists and file not in ["check_orders.py", "test_multiple_tp_sl.py", "add_protection.py", "monitor_orders_realtime.py"]:
            all_ok = False
    
    # ===== 6. CONFIGURACIÓN DE TRADING =====
    print(f"\n📋 6. VERIFICANDO CONFIGURACIÓN DE TRADING")
    print("-" * 80)
    
    leverage = int(os.getenv("LEVERAGE", "5"))
    risk_percent = float(os.getenv("RISK_PERCENT", "1.0"))
    max_positions = int(os.getenv("MAX_POSITIONS", "3"))
    use_market = os.getenv("USE_MARKET_ORDER", "False").lower() == "true"
    
    print(f"⚙️  Apalancamiento: {leverage}x")
    print(f"⚙️  Riesgo por trade: {risk_percent}%")
    print(f"⚙️  Máximo de posiciones: {max_positions}")
    print(f"⚙️  Tipo de orden: {'MARKET' if use_market else 'LIMIT'}")
    
    if leverage > 10:
        print(f"   ⚠️  Apalancamiento alto (>10x), riesgo elevado")
    if risk_percent > 2:
        print(f"   ⚠️  Riesgo por trade alto (>2%), considera reducirlo")
    
    # ===== RESUMEN FINAL =====
    print(f"\n{'='*80}")
    print(f"📊 RESUMEN FINAL")
    print(f"{'='*80}\n")
    
    if all_ok:
        print("✅✅✅ SISTEMA COMPLETAMENTE OPERATIVO ✅✅✅")
        print("\n🚀 Puedes iniciar el trading automático con:")
        print("   python auto_trading_scanner_haack.py")
        print("\n💡 Recomendaciones:")
        print("   1. Monitorea en tiempo real: python monitor_orders_realtime.py")
        print("   2. Verifica órdenes periódicamente: python check_orders.py")
        
        if not testnet:
            print("\n⚠️  ESTÁS EN MODO PRODUCCIÓN (dinero real)")
            print("   Considera probar en testnet primero")
        
    else:
        print("❌ HAY PROBLEMAS QUE NECESITAN ATENCIÓN")
        print("\n🔧 Acciones recomendadas:")
        
        if not api_key or not api_secret:
            print("   1. Configura tus API keys en el archivo .env")
        
        if active_positions:
            has_unprotected = False
            for pos in active_positions:
                symbol = pos['symbol']
                orders = trader.client.futures_get_open_orders(symbol=symbol)
                has_sl = any('STOP' in o['type'] for o in orders)
                if not has_sl:
                    has_unprotected = True
                    break
            
            if has_unprotected:
                print("   2. ¡URGENTE! Agrega protección: python add_protection.py")
        
        print("   3. Revisa los errores marcados arriba")
        print("   4. Consulta SOLUCION_MULTIPLES_TP_SL.md para más ayuda")
    
    print(f"\n{'='*80}\n")
    
    return all_ok


if __name__ == "__main__":
    try:
        result = check_system()
        exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ Error crítico durante la verificación: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
