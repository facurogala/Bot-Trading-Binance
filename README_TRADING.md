# 🤖 Sistema de Trading Automático - Binance Futures

Sistema completo de trading automático para Binance Futures que detecta señales de cruce de EMAs y ejecuta posiciones con Stop Loss y Take Profit automáticos.

## 📋 Características

- ✅ Detección automática de señales de cruce EMA 20/50
- ✅ Ejecución automática de posiciones LONG/SHORT
- ✅ Stop Loss basado en swing high/low + ATR
- ✅ Múltiples Take Profits (3 niveles configurables)
- ✅ Gestión de riesgo por posición (% del capital)
- ✅ Apalancamiento configurable (1-125x)
- ✅ Límite de posiciones simultáneas
- ✅ Alertas por Telegram con detalles completos
- ✅ Análisis multi-timeframe (30m, 1h, 4h)
- ✅ Modo prueba (solo alertas sin trading)

## 🔧 Instalación

### 1. Instalar dependencias

```bash
pip install python-binance pandas pandas-ta python-dotenv requests
```

### 2. Configurar API Keys de Binance

1. Ve a [Binance](https://www.binance.com/es/my/settings/api-management)
2. Crea una nueva API Key
3. **IMPORTANTE**: Habilita permisos para **Futures Trading**
4. Copia tu API Key y Secret

### 3. Configurar archivo `.env`

Edita el archivo `.env` y agrega tus credenciales:

```env
# API Keys de Binance
BINANCE_API_KEY=tu_api_key_real_aqui
BINANCE_API_SECRET=tu_api_secret_real_aqui

# Configuración de Trading
AUTO_TRADE_ENABLED=False    # Cambiar a True para activar trading
USE_MARKET_ORDER=False      # True = Market, False = Limit
LEVERAGE=5                  # Apalancamiento (3-10x recomendado)
RISK_PERCENT=1.0            # % de riesgo por trade
MAX_POSITIONS=3             # Máximo de posiciones simultáneas
```

## 🚀 Uso

### Modo 1: Solo Alertas (Recomendado para empezar)

```bash
python auto_trading_scanner.py
```

Con `AUTO_TRADE_ENABLED=False`, el bot:
- ✅ Detecta señales de trading
- ✅ Envía alertas a Telegram con niveles de SL/TP
- ❌ NO ejecuta trades automáticamente

### Modo 2: Trading Automático

**⚠️ USAR CON PRECAUCIÓN ⚠️**

1. Asegúrate de tener fondos en tu cuenta Binance Futures
2. Configura el riesgo apropiado en `.env`
3. Activa el trading:

```env
AUTO_TRADE_ENABLED=True
```

4. Ejecuta el bot:

```bash
python auto_trading_scanner.py
```

### Probar Conexión

Antes de empezar, prueba que todo funcione:

```bash
python binance_futures_trader.py
```

Este comando verifica:
- ✅ Conexión con Binance
- ✅ Autenticación API
- ✅ Balance disponible
- ✅ Posiciones abiertas

## 📊 Cómo Funciona

### 1. Detección de Señales

El bot escanea cada 30 minutos y detecta:
- **LONG**: Cuando EMA20 cruza por encima de EMA50
- **SHORT**: Cuando EMA20 cruza por debajo de EMA50

### 2. Cálculo de Niveles

**Stop Loss:**
- LONG: Swing Low de últimas 10 velas - (0.2 × ATR)
- SHORT: Swing High de últimas 10 velas + (0.2 × ATR)

**Take Profits (3 niveles):**
- TP1: Precio actual ± 1.0 × ATR
- TP2: Precio actual ± 1.5 × ATR
- TP3: Precio actual ± 2.0 × ATR

### 3. Gestión de Posición

El tamaño de posición se calcula para que:
```
Riesgo por trade = Balance × RISK_PERCENT / 100
Tamaño posición = Riesgo / (Distancia_SL × Leverage)
```

**Ejemplo:**
- Balance: $1000
- Riesgo: 1% = $10
- SL a 2% del precio
- Leverage: 5x
- Tamaño: $10 / 0.02 / 5 = $100 de posición nominal

### 4. Ejecución de Órdenes

El bot ejecuta automáticamente:
1. **Orden de entrada** (LIMIT o MARKET)
2. **Stop Loss** (STOP_MARKET que cierra toda la posición)
3. **Take Profits** (divididos en partes iguales)

## ⚙️ Configuración Avanzada

### Modificar Timeframes

En `auto_trading_scanner.py`:

```python
TIMEFRAMES = ["15m", "30m", "1h", "4h", "1d"]
```

### Modificar Watchlist

```python
WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT",
    # Agrega o quita símbolos aquí
]
```

### Ajustar Take Profits

```python
TP_MULTS = [1, 1.5, 2, 2.5, 3]  # Múltiplos de ATR
```

### Cambiar ATR y Swing Lookback

```python
ATR_LEN = 14            # Período del ATR
SWING_LOOKBACK = 10     # Velas para swing high/low
SL_ATR_BUFFER = 0.2     # Buffer adicional para SL
```

## 🛡️ Gestión de Riesgo

### Recomendaciones

1. **Riesgo por trade**: 0.5-2% del capital
2. **Apalancamiento**: 3-10x (evitar más de 10x)
3. **Posiciones simultáneas**: 3-5 máximo
4. **Empezar con capital pequeño**: Probar con $100-500

### Ejemplo Conservador

```env
LEVERAGE=3
RISK_PERCENT=1.0
MAX_POSITIONS=3
```

### Ejemplo Agresivo

```env
LEVERAGE=10
RISK_PERCENT=2.0
MAX_POSITIONS=5
```

## 📱 Mensajes de Telegram

El bot envía mensajes con:
- 🚨 **Señal detectada** (modo alertas)
- 🤖 **Trade ejecutado** (modo automático)
- Zona de entrada
- Niveles de TP1, TP2, TP3
- Stop Loss
- Precio actual
- Ratio de volumen
- Análisis de momentum

## 🔍 Monitoreo

### Ver Posiciones Abiertas

El bot muestra automáticamente:
```
📊 POSICIONES ABIERTAS (2):
  BTCUSDT: LONG | Qty: 0.05 | Entry: 45000 | PnL: 125.50 USDT
  ETHUSDT: SHORT | Qty: 1.2 | Entry: 2500 | PnL: -15.30 USDT
  💰 PnL Total: 110.20 USDT
```

### Ver en Binance

También puedes revisar tus posiciones en:
- App de Binance → Futures
- Web: https://www.binance.com/es/futures/BTCUSDT

## 🚨 Solución de Problemas

### Error: "Invalid API Key"

- Verifica que las API Keys estén bien copiadas
- Asegúrate de habilitar permisos de Futures
- No uses restricciones de IP si no es necesario

### Error: "Insufficient Balance"

- Transfiere fondos a tu wallet Futures
- En Binance: Wallet → Transfer → Spot → Futures

### Error: "Precision Error"

- El bot ajusta automáticamente la precisión
- Si persiste, reduce el tamaño de posición

### Posiciones no se ejecutan

- Verifica `AUTO_TRADE_ENABLED=True`
- Revisa que tengas balance en Futures
- Comprueba que no hayas alcanzado `MAX_POSITIONS`
- Revisa logs para errores específicos

## ⚠️ Advertencias Importantes

1. **NUNCA** compartas tus API Keys
2. **SIEMPRE** prueba primero en modo alertas
3. **NUNCA** uses todo tu capital
4. **MONITOREA** regularmente tus posiciones
5. **USA** apalancamiento bajo al principio
6. **ENTIENDE** el riesgo de liquidación
7. **NO** dejes el bot sin supervisión al inicio

## 📈 Mejoras Futuras

- [ ] Trailing Stop Loss
- [ ] Filtros de volumen más avanzados
- [ ] Backtesting automático
- [ ] Dashboard web
- [ ] Múltiples estrategias
- [ ] Machine Learning para filtrar señales

## 🆘 Soporte

Si tienes problemas:
1. Revisa los logs del bot
2. Verifica tu configuración en `.env`
3. Prueba primero con `binance_futures_trader.py`
4. Revisa la documentación de Binance

## 📝 Licencia

Uso personal. Trading de criptomonedas conlleva riesgos. Usa bajo tu propia responsabilidad.

---

**⚠️ DISCLAIMER**: Este bot es una herramienta educativa. El trading de futuros con apalancamiento es extremadamente arriesgado. Puedes perder más de tu inversión inicial. Siempre usa stop loss y gestión de riesgo apropiada.
