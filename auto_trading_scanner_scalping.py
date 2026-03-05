"""
⚡ Scanner SCALPING — especializado en 5m a 1h
Señales rápidas con filtros moderados y SL ajustado para movimientos cortos.
"""
import os
import time
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from datetime import datetime, UTC
from dotenv import load_dotenv
import requests
from binance_futures_trader import BinanceFuturesTrader
from trading_database import TradingDatabase
from trading_dashboard import TradingDashboard, generate_quick_report
from risk_guard import RiskGuard
from risk_profiles import apply_risk_profile_defaults
from bot_watchlists import SCALPING_WATCHLIST

# ================== CONFIG ==================
load_dotenv()
RISK_PROFILE_SNAPSHOT = apply_risk_profile_defaults()
TOKEN   = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise ValueError("❌ Error: TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no están configurados en .env")

# Configuración de trading
AUTO_TRADE_ENABLED = os.getenv("AUTO_TRADE_ENABLED", "False").lower() == "true"
USE_MARKET_ORDER = os.getenv("USE_MARKET_ORDER", "False").lower() == "true"
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "3"))
BOT_NAME = "Scalping"

# Timeframes foco scalping
TIMEFRAMES = ["5m", "15m", "30m", "1h"]
TIMEFRAME_NAMES = {
    "5m": "5 minutos",
    "15m": "15 minutos",
    "30m": "30 minutos",
    "1h": "1 hora",
}

client = Client()

WATCHLIST = list(SCALPING_WATCHLIST)

# ===== PRESET SCALPING =====
ATR_PERIOD = 14
ATR_LEN = 14
SWING_LOOKBACK = 8
SL_ATR_MULT = 1.0
TP_ATR_MULT = 2.0
TP_MULTS = [1.0, 1.5, 2.0]

# Tendencia/EMAs
REQUIRE_EMA200_TREND = True
MIN_EMA_DISTANCE = 0.0025     # 0.25%
MIN_TREND_SLOPE = 0.0010      # más momentum

# Volumen y RSI
MIN_VOLUME_RATIO = 1.00
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
ADX_MIN = 13
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
MIN_SCORE_TO_TRADE = 3.2

# Gestión / Frecuencia
MAX_CONCURRENT_POS = 3
COOLDOWN_AFTER_TRADE_MIN = 8
MAX_TRADES_PER_DAY = 20
POSITION_SIZE_MULT = 0.8
LEVERAGE_CAP = 5
PYRAMIDING = False
PARTIALS = {"TP1": 1.272, "TP2": 1.414, "TP3": 1.618}

# Re-escanear cada 10 minutos
SCAN_INTERVAL_SECONDS = 900

# Gestión dinámica de Stop Loss (Scalping)
DYNAMIC_SL_ENABLED = os.getenv("SCALPING_DYNAMIC_SL_ENABLED", os.getenv("DYNAMIC_SL_ENABLED", "True")).lower() == "true"
BREAKEVEN_ON_TP1 = os.getenv("SCALPING_BREAKEVEN_ON_TP1", os.getenv("BREAKEVEN_ON_TP1", "True")).lower() == "true"
BREAKEVEN_OFFSET_PCT = float(os.getenv("SCALPING_BREAKEVEN_OFFSET_PCT", os.getenv("BREAKEVEN_OFFSET_PCT", "0.0")))
TRAILING_ATR_ENABLED = os.getenv("SCALPING_TRAILING_ATR_ENABLED", os.getenv("TRAILING_ATR_ENABLED", "True")).lower() == "true"
TRAILING_ATR_MULT = float(os.getenv("SCALPING_TRAILING_ATR_MULT", "0.8"))
TRAILING_ATR_TIMEFRAME = os.getenv("SCALPING_TRAILING_ATR_TIMEFRAME", "15m")
MIN_SL_MOVE_PERCENT = float(os.getenv("SCALPING_MIN_SL_MOVE_PERCENT", "0.0007"))
EARLY_PROFIT_TAKE_ENABLED = os.getenv("SCALPING_EARLY_PROFIT_TAKE_ENABLED", os.getenv("EARLY_PROFIT_TAKE_ENABLED", "True")).lower() == "true"
EARLY_PROFIT_TAKE_USDT = float(os.getenv("SCALPING_EARLY_PROFIT_TAKE_USDT", os.getenv("EARLY_PROFIT_TAKE_USDT", "8.0")))

# Límites de margen (USDT real invertido) por trade
MIN_MARGIN_USDT = float(os.getenv("SCALPING_MIN_MARGIN_USDT", os.getenv("MIN_MARGIN_USDT", "25.0")))
MAX_MARGIN_USDT = float(os.getenv("SCALPING_MAX_MARGIN_USDT", os.getenv("MAX_MARGIN_USDT", "50.0")))

# Estado runtime
_last_trade_time = {}
_daily_trade_count = {}
_trade_wallet_baseline = {}
_last_wallet_balance_snapshot = None

# Inicializar base de datos y trader
db = TradingDatabase("trading_history.db")
risk_guard = RiskGuard(db, BOT_NAME)
trader = None
if AUTO_TRADE_ENABLED:
    try:
        trader = BinanceFuturesTrader()
        print("✅ Trader de Binance Futures inicializado")
    except Exception as e:
        print(f"❌ Error al inicializar trader: {e}")
        print("⚠️ El bot funcionará solo en modo alerta (sin trading)")
        AUTO_TRADE_ENABLED = False

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ Error Telegram: {r.status_code} -> {r.text}")
    except Exception as e:
        print(f"[WARN] Telegram falló: {e}")

def get_wallet_balance_usdt():
    if not AUTO_TRADE_ENABLED or trader is None:
        return None
    try:
        account = trader.client.futures_account(recvWindow=60000)
        for asset in account.get('assets', []):
            if asset.get('asset') == 'USDT':
                return float(asset.get('walletBalance', 0))
    except Exception as e:
        print(f"⚠️ No se pudo leer walletBalance (Scalping): {e}")

    try:
        return float(trader.get_account_balance())
    except Exception:
        return None

def _to_millis(dt_value):
    if dt_value is None:
        return 0
    try:
        s = str(dt_value).strip()
        if not s:
            return 0
        parsed = datetime.fromisoformat(s.replace('Z', '+00:00'))
        return int(parsed.timestamp() * 1000)
    except Exception:
        return 0

def detect_close_reason_and_price(symbol: str, trade: dict):
    reason = "CLOSE"
    exit_price = 0.0

    if not AUTO_TRADE_ENABLED or trader is None:
        return reason, exit_price

    try:
        entry_ms = _to_millis(trade.get('entry_time'))
        orders = trader.client.futures_get_all_orders(symbol=symbol, limit=120)
        close_candidates = []

        for order in orders:
            if order.get('status') != 'FILLED':
                continue

            order_type = str(order.get('type', ''))
            if order_type not in ['STOP_MARKET', 'STOP', 'TAKE_PROFIT_MARKET', 'TAKE_PROFIT', 'MARKET']:
                continue

            update_ms = int(order.get('updateTime') or order.get('time') or 0)
            if entry_ms and update_ms and update_ms < entry_ms:
                continue

            if order_type == 'MARKET':
                reduce_only = str(order.get('reduceOnly', '')).lower() == 'true'
                close_position = str(order.get('closePosition', '')).lower() == 'true'
                if not reduce_only and not close_position:
                    continue

            close_candidates.append(order)

        if close_candidates:
            last_order = max(close_candidates, key=lambda x: int(x.get('updateTime') or x.get('time') or 0))
            order_type = str(last_order.get('type', ''))

            if 'TAKE_PROFIT' in order_type:
                reason = 'TP'
            elif 'STOP' in order_type:
                reason = 'SL'
            else:
                reason = 'CLOSE'

            # Calcular precio de salida promedio ponderado por cantidad
            total_qty = 0.0
            weighted_price = 0.0
            for c in close_candidates:
                avg_p = float(c.get('avgPrice') or 0)
                exec_qty = float(c.get('executedQty') or 0)
                if avg_p > 0 and exec_qty > 0:
                    weighted_price += avg_p * exec_qty
                    total_qty += exec_qty
            
            if total_qty > 0 and weighted_price > 0:
                exit_price = weighted_price / total_qty
            else:
                exit_price = float(last_order.get('avgPrice') or 0)
                if exit_price <= 0:
                    exit_price = float(last_order.get('stopPrice') or last_order.get('price') or 0)
    except Exception as e:
        print(f"⚠️ No se pudo detectar motivo de cierre (Scalping) en {symbol}: {e}")

    return reason, exit_price

def send_close_summary_telegram(trade: dict, close_reason: str, exit_price: float, wallet_before, wallet_after):
    symbol = trade.get('symbol', '')
    side = trade.get('side', '')
    entry_price = float(trade.get('entry_price') or 0)
    quantity = float(trade.get('quantity') or 0)
    leverage = int(trade.get('leverage') or 1)

    notional = entry_price * quantity
    margin_used = notional / leverage if leverage > 0 else notional

    if side == 'LONG':
        pnl = (exit_price - entry_price) * quantity
    else:
        pnl = (entry_price - exit_price) * quantity

    pnl_pct = ((pnl / margin_used) * 100) if margin_used > 0 else 0.0
    wallet_delta = None
    if wallet_before is not None and wallet_after is not None:
        wallet_delta = float(wallet_after) - float(wallet_before)

    reason_emoji = '🟢 TP' if close_reason == 'TP' else ('🔴 SL' if close_reason == 'SL' else '⚪ CIERRE')
    result_emoji = '📈' if pnl >= 0 else '📉'

    message = (
        f"✅ <b>OPERACIÓN CERRADA</b>\n"
        f"🤖 Bot: <b>{BOT_NAME}</b>\n"
        f"📌 Par: {display_symbol(symbol)} {side}\n"
        f"🏁 Motivo: <b>{reason_emoji}</b>\n\n"
        f"💵 Invertido (margen): {margin_used:.2f} USDT\n"
        f"📦 Notional: {notional:.2f} USDT (x{leverage})\n"
        f"🎯 Entrada: {entry_price:.6f}\n"
        f"🚪 Salida: {exit_price:.6f}\n\n"
        f"{result_emoji} Resultado: <b>{pnl:+.2f} USDT</b> ({pnl_pct:+.2f}%)\n"
    )

    if wallet_before is not None:
        message += f"💰 Wallet anterior: {float(wallet_before):.2f} USDT\n"
    if wallet_after is not None:
        message += f"🏦 Wallet final: {float(wallet_after):.2f} USDT\n"
    if wallet_delta is not None:
        message += f"📊 Cambio wallet: <b>{wallet_delta:+.2f} USDT</b>\n"

    send_telegram(message)

def reconcile_closed_trades_and_notify():
    global _last_wallet_balance_snapshot

    if not AUTO_TRADE_ENABLED or trader is None:
        return

    try:
        positions = trader.get_open_positions()
        open_symbols = {p['symbol'] for p in positions}

        open_trades = [
            t for t in db.get_open_trades()
            if str(t.get('bot') or '').lower() == BOT_NAME.lower()
        ]

        for trade in open_trades:
            symbol = trade.get('symbol')
            if symbol in open_symbols:
                continue

            trade_id = int(trade.get('id'))
            close_reason, exit_price = detect_close_reason_and_price(symbol, trade)

            if exit_price <= 0:
                try:
                    ticker = client.get_symbol_ticker(symbol=symbol)
                    exit_price = float(ticker['price'])
                except Exception:
                    exit_price = float(trade.get('entry_price') or 0)

            db_exit_reason = 'TAKE_PROFIT' if close_reason == 'TP' else ('STOP_LOSS' if close_reason == 'SL' else 'SYNC_CLOSE')
            db.close_trade(trade_id, exit_price=exit_price, exit_reason=db_exit_reason)

            wallet_before = _trade_wallet_baseline.pop(trade_id, None)
            if wallet_before is None:
                wallet_before = _last_wallet_balance_snapshot
            wallet_after = get_wallet_balance_usdt()

            send_close_summary_telegram(
                trade=trade,
                close_reason=close_reason,
                exit_price=exit_price,
                wallet_before=wallet_before,
                wallet_after=wallet_after,
            )

            if wallet_after is not None:
                _last_wallet_balance_snapshot = wallet_after
    except Exception as e:
        print(f"⚠️ Error reconciliando cierres Scalping: {e}")

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
    status = "🚀 <b>TRADE EJECUTADO</b>" if traded else "📣 <b>SEÑAL DETECTADA</b>"
    entry_str = f"{fmt.format(levels['entry_high'])} - {fmt.format(levels['entry_low'])}"
    tp_lines = "\n".join([f"🟢 TP{i+1}: {fmt.format(t)}" if side == "LONG"
                          else f"🔻 TP{i+1}: {fmt.format(t)}"
                          for i, t in enumerate(levels['tp_prices'])])
    message = f"""{status}
🤖 Bot: <b>{BOT_NAME}</b>
📌 Par: <b>{sy}</b> {'🟢 LONG' if side=='LONG' else '🔴 SHORT'}
⏰ Timeframe: {tf_name}

📍 Zona entrada: {entry_str}
🔴 SL: {fmt.format(levels['sl_price'])}
{tp_lines}

💰 Precio actual: {fmt.format(levels['price'])}
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
        tps = [price + TP_ATR_MULT * atr * m for m in [0.6, 0.8, 1.0]]
    else:
        sl = recent_highs + SL_ATR_MULT * atr
        tps = [price - TP_ATR_MULT * atr * m for m in [0.6, 0.8, 1.0]]

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
        wallet_before_trade = get_wallet_balance_usdt()

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

        can_trade, reason = risk_guard.can_open_trade(symbol=symbol)
        if not can_trade:
            print(f"🛑 RiskGuard bloqueó trade en {symbol}: {reason}")
            return False

        open_positions = trader.get_open_positions()
        for pos in open_positions:
            if pos['symbol'] == symbol:
                print(f"⚠️ Ya existe una posición abierta en {symbol}, omitiendo...")
                return False
        if len(open_positions) >= MAX_POSITIONS:
            print(f"⚠️ Máximo de posiciones alcanzado ({MAX_POSITIONS}), omitiendo...")
            return False
        result = trader.open_position(
            symbol=symbol,
            side=side,
            entry_price=levels['entry_price'],
            sl_price=levels['sl_price'],
            tp_prices=levels['tp_prices'],
            force_market=USE_MARKET_ORDER,
            min_margin_usdt=MIN_MARGIN_USDT,
            max_margin_usdt=MAX_MARGIN_USDT,
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
                bot=BOT_NAME
            )
            # Guardar wallet baseline ANTES de registrar órdenes
            _last_trade_time[key] = now
            _daily_trade_count[day] = cnt + 1
            if wallet_before_trade is not None:
                _trade_wallet_baseline[int(trade_id)] = float(wallet_before_trade)
            try:
                db.add_order(
                    trade_id=trade_id,
                    order_id=str(result['entry_order'].get('orderId', 'N/A')),
                    order_type="ENTRY",
                    side=result['entry_order'].get('side', side),
                    symbol=symbol,
                    price=result['entry_price'],
                    quantity=result['quantity'],
                    status="FILLED"
                )
                if result.get('sl_order'):
                    db.add_order(
                        trade_id=trade_id,
                        order_id=str(result['sl_order'].get('orderId', 'N/A')),
                        order_type="STOP_LOSS",
                        side=result['sl_order'].get('side', 'SELL' if side == 'LONG' else 'BUY'),
                        symbol=symbol,
                        price=result['sl_price'],
                        quantity=result['quantity'],
                        status="NEW"
                    )
                for i, tp_order in enumerate(result['tp_orders'], 1):
                    db.add_order(
                        trade_id=trade_id,
                        order_id=str(tp_order.get('orderId', 'N/A')),
                        order_type=f"TAKE_PROFIT_{i}",
                        side=tp_order.get('side', 'SELL' if side == 'LONG' else 'BUY'),
                        symbol=symbol,
                        price=tp_order.get('stopPrice', tp_order.get('price', 0)),
                        quantity=tp_order.get('origQty', result['quantity']),
                        status="NEW"
                    )
            except Exception as e:
                print(f"⚠️ Error al registrar órdenes individuales en DB (Scalping): {e}")
            return True
    except Exception as e:
        print(f"❌ Error en execute_trade: {e}")
    return False

def run_scan_once():
    print("\n" + "="*60)
    print("🛡️ ESCANEO SCALPING")
    print(f"🔍 {len(WATCHLIST)} cryptos en {len(TIMEFRAMES)} timeframes")
    print(datetime.now(UTC).strftime("📅 %Y-%m-%d %H:%M:%S"))
    runtime_auto_trade = AUTO_TRADE_ENABLED and (trader is not None)
    print("🤖 TRADING AUTOMÁTICO ACTIVADO" if runtime_auto_trade else "📢 SOLO ALERTAS")
    print("="*60)

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
                if not filt.get("passed"):
                    continue
                levels = build_levels(side, last, df, symbol, timeframe)
                per_symbol_details.append(f"[{timeframe}] {side} | Precio: {levels['entry_price']}")
                msg = format_trade_message(symbol, side, levels, timeframe, traded=False)
                send_telegram(msg)
                if AUTO_TRADE_ENABLED and trader is not None:
                    traded = execute_trade(symbol, side, levels, timeframe)
                    if traded:
                        send_telegram(format_trade_message(symbol, side, levels, timeframe, traded=True))
                time.sleep(0.05)
            if per_symbol_details:
                print(f"   {display_symbol(symbol)}: Señales")
                for line in per_symbol_details:
                    print(f"      - {line}")
            else:
                print(f"   {display_symbol(symbol)}: Sin señales aprobadas")
        except Exception as e:
            print(f"⚠️ Error analizando {symbol}: {e}")

    # Reportes consolidado
    try:
        print("\n📈 Estadísticas rápidas:")
        generate_quick_report("trading_history.db", bot="Scalping")
        dashboard = TradingDashboard("trading_history.db")
        dashboard.generate_consolidated_report(output_dir="reports", filename_base="trading_report_all")
        print("✅ Reportes actualizados en reports/")
    except Exception as e:
        print(f"⚠️ No se pudieron generar reportes: {e}")

def manage_dynamic_stop_losses():
    """Mueve SL de scalping a breakeven y/o trailing ATR sin empeorar riesgo."""
    if not AUTO_TRADE_ENABLED or trader is None or not DYNAMIC_SL_ENABLED:
        return

    try:
        positions = trader.get_open_positions()
        if not positions:
            return

        open_trades = [
            t for t in db.get_open_trades()
            if str(t.get('bot') or '').lower() == BOT_NAME.lower()
        ]
        trade_by_symbol = {t['symbol']: t for t in open_trades}

        for pos in positions:
            symbol = pos['symbol']
            side = pos['side']
            qty = float(pos.get('quantity', 0))
            entry = float(pos['entryPrice'])
            upnl = float(pos.get('unrealizedProfit', 0))

            current_sl = pos.get('stopLoss')
            trade = trade_by_symbol.get(symbol)
            if not trade:
                continue

            ticker = client.get_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])

            if EARLY_PROFIT_TAKE_ENABLED and upnl >= EARLY_PROFIT_TAKE_USDT:
                print(f"💰 Cierre temprano (Scalping) {symbol}: uPnL={upnl:+.2f} USDT >= {EARLY_PROFIT_TAKE_USDT:.2f}")
                closed = trader.close_position(symbol)
                if closed:
                    try:
                        trader.cancel_all_orders(symbol)
                    except Exception:
                        pass
                    try:
                        trade_id = trade.get('id')
                        if trade_id is not None:
                            db.close_trade(int(trade_id), exit_price=current_price, exit_reason="EARLY_TP_UPNL")
                    except Exception as e:
                        print(f"⚠️ No se pudo cerrar trade en DB para {symbol}: {e}")
                    send_telegram(
                        f"💰 <b>CIERRE TEMPRANO</b>\n"
                        f"🤖 Bot: <b>{BOT_NAME}</b>\n"
                        f"📌 Par: {display_symbol(symbol)} {side}\n"
                        f"📈 PnL: <b>{upnl:+.2f} USDT</b>\n"
                        f"🚪 Precio salida: {current_price:.6f}"
                    )
                continue

            # Reponer protecciones si faltan en exchange
            if (current_sl is None or len(pos.get('takeProfits') or []) == 0) and trader.reconciler is not None:
                try:
                    tp_prices = trade.get('tp_prices') or []
                    sl_db = float(trade.get('sl_price')) if trade.get('sl_price') is not None else None
                    if sl_db is not None and len(tp_prices) > 0 and qty > 0:
                        sl_order, tp_orders = trader.reconciler.ensure_orders_exist(
                            symbol=symbol,
                            side=side,
                            quantity=qty,
                            sl_price=sl_db,
                            tp_prices=tp_prices,
                            max_retries=2,
                        )
                        if sl_order or tp_orders:
                            print(f"🛡️ Reconciliación de salida (Scalping) {symbol}: SL={bool(sl_order)} TPs={len(tp_orders)}")
                except Exception as e:
                    print(f"⚠️ No se pudieron reponer SL/TP en {symbol}: {e}")

            current_sl = pos.get('stopLoss')
            if current_sl is None:
                continue
            current_sl = float(current_sl)

            candidates = []

            if BREAKEVEN_ON_TP1:
                tp_prices = trade.get('tp_prices') or []
                tp1 = float(tp_prices[0]) if tp_prices else None
                if tp1:
                    if side == "LONG" and current_price >= tp1:
                        be_sl = entry * (1 + BREAKEVEN_OFFSET_PCT / 100.0)
                        candidates.append(be_sl)
                    elif side == "SHORT" and current_price <= tp1:
                        be_sl = entry * (1 - BREAKEVEN_OFFSET_PCT / 100.0)
                        candidates.append(be_sl)

            if TRAILING_ATR_ENABLED:
                tf = TRAILING_ATR_TIMEFRAME or (trade.get('timeframe') or '15m')
                df = get_klines(symbol, tf, limit=max(ATR_PERIOD + 30, 120))
                if df is not None and not df.empty and len(df) > ATR_PERIOD + 2:
                    atr_series = ta.atr(df["high"], df["low"], df["close"], length=ATR_PERIOD)
                    atr = float(atr_series.iloc[-1])
                    if atr > 0:
                        if side == "LONG":
                            trail_sl = current_price - (TRAILING_ATR_MULT * atr)
                        else:
                            trail_sl = current_price + (TRAILING_ATR_MULT * atr)
                        candidates.append(trail_sl)

            if not candidates:
                continue

            if side == "LONG":
                target_sl = max([current_sl] + candidates)
                better = target_sl > current_sl
                valid_side = target_sl < current_price
            else:
                target_sl = min([current_sl] + candidates)
                better = target_sl < current_sl
                valid_side = target_sl > current_price

            if not better or not valid_side:
                continue

            move_pct = abs(target_sl - current_sl) / entry if entry > 0 else 0.0
            if move_pct < MIN_SL_MOVE_PERCENT:
                continue

            updated = trader.update_stop_loss(symbol=symbol, side=side, new_sl_price=target_sl)
            if updated:
                print(f"🛡️ SL dinámico (Scalping) {symbol}: {current_sl:.6f} -> {target_sl:.6f}")

    except Exception as e:
        print(f"⚠️ Error en gestión dinámica de SL (Scalping): {e}")

def main():
    print("🤖 Bot SCALPING iniciado")
    print(f"⏰ Timeframes: {', '.join(TIMEFRAME_NAMES[t] for t in TIMEFRAMES)}")
    print("📊 Base de datos: trading_history.db")
    print(f"🛡️ Risk Profile: {RISK_PROFILE_SNAPSHOT['RISK_PROFILE_SELECTED']} ({RISK_PROFILE_SNAPSHOT['RISK_ENV_MODE']})")
    print(f"   • MAX_DAILY_LOSS_USDT={RISK_PROFILE_SNAPSHOT['MAX_DAILY_LOSS_USDT']} | MAX_CONSECUTIVE_LOSSES={RISK_PROFILE_SNAPSHOT['MAX_CONSECUTIVE_LOSSES']}")
    print(f"   • MAX_DRAWDOWN_PCT={RISK_PROFILE_SNAPSHOT['MAX_DRAWDOWN_PCT']} | PAUSE_MIN={RISK_PROFILE_SNAPSHOT['RISK_GUARD_PAUSE_MINUTES']}")
    print(f"   • SL dinámico: {'ON' if DYNAMIC_SL_ENABLED else 'OFF'} | Breakeven TP1: {'ON' if BREAKEVEN_ON_TP1 else 'OFF'} | Trail ATR: {'ON' if TRAILING_ATR_ENABLED else 'OFF'} ({TRAILING_ATR_MULT}x)")
    print(f"   • Cierre temprano por PnL: {'ON' if EARLY_PROFIT_TAKE_ENABLED else 'OFF'} | Umbral: {EARLY_PROFIT_TAKE_USDT:.2f} USDT")
    if AUTO_TRADE_ENABLED and trader is not None:
        print("🤖 TRADING AUTOMÁTICO ACTIVADO")
        print(f"⚡ Tipo de orden: {'MARKET' if USE_MARKET_ORDER else 'LIMIT'}")
        print(f"📈 Max posiciones simultáneas: {MAX_POSITIONS}")
    else:
        print("📢 MODO SOLO ALERTAS (trading desactivado)")
    print("🔄 Escaneando cada 15 minutos...\n")

    tf_list = ", ".join(TIMEFRAME_NAMES[t] for t in TIMEFRAMES)
    mode = "🤖 TRADING AUTOMÁTICO" if AUTO_TRADE_ENABLED and trader is not None else "📢 SOLO ALERTAS"
    send_telegram(
        f"🚀 <b>BOT INICIADO</b>\n"
        f"🤖 Bot: <b>{BOT_NAME}</b>\n"
        f"{mode}\n"
        f"📊 Activos: {len(WATCHLIST)}\n"
        f"⏰ Timeframes: {tf_list}\n"
        f"🔄 Escaneo: cada {int(SCAN_INTERVAL_SECONDS/60)} min"
    )

    while True:
        try:
            manage_dynamic_stop_losses()
            reconcile_closed_trades_and_notify()
            run_scan_once()
            manage_dynamic_stop_losses()
            reconcile_closed_trades_and_notify()
            time.sleep(SCAN_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\n⚠️ Bot detenido por el usuario")
            send_telegram(
                f"⚠️ <b>BOT DETENIDO</b>\n"
                f"🤖 Bot: <b>{BOT_NAME}</b>\n"
                f"🛑 Detenido por usuario"
            )
            break
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            send_telegram(
                f"❌ <b>BOT ERROR</b>\n"
                f"🤖 Bot: <b>{BOT_NAME}</b>\n"
                f"⚠️ Detalle: {e}"
            )
            time.sleep(5)

if __name__ == "__main__":
    main()
