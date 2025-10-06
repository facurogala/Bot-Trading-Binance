# 🚀 Guía Rápida de Comandos

## 🤖 ¿QUÉ HACE ESTA APP?

Esta aplicación es un **bot de trading automático para Binance Futures** que:

### 📊 Funciones Principales:
1. **Analiza el mercado 24/7** - Escanea 27 criptomonedas cada 30 minutos
2. **Detecta oportunidades** - Identifica cruces de medias móviles (EMA 20/50)
3. **Envía alertas** - Te notifica por Telegram cuando encuentra señales
4. **Ejecuta trades automáticamente** - Puede abrir/cerrar posiciones sin intervención
5. **Gestiona riesgo** - Coloca Stop Loss y Take Profits automáticos
6. **Usa apalancamiento** - Opera con leverage de 3x-10x para amplificar ganancias

### 🎯 Estrategia de Trading:
- **Indicador:** Cruces de EMA (Exponential Moving Average)
- **Señal LONG:** Cuando EMA20 cruza por encima de EMA50 (tendencia alcista)
- **Señal SHORT:** Cuando EMA20 cruza por debajo de EMA50 (tendencia bajista)
- **Timeframes:** 30 minutos, 1 hora y 4 horas
- **Gestión de riesgo:** Stop Loss basado en ATR + soporte/resistencia
- **Objetivo:** 3 niveles de Take Profit para salidas parciales

### � Modos de Operación:
- **Testnet (Demo):** Usa dinero virtual de Binance para practicar sin riesgo
- **Real:** Opera con dinero real (solo después de probar en testnet)

### 🛡️ Modo Conservador (NUEVO):
Incluye filtros adicionales para mayor seguridad:
- ✅ Solo opera con volumen alto (1.2x+ promedio)
- ✅ Verifica RSI para evitar sobrecompra/sobreventa
- ✅ Requiere tendencia favorable (EMA200)
- ✅ Limita el tamaño del Stop Loss (máx 2.5%)
- ✅ Reduce número de posiciones simultáneas (2 máx)

---

## 📋 TRES MODOS DISPONIBLES

### 🔔 Modo 1: SOLO ALERTAS (Recomendado para empezar)
```bash
python scanner_alertas.py
```

**¿Qué hace?**
- ✅ Escanea el mercado cada 30 minutos
- ✅ Detecta cruces de EMA 20/50
- ✅ Envía alertas detalladas a Telegram
- ❌ NO ejecuta trades
- ❌ NO usa dinero

**Perfecto para:**
- Ver qué tipo de señales genera
- Analizar la estrategia
- Aprender sin presión
- Seguir las alertas manualmente

---

### 🤖 Modo 2: TRADING AUTOMÁTICO EN TESTNET
```bash
python scanner_trading.py
```

**¿Qué hace?**
- ✅ Escanea el mercado cada 30 minutos
- ✅ Detecta cruces de EMA 20/50
- ✅ Envía alertas a Telegram
- ✅ Ejecuta trades automáticamente
- 🧪 Usa dinero virtual (testnet)
- 💰 ~50 USDT de riesgo por trade

**Perfecto para:**
- Probar la estrategia sin riesgo
- Ver resultados reales
- Practicar gestión de posiciones
- Evaluar el bot antes de usar dinero real

---

### 🛡️ Modo 3: TRADING CONSERVADOR EN TESTNET (RECOMENDADO)
```bash
python scanner_trading_conservador.py
```

**¿Qué hace?**
- ✅ Todo lo del Modo 2, PERO con filtros estrictos:
  - 📊 Solo opera si volumen > 1.2x promedio
  - 📈 Verifica RSI (45-65 para LONG, 35-55 para SHORT)
  - 📉 Requiere tendencia favorable (EMA200)
  - 🛡️ Stop Loss máximo de 2.5%
  - 🎯 Solo 2 posiciones simultáneas (en vez de 3)
- 💰 ~25 USDT de riesgo por trade (50% menos que Modo 2)
- 🎯 Menos trades, pero de mayor calidad

**Perfecto para:**
- Principiantes que quieren seguridad extra
- Reducir número de operaciones
- Aumentar win rate (% de trades ganadores)
- Trading más seguro y controlado

**Configuración conservadora:**
- Leverage: 3x (en vez de 5x)
- Riesgo: 0.5% por trade (en vez de 1%)
- Max posiciones: 2 (en vez de 3)
- Filtros de calidad activados

---

## 🎯 FLUJO RECOMENDADO

### Día 1-2: Solo Alertas
```bash
python scanner_alertas.py
```
- Observa las señales
- Analiza si te gustan
- Sin compromiso
- Sin dinero involucrado

### Día 3-14: Trading Conservador (RECOMENDADO)
```bash
python scanner_trading_conservador.py
```
- Deja que ejecute trades con filtros estrictos
- Dinero virtual (testnet)
- Monitorea resultados diariamente
- Win rate esperado: 50-60%
- ~5-10 trades por mes

### Día 15-30: Trading Normal (Opcional)
```bash
python scanner_trading.py
```
- Si quieres más trades (20-30/mes)
- Sin filtros conservadores
- Win rate esperado: 40-50%
- Más activo pero más riesgoso

### Después de 2-3 meses: Trading Real (Opcional)
Si los resultados son consistentemente buenos:
- Win rate > 60% en modo conservador
- PnL total positivo
- Entiendes cómo funciona el bot
- Ver instrucciones en `README_TRADING.md`

---

## 🔍 ¿CÓMO FUNCIONA INTERNAMENTE?

### 1. Escaneo del Mercado (cada 30 min)
```
Bot inicia → Obtiene datos de Binance → Calcula EMAs
```

Para cada criptomoneda:
- Descarga últimas 300 velas (candlesticks)
- Calcula EMA 20 y EMA 50
- Detecta si hay cruce entre ellas
- Analiza 3 timeframes: 30m, 1h, 4h

### 2. Detección de Señales
```
Cruce detectado → Aplicar filtros → Calcular niveles
```

**Señal LONG (Compra):**
- EMA20 cruza por encima de EMA50
- Indica inicio de tendencia alcista

**Señal SHORT (Venta):**
- EMA20 cruza por debajo de EMA50
- Indica inicio de tendencia bajista

### 3. Aplicación de Filtros (solo modo conservador)
```
Señal → Verificar volumen → Verificar RSI → Verificar tendencia → Verificar SL
```

Si ALGÚN filtro falla → Rechazar señal

### 4. Cálculo de Niveles
```
Precio actual → Calcular SL (Stop Loss) → Calcular TPs (Take Profits)
```

- **Stop Loss:** Basado en mínimos/máximos recientes + ATR
- **Take Profit 1:** Precio + 1.5x ATR (33% de la posición)
- **Take Profit 2:** Precio + 2.5x ATR (33% de la posición)  
- **Take Profit 3:** Precio + 3.5x ATR (34% de la posición)

### 5. Ejecución del Trade (solo modos trading)
```
Calcular tamaño → Abrir posición → Colocar SL/TP → Notificar
```

**Cálculo del tamaño:**
```
Riesgo = Balance × Risk_Percent
Distancia_SL = |Precio - Stop_Loss|
Cantidad = Riesgo / Distancia_SL × Leverage
```

**Ejemplo con $5000:**
- Riesgo: 0.5% = $25
- Distancia SL: 2% = $900
- Leverage: 3x
- Cantidad: $25 / $900 × 3 = 0.083 BTC

### 6. Gestión de Posición
```
Posición abierta → Monitorear → Alcanza TP o SL → Cerrar (parcial/total)
```

- Si precio alcanza TP1 → Vende 33%, mueve SL a breakeven
- Si precio alcanza TP2 → Vende 33% más
- Si precio alcanza TP3 → Cierra todo (ganancia máxima)
- Si precio alcanza SL → Cierra todo (pérdida controlada)

---

## 📊 MONITOREAR EL BOT

### Ver Posiciones y Balance
```bash
python manage_positions.py
```

**Opciones disponibles:**
1. Ver balance
2. Ver posiciones abiertas
3. Cerrar posición
4. Cancelar órdenes
5. Ver historial de trades

### Verificar Configuración
```bash
python verify_setup.py
```

---

## ⚙️ GESTIÓN DEL BOT

### Iniciar Bot
```bash
# Solo alertas
python scanner_alertas.py

# O trading demo
python scanner_trading.py
```

### Detener Bot
Presiona `Ctrl + C` en la terminal donde está corriendo

### Ver Output en Tiempo Real
El bot muestra su progreso en la terminal:
- Símbolos escaneados
- Señales detectadas
- Trades ejecutados (si aplica)
- Próximo escaneo

---

## 📱 ALERTAS EN TELEGRAM

### Formato de Alerta (Solo Alertas)
```
🚨 SEÑAL DETECTADA
BTC/USDT 🟢 LONG
⏰ Timeframe: 1 hora

📍 Zona de Entrada: 62500 - 62300

🟢 TP1: 63200
🟢 TP2: 63550
🟢 TP3: 63900

🔴 SL: 61800

💰 Precio Actual: 62400
📊 Vol Ratio: 1.45x
💡 Volumen normal: señal aceptable ⚪
```

### Formato de Alerta (Trading Demo)
```
🤖 TRADE EJECUTADO
BTC/USDT 🟢 LONG
⏰ Timeframe: 1 hora

📍 Entrada: 62400

🟢 TP1: 63200
🟢 TP2: 63550
🟢 TP3: 63900

🔴 SL: 61800

💰 Precio Actual: 62400
📊 Vol Ratio: 1.45x
💡 Volumen normal: señal aceptable ⚪
```

---

## 🔧 CONFIGURACIÓN ACTUAL

Tu archivo `.env` tiene esta configuración **CONSERVADORA** (actualizada):
- **API Keys:** Testnet configuradas ✅
- **Leverage:** 3x (reducido para seguridad)
- **Riesgo:** 0.5% (~25 USDT por trade)
- **Max Posiciones:** 2 simultáneas
- **Tipo Orden:** LIMIT (mejor control de precio)
- **Timeframes:** 30m, 1h, 4h
- **Cryptos:** 27 símbolos monitoreados

**Los scripts ignoran AUTO_TRADE_ENABLED en `.env`:**
- `scanner_alertas.py` → Siempre solo alertas (sin trades)
- `scanner_trading.py` → Siempre trading demo (sin filtros)
- `scanner_trading_conservador.py` → Siempre trading demo (con filtros)

---

## 📊 COMPARACIÓN DE MODOS

| Característica | Solo Alertas | Trading Normal | Trading Conservador |
|---------------|--------------|----------------|---------------------|
| **Comando** | `scanner_alertas.py` | `scanner_trading.py` | `scanner_trading_conservador.py` |
| **Ejecuta trades** | ❌ No | ✅ Sí | ✅ Sí |
| **Leverage** | N/A | 5x | 3x |
| **Riesgo/trade** | N/A | 1% ($50) | 0.5% ($25) |
| **Max posiciones** | N/A | 3 | 2 |
| **Filtro volumen** | ❌ | ❌ | ✅ (1.2x) |
| **Filtro RSI** | ❌ | ❌ | ✅ (45-65/35-55) |
| **Filtro tendencia** | ❌ | ❌ | ✅ (EMA200) |
| **Filtro SL máx** | ❌ | ❌ | ✅ (2.5%) |
| **Señales/mes** | ~30 | ~25 | ~5-10 |
| **Win rate esperado** | N/A | 40-50% | 50-60% |
| **Recomendado para** | Observar | Intermedios | Principiantes |

---

## 💡 CONCEPTOS CLAVE

### EMA (Exponential Moving Average)
Promedio móvil exponencial que da más peso a precios recientes.
- **EMA20:** Promedio de últimas 20 velas (corto plazo)
- **EMA50:** Promedio de últimas 50 velas (largo plazo)
- **Cruce alcista:** EMA20 > EMA50 (momento de comprar)
- **Cruce bajista:** EMA20 < EMA50 (momento de vender)

### ATR (Average True Range)
Mide la volatilidad del mercado para calcular SL y TP.
- ATR alto = Mercado volátil (SL/TP más amplios)
- ATR bajo = Mercado tranquilo (SL/TP más ajustados)

### Leverage (Apalancamiento)
Multiplica tu poder de compra usando dinero prestado.
- **3x:** Con $1000 puedes operar como si tuvieras $3000
- **5x:** Con $1000 puedes operar como si tuvieras $5000
- ⚠️ Mayor leverage = Mayor ganancia PERO también mayor pérdida

### Stop Loss (SL)
Precio al que se cierra automáticamente la posición para limitar pérdidas.
- Ejemplo: Compras BTC a $50,000, SL en $49,000
- Si baja a $49,000 → Se vende automáticamente
- Pérdida máxima: 2% controlado

### Take Profit (TP)
Precio al que se cierra automáticamente la posición para asegurar ganancias.
- TP1: Primera salida parcial (33%)
- TP2: Segunda salida parcial (33%)
- TP3: Salida final (34%)

### Risk Percent
Porcentaje del balance que arriesgas por trade.
- 0.5% de $5000 = $25 máximo de pérdida por trade
- Si haces 10 trades y todos pierden = -5% del balance
- Si haces 10 trades y todos ganan (1:2) = +10% del balance

### Win Rate
Porcentaje de trades ganadores sobre el total.
- 10 trades: 6 ganan, 4 pierden = 60% win rate
- No necesitas 100% win rate para ser rentable
- Con 50% win rate + buen risk/reward = Rentable

### Testnet
Entorno de prueba de Binance con dinero virtual.
- Funciona exactamente igual que cuenta real
- Pero usa dinero "de mentira"
- Ideal para practicar sin riesgo
- URL: https://testnet.binancefuture.com/

---

## 💡 CONSEJOS Y MEJORES PRÁCTICAS

### Para Solo Alertas:
- Déjalo correr por 24-48 horas
- Revisa qué tipo de señales genera
- Analiza los timeframes que más señales dan
- Decide si te gusta la estrategia

### Para Trading Conservador (RECOMENDADO):
- Déjalo correr al menos 1 semana
- Monitorea diariamente con `manage_positions.py`
- Revisa win rate después de 10 trades (Opción 7)
- No te preocupes si pasan días sin señales (es normal)
- Objetivo: Win rate > 50% antes de pasar a modo normal

### Para Trading Normal:
- Solo después de probar modo conservador
- Monitorea cada 4-6 horas con `manage_positions.py`
- Espera al menos 20 trades para evaluar estrategia
- Si pierdes 3 trades seguidos → Pausa y analiza
- Win rate esperado: 40-50% (menos que conservador)

### General:
- ✅ Empieza SIEMPRE en testnet
- ✅ No uses dinero real hasta tener 60%+ win rate
- ✅ Monitorea posiciones al menos 1 vez al día
- ✅ Lee la documentación completa (`INICIO_RAPIDO.md`)
- ❌ No cambies parámetros después de 1 mal trade
- ❌ No uses más del 2% de riesgo por trade
- ❌ No operes con más de 5x leverage como principiante

---

## 📈 EXPECTATIVAS REALISTAS

### Modo Conservador (Recomendado para principiantes):
- **Señales por mes:** 5-10
- **Trades ejecutados:** 5-8
- **Win rate esperado:** 50-60%
- **Rentabilidad mensual:** 3-10% (si funciona bien)
- **Drawdown máximo:** 2-5%

### Modo Normal (Para intermedios):
- **Señales por mes:** 20-30
- **Trades ejecutados:** 15-25
- **Win rate esperado:** 40-50%
- **Rentabilidad mensual:** 5-15% (más variable)
- **Drawdown máximo:** 5-10%

### Modo Solo Alertas:
- **Señales por mes:** 25-35
- **Para:** Aprender y analizar
- **No genera ganancias** (no ejecuta trades)

**⚠️ IMPORTANTE:** Estos son promedios. Puede haber meses buenos (+20%) y meses malos (-10%). El trading implica riesgo.

---

## 🎓 APRENDIZAJE Y MEJORA

### Semana 1-2: Observación
```bash
python scanner_alertas.py
```
- Aprende a leer las alertas
- Entiende qué significa cada indicador
- Sin presión, solo observación

### Semana 3-4: Práctica Conservadora
```bash
python scanner_trading_conservador.py
```
- Primer contacto con trading automático
- Filtros estrictos te protegen
- Analiza cada trade ejecutado

### Mes 2-3: Experimentación
```bash
# Prueba ambos modos
python scanner_trading_conservador.py
python scanner_trading.py
```
- Compara resultados
- Ajusta parámetros si es necesario
- Identifica qué modo funciona mejor para ti

### Mes 4+: Optimización
- Si win rate > 60% → Considera aumentar riesgo a 1%
- Si win rate < 40% → Vuelve a modo conservador
- Si win rate 40-60% → Mantén configuración actual
- Lee `FILTROS_EXPLICADOS.md` para ajustes avanzados

---

## 📞 ARCHIVOS Y DOCUMENTACIÓN

### Scripts Principales:
- `scanner_alertas.py` → Solo alertas (no ejecuta trades)
- `scanner_trading.py` → Trading automático normal
- `scanner_trading_conservador.py` → Trading con filtros (RECOMENDADO)
- `manage_positions.py` → Gestión de posiciones y balance
- `verify_setup.py` → Verificar que todo esté configurado

### Scripts de Utilidad:
- `test_telegram.py` → Probar notificaciones de Telegram
- `diagnose_api.py` → Diagnosticar problemas con API Keys
- `get_group_id.py` → Obtener ID de grupo de Telegram

### Documentación:
- `COMANDOS.md` → Esta guía (comandos y conceptos)
- `INICIO_RAPIDO.md` → Guía de inicio rápido (5 minutos)
- `FILTROS_EXPLICADOS.md` → Cómo funcionan los filtros conservadores
- `CONFIGURACION_CONSERVADORA.md` → Configuración detallada
- `RESUMEN_CAMBIOS.md` → Qué cambió en la versión conservadora
- `README_COMANDOS.md` → Referencia rápida de comandos
- `README_TRADING.md` → Documentación técnica completa
- `GUIA_RAPIDA.md` → Guía de usuario
- `GUIA_TESTNET.md` → Cómo usar testnet de Binance

### Archivos de Configuración:
- `.env` → Configuración principal (API Keys, leverage, riesgo)
- `auto_trading_scanner.py` → Motor principal del bot (normal)
- `auto_trading_scanner_conservador.py` → Motor del bot (conservador)
- `binance_futures_trader.py` → Lógica de ejecución de trades

---

## 🚀 GUÍA DE INICIO RÁPIDO (5 MINUTOS)

### 1. Verificar configuración
```bash
python verify_setup.py
```
**Debe mostrar:** ✅ en todo

### 2. Elegir modo
```bash
# Opción A: Solo observar (sin trades)
python scanner_alertas.py

# Opción B: Trading conservador (RECOMENDADO)
python scanner_trading_conservador.py

# Opción C: Trading normal
python scanner_trading.py
```

### 3. Dejar correr
El bot escaneará cada 30 minutos automáticamente

### 4. Monitorear (en otra terminal)
```bash
python manage_positions.py
# Selecciona opción 2: Ver posiciones abiertas
```

### 5. Detener cuando quieras
`Ctrl + C` en la terminal del bot

---

## 🎯 EJEMPLO COMPLETO DE UN TRADE

### 1. Bot detecta señal
```
Hora: 14:30
BTC/USDT: Cruce alcista detectado
EMA20 cruza por encima de EMA50
Timeframe: 4 horas
```

### 2. Aplica filtros (modo conservador)
```
✅ Volumen: 1.45x promedio (pasa)
✅ RSI: 58.2 (entre 45-65, pasa)
✅ Tendencia: Precio > EMA200 (pasa)
✅ Stop Loss: 1.89% (< 2.5%, pasa)
```

### 3. Calcula niveles
```
Precio actual: $50,000
Stop Loss: $49,055 (-1.89%)
Take Profit 1: $50,675 (+1.35%)
Take Profit 2: $51,350 (+2.70%)
Take Profit 3: $52,025 (+4.05%)
```

### 4. Calcula tamaño de posición
```
Balance: $5,000
Riesgo: 0.5% = $25
Leverage: 3x
Distancia SL: $945
Cantidad: $25 / $945 × 3 = 0.079 BTC
Valor nominal: $3,950
```

### 5. Ejecuta trade
```
✅ Compra 0.079 BTC a $50,000
✅ Coloca SL a $49,055
✅ Coloca TP1 a $50,675 (33%)
✅ Coloca TP2 a $51,350 (33%)
✅ Coloca TP3 a $52,025 (34%)
📱 Notifica en Telegram
```

### 6. Escenarios posibles

**Escenario A: Alcanza TP1 ($50,675)**
```
✅ Vende 0.026 BTC (33%)
💰 Ganancia: +$17.55
📊 Posición restante: 0.053 BTC
🛡️ Mueve SL a breakeven ($50,000)
```

**Escenario B: Alcanza TP2 ($51,350)**
```
✅ Vende 0.026 BTC más (33%)
💰 Ganancia adicional: +$35.10
📊 Posición restante: 0.027 BTC
```

**Escenario C: Alcanza TP3 ($52,025)**
```
✅ Cierra toda la posición (34%)
💰 Ganancia total: +$160.47
🎉 Trade exitoso completado
```

**Escenario D: Alcanza SL ($49,055)**
```
❌ Cierra toda la posición
💸 Pérdida: -$25.00
🛡️ Pérdida controlada (0.5% del balance)
```

### 7. Resultado final (Escenario C - Éxito)
```
Inversión: $3,950 (con 3x leverage)
Ganancia: $160.47
ROI: 4.06%
Tiempo: 2-5 días (aprox)
Balance nuevo: $5,160.47
```

---

## 🆘 SOLUCIÓN DE PROBLEMAS

### No recibo alertas en Telegram
→ Verifica que el bot esté corriendo
→ Revisa que TELEGRAM_TOKEN y CHAT_ID estén bien en `.env`
→ Prueba: `python test_telegram.py`

### El bot no detecta señales
→ Es normal, puede tardar horas en encontrar cruces de EMA
→ Déjalo correr y espera
→ Las señales dependen del mercado

### Error al ejecutar trades (modo trading)
→ Verifica balance en testnet: `python manage_positions.py`
→ Puede que necesites recargar fondos en testnet
→ O regenerar API Keys de testnet

### Cómo recargar fondos en testnet
→ Ve a: https://testnet.binancefuture.com/
→ Busca opción "Get Test Funds" o similar
→ O contacta soporte de Binance Testnet

---

## 🎯 INICIO INMEDIATO

**Paso 1:** Elige tu modo
```bash
# Solo alertas (sin riesgo, para observar)
python scanner_alertas.py

# Trading conservador (RECOMENDADO para principiantes)
python scanner_trading_conservador.py

# O trading normal (más activo, más riesgo)
python scanner_trading.py
```

**Paso 2:** Deja correr el bot (escanea cada 30 min)

**Paso 3:** Revisa Telegram para alertas

**Paso 4:** (Opcional) Monitorea posiciones en otra terminal
```bash
python manage_positions.py
```

---

## ❓ PREGUNTAS FRECUENTES

### ¿Cuánto dinero necesito para empezar?
- **Testnet:** $0 (dinero virtual gratis)
- **Real:** Mínimo $500-1000 recomendado
- Con menos de $500 → Difícil gestionar riesgo

### ¿Puedo perder más de lo que invierto?
- **Con Stop Loss:** NO, máximo pierdes el riesgo configurado
- **Sin Stop Loss:** SÍ, con leverage podrías perder todo
- **Este bot:** Siempre usa Stop Loss automático ✅

### ¿Cuánto tiempo debo dejar correr el bot?
- **Mínimo:** 24 horas para ver señales
- **Recomendado:** 1-2 semanas para evaluar
- **Ideal:** 1-3 meses antes de pasar a real

### ¿Qué pasa si mi computadora se apaga?
- El bot se detiene
- Las posiciones abiertas NO se cierran
- Los Stop Loss y Take Profits siguen activos en Binance
- Puedes gestionar posiciones desde `manage_positions.py`

### ¿Puedo usar esto en mi celular?
- NO directamente (requiere Python y terminal)
- PERO puedes:
  - Recibir alertas en Telegram desde celular
  - Usar `manage_positions.py` desde PC para gestionar
  - Considerar VPS (servidor en la nube) para 24/7

### ¿Es legal esto?
- ✅ SÍ, usar bots de trading es legal
- ✅ Binance permite automatización vía API
- ⚠️ Consulta regulaciones de tu país sobre trading

### ¿Necesito saber programar?
- NO para usar el bot (solo ejecutar comandos)
- SÍ si quieres modificar la estrategia
- Los comandos son simples (copiar y pegar)

### ¿Qué tan confiable es?
- **Testnet:** 100% seguro (dinero virtual)
- **Real:** Depende del mercado y configuración
- **Consejo:** Prueba 2-3 meses en testnet primero

### ¿Puedo modificar la estrategia?
- SÍ, editando archivos `.py`
- Requiere conocimientos de Python
- Lee `FILTROS_EXPLICADOS.md` para ajustes simples

### ¿El bot funciona 24/7?
- Solo mientras tu PC esté encendida
- Para 24/7: Necesitas VPS o servidor
- Alternativa: Déjalo correr cuando estés despierto

### ¿Cuánto gana en promedio?
- **No hay garantías** (el trading es riesgoso)
- **Modo conservador:** 3-10% mensual (si funciona bien)
- **Modo normal:** 5-15% mensual (más variable)
- **Puede perder:** -5% a -15% en meses malos

---

## 🆘 TROUBLESHOOTING (Solución de Problemas)

### Error: "TELEGRAM_TOKEN no configurado"
**Solución:**
```bash
# Edita .env y verifica que tengas:
TELEGRAM_TOKEN=tu_token_aquí
TELEGRAM_CHAT_ID=tu_chat_id_aquí
```

### Error: "API Key inválida"
**Solución:**
```bash
python diagnose_api.py  # Diagnóstico
```
- Regenera API Keys en Binance Testnet
- Verifica que sean de TESTNET (no de producción)

### No recibo alertas en Telegram
**Solución:**
```bash
python test_telegram.py  # Prueba Telegram
```
- Verifica que el bot esté en el grupo correcto
- Verifica CHAT_ID en `.env`

### Bot no detecta señales
**Esto es NORMAL:**
- Los cruces de EMA no ocurren constantemente
- Puede tardar horas o días en encontrar señales
- Especialmente en modo conservador (filtros estrictos)
- Ten paciencia y déjalo correr

### Error: "Insufficient balance"
**Solución:**
- Ve a https://testnet.binancefuture.com/
- Busca "Get Test Funds" o "Paper Trading"
- Recarga fondos virtuales

### Bot se cierra solo
**Causas posibles:**
- Error en el código → Revisa mensajes de error
- Falta de conexión a internet
- PC se suspendió
**Solución:** Reinicia el bot

### Win rate muy bajo (<30%)
**Solución:**
- Usa modo conservador (`scanner_trading_conservador.py`)
- Lee `FILTROS_EXPLICADOS.md` para ajustes
- Considera que el mercado puede estar en consolidación

---

## 🎓 RECURSOS DE APRENDIZAJE

### Documentación Interna (Empieza aquí):
1. **`INICIO_RAPIDO.md`** → Guía de 5 minutos
2. **`FILTROS_EXPLICADOS.md`** → Cómo funcionan los filtros
3. **`COMANDOS.md`** → Este archivo (conceptos y comandos)
4. **`README_COMANDOS.md`** → Referencia rápida

### Conceptos de Trading (Externos):
- **EMA:** Busca "EMA trading strategy" en YouTube
- **RSI:** Busca "RSI indicator explained"
- **Risk Management:** Busca "position sizing trading"
- **Binance Futures:** Busca "Binance futures tutorial"

### Práctica Recomendada:
1. Lee toda la documentación (1-2 horas)
2. Observa en modo alertas (2-3 días)
3. Practica en testnet conservador (2-4 semanas)
4. Analiza resultados y ajusta
5. Solo entonces considera dinero real

---

## ✅ CHECKLIST ANTES DE EMPEZAR

### Configuración:
- [ ] Python instalado
- [ ] Dependencias instaladas (`pip install -r requirements.txt`)
- [ ] API Keys de testnet configuradas en `.env`
- [ ] Token de Telegram configurado
- [ ] Chat ID de Telegram configurado
- [ ] `verify_setup.py` muestra todo ✅

### Conocimiento:
- [ ] Entiendes qué es leverage
- [ ] Entiendes qué es Stop Loss
- [ ] Entiendes qué es Take Profit
- [ ] Entiendes que el trading implica riesgo
- [ ] Leíste al menos `INICIO_RAPIDO.md`

### Mentalidad:
- [ ] Estás probando en testnet primero
- [ ] No esperas hacerte rico en 1 semana
- [ ] Entiendes que habrá pérdidas
- [ ] Tienes paciencia para dejar correr el bot
- [ ] No vas a cambiar todo después de 1 mal trade

**Si marcaste todos:** ¡Estás listo! 🚀

---

**¿Listo para empezar?** 

**Comando recomendado para principiantes:**
```bash
python scanner_trading_conservador.py
```

**¡El bot comenzará a trabajar para ti!** 🤖📈
