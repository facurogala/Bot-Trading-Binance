"""
Módulo de trading automático para Binance Futures
Maneja la ejecución de órdenes con SL y TP automáticos
Incluye reconciliación automática de órdenes
"""
import os
import time
from typing import Dict, Optional, List

from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

load_dotenv()


class BinanceFuturesTrader:
    def __init__(self):
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")
        self.testnet = os.getenv("TESTNET", "False").lower() == "true"
        self.reconciler = None  # Se inicializa después del cliente

        if not api_key or not api_secret:
            raise ValueError("❌ Error: BINANCE_API_KEY o BINANCE_API_SECRET no están configurados en .env")

        # Configurar cliente según modo
        if self.testnet:
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

        # Verificar credenciales
        try:
            _ = self.client.futures_account(recvWindow=60000)
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
        self.leverage = int(os.getenv("LEVERAGE", "5"))                 # Apalancamiento por defecto
        self.risk_percent = float(os.getenv("RISK_PERCENT", "1.0"))     # % de capital por trade
        self.risk_on_available = os.getenv("RISK_ON_AVAILABLE", "True").lower() == "true"  # True = availableBalance

        # Inicializar reconciler
        try:
            from order_reconciler import OrderReconciler
            self.reconciler = OrderReconciler(self)
            print("✅ Order Reconciler inicializado")
        except Exception as e:
            print(f"⚠️ No se pudo inicializar Order Reconciler: {e}")
            self.reconciler = None

    # ---------------- Saldo y símbolo ----------------

    def get_account_balance(self) -> float:
        """Obtiene el balance en USDT (available o wallet total según RISK_ON_AVAILABLE)."""
        try:
            account = self.client.futures_account(recvWindow=60000)
            for asset in account['assets']:
                if asset['asset'] == 'USDT':
                    if self.risk_on_available:
                        return float(asset.get('availableBalance', asset.get('walletBalance', 0)))
                    return float(asset.get('walletBalance', asset.get('availableBalance', 0)))
            return 0.0
        except Exception as e:
            print(f"❌ Error al obtener balance: {e}")
            return 0.0

    def get_symbol_info(self, symbol: str) -> Dict:
        """Obtiene información del símbolo (precisión, min notional, etc)."""
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

    def _get_symbol_filters(self, symbol: str) -> Dict:
        """Extrae LOT_SIZE, PRICE_FILTER y MIN_NOTIONAL/NOTIONAL del símbolo."""
        try:
            info = self.client.futures_exchange_info()
            for s in info["symbols"]:
                if s["symbol"] == symbol:
                    lot = next(f for f in s["filters"] if f["filterType"] == "LOT_SIZE")
                    prc = next(f for f in s["filters"] if f["filterType"] == "PRICE_FILTER")
                    mn = next((f for f in s["filters"] if f["filterType"] in ("MIN_NOTIONAL", "NOTIONAL")), None)
                    return {
                        "stepSize": float(lot["stepSize"]),
                        "minQty": float(lot["minQty"]),
                        "tickSize": float(prc["tickSize"]),
                        "minNotional": float(mn.get("notional", mn.get("minNotional", 5.0))) if mn else 5.0,
                    }
        except Exception as e:
            print(f"⚠️ _get_symbol_filters error {symbol}: {e}")
        return {"stepSize": 0.001, "minQty": 0.001, "tickSize": 0.01, "minNotional": 5.0}

    # ---------------- Redondeos ----------------

    def round_step_size(self, quantity: float, step_size: float) -> float:
        """Redondea la cantidad hacia abajo según el step_size del símbolo."""
        try:
            import math
            if step_size <= 0:
                return quantity
            steps = math.floor(quantity / step_size)
            q = steps * step_size
            precision = len(str(step_size).split('.')[-1].rstrip('0'))
            return round(q, precision)
        except Exception:
            precision = len(str(step_size).split('.')[-1].rstrip('0'))
            return round(quantity - (quantity % step_size), precision)

    # ---------------- Sizing por riesgo ----------------

    def calculate_position_size(self, symbol: str, entry_price: float, sl_price: float,
                                 min_margin_usdt: float = 0.0,
                                 max_margin_usdt: float = 0.0) -> float:
        """
        Qty por riesgo %:
          - Riesgo monetario al SL ≈ qty * |entry - sl| (futuros USDT lineales)
          - NO dividir por leverage (no cambia el riesgo, sólo el margen requerido)
          - Capear notional a balance * leverage
          - Respetar LOT_SIZE y MIN_NOTIONAL
          - Si max_margin_usdt > 0: cap margin (notional/leverage) a ese valor
          - Si min_margin_usdt > 0: asegurar margin >= ese valor (o rechazar)
        """
        try:
            balance = self.get_account_balance()
            risk_amount = balance * (self.risk_percent / 100.0)
            delta = abs(entry_price - sl_price)

            if entry_price <= 0 or delta <= 0:
                return 0.0

            # Tamaño teórico por riesgo (sin leverage)
            qty_raw = risk_amount / delta           # contratos (monedas)
            notional = qty_raw * entry_price

            # Cap por leverage: evitar notional > balance * leverage
            max_notional = balance * self.leverage
            if notional > max_notional:
                qty_raw = max_notional / entry_price
                notional = qty_raw * entry_price

            # --- Clamp por margen USDT (min/max) ---
            if max_margin_usdt > 0:
                max_notional_by_margin = max_margin_usdt * self.leverage
                if notional > max_notional_by_margin:
                    qty_raw = max_notional_by_margin / entry_price
                    notional = qty_raw * entry_price
                    print(f"📏 Margin capped a {max_margin_usdt} USDT → notional {notional:.2f} USDT")

            if min_margin_usdt > 0:
                min_notional_by_margin = min_margin_usdt * self.leverage
                if notional < min_notional_by_margin:
                    qty_raw = min_notional_by_margin / entry_price
                    notional = qty_raw * entry_price
                    print(f"📏 Margin subido a mínimo {min_margin_usdt} USDT → notional {notional:.2f} USDT")

            # Ajustes por filtros del símbolo
            f = self._get_symbol_filters(symbol)

            # Si notional < minNotional, subir qty a ese mínimo (o devolver 0 si no querés subir riesgo)
            if notional < f["minNotional"]:
                qty_raw = f["minNotional"] / entry_price

            # Respetar stepSize y minQty
            qty = self.round_step_size(qty_raw, f["stepSize"])
            if qty < f["minQty"]:
                qty = f["minQty"]

            # Revalidar notional tras redondeo; si aún queda por debajo del mínimo, subir un paso
            if qty * entry_price < f["minNotional"]:
                import math
                steps_needed = math.ceil((f["minNotional"] / entry_price) / f["stepSize"])
                qty = steps_needed * f["stepSize"]
                qty = self.round_step_size(qty, f["stepSize"])

            # --- Validación final: si tras redondeo el margin excede el max, rechazar ---
            if max_margin_usdt > 0:
                final_margin = (qty * entry_price) / self.leverage
                if final_margin > max_margin_usdt * 1.10:  # 10% tolerancia por redondeo
                    print(f"⚠️ Margin final {final_margin:.2f} excede max {max_margin_usdt} USDT tras redondeo")
                    return 0.0

            return max(qty, 0.0)
        except Exception as e:
            print(f"⚠️ sizing error {symbol}: {e}")
            return 0.0

    # ---------------- Leverage ----------------

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Configura el apalancamiento para un símbolo."""
        try:
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            return True
        except BinanceAPIException as e:
            print(f"⚠️ Error al configurar leverage: {e}")
            return False

    # ---------------- Apertura de posición ----------------

    def open_position(
        self,
        symbol: str,
        side: str,  # "LONG" o "SHORT"
        entry_price: float,
        sl_price: float,
        tp_prices: List[float],
        force_market: bool = False,
        min_margin_usdt: float = 0.0,
        max_margin_usdt: float = 0.0,
    ) -> Optional[Dict]:
        """
        Abre una posición en Binance Futures con SL y múltiples TPs.
        min_margin_usdt / max_margin_usdt: clampean el margen (USDT) por trade.
        """
        try:
            # Configurar apalancamiento
            self.set_leverage(symbol, self.leverage)

            # Calcular tamaño de posición
            quantity = self.calculate_position_size(
                symbol, entry_price, sl_price,
                min_margin_usdt=min_margin_usdt,
                max_margin_usdt=max_margin_usdt,
            )
            if quantity <= 0:
                print(f"❌ Cantidad calculada inválida: {quantity}")
                return None

            # Redondear cantidad según LOT_SIZE (por si acaso)
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
            price_precision = symbol_info.get('pricePrecision', 2) if symbol_info else 2
            entry_price_rounded = round(entry_price, price_precision)

            # Orden de entrada
            if force_market:
                entry_order = self.client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type="MARKET",
                    quantity=quantity
                )
                avg_price_raw = entry_order.get('avgPrice', entry_price_rounded)
                try:
                    actual_entry = float(avg_price_raw)
                except Exception:
                    actual_entry = float(entry_price_rounded)
                if actual_entry <= 0:
                    actual_entry = float(entry_price_rounded)
                print(f"✅ Orden de entrada (MARKET) ejecutada: {entry_order.get('orderId')}")
                order_info = entry_order
            else:
                entry_order = self.client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type="LIMIT",
                    timeInForce="GTC",
                    quantity=quantity,
                    price=entry_price_rounded
                )
                print(f"✅ Orden de entrada (LIMIT) creada: {entry_order.get('orderId')} - esperando fill...")

                # Esperar fill de la LIMIT
                try:
                    timeout = int(os.getenv('ORDER_FILL_TIMEOUT', '30'))  # segundos
                    elapsed = 0.0
                    order_info = None
                    status = entry_order.get('status', '')
                    while (status != 'FILLED') and (elapsed < timeout):
                        time.sleep(0.5)
                        elapsed += 0.5
                        try:
                            order_info = self.client.futures_get_order(symbol=symbol, orderId=entry_order['orderId'])
                            status = order_info.get('status', '')
                        except Exception:
                            pass

                    if status != 'FILLED':
                        print(f"⚠️ Orden de entrada no se llenó en {timeout}s (status={status}). Cancelando orden.")
                        try:
                            self.client.futures_cancel_order(symbol=symbol, orderId=entry_order['orderId'])
                        except Exception:
                            pass
                        return None

                    actual_entry = float(order_info.get('avgPrice', entry_price_rounded)) if order_info else entry_price_rounded

                except Exception as e:
                    print(f"⚠️ Error al esperar fill de la orden de entrada: {e}")
                    return None

            # Cantidad real y entry real (por si hubo fill parcial o avgPrice vino en 0)
            actual_position_qty = quantity
            try:
                positions_info = self.client.futures_position_information(symbol=symbol)
                for p in positions_info:
                    if p['symbol'] == symbol:
                        actual_position_qty = abs(float(p.get('positionAmt', 0)))
                        pos_entry = float(p.get('entryPrice', 0))
                        if pos_entry > 0:
                            actual_entry = pos_entry
                        break
            except Exception:
                actual_position_qty = quantity

            quantity = actual_position_qty

            print(f"\n🔄 Usando reconciliación de órdenes para garantizar SL/TP en Binance...")
            sl_order = None
            tp_orders = []

            if self.reconciler:
                try:
                    sl_order, tp_orders = self.reconciler.ensure_orders_exist(
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        sl_price=sl_price,
                        tp_prices=tp_prices,
                        max_retries=3
                    )
                    if sl_order and len(tp_orders) > 0:
                        print(f"✅ Reconciliación exitosa: 1 SL + {len(tp_orders)} TP(s)")
                    else:
                        print(f"⚠️ Reconciliación parcial: SL={bool(sl_order)}, TPs={len(tp_orders)}")
                except Exception as e:
                    print(f"⚠️ Error en reconciliación: {e}")
                    print("   Intentando método tradicional...")

            # Fallback tradicional
            if not self.reconciler or not sl_order:
                print("⚠️ Usando creación tradicional de órdenes (sin reconciler)")
                sl_side = "SELL" if side == "LONG" else "BUY"
                if symbol_info:
                    price_precision = symbol_info['pricePrecision']
                    sl_price = round(sl_price, price_precision)

                try:
                    sl_order = self.client.futures_create_order(
                        symbol=symbol,
                        side=sl_side,
                        type="STOP_MARKET",
                        stopPrice=sl_price,
                        closePosition=True
                    )
                    print(f"✅ Stop Loss configurado: {sl_order.get('orderId')}")
                except Exception as e:
                    print(f"⚠️ Error al configurar Stop Loss: {e}")
                    sl_order = None

                if len(tp_prices) > 0 and len(tp_orders) == 0:
                    tp_quantity = quantity / len(tp_prices) if quantity > 0 else 0
                    if symbol_info:
                        for f in symbol_info['filters']:
                            if f['filterType'] == 'LOT_SIZE':
                                step_size = float(f['stepSize'])
                                tp_quantity = self.round_step_size(tp_quantity, step_size)
                                break

                    tp_side = "SELL" if side == "LONG" else "BUY"
                    price_precision = symbol_info.get('pricePrecision', 2) if symbol_info else 2

                    for i, tp_price in enumerate(tp_prices, 1):
                        try:
                            if i == len(tp_prices):
                                remaining_qty = quantity - (tp_quantity * (len(tp_prices) - 1))
                                use_qty = remaining_qty
                            else:
                                use_qty = tp_quantity

                            tp_price_rounded = round(tp_price, price_precision)

                            tp_order = self.client.futures_create_order(
                                symbol=symbol,
                                side=tp_side,
                                type="TAKE_PROFIT_MARKET",
                                stopPrice=tp_price_rounded,
                                quantity=use_qty,
                                reduceOnly=True
                            )
                            tp_orders.append(tp_order)
                            print(f"✅ TP{i} configurado en {tp_price_rounded}: {tp_order.get('orderId')}")
                            time.sleep(0.2)
                        except Exception as e:
                            print(f"⚠️ Error al configurar TP{i}: {e}")

            if not sl_order:
                print("❌ No se pudo confirmar Stop Loss. Activando cierre de seguridad...")
                try:
                    self.cancel_all_orders(symbol)
                except Exception:
                    pass

                self.close_position(symbol)
                return None

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

            # Monitoreo opcional
            enable_monitoring = os.getenv("ENABLE_ORDER_MONITORING", "True").lower() == "true"
            if enable_monitoring and self.reconciler:
                monitor_duration = int(os.getenv("ORDER_MONITOR_DURATION", "120"))  # seg
                monitor_interval = int(os.getenv("ORDER_MONITOR_INTERVAL", "15"))   # seg
                print(f"👁️ Iniciando monitoreo de órdenes ({monitor_duration}s)...")
                self.reconciler.start_monitoring(
                    symbol=symbol,
                    trade_id=0,
                    duration_seconds=monitor_duration,
                    check_interval=monitor_interval
                )

            return result

        except BinanceAPIException as e:
            print(f"❌ Error de Binance API: {e}")
            return None
        except Exception as e:
            print(f"❌ Error al abrir posición: {e}")
            return None

    # ---------------- Posiciones / Cierre / Cancelación ----------------

    def get_open_positions(self) -> List[Dict]:
        """Obtiene todas las posiciones abiertas con sus órdenes SL/TP."""
        try:
            positions = self.client.futures_position_information(recvWindow=60000)
            open_positions = []

            for pos in positions:
                position_amt = float(pos['positionAmt'])
                if position_amt != 0:
                    symbol = pos['symbol']

                    unrealized = pos.get('unrealizedProfit', pos.get('unRealizedProfit', 0))
                    leverage = pos.get('leverage', self.leverage)

                    sl_price = None
                    tp_prices = []
                    try:
                        open_orders = self.client.futures_get_open_orders(symbol=symbol)
                        for order in open_orders:
                            order_type = order['type']
                            stop_price = float(order.get('stopPrice', 0))
                            price = float(order.get('price', 0))
                            if order_type in ['STOP_MARKET', 'STOP']:
                                sl_price = stop_price if stop_price > 0 else price
                            elif order_type in ['TAKE_PROFIT_MARKET', 'TAKE_PROFIT', 'LIMIT']:
                                tp_price = stop_price if stop_price > 0 else price
                                if tp_price > 0:
                                    tp_prices.append(tp_price)
                    except Exception:
                        pass

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
        """Cierra manualmente una posición abierta."""
        try:
            positions = self.get_open_positions()
            for pos in positions:
                if pos['symbol'] == symbol:
                    side = "SELL" if pos['side'] == "LONG" else "BUY"
                    _ = self.client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type="MARKET",
                        quantity=pos['quantity'],
                        reduceOnly=True
                    )
                    print(f"✅ Posición cerrada: {symbol}")
                    return True
            print(f"⚠️ No hay posición abierta en {symbol}")
            return False
        except Exception as e:
            print(f"❌ Error al cerrar posición: {e}")
            return False

    def cancel_all_orders(self, symbol: str) -> bool:
        """Cancela todas las órdenes pendientes de un símbolo."""
        try:
            self.client.futures_cancel_all_open_orders(symbol=symbol)
            print(f"✅ Órdenes canceladas para {symbol}")
            return True
        except Exception as e:
            print(f"❌ Error al cancelar órdenes: {e}")
            return False

    def update_stop_loss(self, symbol: str, side: str, new_sl_price: float) -> bool:
        """Reemplaza el stop loss actual por uno nuevo para una posición abierta."""
        try:
            existing_orders = self.client.futures_get_open_orders(symbol=symbol)
            stop_orders = []
            for order in existing_orders:
                order_type = order.get('type', '')
                if order_type in ['STOP_MARKET', 'STOP']:
                    stop_orders.append(order)

            for stop_order in stop_orders:
                try:
                    self.client.futures_cancel_order(symbol=symbol, orderId=stop_order['orderId'])
                except Exception:
                    pass

            created_order = None
            if self.reconciler:
                created_order = self.reconciler.create_stop_loss(symbol=symbol, side=side, sl_price=new_sl_price)
            else:
                sl_side = "SELL" if side == "LONG" else "BUY"
                symbol_info = self.get_symbol_info(symbol)
                if symbol_info:
                    new_sl_price = round(new_sl_price, symbol_info.get('pricePrecision', 2))

                created_order = self.client.futures_create_order(
                    symbol=symbol,
                    side=sl_side,
                    type="STOP_MARKET",
                    stopPrice=new_sl_price,
                    closePosition=True
                )

            if created_order:
                print(f"🔒 SL actualizado en {symbol}: {new_sl_price}")
                return True

            print(f"⚠️ No se pudo crear el nuevo SL para {symbol}")
            return False
        except Exception as e:
            print(f"❌ Error al actualizar Stop Loss en {symbol}: {e}")
            return False


# Función de prueba
if __name__ == "__main__":
    print("🧪 Probando conexión con Binance Futures...\n")
    try:
        trader = BinanceFuturesTrader()

        balance = trader.get_account_balance()
        print(f"\n💰 Balance base para riesgo: {balance:.2f} USDT "
              f"({'available' if trader.risk_on_available else 'wallet'})")

        positions = trader.get_open_positions()
        if positions:
            print(f"\n📊 Posiciones abiertas:")
            for pos in positions:
                print(f"  - {pos['symbol']}: {pos['side']} | Qty: {pos['quantity']} | "
                      f"PnL: {pos['unrealizedProfit']:.2f} USDT")
        else:
            print("\n📊 No hay posiciones abiertas")

        print("\n✅ Módulo de trading funcionando correctamente!")
        print("\n⚠️ IMPORTANTE: Este script NO ejecuta trades en modo prueba.")
        print("   Para trading real, usa auto_trading_scanner.py")
    except Exception as e:
        print(f"\n❌ Error: {e}")
