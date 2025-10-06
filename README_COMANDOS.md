# 🎮 COMANDOS RÁPIDOS - Bot de Trading

## 🚀 INICIAR EL BOT

| Comando | ¿Qué hace? |
|---------|------------|
| `python scanner_alertas.py` | 🔔 **Solo alertas** - Detecta señales y avisa por Telegram. NO ejecuta trades. |
| `python scanner_trading.py` | 🤖 **Trading automático** - Detecta señales Y ejecuta trades con dinero virtual (testnet). |
| `python scanner_trading_conservador.py` | 🛡️ **Trading CONSERVADOR** - Con filtros estrictos de seguridad (RECOMENDADO). |

**Para detener el bot:** Presiona `Ctrl + C`

---

## 📊 VER POSICIONES Y BALANCE

| Comando | ¿Qué hace? |
|---------|------------|
| `python manage_positions.py` | 🎛️ Abre menú interactivo con todas las opciones |

### Opciones del menú:

```
1. 💰 Ver balance                    → Muestra tu balance en USDT
2. 📈 Ver posiciones abiertas        → Lista todas tus posiciones con PnL
3. 📋 Ver órdenes pendientes         → Muestra órdenes que no se ejecutaron aún
4. ❌ Cerrar una posición            → Cierra manualmente una posición específica
5. 🗑️ Cancelar órdenes de un símbolo → Cancela todas las órdenes pendientes (TP, SL, etc)
6. 🚨 CERRAR TODAS LAS POSICIONES    → EMERGENCIA - Cierra todo inmediatamente
7. 🔄 Ver historial de trades        → Muestra últimos 20 trades cerrados
0. 🚪 Salir                          → Sale del programa
```

---

## ⚙️ VERIFICAR CONFIGURACIÓN

| Comando | ¿Qué hace? |
|---------|------------|
| `python verify_setup.py` | ✅ Verifica que todo esté configurado correctamente (API Keys, balance, permisos, etc) |
| `python diagnose_api.py` | 🔍 Diagnóstico detallado de problemas con API Keys |
| `python test_telegram.py` | 📱 Prueba que Telegram funcione enviando un mensaje de prueba |

---

## 🛠️ GESTIÓN DE POSICIONES

### Cerrar UNA posición específica

```bash
python manage_positions.py
# Selecciona opción 4
# Elige el número de la posición que quieres cerrar
```

### Cancelar TODAS las órdenes de un símbolo

```bash
python manage_positions.py
# Selecciona opción 5
# Escribe el símbolo (ej: BTCUSDT)
```
**¿Para qué?** Cancela todos los TPs y SLs pendientes de ese símbolo

### 🚨 EMERGENCIA - Cerrar TODO

```bash
python manage_positions.py
# Selecciona opción 6
# Escribe: CERRAR TODO
```
**⚠️ CUIDADO:** Cierra todas las posiciones abiertas inmediatamente

---

## 📱 VER INFORMACIÓN

### Ver balance actual

```bash
python manage_positions.py
# Selecciona opción 1
```
Muestra:
- Balance total
- Balance disponible
- PnL no realizado

### Ver posiciones abiertas

```bash
python manage_positions.py
# Selecciona opción 2
```
Muestra:
- Símbolo (BTC, ETH, etc)
- Lado (LONG/SHORT)
- Cantidad
- Precio de entrada
- PnL actual
- Leverage

### Ver órdenes pendientes

```bash
python manage_positions.py
# Selecciona opción 3
```
Muestra:
- Órdenes LIMIT no ejecutadas
- Stop Loss pendientes
- Take Profits pendientes

### Ver historial de trades

```bash
python manage_positions.py
# Selecciona opción 7
```
Muestra:
- Últimos 20 trades cerrados
- Ganancia/pérdida de cada uno
- Win rate (% de trades ganadores)
- PnL total

---

## 🔧 ARCHIVOS DE CONFIGURACIÓN

| Archivo | ¿Qué contiene? |
|---------|----------------|
| `.env` | API Keys, leverage, riesgo, configuración del bot |

### Configuración importante en `.env`:

```env
# Cambiar entre testnet y real
TESTNET=True              # True = demo, False = real

# Apalancamiento
LEVERAGE=5                # 1-125x (recomendado: 3-10x)

# Riesgo por trade
RISK_PERCENT=1.0          # 1% = $50 si tienes $5000

# Máximo de posiciones
MAX_POSITIONS=3           # No abre más de 3 posiciones simultáneas
```

**Nota:** Los scripts `scanner_alertas.py` y `scanner_trading.py` ignoran `AUTO_TRADE_ENABLED` en `.env`

---

## 📋 FLUJO DE TRABAJO TÍPICO

### 1. Iniciar el bot
```bash
python scanner_alertas.py
```

### 2. Esperar alertas en Telegram
(El bot escanea cada 30 minutos)

### 3. Ver posiciones (en otra terminal)
```bash
python manage_positions.py
# Opción 2: Ver posiciones abiertas
```

### 4. Cerrar posición si quieres
```bash
python manage_positions.py
# Opción 4: Cerrar una posición
```

### 5. Detener el bot
En la terminal del bot: `Ctrl + C`

---

## 🚨 COMANDOS DE EMERGENCIA

| Situación | Comando |
|-----------|---------|
| ⚠️ Quiero cerrar TODO | `python manage_positions.py` → Opción 6 |
| ⚠️ Cancelar órdenes de BTC | `python manage_positions.py` → Opción 5 → BTCUSDT |
| ⚠️ Ver cuánto perdí/gané | `python manage_positions.py` → Opción 1 |
| ⚠️ Detener el bot | `Ctrl + C` en terminal del bot |

---

## 💡 TIPS RÁPIDOS

### Ver posiciones rápido sin menú
```bash
python verify_setup.py
```
(Muestra balance y posiciones al final)

### Reiniciar el bot
```bash
# Ctrl+C para detener
python scanner_alertas.py  # o scanner_trading.py
```

### Cambiar de modo alertas a trading
```bash
# Ctrl+C en terminal del bot
python scanner_trading.py
```

### Ver logs del bot
Mira la terminal donde está corriendo el bot, ahí aparece todo

---

## 📞 CONTACTO RÁPIDO

| Necesitas | Comando |
|-----------|---------|
| Ver si todo está bien | `python verify_setup.py` |
| Problemas con API Keys | `python diagnose_api.py` |
| Probar Telegram | `python test_telegram.py` |
| Ver este archivo | Lee `README_COMANDOS.md` |
| Documentación completa | Lee `README_TRADING.md` |

---

## ⚙️ CONFIGURACIÓN RÁPIDA

### 🛡️ Modo conservador (poco riesgo) - RECOMENDADO
```env
LEVERAGE=3
RISK_PERCENT=0.5
MAX_POSITIONS=2
USE_MARKET_ORDER=False
```
**Comando:** `python scanner_trading_conservador.py`

**Filtros adicionales:**
- ✅ Volumen mínimo: 1.2x promedio
- ✅ RSI: 45-65 (LONG) / 35-55 (SHORT)
- ✅ Solo a favor de tendencia EMA200
- ✅ Stop Loss máximo: 2.5%

### Modo moderado (riesgo medio)
```env
LEVERAGE=5
RISK_PERCENT=1.0
MAX_POSITIONS=3
USE_MARKET_ORDER=True
```
**Comando:** `python scanner_trading.py`

### Modo agresivo (alto riesgo)
```env
LEVERAGE=10
RISK_PERCENT=2.0
MAX_POSITIONS=5
USE_MARKET_ORDER=True
```
**Comando:** `python scanner_trading.py`

---

## 🎯 CHEAT SHEET

```bash
# INICIAR
python scanner_alertas.py                  # Solo alertas
python scanner_trading_conservador.py      # 🛡️ Trading conservador (RECOMENDADO)
python scanner_trading.py                  # Trading normal

# DETENER
Ctrl + C                                    # En terminal del bot

# VER TODO
python manage_positions.py                 # Menú completo

# EMERGENCIA
python manage_positions.py                 # → Opción 6 → "CERRAR TODO"

# VERIFICAR
python verify_setup.py                     # Estado del sistema
```

---

**💡 TIP:** Guarda este archivo en favoritos para consultar rápido los comandos

**⚠️ RECUERDA:** 
- `scanner_alertas.py` = Sin riesgo (solo avisos)
- `scanner_trading_conservador.py` = 🛡️ Trading conservador con filtros (RECOMENDADO)
- `scanner_trading.py` = Con trades (pero dinero virtual en testnet)
- Siempre puedes cerrar posiciones manualmente con `manage_positions.py`

**📖 DOCUMENTACIÓN:**
- `CONFIGURACION_CONSERVADORA.md` = Guía completa de configuración conservadora
