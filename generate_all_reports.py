"""
📊 Generador Universal de Reportes
Garantiza que todos los reportes se guarden en la carpeta 'reports'
"""
import os
from trading_dashboard import TradingDashboard
from trading_database import TradingDatabase

# Directorio de reportes
REPORTS_DIR = "reports"

def ensure_reports_directory():
    """Crea el directorio de reportes si no existe"""
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)
        print(f"✅ Carpeta '{REPORTS_DIR}' creada")
    return REPORTS_DIR

def generate_all_reports(bot_name=None):
    """Genera todos los reportes y los guarda en la carpeta reports
    
    Args:
        bot_name: Nombre del bot para filtrar (opcional)
    """
    
    print("="*80)
    print("📊 GENERANDO REPORTES COMPLETOS")
    print("="*80)
    
    # Asegurar que existe el directorio
    output_dir = ensure_reports_directory()
    
    # Inicializar base de datos y dashboard
    db = TradingDatabase("trading_history.db")
    dashboard = TradingDashboard("trading_history.db")
    
    # Verificar si hay datos
    stats = db.get_trade_stats(bot=bot_name)
    
    if stats['total_trades'] == 0:
        print("\n⚠️ No hay trades cerrados en la base de datos")
        print("💡 Ejecuta los scanners y espera a que se cierren algunas posiciones")
        return False
    
    print(f"\n📊 Datos disponibles:")
    print(f"   Total trades: {stats['total_trades']}")
    print(f"   Win rate: {stats['win_rate']:.2f}%")
    print(f"   PnL total: ${stats['total_pnl']:.2f}")
    
    if bot_name:
        print(f"   Filtrado por bot: {bot_name}")
    
    # Recalcular PnL
    print(f"\n🔄 Recalculando PnL de trades cerrados...")
    updated = db.recalc_closed_trades_pnl()
    if updated > 0:
        print(f"   ✅ {updated} trade(s) recalculado(s)")
    else:
        print(f"   ℹ️  PnL ya está actualizado")
    
    # Generar reportes
    print(f"\n📈 Generando reportes en '{output_dir}/'...")
    
    try:
        # 1. Reporte consolidado (nombre fijo)
        print(f"\n   1️⃣ Reporte consolidado...")
        dashboard.generate_consolidated_report(
            output_dir=output_dir,
            filename_base="trading_report_all",
            bot=bot_name
        )
        print(f"      ✅ {output_dir}/trading_report_all.txt")
        print(f"      ✅ {output_dir}/trading_report_all.png")
        
        # 2. Reporte completo con timestamp
        print(f"\n   2️⃣ Reporte completo con timestamp...")
        full_report_path = dashboard.generate_full_report(
            output_dir=output_dir,
            bot=bot_name
        )
        print(f"      ✅ {full_report_path}")
        
        # 3. Reportes por bot (si no se filtró por bot específico)
        if not bot_name:
            print(f"\n   3️⃣ Reportes individuales por bot...")
            dashboard.generate_per_bot_reports(output_dir=output_dir)
            print(f"      ✅ Reportes generados por cada bot")
        
        print(f"\n{'='*80}")
        print(f"✅ REPORTES GENERADOS EXITOSAMENTE")
        print(f"{'='*80}")
        print(f"\n📁 Todos los archivos guardados en: {output_dir}/")
        
        # Listar archivos generados
        print(f"\n📋 Archivos en la carpeta:")
        files = sorted([f for f in os.listdir(output_dir) if f.startswith('trading_')])
        for f in files:
            size = os.path.getsize(os.path.join(output_dir, f))
            print(f"   - {f} ({size:,} bytes)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error al generar reportes: {e}")
        import traceback
        traceback.print_exc()
        return False


def clean_old_reports(keep_latest=5):
    """Limpia reportes antiguos, mantiene solo los últimos N
    
    Args:
        keep_latest: Número de reportes con timestamp a mantener
    """
    
    print("="*80)
    print("🧹 LIMPIEZA DE REPORTES ANTIGUOS")
    print("="*80)
    
    output_dir = ensure_reports_directory()
    
    # Buscar reportes con timestamp
    import re
    from datetime import datetime
    
    reports = []
    for filename in os.listdir(output_dir):
        # Buscar archivos tipo: trading_report_2025-10-08_12-30-45.*
        match = re.match(r'trading_report_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.(txt|png)$', filename)
        if match:
            timestamp_str = match.group(1)
            try:
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d_%H-%M-%S')
                reports.append({
                    'filename': filename,
                    'timestamp': timestamp,
                    'path': os.path.join(output_dir, filename)
                })
            except:
                pass
    
    if not reports:
        print("\nℹ️  No hay reportes con timestamp para limpiar")
        return
    
    # Ordenar por timestamp (más reciente primero)
    reports.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Obtener reportes a eliminar
    to_delete = reports[keep_latest:]
    
    if not to_delete:
        print(f"\nℹ️  Solo hay {len(reports)} reporte(s), no se elimina nada")
        return
    
    print(f"\n📊 Encontrados {len(reports)} reporte(s) con timestamp")
    print(f"🗑️  Se eliminarán {len(to_delete)} archivo(s) antiguos (manteniendo últimos {keep_latest})")
    
    for item in to_delete:
        try:
            os.remove(item['path'])
            print(f"   ✅ Eliminado: {item['filename']}")
        except Exception as e:
            print(f"   ❌ Error eliminando {item['filename']}: {e}")
    
    print(f"\n✅ Limpieza completada")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Generador universal de reportes')
    parser.add_argument('--bot', help='Filtrar por bot específico')
    parser.add_argument('--clean', action='store_true', help='Limpiar reportes antiguos')
    parser.add_argument('--keep', type=int, default=5, help='Reportes con timestamp a mantener (default: 5)')
    
    args = parser.parse_args()
    
    if args.clean:
        clean_old_reports(keep_latest=args.keep)
    else:
        generate_all_reports(bot_name=args.bot)


if __name__ == "__main__":
    main()
