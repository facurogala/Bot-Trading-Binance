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
                notes TEXT
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
        
        conn.commit()
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
        notes: Optional[str] = None
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
                sl_price, tp_prices, entry_time, status, timeframe, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            symbol, side, entry_price, quantity, leverage,
            sl_price, tp_prices_json, entry_time, 'OPEN', timeframe, notes
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
    
    def get_closed_trades(self, limit: Optional[int] = None) -> List[Dict]:
        """Obtiene trades cerrados"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = '''
            SELECT * FROM trades 
            WHERE status = 'CLOSED'
            ORDER BY exit_time DESC
        '''
        
        if limit:
            query += f' LIMIT {limit}'
        
        cursor.execute(query)
        
        trades = []
        for row in cursor.fetchall():
            trade = dict(row)
            if trade['tp_prices']:
                trade['tp_prices'] = json.loads(trade['tp_prices'])
            trades.append(trade)
        
        conn.close()
        return trades
    
    def get_trade_stats(self) -> Dict:
        """Obtiene estadísticas generales de trading"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total de trades
        cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'CLOSED'")
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
        cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'CLOSED' AND pnl > 0")
        winning_trades = cursor.fetchone()[0]
        
        # Trades perdedores
        cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'CLOSED' AND pnl < 0")
        losing_trades = cursor.fetchone()[0]
        
        # PnL total
        cursor.execute("SELECT SUM(pnl) FROM trades WHERE status = 'CLOSED'")
        total_pnl = cursor.fetchone()[0] or 0
        
        # Promedio de ganancias
        cursor.execute("SELECT AVG(pnl) FROM trades WHERE status = 'CLOSED' AND pnl > 0")
        avg_win = cursor.fetchone()[0] or 0
        
        # Promedio de pérdidas
        cursor.execute("SELECT AVG(pnl) FROM trades WHERE status = 'CLOSED' AND pnl < 0")
        avg_loss = cursor.fetchone()[0] or 0
        
        # Mejor trade
        cursor.execute("SELECT MAX(pnl) FROM trades WHERE status = 'CLOSED'")
        best_trade = cursor.fetchone()[0] or 0
        
        # Peor trade
        cursor.execute("SELECT MIN(pnl) FROM trades WHERE status = 'CLOSED'")
        worst_trade = cursor.fetchone()[0] or 0
        
        # Ganancias totales
        cursor.execute("SELECT SUM(pnl) FROM trades WHERE status = 'CLOSED' AND pnl > 0")
        total_wins = cursor.fetchone()[0] or 0
        
        # Pérdidas totales
        cursor.execute("SELECT SUM(pnl) FROM trades WHERE status = 'CLOSED' AND pnl < 0")
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
