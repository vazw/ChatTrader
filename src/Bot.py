import asyncio
from datetime import datetime
import time
from uuid import uuid4
import warnings
from tabulate import tabulate
from collections import deque
import pandas as pd
from telegram.ext import ContextTypes
import ccxt.async_support as ccxt

from .AppData import (
    notify_history,
    colorCS,
    lastUpdate,
    timer,
    candle_ohlc,
)
from .AppData.Appdata import (
    AppConfig,
    DefaultRiskTable,
    RiskManageTable,
    PositionMode,
    TATable,
    bot_setting,
    candle,
    clearconsol,
    write_trade_record,
    write_tp_record,
    edit_trade_record,
    edit_all_trade_record,
    read_one_open_trade_record,
)
from .CCXT_Binance import (
    binance_i,
    callbackRate,
    get_order_id,
    RRTP,
)
from .Strategy.Benchmarking import benchmarking as ta_score
from .Strategy.vxma_talib import vxma as ta


bot_name = "VXMA Trading Bot by Vaz.(Version 0.1.6) github.com/vazw/vxma_web"

launch_uid = uuid4()
pd.set_option("display.max_rows", None)
warnings.filterwarnings("ignore")


# Bot setting
insession = dict(name=False, day=False, hour=False)
# STAT setting
barsC = 1502
msg = ""
# timframe dicts and collum
TIMEFRAMES = [
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "2h",
    "4h",
    "6h",
    "8h",
    "12h",
    "1d",
    "3d",
    "1w",
    "1M",
]
statcln = [
    "symbol",
    "entryPrice",
    "positionSide",
    "unrealizedProfit",
    "positionAmt",
    "initialMargin",
    "leverage",
]

TIMEFRAMES_DICT = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "6h": "6h",
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
    "3d": "3d",
    "1w": "1w",
    "1M": "1M",
}

TIMEFRAME_SECONDS = {
    "1m": 60,
    "3m": 60 * 3,
    "5m": 60 * 5,
    "15m": 60 * 15,
    "30m": 60 * 30,
    "1h": 60 * 60,
    "2h": 60 * 60 * 2,
    "4h": 60 * 60 * 4,
    "6h": 60 * 60 * 6,
    "8h": 60 * 60 * 8,
    "12h": 60 * 60 * 12,
    "1d": 60 * 60 * 24,
    "1w": 60 * 60 * 24 * 7,
    "1M": 60 * 60 * 24 * 30,
}


common_names = {
    "symbol": "Symbols",
    "entryPrice": "ราคาเข้า",
    "positionSide": "Side",
    "unrealizedProfit": "u.P/L $",
    "positionAmt": "Amount",
    "initialMargin": "Margin $",
    "leverage": "Leverage",
}


def remove_last_line_from_string(text):
    return text[: text.rfind("\n")]


async def split_list(input_list, chunk_size):
    # Create a deque object from the input list
    deque_obj = deque(input_list)
    # While the deque object is not empty
    while deque_obj:
        # Pop chunk_size elements from the left side of the deque object
        # and append them to the chunk list
        chunk = []
        for _ in range(chunk_size):
            if deque_obj:
                chunk.append(deque_obj.popleft())

        # Yield the chunk
        yield chunk


class BotTrade:
    def __init__(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        chat_id: int = 0,
        status_bot: bool = False,
        status_scan: bool = False,
    ):
        self.status_bot = status_bot
        self.status_scan = status_scan
        self.context = context
        self.chat_id = chat_id
        self.watchlist = []
        self.currentMode = PositionMode()

    def start_bot(self):
        self.status_bot = True

    def stop_bot(self):
        self.status_bot = False

    def enable_scan(self):
        self.status_scan = True

    def disable_scan(self):
        self.status_scan = False

    def update_chat_id(self, chat_id: int):
        self.chat_id = chat_id

    async def run_bot(self):
        print(f"{colorCS.CBOLD}{colorCS.CGREEN}{bot_name}{colorCS.CEND}")
        await self.notify_send("Bot Started")
        while True:
            try:
                if not self.status_bot:
                    return
                await binance_i.update_balance()
                await self.get_currentmode()
                await self.get_waiting_time()
                await self.waiting()
                await asyncio.gather(self.warper_fn())
            except Exception as e:
                print(f"Restarting :{e}")
                lastUpdate.status = "Fallback Mode : Restarting..."
                continue
            finally:
                await binance_i.disconnect()

    async def notify_send(self, message: str):
        return await self.context.bot.send_message(chat_id=self.chat_id, text=message)

    async def notify_send_pic(self, path: str):
        return await self.context.bot.send_photo(chat_id=self.chat_id, photo=path)

    def update_watchlist(self) -> None:
        symbolist = bot_setting()
        self.watchlist = [
            (
                symbolist.index[i],
                symbolist["symbol"][i],
                symbolist["timeframe"][i],
            )
            for i in range(len(symbolist.index))
        ]

    async def update_candle(self) -> None:
        try:
            timenow = time.time()
            update_tasks = [
                asyncio.create_task(binance_i.fetchbars(symbol, tf))
                for symbol, tf in [str(i).split("_") for i in candle_ohlc.keys()]
                if timenow
                > candle_ohlc[f"{symbol}_{tf}"]["cTime"] + TIMEFRAME_SECONDS[tf]
            ]
            if len(update_tasks) > 0:
                async for task in split_list(update_tasks, 10):
                    await asyncio.gather(*task)
        except Exception as e:
            lastUpdate.status = f"{e}"
            print(f"update candle error : {e}")

    async def bot_1(self, symbol, ta_data, tf):
        try:
            if (
                f"{symbol}_{tf}" not in candle_ohlc.keys()
                or candle_ohlc[f"{symbol}_{tf}"]["candle"] is None
            ):
                await binance_i.fetchbars(symbol, tf)
            data1 = candle_ohlc[f"{symbol}_{tf}"]["candle"].copy()
            if data1 is None or len(data1.index) < 100:
                return None
            bot1 = ta(data1, ta_data)
            data1 = bot1.indicator()
            return data1
        except Exception as e:
            lastUpdate.status = f"{e}"
            return self.bot_1(symbol, ta_data, tf)

    async def bot_2(self, symbol, ta_data, tf):
        try:
            if (
                f"{symbol}_{tf}" not in candle_ohlc.keys()
                or candle_ohlc[f"{symbol}_{tf}"]["candle"] is None
            ):
                await binance_i.fetchbars(symbol, tf)
            data2 = candle_ohlc[f"{symbol}_{tf}"]["candle"].copy()
            if data2 is None or len(data2.index) < 100:
                return None
            bot2 = ta(data2, ta_data)
            data2 = bot2.indicator()
            return data2
        except Exception as e:
            lastUpdate.status = f"{e}"
            return self.bot_2(symbol, ta_data, tf)

    async def bot_3(self, symbol, ta_data, tf):
        try:
            if (
                f"{symbol}_{tf}" not in candle_ohlc.keys()
                or candle_ohlc[f"{symbol}_{tf}"]["candle"] is None
            ):
                await binance_i.fetchbars(symbol, tf)
            data3 = candle_ohlc[f"{symbol}_{tf}"]["candle"].copy()
            if data3 is None or len(data3.index) < 100:
                return None
            bot3 = ta(data3, ta_data)
            data3 = bot3.indicator()
            return data3
        except Exception as e:
            lastUpdate.status = f"{e}"
            return self.bot_2(symbol, ta_data, tf)

    async def scaning_method(self, symbol: str, ta_data: TATable, symbols: list):
        try:
            df1, df2, df3 = await asyncio.gather(
                self.bot_1(symbol, ta_data.__dict__, "1d"),
                self.bot_2(symbol, ta_data.__dict__, "6h"),
                self.bot_3(symbol, ta_data.__dict__, "1h"),
            )

            if df1 is not None:
                long_term = ta_score(df1)
                mid_term = ta_score(df2)
                short_term = ta_score(df3)
                long_term_score = long_term.benchmarking()
                mid_term_score = mid_term.benchmarking()
                short_term_score = short_term.benchmarking()
                if (
                    (long_term_score == "Side-Way" and mid_term_score == "Side-Way")
                    or (
                        long_term_score == "Side-Way" and short_term_score == "Side-Way"
                    )
                    or (mid_term_score == "Side-Way" and short_term_score == "Side-Way")
                ):
                    pass
                else:
                    print(f"{symbol} is Trending: {long_term_score}")
                    symbols.append(symbol)
                    lastUpdate.status = f"Added {symbol} to list"

        except Exception as e:
            lastUpdate.status = f"{e}"
            pass

    async def scanSideway(self):
        symbolist = await binance_i.getAllsymbol()
        lastUpdate.status = f"Scanning {len(symbolist)} Symbols"
        ta_data = TATable()
        symbols = []
        tasks = [
            asyncio.create_task(self.scaning_method(symbol, ta_data, symbols))
            for symbol in symbolist
        ]
        async for task in split_list(tasks, 10):
            await asyncio.gather(*task)
        return symbols

    async def get_dailytasks(self):
        daycollum = ["Symbol", "LastPirce", "Long-Term", "Mid-Term", "Short-Term"]
        symbolist = await binance_i.get_symbol()
        ta_data = TATable()
        for symbol in symbolist:
            try:
                df1, df2, df3 = await asyncio.gather(
                    self.bot_1(symbol, ta_data.__dict__, "1d"),
                    self.bot_2(symbol, ta_data.__dict__, "6h"),
                    self.bot_3(symbol, ta_data.__dict__, "1h"),
                )

                # candle(df3, symbol, "1h")
                if df1 is not None:
                    time_now = lastUpdate.candle
                    await self.notify_send_pic(candle(df1, symbol, f"1d {time_now}"))
                    long_term = ta_score(df1)
                    mid_term = ta_score(df2)
                    short_term = ta_score(df3)
                    yield pd.Series(
                        [
                            symbol,
                            df3["close"][len(df3.index) - 1],
                            long_term.benchmarking(),
                            mid_term.benchmarking(),
                            short_term.benchmarking(),
                        ],
                        index=daycollum,
                    )
            except Exception as e:
                lastUpdate.status = f"{e}"
                pass

    async def write_daily_balance(self):
        fiat_balance = binance_i.fiat_balance
        total_balance = fiat_balance["BUSD"]["total"] + fiat_balance["USDT"]["total"]
        local_time = time.ctime(time.time())
        df = pd.DataFrame(
            {
                "DateTime": [local_time],
                "Total": [total_balance],
            }
        )

        # Append the dataframe to the CSV file
        # df.to_csv("balance.csv", index=False, header=True)
        df.to_csv("balance.csv", mode="a", index=False, header=False)

    async def hourly_report(self):
        lastUpdate.status = "Hourly report"
        status = binance_i.position_data
        netunpl = float(
            status["unrealizedProfit"].astype("float64").sum()
            if not status.empty
            else 0.0
        )
        fiat_balance = binance_i.fiat_balance
        lastUpdate.balance = fiat_balance
        msg = (
            "Balance Report\n USDT"
            + f"\nFree   : {round(fiat_balance['USDT']['free'],2)}$"
            + f"\nMargin : {round(fiat_balance['USDT']['used'],2)}$"
            + f"\nTotal  : {round(fiat_balance['USDT']['total'],2)}$\nBUSD"
            + f"\nFree   : {round(fiat_balance['BUSD']['free'],2)}$"
            + f"\nMargin : {round(fiat_balance['BUSD']['used'],2)}$"
            + f"\nTotal  : {round(fiat_balance['BUSD']['total'],2)}$"
            + f"\nNet Profit/Loss  : {round(netunpl,2)}$"
        )
        await self.context.bot.send_message(chat_id=self.chat_id, text=msg)

    async def dailyreport(self):
        lastUpdate.status = "Daily Report"
        try:
            await self.context.bot.send_message(
                chat_id=self.chat_id,
                text="คู่เทรดที่น่าสนใจในวันนี้\n",
            )
            async for line in self.get_dailytasks():
                msg1 = remove_last_line_from_string(str(line))
                await self.context.bot.send_message(chat_id=self.chat_id, text=msg1)
            balance = binance_i.balance
            positions = balance["info"]["positions"]
            status = pd.DataFrame(
                [
                    position
                    for position in positions
                    if float(position["positionAmt"]) != 0
                ],
                columns=statcln,
            )
            margin = float((status["initialMargin"]).astype("float64").sum())
            netunpl = float((status["unrealizedProfit"]).astype("float64").sum())
            status = status.sort_values(by=["unrealizedProfit"], ascending=False)
            status = status.head(1)
            firstline = (status.index)[0]
            upnl = round(float((status["unrealizedProfit"]).astype("float64").sum()), 2)
            symbol = status["symbol"][firstline]
            entryP = status["entryPrice"][firstline]
            metthod = status["positionSide"][firstline]
            msg2 = f"{symbol} > {metthod} at {entryP} \nunrealizedProfit : {upnl}$"
            message = (
                f"Top Performance\n{msg2}\n-----\n"
                + f"Net Margin Used : {round(float(margin),2)}$"
                + f"\nNet unrealizedProfit : {round(float(netunpl),2)}$",
            )
            await self.context.bot.send_message(
                chat_id=self.chat_id,
                text=f"{message}",
            )
            return
        except Exception as e:
            await self.context.bot.send_message(
                chat_id=self.chat_id,
                text=f"เกิดความผิดพลาดในส่วนของแจ้งเตือนรายวัน {e}",
            )
            lastUpdate.status = f"{e}"
            return

    def check_moneymanagment(self, status, quote):
        config = AppConfig()
        max_margin = config.max_margin
        min_balance = config.min_balance
        fiat_balance = binance_i.fiat_balance
        free = fiat_balance[quote]["free"]
        risk = float(
            (
                status["initialMargin"].astype("float64")
                * status["leverage"].astype("float64")
            ).sum()
        )
        margin = float((status["initialMargin"].astype("float64")).sum())
        return {
            "margin": margin,
            "max_margin": max_margin,
            "risk": risk,
            "free": free,
            "min_balance": min_balance,
            "can_trade": False
            if margin > max_margin or free < min_balance or risk > (free * 10)
            else True,
        }

    async def main_bot_no_setting(self, symbol: str) -> None:
        try:
            ta_table_data = TATable()

            balance = binance_i.balance
            risk_manage_data = DefaultRiskTable(symbol, balance)
            lastUpdate.status = f"Scaning {risk_manage_data.symbol}"

            if risk_manage_data.usehedge and self.currentMode.dualSidePosition:
                data, df_hedge = await asyncio.gather(
                    self.bot_1(
                        risk_manage_data.symbol,
                        ta_table_data.__dict__,
                        risk_manage_data.timeframe,
                    ),
                    self.bot_2(
                        risk_manage_data.symbol,
                        ta_table_data.__dict__,
                        risk_manage_data.hedge_timeframe,
                    ),
                )
            else:
                data = await self.bot_1(
                    risk_manage_data.symbol,
                    ta_table_data.__dict__,
                    risk_manage_data.timeframe,
                )
                df_hedge = None

            if data is None:
                return

            positions = balance["info"]["positions"]
            status = pd.DataFrame(
                [
                    position
                    for position in positions
                    if float(position["positionAmt"]) != 0
                ],
                columns=statcln,
            )

            mm_permission = self.check_moneymanagment(status, risk_manage_data.quote)

            if df_hedge is not None:
                await asyncio.gather(
                    self.feed(
                        data,
                        risk_manage_data.__dict__,
                        balance,
                        status,
                        mm_permission,
                    ),
                    self.feed_hedge(
                        df_hedge,
                        data,
                        risk_manage_data.__dict__,
                        balance,
                        status,
                        mm_permission,
                    ),
                )
            else:
                await asyncio.gather(
                    self.feed(
                        data,
                        risk_manage_data.__dict__,
                        balance,
                        status,
                        mm_permission,
                    )
                )

        except Exception as e:
            lastUpdate.status = f"{e}"
            print(f"{risk_manage_data.symbol} got error :{e}")

    async def main_bot(self, symbolist: pd.Series) -> None:
        try:
            ta_table_data = TATable(
                atr_p=symbolist["ATR"],
                atr_m=symbolist["ATR_m"],
                ema=symbolist["EMA"],
                linear=symbolist["subhag"],
                smooth=symbolist["smooth"],
                rsi=symbolist["RSI"],
                aol=symbolist["Andean"],
                pivot=symbolist["Pivot"],
            )

            balance = binance_i.balance
            risk_manage_data = RiskManageTable(symbolist, balance)
            lastUpdate.status = f"Scaning {risk_manage_data.symbol}"

            if risk_manage_data.usehedge and self.currentMode.dualSidePosition:
                data, df_hedge = await asyncio.gather(
                    self.bot_1(
                        risk_manage_data.symbol,
                        ta_table_data.__dict__,
                        risk_manage_data.timeframe,
                    ),
                    self.bot_2(
                        risk_manage_data.symbol,
                        ta_table_data.__dict__,
                        risk_manage_data.hedge_timeframe,
                    ),
                )
            else:
                data = await self.bot_1(
                    risk_manage_data.symbol,
                    ta_table_data.__dict__,
                    risk_manage_data.timeframe,
                )
                df_hedge = None

            if data is None:
                return

            positions = balance["info"]["positions"]
            status = pd.DataFrame(
                [
                    position
                    for position in positions
                    if float(position["positionAmt"]) != 0
                ],
                columns=statcln,
            )

            mm_permission = self.check_moneymanagment(status, risk_manage_data.quote)

            if df_hedge is not None:
                await asyncio.gather(
                    self.feed(
                        data,
                        risk_manage_data.__dict__,
                        balance,
                        status,
                        mm_permission,
                    ),
                    self.feed_hedge(
                        df_hedge,
                        data,
                        risk_manage_data.__dict__,
                        balance,
                        status,
                        mm_permission,
                    ),
                )
            else:
                await asyncio.gather(
                    self.feed(
                        data,
                        risk_manage_data.__dict__,
                        balance,
                        status,
                        mm_permission,
                    )
                )

        except Exception as e:
            lastUpdate.status = f"{e}"
            print(f"{risk_manage_data.symbol} got error :{e}")

    async def waiting(self):
        time_now = lastUpdate.candle
        balance = binance_i.balance
        positions = balance["info"]["positions"]
        status = pd.DataFrame(
            [position for position in positions if float(position["positionAmt"]) != 0],
            columns=statcln,
        )
        status["unrealizedProfit"] = (
            (status["unrealizedProfit"]).astype("float64").round(2)
        )

        status["initialMargin"] = (status["initialMargin"]).astype("float64")
        netunpl = float((status["unrealizedProfit"]).astype("float64").sum())
        status.rename(columns=common_names, errors="ignore", inplace=True)
        print(tabulate(status, showindex=False, headers="keys"))
        fiat_balance = binance_i.fiat_balance
        lastUpdate.balance = fiat_balance
        print(
            "\n BUSD"
            + f"\nFree   : {round(fiat_balance['BUSD']['free'],2)}$"
            + f"\nMargin : {round(fiat_balance['BUSD']['used'],2)}$"
            + f"\nTotal  : {round(fiat_balance['BUSD']['total'],2)}$\nUSDT"
            + f"\nFree   : {round(fiat_balance['USDT']['free'],2)}$"
            + f"\nMargin : {round(fiat_balance['USDT']['used'],2)}$"
            + f"\nTotal  : {round(fiat_balance['USDT']['total'],2)}$"
            + f"\nNet Profit/Loss  : {round(netunpl,2)}$"
        )
        print(
            "\r"
            + colorCS.CRED
            + colorCS.CBOLD
            + f"Update : {colorCS.CGREEN}"
            + f"{time_now}"
            + colorCS.CRED
            + f"{colorCS.CRED} Status : "
            + colorCS.CEND
            + f"{lastUpdate.status}",
            end="\n",
        )

    async def get_waiting_time(self):
        symbolist = bot_setting()
        try:
            all_timeframes = (
                symbolist["timeframe"].tolist() + symbolist["hedgeTF"].tolist()
            )
            tf_secconds = [TIMEFRAME_SECONDS[x] for x in all_timeframes]
            timer.min_timewait = min(tf_secconds)
            if timer.min_timewait >= 3600:
                timer.min_timewait = 1800
                all_timeframes.append("30m")
            timer.min_timeframe = next(
                i for i in all_timeframes if TIMEFRAME_SECONDS[i] == timer.min_timewait
            )
            timer.get_time = True
            lastUpdate.candle = datetime.now()
            await binance_i.fetchbars("BTCUSDT", timer.min_timeframe)
            timer.next_candle = timer.last_closed + timer.min_timewait
        except Exception as e:
            print(f"fail to set min time :{e}")
            return await self.get_waiting_time()

    async def warper_fn(self):
        while True:
            if not self.status_bot:
                return
            try:
                local_time = time.ctime(time.time())

                symbolist = bot_setting()
                if symbolist is None or symbolist.empty:
                    lastUpdate.status = "Idle"
                    await asyncio.sleep(60)
                    return

                all_timeframes = (
                    symbolist["timeframe"].tolist() + symbolist["hedgeTF"].tolist()
                )

                tf_secconds = [TIMEFRAME_SECONDS[x] for x in all_timeframes]

                if timer.min_timewait != min(tf_secconds):
                    print("detected new settings")
                    await self.get_waiting_time()

                if str(local_time[14:-9]) == "1" or str(local_time[14:-9]) == "3":
                    insession["day"] = False
                    insession["hour"] = False

                """create async tasks from each bot settings then run it asynconously
                (Do all at the same time)"""
                lastUpdate.status = "Creating Tasks"

                tasks = [
                    asyncio.create_task(self.main_bot(symbolist.loc[i,]))
                    for i in symbolist.index
                ]

                all_symbols = await binance_i.getAllsymbol()
                configed_symbol = symbolist["symbol"].tolist()
                self.watchlist = [
                    (
                        symbolist.index[i],
                        symbolist["symbol"][i],
                        symbolist["timeframe"][i],
                    )
                    for i in range(len(symbolist.index))
                ]
                if self.status_scan:
                    tasks2 = [
                        asyncio.create_task(self.main_bot_no_setting(symbol))
                        for symbol in all_symbols
                        if symbol not in configed_symbol
                    ]
                else:
                    tasks2 = []

                sub_tasks = []

                if time.time() >= timer.next_candle:
                    lastUpdate.candle = datetime.now()
                    await binance_i.update_balance()
                    await self.update_candle()
                    async for task in split_list(tasks, 10):
                        await asyncio.gather(*task)
                    await asyncio.sleep(0.5)
                    if str(local_time[11:-9]) == "07:0" and not insession["day"]:
                        insession["day"] = True
                        insession["hour"] = True
                        # await asyncio.wait_for(dailyreport())
                        sub_tasks.append(
                            asyncio.create_task(self.write_daily_balance())
                        )
                        sub_tasks.append(asyncio.create_task(self.hourly_report()))
                        sub_tasks.append(asyncio.create_task(self.waiting()))
                    if str(local_time[14:-9]) == "0" and not insession["hour"]:
                        insession["hour"] = True
                        sub_tasks.append(asyncio.create_task(self.hourly_report()))
                        sub_tasks.append(asyncio.create_task(self.waiting()))
                    if len(sub_tasks) > 0:
                        await asyncio.gather(*sub_tasks)
                    async for task in split_list(tasks2, 10):
                        await asyncio.gather(*task)
                    timer.next_candle += timer.min_timewait
                    await binance_i.disconnect()
                else:
                    await binance_i.disconnect()
                    await asyncio.sleep(timer.next_candle - time.time())

            except Exception as e:
                lastUpdate.status = f"{e}"
                print(e)
                lastUpdate.status = "Sleep Mode"
                await asyncio.sleep(10)
                tasks = asyncio.current_task()
                clearconsol()
                tasks.cancel()
                raise

            finally:
                await binance_i.disconnect()

    async def TailingLongOrder(self, df, symbol, exchange, ask, amount, low, side):
        try:
            orderid = get_order_id()
            triggerPrice = binance_i.RR1(low, True, ask, symbol, exchange)
            if triggerPrice is None:
                return
            callbackrate = callbackRate(df, True)
            if self.currentMode.dualSidePosition:
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
            await self.notify_send(msg2)
        except Exception as e:
            print(f"{lastUpdate.status}\n{e}")
            await self.notify_send(
                f"เกิดความผิดพลาดในการเข้า Order : Tailing Stop\n{lastUpdate.status}\n{e}"
            )

    async def TailingShortOrder(self, df, symbol, exchange, bid, amount, high, Sside):
        try:
            orderid = get_order_id()
            triggerPrice = binance_i.RR1(high, False, bid, symbol, exchange)
            if triggerPrice is None:
                return
            callbackrate = callbackRate(df, False)
            if self.currentMode.dualSidePosition:
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
            await self.notify_send(msg2)
        except Exception as e:
            print(f"{lastUpdate.status}\n{e}")
            await self.notify_send(
                f"เกิดความผิดพลาดในการเข้า Order : Tailing Stop\n{lastUpdate.status}\n{e}"
            )

    async def USESLSHORT(self, symbol, exchange, amount, high, Sside):
        try:
            orderid = get_order_id()
            if self.currentMode.dualSidePosition:
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
                    "stop_market",
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
            await self.notify_send(
                "เกิดเตุการณืไม่คาดฝัน Order Stop Loss"
                + f"ทำรายการไม่สำเร็จ {lastUpdate.status}\n{e}"
            )
            return 0.0

    async def USESLLONG(self, symbol, exchange: ccxt.binance, amount, low, side):
        try:
            orderid = get_order_id()
            if self.currentMode.dualSidePosition:
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
                    "stop_market",
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
            await self.notify_send(
                f"เกิดเตุการณืไม่คาดฝัน OrderSL ทำรายการไม่สำเร็จ\n{lastUpdate.status}\n{e}"
            )
            return 0.0

    async def USETPLONG(
        self, symbol, df, exchange, ask, TPRR1, TPRR2, Lside, amttp1, amttp2, USETP2
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
            await self.notify_send(
                f"เกิดเตุการณืไม่คาดฝัน OrderTP ทำรายการไม่สำเร็จ\n{lastUpdate.status}\n{e}"
            )
            return None

    # Position Sizing
    async def buysize(self, df, balance, symbol, exchange, RISK, min_amount):
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
            await self.notify_send(
                f"ใช้ Size ขั้นต่ำสำหรับ {symbol}\nโปรดตรวจสอบ SL ด้วยตนเองอีกครั้ง\n"
                + f"Size เดิม : {amount}\nSize ใหม่ : {min_amount}"
            )
            amount = min_amount
        lot = exchange.amount_to_precision(symbol, amount)
        return float(lot)

    async def sellsize(self, df, balance, symbol, exchange, RISK, min_amount):
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
            await self.notify_send(
                f"ใช้ Size ขั้นต่ำสำหรับ {symbol}\nโปรดตรวจสอบ SL ด้วยตนเองอีกครั้ง\n"
                + f"Size เดิม : {amount}\nSize ใหม่ : {min_amount}"
            )
            amount = min_amount
        lot = exchange.amount_to_precision(symbol, amount)
        return float(lot)

    # OpenLong=Buy
    async def OpenLong(
        self, df, balance, risk_manage, Lside, min_balance, tf, clearorder: bool = True
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
            ask = await binance_i.get_bidask(risk_manage["symbol"], "ask")
            if min_amount * ask < 5.0:
                min_amount = 6.0 / ask
            amount = await self.buysize(
                df,
                balance,
                risk_manage["symbol"],
                exchange,
                risk_manage["risk_size"],
                min_amount,
            )
            leve = await binance_i.setleverage(
                risk_manage["symbol"], risk_manage["leverage"]
            )
            if amount * ask > risk_manage["max_size"] * int(leve):
                new_lots = risk_manage["max_size"] * int(leve) / ask
                if new_lots < min_amount:
                    await self.notify_send(
                        f"Risk Size ใหญ่เกินไป ใช้ Size ขั้นต่ำสำหรับ {risk_manage['symbol']}"  # noqa:
                        + "\nโปรดตรวจสอบ SL ด้วยตนเองอีกครั้ง"
                        + f"Size เดิม : {new_lots}Size ใหม่ : {min_amount}"
                    )
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
                    await self.notify_send(e)
                    return
                if risk_manage["use_tp_1"]:
                    tp12 = await self.USETPLONG(
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
                    slprice = await self.USESLLONG(
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
                await self.notify_send(msg)
                if risk_manage["use_tailing"]:
                    await self.TailingLongOrder(
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
                await self.notify_send(msg)
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
            await self.notify_send_pic(
                candle(df, risk_manage["symbol"], f"{tf} {time_now}")
            )
            return
        except Exception as e:
            print(f"{lastUpdate.status}\n{e}")
            await self.notify_send(
                f"เกิดความผิดพลาดในการเข้า Order : OpenLong\n{lastUpdate.status}\n{e}"
            )
            return

    async def USETPSHORT(
        self, symbol, df, exchange, bid, TPRR1, TPRR2, Sside, amttp1, amttp2, USETP2
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
            await self.notify_send(
                f"เกิดเตุการณืไม่คาดฝัน Order TP  ทำรายการไม่สำเร็จ{lastUpdate.status}\n{e}"
            )
            return None

    # OpenShort=Sell
    async def OpenShort(
        self, df, balance, risk_manage, Sside, min_balance, tf, clearorder: bool = True
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
            bid = await binance_i.get_bidask(risk_manage["symbol"], "bid")
            if min_amount * bid < 5.0:
                min_amount = 6.0 / bid
            amount = await self.sellsize(
                df,
                balance,
                risk_manage["symbol"],
                exchange,
                risk_manage["risk_size"],
                min_amount,
            )
            leve = await binance_i.setleverage(
                risk_manage["symbol"], risk_manage["leverage"]
            )
            if amount * bid > risk_manage["max_size"] * int(leve):
                new_lots = risk_manage["max_size"] * int(leve) / bid
                if new_lots < min_amount:
                    await self.notify_send(
                        f"Risk Size ใหญ่เกินไป ใช้ Size ขั้นต่ำสำหรับ {risk_manage['symbol']}"  # noqa:
                        + "\nโปรดตรวจสอบ SL ด้วยตนเองอีกครั้ง"
                        + f"Size เดิม : {new_lots}Size ใหม่ : {min_amount}"
                    )
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
                    await self.notify_send(e)
                    return
                if risk_manage["use_sl"]:
                    slprice = await self.USESLSHORT(
                        risk_manage["symbol"],
                        exchange,
                        amount,
                        high,
                        Sside,
                    )
                if risk_manage["use_tp_1"]:
                    tp12 = await self.USETPSHORT(
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
                await self.notify_send(msg)
                if risk_manage["use_tailing"]:
                    await self.TailingShortOrder(
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
                await self.notify_send(msg)
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
            await self.notify_send_pic(
                candle(df, risk_manage["symbol"], f"{tf} {time_now}")
            )
            return
        except Exception as e:
            print(f"{lastUpdate.status}\n{e}")
            await self.notify_send(
                f"เกิดความผิดพลาดในการเข้า Order : OpenShort\n{lastUpdate.status}\n{e}"
            )
            return

    # CloseLong=Sell
    async def CloseLong(
        self, df, balance, symbol, amt, pnl, Lside, tf, closeall: bool = False
    ):
        exchange = await binance_i.get_exchange()
        await binance_i.connect_loads()
        try:
            amount = abs(amt)
            upnl = pnl
            quote = symbol[-4:]
            bid = await binance_i.get_bidask(symbol, "bid")
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
            await self.notify_send(msg)
            time_now = lastUpdate.candle
            if closeall:
                edit_all_trade_record(time_now, symbol, "Long", bid)
            else:
                edit_trade_record(time_now, symbol, tf, "Long", bid)

            await self.notify_send_pic(candle(df, symbol, f"{tf} {time_now}"))
            return
        except Exception as e:
            print(f"{lastUpdate.status}\n{e}")
            await self.notify_send(
                f"เกิดความผิดพลาดในการออก Order : CloseLong\n{lastUpdate.status}\n{e}"
            )
            return

    # CloseShort=Buy
    async def CloseShort(
        self, df, balance, symbol, amt, pnl, Sside, tf, closeall: bool = False
    ):
        exchange = await binance_i.get_exchange()
        await binance_i.connect_loads()
        try:
            amount = abs(amt)
            quote = symbol[-4:]
            orderid = get_order_id()
            upnl = pnl
            ask = await binance_i.get_bidask(symbol, "ask")
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
            await self.notify_send(msg)
            time_now = lastUpdate.candle
            if closeall:
                edit_all_trade_record(time_now, symbol, "Short", ask)
            else:
                edit_trade_record(time_now, symbol, tf, "Short", ask)
            await self.notify_send_pic(candle(df, symbol, f"{tf} {time_now}"))
            return
        except Exception as e:
            print(f"{lastUpdate.status}\n{e}")
            await self.notify_send(
                f"เกิดความผิดพลาดในการออก Order : CloseShort\n{lastUpdate.status}\n{e}"
            )
            return

    async def get_currentmode(self):
        exchange = await binance_i.get_exchange()
        try:
            data = await exchange.fetch_account_positions(["BTCUSDT"])
        except Exception as e:
            lastUpdate.status = f"{e}"
            await binance_i.connect_loads()
            data = await exchange.fetch_account_positions(["BTCUSDT"])
        await binance_i.disconnect()
        self.currentMode.dualSidePosition = data[0]["hedged"]
        if self.currentMode.dualSidePosition:
            self.currentMode.Sside = "SHORT"
            self.currentMode.Lside = "LONG"

    async def check_current_position(self, symbol: str, status: pd.DataFrame) -> dict:
        if "/" in symbol:
            posim = symbol[:-5].replace("/", "")
        else:
            posim = symbol
        if status is None:
            return
        status = status[status["symbol"] == posim]

        if status.empty:
            price_long = 0.0
            price_short = 0.0
            amt_short = 0.0
            amt_long = 0.0
            upnl_short = 0.0
            upnl_long = 0.0
            margin_long = 0.0
            margin_short = 0.0
            leverage = 0
        elif len(status.index) > 1:
            amt_long = float(
                (
                    status["positionAmt"][i]
                    for i in status.index
                    if status["symbol"][i] == posim
                    and status["positionSide"][i] == "LONG"
                ).__next__()
            )
            amt_short = float(
                (
                    status["positionAmt"][i]
                    for i in status.index
                    if status["symbol"][i] == posim
                    and status["positionSide"][i] == "SHORT"
                ).__next__()
            )
            upnl_long = float(
                (
                    status["unrealizedProfit"][i]
                    for i in status.index
                    if status["symbol"][i] == posim
                    and status["positionSide"][i] == "LONG"
                ).__next__()
            )
            upnl_short = float(
                (
                    status["unrealizedProfit"][i]
                    for i in status.index
                    if status["symbol"][i] == posim
                    and status["positionSide"][i] == "SHORT"
                ).__next__()
            )
            margin_long = float(
                (
                    status["initialMargin"][i]
                    for i in status.index
                    if status["symbol"][i] == posim
                    and status["positionSide"][i] == "LONG"
                ).__next__()
            )
            margin_short = float(
                (
                    status["initialMargin"][i]
                    for i in status.index
                    if status["symbol"][i] == posim
                    and status["positionSide"][i] == "SHORT"
                ).__next__()
            )
            price_long = float(
                (
                    status["entryPrice"][i]
                    for i in status.index
                    if status["symbol"][i] == posim
                    and status["positionSide"][i] == "LONG"
                ).__next__()
            )
            price_short = float(
                (
                    status["entryPrice"][i]
                    for i in status.index
                    if status["symbol"][i] == posim
                    and status["positionSide"][i] == "SHORT"
                ).__next__()
            )
            leverage = int(
                (
                    status["leverage"][i]
                    for i in status.index
                    if status["symbol"][i] == posim
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
            upnl = float(
                (
                    status["unrealizedProfit"][i]
                    for i in status.index
                    if status["symbol"][i] == posim
                ).__next__()
            )
            price_ = float(
                (
                    status["entryPrice"][i]
                    for i in status.index
                    if status["symbol"][i] == posim
                ).__next__()
            )
            margin_ = float(
                (
                    status["initialMargin"][i]
                    for i in status.index
                    if status["symbol"][i] == posim
                ).__next__()
            )
            amt_long = amt if amt > 0 else 0.0
            amt_short = amt if amt < 0 else 0.0
            margin_long = margin_ if amt > 0 else 0.0
            margin_short = margin_ if amt < 0 else 0.0
            upnl_long = upnl if amt != 0 else 0.0
            upnl_short = upnl if amt != 0 else 0.0
            price_long = price_ if amt > 0 else 0.0
            price_short = price_ if amt < 0 else 0.0
            leverage = int(
                (
                    status["leverage"][i]
                    for i in status.index
                    if status["symbol"][i] == posim
                ).__next__()
            )
        is_in_Long = True if amt_long != 0 else False
        is_in_Short = True if amt_short != 0 else False
        del status
        return {
            "symbol": posim,
            "leverage": leverage,
            "long": {
                "price": price_long,
                "amount": amt_long,
                "pnl": upnl_long,
                "position": is_in_Long,
                "margin": margin_long,
            },
            "short": {
                "price": price_short,
                "amount": amt_short,
                "pnl": upnl_short,
                "position": is_in_Short,
                "margin": margin_short,
            },
        }

    async def get_closed_pnl(self, symbol):
        try:
            exchange = await binance_i.get_exchange()
            closed_pnl = await exchange.fetch_my_trades(symbol, limit=1)
            return closed_pnl[0]
        except Exception:
            return None

    async def check_if_closed_position(
        self,
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
            closed_pnl = await self.get_closed_pnl(symbol)
            await self.notify_send(
                f"{symbol} {timeframe} {direction} got Stop-Loss!\n"
                + f"at {closed_pnl['price']}\nP/L : {closed_pnl['info']['realizedPnl']}"
            )
            time_now = lastUpdate.candle
            edit_trade_record(
                time_now,
                symbol,
                timeframe,
                direction,
                0.0,
                isSl=True,
            )
            await self.notify_send_pic(candle(df, symbol, f"{timeframe} {time_now}"))
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
            closed_pnl = await self.get_closed_pnl(symbol)
            await self.notify_send(
                f"{symbol} {timeframe} {direction} Being Closed!\n"
                + f"at {closed_pnl['price']}\nP/L : {closed_pnl['info']['realizedPnl']}"
            )
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
            closed_pnl = await self.get_closed_pnl(symbol)
            await self.notify_send(
                f"{symbol} {timeframe} {direction} Being TP!!\n"
                + f"at {closed_pnl['price']}\nP/L : {closed_pnl['info']['realizedPnl']}"
            )
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

    async def notify_signal(self, df, risk_manage, mm_permission, signal: str = ""):
        timeframe = risk_manage["timeframe"]
        if f"{risk_manage['symbol']}_{timeframe}" not in notify_history.keys():
            notify_history[f"{risk_manage['symbol']}_{timeframe}"] = 0
        if (
            candle_ohlc[f"{risk_manage['symbol']}_{timeframe}"]["cTime"]
            != notify_history[f"{risk_manage['symbol']}_{timeframe}"]
        ):
            quote = risk_manage["quote"]
            await self.notify_send(
                f"{risk_manage['symbol']} {timeframe}"
                + f"\nเกิดสัญญาณ {signal}\nแต่ "
                + "Risk Margin รวมสูงเกินไปแล้ว!!"
                + f"\nFree Balance : {round(mm_permission['free'],3)} {quote}"
                + f"\nMargin รวม  : {round(mm_permission['margin'],3)} $"
                + f"\nRisk ทั้งหมด : {round(mm_permission['risk'],3)} $\n"
                + f"Risk สูงสุดที่กำหนดไว้ : {round(mm_permission['max_margin'],3)} $"
            )
            await self.notify_send_pic(candle(df, risk_manage["symbol"], timeframe))
            notify_history[f"{risk_manage['symbol']}_{timeframe}"] = candle_ohlc[
                f"{risk_manage['symbol']}_{timeframe}"
            ]["cTime"]

    async def feed(
        self,
        df,
        risk_manage,
        balance,
        status,
        mm_permission,
    ):
        last = len(df.index) - 1

        current_position, closed = await asyncio.gather(  # pyright: ignore
            self.check_current_position(risk_manage["symbol"], status.copy()),
            self.check_if_closed_position(
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
                await self.CloseShort(
                    df,
                    balance,
                    risk_manage["symbol"],
                    current_position["short"]["amount"],
                    current_position["short"]["pnl"],
                    self.currentMode.Sside,
                    risk_manage["timeframe"],
                    closeall=True,
                )
                await binance_i.update_balance(force=True)
                if risk_manage["use_long"]:
                    if mm_permission["can_trade"]:
                        await self.OpenLong(
                            df,
                            balance,
                            risk_manage,
                            self.currentMode.Lside,
                            mm_permission["min_balance"],
                            risk_manage["timeframe"],
                        )
                        await binance_i.update_balance(force=True)
                    else:
                        await self.notify_signal(df, risk_manage, mm_permission, "Long")
                else:
                    print("No permission for excute order : Do nothing")

            else:
                if risk_manage["use_long"]:
                    if mm_permission["can_trade"]:
                        await self.OpenLong(
                            df,
                            balance,
                            risk_manage,
                            self.currentMode.Lside,
                            mm_permission["min_balance"],
                            risk_manage["timeframe"],
                        )
                        await binance_i.update_balance(force=True)
                    else:
                        await self.notify_signal(df, risk_manage, mm_permission, "Long")
                else:
                    print("No permission for excute order : Do nothing")

        if df["SELL"][last] == 1 and short_record is None:
            lastUpdate.status = "changed to Bearish, Sell"
            if current_position["long"]["position"]:
                lastUpdate.status = "closelong"
                await self.CloseLong(
                    df,
                    balance,
                    risk_manage["symbol"],
                    current_position["long"]["amount"],
                    current_position["long"]["pnl"],
                    self.currentMode.Lside,
                    risk_manage["timeframe"],
                    closeall=True,
                )
                await binance_i.update_balance(force=True)
                if risk_manage["use_short"]:
                    if mm_permission["can_trade"]:
                        await self.OpenShort(
                            df,
                            balance,
                            risk_manage,
                            self.currentMode.Sside,
                            mm_permission["min_balance"],
                            risk_manage["timeframe"],
                        )
                        await binance_i.update_balance(force=True)
                    else:
                        await self.notify_signal(
                            df, risk_manage, mm_permission, "Short"
                        )
                else:
                    print("No permission for excute order : Do nothing")
            else:
                if risk_manage["use_short"]:
                    if mm_permission["can_trade"]:
                        await self.OpenShort(
                            df,
                            balance,
                            risk_manage,
                            self.currentMode.Sside,
                            mm_permission["min_balance"],
                            risk_manage["timeframe"],
                        )
                        await binance_i.update_balance(force=True)
                    else:
                        await self.notify_signal(
                            df, risk_manage, mm_permission, "Short"
                        )
                else:
                    print("No permission for excute order : Do nothing")

    async def feed_hedge(
        self,
        df,
        df_trend,
        risk_manage,
        balance,
        status: pd.DataFrame,
        mm_permission,
    ):
        last = len(df.index) - 1

        current_position, closed = await asyncio.gather(  # pyright: ignore
            self.check_current_position(risk_manage["symbol"], status.copy()),
            self.check_if_closed_position(
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
                await self.OpenLong(
                    df,
                    balance,
                    risk_manage,
                    self.currentMode.Lside,
                    mm_permission["min_balance"],
                    risk_manage["hedge_timeframe"],
                    False,
                )
                await binance_i.update_balance(force=True)
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
            await self.CloseShort(
                df,
                balance,
                risk_manage["symbol"],
                current_position["short"]["amount"],
                current_position["short"]["pnl"],
                self.currentMode.Sside,
                risk_manage["hedge_timeframe"],
            )
            await binance_i.update_balance(force=True)

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
                await self.OpenShort(
                    df,
                    balance,
                    risk_manage,
                    self.currentMode.Sside,
                    mm_permission["min_balance"],
                    risk_manage["hedge_timeframe"],
                    False,
                )
                await binance_i.update_balance(force=True)
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
            await self.CloseLong(
                df,
                balance,
                risk_manage["symbol"],
                current_position["long"]["amount"],
                current_position["long"]["pnl"],
                self.currentMode.Lside,
                risk_manage["hedge_timeframe"],
            )
            await binance_i.update_balance(force=True)
