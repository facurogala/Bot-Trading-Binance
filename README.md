# 🤖 Bot de Trading Automático - Binance Futures

Bot de trading automático para Binance Futures con detección de señales EMA, ejecución automática de trades, gestión de riesgo y generación automática de reportes estadísticos.

## 🚀 Características

- ✅ **Trading Automático**: Ejecuta trades automáticamente en Binance Futures
- 📊 **Análisis Multi-Timeframe**: Escanea 30m, 1h y 4h simultáneamente
- 🛡️ **Gestión de Riesgo**: Stop Loss y múltiples Take Profits automáticos
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

## 📁 Estructura del Proyecto

```
Automatizacion/
├── auto_trading_scanner_conservador.py  # Bot con filtros conservadores
├── auto_trading_scanner.py              # Bot normal
├── binance_futures_trader.py            # Módulo de trading
├── trading_database.py                  # Base de datos SQLite
├── trading_dashboard.py                 # Generador de gráficos
├── generate_report.py                   # Script de reportes
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
