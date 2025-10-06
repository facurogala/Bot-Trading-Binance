"""
Diagnóstico detallado de API Keys de Binance
Ayuda a identificar problemas específicos con las credenciales
"""
import os
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException

load_dotenv()

def test_api_keys():
    print("\n" + "="*60)
    print("  🔍 DIAGNÓSTICO DE API KEYS DE BINANCE")
    print("="*60 + "\n")
    
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    testnet = os.getenv("TESTNET", "False").lower() == "true"
    
    if not api_key or not api_secret:
        print("❌ No se encontraron API Keys en .env")
        return
    
    print(f"🔑 API Key: {api_key[:10]}...{api_key[-10:]}")
    print(f"🔑 Secret: {api_secret[:10]}...{api_secret[-10:]}")
    
    if testnet:
        print(f"🧪 Modo: TESTNET (Cuenta Demo)")
        client = Client(api_key, api_secret, testnet=True)
        # URLs correctas para testnet
        client.API_URL = 'https://testnet.binance.vision/api'
        client.FUTURES_URL = 'https://testnet.binancefuture.com/fapi'
        client.FUTURES_DATA_URL = 'https://testnet.binancefuture.com/fapi'
        client.FUTURES_COIN_URL = 'https://testnet.binancefuture.com/dapi'
        client.FUTURES_COIN_DATA_URL = 'https://testnet.binancefuture.com/dapi'
    else:
        print(f"💰 Modo: PRODUCCIÓN (Cuenta Real)")
        client = Client(api_key, api_secret)
    
    # Test 1: Ping básico (sin autenticación)
    print("\n" + "-"*60)
    print("Test 1: Conexión básica a Binance")
    print("-"*60)
    try:
        client.ping()
        print("✅ Conexión a Binance establecida (servidor responde)")
    except Exception as e:
        print(f"❌ No se pudo conectar a Binance: {e}")
        print("   → Verifica tu conexión a internet")
        return
    
    # Test 2: Autenticación Spot (solo si no es testnet)
    if not testnet:
        print("\n" + "-"*60)
        print("Test 2: Autenticación en Binance Spot")
        print("-"*60)
        try:
            account = client.get_account()
            print("✅ Autenticación SPOT exitosa")
            print(f"   → API Key válida para Spot trading")
        except BinanceAPIException as e:
            print(f"❌ Error en Spot: {e}")
            if e.code == -2015:
                print("   → API Key inválida o sin permisos")
                print("   → Verifica que la API Key esté activa en Binance")
            elif e.code == -2014:
                print("   → API Key/Secret incorrectos")
                print("   → Copia nuevamente desde Binance")
            return
    else:
        print("\n" + "-"*60)
        print("Test 2: Autenticación Spot - OMITIDO (modo testnet)")
        print("-"*60)
    
    # Test 3: Autenticación Futures
    print("\n" + "-"*60)
    if testnet:
        print("Test 3: Autenticación en Binance FUTURES TESTNET")
    else:
        print("Test 3: Autenticación en Binance FUTURES")
    print("-"*60)
    try:
        futures_account = client.futures_account()
        print("✅ Autenticación FUTURES exitosa ✨")
        print(f"   → API Key tiene permisos de Futures")
        
        # Mostrar balance
        balance = 0
        for asset in futures_account['assets']:
            if asset['asset'] == 'USDT':
                balance = float(asset['availableBalance'])
                break
        
        print(f"   → Balance Futures: {balance:.2f} USDT")
        
        if balance < 10:
            print("\n⚠️ Balance muy bajo en Futures")
            print("   → Transfiere fondos: Binance → Wallet → Transfer")
            print("   → De Spot a Futures")
        
    except BinanceAPIException as e:
        print(f"❌ Error en Futures: {e}")
        print(f"   Código: {e.code}")
        
        if e.code == -2015:
            print("\n❌ PROBLEMA IDENTIFICADO:")
            print("   Tu API Key NO tiene permisos de Futures habilitados")
            print("\n📋 SOLUCIÓN:")
            print("   1. Ve a: https://www.binance.com/es/my/settings/api-management")
            print("   2. Busca tu API Key actual")
            print("   3. Haz clic en 'Editar restricciones'")
            print("   4. ✅ Marca: 'Enable Futures' o 'Habilitar Futuros'")
            print("   5. Guarda los cambios")
            print("   6. Espera 1-2 minutos y ejecuta este script nuevamente")
            print("\n   O CREA UNA NUEVA API KEY con permisos de Futures")
            
        elif e.code == -2014:
            print("\n❌ PROBLEMA IDENTIFICADO:")
            print("   API Key o Secret incorrectos para Futures")
            print("\n📋 SOLUCIÓN:")
            print("   1. Ve a Binance y crea una nueva API Key")
            print("   2. Asegúrate de marcar 'Enable Futures'")
            print("   3. Copia la nueva API Key y Secret en .env")
            
        else:
            print(f"\n❌ Error desconocido (código {e.code})")
            print("   Consulta: https://binance-docs.github.io/apidocs/spot/en/#error-codes")
        
        return False
    
    # Test 4: Permisos adicionales
    print("\n" + "-"*60)
    print("Test 4: Verificando permisos adicionales")
    print("-"*60)
    
    try:
        # Test órdenes (sin ejecutar)
        exchange_info = client.futures_exchange_info()
        print("✅ Puede leer información del exchange")
    except:
        print("⚠️ No puede leer información del exchange")
    
    # Test 5: Restricciones de IP
    print("\n" + "-"*60)
    print("Test 5: Restricciones de IP")
    print("-"*60)
    
    try:
        account_info = client.get_account()
        api_perms = account_info.get('permissions', [])
        print(f"✅ Permisos detectados: {', '.join(api_perms) if api_perms else 'No especificados'}")
        
        # Intentar detectar restricción de IP
        print("   → Si llegaste hasta aquí, tu IP está autorizada")
        
    except BinanceAPIException as e:
        if 'IP' in str(e):
            print("❌ Tu IP puede estar bloqueada")
            print("   → Ve a Binance → API Management")
            print("   → Edita tu API Key y ajusta restricciones de IP")
    
    print("\n" + "="*60)
    print("  ✅ DIAGNÓSTICO COMPLETADO")
    print("="*60)
    return True

def show_instructions():
    print("\n" + "="*60)
    print("  📚 GUÍA RÁPIDA: CONFIGURAR API KEYS DE FUTURES")
    print("="*60)
    print("""
1️⃣ Ve a Binance:
   https://www.binance.com/es/my/settings/api-management

2️⃣ Opción A - Editar API Key existente:
   • Haz clic en 'Editar restricciones'
   • ✅ Marca: 'Enable Futures' 
   • ✅ Marca: 'Enable Reading'
   • Guarda cambios

3️⃣ Opción B - Crear nueva API Key:
   • Haz clic en 'Crear API'
   • Nombre: "Trading Bot Futures"
   • Permisos:
     ✅ Enable Futures ← CRÍTICO
     ✅ Enable Reading
     ❌ Enable Withdrawals (NO marcar por seguridad)
   • Restricción IP: 'Sin restricción' (al principio)
   • Copia API Key y Secret

4️⃣ Actualizar .env:
   • Pega la nueva API Key y Secret en .env
   • Ejecuta: python diagnose_api.py

5️⃣ Si necesitas fondos en Futures:
   • Binance App/Web → Wallet → Transfer
   • De: Spot → A: USD(S)-M Futures
   • Monto: mínimo $50-100 para empezar
""")

if __name__ == "__main__":
    result = test_api_keys()
    
    if not result:
        show_instructions()
    else:
        print("\n✅ TODO FUNCIONA CORRECTAMENTE")
        print("   Puedes ejecutar: python verify_setup.py")
        print("   O directamente: python auto_trading_scanner.py")
