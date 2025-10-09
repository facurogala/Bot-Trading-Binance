import os
import time
from dotenv import load_dotenv

from binance_futures_trader import BinanceFuturesTrader


def main():
    # Asegurar TESTNET y riesgo mínimo para la prueba
    os.environ.setdefault("TESTNET", "True")
    os.environ.setdefault("RISK_PERCENT", "0.3")  # riesgo muy bajo
    load_dotenv(override=False)

    trader = BinanceFuturesTrader()

    symbol = os.getenv("TP_TEST_SYMBOL", "BTCUSDT")
    side = "SHORT"

    # Tomar precio de mercado actual
    mark = float(trader.client.futures_mark_price(symbol=symbol)["markPrice"])

    # Para SHORT, ponemos una LIMIT apenas por debajo del mark para llenar rápido
    entry_price = round(mark * 0.999, 2)  # ~0.1% debajo (se redondeará a tick internamente)
    # SL más holgado (≈0.8% por encima del mark)
    sl_price = round(mark * 1.008, 2)

    # TPs más lejanos para que la posición respire (≈0.15% a 0.45% por debajo del mark)
    tp_multipliers = (0.9985, 0.9970, 0.9955)
    tp_prices = [round(mark * m, 2) for m in tp_multipliers]

    print("\n===== PRUEBA TP ADJUSTMENT (TESTNET) =====")
    print(f"Symbol: {symbol}")
    print(f"Side:   {side}")
    print(f"Mark:   {mark}")
    print(f"Entry:  {entry_price}")
    print(f"SL:     {sl_price}")
    print(f"TPs in: {tp_prices}")

    result = trader.open_position(
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        sl_price=sl_price,
        tp_prices=tp_prices,
        force_market=False,
    )

    if not result:
        print("❌ La prueba no pudo abrir posición (validación/llenado falló)")
        return

    print("\n— Resultado —")
    print(f"Entry real: {result['entry_price']}")
    print(f"SL final:   {result['sl_price']}")
    print(f"TPs final:  {result['tp_prices']}")

    # Esperar un poco y limpiar (opcional)
    time.sleep(2)
    try:
        trader.cancel_all_orders(symbol)
    except Exception:
        pass
    # Cerrar si quedó posición abierta
    try:
        trader.close_position(symbol)
    except Exception:
        pass


if __name__ == "__main__":
    main()
