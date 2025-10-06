"""
🔔 SCANNER SOLO ALERTAS
Detecta señales y envía alertas a Telegram
NO ejecuta trades automáticamente
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# FORZAR modo solo alertas
os.environ['AUTO_TRADE_ENABLED'] = 'False'

print("\n" + "=" * 60)
print("  🔔 MODO: SOLO ALERTAS (Sin Trading)")
print("=" * 60)
print("✅ El bot detectará señales")
print("✅ Enviará alertas a Telegram")
print("❌ NO ejecutará trades automáticamente")
print("❌ NO usará dinero (ni real ni virtual)")
print("=" * 60)
print()

# Importar y ejecutar el scanner
from auto_trading_scanner import main

if __name__ == "__main__":
    main()
