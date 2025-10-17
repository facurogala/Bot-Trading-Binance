"""
⚡ Scanner SCALPING — especializado en 5m a 1h
Señales rápidas con filtros moderados y SL ajustado para movimientos cortos.
"""
import os
import random
import time
from collections import Counter
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from datetime import datetime, timezone
from dotenv import load_dotenv
import requests
from binance_futures_trader import BinanceFuturesTrader
from trading_database import TradingDatabase
from trading_dashboard import TradingDashboard, generate_quick_report
from auto_closer import AutoCloser
from risk_utils import env_float, parse_float_list, risk_tp_prices
from trade_monitor import TradeMonitor
from trailing_stop_manager import TrailingStopManager, TrailingConfig

# ================== CONFIG ==================
load_dotenv()

BOT_NAME = "Scalping"
MESSAGE_PREFIX = "[SCALP]"
REPORT_BASENAME = "trading_report_scalp"
DB_PATH = "trading_history.db"
BOT_ID = os.getenv("BOT_ID_SCALPING") or f"SCALP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{os.getpid()}"

TOKEN   = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise ValueError("❌ Error: TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no están configurados en .env")

# Configuración de trading
AUTO_TRADE_ENABLED = os.getenv("AUTO_TRADE_ENABLED", "False").lower() == "true"
USE_MARKET_ORDER = os.getenv("USE_MARKET_ORDER", "False").lower() == "true"
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS_SCALPING", os.getenv("MAX_POSITIONS", "3")))

# Timeframes foco scalping
TIMEFRAMES = ["5m", "15m", "30m", "1h"]
TIMEFRAME_NAMES = {
    "5m": "5 minutos",
    "15m": "15 minutos",
    "30m": "30 minutos",
    "1h": "1 hora",
}

client = Client()

WATCHLIST = [
    "ADAUSDT", "ATOMUSDT", "BNBUSDT", "COMPUSDT", "DYDXUSDT", "FETUSDT",
    "GMXUSDT", "INJUSDT", "LDOUSDT", "MINAUSDT", "QNTUSDT", "SEIUSDT",
    "SUIUSDT", "TONUSDT", "YFIUSDT", "1000CATUSDT", "1MBABYDOGEUSDT", "AIUSDT",
    "ALTUSDT", "ARKMUSDT", "ASTRUSDT", "AWEUSDT", "BANANAUSDT", "BBUSDT",
    "BLURUSDT", "CELOUSDT", "CHESSUSDT", "CUSDT", "DOGSUSDT", "EGLDUSDT",
    "EPICUSDT", "GASUSDT", "HOLOUSDT", "IDUSDT", "IOUSDT", "KAIAUSDT",
    "LAUSDT", "LRCUSDT", "MAVUSDT", "MITOUSDT", "NEIROUSDT", "NMRUSDT",
    "OMUSDT", "ORDIUSDT", "PENGUUSDT", "PLUMEUSDT", "QTUMUSDT", "RLCUSDT",
    "SAHARAUSDT", "SIGNUSDT", "SPKUSDT", "STOUSDT", "SUSDT", "THEUSDT",
    "TRUMPUSDT", "TWTUSDT", "VANRYUSDT", "WIFUSDT", "WUSDT", "XTZUSDT",
    "ZENUSDT",
]



# ===== PRESET SCALPING =====
ATR_PERIOD = 14
ATR_LEN = 14
SWING_LOOKBACK = 8
SL_ATR_MULT = 1.0
TP_ATR_MULT = 2.0
TP_MULTS = [1.0, 1.5, 2.0]

# Tendencia/EMAs
REQUIRE_EMA200_TREND = True
MIN_EMA_DISTANCE = 0.0030     # 0.30%
MIN_TREND_SLOPE = 0.0012      # más momentum

# Volumen y RSI
MIN_VOLUME_RATIO = 1.10
RSI_LONG_MIN, RSI_LONG_MAX = 40, 70
RSI_SHORT_MIN, RSI_SHORT_MAX = 30, 60

# Stop/TP / Volatilidad (ajustado a movimientos cortos)
MAX_SL_PERCENT = 0.015        # 1.5%
MIN_ATR_PCT = 0.0010          # 0.10%
MAX_ATR_PCT = 0.030           # 3.0%

# Confluencias rápidas
USE_FIB = True
FIB_LOOKBACK_SWING = 80
FIB_MIN_SWING_RANGE = 0.006
FIB_RETRACEMENTS = [0.382, 0.5, 0.618]
FIB_EXTENSIONS = [1.272, 1.414, 1.618]
FIB_PROXIMITY_TOL = 0.0020
CONFLUENCE_WITH_EMA = True
CONFLUENCE_MAX_DIST_TO_EMA = 0.0025
CONFLUENCE_WITH_SR = True
SR_LOOKBACK = 180
SR_PROXIMITY_TOL = 0.0020
REQUIRE_WICK_REJECTION = False
REQUIRE_CLOSE_IN_DIRECTION = True

# Estructura / Momentum
STRUCT_REQUIRE_HH_HL = False
STRUCT_SWING_DEPTH = 2
ADX_FILTER = True
ADX_MIN = 15
MIN_BODY_TO_RANGE = 0.45
MAX_UPWICK_FOR_LONG = 0.50
MAX_DOWNWICK_FOR_SHORT = 0.50

# Alineación intra-día
TIMEFRAME_ALIGNMENT = True
ALIGN_WITH = ["15m", "30m"]
MIN_TICKS_SINCE_SIGNAL = 1
BLOCK_NEWS_SPIKES = False
ALLOW_SESSION = ["UTC_00_24"]

# Funding
USE_FUNDING_BIAS = True
MAX_POSITIVE_FUNDING = 0.06
MIN_NEGATIVE_FUNDING = -0.06

# Score
USE_SIGNAL_SCORE = True
SCORE_WEIGHTS = {
    "trend_EMA200": 1.6,
    "ema_distance": 1.0,
    "fib_confluence": 1.4,
    "rsi_zone": 0.9,
    "volume_ratio": 1.2,
    "atr_in_range": 1.0,
    "structure_HH_HL": 0.6,
    "adx": 0.8,
}
MIN_SCORE_TO_TRADE = 3.8

# Gestión / Frecuencia
MAX_CONCURRENT_POS = 3
COOLDOWN_AFTER_TRADE_MIN = 10
MAX_TRADES_PER_DAY = 20
POSITION_SIZE_MULT = 0.8
LEVERAGE_CAP = 5
PYRAMIDING = False
PARTIALS = {"TP1": 1.272, "TP2": 1.414, "TP3": 1.618}

RISK_USD_PER_TRADE = env_float(
    10.0,
    "RISK_USD_SCALPING",
    "RISK_USD_GLOBAL",
    "RISK_USD_DEFAULT",
    "RISK_AMOUNT_USD",
    context="Scalping"
)
RISK_REWARD_TARGETS = parse_float_list(
    os.getenv("SCALPING_R_MULTIPLIERS", os.getenv("RISK_R_MULTIPLIERS_DEFAULT")),
    default=(0.7, 1.2, 1.8)
)

# Trailing stop configuration (Scalping estándar)
# Habilitamos por defecto el modo 'tp_lock' desde TP1 para mover el SL al TP alcanzado
TRAILING_MODE = (os.getenv("SCALPING_TRAILING_MODE", os.getenv("TRAILING_MODE_DEFAULT", "tp_lock")) or "tp_lock").strip().lower()
TRAILING_FROM_TP = int(os.getenv("SCALPING_TRAILING_FROM_TP", os.getenv("TRAILING_FROM_TP", "1")))
TRAILING_DYNAMIC_METHOD = (os.getenv("SCALPING_TRAILING_METHOD", os.getenv("TRAILING_METHOD_DEFAULT", "atr")) or "atr").strip().lower()
TRAILING_ATR_MULT = env_float(1.2, "SCALPING_TRAILING_ATR_MULT", "TRAILING_ATR_MULT")
TRAILING_ATR_PERIOD = int(os.getenv("SCALPING_TRAILING_ATR_PERIOD", os.getenv("TRAILING_ATR_PERIOD", "14")))
TRAILING_EMA_PERIOD = int(os.getenv("SCALPING_TRAILING_EMA_PERIOD", os.getenv("TRAILING_EMA_PERIOD", "34")))
TRAILING_SWING_LOOKBACK = int(os.getenv("SCALPING_TRAILING_SWING_LOOKBACK", os.getenv("TRAILING_SWING_LOOKBACK", "5")))
TRAILING_MIN_IMPROVEMENT_PCT = env_float(0.0003, "SCALPING_TRAILING_MIN_IMPROVEMENT_PCT", "TRAILING_MIN_IMPROVEMENT_PCT")
TRAILING_BE_BUFFER_PCT = env_float(0.0, "SCALPING_BREAK_EVEN_BUFFER", "TRAILING_BREAK_EVEN_BUFFER")
TRAILING_LOCK_BUFFER_PCT = env_float(0.0, "SCALPING_TRAILING_LOCK_BUFFER", "TRAILING_LOCK_BUFFER")
TRAILING_GUARD_TICKS = int(os.getenv("SCALPING_TRAILING_GUARD_TICKS", os.getenv("TRAILING_GUARD_TICKS", "2")))
TRAILING_TIMEFRAME = os.getenv("SCALPING_TRAILING_TIMEFRAME", "15m")
TRAILING_NOTIFY = os.getenv("SCALPING_TRAILING_NOTIFY", "True").lower() == "true"

# Re-escanear cada 10 minutos
SCAN_INTERVAL_SECONDS = 900
STARTUP_JITTER_RANGE = (
    env_float(2.0, "SCALPING_JITTER_MIN", "STARTUP_JITTER_MIN", "JITTER_MIN", context="Scalping"),
    env_float(5.0, "SCALPING_JITTER_MAX", "STARTUP_JITTER_MAX", "JITTER_MAX", context="Scalping"),
)

# Estado runtime
_last_trade_time = {}
_daily_trade_count = {}

# Inicializar base de datos y trader
db = TradingDatabase(DB_PATH)
trader = None
auto_closer = None
trailing_manager = None
trade_monitor = None
if AUTO_TRADE_ENABLED:
    try:
        trader = BinanceFuturesTrader(context=BOT_NAME)
        print("✅ Trader de Binance Futures inicializado")
        try:
            auto_closer = AutoCloser(trader, db, bot_name=BOT_NAME)
            auto_closer.start()
        except Exception as e:
            print(f"⚠️ AutoCloser no pudo iniciar: {e}")
        try:
            trailing_config = TrailingConfig(
                mode=TRAILING_MODE,
                start_tp=max(1, TRAILING_FROM_TP),
                dynamic_method=TRAILING_DYNAMIC_METHOD,
                atr_period=TRAILING_ATR_PERIOD,
                atr_mult=TRAILING_ATR_MULT,
                ema_period=TRAILING_EMA_PERIOD,
                swing_lookback=TRAILING_SWING_LOOKBACK,
                min_improvement_pct=TRAILING_MIN_IMPROVEMENT_PCT,
                break_even_buffer_pct=TRAILING_BE_BUFFER_PCT,
                lock_tp_buffer_pct=TRAILING_LOCK_BUFFER_PCT,
                guard_ticks=TRAILING_GUARD_TICKS,
                timeframe_fallback=TRAILING_TIMEFRAME,
                allow_notifications=TRAILING_NOTIFY,
            )
            trailing_manager = TrailingStopManager(
                trader=trader,
                db=db,
                bot_name=BOT_NAME,
                config=trailing_config,
                notify_func=None,
            )
        except Exception as e:
            trailing_manager = None
            print(f"⚠️ TrailingStopManager no pudo iniciar: {e}")
        try:
            trade_monitor = TradeMonitor(trader, db, bot_name=BOT_NAME, trailing_manager=trailing_manager)
            trade_monitor.start()
        except Exception as e:
            trade_monitor = None
            print(f"⚠️ TradeMonitor no pudo iniciar: {e}")
        if hasattr(trader, 'reconciler') and trader.reconciler:
            try:
                daemon_interval = int(os.getenv("PROTECTION_DAEMON_INTERVAL", "45"))
                trader.reconciler.start_protection_daemon(db, interval=daemon_interval, bot_name=BOT_NAME)
            except Exception as e:
                print(f"⚠️ Protection daemon no pudo iniciar: {e}")
    except Exception as e:
        print(f"❌ Error al inicializar trader: {e}")
        print("⚠️ El bot funcionará solo en modo alerta (sin trading)")
        AUTO_TRADE_ENABLED = False

from notifier import send_telegram as _notifier_send


def send_telegram(message: str):
    if not message.startswith(MESSAGE_PREFIX):
        message = f"{MESSAGE_PREFIX} {message}"
    try:
        return _notifier_send(message)
    except Exception as e:
        print(f"[WARN] notifier.send_telegram falló: {e}")
        return False

if TRAILING_NOTIFY and 'trailing_manager' in globals() and trailing_manager:
    try:
        trailing_manager.notify = send_telegram
    except Exception:
        pass

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

def format_trade_message(symbol: str, side: str, levels: dict, timeframe: str, traded: bool = False):
    sy = display_symbol(symbol)
    tf_name = TIMEFRAME_NAMES.get(timeframe, timeframe)
    dec = levels['decimals']
    fmt = f"{{:.{dec}f}}"
    status = (
        f"{MESSAGE_PREFIX} 🤖 <b>{BOT_NAME} — TRADE EJECUTADO</b>"
        if traded
        else f"{MESSAGE_PREFIX} 🚨 <b>{BOT_NAME} — SEÑAL DETECTADA</b>"
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
📊 Vol Ratio: {levels['vol_ratio']:.2f}x"""
    return message

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

    vol_now = float(df["volume"].iloc[-1])
    vol_avg20 = float(df["volume"].tail(20).mean())
    vol_ratio = vol_now / vol_avg20 if vol_avg20 > 0 else 1.0

    if side == "LONG":
        sl = recent_lows - SL_ATR_MULT * atr
    else:
        sl = recent_highs + SL_ATR_MULT * atr

    risk_distance = abs(price - sl)
    tps = risk_tp_prices(price, sl, side, RISK_REWARD_TARGETS)

    return {
        'entry_price': price,
        'entry_high': entry_high,
        'entry_low': entry_low,
        'sl_price': sl,
        'tp_prices': tps,
        'vol_ratio': vol_ratio,
        'price': price,
        'decimals': dec,
        'atr': atr,
        'risk_distance': risk_distance
    }

def check_filters(side: str, df: pd.DataFrame, last_row) -> dict:
    reasons = []
    price = float(last_row["close"]) if "close" in last_row else float(last_row.close)

    # Volumen
    vol_now = float(df["volume"].iloc[-1])
    vol_avg20 = float(df["volume"].tail(20).mean())
    vol_ratio = vol_now / vol_avg20 if vol_avg20 > 0 else 0.0
    if vol_ratio < MIN_VOLUME_RATIO:
        reasons.append(f"❌ Volumen bajo ({vol_ratio:.2f}x < {MIN_VOLUME_RATIO:.2f}x)")
        return {"passed": False, "reasons": reasons}

    # EMAs
    ema20 = float(last_row["EMA20"]) if "EMA20" in last_row else float(last_row.EMA20)
    ema50 = float(last_row["EMA50"]) if "EMA50" in last_row else float(last_row.EMA50)
    ema_distance = abs(ema20 - ema50) / price if price else 0.0
    if ema_distance < MIN_EMA_DISTANCE:
        reasons.append(f"❌ EMAs muy cercanas ({ema_distance*100:.2f}% < {MIN_EMA_DISTANCE*100:.2f}%)")
        return {"passed": False, "reasons": reasons}

    # RSI
    rsi_series = ta.rsi(df["close"], length=14)
    rsi = float(rsi_series.iloc[-1])
    if side == "LONG":
        if not (RSI_LONG_MIN <= rsi <= RSI_LONG_MAX):
            reasons.append(f"❌ RSI LONG fuera ({rsi:.1f} no está {RSI_LONG_MIN}-{RSI_LONG_MAX})")
            return {"passed": False, "reasons": reasons}
    else:
        if not (RSI_SHORT_MIN <= rsi <= RSI_SHORT_MAX):
            reasons.append(f"❌ RSI SHORT fuera ({rsi:.1f} no está {RSI_SHORT_MIN}-{RSI_SHORT_MAX})")
            return {"passed": False, "reasons": reasons}

    # Tendencia EMA200
    if REQUIRE_EMA200_TREND:
        ema200 = ta.ema(df["close"], length=200)
        if len(ema200) > 0:
            ema200_val = float(ema200.iloc[-1])
            if side == "LONG" and price < ema200_val:
                reasons.append("❌ Por debajo de EMA200 (bajista)")
                return {"passed": False, "reasons": reasons}
            if side == "SHORT" and price > ema200_val:
                reasons.append("❌ Por encima de EMA200 (alcista)")
                return {"passed": False, "reasons": reasons}

    # Slope EMA20
    slope20 = float(ta.ema(df["close"], length=20).diff().iloc[-1]) / price if price else 0.0
    if abs(slope20) < MIN_TREND_SLOPE:
        reasons.append(f"❌ Pendiente EMA20 baja ({slope20*100:.2f}% < {MIN_TREND_SLOPE*100:.2f}%)")
        return {"passed": False, "reasons": reasons}

    # ATR% rango y SL máximo
    atr_series = ta.atr(df["high"], df["low"], df["close"], length=ATR_PERIOD)
    atrp = float(atr_series.iloc[-1]) / price if price else 0.0
    if not (MIN_ATR_PCT <= atrp <= MAX_ATR_PCT):
        reasons.append(f"❌ ATR fuera de rango ({atrp*100:.2f}% no en {MIN_ATR_PCT*100:.2f}-{MAX_ATR_PCT*100:.2f}%)")
        return {"passed": False, "reasons": reasons}

    recent_lows  = df["low"].tail(SWING_LOOKBACK).min()
    recent_highs = df["high"].tail(SWING_LOOKBACK).max()
    sl = (recent_lows - SL_ATR_MULT * float(atr_series.iloc[-1])) if side == "LONG" else (recent_highs + SL_ATR_MULT * float(atr_series.iloc[-1]))
    sl_distance = abs(price - sl) / price if price else 0.0
    if sl_distance > MAX_SL_PERCENT:
        reasons.append(f"❌ SL muy amplio ({sl_distance*100:.2f}% > {MAX_SL_PERCENT*100:.1f}%)")
        return {"passed": False, "reasons": reasons}

    return {"passed": True, "reasons": [
        f"✅ Volumen: {vol_ratio:.2f}x",
        f"✅ EMAs separadas: {ema_distance*100:.2f}%",
        f"✅ RSI: {rsi:.1f}",
        f"✅ ATR en rango",
    ]}

def execute_trade(symbol: str, side: str, levels: dict, timeframe: str):
    if not AUTO_TRADE_ENABLED or trader is None:
        return False
    try:
        key = f"{symbol}:{timeframe}"
        now = time.time()
        last_t = _last_trade_time.get(key, 0)
        if now - last_t < COOLDOWN_AFTER_TRADE_MIN * 60:
            print(f"⏳ Cooldown activo para {key}, omitiendo...")
            return False

        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        day_stats = _daily_trade_count.get(day, {"detected": 0, "executed": 0})
        if day_stats.get("executed", 0) >= MAX_TRADES_PER_DAY:
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
            bot_name="Scalping",
            bot_id=BOT_ID,
            timeframe=timeframe,
            notes=f"Señal Scalping - {timeframe}",
            force_market=USE_MARKET_ORDER,
            risk_amount_usd=RISK_USD_PER_TRADE,
            context="auto_trading_scanner_scalping",
            max_positions=max_conc
        )
        if execution:
            trade_id = execution['trade_id']
            if trade_monitor:
                try:
                    trade_monitor.register_trade(symbol, trade_id)
                except Exception as tm_err:
                    print(f"⚠️ TradeMonitor no pudo registrar {symbol}: {tm_err}")
            day_stats["executed"] = day_stats.get("executed", 0) + 1
            _daily_trade_count[day] = day_stats
            _last_trade_time[key] = now
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
            return True
    except Exception as e:
        print(f"❌ Error en execute_trade: {e}")
    return False

def run_scan_once():
    print("\n" + "="*60)
    print("⚡ ESCANEO SCALPING")
    print(f"🔍 {len(WATCHLIST)} cryptos en {len(TIMEFRAMES)} timeframes")
    print(datetime.now(timezone.utc).strftime("📅 %Y-%m-%d %H:%M:%S UTC"))
    print("🤖 TRADING AUTOMÁTICO ACTIVADO" if AUTO_TRADE_ENABLED else "📢 MODO SOLO ALERTAS")
    print("="*60)
    print("🛡️ Filtros activos (Scalping):")
    print(f"   ✅ EMA200 requerida: {'Sí' if REQUIRE_EMA200_TREND else 'No'} | Dist EMAs ≥ {MIN_EMA_DISTANCE*100:.2f}% | Slope ≥ {MIN_TREND_SLOPE*100:.2f}%")
    print(f"   ✅ Volumen mínimo: {MIN_VOLUME_RATIO}x | RSI L: {RSI_LONG_MIN}-{RSI_LONG_MAX} / S: {RSI_SHORT_MIN}-{RSI_SHORT_MAX}")
    print(f"   ✅ SL máx: {MAX_SL_PERCENT*100:.1f}% | ATR% [{MIN_ATR_PCT*100:.2f}–{MAX_ATR_PCT*100:.2f}%]")
    print(f"   ✅ Fib: {'ON' if USE_FIB else 'OFF'} | Confluencias EMA/SR: {CONFLUENCE_WITH_EMA}/{CONFLUENCE_WITH_SR}")
    print(f"   ✅ ADX≥{ADX_MIN} | Estructura HH/HL: {'Sí' if STRUCT_REQUIRE_HH_HL else 'No'}")
    print(f"   ✅ Scoring min: {MIN_SCORE_TO_TRADE}")
    print("="*60)

    summary = {"detected": 0, "approved": 0, "rejected": 0, "executed": 0}
    rejection_reasons: Counter[str] = Counter()

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    day_stats = _daily_trade_count.get(day, {"detected": 0, "approved": 0, "executed": 0})

    for symbol in WATCHLIST:
        try:
            per_symbol_details = []
            for timeframe in TIMEFRAMES:
                df = get_klines(symbol, timeframe, limit=220)
                if df is None or df.empty or len(df) < 60:
                    continue
                df["EMA20"] = ta.ema(df["close"], length=20)
                df["EMA50"] = ta.ema(df["close"], length=50)
                last = df.iloc[-1]
                side = "LONG" if last["EMA20"] > last["EMA50"] else "SHORT"
                filt = check_filters(side, df, last)
                summary["detected"] += 1
                day_stats["detected"] = day_stats.get("detected", 0) + 1
                if not filt.get("passed"):
                    # Log rechazo estilo Swing
                    try:
                        print(f"🛡️ {display_symbol(symbol)} [{timeframe}]: Señal {'BUY' if side=='LONG' else 'SELL'} RECHAZADA")
                        for reason in filt.get('reasons', []):
                            print(f"   {reason}")
                    except Exception:
                        pass
                    summary["rejected"] += 1
                    reasons = filt.get('reasons', [])
                    if reasons:
                        rejection_reasons[reasons[0]] += 1
                    continue
                levels = build_levels(side, last, df, symbol, timeframe)
                per_symbol_details.append(f"[{timeframe}] {side} | Precio: {levels['entry_price']}")
                summary["approved"] += 1
                day_stats["approved"] = day_stats.get("approved", 0) + 1
                msg = format_trade_message(symbol, side, levels, timeframe, traded=False)
                send_telegram(msg)
                # Contabilizar señal aprobada
                try:
                    db.increment_bot_activity(bot=BOT_NAME, approved_delta=1)
                except Exception:
                    pass
                if AUTO_TRADE_ENABLED and trader is not None:
                    traded = execute_trade(symbol, side, levels, timeframe)
                    if traded:
                        try:
                            db.increment_bot_activity(bot=BOT_NAME, executed_delta=1)
                        except Exception:
                            pass
                        send_telegram(format_trade_message(symbol, side, levels, timeframe, traded=True))
                        summary["executed"] += 1
                        day_stats["executed"] = day_stats.get("executed", 0) + 1
                time.sleep(0.05)
            if per_symbol_details:
                print(f"   {display_symbol(symbol)}: Señales")
                for line in per_symbol_details:
                    print(f"      - {line}")
            else:
                print(f"   {display_symbol(symbol)}: Sin señales aprobadas")
        except Exception as e:
            print(f"⚠️ Error analizando {symbol}: {e}")

    _daily_trade_count[day] = day_stats

    print(f"\n📊 Resumen [{BOT_NAME.upper()}]:")
    print(f"   Señales detectadas: {summary['detected']}")
    print(f"   Señales aprobadas: {summary['approved']}")
    print(f"   Señales rechazadas: {summary['rejected']}")
    if rejection_reasons:
        print("   Principales rechazos:")
        for reason, count in rejection_reasons.most_common(2):
            print(f"      - {reason} ({count})")
    print(f"   Trades ejecutados: {summary['executed']}")

    # Reportes consolidado → trading_history
    try:
        print("\n" + "="*60)
        print("📈 GENERANDO REPORTES AUTOMÁTICOS...")
        print("="*60)
        print("\n� ESTADÍSTICAS RÁPIDAS:")
        generate_quick_report(DB_PATH, bot=BOT_NAME)
        dashboard = TradingDashboard(DB_PATH)
        dashboard.generate_consolidated_report(output_dir="reports", filename_base=REPORT_BASENAME, bot=BOT_NAME)
        print(f"✅ Gráfico consolidado actualizado: reports/{REPORT_BASENAME}.png")
        print("="*60)
    except Exception as e:
        print(f"⚠️ No se pudieron generar reportes: {e}")

    log_weekly_kpis()

def log_weekly_kpis():
    try:
        kpis = db.get_bot_weekly_kpis(BOT_NAME)
    except Exception as exc:
        print(f"⚠️ No se pudieron calcular KPIs semanales: {exc}")
        return

    print(f"\n📈 KPIs semanales [{BOT_NAME.upper()}]:")
    total_trades = kpis.get("total_trades", 0)
    if total_trades == 0:
        print("   Sin trades en la última semana.")
        return

    win_rate = kpis.get("win_rate", 0.0)
    profit_factor = kpis.get("profit_factor", 0.0)
    profit_factor_str = "∞" if profit_factor == float("inf") else f"{profit_factor:.2f}"
    net_pnl = kpis.get("net_pnl", 0.0)
    avg_r_multiple = kpis.get("avg_r_multiple", 0.0)
    tp_sl_ratio = kpis.get("tp_sl_ratio", 0.0)
    if tp_sl_ratio == float("inf"):
        tp_sl_ratio_str = "∞"
    else:
        tp_sl_ratio_str = f"{tp_sl_ratio:.2f}"

    print(f"   Trades: {total_trades}")
    print(f"   Win Rate: {win_rate:.1f}%")
    print(f"   Profit Factor: {profit_factor_str}")
    print(f"   Retorno neto: ${net_pnl:.2f}")
    print(f"   Avg R múltiplo: {avg_r_multiple:.2f}")
    print(f"   Ratio TP/SL: {tp_sl_ratio_str}")

def main():
    print("🚀 Bot SCALPING + Auto Trading iniciado")
    print(f"📊 Monitoreando {len(WATCHLIST)} cryptos")
    print(f"⏰ Timeframes: {', '.join(TIMEFRAME_NAMES[t] for t in TIMEFRAMES)}")
    print(f"📊 Base de datos: {DB_PATH}")
    if AUTO_TRADE_ENABLED:
        print("🤖 TRADING AUTOMÁTICO ACTIVADO")
        print(f"⚡ Tipo de orden: {'MARKET' if USE_MARKET_ORDER else 'LIMIT'}")
        print(f"📈 Max posiciones simultáneas: {MAX_POSITIONS}")
        if trader:
            try:
                balance = trader.get_account_balance()
            except Exception:
                balance = 0.0
            print(f"💰 Balance: {balance:.2f} USDT")
            print(f"📊 Leverage: {trader.leverage}x")
            print(f"⚠️ Riesgo por trade: {trader.risk_percent}%")
    else:
        print("📢 MODO SOLO ALERTAS (trading desactivado)")

    minutes = max(1, int(SCAN_INTERVAL_SECONDS/60))
    print(f"\n🛡️ FILTROS {BOT_NAME.upper()} ACTIVOS:")
    print(f"   ✅ Volumen mínimo: {MIN_VOLUME_RATIO}x promedio")
    print(f"   ✅ RSI LONG: {RSI_LONG_MIN}-{RSI_LONG_MAX} | RSI SHORT: {RSI_SHORT_MIN}-{RSI_SHORT_MAX}")
    print(f"   ✅ Distancia EMAs: mín {MIN_EMA_DISTANCE*100:.2f}% | Slope mín {MIN_TREND_SLOPE*100:.2f}%")
    print(f"   ✅ SL máximo: {MAX_SL_PERCENT*100:.1f}% | ATR% [{MIN_ATR_PCT*100:.2f}-{MAX_ATR_PCT*100:.2f}]")
    print(f"   ✅ EMA200 requerida: {'Sí' if REQUIRE_EMA200_TREND else 'No'} | Score min {MIN_SCORE_TO_TRADE}")

    print(f"\n🔄 Escaneando cada {minutes} minutos...\n")

    trailing_summary = (TRAILING_MODE if TRAILING_MODE not in ("off", "none") else "OFF").upper()

    send_telegram(f"""⚡ <b>{BOT_NAME} iniciado</b>
📊 {len(WATCHLIST)} cryptos
⏰ TFs: {', '.join(TIMEFRAME_NAMES[t] for t in TIMEFRAMES)}
🔄 Escaneo cada {minutes} min
🛡️ Score mínimo {MIN_SCORE_TO_TRADE} | Alineación TF: {TIMEFRAME_ALIGNMENT} | Funding: {USE_FUNDING_BIAS}
 �️ Trailing SL: {trailing_summary} desde TP{TRAILING_FROM_TP}
�🗃️ DB: {DB_PATH}
📁 Reporte: reports/{REPORT_BASENAME}.png""")
    jitter_min, jitter_max = STARTUP_JITTER_RANGE
    if jitter_max < jitter_min:
        jitter_min, jitter_max = jitter_max, jitter_min
    jitter_delay = random.uniform(jitter_min, jitter_max)
    print(f"⏳ Jitter inicial: esperando {jitter_delay:.2f}s antes del primer escaneo")
    time.sleep(jitter_delay)
    while True:
        try:
            run_scan_once()
            time.sleep(SCAN_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\n⚠️ Bot detenido por el usuario")
            try:
                if auto_closer:
                    auto_closer.stop()
            except Exception:
                pass
            try:
                if trade_monitor:
                    trade_monitor.stop()
            except Exception:
                pass
            send_telegram(f"⚠️ {BOT_NAME} detenido")
            break
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
