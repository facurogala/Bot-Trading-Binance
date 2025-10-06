"""
Generador de reportes de trading
Crea gráficos y reportes del historial de operaciones
"""
import sys
import os
from trading_dashboard import TradingDashboard, generate_quick_report
from trading_database import TradingDatabase
import argparse

def main():
    parser = argparse.ArgumentParser(description='Generador de reportes de trading')
    parser.add_argument('--db', default='trading_history.db', help='Ruta de la base de datos')
    parser.add_argument('--output', default='reports', help='Directorio de salida para reportes')
    parser.add_argument('--symbol', help='Generar reporte para un símbolo específico')
    parser.add_argument('--quick', action='store_true', help='Mostrar reporte rápido en consola')
    
    args = parser.parse_args()
    
    # Verificar que existe la base de datos
    if not os.path.exists(args.db):
        print(f"❌ Error: Base de datos no encontrada: {args.db}")
        print("💡 Ejecuta primero el bot para generar datos")
        return
    
    print("="*60)
    print("📊 GENERADOR DE REPORTES DE TRADING")
    print("="*60)
    print(f"\n📁 Base de datos: {args.db}")
    print(f"📂 Carpeta de salida: {args.output}\n")
    
    # Reporte rápido
    if args.quick:
        generate_quick_report(args.db)
        return
    
    # Crear dashboard
    dashboard = TradingDashboard(args.db)
    db = TradingDatabase(args.db)
    
    # Verificar si hay datos
    stats = db.get_trade_stats()
    if stats['total_trades'] == 0:
        print("⚠️ No hay trades cerrados en la base de datos")
        print("💡 Ejecuta el bot y espera a que se cierren algunas posiciones")
        return
    
    # Reporte de símbolo específico
    if args.symbol:
        print(f"📈 Generando reporte para {args.symbol}...")
        try:
            filepath = dashboard.plot_symbol_performance(args.symbol, args.output)
            print(f"✅ Reporte generado exitosamente!")
        except Exception as e:
            print(f"❌ Error al generar reporte: {e}")
        return
    
    # Reporte completo
    print("📊 Generando reporte completo...")
    try:
        filepath = dashboard.generate_full_report(args.output)
        print(f"\n✅ ¡Reporte generado exitosamente!")
        print(f"📁 Archivos guardados en: {args.output}/")
        
        # Mostrar resumen
        print("\n" + "="*60)
        generate_quick_report(args.db)
        
    except Exception as e:
        print(f"❌ Error al generar reporte: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
