"""
🧭 Bot Swing Trading — 1h a 1d
Versión con múltiples filtros de confirmación orientada a swings limpios.
"""
import os
import time
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from datetime import datetime, timezone
from dotenv import load_dotenv
import requests
from binance_futures_trader import BinanceFuturesTrader
from collections import Counter, deque
from trading_database import TradingDatabase
from trading_dashboard import TradingDashboard, generate_quick_report
from auto_closer import AutoCloser
from risk_utils import env_float, parse_float_list, risk_tp_prices

# ================== CONFIG ==================
load_dotenv()
TOKEN   = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise ValueError("❌ Error: TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no están configurados en .env")

# Configuración de trading
BOT_NAME = "Swing"
MESSAGE_PREFIX = "[SWING]"
DB_PATH = "trading_history.db"
REPORT_BASENAME = "trading_report_swing"

AUTO_TRADE_ENABLED = os.getenv("AUTO_TRADE_ENABLED", "False").lower() == "true"
USE_MARKET_ORDER = os.getenv("USE_MARKET_ORDER", "False").lower() == "true"
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "2"))

BOT_ID = os.getenv("BOT_ID_SWING") or f"SWING-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{os.getpid()}"

# Timeframes Swing
TIMEFRAMES = ["1h", "2h", "4h", "6h", "12h", "1d"]
TIMEFRAME_NAMES = {
    "1h": "1 hora",
    "2h": "2 horas",
    "4h": "4 horas",
    "6h": "6 horas",
    "12h": "12 horas",
    "1d": "1 día",
}

client = Client()

# Cryptos a monitorear (formato Binance sin /)
WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    "LTCUSDT", "TRXUSDT", "BCHUSDT", "UNIUSDT", "NEARUSDT",
    "FILUSDT", "ETCUSDT", "OPUSDT", "ARBUSDT", "ATOMUSDT",
    "HBARUSDT", "VETUSDT", "SUIUSDT", "APTUSDT", "GRTUSDT",
    "AAVEUSDT", "GALAUSDT", "MINAUSDT", "THETAUSDT", "FLOWUSDT",
    "EGLDUSDT", "AXSUSDT", "IMXUSDT", "SANDUSDT", "MANAUSDT",
    "ENJUSDT", "APEUSDT", "QNTUSDT", "DASHUSDT", "COMPUSDT",
    "ONEUSDT", "CHZUSDT", "INJUSDT", "DYDXUSDT", "STXUSDT",
    "CRVUSDT", "KAVAUSDT", "TWTUSDT", "CAKEUSDT", "FXSUSDT",
    "GMXUSDT", "WOOUSDT", "ROSEUSDT", "KDAUSDT", "ZILUSDT",
    "RVNUSDT", "SSVUSDT", "ALGOUSDT", "CELOUSDT", "YFIUSDT",
    "BAKEUSDT", "GTCUSDT", "HIGHUSDT", "IOSTUSDT", "KNCUSDT",
    "LRCUSDT", "MTLUSDT", "OGNUSDT", "ONTUSDT", "STORJUSDT",
]

# 🧭 PRESET SWING — filtros y gestión
REQUIRE_EMA200_TREND = True
MIN_EMA_DISTANCE = 0.0020      # 0.20%
MIN_TREND_SLOPE = 0.0008

MIN_VOLUME_RATIO = 0.90

RSI_LONG_MIN, RSI_LONG_MAX = 40, 70
RSI_SHORT_MIN, RSI_SHORT_MAX = 30, 60

MAX_SL_PERCENT = 0.060        # 6.0%
ATR_LEN = 14
ATR_PERIOD = 14
MIN_ATR_PCT = 0.0015
MAX_ATR_PCT = 0.060
SL_ATR_MULT = 1.2
TP_ATR_MULT = 2.4

USE_FIB = True
FIB_LOOKBACK_SWING = 150
FIB_MIN_SWING_RANGE = 0.010
FIB_RETRACEMENTS = [0.5, 0.618]
FIB_EXTENSIONS = [1.272, 1.618]
FIB_PROXIMITY_TOL = 0.0030
CONFLUENCE_WITH_EMA = True
CONFLUENCE_MAX_DIST_TO_EMA = 0.0030
CONFLUENCE_WITH_SR = True
SR_LOOKBACK = 400
SR_PROXIMITY_TOL = 0.0030
REQUIRE_WICK_REJECTION = True
REQUIRE_CLOSE_IN_DIRECTION = True

STRUCT_REQUIRE_HH_HL = True
STRUCT_SWING_DEPTH = 3
ADX_FILTER = True
ADX_MIN = 18
MIN_BODY_TO_RANGE = 0.50
MAX_UPWICK_FOR_LONG = 0.40
MAX_DOWNWICK_FOR_SHORT = 0.40

TIMEFRAME_ALIGNMENT = True
ALIGN_WITH = ["4h","12h"]
MIN_TICKS_SINCE_SIGNAL = 2
BLOCK_NEWS_SPIKES = True
ALLOW_SESSION = ["UTC_00_24"]

USE_FUNDING_BIAS = True
MAX_POSITIVE_FUNDING = 0.05
MIN_NEGATIVE_FUNDING = -0.05

USE_SIGNAL_SCORE = True
SCORE_WEIGHTS = {
    "trend_EMA200": 1.8,
    "ema_distance": 1.0,
    "fib_confluence": 2.0,
    "rsi_zone": 1.0,
    "volume_ratio": 1.0,
    "atr_in_range": 1.0,
    "structure_HH_HL": 1.2,
    "adx": 1.0,
}
MIN_SCORE_TO_TRADE = 4.2

MAX_CONCURRENT_POS = 3
COOLDOWN_AFTER_TRADE_MIN = 30
MAX_TRADES_PER_DAY = 10
POSITION_SIZE_MULT = 1.0
LEVERAGE_CAP = 5
PYRAMIDING = False
PARTIALS = {"TP1": 1.272, "TP2": 1.414, "TP3": 1.618}

RISK_USD_PER_TRADE = env_float(
    40.0,
    "RISK_USD_SWING",
    "RISK_USD_GLOBAL",
    "RISK_USD_DEFAULT",
    "RISK_AMOUNT_USD",
    context="Swing"
)
RISK_REWARD_TARGETS = parse_float_list(
    os.getenv("SWING_R_MULTIPLIERS", os.getenv("RISK_R_MULTIPLIERS_DEFAULT")),
    default=(1.0, 1.8, 2.5)
)

# Risk/TP config (compatibilidad con funciones existentes)
SWING_LOOKBACK = 10
SL_ATR_BUFFER = 0.2
TP_MULTS = [1.5, 2.5, 3.5]
# ============================================

# Estado runtime para cooldown y límites diarios
_last_trade_time = {}
_daily_trade_count = {}

# Inicializar base de datos
db = TradingDatabase(DB_PATH)

# Inicializar trader
trader = None
auto_closer = None
if AUTO_TRADE_ENABLED:
    try:
        trader = BinanceFuturesTrader(context=BOT_NAME)
        print("✅ Trader de Binance Futures inicializado")
        # 🧩 Iniciar AutoCloser (cierre completo tras TP/SL)
        try:
            auto_closer = AutoCloser(trader, db, bot_name=BOT_NAME)
            auto_closer.start()
        except Exception as e:
            print(f"⚠️ AutoCloser no pudo iniciar: {e}")
        if hasattr(trader, 'reconciler') and trader.reconciler:
            try:
                daemon_interval = int(os.getenv("PROTECTION_DAEMON_INTERVAL", "60"))
                trader.reconciler.start_protection_daemon(db, interval=daemon_interval, bot_name=BOT_NAME)
            except Exception as e:
                print(f"⚠️ Protection daemon no pudo iniciar: {e}")
    except Exception as e:
        print(f"❌ Error al inicializar trader: {e}")
        print("⚠️ El bot funcionará solo en modo alerta (sin trading)")
        AUTO_TRADE_ENABLED = False

def generar_reportes_automaticos():
    """Genera todos los reportes automáticamente después de cada escaneo"""
    try:
        print("\n" + "="*60)
        print("� GENERANDO REPORTES AUTOMÁTICOS...")
        print("="*60)
        print("\n� ESTADÍSTICAS RÁPIDAS:")
        generate_quick_report(DB_PATH, bot=BOT_NAME)
        dashboard = TradingDashboard(DB_PATH)
        dashboard.generate_consolidated_report(output_dir="reports", filename_base=REPORT_BASENAME, bot=BOT_NAME)
        print(f"✅ Gráfico consolidado actualizado: reports/{REPORT_BASENAME}.png")
        print("="*60)
    except Exception as e:
        print(f"⚠️ Error al generar reportes: {e}")

from notifier import send_telegram as _notifier_send


def send_telegram(message: str):
    if not message.startswith(MESSAGE_PREFIX):
        message = f"{MESSAGE_PREFIX} {message}"
    try:
        return _notifier_send(message)
    except Exception as e:
        print(f"[WARN] notifier.send_telegram falló: {e}")
        return False

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
    else:
        sl = price + SL_ATR_MULT * atr

    risk_distance = abs(price - sl)
    tps = risk_tp_prices(price, sl, side, RISK_REWARD_TARGETS)

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
        'risk_distance': risk_distance,
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
    
    status = (
        f"{MESSAGE_PREFIX} 🤖 <b>{BOT_NAME} — TRADE EJECUTADO</b>"
        if traded
        else f"{MESSAGE_PREFIX} � <b>{BOT_NAME} — SEÑAL DETECTADA</b>"
    )
    
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
        message += "\n\n🛡️ <b>Filtros Swing:</b>"
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
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cnt = _daily_trade_count.get(day, 0)
        if cnt >= MAX_TRADES_PER_DAY:
            print(f"⛔ Límite diario de trades alcanzado ({MAX_TRADES_PER_DAY})")
            return False

        max_conc = min(MAX_CONCURRENT_POS, MAX_POSITIONS)

        execution = trader.execute_protected_entry(
            symbol=symbol,
            side=side,
            entry_price=levels['entry_price'],
            sl_price=levels['sl_price'],
            tp_prices=levels['tp_prices'],
            db=db,
            bot_name=BOT_NAME,
            bot_id=BOT_ID,
            timeframe=timeframe,
            notes=f"Señal EMA Swing - {timeframe}",
            force_market=USE_MARKET_ORDER,
            risk_amount_usd=RISK_USD_PER_TRADE,
            context="auto_trading_scanner_swing",
            max_positions=max_conc
        )

        if not execution:
            print(f"❌ No se pudo ejecutar el trade en {symbol}")
            return False

        trade_id = execution['trade_id']

        if trade_monitor:
            try:
                trade_monitor.register_trade(symbol, trade_id)
            except Exception as e:
                print(f"⚠️ Error registrando en TradeMonitor: {e}")

        if hasattr(trader, 'reconciler') and trader.reconciler:
            enable_monitoring = os.getenv("ENABLE_ORDER_MONITORING", "True").lower() == "true"
            if enable_monitoring:
                monitor_duration = int(os.getenv("ORDER_MONITOR_DURATION", "120"))
                monitor_interval = int(os.getenv("ORDER_MONITOR_INTERVAL", "15"))

                trader.reconciler.start_monitoring(
                    symbol=symbol,
                    trade_id=trade_id,
                    duration_seconds=monitor_duration,
                    check_interval=monitor_interval
                )

        print(f"✅ Trade ejecutado: {symbol} {side} (ID={trade_id})")
        _last_trade_time[key] = now
        _daily_trade_count[day] = cnt + 1
        return True
            
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

    if signal not in ("BUY", "SELL"):
        return {"status": "no_signal"}

    if TIMEFRAME_ALIGNMENT and not timeframe_alignment_ok(symbol, side):
        return {
            "status": "rejected",
            "symbol": symbol,
            "timeframe": timeframe,
            "side": side,
            "reasons": ["❌ Alineación TF no válida"],
        }

    last = last.copy()
    last['symbol'] = symbol
    filters = check_filters(side, df, last)

    if not filters['passed']:
        return {
            "status": "rejected",
            "symbol": symbol,
            "timeframe": timeframe,
            "side": side,
            "reasons": filters.get('reasons', []),
        }

    levels = build_levels(side, last, df, symbol, timeframe)
    return {
        "status": "approved",
        "symbol": symbol,
        "timeframe": timeframe,
        "side": side,
        "filters": filters,
        "levels": levels,
    }

def scan_once():
    """Escanea todas las cryptos en múltiples timeframes"""
    print("\n" + "="*60)
    print(f"🧭 ESCANEO {BOT_NAME.upper()}")
    print(f"🔍 {len(WATCHLIST)} cryptos en {len(TIMEFRAMES)} timeframes")
    print(datetime.now(timezone.utc).strftime("📅 %Y-%m-%d %H:%M:%S UTC"))
    print("🤖 TRADING AUTOMÁTICO ACTIVADO" if AUTO_TRADE_ENABLED else "📢 MODO SOLO ALERTAS")
    print("="*60)
    print(f"🛡️ Filtros activos ({BOT_NAME}):")
    print(f"   ✅ EMA200 requerida: {'Sí' if REQUIRE_EMA200_TREND else 'No'} | Dist EMAs ≥ {MIN_EMA_DISTANCE*100:.2f}% | Slope ≥ {MIN_TREND_SLOPE*100:.2f}%")
    print(f"   ✅ Volumen mínimo: {MIN_VOLUME_RATIO:.2f}x | RSI L: {RSI_LONG_MIN}-{RSI_LONG_MAX} / S: {RSI_SHORT_MIN}-{RSI_SHORT_MAX}")
    print(f"   ✅ SL máx: {MAX_SL_PERCENT*100:.1f}% | ATR% [{MIN_ATR_PCT*100:.2f}–{MAX_ATR_PCT*100:.2f}%]")
    print(f"   ✅ Fib: {'ON' if USE_FIB else 'OFF'} | Confluencias EMA/SR: {CONFLUENCE_WITH_EMA}/{CONFLUENCE_WITH_SR}")
    print(f"   ✅ ADX≥{ADX_MIN} | Estructura HH/HL: {'Sí' if STRUCT_REQUIRE_HH_HL else 'No'}")
    print(f"   ✅ Score min: {MIN_SCORE_TO_TRADE:.2f}")
    print("="*60)

    summary = {"detected": 0, "approved": 0, "rejected": 0, "executed": 0}
    rejection_reasons: Counter[str] = Counter()

    for symbol in WATCHLIST:
        try:
            per_symbol_details = []
            for timeframe in TIMEFRAMES:
                try:
                    result = analyze(symbol, timeframe)
                except ValueError:
                    continue
                except Exception as e:
                    print(f"⚠️ Error analizando {symbol} [{timeframe}]: {e}")
                    continue

                if not result or result.get("status") == "no_signal":
                    continue

                summary["detected"] += 1

                status = result.get("status")
                side = result.get("side")
                if status == "rejected":
                    summary["rejected"] += 1
                    reasons = result.get("reasons", [])
                    try:
                        print(f"🛡️ {display_symbol(symbol)} [{timeframe}]: Señal {'BUY' if side=='LONG' else 'SELL'} RECHAZADA")
                        for reason in reasons[:3]:
                            print(f"   {reason}")
                    except Exception:
                        pass
                    if reasons:
                        rejection_reasons[reasons[0]] += 1
                    continue

                if status == "approved":
                    summary["approved"] += 1
                    levels = result["levels"]
                    filters = result.get("filters")
                    per_symbol_details.append(
                        f"[{timeframe}] {side} | Precio: {levels['entry_price']:.6f}"
                    )
                    send_telegram(format_trade_message(symbol, side, levels, timeframe, traded=False, filters=filters))
                    try:
                        db.increment_bot_activity(bot=BOT_NAME, approved_delta=1)
                    except Exception:
                        pass

                    traded = False
                    if AUTO_TRADE_ENABLED:
                        traded = execute_trade(symbol, side, levels, timeframe)
                    if traded:
                        summary["executed"] += 1
                        try:
                            db.increment_bot_activity(bot=BOT_NAME, executed_delta=1)
                        except Exception:
                            pass
                        send_telegram(format_trade_message(symbol, side, levels, timeframe, traded=True, filters=filters))

                    time.sleep(0.05)

            if per_symbol_details:
                print(f"   {display_symbol(symbol)}: Señales")
                for line in per_symbol_details:
                    print(f"      - {line}")
            else:
                print(f"   {display_symbol(symbol)}: Sin señales aprobadas")
        except Exception as e:
            print(f"⚠️ Error analizando {symbol}: {e}")

    print(f"\n📊 Resumen [{BOT_NAME.upper()}]:")
    print(f"   Señales detectadas: {summary['detected']}")
    print(f"   Señales aprobadas: {summary['approved']}")
    print(f"   Señales rechazadas: {summary['rejected']}")
    if rejection_reasons:
        print("   Principales rechazos:")
        for reason, count in rejection_reasons.most_common(2):
            print(f"      - {reason} ({count})")
    print(f"   Trades ejecutados: {summary['executed']}")

    generar_reportes_automaticos()

    return summary

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
    print("🚀 Bot Swing EMA + Auto Trading iniciado")
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
    
    print(f"\n🛡️ FILTROS SWING ACTIVOS:")
    print(f"   ✅ Volumen mínimo: {MIN_VOLUME_RATIO}x promedio")
    print(f"   ✅ RSI LONG: {RSI_LONG_MIN}-{RSI_LONG_MAX}")
    print(f"   ✅ RSI SHORT: {RSI_SHORT_MIN}-{RSI_SHORT_MAX}")
    print(f"   ✅ Distancia EMAs: mín {MIN_EMA_DISTANCE*100}%")
    print(f"   ✅ SL máximo: {MAX_SL_PERCENT*100}%")
    print(f"   ✅ Tendencia EMA200: {'Requerida' if REQUIRE_EMA200_TREND else 'No requerida'}")
    
    print(f"\n🔄 Escaneando cada 15 minutos...\n")
    
    # Mensaje inicial
    tf_list = ", ".join(TIMEFRAME_NAMES.values())
    mode = "🤖 TRADING AUTOMÁTICO" if AUTO_TRADE_ENABLED else "📢 SOLO ALERTAS"
    send_telegram(f"""🚀 <b>Bot Swing EMA Iniciado</b>

{mode}
📊 {len(WATCHLIST)} cryptos
⏰ Timeframes: {tf_list}
🔄 Escaneo cada 15 min

🛡️ Filtros Swing activados""")
    
    cycle = 0
    while True:
        try:
            # Mostrar posiciones antes del escaneo
            show_positions_summary()
            
            # Escanear
            cycle += 1
            print(f"\n🔄 Rechequeo #{cycle} iniciado a las {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            t0 = time.time()
            summary = scan_once()
            dt = time.time() - t0
            print(
                "✅ Escaneo #{cycle} finalizado en {dt:.1f}s (detected={det}, approved={app}, executed={exe})".format(
                    cycle=cycle,
                    dt=dt,
                    det=summary.get("detected", 0),
                    app=summary.get("approved", 0),
                    exe=summary.get("executed", 0),
                )
            )
            
            # Mostrar posiciones después del escaneo
            show_positions_summary()
            
            # Esperar 15 minutos (900 segundos) con cuenta regresiva visible
            total = 900
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
            send_telegram("⚠️ Bot Swing EMA detenido")
            try:
                if auto_closer:
                    auto_closer.stop()
            except Exception:
                pass
            break
        except Exception as e:
            print(f"\n❌ Error crítico: {e}")
            send_telegram(f"❌ Bot error: {e}")
            print("⏳ Reintentando en 5 minutos...")
            time.sleep(600)

    # Al salir del main loop, asegurar detener AutoCloser
    try:
        if auto_closer:
            auto_closer.stop()
    except Exception:
        pass

if __name__ == "__main__":
    main()
