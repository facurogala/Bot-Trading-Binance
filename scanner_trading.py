"""
🤖 SCANNER CON TRADING AUTOMÁTICO EN TESTNET
Detecta señales, envía alertas Y ejecuta trades con dinero virtual
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# FORZAR modo trading automático + testnet
os.environ['AUTO_TRADE_ENABLED'] = 'True'
os.environ['TESTNET'] = 'True'

print("\n" + "=" * 60)
print("  🤖 MODO: TRADING AUTOMÁTICO EN TESTNET")
print("=" * 60)
print("✅ El bot detectará señales")
print("✅ Enviará alertas a Telegram")
print("✅ Ejecutará trades automáticamente")
print("🧪 Usando TESTNET (dinero virtual, sin riesgo)")
print("💰 Riesgo por trade: ~50 USDT virtuales")
print("=" * 60)
print()

# Importar y ejecutar el scanner
from auto_trading_scanner import main

if __name__ == "__main__":
    main()
