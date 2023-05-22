# The BEERWARE License (BEERWARE)
#
# Copyright (c) 2022 Author. All rights reserved.
#
# Licensed under the "THE BEER-WARE LICENSE" (Revision 42):
# vazw wrote this file. As long as you retain this notice you
# can do whatever you want with this stuff. If we meet some day, and you think
# this stuff is worth it, you can buy me a beer or coffee in return
import numpy as np
import pandas as pd
from talib import EMA


def EMA_CROSS(df, emafast, emaslow) -> pd.DataFrame:
    df["EMA_FAST"] = EMA(df["close"], emafast)
    df["EMA_SLOW"] = EMA(df["close"], emaslow)

    m = len(df.index)
    df["BUY"] = np.full(m, False)
    df["SELL"] = np.full(m, False)
    df["buyPrice"] = np.full(m, np.nan)
    df["sellPrice"] = np.full(m, np.nan)

    for current_candle in range(m):
        if (
            df["EMA_FAST"][current_candle - 1]
            > df["EMA_SLOW"][current_candle - 1]
            and df["EMA_FAST"][current_candle - 2]
            < df["EMA_SLOW"][current_candle - 2]
        ):
            df["BUY"][current_candle] = True
            df["buyPrice"][current_candle] = df["close"][current_candle]
        if (
            df["EMA_FAST"][current_candle - 1]
            < df["EMA_SLOW"][current_candle - 1]
            and df["EMA_FAST"][current_candle - 2]
            > df["EMA_SLOW"][current_candle - 2]
        ):
            df["SELL"][current_candle] = True
            df["sellPrice"][current_candle] = df["close"][current_candle]
    return df
