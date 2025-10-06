"""
Script para generar reportes y gráficos de trading manualmente
Útil para revisar estadísticas sin esperar a que el bot las genere automáticamente
"""
import sys
import os
from trading_dashboard import TradingDashboard, generate_quick_report
from trading_database import TradingDatabase

def main():
    db_path = "trading_history.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Base de datos no encontrada: {db_path}")
        print("💡 Ejecuta primero el bot para generar datos")
        return
    
    print("="*70)
    print("📊 GENERADOR DE REPORTES DE TRADING - CONSERVADOR")
    print("="*70)
    
    # Mostrar opciones
    print("\n¿Qué deseas generar?")
    print("1. Reporte rápido en consola")
    print("2. Gráficos completos (se guardan en carpeta 'reports')")
    print("3. Ambos")
    print("0. Salir")
    
    choice = input("\nSelecciona una opción (1-3): ").strip()
    
    if choice == "0":
        return
    
    db = TradingDatabase(db_path)
    stats = db.get_trade_stats()
    
    if stats['total_trades'] == 0:
        print("\n⚠️ No hay trades cerrados en la base de datos")
        print("💡 Ejecuta el bot y espera a que se cierren algunas posiciones")
        return
    
    # Opción 1: Reporte rápido
    if choice in ["1", "3"]:
        print("\n" + "="*70)
        print("📈 REPORTE RÁPIDO")
        print("="*70)
        generate_quick_report(db_path)
    
    # Opción 2 o 3: Gráficos completos
    if choice in ["2", "3"]:
        print("\n📊 Generando gráficos completos...")
        output_dir = "reports"
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        dashboard = TradingDashboard(db_path)
        
        try:
            filepath = dashboard.generate_full_report(output_dir)
            print(f"\n✅ Reporte completo generado exitosamente!")
            print(f"📁 Ubicación: {filepath}")
            print(f"\n💡 Abre el archivo con un visor de imágenes para ver los gráficos")
        except Exception as e:
            print(f"\n❌ Error al generar gráficos: {e}")
            import traceback
            traceback.print_exc()
    
    # Mostrar resumen adicional
    print("\n" + "="*70)
    print("📊 RESUMEN DE ESTADÍSTICAS")
    print("="*70)
    print(f"📈 Total de Trades: {stats['total_trades']}")
    print(f"✅ Ganadores: {stats['winning_trades']} ({stats['win_rate']:.1f}%)")
    print(f"❌ Perdedores: {stats['losing_trades']} ({100-stats['win_rate']:.1f}%)")
    print(f"💰 PnL Total: ${stats['total_pnl']:.2f}")
    print(f"📊 PnL Promedio: ${stats['avg_pnl']:.2f}")
    print(f"🔝 Mejor Trade: ${stats['best_trade']:.2f}")
    print(f"📉 Peor Trade: ${stats['worst_trade']:.2f}")
    
    if stats['total_pnl'] > 0:
        print(f"\n🎉 ¡Vas ganando! Continúa así")
    elif stats['total_pnl'] < 0:
        print(f"\n⚠️ Revisa tu estrategia y filtros")
    else:
        print(f"\n📊 Break even - Mantén la disciplina")
    
    print("="*70)
    
    # Opción para ver trades individuales
    view_trades = input("\n¿Deseas ver los últimos 10 trades? (s/n): ").strip().lower()
    if view_trades == 's':
        print("\n" + "="*70)
        print("📋 ÚLTIMOS 10 TRADES")
        print("="*70)
        recent_trades = db.get_closed_trades(limit=10)
        
        for trade in recent_trades:
            symbol = trade.get('symbol', 'N/A')
            side = trade.get('side', 'N/A')
            entry = trade.get('entry_price', 0)
            exit_p = trade.get('exit_price', 0)
            pnl = trade.get('pnl', 0)
            pnl_pct = trade.get('pnl_percent', 0)
            status = trade.get('status', 'N/A')
            
            pnl_emoji = "✅" if pnl and pnl > 0 else "❌" if pnl and pnl < 0 else "⚪"
            
            print(f"\n{pnl_emoji} {symbol} | {side}")
            print(f"   Entry: ${entry:.2f} | Exit: ${exit_p:.2f}")
            print(f"   PnL: ${pnl:.2f} ({pnl_pct:+.2f}%) | Status: {status}")
        
        print("="*70)

if __name__ == "__main__":
    main()
