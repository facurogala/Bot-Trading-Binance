# 🛡️ CONFIGURACIÓN CONSERVADORA - Trading Seguro

## 📊 PARÁMETROS RECOMENDADOS

### 1️⃣ Configuración en `.env` (Lo Básico)

```env
# 🔒 CONFIGURACIÓN CONSERVADORA
LEVERAGE=3                    # Apalancamiento bajo (3x en vez de 5x o más)
RISK_PERCENT=0.5             # Solo 0.5% de riesgo por trade
MAX_POSITIONS=2              # Máximo 2 posiciones simultáneas
USE_MARKET_ORDER=False       # Usa LIMIT orders para mejor control
```

**¿Por qué estos valores?**
- **LEVERAGE=3**: Menos apalancamiento = menor riesgo de liquidación
- **RISK_PERCENT=0.5**: Con $5000, solo arriesgas $25 por trade
- **MAX_POSITIONS=2**: Evita sobre-exposición al mercado
- **USE_MARKET_ORDER=False**: Órdenes LIMIT te dan mejor precio de entrada

---

## 🎯 FILTROS ADICIONALES (Código Mejorado)

### 2️⃣ Filtros que deberías agregar al código:

#### ✅ **Filtro de Volumen** (YA EXISTE)
El código actual ya verifica el volumen:
- 🟡 Vol < 0.8x promedio = "bajo impulso" 
- ⚪ Vol 0.8-1.5x promedio = "señal aceptable"
- 🟢 Vol > 1.5x promedio = "buen momentum"

**MEJORA:** Solo operar cuando `vol_ratio >= 1.2` (20% más volumen que promedio)

---

#### ✅ **Filtro de Confirmación Multi-Timeframe**
Actualmente analiza 30m, 1h y 4h por separado.

**MEJORA:** Solo operar cuando:
- La señal aparezca en **2 o más timeframes** a la vez
- O cuando aparezca en el timeframe de **4h** (señal más fuerte)

---

#### ✅ **Filtro de Distancia de EMAs**
**MEJORA:** Solo operar cuando las EMAs estén suficientemente separadas:
```python
# La distancia entre EMA20 y EMA50 debe ser > 0.5% del precio
ema_distance = abs(ema20 - ema50) / price
if ema_distance < 0.005:  # Menos del 0.5%
    return None  # No operar, cruce débil
```

---

#### ✅ **Filtro de Momentum (RSI)**
**NUEVO:** Agregar filtro RSI para evitar zonas de sobrecompra/sobreventa:
```python
# Para LONG: RSI debe estar entre 40-70 (evitar >70 = sobrecompra)
# Para SHORT: RSI debe estar entre 30-60 (evitar <30 = sobreventa)
```

---

#### ✅ **Filtro de Tendencia Mayor (EMA200)**
**NUEVO:** Solo operar a favor de la tendencia principal:
```python
# Para LONG: Solo si precio > EMA200
# Para SHORT: Solo si precio < EMA200
```

---

#### ✅ **Filtro de Stop Loss Razonable**
**MEJORA:** Rechazar trades donde el SL esté demasiado lejos (>3% del precio):
```python
sl_distance = abs(price - sl_price) / price
if sl_distance > 0.03:  # Más del 3%
    return None  # SL muy amplio, mucho riesgo
```

---

## 🔧 IMPLEMENTACIÓN PRÁCTICA

### Opción A: Configuración Rápida (Solo `.env`)

```env
# Edita tu archivo .env con estos valores:
LEVERAGE=3
RISK_PERCENT=0.5
MAX_POSITIONS=2
USE_MARKET_ORDER=False
```

**Esto ya reduce significativamente el riesgo** 👍

---

### Opción B: Filtros Avanzados (Código Mejorado)

Si quieres filtros más estrictos, necesitarás modificar `auto_trading_scanner.py`:

1. **Filtro de volumen mínimo**: Solo operar con `vol_ratio >= 1.2`
2. **Filtro de RSI**: Agregar RSI entre 40-70 (LONG) o 30-60 (SHORT)
3. **Filtro de tendencia EMA200**: Solo operar a favor de tendencia
4. **Filtro de confirmación multi-TF**: Requiere señal en 2+ timeframes
5. **Filtro de SL máximo**: Rechazar si SL > 3% del precio

---

## 📈 COMPARACIÓN DE PERFILES

| Parámetro | Conservador | Moderado | Agresivo |
|-----------|-------------|----------|----------|
| **LEVERAGE** | 3x | 5x | 10x |
| **RISK_PERCENT** | 0.5% | 1.0% | 2.0% |
| **MAX_POSITIONS** | 2 | 3 | 5 |
| **Vol mínimo** | 1.5x | 1.2x | 0.8x |
| **RSI LONG** | 45-65 | 40-70 | 35-75 |
| **RSI SHORT** | 35-55 | 30-60 | 25-65 |
| **Confirmación TF** | 2+ TF | 1 TF | 1 TF |
| **SL máximo** | 2% | 3% | 5% |

---

## 🚀 PASOS PARA ACTIVAR

### 1. Configuración Básica (2 minutos)
```powershell
# Edita .env con Notepad
notepad .env

# Cambia estos valores:
# LEVERAGE=3
# RISK_PERCENT=0.5
# MAX_POSITIONS=2
# USE_MARKET_ORDER=False
```

### 2. Verifica la configuración
```powershell
python verify_setup.py
```

### 3. Inicia el bot
```powershell
python scanner_trading.py
```

---

## 💡 TIPS CONSERVADORES

1. **Empieza con testnet**: Deja `TESTNET=True` al menos 1 mes
2. **Monitorea diariamente**: Usa `python manage_positions.py` cada día
3. **No aumentes leverage**: Mantén 3x hasta tener confianza
4. **Revisa historial**: Opción 7 en `manage_positions.py` para ver win rate
5. **Cierra losses rápido**: Si una posición baja -2%, considera cerrar
6. **Deja winners correr**: No cierres antes de TP1 (salvo emergencia)

---

## ⚠️ SEÑALES DE ALERTA

**Detén el bot si:**
- Pierdes 3 trades seguidos
- Drawdown > 10% de tu balance
- Win rate < 40% después de 20 trades
- Notas que siempre entra en falsos rompimientos

---

## 🎯 SIGUIENTE NIVEL: Filtros Automáticos

¿Quieres que agregue los filtros avanzados al código?

Te puedo crear una versión mejorada de `auto_trading_scanner.py` con:
- ✅ Filtro de volumen mínimo 1.5x
- ✅ Filtro RSI 45-65 (LONG) / 35-55 (SHORT)
- ✅ Filtro EMA200 (solo a favor de tendencia)
- ✅ Filtro SL máximo 2%
- ✅ Confirmación multi-timeframe (requiere 2+ TF)

**¿Te gustaría que implemente estos filtros en el código?** 

Solo dime "implementa los filtros" y lo hago 👍
