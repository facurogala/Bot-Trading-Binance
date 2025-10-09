"""
🔧 Diagnóstico y reparación de la base de datos
Verifica integridad, recalcula PnLs incorrectos y muestra estadísticas
"""
import sqlite3
from trading_database import TradingDatabase
from datetime import datetime

def diagnose_database():
    """Diagnóstico completo de la base de datos"""
    
    print("="*80)
    print("🔧 DIAGNÓSTICO DE BASE DE DATOS")
    print("="*80)
    
    db = TradingDatabase("trading_history.db")
    
    # 1. VERIFICAR ESTRUCTURA
    print("\n📋 1. VERIFICANDO ESTRUCTURA")
    print("-"*80)
    
    conn = sqlite3.connect("trading_history.db")
    cursor = conn.cursor()
    
    # Verificar tablas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    required_tables = ['trades', 'orders', 'daily_stats', 'bot_sessions', 'bot_activity']
    
    for table in required_tables:
        if table in tables:
            print(f"   ✅ Tabla '{table}' existe")
        else:
            print(f"   ❌ Tabla '{table}' NO existe")
    
    # 2. VERIFICAR TRADES ABIERTOS
    print("\n📋 2. VERIFICANDO TRADES ABIERTOS")
    print("-"*80)
    
    open_trades = db.get_open_trades()
    
    if open_trades:
        print(f"   📊 {len(open_trades)} trade(s) abierto(s):")
        for trade in open_trades:
            print(f"\n      🔹 ID: {trade['id']} | {trade['symbol']} {trade['side']}")
            print(f"         Entry: {trade['entry_price']} | Qty: {trade['quantity']}")
            print(f"         SL: {trade.get('sl_price', 'N/A')} | TPs: {len(trade.get('tp_prices', []))}")
            print(f"         Fecha: {trade['entry_time']}")
            print(f"         Bot: {trade.get('bot', 'N/A')}")
    else:
        print(f"   ℹ️  No hay trades abiertos")
    
    # 3. VERIFICAR TRADES CERRADOS
    print("\n📋 3. VERIFICANDO TRADES CERRADOS")
    print("-"*80)
    
    cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'CLOSED'")
    closed_count = cursor.fetchone()[0]
    
    print(f"   📊 {closed_count} trade(s) cerrado(s)")
    
    if closed_count > 0:
        # Verificar trades sin PnL
        cursor.execute("""
            SELECT COUNT(*) FROM trades 
            WHERE status = 'CLOSED' AND pnl IS NULL
        """)
        no_pnl = cursor.fetchone()[0]
        
        if no_pnl > 0:
            print(f"   ⚠️  {no_pnl} trade(s) cerrado(s) SIN PnL calculado")
        else:
            print(f"   ✅ Todos los trades cerrados tienen PnL")
        
        # Verificar trades con PnL = 0
        cursor.execute("""
            SELECT COUNT(*) FROM trades 
            WHERE status = 'CLOSED' AND pnl = 0
        """)
        zero_pnl = cursor.fetchone()[0]
        
        if zero_pnl > 0:
            print(f"   ⚠️  {zero_pnl} trade(s) con PnL = 0 (posible error)")
    
    # 4. VERIFICAR CONSISTENCIA DE PnL
    print("\n📋 4. VERIFICANDO CÁLCULOS DE PnL")
    print("-"*80)
    
    cursor.execute("""
        SELECT id, symbol, side, entry_price, exit_price, quantity, leverage, pnl, pnl_percent
        FROM trades
        WHERE status = 'CLOSED' AND exit_price IS NOT NULL
        LIMIT 5
    """)
    
    sample_trades = cursor.fetchall()
    
    if sample_trades:
        print("   📊 Muestra de trades cerrados (primeros 5):\n")
        
        for trade in sample_trades:
            trade_id, symbol, side, entry, exit_p, qty, lev, pnl, pnl_pct = trade
            
            # Recalcular PnL
            if side == "LONG":
                calculated_pnl = (exit_p - entry) * qty
            else:
                calculated_pnl = (entry - exit_p) * qty
            
            price_ret = ((exit_p - entry) / entry)
            if side == "SHORT":
                price_ret = -price_ret
            calculated_pnl_pct = price_ret * lev * 100.0
            
            # Comparar
            pnl_diff = abs(calculated_pnl - (pnl or 0))
            pnl_pct_diff = abs(calculated_pnl_pct - (pnl_pct or 0))
            
            status_icon = "✅" if pnl_diff < 0.01 else "⚠️"
            
            print(f"      {status_icon} ID: {trade_id} | {symbol} {side}")
            print(f"         Entry: {entry:.6f} | Exit: {exit_p:.6f} | Qty: {qty}")
            print(f"         PnL DB: ${pnl:.2f} | PnL Calc: ${calculated_pnl:.2f} | Diff: ${pnl_diff:.2f}")
            print(f"         ROE% DB: {pnl_pct:.2f}% | ROE% Calc: {calculated_pnl_pct:.2f}% | Diff: {pnl_pct_diff:.2f}%\n")
    
    # 5. ESTADÍSTICAS GENERALES
    print("\n📋 5. ESTADÍSTICAS GENERALES")
    print("-"*80)
    
    stats = db.get_trade_stats()
    
    print(f"   Total trades: {stats['total_trades']}")
    print(f"   Trades ganadores: {stats['winning_trades']} ({stats['win_rate']:.2f}%)")
    print(f"   Trades perdedores: {stats['losing_trades']}")
    print(f"   PnL total: ${stats['total_pnl']:.2f}")
    print(f"   Mejor trade: ${stats['best_trade']:.2f}")
    print(f"   Peor trade: ${stats['worst_trade']:.2f}")
    print(f"   Profit Factor: {stats['profit_factor']:.2f}")
    
    # 6. VERIFICAR ÓRDENES
    print("\n📋 6. VERIFICANDO ÓRDENES")
    print("-"*80)
    
    cursor.execute("SELECT COUNT(*) FROM orders")
    order_count = cursor.fetchone()[0]
    
    print(f"   📊 {order_count} orden(es) registrada(s)")
    
    if order_count > 0:
        cursor.execute("""
            SELECT order_type, COUNT(*) as count
            FROM orders
            GROUP BY order_type
        """)
        
        for order_type, count in cursor.fetchall():
            print(f"      - {order_type}: {count}")
    
    conn.close()
    
    # 7. RECOMENDACIONES
    print("\n📋 7. RECOMENDACIONES")
    print("-"*80)
    
    if no_pnl > 0 or zero_pnl > 0:
        print("   ⚠️  Se recomienda ejecutar el script de reparación:")
        print("      python repair_database.py")
    else:
        print("   ✅ La base de datos parece estar en buen estado")
    
    print("\n" + "="*80)


def repair_database():
    """Repara problemas comunes en la base de datos"""
    
    print("="*80)
    print("🔧 REPARACIÓN DE BASE DE DATOS")
    print("="*80)
    
    db = TradingDatabase("trading_history.db")
    
    print("\n1. Recalculando PnL de todos los trades cerrados...")
    
    updated = db.recalc_closed_trades_pnl()
    
    if updated > 0:
        print(f"   ✅ {updated} trade(s) actualizados")
    else:
        print(f"   ℹ️  No se encontraron trades para actualizar")
    
    print("\n2. Actualizando estadísticas diarias...")
    
    db.update_daily_stats()
    print(f"   ✅ Estadísticas actualizadas")
    
    print("\n3. Verificando integridad...")
    
    # Verificar trades sin entry_time
    conn = sqlite3.connect("trading_history.db")
    cursor = conn.cursor()
    
    cursor.execute("UPDATE trades SET entry_time = ? WHERE entry_time IS NULL", (datetime.now(),))
    rows_fixed = cursor.rowcount
    
    if rows_fixed > 0:
        print(f"   ✅ {rows_fixed} trade(s) sin entry_time reparados")
    
    conn.commit()
    conn.close()
    
    print("\n" + "="*80)
    print("✅ REPARACIÓN COMPLETADA")
    print("="*80)


def clear_all_trades():
    """PELIGRO: Borra todos los trades (para empezar de cero)"""
    
    print("="*80)
    print("⚠️  ¡ADVERTENCIA! BORRAR TODOS LOS TRADES")
    print("="*80)
    
    confirm1 = input("\n¿Estás seguro de que quieres borrar TODOS los trades? (si/no): ")
    
    if confirm1.lower() != "si":
        print("❌ Operación cancelada")
        return
    
    confirm2 = input("¿REALMENTE seguro? Esta acción NO se puede deshacer (SI/no): ")
    
    if confirm2 != "SI":
        print("❌ Operación cancelada")
        return
    
    conn = sqlite3.connect("trading_history.db")
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM orders")
    cursor.execute("DELETE FROM trades")
    cursor.execute("DELETE FROM daily_stats")
    cursor.execute("DELETE FROM bot_activity")
    cursor.execute("DELETE FROM bot_sessions")
    
    conn.commit()
    conn.close()
    
    print("\n✅ Todos los trades han sido borrados")
    print("   La base de datos está vacía y lista para empezar de cero")


if __name__ == "__main__":
    import sys
    
    print("\n🔧 HERRAMIENTAS DE BASE DE DATOS")
    print("="*80)
    print("1. Diagnóstico completo")
    print("2. Reparar base de datos (recalcular PnL)")
    print("3. Borrar todos los trades (PELIGRO)")
    print("="*80)
    
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = input("\nElige una opción (1/2/3): ")
    
    if choice == "1":
        diagnose_database()
    elif choice == "2":
        repair_database()
        print("\nEjecutando diagnóstico post-reparación...\n")
        diagnose_database()
    elif choice == "3":
        clear_all_trades()
    else:
        print("❌ Opción inválida")
