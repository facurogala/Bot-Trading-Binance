"""
Visualizador en tiempo real del estado del trading
Muestra posiciones abiertas, estadísticas y gráficos actualizados
"""
import os
import time
from datetime import datetime
from trading_database import TradingDatabase
from trading_dashboard import generate_quick_report
from binance_futures_trader import BinanceFuturesTrader
from dotenv import load_dotenv

load_dotenv()

class TradingMonitor:
    def __init__(self):
        self.db = TradingDatabase("trading_history.db")
        
        # Intentar conectar con trader si está habilitado
        self.trader = None
        auto_trade = os.getenv("AUTO_TRADE_ENABLED", "False").lower() == "true"
        
        if auto_trade:
            try:
                self.trader = BinanceFuturesTrader()
                print("✅ Conectado a Binance Futures")
            except:
                print("⚠️ No se pudo conectar a Binance (modo solo lectura)")
    
    def show_live_positions(self):
        """Muestra las posiciones abiertas en tiempo real"""
        if not self.trader:
            print("⚠️ No hay conexión con Binance")
            return
        
        print("\n" + "="*80)
        print("📊 POSICIONES ABIERTAS EN TIEMPO REAL")
        print("="*80)
        
        positions = self.trader.get_open_positions()
        
        if not positions:
            print("\n   No hay posiciones abiertas\n")
            return
        
        total_pnl = 0
        
        for i, pos in enumerate(positions, 1):
            symbol = pos['symbol']
            side = pos['side']
            quantity = pos['quantity']
            entry = pos['entryPrice']
            pnl = pos['unrealizedProfit']
            leverage = pos['leverage']
            
            # Calcular PnL%
            position_value = entry * quantity * leverage
            pnl_percent = (pnl / position_value * 100) if position_value > 0 else 0
            
            # Determinar color del PnL
            pnl_icon = "📈" if pnl >= 0 else "📉"
            pnl_sign = "+" if pnl >= 0 else ""
            
            print(f"\n{i}. {symbol} - {side}")
            print(f"   {'─'*70}")
            print(f"   Cantidad:    {quantity}")
            print(f"   Entrada:     ${entry:.4f}")
            print(f"   Leverage:    {leverage}x")
            
            # Stop Loss
            if pos.get('stopLoss'):
                sl = pos['stopLoss']
                sl_distance = abs(entry - sl) / entry * 100
                print(f"   🔴 Stop Loss: ${sl:.4f} (-{sl_distance:.2f}%)")
            else:
                print(f"   🔴 Stop Loss: No configurado")
            
            # Take Profits
            if pos.get('takeProfits') and len(pos['takeProfits']) > 0:
                for j, tp in enumerate(pos['takeProfits'], 1):
                    tp_distance = abs(tp - entry) / entry * 100
                    print(f"   🟢 TP{j}:       ${tp:.4f} (+{tp_distance:.2f}%)")
            
            # PnL
            print(f"   {pnl_icon} PnL:        {pnl_sign}${pnl:.2f} ({pnl_sign}{pnl_percent:.2f}%)")
            
            total_pnl += pnl
        
        print(f"\n{'='*80}")
        total_icon = "📈" if total_pnl >= 0 else "📉"
        total_sign = "+" if total_pnl >= 0 else ""
        print(f"{total_icon} PnL TOTAL: {total_sign}${total_pnl:.2f}")
        print("="*80 + "\n")
    
    def show_database_stats(self):
        """Muestra estadísticas de la base de datos"""
        generate_quick_report("trading_history.db")
    
    def show_recent_trades(self, limit=5):
        """Muestra los últimos trades cerrados"""
        trades = self.db.get_closed_trades(limit=limit)
        
        if not trades:
            print("\n⚠️ No hay trades cerrados en la base de datos\n")
            return
        
        print("\n" + "="*80)
        print(f"📜 ÚLTIMOS {len(trades)} TRADES CERRADOS")
        print("="*80)
        
        for i, trade in enumerate(trades, 1):
            symbol = trade['symbol']
            side = trade['side']
            entry = trade['entry_price']
            exit = trade['exit_price']
            pnl = trade['pnl']
            pnl_pct = trade['pnl_percent']
            reason = trade['exit_reason']
            exit_time = trade['exit_time']
            
            pnl_icon = "✅" if pnl > 0 else "❌"
            pnl_sign = "+" if pnl >= 0 else ""
            
            print(f"\n{i}. {pnl_icon} {symbol} - {side}")
            print(f"   {'─'*70}")
            print(f"   Entrada:     ${entry:.4f}")
            print(f"   Salida:      ${exit:.4f}")
            print(f"   PnL:         {pnl_sign}${pnl:.2f} ({pnl_sign}{pnl_pct:.2f}%)")
            print(f"   Razón:       {reason}")
            print(f"   Timeframe:   {trade.get('timeframe', 'N/A')}")
            print(f"   Fecha:       {exit_time}")
        
        print(f"\n{'='*80}\n")
    
    def show_balance(self):
        """Muestra el balance de la cuenta"""
        if not self.trader:
            print("⚠️ No hay conexión con Binance")
            return
        
        balance = self.trader.get_account_balance()
        mode = "TESTNET" if self.trader.testnet else "PRODUCCIÓN"
        
        print("\n" + "="*80)
        print(f"💰 BALANCE DE LA CUENTA ({mode})")
        print("="*80)
        print(f"\n   Balance disponible: ${balance:.2f} USDT\n")
        print("="*80 + "\n")
    
    def display_full_status(self):
        """Muestra el estado completo del sistema"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print("\n\n")
        print("╔" + "="*78 + "╗")
        print("║" + " "*20 + "🤖 MONITOR DE TRADING" + " "*36 + "║")
        print("║" + f" {timestamp} ".center(78) + "║")
        print("╚" + "="*78 + "╝")
        
        # Balance
        self.show_balance()
        
        # Posiciones abiertas
        self.show_live_positions()
        
        # Últimos trades
        self.show_recent_trades(limit=5)
        
        # Estadísticas históricas
        self.show_database_stats()
    
    def monitor_loop(self, interval=30):
        """Loop de monitoreo continuo"""
        print("🔄 Iniciando monitor de trading...")
        print(f"⏰ Actualizando cada {interval} segundos")
        print("⌨️  Presiona Ctrl+C para detener\n")
        
        try:
            while True:
                self.display_full_status()
                
                print(f"\n⏳ Próxima actualización en {interval} segundos...")
                time.sleep(interval)
                
                # Limpiar pantalla (funciona en Windows y Linux)
                os.system('cls' if os.name == 'nt' else 'clear')
                
        except KeyboardInterrupt:
            print("\n\n⚠️ Monitor detenido por el usuario")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor de trading en tiempo real')
    parser.add_argument('--loop', action='store_true', help='Modo continuo (actualización automática)')
    parser.add_argument('--interval', type=int, default=30, help='Intervalo de actualización en segundos')
    
    args = parser.parse_args()
    
    monitor = TradingMonitor()
    
    if args.loop:
        monitor.monitor_loop(interval=args.interval)
    else:
        monitor.display_full_status()

if __name__ == "__main__":
    main()
