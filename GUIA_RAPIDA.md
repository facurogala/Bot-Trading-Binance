# 🚀 Guía Rápida - Trading Automático Binance Futures

## 📋 Pasos Iniciales

### 1. Instalar dependencias
```bash
pip install python-binance pandas pandas-ta python-dotenv requests
```

### 2. Configurar API Keys

Edita el archivo `.env` y agrega tus credenciales:
```env
BINANCE_API_KEY=tu_api_key_real
BINANCE_API_SECRET=tu_secret_real

# Para empezar, deja esto en False
AUTO_TRADE_ENABLED=False
```

### 3. Verificar configuración
```bash
python verify_setup.py
```

Este comando verifica:
- ✅ Conexión con Binance
- ✅ Balance disponible
- ✅ Configuración correcta
- ✅ Posiciones abiertas

---

## 🎯 Comandos Principales

### 📊 Ver tu cuenta y posiciones
```bash
python manage_positions.py
```
Menu interactivo para:
- Ver balance
- Ver posiciones abiertas
- Cerrar posiciones
- Cancelar órdenes
- Ver historial

### 🤖 Iniciar el bot (SOLO ALERTAS)
```bash
python auto_trading_scanner.py
```
Con `AUTO_TRADE_ENABLED=False`:
- ✅ Detecta señales
- ✅ Envía alertas a Telegram
- ❌ NO ejecuta trades

### 🚀 Trading Automático (CUIDADO!)

1. Primero ejecuta: `python verify_setup.py`
2. Edita `.env` y cambia:
```env
AUTO_TRADE_ENABLED=True
LEVERAGE=5              # Tu apalancamiento deseado
RISK_PERCENT=1.0        # % de riesgo por trade
MAX_POSITIONS=3         # Posiciones simultáneas máximas
```
3. Ejecuta: `python auto_trading_scanner.py`

---

## ⚙️ Configuración Recomendada

### Conservador (Principiante)
```env
AUTO_TRADE_ENABLED=True
LEVERAGE=3
RISK_PERCENT=0.5
MAX_POSITIONS=2
USE_MARKET_ORDER=False
```

### Moderado
```env
AUTO_TRADE_ENABLED=True
LEVERAGE=5
RISK_PERCENT=1.0
MAX_POSITIONS=3
USE_MARKET_ORDER=False
```

### Agresivo (Experimentado)
```env
AUTO_TRADE_ENABLED=True
LEVERAGE=10
RISK_PERCENT=2.0
MAX_POSITIONS=5
USE_MARKET_ORDER=True
```

---

## 📱 Cómo Funciona

1. **El bot escanea** cada 30 minutos buscando cruces de EMA 20/50
2. **Detecta señal** LONG o SHORT
3. **Calcula niveles**:
   - 📍 Zona de entrada (entre EMAs)
   - 🔴 Stop Loss (swing low/high + buffer)
   - 🟢 Take Profits (3 niveles basados en ATR)
4. **Si AUTO_TRADE_ENABLED=True**:
   - Abre posición en Binance Futures
   - Configura SL y TPs automáticamente
   - Envía confirmación a Telegram

---

## 🛡️ Gestión de Riesgo

### Fórmula de Tamaño de Posición
```
Riesgo por Trade = Balance × RISK_PERCENT / 100
Tamaño Posición = Riesgo / (Distancia_SL × Leverage)
```

### Ejemplo Práctico
- Balance: $1000
- RISK_PERCENT: 1% = $10 de riesgo máximo
- SL a 2% del precio
- Leverage: 5x
- **Tamaño: $10 / 0.02 / 5 = $100 nominal**

---

## ⚠️ Checklist Antes de Empezar

- [ ] API Keys configuradas correctamente
- [ ] Permisos de Futures habilitados en Binance
- [ ] `verify_setup.py` ejecutado sin errores
- [ ] Balance suficiente en cuenta Futures ($50-100 mínimo)
- [ ] Probado primero con `AUTO_TRADE_ENABLED=False`
- [ ] Entiendes los riesgos del apalancamiento
- [ ] Configuraste RISK_PERCENT apropiado (≤2%)
- [ ] Probaste `manage_positions.py` para ver cómo cerrar posiciones

---

## 🚨 Comandos de Emergencia

### Ver posiciones rápidamente
```bash
python binance_futures_trader.py
```

### Gestionar posiciones manualmente
```bash
python manage_positions.py
# Opción 6: Cerrar TODAS las posiciones
```

### Detener el bot
```
Ctrl + C
```

---

## 📊 Monitoreo

El bot muestra en consola:
```
📊 POSICIONES ABIERTAS (2):
  BTCUSDT: LONG | Qty: 0.05 | Entry: 45000 | PnL: 125.50 USDT
  ETHUSDT: SHORT | Qty: 1.2 | Entry: 2500 | PnL: -15.30 USDT
  💰 PnL Total: 110.20 USDT
```

También envía alertas a Telegram con cada operación.

---

## 💡 Tips Importantes

1. **Empieza con solo alertas** (`AUTO_TRADE_ENABLED=False`)
2. **Usa capital que puedas perder**
3. **No uses más de 10x de apalancamiento** al principio
4. **Monitorea las primeras 5-10 operaciones** de cerca
5. **Ajusta RISK_PERCENT** según resultados (0.5%-2%)
6. **Revisa diariamente** tus posiciones abiertas
7. **Entiende que puedes perder dinero**

---

## 🆘 Solución de Problemas

### "Invalid API Key"
→ Verifica las API Keys en `.env`
→ Asegura permisos de Futures en Binance

### "Insufficient Balance"
→ Transfiere fondos a tu wallet Futures
→ Binance App: Wallet → Transfer → Spot → Futures

### Bot no ejecuta trades
→ Verifica `AUTO_TRADE_ENABLED=True`
→ Revisa que tengas balance suficiente
→ Confirma que no alcanzaste `MAX_POSITIONS`

### Posición liquidada
→ Reduce `LEVERAGE`
→ Aumenta distancia de SL
→ Reduce `RISK_PERCENT`

---

## 📞 Archivos Importantes

- `auto_trading_scanner.py` → Bot principal
- `binance_futures_trader.py` → Módulo de trading
- `manage_positions.py` → Gestor manual
- `verify_setup.py` → Verificación del sistema
- `.env` → Configuración (API Keys, riesgo, etc)
- `README_TRADING.md` → Documentación completa

---

## ⚠️ DISCLAIMER LEGAL

**El trading de futuros con apalancamiento es extremadamente arriesgado.**

- Puedes perder más de tu inversión inicial
- Este bot es una herramienta educativa
- No garantiza ganancias
- Usa bajo tu propia responsabilidad
- Siempre usa stop loss
- No inviertas dinero que no puedas perder

---

**¿Listo para empezar?**

1. `python verify_setup.py` ✅
2. `python auto_trading_scanner.py` (modo alertas) 📢
3. Cuando estés listo: activa `AUTO_TRADE_ENABLED=True` 🚀
