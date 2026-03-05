import argparse
from typing import List

from binance.client import Client

from binance_futures_trader import BinanceFuturesTrader


def build_tp_prices(entry_price: float, sl_price: float, side: str, rr_multipliers: List[float]) -> List[float]:
    risk_distance = abs(entry_price - sl_price)
    prices = []
    for rr in rr_multipliers:
        if side == "LONG":
            prices.append(entry_price + risk_distance * rr)
        else:
            prices.append(entry_price - risk_distance * rr)
    return prices


def main() -> None:
    parser = argparse.ArgumentParser(description="Abre un trade demo inmediato en Binance Futures Testnet.")
    parser.add_argument("--symbol", default="BTCUSDT", help="Par a operar. Ej: BTCUSDT")
    parser.add_argument("--side", choices=["LONG", "SHORT"], default="LONG", help="Dirección del trade")
    parser.add_argument("--sl-pct", type=float, default=0.6, help="Distancia de SL en porcentaje (ej: 0.6 = 0.6%)")
    parser.add_argument("--rr", default="1,1.5,2", help="RR para TPs separados por coma. Ej: 1,1.5,2")
    parser.add_argument("--execute", action="store_true", help="Ejecuta realmente en testnet. Si no, solo muestra preview.")
    args = parser.parse_args()

    symbol = args.symbol.upper().strip()
    side = args.side.upper().strip()
    sl_pct = max(0.05, float(args.sl_pct)) / 100.0
    rr_multipliers = [float(x.strip()) for x in args.rr.split(",") if x.strip()]

    client = Client()
    ticker = client.get_symbol_ticker(symbol=symbol)
    entry_price = float(ticker["price"])

    if side == "LONG":
        sl_price = entry_price * (1 - sl_pct)
    else:
        sl_price = entry_price * (1 + sl_pct)

    tp_prices = build_tp_prices(entry_price, sl_price, side, rr_multipliers)

    print("\n=== DEMO TRADE PREVIEW ===")
    print(f"Symbol: {symbol}")
    print(f"Side: {side}")
    print(f"Entry (market aprox): {entry_price:.8f}")
    print(f"Stop Loss: {sl_price:.8f}")
    print("Take Profits:")
    for idx, tp in enumerate(tp_prices, 1):
        print(f"  TP{idx}: {tp:.8f}")

    if not args.execute:
        print("\nNo se ejecutó orden. Usa --execute para abrir el trade demo.")
        return

    trader = BinanceFuturesTrader()
    result = trader.open_position(
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        sl_price=sl_price,
        tp_prices=tp_prices,
        force_market=True,
    )

    if not result:
        print("\n❌ No se pudo ejecutar el trade demo.")
        return

    print("\n✅ Trade demo ejecutado")
    print(f"Entry order ID: {result['entry_order'].get('orderId')}")
    print(f"SL order ID: {result['sl_order'].get('orderId') if result.get('sl_order') else 'N/A'}")
    print(f"TP orders: {[o.get('orderId') for o in result.get('tp_orders', [])]}")


if __name__ == "__main__":
    main()
