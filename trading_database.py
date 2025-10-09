"""
Sistema de base de datos para almacenar historial de transacciones
Guarda todas las operaciones y permite análisis histórico
"""
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

class TradingDatabase:
    def __init__(self, db_path: str = "trading_history.db"):
        """Inicializa la base de datos"""
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Crea las tablas necesarias si no existen"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
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
        
        conn.commit()
        # Migración: asegurar que la columna 'bot' exista si la tabla ya existía
        try:
            cursor.execute("PRAGMA table_info(trades)")
            cols = [r[1] for r in cursor.fetchall()]
            if 'bot' not in cols:
                cursor.execute("ALTER TABLE trades ADD COLUMN bot TEXT")
                conn.commit()
            # Nuevos campos para métricas de inversión
            cursor.execute("PRAGMA table_info(trades)")
            cols = [r[1] for r in cursor.fetchall()]
            if 'notional' not in cols:
                cursor.execute("ALTER TABLE trades ADD COLUMN notional REAL")
                conn.commit()
            cursor.execute("PRAGMA table_info(trades)")
            cols = [r[1] for r in cursor.fetchall()]
            if 'risk_usd' not in cols:
                cursor.execute("ALTER TABLE trades ADD COLUMN risk_usd REAL")
                conn.commit()
        except Exception:
            pass

        # Migración: asegurar columnas de fills en 'orders'
        try:
            cursor.execute("PRAGMA table_info(orders)")
            ocols = [r[1] for r in cursor.fetchall()]
            if 'filled_price' not in ocols:
                cursor.execute("ALTER TABLE orders ADD COLUMN filled_price REAL")
                conn.commit()
            cursor.execute("PRAGMA table_info(orders)")
            ocols = [r[1] for r in cursor.fetchall()]
            if 'filled_qty' not in ocols:
                cursor.execute("ALTER TABLE orders ADD COLUMN filled_qty REAL")
                conn.commit()
            # Asegurar filled_time existe (para bases antiguas)
            cursor.execute("PRAGMA table_info(orders)")
            ocols = [r[1] for r in cursor.fetchall()]
            if 'filled_time' not in ocols:
                cursor.execute("ALTER TABLE orders ADD COLUMN filled_time TIMESTAMP")
                conn.commit()
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
            the_date = datetime.utcnow().strftime('%Y-%m-%d')
        conn = sqlite3.connect(self.db_path)
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

    def get_bot_activity(self, bot: Optional[str] = None, days: int = 30) -> List[Dict]:
        """Devuelve serie de actividad por día (últimos 'days' días)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        since = (datetime.utcnow().date()).toordinal() - days
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
        since_ts = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
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
        bot: Optional[str] = None
    ) -> int:
        """
        Registra una nueva operación
        
        Returns:
            ID del trade creado
        """
        conn = sqlite3.connect(self.db_path)
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
        
        cursor.execute('''
            INSERT INTO trades (
                symbol, side, entry_price, quantity, leverage,
                sl_price, tp_prices, entry_time, status, timeframe, notes, bot,
                notional, risk_usd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            symbol, side, entry_price, quantity, leverage,
            sl_price, tp_prices_json, entry_time, 'OPEN', timeframe, notes, bot,
            notional, risk_usd
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
        status: str = "NEW"
    ):
        """Registra una orden individual asociada a un trade"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        created_time = datetime.now()
        
        cursor.execute('''
            INSERT INTO orders (
                trade_id, order_id, order_type, side, symbol,
                price, quantity, status, created_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_id, order_id, order_type, side, symbol,
            price, quantity, status, created_time
        ))
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
        conn = sqlite3.connect(self.db_path)
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
        exit_reason: str = "MANUAL"
    ):
        """Cierra un trade y calcula el PnL correctamente.

        - pnl (USDT): basado en cantidad y movimiento de precio (NO multiplica por leverage)
          LONG:  (exit - entry) * qty
          SHORT: (entry - exit) * qty
        - pnl_percent (%): ROE% aproximado = retorno de precio con signo multiplicado por leverage
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Obtener datos del trade
        cursor.execute('SELECT * FROM trades WHERE id = ?', (trade_id,))
        trade = cursor.fetchone()
        
        if not trade:
            conn.close()
            print(f"⚠️ Trade {trade_id} no encontrado")
            return
        
        # Verificar si ya está cerrado
        if trade[11] == 'CLOSED':  # status column
            conn.close()
            print(f"⚠️ Trade {trade_id} ya está cerrado")
            return
        
        # Validar exit_price
        if exit_price <= 0:
            conn.close()
            print(f"⚠️ Precio de salida inválido: {exit_price}")
            return
        
    # Calcular PnL correcto
        entry_price = float(trade[3])  # entry_price
        quantity = float(trade[5])      # quantity
        leverage = int(trade[6]) if trade[6] is not None else 1  # leverage
        side = str(trade[2]).upper()    # side

        # Validaciones
        if entry_price <= 0 or quantity <= 0:
            conn.close()
            print(f"⚠️ Datos inválidos - Entry: {entry_price}, Qty: {quantity}")
            return

        # Intentar usar fills de órdenes para calcular PnL exacto
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

            # Si hubo fills, considerar posible resto con exit_price (por AutoCloser)
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

        # Si no hay fills, usar fórmula básica con el exit_price recibido
        if pnl is None:
            if side == "LONG":
                pnl = (exit_price - entry_price) * quantity
            else:  # SHORT
                pnl = (entry_price - exit_price) * quantity
            avg_exit = exit_price

        # ROE% aproximado con precio promedio de salida
        price_ret = ((avg_exit - entry_price) / entry_price)
        if side == "SHORT":
            price_ret = -price_ret
        pnl_percent = price_ret * leverage * 100.0
        
        exit_time = datetime.now()
        
        # Actualizar el trade
        cursor.execute('''
            UPDATE trades 
            SET exit_price = ?, exit_time = ?, status = 'CLOSED',
                pnl = ?, pnl_percent = ?, exit_reason = ?
            WHERE id = ? AND status = 'OPEN'
        ''', (avg_exit, exit_time, pnl, pnl_percent, exit_reason, trade_id))
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        if rows_affected > 0:
            symbol = trade[1]  # symbol column
            pnl_icon = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
            print(f"✅ Trade {trade_id} ({symbol}) cerrado: {pnl_icon} ${pnl:.2f} ({pnl_percent:+.2f}%) - {exit_reason}")
            
            # Actualizar estadísticas diarias
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
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO bot_sessions (bot, start_time) VALUES (?, ?)",
            (bot, start_time),
        )
        conn.commit()
        conn.close()

    def clear_bot_session(self, bot: str) -> None:
        """Elimina la sesión (baseline) de un bot."""
        conn = sqlite3.connect(self.db_path)
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
