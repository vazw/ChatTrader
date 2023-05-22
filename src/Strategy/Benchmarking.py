#     DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
#
# Copyright (c) 2022 vazw. All rights reserved.
#
# Licensed under the "THE BEER-WARE LICENSE" (Revision 42):
# Everyone is permitted to copy and distribute verbatim or modified
# copies of this license document, and changing it is allowed as long
# as the name is changed.
#
#     DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
# TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION
#     0. You just DO WHAT THE FUCK YOU WANT TO.
import numpy as np
import pandas as pd
from talib import ADX, MACD, MINUS_DI, PLUS_DI, SMA

ADX_W = 30
VXMA_W = 50
MACD_W = 10
SMA200_W = 10


class benchmarking:
    def __init__(self, data: pd.DataFrame) -> None:
        self.data = data

    # Trending a symbol.
    def benchmarking(self):
        tacollum = ["sma_200", "macd", "adx", "adx+", "adx-"]
        datascoe = pd.DataFrame(columns=tacollum)
        # verify series
        Close = pd.Series(self.data["close"], dtype=np.float64)
        Open = pd.Series(self.data["open"], dtype=np.float64)
        High = pd.Series(self.data["high"], dtype=np.float64)
        Low = pd.Series(self.data["low"], dtype=np.float64)
        try:
            datascoe["sma_200"] = SMA(Close, 200)
            datascoe["macd"], macdsignal, macdhist = MACD(Open, 12, 26, 9)
            del macdhist, macdsignal
            datascoe["adx"] = ADX(High, Low, Close, 14)
            datascoe["adx+"] = PLUS_DI(High, Low, Close, 14)
            datascoe["adx-"] = MINUS_DI(High, Low, Close, 14)
            m = len(datascoe.index) - 1
            adxx = 0
            if (
                datascoe["adx"][m] > 25
                and datascoe["adx+"][m] > datascoe["adx-"][m]
            ):  # noqa:
                adxx = 10
            elif (
                datascoe["adx"][m] > 25
                and datascoe["adx+"][m] < datascoe["adx-"][m]
            ):  # noqa:
                adxx = 0
            else:
                adxx = 5
            macd = 10 if float(datascoe["macd"][m]) > 0 else 0
            sma = 10 if float(datascoe["sma_200"][m]) < float(Close[m]) else 0
            if self.data["vxma"][m] > self.data["vxma"][m - 1]:
                vxda = 10
            elif self.data["vxma"][m] < self.data["vxma"][m - 1]:
                vxda = 0
            else:
                vxda = 5
            score = (
                (macd * MACD_W) / 100
                + (adxx * ADX_W) / 100
                + (sma * SMA200_W) / 100
                + (vxda * VXMA_W) / 100
            )
            if score > 8:
                scr = "Extreme-Bullish"
            elif score > 6:
                scr = "Bullish"
            elif score < 4:
                scr = "Bearish"
            elif score < 2:
                scr = "Extreme-Bearish"
            else:
                scr = "Side-Way"
            return scr
        except Exception as e:
            print(f"Bencmarking is error : {e}")
            return "error"
