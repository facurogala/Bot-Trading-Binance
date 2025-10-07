import os
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from datetime import datetime
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import requests
from trading_database import TradingDatabase
from trading_dashboard import TradingDashboard, generate_quick_report

# ================== CONFIG ==================
load_dotenv()
TOKEN   = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
if not TOKEN or not CHAT_ID:
    raise ValueError("❌ Error: TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no están configurados en .env")

INTERVAL = "1h"
client   = Client()

# Risk/TP config
ATR_LEN = 14
SWING_LOOKBACK = 10           # velas para swing low/high
SL_ATR_BUFFER = 0.2           # extra margen con ATR sobre swing
TP_MULTS = [0.5, 1, 1.5, 2, 2.5, 3]  # múltiplos de ATR para TP1..TP6

OUT_DIR = "graficos"
os.makedirs(OUT_DIR, exist_ok=True)
# ============================================

# Inicializar base de datos
db = TradingDatabase("trading_history.db")

def generar_reportes_automaticos():
    """Genera todos los reportes automáticamente después de cada escaneo"""
    try:
        print(f"\n{'='*60}")
        print("📊 GENERANDO REPORTES AUTOMÁTICOS...")
        print(f"{'='*60}")
        
        # Verificar si hay datos en la base de datos
        stats = db.get_trade_stats()
        
        # 1. Reporte rápido en consola
        print("\n📈 ESTADÍSTICAS RÁPIDAS:")
        generate_quick_report("trading_history.db")
        
        # 2. Generar dashboard completo si hay trades cerrados
        if stats['total_trades'] > 0:
            print("\n📊 Generando gráficos completos...")
            dashboard = TradingDashboard("trading_history.db")
            dashboard.generate_full_report(output_dir="reports")
            print("✅ Gráficos guardados en: reports/")
        else:
            print("\n💡 Aún no hay trades cerrados para generar gráficos completos")
            print("   Los gráficos se generarán cuando se cierren posiciones")
        
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"⚠️ Error al generar reportes: {e}")

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"[WARN] Telegram falló: {e}")

def decimals_for(symbol: str) -> int:
    # Aproximación: USDT 5 decimales, BTC 8 (ajustable si querés usar exchangeInfo/tickSize)
    if symbol.endswith("USDT"):
        return 5
    if symbol.endswith("BTC"):
        return 8
    return 5

def display_symbol(symbol: str) -> str:
    if symbol.endswith("USDT"):
        return f"{symbol[:-4]}/USDT"
    if symbol.endswith("BTC"):
        return f"{symbol[:-3]}/BTC"
    return symbol

def get_valid_symbols():
    exchange_info = client.get_exchange_info()["symbols"]
    valid = [
        s["symbol"] for s in exchange_info
        if s["status"] == "TRADING" and (s["symbol"].endswith("BTC") or s["symbol"].endswith("USDT"))
    ]
    return sorted(valid)

def get_klines(symbol, interval, limit=200):
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        "timestamp","open","high","low","close","volume",
        "close_time","quote_asset_volume","number_of_trades",
        "taker_buy_base_asset_volume","taker_buy_quote_asset_volume","ignore"
    ])
    # Convertir a numérico
    for col in ["open","high","low","close","volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')
    df = df[["timestamp","open","high","low","close","volume"]].dropna()
    return df

def build_levels(side: str, last_row, df, symbol: str):
    """
    Construye Entry Zone (entre EMA20 y EMA50), SL por swing y TP1..TP6 por ATR.
    side: 'LONG' o 'SHORT'
    """
    dec = decimals_for(symbol)

    # ATR
    atr_series = ta.atr(df["high"], df["low"], df["close"], length=ATR_LEN)
    atr = float(atr_series.iloc[-1])

    ema20 = float(last_row["EMA20"])
    ema50 = float(last_row["EMA50"])
    price = float(last_row["close"])

    # Zona de entrada: banda entre EMA20 y EMA50 (ordenada alta-baja)
    entry_high = max(ema20, ema50)
    entry_low  = min(ema20, ema50)

    # Swing levels para SL
    recent_lows  = df["low"].tail(SWING_LOOKBACK).min()
    recent_highs = df["high"].tail(SWING_LOOKBACK).max()

    if side == "LONG":
        # SL por debajo del swing low con pequeño buffer de ATR
        sl = recent_lows - SL_ATR_BUFFER * atr
        # TPs arriba del precio actual por múltiplos de ATR
        tps = [price + m * atr for m in TP_MULTS]
    else:
        # SHORT
        sl = recent_highs + SL_ATR_BUFFER * atr
        # TPs abajo del precio actual por múltiplos de ATR
        tps = [price - m * atr for m in TP_MULTS]

    # Volumen
    vol_now = float(df["volume"].iloc[-1])
    vol_avg20 = float(df["volume"].tail(20).mean())
    vol_ratio = vol_now / vol_avg20 if vol_avg20 > 0 else 0.0

    # Sugerencias simples según volumen
    if vol_ratio < 0.8:
        vol_hint = "Volumen bajo: posible falta de impulso, esperar confirmación 🟡"
    elif vol_ratio < 1.5:
        vol_hint = "Volumen normal: señal aceptable, riesgo moderado ⚪"
    else:
        vol_hint = "Alto volumen: buen momentum, pero cuidar FOMO 🟢"

    fmt = f"{{:.{dec}f}}"
    entry_str = f"{fmt.format(entry_high)} -  {fmt.format(entry_low)}"
    tp_lines = "\n".join([f"🟢 TP{i+1}: {fmt.format(t)}" if side == "LONG"
                          else f"🔻 TP{i+1}: {fmt.format(t)}"
                          for i, t in enumerate(tps)])
    sl_line = f"🔴 SL:  {fmt.format(sl)}"
    price_line = f"💰 Precio: {fmt.format(price)}"
    vol_line = f"📊 Volumen: {vol_now:.0f} | Promedio20: {vol_avg20:.0f} (x{vol_ratio:.2f})"

    return entry_str, tp_lines, sl_line, price_line, vol_line, vol_hint

def analyze(symbol):
    df = get_klines(symbol, INTERVAL, limit=300)
    if len(df) < 60:
        raise ValueError("Datos insuficientes")

    df["EMA20"] = ta.ema(df["close"], length=20)
    df["EMA50"] = ta.ema(df["close"], length=50)

    prev, last = df.iloc[-2], df.iloc[-1]

    signal = "HOLD"
    side = None
    if prev["EMA20"] < prev["EMA50"] and last["EMA20"] > last["EMA50"]:
        signal = "BUY"
        side = "LONG"
    elif prev["EMA20"] > prev["EMA50"] and last["EMA20"] < last["EMA50"]:
        signal = "SELL"
        side = "SHORT"

    # Gráfico simple
    plt.figure(figsize=(10,4))
    plt.plot(df["timestamp"], df["close"], label="Close")
    plt.plot(df["timestamp"], df["EMA20"], label="EMA20")
    plt.plot(df["timestamp"], df["EMA50"], label="EMA50")
    plt.scatter(last["timestamp"], last["close"], label=signal, s=100)
    plt.title(f"{symbol} • Cruce EMA 20/50 • {INTERVAL}")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, f"{symbol}_signal.png"))
    plt.close()

    # Mensaje detallado si hay señal
    message = None
    if signal in ("BUY", "SELL"):
        entry_str, tp_lines, sl_line, price_line, vol_line, vol_hint = build_levels(
            "LONG" if signal == "BUY" else "SHORT",
            last, df, symbol
        )
        sy = display_symbol(symbol)
        head = f"ORDEN A LIMITE\n{sy} {'🟢 LONG' if signal=='BUY' else '🔴 SHORT'}"
        body = (
            f"\n\n📍 Zona de Entrada: {entry_str}\n\n"
            f"{tp_lines}\n\n"
            f"{sl_line}\n\n"
            f"{price_line}\n{vol_line}\n\n"
            f"💡 {vol_hint}"
        )
        message = f"{head}{body}"

    return {
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": symbol,
        "signal": signal,
        "message": message
    }

def main():
    symbols = get_valid_symbols()
    results = []

    # Ping inicial para confirmar que el bot está activo
    send_telegram(f"🤖 Bot EMA activo ({INTERVAL}) — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    for symbol in symbols:
        try:
            res = analyze(symbol)
            results.append(res)
            if res["signal"] != "HOLD" and res["message"]:
                print(f"{symbol}: {res['signal']} → enviando alerta")
                send_telegram(res["message"])
            else:
                print(f"{symbol}: HOLD (sin señal)")
        except Exception as e:
            print(f"{symbol}: error → {e}")

    # Export
    pd.DataFrame(results).to_excel(os.path.join(OUT_DIR, "ema_signals.xlsx"), index=False)
    print("\n✅ Resultados guardados en graficos/ema_signals.xlsx")
    
    # 📊 GENERAR REPORTES AUTOMÁTICAMENTE
    generar_reportes_automaticos()

if __name__ == "__main__":
    main()
