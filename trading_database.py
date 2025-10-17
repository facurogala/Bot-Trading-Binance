"""
Sistema de base de datos para almacenar historial de transacciones
Guarda todas las operaciones y permite análisis histórico
"""
import sqlite3
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import json
import time
import functools

class TradingDatabase:
    def __init__(self, db_path: str = "trading_history.db"):
        """Inicializa la base de datos"""
        self.db_path = db_path
        # Número de reintentos para escrituras cuando la BD está bloqueada
        self._db_write_retries = int(os.getenv("DB_WRITE_RETRIES", "6"))
        self._db_retry_backoff = float(os.getenv("DB_RETRY_BACKOFF", "0.08"))
        self.init_database()
    
    def init_database(self):
        """Crea las tablas necesarias si no existen"""
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        cursor = conn.cursor()
        try:
            # Enable WAL for better concurrent writes from multiple processes
            cursor.execute("PRAGMA journal_mode=WAL;")
        except Exception:
            pass
        try:
            cursor.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            pass
        try:
            cursor.execute("PRAGMA foreign_keys=ON;")
        except Exception:
            pass
        
        # Tabla de trades (posiciones abiertas y cerradas)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                quantity REAL NOT NULL,
                leverage INTEGER NOT NULL,
                sl_price REAL,
                tp_prices TEXT,
                entry_time TIMESTAMP NOT NULL,
                exit_time TIMESTAMP,
                status TEXT NOT NULL,
                pnl REAL,
                pnl_percent REAL,
                exit_reason TEXT,
                timeframe TEXT,
                notes TEXT,
                bot TEXT
            )
        ''')
        
        # Tabla de órdenes individuales
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER,
                order_id TEXT NOT NULL,
                order_type TEXT NOT NULL,
                side TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price REAL,
                quantity REAL,
                status TEXT NOT NULL,
                created_time TIMESTAMP NOT NULL,
                filled_time TIMESTAMP,
                filled_price REAL,
                filled_qty REAL,
                FOREIGN KEY (trade_id) REFERENCES trades(id)
            )
        ''')
        
        # Tabla de estadísticas diarias
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL UNIQUE,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                win_rate REAL DEFAULT 0,
                best_trade REAL DEFAULT 0,
                worst_trade REAL DEFAULT 0
            )
        ''')

        # Tabla de sesiones por bot (para "arrancar desde cero")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_sessions (
                bot TEXT PRIMARY KEY,
                start_time TIMESTAMP NOT NULL
            )
        ''')

        # Tabla de actividad por bot (aprobadas/ejecutadas por día)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_activity (
                date DATE NOT NULL,
                bot TEXT NOT NULL,
                approved_count INTEGER DEFAULT 0,
                executed_count INTEGER DEFAULT 0,
                PRIMARY KEY (date, bot)
            )
        ''')

        # Tabla de intentos de entrada (auditoría de aperturas)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entry_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                bot TEXT,
                bot_id TEXT,
                requested_at TIMESTAMP NOT NULL,
                status TEXT NOT NULL,
                reason TEXT,
                context TEXT,
                metadata TEXT,
                completed_at TIMESTAMP,
                trade_id INTEGER,
                entry_order_id TEXT,
                FOREIGN KEY (trade_id) REFERENCES trades(id)
            )
        ''')

        # Tabla de eventos/auditoría
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER,
                event_type TEXT NOT NULL,
                event_time TIMESTAMP NOT NULL,
                payload TEXT,
                details TEXT,
                FOREIGN KEY (trade_id) REFERENCES trades(id)
            )
        ''')
        
        conn.commit()
        # Migraciones de columnas adicionales
        try:
            cursor.execute("PRAGMA table_info(trades)")
            cols = {r[1] for r in cursor.fetchall()}
            trade_alters = {
                'bot': "ALTER TABLE trades ADD COLUMN bot TEXT",
                'bot_id': "ALTER TABLE trades ADD COLUMN bot_id TEXT",
                'notional': "ALTER TABLE trades ADD COLUMN notional REAL",
                'risk_usd': "ALTER TABLE trades ADD COLUMN risk_usd REAL",
                'margin_used': "ALTER TABLE trades ADD COLUMN margin_used REAL",
                'position_id': "ALTER TABLE trades ADD COLUMN position_id TEXT",
                'entry_order_id': "ALTER TABLE trades ADD COLUMN entry_order_id TEXT",
                'entry_client_order_id': "ALTER TABLE trades ADD COLUMN entry_client_order_id TEXT",
                'exit_order_id': "ALTER TABLE trades ADD COLUMN exit_order_id TEXT",
                'exit_client_order_id': "ALTER TABLE trades ADD COLUMN exit_client_order_id TEXT",
                'margin_balance_entry': "ALTER TABLE trades ADD COLUMN margin_balance_entry REAL",
                'margin_balance_post_entry': "ALTER TABLE trades ADD COLUMN margin_balance_post_entry REAL",
                'margin_balance_exit': "ALTER TABLE trades ADD COLUMN margin_balance_exit REAL",
                'margin_pnl': "ALTER TABLE trades ADD COLUMN margin_pnl REAL",
                'isolated_margin': "ALTER TABLE trades ADD COLUMN isolated_margin REAL"
            }
            for column, statement in trade_alters.items():
                if column not in cols:
                    cursor.execute(statement)
                    conn.commit()
                    cols.add(column)
        except Exception:
            pass

        # Migración: asegurar columnas de fills en 'orders'
        try:
            cursor.execute("PRAGMA table_info(orders)")
            ocols = {r[1] for r in cursor.fetchall()}
            order_alters = {
                'filled_price': "ALTER TABLE orders ADD COLUMN filled_price REAL",
                'filled_qty': "ALTER TABLE orders ADD COLUMN filled_qty REAL",
                'filled_time': "ALTER TABLE orders ADD COLUMN filled_time TIMESTAMP",
                'client_order_id': "ALTER TABLE orders ADD COLUMN client_order_id TEXT",
                'position_id': "ALTER TABLE orders ADD COLUMN position_id TEXT"
            }
            for column, statement in order_alters.items():
                if column not in ocols:
                    cursor.execute(statement)
                    conn.commit()
                    ocols.add(column)
        except Exception:
            pass

        # Backfill: si 'bot' es NULL, inferir desde 'notes' para filas históricas
        try:
            cursor.execute("UPDATE trades SET bot = 'Haack' WHERE bot IS NULL AND notes LIKE '%Haack%'")
            cursor.execute("UPDATE trades SET bot = 'Conservador' WHERE bot IS NULL AND notes LIKE '%Conservador%'")
            cursor.execute("UPDATE trades SET bot = 'Scanner' WHERE bot IS NULL AND (notes LIKE 'Señal EMA - %' OR notes LIKE '%Auto Trading%')")
            conn.commit()
        except Exception:
            pass

        conn.close()
        print(f"✅ Base de datos inicializada: {self.db_path}")

    def _connect(self):
        """Helper para abrir una conexión con parámetros apropiados."""
        return sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)

    def _with_db_retry(self, fn):
        """Decorador local para reintentar operaciones de escritura cuando la BD está bloqueada."""
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(self._db_write_retries):
                try:
                    return fn(*args, **kwargs)
                except sqlite3.OperationalError as exc:
                    last_exc = exc
                    msg = str(exc).lower()
                    if 'database is locked' in msg or 'database table is locked' in msg:
                        backoff = self._db_retry_backoff * (1 + attempt * 0.5)
                        time.sleep(backoff)
                        continue
                    raise
            # If we exhausted retries, raise the last exception
            if last_exc:
                raise last_exc
            return None
        return wrapper

    # ===== Bot Activity (aprobadas/ejecutadas) =====
    def increment_bot_activity(self, bot: str, approved_delta: int = 0, executed_delta: int = 0, the_date: Optional[str] = None) -> None:
        """Incrementa contadores diarios de actividad por bot.

        Args:
            bot: nombre del bot (ej: 'Scalping', 'Swing', 'Haack')
            approved_delta: incremento de señales aprobadas
            executed_delta: incremento de trades ejecutados
            the_date: YYYY-MM-DD; si None usa fecha UTC actual
        """
        if approved_delta == 0 and executed_delta == 0:
            return
        if the_date is None:
            the_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        attempts = 0
        while True:
            try:
                conn = self._connect()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO bot_activity (date, bot, approved_count, executed_count)
                    VALUES (?, ?, 0, 0)
                    ON CONFLICT(date, bot) DO NOTHING
                ''', (the_date, bot))
                cursor.execute('''
                    UPDATE bot_activity
                    SET approved_count = approved_count + ?,
                        executed_count = executed_count + ?
                    WHERE date = ? AND bot = ?
                ''', (approved_delta, executed_delta, the_date, bot))
                conn.commit()
                conn.close()
                break
            except sqlite3.OperationalError as exc:
                attempts += 1
                if attempts >= self._db_write_retries:
                    raise
                time.sleep(self._db_retry_backoff * attempts)

    def get_bot_activity(self, bot: Optional[str] = None, days: int = 30) -> List[Dict]:
        """Devuelve serie de actividad por día (últimos 'days' días)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        since = (datetime.now(timezone.utc).date()).toordinal() - days
        # SQLite no soporta fácilmente date - N; usamos comparación string con >= date('now','-N days')
        if bot:
            cursor.execute(
                '''SELECT date, bot, approved_count, executed_count
                   FROM bot_activity
                   WHERE bot = ? AND date >= date('now', ?)
                   ORDER BY date ASC''',
                (bot, f'-{days} days')
            )
        else:
            cursor.execute(
                '''SELECT date, bot, approved_count, executed_count
                   FROM bot_activity
                   WHERE date >= date('now', ?)
                   ORDER BY date ASC''',
                (f'-{days} days',)
            )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def get_bot_activity_7d_ma(self, bot: Optional[str] = None) -> Dict[str, float]:
        """Promedio móvil 7 días de 'executed_count' por bot.
        Si bot es None, devuelve dict por cada bot.
        Fallback: si no hay actividad, estima usando trades por entry_time.
        """
        result: Dict[str, float] = {}
        if bot:
            bots = [bot]
        else:
            bots = self.get_distinct_bots()
        for b in bots:
            rows = self.get_bot_activity(bot=b, days=14)
            if not rows:
                # Fallback a trades (conteo de entradas por día, últimos 14 días)
                series = self._estimate_activity_from_trades(b, days=14)
            else:
                series = rows
            # Tomar últimos 7 días
            last7 = series[-7:] if len(series) >= 7 else series
            ma = sum(r.get('executed_count', 0) for r in last7) / (len(last7) if last7 else 1)
            result[b] = ma
        return result

    def _estimate_activity_from_trades(self, bot: str, days: int = 14) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT DATE(entry_time) as date, COALESCE(bot, ?) as bot, COUNT(*) as executed_count
               FROM trades
               WHERE DATE(entry_time) >= DATE('now', ?) AND (bot = ? OR (bot IS NULL AND notes LIKE ?))
               GROUP BY DATE(entry_time)''',
            (bot, f'-{days} days', bot, f'%{bot}%')
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        # Normalizar: agregar approved_count=0 para compat
        for r in rows:
            r.setdefault('approved_count', 0)
        return rows

    def get_bot_weekly_kpis(self, bot: str, days: int = 7) -> Dict[str, float]:
        """Calcula KPIs clave de los últimos `days` días para un bot."""
        since_ts = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        trades = self.get_closed_trades(bot=bot, since=since_ts)

        total_trades = len(trades)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "net_pnl": 0.0,
                "avg_r_multiple": 0.0,
                "tp_sl_ratio": 0.0,
            }

        wins = [t for t in trades if (t.get("pnl") or 0) > 0]
        losses = [t for t in trades if (t.get("pnl") or 0) < 0]

        win_rate = (len(wins) / total_trades) * 100.0 if total_trades else 0.0

        total_wins = sum(float(t.get("pnl") or 0.0) for t in wins)
        total_losses_raw = sum(float(t.get("pnl") or 0.0) for t in losses)
        total_losses = abs(total_losses_raw)
        profit_factor = (total_wins / total_losses) if total_losses > 0 else float("inf")

        net_pnl = sum(float(t.get("pnl") or 0.0) for t in trades)

        r_multiples: List[float] = []
        for trade in trades:
            pnl = float(trade.get("pnl") or 0.0)
            risk_usd = trade.get("risk_usd")
            try:
                risk_val = float(risk_usd) if risk_usd not in (None, "", 0) else None
            except Exception:
                risk_val = None
            if risk_val and risk_val != 0:
                r_multiples.append(pnl / risk_val)
        avg_r_multiple = sum(r_multiples) / len(r_multiples) if r_multiples else 0.0

        def _reason_bucket(reason: str) -> str:
            reason_upper = (reason or "").upper()
            if "TP" in reason_upper or "TAKE_PROFIT" in reason_upper:
                return "TP"
            if "SL" in reason_upper or "STOP" in reason_upper:
                return "SL"
            return "OTHER"

        tp_count = 0
        sl_count = 0
        for trade in trades:
            bucket = _reason_bucket(str(trade.get("exit_reason", "")))
            if bucket == "TP":
                tp_count += 1
            elif bucket == "SL":
                sl_count += 1

        if sl_count == 0:
            tp_sl_ratio = float("inf") if tp_count > 0 else 0.0
        else:
            tp_sl_ratio = tp_count / sl_count

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "net_pnl": net_pnl,
            "avg_r_multiple": avg_r_multiple,
            "tp_sl_ratio": tp_sl_ratio,
        }
    
    def add_trade(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        leverage: int,
        sl_price: Optional[float] = None,
        tp_prices: Optional[List[float]] = None,
        timeframe: Optional[str] = None,
        notes: Optional[str] = None,
        bot: Optional[str] = None,
        bot_id: Optional[str] = None,
        entry_order_id: Optional[str] = None,
        entry_client_order_id: Optional[str] = None,
        position_id: Optional[str] = None,
        margin_balance_entry: Optional[float] = None,
        margin_balance_post_entry: Optional[float] = None,
        margin_used: Optional[float] = None,
        isolated_margin: Optional[float] = None
    ) -> int:
        """
        Registra una nueva operación
        
        Returns:
            ID del trade creado
        """
        conn = self._connect()
        cursor = conn.cursor()

        tp_prices_json = json.dumps(tp_prices) if tp_prices else None
        entry_time = datetime.now()
        # Métricas de inversión
        try:
            notional = float(entry_price) * float(quantity)
        except Exception:
            notional = None
        try:
            risk_usd = (abs(float(entry_price) - float(sl_price)) * float(quantity)) if (sl_price is not None) else None
        except Exception:
            risk_usd = None
        
        if margin_used is None and notional is not None:
            try:
                margin_used = float(notional) / float(leverage) if leverage else None
            except Exception:
                margin_used = None

        cursor.execute('''
            INSERT INTO trades (
                symbol, side, entry_price, quantity, leverage,
                sl_price, tp_prices, entry_time, status, timeframe, notes, bot,
                bot_id, notional, risk_usd, margin_used, position_id,
                entry_order_id, entry_client_order_id,
                margin_balance_entry, margin_balance_post_entry, isolated_margin
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            symbol, side, entry_price, quantity, leverage,
            sl_price, tp_prices_json, entry_time, 'OPEN', timeframe, notes, bot,
            bot_id, notional, risk_usd, margin_used, position_id,
            entry_order_id, entry_client_order_id,
            margin_balance_entry, margin_balance_post_entry, isolated_margin
        ))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()

        print(f"✅ Trade registrado: ID={trade_id}, {symbol} {side} @ {entry_price}")
        return trade_id

    def get_bot_investment_summary(self, bot: Optional[str] = None) -> List[Dict]:
        """Promedios de notional y risk_usd por bot.
        Si bot es None: devuelve lista por cada bot. Si se pasa bot: lista de un solo item.
        Usa todos los trades con esos campos no nulos.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if bot:
            cursor.execute(
                '''SELECT COALESCE(bot, ?) as bot,
                          AVG(notional) as avg_notional,
                          AVG(risk_usd) as avg_risk_usd,
                          COUNT(*) as trades
                   FROM trades
                   WHERE (bot = ? OR (bot IS NULL AND notes LIKE ?))
                     AND notional IS NOT NULL
                   ''',
                (bot, bot, f'%{bot}%')
            )
            rows = [dict(cursor.fetchone() or {})]
        else:
            cursor.execute(
                '''SELECT bot,
                          AVG(notional) as avg_notional,
                          AVG(risk_usd) as avg_risk_usd,
                          COUNT(*) as trades
                   FROM trades
                   WHERE notional IS NOT NULL
                   GROUP BY bot'''
            )
            rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        # Limpieza de None
        out = []
        for r in rows:
            if not r:
                continue
            name = r.get('bot') or 'SIN_BOT'
            out.append({
                'bot': name,
                'avg_notional': float(r.get('avg_notional') or 0.0),
                'avg_risk_usd': float(r.get('avg_risk_usd') or 0.0),
                'trades': int(r.get('trades') or 0)
            })
        return out
    
    def add_order(
        self,
        trade_id: int,
        order_id: str,
        order_type: str,
        side: str,
        symbol: str,
        price: Optional[float] = None,
        quantity: Optional[float] = None,
        status: str = "NEW",
        client_order_id: Optional[str] = None,
        position_id: Optional[str] = None
    ):
        """Registra una orden individual asociada a un trade"""
        conn = self._connect()
        cursor = conn.cursor()

        created_time = datetime.now()

        cursor.execute('''
            INSERT INTO orders (
                trade_id, order_id, order_type, side, symbol,
                price, quantity, status, created_time, client_order_id, position_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_id, order_id, order_type, side, symbol,
            price, quantity, status, created_time, client_order_id, position_id
        ))
        conn.commit()
        conn.close()

    def create_entry_attempt(
        self,
        symbol: str,
        side: str,
        bot: Optional[str] = None,
        bot_id: Optional[str] = None,
        context: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> int:
        """Inserta un intento de entrada en estado PENDING."""
        conn = self._connect()
        cursor = conn.cursor()
        requested_at = datetime.now()
        metadata_json = json.dumps(metadata) if metadata else None
        cursor.execute('''
            INSERT INTO entry_attempts (
                symbol, side, bot, bot_id, requested_at, status, context, metadata
            ) VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?)
        ''', (symbol, side, bot, bot_id, requested_at, context, metadata_json))
        attempt_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return attempt_id

    def finish_entry_attempt(
        self,
        attempt_id: int,
        status: str,
        reason: Optional[str] = None,
        trade_id: Optional[int] = None,
        entry_order_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """Actualiza un intento de entrada con el resultado final."""
        conn = self._connect()
        cursor = conn.cursor()
        completed_at = datetime.now()
        metadata_json = json.dumps(metadata) if metadata else None
        cursor.execute('''
            UPDATE entry_attempts
            SET status = ?, reason = ?, completed_at = ?, trade_id = ?, entry_order_id = ?, metadata = COALESCE(?, metadata)
            WHERE id = ?
        ''', (status, reason, completed_at, trade_id, entry_order_id, metadata_json, attempt_id))
        conn.commit()
        conn.close()

    def log_trade_event(
        self,
        trade_id: Optional[int],
        event_type: str,
        details: Optional[str] = None,
        payload: Optional[Dict] = None,
        event_time: Optional[datetime] = None
    ) -> int:
        """Registra un evento/auditoría relacionado con un trade."""
        conn = self._connect()
        cursor = conn.cursor()
        when = event_time or datetime.now()
        payload_json = json.dumps(payload) if payload else None
        cursor.execute('''
            INSERT INTO trade_events (trade_id, event_type, event_time, payload, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (trade_id, event_type, when, payload_json, details))
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return event_id

    def log_sl_update(
        self,
        trade_id: int,
        old_sl: Optional[float],
        new_sl: float,
        trigger: str,
        order_id: Optional[str] = None,
        extra: Optional[Dict] = None
    ) -> None:
        """Audita movimiento de SL dinámico."""
        payload = {
            "old_sl": old_sl,
            "new_sl": new_sl,
            "trigger": trigger,
            "order_id": order_id
        }
        if extra:
            payload.update(extra)
        self.log_trade_event(
            trade_id=trade_id,
            event_type="SL_UPDATE",
            payload=payload
        )

    def get_order_by_id(self, order_id: str) -> Optional[Dict]:
        """Retrieve a single order by its Binance order_id."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM orders WHERE order_id = ?', (str(order_id),))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_order_status(self, order_id: str, status: str, timestamp: Optional[datetime] = None) -> None:
        """Update status (and optionally timestamp) of an order."""
        conn = self._connect()
        cursor = conn.cursor()
        params = [status]
        set_clause = "status = ?"
        if timestamp is None:
            if status.upper() == "CANCELLED":
                timestamp = datetime.now()
        if timestamp is not None:
            set_clause += ", filled_time = ?"
            params.append(timestamp)
        params.append(str(order_id))
        cursor.execute(f"UPDATE orders SET {set_clause} WHERE order_id = ?", params)
        conn.commit()
        conn.close()

    def update_trade_sl(self, trade_id: int, sl_price: float) -> None:
        """Persist the latest stop-loss price for a trade."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('UPDATE trades SET sl_price = ? WHERE id = ?', (float(sl_price), int(trade_id)))
        conn.commit()
        conn.close()

    def update_order_fill(self, order_id: str, filled_price: Optional[float] = None, filled_qty: Optional[float] = None, filled_time: Optional[str] = None, status: Optional[str] = None) -> None:
        """Actualiza información de fill para una orden por order_id.

        Args:
            order_id: ID de la orden en Binance (texto)
            filled_price: Precio promedio de ejecución
            filled_qty: Cantidad ejecutada
            filled_time: Timestamp ISO o datetime para la ejecución
            status: Nuevo estado (por defecto 'FILLED' si se proveen fills)
        """
        conn = self._connect()
        cursor = conn.cursor()
        set_parts = []
        params: list = []
        if filled_price is not None:
            set_parts.append("filled_price = ?")
            params.append(float(filled_price))
        if filled_qty is not None:
            set_parts.append("filled_qty = ?")
            params.append(float(filled_qty))
        if filled_time is not None:
            set_parts.append("filled_time = ?")
            params.append(filled_time)
        if status is None and (filled_price is not None or filled_qty is not None or filled_time is not None):
            status = 'FILLED'
        if status is not None:
            set_parts.append("status = ?")
            params.append(status)
        if not set_parts:
            conn.close()
            return
        params.append(str(order_id))
        sql = f"UPDATE orders SET {', '.join(set_parts)} WHERE order_id = ?"
        cursor.execute(sql, params)
        conn.commit()
        conn.close()
    
    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        exit_reason: str = "MANUAL",
        exit_order_id: Optional[str] = None,
        exit_client_order_id: Optional[str] = None,
        margin_balance_exit: Optional[float] = None
    ):
        """Cierra un trade y calcula el PnL correctamente.

        - pnl (USDT): basado en cantidad y movimiento de precio (NO multiplica por leverage)
          LONG:  (exit - entry) * qty
          SHORT: (entry - exit) * qty
        - pnl_percent (%): ROE% aproximado = retorno de precio con signo multiplicado por leverage
        """
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM trades WHERE id = ?', (trade_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            print(f"⚠️ Trade {trade_id} no encontrado")
            return

        trade = dict(row)

        status = (trade.get('status') or '').upper()
        if status == 'CLOSED':
            conn.close()
            print(f"⚠️ Trade {trade_id} ya está cerrado")
            return

        if exit_price <= 0:
            conn.close()
            print(f"⚠️ Precio de salida inválido: {exit_price}")
            return

        try:
            entry_price = float(trade.get('entry_price'))
            quantity = float(trade.get('quantity'))
            leverage = int(trade.get('leverage') or 1)
            side = str(trade.get('side') or '').upper()
        except Exception:
            conn.close()
            print(f"⚠️ Datos inválidos para cierre de trade {trade_id}")
            return

        if entry_price <= 0 or quantity <= 0:
            conn.close()
            print(f"⚠️ Datos inválidos - Entry: {entry_price}, Qty: {quantity}")
            return

        pnl = None
        avg_exit = None
        try:
            conn2 = sqlite3.connect(self.db_path)
            conn2.row_factory = sqlite3.Row
            c2 = conn2.cursor()
            c2.execute('''
                SELECT filled_price, filled_qty, order_type
                FROM orders
                WHERE trade_id = ? AND status = 'FILLED' AND (
                    order_type = 'STOP_LOSS' OR order_type LIKE 'TAKE_PROFIT%'
                )
            ''', (trade_id,))
            fills = [dict(r) for r in c2.fetchall()]
            conn2.close()

            total_qty = 0.0
            pnl_sum = 0.0
            weighted_px_sum = 0.0
            for f in fills:
                fp = f.get('filled_price')
                fq = f.get('filled_qty')
                if fp is None or fq is None:
                    continue
                fp = float(fp)
                fq = float(fq)
                if fq <= 0:
                    continue
                if side == "LONG":
                    pnl_sum += (fp - entry_price) * fq
                else:
                    pnl_sum += (entry_price - fp) * fq
                weighted_px_sum += fp * fq
                total_qty += fq

            remaining_qty = max(quantity - total_qty, 0.0)
            if total_qty > 0.0:
                if remaining_qty > 0.0 and exit_price > 0:
                    if side == "LONG":
                        pnl_sum += (exit_price - entry_price) * remaining_qty
                    else:
                        pnl_sum += (entry_price - exit_price) * remaining_qty
                    weighted_px_sum += exit_price * remaining_qty
                    total_qty += remaining_qty

                pnl = pnl_sum
                avg_exit = (weighted_px_sum / total_qty) if total_qty > 0 else exit_price
        except Exception:
            pnl = None
            avg_exit = None

        if pnl is None:
            if side == "LONG":
                pnl = (exit_price - entry_price) * quantity
            else:
                pnl = (entry_price - exit_price) * quantity
            avg_exit = exit_price

        price_ret = ((avg_exit - entry_price) / entry_price)
        if side == "SHORT":
            price_ret = -price_ret
        pnl_percent = price_ret * leverage * 100.0

        margin_entry_ref = None
        try:
            if trade.get('margin_balance_entry') is not None:
                margin_entry_ref = float(trade.get('margin_balance_entry'))
            elif trade.get('margin_balance_post_entry') is not None:
                margin_entry_ref = float(trade.get('margin_balance_post_entry'))
        except Exception:
            margin_entry_ref = None

        margin_pnl = None
        if margin_entry_ref is not None and margin_balance_exit is not None:
            try:
                margin_pnl = float(margin_balance_exit) - float(margin_entry_ref)
            except Exception:
                margin_pnl = None

        exit_time = datetime.now()

        update_fields = [
            ('exit_price', avg_exit),
            ('exit_time', exit_time),
            ('status', 'CLOSED'),
            ('pnl', pnl),
            ('pnl_percent', pnl_percent),
            ('exit_reason', exit_reason)
        ]
        if exit_order_id is not None:
            update_fields.append(('exit_order_id', exit_order_id))
        if exit_client_order_id is not None:
            update_fields.append(('exit_client_order_id', exit_client_order_id))
        if margin_balance_exit is not None:
            update_fields.append(('margin_balance_exit', margin_balance_exit))
        if margin_pnl is not None:
            update_fields.append(('margin_pnl', margin_pnl))

        set_clause = ', '.join(f"{col} = ?" for col, _ in update_fields)
        params = [val for _, val in update_fields]
        params.append(trade_id)

        cursor.execute(
            f"UPDATE trades SET {set_clause} WHERE id = ? AND status = 'OPEN'",
            tuple(params)
        )

        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        if rows_affected > 0:
            symbol = trade.get('symbol')
            pnl_icon = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
            margin_msg = f" | ΔMargin: {margin_pnl:+.2f}" if margin_pnl is not None else ""
            print(f"✅ Trade {trade_id} ({symbol}) cerrado: {pnl_icon} ${pnl:.2f} ({pnl_percent:+.2f}%) - {exit_reason}{margin_msg}")
            self.update_daily_stats()
        else:
            print(f"⚠️ Trade {trade_id} no pudo cerrarse (ya estaba cerrado o no existe)")

    def recalc_closed_trades_pnl(self) -> int:
        """Recalcula y corrige pnl y pnl_percent de todos los trades cerrados.

        Devuelve la cantidad de filas actualizadas.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, side, entry_price, exit_price, quantity, leverage
            FROM trades
            WHERE status = 'CLOSED' AND exit_price IS NOT NULL
        ''')
        rows = cursor.fetchall()

        updated = 0
        for r in rows:
            try:
                side = (r["side"] or "").upper()
                entry = float(r["entry_price"])
                exitp = float(r["exit_price"]) if r["exit_price"] is not None else None
                qty = float(r["quantity"]) if r["quantity"] is not None else None
                lev = int(r["leverage"]) if r["leverage"] is not None else 1
                if exitp is None or qty is None:
                    continue

                # Intentar usar fills del trade para recalcular
                cursor2 = conn.cursor()
                cursor2.execute('''
                    SELECT filled_price, filled_qty
                    FROM orders
                    WHERE trade_id = ? AND status = 'FILLED' AND (
                        order_type = 'STOP_LOSS' OR order_type LIKE 'TAKE_PROFIT%'
                    )
                ''', (r["id"],))
                fills = cursor2.fetchall()

                total_qty = 0.0
                pnl_sum = 0.0
                weighted_px_sum = 0.0
                for fp, fq in fills:
                    if fp is None or fq is None:
                        continue
                    fp = float(fp); fq = float(fq)
                    if fq <= 0:
                        continue
                    if side == "LONG":
                        pnl_sum += (fp - entry) * fq
                    else:
                        pnl_sum += (entry - fp) * fq
                    weighted_px_sum += fp * fq
                    total_qty += fq

                # Si no hay fills, usar cálculo básico
                if total_qty <= 0:
                    # price return con signo
                    price_ret = ((exitp - entry) / entry)
                    if side == "SHORT":
                        price_ret = -price_ret
                    pnl = (exitp - entry) * qty if side == "LONG" else (entry - exitp) * qty
                    pnl_percent = price_ret * lev * 100.0
                else:
                    # Si quedó remanente no cubierto por fills, asumir al exitp
                    remaining_qty = max(qty - total_qty, 0.0)
                    if remaining_qty > 0:
                        if side == "LONG":
                            pnl_sum += (exitp - entry) * remaining_qty
                        else:
                            pnl_sum += (entry - exitp) * remaining_qty
                        weighted_px_sum += exitp * remaining_qty
                        total_qty += remaining_qty
                    avg_exit = weighted_px_sum / total_qty if total_qty > 0 else exitp
                    price_ret = ((avg_exit - entry) / entry)
                    if side == "SHORT":
                        price_ret = -price_ret
                    pnl = pnl_sum
                    pnl_percent = price_ret * lev * 100.0

                cursor.execute(
                    "UPDATE trades SET pnl = ?, pnl_percent = ? WHERE id = ?",
                    (pnl, pnl_percent, r["id"]) 
                )
                updated += 1
            except Exception:
                # Si algo falla para una fila, continuar con la siguiente
                continue

        conn.commit()
        conn.close()
        if updated:
            print(f"🛠️ Recalculados pnl/pnl_percent en {updated} trades cerrados")
        return updated
    
    def get_open_trades(self) -> List[Dict]:
        """Obtiene todos los trades abiertos"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades 
            WHERE status = 'OPEN'
            ORDER BY entry_time DESC
        ''')
        
        trades = []
        for row in cursor.fetchall():
            trade = dict(row)
            if trade['tp_prices']:
                trade['tp_prices'] = json.loads(trade['tp_prices'])
            trades.append(trade)
        
        conn.close()
        return trades
    
    def get_closed_trades(self, limit: Optional[int] = None, bot: Optional[str] = None, since: Optional[datetime] = None) -> List[Dict]:
        """Obtiene trades cerrados. Si 'bot' se indica, filtra por la columna 'bot' (fallback: notes LIKE).
        Si existe una sesión para ese bot o se pasa 'since', solo devuelve a partir de esa fecha.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = '''
            SELECT * FROM trades 
            WHERE status = 'CLOSED'
        '''
        params: list = []
        if bot:
            # Intentar por columna 'bot'; si hay NULL/"", también considerar notes LIKE como respaldo
            query += " AND (bot = ? OR (bot IS NULL AND notes LIKE ?))"
            params.extend([bot, f"%{bot}%"]) 

            # Aplicar sesión si no se pasó 'since'
            if since is None:
                start = self.get_bot_session_start(bot)
                if start is not None:
                    since = start

        if since is not None:
            query += " AND COALESCE(exit_time, entry_time) >= ?"
            params.append(since)
        query += " ORDER BY exit_time DESC"
        
        if limit:
            query += f' LIMIT {limit}'
        
        cursor.execute(query, params)
        
        trades = []
        for row in cursor.fetchall():
            trade = dict(row)
            if trade['tp_prices']:
                trade['tp_prices'] = json.loads(trade['tp_prices'])
            trades.append(trade)
        
        conn.close()
        return trades
    
    def get_trade_stats(self, bot: Optional[str] = None, since: Optional[datetime] = None) -> Dict:
        """Obtiene estadísticas generales de trading. Si 'bot' se indica, filtra por columna 'bot' (fallback: notes LIKE).
        Si existe una sesión para ese bot o se pasa 'since', solo cuenta trades desde esa fecha.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        where = "WHERE status = 'CLOSED'"
        params: list = []
        if bot:
            where += " AND (bot = ? OR (bot IS NULL AND notes LIKE ?))"
            params.extend([bot, f"%{bot}%"])
            if since is None:
                start = self.get_bot_session_start(bot)
                if start is not None:
                    since = start
        if since is not None:
            where += " AND COALESCE(exit_time, entry_time) >= ?"
            params.append(since)
        
        # Total de trades
        cursor.execute(f"SELECT COUNT(*) FROM trades {where}", params)
        total_trades = cursor.fetchone()[0]
        
        if total_trades == 0:
            conn.close()
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'best_trade': 0,
                'worst_trade': 0,
                'profit_factor': 0
            }
        
        # Trades ganadores
        cursor.execute(f"SELECT COUNT(*) FROM trades {where} AND pnl > 0", params)
        winning_trades = cursor.fetchone()[0]
        
        # Trades perdedores
        cursor.execute(f"SELECT COUNT(*) FROM trades {where} AND pnl < 0", params)
        losing_trades = cursor.fetchone()[0]
        
        # PnL total
        cursor.execute(f"SELECT SUM(pnl) FROM trades {where}", params)
        total_pnl = cursor.fetchone()[0] or 0
        
        # Promedio de ganancias
        cursor.execute(f"SELECT AVG(pnl) FROM trades {where} AND pnl > 0", params)
        avg_win = cursor.fetchone()[0] or 0
        
        # Promedio de pérdidas
        cursor.execute(f"SELECT AVG(pnl) FROM trades {where} AND pnl < 0", params)
        avg_loss = cursor.fetchone()[0] or 0
        
        # Mejor trade
        cursor.execute(f"SELECT MAX(pnl) FROM trades {where}", params)
        best_trade = cursor.fetchone()[0] or 0
        
        # Peor trade
        cursor.execute(f"SELECT MIN(pnl) FROM trades {where}", params)
        worst_trade = cursor.fetchone()[0] or 0
        
        # Ganancias totales
        cursor.execute(f"SELECT SUM(pnl) FROM trades {where} AND pnl > 0", params)
        total_wins = cursor.fetchone()[0] or 0
        
        # Pérdidas totales
        cursor.execute(f"SELECT SUM(pnl) FROM trades {where} AND pnl < 0", params)
        total_losses = abs(cursor.fetchone()[0] or 0)
        
        conn.close()
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        profit_factor = (total_wins / total_losses) if total_losses > 0 else float('inf')
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'profit_factor': profit_factor
        }
    
    def update_daily_stats(self):
        """Actualiza las estadísticas del día actual"""
        conn = self._connect()
        cursor = conn.cursor()

        today = datetime.now().date()
        
        # Obtener trades del día
        cursor.execute('''
            SELECT COUNT(*), 
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                   SUM(pnl) as total_pnl,
                   MAX(pnl) as best_trade,
                   MIN(pnl) as worst_trade
            FROM trades 
            WHERE DATE(exit_time) = ? AND status = 'CLOSED'
        ''', (today,))
        
        result = cursor.fetchone()
        total_trades = result[0] or 0
        winning_trades = result[1] or 0
        losing_trades = result[2] or 0
        total_pnl = result[3] or 0
        best_trade = result[4] or 0
        worst_trade = result[5] or 0
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Actualizar o insertar
        cursor.execute('''
            INSERT OR REPLACE INTO daily_stats 
            (date, total_trades, winning_trades, losing_trades, 
             total_pnl, win_rate, best_trade, worst_trade)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (today, total_trades, winning_trades, losing_trades,
              total_pnl, win_rate, best_trade, worst_trade))
        conn.commit()
        conn.close()
    
    def get_trades_by_symbol(self, symbol: str) -> List[Dict]:
        """Obtiene todos los trades de un símbolo específico"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades 
            WHERE symbol = ? AND status = 'CLOSED'
            ORDER BY exit_time DESC
        ''', (symbol,))
        
        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return trades

    def get_trades_by_bot(self, bot: str, limit: Optional[int] = None) -> List[Dict]:
        """Obtiene trades cerrados filtrando por la columna 'bot' (fallback: notes LIKE)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = '''
            SELECT * FROM trades
            WHERE status = 'CLOSED' AND (bot = ? OR (bot IS NULL AND notes LIKE ?))
            ORDER BY exit_time DESC
        '''
        if limit:
            query += f' LIMIT {limit}'
        cursor.execute(query, (bot, f"%{bot}%"))
        rows = cursor.fetchall()
        trades = [dict(r) for r in rows]
        conn.close()
        return trades

    def get_distinct_bots(self) -> List[str]:
        """Devuelve la lista de bots distintos presentes en la base (excluyendo NULL y '')."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT bot FROM trades WHERE bot IS NOT NULL AND bot <> ''")
        bots = [r[0] for r in cursor.fetchall()]
        conn.close()
        return bots

    def get_bot_summary(self) -> List[Dict]:
        """Resumen por bot: trades, pnl. Incluye totales al final."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COALESCE(bot, 'SIN_BOT') as bot,
                   COUNT(*) as trades,
                   SUM(CASE WHEN pnl IS NULL THEN 0 ELSE pnl END) as total_pnl
            FROM trades
            WHERE status = 'CLOSED'
            GROUP BY COALESCE(bot, 'SIN_BOT')
            ORDER BY trades DESC
        ''')
        rows = [dict(r) for r in cursor.fetchall()]
        # Totales
        cursor.execute("SELECT COUNT(*), SUM(CASE WHEN pnl IS NULL THEN 0 ELSE pnl END) FROM trades WHERE status='CLOSED'")
        t = cursor.fetchone()
        conn.close()
        total_trades = t[0] or 0
        total_pnl = t[1] or 0.0
        rows.append({"bot": "TOTAL", "trades": total_trades, "total_pnl": total_pnl})
        return rows

    # ===== Sesiones por bot =====
    def start_bot_session(self, bot: str, start_time: Optional[datetime] = None) -> None:
        """Inicia o reinicia la sesión (baseline) de un bot desde 'start_time' (o ahora)."""
        if start_time is None:
            start_time = datetime.now()
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO bot_sessions (bot, start_time) VALUES (?, ?)",
            (bot, start_time),
        )
        conn.commit()
        conn.close()

    def clear_bot_session(self, bot: str) -> None:
        """Elimina la sesión (baseline) de un bot."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bot_sessions WHERE bot = ?", (bot,))
        conn.commit()
        conn.close()

    def get_bot_session_start(self, bot: str) -> Optional[str]:
        """Obtiene el inicio de sesión de un bot o None si no existe."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT start_time FROM bot_sessions WHERE bot = ?", (bot,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None


# Función de prueba
if __name__ == "__main__":
    print("🗄️ Probando sistema de base de datos...\n")
    
    db = TradingDatabase("test_trading.db")
    
    # Ejemplo: Agregar un trade
    trade_id = db.add_trade(
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        quantity=0.1,
        leverage=5,
        sl_price=49000.0,
        tp_prices=[51000.0, 52000.0, 53000.0],
        timeframe="1h",
        notes="Señal EMA alcista"
    )
    
    # Simular cierre de trade
    db.close_trade(trade_id, exit_price=51500.0, exit_reason="TP1")
    
    # Obtener estadísticas
    stats = db.get_trade_stats()
    print(f"\n📊 Estadísticas:")
    print(f"  Total trades: {stats['total_trades']}")
    print(f"  Win rate: {stats['win_rate']:.2f}%")
    print(f"  PnL total: ${stats['total_pnl']:.2f}")
    
    print(f"\n✅ Base de datos funcionando correctamente!")
