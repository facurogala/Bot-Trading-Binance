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
from typing import Callable, Dict, List, Optional, Set
from datetime import datetime
from binance.exceptions import BinanceAPIException


class TradeMonitor:
    def __init__(
        self,
        trader,
        db,
        bot_name: Optional[str] = None,
        trailing_manager: Optional[object] = None,
        tp_callback: Optional[Callable[[int, int, Optional[float]], None]] = None,
    ):
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
        self.trailing_manager = trailing_manager
        self._tp_callback = tp_callback
        
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
                'last_exit_client_id': None,
                'tp_hits': set(),
                'timeframe': trade.get('timeframe'),
                'position_id': trade.get('position_id'),
                'symbol': symbol
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
                    'last_exit_client_id': None,
                    'tp_hits': set(),
                    'timeframe': trade.get('timeframe'),
                    'position_id': trade.get('position_id'),
                    'symbol': symbol
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

                        try:
                            self.db.log_trade_event(
                                trade_id=tracked['trade_id'],
                                event_type="TRADE_CLOSED",
                                payload={
                                    "symbol": symbol,
                                    "exit_price": exit_price,
                                    "exit_reason": exit_reason,
                                    "margin_balance_exit": margin_exit
                                }
                            )
                        except Exception:
                            pass
                        
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

                                    # Determinar tipo de salida antes de loguear
                                    if 'STOP' in order_type and 'TAKE_PROFIT' not in order_type:
                                        exit_type = "STOP_LOSS"
                                    else:
                                        exit_type = "TAKE_PROFIT"

                                    try:
                                        self.db.log_trade_event(
                                            trade_id=tracked['trade_id'] if tracked else None,
                                            event_type="ORDER_FILLED",
                                            payload={
                                                "symbol": symbol,
                                                "order_id": order_id,
                                                "order_type": exit_type,
                                                "price": avg_price,
                                                "quantity": executed_qty,
                                                "update_time": filled_ts
                                            }
                                        )
                                    except Exception:
                                        pass

                                    # Actualizar órdenes procesadas
                                    self._processed_orders.add(order_id)

                                    print(f"🔔 TradeMonitor: {exit_type} ejecutado - {symbol} @ {avg_price:.6f} | qty={executed_qty}")
                                    if exit_type == "TAKE_PROFIT" and tracked is not None and self.trailing_manager:
                                        try:
                                            self._handle_take_profit(symbol, tracked, order, avg_price, executed_qty)
                                        except Exception as trailing_exc:
                                            print(f"⚠️ TradeMonitor: error aplicando trailing para {symbol}: {trailing_exc}")
                    
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
    
    def _handle_take_profit(self, symbol: str, tracked: Dict, order: Dict, avg_price: float, executed_qty: float) -> None:
        order_id = str(order.get('orderId')) if order.get('orderId') is not None else None
        tp_index = None

        if order_id:
            try:
                order_row = self.db.get_order_by_id(order_id)
            except Exception:
                order_row = None
            if order_row:
                order_type = str(order_row.get('order_type') or '')
                if order_type.upper().startswith('TAKE_PROFIT'):
                    try:
                        tp_index = int(order_type.split('_')[-1])
                    except (ValueError, IndexError):
                        tp_index = None

        if tp_index is None:
            tp_index = self._infer_tp_index(tracked, avg_price)

        if tp_index is None:
            return

        hits: Set[int] = tracked.setdefault('tp_hits', set())
        if tp_index in hits:
            return

        new_sl = self.trailing_manager.on_take_profit(
            symbol=symbol,
            tracked=tracked,
            tp_index=tp_index,
            fill_price=avg_price,
            executed_qty=executed_qty,
            order_id=order_id,
        )

        if new_sl is not None:
            previous_sl = tracked.get('sl_price')
            hits.add(tp_index)
            tracked['sl_price'] = new_sl
            try:
                self.db.log_sl_update(
                    trade_id=tracked['trade_id'],
                    old_sl=previous_sl,
                    new_sl=new_sl,
                    trigger=f"TP{tp_index}",
                    order_id=order_id,
                    extra={
                        "symbol": symbol,
                        "fill_price": avg_price,
                        "executed_qty": executed_qty
                    }
                )
            except Exception:
                pass
        else:
            hits.add(tp_index)

        if self._tp_callback:
            try:
                self._tp_callback(tracked['trade_id'], tp_index, new_sl)
            except Exception as callback_exc:
                print(f"⚠️ TradeMonitor: error en callback TP: {callback_exc}")

        # Si este TP es el último, intentamos cerrar cualquier remanente inmediatamente
        tp_prices = tracked.get('tp_prices') or []
        try:
            total_tps = len(tp_prices)
        except Exception:
            total_tps = 0
        if total_tps > 0 and tp_index == total_tps:
            try:
                # Verificar cantidad abierta actual
                positions = self.client.futures_position_information(symbol=symbol)
                qty_open = 0.0
                side = (tracked.get('side') or 'LONG').upper()
                for pos in positions:
                    if pos.get('symbol') == symbol:
                        try:
                            qty_open = abs(float(pos.get('positionAmt') or 0))
                        except Exception:
                            qty_open = 0.0
                        break
                # Si hay remanente, cerrar con reduceOnly
                if qty_open > 0:
                    # Validar notional mínima para evitar rechazos
                    try:
                        last_price = float(self.client.futures_symbol_ticker(symbol=symbol).get('price'))
                    except Exception:
                        last_price = avg_price or float(tracked.get('entry_price') or 0)
                    min_notional = float(os.getenv('AUTO_CLOSER_MIN_NOTIONAL', '5.0'))
                    if last_price > 0 and qty_open * last_price >= min_notional:
                        mkt_side = 'SELL' if side == 'LONG' else 'BUY'
                        try:
                            self.client.futures_create_order(
                                symbol=symbol,
                                side=mkt_side,
                                type='MARKET',
                                quantity=qty_open,
                                reduceOnly=True
                            )
                            try:
                                self.db.log_trade_event(
                                    trade_id=tracked['trade_id'],
                                    event_type="EMERGENCY_FLATTEN",
                                    payload={
                                        "symbol": symbol,
                                        "quantity": qty_open,
                                        "side": mkt_side
                                    }
                                )
                            except Exception:
                                pass
                        except Exception as e:
                            print(f"⚠️ TradeMonitor: No se pudo cerrar remanente en último TP {symbol}: {e}")
                    # Cancelar órdenes pendientes (SL/TP restantes)
                    try:
                        self.trader.cancel_all_orders(symbol)
                    except Exception:
                        pass
            except Exception as e:
                print(f"⚠️ TradeMonitor: error al cerrar remanente tras último TP en {symbol}: {e}")

    def _infer_tp_index(self, tracked: Dict, fill_price: float) -> Optional[int]:
        tp_prices = tracked.get('tp_prices') or []
        if not tp_prices:
            return None
        try:
            fill_price = float(fill_price)
        except Exception:
            return None

        diffs = [abs(fill_price - float(tp)) for tp in tp_prices]
        if not diffs:
            return None
        best_idx = min(range(len(diffs)), key=lambda i: diffs[i])
        tolerance = float(tracked.get('entry_price', 0)) * 0.003  # 0.3% tolerance
        if diffs[best_idx] > tolerance:
            return None
        return best_idx + 1

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
