import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

import pandas as pd
import pandas_ta as ta
from dotenv import load_dotenv
from binance.client import Client

from binance_futures_trader import BinanceFuturesTrader
from trading_database import TradingDatabase

from auto_closer import AutoCloser
from trade_monitor import TradeMonitor
from trailing_stop_manager import TrailingStopManager, TrailingConfig
from notifier import send_telegram as _notifier_send

load_dotenv()


def _float_env(default: float, *keys: str) -> float:
    """Return first valid float found in env vars fallback chain."""
    for key in keys:
        val = os.getenv(key)
        if val is None or str(val).strip() == "":
            continue
        try:
            return float(val)
        except ValueError:
            print(f"⚠️ Valor inválido en {key}='{val}'. Usando {default}.")
    return float(default)


BOT_NAME = "GridLax"
MESSAGE_PREFIX = os.getenv("GRID_MESSAGE_PREFIX", "[GRID-LAX]")
STATUS_PREFIX = os.getenv("GRID_STATUS_PREFIX", "[GRID-LAX-STATUS]")
DB_PATH = os.getenv("TRADING_DB_PATH", "trading_history.db")
BOT_ID = os.getenv("BOT_ID_GRID_LAX") or f"GRID-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{os.getpid()}"

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise ValueError("❌ Error: TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no están configurados en .env")

AUTO_TRADE_ENABLED = os.getenv("AUTO_TRADE_ENABLED_GRID_LAX", os.getenv("AUTO_TRADE_ENABLED", "False")).lower() == "true"
USE_MARKET_ORDER = os.getenv("GRID_USE_MARKET_ORDER", os.getenv("USE_MARKET_ORDER", "False")).lower() == "true"
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS_GRID_LAX", os.getenv("MAX_POSITIONS", "4")))

BASE_TIMEFRAME = os.getenv("GRID_BASE_TIMEFRAME", "1h")
RANGE_LOOKBACK = max(60, int(os.getenv("GRID_RANGE_LOOKBACK", "240")))
RANGE_SMOOTH = max(1, int(os.getenv("GRID_RANGE_SMOOTH", "12")))
MIN_RANGE_PCT = max(0.0, _float_env(0.012, "GRID_MIN_RANGE_PCT", "GRID_RANGE_MIN_PCT"))
MAX_RANGE_PCT = max(_float_env(0.08, "GRID_MAX_RANGE_PCT", "GRID_RANGE_MAX_PCT"), MIN_RANGE_PCT + 1e-6)

GRID_LEVELS = max(2, int(os.getenv("GRID_LEVELS", "12")))
LEVELS_PER_SIDE = max(1, GRID_LEVELS // 2)
GRID_LEVELS = LEVELS_PER_SIDE * 2
TP_PERCENT = max(0.0, _float_env(0.006, "GRID_TP_PERCENT", "GRID_TP_PCT"))
MASTER_STOP_PERCENT = _float_env(0.012, "GRID_MASTER_STOP_PERCENT", "GRID_STOP_PCT")
LEVEL_NOTIONAL_USD = _float_env(15.0, "GRID_LEVEL_NOTIONAL_USD", "LEVEL_NOTIONAL_USD")

LEVEL_COOLDOWN_SECONDS = max(0, int(os.getenv("GRID_LEVEL_COOLDOWN_SECONDS", "120")))
ENTRY_BUFFER_PCT = max(0.0, _float_env(0.0015, "GRID_ENTRY_BUFFER_PCT", "ENTRY_BUFFER_PCT"))
ENTRY_RELEASE_PCT = max(0.0, _float_env(0.0025, "GRID_ENTRY_RELEASE_PCT", "ENTRY_RELEASE_PCT"))
INNER_RANGE_RATIO = max(0.0, _float_env(0.18, "GRID_INNER_RANGE_RATIO", "GRID_CORE_RATIO"))
MASTER_STOP_PERCENT = max(MASTER_STOP_PERCENT, 0.0)

MAX_TREND_SLOPE = max(0.0, _float_env(0.0012, "GRID_MAX_TREND_SLOPE", "MAX_TREND_SLOPE"))
EMA_DISTANCE_MAX = max(0.0, _float_env(0.02, "GRID_EMA_DISTANCE_MAX", "EMA_DISTANCE_MAX"))
RSI_NEUTRAL_LOW = _float_env(45.0, "GRID_RSI_NEUTRAL_LOW", "RSI_NEUTRAL_LOW")
RSI_NEUTRAL_HIGH = _float_env(55.0, "GRID_RSI_NEUTRAL_HIGH", "RSI_NEUTRAL_HIGH")
MAX_ADX = max(0.0, _float_env(18.0, "GRID_MAX_ADX", "MAX_ADX"))

ATR_PERIOD = int(os.getenv("GRID_ATR_PERIOD", "14"))
ATR_MIN_PCT = max(0.0, _float_env(0.001, "GRID_ATR_MIN_PCT", "ATR_MIN_PCT"))
ATR_MAX_PCT = max(ATR_MIN_PCT + 1e-6, _float_env(0.008, "GRID_ATR_MAX_PCT", "ATR_MAX_PCT"))

if RSI_NEUTRAL_HIGH < RSI_NEUTRAL_LOW:
    RSI_NEUTRAL_LOW, RSI_NEUTRAL_HIGH = RSI_NEUTRAL_HIGH, RSI_NEUTRAL_LOW

TP_NOTIFY_LIMIT = max(1, int(os.getenv("GRID_TP_NOTIFY_LIMIT", "120")))
TP_PARTIALS = (0.5, 0.3, 0.2)

DEFAULT_GRID_SYMBOLS = [
    "ALGOUSDT", "AVAXUSDT", "BTCUSDT", "CRVUSDT", "ENSUSDT", "FILUSDT",
    "GRTUSDT", "KAVAUSDT", "LINKUSDT", "NEARUSDT", "RENDERUSDT", "SNXUSDT",
    "SUSHIUSDT", "TRXUSDT", "ZECUSDT", "1000CHEEMSUSDT", "ACHUSDT", "AIXBTUSDT",
    "ANKRUSDT", "ARPAUSDT", "AUCTIONUSDT", "AXLUSDT", "BANDUSDT", "BEAMXUSDT",
    "BMTUSDT", "CETUSUSDT", "COOKIEUSDT", "CYBERUSDT", "DOLOUSDT", "EIGENUSDT",
    "ETHFIUSDT", "GMTUSDT", "HOOKUSDT", "ILVUSDT", "JASMYUSDT", "KAITOUSDT",
    "LINEAUSDT", "MAGICUSDT", "MBOXUSDT", "MORPHOUSDT", "NEOUSDT", "NOTUSDT",
    "ONDOUSDT", "PARTIUSDT", "PEOPLEUSDT", "PNUTUSDT", "REDUSDT", "ROSEUSDT",
    "SCRTUSDT", "SKLUSDT", "SSVUSDT", "STRKUSDT", "SXTUSDT", "TOWNSUSDT",
    "TSTUSDT", "UMAUSDT", "VETUSDT", "WLDUSDT", "XAIUSDT", "XVGUSDT",
    "ZKUSDT",
]


WATCHLIST_ENV = [s.strip().upper() for s in os.getenv("GRID_WATCHLIST", "").split(",") if s.strip()]
if WATCHLIST_ENV:
    WATCHLIST = WATCHLIST_ENV
else:
    WATCHLIST = DEFAULT_GRID_SYMBOLS

STARTUP_JITTER_RANGE = (
    _float_env(2.0, "GRID_JITTER_MIN", "STARTUP_JITTER_MIN", "JITTER_MIN"),
    _float_env(5.0, "GRID_JITTER_MAX", "STARTUP_JITTER_MAX", "JITTER_MAX"),
)

client = Client()

db = TradingDatabase(DB_PATH)
trader: Optional[BinanceFuturesTrader] = None
auto_closer: Optional[AutoCloser] = None
trailing_manager: Optional[TrailingStopManager] = None
trade_monitor: Optional[TradeMonitor] = None

TRAILING_ENABLED = os.getenv("GRID_TRAILING_ENABLED", "True").lower() == "true"
TRAILING_TRIGGER_PCT = _float_env(0.003, "GRID_TRAILING_TRIGGER_PCT", "GRID_TRAIL_TRIGGER")
TRAILING_STEP_PCT = _float_env(0.0015, "GRID_TRAILING_STEP_PCT", "GRID_TRAIL_STEP")
TRAILING_MAX_LOCK_PCT = _float_env(0.007, "GRID_TRAILING_MAX_LOCK_PCT", "GRID_TRAIL_MAX_LOCK")
TRAILING_BE_BUFFER_PCT = _float_env(0.0002, "GRID_TRAILING_BE_BUFFER", "GRID_TRAIL_BE_BUFFER")
TRAILING_GUARD_PCT = _float_env(0.0004, "GRID_TRAILING_GUARD_PCT", "GRID_TRAIL_GUARD")
TRAILING_GUARD_TICKS = int(os.getenv("GRID_TRAILING_GUARD_TICKS", os.getenv("TRAILING_GUARD_TICKS", "2")))
TRAILING_MIN_IMPROVEMENT_PCT = _float_env(0.0002, "GRID_TRAILING_MIN_IMPROVEMENT_PCT", "TRAILING_MIN_IMPROVEMENT_PCT")
TRAILING_NOTIFY = os.getenv("GRID_TRAILING_NOTIFY", "False").lower() == "true"

if AUTO_TRADE_ENABLED:
    try:
        trader = BinanceFuturesTrader(context=BOT_NAME)
    except Exception as exc:
        print(f"❌ No se pudo inicializar trader: {exc}")
        AUTO_TRADE_ENABLED = False
        trader = None

if AUTO_TRADE_ENABLED and trader is not None:
    try:
        auto_closer = AutoCloser(trader, db, bot_name=BOT_NAME)
        auto_closer.start()
    except Exception as exc:
        auto_closer = None
        print(f"⚠️ AutoCloser no pudo iniciar: {exc}")

    if TRAILING_ENABLED:
        try:
            trailing_config = TrailingConfig(
                mode="dynamic",
                start_tp=1,
                dynamic_method=os.getenv("GRID_TRAILING_METHOD", os.getenv("TRAILING_METHOD_DEFAULT", "atr")),
                atr_period=int(os.getenv("GRID_TRAILING_ATR_PERIOD", os.getenv("TRAILING_ATR_PERIOD", "14"))),
                atr_mult=_float_env(1.1, "GRID_TRAILING_ATR_MULT", "TRAILING_ATR_MULT"),
                ema_period=int(os.getenv("GRID_TRAILING_EMA_PERIOD", os.getenv("TRAILING_EMA_PERIOD", "34"))),
                swing_lookback=int(os.getenv("GRID_TRAILING_SWING_LOOKBACK", os.getenv("TRAILING_SWING_LOOKBACK", "5"))),
                min_improvement_pct=TRAILING_MIN_IMPROVEMENT_PCT,
                break_even_buffer_pct=TRAILING_BE_BUFFER_PCT,
                lock_tp_buffer_pct=_float_env(0.0, "GRID_TRAILING_LOCK_BUFFER", "TRAILING_LOCK_BUFFER"),
                guard_ticks=TRAILING_GUARD_TICKS,
                timeframe_fallback=os.getenv("GRID_TRAILING_TIMEFRAME", BASE_TIMEFRAME),
                allow_notifications=TRAILING_NOTIFY
            )
            trailing_manager = TrailingStopManager(
                trader=trader,
                db=db,
                bot_name=BOT_NAME,
                config=trailing_config,
                notify_func=None
            )
            if TRAILING_NOTIFY:
                try:
                    trailing_manager.notify = send_telegram
                except Exception:
                    pass
        except Exception as exc:
            trailing_manager = None
            print(f"⚠️ TrailingStopManager no pudo iniciar: {exc}")

    try:
        trade_monitor = TradeMonitor(
            trader,
            db,
            bot_name=BOT_NAME,
            trailing_manager=trailing_manager,
            tp_callback=register_tp_hit
        )
        trade_monitor.start()
    except Exception as exc:
        trade_monitor = None
        print(f"⚠️ TradeMonitor no pudo iniciar: {exc}")


@dataclass
class GridLevel:
    index: int
    price: float
    tp: float
    sl: float
    side: str
    active: bool = False
    trade_id: Optional[int] = None
    position_id: Optional[str] = None
    quantity: Optional[float] = None
    entry_price: Optional[float] = None
    last_trigger_at: float = 0.0
    trail_stage: int = 0
    tp_targets: List[float] = field(default_factory=list)
    tp_hits: Set[int] = field(default_factory=set)


@dataclass
class GridSnapshot:
    range_low: float
    range_high: float
    mid: float
    levels: Dict[str, List[GridLevel]]


@dataclass
class SymbolState:
    activated: bool = False
    snapshot: Optional[GridSnapshot] = None
    last_activation_alert: float = 0.0
    last_break_alert: float = 0.0
    last_summary_day: str = ""


_grid_states: Dict[str, SymbolState] = {}
_recent_closed_cache: Dict[int, datetime] = {}


def get_state(symbol: str) -> SymbolState:
    return _grid_states.setdefault(symbol, SymbolState())


def decimals_for(symbol: str) -> int:
    if symbol.endswith("USDT"):
        return 4 if symbol.startswith("1000") else 3
    if symbol.endswith("BTC"):
        return 6
    return 5


def display_symbol(symbol: str) -> str:
    if symbol.endswith("USDT"):
        return f"{symbol[:-4]}/USDT"
    if symbol.endswith("BTC"):
        return f"{symbol[:-3]}/BTC"
    return symbol


def send_telegram(message: str) -> None:
    if not message.startswith(MESSAGE_PREFIX) and not message.startswith(STATUS_PREFIX):
        message = f"{MESSAGE_PREFIX} {message}"
    try:
        _notifier_send(message)
    except Exception as exc:
        print(f"⚠️ Telegram error: {exc}")


def countdown(seconds: int) -> None:
    remaining_total = max(int(seconds), 0)
    for remaining in range(remaining_total, 0, -1):
        mins, secs = divmod(remaining, 60)
        print(f"\r⌛ Próximo escaneo en {mins:02d}:{secs:02d}", end="", flush=True)
        time.sleep(1)
    print("\r⌛ Próximo escaneo en 00:00        ")
    print()


def get_klines(symbol: str, interval: str, limit: int = 220) -> pd.DataFrame:
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
    ])
    if df.empty:
        raise ValueError("klines vacíos")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df[["timestamp", "open", "high", "low", "close", "volume"]].dropna()
    return df


def build_tp_targets(entry_price: float, side: str) -> List[float]:
    base_pct = max(TP_PERCENT, 0.0)
    step_pct = TRAILING_STEP_PCT if TRAILING_STEP_PCT > 0 else base_pct / 2 if base_pct > 0 else 0.001
    boosts = [0.0, step_pct, step_pct * 2]
    targets: List[float] = []
    for extra in boosts:
        adj = base_pct + extra
        if side == "LONG":
            targets.append(entry_price * (1 + adj))
        else:
            targets.append(entry_price * (1 - adj))
    if side == "LONG":
        targets = sorted({max(t, 1e-9) for t in targets})
    else:
        targets = sorted({max(t, 1e-9) for t in targets}, reverse=True)
    return targets


def compute_range(df: pd.DataFrame) -> Optional[GridSnapshot]:
    if len(df) < max(RANGE_LOOKBACK, RANGE_SMOOTH) + 10:
        return None
    window = df.tail(RANGE_LOOKBACK)
    if window.empty:
        return None
    smooth = window[["high", "low"]].rolling(RANGE_SMOOTH).mean().dropna()
    if smooth.empty:
        return None
    high = float(smooth["high"].max())
    low = float(smooth["low"].min())
    if high <= 0 or low <= 0 or high <= low:
        return None
    mid = (high + low) / 2
    width_pct = (high - low) / mid
    if width_pct < MIN_RANGE_PCT or width_pct > MAX_RANGE_PCT:
        return None
    if LEVELS_PER_SIDE <= 0:
        return None
    step = (high - low) / GRID_LEVELS
    if step <= 0:
        return None
    levels: Dict[str, List[GridLevel]] = {"LONG": [], "SHORT": []}
    for idx in range(LEVELS_PER_SIDE):
        offset = (idx + 0.5) * step
        long_price = mid - offset
        short_price = mid + offset
        if long_price > 0:
            long_targets = build_tp_targets(long_price, "LONG")
            levels["LONG"].append(GridLevel(
                index=idx + 1,
                price=long_price,
                tp=long_targets[0] if long_targets else long_price * (1 + TP_PERCENT),
                sl=long_price * (1 - MASTER_STOP_PERCENT),
                side="LONG",
                tp_targets=long_targets
            ))
        short_targets = build_tp_targets(short_price, "SHORT")
        levels["SHORT"].append(GridLevel(
            index=idx + 1,
            price=short_price,
            tp=short_targets[0] if short_targets else short_price * (1 - TP_PERCENT),
            sl=short_price * (1 + MASTER_STOP_PERCENT),
            side="SHORT",
            tp_targets=short_targets
        ))
    return GridSnapshot(range_low=low, range_high=high, mid=mid, levels=levels)


def merge_snapshot(state: SymbolState, snapshot: GridSnapshot) -> None:
    prev = state.snapshot
    if not prev:
        state.snapshot = snapshot
        return
    merged_levels: Dict[str, List[GridLevel]] = {"LONG": [], "SHORT": []}
    for side in ("LONG", "SHORT"):
        old_map = {lvl.index: lvl for lvl in prev.levels.get(side, [])}
        for lvl in snapshot.levels.get(side, []):
            keep = old_map.get(lvl.index)
            if keep and keep.active:
                keep.price = lvl.price
                keep.tp = lvl.tp
                keep.sl = lvl.sl
                keep.tp_targets = lvl.tp_targets
                merged_levels[side].append(keep)
            else:
                merged_levels[side].append(lvl)
    state.snapshot = GridSnapshot(
        range_low=snapshot.range_low,
        range_high=snapshot.range_high,
        mid=snapshot.mid,
        levels=merged_levels
    )


def activation_needed(state: SymbolState, price: float) -> bool:
    if not state.snapshot:
        return False
    now = time.time()
    if not state.activated:
        return True
    if price < state.snapshot.range_low or price > state.snapshot.range_high:
        return False
    if now - state.last_activation_alert > 600:
        return True
    return False


def send_activation(symbol: str, state: SymbolState, price: float) -> None:
    if not state.snapshot:
        return
    dec = decimals_for(symbol)
    fmt = f"{{:.{dec}f}}"
    total_levels = sum(len(state.snapshot.levels[s]) for s in ("LONG", "SHORT"))
    per_side = len(state.snapshot.levels["LONG"])
    print(
        f"⚙️ {display_symbol(symbol)} activado: rango {fmt.format(state.snapshot.range_low)}-"
        f"{fmt.format(state.snapshot.range_high)} con {total_levels} niveles ({per_side} por lado)."
    )
    state.activated = True
    state.last_activation_alert = time.time()


def send_break(symbol: str, state: SymbolState, price: float, direction: str) -> None:
    if not state.snapshot:
        return
    dec = decimals_for(symbol)
    fmt = f"{{:.{dec}f}}"
    diffusion = price - state.snapshot.range_high if direction == "UP" else state.snapshot.range_low - price
    diff_pct = diffusion / state.snapshot.range_high if direction == "UP" else diffusion / state.snapshot.range_low
    range_edge = state.snapshot.range_high if direction == "UP" else state.snapshot.range_low
    trend_side = "arriba" if direction == "UP" else "abajo"
    comparison = ">" if direction == "UP" else "<"
    print(
        f"🚨 {display_symbol(symbol)} rompió el rango por {trend_side}: precio {fmt.format(price)} {comparison} "
        f"{fmt.format(range_edge)} ({diff_pct * 100:+.2f}%). Grid desactivado."
    )
    state.last_break_alert = time.time()
    state.activated = False
    try:
        send_telegram(
            f"{STATUS_PREFIX} 🚨 {display_symbol(symbol)} rompió el rango por {trend_side}."
            f" Se desactiva la malla hasta nuevo rango."
        )
    except Exception:
        pass


def execute_level(symbol: str, timeframe: str, level: GridLevel) -> Optional[int]:
    if not AUTO_TRADE_ENABLED or trader is None:
        return None
    try:
        entry_price = float(client.futures_mark_price(symbol=symbol)["markPrice"])
    except Exception:
        entry_price = level.price
    if level.side == "LONG" and entry_price <= 0:
        entry_price = level.price
    if level.side == "SHORT" and entry_price <= 0:
        entry_price = level.price
    sl_price = level.sl
    if not level.tp_targets:
        level.tp_targets = build_tp_targets(level.price, level.side)
    tp_targets = level.tp_targets[:len(TP_PARTIALS)] or [level.tp]
    if len(tp_targets) < len(TP_PARTIALS):
        # replicate last target to fill ladder if needed
        tp_targets.extend([tp_targets[-1]] * (len(TP_PARTIALS) - len(tp_targets)))
    try:
        result = trader.execute_protected_entry(
            symbol=symbol,
            side=level.side,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_prices=tp_targets,
            db=db,
            bot_name=BOT_NAME,
            bot_id=BOT_ID,
            timeframe=timeframe,
            notes=f"grid_level_{level.side.lower()}_{level.index}",
            force_market=USE_MARKET_ORDER,
            risk_amount_usd=LEVEL_NOTIONAL_USD,
            context="grid",
            max_positions=MAX_POSITIONS,
            tp_allocations=list(TP_PARTIALS)
        )
    except Exception as exc:
        print(f"❌ No se pudo ejecutar nivel {symbol} {level.side} #{level.index}: {exc}")
        return None
    if not result:
        return None
    bundle = result.get("order_bundle") or {}
    level.trade_id = result.get("trade_id")
    level.position_id = bundle.get("position_id")
    level.quantity = bundle.get("quantity")
    level.entry_price = bundle.get("entry_price") or entry_price
    sl_committed = bundle.get("sl_price")
    if sl_committed:
        try:
            level.sl = float(sl_committed)
        except Exception:
            pass
    tp_prices = bundle.get("tp_prices") or []
    if tp_prices:
        try:
            level.tp = float(tp_prices[0])
        except Exception:
            pass
        try:
            level.tp_targets = [float(p) for p in tp_prices]
        except Exception:
            pass
    level.active = True
    level.last_trigger_at = time.time()
    level.trail_stage = 0
    level.tp_hits.clear()
    if trade_monitor and level.trade_id:
        try:
            trade_monitor.register_trade(symbol, level.trade_id)
        except Exception as monitor_exc:
            print(f"⚠️ TradeMonitor no pudo registrar {symbol}: {monitor_exc}")
    return level.trade_id


def send_order_execution(symbol: str, level: GridLevel) -> None:
    dec = decimals_for(symbol)
    fmt = f"{{:.{dec}f}}"
    qty = level.quantity or (LEVEL_NOTIONAL_USD / max(level.price, 1e-9))
    side_levels_list = state_levels(symbol, level.side)
    other_side = state_levels(symbol, "LONG" if level.side == "SHORT" else "SHORT")
    remaining_this_side = sum(1 for lv in side_levels_list if not lv.active)
    remaining_other_side = sum(1 for lv in other_side if not lv.active)
    orientation = "abajo" if level.side == "LONG" else "arriba"
    counterpart_orientation = "arriba" if level.side == "LONG" else "abajo"
    targets = level.tp_targets or [level.tp]
    tp_lines = []
    for idx, target in enumerate(targets[:len(TP_PARTIALS)], 1):
        alloc = TP_PARTIALS[idx - 1] if idx - 1 < len(TP_PARTIALS) else 0
        tp_lines.append(f"TP{idx} ({alloc*100:.0f}%): {fmt.format(target)}")
    tp_block = "\n".join(tp_lines)
    message = (
        f"✅ ORDEN EJECUTADA\n"
        f"{display_symbol(symbol)} — {level.side}\n\n"
        f"💎 Entrada: {fmt.format(level.entry_price or level.price)}\n"
        f"📦 Cantidad: {qty:.4f} (≈{LEVEL_NOTIONAL_USD:.2f} USDT)\n"
        f"🎯 Objetivos:\n{tp_block}\n"
        f"📊 Niveles pendientes: {remaining_this_side}/{len(side_levels_list)} {orientation}, "
        f"{remaining_other_side}/{len(other_side)} {counterpart_orientation}"
    )
    send_telegram(message)


def send_manual_alert(symbol: str, level: GridLevel, price: float) -> None:
    dec = decimals_for(symbol)
    fmt = f"{{:.{dec}f}}"
    side_levels_list = state_levels(symbol, level.side)
    other_side = state_levels(symbol, "LONG" if level.side == "SHORT" else "SHORT")
    remaining_this_side = sum(1 for lv in side_levels_list if not lv.active)
    remaining_other_side = sum(1 for lv in other_side if not lv.active)
    orientation = "abajo" if level.side == "LONG" else "arriba"
    counterpart_orientation = "arriba" if level.side == "LONG" else "abajo"
    targets = level.tp_targets or build_tp_targets(level.price, level.side)
    tp_lines = []
    for idx, target in enumerate(targets[:len(TP_PARTIALS)], 1):
        alloc = TP_PARTIALS[idx - 1] if idx - 1 < len(TP_PARTIALS) else 0
        tp_lines.append(f"TP{idx} ({alloc*100:.0f}%): {fmt.format(target)}")
    tp_block = "\n".join(tp_lines)
    message = (
        f"🔔 POSIBLE ENTRADA\n"
        f"{display_symbol(symbol)} — {level.side}\n\n"
        f"💎 Nivel: {fmt.format(price)} (target {fmt.format(level.price)})\n"
        f"🎯 Objetivos sugeridos:\n{tp_block}\n"
        f"🛑 Stop sugerido: {fmt.format(level.sl)}\n"
        f"📊 Pendientes: {remaining_this_side}/{len(side_levels_list)} {orientation}, "
        f"{remaining_other_side}/{len(other_side)} {counterpart_orientation}"
    )
    send_telegram(message)


def state_levels(symbol: str, side: str) -> List[GridLevel]:
    snap = get_state(symbol).snapshot
    if not snap:
        return []
    return snap.levels.get(side, [])


def register_tp_hit(trade_id: int, tp_index: int, new_sl: Optional[float]) -> None:
    for symbol, state in _grid_states.items():
        snap = state.snapshot
        if not snap:
            continue
        for side in ("LONG", "SHORT"):
            for level in snap.levels.get(side, []):
                if level.trade_id == trade_id:
                    level.tp_hits.add(tp_index)
                    if new_sl is not None:
                        level.sl = new_sl
                    elif tp_index == 1 and level.entry_price:
                        level.sl = level.entry_price
                    return


def monitor_closed_trades() -> None:
    global _recent_closed_cache
    try:
        trades = db.get_trades_by_bot(BOT_NAME, limit=TP_NOTIFY_LIMIT)
    except Exception as exc:
        print(f"⚠️ No se pudo obtener trades cerrados: {exc}")
        return
    for trade in trades:
        trade_id = trade.get("id")
        if not trade_id or trade_id in _recent_closed_cache:
            continue
        exit_time = trade.get("exit_time")
        if exit_time is None:
            continue
        try:
            exit_dt = datetime.fromisoformat(exit_time) if isinstance(exit_time, str) else exit_time
        except Exception:
            exit_dt = datetime.now()
        if exit_dt < datetime.now() - timedelta(days=2):
            _recent_closed_cache[trade_id] = exit_dt
            continue
        symbol = trade.get("symbol", "")
        side = (trade.get("side") or "").upper()
        pnl = float(trade.get("pnl") or 0)
        entry_price = float(trade.get("entry_price") or 0)
        exit_price = float(trade.get("exit_price") or 0)
        qty = float(trade.get("quantity") or 0)
        dec = decimals_for(symbol)
        fmt = f"{{:.{dec}f}}"
        target_levels = state_levels(symbol, side)
        match_level = None
        for lvl in target_levels:
            if abs((lvl.price - entry_price) / max(lvl.price, 1e-9)) <= ENTRY_RELEASE_PCT * 2:
                match_level = lvl
                break
        action = "TP" if pnl >= 0 else "Stop"
        benefit = f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"
        symbol_display = display_symbol(symbol)
        reposition_note = ""
        if match_level:
            direction = "BUY" if side == "LONG" else "SELL"
            reposition_note = f" | Reposición {direction} {fmt.format(match_level.price)}"
            match_level.active = False
            match_level.trade_id = None
            match_level.quantity = None
            match_level.entry_price = None
            match_level.last_trigger_at = 0.0
            match_level.trail_stage = 0
            match_level.tp_hits.clear()
        console_msg = (
            f"ℹ️ {symbol_display} cierre {action}: {benefit} USDT @ {fmt.format(exit_price)}, "
            f"tamaño {qty:.4f}, entrada {fmt.format(entry_price)}{reposition_note}"
        )
        print(console_msg)
        _recent_closed_cache[trade_id] = exit_dt
    # cleanup cache
    cutoff = datetime.now() - timedelta(days=3)
    _recent_closed_cache = {tid: ts for tid, ts in _recent_closed_cache.items() if ts >= cutoff}


def should_trigger(level: GridLevel, price: float) -> bool:
    if level.active:
        return False
    if level.last_trigger_at and (time.time() - level.last_trigger_at) < LEVEL_COOLDOWN_SECONDS:
        return False
    if level.side == "LONG":
        trigger_price = level.price * (1 + ENTRY_BUFFER_PCT)
        return price <= trigger_price
    trigger_price = level.price * (1 - ENTRY_BUFFER_PCT)
    return price >= trigger_price


def refresh_level_states(symbol: str, price: float) -> None:
    state = get_state(symbol)
    if not state.snapshot:
        return
    tolerance = ENTRY_RELEASE_PCT
    open_positions = []
    if trader:
        try:
            open_positions = trader.get_open_positions()
        except Exception as exc:
            print(f"⚠️ No se pudieron obtener posiciones: {exc}")
    group: Dict[str, List[Dict]] = {}
    for pos in open_positions:
        sym = pos.get("symbol")
        if sym != symbol:
            continue
        side = (pos.get("side") or "").upper()
        group.setdefault(side, []).append(pos)
    for side in ("LONG", "SHORT"):
        for level in state.snapshot.levels.get(side, []):
            if level.active:
                matched = False
                for pos in group.get(side, []):
                    try:
                        entry = float(pos.get("entryPrice") or 0)
                    except Exception:
                        entry = 0
                    if entry <= 0:
                        continue
                    if abs((entry - (level.entry_price or level.price)) / entry) <= tolerance:
                        matched = True
                        break
                if not matched:
                    level.active = False
                    level.trade_id = None
                    level.quantity = None
                    level.entry_price = None
                    level.trail_stage = 0
                    level.tp_hits.clear()


def maybe_trail_levels(symbol: str, fallback_price: float) -> None:
    if not (AUTO_TRADE_ENABLED and TRAILING_ENABLED and trailing_manager and trader):
        return

    state = get_state(symbol)
    if not state.snapshot:
        return

    try:
        mark_data = client.futures_mark_price(symbol=symbol)
        mark_price = float(mark_data.get("markPrice")) if mark_data else float("nan")
    except Exception:
        mark_price = float("nan")

    if not mark_price or mark_price != mark_price:
        mark_price = fallback_price

    if mark_price <= 0:
        return

    for side in ("LONG", "SHORT"):
        for level in state.snapshot.levels.get(side, []):
            if not level.active or not level.trade_id or not level.entry_price:
                continue
            if not level.tp_targets:
                level.tp_targets = build_tp_targets(level.price, side)
            if 1 not in level.tp_hits:
                continue

            try:
                entry = float(level.entry_price)
            except Exception:
                continue
            if entry <= 0:
                continue

            profit_pct = (mark_price - entry) / max(entry, 1e-9) if side == "LONG" else (entry - mark_price) / max(entry, 1e-9)
            if profit_pct <= max(TRAILING_TRIGGER_PCT, 0.0):
                continue
            if TRAILING_STEP_PCT <= 0:
                continue

            stages_over_trigger = (profit_pct - TRAILING_TRIGGER_PCT) / TRAILING_STEP_PCT
            stage_target = int(stages_over_trigger) + 1
            if stage_target <= level.trail_stage:
                continue

            lock_pct = TRAILING_BE_BUFFER_PCT + stage_target * TRAILING_STEP_PCT
            max_lock_margin = profit_pct - TRAILING_GUARD_PCT
            if max_lock_margin > 0:
                lock_pct = min(lock_pct, max_lock_margin)
            lock_pct = min(lock_pct, TRAILING_MAX_LOCK_PCT)

            if lock_pct <= 0:
                continue

            candidate = entry * (1 + lock_pct) if side == "LONG" else entry * (1 - lock_pct)

            try:
                new_sl = trailing_manager._commit_stop_update(
                    symbol=symbol,
                    side=side,
                    trade_id=int(level.trade_id),
                    new_target=candidate,
                    entry_price=entry,
                    previous_sl=level.sl,
                    order_id=None,
                    tp_index=stage_target,
                    position_id=level.position_id,
                )
            except Exception as exc:
                print(f"⚠️ Trailing stop fallo para {symbol}: {exc}")
                continue

            if new_sl is None:
                continue

            level.sl = new_sl
            level.trail_stage = stage_target


def run_symbol(symbol: str) -> None:
    state = get_state(symbol)
    try:
        df = get_klines(symbol, BASE_TIMEFRAME, limit=RANGE_LOOKBACK + 60)
    except Exception as exc:
        print(f"⚠️ {symbol}: no se pudieron obtener klines ({exc})")
        return

    closes = df["close"].astype(float)
    if closes.isna().any():
        closes = closes.dropna()
    min_required = max(200, RANGE_LOOKBACK)
    if len(closes) < min_required:
        print(f"ℹ️ {symbol}: historial insuficiente para filtros avanzados")
        return

    ema200 = closes.ewm(span=200, adjust=False).mean()
    ema_current = float(ema200.iloc[-1]) if not ema200.empty else 0.0
    ema_prev = float(ema200.diff().iloc[-1]) if ema200.size > 1 else 0.0
    if ema_current <= 0:
        print(f"ℹ️ {symbol}: EMA200 inválida, se omite")
        return
    slope = abs(ema_prev / ema_current)
    if slope > MAX_TREND_SLOPE:
        print(f"ℹ️ {symbol}: tendencia (slope {slope*100:.2f}%), grid omitido")
        return

    ema_distance = abs(closes.iloc[-1] - ema_current) / ema_current
    if ema_distance > EMA_DISTANCE_MAX:
        print(f"ℹ️ {symbol}: precio {ema_distance*100:.2f}% alejado de EMA200, grid omitido")
        return

    rsi_series = ta.rsi(closes, length=14)
    rsi_value = float(rsi_series.iloc[-1]) if not rsi_series.empty else None
    if rsi_value is None:
        print(f"ℹ️ {symbol}: RSI no disponible")
        return
    if rsi_value < RSI_NEUTRAL_LOW or rsi_value > RSI_NEUTRAL_HIGH:
        print(f"ℹ️ {symbol}: RSI {rsi_value:.1f} fuera de zona neutra {RSI_NEUTRAL_LOW}-{RSI_NEUTRAL_HIGH}")
        return

    highs = df["high"].astype(float)
    lows = df["low"].astype(float)
    adx_df = ta.adx(highs, lows, closes, length=14)
    adx_value = None
    if adx_df is not None and not adx_df.empty:
        adx_cols = [c for c in adx_df.columns if c.upper().startswith("ADX")]
        if adx_cols:
            adx_value = float(adx_df[adx_cols[0]].iloc[-1])
    if adx_value is None or adx_value != adx_value:
        print(f"ℹ️ {symbol}: ADX no disponible")
        return
    if adx_value > MAX_ADX:
        print(f"ℹ️ {symbol}: ADX {adx_value:.1f} indica tendencia, grid omitido")
        return

    atr_series = ta.atr(highs, lows, closes, length=ATR_PERIOD)
    if atr_series is None or atr_series.empty:
        print(f"ℹ️ {symbol}: ATR no disponible")
        return
    atr_value = float(atr_series.iloc[-1])
    price = float(df["close"].iloc[-1])
    if price <= 0 or atr_value <= 0:
        print(f"ℹ️ {symbol}: datos ATR inválidos")
        return
    atr_pct = atr_value / price
    if atr_pct < ATR_MIN_PCT or atr_pct > ATR_MAX_PCT:
        print(
            f"ℹ️ {symbol}: ATR% {atr_pct*100:.2f}% fuera de rango {ATR_MIN_PCT*100:.2f}-{ATR_MAX_PCT*100:.2f}%."
        )
        return

    snapshot = compute_range(df)
    if not snapshot:
        print(f"ℹ️ {symbol}: sin rango lateral válido")
        return

    width = snapshot.range_high - snapshot.range_low
    if width <= 0:
        return
    core_ratio = max(0.0, min(INNER_RANGE_RATIO, 0.45))
    inner_low = snapshot.range_low + width * core_ratio
    inner_high = snapshot.range_high - width * core_ratio
    if price < inner_low or price > inner_high:
        print(f"ℹ️ {symbol}: precio en bordes de rango, grid omitido")
        return

    merge_snapshot(state, snapshot)
    refresh_level_states(symbol, price)
    maybe_trail_levels(symbol, price)
    upper_limit = state.snapshot.range_high * (1 + MASTER_STOP_PERCENT)
    lower_limit = state.snapshot.range_low * (1 - MASTER_STOP_PERCENT)
    if price >= upper_limit:
        send_break(symbol, state, price, "UP")
        return
    if price <= lower_limit:
        send_break(symbol, state, price, "DOWN")
        return
    if activation_needed(state, price):
        send_activation(symbol, state, price)
    for side in ("LONG", "SHORT"):
        for level in state.snapshot.levels.get(side, []):
            if should_trigger(level, price):
                if AUTO_TRADE_ENABLED:
                    trade_id = execute_level(symbol, BASE_TIMEFRAME, level)
                    if trade_id:
                        send_order_execution(symbol, level)
                else:
                    level.last_trigger_at = time.time()
                    send_manual_alert(symbol, level, price)


def maybe_send_summary(symbol: str) -> None:
    state = get_state(symbol)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.last_summary_day == today:
        return
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        trades = db.get_trades_by_symbol(symbol)
    except Exception as exc:
        print(f"⚠️ No se pudo obtener trades para resumen ({symbol}): {exc}")
        return
    daily: List[dict] = []
    total: List[dict] = []
    for trade in trades:
        bot_tag = trade.get("bot") or ""
        notes = trade.get("notes") or ""
        if BOT_NAME not in (bot_tag or "") and BOT_NAME not in notes:
            continue
        exit_time = trade.get("exit_time")
        if exit_time is None:
            continue
        try:
            exit_dt = datetime.fromisoformat(exit_time) if isinstance(exit_time, str) else exit_time
        except Exception:
            continue
        total.append(trade)
        exit_dt_aware = exit_dt
        if exit_dt_aware.tzinfo is None:
            exit_dt_aware = exit_dt_aware.replace(tzinfo=timezone.utc)
        exit_dt_aware = exit_dt_aware.astimezone(timezone.utc)
        if exit_dt_aware >= start:
            daily.append(trade)
    if not daily:
        return
    total_trades = len(daily)
    wins = sum(1 for t in daily if float(t.get("pnl") or 0) > 0)
    losses = sum(1 for t in daily if float(t.get("pnl") or 0) < 0)
    pnl_day = sum(float(t.get("pnl") or 0) for t in daily)
    pnl_total = sum(float(t.get("pnl") or 0) for t in total)
    roi_base = LEVEL_NOTIONAL_USD * max(total_trades, 1)
    roi_pct = (pnl_day / roi_base) * 100 if roi_base > 0 else 0.0
    message = (
        f"ℹ️ {display_symbol(symbol)} resumen diario: {total_trades} trades (W:{wins}/L:{losses}), "
        f"ROI {roi_pct:+.2f}%, acumulado {pnl_total:+.2f} USDT"
    )
    print(message)
    state.last_summary_day = today


def run_scan_once() -> None:
    print("\n" + "=" * 60)
    print("⚙️ ESCANEO GRID LAX")
    print(f"🔍 {len(WATCHLIST)} símbolos en {BASE_TIMEFRAME}")
    print(datetime.now(timezone.utc).strftime("📅 %Y-%m-%d %H:%M:%S UTC"))
    print("🤖 TRADING AUTOMÁTICO ACTIVADO" if AUTO_TRADE_ENABLED else "📢 MODO SOLO ALERTAS")
    print("=" * 60)
    for symbol in WATCHLIST:
        try:
            run_symbol(symbol)
        except Exception as exc:
            print(f"❌ Error en símbolo {symbol}: {exc}")
    monitor_closed_trades()
    for symbol in WATCHLIST:
        maybe_send_summary(symbol)


def main() -> None:
    print("🚀 Bot GRID LAX iniciado")
    print(f"📊 Monitoreando {len(WATCHLIST)} símbolos")
    print(f"⏰ Timeframe base: {BASE_TIMEFRAME}")
    print(f"📊 Base de datos: {DB_PATH}")
    print("🤖 Auto trading: ON" if AUTO_TRADE_ENABLED else "📢 Solo alertas")
    # Send a startup notification to Telegram (best-effort)
    try:
        msg = (
            f"{STATUS_PREFIX} 🚀 {BOT_NAME} iniciado. Monitoreando {len(WATCHLIST)} símbolos en {BASE_TIMEFRAME}."
        )
        # call local send_telegram wrapper which will fallback-check env and log failures
        send_telegram(msg)
    except Exception as exc:
        # Do not fail startup if Telegram notification can't be sent
        print(f"⚠️ Error enviando notificación de inicio a Telegram: {exc}")
    jitter_min, jitter_max = STARTUP_JITTER_RANGE
    if jitter_max < jitter_min:
        jitter_min, jitter_max = jitter_max, jitter_min
    jitter_delay = random.uniform(jitter_min, jitter_max)
    print(f"⏳ Jitter inicial: esperando {jitter_delay:.2f}s antes del primer escaneo")
    time.sleep(jitter_delay)
    try:
        while True:
            run_scan_once()
            interval = int(os.getenv("GRID_SCAN_INTERVAL_SECONDS", "300"))
            wait_seconds = max(interval, 300)
            countdown(wait_seconds)
    except KeyboardInterrupt:
        print("🛑 Grid LAX detenido manualmente")


if __name__ == "__main__":
    main()
