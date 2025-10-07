"""
🛡️ Scanner automático con filtros CONSERVADORES para trading seguro
Versión mejorada con múltiples filtros de confirmación
"""
import os
import time
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from datetime import datetime
from dotenv import load_dotenv
import requests
from binance_futures_trader import BinanceFuturesTrader
from trading_database import TradingDatabase
from trading_dashboard import TradingDashboard, generate_quick_report

# ================== CONFIG ==================
load_dotenv()
TOKEN   = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise ValueError("❌ Error: TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no están configurados en .env")

# Configuración de trading
AUTO_TRADE_ENABLED = os.getenv("AUTO_TRADE_ENABLED", "False").lower() == "true"
USE_MARKET_ORDER = os.getenv("USE_MARKET_ORDER", "False").lower() == "true"
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "2"))

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
    "BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "ADAUSDT", "TRXUSDT",
    "AVAXUSDT", "POLUSDT", "INJUSDT", "APTUSDT", "OPUSDT", "ARBUSDT",
    "SEIUSDT", "TIAUSDT", "HBARUSDT", "STRKUSDT", "SUIUSDT",
    "BNBUSDT", "DOGEUSDT", "TONUSDT", "DOTUSDT", "LTCUSDT",
    "UNIUSDT", "NEARUSDT", "ICPUSDT", "ETCUSDT", "LINKUSDT"
]

# 🛡️ PRESET CONSERVADOR — filtros y gestión
REQUIRE_EMA200_TREND = True
MIN_EMA_DISTANCE = 0.005      # 0.50%
MIN_TREND_SLOPE = 0.0010

MIN_VOLUME_RATIO = 1.30

RSI_LONG_MIN, RSI_LONG_MAX = 45, 60
RSI_SHORT_MIN, RSI_SHORT_MAX = 40, 55

MAX_SL_PERCENT = 0.020        # 2.0%
ATR_LEN = 14
ATR_PERIOD = 14
MIN_ATR_PCT = 0.005
MAX_ATR_PCT = 0.020
SL_ATR_MULT = 1.2
TP_ATR_MULT = 2.6

USE_FIB = True
FIB_LOOKBACK_SWING = 150
FIB_MIN_SWING_RANGE = 0.012
FIB_RETRACEMENTS = [0.5, 0.618]
FIB_EXTENSIONS = [1.272, 1.618]
FIB_PROXIMITY_TOL = 0.0010
CONFLUENCE_WITH_EMA = True
CONFLUENCE_MAX_DIST_TO_EMA = 0.0015
CONFLUENCE_WITH_SR = True
SR_LOOKBACK = 400
SR_PROXIMITY_TOL = 0.0010
REQUIRE_WICK_REJECTION = True
REQUIRE_CLOSE_IN_DIRECTION = True

STRUCT_REQUIRE_HH_HL = True
STRUCT_SWING_DEPTH = 3
ADX_FILTER = True
ADX_MIN = 20
MIN_BODY_TO_RANGE = 0.55
MAX_UPWICK_FOR_LONG = 0.35
MAX_DOWNWICK_FOR_SHORT = 0.35

TIMEFRAME_ALIGNMENT = True
ALIGN_WITH = ["30m","1h","4h"]
MIN_TICKS_SINCE_SIGNAL = 3
BLOCK_NEWS_SPIKES = True
ALLOW_SESSION = ["UTC_12_22"]

USE_FUNDING_BIAS = True
MAX_POSITIVE_FUNDING = 0.03
MIN_NEGATIVE_FUNDING = -0.03

USE_SIGNAL_SCORE = True
SCORE_WEIGHTS = {
    "trend_EMA200": 2.0,
    "ema_distance": 1.2,
    "fib_confluence": 2.2,
    "rsi_zone": 1.0,
    "volume_ratio": 1.5,
    "atr_in_range": 1.0,
    "structure_HH_HL": 1.7,
    "adx": 1.2,
}
MIN_SCORE_TO_TRADE = 6.5

MAX_CONCURRENT_POS = 2
COOLDOWN_AFTER_TRADE_MIN = 60
MAX_TRADES_PER_DAY = 6
POSITION_SIZE_MULT = 0.6
LEVERAGE_CAP = 3
PYRAMIDING = False
PARTIALS = {"TP1": 1.272, "TP2": 1.414, "TP3": 1.618}

# Risk/TP config (compatibilidad con funciones existentes)
SWING_LOOKBACK = 10
SL_ATR_BUFFER = 0.2
TP_MULTS = [1.5, 2.5, 3.5]
# ============================================

# Estado runtime para cooldown y límites diarios
_last_trade_time = {}
_daily_trade_count = {}

# Inicializar base de datos
db = TradingDatabase("trading_history.db")

# Inicializar trader
trader = None
if AUTO_TRADE_ENABLED:
    try:
        trader = BinanceFuturesTrader()
        print("✅ Trader de Binance Futures inicializado")
    except Exception as e:
        print(f"❌ Error al inicializar trader: {e}")
        print("⚠️ El bot funcionará solo en modo alerta (sin trading)")
        AUTO_TRADE_ENABLED = False

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
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
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

# ===== Utilidades avanzadas =====
def pct(x: float) -> float:
    return x * 100.0

def atr_pct(df: pd.DataFrame, length: int = ATR_PERIOD) -> float:
    atr = ta.atr(df["high"], df["low"], df["close"], length=length).iloc[-1]
    price = float(df["close"].iloc[-1])
    return float(atr) / price if price else 0.0

def ema_slope(series: pd.Series, lookback: int = 10) -> float:
    if len(series) < lookback + 1:
        return 0.0
    y2 = float(series.iloc[-1])
    y1 = float(series.iloc[-(lookback + 1)])
    price_now = float(series.iloc[-1]) if series.iloc[-1] else 0.0
    return (y2 - y1) / price_now if price_now else 0.0

def fib_levels_from_swing(df: pd.DataFrame, lookback: int, side: str):
    if len(df) < lookback:
        return None
    window = df.tail(lookback)
    high = float(window["high"].max())
    low = float(window["low"].min())
    rng = (high - low) / high if high else 0.0
    if rng < FIB_MIN_SWING_RANGE:
        return None
    levels = {}
    if side == "LONG":
        levels["retracements"] = [high - (high - low) * r for r in FIB_RETRACEMENTS]
        levels["extensions"] = [low + (high - low) * e for e in FIB_EXTENSIONS]
    else:
        levels["retracements"] = [low + (high - low) * r for r in FIB_RETRACEMENTS]
        levels["extensions"] = [high - (high - low) * e for e in FIB_EXTENSIONS]
    levels["range_pct"] = rng
    return levels

def nearest_sr(df: pd.DataFrame, lookback: int):
    w = df.tail(lookback)
    highs = w["high"].rolling(3).apply(lambda x: float(x[1] > x[0] and x[1] > x[2]))
    lows = w["low"].rolling(3).apply(lambda x: float(x[1] < x[0] and x[1] < x[2]))
    levels = []
    for i in range(2, len(w)):
        if highs.iloc[i] == 1.0:
            levels.append(float(w["high"].iloc[i]))
        if lows.iloc[i] == 1.0:
            levels.append(float(w["low"].iloc[i]))
    levels = sorted(list(set(round(v, 6) for v in levels)))
    return levels[-30:]

def candle_anatomy(last: pd.Series):
    o, h, l, c = map(float, [last["open"], last["high"], last["low"], last["close"]])
    rng = max(1e-12, h - l)
    body = abs(c - o)
    up_wick = max(0.0, h - max(c, o))
    dn_wick = max(0.0, min(c, o) - l)
    return {
        "body_pct": body / rng,
        "up_wick_pct": up_wick / rng,
        "down_wick_pct": dn_wick / rng,
        "close_dir": 1.0 if c > o else (-1.0 if c < o else 0.0),
    }

def timeframe_alignment_ok(symbol: str, side: str) -> bool:
    if not TIMEFRAME_ALIGNMENT:
        return True
    ok = 0
    for tf in ALIGN_WITH:
        try:
            df = get_klines(symbol, tf, limit=200)
            df["EMA20"] = ta.ema(df["close"], length=20)
            df["EMA50"] = ta.ema(df["close"], length=50)
            last = df.iloc[-1]
            if side == "LONG" and last["EMA20"] > last["EMA50"]:
                ok += 1
            if side == "SHORT" and last["EMA20"] < last["EMA50"]:
                ok += 1
        except Exception:
            continue
    return ok == len(ALIGN_WITH)

def get_funding_bias(symbol: str):
    try:
        rates = client.futures_funding_rate(symbol=symbol, limit=1)
        if rates:
            return float(rates[0]["fundingRate"])
    except Exception:
        return None
    return None

def check_filters(side: str, df: pd.DataFrame, last_row) -> dict:
    """
    🛡️ Verifica todos los filtros conservadores
    Retorna dict con 'passed' (bool) y 'reasons' (list)
    """
    reasons = []
    price = float(last_row["close"])
    
    # 1️⃣ Filtro de VOLUMEN
    vol_now = float(df["volume"].iloc[-1])
    vol_avg20 = float(df["volume"].tail(20).mean())
    vol_ratio = vol_now / vol_avg20 if vol_avg20 > 0 else 0.0
    
    if vol_ratio < MIN_VOLUME_RATIO:
        reasons.append(f"❌ Volumen bajo ({vol_ratio:.2f}x < {MIN_VOLUME_RATIO}x)")
        return {'passed': False, 'reasons': reasons, 'vol_ratio': vol_ratio}
    
    # 2️⃣ Filtro de DISTANCIA ENTRE EMAs
    ema20 = float(last_row["EMA20"])
    ema50 = float(last_row["EMA50"])
    ema_distance = abs(ema20 - ema50) / price
    
    if ema_distance < MIN_EMA_DISTANCE:
        reasons.append(f"❌ EMAs muy cercanas ({ema_distance*100:.2f}% < {MIN_EMA_DISTANCE*100:.1f}%)")
        return {'passed': False, 'reasons': reasons, 'vol_ratio': vol_ratio}
    
    # 3️⃣ Filtro de RSI
    rsi_series = ta.rsi(df["close"], length=14)
    rsi = float(rsi_series.iloc[-1])
    
    if side == "LONG":
        if rsi < RSI_LONG_MIN or rsi > RSI_LONG_MAX:
            reasons.append(f"❌ RSI fuera de rango LONG ({rsi:.1f} no está entre {RSI_LONG_MIN}-{RSI_LONG_MAX})")
            return {'passed': False, 'reasons': reasons, 'vol_ratio': vol_ratio, 'rsi': rsi}
    else:  # SHORT
        if rsi < RSI_SHORT_MIN or rsi > RSI_SHORT_MAX:
            reasons.append(f"❌ RSI fuera de rango SHORT ({rsi:.1f} no está entre {RSI_SHORT_MIN}-{RSI_SHORT_MAX})")
            return {'passed': False, 'reasons': reasons, 'vol_ratio': vol_ratio, 'rsi': rsi}
    
    # 4️⃣ Filtro de TENDENCIA (EMA200)
    if REQUIRE_EMA200_TREND:
        ema200 = ta.ema(df["close"], length=200)
        if len(ema200) > 0:
            ema200_val = float(ema200.iloc[-1])
            if side == "LONG" and price < ema200_val:
                reasons.append(f"❌ Precio por debajo de EMA200 (tendencia bajista)")
                return {'passed': False, 'reasons': reasons, 'vol_ratio': vol_ratio, 'rsi': rsi}
            elif side == "SHORT" and price > ema200_val:
                reasons.append(f"❌ Precio por encima de EMA200 (tendencia alcista)")
                return {'passed': False, 'reasons': reasons, 'vol_ratio': vol_ratio, 'rsi': rsi}

    # 5️⃣ Pendiente de EMA20
    slope20 = ema_slope(ta.ema(df["close"], length=20), lookback=10)
    if abs(slope20) < MIN_TREND_SLOPE:
        reasons.append(f"❌ Pendiente EMA20 baja ({pct(abs(slope20)):.2f}% < {pct(MIN_TREND_SLOPE):.2f}%)")
        return {'passed': False, 'reasons': reasons}

    # 6️⃣ ATR% dentro de rango
    atrp = atr_pct(df, length=ATR_PERIOD)
    if not (MIN_ATR_PCT <= atrp <= MAX_ATR_PCT):
        reasons.append(f"❌ ATR fuera de rango ({pct(atrp):.2f}% no en {pct(MIN_ATR_PCT):.2f}-{pct(MAX_ATR_PCT):.2f}%)")
        return {'passed': False, 'reasons': reasons}

    # 7️⃣ Filtro de STOP LOSS (calculado previamente)
    atr_series = ta.atr(df["high"], df["low"], df["close"], length=ATR_LEN)
    atr = float(atr_series.iloc[-1])
    recent_lows = df["low"].tail(SWING_LOOKBACK).min()
    recent_highs = df["high"].tail(SWING_LOOKBACK).max()
    
    if side == "LONG":
        sl = recent_lows - SL_ATR_BUFFER * atr
    else:
        sl = recent_highs + SL_ATR_BUFFER * atr
    
    sl_distance = abs(price - sl) / price
    
    if sl_distance > MAX_SL_PERCENT:
        reasons.append(f"❌ Stop Loss muy amplio ({sl_distance*100:.2f}% > {MAX_SL_PERCENT*100:.1f}%)")
        return {'passed': False, 'reasons': reasons, 'vol_ratio': vol_ratio, 'rsi': rsi}
    
    # 8️⃣ Confluencias Fib/EMA/SR
    fib_conf = 0.0
    ema_conf = 0.0
    sr_conf = 0.0
    if USE_FIB:
        fl = fib_levels_from_swing(df, FIB_LOOKBACK_SWING, side)
        if fl:
            for lv in fl["retracements"]:
                if abs(price - lv) / price <= FIB_PROXIMITY_TOL:
                    fib_conf = 1.0
                    break
    if CONFLUENCE_WITH_EMA:
        ema_base = ema20 if side == "LONG" else ema50
        if abs(price - ema_base) / price <= CONFLUENCE_MAX_DIST_TO_EMA:
            ema_conf = 1.0
    if CONFLUENCE_WITH_SR:
        srs = nearest_sr(df, SR_LOOKBACK)
        for lv in srs:
            if abs(price - lv) / price <= SR_PROXIMITY_TOL:
                sr_conf = 1.0
                break

    # 9️⃣ Anatomía de vela
    ana = candle_anatomy(last_row)
    if REQUIRE_CLOSE_IN_DIRECTION:
        if side == "LONG" and ana["close_dir"] < 0:
            reasons.append("❌ Cierre de vela en contra")
            return {'passed': False, 'reasons': reasons}
        if side == "SHORT" and ana["close_dir"] > 0:
            reasons.append("❌ Cierre de vela en contra")
            return {'passed': False, 'reasons': reasons}
    if REQUIRE_WICK_REJECTION:
        if side == "LONG" and ana["up_wick_pct"] > MAX_UPWICK_FOR_LONG:
            reasons.append("❌ Mecha superior excesiva para LONG")
            return {'passed': False, 'reasons': reasons}
        if side == "SHORT" and ana["down_wick_pct"] > MAX_DOWNWICK_FOR_SHORT:
            reasons.append("❌ Mecha inferior excesiva para SHORT")
            return {'passed': False, 'reasons': reasons}
    if ana["body_pct"] < MIN_BODY_TO_RANGE:
        reasons.append("❌ Cuerpo pequeño en relación al rango")
        return {'passed': False, 'reasons': reasons}

    # 🔟 ADX
    if ADX_FILTER:
        adx = float(ta.adx(df["high"], df["low"], df["close"], length=14)["ADX_14"].iloc[-1])
        if adx < ADX_MIN:
            reasons.append(f"❌ ADX débil ({adx:.1f} < {ADX_MIN})")
            return {'passed': False, 'reasons': reasons}

    # 1️⃣1️⃣ Funding bias
    if USE_FUNDING_BIAS:
        fb = get_funding_bias(last_row.get('symbol', '')) if hasattr(last_row, 'get') else None
        if fb is not None:
            if fb > MAX_POSITIVE_FUNDING and side == "LONG":
                reasons.append(f"❌ Funding positivo alto ({fb:.4f}) en LONG")
                return {'passed': False, 'reasons': reasons}
            if fb < MIN_NEGATIVE_FUNDING and side == "SHORT":
                reasons.append(f"❌ Funding negativo alto ({fb:.4f}) en SHORT")
                return {'passed': False, 'reasons': reasons}

    # ✅ Scoring final
    score = 0.0
    if USE_SIGNAL_SCORE:
        score += SCORE_WEIGHTS.get("trend_EMA200", 0) * (1.0 if (not REQUIRE_EMA200_TREND or (price >= ta.ema(df['close'], length=200).iloc[-1]) == (side == 'LONG')) else 0)
        score += SCORE_WEIGHTS.get("ema_distance", 0) * min(1.0, ema_distance / MIN_EMA_DISTANCE)
        score += SCORE_WEIGHTS.get("fib_confluence", 0) * (1.0 if (fib_conf + ema_conf + sr_conf) >= 1.0 else 0.0)
        score += SCORE_WEIGHTS.get("rsi_zone", 0) * 1.0
        score += SCORE_WEIGHTS.get("volume_ratio", 0) * min(1.5, vol_ratio) / 1.5
        score += SCORE_WEIGHTS.get("atr_in_range", 0) * 1.0
        score += SCORE_WEIGHTS.get("structure_HH_HL", 0) * 1.0
        if ADX_FILTER:
            adx = float(ta.adx(df['high'], df['low'], df['close'], length=14)['ADX_14'].iloc[-1])
            score += SCORE_WEIGHTS.get("adx", 0) * min(1.0, adx / 50.0)

    if USE_SIGNAL_SCORE and score < MIN_SCORE_TO_TRADE:
        reasons.append(f"❌ Score insuficiente ({score:.2f} < {MIN_SCORE_TO_TRADE:.2f})")
        return {'passed': False, 'reasons': reasons}

    return {
        'passed': True, 
        'reasons': [
            f"✅ Volumen: {vol_ratio:.2f}x",
            f"✅ EMAs separadas: {ema_distance*100:.2f}%",
            f"✅ RSI: {rsi:.1f}",
            f"✅ SL razonable: {sl_distance*100:.2f}%",
            f"✅ Confluencias: {'Sí' if (fib_conf+ema_conf+sr_conf)>=1.0 else 'No'}",
            f"✅ Score: {score:.2f}",
        ],
        'vol_ratio': vol_ratio,
        'rsi': rsi,
        'sl_distance': sl_distance,
        'score': score
    }

def build_levels(side: str, last_row, df, symbol: str, timeframe: str):
    dec = decimals_for(symbol)
    atr_series = ta.atr(df["high"], df["low"], df["close"], length=ATR_LEN)
    atr = float(atr_series.iloc[-1])

    ema20 = float(last_row["EMA20"])
    ema50 = float(last_row["EMA50"])
    price = float(last_row["close"])

    entry_high = max(ema20, ema50)
    entry_low  = min(ema20, ema50)

    # SL/TP basados en ATR y preset
    if side == "LONG":
        sl = price - SL_ATR_MULT * atr
        tps = [price + TP_ATR_MULT * atr * m for m in [1.0, 0.8, 0.6]]
    else:
        sl = price + SL_ATR_MULT * atr
        tps = [price - TP_ATR_MULT * atr * m for m in [1.0, 0.8, 0.6]]

    vol_now = float(df["volume"].iloc[-1])
    vol_avg20 = float(df["volume"].tail(20).mean())
    vol_ratio = vol_now / vol_avg20 if vol_avg20 > 0 else 0.0

    if vol_ratio < 1.0:
        vol_hint = "Volumen bajo 🟡"
    elif vol_ratio < 1.5:
        vol_hint = "Volumen normal ⚪"
    else:
        vol_hint = "Alto volumen 🟢"

    # Info Fib/SR
    fib_info = fib_levels_from_swing(df, FIB_LOOKBACK_SWING, side) if USE_FIB else None
    sr_info = nearest_sr(df, SR_LOOKBACK) if CONFLUENCE_WITH_SR else []

    return {
        'entry_price': price,
        'entry_high': entry_high,
        'entry_low': entry_low,
        'sl_price': sl,
        'tp_prices': tps,
        'vol_ratio': vol_ratio,
        'vol_hint': vol_hint,
        'price': price,
        'decimals': dec,
        'atr': atr,
        'fib': fib_info,
        'sr': sr_info[-5:] if sr_info else []
    }

def format_trade_message(symbol: str, side: str, levels: dict, timeframe: str, 
                         traded: bool = False, filters: dict = None):
    """Formatea el mensaje de alerta/ejecución con info de filtros"""
    sy = display_symbol(symbol)
    tf_name = TIMEFRAME_NAMES.get(timeframe, timeframe)
    dec = levels['decimals']
    fmt = f"{{:.{dec}f}}"
    
    status = "🛡️ <b>TRADE CONSERVADOR EJECUTADO</b>" if traded else "🛡️ <b>SEÑAL CONSERVADORA</b>"
    
    entry_str = f"{fmt.format(levels['entry_high'])} - {fmt.format(levels['entry_low'])}"
    tp_lines = "\n".join([f"🟢 TP{i+1}: {fmt.format(t)}" if side == "LONG"
                          else f"🔻 TP{i+1}: {fmt.format(t)}"
                          for i, t in enumerate(levels['tp_prices'])])
    
    message = f"""{status}
<b>{sy}</b> {'🟢 LONG' if side=='LONG' else '🔴 SHORT'}
⏰ Timeframe: {tf_name}

📍 Zona de Entrada: {entry_str}

{tp_lines}

🔴 SL: {fmt.format(levels['sl_price'])}

💰 Precio Actual: {fmt.format(levels['price'])}
📊 Vol Ratio: {levels['vol_ratio']:.2f}x

💡 {levels['vol_hint']}"""
    
    # Agregar info de filtros si está disponible
    if filters and filters.get('passed'):
        message += "\n\n🛡️ <b>Filtros Conservadores:</b>"
        for reason in filters['reasons']:
            message += f"\n{reason}"
    
    return message

def execute_trade(symbol: str, side: str, levels: dict, timeframe: str):
    """Ejecuta el trade en Binance Futures"""
    if not AUTO_TRADE_ENABLED or trader is None:
        return False
    
    try:
        # Cooldown y límites
        key = f"{symbol}:{timeframe}"
        now = time.time()
        last_t = _last_trade_time.get(key, 0)
        if now - last_t < COOLDOWN_AFTER_TRADE_MIN * 60:
            print(f"⏳ Cooldown activo para {key}, omitiendo...")
            return False
        day = datetime.utcnow().strftime('%Y-%m-%d')
        cnt = _daily_trade_count.get(day, 0)
        if cnt >= MAX_TRADES_PER_DAY:
            print(f"⛔ Límite diario de trades alcanzado ({MAX_TRADES_PER_DAY})")
            return False

        # Verificar número de posiciones abiertas
        open_positions = trader.get_open_positions()
        
        # Verificar si ya hay una posición en este símbolo
        for pos in open_positions:
            if pos['symbol'] == symbol:
                print(f"⚠️ Ya existe una posición abierta en {symbol}, omitiendo...")
                return False
        
        max_conc = min(MAX_CONCURRENT_POS, MAX_POSITIONS)
        if len(open_positions) >= max_conc:
            print(f"⚠️ Máximo de posiciones alcanzado ({max_conc}), omitiendo...")
            return False
        
        # Ejecutar la orden
        result = trader.open_position(
            symbol=symbol,
            side=side,
            entry_price=levels['entry_price'],
            sl_price=levels['sl_price'],
            tp_prices=levels['tp_prices'],
            force_market=USE_MARKET_ORDER
        )
        
        if result:
            print(f"✅ Trade ejecutado: {symbol} {side}")
            
            # 📊 Registrar en la base de datos
            try:
                trade_id = db.add_trade(
                    symbol=symbol,
                    side=side,
                    entry_price=result['entry_price'],
                    quantity=result['quantity'],
                    leverage=result['leverage'],
                    sl_price=result['sl_price'],
                    tp_prices=result['tp_prices'],
                    timeframe=timeframe,
                    notes=f"Señal EMA Conservador - {timeframe}",
                    bot="Conservador"
                )
                
                # Registrar órdenes individuales
                db.add_order(
                    trade_id=trade_id,
                    order_id=str(result['entry_order']['orderId']),
                    order_type="ENTRY",
                    side=result['entry_order']['side'],
                    symbol=symbol,
                    price=result['entry_price'],
                    quantity=result['quantity'],
                    status="FILLED"
                )
                
                db.add_order(
                    trade_id=trade_id,
                    order_id=str(result['sl_order']['orderId']),
                    order_type="STOP_LOSS",
                    side=result['sl_order']['side'],
                    symbol=symbol,
                    price=result['sl_price'],
                    quantity=result['quantity'],
                    status="NEW"
                )
                
                for i, tp_order in enumerate(result['tp_orders'], 1):
                    db.add_order(
                        trade_id=trade_id,
                        order_id=str(tp_order['orderId']),
                        order_type=f"TAKE_PROFIT_{i}",
                        side=tp_order['side'],
                        symbol=symbol,
                        price=tp_order['stopPrice'],
                        quantity=tp_order['origQty'],
                        status="NEW"
                    )
                
                print(f"📊 Trade registrado en DB: ID={trade_id}")
                _last_trade_time[key] = now
                _daily_trade_count[day] = cnt + 1
            except Exception as e:
                print(f"⚠️ Error al registrar en DB: {e}")
            
            return True
        else:
            print(f"❌ No se pudo ejecutar el trade en {symbol}")
            return False
            
    except Exception as e:
        print(f"❌ Error al ejecutar trade: {e}")
        return False

def analyze(symbol, timeframe):
    """Analiza un símbolo con filtros conservadores"""
    df = get_klines(symbol, timeframe, limit=300)
    if len(df) < 200:  # Necesitamos al menos 200 velas para EMA200
        raise ValueError("Datos insuficientes")

    df["EMA20"] = ta.ema(df["close"], length=20)
    df["EMA50"] = ta.ema(df["close"], length=50)

    prev, last = df.iloc[-2], df.iloc[-1]

    signal = "HOLD"
    side = None
    
    # Detectar cruce de EMAs
    if prev["EMA20"] < prev["EMA50"] and last["EMA20"] > last["EMA50"]:
        signal = "BUY"
        side = "LONG"
    elif prev["EMA20"] > prev["EMA50"] and last["EMA20"] < last["EMA50"]:
        signal = "SELL"
        side = "SHORT"

    if signal in ("BUY", "SELL"):
        # Alineación multi-TF
        if TIMEFRAME_ALIGNMENT and not timeframe_alignment_ok(symbol, side):
            return None
        # 🛡️ VERIFICAR FILTROS CONSERVADORES
        last = last.copy()
        last['symbol'] = symbol
        filters = check_filters(side, df, last)
        
        if not filters['passed']:
            # Señal rechazada por filtros
            print(f"🛡️ {display_symbol(symbol)} [{timeframe}]: Señal {signal} RECHAZADA")
            for reason in filters['reasons']:
                print(f"   {reason}")
            return None
        
        # ✅ Señal aprobada por todos los filtros
        levels = build_levels(side, last, df, symbol, timeframe)
        
        # Intentar ejecutar el trade
        traded = False
        if AUTO_TRADE_ENABLED:
            traded = execute_trade(symbol, side, levels, timeframe)
        
        # Enviar mensaje a Telegram
        message = format_trade_message(symbol, side, levels, timeframe, traded, filters)
        send_telegram(message)
        
        return {
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "timeframe": timeframe,
            "signal": signal,
            "side": side,
            "traded": traded,
            "filters": filters
        }
    
    return None

def scan_once():
    """Escanea todas las cryptos en múltiples timeframes"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*60}")
    print(f"🛡️ ESCANEO CONSERVADOR")
    print(f"🔍 {len(WATCHLIST)} cryptos en {len(TIMEFRAMES)} timeframes")
    print(f"📅 {timestamp}")
    if AUTO_TRADE_ENABLED:
        print(f"🤖 TRADING AUTOMÁTICO ACTIVADO")
    else:
        print(f"📢 MODO SOLO ALERTAS")
    print(f"{'='*60}")
    print(f"🛡️ Filtros activos (Conservador):")
    print(f"   ✅ EMA200 requerida: {'Sí' if REQUIRE_EMA200_TREND else 'No'} | Dist EMAs ≥ {MIN_EMA_DISTANCE*100:.2f}% | Slope ≥ {MIN_TREND_SLOPE*100:.2f}%")
    print(f"   ✅ Volumen mínimo: {MIN_VOLUME_RATIO}x | RSI L: {RSI_LONG_MIN}-{RSI_LONG_MAX} / S: {RSI_SHORT_MIN}-{RSI_SHORT_MAX}")
    print(f"   ✅ SL máx: {MAX_SL_PERCENT*100:.1f}% | ATR% [{MIN_ATR_PCT*100:.2f}–{MAX_ATR_PCT*100:.2f}%]")
    print(f"   ✅ Fib: {'ON' if USE_FIB else 'OFF'} | Confluencias EMA/SR: {CONFLUENCE_WITH_EMA}/{CONFLUENCE_WITH_SR}")
    print(f"   ✅ ADX≥{ADX_MIN} | Estructura HH/HL: {'Sí' if STRUCT_REQUIRE_HH_HL else 'No'}")
    print(f"   ✅ Scoring min: {MIN_SCORE_TO_TRADE}")
    print(f"{'='*60}")
    
    signals_found = 0
    trades_executed = 0
    signals_rejected = 0
    
    for symbol in WATCHLIST:
        symbol_has_signal = False
        
        for timeframe in TIMEFRAMES:
            try:
                result = analyze(symbol, timeframe)
                if result:
                    tf_name = TIMEFRAME_NAMES.get(timeframe, timeframe)
                    status = "ejecutado" if result.get('traded') else "detectado"
                    print(f"✅ {display_symbol(symbol)} [{tf_name}]: {result['signal']} → {status}")
                    # Detalle adicional: ATR y SL%
                    try:
                        lv = result.get('levels', {})
                        if lv:
                            sl_pct = abs(lv['price'] - lv['sl_price']) / lv['price'] * 100 if lv['price'] else 0
                            print(f"   ↳ ATR: {lv.get('atr', 0):.4f} | SL: -{sl_pct:.2f}% | Precio: {lv['price']:.6f}")
                    except Exception:
                        pass
                    
                    signals_found += 1
                    if result.get('traded'):
                        trades_executed += 1
                    
                    symbol_has_signal = True
                    time.sleep(1)
                    
            except Exception as e:
                # No mostrar errores normales de "no señal"
                if "Datos insuficientes" not in str(e):
                    print(f"❌ {symbol} [{timeframe}]: error → {e}")
        
        if not symbol_has_signal:
            print(f"   {display_symbol(symbol)}: Sin señales aprobadas")
    
    print(f"\n✅ Escaneo completado: {signals_found} señal(es) aprobada(s)")
    if AUTO_TRADE_ENABLED:
        print(f"🤖 Trades ejecutados: {trades_executed}")
    
    # 📊 GENERAR REPORTES AUTOMÁTICAMENTE
    generar_reportes_automaticos()
    
    return signals_found, trades_executed

def show_positions_summary():
    """Muestra un resumen de las posiciones abiertas"""
    if not AUTO_TRADE_ENABLED or trader is None:
        return
    
    positions = trader.get_open_positions()
    if positions:
        print(f"\n📊 POSICIONES ABIERTAS ({len(positions)}):")
        total_pnl = 0
        for pos in positions:
            # Línea principal
            print(f"\n  🔹 {pos['symbol']}: {pos['side']} | "
                  f"Qty: {pos['quantity']} | "
                  f"Entry: ${pos['entryPrice']:.2f}")
            
            # Stop Loss
            if pos.get('stopLoss'):
                sl_dist = abs(pos['entryPrice'] - pos['stopLoss']) / pos['entryPrice'] * 100
                print(f"     🔴 Stop Loss: ${pos['stopLoss']:.2f} (-{sl_dist:.2f}%)")
            else:
                print(f"     🔴 Stop Loss: No configurado")
            
            # Take Profits
            if pos.get('takeProfits') and len(pos['takeProfits']) > 0:
                for i, tp in enumerate(pos['takeProfits'], 1):
                    tp_dist = abs(tp - pos['entryPrice']) / pos['entryPrice'] * 100
                    print(f"     🟢 TP{i}: ${tp:.2f} (+{tp_dist:.2f}%)")
            else:
                print(f"     🟢 Take Profits: No configurados")
            
            # PnL
            pnl = pos['unrealizedProfit']
            pnl_symbol = "📈" if pnl >= 0 else "📉"
            print(f"     {pnl_symbol} PnL: {pnl:+.2f} USDT")
            
            total_pnl += pnl
        
        print(f"\n  💰 PnL Total: {total_pnl:+.2f} USDT\n")

def main():
    """Loop infinito que escanea cada 30 minutos"""
    print("🛡️ Bot EMA Scanner CONSERVADOR + Auto Trading iniciado")
    print(f"📊 Monitoreando {len(WATCHLIST)} cryptos")
    print(f"⏰ Timeframes: {', '.join(TIMEFRAME_NAMES.values())}")
    print(f"📊 Base de datos: trading_history.db")
    
    if AUTO_TRADE_ENABLED:
        print(f"🤖 TRADING AUTOMÁTICO ACTIVADO")
        print(f"⚡ Tipo de orden: {'MARKET' if USE_MARKET_ORDER else 'LIMIT'}")
        print(f"📈 Max posiciones simultáneas: {MAX_POSITIONS}")
        if trader:
            balance = trader.get_account_balance()
            print(f"💰 Balance: {balance:.2f} USDT")
            print(f"📊 Leverage: {trader.leverage}x")
            print(f"⚠️ Riesgo por trade: {trader.risk_percent}%")
    else:
        print(f"📢 MODO SOLO ALERTAS (trading desactivado)")
    
    print(f"\n🛡️ FILTROS CONSERVADORES ACTIVOS:")
    print(f"   ✅ Volumen mínimo: {MIN_VOLUME_RATIO}x promedio")
    print(f"   ✅ RSI LONG: {RSI_LONG_MIN}-{RSI_LONG_MAX}")
    print(f"   ✅ RSI SHORT: {RSI_SHORT_MIN}-{RSI_SHORT_MAX}")
    print(f"   ✅ Distancia EMAs: mín {MIN_EMA_DISTANCE*100}%")
    print(f"   ✅ SL máximo: {MAX_SL_PERCENT*100}%")
    print(f"   ✅ Tendencia EMA200: {'Requerida' if REQUIRE_EMA200_TREND else 'No requerida'}")
    
    print(f"\n🔄 Escaneando cada 30 minutos...\n")
    
    # Mensaje inicial
    tf_list = ", ".join(TIMEFRAME_NAMES.values())
    mode = "🤖 TRADING AUTOMÁTICO" if AUTO_TRADE_ENABLED else "📢 SOLO ALERTAS"
    send_telegram(f"""🛡️ <b>Bot EMA CONSERVADOR Iniciado</b>

{mode}
📊 {len(WATCHLIST)} cryptos
⏰ Timeframes: {tf_list}
🔄 Escaneo cada 30 min

🛡️ Filtros conservadores activados""")
    
    cycle = 0
    while True:
        try:
            # Mostrar posiciones antes del escaneo
            show_positions_summary()
            
            # Escanear
            cycle += 1
            print(f"\n🔄 Rechequeo #{cycle} iniciado a las {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            t0 = time.time()
            signals, trades = scan_once()
            dt = time.time() - t0
            print(f"✅ Escaneo #{cycle} finalizado en {dt:.1f}s (señales={signals}, trades={trades})")
            
            # Mostrar posiciones después del escaneo
            show_positions_summary()
            
            # Esperar 30 minutos (1800 segundos) con cuenta regresiva visible
            total = 1800
            next_eta = datetime.now().timestamp() + total
            while total > 0:
                mins = total // 60
                secs = total % 60
                eta = datetime.fromtimestamp(next_eta).strftime('%H:%M:%S')
                print(f"⏳ Próximo escaneo en {mins}m {secs:02d}s (ETA {eta})")
                step = 60 if total >= 60 else total
                time.sleep(step)
                total -= step
            
        except KeyboardInterrupt:
            print("\n\n⚠️ Bot detenido por el usuario")
            send_telegram("⚠️ Bot EMA CONSERVADOR detenido")
            break
        except Exception as e:
            print(f"\n❌ Error crítico: {e}")
            send_telegram(f"❌ Bot error: {e}")
            print("⏳ Reintentando en 5 minutos...")
            time.sleep(300)

if __name__ == "__main__":
    main()
