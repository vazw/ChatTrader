import asyncio  # pyright: ignore # noqa:
from datetime import datetime
import ccxt.async_support as ccxt
import pandas as pd

from .AppData import (
    currentMode,
    lastUpdate,
    candle_ohlc,
    timer,
    notify_history,
)
from .AppData.Appdata import (
    AppConfig,
    bot_setting,
    candle,
    # notify_send,
    write_trade_record,
    write_tp_record,
    edit_trade_record,
    edit_all_trade_record,
    read_one_open_trade_record,
)

barsC = 1502


class AccountBalance:
    """docstring for AccountBalance."""

    def __init__(self):
        self.balance = ""
        self.fiat_balance = ""

    async def update_balance(self):
        exchange = await binance_i.get_exchange()
        try:
            balance = await exchange.fetch_balance()
            self.balance = balance
            self.fiat_balance = {x: y for x, y in balance.items() if "USD" in x[-4:]}
        except Exception as e:
            lastUpdate.status = f"{e}"
            balance = await exchange.fetch_balance()
            self.balance = balance
            self.fiat_balance = {x: y for x, y in balance.items() if "USD" in x[-4:]}


account_balance = AccountBalance()


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

    def __init__(self):
        self.exchange = None

    async def connect(self) -> None:
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


binance_i = Binance()


async def get_bidask(symbol, exchange, bidask="ask"):
    try:
        info = await exchange.fetch_bids_asks([symbol])
        return float(next(y[bidask] for x, y in info.items()))  # pyright: ignore
    except Exception:
        return await get_bidask(symbol, exchange, bidask)


async def get_symbol():
    """
    get top 10 volume symbol of the day
    """
    symbolist = bot_setting()
    lastUpdate.status = "fecthing Symbol of Top 10 Volume..."
    exchange = await binance_i.get_exchange()
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


async def getAllsymbol():
    """
    Get all symbols
    """
    exchange = await binance_i.get_exchange()
    try:
        market = await exchange.fetch_tickers(params={"type": "future"})
    except Exception as e:
        print(f"{lastUpdate.status}\n{e}")
        market = await exchange.fetch_tickers(params={"type": "future"})
    symbols = pd.DataFrame([y for x, y in market.items() if "USD" in x[-4:]])
    symbols = symbols.sort_values(by=["quoteVolume"], ascending=False)
    return [symbol for symbol in symbols["symbol"]]


async def fetching_candle_ohlc(symbol, timeframe, limits):
    exchange = await binance_i.get_exchange()
    try:
        bars = await exchange.fetch_ohlcv(
            symbol, timeframe=timeframe, since=None, limit=limits
        )
        return bars
    except ccxt.errors.BadSymbol as e:
        print(f"No symbols skip : {e}")
        return None
    except Exception as e:
        print(f"failed to fetching_candle_ohlc : {e}")
        return await fetching_candle_ohlc(symbol, timeframe, limits)


async def fetchbars(symbol, timeframe) -> None:
    """
    get candle from exchange and update them to ram
    """
    if (
        f"{symbol}_{timeframe}" not in candle_ohlc.keys()
        or candle_ohlc[f"{symbol}_{timeframe}"]["candle"] is None
    ):
        bars = await fetching_candle_ohlc(symbol, timeframe, barsC)
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
        bars = await fetching_candle_ohlc(symbol, timeframe, 5)
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
async def setleverage(symbol, lev, exchange):
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


def RR1(stop, side, price, symbol, exchange):
    if side:
        target = price * (1 + ((price - float(stop)) / price) * 1)
        return exchange.price_to_precision(symbol, target)
    elif not side:
        target = price * (1 - ((float(stop) - price) / price) * 1)
        return exchange.price_to_precision(symbol, target)
    else:
        return None


async def TailingLongOrder(df, symbol, exchange, ask, amount, low, side):
    try:
        orderid = get_order_id()
        triggerPrice = RR1(low, True, ask, symbol, exchange)
        if triggerPrice is None:
            return
        callbackrate = callbackRate(df, True)
        if currentMode.dualSidePosition:
            ordertailingSL = await exchange.create_order(
                symbol,
                "TRAILING_STOP_MARKET",
                "sell",
                amount,
                params={
                    "activationPrice": triggerPrice,
                    "callbackRate": callbackrate,
                    "positionSide": side,
                    "newClientOrderId": orderid,
                },
            )
        else:
            ordertailingSL = await exchange.create_order(
                symbol,
                "TRAILING_STOP_MARKET",
                "sell",
                amount,
                params={
                    "activationPrice": triggerPrice,
                    "callbackRate": callbackrate,
                    "positionSide": side,
                    "newClientOrderId": orderid,
                },
            )
        print(ordertailingSL)
        msg2 = (
            "BINANCE:"
            + f"\nCoin        : {symbol}"
            + "\nStatus      : Tailing-StopLoss"
            + f"\nAmount      : {amount}"
            + f"\nCallbackRate: {callbackrate}%"
            + f"\ntriggerPrice: {triggerPrice}"
        )
        # notify_send(msg2)
    except Exception as e:
        print(f"{lastUpdate.status}\n{e}")
        # notify_send(
        #     f"เกิดความผิดพลาดในการเข้า Order : Tailing Stop\n{lastUpdate.status}\n{e}"
        # )


async def TailingShortOrder(df, symbol, exchange, bid, amount, high, Sside):
    try:
        orderid = get_order_id()
        triggerPrice = RR1(high, False, bid, symbol, exchange)
        if triggerPrice is None:
            return
        callbackrate = callbackRate(df, False)
        if currentMode.dualSidePosition:
            ordertailingSL = await exchange.create_order(
                symbol,
                "TRAILING_STOP_MARKET",
                "buy",
                amount,
                params={
                    "activationPrice": triggerPrice,
                    "callbackRate": callbackrate,
                    "positionSide": Sside,
                    "newClientOrderId": orderid,
                },
            )
        else:
            ordertailingSL = await exchange.create_order(
                symbol,
                "TRAILING_STOP_MARKET",
                "buy",
                amount,
                params={
                    "activationPrice": triggerPrice,
                    "callbackRate": callbackrate,
                    "reduceOnly": True,
                    "positionSide": Sside,
                    "newClientOrderId": orderid,
                },
            )
        print(ordertailingSL)
        msg2 = (
            "BINANCE:"
            + f"\nCoin        : {symbol}"
            + "\nStatus      : Tailing-StopLoss"
            + f"\nAmount      : {amount}"
            + f"\nCallbackRate: {callbackrate}%"
            + f"\ntriggerPrice: {triggerPrice}"
        )
        # notify_send(msg2)
    except Exception as e:
        print(f"{lastUpdate.status}\n{e}")
        # notify_send(
        #     f"เกิดความผิดพลาดในการเข้า Order : Tailing Stop\n{lastUpdate.status}\n{e}"
        # )


async def USESLSHORT(symbol, exchange, amount, high, Sside):
    try:
        orderid = get_order_id()
        if currentMode.dualSidePosition:
            orderSL = await exchange.create_order(
                symbol,
                "stop_market",
                "buy",
                amount,
                params={
                    "stopPrice": float(high),
                    "positionSide": Sside,
                    "newClientOrderId": orderid,
                },
            )
            print(orderSL)
        else:
            orderSL = await exchange.create_order(
                symbol,
                "stop",
                "buy",
                amount,
                float(high),
                params={
                    "stopPrice": float(high),
                    "triggerPrice": float(high),
                    "reduceOnly": True,
                    "positionSide": Sside,
                    "newClientOrderId": orderid,
                },
            )
        return high
    except Exception as e:
        print(f"{lastUpdate.status}\n{e}")
        # notify_send(
        #     "เกิดเตุการณืไม่คาดฝัน Order Stop Loss"
        #     + f"ทำรายการไม่สำเร็จ {lastUpdate.status}\n{e}"
        # )
        return 0.0


async def USESLLONG(symbol, exchange: ccxt.binance, amount, low, side):
    try:
        orderid = get_order_id()
        if currentMode.dualSidePosition:
            orderSL = await exchange.create_order(
                symbol,
                "stop_market",
                "sell",
                amount,
                params={
                    "stopPrice": float(low),
                    "positionSide": side,
                    "newClientOrderId": orderid,
                },
            )
        else:
            orderSL = await exchange.create_order(
                symbol,
                "stop",
                "sell",
                amount,
                float(low),
                params={
                    "stopPrice": float(low),
                    "triggerPrice": float(low),
                    "reduceOnly": True,
                    "positionSide": side,
                    "newClientOrderId": orderid,
                },
            )
        print(orderSL)
        return low
    except Exception as e:
        print(f"{lastUpdate.status}\n{e}")
        # notify_send(
        #     f"เกิดเตุการณืไม่คาดฝัน OrderSL ทำรายการไม่สำเร็จ\n{lastUpdate.status}\n{e}"
        # )
        return 0.0


async def USETPLONG(
    symbol, df, exchange, ask, TPRR1, TPRR2, Lside, amttp1, amttp2, USETP2
):
    try:
        stop_price = exchange.price_to_precision(
            symbol, RRTP(df, True, 1, ask, TPRR1, TPRR2)
        )
        orderid = get_order_id()
        orderTP = await exchange.create_order(
            symbol,
            "TAKE_PROFIT_MARKET",
            "sell",
            amttp1,
            stop_price,
            params={
                "stopPrice": stop_price,
                "triggerPrice": stop_price,
                "positionSide": Lside,
                "newClientOrderId": orderid,
            },
        )
        print(orderTP)
        if USETP2:
            triggerPrice = exchange.price_to_precision(
                symbol, RRTP(df, True, 2, ask, TPRR1, TPRR2)
            )
            orderid = get_order_id()
            orderTP2 = await exchange.create_order(
                symbol,
                "TAKE_PROFIT_MARKET",
                "sell",
                amttp2,
                triggerPrice,
                params={
                    "stopPrice": triggerPrice,
                    "triggerPrice": triggerPrice,
                    "positionSide": Lside,
                    "newClientOrderId": orderid,
                },
            )
            print(orderTP2)
            return [stop_price, triggerPrice]
        return [stop_price]
    except Exception as e:
        print(f"{lastUpdate.status}\n{e}")
        # notify_send(
        #     f"เกิดเตุการณืไม่คาดฝัน OrderTP ทำรายการไม่สำเร็จ\n{lastUpdate.status}\n{e}"
        # )
        return None


# Position Sizing
def buysize(df, balance, symbol, exchange, RISK, min_amount):
    last = len(df.index) - 1
    quote = symbol[-4:]
    freeusd = float(balance["free"][quote])
    low = float(df["lowest"][last])
    if RISK[0] == "$":
        risk = float(RISK[1 : len(RISK)])
    elif RISK[0] == "%":
        percent = float(RISK[1 : len(RISK)])
        risk = (percent / 100) * freeusd
    else:
        risk = float(RISK)
    amount = abs(risk / (df["close"][last] - low))
    if amount < min_amount:
        # notify_send(
        #     f"ใช้ Size ขั้นต่ำสำหรับ {symbol}\nโปรดตรวจสอบ SL ด้วยตนเองอีกครั้ง\n"
        #     + f"Size เดิม : {amount}\nSize ใหม่ : {min_amount}"
        # )
        amount = min_amount
    lot = exchange.amount_to_precision(symbol, amount)
    return float(lot)


def sellsize(df, balance, symbol, exchange, RISK, min_amount):
    last = len(df.index) - 1
    quote = symbol[-4:]
    freeusd = float(balance["free"][quote])
    high = float(df["highest"][last])
    if RISK[0] == "$":
        risk = float(RISK[1 : len(RISK)])
    elif RISK[0] == "%":
        percent = float(RISK[1 : len(RISK)])
        risk = (percent / 100) * freeusd
    else:
        risk = float(RISK)
    amount = abs(risk / (high - df["close"][last]))
    if amount < min_amount:
        # notify_send(
        #     f"ใช้ Size ขั้นต่ำสำหรับ {symbol}\nโปรดตรวจสอบ SL ด้วยตนเองอีกครั้ง\n"
        #     + f"Size เดิม : {amount}\nSize ใหม่ : {min_amount}"
        # )
        amount = min_amount
    lot = exchange.amount_to_precision(symbol, amount)
    return float(lot)


# OpenLong=Buy
async def OpenLong(
    df, balance, risk_manage, Lside, min_balance, tf, clearorder: bool = True
):
    exchange = await binance_i.get_exchange()
    await binance_i.connect_loads()
    try:
        if clearorder:
            await exchange.cancel_all_orders(risk_manage["symbol"])
        markets = await exchange.fetchMarkets()
        min_amount = float(
            (
                data["limits"]["amount"]["min"]
                for data in markets
                if data["symbol"] == risk_manage["symbol"]
            ).__next__()
        )
        ask = await get_bidask(risk_manage["symbol"], exchange, "ask")
        if min_amount * ask < 5.0:
            min_amount = 6.0 / ask
        amount = buysize(
            df,
            balance,
            risk_manage["symbol"],
            exchange,
            risk_manage["risk_size"],
            min_amount,
        )
        leve = await setleverage(
            risk_manage["symbol"], risk_manage["leverage"], exchange
        )
        if amount * ask > risk_manage["max_size"] * int(leve):
            new_lots = risk_manage["max_size"] * int(leve) / ask
            if new_lots < min_amount:
                # notify_send(
                #     f"Risk Size ใหญ่เกินไป ใช้ Size ขั้นต่ำสำหรับ {risk_manage['symbol']}"  # noqa:
                #     + "\nโปรดตรวจสอบ SL ด้วยตนเองอีกครั้ง"
                #     + f"Size เดิม : {new_lots}Size ใหม่ : {min_amount}"
                # )
                new_lots = min_amount
            amount = float(
                exchange.amount_to_precision(risk_manage["symbol"], new_lots)
            )
        free = float(risk_manage["free_balance"])
        amttp1 = amount * (risk_manage["tp_percent"] / 100)
        amttp2 = amount * (risk_manage["tp_percent_2"] / 100)
        low = df["lowest"][len(df.index) - 1]
        quote = risk_manage["quote"]
        if free > min_balance:
            try:
                orderid = get_order_id()
                order = await exchange.create_market_order(
                    risk_manage["symbol"],
                    "buy",
                    amount,
                    params={
                        "positionSide": Lside,
                        "newClientOrderId": orderid,
                    },
                )
                print(order)
                margin = ask * amount / int(leve)
                total = float(balance["total"][quote])
            except ccxt.InsufficientFunds as e:
                # notify_send(e)
                return
            if risk_manage["use_tp_1"]:
                tp12 = await USETPLONG(
                    risk_manage["symbol"],
                    df,
                    exchange,
                    ask,
                    risk_manage["risk_reward_1"],
                    risk_manage["risk_reward_2"],
                    Lside,
                    amttp1,
                    amttp2,
                    risk_manage["use_tp_2"],
                )
            if risk_manage["use_sl"]:
                slprice = await USESLLONG(
                    risk_manage["symbol"],
                    exchange,
                    amount,
                    low,
                    Lside,
                )
            msg = (
                "BINANCE:"
                + f"\nCoin        : {risk_manage['symbol']}"
                + "\nStatus      : OpenLong[BUY]"
                + f"\nAmount      : {amount}({round((amount * ask), 2)}{quote})"
                + f"\nPrice       : {ask}{quote}"
                + f"\nmargin      : {round(margin, 2)}{quote}"
                + f"\nBalance     : {round(total, 2)}{quote}"
                + f"\nTP Price    : {tp12}{quote}"
                + f"\nSL Price    : {slprice}{quote}"
            )
            # notify_send(msg)
            if risk_manage["use_tailing"]:
                await TailingLongOrder(
                    df,
                    risk_manage["symbol"],
                    exchange,
                    ask,
                    amount,
                    low,
                    Lside,
                )
        else:
            msg = (
                f"MARGIN-CALL!!!\nยอดเงินต่ำกว่าที่กำหนดไว้ :{min_balance}USD"
                + f"\nยอดปัจจุบัน  {round(free, 2)}"
                + " USD\nบอทจะทำการยกเลิกการเข้า Position ทั้งหมด"
            )
            # notify_send(msg)
            return
        time_now = lastUpdate.candle
        write_trade_record(
            time_now,
            risk_manage["symbol"],
            tf,
            amount,
            ask,
            "Long",
            tp12,
            slprice,
        )
        candle(df, risk_manage["symbol"], f"{tf} {time_now}")
        return
    except Exception as e:
        print(f"{lastUpdate.status}\n{e}")
        # notify_send(
        #     f"เกิดความผิดพลาดในการเข้า Order : OpenLong\n{lastUpdate.status}\n{e}"
        # )
        return


async def USETPSHORT(
    symbol, df, exchange, bid, TPRR1, TPRR2, Sside, amttp1, amttp2, USETP2
):
    try:
        triggerPrice = exchange.price_to_precision(
            symbol, RRTP(df, False, 1, bid, TPRR1, TPRR2)
        )
        orderid = get_order_id()
        orderTP = await exchange.create_order(
            symbol,
            "TAKE_PROFIT_MARKET",
            "buy",
            amttp1,
            triggerPrice,
            params={
                "stopPrice": triggerPrice,
                "triggerPrice": triggerPrice,
                "positionSide": Sside,
                "newClientOrderId": orderid,
            },
        )
        print(orderTP)
        if USETP2:
            triggerPrice2 = exchange.price_to_precision(
                symbol, RRTP(df, False, 2, bid, TPRR1, TPRR2)
            )
            orderid = get_order_id()
            orderTP2 = await exchange.create_order(
                symbol,
                "TAKE_PROFIT_MARKET",
                "buy",
                amttp2,
                triggerPrice,
                params={
                    "stopPrice": triggerPrice,
                    "triggerPrice": triggerPrice,
                    "positionSide": Sside,
                    "newClientOrderId": orderid,
                },
            )
            print(orderTP2)
            return [triggerPrice, triggerPrice2]
        return [triggerPrice]
    except Exception as e:
        print(f"{lastUpdate.status}\n{e}")
        # notify_send(
        #     f"เกิดเตุการณืไม่คาดฝัน Order TP  ทำรายการไม่สำเร็จ{lastUpdate.status}\n{e}"
        # )
        return None


# OpenShort=Sell
async def OpenShort(
    df, balance, risk_manage, Sside, min_balance, tf, clearorder: bool = True
):
    exchange = await binance_i.get_exchange()
    await binance_i.connect_loads()
    try:
        if clearorder:
            await exchange.cancel_all_orders(risk_manage["symbol"])
        markets = await exchange.fetchMarkets()
        min_amount = float(
            (
                data["limits"]["amount"]["min"]
                for data in markets
                if data["symbol"] == risk_manage["symbol"]
            ).__next__()
        )
        bid = await get_bidask(risk_manage["symbol"], exchange, "bid")
        if min_amount * bid < 5.0:
            min_amount = 6.0 / bid
        amount = sellsize(
            df,
            balance,
            risk_manage["symbol"],
            exchange,
            risk_manage["risk_size"],
            min_amount,
        )
        leve = await setleverage(
            risk_manage["symbol"], risk_manage["leverage"], exchange
        )
        if amount * bid > risk_manage["max_size"] * int(leve):
            new_lots = risk_manage["max_size"] * int(leve) / bid
            if new_lots < min_amount:
                # notify_send(
                #     f"Risk Size ใหญ่เกินไป ใช้ Size ขั้นต่ำสำหรับ {risk_manage['symbol']}"  # noqa:
                #     + "\nโปรดตรวจสอบ SL ด้วยตนเองอีกครั้ง"
                #     + f"Size เดิม : {new_lots}Size ใหม่ : {min_amount}"
                # )
                new_lots = min_amount
            amount = float(
                exchange.amount_to_precision(risk_manage["symbol"], new_lots)
            )
        free = float(risk_manage["free_balance"])
        amttp1 = amount * (risk_manage["tp_percent"] / 100)
        amttp2 = amount * (risk_manage["tp_percent_2"] / 100)
        high = df["highest"][len(df.index) - 1]
        quote = risk_manage["quote"]
        if free > min_balance:
            try:
                orderid = get_order_id()
                order = await exchange.create_market_order(
                    risk_manage["symbol"],
                    "sell",
                    amount,
                    params={
                        "positionSide": Sside,
                        "newClientOrderId": orderid,
                    },
                )
                print(order)
                margin = bid * amount / int(leve)
                total = float(balance["total"][quote])
            except ccxt.InsufficientFunds as e:
                # notify_send(e)
                return
            if risk_manage["use_sl"]:
                slprice = await USESLSHORT(
                    risk_manage["symbol"],
                    exchange,
                    amount,
                    high,
                    Sside,
                )
            if risk_manage["use_tp_1"]:
                tp12 = await USETPSHORT(
                    risk_manage["symbol"],
                    df,
                    exchange,
                    bid,
                    risk_manage["risk_reward_1"],
                    risk_manage["risk_reward_2"],
                    Sside,
                    amttp1,
                    amttp2,
                    risk_manage["use_tp_2"],
                )
            msg = (
                "BINANCE:"
                + f"\nCoin        : {risk_manage['symbol']}"
                + "\nStatus      : OpenShort[SELL]"
                + f"\nAmount      : {amount}({round((amount * bid), 2)}{quote})"
                + f"\nPrice       : {bid}{quote}"
                + f"\nmargin      : {round(margin, 2)}{quote}"
                + f"\nBalance     : {round(total, 2)}{quote}"
                + f"\nTP Price    : {tp12}{quote}"
                + f"\nSL Price    : {slprice}{quote}"
            )
            # notify_send(msg)
            if risk_manage["use_tailing"]:
                await TailingShortOrder(
                    df,
                    risk_manage["symbol"],
                    exchange,
                    bid,
                    amount,
                    high,
                    Sside,
                )
        else:
            msg = (
                f"MARGIN-CALL!!!\nยอดเงินต่ำกว่าที่กำหนดไว้ :{min_balance}USD"
                + f"\nยอดปัจจุบัน  {round(free, 2)}"
                + " USD\nบอทจะทำการยกเลิกการเข้า Position ทั้งหมด"
            )
            # notify_send(msg)
            return
        time_now = lastUpdate.candle
        write_trade_record(
            time_now,
            risk_manage["symbol"],
            tf,
            amount,
            bid,
            "Short",
            tp12,
            slprice,
        )
        candle(df, risk_manage["symbol"], f"{tf} {time_now}")
        return
    except Exception as e:
        print(f"{lastUpdate.status}\n{e}")
        # notify_send(
        #     f"เกิดความผิดพลาดในการเข้า Order : OpenShort\n{lastUpdate.status}\n{e}"
        # )
        return


# CloseLong=Sell
async def CloseLong(df, balance, symbol, amt, pnl, Lside, tf, closeall: bool = False):
    exchange = await binance_i.get_exchange()
    await binance_i.connect_loads()
    try:
        amount = abs(amt)
        upnl = pnl
        quote = symbol[-4:]
        bid = await get_bidask(symbol, exchange, "bid")
        orderid = get_order_id()
        try:
            order = await exchange.create_market_order(
                symbol,
                "sell",
                amount,
                params={
                    "positionSide": Lside,
                    "newClientOrderId": orderid,
                },
            )
        except Exception as e:
            lastUpdate.status = f"{e}"
            await binance_i.connect_loads()
            order = await exchange.create_market_order(
                symbol,
                "sell",
                amount,
                params={
                    "positionSide": Lside,
                    "newClientOrderId": orderid,
                },
            )
            print(order)
        total = float(balance["total"][quote])
        msg = (
            "BINANCE:\n"
            + f"Coin        : {symbol}\n"
            + "Status      : CloseLong[SELL]\n"
            + f"Amount      : {str(amount)}({round((amount * bid), 2)} {quote})\n"
            + f"Price       : {bid} {quote}\n"
            + f"Realized P/L:  {round(upnl, 2)} {quote}\n"
            + f"Balance     : {round(total, 2)} {quote}"
        )
        # notify_send(msg)
        time_now = lastUpdate.candle
        if closeall:
            edit_all_trade_record(time_now, symbol, "Long", bid)
        else:
            edit_trade_record(time_now, symbol, tf, "Long", bid)

        candle(df, symbol, f"{tf} {time_now}")
        return
    except Exception as e:
        print(f"{lastUpdate.status}\n{e}")
        # notify_send(
        #     f"เกิดความผิดพลาดในการออก Order : CloseLong\n{lastUpdate.status}\n{e}"
        # )
        return


# CloseShort=Buy
async def CloseShort(df, balance, symbol, amt, pnl, Sside, tf, closeall: bool = False):
    exchange = await binance_i.get_exchange()
    await binance_i.connect_loads()
    try:
        amount = abs(amt)
        quote = symbol[-4:]
        orderid = get_order_id()
        upnl = pnl
        ask = await get_bidask(symbol, exchange, "ask")
        try:
            order = await exchange.create_market_order(
                symbol,
                "buy",
                amount,
                params={
                    "positionSide": Sside,
                    "newClientOrderId": orderid,
                },
            )
        except Exception as e:
            print(f"{lastUpdate.status}\n{e}")
            await binance_i.connect_loads()
            order = await exchange.create_market_order(
                symbol,
                "buy",
                amount,
                params={
                    "positionSide": Sside,
                    "newClientOrderId": orderid,
                },
            )
            print(order)
        total = float(balance["total"][quote])
        msg = (
            "BINANCE:\n"
            f"Coin        : {symbol}\n"
            "Status      : CloseShort[BUY]\n"
            f"Amount      : {str(amount)}({round((amount * ask), 2)}{quote})\n"
            f"Price       : {ask} {quote}\n"
            f"Realized P/L:  {round(upnl, 2)}{quote}\n"
            f"Balance     : {round(total, 2)}{quote}"
        )
        # notify_send(msg)
        time_now = lastUpdate.candle
        if closeall:
            edit_all_trade_record(time_now, symbol, "Short", ask)
        else:
            edit_trade_record(time_now, symbol, tf, "Short", ask)
        candle(df, symbol, f"{tf} {time_now}")
        return
    except Exception as e:
        print(f"{lastUpdate.status}\n{e}")
        # notify_send(
        #     f"เกิดความผิดพลาดในการออก Order : CloseShort\n{lastUpdate.status}\n{e}"
        # )
        return


async def get_currentmode():
    exchange = await binance_i.get_exchange()
    try:
        currentMODE = await exchange.fapiPrivate_get_positionside_dual()
    except Exception as e:
        lastUpdate.status = f"{e}"
        await binance_i.connect_loads()
        currentMODE = await exchange.fapiPrivate_get_positionside_dual()
    await binance_i.disconnect()
    currentMode.dualSidePosition = currentMODE["dualSidePosition"]
    if currentMode.dualSidePosition:
        currentMode.Sside = "SHORT"
        currentMode.Lside = "LONG"


async def check_current_position(symbol: str, status: pd.DataFrame) -> dict:
    if "/" in symbol:
        posim = symbol[:-5].replace("/", "")
    else:
        posim = symbol
    if status is None:
        return
    status = status[status["symbol"] == posim]

    if status.empty:
        amt_short = 0.0
        amt_long = 0.0
        upnl_short = 0.0
        upnl_long = 0.0
    elif len(status.index) > 1:
        amt_long = float(
            (
                status["positionAmt"][i]
                for i in status.index
                if status["symbol"][i] == posim and status["positionSide"][i] == "LONG"
            ).__next__()
        )
        amt_short = float(
            (
                status["positionAmt"][i]
                for i in status.index
                if status["symbol"][i] == posim and status["positionSide"][i] == "SHORT"
            ).__next__()
        )
        upnl_long = float(
            (
                status["unrealizedProfit"][i]
                for i in status.index
                if status["symbol"][i] == posim and status["positionSide"][i] == "LONG"
            ).__next__()
        )
        upnl_short = float(
            (
                status["unrealizedProfit"][i]
                for i in status.index
                if status["symbol"][i] == posim and status["positionSide"][i] == "SHORT"
            ).__next__()
        )
    else:
        amt = float(
            (
                status["positionAmt"][i]
                for i in status.index
                if status["symbol"][i] == posim
            ).__next__()
        )
        amt_long = amt if amt > 0 else 0.0
        amt_short = amt if amt < 0 else 0.0
        upnl = float(
            (
                status["unrealizedProfit"][i]
                for i in status.index
                if status["symbol"][i] == posim
            ).__next__()
        )
        upnl_long = upnl if amt != 0 else 0.0
        upnl_short = upnl if amt != 0 else 0.0

    is_in_Long = True if amt_long != 0 else False
    is_in_Short = True if amt_short != 0 else False
    del status
    return {
        "symbol": posim,
        "long": {
            "amount": amt_long,
            "pnl": upnl_long,
            "position": is_in_Long,
        },
        "short": {
            "amount": amt_short,
            "pnl": upnl_short,
            "position": is_in_Short,
        },
    }


async def get_closed_pnl(symbol):
    try:
        exchange = await binance_i.get_exchange()
        closed_pnl = await exchange.fetch_my_trades(symbol, limit=1)
        return closed_pnl[0]
    except Exception:
        return None


async def check_if_closed_position(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    status: pd.DataFrame,
    direction: str = "",
) -> None:
    """
    check if open position still exits
    """
    saved_position = read_one_open_trade_record(symbol, timeframe, direction)
    if saved_position is None:
        del status
        return
    posim = symbol[:-5].replace("/", "")
    last = len(df.index) - 1
    if df["isSL"][last] == 1 and saved_position is not None:
        closed_pnl = await get_closed_pnl(symbol)
        # notify_send(
        #     f"{symbol} {timeframe} {direction} got Stop-Loss!\n"
        #     + f"at {closed_pnl['price']}\nP/L : {closed_pnl['info']['realizedPnl']}"
        # )
        time_now = lastUpdate.candle
        edit_trade_record(
            time_now,
            symbol,
            timeframe,
            direction,
            0.0,
            isSl=True,
        )
        candle(df, symbol, f"{timeframe} {time_now}")
        del status
        return

    ex_position = [
        f"{status['symbol'][i]}"
        for i in status.index
        if status["symbol"][i] == posim
        and (
            status["positionSide"][i] == direction.upper()
            or (
                (status["positionAmt"][i] > 0)
                if direction.upper() == "LONG"
                else (status["positionAmt"][i] < 0)
            )
        )
    ]
    if posim not in ex_position and saved_position is not None:
        closed_pnl = await get_closed_pnl(symbol)
        # notify_send(
        #     f"{symbol} {timeframe} {direction} Being Closed!\n"
        #     + f"at {closed_pnl['price']}\nP/L : {closed_pnl['info']['realizedPnl']}"
        # )
        edit_trade_record(
            lastUpdate.candle,
            symbol,
            timeframe,
            direction,
            closed_pnl["price"],
        )
        del status
        return

    ex_amount = float(
        (
            status["positionAmt"][i]
            for i in status.index
            if status["symbol"][i] == posim
            and (
                status["positionSide"][i] == direction.upper()
                or (
                    (status["positionAmt"][i] > 0)
                    if direction.upper() == "LONG"
                    else (status["positionAmt"][i] < 0)
                )
            )
        ).__next__()
    )
    saved_amount = float(saved_position["Amount"])
    if saved_amount != abs(ex_amount):
        closed_pnl = await get_closed_pnl(symbol)
        # notify_send(
        #     f"{symbol} {timeframe} {direction} Being TP!!\n"
        #     + f"at {closed_pnl['price']}\nP/L : {closed_pnl['info']['realizedPnl']}"
        # )
        write_tp_record(
            lastUpdate.candle,
            symbol,
            timeframe,
            direction,
            closed_pnl["price"],
            saved_amount - abs(ex_amount),
            saved_position,
        )
        del status
        return


def notify_signal(df, risk_manage, mm_permission, signal: str = ""):
    timeframe = risk_manage["timeframe"]
    if f"{risk_manage['symbol']}_{timeframe}" not in notify_history.keys():
        notify_history[f"{risk_manage['symbol']}_{timeframe}"] = 0
    if (
        candle_ohlc[f"{risk_manage['symbol']}_{timeframe}"]["cTime"]
        != notify_history[f"{risk_manage['symbol']}_{timeframe}"]
    ):
        quote = risk_manage["quote"]
        # notify_send(
        #     f"{risk_manage['symbol']} {timeframe}"
        #     + f"\nเกิดสัญญาณ {signal}\nแต่ "
        #     + "Risk Margin รวมสูงเกินไปแล้ว!!"
        #     + f"\nFree Balance : {round(mm_permission['free'],3)} {quote}"
        #     + f"\nMargin รวม  : {round(mm_permission['margin'],3)} $"
        #     + f"\nRisk ทั้งหมด : {round(mm_permission['risk'],3)} $\n"
        #     + f"Risk สูงสุดที่กำหนดไว้ : {round(mm_permission['max_margin'],3)} $",  # noqa:
        #     sticker=17857,
        #     package=1070,
        # )
        # candle(df, risk_manage["symbol"], timeframe)
        notify_history[f"{risk_manage['symbol']}_{timeframe}"] = candle_ohlc[
            f"{risk_manage['symbol']}_{timeframe}"
        ]["cTime"]


async def feed(
    df,
    risk_manage,
    balance,
    status,
    mm_permission,
):
    last = len(df.index) - 1

    current_position, closed = await asyncio.gather(  # pyright: ignore
        check_current_position(risk_manage["symbol"], status.copy()),
        check_if_closed_position(
            df,
            risk_manage["symbol"],
            risk_manage["timeframe"],
            status.copy(),
            "Long" if df["trend"][last - 1] == 1 else "Short",
        ),
    )

    long_record = read_one_open_trade_record(
        risk_manage["symbol"], risk_manage["timeframe"], "Long"
    )
    short_record = read_one_open_trade_record(
        risk_manage["symbol"], risk_manage["timeframe"], "Short"
    )

    if df["BUY"][last] == 1 and long_record is None:
        lastUpdate.status = "changed to Bullish, buy"
        if current_position["short"]["position"]:
            lastUpdate.status = "closeshort"
            await CloseShort(
                df,
                balance,
                risk_manage["symbol"],
                current_position["short"]["amount"],
                current_position["short"]["pnl"],
                currentMode.Sside,
                risk_manage["timeframe"],
                closeall=True,
            )
            await account_balance.update_balance()
            if risk_manage["use_long"]:
                if mm_permission["can_trade"]:
                    await OpenLong(
                        df,
                        balance,
                        risk_manage,
                        currentMode.Lside,
                        mm_permission["min_balance"],
                        risk_manage["timeframe"],
                    )
                    await account_balance.update_balance()
                else:
                    notify_signal(df, risk_manage, mm_permission, "Long")
            else:
                print("No permission for excute order : Do nothing")

        else:
            if risk_manage["use_long"]:
                if mm_permission["can_trade"]:
                    await OpenLong(
                        df,
                        balance,
                        risk_manage,
                        currentMode.Lside,
                        mm_permission["min_balance"],
                        risk_manage["timeframe"],
                    )
                    await account_balance.update_balance()
                else:
                    notify_signal(df, risk_manage, mm_permission, "Long")
            else:
                print("No permission for excute order : Do nothing")

    if df["SELL"][last] == 1 and short_record is None:
        lastUpdate.status = "changed to Bearish, Sell"
        if current_position["long"]["position"]:
            lastUpdate.status = "closelong"
            await CloseLong(
                df,
                balance,
                risk_manage["symbol"],
                current_position["long"]["amount"],
                current_position["long"]["pnl"],
                currentMode.Lside,
                risk_manage["timeframe"],
                closeall=True,
            )
            await account_balance.update_balance()
            if risk_manage["use_short"]:
                if mm_permission["can_trade"]:
                    await OpenShort(
                        df,
                        balance,
                        risk_manage,
                        currentMode.Sside,
                        mm_permission["min_balance"],
                        risk_manage["timeframe"],
                    )
                    await account_balance.update_balance()
                else:
                    notify_signal(df, risk_manage, mm_permission, "Short")
            else:
                print("No permission for excute order : Do nothing")
        else:
            if risk_manage["use_short"]:
                if mm_permission["can_trade"]:
                    await OpenShort(
                        df,
                        balance,
                        risk_manage,
                        currentMode.Sside,
                        mm_permission["min_balance"],
                        risk_manage["timeframe"],
                    )
                    await account_balance.update_balance()
                else:
                    notify_signal(df, risk_manage, mm_permission, "Short")
            else:
                print("No permission for excute order : Do nothing")


async def feed_hedge(
    df,
    df_trend,
    risk_manage,
    balance,
    status: pd.DataFrame,
    mm_permission,
):
    last = len(df.index) - 1

    current_position, closed = await asyncio.gather(  # pyright: ignore
        check_current_position(risk_manage["symbol"], status.copy()),
        check_if_closed_position(
            df,
            risk_manage["symbol"],
            risk_manage["hedge_timeframe"],
            status.copy(),
            "Long" if df["trend"][last - 1] == 1 else "Short",
        ),
    )

    long_record = read_one_open_trade_record(
        risk_manage["symbol"], risk_manage["hedge_timeframe"], "Long"
    )
    short_record = read_one_open_trade_record(
        risk_manage["symbol"], risk_manage["hedge_timeframe"], "Short"
    )

    last_b = len(df_trend.index) - 1

    # Open Long if ther higher trend are bullish
    # but got bearish signal on lower timeframe
    if (
        df["BUY"][last] == 1
        and df_trend["trend"][last_b] == 0
        and current_position["short"]["position"]
        and long_record is None
    ):
        print("hedging changed to Bullish, buy")
        if risk_manage["use_long"]:
            await OpenLong(
                df,
                balance,
                risk_manage,
                currentMode.Lside,
                mm_permission["min_balance"],
                risk_manage["hedge_timeframe"],
                False,
            )
            await account_balance.update_balance()
        else:
            print("No permission for excute order : Do nothing")

    # Close Short if the higher trend are bullish
    # and have a hedging position
    if (
        df["BUY"][last] == 1
        and df_trend["trend"][last_b] == 1
        and current_position["short"]["position"]
        and short_record is not None
    ):
        print("hedging changed to Bullish, closeshort buy")
        await CloseShort(
            df,
            balance,
            risk_manage["symbol"],
            current_position["short"]["amount"],
            current_position["short"]["pnl"],
            currentMode.Sside,
            risk_manage["hedge_timeframe"],
        )
        await account_balance.update_balance()

    # Open Short if the higher trend are bullish
    # but got Sell signal form lower timeframe
    if (
        df["SELL"][last] == 1
        and df_trend["trend"][last_b] == 1
        and current_position["long"]["position"]
        and short_record is None
    ):
        print("hedging changed to Bearish, Sell")
        if risk_manage["use_short"]:
            await OpenShort(
                df,
                balance,
                risk_manage,
                currentMode.Sside,
                mm_permission["min_balance"],
                risk_manage["hedge_timeframe"],
                False,
            )
            await account_balance.update_balance()
        else:
            print("No permission for excute order : Do nothing")

    # Close Long position if the higher timeframe are bearish
    # and have a Hedging position
    if (
        df["SELL"][last] == 1
        and df_trend["trend"][last_b] == 0
        and current_position["long"]["position"]
        and long_record is not None
    ):
        print("hedging changed to Bearish, Sell")
        await CloseLong(
            df,
            balance,
            risk_manage["symbol"],
            current_position["long"]["amount"],
            current_position["long"]["pnl"],
            currentMode.Lside,
            risk_manage["hedge_timeframe"],
        )
        await account_balance.update_balance()
