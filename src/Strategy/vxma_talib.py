import math
import warnings

import numpy as np
import pandas as pd
from talib import EMA, LINEARREG, MAX, MIN, RSI, SMA, TRANGE

# __author__ = "Vaz, Jakkaphat"
# __email__ = "4wonzest@gmail.com"


warnings.filterwarnings("ignore")
pd.set_option("display.max_row", None)
bCollum = ["BUY", "buyPrice", "SELL", "sellPrice"]
common_names = {
    "Date": "date",
    "Time": "time",
    "Timestamp": "timestamp",
    "Datetime": "datetime",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
    "Dividends": "dividends",
    "Stock Splits": "split",
}


class vxma:
    def __init__(self, data, ta_table=None) -> None:
        """
        vxma strategy form trading view by vaz.
        using EMA, RSI, ATR, LINREG AND ALPHATREND TA to calculate.
        : https://www.tradingview.com/script/m54nptt2-VXMA-Bot/
        ---------------------
        :data= any | in the form of
        >> ["timestamp", "open", "high", "low", "close", "volume"]
        :ta_table = {
            "atr_p": 12,
            "atr_m": 1.6,
            "ema": 30,
            "linear": 30,
            "smooth": 30,
            "rsi": 25,
            "aol": 30,
            "pivot": 60,
        }"""
        if data.empty:
            return
        if len(data.columns) > 0:
            # Preemptively drop the rows that are all NaNs
            # Might need to be moved to AnalysisIndicators.__call__() to be
            #   toggleable via kwargs.
            # df.dropna(axis=0, inplace=True)
            # Preemptively rename columns to lowercase
            data.rename(columns=common_names, errors="ignore", inplace=True)
            if ta_table is None:
                ta_table = {
                    "atr_p": 12,
                    "atr_m": 1.6,
                    "ema": 30,
                    "linear": 30,
                    "smooth": 30,
                    "rsi": 25,
                    "aol": 30,
                    "pivot": 60,
                }

            # Preemptively lowercase the index
            index_name = data.index.name
            if index_name is not None:
                data.index.rename(index_name.lower(), inplace=True)
            self.data = data
            self.open = pd.Series(data.open, dtype=np.float64)
            self.high = pd.Series(data.high, dtype=np.float64)
            self.low = pd.Series(data.low, dtype=np.float64)
            self.close = pd.Series(data.close, dtype=np.float64)
            self.atr = int(ta_table["atr_p"])
            self.atrm = float(ta_table["atr_m"])
            self.subhag = int(ta_table["linear"])
            self.smooth = int(ta_table["smooth"])
            self.ema = int(ta_table["ema"])
            self.rsi = int(ta_table["rsi"])
            self.aol = int(ta_table["aol"])
            self.pivot = int(ta_table["pivot"])
            self.length = len(data.index)
        else:
            raise AttributeError("DataFrame No columns!")

    def swing_low(self):
        """calculate swing low price with given data"""
        return MIN(self.low, self.pivot)

    def swing_high(self):
        """calculate swing high price with given data"""
        return MAX(self.high, self.pivot)

    def andean(self):
        """calculate Andean Oscillator.
        tradingview.
        :https://www.tradingview.com/script/x9qYvBYN-Andean-Oscillator/
        Then we need bull and bear component
        C = close , O = open
        up1 := nz(math.max(C, O, up1[1] - (up1[1] - C) * alpha), C)
        up2 := nz(math.max(C * C, O * O, up2[1] - (up2[1] - C * C) * alpha), C * C)
        dn1 := nz(math.min(C, O, dn1[1] + (C - dn1[1]) * alpha), C)
        dn2 := nz(math.min(C * C, O * O, dn2[1] + (C * C - dn2[1]) * alpha), C * C)
        //Components
        bull = math.sqrt(dn2 - dn1 * dn1)
        bear = math.sqrt(up2 - up1 * up1)
        """

        alpha = 2 / (self.aol + 1)
        Close = pd.Series(self.close, dtype=np.float64)
        Open = pd.Series(self.open, dtype=np.float64)
        up2 = np.full(self.length, np.nan)
        up1 = np.full(self.length, np.nan)
        dn1 = np.full(self.length, np.nan)
        dn2 = np.full(self.length, np.nan)
        cBull = np.full(self.length, np.nan)
        cBear = np.full(self.length, np.nan)
        for i in range(2, self.length):
            up11 = max(
                Close[i], Open[i], up1[i - 1] - (up1[i - 1] - Close[i]) * alpha
            )
            up22 = max(
                Close[i] ** 2,
                Open[i] ** 2,
                up2[i - 1] - (up2[i - 1] - Close[i] ** 2) * alpha,
            )
            dn11 = min(
                Close[i], Open[i], dn1[i - 1] + (Close[i] - dn1[i - 1]) * alpha
            )
            dn22 = min(
                Close[i] ** 2,
                Open[i] ** 2,
                dn2[i - 1] + (Close[i] ** 2 - dn2[i - 1]) * alpha,
            )
            up11 = up1[i] = up11 if pd.notnull(up11) else Close[i]
            up22 = up2[i] = up22 if pd.notnull(up22) else Close[i] ** 2
            dn11 = dn1[i] = dn11 if pd.notnull(dn11) else Close[i]
            dn22 = dn2[i] = dn22 if pd.notnull(dn22) else Close[i] ** 2
            cBull[i] = math.sqrt(abs(dn22 - (dn11**2)))
            cBear[i] = math.sqrt(abs(up22 - (up11**2)))
        return cBull, cBear

    # AlphaTrend
    def alPhaT(self):
        """AlphaTrend strategy.
        tradingview.
        :https://www.tradingview.com/script/o50NYLAZ-AlphaTrend/
        """
        Close = self.close
        alpha = pd.Series(np.full(self.length, np.nan), index=Close.index)
        High = self.high
        Low = self.low
        atr = SMA(TRANGE(High, Low, Close), self.atr)
        rsi = RSI(Close, self.rsi)
        dnT = High + (atr * self.atrm)
        upT = Low - (atr * self.atrm)
        for i in range(1, self.length):
            if rsi[i] >= 50:
                if upT[i] < (alpha[i - 1] if pd.notnull(alpha[i - 1]) else 0):
                    alpha[i] = alpha[i - 1] if pd.notnull(alpha[i - 1]) else 0
                else:
                    alpha[i] = upT[i]
            else:
                if dnT[i] > (alpha[i - 1] if pd.notnull(alpha[i - 1]) else 0):
                    alpha[i] = alpha[i - 1] if pd.notnull(alpha[i - 1]) else 0
                else:
                    alpha[i] = dnT[i]
        return alpha.shift(2)

    def vxma_(self):
        """
        Core strategy that calculate VXMA
        """
        vxma = pd.Series(np.full(self.length, np.nan), index=self.data.index)
        Close = pd.Series(self.close, dtype=np.float64)
        component = pd.DataFrame(columns=["ema", "linear", "alpha"])
        component["ema"] = EMA(Close, self.ema)
        component["linear"] = EMA(LINEARREG(Close, self.subhag), self.smooth)
        component["alpha"] = self.alPhaT()
        cBull, cBear = self.andean()
        clohi = component.max(axis=1)
        clolo = component.min(axis=1)
        for i in range(2, self.length):
            if cBull[i] > cBear[i]:
                if clolo[i] < (vxma[i - 1] if pd.notnull(vxma[i - 1]) else 0):
                    vxma[i] = vxma[i - 1] if pd.notnull(vxma[i - 1]) else 0
                else:
                    vxma[i] = clolo[i]
            elif cBull[i] < cBear[i]:
                if clohi[i] > (vxma[i - 1] if pd.notnull(vxma[i - 1]) else 0):
                    vxma[i] = vxma[i - 1] if pd.notnull(vxma[i - 1]) else 0
                else:
                    vxma[i] = clohi[i]
            else:
                vxma[i] = vxma[i - 1] if pd.notnull(vxma[i - 1]) else 0
        return vxma

    def checkForSignal(self):
        """
        check for signal with calculated data.
        """
        preBuy = np.full(self.length, np.nan)
        preSell = np.full(self.length, np.nan)
        buyPrice = np.full(self.length, np.nan)
        sellPrice = np.full(self.length, np.nan)
        slPrice = np.full(self.length, np.nan)
        isSL = np.full(self.length, 0)
        BUY = np.full(self.length, 0)
        SELL = np.full(self.length, 0)
        trend = np.full(self.length, np.nan)
        vxma_ = self.data["vxma"]
        Close = self.close
        High = self.high
        Low = self.low
        lowest = self.data["lowest"]
        highest = self.data["highest"]
        TRENDL = np.full(self.length, np.nan)
        for i in range(2, self.length):
            # Get trend True = Bull False = Bear
            if vxma_[i] > vxma_[i - 1] and vxma_[i - 1] > vxma_[i - 2]:
                trend[i] = 1
            elif vxma_[i] < vxma_[i - 1] and vxma_[i - 1] < vxma_[i - 2]:
                trend[i] = 0
            else:
                if trend[i - 1] == 1 and Low[i] < slPrice[i - 1]:
                    trend[i] = np.nan
                    isSL[i] = 1
                elif trend[i - 1] == 0 and High[i] > slPrice[i - 1]:
                    trend[i] = np.nan
                    isSL[i] = 1
                else:
                    trend[i] = trend[i - 1]
            if trend[i - 1] == 1:
                slPrice[i] = slPrice[i - 1]
            elif trend[i - 1] == 0:
                slPrice[i] = slPrice[i - 1]
            else:
                slPrice[i] = np.nan
            # if trend change get pre-signal
            if trend[i] != 1 and trend[i - 1] == 1 and isSL[i] != 1:
                preBuy[i] = 0
                preSell[i] = 1
                TRENDL[i] = Low[i]
            elif trend[i] == 1 and trend[i - 1] != 1 and isSL[i] != 1:
                preBuy[i] = 1
                preSell[i] = 0
                TRENDL[i] = High[i]
            else:
                preBuy[i] = 0
                preSell[i] = 0
            # if close is above cloud is buy signal
            if (
                Close[i] > vxma_[i]
                and (preBuy[i] == 1 or preBuy[i - 1] == 1)
                and (BUY[i - 1] != 1)
            ):
                BUY[i] = 1
                buyPrice[i] = Close[i]
                slPrice[i] = lowest[i - 1]
            elif (
                Close[i] < vxma_[i]
                and (preSell[i] == 1 or preSell[i - 1] == 1)
                and (SELL[i - 1] != 1)
            ):
                SELL[i] = 1
                sellPrice[i] = Close[i]
                slPrice[i] = highest[i - 1]
            else:
                BUY[i] = 0
                SELL[i] = 0

        self.data["trend"] = trend
        self.data["BUY"] = BUY
        self.data["buyPrice"] = buyPrice
        self.data["SELL"] = SELL
        self.data["sellPrice"] = sellPrice
        self.data["isSL"] = isSL
        self.data["SLPRICE"] = slPrice
        self.data["TRENDL"] = TRENDL
        return self.data

    def indicator(self):
        self.data["vxma"] = self.vxma_()
        self.data["lowest"] = self.swing_low()
        self.data["highest"] = self.swing_high()
        self.data = self.checkForSignal()
        return self.data


vxma.__doc__ = """VXMA (vxma)
VXMA is an overlap indicator. It is used to help identify
trend, setting stop loss, identify support and resistance,
and aim to avoid drawdown on sideway condition,
and/or generate buy & sell signals.

Args:
    open (pd.Series): Series of 'open's
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    atr length (int) : length for ATR calculation. Default: 12
    atr_m multiplier (float): Coefficient for
        upper(upT) and lower(dnT) band distance to
        midrange. Default: 1.6
    ema length (int) : length for EMA calculation. Default: 30
    rsi length (int) : length for RSI calculation. Default: 25
    linreg length (int) : length for LENREG calculation. Default: 30
    smoot length (int) : length for SMOOTH calculation. Default: 30
    aol length (int) : length for ANDEAN oscillator calculation. Default: 30

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: vxma (vxma),
                  trend (trend),
                  BUY (long),
                  SELL (short),
                  columns.

Sources:
    tradingview.
    :https://www.tradingview.com/script/m54nptt2-VXMA-Bot/
    :https://www.tradingview.com/script/o50NYLAZ-AlphaTrend/
    :https://www.tradingview.com/script/x9qYvBYN-Andean-Oscillator/

Calculation:
    Default Inputs:
        atr length=12, multiplier=1.6
        ema length=30, rsi = 25
        linreg length=30, smooth=30
        andean oscillator=30
    Default Direction:
    Set to 0 or no-trend at start

    Start with Alphatrend
    dnT = High + atr * atrm
    upT = Low - atr * atrm
    if rsi[i] >= 50:
        if ( upT[i] < alpha[i - 1]
            if alpha[i - 1] is not np.nan
            else 0):
            alpha[i] = ( alpha[i - 1] if alpha[i - 1] is not np.nan else 0)
        else:
            alpha[i] = upT[i]
    else:
        if ( dnT[i] > alpha[i - 1]
            if alpha[i - 1] is not np.nan
            else 0):
            alpha[i] = ( alpha[i - 1] if alpha[i - 1] is not np.nan else 0)
        else:
            alpha[i] = dnT[i]

    Then we need bull and bear component
    C = close , O = open
    up1 := nz(math.max(C, O, up1[1] - (up1[1] - C) * alpha), C)
    up2 := nz(math.max(C * C, O * O, up2[1] - (up2[1] - C * C) * alpha), C * C)
    dn1 := nz(math.min(C, O, dn1[1] + (C - dn1[1]) * alpha), C)
    dn2 := nz(math.min(C * C, O * O, dn2[1] + (C * C - dn2[1]) * alpha), C * C)
    //Components
    bull = math.sqrt(dn2 - dn1 * dn1)
    bear = math.sqrt(up2 - up1 * up1)

    Finally we can calculate vxma
    clohi = max(ema[i], linreg[i], alphatrend[i - 2])
    clolo = min(ema[i], linreg[i], alphatrend[i - 2])
    if bull[i] > bear[i]:
        if clolo < ( vxma[i - 1] if vxma[i - 1] is not np.nan else 0):
            vxma[i] = ( vxma[i - 1] if vxma[i - 1] is not np.nan else 0)
        else:
            vxma[i] = clolo
    elif bull[i] < bear[i]:
        if clohi > ( vxma[i - 1] if vxma[i - 1] is not np.nan else 0):
            vxma[i] = ( vxma[i - 1] if vxma[i - 1] is not np.nan else 0)
        else:
            vxma[i] = clohi
    else:
        vxma[i] = vxma[i - 1] if vxma[i - 1] is not np.nan else 0
"""
