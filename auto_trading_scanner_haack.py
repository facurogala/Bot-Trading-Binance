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


# ================== CONFIG ==================
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise ValueError("❌ Error: TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no están configurados en .env")

# Modo trading
AUTO_TRADE_ENABLED = os.getenv("AUTO_TRADE_ENABLED", "False").lower() == "true"
USE_MARKET_ORDER = os.getenv("USE_MARKET_ORDER", "False").lower() == "true"
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "6"))  # Haack: hasta 6 posiciones

# 6 timeframes (equilibrio entre reacción y estabilidad)
TIMEFRAMES = ["5m", "15m", "30m", "1h", "2h", "4h"]
TIMEFRAME_NAMES = {
    "5m": "5 minutos",
    "15m": "15 minutos",
    "30m": "30 minutos",
    "1h": "1 hora",
    "2h": "2 horas",
    "4h": "4 horas",
}

# Cliente binance solo para klines
client = Client()

# 70 coins — cobertura amplia en Futures (moderado)
WATCHLIST: List[str] = [
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
MIN_VOLUME_RATIO = 1.10

# RSI
RSI_LONG_MIN, RSI_LONG_MAX = 40, 70
RSI_SHORT_MIN, RSI_SHORT_MAX = 30, 60

# Stop/TP / Volatilidad
MAX_SL_PERCENT = 0.035        # 3.5%
MIN_ATR_PCT = 0.004           # 0.4%
MAX_ATR_PCT = 0.030           # 3.0%

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
ADX_MIN = 18
MIN_BODY_TO_RANGE = 0.5
MAX_UPWICK_FOR_LONG = 0.4
MAX_DOWNWICK_FOR_SHORT = 0.4

# Timing y confirmaciones
TIMEFRAME_ALIGNMENT = True
ALIGN_WITH = ["30m", "1h"]
MIN_TICKS_SINCE_SIGNAL = 2
BLOCK_NEWS_SPIKES = True
ALLOW_SESSION = ["UTC_10_24"]

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
    "trend_ema200": 2.0,
    "kumo_trend": 2.0,
    "tenkan_kijun_cross": 1.8,
    "tk_strength": 1.2,          # fuerte/medio/débil
    "ema20_50_cross": 1.5,
    "ema_distance": 1.0,
    "rsi_zone": 1.0,
    "volume_ratio": 1.2,
    "atr_in_range": 1.0,
    "adx": 1.0,
    "fib_confluence": 1.5,
    "sr_confluence": 0.8,
    "multi_tf_alignment": 1.0,
}
MIN_SCORE_TO_TRADE = 6.0  # ajustá según selectividad deseada

# Gestión / Frecuencia
MAX_CONCURRENT_POS = 3
COOLDOWN_AFTER_TRADE_MIN = 30
MAX_TRADES_PER_DAY = 10
POSITION_SIZE_MULT = 1.0  # Nota: informativo (ajuste fino requiere cambios en trader)
LEVERAGE_CAP = 5
PYRAMIDING = False
PARTIALS = {"TP1": 1.272, "TP2": 1.414, "TP3": 1.618}

# Intervalo entre escaneos
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "900"))

# Estado runtime (cooldown y límites diarios)
_last_trade_time: Dict[str, float] = {}           # clave: f"{symbol}:{timeframe}"
_daily_trade_count: Dict[str, int] = {}           # clave día YYYY-MM-DD


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

    # GATES
    if GATE_BLOCK_IN_KUMO and where == "inside":
        return False, 0.0, {"reason": "Precio dentro del Kumo"}
    if GATE_REQUIRE_ICHI_TREND:
        if (side=="LONG" and where=="below") or (side=="SHORT" and where=="above"):
            return False, 0.0, {"reason": "Tendencia Kumo en contra"}
    if GATE_MIN_EMA_DIST is not None and ema_distance < GATE_MIN_EMA_DIST:
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
    if side == "LONG":
        if rsi < RSI_LONG_MIN or rsi > RSI_LONG_MAX:
            reasons.append(f"❌ RSI fuera de rango LONG ({rsi:.1f} no está {RSI_LONG_MIN}-{RSI_LONG_MAX})")
            return {"passed": False, "reasons": reasons, "vol_ratio": vol_ratio, "rsi": rsi}
    else:
        if rsi < RSI_SHORT_MIN or rsi > RSI_SHORT_MAX:
            reasons.append(f"❌ RSI fuera de rango SHORT ({rsi:.1f} no está {RSI_SHORT_MIN}-{RSI_SHORT_MAX})")
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

    # ATR% dentro de rango
    atr_pct_now = atr / price if price > 0 else 0.0
    if not (MIN_ATR_PCT <= atr_pct_now <= MAX_ATR_PCT):
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
            reasons.append("❌ Mecha superior excesiva para LONG")
            return {"passed": False, "reasons": reasons}
        if side == "SHORT" and ana["down_wick_pct"] > MAX_DOWNWICK_FOR_SHORT:
            reasons.append("❌ Mecha inferior excesiva para SHORT")
            return {"passed": False, "reasons": reasons}
    if ana["body_pct"] < MIN_BODY_TO_RANGE:
        reasons.append("❌ Cuerpo pequeño en relación al rango")
        return {"passed": False, "reasons": reasons}

    # ADX
    adx_val = None
    if ADX_FILTER:
        adx_val = last_adx(df, length=14)
        if adx_val is None:
            reasons.append("❌ ADX no disponible")
            return {"passed": False, "reasons": reasons}
        if adx_val < ADX_MIN:
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
        return {
            "passed": True,
            "reasons": reasons_ok,
            "vol_ratio": vol_ratio,
            "rsi": rsi,
            "sl_distance": sl_distance,
            "score": score_total,
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
            tps = [price + TP_ATR_MULT * atr * m for m in [1.0, 0.8, 0.6]]
        else:
            tps = [price - TP_ATR_MULT * atr * m for m in [1.0, 0.8, 0.6]]
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
    }


def format_trade_message(symbol: str, side: str, levels: Dict, timeframe: str, traded: bool = False) -> str:
    s = display_symbol(symbol)
    action = "🚀 EJECUTADO" if traded else "👀 SEÑAL"
    return (
        f"{action} {side} — {s} [{timeframe}]\n"
        f"Precio: {levels['price']}\n"
        f"Entrada: {levels['entry_low']} - {levels['entry_high']}\n"
        f"SL: {levels['sl']}\n"
        f"TPs: {levels['tp1']} | {levels['tp2']} | {levels['tp3']}"
    )


def execute_trade(trader: BinanceFuturesTrader, db: TradingDatabase, symbol: str, side: str, levels: Dict, timeframe: str) -> Optional[Dict]:
    """Ejecuta el trade respetando límites y guarda en DB."""
    try:
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

        open_positions = trader.get_open_positions() if trader else []
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
        )

        _last_trade_time[key] = now
        _daily_trade_count[day] = cnt + 1
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

    # Señal tipo cruce EMA20/EMA50
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

    if side is None:
        return None

    # Alineación multi-timeframe
    if TIMEFRAME_ALIGNMENT and not timeframe_alignment_ok(symbol, side):
        return None

    # Filtros Haack (inyectamos symbol para funding)
    last = last.copy()
    last["symbol"] = symbol
    check = check_filters(side, df, last)
    if not check.get("passed", False):
        return None

    levels = build_levels(side, last, df, symbol, timeframe)
    return {"symbol": symbol, "side": side, "levels": levels, "metrics": check}


def scan_once(trader: Optional[BinanceFuturesTrader], db: TradingDatabase) -> None:
    """Escanea toda la watchlist en todos los timeframes una vez, con resumen por símbolo."""
    # Encabezado estilo conservador
    print("\n" + "="*60)
    print("🛡️ ESCANEO HAACK")
    print(f"🔍 {len(WATCHLIST)} cryptos en {len(TIMEFRAMES)} timeframes")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🤖 TRADING AUTOMÁTICO ACTIVADO" if AUTO_TRADE_ENABLED else "📢 SOLO ALERTAS")
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
                per_symbol_details.append(
                    f"[{timeframe}] {signal['side']} | Precio: {lv['price']} | SL: {lv['sl']} (-{sl_pct:.2f}%) | ATR: {atr_val:.4f} | TP: {lv['tp1']} / {lv['tp2']} / {lv['tp3']} | Score: {sc if sc is not None else '-'} | {fibtxt}/{srtxt}"
                )

                msg = format_trade_message(symbol, signal["side"], signal["levels"], timeframe, traded=False)
                send_telegram(msg)

                if AUTO_TRADE_ENABLED and trader is not None:
                    res = execute_trade(trader, db, symbol, signal["side"], signal["levels"], timeframe)
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
        # Generar gráficos completos si hay trades registrados
        dashboard = TradingDashboard("trading_history.db")
        dashboard.generate_full_report(output_dir="reports")
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


def main():
    """Loop de escaneo con UI estilo conservador."""
    print("🤖 Bot EMA+Ichimoku Scanner HAACK + Auto Trading iniciado")
    print(f"📊 Monitoreando {len(WATCHLIST)} cryptos")
    print(f"⏰ Timeframes: {', '.join(TIMEFRAME_NAMES.values())}")
    print(f"📊 Base de datos: trading_history.db")

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

    minutes = max(1, int(SCAN_INTERVAL_SECONDS / 60))
    print(f"\n🔄 Escaneando cada {minutes} minutos...\n")

    # Mensaje inicial a Telegram
    tf_list = ", ".join(TIMEFRAME_NAMES.values())
    mode = "🤖 TRADING AUTOMÁTICO" if AUTO_TRADE_ENABLED else "📢 SOLO ALERTAS"
    send_telegram(f"""🤖 <b>Bot EMA+Ichimoku HAACK Iniciado</b>\n\n{mode}\n📊 {len(WATCHLIST)} cryptos\n⏰ Timeframes: {tf_list}\n🔄 Escaneo cada {minutes} min\n\n🛡️ Filtros activos + scoring híbrido""")

    # Inicializar componentes
    db = TradingDatabase("trading_history.db")
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

    # Loop de escaneo
    while True:
        try:
            # Mostrar posiciones antes del escaneo
            show_positions_summary(trader)

            # Escanear
            scan_once(trader, db)

            # Mostrar posiciones después del escaneo
            show_positions_summary(trader)

            print(f"\n⏳ Esperando {minutes} minutos hasta el próximo escaneo...")
            time.sleep(SCAN_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print("\n\n⚠️ Bot detenido por el usuario")
            send_telegram("⚠️ Bot EMA+Ichimoku HAACK detenido")
            break
        except Exception as e:
            print(f"\n❌ Error crítico: {e}")
            send_telegram(f"❌ Bot error: {e}")
            print("⏳ Reintentando en 5 minutos...")
            time.sleep(300)


if __name__ == "__main__":
    main()
