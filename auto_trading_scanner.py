"""
Scanner automático con ejecución de trades en Binance Futures
Detecta señales EMA y ejecuta posiciones automáticamente con SL y TP
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
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "3"))  # Máximo de posiciones simultáneas

# Múltiples timeframes a analizar
TIMEFRAMES = ["3m","5m", "30m", "1h", "2h","4h","6h","12h"]
TIMEFRAME_NAMES = {
    "30m": "30 minutos",
    "1h": "1 hora",
    "2h": "2 horas",
    "4h": "4 horas",
    "6h": "6 horas",
    "12h": "12 horas"
}

client = Client()

# Cryptos a monitorear (formato Binance sin / - Solo pares disponibles en Futures)
WATCHLIST = [
    # Top principales
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    # Populares
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    "LTCUSDT", "TRXUSDT", "BCHUSDT",
    # DeFi y Layer 2
    "UNIUSDT", "NEARUSDT", "FILUSDT", "ETCUSDT",
    "OPUSDT", "ARBUSDT", "ATOMUSDT", "HBARUSDT",
    # Nuevos y prometedores
    "VETUSDT", "SUIUSDT", "APTUSDT", "GRTUSDT",
    "AAVEUSDT", "GALAUSDT", "MINAUSDT", "THETAUSDT",
    # Gaming y NFT
    "FLOWUSDT", "EGLDUSDT", "AXSUSDT", "IMXUSDT",
    "SANDUSDT", "MANAUSDT", "ENJUSDT", "APEUSDT",
    # Otros altcoins
    "QNTUSDT", "DASHUSDT", "COMPUSDT",
    "ONEUSDT", "CHZUSDT", "INJUSDT", "DYDXUSDT", "STXUSDT",
    "CRVUSDT", "KAVAUSDT", "TWTUSDT", "CAKEUSDT", "FXSUSDT",
    "GMXUSDT", "WOOUSDT", "ROSEUSDT", "KDAUSDT",
    # Adicionales
    "ZILUSDT", "RVNUSDT", "SSVUSDT",
    "ALGOUSDT", "CELOUSDT", "YFIUSDT",
    "BAKEUSDT", "GTCUSDT",
    "HIGHUSDT", "IOSTUSDT", "KNCUSDT", "LRCUSDT", "MTLUSDT",
    "OGNUSDT", "ONTUSDT", "RLCUSDT",
    "STORJUSDT", "VTHOUSDT", "XMRUSDT", "ZECUSDT"
]

# ===== PRESET AGRESIVO =====
# Risk/TP config
ATR_LEN = 14
SWING_LOOKBACK = 10
SL_ATR_BUFFER = 0.2
TP_MULTS = [1, 1.5, 2]

# Tendencia/EMAs
REQUIRE_EMA200_TREND = True  # podés poner False si querés contra-tendencia
MIN_EMA_DISTANCE = 0.0015    # 0.15%
MIN_TREND_SLOPE = 0.0005

# Volumen
MIN_VOLUME_RATIO = 1.00

# RSI
RSI_LONG_MIN, RSI_LONG_MAX = 35, 75
RSI_SHORT_MIN, RSI_SHORT_MAX = 25, 65

# Stop/TP / Volatilidad
MAX_SL_PERCENT   = 0.050    # ≤ 5.0% distancia de SL
ATR_PERIOD = 14
MIN_ATR_PCT = 0.0025        # 0.25%
MAX_ATR_PCT = 0.040         # 4.0%
SL_ATR_MULT = 1.1
TP_ATR_MULT = 2.2

# Fibonacci y Confluencias
USE_FIB = True
FIB_LOOKBACK_SWING = 90
FIB_MIN_SWING_RANGE = 0.008
FIB_RETRACEMENTS = [0.382, 0.5, 0.618, 0.786]
FIB_EXTENSIONS = [1.272, 1.414, 1.618, 2.000]
FIB_PROXIMITY_TOL = 0.0025
CONFLUENCE_WITH_EMA = True
CONFLUENCE_MAX_DIST_TO_EMA = 0.0035
CONFLUENCE_WITH_SR = True
SR_LOOKBACK = 250
SR_PROXIMITY_TOL = 0.0025
REQUIRE_WICK_REJECTION = False
REQUIRE_CLOSE_IN_DIRECTION = True

# Estructura / Momentum
STRUCT_REQUIRE_HH_HL = False
STRUCT_SWING_DEPTH = 2
ADX_FILTER = True
ADX_MIN = 14
MIN_BODY_TO_RANGE = 0.40
MAX_UPWICK_FOR_LONG = 0.5
MAX_DOWNWICK_FOR_SHORT = 0.5

# Timing y confirmaciones
TIMEFRAME_ALIGNMENT = False
ALIGN_WITH = ["30m"]
MIN_TICKS_SINCE_SIGNAL = 1
BLOCK_NEWS_SPIKES = False
ALLOW_SESSION = ["UTC_00_24"]

# Perps/Funding
USE_FUNDING_BIAS = True
MAX_POSITIVE_FUNDING = 0.08
MIN_NEGATIVE_FUNDING = -0.08

# Score
USE_SIGNAL_SCORE = True
SCORE_WEIGHTS = {
    "trend_EMA200": 1.5,
    "ema_distance": 0.8,
    "fib_confluence": 1.8,
    "rsi_zone": 0.8,
    "volume_ratio": 1.2,
    "atr_in_range": 0.8,
    "structure_HH_HL": 0.8,
    "adx": 0.8
}
MIN_SCORE_TO_TRADE = 3.5

# Gestión / Frecuencia
MAX_CONCURRENT_POS = 4
COOLDOWN_AFTER_TRADE_MIN = 10
MAX_TRADES_PER_DAY = 18
POSITION_SIZE_MULT = 1.3
LEVERAGE_CAP = 8
PYRAMIDING = True
PARTIALS = {"TP1": 1.272, "TP2": 1.414, "TP3": 1.618, "TP4": 2.000}

# Estado runtime
_last_trade_time = {}
_daily_trade_count = {}

def check_filters(side: str, df: pd.DataFrame, last_row) -> dict:
    """Verifica filtros preset agresivo con scoring y confluencias."""
    reasons = []
    price = float(last_row["close"]) if "close" in last_row else float(last_row.close)

    # Volumen
    vol_now = float(df["volume"].iloc[-1])
    vol_avg20 = float(df["volume"].tail(20).mean())
    vol_ratio = vol_now / vol_avg20 if vol_avg20 > 0 else 0.0
    if vol_ratio < MIN_VOLUME_RATIO:
        reasons.append(f"❌ Volumen bajo ({vol_ratio:.2f}x < {MIN_VOLUME_RATIO:.2f}x)")
        return {"passed": False, "reasons": reasons}

    # Distancia EMAs
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

    # Tendencia EMA200 (opcional)
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

    # ATR% rango
    atr_series = ta.atr(df["high"], df["low"], df["close"], length=ATR_PERIOD)
    atrp = float(atr_series.iloc[-1]) / price if price else 0.0
    if not (MIN_ATR_PCT <= atrp <= MAX_ATR_PCT):
        reasons.append(f"❌ ATR fuera de rango ({atrp*100:.2f}% no en {MIN_ATR_PCT*100:.2f}-{MAX_ATR_PCT*100:.2f}%)")
        return {"passed": False, "reasons": reasons}

    # SL razonable
    atr_series = ta.atr(df["high"], df["low"], df["close"], length=ATR_LEN)
    atr = float(atr_series.iloc[-1]) if len(atr_series) > 0 else 0.0
    recent_lows = df["low"].tail(SWING_LOOKBACK).min()
    recent_highs = df["high"].tail(SWING_LOOKBACK).max()
    sl = (recent_lows - SL_ATR_BUFFER * atr) if side == "LONG" else (recent_highs + SL_ATR_BUFFER * atr)
    sl_distance = abs(price - sl) / price if price else 0.0
    if sl_distance > MAX_SL_PERCENT:
        reasons.append(f"❌ SL muy amplio ({sl_distance*100:.2f}% > {MAX_SL_PERCENT*100:.1f}%)")
        return {"passed": False, "reasons": reasons}

    # Confluencias: Fib/EMA/SR
    fib_conf = 0.0
    ema_conf = 0.0
    sr_conf = 0.0
    # Fib retracements contra el swing
    try:
        w = df.tail(FIB_LOOKBACK_SWING)
        hi = float(w['high'].max()); lo = float(w['low'].min())
        rng = (hi - lo) / hi if hi else 0.0
        if rng >= FIB_MIN_SWING_RANGE:
            rets = [hi - (hi - lo) * r for r in FIB_RETRACEMENTS] if side=='LONG' else [lo + (hi - lo) * r for r in FIB_RETRACEMENTS]
            if any(abs(price - lv)/price <= FIB_PROXIMITY_TOL for lv in rets):
                fib_conf = 1.0
    except Exception:
        pass
    if abs(price - (ema20 if side=='LONG' else ema50))/price <= CONFLUENCE_MAX_DIST_TO_EMA:
        ema_conf = 1.0
    # SR pivots
    try:
        w = df.tail(SR_LOOKBACK)
        highs = w['high'].rolling(3).apply(lambda x: float(x[1] > x[0] and x[1] > x[2]))
        lows  = w['low'].rolling(3).apply(lambda x: float(x[1] < x[0] and x[1] < x[2]))
        lvls = []
        for i in range(2, len(w)):
            if highs.iloc[i] == 1.0: lvls.append(float(w['high'].iloc[i]))
            if lows.iloc[i] == 1.0:  lvls.append(float(w['low'].iloc[i]))
        if any(abs(price - lv)/price <= SR_PROXIMITY_TOL for lv in lvls):
            sr_conf = 1.0
    except Exception:
        pass

    # Score
    score = 0.0
    if USE_SIGNAL_SCORE:
        score += SCORE_WEIGHTS.get("trend_EMA200", 0) * (1.0 if (not REQUIRE_EMA200_TREND or price >= ta.ema(df['close'], length=200).iloc[-1]) == (side=='LONG') else 0)
        score += SCORE_WEIGHTS.get("ema_distance", 0) * min(1.0, ema_distance / MIN_EMA_DISTANCE)
        score += SCORE_WEIGHTS.get("fib_confluence", 0) * (1.0 if (fib_conf+ema_conf+sr_conf)>=1.0 else 0.0)
        score += SCORE_WEIGHTS.get("rsi_zone", 0) * 1.0
        score += SCORE_WEIGHTS.get("volume_ratio", 0) * min(1.5, vol_ratio)/1.5
        score += SCORE_WEIGHTS.get("atr_in_range", 0) * 1.0
        score += SCORE_WEIGHTS.get("structure_HH_HL", 0) * (0.5 if not STRUCT_REQUIRE_HH_HL else 1.0)
        if ADX_FILTER:
            adx = float(ta.adx(df['high'], df['low'], df['close'], length=14)['ADX_14'].iloc[-1])
            score += SCORE_WEIGHTS.get("adx", 0) * min(1.0, adx/50.0)

    if USE_SIGNAL_SCORE and score < MIN_SCORE_TO_TRADE:
        reasons.append(f"❌ Score insuficiente ({score:.2f} < {MIN_SCORE_TO_TRADE:.2f})")
        return {"passed": False, "reasons": reasons}

    return {"passed": True, "reasons": [
        f"✅ Volumen: {vol_ratio:.2f}x",
        f"✅ EMAs separadas: {ema_distance*100:.2f}%",
        f"✅ RSI: {rsi:.1f}",
        f"✅ SL razonable: {sl_distance*100:.2f}%",
        f"✅ Confluencias: {'Sí' if (fib_conf+ema_conf+sr_conf)>=1.0 else 'No'}",
        f"✅ Score: {score:.2f}",
    ], 'score': score}

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

# Inicializar base de datos
db = TradingDatabase("trading_history.db")
print("✅ Base de datos de trading inicializada")

# Diccionario para rastrear trades abiertos
open_trades_registry = {}  # {symbol: trade_id}

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

    # Calcular vol_ratio PRIMERO (antes de usarlo)
    vol_now = float(df["volume"].iloc[-1])
    vol_avg20 = float(df["volume"].tail(20).mean())
    vol_ratio = vol_now / vol_avg20 if vol_avg20 > 0 else 1.0

    # Ajustar SL dinámicamente según volatilidad (vol_ratio)
    # Si vol_ratio > 1 -> ampliar buffer; si <1 -> reducir
    vol_scale = 1.0
    if vol_ratio > 1.0:
        vol_scale = 1.0 + (vol_ratio - 1.0)  # ejemplo: vol_ratio 1.5 => scale 1.5
    else:
        vol_scale = max(0.7, vol_ratio)  # no reducir demasiado, mínimo 0.7

    sl_buffer = SL_ATR_BUFFER * vol_scale

    if side == "LONG":
        sl = recent_lows - sl_buffer * atr
    else:
        sl = recent_highs + sl_buffer * atr

    # TPs según ATR preset
    if side == 'LONG':
        tps = [price + TP_ATR_MULT * atr * m for m in [1.0, 0.8, 0.6]]
    else:
        tps = [price - TP_ATR_MULT * atr * m for m in [1.0, 0.8, 0.6]]

    if vol_ratio < 0.8:
        vol_hint = "Volumen bajo: posible falta de impulso 🟡"
    elif vol_ratio < 1.5:
        vol_hint = "Volumen normal: señal aceptable ⚪"
    else:
        vol_hint = "Alto volumen: buen momentum 🟢"

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
        'atr': atr
    }

def format_trade_message(symbol: str, side: str, levels: dict, timeframe: str, traded: bool = False):
    """Formatea el mensaje de alerta/ejecución"""
    sy = display_symbol(symbol)
    tf_name = TIMEFRAME_NAMES.get(timeframe, timeframe)
    dec = levels['decimals']
    fmt = f"{{:.{dec}f}}"
    
    status = "🤖 <b>TRADE EJECUTADO</b>" if traded else "🚨 <b>SEÑAL DETECTADA</b>"
    
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
    
    return message

def execute_trade(symbol: str, side: str, levels: dict, timeframe: str):
    """Ejecuta el trade en Binance Futures y lo registra en la base de datos"""
    if not AUTO_TRADE_ENABLED or trader is None:
        return False
    
    try:
        # Verificar número de posiciones abiertas
        open_positions = trader.get_open_positions()
        
        # Verificar si ya hay una posición en este símbolo
        for pos in open_positions:
            if pos['symbol'] == symbol:
                print(f"⚠️ Ya existe una posición abierta en {symbol}, omitiendo...")
                return False
        
        if len(open_positions) >= MAX_POSITIONS:
            print(f"⚠️ Máximo de posiciones alcanzado ({MAX_POSITIONS}), omitiendo...")
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
            # Registrar en la base de datos
            trade_id = db.add_trade(
                symbol=symbol,
                side=side,
                entry_price=result['entry_price'],
                quantity=result['quantity'],
                leverage=result['leverage'],
                sl_price=result['sl_price'],
                tp_prices=result['tp_prices'],
                timeframe=timeframe,
                notes=f"Señal EMA - {timeframe}",
                bot="Scanner"
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
            
            if result.get('sl_order'):
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
                    price=result['tp_prices'][i-1],
                    status="NEW"
                )
            
            # Guardar referencia al trade
            open_trades_registry[symbol] = trade_id
            
            # Iniciar monitoreo con el trade_id correcto si el reconciler está disponado
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
            
            print(f"✅ Trade ejecutado y registrado: {symbol} {side} (ID: {trade_id})")
            return True
        else:
            print(f"❌ No se pudo ejecutar el trade en {symbol}")
            return False
            
    except Exception as e:
        print(f"❌ Error al ejecutar trade: {e}")
        return False

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

    if signal in ("BUY", "SELL"):
        # Filtros de calidad (laxos)
        filters = check_filters(side, df, last)
        if not filters.get('passed', False):
            return None
        levels = build_levels(side, last, df, symbol, timeframe)
        
        # Intentar ejecutar el trade
        traded = False
        if AUTO_TRADE_ENABLED:
            traded = execute_trade(symbol, side, levels, timeframe)
        
        # Enviar mensaje a Telegram
        message = format_trade_message(symbol, side, levels, timeframe, traded)
        send_telegram(message)
        
        return {
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "timeframe": timeframe,
            "signal": signal,
            "side": side,
            "traded": traded,
            "levels": levels
        }
    
    return None

def scan_once():
    """Escanea todas las cryptos en múltiples timeframes"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*60}")
    print(f"🔍 Escaneando {len(WATCHLIST)} cryptos en {len(TIMEFRAMES)} timeframes")
    print(f"📅 {timestamp}")
    if AUTO_TRADE_ENABLED:
        print(f"🤖 TRADING AUTOMÁTICO ACTIVADO")
    else:
        print(f"📢 MODO SOLO ALERTAS")
    print(f"{'='*60}")
    print(f"🛡️ Filtros activos (Agresivo):")
    print(f"   ✅ EMA200 requerida: {'Sí' if REQUIRE_EMA200_TREND else 'No'} | Dist EMAs ≥ {MIN_EMA_DISTANCE*100:.2f}% | Slope ≥ {MIN_TREND_SLOPE*100:.2f}%")
    print(f"   ✅ Volumen mínimo: {MIN_VOLUME_RATIO}x | RSI L: {RSI_LONG_MIN}-{RSI_LONG_MAX} / S: {RSI_SHORT_MIN}-{RSI_SHORT_MAX}")
    print(f"   ✅ SL máx: {MAX_SL_PERCENT*100:.1f}% | ATR% [{MIN_ATR_PCT*100:.2f}–{MAX_ATR_PCT*100:.2f}%]")
    print(f"   ✅ Fib: {'ON' if USE_FIB else 'OFF'} | Confluencias EMA/SR: {CONFLUENCE_WITH_EMA}/{CONFLUENCE_WITH_SR}")
    print(f"   ✅ ADX≥{ADX_MIN} | Estructura HH/HL: {'Sí' if STRUCT_REQUIRE_HH_HL else 'No'}")
    print(f"   ✅ Scoring min: {MIN_SCORE_TO_TRADE}")
    print(f"{'='*60}")
    
    signals_found = 0
    trades_executed = 0
    
    for symbol in WATCHLIST:
        symbol_has_signal = False
        
        for timeframe in TIMEFRAMES:
            try:
                result = analyze(symbol, timeframe)
                if result:
                    tf_name = TIMEFRAME_NAMES.get(timeframe, timeframe)
                    status = "ejecutado" if result.get('traded') else "detectado"
                    print(f"🚨 {display_symbol(symbol)} [{tf_name}]: {result['signal']} → {status}")
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
                print(f"❌ {symbol} [{timeframe}]: error → {e}")
        
        if not symbol_has_signal:
            print(f"   {display_symbol(symbol)}: Sin señales")
    
    print(f"\n✅ Escaneo completado: {signals_found} señal(es) detectada(s)")
    if AUTO_TRADE_ENABLED:
        print(f"🤖 Trades ejecutados: {trades_executed}")
    
    # 📊 GENERAR REPORTES AUTOMÁTICAMENTE
    generar_reportes_automaticos()
    
    return signals_found, trades_executed

def check_closed_positions():
    """Verifica si hay posiciones cerradas y actualiza la base de datos"""
    if not AUTO_TRADE_ENABLED or trader is None:
        return
    
    # Obtener posiciones activas en Binance
    current_positions = trader.get_open_positions()
    current_symbols = {pos['symbol'] for pos in current_positions}
    
    # Verificar si alguna posición registrada ya no está abierta
    closed_symbols = []
    for symbol, trade_id in open_trades_registry.items():
        if symbol not in current_symbols:
            # La posición se cerró
            closed_symbols.append(symbol)
            
            # Obtener precio actual para calcular PnL
            try:
                ticker = client.get_symbol_ticker(symbol=symbol)
                exit_price = float(ticker['price'])
                
                # Cerrar el trade en la base de datos
                db.close_trade(trade_id, exit_price, "AUTO_CLOSED")
                print(f"✅ Trade cerrado y registrado: {symbol} (ID: {trade_id})")
            except Exception as e:
                print(f"⚠️ Error al cerrar trade {trade_id} en BD: {e}")
    
    # Limpiar el registro
    for symbol in closed_symbols:
        del open_trades_registry[symbol]

def show_positions_summary():
    """Muestra un resumen de las posiciones abiertas"""
    if not AUTO_TRADE_ENABLED or trader is None:
        return
    
    # Verificar posiciones cerradas primero
    check_closed_positions()
    
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
    
    # Mostrar estadísticas generales de la base de datos
    stats = db.get_trade_stats()
    if stats['total_trades'] > 0:
        print(f"📊 ESTADÍSTICAS HISTÓRICAS:")
        print(f"  Total trades cerrados: {stats['total_trades']}")
        print(f"  Win rate: {stats['win_rate']:.1f}%")
        print(f"  PnL histórico total: ${stats['total_pnl']:.2f}\n")

def main():
    """Loop infinito que escanea cada 30 minutos"""
    print("🤖 Bot EMA Scanner + Auto Trading iniciado")
    print(f"📊 Monitoreando {len(WATCHLIST)} cryptos")
    print(f"⏰ Timeframes: {', '.join(TIMEFRAME_NAMES.values())}")
    print(f"📊 Base de datos: trading_history.db")
    print(f"📈 Reportes automáticos: Activados")
    
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
    
    print(f"🔄 Escaneando cada 30 minutos...\n")
    
    # Mensaje inicial
    tf_list = ", ".join(TIMEFRAME_NAMES.values())
    mode = "🤖 TRADING AUTOMÁTICO" if AUTO_TRADE_ENABLED else "📢 SOLO ALERTAS"
    send_telegram(f"""🤖 <b>Bot EMA Auto Trading Iniciado</b>

{mode}
📊 {len(WATCHLIST)} cryptos
⏰ Timeframes: {tf_list}
🔄 Escaneo cada 30 min""")
    
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
            send_telegram("⚠️ Bot EMA Auto Trading detenido")
            break
        except Exception as e:
            print(f"\n❌ Error crítico: {e}")
            send_telegram(f"❌ Bot error: {e}")
            print("⏳ Reintentando en 5 minutos...")
            time.sleep(120)

if __name__ == "__main__":
    main()
