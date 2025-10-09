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


# ========================= Helpers =========================
def _round_to_step(value: float, step: float) -> float:
    """Redondea hacia abajo al múltiplo de step."""
    import math
    if step <= 0:
        return value
    steps = math.floor(value / step)
    prec = len(str(step).split('.')[-1].rstrip('0'))
    return round(steps * step, prec)


def _round_to_tick(price: float, tick: float) -> float:
    """Redondea hacia abajo al múltiplo de tickSize."""
    import math
    if tick <= 0:
        return price
    steps = math.floor(price / tick)
    prec = len(str(tick).split('.')[-1].rstrip('0'))
    return round(steps * tick, prec)


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

    def get_margin_balance(self) -> float:
        """Devuelve el margin balance total reportado por Binance (wallet + PnL no realizado)."""
        try:
            account = self.client.futures_account(recvWindow=60000)
            if account is None:
                return 0.0
            return float(account.get('totalMarginBalance') or account.get('totalWalletBalance') or 0.0)
        except Exception as e:
            print(f"⚠️ Error al obtener margin balance: {e}")
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
        return _round_to_step(quantity, step_size)

    # ---------------- Sizing por riesgo ----------------

    def calculate_position_size(self, symbol: str, entry_price: float, sl_price: float) -> float:
        """
        Qty por riesgo %:
          - Riesgo monetario al SL ≈ qty * |entry - sl| (futuros USDT lineales)
          - NO dividir por leverage (no cambia el riesgo, sólo el margen requerido)
          - Capear notional a balance * leverage
          - Respetar LOT_SIZE y MIN_NOTIONAL
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

            # Ajustes por filtros del símbolo
            f = self._get_symbol_filters(symbol)

            # Si notional < minNotional, subir qty a ese mínimo
            if notional < f["minNotional"]:
                qty_raw = f["minNotional"] / entry_price

            # Respetar stepSize y minQty
            qty = self.round_step_size(qty_raw, f["stepSize"])
            if qty < f["minQty"]:
                qty = f["minQty"]

            # Revalidar notional tras redondeo; si queda por debajo, subir un paso
            if qty * entry_price < f["minNotional"]:
                import math
                steps_needed = math.ceil((f["minNotional"] / entry_price) / f["stepSize"])
                qty = steps_needed * f["stepSize"]
                qty = self.round_step_size(qty, f["stepSize"])

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
        force_market: bool = False
    ) -> Optional[Dict]:
        """
        Abre una posición en Binance Futures con SL y múltiples TPs.
        Parcheado con:
          - Validaciones LONG/SHORT vs mark
          - Redondeo por tickSize para SL/TP
          - workingType="MARK_PRICE", priceProtect=True
          - Compatibilidad hedge mode con positionSide
        """
        try:
            margin_before = self.get_margin_balance()
            # Configurar apalancamiento
            self.set_leverage(symbol, self.leverage)

            # Calcular tamaño de posición
            quantity = self.calculate_position_size(symbol, entry_price, sl_price)
            if quantity <= 0:
                print(f"❌ Cantidad calculada inválida: {quantity}")
                return None

            # Info del símbolo y filtros
            symbol_info = self.get_symbol_info(symbol)
            f = self._get_symbol_filters(symbol)
            step_size = f["stepSize"]
            tick_size = f["tickSize"]

            # Dirección de la orden
            is_long = (side == "LONG")
            order_side = "BUY" if is_long else "SELL"

            print(f"\n{'='*60}")
            print(f"📊 ABRIENDO POSICIÓN {side}")
            print(f"{'='*60}")
            print(f"Symbol: {symbol}")
            print(f"Side: {order_side}")
            print(f"Quantity (pre-redondeo): {quantity}")
            print(f"Entry: {entry_price}")
            print(f"SL: {sl_price}")
            print(f"TPs: {tp_prices}")
            print(f"Leverage: {self.leverage}x")
            print(f"{'='*60}\n")

            # Redondear cantidad a LOT_SIZE
            quantity = self.round_step_size(quantity, step_size)

            # Obtener MARK_PRICE para validaciones de disparo
            mark = float(self.client.futures_mark_price(symbol=symbol)["markPrice"])

            # Redondeos de precios por tick
            entry_price_rounded = _round_to_tick(entry_price, tick_size)
            sl_price_rounded = _round_to_tick(sl_price, tick_size)
            tp_prices_rounded = [_round_to_tick(p, tick_size) for p in tp_prices]

            # Validaciones de disparo correctas
            if is_long and not (sl_price_rounded < mark):
                raise ValueError(f"SL inválido LONG: stopPrice {sl_price_rounded} debe ser < mark {mark}")
            if (not is_long) and not (sl_price_rounded > mark):
                raise ValueError(f"SL inválido SHORT: stopPrice {sl_price_rounded} debe ser > mark {mark}")
            for i, p in enumerate(tp_prices_rounded):
                if is_long and not (p > mark):
                    raise ValueError(f"TP{i+1} inválido LONG: stopPrice {p} debe ser > mark {mark}")
                if (not is_long) and not (p < mark):
                    raise ValueError(f"TP{i+1} inválido SHORT: stopPrice {p} debe ser < mark {mark}")

            # Detectar hedge mode
            try:
                hedge = self.client.futures_position_mode()['dualSidePosition']  # True = hedge
            except Exception:
                hedge = False
            position_side = "LONG" if is_long else "SHORT"

            # ===== Orden de entrada =====
            if force_market:
                entry_order = self.client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type="MARKET",
                    quantity=quantity
                )
                actual_entry = float(entry_order.get('avgPrice', entry_price_rounded))
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

            # Asegurar entry real válido (> 0). En órdenes MARKET, avgPrice puede venir 0.
            try:
                # Intentar varias veces leer entryPrice de la posición si avgPrice es 0
                attempts = 0
                while ((not actual_entry) or (actual_entry <= 0)) and attempts < 10:
                    pos_info = self.client.futures_position_information(symbol=symbol)
                    for _p in pos_info:
                        if _p.get('symbol') == symbol:
                            amt = float(_p.get('positionAmt', 0))
                            ep = float(_p.get('entryPrice', 0))
                            if abs(amt) > 0 and ep > 0:
                                actual_entry = ep
                                break
                    if (not actual_entry) or (actual_entry <= 0):
                        time.sleep(0.2)
                        attempts += 1
                if (not actual_entry) or (actual_entry <= 0):
                    # Fallback conservador: usar el precio de orden redondeado o mark
                    actual_entry = entry_price_rounded if entry_price_rounded > 0 else mark
            except Exception:
                if (not actual_entry) or (actual_entry <= 0):
                    actual_entry = entry_price_rounded if entry_price_rounded > 0 else mark

            # ——— Ajuste extra: asegurar que los TP estén del lado correcto respecto al precio de entrada real ———
            try:
                # Refrescar mark para validar después del ajuste
                mark_after = float(self.client.futures_mark_price(symbol=symbol)["markPrice"])
            except Exception:
                mark_after = mark

            # Asegurar TPs correctos según el lado de la operación
            def _fallback_tps(entry: float, sl: float, is_long_pos: bool) -> List[float]:
                # Genera 3 TPs basados en la distancia al SL (0.6, 0.8, 1.0 R)
                dist = abs(entry - sl)
                if dist <= tick_size:
                    dist = tick_size * 3
                scales = [1.0, 0.8, 0.6]
                if is_long_pos:
                    return [_round_to_tick(entry + dist * s, tick_size) for s in scales]
                else:
                    return [_round_to_tick(entry - dist * s, tick_size) for s in scales]

            # Filtrar TPs por lado rentable relativo a la entrada real
            orig_tp = list(tp_prices_rounded)
            if is_long:
                tp_prices_rounded = [p for p in tp_prices_rounded if p > actual_entry]
                # Orden ascendente para LONG (del más cercano al más lejano)
                tp_prices_rounded.sort()
            else:
                tp_prices_rounded = [p for p in tp_prices_rounded if p < actual_entry]
                # Orden descendente para SHORT (del más cercano al más lejano)
                tp_prices_rounded.sort(reverse=True)

            if len(tp_prices_rounded) == 0:
                print("⚠️ Ningún TP original estaba del lado correcto vs entry; generando TPs de respaldo basados en SL…")
                tp_prices_rounded = _fallback_tps(actual_entry, sl_price_rounded, is_long)

            # Revalidar relación con mark price (LONG: TP > mark; SHORT: TP < mark)
            tps_ok = []
            for p in tp_prices_rounded:
                # Evitar precios no positivos
                if p <= 0:
                    p = tick_size
                if is_long and p <= mark_after:
                    # Empujar al menos 1 tick por encima del mark
                    p = _round_to_tick(mark_after + tick_size, tick_size)
                if (not is_long) and p >= mark_after:
                    # Empujar al menos 1 tick por debajo del mark
                    p = _round_to_tick(mark_after - tick_size, tick_size)
                tps_ok.append(p)

            # Eliminar duplicados manteniendo el orden
            seen = set()
            tp_prices_rounded = []
            for p in tps_ok:
                if p not in seen:
                    tp_prices_rounded.append(p)
                    seen.add(p)

            # Log si hubo ajuste
            if tp_prices_rounded != orig_tp:
                print("ℹ️ TPs ajustados respecto a la entrada real para asegurar dirección correcta:")
                print(f"   Antes: {orig_tp}")
                print(f"   Después: {tp_prices_rounded}")

            # Cantidad real (por si hubo fill parcial)
            actual_position_qty = quantity
            position_id = None
            isolated_margin = None
            position_notional = None
            try:
                positions_info = self.client.futures_position_information(symbol=symbol)
                for p in positions_info:
                    if p.get('symbol') == symbol:
                        actual_position_qty = abs(float(p.get('positionAmt', 0)))
                        position_id = str(p.get('positionId') or f"{symbol}-{p.get('positionSide', 'BOTH')}")
                        try:
                            isolated_margin = float(p.get('isolatedMargin')) if p.get('isolatedMargin') is not None else None
                        except Exception:
                            isolated_margin = None
                        try:
                            position_notional = abs(float(p.get('notional'))) if p.get('notional') is not None else None
                        except Exception:
                            position_notional = None
                        break
            except Exception:
                actual_position_qty = quantity
                position_id = None

            quantity = self.round_step_size(actual_position_qty, step_size)

            margin_after_entry = self.get_margin_balance()
            position_notional = position_notional or (abs(quantity) * actual_entry)
            margin_used = None
            try:
                if self.leverage > 0:
                    margin_used = position_notional / self.leverage
            except Exception:
                margin_used = None

            # ========== CREACIÓN DE ÓRDENES SL Y TP ==========
            print(f"\n{'='*60}")
            print(f"🎯 CONFIGURANDO STOP LOSS Y TAKE PROFITS")
            print(f"{'='*60}")

            sl_order = None
            tp_orders = []

            # ===== STOP LOSS =====
            sl_side = "SELL" if is_long else "BUY"
            sl_kwargs = dict(
                symbol=symbol,
                side=sl_side,
                type="STOP_MARKET",
                stopPrice=sl_price_rounded,
                workingType="MARK_PRICE",
                priceProtect=True
            )
            if hedge:
                sl_kwargs["positionSide"] = position_side
                sl_kwargs["closePosition"] = True
            else:
                sl_kwargs["closePosition"] = True

            max_sl_retries = 3
            for attempt in range(max_sl_retries):
                try:
                    sl_order = self.client.futures_create_order(**sl_kwargs)
                    print(f"✅ Stop Loss creado (id={sl_order.get('orderId')}, price={sl_price_rounded})")
                    break
                except Exception as e:
                    print(f"❌ SL intento {attempt + 1}/{max_sl_retries} falló: {e}")
                    if attempt < max_sl_retries - 1:
                        time.sleep(1)

            # ===== TAKE PROFITS =====
            if len(tp_prices_rounded) > 0 and quantity > 0:
                tp_target_count = len(tp_prices_rounded)
                print(f"\n🎯 Creando {tp_target_count} Take Profit(s)...")

                # qty por TP
                base_tp_qty = self.round_step_size(quantity / tp_target_count, step_size)
                tp_side = "SELL" if is_long else "BUY"
                final_tp_prices: List[float] = []

                for i, tp in enumerate(tp_prices_rounded, 1):
                    # Garantizar condición estricta respecto a la entrada real
                    if is_long and tp <= actual_entry:
                        tp = _round_to_tick(actual_entry + tick_size, tick_size)
                    elif (not is_long) and tp >= actual_entry:
                        tp = _round_to_tick(actual_entry - tick_size, tick_size)

                    # Revalidación adicional vs mark actual por seguridad
                    try:
                        current_mark = float(self.client.futures_mark_price(symbol=symbol)["markPrice"])
                    except Exception:
                        current_mark = mark
                    if is_long and tp <= current_mark:
                        tp = _round_to_tick(max(current_mark, actual_entry) + tick_size, tick_size)
                    if (not is_long) and tp >= current_mark:
                        tp = _round_to_tick(min(current_mark, actual_entry) - tick_size, tick_size)

                    use_qty = base_tp_qty if i < len(tp_prices_rounded) else self.round_step_size(
                        quantity - base_tp_qty * (len(tp_prices_rounded) - 1), step_size
                    )
                    if use_qty <= 0:
                        continue

                    tp_kwargs = dict(
                        symbol=symbol,
                        side=tp_side,
                        type="TAKE_PROFIT_MARKET",
                        stopPrice=tp,
                        quantity=use_qty,
                        reduceOnly=True,
                        workingType="MARK_PRICE",
                        priceProtect=True
                    )
                    if hedge:
                        tp_kwargs["positionSide"] = position_side

                    max_tp_retries = 3
                    for attempt in range(max_tp_retries):
                        try:
                            tp_order = self.client.futures_create_order(**tp_kwargs)
                            tp_orders.append(tp_order)
                            actual_tp_price = float(tp_order.get('stopPrice') or tp_order.get('price') or tp)
                            final_tp_prices.append(actual_tp_price)
                            print(f"   ✅ TP{i} creado (id={tp_order.get('orderId')}, price={actual_tp_price}, qty={use_qty})")
                            break
                        except Exception as e:
                            print(f"   ❌ TP{i} intento {attempt + 1}/{max_tp_retries} falló: {e}")
                            if attempt < max_tp_retries - 1:
                                time.sleep(1)
                    time.sleep(0.25)

                if final_tp_prices:
                    tp_prices_rounded = final_tp_prices
                else:
                    tp_prices_rounded = []

            # ===== RESUMEN =====
            print(f"\n{'='*60}")
            print(f"📋 RESUMEN DE ÓRDENES")
            print(f"{'='*60}")
            print(f"Stop Loss: {'CREADO' if sl_order else 'NO CREADO'}")
            print(f"Take Profits creados: {len(tp_orders)}/{len(tp_prices_rounded)}")

            if not sl_order:
                print("\n⚠️ ATENCIÓN: NO se pudo crear el Stop Loss. La posición está desprotegida.\n")

            # ===== VERIFICACIÓN EN BINANCE =====
            print("\n🔍 Verificando órdenes en Binance...")
            time.sleep(1)
            try:
                open_orders = self.client.futures_get_open_orders(symbol=symbol)
                sl_found = False
                tp_count = 0
                print("\n📋 Órdenes activas encontradas:")
                for order in open_orders:
                    otype = order.get('type', '')
                    oid = order.get('orderId', '')
                    sprice = order.get('stopPrice', '')
                    qty = order.get('origQty', '')
                    if 'STOP' in otype and 'TAKE_PROFIT' not in otype:
                        sl_found = True
                        print(f"   🛑 SL: id={oid} | price={sprice}")
                    elif 'TAKE_PROFIT' in otype:
                        tp_count += 1
                        print(f"   🎯 TP: id={oid} | price={sprice} | qty={qty}")
                if not sl_found:
                    print("❌ No se encontró SL activo.")
                if tp_count == len(tp_prices_rounded):
                    print(f"✅ Verificados {tp_count}/{len(tp_prices_rounded)} TP")
                else:
                    print(f"⚠️ Verificados {tp_count}/{len(tp_prices_rounded)} TP")
            except Exception as e:
                print(f"⚠️ Error al verificar órdenes: {e}")

            result = {
                'symbol': symbol,
                'side': side,
                'entry_order': entry_order,
                'sl_order': sl_order,
                'tp_orders': tp_orders,
                'quantity': quantity,
                'entry_price': actual_entry,
                'sl_price': sl_price_rounded,
                'tp_prices': tp_prices_rounded,
                'leverage': self.leverage,
                'position_id': position_id,
                'isolated_margin': isolated_margin,
                'position_notional': position_notional,
                'margin_before': margin_before,
                'margin_after': margin_after_entry,
                'margin_used': margin_used,
                'entry_order_id': str(entry_order.get('orderId')) if isinstance(entry_order, dict) else None,
                'entry_client_order_id': entry_order.get('clientOrderId') if isinstance(entry_order, dict) else None
            }

            print(f"\n{'='*60}")
            print(f"✅ Posición {side} abierta exitosamente en {symbol}")
            print(f"{'='*60}\n")

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
                        'takeProfits': tp_prices,
                        'position_id': str(pos.get('positionId') or f"{symbol}-{pos.get('positionSide', 'BOTH')}") if symbol else None,
                        'marginType': pos.get('marginType'),
                        'isolatedMargin': float(pos.get('isolatedMargin')) if pos.get('isolatedMargin') else None,
                        'notional': float(pos.get('notional')) if pos.get('notional') else abs(position_amt) * float(pos['entryPrice']) if pos.get('entryPrice') else None
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
        """Cancela todas las órdenes pendientes de un símbolo."""
        try:
            self.client.futures_cancel_all_open_orders(symbol=symbol)
            print(f"✅ Órdenes canceladas para {symbol}")
            return True
        except Exception as e:
            print(f"❌ Error al cancelar órdenes: {e}")
            return False


# ========================= Prueba rápida =========================
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
