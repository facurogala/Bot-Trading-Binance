# 🚀 INICIO RÁPIDO - Modo Conservador

## 📋 LISTA DE VERIFICACIÓN (5 minutos)

### ✅ Paso 1: Verificar configuración
```powershell
python verify_setup.py
```

**Debe mostrar:**
- ✅ Balance: ~4989 USDT (testnet)
- ✅ Leverage: 3x
- ✅ Riesgo por trade: 0.5%
- ✅ Max posiciones: 2

---

### ✅ Paso 2: Iniciar bot conservador
```powershell
python scanner_trading_conservador.py
```

**Verás algo como:**
```
============================================================
  🛡️ MODO: TRADING CONSERVADOR EN TESTNET
============================================================
✅ El bot detectará señales
✅ Enviará alertas a Telegram
✅ Ejecutará trades automáticamente
🧪 Usando TESTNET (dinero virtual, sin riesgo)
🛡️ FILTROS CONSERVADORES ACTIVADOS:
   • Volumen mínimo: 1.2x promedio
   • RSI entre 45-65 (LONG) / 35-55 (SHORT)
   • Solo a favor de tendencia EMA200
   • Stop Loss máximo: 2.5%
============================================================
```

---

### ✅ Paso 3: Monitorear en Telegram
Abre Telegram y busca el mensaje:
```
🛡️ Bot EMA CONSERVADOR Iniciado
🤖 TRADING AUTOMÁTICO
📊 27 cryptos
⏰ Timeframes: 30 minutos, 1 hora, 4 horas
🔄 Escaneo cada 30 min
🛡️ Filtros conservadores activados
```

---

### ✅ Paso 4: (Opcional) Ver posiciones en tiempo real

**Abre otra terminal** (PowerShell) y ejecuta:
```powershell
cd "C:\Users\Facu\Desktop\Automatizacion"
python manage_positions.py
```

Luego selecciona:
- **Opción 1:** Ver balance
- **Opción 2:** Ver posiciones abiertas
- **Opción 7:** Ver historial de trades

---

## 📱 CÓMO SE VEN LAS ALERTAS

### Alerta de señal detectada:
```
🛡️ SEÑAL CONSERVADORA
BTC/USDT 🟢 LONG
⏰ Timeframe: 4 horas

📍 Zona de Entrada: 45,230 - 45,180

🟢 TP1: 45,680
🟢 TP2: 46,130
🟢 TP3: 46,580

🔴 SL: 44,780

💰 Precio Actual: 45,200
📊 Vol Ratio: 1.45x

💡 Alto volumen 🟢

🛡️ Filtros Conservadores:
✅ Volumen: 1.45x
✅ EMAs separadas: 0.78%
✅ RSI: 58.2
✅ SL razonable: 1.89%
```

---

## 🎯 PRIMERAS SEÑALES - QUÉ ESPERAR

### En las primeras horas:
- Probablemente NO verás señales
- El bot escaneará cada 30 minutos
- Los filtros rechazarán señales de baja calidad

### Mensajes típicos en consola:
```
🛡️ ESCANEO CONSERVADOR
🔍 27 cryptos en 3 timeframes
📅 2025-10-05 14:30:00
============================================================
🛡️ Filtros activos:
   ✅ Volumen mínimo: 1.2x
   ✅ RSI LONG: 45-65
   ✅ RSI SHORT: 35-55
   ✅ SL máximo: 2.5%
   ✅ Tendencia EMA200: Sí
============================================================

   BTC/USDT: Sin señales aprobadas
   ETH/USDT: Sin señales aprobadas
   SOL/USDT: Sin señales aprobadas
   ...

✅ Escaneo completado: 0 señal(es) aprobada(s)

⏳ Esperando 30 minutos hasta el próximo escaneo...
```

**Esto es NORMAL y BUENO** 👍 Significa que los filtros están funcionando.

---

## 🚨 CUANDO APAREZCA UNA SEÑAL

### En consola verás:
```
✅ BTC/USDT [4 horas]: BUY → ejecutado
   ✅ Volumen: 1.45x
   ✅ EMAs separadas: 0.78%
   ✅ RSI: 58.2
   ✅ SL razonable: 1.89%

🤖 Trades ejecutados: 1
```

### En Telegram verás:
```
🛡️ TRADE CONSERVADOR EJECUTADO
BTC/USDT 🟢 LONG
...
```

### Para verificar la posición:
```powershell
# En otra terminal:
python manage_positions.py
# Opción 2: Ver posiciones abiertas
```

---

## ⚙️ AJUSTES DURANTE LA OPERACIÓN

### Para cerrar una posición manualmente:
```powershell
python manage_positions.py
# Opción 4: Cerrar una posición
# Selecciona el número de posición
```

### Para cerrar TODO en emergencia:
```powershell
python manage_positions.py
# Opción 6: 🚨 CERRAR TODAS LAS POSICIONES
# Escribe: CERRAR TODO
```

### Para detener el bot:
En la terminal donde corre el bot:
```
Ctrl + C
```

---

## 📊 MONITOREO DIARIO (5 minutos/día)

### Rutina recomendada:

**Mañana (9:00 AM):**
```powershell
python manage_positions.py
# Opción 1: Ver balance
# Opción 2: Ver posiciones abiertas
```

**Tarde (5:00 PM):**
```powershell
python manage_positions.py
# Opción 2: Ver posiciones abiertas
```

**Antes de dormir:**
- Revisar Telegram para nuevas alertas
- Si hay pérdidas > 2%, considerar cerrar

---

## 🎓 INTERPRETANDO RESULTADOS

### Después de 1 semana:
```powershell
python manage_positions.py
# Opción 7: Ver historial de trades
```

**Busca:**
- Win rate (% de trades ganadores)
- PnL total
- Número de trades ejecutados

### Señales de éxito:
- ✅ Win rate > 50%
- ✅ PnL total positivo
- ✅ 3-8 trades ejecutados en la semana
- ✅ No hubo liquidaciones

### Señales de alerta:
- ⚠️ Win rate < 40%
- ⚠️ PnL total muy negativo (-5% o más)
- ⚠️ Muchos trades seguidos perdiendo

---

## 🔧 SI ALGO SALE MAL

### Bot no inicia:
```powershell
python verify_setup.py
```
Revisa que todos los checks pasen ✅

### No aparecen señales después de 24h:
**Esto es normal en modo conservador**. Los filtros son estrictos.

Si quieres ver más señales:
- Edita `auto_trading_scanner_conservador.py`
- Cambia `MIN_VOLUME_RATIO = 1.0` (línea ~52)
- Reinicia el bot

### Muchas pérdidas seguidas (3+):
```powershell
# Detener el bot: Ctrl+C

# Revisar configuración
python verify_setup.py

# Considerar hacer filtros más estrictos
# O esperar mejores condiciones de mercado
```

---

## 📈 PRÓXIMOS PASOS (Después de 1 mes)

### Si todo va bien:
1. ✅ Revisa estadísticas completas (Opción 7)
2. ✅ Si win rate > 60%, considera:
   - Aumentar RISK_PERCENT a 1%
   - Aumentar MAX_POSITIONS a 3
3. ✅ Sigue en testnet al menos 2-3 meses

### Si hay problemas:
1. ⚠️ Haz filtros más estrictos:
   ```python
   MIN_VOLUME_RATIO = 1.5
   RSI_LONG_MIN = 48
   RSI_LONG_MAX = 62
   ```
2. ⚠️ Baja el leverage a 2x
3. ⚠️ Considera solo operar en timeframe 4h

---

## 💡 COMANDOS MÁS USADOS

```powershell
# Ver resumen rápido
python verify_setup.py

# Iniciar bot
python scanner_trading_conservador.py

# Ver posiciones
python manage_positions.py

# Detener bot
Ctrl + C
```

---

## 📚 DOCUMENTACIÓN COMPLETA

- `RESUMEN_CAMBIOS.md` - Qué cambió y por qué
- `CONFIGURACION_CONSERVADORA.md` - Guía completa de configuración
- `README_COMANDOS.md` - Todos los comandos disponibles
- `README_TRADING.md` - Documentación técnica completa

---

**🎉 ¡Ya estás listo para empezar!**

**Primer comando:**
```powershell
python scanner_trading_conservador.py
```

**¿Dudas?** Revisa `CONFIGURACION_CONSERVADORA.md` o `README_COMANDOS.md`
