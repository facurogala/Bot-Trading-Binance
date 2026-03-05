"""
🤖 Scanner Haack — Estilo híbrido (moderado) para Binance Futures

Objetivo: señales diarias moderadas, alta calidad, riesgo moderado/bajo,
TPs cercanos/moderados y máximo 6 posiciones simultáneas.

Requisitos de entorno (.env):
  - BINANCE_API_KEY, BINANCE_API_SECRET
  - TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
  - TESTNET=True/False, AUTO_TRADE_ENABLED=True/False
  - USE_MARKET_ORDER=True/False, LEVERAGE, RISK_PERCENT, MAX_POSITIONS
"""

import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from functools import lru_cache

import pandas as pd
import pandas_ta as ta
import requests
from binance.client import Client
from dotenv import load_dotenv

from binance_futures_trader import BinanceFuturesTrader
from trading_database import TradingDatabase
from trading_dashboard import generate_quick_report, TradingDashboard
from risk_guard import RiskGuard
from risk_profiles import apply_risk_profile_defaults
from bot_watchlists import HAACK_WATCHLIST


# ================== CONFIG ==================
load_dotenv()
RISK_PROFILE_SNAPSHOT = apply_risk_profile_defaults()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise ValueError("❌ Error: TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no están configurados en .env")

# Modo trading
AUTO_TRADE_ENABLED = os.getenv("AUTO_TRADE_ENABLED", "False").lower() == "true"
USE_MARKET_ORDER = os.getenv("USE_MARKET_ORDER", "False").lower() == "true"
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "6"))  # Haack: hasta 6 posiciones
BOT_NAME = "Haack"

# Timeframes generales (enfoque más lento)
TIMEFRAMES = ["4h", "12h", "1d"]
TIMEFRAME_NAMES = {
    "4h": "4 horas",
    "12h": "12 horas",
    "1d": "1 día",
}

# Cliente binance solo para klines
client = Client()

# 70 coins — cobertura amplia en Futures (moderado)
WATCHLIST: List[str] = list(HAACK_WATCHLIST)

# ====== Preset de calidad: HAACK (medio) ======
# Riesgo y niveles (equilibrado)
ATR_PERIOD = 14           # <- Usaremos solo este
ATR_LEN = ATR_PERIOD      # unificar ATR
SWING_LOOKBACK = 10
SL_ATR_MULT = 1.2         # SL = precio ± 1.2 * ATR
TP_MULTS = [1.0, 1.6, 2.2]  # TPs cercanos/moderados
TP_ATR_MULT = 2.4         # fallback si TP_MULTS = None

# Tendencia/EMAs
REQUIRE_EMA200_TREND = True
MIN_EMA_DISTANCE = 0.003      # 0.30%
MIN_TREND_SLOPE = 0.0008      # pendiente relativa de EMA20 (en 10 velas)

# Volumen
MIN_VOLUME_RATIO = 0.80

# RSI
RSI_LONG_MIN, RSI_LONG_MAX = 40, 70
RSI_SHORT_MIN, RSI_SHORT_MAX = 30, 60

# Stop/TP / Volatilidad
MAX_SL_PERCENT = 0.080        # 3.5%
MIN_ATR_PCT = 0.0015           # 0.4%
MAX_ATR_PCT = 0.080           # 3.0%

# Fibonacci y Confluencias
USE_FIB = True
FIB_LOOKBACK_SWING = 120
FIB_MIN_SWING_RANGE = 0.010
FIB_RETRACEMENTS = [0.382, 0.5, 0.618]
FIB_EXTENSIONS = [1.272, 1.414, 1.618]
FIB_PROXIMITY_TOL = 0.0015
CONFLUENCE_WITH_EMA = True
CONFLUENCE_MAX_DIST_TO_EMA = 0.0020
CONFLUENCE_WITH_SR = True
SR_LOOKBACK = 300
SR_PROXIMITY_TOL = 0.0015
REQUIRE_WICK_REJECTION = True
REQUIRE_CLOSE_IN_DIRECTION = True

# Estructura / Momentum
STRUCT_REQUIRE_HH_HL = True
STRUCT_SWING_DEPTH = 3
ADX_FILTER = True
ADX_MIN = 14
MIN_BODY_TO_RANGE = 0.5
MAX_UPWICK_FOR_LONG = 0.4
MAX_DOWNWICK_FOR_SHORT = 0.4

# Timing y confirmaciones
TIMEFRAME_ALIGNMENT = True
ALIGN_WITH = ["12h"]
MIN_TICKS_SINCE_SIGNAL = 2
BLOCK_NEWS_SPIKES = True
ALLOW_SESSION = ["UTC_10_24"]
ALLOW_CONTINUATION_SIGNALS = True

# Perps/Funding
USE_FUNDING_BIAS = True
MAX_POSITIVE_FUNDING = 0.05   # %
MIN_NEGATIVE_FUNDING = -0.05  # %

# ====== Ichimoku (según artículo) ======
USE_ICHI = True
ICHI_TENKAN = 9
ICHI_KIJUN = 26
ICHI_SENKOUB = 52
ICHI_BLOCK_IN_KUMO = True            # no operar dentro de la nube
ICHI_REQUIRE_TREND = True            # precio a favor respecto del Kumo
ICHI_USE_CHIKOU_FILTER = True        # Chikou confirma
ICHI_MIN_SIGNAL_STRENGTH = "medium"  # "weak" | "medium" | "strong"
ICHI_STOP_MODE = "kijun"             # "kijun" | "ssb" | "atr"

# ====== Híbrido EMA + Ichimoku (gates + score) ======
USE_HYBRID = True

# Filtros (gates)
GATE_BLOCK_IN_KUMO = True
GATE_REQUIRE_EMA200_TREND = True
GATE_REQUIRE_ICHI_TREND = True
GATE_CHIKOU_CONFIRM = True
GATE_MIN_EMA_DIST = MIN_EMA_DISTANCE             # 0.30%
GATE_ATR_RANGE = (MIN_ATR_PCT, MAX_ATR_PCT)

# Scoring (ponderaciones)
SCORE_W = {
    "trend_ema200": 2.2,
    "kumo_trend": 2.0,
    "tenkan_kijun_cross": 1.8,
    "tk_strength": 1.2,          # fuerte/medio/débil
    "ema20_50_cross": 2.2,       # cruces EMA más relevantes
    "ema_distance": 1.0,
    "rsi_zone": 1.0,
    "volume_ratio": 1.2,
    "atr_in_range": 1.0,
    "adx": 1.0,
    "fib_confluence": 1.5,
    "sr_confluence": 0.8,
    "multi_tf_alignment": 1.0,
    "impulse": 2.0,              # bonus por vela de impulso (H1/H4)
}
MIN_SCORE_TO_TRADE = 4.8  # modo más activo

# Gestión / Frecuencia
MAX_CONCURRENT_POS = 3
COOLDOWN_AFTER_TRADE_MIN = 15
MAX_TRADES_PER_DAY = 10
POSITION_SIZE_MULT = 1.0  # Nota: informativo (ajuste fino requiere cambios en trader)
LEVERAGE_CAP = 5
PYRAMIDING = False
PARTIALS = {"TP1": 1.272, "TP2": 1.414, "TP3": 1.618}

# Intervalo entre escaneos
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "900"))

# Gestión dinámica de Stop Loss (Haack)
DYNAMIC_SL_ENABLED = os.getenv("HAACK_DYNAMIC_SL_ENABLED", os.getenv("DYNAMIC_SL_ENABLED", "True")).lower() == "true"
BREAKEVEN_ON_TP1 = os.getenv("HAACK_BREAKEVEN_ON_TP1", os.getenv("BREAKEVEN_ON_TP1", "True")).lower() == "true"
BREAKEVEN_OFFSET_PCT = float(os.getenv("HAACK_BREAKEVEN_OFFSET_PCT", os.getenv("BREAKEVEN_OFFSET_PCT", "0.0")))
TRAILING_ATR_ENABLED = os.getenv("HAACK_TRAILING_ATR_ENABLED", os.getenv("TRAILING_ATR_ENABLED", "True")).lower() == "true"
TRAILING_ATR_MULT = float(os.getenv("HAACK_TRAILING_ATR_MULT", "1.4"))
TRAILING_ATR_TIMEFRAME = os.getenv("HAACK_TRAILING_ATR_TIMEFRAME", "4h")
MIN_SL_MOVE_PERCENT = float(os.getenv("HAACK_MIN_SL_MOVE_PERCENT", "0.0015"))
EARLY_PROFIT_TAKE_ENABLED = os.getenv("HAACK_EARLY_PROFIT_TAKE_ENABLED", os.getenv("EARLY_PROFIT_TAKE_ENABLED", "True")).lower() == "true"
EARLY_PROFIT_TAKE_USDT = float(os.getenv("HAACK_EARLY_PROFIT_TAKE_USDT", os.getenv("EARLY_PROFIT_TAKE_USDT", "10.0")))

# Límites de margen (USDT real invertido) por trade
MIN_MARGIN_USDT = float(os.getenv("HAACK_MIN_MARGIN_USDT", os.getenv("MIN_MARGIN_USDT", "25.0")))
MAX_MARGIN_USDT = float(os.getenv("HAACK_MAX_MARGIN_USDT", os.getenv("MAX_MARGIN_USDT", "50.0")))

# Estado runtime (cooldown y límites diarios)
_last_trade_time: Dict[str, float] = {}           # clave: f"{symbol}:{timeframe}"
_daily_trade_count: Dict[str, int] = {}           # clave día YYYY-MM-DD
_trade_wallet_baseline: Dict[int, float] = {}
_last_wallet_balance_snapshot: Optional[float] = None

# ====== Impulsos (sensibilidad H1 / H4) ======
IMPULSE_ENABLED = True
IMPULSE_TFS = ["1h", "4h"]
IMPULSE_BODY_ATR_MULT = 1.0      # cuerpo >= 1.0x ATR (más sensible)
IMPULSE_MIN_BODY_PCT = 0.50      # cuerpo >= 50% del rango
IMPULSE_BREAK_LOOKBACK = 12      # rompe HH/LL de N velas previas (más corto)
IMPULSE_MIN_VOL_RATIO = 1.00     # volumen >= 1.0x promedio 20

# Timeframes extra permitidos por símbolo para impulsos (BTC muy líquido)
IMPULSE_TFS_EXTRA_BY_SYMBOL = {
    "BTCUSDT": ["5m", "15m", "30m", "1h", "2h", "4h", "12h", "1d"],
}

def impulse_tf_allowed(symbol: Optional[str], timeframe: str) -> bool:
    extra = []
    if symbol and symbol in IMPULSE_TFS_EXTRA_BY_SYMBOL:
        extra = IMPULSE_TFS_EXTRA_BY_SYMBOL[symbol]
    return timeframe in IMPULSE_TFS or timeframe in extra


# ================== UTILIDADES ==================
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ Error Telegram: {r.status_code} -> {r.text}")
    except Exception as e:
        print(f"[WARN] Telegram falló: {e}")


def get_wallet_balance_usdt(trader: Optional[BinanceFuturesTrader]) -> Optional[float]:
    if trader is None:
        return None
    try:
        account = trader.client.futures_account(recvWindow=60000)
        for asset in account.get('assets', []):
            if asset.get('asset') == 'USDT':
                return float(asset.get('walletBalance', 0))
    except Exception as e:
        print(f"⚠️ No se pudo leer walletBalance (Haack): {e}")

    try:
        return float(trader.get_account_balance())
    except Exception:
        return None


def _to_millis(dt_value) -> int:
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


def detect_close_reason_and_price(
    trader: Optional[BinanceFuturesTrader],
    symbol: str,
    trade: Dict,
) -> Tuple[str, float]:
    reason = "CLOSE"
    exit_price = 0.0

    if trader is None:
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
        print(f"⚠️ No se pudo detectar motivo de cierre (Haack) en {symbol}: {e}")

    return reason, exit_price


def send_close_summary_telegram(
    trade: Dict,
    close_reason: str,
    exit_price: float,
    wallet_before: Optional[float],
    wallet_after: Optional[float],
):
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


def reconcile_closed_trades_and_notify(trader: Optional[BinanceFuturesTrader], db: TradingDatabase):
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
            close_reason, exit_price = detect_close_reason_and_price(trader, symbol, trade)

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
            wallet_after = get_wallet_balance_usdt(trader)

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
        print(f"⚠️ Error reconciliando cierres Haack: {e}")


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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


def get_klines(symbol: str, interval: str, limit: int = 300) -> pd.DataFrame:
    try:
        kl = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    except Exception as e:
        print(f"⚠️ get_klines fallo {symbol}-{interval}: {e}")
        return pd.DataFrame()

    df = pd.DataFrame(
        kl,
        columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore",
        ],
    )
    if df.empty:
        return df
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df[["timestamp", "open", "high", "low", "close", "volume"]].dropna()
    return df


@lru_cache(maxsize=512)
def cached_klines(symbol: str, interval: str, limit: int = 300) -> pd.DataFrame:
    # Cache por ciclo para alignment y análisis
    return get_klines(symbol, interval, limit)


# ====== Indicadores y utilidades avanzadas ======
def pct(x: float) -> float:
    return x * 100.0


def get_atr_series(df: pd.DataFrame) -> pd.Series:
    return ta.atr(df["high"], df["low"], df["close"], length=ATR_LEN)


def atr_pct(df: pd.DataFrame, length: int = ATR_PERIOD) -> float:
    atr = ta.atr(df["high"], df["low"], df["close"], length=length).iloc[-1]
    price = float(df["close"].iloc[-1])
    return float(atr) / price if price else 0.0


def ema_slope(series: pd.Series, lookback: int = 10) -> float:
    # Nota: la pendiente es (EMA_t - EMA_t-lookback) / EMA_t -> pendiente relativa de EMA
    if len(series) < lookback + 1:
        return 0.0
    y2 = float(series.iloc[-1])
    y1 = float(series.iloc[-(lookback + 1)])
    return (y2 - y1) / y2 if y2 else 0.0


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
        # Retracements desde high hacia low
        levels["retracements"] = [high - (high - low) * r for r in FIB_RETRACEMENTS]
        levels["extensions"] = [low + (high - low) * e for e in FIB_EXTENSIONS]
    else:
        # SHORT: espejo
        levels["retracements"] = [low + (high - low) * r for r in FIB_RETRACEMENTS]
        levels["extensions"] = [high - (high - low) * e for e in FIB_EXTENSIONS]
    levels["range_pct"] = rng
    return levels


def nearest_sr(df: pd.DataFrame, lookback: int) -> List[float]:
    # S/R con ventana centrada y sin NaNs
    w = df.tail(lookback).copy()
    if len(w) < 3:
        return []
    highs = w["high"].rolling(3, min_periods=3, center=True).apply(
        lambda x: float(x[1] > x[0] and x[1] > x[2]), raw=True
    )
    lows = w["low"].rolling(3, min_periods=3, center=True).apply(
        lambda x: float(x[1] < x[0] and x[1] < x[2]), raw=True
    )
    levels = []
    for i in range(len(w)):
        if 1 <= i <= len(w) - 2:
            if highs.iloc[i] == 1.0:
                levels.append(float(w["high"].iloc[i]))
            if lows.iloc[i] == 1.0:
                levels.append(float(w["low"].iloc[i]))
    levels = sorted(list(set(round(v, 6) for v in levels)))
    return levels[-30:]


def candle_anatomy(last: pd.Series) -> Dict[str, float]:
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


def last_adx(df: pd.DataFrame, length: int = 14) -> Optional[float]:
    # ADX robusto a nombres de columnas
    adx_df = ta.adx(df["high"], df["low"], df["close"], length=length)
    if adx_df is None or len(adx_df) == 0:
        return None
    for col in list(adx_df.columns)[::-1]:
        if "ADX" in col.upper():
            try:
                return float(adx_df[col].iloc[-1])
            except Exception:
                return None
    return None


def detect_impulse(df: pd.DataFrame, side: str, timeframe: str, symbol: Optional[str] = None) -> Tuple[bool, Dict[str, float]]:
    """Detecta vela de impulso en H1/H4 con condiciones de cuerpo, ATR, volumen y ruptura.
    Retorna (is_impulse, metrics).
    """
    if not IMPULSE_ENABLED or not impulse_tf_allowed(symbol, timeframe):
        return False, {}
    if df is None or len(df) < max(ATR_PERIOD + 2, IMPULSE_BREAK_LOOKBACK + 5):
        return False, {}

    last = df.iloc[-1]
    prev_window = df.iloc[-(IMPULSE_BREAK_LOOKBACK+1):-1]

    atr = float(get_atr_series(df).iloc[-1])
    o, h, l, c = map(float, [last["open"], last["high"], last["low"], last["close"]])
    rng = max(1e-12, h - l)
    body = abs(c - o)
    body_pct = body / rng
    body_vs_atr = body / max(1e-9, atr)

    vol_now = float(last["volume"]) if "volume" in last else 0.0
    vol_avg20 = float(df["volume"].tail(20).mean()) if "volume" in df else 0.0
    vol_ratio = vol_now / vol_avg20 if vol_avg20 > 0 else 0.0

    if side == "LONG":
        broke = c > float(prev_window["high"].max())
        dir_ok = c > o
    else:
        broke = c < float(prev_window["low"].min())
        dir_ok = c < o

    is_impulse = (
        dir_ok and (broke or body_vs_atr >= IMPULSE_BODY_ATR_MULT) and
        body_pct >= IMPULSE_MIN_BODY_PCT and
        vol_ratio >= IMPULSE_MIN_VOL_RATIO
    )

    metrics = {
        "body_pct": body_pct,
        "body_vs_atr": body_vs_atr,
        "vol_ratio": vol_ratio,
        "broke": float(broke),
    }
    return is_impulse, metrics


def timeframe_alignment_ok(symbol: str, side: str) -> bool:
    if not TIMEFRAME_ALIGNMENT:
        return True
    ok = 0
    for tf in ALIGN_WITH:
        try:
            df = cached_klines(symbol, tf, limit=200)
            if df is None or df.empty or len(df) < 60:
                continue
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


def get_funding_bias(symbol: str) -> Optional[float]:
    # python-binance FUTURES funding rate
    try:
        rates = client.futures_funding_rate(symbol=symbol, limit=1)
        if rates:
            return float(rates[0]["fundingRate"])  # decimal
    except Exception:
        return None
    return None


# ====== Ichimoku ======
def ichimoku_components(df: pd.DataFrame,
                        tenkan:int=ICHI_TENKAN,
                        kijun:int=ICHI_KIJUN,
                        senkou_b:int=ICHI_SENKOUB):
    """Calcula Ichimoku estilo Donchian. Devuelve dict con Series."""
    if df is None or df.empty:
        return None
    h = df["high"]; l = df["low"]; c = df["close"]

    def mid(hh, ll):
        return (hh + ll) / 2.0

    tenkan_hi = h.rolling(tenkan).max()
    tenkan_lo = l.rolling(tenkan).min()
    tenkan_sen = mid(tenkan_hi, tenkan_lo)

    kijun_hi = h.rolling(kijun).max()
    kijun_lo = l.rolling(kijun).min()
    kijun_sen = mid(kijun_hi, kijun_lo)

    # A/B desplazadas 26 barras en el gráfico clásico; para filtrar ahora, usamos versión "now" sin shift
    senkou_span_a = ((tenkan_sen + kijun_sen) / 2.0).shift(kijun)  # adelantada
    senkou_span_b = mid(h.rolling(senkou_b).max(), l.rolling(senkou_b).min()).shift(kijun)

    chikou_span = c.shift(-kijun)  # precio desplazado 26 a la izquierda en el gráfico tradicional

    ssa_now = ((tenkan_sen + kijun_sen) / 2.0)  # sin shift, para estado actual
    ssb_now = mid(h.rolling(senkou_b).max(), l.rolling(senkou_b).min())

    out = {
        "tenkan": tenkan_sen,
        "kijun": kijun_sen,
        "ssa_fwd": senkou_span_a,
        "ssb_fwd": senkou_span_b,
        "ssa_now": ssa_now,
        "ssb_now": ssb_now,
        "chikou": chikou_span,
    }
    return out


def ichi_price_vs_kumo(price: float, ssa_now: float, ssb_now: float) -> str:
    top = max(ssa_now, ssb_now); bot = min(ssa_now, ssb_now)
    if price > top: return "above"
    if price < bot: return "below"
    return "inside"


def ichi_signal_strength(side: str, where: str, chikou_ok: bool) -> str:
    if side == "LONG":
        if where == "above" and chikou_ok: return "strong"
        if where == "inside" and chikou_ok: return "medium"
        if where == "below": return "weak"
    else:
        if where == "below" and chikou_ok: return "strong"
        if where == "inside" and chikou_ok: return "medium"
        if where == "above": return "weak"
    return "weak"


def ichi_stop(price: float, side: str, kijun: float, ssa_now: float, ssb_now: float, atr: float) -> float:
    if ICHI_STOP_MODE == "kijun" and pd.notna(kijun):
        return kijun
    if ICHI_STOP_MODE == "ssb" and pd.notna(ssa_now) and pd.notna(ssb_now):
        edge = min(ssa_now, ssb_now) if side == "LONG" else max(ssa_now, ssb_now)
        return edge
    # fallback a ATR
    return price - SL_ATR_MULT * atr if side == "LONG" else price + SL_ATR_MULT * atr


# ====== Híbrido: gates + score ======
def hybrid_gate_and_score(side: str, df: pd.DataFrame, last_row: pd.Series,
                          ema20_series: pd.Series, ema50_series: pd.Series,
                          precomputed: dict) -> Tuple[bool, float, dict]:
    """Gates + score híbrido EMA/RSI/ATR/ADX/Fib/Vol + Ichimoku."""
    notes = {}
    price = float(last_row["close"])

    ema20 = float(ema20_series.iloc[-1]); ema50 = float(ema50_series.iloc[-1])
    ema_distance = abs(ema20 - ema50) / price
    notes["ema_distance"] = ema_distance

    vol_ratio = precomputed.get("vol_ratio", 1.0)
    rsi = precomputed.get("rsi", None)
    atr = precomputed.get("atr", None)
    atr_pct_now = precomputed.get("atr_pct_now", None)
    adx_val = precomputed.get("adx", None)
    fib_conf = precomputed.get("fib_conf", 0.0)
    sr_conf  = precomputed.get("sr_conf", 0.0)
    mtaf_ok = precomputed.get("mtaf_ok", True)

    # Ichimoku
    ichi = ichimoku_components(df)
    if ichi is None or pd.isna(ichi["ssa_now"].iloc[-1]) or pd.isna(ichi["ssb_now"].iloc[-1]):
        return False, 0.0, {"reason": "Ichimoku no disponible"}

    where = ichi_price_vs_kumo(price, float(ichi["ssa_now"].iloc[-1]), float(ichi["ssb_now"].iloc[-1]))
    tk_now_up   = ichi["tenkan"].iloc[-1] > ichi["kijun"].iloc[-1]
    tk_prev_up  = ichi["tenkan"].iloc[-2] > ichi["kijun"].iloc[-2]
    tk_cross_lo =  tk_now_up and not tk_prev_up
    tk_cross_sh = (ichi["tenkan"].iloc[-1] < ichi["kijun"].iloc[-1]) and not (ichi["tenkan"].iloc[-2] < ichi["kijun"].iloc[-2])
    tk_cross = tk_cross_lo if side=="LONG" else tk_cross_sh

    chik_ok = True
    if GATE_CHIKOU_CONFIRM:
        try:
            chik = float(ichi["chikou"].iloc[-1])
            ref  = float(df["close"].iloc[-ICHI_KIJUN]) if len(df) > ICHI_KIJUN else float(df["close"].iloc[0])
            chik_ok = (chik > ref) if side=="LONG" else (chik < ref)
        except Exception:
            chik_ok = True

    strength = ichi_signal_strength(side, where, chik_ok)
    notes["ichi_where"] = where
    notes["ichi_tk_cross"] = tk_cross
    notes["ichi_strength"] = strength

    # Impulso: puede relajar gates sutilmente
    impulse = precomputed.get("impulse", False)
    # GATES
    if GATE_BLOCK_IN_KUMO and where == "inside" and not impulse:
        return False, 0.0, {"reason": "Precio dentro del Kumo"}
    if GATE_REQUIRE_ICHI_TREND and not impulse:
        if (side=="LONG" and where=="below") or (side=="SHORT" and where=="above"):
            return False, 0.0, {"reason": "Tendencia Kumo en contra"}
    # En impulso permitimos EMAs un poco más cerca (80% del umbral)
    min_ema = GATE_MIN_EMA_DIST * (0.8 if impulse else 1.0)
    if GATE_MIN_EMA_DIST is not None and ema_distance < min_ema:
        return False, 0.0, {"reason": "EMAs muy juntas"}
    lo, hi = GATE_ATR_RANGE
    if atr_pct_now is not None and not (lo <= atr_pct_now <= hi):
        return False, 0.0, {"reason": "ATR% fuera de rango"}
    if GATE_REQUIRE_EMA200_TREND:
        ema200 = float(ta.ema(df["close"], length=200).iloc[-1])
        if (side=="LONG" and price < ema200) or (side=="SHORT" and price > ema200):
            return False, 0.0, {"reason": "EMA200 en contra"}
    if GATE_CHIKOU_CONFIRM and not chik_ok:
        return False, 0.0, {"reason": "Chikou no confirma"}

    # SCORE
    score = 0.0
    score += SCORE_W["trend_ema200"] * 1.0
    score += SCORE_W["kumo_trend"]   * (1.0 if ((side=="LONG" and where=="above") or (side=="SHORT" and where=="below")) else 0.0)

    ema_cross_ok = (ema20 > ema50) if side=="LONG" else (ema20 < ema50)
    score += SCORE_W["ema20_50_cross"] * (1.0 if ema_cross_ok else 0.0)

    score += SCORE_W["tenkan_kijun_cross"] * (1.0 if tk_cross else 0.0)
    strength_rank = {"weak": 0.4, "medium": 0.7, "strong": 1.0}
    score += SCORE_W["tk_strength"] * strength_rank.get(strength, 0.4)

    score += SCORE_W["ema_distance"]   * (min(1.0, ema_distance / GATE_MIN_EMA_DIST) if GATE_MIN_EMA_DIST else 0.0)
    score += SCORE_W["rsi_zone"]       * 1.0
    score += SCORE_W["volume_ratio"]   * (min(1.2, vol_ratio) / 1.2)
    score += SCORE_W["atr_in_range"]   * 1.0
    if adx_val is not None:
        score += SCORE_W["adx"] * min(1.0, adx_val / 50.0)
    score += SCORE_W["fib_confluence"] * (1.0 if (fib_conf >= 1.0) else 0.0)
    score += SCORE_W["sr_confluence"]  * (1.0 if (sr_conf  >= 1.0) else 0.0)
    score += SCORE_W["multi_tf_alignment"] * (1.0 if mtaf_ok else 0.0)
    if impulse:
        score += SCORE_W.get("impulse", 0.0) * 1.0
        notes["impulse"] = True

    notes["score"] = score
    return True, score, notes


def check_filters(side: str, df: pd.DataFrame, last_row: pd.Series) -> Dict:
    """
    Verifica filtros de calidad para el setup Haack.
    Retorna: {'passed': bool, 'reasons': List[str], métricas...}
    """
    reasons: List[str] = []
    if df is None or df.empty:
        return {"passed": False, "reasons": ["❌ DataFrame vacío"]}

    price = float(last_row["close"])
    if price <= 0:
        return {"passed": False, "reasons": ["❌ Precio inválido"]}

    # ATR (1 sola vez)
    atr_series = get_atr_series(df)
    if atr_series is None or len(atr_series) == 0:
        return {"passed": False, "reasons": ["❌ ATR no disponible"]}
    atr = float(atr_series.iloc[-1])
    if atr <= 0:
        return {"passed": False, "reasons": ["❌ ATR inválido"]}

    # Volumen
    vol_now = float(df["volume"].iloc[-1])
    vol_avg20 = float(df["volume"].tail(20).mean())
    vol_ratio = vol_now / vol_avg20 if vol_avg20 > 0 else 0.0
    if vol_ratio < MIN_VOLUME_RATIO:
        reasons.append(f"❌ Volumen bajo ({vol_ratio:.2f}x < {MIN_VOLUME_RATIO:.2f}x)")
        return {"passed": False, "reasons": reasons, "vol_ratio": vol_ratio}

    # EMAs y distancia
    ema20_series = ta.ema(df["close"], length=20)
    ema50_series = ta.ema(df["close"], length=50)
    ema20 = float(ema20_series.iloc[-1])
    ema50 = float(ema50_series.iloc[-1])
    ema_distance = abs(ema20 - ema50) / price
    if ema_distance < MIN_EMA_DISTANCE:
        reasons.append(f"❌ EMAs muy cercanas ({ema_distance*100:.2f}% < {MIN_EMA_DISTANCE*100:.2f}%)")
        return {"passed": False, "reasons": reasons, "vol_ratio": vol_ratio}

    # RSI
    rsi_series = ta.rsi(df["close"], length=14)
    rsi = float(rsi_series.iloc[-1])
    # Impulso puede ampliar levemente el rango permitido
    tf = str(last_row.get("timeframe", "")) if "timeframe" in last_row else ""
    sym = str(last_row.get("symbol", "")) if "symbol" in last_row else None
    is_impulse, imp_metrics = detect_impulse(df, side, tf, sym) if tf else (False, {})
    if side == "LONG":
        rsi_min, rsi_max = RSI_LONG_MIN - (5 if is_impulse else 0), RSI_LONG_MAX + (3 if is_impulse else 0)
        if rsi < rsi_min or rsi > rsi_max:
            reasons.append(f"❌ RSI fuera de rango LONG ({rsi:.1f} no está {rsi_min}-{rsi_max})")
            return {"passed": False, "reasons": reasons, "vol_ratio": vol_ratio, "rsi": rsi}
    else:
        rsi_min, rsi_max = RSI_SHORT_MIN - (3 if is_impulse else 0), RSI_SHORT_MAX + (5 if is_impulse else 0)
        if rsi < rsi_min or rsi > rsi_max:
            reasons.append(f"❌ RSI fuera de rango SHORT ({rsi:.1f} no está {rsi_min}-{rsi_max})")
            return {"passed": False, "reasons": reasons, "vol_ratio": vol_ratio, "rsi": rsi}

    # Tendencia EMA200 (si se pide)
    if REQUIRE_EMA200_TREND:
        ema200 = ta.ema(df["close"], length=200)
        if len(ema200) > 0:
            ema200_val = float(ema200.iloc[-1])
            if side == "LONG" and price < ema200_val:
                reasons.append("❌ Precio por debajo de EMA200 (tendencia bajista)")
                return {"passed": False, "reasons": reasons}
            if side == "SHORT" and price > ema200_val:
                reasons.append("❌ Precio por encima de EMA200 (tendencia alcista)")
                return {"passed": False, "reasons": reasons}

    # Pendiente EMA20 (momentum de tendencia)
    slope20 = ema_slope(ema20_series, lookback=10)
    if abs(slope20) < MIN_TREND_SLOPE:
        reasons.append(f"❌ Pendiente EMA20 baja ({pct(abs(slope20)):.2f}% < {pct(MIN_TREND_SLOPE):.2f}%)")
        return {"passed": False, "reasons": reasons, "vol_ratio": vol_ratio, "rsi": rsi}

    # ATR% dentro de rango (flex +10% por impulso fuerte)
    atr_pct_now = atr / price if price > 0 else 0.0
    max_atr_allowed = MAX_ATR_PCT * (1.10 if is_impulse else 1.0)
    if not (MIN_ATR_PCT <= atr_pct_now <= max_atr_allowed):
        reasons.append(f"❌ ATR fuera de rango ({pct(atr_pct_now):.2f}% no en {pct(MIN_ATR_PCT):.2f}-{pct(MAX_ATR_PCT):.2f}%)")
        return {"passed": False, "reasons": reasons}

    # SL consistente con build_levels: precio ± SL_ATR_MULT * ATR
    sl = price - SL_ATR_MULT * atr if side == "LONG" else price + SL_ATR_MULT * atr
    sl_distance = abs(price - sl) / price
    if sl_distance > MAX_SL_PERCENT:
        reasons.append(f"❌ Stop Loss muy amplio ({sl_distance*100:.2f}% > {MAX_SL_PERCENT*100:.1f}%)")
        return {"passed": False, "reasons": reasons, "vol_ratio": vol_ratio, "rsi": rsi}

    # Anatomía de vela (cierre y mechas)
    ana = candle_anatomy(last_row)
    if REQUIRE_CLOSE_IN_DIRECTION:
        if side == "LONG" and ana["close_dir"] < 0:
            reasons.append("❌ Cierre de vela en contra")
            return {"passed": False, "reasons": reasons}
        if side == "SHORT" and ana["close_dir"] > 0:
            reasons.append("❌ Cierre de vela en contra")
            return {"passed": False, "reasons": reasons}
    if REQUIRE_WICK_REJECTION:
        if side == "LONG" and ana["up_wick_pct"] > MAX_UPWICK_FOR_LONG:
            if not is_impulse:
                reasons.append("❌ Mecha superior excesiva para LONG")
                return {"passed": False, "reasons": reasons}
        if side == "SHORT" and ana["down_wick_pct"] > MAX_DOWNWICK_FOR_SHORT:
            if not is_impulse:
                reasons.append("❌ Mecha inferior excesiva para SHORT")
                return {"passed": False, "reasons": reasons}
    if ana["body_pct"] < MIN_BODY_TO_RANGE:
        reasons.append("❌ Cuerpo pequeño en relación al rango")
        return {"passed": False, "reasons": reasons}

    # ADX
    adx_val = None
    if ADX_FILTER:
        adx_val = last_adx(df, length=14)
        if adx_val is None and not is_impulse:
            reasons.append("❌ ADX no disponible")
            return {"passed": False, "reasons": reasons}
        if adx_val is not None:
            min_adx = ADX_MIN * (0.7 if is_impulse else 1.0)
            if adx_val < min_adx and not is_impulse:
                reasons.append(f"❌ ADX débil ({adx_val:.1f} < {ADX_MIN})")
                return {"passed": False, "reasons": reasons}

    # Estructura HH/HL
    if STRUCT_REQUIRE_HH_HL:
        w = df.tail(max(STRUCT_SWING_DEPTH * 3, 20))
        highs = w["high"].rolling(3, min_periods=3, center=True).apply(
            lambda x: float(x[1] > x[0] and x[1] > x[2]), raw=True
        )
        lows = w["low"].rolling(3, min_periods=3, center=True).apply(
            lambda x: float(x[1] < x[0] and x[1] < x[2]), raw=True
        )
        swing_highs = [float(w["high"].iloc[i]) for i in range(len(w)) if highs.iloc[i] == 1.0]
        swing_lows = [float(w["low"].iloc[i]) for i in range(len(w)) if lows.iloc[i] == 1.0]
        ok_struct = True
        if side == "LONG" and len(swing_highs) >= STRUCT_SWING_DEPTH and len(swing_lows) >= STRUCT_SWING_DEPTH:
            ok_struct = all(swing_highs[i] > swing_highs[i-1] for i in range(1, STRUCT_SWING_DEPTH)) and \
                        all(swing_lows[i] > swing_lows[i-1] for i in range(1, STRUCT_SWING_DEPTH))
        if side == "SHORT" and len(swing_highs) >= STRUCT_SWING_DEPTH and len(swing_lows) >= STRUCT_SWING_DEPTH:
            ok_struct = all(swing_highs[i] < swing_highs[i-1] for i in range(1, STRUCT_SWING_DEPTH)) and \
                        all(swing_lows[i] < swing_lows[i-1] for i in range(1, STRUCT_SWING_DEPTH))
        if not ok_struct:
            reasons.append("❌ Estructura de swings no alineada")
            return {"passed": False, "reasons": reasons}

    # Confluencias FIB/EMA/SR
    fib_conf = 0.0
    ema_conf = 0.0
    sr_conf = 0.0
    if USE_FIB:
        fl = fib_levels_from_swing(df, FIB_LOOKBACK_SWING, side)
        if fl:
            for lv in fl["retracements"]:
                if abs(price - lv) / price <= FIB_PROXIMITY_TOL:
                    fib_conf += 1.0
                    break
    if CONFLUENCE_WITH_EMA:
        base = ema20 if side == "LONG" else ema50
        if abs(price - base) / price <= CONFLUENCE_MAX_DIST_TO_EMA:
            ema_conf = 1.0
    if CONFLUENCE_WITH_SR:
        srs = nearest_sr(df, SR_LOOKBACK)
        for lv in srs:
            if abs(price - lv) / price <= SR_PROXIMITY_TOL:
                sr_conf = 1.0
                break

    # Alineación multi-timeframe (si la chequeás fuera, marcá mtaf_ok=True allá)
    mtaf_ok = True

    # Funding bias
    if USE_FUNDING_BIAS and "symbol" in last_row:
        fb = get_funding_bias(str(last_row["symbol"]))
        if fb is not None:
            if fb > MAX_POSITIVE_FUNDING and side == "LONG":
                reasons.append(f"❌ Funding positivo alto ({fb:.4f}) en LONG")
                return {"passed": False, "reasons": reasons}
            if fb < MIN_NEGATIVE_FUNDING and side == "SHORT":
                reasons.append(f"❌ Funding negativo alto ({fb:.4f}) en SHORT")
                return {"passed": False, "reasons": reasons}

    # ==== HÍBRIDO: gates + score ====
    if USE_HYBRID:
        precomputed = {
            "vol_ratio": vol_ratio,
            "rsi": rsi,
            "atr": atr,
            "atr_pct_now": atr_pct_now,
            "adx": adx_val,
            "fib_conf": fib_conf,
            "sr_conf": sr_conf,
            "mtaf_ok": mtaf_ok,
            "impulse": is_impulse,
        }
        ok, score_h, notes = hybrid_gate_and_score(
            side, df, last_row, ema20_series=ema20_series, ema50_series=ema50_series, precomputed=precomputed
        )
        if not ok:
            return {"passed": False, "reasons": [f"❌ Gate híbrido: {notes.get('reason', 'fail')}"]}

        score_total = score_h
        if score_total < MIN_SCORE_TO_TRADE:
            return {"passed": False, "reasons": [f"❌ Score híbrido insuficiente ({score_total:.2f} < {MIN_SCORE_TO_TRADE:.2f})"]}

        reasons_ok = [
            f"✅ Volumen: {vol_ratio:.2f}x",
            f"✅ EMAs separadas: {ema_distance*100:.2f}%",
            f"✅ RSI: {rsi:.1f}",
            f"✅ SL razonable: {sl_distance*100:.2f}%",
            f"✅ Kumo: {notes.get('ichi_where','-')} | TK: {notes.get('ichi_tk_cross', False)} | fuerza: {notes.get('ichi_strength','-')}",
            f"✅ Score: {score_total:.2f}",
        ]
        if is_impulse:
            reasons_ok.append(
                f"✅ Impulso {tf}: cuerpo/ATR={imp_metrics.get('body_vs_atr',0):.2f} | cuerpo%={imp_metrics.get('body_pct',0)*100:.0f}% | vol={imp_metrics.get('vol_ratio',0):.2f}x"
            )
        return {
            "passed": True,
            "reasons": reasons_ok,
            "vol_ratio": vol_ratio,
            "rsi": rsi,
            "sl_distance": sl_distance,
            "score": score_total,
            "impulse": is_impulse,
        }

    # Si no se usa híbrido, devolvemos el paquete base
    reasons_ok = [
        f"✅ Volumen: {vol_ratio:.2f}x",
        f"✅ EMAs separadas: {ema_distance*100:.2f}%",
        f"✅ RSI: {rsi:.1f}",
        f"✅ SL razonable: {sl_distance*100:.2f}%",
        f"✅ Confluencias: {'Sí' if (fib_conf+ema_conf+sr_conf)>=1.0 else 'No'}",
    ]
    return {
        "passed": True,
        "reasons": reasons_ok,
        "vol_ratio": vol_ratio,
        "rsi": rsi,
        "sl_distance": sl_distance,
        "impulse": is_impulse,
    }


def build_levels(side: str, last_row: pd.Series, df: pd.DataFrame, symbol: str, timeframe: str) -> Dict:
    dec = decimals_for(symbol)
    atr_series = get_atr_series(df)
    atr = float(atr_series.iloc[-1])

    ema20 = float(ta.ema(df["close"], length=20).iloc[-1])
    ema50 = float(ta.ema(df["close"], length=50).iloc[-1])
    price = float(last_row["close"])

    entry_high = max(ema20, ema50)
    entry_low = min(ema20, ema50)

    # SL Ichimoku (kijun/ssb) o ATR
    if USE_ICHI:
        ichi = ichimoku_components(df)
        kijun_val = float(ichi["kijun"].iloc[-1]) if ichi is not None else float('nan')
        ssa_now = float(ichi["ssa_now"].iloc[-1]) if ichi is not None else float('nan')
        ssb_now = float(ichi["ssb_now"].iloc[-1]) if ichi is not None else float('nan')
        sl_raw = ichi_stop(price, side, kijun_val, ssa_now, ssb_now, atr)
    else:
        sl_raw = price - SL_ATR_MULT * atr if side == "LONG" else price + SL_ATR_MULT * atr

    sl = sl_raw
    sl_distance = abs(price - sl) / price
    if sl_distance > MAX_SL_PERCENT:
        sl = price - SL_ATR_MULT * atr if side == "LONG" else price + SL_ATR_MULT * atr

    # TPs
    if TP_MULTS is None:
        if side == "LONG":
            tps = [price + TP_ATR_MULT * atr * m for m in [0.6, 0.8, 1.0]]
        else:
            tps = [price - TP_ATR_MULT * atr * m for m in [0.6, 0.8, 1.0]]
    else:
        if side == "LONG":
            tps = [price + m * atr for m in TP_MULTS]
        else:
            tps = [price - m * atr for m in TP_MULTS]

    # Info Fib/SR (diagnóstico)
    fib_info = fib_levels_from_swing(df, FIB_LOOKBACK_SWING, side) if USE_FIB else None
    sr_info = nearest_sr(df, SR_LOOKBACK) if CONFLUENCE_WITH_SR else []

    return {
        "entry_high": round(entry_high, dec),
        "entry_low": round(entry_low, dec),
        "sl": round(sl, dec),
        "tp1": round(tps[0], dec),
        "tp2": round(tps[1], dec),
        "tp3": round(tps[2], dec),
        "price": round(price, dec),
        "atr": atr,
        "timeframe": timeframe,
        "fib": fib_info,
        "sr": sr_info[-5:] if sr_info else [],
        "impulse_flag": bool(last_row.get("impulse", False)),
    }


def format_trade_message(symbol: str, side: str, levels: Dict, timeframe: str, traded: bool = False) -> str:
    s = display_symbol(symbol)
    action = "🚀 <b>TRADE EJECUTADO</b>" if traded else "📣 <b>SEÑAL DETECTADA</b>"
    imp = levels.get("impulse_flag", False)
    imp_txt = " ⚡IMPULSO" if imp else ""
    return (
        f"{action}\n"
        f"🤖 Bot: <b>{BOT_NAME}</b>\n"
        f"📌 Par: <b>{s}</b> {'🟢 LONG' if side=='LONG' else '🔴 SHORT'}{imp_txt}\n"
        f"⏰ Timeframe: {timeframe}\n\n"
        f"📍 Zona entrada: {levels['entry_low']} - {levels['entry_high']}\n"
        f"🔴 SL: {levels['sl']}\n"
        f"🟢 TP1: {levels['tp1']}\n"
        f"🟢 TP2: {levels['tp2']}\n"
        f"🟢 TP3: {levels['tp3']}\n\n"
        f"💰 Precio actual: {levels['price']}"
    )


def execute_trade(
    trader: BinanceFuturesTrader,
    db: TradingDatabase,
    symbol: str,
    side: str,
    levels: Dict,
    timeframe: str,
    risk_guard: Optional[RiskGuard] = None,
) -> Optional[Dict]:
    """Ejecuta el trade respetando límites y guarda en DB."""
    try:
        wallet_before_trade = get_wallet_balance_usdt(trader)

        # Cooldown por símbolo/timeframe
        key = f"{symbol}:{timeframe}"
        now = time.time()
        last_t = _last_trade_time.get(key, 0)
        if now - last_t < COOLDOWN_AFTER_TRADE_MIN * 60:
            print(f"⏳ Cooldown activo para {key}, omitiendo trade")
            return None

        # Límite diario
        day = datetime.utcnow().strftime('%Y-%m-%d')
        cnt = _daily_trade_count.get(day, 0)
        if cnt >= MAX_TRADES_PER_DAY:
            print(f"⛔ Límite diario de trades alcanzado ({MAX_TRADES_PER_DAY})")
            return None

        if risk_guard is not None:
            can_trade, reason = risk_guard.can_open_trade(symbol=symbol)
            if not can_trade:
                print(f"🛑 RiskGuard bloqueó trade en {symbol}: {reason}")
                return None

        open_positions = trader.get_open_positions() if trader else []

        # Verificar si ya hay posición abierta en este símbolo
        for pos in open_positions:
            if pos['symbol'] == symbol:
                print(f"⚠️ Ya existe una posición abierta en {symbol}, omitiendo...")
                return None

        # Límite de concurrencia por preset
        max_conc = min(MAX_CONCURRENT_POS, MAX_POSITIONS)
        if len(open_positions) >= max_conc:
            print(f"⚠️ Máximo de posiciones alcanzado ({max_conc}), omitiendo {symbol}")
            return None

        entry_price = levels["price"]
        sl_price = levels["sl"]
        tp_prices = [levels["tp1"], levels["tp2"], levels["tp3"]]

        result = trader.open_position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_prices=tp_prices,
            force_market=USE_MARKET_ORDER,
            min_margin_usdt=MIN_MARGIN_USDT,
            max_margin_usdt=MAX_MARGIN_USDT,
        )

        if not result:
            return None

        trade_id = db.add_trade(
            symbol=symbol,
            side=side,
            entry_price=result.get("entry_price", entry_price),
            quantity=result.get("quantity", 0),
            leverage=result.get("leverage", int(os.getenv("LEVERAGE", "5"))),
            sl_price=sl_price,
            tp_prices=tp_prices,
            timeframe=timeframe,
            notes="Haack",
            bot="Haack",
        )

        # Registrar órdenes individuales en DB
        try:
            db.add_order(
                trade_id=trade_id,
                order_id=str(result['entry_order']['orderId']),
                order_type="ENTRY",
                side=result['entry_order']['side'],
                symbol=symbol,
                price=result.get('entry_price', entry_price),
                quantity=result.get('quantity', 0),
                status="FILLED"
            )
            if result.get('sl_order'):
                db.add_order(
                    trade_id=trade_id,
                    order_id=str(result['sl_order']['orderId']),
                    order_type="STOP_LOSS",
                    side=result['sl_order']['side'],
                    symbol=symbol,
                    price=sl_price,
                    quantity=result.get('quantity', 0),
                    status="NEW"
                )
            for i, tp_order in enumerate(result.get('tp_orders', []), 1):
                db.add_order(
                    trade_id=trade_id,
                    order_id=str(tp_order['orderId']),
                    order_type=f"TAKE_PROFIT_{i}",
                    side=tp_order['side'],
                    symbol=symbol,
                    price=tp_order.get('stopPrice', tp_order.get('price', 0)),
                    quantity=tp_order.get('origQty', 0),
                    status="NEW"
                )
        except Exception as e:
            print(f"⚠️ Error al registrar órdenes individuales en DB (Haack): {e}")

        _last_trade_time[key] = now
        _daily_trade_count[day] = cnt + 1
        if wallet_before_trade is not None:
            _trade_wallet_baseline[int(trade_id)] = float(wallet_before_trade)
        return {"trade_id": trade_id, **result}
    except Exception as e:
        print(f"❌ Error en execute_trade: {e}")
        return None


def analyze(symbol: str, timeframe: str) -> Optional[Dict]:
    """Analiza un símbolo/timeframe y retorna señal si corresponde."""
    df = get_klines(symbol, timeframe, limit=300)
    if df is None or df.empty or len(df) < 60:
        return None

    # Indicadores principales
    df["EMA20"] = ta.ema(df["close"], length=20)
    df["EMA50"] = ta.ema(df["close"], length=50)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Señal tipo cruce EMA20/EMA50 (prioridad alta)
    long_signal = (last["EMA20"] > last["EMA50"]) and (prev["EMA20"] <= prev["EMA50"])
    short_signal = (last["EMA20"] < last["EMA50"]) and (prev["EMA20"] >= prev["EMA50"])

    side = "LONG" if long_signal else ("SHORT" if short_signal else None)

    # Alternativamente, habilitar cruce Ichimoku si no hay cruce EMA
    if USE_ICHI and side is None:
        ichi = ichimoku_components(df)
        if ichi is not None and len(df) >= max(ICHI_SENKOUB, ICHI_KIJUN) + 5:
            tk_now_up = ichi["tenkan"].iloc[-1] > ichi["kijun"].iloc[-1]
            tk_prev_up = ichi["tenkan"].iloc[-2] > ichi["kijun"].iloc[-2]
            tk_cross_long = tk_now_up and not tk_prev_up
            tk_cross_short = (ichi["tenkan"].iloc[-1] < ichi["kijun"].iloc[-1]) and not (ichi["tenkan"].iloc[-2] < ichi["kijun"].iloc[-2])
            if tk_cross_long:
                side = "LONG"
            elif tk_cross_short:
                side = "SHORT"

    # Fallback: continuación de tendencia (evita depender de un cruce exacto en la vela actual)
    if side is None and ALLOW_CONTINUATION_SIGNALS:
        ema20_now = float(last["EMA20"])
        ema50_now = float(last["EMA50"])
        close_now = float(last["close"])
        if ema20_now > ema50_now and close_now >= ema20_now:
            side = "LONG"
        elif ema20_now < ema50_now and close_now <= ema20_now:
            side = "SHORT"

    # Fallback final: impulso puro en TF permitidos
    if side is None and IMPULSE_ENABLED and impulse_tf_allowed(symbol, timeframe):
        imp_long, _ = detect_impulse(df, "LONG", timeframe, symbol)
        imp_short, _ = detect_impulse(df, "SHORT", timeframe, symbol)
        if imp_long and not imp_short:
            side = "LONG"
        elif imp_short and not imp_long:
            side = "SHORT"
        elif imp_long and imp_short:
            # desambiguar por dirección del cuerpo
            side = "LONG" if float(last["close"]) > float(last["open"]) else "SHORT"

    if side is None:
        return None

    # Alineación multi-timeframe (no bloquear si hay impulso fuerte)
    sim_long, _ = detect_impulse(df, "LONG", timeframe, symbol)
    sim_short, _ = detect_impulse(df, "SHORT", timeframe, symbol)
    strong_impulse = sim_long or sim_short
    if TIMEFRAME_ALIGNMENT and not strong_impulse and not timeframe_alignment_ok(symbol, side):
        return None

    # Filtros Haack (inyectamos symbol para funding)
    last = last.copy()
    last["symbol"] = symbol
    last["timeframe"] = timeframe
    check = check_filters(side, df, last)
    if not check.get("passed", False):
        return None

    # Marcar impulso en niveles si aplica
    if check.get("impulse"):
        last["impulse"] = True
    levels = build_levels(side, last, df, symbol, timeframe)
    return {"symbol": symbol, "side": side, "levels": levels, "metrics": check}


def scan_once(trader: Optional[BinanceFuturesTrader], db: TradingDatabase, risk_guard: Optional[RiskGuard] = None) -> None:
    """Escanea toda la watchlist en todos los timeframes una vez, con resumen por símbolo."""
    # Encabezado estilo conservador
    print("\n" + "="*60)
    print("🛡️ ESCANEO HAACK")
    print(f"🔍 {len(WATCHLIST)} cryptos en {len(TIMEFRAMES)} timeframes")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    runtime_auto_trade = AUTO_TRADE_ENABLED and (trader is not None)
    print("🤖 TRADING AUTOMÁTICO ACTIVADO" if runtime_auto_trade else "📢 SOLO ALERTAS")
    print("="*60)
    print("🛡️ Filtros activos:")
    print(f"   ✅ Tendencia EMA200 requerida: {'Sí' if REQUIRE_EMA200_TREND else 'No'}")
    print(f"   ✅ Distancia EMAs mínima: {MIN_EMA_DISTANCE*100:.2f}% | Slope min: {MIN_TREND_SLOPE*100:.2f}%")
    print(f"   ✅ Volumen mínimo: {MIN_VOLUME_RATIO}x")
    print(f"   ✅ RSI LONG: {RSI_LONG_MIN}-{RSI_LONG_MAX} | SHORT: {RSI_SHORT_MIN}-{RSI_SHORT_MAX}")
    print(f"   ✅ SL máximo: {MAX_SL_PERCENT*100:.1f}% | ATR% [{MIN_ATR_PCT*100:.2f}%, {MAX_ATR_PCT*100:.2f}%]")
    print(f"   ✅ FIB: {'ON' if USE_FIB else 'OFF'} | Confluencias EMA/SR: {CONFLUENCE_WITH_EMA}/{CONFLUENCE_WITH_SR}")
    print(f"   ✅ ADX min: {ADX_MIN} | Estructura HH/HL: {'Sí' if STRUCT_REQUIRE_HH_HL else 'No'}")
    print(f"   ✅ Alineación TF: {'Sí' if TIMEFRAME_ALIGNMENT else 'No'} -> {', '.join(ALIGN_WITH) if TIMEFRAME_ALIGNMENT else '-'}")
    print(f"   ✅ Ichimoku: {'ON' if USE_ICHI else 'OFF'} | Híbrido: {'ON' if USE_HYBRID else 'OFF'}")
    print(f"   ✅ Señales por cruce + continuación EMA; sensibilidad a impulsos en 1h/4h")
    print("="*60)

    total_signals = 0
    executed = 0

    # Resumen por símbolo
    for symbol in WATCHLIST:
        try:
            per_symbol_details: List[str] = []
            for timeframe in TIMEFRAMES:
                signal = analyze(symbol, timeframe)
                if not signal:
                    # Diagnóstico: verificar impulsos perdidos en BTCUSDT
                    if symbol == "BTCUSDT" and timeframe in ("1h", "4h"):
                        try:
                            dfd = cached_klines(symbol, timeframe, limit=300)
                            if dfd is not None and not dfd.empty:
                                impL, mL = detect_impulse(dfd, "LONG", timeframe, symbol)
                                impS, mS = detect_impulse(dfd, "SHORT", timeframe, symbol)
                                if impL or impS:
                                    print(f"      · BTCUSDT {timeframe} IMPULSO detectado (no pasó filtros): LONG={impL} SHORT={impS} | metrics={mL if impL else mS}")
                        except Exception:
                            pass
                    time.sleep(0.05)
                    continue

                total_signals += 1
                # Detalle por señal
                lv = signal["levels"]
                try:
                    sl_pct = abs(lv['price'] - lv['sl']) / lv['price'] * 100 if lv['price'] else 0
                    atr_val = lv.get('atr', 0)
                except Exception:
                    sl_pct = 0
                    atr_val = 0
                sc = signal.get("metrics", {}).get("score")
                fibtxt = "FIB" if lv.get("fib") else "-"
                srtxt = f"SRx{len(lv.get('sr', []))}" if lv.get("sr") else "-"
                imp_txt = " ⚡" if lv.get("impulse_flag") else ""
                per_symbol_details.append(
                    f"[{timeframe}] {signal['side']}{imp_txt} | Precio: {lv['price']} | SL: {lv['sl']} (-{sl_pct:.2f}%) | ATR: {atr_val:.4f} | TP: {lv['tp1']} / {lv['tp2']} / {lv['tp3']} | Score: {sc if sc is not None else '-'} | {fibtxt}/{srtxt}"
                )

                msg = format_trade_message(symbol, signal["side"], signal["levels"], timeframe, traded=False)
                send_telegram(msg)

                if AUTO_TRADE_ENABLED and trader is not None:
                    res = execute_trade(trader, db, symbol, signal["side"], signal["levels"], timeframe, risk_guard=risk_guard)
                    if res:
                        executed += 1
                        send_telegram(format_trade_message(symbol, signal["side"], signal["levels"], timeframe, traded=True))
                        time.sleep(0.3)

                time.sleep(0.1)  # throttle por símbolo/timeframe

            # Línea de resumen por símbolo
            sym_disp = display_symbol(symbol)
            if per_symbol_details:
                print(f"   {sym_disp}: Señales")
                for line in per_symbol_details:
                    print(f"      - {line}")
            else:
                print(f"   {sym_disp}: Sin señales aprobadas")

        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"⚠️ Error analizando {symbol}: {e}")
            time.sleep(0.05)

    print(f"\n📊 Señales encontradas: {total_signals} | Trades ejecutados: {executed}")

    # Reporte rápido + gráficos si hay info
    try:
        print("\n📈 Estadísticas rápidas:")
        generate_quick_report("trading_history.db")
        # Generar gráfico consolidado (pisa el anterior)
        dashboard = TradingDashboard("trading_history.db")
        # Consolidado: un único archivo que se pisa en cada ciclo
        dashboard.generate_consolidated_report(output_dir="reports", filename_base="trading_report_all")
        print("✅ Reportes actualizados en reports/")
    except Exception as e:
        print(f"⚠️ No se pudieron generar reportes: {e}")


def show_positions_summary(trader: Optional[BinanceFuturesTrader]):
    """Muestra un resumen de posiciones abiertas (estilo UI conservador)."""
    print("\n" + "=" * 60)
    print("  📊 RESUMEN DE POSICIONES ABIERTAS")
    print("=" * 60)

    if not trader:
        print("⚠️ Modo solo alertas (sin conexión activa a Binance)")
        return

    try:
        positions = trader.get_open_positions()
        if not positions:
            print("\n   No hay posiciones abiertas\n")
            return

        total_pnl = 0.0
        for i, pos in enumerate(positions, 1):
            symbol = pos.get('symbol')
            side = pos.get('side')
            qty = float(pos.get('quantity', 0))
            entry = float(pos.get('entryPrice', 0))
            upnl = float(pos.get('unrealizedProfit', 0))
            total_pnl += upnl

            print(f"{i:02d}. {symbol}  {side}  qty={qty}  entrada={entry}  uPnL={upnl:+.2f} USDT")
        print(f"\n  💰 PnL Total: {total_pnl:+.2f} USDT\n")
    except Exception as e:
        print(f"⚠️ No se pudo obtener posiciones: {e}")


def manage_dynamic_stop_losses(trader: Optional[BinanceFuturesTrader], db: TradingDatabase):
    """Mueve SL de Haack a breakeven y/o trailing ATR sin empeorar riesgo."""
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
                print(f"💰 Cierre temprano (Haack) {symbol}: uPnL={upnl:+.2f} USDT >= {EARLY_PROFIT_TAKE_USDT:.2f}")
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
                            print(f"🛡️ Reconciliación de salida (Haack) {symbol}: SL={bool(sl_order)} TPs={len(tp_orders)}")
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
                tf = TRAILING_ATR_TIMEFRAME or (trade.get('timeframe') or '4h')
                df = get_klines(symbol, tf, limit=max(ATR_PERIOD + 30, 140))
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
                print(f"🛡️ SL dinámico (Haack) {symbol}: {current_sl:.6f} -> {target_sl:.6f}")

    except Exception as e:
        print(f"⚠️ Error en gestión dinámica de SL (Haack): {e}")


def main():
    """Loop de escaneo con UI estilo conservador."""
    global AUTO_TRADE_ENABLED
    print("🤖 Bot EMA+Ichimoku Scanner HAACK + Auto Trading iniciado")
    print(f"📊 Monitoreando {len(WATCHLIST)} cryptos")
    print(f"⏰ Timeframes: {', '.join(TIMEFRAME_NAMES.values())}")
    print(f"📊 Base de datos: trading_history.db")
    print(f"🛡️ Risk Profile: {RISK_PROFILE_SNAPSHOT['RISK_PROFILE_SELECTED']} ({RISK_PROFILE_SNAPSHOT['RISK_ENV_MODE']})")
    print(f"   • MAX_DAILY_LOSS_USDT={RISK_PROFILE_SNAPSHOT['MAX_DAILY_LOSS_USDT']} | MAX_CONSECUTIVE_LOSSES={RISK_PROFILE_SNAPSHOT['MAX_CONSECUTIVE_LOSSES']}")
    print(f"   • MAX_DRAWDOWN_PCT={RISK_PROFILE_SNAPSHOT['MAX_DRAWDOWN_PCT']} | PAUSE_MIN={RISK_PROFILE_SNAPSHOT['RISK_GUARD_PAUSE_MINUTES']}")

    if AUTO_TRADE_ENABLED:
        print("🤖 TRADING AUTOMÁTICO ACTIVADO")
        print(f"⚡ Tipo de orden: {'MARKET' if USE_MARKET_ORDER else 'LIMIT'}")
        print(f"📈 Max posiciones simultáneas: {MAX_POSITIONS}")
    else:
        print("📢 MODO SOLO ALERTAS (trading desactivado)")

    # Filtros Haack
    print("\n🛡️ FILTROS HAACK ACTIVOS:")
    print(f"   ✅ Volumen mínimo: {MIN_VOLUME_RATIO}x promedio")
    print(f"   ✅ RSI LONG: {RSI_LONG_MIN}-{RSI_LONG_MAX}")
    print(f"   ✅ RSI SHORT: {RSI_SHORT_MIN}-{RSI_SHORT_MAX}")
    print(f"   ✅ Distancia EMAs: mín {MIN_EMA_DISTANCE*100:.2f}%")
    print(f"   ✅ SL máximo: {MAX_SL_PERCENT*100:.2f}%")
    print(f"   ✅ Tendencia EMA200: {'Requerida' if REQUIRE_EMA200_TREND else 'No requerida'}")
    print(f"   ✅ Ichimoku: Tenkan/Kijun/Kumo/Chikou (params {ICHI_TENKAN},{ICHI_KIJUN},{ICHI_SENKOUB})")
    print(f"   ✅ Score mínimo híbrido: {MIN_SCORE_TO_TRADE:.2f}")
    print(f"   ⚡ Impulsos activos en: {', '.join(IMPULSE_TFS)} | cuerpo>={int(IMPULSE_MIN_BODY_PCT*100)}% & cuerpo>= {IMPULSE_BODY_ATR_MULT}x ATR & vol>={IMPULSE_MIN_VOL_RATIO}x")
    print(f"   ✅ SL dinámico: {'ON' if DYNAMIC_SL_ENABLED else 'OFF'} | Breakeven TP1: {'ON' if BREAKEVEN_ON_TP1 else 'OFF'} | Trail ATR: {'ON' if TRAILING_ATR_ENABLED else 'OFF'} ({TRAILING_ATR_MULT}x)")
    print(f"   ✅ Cierre temprano por PnL: {'ON' if EARLY_PROFIT_TAKE_ENABLED else 'OFF'} | Umbral: {EARLY_PROFIT_TAKE_USDT:.2f} USDT")

    minutes = max(1, int(SCAN_INTERVAL_SECONDS / 60))
    print(f"\n🔄 Escaneando cada {minutes} minutos...\n")

    # Mensaje inicial a Telegram
    tf_list = ", ".join(TIMEFRAME_NAMES.values())
    mode = "🤖 TRADING AUTOMÁTICO" if AUTO_TRADE_ENABLED else "📢 SOLO ALERTAS"
    send_telegram(
        f"🚀 <b>BOT INICIADO</b>\n"
        f"🤖 Bot: <b>{BOT_NAME}</b>\n"
        f"{mode}\n"
        f"📊 Activos: {len(WATCHLIST)}\n"
        f"⏰ Timeframes: {tf_list}\n"
        f"🔄 Escaneo: cada {minutes} min"
    )

    # Inicializar componentes
    db = TradingDatabase("trading_history.db")
    risk_guard = RiskGuard(db, BOT_NAME)
    trader: Optional[BinanceFuturesTrader] = None
    if AUTO_TRADE_ENABLED:
        try:
            trader = BinanceFuturesTrader()
            # Mostrar datos de cuenta
            balance = trader.get_account_balance()
            print(f"💰 Balance: {balance:.2f} USDT")
            print(f"📊 Leverage: {trader.leverage}x")
            print(f"⚠️ Riesgo por trade: {trader.risk_percent}%")
        except Exception as e:
            print(f"⚠️ No se pudo iniciar trader (modo alerta): {e}")
            trader = None
            AUTO_TRADE_ENABLED = False
            print("📢 Auto-trading desactivado por falla de autenticación. El bot continuará solo con alertas.")

    # Loop de escaneo
    while True:
        try:
            # Mostrar posiciones antes del escaneo
            show_positions_summary(trader)
            manage_dynamic_stop_losses(trader, db)
            reconcile_closed_trades_and_notify(trader, db)

            # Escanear
            scan_once(trader, db, risk_guard=risk_guard)

            # Mostrar posiciones después del escaneo
            show_positions_summary(trader)
            manage_dynamic_stop_losses(trader, db)
            reconcile_closed_trades_and_notify(trader, db)

            print(f"\n⏳ Esperando {minutes} minutos hasta el próximo escaneo...")
            time.sleep(SCAN_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print("\n\n⚠️ Bot detenido por el usuario")
            send_telegram(
                f"⚠️ <b>BOT DETENIDO</b>\n"
                f"🤖 Bot: <b>{BOT_NAME}</b>\n"
                f"🛑 Detenido por usuario"
            )
            break
        except Exception as e:
            print(f"\n❌ Error crítico: {e}")
            send_telegram(
                f"❌ <b>BOT ERROR</b>\n"
                f"🤖 Bot: <b>{BOT_NAME}</b>\n"
                f"⚠️ Detalle: {e}"
            )
            print("⏳ Reintentando en 5 minutos...")
            time.sleep(300)


if __name__ == "__main__":
    main()
