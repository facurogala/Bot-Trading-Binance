# 📊 Sistema de Reportes - Guía Completa

## ✅ **TODOS los reportes se guardan en la carpeta `reports/`**

La carpeta `reports/` se crea automáticamente si no existe.

## 📁 **Tipos de reportes generados:**

### 1. **Reporte Consolidado (nombre fijo)**
```
reports/trading_report_all.txt
reports/trading_report_all.png
```
- **Se sobrescribe** cada vez que generas reportes
- Contiene todos los trades (o filtrados por bot)
- Útil para tener siempre el reporte más reciente con nombre fijo

### 2. **Reportes con Timestamp**
```
reports/trading_report_20251008_070511.txt
reports/trading_report_20251008_070511.png
```
- **NO se sobrescribe**, crea uno nuevo cada vez
- Útil para guardar historial de reportes
- Formato: `trading_report_YYYYMMDD_HHMMSS.*`

### 3. **Reportes por Bot**
```
reports/trading_report_Scalping_20251008_070511.txt
reports/trading_report_Scalping_20251008_070511.png
reports/trading_report_Haack_20251008_070511.txt
reports/trading_report_Haack_20251008_070511.png
```
- Un reporte separado por cada bot detectado en la DB
- Solo se generan cuando ejecutas `--per-bot`

## 🚀 **Cómo generar reportes:**

### **Opción 1: Generar TODOS los reportes (recomendado)**
```powershell
python generate_all_reports.py
```

**Genera:**
- ✅ `trading_report_all.txt` y `.png` (consolidado)
- ✅ `trading_report_TIMESTAMP.txt` y `.png` (con timestamp)
- ✅ Un reporte por cada bot detectado

### **Opción 2: Filtrar por bot específico**
```powershell
python generate_all_reports.py --bot Haack
python generate_all_reports.py --bot Scanner
python generate_all_reports.py --bot Scalping
```

**Genera:**
- ✅ `trading_report_all.txt` y `.png` (solo con datos de ese bot)
- ✅ `trading_report_TIMESTAMP.txt` y `.png` (solo con datos de ese bot)

### **Opción 3: Limpiar reportes antiguos**
```powershell
# Mantener solo los últimos 5 reportes con timestamp
python generate_all_reports.py --clean

# Mantener solo los últimos 10
python generate_all_reports.py --clean --keep 10
```

**Limpia:**
- ❌ Reportes antiguos con timestamp
- ✅ Mantiene `trading_report_all.*` (siempre se conserva)
- ✅ Mantiene los últimos N reportes con timestamp

### **Opción 4: Generador original (más opciones)**
```powershell
# Reporte completo
python generate_report.py

# Filtrado por bot
python generate_report.py --bot Haack

# Reporte de un símbolo específico
python generate_report.py --symbol BTCUSDT

# Reportes individuales por cada bot
python generate_report.py --per-bot

# Reporte rápido en consola (sin archivos)
python generate_report.py --quick
```

## 🔄 **Generación automática:**

Los reportes se generan **automáticamente** cuando ejecutas los scanners:

```powershell
python auto_trading_scanner_haack.py
python auto_trading_scanner.py
python auto_trading_scanner_scalping.py
python auto_trading_scanner_swing.py
```

Al finalizar cada ciclo de escaneo, se actualiza automáticamente:
- ✅ `reports/trading_report_all.txt`
- ✅ `reports/trading_report_all.png`

## 📊 **Contenido de los reportes:**

### **Archivo .txt contiene:**
```
╔═══════════════════════════════════════════════════════════════╗
║              REPORTE DE TRADING (CONSOLIDADO)                 ║
╚═══════════════════════════════════════════════════════════════╝

ESTADÍSTICAS GENERALES
============================================================
Total de Trades:           15
Trades Ganadores:          10 (66.7%)
Trades Perdedores:         5 (33.3%)

RENDIMIENTO
============================================================
PnL Total:                 $450.25
Promedio Ganancia:         $75.50
Promedio Pérdida:          -$45.20
Mejor Trade:               $150.00
Peor Trade:                -$85.00
Profit Factor:             2.15

ACTIVIDAD (PROMEDIO 7 DÍAS)
============================================================
Bot Haack: 3.50 operac./día
Bot Scanner: 1.20 operac./día

ÚLTIMOS 10 TRADES
============================================================
[Lista detallada de los últimos 10 trades]
```

### **Archivo .png contiene:**
- 📈 Gráfico de PnL acumulado
- 📊 Distribución de wins/losses
- 📉 Drawdown
- 📊 Performance por símbolo (si hay datos)

## 🗂️ **Estructura de la carpeta reports:**

```
reports/
├── trading_report_all.txt              # Consolidado (se sobrescribe)
├── trading_report_all.png              # Consolidado (se sobrescribe)
├── trading_report_20251008_070511.txt  # Con timestamp (historial)
├── trading_report_20251008_070511.png  # Con timestamp (historial)
├── trading_report_20251008_080320.txt  # Con timestamp (historial)
├── trading_report_20251008_080320.png  # Con timestamp (historial)
├── trading_report_Haack_20251008.txt   # Por bot
├── trading_report_Haack_20251008.png   # Por bot
├── trading_report_Scanner_20251008.txt # Por bot
└── trading_report_Scanner_20251008.png # Por bot
```

## 🔧 **Comandos útiles:**

### Ver todos los reportes disponibles
```powershell
ls reports/
```

### Ver solo reportes consolidados
```powershell
ls reports/trading_report_all.*
```

### Ver solo reportes con timestamp
```powershell
ls reports/trading_report_202*.txt
```

### Abrir el reporte consolidado
```powershell
# Ver texto
type reports\trading_report_all.txt

# Ver imagen
start reports\trading_report_all.png
```

### Contar cuántos reportes hay
```powershell
(ls reports/).Count
```

## 📋 **Checklist:**

- [x] ✅ Los reportes se guardan en `reports/`
- [x] ✅ La carpeta se crea automáticamente si no existe
- [x] ✅ Se generan reportes consolidados con nombre fijo
- [x] ✅ Se generan reportes con timestamp para historial
- [x] ✅ Se pueden filtrar por bot
- [x] ✅ Se pueden limpiar reportes antiguos
- [x] ✅ Se generan automáticamente al ejecutar scanners

## 💡 **Recomendaciones:**

1. **Para ver el último reporte:** Abre `reports/trading_report_all.txt`

2. **Para mantener historial:** Los reportes con timestamp se acumulan

3. **Para liberar espacio:** Ejecuta `python generate_all_reports.py --clean` periódicamente

4. **Para análisis por bot:** Usa `python generate_all_reports.py --bot NombreDelBot`

5. **Backup:** Copia la carpeta `reports/` periódicamente para guardar historial

## 🆘 **Solución de problemas:**

### Problema: "No se genera el reporte"
**Causa:** No hay trades cerrados en la DB
**Solución:**
```powershell
python diagnose_database.py
# Verifica si hay trades cerrados
```

### Problema: "La carpeta reports no existe"
**Causa:** Nunca se ejecutó el generador
**Solución:**
```powershell
python generate_all_reports.py
# Se crea automáticamente
```

### Problema: "Reporte muestra datos antiguos"
**Causa:** El reporte no se ha regenerado
**Solución:**
```powershell
python generate_all_reports.py
# Regenera todos los reportes
```

### Problema: "Demasiados archivos en reports/"
**Solución:**
```powershell
python generate_all_reports.py --clean --keep 5
# Mantiene solo los últimos 5
```

## 📊 **Ejemplo de uso completo:**

```powershell
# 1. Ejecutar scanner
python auto_trading_scanner_haack.py

# 2. Esperar a que se cierren trades

# 3. Ver reporte actualizado
type reports\trading_report_all.txt

# 4. Abrir gráfico
start reports\trading_report_all.png

# 5. Generar reporte detallado con timestamp
python generate_all_reports.py

# 6. Limpiar reportes antiguos (mantener últimos 5)
python generate_all_reports.py --clean
```

---

✅ **Todo listo: Los reportes siempre se guardan en `reports/`**
