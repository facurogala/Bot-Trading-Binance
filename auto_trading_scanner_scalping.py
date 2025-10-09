"""
⚡ Scanner SCALPING — especializado en 5m a 1h
Señales rápidas con filtros moderados y SL ajustado para movimientos cortos.
"""
import os
import time
from collections import Counter
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from datetime import datetime
from dotenv import load_dotenv
import requests
from binance_futures_trader import BinanceFuturesTrader
from trading_database import TradingDatabase
from trading_dashboard import TradingDashboard, generate_quick_report
from auto_closer import AutoCloser

# ================== CONFIG ==================
load_dotenv()

BOT_NAME = "Scalping"
MESSAGE_PREFIX = "[SCALP]"
REPORT_BASENAME = "trading_report_scalp"
BOT_ID = os.getenv("BOT_ID_SCALPING") or f"SCALP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{os.getpid()}"

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

# Re-escanear cada 10 minutos
SCAN_INTERVAL_SECONDS = 900

# Estado runtime
_last_trade_time = {}
_daily_trade_count = {}

# Inicializar base de datos y trader
db = TradingDatabase("trading_history.db")
trader = None
auto_closer = None
if AUTO_TRADE_ENABLED:
    try:
        trader = BinanceFuturesTrader()
        print("✅ Trader de Binance Futures inicializado")
        try:
            auto_closer = AutoCloser(trader, db, bot_name="Scalping")
            auto_closer.start()
        except Exception as e:
            print(f"⚠️ AutoCloser no pudo iniciar: {e}")
    except Exception as e:
        print(f"❌ Error al inicializar trader: {e}")
        print("⚠️ El bot funcionará solo en modo alerta (sin trading)")
        AUTO_TRADE_ENABLED = False

def send_telegram(message: str):
    if not message.startswith(MESSAGE_PREFIX):
        message = f"{MESSAGE_PREFIX} {message}"
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            print("✅ Mensaje enviado a Telegram")
        else:
            print(f"⚠️ Error Telegram: {r.status_code} -> {r.text}")
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

def format_trade_message(symbol: str, side: str, levels: dict, timeframe: str, traded: bool = False):
    sy = display_symbol(symbol)
    tf_name = TIMEFRAME_NAMES.get(timeframe, timeframe)
    dec = levels['decimals']
    fmt = f"{{:.{dec}f}}"
    status = f"{MESSAGE_PREFIX} 🤖 <b>TRADE EJECUTADO</b>" if traded else f"{MESSAGE_PREFIX} 🚨 <b>SEÑAL DETECTADA</b>"
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
        tps = [price + TP_ATR_MULT * atr * m for m in [1.0, 0.8, 0.6]]
    else:
        sl = recent_highs + SL_ATR_MULT * atr
        tps = [price - TP_ATR_MULT * atr * m for m in [1.0, 0.8, 0.6]]

    return {
        'entry_price': price,
        'entry_high': entry_high,
        'entry_low': entry_low,
        'sl_price': sl,
        'tp_prices': tps,
        'vol_ratio': vol_ratio,
        'price': price,
        'decimals': dec,
        'atr': atr
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

        day = datetime.utcnow().strftime("%Y-%m-%d")
        day_stats = _daily_trade_count.get(day, {"detected": 0, "executed": 0})
        if day_stats.get("executed", 0) >= MAX_TRADES_PER_DAY:
            print(f"⛔ Límite diario de trades alcanzado ({MAX_TRADES_PER_DAY})")
            return False

        open_positions = trader.get_open_positions()
        for pos in open_positions:
            if pos['symbol'] == symbol:
                print(f"⚠️ Ya existe una posición abierta en {symbol}, omitiendo...")
                return False
        max_conc = min(MAX_CONCURRENT_POS, MAX_POSITIONS)
        if len(open_positions) >= max_conc:
            print(f"⚠️ Máximo de posiciones alcanzado ({max_conc}), omitiendo...")
            return False
        result = trader.open_position(
            symbol=symbol,
            side=side,
            entry_price=levels['entry_price'],
            sl_price=levels['sl_price'],
            tp_prices=levels['tp_prices'],
            force_market=USE_MARKET_ORDER
        )
        if result:
            trade_id = db.add_trade(
                symbol=symbol,
                side=side,
                entry_price=result['entry_price'],
                quantity=result['quantity'],
                leverage=result['leverage'],
                sl_price=result['sl_price'],
                tp_prices=result['tp_prices'],
                timeframe=timeframe,
                notes=f"Señal Scalping - {timeframe}",
                bot="Scalping",
                bot_id=BOT_ID,
                entry_order_id=result.get('entry_order_id'),
                entry_client_order_id=result.get('entry_client_order_id'),
                position_id=result.get('position_id'),
                margin_balance_entry=result.get('margin_before'),
                margin_balance_post_entry=result.get('margin_after'),
                margin_used=result.get('margin_used'),
                isolated_margin=result.get('isolated_margin')
            )
            entry_price_record = result['entry_order'].get('avgPrice', result['entry_price']) if isinstance(result.get('entry_order'), dict) else result['entry_price']
            try:
                entry_price_record = float(entry_price_record)
            except Exception:
                entry_price_record = result['entry_price']
            db.add_order(
                trade_id=trade_id,
                order_id=str(result['entry_order']['orderId']),
                order_type="ENTRY",
                side=result['entry_order']['side'],
                symbol=symbol,
                price=entry_price_record,
                quantity=result['quantity'],
                status=result['entry_order'].get('status', 'FILLED'),
                client_order_id=result['entry_order'].get('clientOrderId'),
                position_id=result.get('position_id')
            )
            if result.get('sl_order'):
                db.add_order(
                    trade_id=trade_id,
                    order_id=str(result['sl_order']['orderId']),
                    order_type="STOP_LOSS",
                    side=result['sl_order']['side'],
                    symbol=symbol,
                    price=result['sl_price'],
                    quantity=result['quantity'],
                    status="NEW",
                    client_order_id=result['sl_order'].get('clientOrderId'),
                    position_id=result.get('position_id')
                )
            for i, tp_order in enumerate(result['tp_orders'], 1):
                tp_price = tp_order.get('stopPrice') or tp_order.get('price') or (result['tp_prices'][i-1] if i-1 < len(result['tp_prices']) else None)
                db.add_order(
                    trade_id=trade_id,
                    order_id=str(tp_order['orderId']),
                    order_type=f"TAKE_PROFIT_{i}",
                    side=tp_order['side'],
                    symbol=symbol,
                    price=tp_price,
                    quantity=result['quantity'],
                    status=tp_order.get('status', 'NEW'),
                    client_order_id=tp_order.get('clientOrderId'),
                    position_id=result.get('position_id')
                )
            day_stats["executed"] = day_stats.get("executed", 0) + 1
            _daily_trade_count[day] = day_stats
            _last_trade_time[key] = now
            return True
    except Exception as e:
        print(f"❌ Error en execute_trade: {e}")
    return False

def run_scan_once():
    print("\n" + "="*60)
    print("⚡ ESCANEO SCALPING")
    print(f"🔍 {len(WATCHLIST)} cryptos en {len(TIMEFRAMES)} timeframes")
    print(datetime.utcnow().strftime("📅 %Y-%m-%d %H:%M:%S"))
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

    summary = {"detected": 0, "rejected": 0, "executed": 0}
    rejection_reasons: Counter[str] = Counter()

    day = datetime.utcnow().strftime("%Y-%m-%d")
    day_stats = _daily_trade_count.get(day, {"detected": 0, "executed": 0})

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
                msg = format_trade_message(symbol, side, levels, timeframe, traded=False)
                send_telegram(msg)
                # Contabilizar señal aprobada
                try:
                    db.increment_bot_activity(bot="Scalping", approved_delta=1)
                except Exception:
                    pass
                if AUTO_TRADE_ENABLED and trader is not None:
                    traded = execute_trade(symbol, side, levels, timeframe)
                    if traded:
                        try:
                            db.increment_bot_activity(bot="Scalping", executed_delta=1)
                        except Exception:
                            pass
                        send_telegram(format_trade_message(symbol, side, levels, timeframe, traded=True))
                        summary["executed"] += 1
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

    print("\n📊 Resumen [SCALP]:")
    print(f"   Señales detectadas: {summary['detected']}")
    print(f"   Señales rechazadas: {summary['rejected']}")
    if rejection_reasons:
        print("   Principales rechazos:")
        for reason, count in rejection_reasons.most_common(2):
            print(f"      - {reason} ({count})")
    print(f"   Trades ejecutados: {summary['executed']}")

    # Reportes consolidado
    try:
        print("\n" + "="*60)
        print("� GENERANDO REPORTES AUTOMÁTICOS...")
        print("="*60)
        print("\n📈 ESTADÍSTICAS RÁPIDAS:")
        generate_quick_report("trading_history.db", bot="Scalping")
        dashboard = TradingDashboard("trading_history.db")
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

    print("\n📈 KPIs semanales [SCALP]:")
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
    print("📊 Base de datos: trading_history.db")
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
    print(f"\n🛡️ FILTROS SCALPING ACTIVOS:")
    print(f"   ✅ Volumen mínimo: {MIN_VOLUME_RATIO}x promedio")
    print(f"   ✅ RSI LONG: {RSI_LONG_MIN}-{RSI_LONG_MAX}")
    print(f"   ✅ RSI SHORT: {RSI_SHORT_MIN}-{RSI_SHORT_MAX}")
    print(f"   ✅ Distancia EMAs: mín {MIN_EMA_DISTANCE*100:.2f}%")
    print(f"   ✅ SL máximo: {MAX_SL_PERCENT*100:.1f}%")
    print(f"   ✅ Tendencia EMA200: {'Requerida' if REQUIRE_EMA200_TREND else 'No requerida'}")

    print(f"\n🔄 Escaneando cada {minutes} minutos...\n")
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
            break
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
