"""
AutoCloser: Snippet plug & play para cerrar completamente posiciones residuales
cuando se ejecutan los TP/SL, y para reflejar el cierre en la base de datos.

Objetivo:
- Evitar que quede "polvo" de posición abierto tras ejecutar TPs por redondeos.
- Si la posición ya se cerró por SL/TP (en exchange) pero la DB sigue en OPEN,
  cerrar el trade en la DB con el precio de mercado actual.

Uso (en cada bot):
    from auto_closer import AutoCloser
    auto_closer = AutoCloser(trader, db, bot_name="Swing")
    auto_closer.start()

Config (.env):
- AUTO_CLOSER_ENABLED=True
- AUTO_CLOSER_INTERVAL=10   # segundos
- AUTO_CLOSER_MIN_NOTIONAL=5.0  # USDT mínimos para forzar cierre del remanente
"""
import os
import time
import threading
from typing import Optional, Dict, List

from binance.exceptions import BinanceAPIException


class AutoCloser:
    def __init__(self, trader, db, bot_name: Optional[str] = None):
        self.trader = trader
        self.db = db
        self.bot_name = bot_name
        self.client = trader.client
        self.enabled = os.getenv("AUTO_CLOSER_ENABLED", "True").lower() == "true"
        self.interval = int(os.getenv("AUTO_CLOSER_INTERVAL", "10"))
        self.min_notional = float(os.getenv("AUTO_CLOSER_MIN_NOTIONAL", "5.0"))
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self):
        if not self.enabled:
            print("⚠️ AutoCloser deshabilitado (AUTO_CLOSER_ENABLED=False)")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"🧩 AutoCloser iniciado (intervalo={self.interval}s)")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        print("🧩 AutoCloser detenido")

    # ---------------- Internals ----------------

    def _loop(self):
        while self._running:
            try:
                self._tick()
            except Exception as e:
                print(f"⚠️ AutoCloser error: {e}")
            time.sleep(self.interval)

    def _tick(self):
        # Tomar trades abiertos desde la DB (si bot_name se pasó, podría filtrarse más adelante)
        open_trades = self.db.get_open_trades()
        if not open_trades:
            return

        # Posiciones en Binance para conocer qty y órdenes
        positions = self.trader.get_open_positions()
        pos_by_symbol: Dict[str, Dict] = {p['symbol']: p for p in positions}

        for t in open_trades:
            symbol = t['symbol']
            trade_id = t['id']
            entry_price = float(t['entry_price'])
            leverage = int(t.get('leverage') or self.trader.leverage)

            # Estado de exchange
            pos = pos_by_symbol.get(symbol)

            if not pos:
                # No hay posición en exchange pero la DB dice OPEN => se cerró (por SL/TP/manual)
                # Cerrar en DB con precio de mercado actual
                exit_price = self._get_mark_price_safe(symbol) or entry_price
                try:
                    self._finalize_trade(trade_id, symbol, exit_price, exit_reason="AUTO_CLOSER_DETECTED")
                except Exception as e:
                    print(f"⚠️ AutoCloser no pudo cerrar DB para {symbol} id={trade_id}: {e}")
                # Limpiar órdenes residuales
                try:
                    self.trader.cancel_all_orders(symbol)
                except Exception:
                    pass
                continue

            # Hay posición: verificar órdenes SL/TP abiertas
            try:
                open_orders = self.client.futures_get_open_orders(symbol=symbol)
            except BinanceAPIException as e:
                print(f"⚠️ AutoCloser open_orders {symbol}: {e}")
                open_orders = []
            except Exception:
                open_orders = []

            # Clasificar órdenes y estimar cantidad TP pendiente
            sl_exists = False
            tp_total_qty = 0.0
            for o in open_orders:
                typ = o.get('type', '')
                if 'STOP' in typ and 'TAKE_PROFIT' not in typ:
                    sl_exists = True
                elif 'TAKE_PROFIT' in typ:
                    try:
                        tpq = float(o.get('origQty') or o.get('origQuantity') or 0)
                        tp_total_qty += max(tpq, 0.0)
                    except Exception:
                        pass

            # Cálculos sobre remanente
            qty_open = float(pos['quantity'])
            notional_open = qty_open * float(pos['entryPrice']) if pos['entryPrice'] else 0.0

            # Regla 1: si no hay TPs ni SL y sigue habiendo qty => cerrar remanente reduceOnly MARKET
            if (not sl_exists) and (tp_total_qty <= 0.0) and qty_open > 0:
                # Sólo cerrar si supera un mínimo notional para evitar rechazos
                if (qty_open * self._get_last_price_safe(symbol)) >= self.min_notional:
                    self._force_close_remaining(symbol, pos)
                    # Cerrar en DB con último precio
                    exit_price = self._get_mark_price_safe(symbol) or self._get_last_price_safe(symbol) or entry_price
                    try:
                        self._finalize_trade(trade_id, symbol, exit_price, exit_reason="AUTO_CLOSER_TP")
                    except Exception as e:
                        print(f"⚠️ AutoCloser no pudo cerrar DB {symbol}: {e}")
                continue

            # Regla 2: si la suma de TPs es menor a la qty abierta (por redondeos), cerrar la diferencia
            if qty_open > 0 and tp_total_qty > 0 and tp_total_qty < qty_open:
                diff_qty = qty_open - tp_total_qty
                # Evitar cerrar cantidades por debajo del stepSize; intentaremos cerrar todo directamente
                if (diff_qty * self._get_last_price_safe(symbol)) >= self.min_notional:
                    self._force_close_quantity(symbol, diff_qty, pos)

                # Si tras intento, la posición queda muy pequeña, intentamos cierre total
                # (sin bloquear si falla)
                try:
                    after = self.trader.get_open_positions()
                    apos = next((p for p in after if p['symbol'] == symbol), None)
                    if not apos or float(apos['quantity']) <= 0:
                        exit_price = self._get_mark_price_safe(symbol) or self._get_last_price_safe(symbol) or entry_price
                        self._finalize_trade(trade_id, symbol, exit_price, exit_reason="AUTO_CLOSER_TP")
                except Exception:
                    pass

    # ---------------- Helpers ----------------

    def _get_mark_price_safe(self, symbol: str) -> Optional[float]:
        try:
            mp = self.client.futures_mark_price(symbol=symbol)
            return float(mp.get('markPrice')) if mp else None
        except Exception:
            return None

    def _get_last_price_safe(self, symbol: str) -> float:
        try:
            t = self.client.futures_symbol_ticker(symbol=symbol)
            return float(t.get('price')) if t else 0.0
        except Exception:
            return 0.0

    def _force_close_remaining(self, symbol: str, pos: Dict):
        side = 'SELL' if pos['side'] == 'LONG' else 'BUY'
        qty = float(pos['quantity'])
        if qty <= 0:
            return
        try:
            print(f"🧩 AutoCloser: cerrando remanente {symbol} qty={qty}")
            self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=qty,
                reduceOnly=True
            )
            # Cancelar órdenes (por si quedaron)
            try:
                self.trader.cancel_all_orders(symbol)
            except Exception:
                pass
        except Exception as e:
            print(f"⚠️ AutoCloser no pudo cerrar remanente {symbol}: {e}")

    def _force_close_quantity(self, symbol: str, qty: float, pos: Dict):
        side = 'SELL' if pos['side'] == 'LONG' else 'BUY'
        if qty <= 0:
            return
        try:
            print(f"🧩 AutoCloser: cerrando diferencia {symbol} qty={qty}")
            self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=qty,
                reduceOnly=True
            )
        except Exception as e:
            print(f"⚠️ AutoCloser no pudo cerrar qty {symbol}: {e}")

    def _finalize_trade(self, trade_id: int, symbol: str, exit_price: float, exit_reason: str):
        # Cierra el trade en DB si aún está OPEN
        try:
            try:
                margin_exit = self.trader.get_margin_balance()
            except Exception:
                margin_exit = None
            self.db.close_trade(
                trade_id,
                exit_price=exit_price,
                exit_reason=exit_reason,
                margin_balance_exit=margin_exit
            )
        except Exception as e:
            # Si falló por estado ya cerrado, ignorar
            print(f"⚠️ AutoCloser close_trade fallo id={trade_id}: {e}")
