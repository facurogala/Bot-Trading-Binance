import os
import time
from dotenv import load_dotenv

from binance_futures_trader import BinanceFuturesTrader


def main():
    # Configuración para una prueba larga en TESTNET
    os.environ.setdefault("TESTNET", "True")
    os.environ.setdefault("RISK_PERCENT", "0.3")  # riesgo muy bajo
    os.environ.setdefault("ENABLE_ORDER_MONITORING", "True")
    os.environ.setdefault("ORDER_MONITOR_DURATION", "900")  # 15 min
    os.environ.setdefault("ORDER_MONITOR_INTERVAL", "20")
    load_dotenv(override=False)

    trader = BinanceFuturesTrader(context="tp_adjustment_testnet_long")

    symbol = os.getenv("TP_TEST_SYMBOL", "BTCUSDT")
    side = os.getenv("TP_TEST_SIDE", "SHORT").upper()  # SHORT por defecto

    mark = float(trader.client.futures_mark_price(symbol=symbol)["markPrice"])

    if side == "LONG":
        # LONG: entry ~0.1% arriba, SL ~0.8% abajo, TPs mucho más lejos
        entry_price = round(mark * 1.001, 2)
        sl_price = round(mark * 0.992, 2)
        tp_prices = [round(mark * m, 2) for m in (1.0025, 1.0045, 1.0065)]
    else:
        # SHORT: entry ~0.1% abajo, SL ~0.8% arriba, TPs más lejanos
        entry_price = round(mark * 0.999, 2)
        sl_price = round(mark * 1.008, 2)
        tp_prices = [round(mark * m, 2) for m in (0.9985, 0.9970, 0.9955)]

    print("\n===== PRUEBA LARGA TP ADJUSTMENT (TESTNET) =====")
    print(f"Symbol: {symbol}")
    print(f"Side:   {side}")
    print(f"Mark:   {mark}")
    print(f"Entry:  {entry_price}")
    print(f"SL:     {sl_price}")
    print(f"TPs in: {tp_prices}")
    print("Dejaré las órdenes activas por ~15 minutos para verificación manual en Binance testnet…")

    result = trader.open_position(
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        sl_price=sl_price,
        tp_prices=tp_prices,
        force_market=True,  # fill inmediato
    )

    if not result:
        print("❌ La prueba no pudo abrir posición (validación/llenado falló)")
        return

    print("\n— Resultado —")
    print(f"Entry real: {result['entry_price']}")
    print(f"SL final:   {result['sl_price']}")
    print(f"TPs final:  {result['tp_prices']}")

    # Mantener el script vivo para que puedas observar logs del monitor y revisar en Binance
    duration = int(os.getenv("ORDER_MONITOR_DURATION", "900"))
    for remaining in range(duration, 0, -20):
        print(f"⏳ Observando... quedan ~{remaining}s")
        time.sleep(20)

    print("\n⏹️ Fin de la ventana de observación. Las órdenes siguen activas en Binance testnet.")
    print("Puedes cancelarlas/cerrarlas manualmente luego si lo deseas.")


if __name__ == "__main__":
    main()
