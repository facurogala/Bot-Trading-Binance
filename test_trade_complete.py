"""
Script de prueba completo con reconciliación de órdenes SL/TP

Demuestra:
1. Cálculo de niveles dinámicos según volatilidad
2. Apertura de posición MARKET
3. Reconciliación automática de órdenes SL/TP
4. Monitoreo periódico
5. Verificación en Binance

Uso:
  python test_trade_complete.py [SYMBOL] [SIDE]

Ejemplo:
  python test_trade_complete.py BTCUSDT LONG
"""
import sys
import os
import time
from binance_futures_trader import BinanceFuturesTrader
from binance.client import Client
import pandas as pd
import pandas_ta as ta

# Config
ATR_LEN = 14
SWING_LOOKBACK = 10
SL_ATR_BUFFER = 0.2
TP_MULTS = [1, 1.5, 2]

def get_klines(symbol, interval="15m", limit=200):
    client = Client()
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        "timestamp","open","high","low","close","volume",
        "close_time","quote_asset_volume","number_of_trades",
        "taker_buy_base_asset_volume","taker_buy_quote_asset_volume","ignore"
    ])
    for col in ["open","high","low","close","volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')
    return df[["timestamp","open","high","low","close","volume"]].dropna()

def decimals_for(symbol: str) -> int:
    return 5 if symbol.endswith("USDT") else 8

def build_levels(side: str, last_row, df, symbol: str):
    dec = decimals_for(symbol)
    atr_series = ta.atr(df["high"], df["low"], df["close"], length=ATR_LEN)
    atr = float(atr_series.iloc[-1])
    
    ema20 = float(last_row["EMA20"])
    ema50 = float(last_row["EMA50"])
    price = float(last_row["close"])
    
    recent_lows = df["low"].tail(SWING_LOOKBACK).min()
    recent_highs = df["high"].tail(SWING_LOOKBACK).max()
    
    vol_now = float(df["volume"].iloc[-1])
    vol_avg20 = float(df["volume"].tail(20).mean())
    vol_ratio = vol_now / vol_avg20 if vol_avg20 > 0 else 1.0
    
    # Ajuste dinámico de SL
    vol_scale = 1.0 + (vol_ratio - 1.0) if vol_ratio > 1.0 else max(0.7, vol_ratio)
    sl_buffer = SL_ATR_BUFFER * vol_scale
    
    sl = recent_lows - sl_buffer * atr if side == "LONG" else recent_highs + sl_buffer * atr
    
    # TPs basados en risk-reward
    sl_distance_pct = abs(price - sl) / price if price > 0 else 0.0
    tps = []
    for m in TP_MULTS:
        tp = price + (sl_distance_pct * price * m) if side == 'LONG' else price - (sl_distance_pct * price * m)
        tps.append(tp)
    
    vol_hint = ("Volumen bajo 🟡" if vol_ratio < 0.8 else 
                "Volumen normal ⚪" if vol_ratio < 1.5 else 
                "Alto volumen 🟢")
    
    return {
        'entry_price': price, 'sl_price': sl, 'tp_prices': tps,
        'vol_ratio': vol_ratio, 'vol_hint': vol_hint, 'price': price,
        'decimals': dec, 'atr': atr, 'sl_distance_pct': sl_distance_pct * 100
    }

def main():
    symbol = sys.argv[1].upper() if len(sys.argv) > 1 else 'BTCUSDT'
    side = sys.argv[2].upper() if len(sys.argv) > 2 else 'LONG'
    
    if side not in ['LONG', 'SHORT']:
        print("❌ SIDE debe ser LONG o SHORT")
        return
    
    print("="*70)
    print(f"🧪 TEST COMPLETO: {side} en {symbol} (con reconciliación)")
    print("="*70)
    
    # Trader
    try:
        trader = BinanceFuturesTrader()
        balance = trader.get_account_balance()
        print(f"\n💰 Balance: {balance:.2f} USDT")
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    # Datos
    print(f"\n📊 Obteniendo datos...")
    try:
        df = get_klines(symbol, "15m", 300)
        if len(df) < 60:
            print("❌ Datos insuficientes")
            return
        
        df["EMA20"] = ta.ema(df["close"], length=20)
        df["EMA50"] = ta.ema(df["close"], length=50)
        last_row = df.iloc[-1]
        print(f"✅ Precio: ${float(last_row['close']):.4f}")
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    # Niveles
    print(f"\n📈 Calculando niveles...")
    levels = build_levels(side, last_row, df, symbol)
    
    print(f"\n{'='*70}")
    print("📊 NIVELES (ajustados por riesgo/volatilidad)")
    print(f"{'='*70}")
    print(f"Precio: ${levels['price']:.6f} | ATR: ${levels['atr']:.6f}")
    print(f"Volatilidad: {levels['vol_ratio']:.2f}x | {levels['vol_hint']}")
    print(f"\n🔴 SL: ${levels['sl_price']:.6f} | Dist: {levels['sl_distance_pct']:.2f}%")
    for i, tp in enumerate(levels['tp_prices'], 1):
        dist = abs(tp - levels['price']) / levels['price'] * 100
        print(f"🟢 TP{i}: ${tp:.6f} | R:R {TP_MULTS[i-1]}:1 (+{dist:.2f}%)")
    print(f"{'='*70}\n")
    
    # Confirmar
    confirm = input(f"⚠️ ¿Abrir posición {side}? (si/no): ")
    if confirm.lower() not in ['si', 's', 'yes', 'y']:
        print("❌ Cancelado")
        return
    
    # Abrir
    print(f"\n🚀 Abriendo posición...")
    try:
        result = trader.open_position(
            symbol=symbol,
            side=side,
            entry_price=levels['entry_price'],
            sl_price=levels['sl_price'],
            tp_prices=levels['tp_prices'],
            force_market=True
        )
        
        if result:
            print(f"\n{'='*70}")
            print("✅ POSICIÓN ABIERTA CON RECONCILIACIÓN")
            print(f"{'='*70}")
            print(f"Symbol: {result['symbol']} | Side: {result['side']}")
            print(f"Qty: {result['quantity']} | Entry: ${result['entry_price']:.6f}")
            print(f"Leverage: {result['leverage']}x")
            print(f"\n📋 Entry Order: {result['entry_order'].get('orderId')}")
            if result.get('sl_order'):
                print(f"🔴 SL Order: {result['sl_order'].get('orderId')}")
            for i, tp in enumerate(result.get('tp_orders', []), 1):
                print(f"🟢 TP{i} Order: {tp.get('orderId')}")
            print(f"{'='*70}\n")
            
            # Esperar un poco para que el monitoreo inicie
            print("⏳ Esperando 3s antes de verificar...")
            time.sleep(3)
            
            # Debug
            print("\n🔍 Verificando órdenes en Binance...\n")
            import subprocess
            subprocess.run([sys.executable, "debug_orders.py", symbol])
            
            print(f"\n{'='*70}")
            print("✅ TEST COMPLETADO")
            print(f"{'='*70}")
            print("📌 Las órdenes SL/TP están en Binance con:")
            print("   • reduceOnly=True en TPs")
            print("   • closePosition=True en SL (implica reduce-only)")
            print("   • Monitoreo activo por 2 minutos")
            print("   • Cancelación recíproca cuando se ejecute una")
            print(f"{'='*70}\n")
        else:
            print("❌ No se pudo abrir")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
