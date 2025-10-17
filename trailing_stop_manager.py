from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Optional

import pandas as pd
import pandas_ta as ta


@dataclass
class TrailingConfig:
    """High-level configuration for trailing stop adjustments."""

    mode: str = "off"                # off | breakeven | tp_lock | dynamic
    start_tp: int = 1                 # TP number from which the logic starts (1-indexed)
    dynamic_method: str = "atr"      # atr | ema | swing
    atr_period: int = 14
    atr_mult: float = 1.2
    ema_period: int = 34
    swing_lookback: int = 5
    min_improvement_pct: float = 0.0003   # 0.03% improvement minimum
    break_even_buffer_pct: float = 0.0
    lock_tp_buffer_pct: float = 0.0002
    guard_ticks: int = 2
    timeframe_fallback: str = "15m"
    allow_notifications: bool = True


class TrailingStopManager:
    """Applies trailing-stop policies once partial targets are hit."""

    def __init__(
        self,
        trader,
        db,
        bot_name: Optional[str] = None,
        config: Optional[TrailingConfig] = None,
        notify_func: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.trader = trader
        self.db = db
        self.bot_name = bot_name
        self.config = config or TrailingConfig()
        self.client = trader.client
        self.notify = notify_func if self.config.allow_notifications else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def on_take_profit(
        self,
        symbol: str,
        tracked: Dict,
        tp_index: int,
        fill_price: float,
        executed_qty: float,
        order_id: Optional[str] = None,
    ) -> Optional[float]:
        """Handle TP fill event and update the stop-loss if policy requires it."""
        mode = (self.config.mode or "off").strip().lower()
        if mode in ("off", "none"):
            return None
        if tp_index < max(1, self.config.start_tp):
            return None

        side = (tracked.get("side") or "").upper()
        entry_price = float(tracked.get("entry_price") or 0)
        if entry_price <= 0 or side not in {"LONG", "SHORT"}:
            return None

        existing_sl = tracked.get("sl_price")
        tp_prices = tracked.get("tp_prices") or []
        timeframe = tracked.get("timeframe") or self.config.timeframe_fallback
        trade_id_val = tracked.get("trade_id")
        if trade_id_val is None:
            return None

        be_sl: Optional[float] = None
        if tp_index == 1:
            candidate = self._calc_break_even_target(side, entry_price)
            if candidate is not None:
                # Evitar relajar stops existentes mejores que BE
                if existing_sl is not None:
                    try:
                        existing_sl_val = float(existing_sl)
                    except Exception:
                        existing_sl_val = None
                    else:
                        if side == "LONG" and existing_sl_val >= candidate:
                            be_sl = existing_sl_val
                        elif side == "SHORT" and existing_sl_val <= candidate:
                            be_sl = existing_sl_val
                if be_sl is None:
                    be_sl = self._commit_stop_update(
                        symbol=symbol,
                        side=side,
                        trade_id=int(trade_id_val),
                        new_target=candidate,
                        entry_price=entry_price,
                        previous_sl=existing_sl,
                        order_id=order_id,
                        tp_index=tp_index,
                        position_id=tracked.get("position_id"),
                    )
                if be_sl is not None:
                    tracked["sl_price"] = be_sl
                    if self.notify:
                        try:
                            self.notify(
                                f"{symbol} → SL movido a break-even tras TP1\nNuevo SL: {be_sl:.6f}"
                            )
                        except Exception:
                            pass
        if tp_index == 1 and be_sl is not None:
            return be_sl

        candidate = None
        if mode == "breakeven":
            candidate = self._calc_break_even_target(side, entry_price)
        elif mode in ("tp", "tp_lock", "tp1"):
            candidate = self._calc_tp_lock_target(side, tp_prices, tp_index)
        elif mode == "dynamic":
            candidate = self._calc_dynamic_target(symbol, side, timeframe, entry_price, existing_sl)
        else:
            return None

        if candidate is None:
            return None

        new_sl = self._commit_stop_update(
            symbol=symbol,
            side=side,
            trade_id=int(trade_id_val),
            new_target=candidate,
            entry_price=entry_price,
            previous_sl=existing_sl,
            order_id=order_id,
            tp_index=tp_index,
            position_id=tracked.get("position_id"),
        )

        if new_sl is not None:
            tracked["sl_price"] = new_sl
            if self.notify:
                mode_name = {
                    "breakeven": "break-even",
                    "tp": "TP lock",
                    "tp_lock": "TP lock",
                    "tp1": "TP lock",
                    "dynamic": f"trailing {self.config.dynamic_method}"
                }.get(mode, mode)
                msg = (
                    f"{symbol} → SL ajustado tras TP{tp_index} ({mode_name})\n"
                    f"Nuevo SL: {new_sl:.6f}"
                )
                try:
                    self.notify(msg)
                except Exception:
                    pass
        return new_sl

    # ------------------------------------------------------------------
    # Target calculators
    # ------------------------------------------------------------------
    def _calc_break_even_target(self, side: str, entry_price: float) -> float:
        buffer_pct = max(0.0, float(self.config.break_even_buffer_pct))
        if side == "LONG":
            return entry_price * (1 + buffer_pct)
        return entry_price * (1 - buffer_pct)

    def _calc_tp_lock_target(self, side: str, tp_prices, tp_index: int) -> Optional[float]:
        if not tp_prices:
            return None
        idx = min(max(tp_index - 1, 0), len(tp_prices) - 1)
        base = float(tp_prices[idx])
        buffer_pct = max(0.0, float(self.config.lock_tp_buffer_pct))
        if side == "LONG":
            return base * (1 - buffer_pct)
        return base * (1 + buffer_pct)

    def _calc_dynamic_target(
        self,
        symbol: str,
        side: str,
        timeframe: str,
        entry_price: float,
        existing_sl: Optional[float],
    ) -> Optional[float]:
        try:
            df = self._fetch_dataframe(symbol, timeframe, limit=max(120, self.config.swing_lookback * 3))
        except Exception as exc:
            print(f"⚠️ TrailingStopManager ({symbol}) no pudo obtener velas para trailing: {exc}")
            return None
        if df is None or df.empty or len(df) < max(20, self.config.atr_period + 5):
            return None

        method = (self.config.dynamic_method or "atr").lower()
        close_price = float(df["close"].iloc[-1])
        candidate = None

        try:
            if method == "ema":
                ema_val = float(ta.ema(df["close"], length=self.config.ema_period).iloc[-1])
                candidate = ema_val
            elif method == "swing":
                if side == "LONG":
                    candidate = float(df["low"].tail(self.config.swing_lookback).min())
                else:
                    candidate = float(df["high"].tail(self.config.swing_lookback).max())
            else:  # Default ATR
                atr_series = ta.atr(df["high"], df["low"], df["close"], length=self.config.atr_period)
                atr_value = float(atr_series.iloc[-1])
                mult = max(0.1, float(self.config.atr_mult))
                if side == "LONG":
                    candidate = close_price - atr_value * mult
                else:
                    candidate = close_price + atr_value * mult
        except Exception as exc:
            print(f"⚠️ TrailingStopManager ({symbol}) fallo cálculo dinámico: {exc}")
            return None

        if candidate is None or candidate <= 0:
            return None

        # Never loosen the stop beyond entry (keep profit locked once we're trailing)
        if side == "LONG":
            floor_val = entry_price * (1 + self.config.break_even_buffer_pct)
            if existing_sl:
                floor_val = max(floor_val, float(existing_sl))
            candidate = max(candidate, floor_val)
        else:
            ceil_val = entry_price * (1 - self.config.break_even_buffer_pct)
            if existing_sl:
                ceil_val = min(ceil_val, float(existing_sl))
            candidate = min(candidate, ceil_val)

        return candidate

    # ------------------------------------------------------------------
    # Binance + DB orchestration
    # ------------------------------------------------------------------
    def _commit_stop_update(
        self,
        symbol: str,
        side: str,
        trade_id: int,
        new_target: float,
        entry_price: float,
        previous_sl: Optional[float],
        order_id: Optional[str],
        tp_index: int,
        position_id: Optional[str],
    ) -> Optional[float]:
        try:
            filters = self.trader._get_symbol_filters(symbol)
        except Exception:
            filters = {"tickSize": 0.01}
        tick = float(filters.get("tickSize", 0.01))

        mark_price = None
        try:
            mp = self.client.futures_mark_price(symbol=symbol)
            mark_price = float(mp.get("markPrice")) if mp else None
        except Exception:
            mark_price = None

        candidate = float(new_target)
        guard_ticks = max(1, int(self.config.guard_ticks))
        if mark_price and mark_price > 0:
            if side == "LONG":
                upper_bound = mark_price - tick * guard_ticks
                candidate = min(candidate, upper_bound)
            else:
                lower_bound = mark_price + tick * guard_ticks
                candidate = max(candidate, lower_bound)

        candidate = self._round_stop_price(candidate, tick, side)
        if candidate <= 0:
            return None

        if previous_sl is not None:
            min_improvement_abs = max(entry_price * self.config.min_improvement_pct, tick * guard_ticks)
            if side == "LONG" and candidate <= float(previous_sl) + min_improvement_abs:
                return None
            if side == "SHORT" and candidate >= float(previous_sl) - min_improvement_abs:
                return None

        sl_side = "SELL" if side == "LONG" else "BUY"
        params = {
            "symbol": symbol,
            "side": sl_side,
            "type": "STOP_MARKET",
            "stopPrice": candidate,
            "closePosition": True,
            "workingType": "MARK_PRICE",
            "priceProtect": True,
        }

        try:
            new_order = self.client.futures_create_order(**params)
        except Exception as exc:
            print(f"❌ TrailingStopManager ({symbol}) no pudo crear nuevo SL: {exc}")
            return None

        # Cancel previous stop(s) once we have a fresh order in place
        self._cancel_previous_stops(symbol, keep_order_id=str(new_order.get("orderId")))

        # Update DB bookkeeping
        try:
            if order_id:
                self.db.update_order_status(order_id, status="FILLED")
        except Exception:
            pass
        try:
            self.db.update_trade_sl(trade_id, candidate)
        except Exception:
            pass
        try:
            self.db.add_order(
                trade_id=trade_id,
                order_id=str(new_order.get("orderId")),
                order_type="STOP_LOSS",
                side=sl_side,
                symbol=symbol,
                price=candidate,
                quantity=None,
                status=new_order.get("status", "NEW"),
                client_order_id=new_order.get("clientOrderId"),
                position_id=position_id,
            )
        except Exception:
            pass

        print(
            f"🛡️ TrailingStopManager: SL actualizado {symbol} -> {candidate:.6f} (TP{tp_index})"
        )
        return candidate

    def _cancel_previous_stops(self, symbol: str, keep_order_id: Optional[str]) -> None:
        try:
            open_orders = self.client.futures_get_open_orders(symbol=symbol)
        except Exception:
            return
        for order in open_orders:
            oid = str(order.get("orderId"))
            if oid == keep_order_id:
                continue
            otype = order.get("type", "")
            if "STOP" in otype and "TAKE_PROFIT" not in otype:
                try:
                    self.client.futures_cancel_order(symbol=symbol, orderId=order.get("orderId"))
                    self.db.update_order_status(oid, status="CANCELLED")
                except Exception:
                    continue

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _round_stop_price(self, price: float, tick: float, side: str) -> float:
        if tick <= 0:
            return price
        precision = max(len(('{0:.10f}'.format(tick)).rstrip('0').split('.')[-1]), 0)
        if side == "LONG":
            steps = math.floor(price / tick)
        else:
            steps = math.ceil(price / tick)
        return round(max(steps, 1) * tick, precision)

    def _fetch_dataframe(self, symbol: str, timeframe: str, limit: int = 150) -> Optional[pd.DataFrame]:
        try:
            raw = self.client.get_klines(symbol=symbol, interval=timeframe, limit=limit)
            if not raw:
                return None
        except Exception:
            raise
        cols = [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "number_of_trades",
            "taker_buy_base_asset_volume",
            "taker_buy_quote_asset_volume",
            "ignore",
        ]
        df = pd.DataFrame(raw, columns=cols)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df[["timestamp", "open", "high", "low", "close", "volume"]].dropna()
        return df
