"""
Generador de gráficos y reportes de trading
Visualiza el rendimiento del bot y estadísticas
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import pandas as pd
from trading_database import TradingDatabase
from typing import Optional
import os

class TradingDashboard:
    def __init__(self, db_path: str = "trading_history.db"):
        """Inicializa el dashboard con la base de datos"""
        self.db = TradingDatabase(db_path)
        
        # Configurar estilo de matplotlib
        plt.style.use('seaborn-v0_8-darkgrid')
        self.colors = {
            'profit': '#26a69a',  # Verde
            'loss': '#ef5350',    # Rojo
            'neutral': '#78909c'  # Gris
        }
        # Filtro actual de bot para gráficos (None = todos)
        self._filter_bot = None
    
    def generate_full_report(self, output_dir: str = "reports", bot: Optional[str] = None):
        """Genera un reporte completo con todos los gráficos.
        Si 'bot' se especifica, filtra las estadísticas y trades por ese bot (campo 'notes').
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        print("Generando reporte completo...\n")
        # Guardar filtro de bot para usos internos durante este render
        self._filter_bot = bot
        
        # Crear figura con múltiples subgráficos
        fig = plt.figure(figsize=(20, 12))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        
        # 1. Curva de equity
        ax1 = fig.add_subplot(gs[0, :])
        self._plot_equity_curve(ax1)
        
        # 2. Distribución de PnL
        ax2 = fig.add_subplot(gs[1, 0])
        self._plot_pnl_distribution(ax2)
        
        # 3. Win Rate
        ax3 = fig.add_subplot(gs[1, 1])
        self._plot_win_rate(ax3)
        
        # 4. Trades por símbolo
        ax4 = fig.add_subplot(gs[1, 2])
        self._plot_trades_by_symbol(ax4)
        
        # 5. Performance por timeframe
        ax5 = fig.add_subplot(gs[2, 0])
        self._plot_performance_by_timeframe(ax5)
        
        # 6. Distribución de duración de trades
        ax6 = fig.add_subplot(gs[2, 1])
        self._plot_trade_duration(ax6)
        
        # 7. Métricas resumen
        ax7 = fig.add_subplot(gs[2, 2])
        self._plot_summary_metrics(ax7)
        
        # Título general
        stats = self.db.get_trade_stats(bot=self._filter_bot)
        title_prefix = f"Dashboard de Trading"
        if self._filter_bot:
            title_prefix += f" - Bot: {self._filter_bot}"
        fig.suptitle(
            f'{title_prefix} - Total PnL: ${stats["total_pnl"]:.2f} | Win Rate: {stats["win_rate"]:.1f}%',
            fontsize=16, fontweight='bold'
        )
        
        # Guardar
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(output_dir, f"trading_report_{timestamp}.png")
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        print(f"Reporte guardado: {filepath}")
        
        plt.close()
        
        # Generar también reporte de texto
        self._generate_text_report(output_dir, timestamp, bot=self._filter_bot)
        
        return filepath

    def generate_consolidated_report(self, output_dir: str = "reports", filename_base: str = "trading_report", bot: Optional[str] = None):
        """Genera un reporte completo pero guardando SIEMPRE con el mismo nombre (pisa el anterior).
        Si 'bot' es None, incluye TODOS los bots (reporte unificado).
        Crea dos archivos:
          - PNG: {output_dir}/{filename_base}.png
          - TXT: {output_dir}/{filename_base}.txt
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Guardar filtro de bot para usos internos durante este render
        self._filter_bot = bot

        # Crear figura con múltiples subgráficos (idéntico a generate_full_report)
        fig = plt.figure(figsize=(20, 12))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

        ax1 = fig.add_subplot(gs[0, :])
        self._plot_equity_curve(ax1)

        ax2 = fig.add_subplot(gs[1, 0])
        self._plot_pnl_distribution(ax2)

        ax3 = fig.add_subplot(gs[1, 1])
        self._plot_win_rate(ax3)

        ax4 = fig.add_subplot(gs[1, 2])
        self._plot_trades_by_symbol(ax4)

        ax5 = fig.add_subplot(gs[2, 0])
        self._plot_performance_by_timeframe(ax5)

        ax6 = fig.add_subplot(gs[2, 1])
        self._plot_trade_duration(ax6)

        ax7 = fig.add_subplot(gs[2, 2])
        self._plot_summary_metrics(ax7)

        stats = self.db.get_trade_stats(bot=self._filter_bot)
        title_prefix = f"Dashboard de Trading"
        if self._filter_bot:
            title_prefix += f" - Bot: {self._filter_bot}"
        fig.suptitle(
            f'{title_prefix} - Total PnL: ${stats["total_pnl"]:.2f} | Win Rate: {stats["win_rate"]:.1f}%',
            fontsize=16, fontweight='bold'
        )

        # Guardado fijo (sin timestamp): pisa el anterior
        png_path = os.path.join(output_dir, f"{filename_base}.png")
        plt.savefig(png_path, dpi=300, bbox_inches='tight')
        print(f"Reporte guardado (consolidado): {png_path}")
        plt.close()

        # Reporte de texto fijo
        self._generate_text_report_fixed(output_dir, filename_base, bot=self._filter_bot)

        return png_path

    def _generate_text_report_fixed(self, output_dir: str, filename_base: str, bot: Optional[str] = None):
        """Versión fija del reporte de texto, pisa el archivo anterior."""
        stats = self.db.get_trade_stats(bot=bot)
        trades = self.db.get_closed_trades(limit=10, bot=bot)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report = f"""
╔═══════════════════════════════════════════════════════════════╗
║              REPORTE DE TRADING (CONSOLIDADO)                 ║
╚═══════════════════════════════════════════════════════════════╝

Generado: {ts}

ESTADÍSTICAS GENERALES{(' - Bot: ' + bot) if bot else ''}
{'='*60}
Total de Trades:           {stats['total_trades']}
Trades Ganadores:          {stats['winning_trades']} ({stats['win_rate']:.1f}%)
Trades Perdedores:         {stats['losing_trades']} ({100-stats['win_rate']:.1f}%)

RENDIMIENTO
{'='*60}
PnL Total:                 ${stats['total_pnl']:.2f}
Promedio Ganancia:         ${stats['avg_win']:.2f}
Promedio Pérdida:          ${stats['avg_loss']:.2f}
Mejor Trade:               ${stats['best_trade']:.2f}
Peor Trade:                ${stats['worst_trade']:.2f}
Profit Factor:             {stats['profit_factor']:.2f}

ÚLTIMOS 10 TRADES
{'='*60}
"""

        for i, trade in enumerate(trades, 1):
            pnl_sign = "+" if trade['pnl'] > 0 else ""
            report += f"""
Trade #{i}:
  Símbolo:    {trade['symbol']}
  Lado:       {trade['side']}
  Entrada:    ${trade['entry_price']:.2f}
  Salida:     ${trade['exit_price']:.2f}
  PnL:        {pnl_sign}${trade['pnl']:.2f} ({pnl_sign}{trade['pnl_percent']:.2f}%)
  Razón:      {trade['exit_reason']}
  Timeframe:  {trade.get('timeframe', 'N/A')}
  Fecha:      {trade['exit_time']}
"""

        filepath = os.path.join(output_dir, f"{filename_base}.txt")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Reporte de texto guardado (consolidado): {filepath}")
    
    def _plot_equity_curve(self, ax):
        """Gráfico de curva de equity (balance acumulado)"""
        trades = self.db.get_closed_trades(bot=self._filter_bot)
        
        if not trades:
            ax.text(0.5, 0.5, 'No hay datos suficientes', 
                   ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Curva de Equity')
            return
        
        # Ordenar por fecha
        trades_sorted = sorted(trades, key=lambda x: x['exit_time'])
        
        dates = [datetime.strptime(t['exit_time'], '%Y-%m-%d %H:%M:%S.%f') 
                for t in trades_sorted]
        pnls = [t['pnl'] for t in trades_sorted]
        
        # Calcular equity acumulado
        equity = [sum(pnls[:i+1]) for i in range(len(pnls))]
        
        ax.plot(dates, equity, linewidth=2, color=self.colors['profit'], marker='o', markersize=4)
        ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax.fill_between(dates, equity, 0, alpha=0.3, color=self.colors['profit'])
        
        ax.set_title('Curva de Equity', fontsize=14, fontweight='bold')
        ax.set_xlabel('Fecha')
        ax.set_ylabel('PnL Acumulado ($)')
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    def _plot_pnl_distribution(self, ax):
        """Distribución de ganancias y pérdidas"""
        trades = self.db.get_closed_trades(bot=self._filter_bot)
        
        if not trades:
            ax.text(0.5, 0.5, 'No hay datos', ha='center', va='center', 
                   transform=ax.transAxes)
            ax.set_title('Distribución de PnL')
            return
        
        pnls = [t['pnl'] for t in trades]
        colors = [self.colors['profit'] if p > 0 else self.colors['loss'] for p in pnls]
        
        ax.bar(range(len(pnls)), pnls, color=colors, alpha=0.7)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
        
        ax.set_title('Distribución de PnL por Trade', fontsize=12, fontweight='bold')
        ax.set_xlabel('Trade #')
        ax.set_ylabel('PnL ($)')
        ax.grid(True, alpha=0.3, axis='y')
    
    def _plot_win_rate(self, ax):
        """Gráfico de win rate"""
        stats = self.db.get_trade_stats(bot=self._filter_bot)
        
        if stats['total_trades'] == 0:
            ax.text(0.5, 0.5, 'No hay datos', ha='center', va='center', 
                   transform=ax.transAxes)
            ax.set_title('Win Rate')
            return
        
        sizes = [stats['winning_trades'], stats['losing_trades']]
        labels = [f"Ganados\n{stats['winning_trades']}", 
                 f"Perdidos\n{stats['losing_trades']}"]
        colors = [self.colors['profit'], self.colors['loss']]
        
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, colors=colors, autopct='%1.1f%%',
            startangle=90, textprops={'fontsize': 10, 'weight': 'bold'}
        )
        
        ax.set_title(f"Win Rate: {stats['win_rate']:.1f}%", 
                    fontsize=12, fontweight='bold')
    
    def _plot_trades_by_symbol(self, ax):
        """Gráfico de trades por símbolo"""
        trades = self.db.get_closed_trades(bot=self._filter_bot)
        
        if not trades:
            ax.text(0.5, 0.5, 'No hay datos', ha='center', va='center', 
                   transform=ax.transAxes)
            ax.set_title('Trades por Símbolo')
            return
        
        # Contar trades por símbolo
        symbol_counts = {}
        symbol_pnl = {}
        
        for trade in trades:
            symbol = trade['symbol']
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
            symbol_pnl[symbol] = symbol_pnl.get(symbol, 0) + trade['pnl']
        
        # Top 10 símbolos
        top_symbols = sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        symbols = [s[0] for s in top_symbols]
        counts = [s[1] for s in top_symbols]
        colors_list = [self.colors['profit'] if symbol_pnl[s] > 0 
                      else self.colors['loss'] for s in symbols]
        
        ax.barh(symbols, counts, color=colors_list, alpha=0.7)
        ax.set_title('Top 10 Símbolos Más Operados', fontsize=12, fontweight='bold')
        ax.set_xlabel('Número de Trades')
        ax.grid(True, alpha=0.3, axis='x')
    
    def _plot_performance_by_timeframe(self, ax):
        """Performance por timeframe"""
        trades = self.db.get_closed_trades(bot=self._filter_bot)
        
        if not trades:
            ax.text(0.5, 0.5, 'No hay datos', ha='center', va='center', 
                   transform=ax.transAxes)
            ax.set_title('Performance por Timeframe')
            return
        
        timeframe_pnl = {}
        timeframe_count = {}
        
        for trade in trades:
            tf = trade.get('timeframe', 'N/A')
            timeframe_pnl[tf] = timeframe_pnl.get(tf, 0) + trade['pnl']
            timeframe_count[tf] = timeframe_count.get(tf, 0) + 1
        
        timeframes = list(timeframe_pnl.keys())
        pnls = list(timeframe_pnl.values())
        colors_list = [self.colors['profit'] if p > 0 else self.colors['loss'] for p in pnls]
        
        bars = ax.bar(timeframes, pnls, color=colors_list, alpha=0.7)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
        
        # Agregar etiquetas con cantidad de trades
        for bar, tf in zip(bars, timeframes):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'({timeframe_count[tf]})',
                   ha='center', va='bottom' if height > 0 else 'top',
                   fontsize=8)
        
        ax.set_title('PnL por Timeframe', fontsize=12, fontweight='bold')
        ax.set_ylabel('PnL Total ($)')
        ax.grid(True, alpha=0.3, axis='y')
    
    def _plot_trade_duration(self, ax):
        """Distribución de duración de trades"""
        trades = self.db.get_closed_trades(bot=self._filter_bot)
        
        if not trades:
            ax.text(0.5, 0.5, 'No hay datos', ha='center', va='center', 
                   transform=ax.transAxes)
            ax.set_title('Duración de Trades')
            return
        
        durations = []
        for trade in trades:
            if trade['entry_time'] and trade['exit_time']:
                entry = datetime.strptime(trade['entry_time'], '%Y-%m-%d %H:%M:%S.%f')
                exit = datetime.strptime(trade['exit_time'], '%Y-%m-%d %H:%M:%S.%f')
                duration_hours = (exit - entry).total_seconds() / 3600
                durations.append(duration_hours)
        
        if durations:
            ax.hist(durations, bins=20, color=self.colors['neutral'], alpha=0.7, edgecolor='black')
            ax.set_title('Distribución de Duración de Trades', fontsize=12, fontweight='bold')
            ax.set_xlabel('Duración (horas)')
            ax.set_ylabel('Frecuencia')
            ax.grid(True, alpha=0.3, axis='y')
            
            avg_duration = sum(durations) / len(durations)
            ax.axvline(avg_duration, color='red', linestyle='--', linewidth=2,
                      label=f'Promedio: {avg_duration:.1f}h')
            ax.legend()
    
    def _plot_summary_metrics(self, ax):
        """Panel con métricas resumen"""
        ax.axis('off')
        stats = self.db.get_trade_stats(bot=self._filter_bot)
        
        # Preparar texto
        metrics_text = f"""
RESUMEN DE PERFORMANCE{f' - Bot: {self._filter_bot}' if self._filter_bot else ''}

Total de Trades: {stats['total_trades']}
Trades Ganadores: {stats['winning_trades']}
Trades Perdedores: {stats['losing_trades']}

PnL Total: ${stats['total_pnl']:.2f}
Promedio Ganancia: ${stats['avg_win']:.2f}
Promedio Pérdida: ${stats['avg_loss']:.2f}

Mejor Trade: ${stats['best_trade']:.2f}
Peor Trade: ${stats['worst_trade']:.2f}

Profit Factor: {stats['profit_factor']:.2f}
Win Rate: {stats['win_rate']:.1f}%
    """
        
        # Color del fondo según performance
        bg_color = self.colors['profit'] if stats['total_pnl'] > 0 else self.colors['loss']
        
        ax.text(0.5, 0.5, metrics_text.strip(), 
               ha='center', va='center',
               fontsize=11, family='monospace',
               bbox=dict(boxstyle='round', facecolor=bg_color, alpha=0.2, pad=1))
    
    def _generate_text_report(self, output_dir: str, timestamp: str, bot: Optional[str] = None):
        """Genera reporte en formato texto. Si 'bot' se pasa, filtra por ese bot."""
        stats = self.db.get_trade_stats(bot=bot)
        trades = self.db.get_closed_trades(limit=10, bot=bot)
        
        report = f"""
╔═══════════════════════════════════════════════════════════════╗
║              REPORTE DE TRADING - {timestamp}                 ║
╚═══════════════════════════════════════════════════════════════╝

ESTADÍSTICAS GENERALES{(' - Bot: ' + bot) if bot else ''}
{'='*60}
Total de Trades:           {stats['total_trades']}
Trades Ganadores:          {stats['winning_trades']} ({stats['win_rate']:.1f}%)
Trades Perdedores:         {stats['losing_trades']} ({100-stats['win_rate']:.1f}%)

RENDIMIENTO
{'='*60}
PnL Total:                 ${stats['total_pnl']:.2f}
Promedio Ganancia:         ${stats['avg_win']:.2f}
Promedio Pérdida:          ${stats['avg_loss']:.2f}
Mejor Trade:               ${stats['best_trade']:.2f}
Peor Trade:                ${stats['worst_trade']:.2f}
Profit Factor:             {stats['profit_factor']:.2f}

ÚLTIMOS 10 TRADES
{'='*60}
"""
        
        for i, trade in enumerate(trades, 1):
            pnl_sign = "+" if trade['pnl'] > 0 else ""
            report += f"""
Trade #{i}:
  Símbolo:    {trade['symbol']}
  Lado:       {trade['side']}
  Entrada:    ${trade['entry_price']:.2f}
  Salida:     ${trade['exit_price']:.2f}
  PnL:        {pnl_sign}${trade['pnl']:.2f} ({pnl_sign}{trade['pnl_percent']:.2f}%)
  Razón:      {trade['exit_reason']}
  Timeframe:  {trade.get('timeframe', 'N/A')}
  Fecha:      {trade['exit_time']}
"""
        
        # Guardar reporte
        filepath = os.path.join(output_dir, f"trading_report_{timestamp}.txt")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Reporte de texto guardado: {filepath}")

    def generate_per_bot_reports(self, output_dir: str = "reports") -> None:
        """Genera un reporte completo (png+txt) por cada bot presente en la DB."""
        bots = self.db.get_distinct_bots()
        if not bots:
            print("No hay bots registrados en la base de datos para generar reportes por bot.")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        for b in bots:
            try:
                print(f"Generando reporte para bot: {b}...")
                self.generate_full_report(output_dir=output_dir, bot=b)
            except Exception as e:
                print(f"No se pudo generar reporte para {b}: {e}")

    def sanity_check_by_bot(self) -> None:
        """Muestra un resumen rápido por bot para verificar que no 'inventa' trades."""
        rows = self.db.get_bot_summary()
        print("\n" + "-"*60)
        print("SANITY CHECK POR BOT")
        print("-"*60)
        for r in rows:
            print(f"{r['bot']}: trades={r['trades']} | total_pnl={r['total_pnl']:+.2f}")
        print("-"*60 + "\n")
    
    def plot_symbol_performance(self, symbol: str, output_dir: str = "reports"):
        """Genera gráfico específico para un símbolo"""
        trades = self.db.get_trades_by_symbol(symbol)
        
        if not trades:
            print(f"No hay trades para {symbol}")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'Performance de {symbol}', fontsize=16, fontweight='bold')
        
        # PnL por trade
        ax1 = axes[0, 0]
        pnls = [t['pnl'] for t in trades]
        colors = [self.colors['profit'] if p > 0 else self.colors['loss'] for p in pnls]
        ax1.bar(range(len(pnls)), pnls, color=colors, alpha=0.7)
        ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
        ax1.set_title('PnL por Trade')
        ax1.set_xlabel('Trade #')
        ax1.set_ylabel('PnL ($)')
        ax1.grid(True, alpha=0.3, axis='y')
        
        # Curva de equity
        ax2 = axes[0, 1]
        equity = [sum(pnls[:i+1]) for i in range(len(pnls))]
        ax2.plot(equity, linewidth=2, color=self.colors['profit'], marker='o')
        ax2.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax2.set_title('Equity Acumulado')
        ax2.set_xlabel('Trade #')
        ax2.set_ylabel('PnL Acumulado ($)')
        ax2.grid(True, alpha=0.3)
        
        # Distribución de PnL%
        ax3 = axes[1, 0]
        pnl_percents = [t['pnl_percent'] for t in trades]
        ax3.hist(pnl_percents, bins=15, color=self.colors['neutral'], alpha=0.7, edgecolor='black')
        ax3.axvline(x=0, color='red', linestyle='--', linewidth=2)
        ax3.set_title('Distribución de PnL%')
        ax3.set_xlabel('PnL %')
        ax3.set_ylabel('Frecuencia')
        ax3.grid(True, alpha=0.3, axis='y')
        
        # Métricas
        ax4 = axes[1, 1]
        ax4.axis('off')
        
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t['pnl'] > 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        total_pnl = sum(pnls)
        
        metrics_text = f"""
{symbol} - RESUMEN

Total Trades: {total_trades}
Ganadores: {winning_trades}
Win Rate: {win_rate:.1f}%

PnL Total: ${total_pnl:.2f}
Mejor: ${max(pnls):.2f}
Peor: ${min(pnls):.2f}
Promedio: ${sum(pnls)/len(pnls):.2f}
        """
        
        bg_color = self.colors['profit'] if total_pnl > 0 else self.colors['loss']
        ax4.text(0.5, 0.5, metrics_text.strip(), 
                ha='center', va='center', fontsize=12, family='monospace',
                bbox=dict(boxstyle='round', facecolor=bg_color, alpha=0.2, pad=1))
        
        # Guardar
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(output_dir, f"{symbol}_report_{timestamp}.png")
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Reporte de {symbol} guardado: {filepath}")
        return filepath


# Función para generar reporte rápido
def generate_quick_report(db_path: str = "trading_history.db", bot: Optional[str] = None):
    """Genera un reporte rápido y lo muestra en consola. Si 'bot' se indica, filtra por ese bot (campo 'notes')."""
    db = TradingDatabase(db_path)
    stats = db.get_trade_stats(bot=bot)
    
    print("\n" + "="*60)
    title = "REPORTE RÁPIDO DE TRADING" + (f" - Bot: {bot}" if bot else "")
    print(title)
    print("="*60)
    print(f"\nPnL Total: ${stats['total_pnl']:.2f}")
    print(f"Total Trades: {stats['total_trades']}")
    print(f"Win Rate: {stats['win_rate']:.1f}%")
    print(f"Mejor Trade: ${stats['best_trade']:.2f}")
    print(f"Peor Trade: ${stats['worst_trade']:.2f}")
    print(f"Profit Factor: {stats['profit_factor']:.2f}")
    print("="*60 + "\n")


# Función de prueba
if __name__ == "__main__":
    print("Probando generador de gráficos...\n")
    
    # Crear dashboard
    dashboard = TradingDashboard("test_trading.db")
    
    # Generar reporte completo
    try:
        report_path = dashboard.generate_full_report()
        print(f"\nReporte generado exitosamente!")
        print(f"Ubicación: {report_path}")
    except Exception as e:
        print(f"Error al generar reporte: {e}")
    
    # Reporte rápido
    generate_quick_report("test_trading.db")
