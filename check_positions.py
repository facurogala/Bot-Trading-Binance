from binance_futures_trader import BinanceFuturesTrader

trader = BinanceFuturesTrader()
positions = trader.get_open_positions()

print("\n📊 POSICIONES ABIERTAS:")
if positions:
    for p in positions:
        print(f"  • {p['symbol']}: {p['side']} | Qty: {p['quantity']} | Entry: ${p['entryPrice']:.5f}")
        print(f"    PnL: {p['unrealizedProfit']:+.2f} USDT")
        if p.get('stopLoss'):
            print(f"    🔴 SL: ${p['stopLoss']:.5f}")
        if p.get('takeProfits'):
            for i, tp in enumerate(p['takeProfits'], 1):
                print(f"    🟢 TP{i}: ${tp:.5f}")
else:
    print("  ⚠️ No hay posiciones abiertas")
