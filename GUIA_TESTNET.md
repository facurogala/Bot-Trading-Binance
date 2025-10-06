# 🧪 Guía para Usar Binance Testnet (Cuenta Demo)

## ¿Qué es Binance Testnet?

Binance Testnet es un **entorno de pruebas gratuito** que simula el trading real de Binance Futures, pero con dinero virtual. Es perfecto para:

- ✅ Probar estrategias sin riesgo
- ✅ Aprender a usar el sistema
- ✅ Verificar que el bot funcione correctamente
- ✅ Practicar sin invertir dinero real

**Balance inicial:** 10,000 USDT virtuales (puedes recargar cuando quieras)

---

## 🚀 Paso 1: Crear Cuenta en Testnet

### 1. Ve a Binance Futures Testnet:
```
https://testnet.binancefuture.com/
```

### 2. Inicia sesión:
- Puedes usar tu cuenta de **GitHub** o **Google**
- NO necesitas cuenta de Binance
- Es completamente gratis

### 3. Una vez dentro:
- Verás que tienes **10,000 USDT** de balance virtual
- La interfaz es idéntica a Binance Futures real

---

## 🔑 Paso 2: Obtener API Keys de Testnet

### 1. En la Testnet, haz clic en tu perfil (arriba a la derecha)

### 2. Busca la opción **"API Key"**

### 3. Genera una nueva API Key:
- Dale un nombre: "Trading Bot Test"
- **Copia la API Key** (algo como: `abcd1234efgh5678...`)
- **Copia el Secret** (aparece solo una vez)

### 4. Permisos necesarios:
- ✅ Enable Reading
- ✅ Enable Futures Trading
- ❌ NO Enable Withdrawals

---

## ⚙️ Paso 3: Configurar el Bot para Testnet

### 1. Abre tu archivo `.env`

### 2. Reemplaza las API Keys con las de Testnet:
```env
# ===== BINANCE FUTURES API =====
BINANCE_API_KEY=tu_api_key_de_testnet_aqui
BINANCE_API_SECRET=tu_secret_de_testnet_aqui
```

### 3. **IMPORTANTE:** Activa el modo Testnet:
```env
# Modo testnet para pruebas (True/False)
TESTNET=True
```

### 4. Puedes activar trading automático sin miedo:
```env
# Activar/desactivar trading automático (True/False)
AUTO_TRADE_ENABLED=True
```

---

## ✅ Paso 4: Verificar Configuración

```bash
python diagnose_api.py
```

Deberías ver:
```
🧪 Modo: TESTNET (Cuenta Demo)
✅ Autenticación FUTURES TESTNET exitosa ✨
💰 Balance Futures: 10000.00 USDT
```

---

## 🤖 Paso 5: Ejecutar el Bot en Testnet

```bash
python auto_trading_scanner.py
```

El bot:
- ✅ Usará dinero virtual (10,000 USDT)
- ✅ Ejecutará trades reales en el entorno de prueba
- ✅ NO arriesgará dinero real
- ✅ Enviará alertas a Telegram normalmente

---

## 📊 Configuración Recomendada para Testnet

Como es dinero virtual, puedes ser más agresivo para probar:

```env
# .env para Testnet
TESTNET=True
AUTO_TRADE_ENABLED=True
USE_MARKET_ORDER=True          # Órdenes market para ejecución inmediata
LEVERAGE=10                    # Puedes probar con leverage alto
RISK_PERCENT=2.0              # Mayor riesgo para ver resultados rápido
MAX_POSITIONS=5               # Más posiciones simultáneas
```

---

## 🔄 Cambiar de Testnet a Producción

### Cuando estés listo para usar dinero real:

1. **Obtén tus API Keys de Binance REAL:**
   - Ve a: https://www.binance.com/es/my/settings/api-management
   - Crea API Keys con permisos de Futures

2. **Actualiza tu `.env`:**
   ```env
   BINANCE_API_KEY=tu_api_key_real_de_binance
   BINANCE_API_SECRET=tu_secret_real_de_binance
   
   # ¡IMPORTANTE! Cambia esto:
   TESTNET=False
   
   # Usa configuración más conservadora:
   LEVERAGE=5
   RISK_PERCENT=1.0
   MAX_POSITIONS=3
   ```

3. **Transfiere fondos reales a Binance Futures:**
   - Binance → Wallet → Transfer
   - De: Spot → A: USD(S)-M Futures
   - Monto: Mínimo $50-100

4. **Verifica:**
   ```bash
   python diagnose_api.py
   ```

5. **Ejecuta:**
   ```bash
   python auto_trading_scanner.py
   ```

---

## 📱 Monitorear Testnet

### Desde la Web:
Abre: https://testnet.binancefuture.com/
- Ve tus posiciones abiertas
- Revisa el historial de trades
- Ve el PnL (ganancias/pérdidas)

### Desde el Bot:
```bash
python manage_positions.py
```

---

## 💡 Ventajas de Testnet

✅ **Sin riesgo:** Dinero 100% virtual
✅ **Balance ilimitado:** Puedes recargar cuando quieras
✅ **Entorno real:** Precios y datos reales del mercado
✅ **Prueba completa:** Todas las funciones del bot
✅ **Aprende sin presión:** Experimenta libremente

---

## ⚠️ Limitaciones de Testnet

❌ **No ganas dinero real:** Las ganancias son virtuales
❌ **Liquidez diferente:** Puede haber menos liquidez que en producción
❌ **Sin emociones:** No sentirás el miedo/codicia del trading real
❌ **Slippage diferente:** Las órdenes pueden ejecutarse distinto

---

## 🎯 Plan Recomendado

### Semana 1-2: Testnet
```env
TESTNET=True
AUTO_TRADE_ENABLED=True
LEVERAGE=5-10
RISK_PERCENT=2.0
```
- Deja correr el bot
- Monitorea resultados
- Ajusta parámetros
- Aprende el sistema

### Semana 3+: Producción (si los resultados son buenos)
```env
TESTNET=False
AUTO_TRADE_ENABLED=True
LEVERAGE=3-5
RISK_PERCENT=1.0
```
- Empieza con capital pequeño ($100-500)
- Monitorea MUY de cerca
- Aumenta gradualmente

---

## 🆘 Solución de Problemas

### "No se puede conectar a Testnet"
→ Verifica que usaste las API Keys de https://testnet.binancefuture.com
→ NO uses las API Keys de Binance real

### "Balance sigue en 0"
→ En testnet.binancefuture.com, busca opción para "recargar balance"
→ O crea una nueva cuenta de testnet

### "El bot no ejecuta trades"
→ Verifica: `TESTNET=True` y `AUTO_TRADE_ENABLED=True` en .env
→ Ejecuta: `python diagnose_api.py`

---

## 📞 Archivos de Configuración

### .env para TESTNET:
```env
BINANCE_API_KEY=tu_key_de_testnet
BINANCE_API_SECRET=tu_secret_de_testnet
TESTNET=True
AUTO_TRADE_ENABLED=True
LEVERAGE=10
RISK_PERCENT=2.0
MAX_POSITIONS=5
```

### .env para PRODUCCIÓN:
```env
BINANCE_API_KEY=tu_key_real_de_binance
BINANCE_API_SECRET=tu_secret_real
TESTNET=False
AUTO_TRADE_ENABLED=True
LEVERAGE=5
RISK_PERCENT=1.0
MAX_POSITIONS=3
```

---

**🎓 RECOMENDACIÓN:** Usa Testnet por al menos 1-2 semanas antes de pasar a dinero real. Esto te permitirá entender el sistema, ajustar parámetros y ganar confianza sin riesgo.

---

**📌 Enlaces Importantes:**
- Testnet: https://testnet.binancefuture.com/
- Binance Real: https://www.binance.com/es/futures/BTCUSDT
- API Management Real: https://www.binance.com/es/my/settings/api-management
