"""
Sistema de reconciliación de órdenes SL/TP en Binance Futures

Este módulo garantiza que:
1. Las órdenes SL/TP existen en Binance después del fill
2. Si faltan, las recrea automáticamente
3. Cuando una orden se ejecuta (SL o TP), cancela las otras
4. Monitorea periódicamente el estado de las órdenes

Uso:
    reconciler = OrderReconciler(trader)
    reconciler.ensure_orders_exist(symbol, side, quantity, sl_price, tp_prices)
    reconciler.start_monitoring(symbol, trade_id)
"""
import time
import threading
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import re


class OrderReconciler:
    def __init__(self, trader):
        """
        Args:
            trader: Instancia de BinanceFuturesTrader
        """
        self.trader = trader
        self.client = trader.client
        self.monitoring_threads = {}  # {symbol: thread}
        self.active_monitors = {}  # {symbol: bool}
        self.stop_limit_cooldown_seconds = 300
        self.stop_limit_global_until = 0.0
        self.last_cooldown_log_ts = 0.0
        self.last_orphan_cleanup_ts = 0.0

    def _extract_error_code(self, error: Exception) -> Optional[int]:
        """Extrae code=-XXXX desde BinanceAPIException o string."""
        code = getattr(error, 'code', None)
        if code is not None:
            try:
                return int(code)
            except Exception:
                pass

        text = str(error)
        match = re.search(r'code=([-]?\d+)', text)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None
        return None

    def _is_stop_order_limit_error(self, error: Exception) -> bool:
        code = self._extract_error_code(error)
        if code == -4045:
            return True
        return "max stop order limit" in str(error).lower()

    def _cleanup_orphan_protection_orders(self, max_cancel: int = 40) -> int:
        """
        Cancela órdenes de protección huérfanas (reduceOnly/closePosition)
        en símbolos sin posición abierta. Ayuda a liberar cupo de stop orders.
        """
        now = time.time()
        if (now - self.last_orphan_cleanup_ts) < 120:
            return 0
        self.last_orphan_cleanup_ts = now

        try:
            open_orders = self.client.futures_get_open_orders()
        except Exception as e:
            print(f"⚠️ No se pudo listar órdenes para limpieza de huérfanas: {e}")
            return 0

        candidates = []
        for order in open_orders:
            order_type = order.get('type', '')
            if 'STOP' not in order_type and 'TAKE_PROFIT' not in order_type:
                continue

            reduce_only = str(order.get('reduceOnly', '')).lower() == 'true'
            close_position = str(order.get('closePosition', '')).lower() == 'true'
            if reduce_only or close_position:
                candidates.append(order)

        if not candidates:
            return 0

        cancelled = 0
        checked_symbols = {}

        for order in candidates:
            if cancelled >= max_cancel:
                break

            symbol = order.get('symbol')
            order_id = order.get('orderId')
            if not symbol or not order_id:
                continue

            if symbol not in checked_symbols:
                try:
                    positions = self.client.futures_position_information(symbol=symbol)
                    position_amt = 0.0
                    for pos in positions:
                        if pos.get('symbol') == symbol:
                            position_amt = abs(float(pos.get('positionAmt', 0)))
                            break
                    checked_symbols[symbol] = position_amt > 0
                except Exception:
                    checked_symbols[symbol] = True

            has_open_position = checked_symbols[symbol]
            if has_open_position:
                continue

            try:
                self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
                cancelled += 1
            except Exception:
                pass

        if cancelled > 0:
            print(f"🧹 Limpieza automática: {cancelled} orden(es) de protección huérfana(s) cancelada(s)")

        return cancelled

    def _activate_stop_limit_cooldown(self, error: Exception):
        """Activa cooldown global para evitar reintentos inútiles con code -4045."""
        _ = self._cleanup_orphan_protection_orders()
        until = time.time() + self.stop_limit_cooldown_seconds
        self.stop_limit_global_until = max(self.stop_limit_global_until, until)
        print(
            f"⛔ Límite de stop orders alcanzado (-4045). "
            f"Se pausa creación de SL/TP por {self.stop_limit_cooldown_seconds}s."
        )

    def _is_stop_limit_cooldown_active(self) -> bool:
        return time.time() < self.stop_limit_global_until

    def _log_cooldown_skip(self, symbol: str):
        now = time.time()
        if now - self.last_cooldown_log_ts < 60:
            return
        self.last_cooldown_log_ts = now
        remaining = int(max(0, self.stop_limit_global_until - now))
        print(
            f"⏸️ {symbol}: reconciliación SL/TP omitida temporalmente "
            f"(cooldown -4045 activo, restan ~{remaining}s)"
        )
        
    def get_position_side(self, side: str) -> str:
        """
        Obtiene el positionSide correcto para hedge mode
        En one-way mode, esto no se usa (None o "BOTH")
        """
        # Por ahora asumimos one-way mode (más común)
        # Si necesitas hedge mode, descomentar:
        # return "LONG" if side == "LONG" else "SHORT"
        return "BOTH"
    
    def get_existing_orders(self, symbol: str) -> Dict[str, List]:
        """
        Obtiene órdenes existentes categorizadas por tipo
        
        Returns:
            {
                'stop_loss': [order, ...],
                'take_profit': [order, ...],
                'entry': [order, ...]
            }
        """
        try:
            orders = self.client.futures_get_open_orders(symbol=symbol)
            
            categorized = {
                'stop_loss': [],
                'take_profit': [],
                'entry': []
            }
            
            for order in orders:
                order_type = order.get('type', '')
                is_close_position = str(order.get('closePosition', '')).lower() == 'true'
                
                if ('STOP' in order_type and 'TAKE_PROFIT' not in order_type) or is_close_position:
                    categorized['stop_loss'].append(order)
                elif 'TAKE_PROFIT' in order_type:
                    categorized['take_profit'].append(order)
                elif order_type in ['LIMIT', 'MARKET']:
                    categorized['entry'].append(order)
            
            return categorized
            
        except Exception as e:
            print(f"⚠️ Error obteniendo órdenes existentes: {e}")
            return {'stop_loss': [], 'take_profit': [], 'entry': []}
    
    def set_position_tp_sl(
        self,
        symbol: str,
        side: str,
        tp_price: Optional[float] = None,
        sl_price: Optional[float] = None
    ) -> bool:
        """
        Configura TP/SL directamente en la posición usando futures_position_mode
        Esto hace que aparezcan en la columna "TP/SL" de la interfaz web
        
        Args:
            symbol: Par (ej: BTCUSDT)
            side: LONG o SHORT
            tp_price: Precio de take profit (opcional)
            sl_price: Precio de stop loss (opcional)
        """
        try:
            # Obtener precisión
            symbol_info = self.trader.get_symbol_info(symbol)
            if symbol_info:
                price_precision = symbol_info['pricePrecision']
                if tp_price:
                    tp_price = round(tp_price, price_precision)
                if sl_price:
                    sl_price = round(sl_price, price_precision)
            
            # Determinar el tipo de stop loss y take profit según el lado
            if side == "LONG":
                stop_loss_type = "STOP_MARKET"
                take_profit_type = "TAKE_PROFIT_MARKET"
            else:  # SHORT
                stop_loss_type = "STOP_MARKET"
                take_profit_type = "TAKE_PROFIT_MARKET"
            
            # Configurar usando el endpoint de batch order
            # Esto permite configurar TP y SL que aparezcan integrados
            params = {
                'symbol': symbol,
                'stopLossPrice': str(sl_price) if sl_price else None,
                'takeProfitPrice': str(tp_price) if tp_price else None,
                'stopLossType': stop_loss_type if sl_price else None,
                'takeProfitType': take_profit_type if tp_price else None
            }
            
            # Filtrar None values
            params = {k: v for k, v in params.items() if v is not None}
            
            if params:
                # Nota: Este endpoint puede no estar disponible en todas las versiones
                # Si falla, usaremos el método de órdenes separadas
                try:
                    result = self.client.futures_position_mode(**params)
                    print(f"✅ TP/SL integrado configurado")
                    return True
                except Exception as e:
                    print(f"⚠️ Método integrado no disponible: {e}")
                    print(f"   Usando método de órdenes separadas...")
                    return False
            
            return True
            
        except Exception as e:
            print(f"⚠️ Error configurando TP/SL integrado: {e}")
            return False
    
    def create_stop_loss(
        self, 
        symbol: str, 
        side: str, 
        sl_price: float,
        position_side: str = "BOTH"
    ) -> Optional[Dict]:
        """
        Crea orden de Stop Loss en Binance
        
        Args:
            symbol: Par (ej: BTCUSDT)
            side: LONG o SHORT (de la posición)
            sl_price: Precio del stop loss
            position_side: BOTH para one-way, LONG/SHORT para hedge
        """
        try:
            sl_side = "SELL" if side == "LONG" else "BUY"
            
            # Obtener precisión
            symbol_info = self.trader.get_symbol_info(symbol)
            if symbol_info:
                price_precision = symbol_info['pricePrecision']
                sl_price = round(sl_price, price_precision)
            
            # Crear orden STOP_MARKET con closePosition
            # IMPORTANTE: No enviar reduceOnly cuando se usa closePosition
            params = {
                'symbol': symbol,
                'side': sl_side,
                'type': 'STOP_MARKET',
                'stopPrice': sl_price,
                'closePosition': True  # closePosition ya implica reduce only
            }
            
            # Si usas hedge mode, agregar positionSide
            # if position_side != "BOTH":
            #     params['positionSide'] = position_side
            
            sl_order = self.client.futures_create_order(**params)
            
            print(f"✅ Stop Loss creado: {sl_order.get('orderId')} @ {sl_price}")
            return sl_order
            
        except Exception as e:
            if self._is_stop_order_limit_error(e):
                self._activate_stop_limit_cooldown(e)
                return None
            # -4130: ya existe un stop con closePosition en esa dirección → buscar y devolver el existente
            if self._extract_error_code(e) == -4130:
                print(f"⚠️ SL con closePosition ya existe en Binance para {symbol}, buscando orden existente...")
                try:
                    open_orders = self.client.futures_get_open_orders(symbol=symbol)
                    for o in open_orders:
                        otype = o.get('type', '')
                        is_close = str(o.get('closePosition', '')).lower() == 'true'
                        if ('STOP' in otype and 'TAKE_PROFIT' not in otype) or is_close:
                            print(f"✅ Stop Loss existente encontrado: {o.get('orderId')} @ {o.get('stopPrice')}")
                            return o
                except Exception as lookup_e:
                    print(f"⚠️ No se pudo buscar SL existente: {lookup_e}")
                # Devolver un placeholder para evitar reintentos
                return {'orderId': None, 'type': 'STOP_MARKET', 'stopPrice': sl_price, '_existing': True}
            print(f"❌ Error creando Stop Loss: {e}")
            return None
    
    def create_take_profit(
        self,
        symbol: str,
        side: str,
        tp_price: float,
        quantity: float,
        position_side: str = "BOTH"
    ) -> Optional[Dict]:
        """
        Crea orden de Take Profit en Binance
        
        Args:
            symbol: Par (ej: BTCUSDT)
            side: LONG o SHORT (de la posición)
            tp_price: Precio del take profit
            quantity: Cantidad a cerrar
            position_side: BOTH para one-way, LONG/SHORT para hedge
        """
        try:
            tp_side = "SELL" if side == "LONG" else "BUY"
            
            # Obtener precisión
            symbol_info = self.trader.get_symbol_info(symbol)
            if symbol_info:
                price_precision = symbol_info['pricePrecision']
                tp_price = round(tp_price, price_precision)
                
                # Ajustar quantity según step_size
                for f in symbol_info['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        step_size = float(f['stepSize'])
                        quantity = self.trader.round_step_size(quantity, step_size)
                        break
            
            # Crear orden TAKE_PROFIT_MARKET con reduceOnly
            params = {
                'symbol': symbol,
                'side': tp_side,
                'type': 'TAKE_PROFIT_MARKET',
                'stopPrice': tp_price,
                'quantity': quantity,
                'reduceOnly': True
            }
            
            # Si usas hedge mode, agregar positionSide
            # if position_side != "BOTH":
            #     params['positionSide'] = position_side
            
            tp_order = self.client.futures_create_order(**params)
            
            print(f"✅ Take Profit creado: {tp_order.get('orderId')} @ {tp_price} | Qty: {quantity}")
            return tp_order
            
        except Exception as e:
            if self._is_stop_order_limit_error(e):
                self._activate_stop_limit_cooldown(e)
                return None
            print(f"❌ Error creando Take Profit: {e}")
            return None
    
    def ensure_orders_exist(
        self,
        symbol: str,
        side: str,
        quantity: float,
        sl_price: float,
        tp_prices: List[float],
        max_retries: int = 3
    ) -> Tuple[Optional[Dict], List[Dict]]:
        """
        Garantiza que las órdenes SL/TP existan en Binance
        Si no existen, las crea con reintentos
        
        Returns:
            (sl_order, [tp_orders])
        """
        position_side = self.get_position_side(side)
        
        # Verificar órdenes existentes
        existing = self.get_existing_orders(symbol)

        # Si Binance está en límite de stop orders, no insistir en este ciclo
        if self._is_stop_limit_cooldown_active():
            sl_existing = existing['stop_loss'][0] if existing['stop_loss'] else None
            tp_existing = existing['take_profit'][:len(tp_prices)]
            if sl_existing is None or len(tp_existing) < len(tp_prices):
                self._log_cooldown_skip(symbol)
            return sl_existing, tp_existing
        
        # Stop Loss
        sl_order = None
        if not existing['stop_loss']:
            print(f"⚠️ No se encontró Stop Loss, creando...")
            for attempt in range(max_retries):
                sl_order = self.create_stop_loss(symbol, side, sl_price, position_side)
                if sl_order:
                    break
                if self._is_stop_limit_cooldown_active():
                    break
                time.sleep(1)
        else:
            sl_order = existing['stop_loss'][0]
            print(f"✅ Stop Loss ya existe: {sl_order.get('orderId')}")
        
        # Take Profits
        tp_orders = []
        needed_tps = len(tp_prices)
        existing_tps = len(existing['take_profit'])
        
        if existing_tps < needed_tps:
            print(f"⚠️ Faltan {needed_tps - existing_tps} Take Profit(s), creando...")
            
            # Usar TPs existentes
            tp_orders.extend(existing['take_profit'])
            
            # Crear los que faltan
            tp_quantity = quantity / needed_tps if quantity > 0 else 0
            
            for i, tp_price in enumerate(tp_prices[existing_tps:], existing_tps + 1):
                # Última TP toma el resto
                if i == needed_tps:
                    remaining_qty = quantity - (tp_quantity * (needed_tps - 1))
                    use_qty = remaining_qty
                else:
                    use_qty = tp_quantity
                
                for attempt in range(max_retries):
                    tp_order = self.create_take_profit(
                        symbol, side, tp_price, use_qty, position_side
                    )
                    if tp_order:
                        tp_orders.append(tp_order)
                        break
                    if self._is_stop_limit_cooldown_active():
                        break
                    time.sleep(1)

                if self._is_stop_limit_cooldown_active():
                    break
        else:
            tp_orders = existing['take_profit'][:needed_tps]
            print(f"✅ Take Profits ya existen: {len(tp_orders)} órdenes")
        
        return sl_order, tp_orders
    
    def cancel_reciprocal_orders(self, symbol: str, executed_order_id: str):
        """
        Cuando una orden se ejecuta (SL o TP), cancela las otras
        
        Args:
            symbol: Par
            executed_order_id: ID de la orden que se ejecutó
        """
        try:
            print(f"\n🔄 Orden ejecutada ({executed_order_id}), cancelando órdenes recíprocas...")
            
            # Obtener todas las órdenes abiertas
            open_orders = self.client.futures_get_open_orders(symbol=symbol)
            
            cancelled_count = 0
            for order in open_orders:
                order_id = str(order.get('orderId'))
                order_type = order.get('type', '')
                
                # No cancelar la orden ejecutada (por si acaso aún aparece)
                if order_id == str(executed_order_id):
                    continue
                
                # Cancelar SL y TPs
                if 'STOP' in order_type or 'TAKE_PROFIT' in order_type:
                    try:
                        self.client.futures_cancel_order(
                            symbol=symbol,
                            orderId=order_id
                        )
                        print(f"  ✅ Cancelada orden {order_type}: {order_id}")
                        cancelled_count += 1
                    except Exception as e:
                        print(f"  ⚠️ No se pudo cancelar {order_id}: {e}")
            
            print(f"✅ Canceladas {cancelled_count} orden(es) recíproca(s)")
            
        except Exception as e:
            print(f"❌ Error cancelando órdenes recíprocas: {e}")
    
    def monitor_orders(
        self,
        symbol: str,
        trade_id: int,
        duration_seconds: int = 60,
        check_interval: int = 10
    ):
        """
        Monitorea órdenes periódicamente y ejecuta acciones si es necesario
        
        Args:
            symbol: Par a monitorear
            trade_id: ID del trade en la base de datos
            duration_seconds: Duración del monitoreo (60s por defecto)
            check_interval: Intervalo entre checks (10s por defecto)
        """
        print(f"\n👁️ Iniciando monitoreo de órdenes para {symbol} (trade_id: {trade_id})")
        print(f"   Duración: {duration_seconds}s | Intervalo: {check_interval}s")
        
        start_time = time.time()
        
        while self.active_monitors.get(symbol, False):
            elapsed = time.time() - start_time
            
            if elapsed > duration_seconds:
                print(f"\n⏰ Monitoreo completado para {symbol} ({duration_seconds}s)")
                break
            
            try:
                # Verificar estado de la posición
                positions = self.client.futures_position_information(symbol=symbol)
                position_amt = 0
                
                for pos in positions:
                    if pos['symbol'] == symbol:
                        position_amt = abs(float(pos.get('positionAmt', 0)))
                        break
                
                # Si la posición se cerró, cancelar órdenes restantes
                if position_amt == 0:
                    print(f"\n✅ Posición cerrada en {symbol}, limpiando órdenes...")
                    try:
                        self.client.futures_cancel_all_open_orders(symbol=symbol)
                        print(f"  ✅ Órdenes limpiadas")
                    except Exception:
                        pass
                    break
                
                # Verificar si hay órdenes ejecutadas
                existing = self.get_existing_orders(symbol)
                
                # Si no hay SL ni TP, significa que se ejecutaron
                if not existing['stop_loss'] and not existing['take_profit']:
                    print(f"\n✅ Todas las órdenes SL/TP ejecutadas o canceladas para {symbol}")
                    break
                
            except Exception as e:
                print(f"⚠️ Error en monitoreo: {e}")
            
            time.sleep(check_interval)
        
        # Limpiar registro
        self.active_monitors[symbol] = False
        if symbol in self.monitoring_threads:
            del self.monitoring_threads[symbol]
        
        print(f"✅ Monitoreo finalizado para {symbol}")
    
    def start_monitoring(
        self,
        symbol: str,
        trade_id: int,
        duration_seconds: int = 60,
        check_interval: int = 10
    ):
        """
        Inicia monitoreo en background thread
        """
        # Si ya hay un thread activo, no crear otro
        if symbol in self.monitoring_threads and self.monitoring_threads[symbol].is_alive():
            print(f"⚠️ Ya hay un monitoreo activo para {symbol}")
            return
        
        self.active_monitors[symbol] = True
        
        thread = threading.Thread(
            target=self.monitor_orders,
            args=(symbol, trade_id, duration_seconds, check_interval),
            daemon=True
        )
        thread.start()
        
        self.monitoring_threads[symbol] = thread
    
    def stop_monitoring(self, symbol: str):
        """Detiene el monitoreo de un símbolo"""
        self.active_monitors[symbol] = False


# Funciones de test
if __name__ == "__main__":
    print("🧪 Test del Order Reconciler")
    print("\nEste módulo debe usarse en conjunto con BinanceFuturesTrader")
    print("Ver test_open_position.py para ejemplos de uso")
