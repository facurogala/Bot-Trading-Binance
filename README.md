# 🤖 Bot de Trading Automático - Binance Futures

Bot de trading automático para Binance Futures con detección de señales EMA, ejecución automática de trades, gestión de riesgo adaptativa y reconciliación de órdenes SL/TP.

## 🚀 Características

- ✅ **Trading Automático**: Ejecuta trades automáticamente en Binance Futures
- 📊 **Análisis Multi-Timeframe**: Escanea múltiples timeframes simultáneamente
- 🛡️ **Gestión de Riesgo Adaptativa**: SL/TP se ajustan según volatilidad percibida
- 🔄 **Reconciliación de Órdenes**: Garantiza que SL/TP existan en Binance
- 👁️ **Monitoreo Continuo**: Verifica órdenes periódicamente y las recrea si faltan
- 🎯 **Cancelación Recíproca**: Cuando SL o TP se ejecutan, cancela las otras automáticamente
- 📈 **Reportes Automáticos**: Genera gráficos y estadísticas después de cada escaneo
- 💰 **Base de Datos**: Registra todas las señales y trades en SQLite
- 🔔 **Notificaciones Telegram**: Alertas en tiempo real
- 🧪 **Modo Testnet**: Practica sin riesgo en cuenta demo

## 📦 Instalación

### 1. Clonar el repositorio

```bash
git clone <tu-repositorio>
cd Automatizacion
```

### 2. Instalar dependencias

```bash
pip install python-binance pandas pandas-ta python-dotenv requests matplotlib seaborn
```

### 3. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
# Binance API (Testnet o Real)
BINANCE_API_KEY=tu_api_key
BINANCE_SECRET_KEY=tu_secret_key
USE_TESTNET=True

# Telegram (para notificaciones)
TELEGRAM_TOKEN=tu_bot_token
TELEGRAM_CHAT_ID=tu_chat_id

# Trading (Configuración)
AUTO_TRADE_ENABLED=True
USE_MARKET_ORDER=False
MAX_POSITIONS=3
LEVERAGE=3
RISK_PERCENT=1.0

# Reconciliación y Monitoreo de Órdenes
ENABLE_ORDER_MONITORING=True
ORDER_MONITOR_DURATION=120
ORDER_MONITOR_INTERVAL=15
ORDER_FILL_TIMEOUT=30

# Risk profile (nuevo)
# AUTO => TESTNET_SAFE si TESTNET/USE_TESTNET=True, si no PROD_SAFE
RISK_PROFILE=AUTO
RISK_GUARD_ENABLED=True
MAX_DAILY_LOSS_USDT=50
MAX_CONSECUTIVE_LOSSES=3
MAX_DRAWDOWN_PCT=12
RISK_GUARD_PAUSE_MINUTES=180

# Opcional para habilitar cálculo real de drawdown sobre equity
RISK_GUARD_INITIAL_EQUITY_USDT=0

# Límites globales cross-bot (0 = desactivado)
MAX_GLOBAL_OPEN_POSITIONS=0
MAX_GLOBAL_SYMBOL_POSITIONS=1
MAX_GLOBAL_EXPOSURE_USDT=0
MAX_SYMBOL_EXPOSURE_USDT=0
```

### Distribución de pares por estrategia

- `Scalping`: lista reducida y líquida (alta ejecución, menor slippage)
- `Swing`: lista intermedia (balance entre liquidez y cobertura)
- `Haack`: lista amplia (más selectividad por filtros)

### Perfiles de Riesgo (automáticos)

- `RISK_PROFILE=AUTO` (recomendado):
    - En testnet (`TESTNET=True` o `USE_TESTNET=True`) usa perfil `TESTNET_SAFE`.
    - En producción usa perfil `PROD_SAFE`.
- También puedes fijar `RISK_PROFILE=CONSERVATIVE` o `RISK_PROFILE=AGGRESSIVE`.
- Si defines manualmente cualquier variable (`MAX_DAILY_LOSS_USDT`, etc.), ese valor tiene prioridad sobre el perfil.

### Cambio rápido de entorno (PowerShell)

Puedes cambiar el `.env` activo con un solo comando:

```powershell
# Activar perfil testnet
powershell -ExecutionPolicy Bypass -File .\switch_env.ps1 -Profile testnet

# Activar perfil producción
powershell -ExecutionPolicy Bypass -File .\switch_env.ps1 -Profile production
```

### 4. Obtener API Keys de Binance Testnet

1. Ve a [Binance Testnet](https://testnet.binancefuture.com/)
2. Inicia sesión con GitHub/Google
3. Genera tus API Keys
4. Pégalas en el archivo `.env`

### 5. Configurar Bot de Telegram (Opcional)

1. Habla con [@BotFather](https://t.me/botfather)
2. Crea un nuevo bot con `/newbot`
3. Obtén el token y guárdalo
4. Obtén tu Chat ID con `python get_group_id.py`

## 🎯 Uso

### Bot Conservador (Recomendado)

El bot conservador aplica múltiples filtros de confirmación para reducir señales falsas:

```bash
python auto_trading_scanner_conservador.py
```

**Filtros activos:**
- ✅ Volumen mínimo: 1.2x el promedio
- ✅ RSI LONG: 45-65 (evita sobrecompra)
- ✅ RSI SHORT: 35-55 (evita sobreventa)
- ✅ Distancia mínima EMAs: 0.5%
- ✅ Stop Loss máximo: 2.5%
- ✅ Tendencia EMA200 requerida

### Bot Normal (Más señales)

```bash
python auto_trading_scanner.py
```

**Características:**
- Detecta más señales (menos filtros)
- Útil en mercados con alta volatilidad
- Requiere mayor monitoreo

## 📊 Reportes Automáticos

Ambos bots generan reportes automáticamente después de cada escaneo:

### 1. Estadísticas en Consola

Se muestran automáticamente:
- 💰 PnL Total
- 📊 Total de Trades
- ✅ Win Rate
- 🏆 Mejor/Peor Trade
- ⚖️ Profit Factor

### 2. Gráficos Completos

Se generan en la carpeta `reports/`:
- Curva de balance
- Distribución de PnL
- Win rate por símbolo
- Drawdown
- Y más...

### 3. Generar Reportes Manualmente

Si quieres generar reportes en cualquier momento:

```bash
# Reporte completo con gráficos
python generate_report.py

# Estadísticas rápidas
python generate_report.py --quick

# Dashboard interactivo
python view_stats.py
```

## � Sistema de Reconciliación de Órdenes SL/TP

### ¿Por qué es importante?

Las órdenes SL/TP **viven en Binance**, no en el bot. Esto significa que:
- ✅ Funcionan aunque tu PC esté apagado
- ✅ Se ejecutan incluso si el bot se cae
- ✅ Protegen tu capital 24/7

### Cómo funciona

1. **Después del fill de entrada**: El bot verifica que la posición existe en Binance
2. **Crea SL/TP con flags correctos**:
   - `STOP_MARKET` con `closePosition=True` para SL (closePosition ya implica reduce-only)
   - `TAKE_PROFIT_MARKET` con `reduceOnly=True` para cada TP
3. **Reconciliación automática**: Si una orden falta, la recrea (hasta 3 reintentos)
4. **Monitoreo continuo**: Cada 15s durante 2 minutos verifica que las órdenes existan
5. **Cancelación recíproca**: Cuando SL o TP se ejecuta, cancela las otras automáticamente

### Configuración de Reconciliación

En `.env`:

```env
# Habilitar monitoreo automático
ENABLE_ORDER_MONITORING=True

# Duración del monitoreo (segundos)
ORDER_MONITOR_DURATION=120

# Intervalo de verificación (segundos)
ORDER_MONITOR_INTERVAL=15

# Timeout para fill de órdenes LIMIT (segundos)
ORDER_FILL_TIMEOUT=30
```

### Verificar Órdenes en Binance

```bash
# Ver todas las órdenes de un símbolo
python debug_orders.py BTCUSDT

# Ver posiciones y órdenes activas
python manage_positions.py
```

## 📊 Gestión de Riesgo Adaptativa

El bot ajusta automáticamente SL y TP según:

### 1. Volatilidad (vol_ratio)
- **Alta volatilidad (>1.5x)**: SL más amplio, permite respirar al precio
- **Volatilidad normal (0.8-1.5x)**: SL estándar
- **Baja volatilidad (<0.8x)**: SL más ajustado (mínimo 0.7x)

### 2. Take Profits basados en Risk-Reward
- TPs se calculan como múltiplos de la distancia del SL
- Por defecto: TP1=1:1, TP2=1.5:1, TP3=2:1
- Ejemplo: Si SL está a 2%, TP1=2%, TP2=3%, TP3=4%

### Ejemplo de Niveles

```
Precio: $50,000
ATR: $500
Volatilidad: 1.5x (alta)

SL: $49,200 (-1.6%, ampliado por volatilidad)
TP1: $50,800 (+1.6%, ratio 1:1)
TP2: $51,200 (+2.4%, ratio 1.5:1)
TP3: $51,600 (+3.2%, ratio 2:1)
```

## 🧪 Probar en Testnet

### Script de Prueba Completo

```bash
# Abre una posición MARKET, crea SL/TP, y verifica
python test_trade_complete.py BTCUSDT LONG
python test_trade_complete.py ADAUSDT SHORT
```

Este script:
1. Calcula niveles dinámicos
2. Abre posición MARKET
3. Crea SL/TP con reconciliación
4. Muestra los Order IDs
5. Ejecuta debug para verificar en Binance
6. Inicia monitoreo automático

## �📁 Estructura del Proyecto

```
Automatizacion/
├── auto_trading_scanner_conservador.py  # Bot con filtros conservadores
├── auto_trading_scanner.py              # Bot normal
├── binance_futures_trader.py            # Módulo de trading + reconciliación
├── order_reconciler.py                  # Sistema de reconciliación de órdenes
├── trading_database.py                  # Base de datos SQLite
├── trading_dashboard.py                 # Generador de gráficos
├── generate_report.py                   # Script de reportes
├── test_trade_complete.py               # Test completo de trading
├── debug_orders.py                      # Diagnóstico de órdenes
├── view_stats.py                        # Visualizador de estadísticas
├── monitor_trading.py                   # Monitor de posiciones
├── manage_positions.py                  # Gestión manual de posiciones
├── .env                                 # Variables de entorno (NO SUBIR A GIT)
├── trading_history.db                   # Base de datos (se crea automáticamente)
└── reports/                             # Carpeta de reportes (se crea automáticamente)
```

## 🛠️ Herramientas Adicionales

### Monitorear Posiciones

```bash
python monitor_trading.py
```

### Gestionar Posiciones Manualmente

```bash
# Ver posiciones abiertas
python manage_positions.py --list

# Cerrar una posición específica
python manage_positions.py --close BTCUSDT

# Cerrar todas las posiciones
python manage_positions.py --close-all
```

### Verificar Configuración

```bash
python verify_setup.py
```

### Diagnosticar API

```bash
python diagnose_api.py
```

## ⚙️ Configuración Avanzada

### Variables de Entorno (.env)

| Variable | Descripción | Valor por defecto |
|----------|-------------|-------------------|
| `USE_TESTNET` | Usar Binance Testnet | `True` |
| `AUTO_TRADE_ENABLED` | Trading automático | `False` |
| `USE_MARKET_ORDER` | Usar órdenes de mercado | `False` |
| `MAX_POSITIONS` | Máximo de posiciones simultáneas | `2` |
| `LEVERAGE` | Apalancamiento | `3` |
| `RISK_PERCENT` | Riesgo por trade (%) | `1.0` |

### Modificar Cryptos a Monitorear

Edita la variable `WATCHLIST` en el bot:

```python
WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT",
    # Agrega más aquí...
]
```

### Modificar Timeframes

Edita la variable `TIMEFRAMES`:

```python
TIMEFRAMES = ["15m", "30m", "1h", "4h"]
```

### Ajustar Filtros Conservadores

En `auto_trading_scanner_conservador.py`:

```python
MIN_VOLUME_RATIO = 1.2        # Volumen mínimo
MIN_EMA_DISTANCE = 0.005      # Distancia mínima EMAs (0.5%)
MAX_SL_PERCENT = 0.025        # Stop Loss máximo (2.5%)
RSI_LONG_MIN = 45             # RSI mínimo para LONG
RSI_LONG_MAX = 65             # RSI máximo para LONG
```

## 🔒 Seguridad

- ⚠️ **NUNCA** subas tu archivo `.env` a GitHub
- 🔐 Usa API Keys con permisos limitados (solo Trading)
- 🧪 Prueba primero en Testnet
- 💰 Usa montos pequeños al inicio
- 📊 Monitorea constantemente el bot

## 📈 Interpretación de Reportes

### Win Rate
- **> 60%**: Excelente estrategia
- **50-60%**: Buena estrategia
- **< 50%**: Revisar filtros

### Profit Factor
- **> 2.0**: Excelente
- **1.5-2.0**: Bueno
- **< 1.5**: Mejorar gestión de riesgo

### Drawdown
- **< 10%**: Bajo riesgo
- **10-20%**: Riesgo moderado
- **> 20%**: Alto riesgo, reducir apalancamiento

## 🐛 Troubleshooting

### Error: "API key inválida"
- Verifica que las keys sean de Testnet si `USE_TESTNET=True`
- Verifica que las keys tengan permisos de Trading

### Error: "Insufficient balance"
- En Testnet, recarga tu balance desde el sitio
- En Real, deposita más USDT

### No detecta señales
- Es normal en mercados laterales
- Prueba con más cryptos en `WATCHLIST`
- Ajusta los filtros conservadores

### Reportes vacíos
- Espera a que se ejecuten y cierren algunos trades
- Los gráficos completos requieren trades cerrados

## 📞 Soporte

Si encuentras problemas:
1. Verifica la configuración con `python verify_setup.py`
2. Revisa los logs del bot
3. Consulta la base de datos: `python view_stats.py`

## 📝 Licencia

Este proyecto es de código abierto para uso personal y educativo.

## ⚠️ Disclaimer

El trading de criptomonedas conlleva riesgos significativos. Este bot es una herramienta educativa y no garantiza ganancias. Usa bajo tu propio riesgo.

---

**¡Happy Trading! 🚀📈**
