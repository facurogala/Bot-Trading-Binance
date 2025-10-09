"""
🔍 Trade Monitor - Sistema mejorado de detección y registro de trades

Este módulo:
1. Detecta cuando se ejecutan las órdenes de entrada
2. Detecta cuando se ejecutan SL/TP
3. Actualiza automáticamente la base de datos
4. Calcula correctamente el PnL

Uso:
    from trade_monitor import TradeMonitor
    monitor = TradeMonitor(trader, db)
    monitor.start()
"""
import os
import time
import threading
from typing import Dict, List, Optional, Set
from datetime import datetime
from binance.exceptions import BinanceAPIException


class TradeMonitor:
    def __init__(self, trader, db, bot_name: Optional[str] = None):
        """
        Args:
            trader: Instancia de BinanceFuturesTrader
            db: Instancia de TradingDatabase
            bot_name: Nombre del bot (opcional, para filtrar)
        """
        self.trader = trader
        self.db = db
        self.bot_name = bot_name
        self.client = trader.client
        
        # Configuración
        self.enabled = os.getenv("TRADE_MONITOR_ENABLED", "True").lower() == "true"
        self.interval = int(os.getenv("TRADE_MONITOR_INTERVAL", "5"))  # segundos
        
        # Control del thread
        self._thread: Optional[threading.Thread] = None
        self._running = False
        
        # Cache de posiciones rastreadas
        self._tracked_positions: Dict[str, Dict] = {}  # {symbol: {trade_id, qty, side, entry_price}}
        self._processed_orders: Set[str] = set()  # IDs de órdenes ya procesadas
        
        print(f"🔍 TradeMonitor inicializado (bot={bot_name or 'ALL'})")
    
    def start(self):
        """Inicia el monitoreo en background"""
        if not self.enabled:
            print("⚠️ TradeMonitor deshabilitado (TRADE_MONITOR_ENABLED=False)")
            return
        
        if self._running:
            print("⚠️ TradeMonitor ya está corriendo")
            return
        
        # Cargar posiciones abiertas desde la DB
        self._load_tracked_positions()
        
        self._running = True
        self._thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._thread.start()
        
        print(f"✅ TradeMonitor iniciado (intervalo: {self.interval}s)")
    
    def stop(self):
        """Detiene el monitoreo"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        print("🔍 TradeMonitor detenido")
    
    def register_trade(self, symbol: str, trade_id: int):
        """Registra un trade para monitoreo"""
        try:
            # Obtener datos del trade de la DB
            open_trades = self.db.get_open_trades()
            trade = next((t for t in open_trades if t['id'] == trade_id), None)
            
            if not trade:
                print(f"⚠️ TradeMonitor: Trade {trade_id} no encontrado en DB")
                return
            
            self._tracked_positions[symbol] = {
                'trade_id': trade_id,
                'quantity': float(trade['quantity']),
                'side': trade['side'],
                'entry_price': float(trade['entry_price']),
                'sl_price': float(trade.get('sl_price', 0)) if trade.get('sl_price') else None,
                'tp_prices': trade.get('tp_prices', []),
                'registered_at': datetime.now(),
                'last_exit_order_id': None,
                'last_exit_client_id': None
            }
            
            print(f"✅ TradeMonitor: Registrado {symbol} (ID: {trade_id})")
            
        except Exception as e:
            print(f"❌ TradeMonitor: Error registrando trade: {e}")
    
    def _load_tracked_positions(self):
        """Carga posiciones abiertas desde la DB"""
        try:
            open_trades = self.db.get_open_trades()
            
            for trade in open_trades:
                if self.bot_name and trade.get('bot') != self.bot_name:
                    continue
                
                symbol = trade['symbol']
                self._tracked_positions[symbol] = {
                    'trade_id': trade['id'],
                    'quantity': float(trade['quantity']),
                    'side': trade['side'],
                    'entry_price': float(trade['entry_price']),
                    'sl_price': float(trade.get('sl_price', 0)) if trade.get('sl_price') else None,
                    'tp_prices': trade.get('tp_prices', []),
                    'registered_at': datetime.now(),
                    'last_exit_order_id': None,
                    'last_exit_client_id': None
                }
            
            if self._tracked_positions:
                print(f"📊 TradeMonitor: Cargadas {len(self._tracked_positions)} posición(es) abierta(s)")
        
        except Exception as e:
            print(f"❌ TradeMonitor: Error cargando posiciones: {e}")
    
    def _monitoring_loop(self):
        """Loop principal de monitoreo"""
        while self._running:
            try:
                self._check_positions()
                self._check_orders()
            except Exception as e:
                print(f"❌ TradeMonitor error en loop: {e}")
            
            time.sleep(self.interval)
    
    def _check_positions(self):
        """Verifica el estado de las posiciones"""
        if not self._tracked_positions:
            return
        
        try:
            # Obtener posiciones activas en Binance
            binance_positions = self.client.futures_position_information()
            active_symbols = set()
            
            for pos in binance_positions:
                amt = float(pos.get('positionAmt', 0))
                if amt != 0:
                    active_symbols.add(pos['symbol'])
            
            # Verificar posiciones cerradas
            closed_symbols = []
            
            for symbol, tracked in list(self._tracked_positions.items()):
                if symbol not in active_symbols:
                    # La posición se cerró en Binance
                    closed_symbols.append(symbol)
                    
                    # Obtener precio de salida
                    try:
                        exit_price = self._get_exit_price(symbol, tracked)
                        exit_reason = self._determine_exit_reason(symbol, tracked, exit_price)
                        try:
                            margin_exit = self.trader.get_margin_balance()
                        except Exception:
                            margin_exit = None
                        
                        # Cerrar en DB
                        self.db.close_trade(
                            trade_id=tracked['trade_id'],
                            exit_price=exit_price,
                            exit_reason=exit_reason,
                            exit_order_id=tracked.get('last_exit_order_id'),
                            exit_client_order_id=tracked.get('last_exit_client_id'),
                            margin_balance_exit=margin_exit
                        )
                        
                        print(f"✅ TradeMonitor: Trade cerrado - {symbol} @ {exit_price:.6f} ({exit_reason})")
                        
                    except Exception as e:
                        print(f"❌ TradeMonitor: Error cerrando trade {symbol}: {e}")
            
            # Limpiar posiciones cerradas del tracking
            for symbol in closed_symbols:
                del self._tracked_positions[symbol]
        
        except Exception as e:
            print(f"❌ TradeMonitor: Error verificando posiciones: {e}")
    
    def _check_orders(self):
        """Verifica órdenes ejecutadas (SL/TP)"""
        if not self._tracked_positions:
            return
        
        try:
            for symbol in list(self._tracked_positions.keys()):
                # Obtener órdenes recientes del símbolo
                try:
                    # Últimas órdenes (incluyendo ejecutadas)
                    orders = self.client.futures_get_all_orders(
                        symbol=symbol,
                        limit=20
                    )
                    
                    # Filtrar órdenes ejecutadas recientemente
                    for order in orders:
                        order_id = str(order['orderId'])
                        status = order['status']
                        order_type = order['type']
                        
                        # Solo procesar órdenes ejecutadas que no hayamos procesado antes
                        if status == 'FILLED' and order_id not in self._processed_orders:
                            
                            # Verificar si es SL o TP
                            if 'STOP' in order_type or 'TAKE_PROFIT' in order_type:
                                avg_price = float(order.get('avgPrice', 0) or order.get('avgPrice', 0))
                                executed_qty = float(order.get('executedQty', 0) or order.get('origQty', 0) or 0)
                                update_time = order.get('updateTime') or order.get('time')
                                filled_ts = None
                                try:
                                    # Si viene en ms epoch
                                    if isinstance(update_time, (int, float)):
                                        from datetime import datetime
                                        filled_ts = datetime.fromtimestamp(int(update_time)/1000.0).strftime('%Y-%m-%d %H:%M:%S')
                                    else:
                                        filled_ts = str(update_time) if update_time else None
                                except Exception:
                                    filled_ts = None

                                if avg_price > 0:
                                    # Persistir fill en la DB
                                    try:
                                        self.db.update_order_fill(
                                            order_id=order_id,
                                            filled_price=avg_price,
                                            filled_qty=executed_qty if executed_qty > 0 else None,
                                            filled_time=filled_ts,
                                            status='FILLED'
                                        )
                                    except Exception as _e:
                                        pass

                                    tracked = self._tracked_positions.get(symbol)
                                    if tracked is not None:
                                        tracked['last_exit_order_id'] = order_id
                                        tracked['last_exit_client_id'] = order.get('clientOrderId')

                                    # Actualizar órdenes procesadas
                                    self._processed_orders.add(order_id)

                                    # Determinar tipo de salida
                                    if 'STOP' in order_type and 'TAKE_PROFIT' not in order_type:
                                        exit_type = "STOP_LOSS"
                                    else:
                                        exit_type = "TAKE_PROFIT"

                                    print(f"🔔 TradeMonitor: {exit_type} ejecutado - {symbol} @ {avg_price:.6f} | qty={executed_qty}")
                    
                    # Limpiar cache de órdenes (mantener solo últimas 1000)
                    if len(self._processed_orders) > 1000:
                        self._processed_orders = set(list(self._processed_orders)[-500:])
                
                except BinanceAPIException as e:
                    if e.code == -1121:  # Invalid symbol
                        continue
                    else:
                        print(f"⚠️ TradeMonitor: Error obteniendo órdenes de {symbol}: {e}")
                except Exception as e:
                    print(f"⚠️ TradeMonitor: Error procesando órdenes de {symbol}: {e}")
        
        except Exception as e:
            print(f"❌ TradeMonitor: Error verificando órdenes: {e}")
    
    def _get_exit_price(self, symbol: str, tracked: Dict) -> float:
        """Obtiene el precio de salida más preciso posible"""
        try:
            # Intentar obtener el mark price
            mark_price_data = self.client.futures_mark_price(symbol=symbol)
            if mark_price_data and 'markPrice' in mark_price_data:
                return float(mark_price_data['markPrice'])
        except:
            pass
        
        try:
            # Fallback: ticker price
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            if ticker and 'price' in ticker:
                return float(ticker['price'])
        except:
            pass
        
        # Último fallback: entry price (no ideal, pero mejor que nada)
        return tracked.get('entry_price', 0)
    
    def _determine_exit_reason(self, symbol: str, tracked: Dict, exit_price: float) -> str:
        """Determina el motivo de salida basándose en el precio"""
        entry_price = tracked['entry_price']
        side = tracked['side']
        sl_price = tracked.get('sl_price')
        tp_prices = tracked.get('tp_prices', [])
        
        # Verificar si fue por SL
        if sl_price:
            tolerance = entry_price * 0.001  # 0.1% de tolerancia
            
            if side == "LONG":
                if exit_price <= sl_price + tolerance:
                    return "STOP_LOSS"
            else:  # SHORT
                if exit_price >= sl_price - tolerance:
                    return "STOP_LOSS"
        
        # Verificar si fue por TP
        if tp_prices:
            tolerance = entry_price * 0.002  # 0.2% de tolerancia
            
            for i, tp in enumerate(tp_prices, 1):
                if abs(exit_price - tp) <= tolerance:
                    return f"TAKE_PROFIT_{i}"
        
        # Si no coincide con SL ni TP
        return "MANUAL_CLOSE"
    
    def get_status(self) -> Dict:
        """Obtiene el estado actual del monitor"""
        return {
            'running': self._running,
            'tracked_positions': len(self._tracked_positions),
            'processed_orders': len(self._processed_orders),
            'bot_name': self.bot_name,
            'interval': self.interval
        }


# Instancia global (opcional)
_global_monitor: Optional[TradeMonitor] = None


def get_global_monitor() -> Optional[TradeMonitor]:
    """Obtiene la instancia global del monitor"""
    return _global_monitor


def init_global_monitor(trader, db, bot_name: Optional[str] = None):
    """Inicializa el monitor global"""
    global _global_monitor
    
    if _global_monitor is not None:
        _global_monitor.stop()
    
    _global_monitor = TradeMonitor(trader, db, bot_name)
    _global_monitor.start()
    
    return _global_monitor


# Prueba
if __name__ == "__main__":
    print("🔍 TradeMonitor - Sistema de monitoreo de trades")
    print("Este módulo debe usarse integrado con los scanners")
    print("\nEjemplo de uso:")
    print("  from trade_monitor import TradeMonitor")
    print("  monitor = TradeMonitor(trader, db)")
    print("  monitor.start()")
