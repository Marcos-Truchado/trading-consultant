"""
IBKR Connector
==============
Conexión a Trader Workstation / IB Gateway para:
  1. Traer histórico de precios (sustituye a yfinance en el dashboard)
  2. Leer posiciones y resumen de cuenta
  3. Enviar órdenes MANUALES cuando tú lo decidas desde el dashboard

CÓMO EVITA EL LÍO DE THREADING CON STREAMLIT
---------------------------------------------
Streamlit reejecuta tu script en su propio hilo con cada interacción, y ese
hilo no tiene garantizado un event loop de asyncio válido en todo momento.
ib_insync/ib_async SÍ necesitan un loop vivo para funcionar. Parchear esto
"arreglando el loop del hilo de Streamlit" en cada método no es fiable:
Streamlit puede cambiar el estado de ese hilo entre reruns.

La solución de fondo: toda la comunicación con IBKR corre en un HILO PROPIO,
separado, que mantiene su event loop vivo todo el tiempo (loop.run_forever()).
Streamlit nunca toca ese loop directamente -- solo manda corutinas a ese hilo
con run_coroutine_threadsafe() y espera el resultado con un timeout. Así el
hilo de Streamlit ni se entera de que existe asyncio.

No se usa ninguna medida de seguridad, por el momento, el programa no sale internet,
solo corre en localhost.


Requisitos:
  pip install ib_insync   (o ib_async si tienes Python 3.10+)
  TWS o IB Gateway corriendo en local con API habilitada.
"""
import asyncio
import threading
import pandas as pd
from typing import Optional, List, Dict

# eventkit (dependencia de ib_insync) pide un event loop de asyncio ya activo
# en el momento de IMPORTARSE, en el hilo que hace el import. Streamlit corre
# el script en un hilo ('ScriptRunner.scriptThread') que no trae uno por
# defecto, así que hay que crearlo aquí ANTES del import o revienta al cargar
# el módulo.
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

try:
    from ib_async import IB, Stock, MarketOrder, LimitOrder, util
except ImportError:
    from ib_insync import IB, Stock, MarketOrder, LimitOrder, util


class _IBLoopThread:
    """
    Hilo único, compartido por toda la app, con un event loop de asyncio que
    vive permanentemente. Se crea la primera vez que se necesita y se
    reutiliza siempre -- así evitamos el problema de que Streamlit reejecute
    el script y "pierda" el loop.
    """
    _loop: Optional[asyncio.AbstractEventLoop] = None
    _thread: Optional[threading.Thread] = None
    _lock = threading.Lock()

    @classmethod
    def get_loop(cls) -> asyncio.AbstractEventLoop:
        with cls._lock:
            if cls._loop is None or cls._loop.is_closed():
                cls._loop = asyncio.new_event_loop()

                def _run():
                    # set_event_loop hay que llamarlo DENTRO del hilo que lo va
                    # a usar -- pasar el objeto loop desde fuera no basta,
                    # asyncio.get_event_loop() sigue sin encontrar nada si no
                    # se registra explícitamente aquí.
                    asyncio.set_event_loop(cls._loop)
                    cls._loop.run_forever()

                cls._thread = threading.Thread(target=_run, daemon=True, name="IBKR-loop")
                cls._thread.start()
        return cls._loop

    @classmethod
    def run(cls, coro, timeout: float = 30):
        """Ejecuta una corutina en el hilo dedicado y espera el resultado."""
        loop = cls.get_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result(timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"IBKR no respondió en {timeout}s. Revisa en IB Gateway/TWS si hay "
                "algún mensaje de error (activa 'Mostrar mensajes API'), y confirma "
                "que la API está habilitada y el puerto es el correcto."
            )


class IBKRConnector:
    def __init__(self, host: str = '127.0.0.1', port: int = 7497, client_id: int = 1):
        self.ib: Optional[IB] = None
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connected = False

    # ---------------- Conexión ----------------

    def connect(self) -> Dict:
        async def _do_connect():
            ib = IB()
            await ib.connectAsync(self.host, self.port, clientId=self.client_id, timeout=10)
            # Sin suscripción de mercado en tiempo real -> pedimos datos DELAYED (gratis)
            ib.reqMarketDataType(3)
            return ib

        try:
            self.ib = _IBLoopThread.run(_do_connect(), timeout=15)
            self.connected = True
            return {"ok": True, "msg": f"Conectado a {self.host}:{self.port}"}
        except Exception as e:
            self.connected = False
            self.ib = None
            return {"ok": False, "msg": f"Error de conexión: {e}. ¿Está TWS/Gateway abierto y la API habilitada?"}

    def disconnect(self):
        if self.connected and self.ib:
            async def _do_disconnect():
                self.ib.disconnect()
            try:
                _IBLoopThread.run(_do_disconnect(), timeout=5)
            except Exception:
                pass
        self.connected = False
        self.ib = None

    # ---------------- Datos ----------------

    def get_historical_bars(self, ticker: str, duration: str = "2 Y", bar_size: str = "1 day") -> Optional[pd.DataFrame]:
        if not self.connected or not self.ib:
            raise ConnectionError("No conectado a IBKR. Llama a connect() primero.")

        async def _do_fetch():
            contract = Stock(ticker.upper(), 'SMART', 'USD')
            await self.ib.qualifyContractsAsync(contract)
            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1,
            )
            return bars

        bars = _IBLoopThread.run(_do_fetch(), timeout=30)
        if not bars:
            return None

        df = util.df(bars)
        df.rename(columns={
            'date': 'Date', 'open': 'Open', 'high': 'High',
            'low': 'Low', 'close': 'Close', 'volume': 'Volume',
        }, inplace=True)
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        return df

    def get_positions(self) -> List[Dict]:
        if not self.connected or not self.ib:
            raise ConnectionError("No conectado a IBKR.")

        async def _do_positions():
            await self.ib.reqPositionsAsync()
            return self.ib.positions()

        positions = _IBLoopThread.run(_do_positions(), timeout=15)
        return [{
            "symbol": p.contract.symbol,
            "qty": p.position,
            "avg_cost": round(p.avgCost, 2),
        } for p in positions]

    def get_account_summary(self) -> Dict:
        if not self.connected or not self.ib:
            raise ConnectionError("No conectado a IBKR.")

        wanted = ("NetLiquidation", "TotalCashValue", "BuyingPower", "GrossPositionValue")

        async def _do_summary():
            vals = await self.ib.accountSummaryAsync()
            return {v.tag: v.value for v in vals if v.tag in wanted}

        return _IBLoopThread.run(_do_summary(), timeout=15)

    # ================= ÓRDENES MANUALES =================
    # Solo se llaman desde un botón del dashboard, tras confirmación explícita
    # del usuario. Nunca desde código de análisis/scoring.

    def place_market_order(self, ticker: str, action: str, qty: int) -> Dict:
        if not self.connected or not self.ib:
            raise ConnectionError("No conectado a IBKR.")

        async def _do_order():
            contract = Stock(ticker.upper(), 'SMART', 'USD')
            await self.ib.qualifyContractsAsync(contract)
            order = MarketOrder(action.upper(), qty)
            trade = self.ib.placeOrder(contract, order)
            await asyncio.sleep(1)
            return {"status": trade.orderStatus.status, "order_id": trade.order.orderId}

        return _IBLoopThread.run(_do_order(), timeout=20)

    def place_limit_order(self, ticker: str, action: str, qty: int, limit_price: float) -> Dict:
        if not self.connected or not self.ib:
            raise ConnectionError("No conectado a IBKR.")

        async def _do_order():
            contract = Stock(ticker.upper(), 'SMART', 'USD')
            await self.ib.qualifyContractsAsync(contract)
            order = LimitOrder(action.upper(), qty, limit_price)
            trade = self.ib.placeOrder(contract, order)
            await asyncio.sleep(1)
            return {"status": trade.orderStatus.status, "order_id": trade.order.orderId}

        return _IBLoopThread.run(_do_order(), timeout=20)
