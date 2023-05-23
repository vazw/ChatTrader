import asyncio  # pyright: ignore # noqa:
from datetime import datetime
from time import time
import ccxt.async_support as ccxt
import pandas as pd

from .AppData import lastUpdate, candle_ohlc, timer, retry, POSITION_COLLUMN
from .AppData.Appdata import AppConfig, bot_setting

barsC = 1502


def callbackRate(data, direction):
    m = len(data.index)
    close = data["close"][m - 1]
    highest = data["highest"][m - 1]
    lowest = data["lowest"][m - 1]
    try:
        if direction:
            rate = round((100 - (lowest / close * 100)), 1)
        else:
            rate = round((100 - (close / highest * 100)), 1)
        if rate > 5.0:
            return 5.0
        elif rate < 1.0:
            return 1.0
        else:
            return rate
    except Exception as e:
        lastUpdate.status = f"callbackRate is error : {e}"
        return 2.5


def get_order_id() -> str:
    """ """
    id = datetime.now().isoformat()
    return f"vxma_{id}"


# TP with Risk:Reward
def RRTP(df, direction, step, price, TPRR1, TPRR2):
    m = len(df.index)
    if direction:
        low = float(df["lowest"][m - 1])
        if step == 1:
            return price * (1 + ((price - low) / price) * float(TPRR1))
        if step == 2:
            return price * (1 + ((price - low) / price) * float(TPRR2))
    else:
        high = float(df["highest"][m - 1])
        if step == 1:
            return price * (1 - ((high - price) / price) * float(TPRR1))
        if step == 2:
            return price * (1 - ((high - price) / price) * float(TPRR2))


class Binance:
    """Binance singleton instance"""

    def __init__(self, api: str = None, sapi: str = None):
        self.exchange = None
        self.test_api = api
        self.test_sapi = sapi
        self.balance = ""
        self.fiat_balance = ""
        self.update_time = 0
        self.position_data = pd.DataFrame()

    async def connect(self) -> None:
        if self.test_api is not None:
            BNBCZ = {
                "apiKey": self.test_api,
                "secret": self.test_sapi,
                "options": {"defaultType": "future"},
                "enableRateLimit": True,
                "adjustForTimeDifference": True,
            }
            exchange = ccxt.binance(BNBCZ)
            self.exchange = exchange
        else:
            config = AppConfig()
            exchange = ccxt.binance(config.BNBCZ)
            self.exchange = exchange

    async def connect_loads(self) -> None:
        await self.exchange.load_markets(reload=True)

    async def get_exchange(self) -> ccxt.binance:
        if self.exchange is None:
            await self.connect()
            return self.exchange
        else:
            return self.exchange

    async def disconnect(self) -> None:
        if self.exchange is not None:
            await self.exchange.close()
            self.exchange = None

    @retry(5, lambda e: print(f"ERROR in update_balance: {e}"))
    async def update_balance(self, force: bool = False):
        if time() - self.update_time > 600 or force:
            exchange = await self.get_exchange()
            balance = await exchange.fetch_balance()
            self.update_time = time()
            self.balance = balance
            self.fiat_balance = {x: y for x, y in balance.items() if "USD" in x[-4:]}
            positions = self.balance["info"]["positions"]
            status = pd.DataFrame(
                [
                    position
                    for position in positions
                    if float(position["positionAmt"]) != 0
                ],
                columns=POSITION_COLLUMN,
            )
            status["unrealizedProfit"] = (
                (status["unrealizedProfit"]).astype("float64").round(3)
            )

            status["initialMargin"] = (
                (status["initialMargin"]).astype("float64").round(3)
            )
            self.position_data = status

    @retry(10, lambda e: print(f"ERROR in update_balance: {e}"))
    async def get_bidask(self, symbol, bidask="ask"):
        exchange = await self.get_exchange()
        info = await exchange.fetch_bids_asks([symbol])
        return float(next(y[bidask] for x, y in info.items()))  # pyright: ignore

    async def get_symbol(self):
        """
        get top 10 volume symbol of the day
        """
        symbolist = bot_setting()
        lastUpdate.status = "fecthing Symbol of Top 10 Volume..."
        exchange = await self.get_exchange()
        try:
            market = await exchange.fetch_tickers(params={"type": "future"})
        except Exception as e:
            print(f"{lastUpdate.status}\n{e}")
            market = await exchange.fetch_tickers(params={"type": "future"})
        symbols = pd.DataFrame([y for x, y in market.items() if "USD" in x[-4:]])
        symbols = symbols.sort_values(by=["quoteVolume"], ascending=False)
        symbols = symbols.head(10)
        newsym = [symbol for symbol in symbols["symbol"]]
        if symbolist is not None and len(symbolist.index) > 0:
            for i in range(len(symbolist.index)):
                newsym.append(symbolist["symbol"][i])
        newsym = list(dict.fromkeys(newsym))
        print(f"Interested : {newsym}")
        return newsym

    async def getAllsymbol(self):
        """
        Get all symbols
        """
        exchange = await self.get_exchange()
        try:
            market = await exchange.fetch_tickers(params={"type": "future"})
        except Exception as e:
            print(f"{lastUpdate.status}\n{e}")
            market = await exchange.fetch_tickers(params={"type": "future"})
        symbols = pd.DataFrame([y for x, y in market.items() if "USD" in x[-4:]])
        symbols = symbols.sort_values(by=["quoteVolume"], ascending=False)
        return [symbol for symbol in symbols["symbol"]]

    @retry(10, lambda e: print(f"ERROR in update_balance: {e}"))
    async def fetching_candle_ohlc(self, symbol, timeframe, limits):
        exchange = await self.get_exchange()
        try:
            bars = await exchange.fetch_ohlcv(
                symbol, timeframe=timeframe, since=None, limit=limits
            )
            return bars
        except ccxt.errors.BadSymbol as e:
            print(f"No symbols skip : {e}")
            return None

    async def fetchbars(self, symbol, timeframe) -> None:
        """
        get candle from exchange and update them to ram
        """
        if (
            f"{symbol}_{timeframe}" not in candle_ohlc.keys()
            or candle_ohlc[f"{symbol}_{timeframe}"]["candle"] is None
        ):
            bars = await self.fetching_candle_ohlc(symbol, timeframe, barsC)
            if bars is None:
                return
            df = pd.DataFrame(
                bars[:-1],
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )
            if timer.get_time and timeframe == timer.min_timeframe:
                timer.last_closed = int(df["timestamp"][len(df.index) - 1] / 1000)
                timer.get_time = False

            closed_time = int(df["timestamp"][len(df.index) - 1] / 1000)
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).map(
                lambda x: x.tz_convert("Asia/Bangkok")
            )
            df = df.set_index("timestamp")
            candle_ohlc.update(
                {
                    f"{symbol}_{timeframe}": {
                        "candle": df,
                        "cTime": closed_time,
                    }
                }
            )
        else:
            bars = await self.fetching_candle_ohlc(symbol, timeframe, 5)
            df = pd.DataFrame(
                bars[:-1],
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )
            if bars is None:
                return
            if timer.get_time and timeframe == timer.min_timeframe:
                timer.last_closed = int(df["timestamp"][len(df.index) - 1] / 1000)
                timer.get_time = False

            closed_time = int(df["timestamp"][len(df.index) - 1] / 1000)
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).map(
                lambda x: x.tz_convert("Asia/Bangkok")
            )
            df = df.set_index("timestamp")
            df = pd.concat(
                [candle_ohlc[f"{symbol}_{timeframe}"]["candle"], df],
                ignore_index=False,
            )
            df = df[~df.index.duplicated(keep="last")].tail(barsC)
            candle_ohlc[f"{symbol}_{timeframe}"]["candle"] = df
            candle_ohlc[f"{symbol}_{timeframe}"]["cTime"] = closed_time

    # set leverage pass
    async def setleverage(self, symbol, lev):
        exchange = await self.get_exchange()
        try:
            await exchange.set_leverage(lev, symbol)
            return lev
        except Exception as e:
            print(f"{lastUpdate.status}\n{e}")
            lever = await exchange.fetch_positions_risk([symbol])
            lev = max(
                [
                    y["leverage"]
                    for x, y in enumerate(lever)  # pyright: ignore
                    if y["info"]["symbol"] == symbol or y["symbol"] == symbol
                ]
            )
            await exchange.set_leverage(int(lev), symbol)
            return round(int(lev), 0)

    def RR1(self, stop, side, price, symbol, exchange):
        if side:
            target = price * (1 + ((price - float(stop)) / price) * 1)
            return exchange.price_to_precision(symbol, target)
        elif not side:
            target = price * (1 - ((float(stop) - price) / price) * 1)
            return exchange.price_to_precision(symbol, target)
        else:
            return None

    async def get_tp_sl_price(self, symbol: str = "BTCUSDT", side: str = "BOTH"):
        slId = 0
        tpId = 0
        slPrice = 0.0
        tpPrice = 0.0
        exchange = await self.get_exchange()
        order_list = await exchange.fetch_orders(symbol, limit=10)
        symbol_order = pd.DataFrame(
            [
                order["info"]
                for order in order_list
                if order["info"]["status"] == "NEW"
                and order["info"]["positionSide"] == side
            ]
        )
        sl_price = (
            symbol_order.loc[symbol_order["origType"] == "STOP_MARKET"]
            .copy()
            .reset_index()
        )
        tp_price = (
            symbol_order.loc[symbol_order["origType"] == "TAKE_PROFIT_MARKET"]
            .copy()
            .reset_index()
        )
        if len(sl_price.index) > 0:
            slId = sl_price["orderId"][0]
            slPrice = float(sl_price["stopPrice"][0])
        if len(tp_price.index) > 0:
            tpId = tp_price["orderId"][0]
            tpPrice = float(tp_price["stopPrice"][0])
        return {
            "sl_id": slId,
            "sl_price": slPrice,
            "tp_id": tpId,
            "tp_price": tpPrice,
        }

    async def cancel_order(self, symbol: str = "BTCUSDT", order_id: str = "0"):
        exchange = await self.get_exchange()
        await exchange.cancel_order(
            order_id,
            symbol,
        )


binance_i = Binance()
