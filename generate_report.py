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
    parser.add_argument('--bot', help='Filtrar reportes por un bot específico (columna bot)')
    parser.add_argument('--per-bot', action='store_true', help='Generar un reporte por cada bot detectado en la DB')
    parser.add_argument('--sanity', action='store_true', help='Imprimir verificación rápida de trades por bot')
    parser.add_argument('--since', help='ISO datetime para calcular estadísticas desde ese momento (override de sesión)')
    parser.add_argument('--start-session', action='store_true', help='Iniciar o reiniciar sesión para --bot desde ahora (baseline)')
    parser.add_argument('--clear-session', action='store_true', help='Eliminar sesión guardada para --bot')
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
        generate_quick_report(args.db, bot=args.bot)
        return
    
    # Crear dashboard
    dashboard = TradingDashboard(args.db)
    db = TradingDatabase(args.db)

    # Recalcular PnL de trades cerrados para asegurar consistencia antes de generar reportes
    try:
        updated = db.recalc_closed_trades_pnl()
        if updated:
            print(f"🛠️ Recalculados {updated} trades cerrados (pnl y % corregidos)")
    except Exception as _e:
        # Continuar aunque falle la recalculación (no bloquear el reporte)
        print("⚠️ No se pudo ejecutar la recalculación de PnL. Continuando...")
    
    # Gestión de sesión por bot
    if args.bot and args.start_session:
        db.start_bot_session(args.bot)
        print(f"✅ Sesión iniciada para bot '{args.bot}' desde ahora")
    if args.bot and args.clear_session:
        db.clear_bot_session(args.bot)
        print(f"🧹 Sesión eliminada para bot '{args.bot}'")
    
    # Parse since (si viene)
    since_dt = None
    if args.since:
        try:
            from datetime import datetime as _dt
            since_dt = _dt.fromisoformat(args.since)
        except Exception:
            print("⚠️ --since inválido; usar formato ISO YYYY-MM-DDTHH:MM:SS")
            since_dt = None

    # Verificar si hay datos
    stats = db.get_trade_stats(bot=args.bot, since=since_dt)
    if stats['total_trades'] == 0:
        print("⚠️ No hay trades cerrados en la base de datos")
        print("💡 Ejecuta el bot y espera a que se cierren algunas posiciones")
        return
    
    # Sanity check por bot
    if args.sanity:
        dashboard.sanity_check_by_bot()
        # continuar con otras opciones

    # Reporte por bot automático
    if args.per_bot:
        dashboard.generate_per_bot_reports(args.output)
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
        filepath = dashboard.generate_full_report(args.output, bot=args.bot)
        # Generar también reporte consolidado de nombre fijo
        dashboard.generate_consolidated_report(args.output, filename_base="trading_report_all", bot=args.bot)
        print(f"\n✅ ¡Reporte generado exitosamente!")
        print(f"📁 Archivos guardados en: {args.output}/")
        
        # Mostrar resumen
        print("\n" + "="*60)
        generate_quick_report(args.db, bot=args.bot)
        
    except Exception as e:
        print(f"❌ Error al generar reporte: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
