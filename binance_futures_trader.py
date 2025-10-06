"""
Módulo de trading automático para Binance Futures
Maneja la ejecución de órdenes con SL y TP automáticos
"""
import os
from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv
from typing import Dict, Optional, List
import time

load_dotenv()

class BinanceFuturesTrader:
    def __init__(self):
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")
        self.testnet = os.getenv("TESTNET", "False").lower() == "true"
        
        if not api_key or not api_secret:
            raise ValueError("❌ Error: BINANCE_API_KEY o BINANCE_API_SECRET no están configurados en .env")
        
        # Configurar cliente según modo
        if self.testnet:
            # Testnet - Configuración especial
            print("🧪 MODO TESTNET ACTIVADO - Usando cuenta demo")
            self.client = Client(api_key, api_secret, testnet=True)
            # URLs correctas para testnet
            self.client.API_URL = 'https://testnet.binance.vision/api'
            self.client.FUTURES_URL = 'https://testnet.binancefuture.com/fapi'
            self.client.FUTURES_DATA_URL = 'https://testnet.binancefuture.com/fapi'
            self.client.FUTURES_COIN_URL = 'https://testnet.binancefuture.com/dapi'
            self.client.FUTURES_COIN_DATA_URL = 'https://testnet.binancefuture.com/dapi'
        else:
            print("💰 MODO PRODUCCIÓN - Usando cuenta real")
            self.client = Client(api_key, api_secret)
        
        # Sincronizar timestamp con el servidor de Binance
        try:
            server_time = self.client.get_server_time()
            local_time = int(time.time() * 1000)
            self.client.timestamp_offset = server_time['serverTime'] - local_time
            print(f"⏰ Timestamp sincronizado (offset: {self.client.timestamp_offset}ms)")
        except Exception as e:
            print(f"⚠️ No se pudo sincronizar timestamp: {e}")
            self.client.timestamp_offset = 0
        
        # Verificar que las credenciales sean válidas
        try:
            # Usar recvWindow mayor para evitar problemas de sincronización de tiempo
            account = self.client.futures_account(recvWindow=60000)
            if self.testnet:
                print("✅ Conexión con Binance Futures TESTNET establecida")
            else:
                print("✅ Conexión con Binance Futures establecida correctamente")
        except BinanceAPIException as e:
            if self.testnet:
                print("\n❌ Error al conectar con TESTNET")
                print(f"   Detalle: {e}")
                print("\n💡 Verifica:")
                print("   1. Las API Keys son de https://testnet.binancefuture.com")
                print("   2. NO uses API Keys de Binance real para testnet")
                print("   3. Regenera las API Keys en testnet si es necesario")
            raise ValueError(f"❌ Error de autenticación con Binance: {e}")
        
        # Configuración de trading
        self.leverage = int(os.getenv("LEVERAGE", "5"))  # Apalancamiento por defecto
        self.risk_percent = float(os.getenv("RISK_PERCENT", "1.0"))  # % de capital por trade
        
    def get_account_balance(self) -> float:
        """Obtiene el balance disponible en USDT"""
        try:
            account = self.client.futures_account(recvWindow=60000)
            for asset in account['assets']:
                if asset['asset'] == 'USDT':
                    return float(asset['availableBalance'])
            return 0.0
        except Exception as e:
            print(f"❌ Error al obtener balance: {e}")
            return 0.0
    
    def get_symbol_info(self, symbol: str) -> Dict:
        """Obtiene información del símbolo (precisión, min notional, etc)"""
        try:
            exchange_info = self.client.futures_exchange_info()
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    return {
                        'symbol': symbol,
                        'pricePrecision': s['pricePrecision'],
                        'quantityPrecision': s['quantityPrecision'],
                        'filters': s['filters']
                    }
            return {}
        except Exception as e:
            print(f"❌ Error al obtener info del símbolo {symbol}: {e}")
            return {}
    
    def round_step_size(self, quantity: float, step_size: float) -> float:
        """Redondea la cantidad según el step_size del símbolo"""
        precision = len(str(step_size).split('.')[-1].rstrip('0'))
        return round(quantity - (quantity % step_size), precision)
    
    def calculate_position_size(self, symbol: str, entry_price: float, sl_price: float) -> float:
        """
        Calcula el tamaño de la posición basado en el riesgo configurado
        """
        balance = self.get_account_balance()
        risk_amount = balance * (self.risk_percent / 100)
        
        # Distancia del SL en %
        sl_distance_pct = abs(entry_price - sl_price) / entry_price
        
        # Cantidad a operar considerando apalancamiento
        position_value = risk_amount / sl_distance_pct
        quantity = (position_value / entry_price) / self.leverage
        
        # Ajustar según precisión del símbolo
        symbol_info = self.get_symbol_info(symbol)
        if symbol_info:
            for f in symbol_info['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f['stepSize'])
                    quantity = self.round_step_size(quantity, step_size)
                    break
        
        return quantity
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Configura el apalancamiento para un símbolo"""
        try:
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            return True
        except BinanceAPIException as e:
            print(f"⚠️ Error al configurar leverage: {e}")
            return False
    
    def open_position(
        self, 
        symbol: str, 
        side: str,  # "LONG" o "SHORT"
        entry_price: float,
        sl_price: float,
        tp_prices: List[float],
        force_market: bool = False
    ) -> Optional[Dict]:
        """
        Abre una posición en Binance Futures con SL y múltiples TPs
        
        Args:
            symbol: Par a tradear (ej: "BTCUSDT")
            side: "LONG" o "SHORT"
            entry_price: Precio de entrada
            sl_price: Precio de stop loss
            tp_prices: Lista de precios de take profit
            force_market: Si True, ejecuta orden market inmediatamente
        
        Returns:
            Dict con información de la operación o None si falla
        """
        try:
            # Configurar apalancamiento
            self.set_leverage(symbol, self.leverage)
            
            # Calcular tamaño de posición
            quantity = self.calculate_position_size(symbol, entry_price, sl_price)
            
            if quantity <= 0:
                print(f"❌ Cantidad calculada inválida: {quantity}")
                return None
            
            # Redondear cantidad según step_size
            symbol_info = self.get_symbol_info(symbol)
            if symbol_info:
                for f in symbol_info['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        step_size = float(f['stepSize'])
                        quantity = self.round_step_size(quantity, step_size)
                        break
            
            # Dirección de la orden
            order_side = "BUY" if side == "LONG" else "SELL"
            
            print(f"\n{'='*60}")
            print(f"📊 ABRIENDO POSICIÓN {side}")
            print(f"{'='*60}")
            print(f"Symbol: {symbol}")
            print(f"Side: {order_side}")
            print(f"Quantity: {quantity}")
            print(f"Entry: {entry_price}")
            print(f"SL: {sl_price}")
            print(f"TPs: {tp_prices}")
            print(f"Leverage: {self.leverage}x")
            print(f"{'='*60}\n")
            
            # Obtener precisión de precio para redondear correctamente
            symbol_info = self.get_symbol_info(symbol)
            price_precision = symbol_info.get('pricePrecision', 2) if symbol_info else 2
            entry_price_rounded = round(entry_price, price_precision)
            
            # Orden de entrada (LIMIT o MARKET)
            if force_market:
                entry_order = self.client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type="MARKET",
                    quantity=quantity
                )
                actual_entry = float(entry_order['avgPrice'])
            else:
                entry_order = self.client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type="LIMIT",
                    timeInForce="GTC",
                    quantity=quantity,
                    price=entry_price_rounded
                )
                actual_entry = entry_price_rounded
            
            print(f"✅ Orden de entrada ejecutada: {entry_order['orderId']}")
            
            # Stop Loss (orden STOP_MARKET)
            sl_side = "SELL" if side == "LONG" else "BUY"
            
            # Redondear SL según precisión
            symbol_info = self.get_symbol_info(symbol)
            if symbol_info:
                price_precision = symbol_info['pricePrecision']
                sl_price = round(sl_price, price_precision)
            
            sl_order = self.client.futures_create_order(
                symbol=symbol,
                side=sl_side,
                type="STOP_MARKET",
                stopPrice=sl_price,
                closePosition=True  # Cierra toda la posición
            )
            
            print(f"✅ Stop Loss configurado: {sl_order['orderId']}")
            
            # Take Profits (dividir la posición en partes iguales)
            tp_orders = []
            if len(tp_prices) > 0:
                tp_quantity = quantity / len(tp_prices)
                
                # Ajustar según step_size
                symbol_info = self.get_symbol_info(symbol)
                if symbol_info:
                    for f in symbol_info['filters']:
                        if f['filterType'] == 'LOT_SIZE':
                            step_size = float(f['stepSize'])
                            tp_quantity = self.round_step_size(tp_quantity, step_size)
                            break
                
                tp_side = "SELL" if side == "LONG" else "BUY"
                
                # Obtener precisión de precio
                price_precision = symbol_info.get('pricePrecision', 2) if symbol_info else 2
                
                for i, tp_price in enumerate(tp_prices, 1):
                    try:
                        # Última TP toma el resto de la posición
                        if i == len(tp_prices):
                            remaining_qty = quantity - (tp_quantity * (len(tp_prices) - 1))
                            use_qty = remaining_qty
                        else:
                            use_qty = tp_quantity
                        
                        # Redondear TP según precisión
                        tp_price_rounded = round(tp_price, price_precision)
                        
                        tp_order = self.client.futures_create_order(
                            symbol=symbol,
                            side=tp_side,
                            type="TAKE_PROFIT_MARKET",
                            stopPrice=tp_price_rounded,
                            quantity=use_qty
                        )
                        tp_orders.append(tp_order)
                        print(f"✅ TP{i} configurado en {tp_price_rounded}: {tp_order['orderId']}")
                        time.sleep(0.2)  # Pequeña pausa entre órdenes
                        
                    except Exception as e:
                        print(f"⚠️ Error al configurar TP{i}: {e}")
            
            result = {
                'symbol': symbol,
                'side': side,
                'entry_order': entry_order,
                'sl_order': sl_order,
                'tp_orders': tp_orders,
                'quantity': quantity,
                'entry_price': actual_entry,
                'sl_price': sl_price,
                'tp_prices': tp_prices,
                'leverage': self.leverage
            }
            
            print(f"\n✅ Posición {side} abierta exitosamente en {symbol}")
            return result
            
        except BinanceAPIException as e:
            print(f"❌ Error de Binance API: {e}")
            return None
        except Exception as e:
            print(f"❌ Error al abrir posición: {e}")
            return None
    
    def get_open_positions(self) -> List[Dict]:
        """Obtiene todas las posiciones abiertas con sus órdenes SL/TP"""
        try:
            positions = self.client.futures_position_information(recvWindow=60000)
            open_positions = []
            
            for pos in positions:
                position_amt = float(pos['positionAmt'])
                if position_amt != 0:
                    symbol = pos['symbol']
                    
                    # Manejar campos que pueden no existir en testnet
                    unrealized = pos.get('unrealizedProfit', pos.get('unRealizedProfit', 0))
                    
                    # Obtener leverage, con fallback
                    leverage = pos.get('leverage', self.leverage)
                    
                    # Obtener órdenes abiertas para este símbolo (SL y TP)
                    sl_price = None
                    tp_prices = []
                    
                    try:
                        open_orders = self.client.futures_get_open_orders(symbol=symbol)
                        for order in open_orders:
                            order_type = order['type']
                            stop_price = float(order.get('stopPrice', 0))
                            price = float(order.get('price', 0))
                            
                            # Identificar Stop Loss
                            if order_type in ['STOP_MARKET', 'STOP']:
                                sl_price = stop_price if stop_price > 0 else price
                            
                            # Identificar Take Profits
                            elif order_type in ['TAKE_PROFIT_MARKET', 'TAKE_PROFIT', 'LIMIT']:
                                tp_price = stop_price if stop_price > 0 else price
                                if tp_price > 0:
                                    tp_prices.append(tp_price)
                    except Exception as e:
                        # Si falla obtener órdenes, continuar sin ellas
                        pass
                    
                    # Ordenar TPs
                    tp_prices.sort()
                    
                    open_positions.append({
                        'symbol': pos['symbol'],
                        'side': 'LONG' if position_amt > 0 else 'SHORT',
                        'quantity': abs(position_amt),
                        'entryPrice': float(pos['entryPrice']),
                        'unrealizedProfit': float(unrealized),
                        'leverage': int(leverage) if leverage else self.leverage,
                        'stopLoss': sl_price,
                        'takeProfits': tp_prices
                    })
            
            return open_positions
        except Exception as e:
            print(f"❌ Error al obtener posiciones: {e}")
            return []
    
    def close_position(self, symbol: str) -> bool:
        """Cierra manualmente una posición abierta"""
        try:
            positions = self.get_open_positions()
            
            for pos in positions:
                if pos['symbol'] == symbol:
                    side = "SELL" if pos['side'] == "LONG" else "BUY"
                    
                    order = self.client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type="MARKET",
                        quantity=pos['quantity']
                    )
                    
                    print(f"✅ Posición cerrada: {symbol}")
                    return True
            
            print(f"⚠️ No hay posición abierta en {symbol}")
            return False
            
        except Exception as e:
            print(f"❌ Error al cerrar posición: {e}")
            return False
    
    def cancel_all_orders(self, symbol: str) -> bool:
        """Cancela todas las órdenes pendientes de un símbolo"""
        try:
            self.client.futures_cancel_all_open_orders(symbol=symbol)
            print(f"✅ Órdenes canceladas para {symbol}")
            return True
        except Exception as e:
            print(f"❌ Error al cancelar órdenes: {e}")
            return False


# Función de prueba
if __name__ == "__main__":
    print("🧪 Probando conexión con Binance Futures...\n")
    
    try:
        trader = BinanceFuturesTrader()
        
        # Mostrar balance
        balance = trader.get_account_balance()
        print(f"\n💰 Balance disponible: {balance:.2f} USDT")
        
        # Mostrar posiciones abiertas
        positions = trader.get_open_positions()
        if positions:
            print(f"\n📊 Posiciones abiertas:")
            for pos in positions:
                print(f"  - {pos['symbol']}: {pos['side']} | Qty: {pos['quantity']} | PnL: {pos['unrealizedProfit']:.2f} USDT")
        else:
            print("\n📊 No hay posiciones abiertas")
        
        print("\n✅ Módulo de trading funcionando correctamente!")
        print("\n⚠️ IMPORTANTE: Este script NO ejecuta trades en modo prueba.")
        print("   Para trading real, usa auto_trading_scanner.py")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
