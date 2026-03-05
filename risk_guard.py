import os
import time
from datetime import datetime
from typing import Optional, Tuple


class RiskGuard:
    """Guardia de riesgo global por bot basada en trades cerrados de la base de datos."""

    def __init__(self, db, bot_name: str):
        self.db = db
        self.bot_name = bot_name
        self.enabled = os.getenv("RISK_GUARD_ENABLED", "True").lower() == "true"
        self.max_daily_loss_usdt = float(os.getenv("MAX_DAILY_LOSS_USDT", "0"))
        self.max_drawdown_pct = float(os.getenv("MAX_DRAWDOWN_PCT", "0"))
        self.max_consecutive_losses = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "0"))
        self.pause_minutes = int(os.getenv("RISK_GUARD_PAUSE_MINUTES", "60"))
        self.initial_equity_usdt = float(os.getenv("RISK_GUARD_INITIAL_EQUITY_USDT", "0"))
        self.max_global_open_positions = int(os.getenv("MAX_GLOBAL_OPEN_POSITIONS", "0"))
        self.max_global_symbol_positions = int(os.getenv("MAX_GLOBAL_SYMBOL_POSITIONS", "1"))
        self.max_global_exposure_usdt = float(os.getenv("MAX_GLOBAL_EXPOSURE_USDT", "0"))
        self.max_symbol_exposure_usdt = float(os.getenv("MAX_SYMBOL_EXPOSURE_USDT", "0"))
        self.pause_until_ts = 0.0

    @staticmethod
    def _safe_float(value, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _estimate_trade_notional(self, trade: dict) -> float:
        entry_price = self._safe_float(trade.get("entry_price"), 0.0)
        quantity = self._safe_float(trade.get("quantity"), 0.0)
        if entry_price <= 0 or quantity <= 0:
            return 0.0
        return entry_price * quantity

    def _open_exposure_summary(self) -> tuple:
        open_trades = self.db.get_open_trades()
        by_symbol = {}
        total_notional = 0.0

        for trade in open_trades:
            symbol = str(trade.get("symbol") or "")
            if not symbol:
                continue
            by_symbol[symbol] = by_symbol.get(symbol, 0) + 1
            total_notional += self._estimate_trade_notional(trade)

        return open_trades, by_symbol, total_notional

    def _today_start_utc(self) -> datetime:
        now = datetime.utcnow()
        return datetime(now.year, now.month, now.day)

    def _activate_pause(self) -> None:
        self.pause_until_ts = time.time() + (self.pause_minutes * 60)

    def _consecutive_losses(self, trades_desc: list) -> int:
        losses = 0
        for trade in trades_desc:
            pnl = float(trade.get("pnl") or 0)
            if pnl < 0:
                losses += 1
            else:
                break
        return losses

    def _drawdown_pct(self, trades_desc: list) -> Optional[float]:
        if self.initial_equity_usdt <= 0:
            return None

        trades_asc = list(reversed(trades_desc))
        equity = self.initial_equity_usdt
        peak = equity
        max_dd = 0.0

        for trade in trades_asc:
            pnl = float(trade.get("pnl") or 0)
            equity += pnl
            if equity > peak:
                peak = equity
            if peak > 0:
                dd = ((peak - equity) / peak) * 100
                if dd > max_dd:
                    max_dd = dd

        return max_dd

    def can_open_trade(self, symbol: Optional[str] = None, estimated_notional_usdt: float = 0.0) -> Tuple[bool, str]:
        if not self.enabled:
            return True, "RiskGuard desactivado"

        now_ts = time.time()
        if self.pause_until_ts > now_ts:
            remaining = int((self.pause_until_ts - now_ts) / 60)
            return False, f"RiskGuard pausado {remaining}m"

        trades_today = self.db.get_closed_trades(bot=self.bot_name, since=self._today_start_utc())
        total_pnl_today = sum(float(t.get("pnl") or 0) for t in trades_today)

        if self.max_daily_loss_usdt > 0 and total_pnl_today <= -self.max_daily_loss_usdt:
            self._activate_pause()
            return False, (
                f"Límite de pérdida diaria alcanzado: {total_pnl_today:.2f} <= -{self.max_daily_loss_usdt:.2f} USDT"
            )

        if self.max_consecutive_losses > 0:
            losses = self._consecutive_losses(trades_today)
            if losses >= self.max_consecutive_losses:
                self._activate_pause()
                return False, f"Racha de pérdidas alcanzada: {losses}"

        if self.max_drawdown_pct > 0:
            dd = self._drawdown_pct(trades_today)
            if dd is not None and dd >= self.max_drawdown_pct:
                self._activate_pause()
                return False, f"Drawdown máximo alcanzado: {dd:.2f}%"

        # Exposición global (cross-bot): usa todos los trades abiertos en DB
        open_trades, by_symbol, total_notional = self._open_exposure_summary()

        if self.max_global_open_positions > 0 and len(open_trades) >= self.max_global_open_positions:
            return False, (
                f"Límite global de posiciones abiertas alcanzado: "
                f"{len(open_trades)}/{self.max_global_open_positions}"
            )

        if symbol and self.max_global_symbol_positions > 0:
            symbol_count = by_symbol.get(symbol, 0)
            if symbol_count >= self.max_global_symbol_positions:
                return False, (
                    f"Límite global por símbolo alcanzado en {symbol}: "
                    f"{symbol_count}/{self.max_global_symbol_positions}"
                )

        est_notional = max(0.0, self._safe_float(estimated_notional_usdt, 0.0))
        if self.max_global_exposure_usdt > 0 and (total_notional + est_notional) > self.max_global_exposure_usdt:
            return False, (
                f"Límite global de exposición alcanzado: "
                f"{(total_notional + est_notional):.2f}/{self.max_global_exposure_usdt:.2f} USDT"
            )

        if symbol and self.max_symbol_exposure_usdt > 0:
            symbol_notional = 0.0
            for trade in open_trades:
                if str(trade.get("symbol") or "") == symbol:
                    symbol_notional += self._estimate_trade_notional(trade)
            if (symbol_notional + est_notional) > self.max_symbol_exposure_usdt:
                return False, (
                    f"Límite de exposición por símbolo alcanzado en {symbol}: "
                    f"{(symbol_notional + est_notional):.2f}/{self.max_symbol_exposure_usdt:.2f} USDT"
                )

        return True, f"OK (PnL día: {total_pnl_today:.2f} USDT)"
