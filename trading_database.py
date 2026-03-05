"""
Sistema de base de datos para almacenar historial de transacciones
Guarda todas las operaciones y permite análisis histórico
"""
import sqlite3
import os
from datetime import datetime
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
        
        conn.commit()
        # Migración: asegurar que la columna 'bot' exista si la tabla ya existía
        try:
            cursor.execute("PRAGMA table_info(trades)")
            cols = [r[1] for r in cursor.fetchall()]
            if 'bot' not in cols:
                cursor.execute("ALTER TABLE trades ADD COLUMN bot TEXT")
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
        
        cursor.execute('''
            INSERT INTO trades (
                symbol, side, entry_price, quantity, leverage, 
                sl_price, tp_prices, entry_time, status, timeframe, notes, bot
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            symbol, side, entry_price, quantity, leverage,
            sl_price, tp_prices_json, entry_time, 'OPEN', timeframe, notes, bot
        ))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✅ Trade registrado: ID={trade_id}, {symbol} {side} @ {entry_price}")
        return trade_id
    
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
    
    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        exit_reason: str = "MANUAL"
    ):
        """Cierra un trade y calcula el PnL"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Obtener datos del trade
        cursor.execute('SELECT * FROM trades WHERE id = ?', (trade_id,))
        trade = cursor.fetchone()
        
        if not trade:
            conn.close()
            print(f"⚠️ Trade {trade_id} no encontrado")
            return
        
        # Calcular PnL
        entry_price = trade[3]
        quantity = trade[5]
        leverage = trade[6]
        side = trade[2]

        if not entry_price or entry_price <= 0:
            print(f"⚠️ Trade {trade_id} con entry_price inválido ({entry_price}). Cerrando sin cálculo de PnL.")
            pnl_percent = 0.0
            pnl = 0.0
            exit_time = datetime.now()
            cursor.execute('''
                UPDATE trades 
                SET exit_price = ?, exit_time = ?, status = 'CLOSED',
                    pnl = ?, pnl_percent = ?, exit_reason = ?
                WHERE id = ?
            ''', (exit_price, exit_time, pnl, pnl_percent, exit_reason, trade_id))
            conn.commit()
            conn.close()
            self.update_daily_stats()
            return
        
        if side == "LONG":
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100 * leverage
        else:  # SHORT
            pnl_percent = ((entry_price - exit_price) / entry_price) * 100 * leverage
        
        position_value = entry_price * quantity * leverage
        pnl = (pnl_percent / 100) * position_value
        
        exit_time = datetime.now()
        
        # Actualizar el trade
        cursor.execute('''
            UPDATE trades 
            SET exit_price = ?, exit_time = ?, status = 'CLOSED',
                pnl = ?, pnl_percent = ?, exit_reason = ?
            WHERE id = ?
        ''', (exit_price, exit_time, pnl, pnl_percent, exit_reason, trade_id))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Trade {trade_id} cerrado: PnL = ${pnl:.2f} ({pnl_percent:+.2f}%)")
        
        # Actualizar estadísticas diarias
        self.update_daily_stats()
    
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
