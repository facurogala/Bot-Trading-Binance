"""
Sincroniza fills reales (precio/cantidad) desde Binance Futures y actualiza la DB.

- Busca trades cerrados recientes y sus órdenes (SL/TP)
- Trae userTrades de futures y cruza por orderId
- Actualiza orders.filled_price / filled_qty / filled_time / status
- Recalcula PnL de trades cerrados usando fills

Uso (PowerShell):
  python .\sync_fills_from_binance.py --days 7
  python .\sync_fills_from_binance.py --trade-id 123
"""
from datetime import datetime, timedelta
from typing import Optional, Dict
import argparse

from trading_database import TradingDatabase
from binance_futures_trader import BinanceFuturesTrader


def to_ms(ts: str) -> int:
    # Convierte 'YYYY-mm-dd HH:MM:SS[.ffffff]' local a epoch ms
    try:
        if '.' in ts:
            dt = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S.%f')
        else:
            dt = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


def sync_for_trade(db: TradingDatabase, client, trade_row: Dict) -> int:
    """Sincroniza fills (por orderId) para un trade y devuelve cantidad de órdenes actualizadas."""
    trade_id = trade_row['id']
    symbol = trade_row['symbol']
    entry_time = trade_row.get('entry_time')
    exit_time = trade_row.get('exit_time') or trade_row.get('entry_time')

    if not symbol or not entry_time:
        return 0

    start_ms = max(to_ms(entry_time) - 5 * 60_000, 0)
    end_ms = to_ms(exit_time) + 5 * 60_000 if exit_time else start_ms + 24 * 60 * 60_000

    # Traer operaciones de cuenta para el símbolo
    try:
        acct_trades = client.futures_account_trades(symbol=symbol, startTime=start_ms, endTime=end_ms)
    except Exception as e:
        print(f"⚠️ No se pudo obtener userTrades para {symbol}: {e}")
        return 0

    if not acct_trades:
        return 0

    # Index por orderId -> aggregation
    by_order: Dict[str, Dict] = {}
    for t in acct_trades:
        oid = str(t.get('orderId'))
        price = float(t.get('price', 0) or 0)
        qty = float(t.get('qty', 0) or 0)
        time_ms = int(t.get('time', 0) or 0)
        if oid is None or qty <= 0:
            continue
        agg = by_order.setdefault(oid, {'sum_px_qty': 0.0, 'sum_qty': 0.0, 'last_time': 0})
        agg['sum_px_qty'] += price * qty
        agg['sum_qty'] += qty
        agg['last_time'] = max(agg['last_time'], time_ms)

    # Obtener órdenes del trade (SL/TP)
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT id, order_id, order_type FROM orders
        WHERE trade_id = ? AND (order_type = 'STOP_LOSS' OR order_type LIKE 'TAKE_PROFIT%')
    ''', (trade_id,))
    rows = c.fetchall()
    conn.close()

    updated = 0
    for r in rows:
        oid = str(r['order_id'])
        agg = by_order.get(oid)
        if not agg or agg['sum_qty'] <= 0:
            continue
        avg_price = agg['sum_px_qty'] / agg['sum_qty']
        filled_ts = datetime.fromtimestamp(agg['last_time']/1000.0).strftime('%Y-%m-%d %H:%M:%S')
        try:
            db.update_order_fill(order_id=oid, filled_price=avg_price, filled_qty=agg['sum_qty'], filled_time=filled_ts, status='FILLED')
            updated += 1
        except Exception as e:
            print(f"⚠️ No se pudo actualizar order_id={oid}: {e}")

    return updated


def main():
    parser = argparse.ArgumentParser(description='Sync de fills desde Binance para recalcular PnL exacto')
    parser.add_argument('--days', type=int, default=7, help='Rango de días hacia atrás para trades cerrados')
    parser.add_argument('--trade-id', type=int, help='Sincronizar solo este trade_id')
    args = parser.parse_args()

    db = TradingDatabase('trading_history.db')
    trader = BinanceFuturesTrader()
    client = trader.client

    total_updates = 0

    if args.trade_id:
        # Buscar ese trade
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM trades WHERE id = ?", (args.trade_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            print(f"❌ Trade id={args.trade_id} no encontrado")
            return
        total_updates += sync_for_trade(db, client, dict(row))
    else:
        # Últimos N días de trades cerrados
        since = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d %H:%M:%S')
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM trades WHERE status='CLOSED' AND COALESCE(exit_time, entry_time) >= ? ORDER BY exit_time DESC", (since,))
        trades = [dict(r) for r in c.fetchall()]
        conn.close()
        for t in trades:
            total_updates += sync_for_trade(db, client, t)

    if total_updates > 0:
        print(f"🛠️ Fills actualizados en {total_updates} orden(es). Recalculando PnL...")
        updated = db.recalc_closed_trades_pnl()
        print(f"✅ {updated} trade(s) recalculado(s)")
    else:
        print("ℹ️ No se encontraron fills nuevos para actualizar")


if __name__ == '__main__':
    main()
