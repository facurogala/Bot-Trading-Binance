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

# 🛡️ FILTROS CONSERVADORES
MIN_VOLUME_RATIO = 1.2        # Volumen mínimo: 1.2x el promedio (20% más)
MIN_EMA_DISTANCE = 0.005      # Distancia mínima entre EMAs: 0.5% del precio
MAX_SL_PERCENT = 0.025        # Stop Loss máximo: 2.5% del precio
RSI_LONG_MIN = 45             # RSI mínimo para LONG
RSI_LONG_MAX = 65             # RSI máximo para LONG
RSI_SHORT_MIN = 35            # RSI mínimo para SHORT
RSI_SHORT_MAX = 55            # RSI máximo para SHORT
REQUIRE_EMA200_TREND = True   # Requiere operar a favor de EMA200
REQUIRE_MULTI_TF = False      # Requiere confirmación en múltiples TF (más estricto)

# Risk/TP config
ATR_LEN = 14
SWING_LOOKBACK = 10
SL_ATR_BUFFER = 0.2
TP_MULTS = [1.5, 2.5, 3.5]    # TPs más conservadores (más distantes)
# ============================================

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
    
    # 5️⃣ Filtro de STOP LOSS (calculado previamente)
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
    
    # ✅ Todos los filtros pasados
    return {
        'passed': True, 
        'reasons': [
            f"✅ Volumen: {vol_ratio:.2f}x",
            f"✅ EMAs separadas: {ema_distance*100:.2f}%",
            f"✅ RSI: {rsi:.1f}",
            f"✅ SL razonable: {sl_distance*100:.2f}%"
        ],
        'vol_ratio': vol_ratio,
        'rsi': rsi,
        'sl_distance': sl_distance
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

    if vol_ratio < 1.0:
        vol_hint = "Volumen bajo 🟡"
    elif vol_ratio < 1.5:
        vol_hint = "Volumen normal ⚪"
    else:
        vol_hint = "Alto volumen 🟢"

    return {
        'entry_price': price,
        'entry_high': entry_high,
        'entry_low': entry_low,
        'sl_price': sl,
        'tp_prices': tps,
        'vol_ratio': vol_ratio,
        'vol_hint': vol_hint,
        'price': price,
        'decimals': dec
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
            print(f"✅ Trade ejecutado: {symbol} {side}")
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
        # 🛡️ VERIFICAR FILTROS CONSERVADORES
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
    print(f"🛡️ Filtros activos:")
    print(f"   ✅ Volumen mínimo: {MIN_VOLUME_RATIO}x")
    print(f"   ✅ RSI LONG: {RSI_LONG_MIN}-{RSI_LONG_MAX}")
    print(f"   ✅ RSI SHORT: {RSI_SHORT_MIN}-{RSI_SHORT_MAX}")
    print(f"   ✅ SL máximo: {MAX_SL_PERCENT*100}%")
    print(f"   ✅ Tendencia EMA200: {'Sí' if REQUIRE_EMA200_TREND else 'No'}")
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
    
    while True:
        try:
            # Mostrar posiciones antes del escaneo
            show_positions_summary()
            
            # Escanear
            signals, trades = scan_once()
            
            # Mostrar posiciones después del escaneo
            show_positions_summary()
            
            # Esperar 30 minutos (1800 segundos)
            print(f"\n⏳ Esperando 30 minutos hasta el próximo escaneo...")
            time.sleep(1800)
            
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
