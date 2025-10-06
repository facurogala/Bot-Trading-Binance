# 🤖 Sistema de Trading Automático - Estructura del Proyecto

## 📁 Archivos del Proyecto

```
Automatizacion/
│
├── 📄 .env                          # Configuración (API Keys, parámetros)
│
├── 🤖 ARCHIVOS PRINCIPALES
│   ├── auto_trading_scanner.py      # Bot principal con trading automático
│   ├── binance_futures_trader.py    # Módulo de trading en Binance Futures
│   ├── scanner_loop.py              # Bot original (solo alertas)
│   └── macd_scanner_once.py         # Scanner de una vez
│
├── 🛠️ UTILIDADES
│   ├── verify_setup.py              # Verifica configuración y conexión
│   ├── manage_positions.py          # Gestor interactivo de posiciones
│   ├── test_telegram.py             # Prueba conexión Telegram
│   └── get_group_id.py              # Obtiene ID de chat Telegram
│
└── 📚 DOCUMENTACIÓN
    ├── README_TRADING.md            # Documentación completa
    └── GUIA_RAPIDA.md              # Guía rápida de inicio
```

## 🔄 Flujo de Trabajo

### 1️⃣ Configuración Inicial
```
┌─────────────────┐
│  Crear API Keys │
│   en Binance    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Configurar     │
│   archivo .env  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ verify_setup.py │ ◄── Ejecutar para verificar
└─────────────────┘
```

### 2️⃣ Modo Solo Alertas (Recomendado para empezar)
```
.env: AUTO_TRADE_ENABLED=False

┌──────────────────────┐
│ auto_trading_        │
│ scanner.py           │
└──────────┬───────────┘
           │
           ▼
    ┌─────────────┐
    │ Detecta     │
    │ Señales EMA │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │  Calcula    │
    │  SL y TPs   │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │   Envía     │
    │  Alerta a   │
    │  Telegram   │
    └─────────────┘
```

### 3️⃣ Modo Trading Automático
```
.env: AUTO_TRADE_ENABLED=True

┌──────────────────────┐
│ auto_trading_        │
│ scanner.py           │
└──────────┬───────────┘
           │
           ▼
    ┌─────────────┐
    │ Detecta     │
    │ Señales EMA │
    └──────┬──────┘
           │
           ▼
    ┌─────────────────────┐
    │ binance_futures_    │
    │ trader.py           │
    └──────┬──────────────┘
           │
           ├─► Orden de Entrada (LIMIT/MARKET)
           ├─► Stop Loss (STOP_MARKET)
           └─► Take Profits (TP1, TP2, TP3)
           │
           ▼
    ┌─────────────┐
    │ Confirma en │
    │  Telegram   │
    └─────────────┘
```

## 🎮 Comandos por Uso

### 🔍 Para Verificar Todo
```bash
python verify_setup.py
```
→ Revisa configuración, balance, conexión, etc.

### 📢 Para Recibir Solo Alertas
```bash
python auto_trading_scanner.py
```
→ Con `AUTO_TRADE_ENABLED=False` en `.env`

### 🤖 Para Trading Automático
```bash
# 1. Configurar
# Editar .env: AUTO_TRADE_ENABLED=True

# 2. Verificar
python verify_setup.py

# 3. Ejecutar
python auto_trading_scanner.py
```

### 🛠️ Para Gestionar Posiciones
```bash
python manage_positions.py
```
→ Menu interactivo para ver/cerrar posiciones

### 🧪 Para Probar Telegram
```bash
python test_telegram.py
```

## 📊 Archivos de Configuración

### `.env` - Estructura
```env
# Telegram (ya configurado)
TELEGRAM_TOKEN=...
TELEGRAM_CHAT_ID=...

# Binance (DEBES CONFIGURAR)
BINANCE_API_KEY=tu_api_key
BINANCE_API_SECRET=tu_secret

# Trading
AUTO_TRADE_ENABLED=False    # True para trading automático
USE_MARKET_ORDER=False      # True para órdenes market
LEVERAGE=5                  # Apalancamiento (1-125)
RISK_PERCENT=1.0           # % de riesgo por trade
MAX_POSITIONS=3            # Max posiciones simultáneas
```

## 🎯 Casos de Uso

### Caso 1: Solo quiero alertas
```bash
# .env: AUTO_TRADE_ENABLED=False
python auto_trading_scanner.py
```

### Caso 2: Quiero trading automático conservador
```env
# .env
AUTO_TRADE_ENABLED=True
LEVERAGE=3
RISK_PERCENT=0.5
MAX_POSITIONS=2
```
```bash
python auto_trading_scanner.py
```

### Caso 3: Ver mis posiciones actuales
```bash
python manage_positions.py
# Seleccionar opción 2
```

### Caso 4: Cerrar todas las posiciones (emergencia)
```bash
python manage_positions.py
# Seleccionar opción 6
```

### Caso 5: Ver mi historial de trades
```bash
python manage_positions.py
# Seleccionar opción 7
```

## 🔐 Seguridad

### ✅ Buenas Prácticas
- ✅ API Keys solo con permisos de Futures (no Withdrawals)
- ✅ Archivo `.env` nunca se sube a Git
- ✅ Empezar con `AUTO_TRADE_ENABLED=False`
- ✅ Probar con capital pequeño primero
- ✅ Usar leverage bajo (3-5x) al inicio

### ❌ Nunca Hacer
- ❌ Compartir tus API Keys
- ❌ Subir `.env` a repositorios públicos
- ❌ Usar todo tu capital
- ❌ Leverage muy alto (>20x) sin experiencia
- ❌ Dejar el bot sin supervisión al inicio

## 📈 Estrategia del Bot

### Señales
- **LONG**: EMA20 cruza por arriba de EMA50
- **SHORT**: EMA20 cruza por abajo de EMA50

### Timeframes Analizados
- 30 minutos
- 1 hora
- 4 horas

### Niveles Calculados
- **Entry Zone**: Entre EMA20 y EMA50
- **Stop Loss**: Swing Low/High + 0.2×ATR de buffer
- **Take Profits**: 3 niveles (1×ATR, 1.5×ATR, 2×ATR)

### Gestión de Posición
- Tamaño basado en % de riesgo configurado
- Leverage aplicado automáticamente
- División equitativa entre TPs
- SL cierra toda la posición

## 🎓 Próximos Pasos

1. **Lee** `GUIA_RAPIDA.md` para comandos básicos
2. **Configura** tus API Keys en `.env`
3. **Ejecuta** `python verify_setup.py`
4. **Prueba** con `AUTO_TRADE_ENABLED=False`
5. **Monitorea** las alertas durante unos días
6. **Activa** trading automático cuando estés listo
7. **Ajusta** parámetros según tus resultados

## 📞 Ayuda Rápida

### ¿Algo no funciona?
```bash
python verify_setup.py
```

### ¿Quiero cerrar una posición ya?
```bash
python manage_positions.py
```

### ¿El bot está corriendo?
Mira la consola, debe mostrar:
```
🔍 Escaneando X cryptos en Y timeframes
```

---

**🚀 ¡Estás listo para empezar!**

Empieza con: `python verify_setup.py`
