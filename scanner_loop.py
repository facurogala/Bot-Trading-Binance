import os
import time
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from datetime import datetime
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

# Múltiples timeframes a analizar
TIMEFRAMES = ["30m", "1h", "4h"]
TIMEFRAME_NAMES = {
    "30m": "30 minutos",
    "1h": "1 hora",
    "4h": "4 horas"
}

client = Client()

# Cryptos a monitorear (formato Binance sin /)
WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLBTC", "ADABTC", "TRXUSDT",
    "AVAXUSDT", "MATICUSDT", "INJUSDT", "APTUSDT", "OPUSDT", "ARBUSDT",
    "SEIUSDT", "TIAUSDT", "HBARUSDT", "STRKUSDT", "ZECBTC", "SUIBTC",
    "BNBUSDT", "DOGEUSDT", "TONUSDT", "SHIBUSDT", "DOTUSDT", "LTCUSDT",
    "UNIUSDT", "NEARUSDT", "ICPUSDT", "ETCUSDT"
]

# Risk/TP config
ATR_LEN = 14
SWING_LOOKBACK = 10
SL_ATR_BUFFER = 0.2
TP_MULTS = [0.5, 1, 1.5, 2, 2.5, 3]
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
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            print(f"✅ Mensaje enviado a Telegram")
        else:
            print(f"⚠️ Error Telegram: {r.status_code}")
    except Exception as e:
        print(f"[WARN] Telegram falló: {e}")

def decimals_for(symbol: str) -> int:
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

def get_klines(symbol, interval, limit=200):
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        "timestamp","open","high","low","close","volume",
        "close_time","quote_asset_volume","number_of_trades",
        "taker_buy_base_asset_volume","taker_buy_quote_asset_volume","ignore"
    ])
    for col in ["open","high","low","close","volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')
    df = df[["timestamp","open","high","low","close","volume"]].dropna()
    return df

def build_levels(side: str, last_row, df, symbol: str, timeframe: str):
    dec = decimals_for(symbol)
    atr_series = ta.atr(df["high"], df["low"], df["close"], length=ATR_LEN)
    atr = float(atr_series.iloc[-1])

    ema20 = float(last_row["EMA20"])
    ema50 = float(last_row["EMA50"])
    price = float(last_row["close"])

    entry_high = max(ema20, ema50)
    entry_low  = min(ema20, ema50)

    recent_lows  = df["low"].tail(SWING_LOOKBACK).min()
    recent_highs = df["high"].tail(SWING_LOOKBACK).max()

    if side == "LONG":
        sl = recent_lows - SL_ATR_BUFFER * atr
        tps = [price + m * atr for m in TP_MULTS]
    else:
        sl = recent_highs + SL_ATR_BUFFER * atr
        tps = [price - m * atr for m in TP_MULTS]

    vol_now = float(df["volume"].iloc[-1])
    vol_avg20 = float(df["volume"].tail(20).mean())
    vol_ratio = vol_now / vol_avg20 if vol_avg20 > 0 else 0.0

    if vol_ratio < 0.8:
        vol_hint = "Volumen bajo: posible falta de impulso, esperar confirmación 🟡"
    elif vol_ratio < 1.5:
        vol_hint = "Volumen normal: señal aceptable, riesgo moderado ⚪"
    else:
        vol_hint = "Alto volumen: buen momentum, pero cuidar FOMO 🟢"

    fmt = f"{{:.{dec}f}}"
    entry_str = f"{fmt.format(entry_high)} - {fmt.format(entry_low)}"
    tp_lines = "\n".join([f"🟢 TP{i+1}: {fmt.format(t)}" if side == "LONG"
                          else f"🔻 TP{i+1}: {fmt.format(t)}"
                          for i, t in enumerate(tps)])
    sl_line = f"🔴 SL: {fmt.format(sl)}"
    price_line = f"💰 Precio: {fmt.format(price)}"
    vol_line = f"📊 Vol: {vol_now:.0f} | Avg20: {vol_avg20:.0f} (x{vol_ratio:.2f})"

    return entry_str, tp_lines, sl_line, price_line, vol_line, vol_hint

def analyze(symbol, timeframe):
    """Analiza un símbolo en un timeframe específico"""
    df = get_klines(symbol, timeframe, limit=300)
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

    message = None
    if signal in ("BUY", "SELL"):
        entry_str, tp_lines, sl_line, price_line, vol_line, vol_hint = build_levels(
            "LONG" if signal == "BUY" else "SHORT",
            last, df, symbol, timeframe
        )
        sy = display_symbol(symbol)
        tf_name = TIMEFRAME_NAMES.get(timeframe, timeframe)
        
        head = f"🚨 SEÑAL DETECTADA\n{sy} {'🟢 LONG' if signal=='BUY' else '🔴 SHORT'}\n⏰ Timeframe: {tf_name}"
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
        "timeframe": timeframe,
        "signal": signal,
        "message": message
    }

def scan_once():
    """Escanea todas las cryptos en múltiples timeframes"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*60}")
    print(f"🔍 Escaneando {len(WATCHLIST)} cryptos en {len(TIMEFRAMES)} timeframes")
    print(f"📅 {timestamp}")
    print(f"{'='*60}")
    
    signals_found = 0
    
    for symbol in WATCHLIST:
        symbol_has_signal = False
        
        # Analizar cada timeframe
        for timeframe in TIMEFRAMES:
            try:
                res = analyze(symbol, timeframe)
                if res["signal"] != "HOLD" and res["message"]:
                    tf_name = TIMEFRAME_NAMES.get(timeframe, timeframe)
                    print(f"🚨 {display_symbol(symbol)} [{tf_name}]: {res['signal']} → Enviando alerta")
                    send_telegram(res["message"])
                    signals_found += 1
                    symbol_has_signal = True
                    time.sleep(1)  # Evitar spam
            except Exception as e:
                print(f"❌ {symbol} [{timeframe}]: error → {e}")
        
        # Solo imprimir "Sin señal" si no hubo señales en ningún timeframe
        if not symbol_has_signal:
            print(f"   {display_symbol(symbol)}: Sin señales")
    
    print(f"\n✅ Escaneo completado: {signals_found} señal(es) detectada(s)")
    
    # 📊 GENERAR REPORTES AUTOMÁTICAMENTE
    generar_reportes_automaticos()
    
    return signals_found

def main():
    """Loop infinito que escanea cada 30 minutos"""
    print("🤖 Bot EMA Scanner Multi-Timeframe iniciado")
    print(f"📊 Monitoreando {len(WATCHLIST)} cryptos")
    print(f"⏰ Timeframes: {', '.join(TIMEFRAME_NAMES.values())}")
    print(f"🔄 Escaneando cada 30 minutos...\n")
    
    # Mensaje inicial
    tf_list = ", ".join(TIMEFRAME_NAMES.values())
    send_telegram(f"🤖 Bot EMA Multi-Timeframe activo\n📊 {len(WATCHLIST)} cryptos\n⏰ Timeframes: {tf_list}\n🔄 Escaneo cada 30 min")
    
    while True:
        try:
            scan_once()
            
            # Esperar 30 minutos (1800 segundos)
            print(f"\n⏳ Esperando 30 minutos hasta el próximo escaneo...")
            time.sleep(1800)
            
        except KeyboardInterrupt:
            print("\n\n⚠️ Bot detenido por el usuario")
            send_telegram("⚠️ Bot EMA detenido")
            break
        except Exception as e:
            print(f"\n❌ Error crítico: {e}")
            send_telegram(f"❌ Bot EMA error: {e}")
            print("⏳ Reintentando en 5 minutos...")
            time.sleep(300)

if __name__ == "__main__":
    main()
