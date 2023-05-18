import asyncio
import time
from uuid import uuid4
import warnings
from tabulate import tabulate
from collections import deque

import pandas as pd

from vxma_d.AppData import (
    colorCS,
    lastUpdate,
    timer,
    candle_ohlc,
)
from vxma_d.AppData.Appdata import (
    AppConfig,
    DefaultRiskTable,
    RiskManageTable,
    TATable,
    bot_setting,
    candle,
    clearconsol,
    notify_send,
)
from vxma_d.MarketEX.CCXT_Binance import (
    feed,
    feed_hedge,
    getAllsymbol,
    get_currentmode,
    get_symbol,
    account_balance,
    fetchbars,
    binance_i,
)
from vxma_d.Strategy.Benchmarking import benchmarking as ta_score
from vxma_d.Strategy.vxma_talib import vxma as ta


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


async def update_candle() -> None:
    try:
        timenow = time.time()
        update_tasks = [
            asyncio.create_task(fetchbars(symbol, tf))
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


async def bot_1(symbol, ta_data, tf):
    try:
        if (
            f"{symbol}_{tf}" not in candle_ohlc.keys()
            or candle_ohlc[f"{symbol}_{tf}"]["candle"] is None
        ):
            await fetchbars(symbol, tf)
        data1 = candle_ohlc[f"{symbol}_{tf}"]["candle"].copy()
        if data1 is None or len(data1.index) < 100:
            return None
        bot1 = ta(data1, ta_data)
        data1 = bot1.indicator()
        return data1
    except Exception as e:
        lastUpdate.status = f"{e}"
        return bot_1(symbol, ta_data, tf)


async def bot_2(symbol, ta_data, tf):
    try:
        if (
            f"{symbol}_{tf}" not in candle_ohlc.keys()
            or candle_ohlc[f"{symbol}_{tf}"]["candle"] is None
        ):
            await fetchbars(symbol, tf)
        data2 = candle_ohlc[f"{symbol}_{tf}"]["candle"].copy()
        if data2 is None or len(data2.index) < 100:
            return None
        bot2 = ta(data2, ta_data)
        data2 = bot2.indicator()
        return data2
    except Exception as e:
        lastUpdate.status = f"{e}"
        return bot_2(symbol, ta_data, tf)


async def bot_3(symbol, ta_data, tf):
    try:
        if (
            f"{symbol}_{tf}" not in candle_ohlc.keys()
            or candle_ohlc[f"{symbol}_{tf}"]["candle"] is None
        ):
            await fetchbars(symbol, tf)
        data3 = candle_ohlc[f"{symbol}_{tf}"]["candle"].copy()
        if data3 is None or len(data3.index) < 100:
            return None
        bot3 = ta(data3, ta_data)
        data3 = bot3.indicator()
        return data3
    except Exception as e:
        lastUpdate.status = f"{e}"
        return bot_2(symbol, ta_data, tf)


async def scaning_method(symbol: str, ta_data: TATable, symbols: list):
    try:

        df1, df2, df3 = await asyncio.gather(
            bot_1(symbol, ta_data.__dict__, "1d"),
            bot_2(symbol, ta_data.__dict__, "6h"),
            bot_3(symbol, ta_data.__dict__, "1h"),
        )

        if df1 is not None:
            long_term = ta_score(df1)
            mid_term = ta_score(df2)
            short_term = ta_score(df3)
            long_term_score = long_term.benchmarking()
            mid_term_score = mid_term.benchmarking()
            short_term_score = short_term.benchmarking()
            if (
                (
                    long_term_score == "Side-Way"
                    and mid_term_score == "Side-Way"
                )
                or (
                    long_term_score == "Side-Way"
                    and short_term_score == "Side-Way"
                )
                or (
                    mid_term_score == "Side-Way"
                    and short_term_score == "Side-Way"
                )
            ):
                pass
            else:
                print(f"{symbol} is Trending: {long_term_score}")
                symbols.append(symbol)
                lastUpdate.status = f"Added {symbol} to list"

    except Exception as e:
        lastUpdate.status = f"{e}"
        pass


async def scanSideway():
    symbolist = await getAllsymbol()
    lastUpdate.status = f"Scanning {len(symbolist)} Symbols"
    ta_data = TATable()
    symbols = []
    tasks = [
        asyncio.create_task(scaning_method(symbol, ta_data, symbols))
        for symbol in symbolist
    ]
    async for task in split_list(tasks, 10):
        await asyncio.gather(*task)
    return symbols


async def get_dailytasks():
    daycollum = ["Symbol", "LastPirce", "Long-Term", "Mid-Term", "Short-Term"]
    symbolist = await get_symbol()
    ta_data = TATable()
    for symbol in symbolist:
        try:
            df1, df2, df3 = await asyncio.gather(
                bot_1(symbol, ta_data.__dict__, "1d"),
                bot_2(symbol, ta_data.__dict__, "6h"),
                bot_3(symbol, ta_data.__dict__, "1h"),
            )

            # candle(df3, symbol, "1h")
            if df1 is not None:
                time_now = lastUpdate.candle
                candle(df1, symbol, f"1d {time_now}")
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


def remove_last_line_from_string(text):
    return text[: text.rfind("\n")]


async def write_daily_balance():
    fiat_balance = account_balance.fiat_balance
    total_balance = (
        fiat_balance["BUSD"]["total"] + fiat_balance["USDT"]["total"]
    )
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


async def hourly_report():
    balance = account_balance.balance
    lastUpdate.status = "Hourly report"
    positions = balance["info"]["positions"]
    status = pd.DataFrame(
        [
            position
            for position in positions
            if float(position["positionAmt"]) != 0
        ],
        columns=statcln,
    )
    netunpl = float(
        status["unrealizedProfit"].astype("float64").sum()
        if not status.empty
        else 0.0
    )
    fiat_balance = account_balance.fiat_balance
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
    notify_send(msg)


async def dailyreport():
    lastUpdate.status = "Daily Report"
    try:
        notify_send(
            "คู่เทรดที่น่าสนใจในวันนี้\n",
            sticker=1990,
            package=446,
        )
        async for line in get_dailytasks():
            msg1 = remove_last_line_from_string(str(line))
            notify_send(msg=msg1)
        balance = account_balance.balance
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
        upnl = round(
            float((status["unrealizedProfit"]).astype("float64").sum()), 2
        )
        symbol = status["symbol"][firstline]
        entryP = status["entryPrice"][firstline]
        metthod = status["positionSide"][firstline]
        msg2 = f"{symbol} > {metthod} at {entryP} \nunrealizedProfit : {upnl}$"
        message = (
            f"Top Performance\n{msg2}\n-----\n"
            + f"Net Margin Used : {round(float(margin),2)}$"
            + f"\nNet unrealizedProfit : {round(float(netunpl),2)}$",
        )
        notify_send(
            message,
            sticker=1995,
            package=446,
        )
        return
    except Exception as e:
        notify_send(f"เกิดความผิดพลาดในส่วนของแจ้งเตือนรายวัน {e}")
        lastUpdate.status = f"{e}"
        return


def check_moneymanagment(status, quote):
    config = AppConfig()
    max_margin = config.max_margin
    min_balance = config.min_balance
    fiat_balance = account_balance.fiat_balance
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


async def main_bot_no_setting(symbol: str) -> None:
    try:
        ta_table_data = TATable()

        balance = account_balance.balance
        risk_manage_data = DefaultRiskTable(symbol, balance)
        lastUpdate.status = f"Scaning {risk_manage_data.symbol}"

        if risk_manage_data.usehedge:
            data, df_hedge = await asyncio.gather(
                bot_1(
                    risk_manage_data.symbol,
                    ta_table_data.__dict__,
                    risk_manage_data.timeframe,
                ),
                bot_2(
                    risk_manage_data.symbol,
                    ta_table_data.__dict__,
                    risk_manage_data.hedge_timeframe,
                ),
            )
        else:
            data = await bot_1(
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

        mm_permission = check_moneymanagment(status, risk_manage_data.quote)

        if df_hedge is not None:
            await asyncio.gather(
                feed(
                    data,
                    risk_manage_data.__dict__,
                    balance,
                    status,
                    mm_permission,
                ),
                feed_hedge(
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
                feed(
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


async def main_bot(symbolist: pd.Series) -> None:
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

        balance = account_balance.balance
        risk_manage_data = RiskManageTable(symbolist, balance)
        lastUpdate.status = f"Scaning {risk_manage_data.symbol}"

        if risk_manage_data.usehedge:
            data, df_hedge = await asyncio.gather(
                bot_1(
                    risk_manage_data.symbol,
                    ta_table_data.__dict__,
                    risk_manage_data.timeframe,
                ),
                bot_2(
                    risk_manage_data.symbol,
                    ta_table_data.__dict__,
                    risk_manage_data.hedge_timeframe,
                ),
            )
        else:
            data = await bot_1(
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

        mm_permission = check_moneymanagment(status, risk_manage_data.quote)

        if df_hedge is not None:
            await asyncio.gather(
                feed(
                    data,
                    risk_manage_data.__dict__,
                    balance,
                    status,
                    mm_permission,
                ),
                feed_hedge(
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
                feed(
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


async def waiting():
    time_now = lastUpdate.candle
    balance = account_balance.balance
    positions = balance["info"]["positions"]
    status = pd.DataFrame(
        [
            position
            for position in positions
            if float(position["positionAmt"]) != 0
        ],
        columns=statcln,
    )
    status["unrealizedProfit"] = (
        (status["unrealizedProfit"]).astype("float64").round(2)
    )

    status["initialMargin"] = (status["initialMargin"]).astype("float64")
    netunpl = float((status["unrealizedProfit"]).astype("float64").sum())
    status.rename(columns=common_names, errors="ignore", inplace=True)
    print(tabulate(status, showindex=False, headers="keys"))
    fiat_balance = account_balance.fiat_balance
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
        + time_now
        + colorCS.CRED
        + f"{colorCS.CRED} Status : "
        + colorCS.CEND
        + f"{lastUpdate.status}",
        end="\n",
    )


async def get_waiting_time():
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
            i
            for i in all_timeframes
            if TIMEFRAME_SECONDS[i] == timer.min_timewait
        )
        timer.get_time = True
        lastUpdate.candle = time.ctime(time.time())
        await fetchbars("BTCUSDT", timer.min_timeframe)
        timer.next_candle = timer.last_closed + timer.min_timewait
    except Exception as e:
        print(f"fail to set min time :{e}")
        return await get_waiting_time()


async def warper_fn():
    while True:
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
                await get_waiting_time()

            if str(local_time[14:-9]) == "1" or str(local_time[14:-9]) == "3":
                insession["day"] = False
                insession["hour"] = False

            """create async tasks from each bot settings then run it asynconously
            (Do all at the same time)"""
            lastUpdate.status = "Creating Tasks"

            tasks = [
                asyncio.create_task(
                    main_bot(
                        symbolist.iloc[
                            i,
                        ]
                    )
                )
                for i in symbolist.index
            ]

            all_symbols = await getAllsymbol()
            configed_symbol = symbolist["symbol"].tolist()
            tasks2 = [
                asyncio.create_task(main_bot_no_setting(symbol))
                for symbol in all_symbols
                if symbol not in configed_symbol
            ]

            sub_tasks = []

            if time.time() >= timer.next_candle:
                lastUpdate.candle = time.ctime(time.time())
                await account_balance.update_balance()
                await update_candle()
                async for task in split_list(tasks, 10):
                    await asyncio.gather(*task)
                await asyncio.sleep(0.5)
                if str(local_time[11:-9]) == "07:0" and not insession["day"]:
                    insession["day"] = True
                    insession["hour"] = True
                    # await asyncio.wait_for(dailyreport())
                    sub_tasks.append(
                        asyncio.create_task(write_daily_balance())
                    )
                    sub_tasks.append(asyncio.create_task(hourly_report()))
                    sub_tasks.append(asyncio.create_task(waiting()))
                if str(local_time[14:-9]) == "0" and not insession["hour"]:
                    insession["hour"] = True
                    sub_tasks.append(asyncio.create_task(hourly_report()))
                    sub_tasks.append(asyncio.create_task(waiting()))
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
            notify_send(f"เกิดข้อผิดพลาดภายนอก\n{e}\nRestarting Bot...")
            lastUpdate.status = "Sleep Mode"
            await asyncio.sleep(10)
            tasks = asyncio.current_task()
            clearconsol()
            tasks.cancel()
            raise

        finally:
            await binance_i.disconnect()


async def run_bot():
    config = AppConfig()
    if config.notify_token == "":
        await asyncio.sleep(60)
        return
    print(f"{colorCS.CBOLD}{colorCS.CGREEN}{bot_name}{colorCS.CEND}")
    try:
        await account_balance.update_balance()
        await get_currentmode()
        await get_waiting_time()
        await waiting()
        await asyncio.gather(warper_fn())
    except Exception as e:
        print(f"Restarting :{e}")
        lastUpdate.status = "Fallback Mode : Restarting..."
        return
