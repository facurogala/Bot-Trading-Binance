"""
🛡️ SCANNER CON TRADING CONSERVADOR EN TESTNET
Versión mejorada con múltiples filtros de seguridad
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# FORZAR modo trading automático + testnet
os.environ['AUTO_TRADE_ENABLED'] = 'True'
os.environ['TESTNET'] = 'True'

print("\n" + "=" * 60)
print("  🛡️ MODO: TRADING CONSERVADOR EN TESTNET")
print("=" * 60)
print("✅ El bot detectará señales")
print("✅ Enviará alertas a Telegram")
print("✅ Ejecutará trades automáticamente")
print("🧪 Usando TESTNET (dinero virtual, sin riesgo)")
print("🛡️ FILTROS CONSERVADORES ACTIVADOS:")
print("   • Volumen mínimo: 1.2x promedio")
print("   • RSI entre 45-65 (LONG) / 35-55 (SHORT)")
print("   • Solo a favor de tendencia EMA200")
print("   • Stop Loss máximo: 2.5%")
print("   • Distancia mínima entre EMAs: 0.5%")
print("=" * 60)
print()

# Importar y ejecutar el scanner CONSERVADOR
from auto_trading_scanner_conservador import main

if __name__ == "__main__":
    main()
