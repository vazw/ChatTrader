import asyncio
from datetime import datetime
from random import choice
import os
import pandas as pd
import sqlite3
import json
import ccxt.async_support as ccxt
from telegram import (
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.AppData import HELP_MESSAGE, WELCOME_MESSAGE, split_list
from src.AppData.Appdata import (
    REPLY_MARKUP,
    TA_TYPE,
    EGGS,
    AppConfig,
    TATable,
    bot_setting,
    candle,
    write_trade_record,
    edit_all_trade_record,
    vxma_settings,
    vxma_settings_info,
    chat,
    remove_last_line_from_string,
    caculate_margin,
)
from src.Bot import BotTrade
from src.CCXT_Binance import (
    Binance,
    get_order_id,
)
import warnings

warnings.filterwarnings("ignore")

## Constanc represent ConversationHandler step
## TRADE HANDLER
T_SYMBOL, T_LEV, T_AMT, T_PRICE, T_TP, T_SL = range(6)
## API MENU
STEP1_API, STEP2_API_SEC = range(6, 8)
## BotSetting
B_RISK, B_MIN_BL, B_SYMBOL = range(8, 11)
## Position Settings
P_LEV, P_TP, P_SL, SETTING_STATE = range(11, 15)


class Telegram:
    def __init__(self, token: str):
        self.Token = token
        self.application = ApplicationBuilder().token(self.Token).build()
        self.binance_ = Binance()
        self.chat_id = 0
        self.msg_id = []
        self.ask_msg_id = []
        self.uniq_msg_id = []
        self.position_tp_sl_order = []
        self.status_bot = False
        self.status_scan = False

        self.risk = {"max_risk": 50.0, "min_balance": 10.0}
        self.trade_reply_text = ":"
        self.coin_pnl_reply_text = ""
        self.pnl_reply = ""
        self.trade_reply_margin = ""
        self.risk_reply_text = ":"
        self.watchlist_reply_text = ":"
        self.coins_settings_key = ""
        self.vxma_settings_selected_state = ""
        self.vxma_menu_selected_state = ""
        self.trade_menu_selected = ""
        self.trade_order = {}
        self.sec_info = {
            "API_KEY": "",
            "API_SEC": "",
            "PASS": "",
        }
        self.vxma_settings = vxma_settings
        self.dynamic_reply_markup = {}
        self.reply_markup = REPLY_MARKUP
        self.bot_trade = BotTrade(self.chat_id, self.status_bot, self.status_scan)

        # Buttons at the bottom
        self.reply_key = ReplyKeyboardMarkup(
            [
                [
                    KeyboardButton("/menu"),
                    KeyboardButton("/clear"),
                    KeyboardButton("/help"),
                ]
            ],
            resize_keyboard=True,
        )
        self.pnl_back_button = [
            [
                InlineKeyboardButton(
                    "❌ กลับ",
                    callback_data="{'M': 'PNLC', 'H' :'BACK_TO_MENU'}",
                )
            ]
        ]
        self.load_database()

    def reset_conversation(self):
        self.conversation = [
            {
                "role": "system",
                "content": "You're an Inverstor Expert who can always excute the right\
method to make great profit in Cryptocurrency Markets",
            },
            {
                "role": "user",
                "content": "This is the list of BITCOIN  Daily Closed Price in Dollars in the past month\
28286.7, 28395.9, 29459.0, 29300.0, 29212.7, 29223.0, 28054.4, 28656.5, \
29018.4, 28826.0, 29491.5, 28837.8, 28419.4, 27659.8, 27610.2, 27582.9, \
26956.4, 26785.1, 26762.7, 26901.9, 27152.5, 27024.8, 27395.8, 26809.3, \
26870.1, 27089.5, 26732.8, 26840.2, 27209.9, 26313.8",
            },
            {"role": "user", "content": "BITCOIN now cost 26325.94$"},
        ]

    def update_inline_keyboard(self):
        trade = [
            [
                InlineKeyboardButton(
                    f"Order Type: {self.trade_order['type']}",
                    callback_data='{"M": "trade", "H": "Type"}',
                ),
                InlineKeyboardButton(
                    f"Leverage: X{self.trade_order['lev']}",
                    callback_data='{"M": "trade", "H": "Lev"}',
                ),
            ],
            [
                InlineKeyboardButton(
                    f"ราคา : {self.trade_order['price']}",
                    callback_data='{"M": "trade", "H": "Price"}',
                ),
            ],
            [
                InlineKeyboardButton(
                    "-",
                    callback_data='{"M": "trade", "H": "-"}',
                ),
                InlineKeyboardButton(
                    f"จำนวน : {self.trade_order['amt'] if self.trade_order['amt'] > 0.0 else '--.--'}",
                    callback_data='{"M": "trade", "H": "Amt"}',
                ),
                InlineKeyboardButton(
                    "+",
                    callback_data='{"M": "trade", "H": "+"}',
                ),
            ],
            [
                InlineKeyboardButton(
                    f"TP : {self.trade_order['tp_price'] if self.trade_order['tp_price'] > 0.0 else '--.--'}",
                    callback_data='{"M": "trade", "H": "TP"}',
                ),
            ],
            [
                InlineKeyboardButton(
                    f"SL : {self.trade_order['sl_price'] if self.trade_order['sl_price'] > 0.0 else '--.--'}",
                    callback_data='{"M": "trade", "H": "SL"}',
                ),
            ],
            [
                InlineKeyboardButton(
                    "LONG 📈",
                    callback_data='{"M": "trade", "H": "LONG"}',
                ),
                InlineKeyboardButton(
                    "📉 SHORT",
                    callback_data='{"M": "trade", "H": "SHORT"}',
                ),
            ],
            [
                InlineKeyboardButton(
                    "เปลี่ยนเหรียญ",
                    callback_data='{"M": "trade", "H": "Change"}',
                ),
                InlineKeyboardButton(
                    "❌ กลับ",
                    callback_data='{"M": "trade", "H": "BACK"}',
                ),
            ],
        ]
        position = [
            [
                InlineKeyboardButton(
                    "เพิ่ม TP 🚀",
                    callback_data='{"M": "pos", "H": "TP", "D": 0}',
                ),
                InlineKeyboardButton(
                    "⏹เพิ่ม SL",
                    callback_data='{"M": "pos", "H": "SL", "D": 0}',
                ),
            ],
            [
                InlineKeyboardButton(
                    f"ปิด Postion : {self.trade_order['price']}",
                    callback_data='{"M": "position_", "H": "Close"}',
                ),
            ],
            [
                InlineKeyboardButton(
                    f"Leverage: X{self.trade_order['lev']}",
                    callback_data='{"M": "pos", "H": "Lev"}',
                ),
                InlineKeyboardButton(
                    "❌ กลับ",
                    callback_data='{"M": "position_", "H": "BACK"}',
                ),
            ],
        ]
        if self.trade_order["pnl"] != 0.0:
            trade = [
                [
                    InlineKeyboardButton(
                        "ℹ️ ดูรายละเอียด Position ที่มี",
                        callback_data=json.dumps(
                            {
                                "M": "PNLC",
                                "H": self.trade_order["symbol"],
                            }
                        ),
                    ),
                ]
            ] + trade
        if len(self.position_tp_sl_order) > 0:
            tp_sl = [
                [
                    InlineKeyboardButton(
                        f"{i['type'].upper()} : {i['price']}",
                        callback_data=json.dumps(
                            {
                                "M": "pos",
                                "H": f"{i['type']}".upper(),
                                "D": f"{i['id']}|{i['price']}",
                            }
                        ),
                    )
                ]
                for i in self.position_tp_sl_order
            ]
            position = tp_sl + position
        self.dynamic_reply_markup = {
            "trade": InlineKeyboardMarkup(trade),
            "setting": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            f"BOT STATUS : {'ON 🟢' if self.status_bot else 'OFF 🔴'}",
                            callback_data='{"M": "setting", "H": "BOT"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "ตั้งค่ากลยุทธ์/เหรียญ",
                            callback_data='{"M": "setting", "H": "COINS"}',
                        ),
                        InlineKeyboardButton(
                            f"SCAN : {'ON 🟢' if self.status_scan else 'OFF 🔴'}",
                            callback_data='{"M": "setting", "H": "SCAN"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "ตั้งค่าความเสี่ยง",
                            callback_data='{"M": "setting", "H": "RISK"}',
                        ),
                        InlineKeyboardButton(
                            "⚙️ตั้งค่า API",
                            callback_data='{"M": "secure", "H": "API"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "❌ กลับ",
                            callback_data='{"M": "setting", "H": "BACK"}',
                        ),
                    ],
                ]
            ),
            "risk": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            f"ความเสี่ยงที่รับได้ : {self.risk['max_risk']} $",
                            callback_data='{"M": "risk", "H": "MAX_RISK"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            f"จะหยุดบอทเมื่อเงินเหลือ : {self.risk['min_balance']} $",
                            callback_data='{"M": "risk", "H": "MIN_BALANCE"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "บันทึก💾",
                            callback_data='{"M": "risk", "H": "SAVE"}',
                        ),
                        InlineKeyboardButton(
                            "❌ กลับ",
                            callback_data='{"M": "risk", "H": "BACK"}',
                        ),
                    ],
                ]
            ),
            "position": InlineKeyboardMarkup(position),
            "vxma_settings": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings" , "H": "timeframe", "Type": "str"}',
                            text=f"timeframe : {self.vxma_settings['timeframe']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "hedge", "Type": "bool"}',
                            text=f"hedge : {'ON 🟢' if self.vxma_settings['hedge'] else 'OFF 🔴'}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "hedgeTF", "Type": "str"}',
                            text=f"hedgeTF : {self.vxma_settings['hedgeTF']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "ATR", "Type": "int"}',
                            text=f"ATR : {self.vxma_settings['ATR']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "ATR_m", "Type": "float"}',
                            text=f"ATR_m : {self.vxma_settings['ATR_m']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "Pivot", "Type": "int"}',
                            text=f"Pivot : {self.vxma_settings['Pivot']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "EMA", "Type": "int"}',
                            text=f"EMA : {self.vxma_settings['EMA']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "subhag", "Type": "int"}',
                            text=f"subhag : {self.vxma_settings['subhag']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H" : "smooth", "Type": "int"}',
                            text=f"smooth : {self.vxma_settings['smooth']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "RSI", "Type": "int"}',
                            text=f"RSI : {self.vxma_settings['RSI']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "Andean", "Type": "int"}',
                            text=f"Andean : {self.vxma_settings['Andean']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "leverage", "Type": "int"}',
                            text=f"leverage : {self.vxma_settings['leverage']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "Useshort", "Type": "bool"}',
                            text=f"Useshort : {'ON 🟢' if self.vxma_settings['Useshort'] else 'OFF 🔴'}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H":"UseTP", "Type": "bool"}',
                            text=f"UseTP : {'ON 🟢' if self.vxma_settings['UseTP'] else 'OFF 🔴'}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "UseTP2", "Type": "bool"}',
                            text=f"UseTP2 : {'ON 🟢' if self.vxma_settings['UseTP2'] else 'OFF 🔴'}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "Uselong", "Type": "bool"}',
                            text=f"Uselong : {'ON 🟢' if self.vxma_settings['Uselong'] else 'OFF 🔴'}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "UseSL", "Type": "bool"}',
                            text=f"UseSL : {'ON 🟢' if self.vxma_settings['UseSL'] else 'OFF 🔴'}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "Tail_SL", "Type": "bool"}',
                            text=f"Tail_SL : {'ON 🟢' if self.vxma_settings['Tail_SL'] else 'OFF 🔴'}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "TP1", "Type": "int"}',
                            text=f"TP1 : {self.vxma_settings['TP1']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "RR1", "Type": "float"}',
                            text=f"RR1 : {self.vxma_settings['RR1']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "RR2", "Type": "float"}',
                            text=f"RR2 : {self.vxma_settings['RR2']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "TP2", "Type": "int"}',
                            text=f"TP2 : {self.vxma_settings['TP2']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "Risk", "Type": "str"}',
                            text=f"Risk : {self.vxma_settings['Risk']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "maxMargin, "Type": "str""}',
                            text=f"maxMargin : {self.vxma_settings['maxMargin']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "กราฟ📈",
                            callback_data='{"M": "vxma_settings", "H": "CHART"}',
                        ),
                        InlineKeyboardButton(
                            "💾บันทึก",
                            callback_data='{"M": "vxma_settings", "H": "SAVE"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "ลบ🗑",
                            callback_data='{"M": "vxma_settings", "H": "DELETE"}',
                        ),
                        InlineKeyboardButton(
                            "❌ กลับ",
                            callback_data='{"M": "vxma_settings", "H": "BACK"}',
                        ),
                    ],
                ]
            ),
            "vxma_settings_1": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            f"เหรียญ : {self.vxma_settings['symbol'][:-5]}",
                            callback_data='{"M": "vxma_settings", "H": "symbol", "Type": "str"}',
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings" , "H": "timeframe", "Type": "str"}',
                            text=f"timeframe : {self.vxma_settings['timeframe']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "เทรด💹",
                            callback_data='{"M": "vxma_settings", "H": "TRADE"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "⚙️ตั้งค่ากลยุทธ์",
                            callback_data='{"M": "vxma_settings", "H": "Setting"}',
                        ),
                        InlineKeyboardButton(
                            "❌ กลับ",
                            callback_data='{"M": "vxma_settings", "H": "BACK"}',
                        ),
                    ],
                ]
            ),
            "vxma_settings_2": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings" , "H": "timeframe", "Type": "str"}',
                            text=f"timeframe : {self.vxma_settings['timeframe']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "hedge", "Type": "bool"}',
                            text=f"hedge : {'ON 🟢' if self.vxma_settings['hedge'] else 'OFF 🔴'}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "hedgeTF", "Type": "str"}',
                            text=f"hedgeTF : {self.vxma_settings['hedgeTF']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "ATR", "Type": "int"}',
                            text=f"ATR : {self.vxma_settings['ATR']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "ATR_m", "Type": "float"}',
                            text=f"ATR_m : {self.vxma_settings['ATR_m']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "Pivot", "Type": "int"}',
                            text=f"Pivot : {self.vxma_settings['Pivot']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "EMA", "Type": "int"}',
                            text=f"EMA : {self.vxma_settings['EMA']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "subhag", "Type": "int"}',
                            text=f"subhag : {self.vxma_settings['subhag']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H" : "smooth", "Type": "int"}',
                            text=f"smooth : {self.vxma_settings['smooth']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "RSI", "Type": "int"}',
                            text=f"RSI : {self.vxma_settings['RSI']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "Andean", "Type": "int"}',
                            text=f"Andean : {self.vxma_settings['Andean']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "leverage", "Type": "int"}',
                            text=f"leverage : {self.vxma_settings['leverage']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "Useshort", "Type": "bool"}',
                            text=f"Useshort : {'ON 🟢' if self.vxma_settings['Useshort'] else 'OFF 🔴'}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H":"UseTP", "Type": "bool"}',
                            text=f"UseTP : {'ON 🟢' if self.vxma_settings['UseTP'] else 'OFF 🔴'}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "UseTP2", "Type": "bool"}',
                            text=f"UseTP2 : {'ON 🟢' if self.vxma_settings['UseTP2'] else 'OFF 🔴'}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "Uselong", "Type": "bool"}',
                            text=f"Uselong : {'ON 🟢' if self.vxma_settings['Uselong'] else 'OFF 🔴'}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "UseSL", "Type": "bool"}',
                            text=f"UseSL : {'ON 🟢' if self.vxma_settings['UseSL'] else 'OFF 🔴'}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "Tail_SL", "Type": "bool"}',
                            text=f"Tail_SL : {'ON 🟢' if self.vxma_settings['Tail_SL'] else 'OFF 🔴'}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "TP1", "Type": "int"}',
                            text=f"%TP1 : {self.vxma_settings['TP1']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "RR1", "Type": "float"}',
                            text=f"RR1 : {self.vxma_settings['RR1']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "Risk", "Type": "str"}',
                            text=f"Risk : {self.vxma_settings['Risk']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "TP2", "Type": "int"}',
                            text=f"%TP2 : {self.vxma_settings['TP2']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "RR2", "Type": "float"}',
                            text=f"RR2 : {self.vxma_settings['RR2']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"M": "vxma_settings", "H": "maxMargin, "Type": "str""}',
                            text=f"maxMargin : {self.vxma_settings['maxMargin']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "กราฟ📈",
                            callback_data='{"M": "vxma_settings", "H": "CHART"}',
                        ),
                        InlineKeyboardButton(
                            "เปลี่ยนเหรียญ",
                            callback_data='{"M": "vxma_settings", "H": "symbol", "Type": "str"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "เพิ่มตั้งค่านี้ไปยังบอท💾",
                            callback_data='{"M": "vxma_settings", "H": "SAVE_ADD"}',
                        ),
                        InlineKeyboardButton(
                            "❌ กลับ",
                            callback_data='{"M": "vxma_settings", "H": "BACK_2"}',
                        ),
                    ],
                ]
            ),
        }

    def load_database(self) -> None:
        config = AppConfig()
        self.risk["max_risk"] = config.max_margin
        self.risk["min_balance"] = config.min_balance

    def reset_trade_order_data(self) -> None:
        self.trade_order = {
            "symbol": "",
            "type": "MARKET",
            "side": "BOTH",
            "new_lev": 10,
            "lev": 50,
            "e_price": 0.0,
            "price": 0.0,
            "min_amt": 0.0,
            "amt": 0.0,
            "margin": 0.0,
            "pnl": 0.0,
            "tp": False,
            "tp_id": 0,
            "tp_price": 0.0,
            "new_tp_price": 0.0,
            "sl": False,
            "sl_id": 0,
            "sl_price": 0.0,
            "new_sl_price": 0.0,
        }

    def setup_bot(self) -> None:
        # Basic Commands
        self.reset_conversation()
        self.reset_trade_order_data()
        self.update_inline_keyboard()

        default_handlers = [
            CommandHandler("start", self.start),
            CommandHandler("help", self.help_command),
            CommandHandler("menu", self.menu_command),
            CommandHandler("clear", self.clear_command),
            # Handler for Back to menu for all menu
            CallbackQueryHandler(
                self.back_to_menu,
                lambda x: (eval(x))["M"] in ["fiat", "pnl", "setting", "secure"]
                and (eval(x))["H"] == "BACK",
            ),
        ]

        main_menu_handlers = [
            # Handlers set for buttons workarounds.
            CallbackQueryHandler(self.button_menu, lambda x: (eval(x))["M"] == "menu"),
            CallbackQueryHandler(self.fiat_handler, lambda x: (eval(x))["M"] == "fiat"),
            CallbackQueryHandler(
                self.setting_handler, lambda x: (eval(x))["M"] == "setting"
            ),
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.analyse_handler, lambda x: (eval(x))["M"] == "analyse"
                    )
                ],
                states={
                    SETTING_STATE: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            self.analyse_get_symbol,
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.back_to_analyse_menu)],
            ),
        ]

        # trade_handler
        trade_menu_handlers = [
            # symbol
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.get_symbol_handler,
                        lambda x: (eval(x))["M"] == "menuex"
                        and (eval(x))["H"] == "Trade",
                    )
                ],
                states={
                    T_SYMBOL: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, self.update_trade_symbol
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.back_to_menu)],
            ),
            # Edit symbol
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.get_symbol_handler,
                        lambda x: (eval(x))["M"] == "trade"
                        and (eval(x))["H"] == "Change",
                    )
                ],
                states={
                    T_SYMBOL: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, self.update_trade_symbol
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.back_to_trade_menu)],
            ),
            # Leverage
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.get_lev_handler,
                        lambda x: (eval(x))["M"] == "trade" and (eval(x))["H"] == "Lev",
                    )
                ],
                states={
                    T_LEV: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, self.update_trade_lev
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.back_to_trade_menu)],
            ),
            # amount
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.get_amount_handler,
                        lambda x: (eval(x))["M"] == "trade" and (eval(x))["H"] == "Amt",
                    )
                ],
                states={
                    T_AMT: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, self.update_trade_amt
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.back_to_trade_menu)],
            ),
            # TP price
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.get_tp_price_handler,
                        lambda x: (eval(x))["M"] == "trade" and (eval(x))["H"] == "TP",
                    )
                ],
                states={
                    T_TP: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, self.update_trade_tp_price
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.back_to_trade_menu)],
            ),
            # SL price
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.get_sl_price_handler,
                        lambda x: (eval(x))["M"] == "trade" and (eval(x))["H"] == "SL",
                    )
                ],
                states={
                    T_SL: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, self.update_trade_sl_price
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.back_to_trade_menu)],
            ),
            CallbackQueryHandler(
                self.trade_order_type,
                lambda x: (eval(x))["M"] == "trade" and (eval(x))["H"] == "Type",
            ),
            CallbackQueryHandler(
                self.trade_order_type_handler,
                lambda x: (eval(x))["M"] == "order_type",
            ),
            # Long Buttons
            CallbackQueryHandler(
                self.trade_long_button,
                lambda x: (eval(x))["M"] == "trade" and (eval(x))["H"] == "LONG",
            ),
            # # Short Buttons
            CallbackQueryHandler(
                self.trade_short_button,
                lambda x: (eval(x))["M"] == "trade" and (eval(x))["H"] == "SHORT",
            ),
            # BACK
            CallbackQueryHandler(
                self.back_from_trade_menu,
                lambda x: (eval(x))["M"] == "trade" and (eval(x))["H"] == "BACK",
            ),
            # + - buttons
            CallbackQueryHandler(
                self.trade_amount_plus_minus,
                lambda x: (eval(x))["M"] == "trade"
                and (eval(x))["H"] == "+"
                or (eval(x))["H"] == "-",
            ),
        ]

        position_pnl_handlers = [
            # confirm buttons
            CallbackQueryHandler(
                self.position_confirm_lev,
                lambda x: (eval(x))["M"] == "position_confirm_lev",
            ),
            CallbackQueryHandler(
                self.position_confirm_sl,
                lambda x: (eval(x))["M"] == "position_confirm_sl",
            ),
            CallbackQueryHandler(
                self.position_confirm_tp,
                lambda x: (eval(x))["M"] == "position_confirm_tp",
            ),
            # Symbols
            CallbackQueryHandler(
                self.info_pnl_per_coin,
                lambda x: (eval(x))["M"] == "PNLC",
            ),
            # back from info_pnl_per_coin
            CallbackQueryHandler(
                self.show_position_coins_menu,
                lambda x: (eval(x))["M"] == "position_" and (eval(x))["H"] == "BACK",
            ),
            # edit symbol fot pnl
            CallbackQueryHandler(
                self.show_position_coins_menu,
                lambda x: (eval(x))["M"] == "pnl" and (eval(x))["H"] == "COINS",
            ),
            # ClosePosition
            CallbackQueryHandler(
                self.position_close_handler,
                lambda x: (eval(x))["M"] == "position_" and (eval(x))["H"] == "Close",
            ),
            # edit TP,SL,Leverage Handlers
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.position_get_tp_price_handler,
                        lambda x: (eval(x))["M"] == "pos" and (eval(x))["H"] == "TP",
                    )
                ],
                states={
                    P_TP: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            self.position_update_trade_tp_price,
                        )
                    ],
                },
                fallbacks=[
                    CommandHandler("cancel", self.back_to_show_position_coins_menu)
                ],
            ),
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.position_get_sl_price_handler,
                        lambda x: (eval(x))["M"] == "pos" and (eval(x))["H"] == "SL",
                    )
                ],
                states={
                    P_SL: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            self.position_update_trade_sl_price,
                        )
                    ],
                },
                fallbacks=[
                    CommandHandler("cancel", self.back_to_show_position_coins_menu)
                ],
            ),
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.position_get_lev_handler,
                        lambda x: (eval(x))["M"] == "pos" and (eval(x))["H"] == "Lev",
                    )
                ],
                states={
                    P_LEV: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            self.position_update_trade_lev,
                        )
                    ],
                },
                fallbacks=[
                    CommandHandler("cancel", self.back_to_show_position_coins_menu)
                ],
            ),
        ]

        # Setting Handler
        bot_setting_handlers = [
            # Risk
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.get_max_risk_handler,
                        lambda x: (eval(x))["M"] == "risk"
                        and (eval(x))["H"] == "MAX_RISK",
                    )
                ],
                states={
                    B_RISK: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, self.update_max_risk
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.back_to_risk_menu)],
            ),
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.get_min_balance_handler,
                        lambda x: (eval(x))["M"] == "risk"
                        and (eval(x))["H"] == "MIN_BALANCE",
                    )
                ],
                states={
                    B_MIN_BL: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, self.update_min_balance
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.back_to_risk_menu)],
            ),
            CallbackQueryHandler(
                self.save_risk_to_db,
                lambda x: (eval(x))["M"] == "risk" and (eval(x))["H"] == "SAVE",
            ),
            CallbackQueryHandler(
                self.back_from_risk_menu,
                lambda x: ((eval(x))["M"] == "risk" or (eval(x))["M"] == "COINS")
                and (eval(x))["H"] == "BACK",
            ),
            ## TODO add symbols handler for setting
            CallbackQueryHandler(
                self.edit_config_per_coin,
                lambda x: (eval(x))["M"] == "COINS",
            ),
            # CallbackQueryHandler(
            #     self.vxma_settings_handler,
            #     lambda x: (eval(x))["M"] == "vxma_settings",
            # ),
            CallbackQueryHandler(
                self.vxma_save_settings_confirm,
                lambda x: (eval(x))["M"] == "vxma_settings_confirm_save",
            ),
            CallbackQueryHandler(
                self.vxma_save_settings_confirm_2,
                lambda x: (eval(x))["M"] == "vxma_settings_confirm_save_2",
            ),
            CallbackQueryHandler(
                self.vxma_del_settings_confirm,
                lambda x: (eval(x))["M"] == "vxma_settings_confirm_del",
            ),
            # entry_points=[
            #     CallbackQueryHandler(
            #         self.vxma_edit_settings_confirm,
            #         lambda x: (eval(x))["M"] == "vxma_settings_confirm",
            #     )
            # ],
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.vxma_settings_handler,
                        lambda x: (eval(x))["M"] == "vxma_settings",
                    )
                ],
                states={
                    SETTING_STATE: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, self.vxma_get_settings
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.back_to_vxma_settings)],
            ),
        ]

        # secure_handler
        api_setting_handlers = [
            # API
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.set_api_handler,
                        lambda x: (eval(x))["M"] == "secure"
                        and (eval(x))["H"] == "API",
                    )
                ],
                states={
                    STEP1_API: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, self.get_api_key
                        )
                    ],
                    STEP2_API_SEC: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, self.get_api_sec
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.back_to_secure_menu)],
            ),
        ]

        # Add all Handlers.
        self.application.add_handlers(default_handlers)
        self.application.add_handlers(main_menu_handlers)
        self.application.add_handlers(position_pnl_handlers)
        self.application.add_handlers(trade_menu_handlers)
        self.application.add_handlers(bot_setting_handlers)
        self.application.add_handlers(api_setting_handlers)

        # Talking bot.
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.echo)
        )
        # Handler for unknown commands at the last handler
        self.application.add_handler(MessageHandler(filters.COMMAND, self.unknown))

        # Running Background job.
        self.application.job_queue.run_once(self.make_bot_task, when=5)
        self.application.job_queue.run_once(self.clear_task, when=10)

        self.application.run_polling()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sends a message with three Keyboard buttons attached."""
        self.chat_id = update.effective_chat.id
        self.bot_trade.update_chat_id(self.chat_id)
        await context.bot.delete_message(
            chat_id=self.chat_id, message_id=update.message.message_id
        )

        await update.message.reply_text(WELCOME_MESSAGE, reply_markup=self.reply_key)

    async def clear_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        self.msg_id.append(update.message.message_id)
        self.reset_conversation()
        delete_list = self.uniq_msg_id + self.msg_id + self.ask_msg_id
        if len(delete_list) > 0:
            for id in delete_list:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
            self.uniq_msg_id.clear()
            self.msg_id.clear()
            self.ask_msg_id.clear()

        msg = await update.message.reply_text("Cleared!!")
        self.msg_id.append(msg.message_id)

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ) -> None:
        """Displays info on how to use the bot."""
        msg = await update.message.reply_text(HELP_MESSAGE)
        self.uniq_msg_id.append(msg.message_id)
        await context.bot.delete_message(
            chat_id=self.chat_id, message_id=update.message.message_id
        )

    async def unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="ขออภัยค่ะนายท่าน ดิฉันไม่เข้าใจคำสั่งที่ท่านสื่อ",
        )
        self.uniq_msg_id.append(msg.message_id)

    ## Main Menu Nesting
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sends a message with three inline buttons attached."""
        await context.bot.delete_message(
            chat_id=self.chat_id, message_id=update.message.message_id
        )
        msg = await update.message.reply_text(
            "🙏ยินดีต้อนรับค่ะนายท่าน นี่คือรายการทั้งหมด\nที่น้องเลขาคนนี้สามารถช่วยนายท่านได้:",
            reply_markup=self.reply_markup["menu"],
        )
        self.uniq_msg_id.append(msg.message_id)

    async def button_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ) -> None:
        """nested respons for each Method on main menu"""
        query = update.callback_query

        await query.answer()
        callback = eval(query.data)
        ## Main menu will be here
        if callback["H"] == "CheckBalance":
            msgs = await query.edit_message_text(
                text="โปรดเลือกกระเป๋าเงินเฟียต",
                reply_markup=self.reply_markup["fiat"],
            )
            await self.binance_.update_balance()
            await self.binance_.disconnect()
            # Trade use different callback
        # elif callback["H"] == "Trade":
        #     msgs = await query.edit_message_text(
        #         text="Please Select Fiat Balance",
        #         reply_markup=self.reply_markup["trade"],
        #     )
        elif callback["H"] == "Analyser":
            msgs = await query.edit_message_text(
                text="โปรดเลือกกลยุทธ์ของท่าน",
                reply_markup=self.reply_markup["analyse"],
            )
        elif callback["H"] == "PositionData":
            msgs = await query.edit_message_text(text="โปรดรอซักครู่...")
            await self.binance_.update_balance()
            await self.binance_.disconnect()
            self.trade_menu_selected = "pnl"
            status = self.binance_.position_data
            if len(status.index) > 0:
                text = [
                    f"{status['positionSide'][i] if status['positionSide'][i] != 'BOTH' else ''} {status['symbol'][i]} จำนวน {status['positionAmt'][i]} P/L {round(status['unrealizedProfit'][i], 3)}$\n"
                    for i in range(len(status.index))
                ]
                self.pnl_reply = "Postion ที่มีการเปิดอยู่\n" + "".join(text)
            else:
                self.pnl_reply = "ไม่มี Postion ที่มีการเปิดอยู่"
            msgs = await query.edit_message_text(
                text=self.pnl_reply,
                reply_markup=self.reply_markup["pnl"],
            )
        elif callback["H"] == "BotSetting":
            text = [
                f"{symbol[:-5]} {tf}\n"
                for id, symbol, tf in self.bot_trade.watchlist  # pyright: ignore
            ]
            text0 = (
                "เหรียญที่ดูอยู่ :\n"
                if len(text) > 0
                else "กดเปิดบอทเพื่อโหลดลิสต์เหรียญ"
            )
            self.watchlist_reply_text = (
                f"{text0}" + "".join(text) + "\n\nโปรดเลือกการตั้งค่า"
            )
            msgs = await query.edit_message_text(
                text=f"{self.watchlist_reply_text}",
                reply_markup=self.dynamic_reply_markup["setting"],
            )
        # elif callback["H"] == "apiSetting":
        #     msgs = await query.edit_message_text(
        #         text="โปรดเลือกการตั้งค่า",
        #         reply_markup=self.reply_markup["secure"],
        #     )
        elif callback["H"] == "X":
            await query.delete_message()
        else:
            msgs = await query.edit_message_text(
                text="Selected again!", reply_markup=self.reply_markup["menu"]
            )
        # Save message_id to delete at the end.
        try:
            self.uniq_msg_id.append(msgs.message_id)
        except Exception:
            # Just pass if "X"
            pass

    async def back_to_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """This Handler can Handle both command and inline button respons"""
        query = update.callback_query
        msg = choice(EGGS)
        if query is not None:
            # For Back Buttons
            await query.answer()
            msgs = await query.edit_message_text(
                text=msg, reply_markup=self.reply_markup["menu"]
            )
            self.uniq_msg_id.append(msgs.message_id)
        else:
            # For Commands cancel
            self.msg_id.append(update.message.message_id)
            await self.delete_unig_messages(context)
            msgs = await update.message.reply_text(
                msg, reply_markup=self.reply_markup["menu"]
            )
            self.uniq_msg_id.append(msgs.message_id)
            return ConversationHandler.END

    ## Fiat Balance menu
    async def fiat_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        """If received CheckBalance Mode
        this is nested Method respon for CheckBalance"""
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("กำลังโหลดข้อมูล...")
        callback = eval(query.data)
        fiat_balance = self.binance_.fiat_balance
        status = self.binance_.position_data
        netunpl = float(
            status["unrealizedProfit"].astype("float64").sum()
            if not status.empty
            else 0.0
        )

        if callback["H"] == "ALL":
            msg = (
                "BUSD"
                + f"\nFree   : {round(fiat_balance['BUSD']['free'],2)}$"
                + f"\nMargin : {round(fiat_balance['BUSD']['used'],2)}$"
                + f"\nTotal  : {round(fiat_balance['BUSD']['total'],2)}$\nUSDT"
                + f"\nFree   : {round(fiat_balance['USDT']['free'],2)}$"
                + f"\nMargin : {round(fiat_balance['USDT']['used'],2)}$"
                + f"\nTotal  : {round(fiat_balance['USDT']['total'],2)}$"
                + f"\nกำไร/ขาดทุน  : {round(netunpl,2)}$"
            )
        elif callback["H"] == "RE":
            await query.edit_message_text("กำลัง Refresh ข้อมูลจาก Exchange")
            await asyncio.gather(
                self.binance_.update_balance(True), self.bot_trade.get_currentmode()
            )
            fiat_balance = self.binance_.fiat_balance
            status = self.binance_.position_data
            netunpl = float(
                status["unrealizedProfit"].astype("float64").sum()
                if not status.empty
                else 0.0
            )
            msg = (
                "BUSD"
                + f"\nFree   : {round(fiat_balance['BUSD']['free'],2)}$"
                + f"\nMargin : {round(fiat_balance['BUSD']['used'],2)}$"
                + f"\nTotal  : {round(fiat_balance['BUSD']['total'],2)}$\nUSDT"
                + f"\nFree   : {round(fiat_balance['USDT']['free'],2)}$"
                + f"\nMargin : {round(fiat_balance['USDT']['used'],2)}$"
                + f"\nTotal  : {round(fiat_balance['USDT']['total'],2)}$"
                + f"\nกำไร/ขาดทุน  : {round(netunpl,2)}$"
            )
        elif callback["H"] == "BUSD":
            msg = (
                "BUSD"
                + f"\nFree   : {round(fiat_balance['BUSD']['free'],2)}$"
                + f"\nMargin : {round(fiat_balance['BUSD']['used'],2)}$"
                + f"\nTotal  : {round(fiat_balance['BUSD']['total'],2)}$"
                + f"\nกำไร/ขาดทุน  : {round(netunpl,2)}$"
            )
        elif callback["H"] == "USDT":
            msg = (
                "USDT"
                + f"\nFree   : {round(fiat_balance['USDT']['free'],2)}$"
                + f"\nMargin : {round(fiat_balance['USDT']['used'],2)}$"
                + f"\nTotal  : {round(fiat_balance['USDT']['total'],2)}$"
                + f"\nกำไร/ขาดทุน  : {round(netunpl,2)}$"
            )
        msgs = await query.edit_message_text(
            text=msg, reply_markup=self.reply_markup["menu"]
        )
        self.uniq_msg_id.append(msgs.message_id)

    ## Trade menu
    async def back_to_trade_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        CommandHandler for get back to trade menu
        """
        self.msg_id.append(update.message.message_id)
        await self.delete_ask_messages(context)
        msgs = await update.message.reply_text(
            self.trade_reply_text + self.trade_reply_margin,
            reply_markup=self.dynamic_reply_markup["trade"],
        )
        self.uniq_msg_id.append(msgs.message_id)
        return ConversationHandler.END

    async def get_symbol_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        """Handler to asks for trade symbol"""
        query = update.callback_query
        await query.answer()
        msg = await query.edit_message_text(
            text="โปรดใส่ชื่อเหรียญ เช่น btcbusd bnbusdt eth xmr\n\n กด /cancel เพื่อยกเลิก"
        )
        self.ask_msg_id.append(msg.message_id)
        return T_SYMBOL

    async def update_trade_symbol(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handler that received trade symbol (STEP1)"""
        respon = update.message.text
        self.msg_id.append(update.message.message_id)
        msg0 = await update.message.reply_text("กำลังโหลดข้อมูลเหรียญ โปรดรอซักครู่")
        self.ask_msg_id.append(msg0.message_id)
        self.reset_trade_order_data()
        self.trade_menu_selected = "trade"
        symbol = respon.upper()
        """TODO"""
        try:
            if ":" in symbol:
                self.trade_order["symbol"] = symbol
            else:
                if symbol.endswith("BUSD") or symbol.endswith("USDT"):
                    quote = "BUSD" if symbol.endswith("BUSD") else "USDT"
                    base = symbol[:-4]
                else:
                    quote = "USDT"
                    base = symbol
                self.trade_order["symbol"] = f"{base}/{quote}:{quote}"
            exchange = await self.binance_.get_exchange()
            self.trade_order["price"] = await self.binance_.get_bidask(
                self.trade_order["symbol"], "bid"
            )
            markets = await exchange.fetchMarkets()
            self.trade_order["min_amt"] = float(
                (
                    data["limits"]["amount"]["min"]
                    for data in markets
                    if data["symbol"] == self.trade_order["symbol"]
                ).__next__()
            )
            if self.trade_order["min_amt"] * self.trade_order["price"] < 5.0:
                self.trade_order["min_amt"] = exchange.amount_to_precision(
                    self.trade_order["symbol"], 6.0 / self.trade_order["price"]
                )
            await self.binance_.update_balance()
            currnet_position = await self.bot_trade.check_current_position(
                self.trade_order["symbol"], self.binance_.position_data.copy()
            )
            await self.binance_.disconnect()
            if currnet_position["leverage"] > 0:
                self.trade_order["lev"] = currnet_position["leverage"]
            text = f"คู่เหรียญ  {self.trade_order['symbol']}\nราคาปัจจุบัน : {self.trade_order['price']}$"
            if currnet_position["long"]["position"]:
                self.trade_order["pnl"] = currnet_position["long"]["pnl"]
                self.trade_order["side"] = "LONG"
                text += f"\n\n ท่านมี Position Long ของ เหรียญนี้อยู่ในมือ\n\
เป็นจำนวน  {round(currnet_position['long']['amount'], 3)} เหรียญ\n\
ใช้ Margin  {round(currnet_position['long']['margin'], 3)}$\n\
กำไร/ขาดทุน {round(currnet_position['long']['pnl'], 3)}$"

            if currnet_position["short"]["position"]:
                self.trade_order["pnl"] = currnet_position["short"]["pnl"]
                self.trade_order["side"] = "SHORT"
                text += f"\n\n และท่านยังมี Position Short ของ เหรียญนี้อยู่ในมือ\n\
เป็นจำนวน  {round(currnet_position['short']['amount'], 3)} เหรียญ\n\
ใช้ Margin  {round(currnet_position['short']['margin'], 3)}$\n\
กำไร/ขาดทุน {round(currnet_position['short']['pnl'], 3)}$"

            self.trade_reply_text = text
            self.update_inline_keyboard()
        except Exception as e:
            text = f"เกิดข้อผิดพลาด {e} ขึ้นกับเหรียญที่ท่านเลือก: {respon} โปรดลองเปลี่ยนเหรียญใหม่อีกครั้งค่ะ"

        msg = await update.message.reply_text(
            text,
            reply_markup=self.dynamic_reply_markup["trade"],
        )
        self.uniq_msg_id.append(msg.message_id)
        await self.delete_ask_messages(context)
        return ConversationHandler.END

    async def get_lev_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        """Handler to asks for trade Leverage"""
        query = update.callback_query
        await query.answer()
        msg = await query.edit_message_text(
            text="โปรดใส่จำนวนตัวคูณ เช่น 1 , 5 , 10 , 20 , 25 , 50 , 100 , 125\n\n กด /cancel เพื่อยกเลิก"
        )
        self.ask_msg_id.append(msg.message_id)
        return T_LEV

    async def update_trade_lev(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handler that received trade amount (STEP1)"""
        respon = update.message.text
        self.msg_id.append(update.message.message_id)
        try:
            self.trade_order["lev"] = int(respon)
            self.update_inline_keyboard()
            margin = caculate_margin(
                self.trade_order["price"],
                self.trade_order["amt"],
                self.trade_order["lev"],
            )

            text = f"\n\nOrder นี้จะใช้ Margin ทั้งหมด: {round(margin, 3)}$"
            self.trade_reply_margin = text

        except Exception as e:
            text = f"\n\nเกิดข้อผิดพลาด {e}\nLeverage ต้องเป็นตัวเลขเท่านั้น โปรดทำรายการใหม่อีกครั้งค่ะ"
        msg = await update.message.reply_text(
            self.trade_reply_text + self.trade_reply_margin + text,
            reply_markup=self.dynamic_reply_markup["trade"],
        )
        self.uniq_msg_id.append(msg.message_id)
        await self.delete_ask_messages(context)
        return ConversationHandler.END

    async def get_amount_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        """Handler to asks for trade amount"""
        query = update.callback_query
        await query.answer()
        msg = await query.edit_message_text(
            text=f"โปรดใส่จำนวนเหรียญ และตรวจสอบทศนิยมให้ดี\nเหรียญนี้ใช้ Size ขั้นต่ำ : {self.trade_order['min_amt']}\n\n กด /cancel เพื่อยกเลิก"
        )
        self.ask_msg_id.append(msg.message_id)
        return T_AMT

    async def update_trade_amt(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handler that received trade amount (STEP1)"""
        respon = update.message.text
        self.msg_id.append(update.message.message_id)
        try:
            self.trade_order["amt"] = abs(float(respon))
            self.update_inline_keyboard()
            margin = caculate_margin(
                self.trade_order["price"],
                self.trade_order["amt"],
                self.trade_order["lev"],
            )

            text = f"\n\nOrder นี้จะใช้ Margin ทั้งหมด: {round(margin, 3)}$"
            self.trade_reply_margin = text
        except Exception as e:
            text = f"เกิดข้อผิดพลาด {e}\nโปรดตรวจสอบเลขทศนิยม หรือจำนวนเหรียญให้ถูกต้องแล้วทำรายการใหม่ค่ะ"
        msg = await update.message.reply_text(
            self.trade_reply_text + text,
            reply_markup=self.dynamic_reply_markup["trade"],
        )
        self.uniq_msg_id.append(msg.message_id)
        await self.delete_ask_messages(context)
        return ConversationHandler.END

    async def get_tp_price_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        """Handler to asks for trade TP Price"""
        query = update.callback_query
        await query.answer()
        msg = await query.edit_message_text(
            text="โปรดใส่ราคา Take Profit \n\n กด /cancel เพื่อยกเลิก"
        )
        self.ask_msg_id.append(msg.message_id)
        return T_TP

    async def update_trade_tp_price(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handler that received trade TP Price (STEP1)"""
        respon = update.message.text
        self.msg_id.append(update.message.message_id)
        try:
            self.trade_order["tp_price"] = float(respon)
            self.trade_order["tp"] = True
            self.update_inline_keyboard()
            text = (
                f"\n\nทำการเพิ่มราคา Take Profit สำเร็จ: {self.trade_order['tp_price']}"
            )
        except Exception as e:
            text = f"เกิดข้อผิดพลาด {e}\nโปรดตรวจสอบเลขทศนิยม หรือราคาเหรียญให้ถูกต้องแล้วทำรายการใหม่ค่ะ"
        msg = await update.message.reply_text(
            self.trade_reply_text + self.trade_reply_margin + text,
            reply_markup=self.dynamic_reply_markup["trade"],
        )
        self.uniq_msg_id.append(msg.message_id)
        await self.delete_ask_messages(context)
        return ConversationHandler.END

    async def get_sl_price_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        """Handler to asks for trade SL Price"""
        query = update.callback_query
        await query.answer()
        msg = await query.edit_message_text(
            text="โปรดใส่ราคา Stop-Loss \n\n กด /cancel เพื่อยกเลิก"
        )
        self.ask_msg_id.append(msg.message_id)
        return T_SL

    async def update_trade_sl_price(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handler that received trade SL Price (STEP1)"""
        respon = update.message.text
        self.msg_id.append(update.message.message_id)
        try:
            self.trade_order["sl_price"] = float(respon)
            self.trade_order["sl"] = True
            self.update_inline_keyboard()
            text = (
                f"\n\nทำการเพิ่มราคา Stop-Loss สำเร็จ: {self.trade_order['sl_price']}"
            )
        except Exception as e:
            text = f"\nเกิดข้อผิดพลาด {e}\nโปรดตรวจสอบเลขทศนิยม หรือราคาเหรียญให้ถูกต้องแล้วทำรายการใหม่ค่ะ"

        msg = await update.message.reply_text(
            self.trade_reply_text + self.trade_reply_margin + text,
            reply_markup=self.dynamic_reply_markup["trade"],
        )
        self.uniq_msg_id.append(msg.message_id)
        await self.delete_ask_messages(context)
        return ConversationHandler.END

    async def trade_order_type(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        msg = "โปรดเลือกประเภทคำสั่งซื้อ-ขาย:"
        msgs = await query.edit_message_text(
            text=msg, reply_markup=self.reply_markup["order_type"]
        )
        self.uniq_msg_id.append(msgs.message_id)

    async def trade_order_type_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["H"] == "BACK":
            msgs = await query.edit_message_text(
                text=self.trade_reply_text + self.trade_reply_margin,
                reply_markup=self.dynamic_reply_markup["trade"],
            )
        else:
            self.trade_order["type"] = f"{callback['H']}"
            self.update_inline_keyboard()
            msgs = await query.edit_message_text(
                text=self.trade_reply_text + self.trade_reply_margin,
                reply_markup=self.dynamic_reply_markup["trade"],
            )
        self.uniq_msg_id.append(msgs.message_id)

    async def trade_long_button(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        async def open_long():
            orderid = get_order_id()
            try:
                await exchange.cancel_all_orders(self.trade_order["symbol"])
                await self.binance_.setleverage(
                    self.trade_order["symbol"], self.trade_order["lev"]
                )
                await exchange.create_market_order(
                    self.trade_order["symbol"],
                    "buy",
                    abs(float(self.trade_order["amt"])),
                    params={
                        "positionSide": self.bot_trade.currentMode.Lside,
                        "newClientOrderId": orderid,
                    },
                )
                await self.binance_.update_balance(force=True)
                self.trade_order["margin"] = caculate_margin(
                    self.trade_order["price"],
                    self.trade_order["amt"],
                    self.trade_order["lev"],
                )
                return f"\n\nรายงานการทำธุรกรรม :\n\
ได้ออกคำสั่งเปิด Long สำหรับ : {self.trade_order['symbol']}\n\
จำนวน : {self.trade_order['amt']}\n\
Leverage: {self.trade_order['lev']}\n\
Margin : {self.trade_order['margin']}"
            except ccxt.InsufficientFunds:
                return "\nข้ออภัยค่ะ ยอดเงินของท่านไม่เพียงพอในการออก Order💸\
    โปรดตรวจสอบ Size โดยระเอียดอีกครั้ง แล้วทำรายการใหม่ ขอบคุณค่ะ🙏"
            except Exception as e:
                return f"\nข้ออภัยค่ะ เกิดข้อพิดพลาดขณะที่บอททำการส่งคำสั่ง Long ได้เกิด Error :{e}"

        async def open_tp_long():
            orderid = get_order_id()
            try:
                orderTP = await exchange.create_order(
                    self.trade_order["symbol"],
                    "TAKE_PROFIT_MARKET",
                    "sell",
                    self.trade_order["amt"],
                    self.trade_order["tp_price"],
                    params={
                        "stopPrice": self.trade_order["tp_price"],
                        "triggerPrice": self.trade_order["tp_price"],
                        "positionSide": self.bot_trade.currentMode.Lside,
                        "newClientOrderId": orderid,
                    },
                )
                return f"\n{orderTP['status']} -> ส่งคำสั่ง Take Profit ที่ {self.trade_order['tp_price']} เรียบร้อยแล้ว"

            except Exception as e:
                return f"\nเกิดข้อผิดพลาดตอนส่งคำสั่ง Take Profit :{e}"

        async def open_sl_long():
            orderid = get_order_id()
            try:
                orderSL = await exchange.create_order(
                    self.trade_order["symbol"],
                    "stop_market",
                    "sell",
                    self.trade_order["amt"],
                    params={
                        "stopPrice": self.trade_order["sl_price"],
                        "positionSide": self.bot_trade.currentMode.Lside,
                        "newClientOrderId": orderid,
                    },
                )
                return f"\n{orderSL['status']} -> ส่งคำสั่ง Stop-Loss ที่ {self.trade_order['sl_price']} เรียบร้อยแล้ว"
            except Exception as e:
                return f"\nเกิดข้อผิดพลาดในการส่งคำสั่ง Stop-Loss :{e}"

        async def close_short():
            orderid = get_order_id()
            try:
                order = await exchange.create_market_order(
                    self.trade_order["symbol"],
                    "buy",
                    abs(position_data["short"]["amount"]),
                    params={
                        "positionSide": self.bot_trade.currentMode.Sside,
                        "newClientOrderId": orderid,
                    },
                )
                await self.binance_.update_balance(force=True)
                pnl = "กำไร" if position_data["short"]["pnl"] > 0.0 else "ขาดทุน"
                return f"\n{order['status']} - ธุรกรรมที่ถูกปิดไป{pnl} : {position_data['short']['pnl']}$"
            except Exception as e:
                return f"\nเกิดข้อผิดพลาดในการปิด Order เดิม :{e}"

        query = update.callback_query
        await query.answer()
        text_repons = ["", "", "", ""]
        await query.edit_message_text("กำลังส่งข้อมูลไปยัง Exchange โปรดรอซักครู่")
        exchange = await self.binance_.get_exchange()
        await self.binance_.connect_loads()
        await self.bot_trade.get_currentmode()
        try:
            self.trade_order["amt"] = exchange.amount_to_precision(
                self.trade_order["symbol"], self.trade_order["amt"]
            )
            await self.bot_trade.get_currentmode()
            position_data = await self.bot_trade.check_current_position(
                self.trade_order["symbol"], self.binance_.position_data.copy()
            )
            if position_data["short"]["position"]:
                text1 = await close_short()
                text_repons[1] = text1
                edit_all_trade_record(
                    datetime.now(),
                    self.trade_order["symbol"],
                    "-",
                    "Short",
                    self.trade_order["price"],
                )
            text0 = await open_long()
            text_repons[0] = text0
            if self.trade_order["tp"]:
                self.trade_order["tp_price"] = exchange.price_to_precision(
                    self.trade_order["symbol"], self.trade_order["tp_price"]
                )
                text2 = await open_tp_long()
                text_repons[2] = text2
            if self.trade_order["sl"]:
                self.trade_order["sl_price"] = exchange.price_to_precision(
                    self.trade_order["symbol"], self.trade_order["sl_price"]
                )
                text3 = await open_sl_long()
                text_repons[3] = text3
            text = "".join(text_repons)
            await self.binance_.disconnect()
            write_trade_record(
                datetime.now(),
                self.trade_order["symbol"],
                "-",
                self.trade_order["amt"],
                self.trade_order["price"],
                "Long",
                self.trade_order["tp_price"] if self.trade_order["tp"] else None,
                self.trade_order["sl_price"] if self.trade_order["sl"] else None,
            )
        except Exception as e:
            text = f"\nเกิดข้อผิดพลาด {e}\n\nโปรดลองส่ง Order อีกครั้งค่ะ"

        await query.edit_message_text(
            self.trade_reply_text + text,
            reply_markup=self.reply_markup["menu"],
        )

    async def trade_short_button(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        async def open_short():
            orderid = get_order_id()
            try:
                await exchange.cancel_all_orders(self.trade_order["symbol"])
                await self.binance_.setleverage(
                    self.trade_order["symbol"], self.trade_order["lev"]
                )
                await exchange.create_market_order(
                    self.trade_order["symbol"],
                    "sell",
                    abs(float(self.trade_order["amt"])),
                    params={
                        "positionSide": self.bot_trade.currentMode.Sside,
                        "newClientOrderId": orderid,
                    },
                )
                self.trade_order["margin"] = caculate_margin(
                    self.trade_order["price"],
                    self.trade_order["amt"],
                    self.trade_order["lev"],
                )
                await self.binance_.update_balance(force=True)
                return f"\n\nรายงานการทำธุรกรรม :\n\
ได้ออกคำสั่งเปิด Short สำหรับ : {self.trade_order['symbol']}\n\
จำนวน : {self.trade_order['amt']}\n\
Leverage: {self.trade_order['lev']}\n\
Margin : {self.trade_order['margin']}"
            except ccxt.InsufficientFunds:
                return "\nข้ออภัยค่ะ ยอดเงินของท่านไม่เพียงพอในการออก Order💸\
    โปรดตรวจสอบ Size โดยระเอียดอีกครั้ง แล้วทำรายการใหม่ ขอบคุณค่ะ🙏"
            except Exception as e:
                return f"\nข้ออภัยค่ะ เกิดข้อพิดพลาดขณะที่บอททำการส่งคำสั่ง Short ได้เกิด Error :{e}"

        async def open_tp_short():
            orderid = get_order_id()
            try:
                orderTP = await exchange.create_order(
                    self.trade_order["symbol"],
                    "TAKE_PROFIT_MARKET",
                    "buy",
                    self.trade_order["amt"],
                    self.trade_order["tp_price"],
                    params={
                        "stopPrice": self.trade_order["tp_price"],
                        "triggerPrice": self.trade_order["tp_price"],
                        "positionSide": self.bot_trade.currentMode.Sside,
                        "newClientOrderId": orderid,
                    },
                )
                return f"\n{orderTP['status']} -> ส่งคำสั่ง Take Profit ที่ {self.trade_order['tp_price']} เรียบร้อยแล้ว"

            except Exception as e:
                return f"\nเกิดข้อผิดพลาดตอนส่งคำสั่ง Take Profit :{e}"

        async def open_sl_short():
            orderid = get_order_id()
            try:
                orderSL = await exchange.create_order(
                    self.trade_order["symbol"],
                    "stop_market",
                    "buy",
                    self.trade_order["amt"],
                    params={
                        "stopPrice": self.trade_order["sl_price"],
                        "positionSide": self.bot_trade.currentMode.Sside,
                        "newClientOrderId": orderid,
                    },
                )
                return f"\n{orderSL['status']} -> ส่งคำสั่ง Stop-Loss ที่ {self.trade_order['sl_price']} เรียบร้อยแล้ว"
            except Exception as e:
                return f"\nเกิดข้อผิดพลาดในการส่งคำสั่ง Stop-Loss :{e}"

        async def close_long():
            orderid = get_order_id()
            try:
                order = await exchange.create_market_order(
                    self.trade_order["symbol"],
                    "sell",
                    abs(position_data["long"]["amount"]),
                    params={
                        "positionSide": self.bot_trade.currentMode.Lside,
                        "newClientOrderId": orderid,
                    },
                )
                await self.binance_.update_balance(force=True)
                pnl = "กำไร" if position_data["long"]["pnl"] > 0.0 else "ขาดทุน"
                return f"\n{order['status']} - ธุรกรรมที่ถูกปิดไป{pnl} : {position_data['long']['pnl']}$"
            except Exception as e:
                return f"\nเกิดข้อผิดพลาดในการปิด Order เดิม :{e}"

        query = update.callback_query
        await query.answer()
        text_repons = ["", "", "", ""]
        await query.edit_message_text("กำลังส่งข้อมูลไปยัง Exchange โปรดรอซักครู่")
        exchange = await self.binance_.get_exchange()
        await self.binance_.connect_loads()
        await self.bot_trade.get_currentmode()
        try:
            self.trade_order["amt"] = exchange.amount_to_precision(
                self.trade_order["symbol"], self.trade_order["amt"]
            )
            await self.bot_trade.get_currentmode()
            position_data = await self.bot_trade.check_current_position(
                self.trade_order["symbol"], self.binance_.position_data.copy()
            )
            if position_data["long"]["position"]:
                text1 = await close_long()
                text_repons[1] = text1
                edit_all_trade_record(
                    datetime.now(),
                    self.trade_order["symbol"],
                    "-",
                    "Long",
                    self.trade_order["price"],
                )
            text0 = await open_short()
            text_repons[0] = text0
            if self.trade_order["tp"]:
                self.trade_order["tp_price"] = exchange.price_to_precision(
                    self.trade_order["symbol"], self.trade_order["tp_price"]
                )
                text2 = await open_tp_short()
                text_repons[2] = text2
            if self.trade_order["sl"]:
                self.trade_order["sl_price"] = exchange.price_to_precision(
                    self.trade_order["symbol"], self.trade_order["sl_price"]
                )
                text3 = await open_sl_short()
                text_repons[3] = text3
            await self.binance_.disconnect()
            text = "".join(text_repons)
            write_trade_record(
                datetime.now(),
                self.trade_order["symbol"],
                "-",
                self.trade_order["amt"],
                self.trade_order["price"],
                "Short",
                self.trade_order["tp_price"] if self.trade_order["tp"] else None,
                self.trade_order["sl_price"] if self.trade_order["sl"] else None,
            )
        except Exception as e:
            text = f"\nเกิดข้อผิดพลาด {e}\n\nโปรดลองส่ง Order อีกครั้งค่ะ"

        await query.edit_message_text(
            self.trade_reply_text + text,
            reply_markup=self.reply_markup["menu"],
        )

    async def trade_amount_plus_minus(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["H"] == "+":
            self.trade_order["amt"] += float(self.trade_order["min_amt"])
        if callback["H"] == "-":
            self.trade_order["amt"] -= float(self.trade_order["min_amt"])
        self.update_inline_keyboard()
        margin = caculate_margin(
            self.trade_order["price"],
            self.trade_order["amt"],
            self.trade_order["lev"],
        )

        text = f"\n\nOrder นี้จะใช้ Margin ทั้งหมด: {round(margin, 3)}$"
        self.trade_reply_margin = text
        await query.edit_message_text(
            self.trade_reply_text + self.trade_reply_margin,
            reply_markup=self.dynamic_reply_markup["trade"],
        )

    async def back_from_trade_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        if self.trade_menu_selected == "vxma_settings_1":
            msgs = await query.edit_message_text(
                text=self.text_reply_bot_setting,
                reply_markup=self.dynamic_reply_markup[self.vxma_menu_selected_state],
            )
        else:
            msgs = await query.edit_message_text(
                text=choice(EGGS),
                reply_markup=self.reply_markup["menu"],
            )

        self.uniq_msg_id.append(msgs.message_id)

    ## Analyser menu
    async def back_to_analyse_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        if query is not None:
            # For Back Buttons
            await query.answer()
            msgs = await query.edit_message_text(
                text="โปรดเลือกกลยุทธ์ของท่าน",
                reply_markup=self.reply_markup["analyse"],
            )
            self.uniq_msg_id.append(msgs.message_id)
        else:
            # For Commands cancel
            self.msg_id.append(update.message.message_id)
            await self.delete_unig_messages(context)
            msgs = await update.message.reply_text(
                text="โปรดเลือกกลยุทธ์ของท่าน",
                reply_markup=self.reply_markup["analyse"],
            )
            self.uniq_msg_id.append(msgs.message_id)
            return ConversationHandler.END

    async def analyse_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ) -> None:
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["H"] == "BACK":
            msgs = await query.edit_message_text(
                text=choice(EGGS), reply_markup=self.reply_markup["menu"]
            )
            self.uniq_msg_id.append(msgs.message_id)
            return ConversationHandler.END
        if callback["H"] == "VXMA":
            msg = await query.edit_message_text(
                text="โปรดกรอกชื่อคู่เทรดที่ท่านต้องการวิเคราะห์\n เช่น btc bnbbusd ethusdt\n\nกด /cancel เพื่อยกเลิก"
            )
            self.ask_msg_id.append(msg.message_id)
            return SETTING_STATE

    async def vxma_send_candle_pic(self, update):
        ta_data = TATable(
            atr_p=self.vxma_settings["ATR"],
            atr_m=self.vxma_settings["ATR_m"],
            ema=self.vxma_settings["EMA"],
            linear=self.vxma_settings["subhag"],
            smooth=self.vxma_settings["smooth"],
            rsi=self.vxma_settings["RSI"],
            aol=self.vxma_settings["Andean"],
            pivot=self.vxma_settings["Pivot"],
        )
        df = await self.bot_trade.bot_3(
            self.vxma_settings["symbol"],
            ta_data.__dict__,
            self.vxma_settings["timeframe"],
        )
        path = candle(df, self.vxma_settings["symbol"], self.vxma_settings["timeframe"])
        msgs0 = await update.message.reply_photo(path)
        self.uniq_msg_id.append(msgs0.message_id)

    async def analyse_get_symbol(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        respon = update.message.text
        self.msg_id.append(update.message.message_id)
        msg0 = await update.message.reply_text("กำลังโหลดข้อมูลเหรียญ โปรดรอซักครู่")
        self.ask_msg_id.append(msg0.message_id)
        try:
            symbol = str(respon).upper()
            if symbol.endswith("BUSD") or symbol.endswith("USDT"):
                quote = "BUSD" if symbol.endswith("BUSD") else "USDT"
                base = symbol[:-4]
            else:
                quote = "USDT"
                base = symbol
            self.reset_trade_order_data()
            self.vxma_settings = vxma_settings
            self.trade_order["symbol"] = self.vxma_settings[
                "symbol"
            ] = f"{base}/{quote}:{quote}"
            self.vxma_menu_selected_state = "vxma_settings_1"
            self.update_inline_keyboard()
            await self.vxma_send_candle_pic(update)
            self.text_reply_bot_setting = f"รายการตั้งค่ากลยุทธ์สำหรับ {symbol}"
            msgs = await update.message.reply_text(
                text=self.text_reply_bot_setting,
                reply_markup=self.dynamic_reply_markup[self.vxma_menu_selected_state],
            )
        except Exception as e:
            text = f"เกิดข้อผิดพลาด :{e}\nโปรดตรวจสอบให้แน่ใจว่าเหรียญ {self.vxma_settings['symbol']} นั้นถูกต้อง\n\nโปรดทำรายการใหม่อีกครั้ง"
            msgs = await update.message.reply_text(
                text=text,
                reply_markup=self.reply_markup["analyse"],
            )
        self.uniq_msg_id.append(msgs.message_id)
        await self.delete_ask_messages(context)
        return ConversationHandler.END

    ## Position PNL Handlers
    async def position_get_lev_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        """Handler to asks for trade Leverage"""
        query = update.callback_query
        await query.answer()
        msg = await query.edit_message_text(
            text=f"Leverage ที่ใช้อยู่คือ {self.trade_order['lev']}\n\
หากต้องการแก้ไขโปรดใส่จำนวนตัวคูณ เช่น 1 , 5 , 10 , 20 , 25 , 50 , 100 , 125\
\n\n กด /cancel เพื่อยกเลิก"
        )
        self.ask_msg_id.append(msg.message_id)
        return P_LEV

    async def position_update_trade_lev(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handler that received trade amount (STEP1)"""
        respon = update.message.text
        self.msg_id.append(update.message.message_id)
        try:
            self.trade_order["new_lev"] = int(respon)
            margin = (
                self.trade_order["price"]
                * self.trade_order["amt"]
                / self.trade_order["new_lev"]
            )

            text = f"ท่านต้องการแก้ไข Leverage จาก {self.trade_order['lev']}\
ไปเป็น {self.trade_order['new_lev']}\n\
Order นี้จะใช้ Margin จะปรับเป็น: {round(margin, 3)}$\n\
\nหากถูกต้องกด \"ยืนยัน\" เพื่อส่งคำสั่ง"
            msg = await update.message.reply_text(
                text,
                reply_markup=self.reply_markup["position_confirm_lev"],
            )
        except Exception as e:
            text = f"\n\nเกิดข้อผิดพลาด {e}\nLeverage ต้องเป็นตัวเลขเท่านั้น โปรดทำรายการใหม่อีกครั้งค่ะ"
            msg = await update.message.reply_text(
                self.coin_pnl_reply_text + text,
                reply_markup=self.dynamic_reply_markup["position"],
            )
        self.uniq_msg_id.append(msg.message_id)
        await self.delete_ask_messages(context)
        return ConversationHandler.END

    async def position_confirm_lev(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["H"] == "BACK":
            msgs = await query.edit_message_text(
                text=self.coin_pnl_reply_text,
                reply_markup=self.dynamic_reply_markup["position"],
            )
        elif callback["H"] == "OK":
            await self.binance_.setleverage(
                self.trade_order["symbol"], self.trade_order["new_lev"]
            )
            await self.binance_.update_balance(True)
            await self.binance_.disconnect()
            position_data = await self.bot_trade.check_current_position(
                self.trade_order["symbol"], self.binance_.position_data.copy()
            )
            self.trade_order["lev"] = self.trade_order["new_lev"]
            self.trade_order["pnl"] = position_data[self.trade_order["type"]]["pnl"]
            self.trade_order["margin"] = position_data[self.trade_order["type"]][
                "margin"
            ]
            emoji = "📈" if self.trade_order["type"].upper() == "LONG" else "📉"
            pnl_t = "ขาดทุน" if self.trade_order["pnl"] < 0.0 else "กำไร"

            text = f"\n{emoji}Postion {self.trade_order['type'].upper()}\n\
🪙จำนวน {self.trade_order['amt']}\n\n\
💶ราคาเข้า : {self.trade_order['e_price']}\n\
💵ราคาปัจจุบัน : {self.trade_order['price']}\n\n\
💰Margin ที่ใช้ : {self.trade_order['margin']}$\n\
Leverage : X{self.trade_order['lev']}\n\
💸{pnl_t} : {self.trade_order['pnl']}$"
            self.coin_pnl_reply_text = f"เหรียญ {self.trade_order['symbol']}" + text
            self.update_inline_keyboard()
            msgs = await query.edit_message_text(
                text=self.coin_pnl_reply_text,
                reply_markup=self.dynamic_reply_markup["position"],
            )

        self.uniq_msg_id.append(msgs.message_id)

    async def position_get_tp_price_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        """Handler to asks for trade TP Price"""
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        text2 = ""
        if callback["D"] != 0:
            price = callback["D"].split("|")
            self.trade_order["tp_id"], self.trade_order["tp_price"] = price
            text2 = "\nใส่ 0 หากต้องการส่งคำสั่งยกเลิก Order นี้"
        text = (
            f"ราคา Take Profit เดิมของท่านคือ : {self.trade_order['tp_price']}"
            if self.trade_order["tp_price"] != 0.0
            else ""
        )
        msg = await query.edit_message_text(
            text=f"{self.trade_order['symbol']} {self.trade_order['type'].upper()}\n{text}\n\
ราคาเปิด Position นี้คือ : {self.trade_order['price']}\n\
โปรดใส่ราคา Take Profit หากต้องการแก้ไข \n\
หรือหากต้องการใช้ % คำนวนให้พิมพ์ ลงท้ายด้วย % เช่น 5%{text2}\n\n กด /cancel เพื่อยกเลิก"
        )
        self.ask_msg_id.append(msg.message_id)
        return P_TP

    async def position_update_trade_tp_price(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handler that received trade TP Price (STEP1)"""
        respon = update.message.text
        self.msg_id.append(update.message.message_id)
        try:
            if str(respon).endswith("%"):
                if self.trade_order["type"] == "long":
                    self.trade_order["new_tp_price"] = (
                        self.trade_order["e_price"] * (float(respon[:-1]) + 100) / 100
                    )
                elif self.trade_order["type"] == "short":
                    self.trade_order["new_tp_price"] = (
                        self.trade_order["e_price"] * (float(respon[:-1]) - 100) / 100
                    )
            else:
                self.trade_order["new_tp_price"] = float(respon)
            self.trade_order["tp"] = True
            text_ = (
                f"แก้ไขราคา Take Profit จาก {self.trade_order['tp_price']}  ไปเป็น"
                if self.trade_order["tp_price"] != 0.0
                else "เพิ่มราคา Take Profit "
            )

            text = f"ท่านต้องการ{text_}\
{'ยกเลิก' if self.trade_order['new_tp_price'] == 0.0 else self.trade_order['new_tp_price']}\n\
\nหากถูกต้องกด \"ยืนยัน\" เพื่อส่งคำสั่ง"
            msg = await update.message.reply_text(
                text,
                reply_markup=self.reply_markup["position_confirm_tp"],
            )
        except Exception as e:
            text = f"เกิดข้อผิดพลาด {e}\nโปรดตรวจสอบเลขทศนิยม หรือราคาเหรียญให้ถูกต้องแล้วทำรายการใหม่ค่ะ"
            msg = await update.message.reply_text(
                self.coin_pnl_reply_text + text,
                reply_markup=self.dynamic_reply_markup["position"],
            )
        self.uniq_msg_id.append(msg.message_id)
        await self.delete_ask_messages(context)
        return ConversationHandler.END

    async def position_confirm_tp(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        async def open_tp(side: str = "buy", position_side: str = "BOTH"):
            orderid = get_order_id()
            try:
                order = await exchange.create_order(
                    self.trade_order["symbol"],
                    "TAKE_PROFIT_MARKET",
                    side,
                    abs(float(self.trade_order["amt"])),
                    self.trade_order["new_tp_price"],
                    params={
                        "stopPrice": self.trade_order["new_tp_price"],
                        "triggerPrice": self.trade_order["new_tp_price"],
                        "positionSide": position_side,
                        "newClientOrderId": orderid,
                    },
                )
                self.position_tp_sl_order.append(
                    {
                        "type": "tp",
                        "price": self.trade_order["new_tp_price"],
                        "id": order["id"],
                    }
                )
                return f"\n{order['status']} -> ส่งคำสั่ง Take Profit ที่ {self.trade_order['new_tp_price']} เรียบร้อยแล้ว"

            except Exception as e:
                return f"\nเกิดข้อผิดพลาดตอนส่งคำสั่ง Take Profit :{e}"

        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["H"] == "BACK":
            msgs = await query.edit_message_text(
                text=self.coin_pnl_reply_text,
                reply_markup=self.dynamic_reply_markup["position"],
            )
        elif callback["H"] == "OK":
            await query.edit_message_text("กำลังส่งข้อมูลไปยัง Exchange โปรดรอซักครู่")
            text = ""
            exchange = await self.binance_.get_exchange()
            await self.binance_.connect_loads()
            if self.trade_order["tp_id"] != 0:
                await self.binance_.cancel_order(
                    self.trade_order["symbol"], self.trade_order["tp_id"]
                )
                self.position_tp_sl_order = [
                    i
                    for i in self.position_tp_sl_order
                    if i["id"] != self.trade_order["tp_id"]
                ]
                self.trade_order["tp_price"] = 0.0
            if self.trade_order["new_tp_price"] != 0.0:
                self.trade_order["new_tp_price"] = exchange.price_to_precision(
                    self.trade_order["symbol"], self.trade_order["new_tp_price"]
                )
                if self.trade_order["type"] == "long":
                    text += await open_tp("sell", self.bot_trade.currentMode.Lside)
                elif self.trade_order["type"] == "short":
                    text += await open_tp("buy", self.bot_trade.currentMode.Sside)
            # self.trade_order["tp_price"] = float(self.trade_order["new_tp_price"])
            await self.binance_.disconnect()

            self.update_inline_keyboard()
            msgs = await query.edit_message_text(
                text=self.coin_pnl_reply_text + text,
                reply_markup=self.dynamic_reply_markup["position"],
            )

        self.uniq_msg_id.append(msgs.message_id)

    async def position_get_sl_price_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        """Handler to asks for trade SL Price"""
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        text2 = ""
        if callback["D"] != 0:
            price = callback["D"].split("|")
            self.trade_order["sl_id"], self.trade_order["sl_price"] = price
            text2 = "\nใส่ 0 หากต้องการส่งคำสั่งยกเลิก Order นี้"
        text = (
            f"ราคา Stop-Loss เดิมของท่านคือ : {self.trade_order['sl_price']}"
            if self.trade_order["sl_price"] != 0.0
            else ""
        )
        msg = await query.edit_message_text(
            text=f"{self.trade_order['type'].upper()} {self.trade_order['symbol']}\n{text}\n\
ราคาเปิด Position นี้คือ : {self.trade_order['price']}\n\
โปรดใส่ราคา Stop-Loss ใหม่หากต้องการแก้ไข\n\
หรือหากต้องการใช้ % คำนวนให้พิมพ์ ลงท้ายด้วย % เช่น 5%{text2}\n\n กด /cancel เพื่อยกเลิก"
        )
        self.ask_msg_id.append(msg.message_id)
        return P_SL

    async def position_update_trade_sl_price(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handler that received trade SL Price (STEP1)"""
        respon = update.message.text
        self.msg_id.append(update.message.message_id)
        try:
            if str(respon).endswith("%"):
                if self.trade_order["type"] == "long":
                    self.trade_order["new_sl_price"] = (
                        self.trade_order["e_price"] * (float(respon[:-1]) - 100) / 100
                    )
                elif self.trade_order["type"] == "short":
                    self.trade_order["new_sl_price"] = (
                        self.trade_order["e_price"] * (float(respon[:-1]) + 100) / 100
                    )
            else:
                self.trade_order["new_sl_price"] = float(respon)
            self.trade_order["sl"] = True
            text_ = (
                f"แก้ไขราคา Stop-Loss  จาก {self.trade_order['sl_price']} ไปเป็น"
                if self.trade_order["sl_price"] != 0.0
                else "เพิ่มราคา Stop-Loss เท่ากับ"
            )
            text = f"ท่านต้องการ{text_}\
{'ยกเลิก' if self.trade_order['new_sl_price'] == 0.0 else self.trade_order['new_sl_price']}\n\
\nหากถูกต้องกด \"ยืนยัน\" เพื่อส่งคำสั่ง"

            msg = await update.message.reply_text(
                text,
                reply_markup=self.reply_markup["position_confirm_sl"],
            )
        except Exception as e:
            text = f"\nเกิดข้อผิดพลาด {e}\nโปรดตรวจสอบเลขทศนิยม หรือราคาเหรียญให้ถูกต้องแล้วทำรายการใหม่ค่ะ"

            msg = await update.message.reply_text(
                self.coin_pnl_reply_text + text,
                reply_markup=self.dynamic_reply_markup["position"],
            )
        self.uniq_msg_id.append(msg.message_id)
        await self.delete_ask_messages(context)
        return ConversationHandler.END

    async def position_confirm_sl(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        async def open_sl(side: str = "buy", position_side: str = "BOTH"):
            orderid = get_order_id()
            try:
                order = await exchange.create_order(
                    self.trade_order["symbol"],
                    "stop_market",
                    side,
                    abs(float(self.trade_order["amt"])),
                    params={
                        "stopPrice": self.trade_order["new_sl_price"],
                        "positionSide": position_side,
                        "newClientOrderId": orderid,
                    },
                )
                self.position_tp_sl_order.append(
                    {
                        "type": "sl",
                        "price": self.trade_order["new_sl_price"],
                        "id": order["id"],
                    }
                )
                return f"\n{order['status']} -> ส่งคำสั่ง Stop-Loss ที่ {self.trade_order['new_sl_price']} เรียบร้อยแล้ว"

            except Exception as e:
                return f"\nเกิดข้อผิดพลาดตอนส่งคำสั่ง Stop-Loss :{e}"

        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["H"] == "BACK":
            msgs = await query.edit_message_text(
                text=self.coin_pnl_reply_text,
                reply_markup=self.dynamic_reply_markup["position"],
            )
        elif callback["H"] == "OK":
            await query.edit_message_text("กำลังส่งข้อมูลไปยัง Exchange โปรดรอซักครู่")
            exchange = await self.binance_.get_exchange()
            await self.binance_.connect_loads()
            text = ""
            if self.trade_order["sl_id"] != 0:
                await self.binance_.cancel_order(
                    self.trade_order["symbol"], self.trade_order["sl_id"]
                )
                self.trade_order["sl_price"] = 0.0
                self.position_tp_sl_order = [
                    i
                    for i in self.position_tp_sl_order
                    if i["id"] != self.trade_order["sl_id"]
                ]
            if self.trade_order["new_sl_price"] != 0.0:
                self.trade_order["new_sl_price"] = exchange.price_to_precision(
                    self.trade_order["symbol"], self.trade_order["new_sl_price"]
                )
                if self.trade_order["type"] == "long":
                    text += await open_sl("sell", self.bot_trade.currentMode.Lside)
                elif self.trade_order["type"] == "short":
                    text += await open_sl("buy", self.bot_trade.currentMode.Sside)
            await self.binance_.disconnect()

            self.update_inline_keyboard()
            msgs = await query.edit_message_text(
                text=self.coin_pnl_reply_text + text,
                reply_markup=self.dynamic_reply_markup["position"],
            )

        self.uniq_msg_id.append(msgs.message_id)

    async def position_close_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        async def close_order(side: str = "buy", position_side: str = "BOTH"):
            orderid = get_order_id()
            try:
                order = await exchange.create_market_order(
                    self.trade_order["symbol"],
                    side,
                    abs(float(self.trade_order["amt"])),
                    params={
                        "positionSide": position_side,
                        "newClientOrderId": orderid,
                    },
                )
                await self.binance_.update_balance(force=True)
                pnl = "\nกำไร" if self.trade_order["pnl"] > 0.0 else "ขาดทุน"
                return f"{order['status']} - ธุรกรรมที่ถูกปิดไป{pnl} : {self.trade_order['pnl']}$\n\n"
            except Exception as e:
                return f"\nเกิดข้อผิดพลาดในการปิด Order เดิม :{e}"

        query = update.callback_query
        await query.answer()
        await query.edit_message_text("กำลังส่งข้อมูลไปยัง Exchange โปรดรอซักครู่")
        exchange = await self.binance_.get_exchange()
        await self.binance_.connect_loads()
        if self.trade_order["type"] == "long":
            text = await close_order("sell", self.bot_trade.currentMode.Lside)
        elif self.trade_order["type"] == "short":
            text = await close_order("buy", self.bot_trade.currentMode.Sside)
        await self.binance_.update_balance(True)
        await self.binance_.disconnect()
        self.coin_pnl_reply_text = remove_last_line_from_string(
            self.coin_pnl_reply_text
        )
        msgs = await query.edit_message_text(
            text=self.coin_pnl_reply_text + text + choice(EGGS),
            reply_markup=self.reply_markup["menu"],
        )

        self.uniq_msg_id.append(msgs.message_id)

    async def back_to_show_position_coins_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """This Handler can Handle both command and inline button respons"""
        query = update.callback_query
        if query is not None:
            # For Back Buttons
            await query.answer()
            msgs = await query.message.edit_text(
                self.coin_pnl_reply_text,
                reply_markup=self.dynamic_reply_markup["position"],
            )
            self.uniq_msg_id.append(msgs.message_id)
        else:
            # For Commands cancel
            self.msg_id.append(update.message.message_id)
            await self.delete_unig_messages(context)
            msgs = await update.message.reply_text(
                self.coin_pnl_reply_text,
                reply_markup=self.dynamic_reply_markup["position"],
            )
            self.uniq_msg_id.append(msgs.message_id)
            return ConversationHandler.END

    async def show_position_coins_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        if self.trade_menu_selected != "pnl":
            await query.edit_message_text("กำลังอัพเดตราคาเหรียญ โปรดรอซักครู่")
            self.trade_order["price"] = await self.binance_.get_bidask(
                self.trade_order["symbol"], "bid"
            )
            self.trade_order["type"] = "MARKET"
            self.trade_order["amt"] = 0.0
            self.update_inline_keyboard()
            msgs = await query.edit_message_text(
                self.trade_reply_text,
                reply_markup=self.dynamic_reply_markup["trade"],
            )
            self.uniq_msg_id.append(msgs.message_id)
            return

        await query.edit_message_text("โปรดรอซักครู่..")
        await self.binance_.update_balance()
        await self.binance_.disconnect()
        status = self.binance_.position_data
        if len(status.index) > 0:
            positiondata = [
                (
                    json.dumps(
                        {
                            "M": "PNLC",
                            "H": status["symbol"][i],
                            "Side": status["positionSide"][i],
                        }
                    ),
                    f"{status['positionSide'][i] if status['positionSide'][i] != 'BOTH' else ''} {status['symbol'][i]} P/L {round(status['unrealizedProfit'][i], 3)}$",
                )
                for i in range(len(status.index))
            ]
            msg = "โปรดเลือกเหรียญดังนี้:"
            coins = [
                [
                    InlineKeyboardButton(
                        f"{x}",
                        callback_data=f"{i}",
                    )
                ]
                for i, x in positiondata
            ]
            coins_key = InlineKeyboardMarkup(coins + self.pnl_back_button)
            text = [
                f"{status['symbol'][i]} จำนวน {status['positionAmt'][i]} P/L {round(status['unrealizedProfit'][i], 3)}$\n"
                for i in range(len(status.index))
            ]
            self.pnl_reply = "Postion ที่มีการเปิดอยู่\n" + "".join(text)
        else:
            coins_key = InlineKeyboardMarkup(self.pnl_back_button)
            self.pnl_reply = "หากคุณมีความรู้ แต่ยังขาดทุนอยู่ นั่นแสดงว่า คุณยังควบคุมความโลภ และความกลัว ไม่ได้"
            msg = "ท่านไม่มี Position ใด ๆ อยู่ในขณะนี้"
        msgs = await query.edit_message_text(text=msg, reply_markup=coins_key)
        self.uniq_msg_id.append(msgs.message_id)

    async def info_pnl_per_coin(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["H"] == "BACK_TO_MENU":
            msgs = await query.edit_message_text(
                text=f"{self.pnl_reply}",
                reply_markup=self.reply_markup["pnl"],
            )
        elif "Side" not in callback.keys():
            symbol = callback["H"]
            if "/" in symbol:
                posim = symbol[:-5].replace("/", "")
            else:
                posim = symbol
            await self.binance_.update_balance()
            await self.binance_.disconnect()
            status = self.binance_.position_data
            status = status[status["symbol"] == posim]
            positiondata = [
                (
                    json.dumps(
                        {
                            "M": "PNLC",
                            "H": status["symbol"][i],
                            "Side": status["positionSide"][i],
                        }
                    ),
                    f"{status['positionSide'][i] if status['positionSide'][i] != 'BOTH' else ''} {status['symbol'][i]} P/L {round(status['unrealizedProfit'][i], 3)}$",
                )
                for i in range(len(status.index))
            ]
            coins = [
                [
                    InlineKeyboardButton(
                        f"{x}",
                        callback_data=f"{i}",
                    )
                ]
                for i, x in positiondata
            ]
            coins_key = InlineKeyboardMarkup(
                coins
                + [
                    [
                        InlineKeyboardButton(
                            "❌ กลับ",
                            callback_data="{'M': 'position_', 'H' :'BACK'}",
                        )
                    ]
                ]
            )
            msgs = await query.edit_message_text(
                "โปรดเลือก Position ที่ต้องการตรวจสอบ", reply_markup=coins_key
            )
        else:
            ## TODO EDIT POSITION
            self.reset_trade_order_data()
            await query.edit_message_text("กำลังโหลดข้อมูลออเดอร์...")
            symbol = str(callback["H"]).upper()
            if ":" in symbol:
                self.trade_order["symbol"] = symbol
            else:
                if symbol.endswith("BUSD") or symbol.endswith("USDT"):
                    quote = "BUSD" if symbol.endswith("BUSD") else "USDT"
                    base = symbol[:-4]
                else:
                    quote = "USDT"
                    base = symbol
                self.trade_order["symbol"] = f"{base}/{quote}:{quote}"
            exchange = await self.binance_.get_exchange()
            await self.binance_.connect_loads()
            self.trade_order["price"] = await self.binance_.get_bidask(
                self.trade_order["symbol"], "bid"
            )
            markets = await exchange.fetchMarkets()
            self.trade_order["min_amt"] = float(
                (
                    data["limits"]["amount"]["min"]
                    for data in markets
                    if data["symbol"] == self.trade_order["symbol"]
                ).__next__()
            )
            if self.trade_order["min_amt"] * self.trade_order["price"] < 5.0:
                self.trade_order["min_amt"] = exchange.amount_to_precision(
                    self.trade_order["symbol"], 6.0 / self.trade_order["price"]
                )
            position_data = await self.bot_trade.check_current_position(
                self.trade_order["symbol"], self.binance_.position_data.copy()
            )
            if (
                callback["Side"].upper() != "BOTH"
                and not self.bot_trade.currentMode.dualSidePosition
            ):
                await self.bot_trade.get_currentmode()
            self.trade_order["type"] = (
                f"{callback['Side']}".lower()
                if self.bot_trade.currentMode.dualSidePosition
                else "long"
                if position_data["long"]["position"]
                else "short"
            )
            self.position_tp_sl_order = await self.binance_.get_tp_sl_price(
                self.trade_order["symbol"],
                f"{callback['Side']}".upper()
                if self.bot_trade.currentMode.dualSidePosition
                else "BOTH",
            )
            await self.binance_.disconnect()
            self.trade_order["amt"] = abs(
                position_data[self.trade_order["type"]]["amount"]
            )
            self.trade_order["e_price"] = position_data[self.trade_order["type"]][
                "price"
            ]
            self.trade_order["pnl"] = position_data[self.trade_order["type"]]["pnl"]
            self.trade_order["margin"] = position_data[self.trade_order["type"]][
                "margin"
            ]
            pnl_t = "ขาดทุน" if self.trade_order["pnl"] < 0.0 else "กำไร"
            emoji = "📈" if self.trade_order["type"].upper() == "LONG" else "📉"
            self.trade_order["lev"] = position_data["leverage"]
            text = f"\n{emoji}Postion {self.trade_order['type'].upper()}\n\
🪙จำนวน {self.trade_order['amt']}\n\n\
💶ราคาเข้า : {self.trade_order['e_price']}\n\
💵ราคาปัจจุบัน : {self.trade_order['price']}\n\n\
💰Margin ที่ใช้ : {self.trade_order['margin']}$\n\
Leverage : X{self.trade_order['lev']}\n\
💸{pnl_t} : {self.trade_order['pnl']}$"
            self.coin_pnl_reply_text = f"เหรียญ {self.trade_order['symbol']}" + text
            self.update_inline_keyboard()
            msgs = await query.edit_message_text(
                text=self.coin_pnl_reply_text,
                reply_markup=self.dynamic_reply_markup["position"],
            )

        self.uniq_msg_id.append(msgs.message_id)

    ## Settings menu
    async def setting_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ) -> None:
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["H"] == "BOT":
            if self.status_bot:
                self.status_bot = False
                text = "\n\n🔴ปิดบอทสำเร็จ"
                self.bot_trade.stop_bot()
            elif not self.status_bot:
                self.status_bot = True
                text = "\n\n🟢เปิดบอทสำเร็จ"
                self.bot_trade.start_bot()
            self.update_inline_keyboard()
            msg = f"{self.watchlist_reply_text}" + text
            msgs = await query.edit_message_text(
                text=msg, reply_markup=self.dynamic_reply_markup["setting"]
            )
        elif callback["H"] == "SCAN":
            if self.status_scan:
                self.status_scan = False
                text = "\n\n🔴ปิดบอทแสกนตลาดสำเร็จ"
                self.bot_trade.disable_scan()
            elif not self.status_scan:
                self.status_scan = True
                text = "\n\n🟢เปิดบอทแสกนตลาดสำเร็จ"
                self.bot_trade.enable_scan()
            self.update_inline_keyboard()
            msg = f"{self.watchlist_reply_text}" + text
            msgs = await query.edit_message_text(
                text=msg, reply_markup=self.dynamic_reply_markup["setting"]
            )
        elif callback["H"] == "RISK":
            msg = "อย่าเสี่ยงมากนะคะนายท่าน \n" + choice(EGGS)
            msgs = await query.edit_message_text(
                text=msg, reply_markup=self.dynamic_reply_markup["risk"]
            )
        elif callback["H"] == "COINS":
            msg = "โปรดเลือกเหรียญดังนี้:"
            coins = [
                [
                    InlineKeyboardButton(
                        f"{symbol[:-5]} {tf}".replace("/", ""),
                        callback_data=json.dumps({"M": "COINS", "H": f"{cid}"}),
                    )
                    for cid, symbol, tf in symbol_list
                ]
                for symbol_list in split_list(self.bot_trade.watchlist, 3)
            ] + [
                [
                    InlineKeyboardButton(
                        "❌ กลับ",
                        callback_data="{'M': 'COINS', 'H': 'BACK_TO_MENU'}",
                    )
                ]
            ]
            self.coins_settings_key = InlineKeyboardMarkup(coins)
            msgs = await query.edit_message_text(
                text=msg, reply_markup=self.coins_settings_key
            )
        self.uniq_msg_id.append(msgs.message_id)

    ## Risk Settings
    async def get_max_risk_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        msg = await query.edit_message_text(
            text=f"โปรดกรอกจำนวนความเสี่ยงที่ท่านรับได้\n\
จำนวนนี้ จะนำไปคำนวนระหว่างความเสี่ยงทั้งหมด และ Postion ในมือ\
ค่าปัจจุบันคือ {self.risk['max_risk']}\n\n กด /cancel เพื่อยกเลิก"
        )
        self.ask_msg_id.append(msg.message_id)
        return B_RISK

    async def update_max_risk(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        respon = update.message.text
        self.msg_id.append(update.message.message_id)
        try:
            self.risk["max_risk"] = float(respon)
            text = f"ท่านได้กำหนดความเสี่ยงทั้งหมดไว้ที่ : {self.risk['max_risk']}\n"
            self.risk_reply_text = text + choice(EGGS)
            self.update_inline_keyboard()
        except Exception as e:
            text = f"เกิดข้อผิดพลาด {e}\nโปรดทำรายการใหม่อีกรั้ง"

        msg = await update.message.reply_text(
            text,
            reply_markup=self.dynamic_reply_markup["risk"],
        )
        self.uniq_msg_id.append(msg.message_id)
        await self.delete_ask_messages(context)
        return ConversationHandler.END

    async def get_min_balance_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        msg = await query.edit_message_text(
            text=f"โปรดกรอกจำนวน กระเป๋าเงินขั้นต่ำที่จะทำการหยุดบอท\n\
ปัจจุบันกำหนดไว้ที่ {self.risk['min_balance']}\n\n กด /cancel เพื่อยกเลิก"
        )
        self.ask_msg_id.append(msg.message_id)
        return B_MIN_BL

    async def update_min_balance(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        respon = update.message.text
        self.msg_id.append(update.message.message_id)
        try:
            self.risk["min_balance"] = float(respon)
            text = (
                self.risk_reply_text
                + f"\nท่านได้กำหนดกระเป๋าเงินขั้นต่ำไว้ที่ : {self.risk['min_balance']}"
            )
            self.risk_reply_text = text
            self.update_inline_keyboard()
        except Exception as e:
            text = f"เกิดข้อผิดพลาด {e}\nโปรดทำรายการใหม่อีกรั้ง"

        msg = await update.message.reply_text(
            text,
            reply_markup=self.dynamic_reply_markup["risk"],
        )
        self.uniq_msg_id.append(msg.message_id)
        await self.delete_ask_messages(context)
        return ConversationHandler.END

    async def save_risk_to_db(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        try:
            with sqlite3.connect("vxma.db", check_same_thread=False) as con:
                # Read
                config = pd.read_sql("SELECT * FROM key", con=con)
                # Edit
                config["freeB"][0] = self.risk["max_risk"]
                config["minB"][0] = self.risk["min_balance"]
                # Save
                config = config.set_index("apikey")
                config.to_sql(
                    "key",
                    con=con,
                    if_exists="replace",
                    index=True,
                    index_label="apikey",
                )
                con.commit()
            text = "บันทึกข้อมูลสำเร็จแล้วค่ะ"
        except Exception as e:
            text = (
                f"เกิดข้อผิดพลาดขึ้นเนื่องจาก {e}\n\nโปรดทดลองทำรายการใหม่อีกครั้งค่ะ"
            )
        msgs = await query.edit_message_text(
            text=text, reply_markup=self.dynamic_reply_markup["risk"]
        )
        self.uniq_msg_id.append(msgs.message_id)

    async def back_from_risk_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ) -> None:
        query = update.callback_query
        msg = self.risk_reply_text + f"{self.watchlist_reply_text}"
        await query.answer()
        msgs = await query.edit_message_text(
            text=msg, reply_markup=self.dynamic_reply_markup["setting"]
        )
        self.uniq_msg_id.append(msgs.message_id)

    async def back_to_risk_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        self.msg_id.append(update.message.message_id)
        await self.delete_unig_messages(context)
        msg = self.risk_reply_text + "\n\nอย่าเสี่ยงมากนะคะนายท่าน"
        msgs = await update.message.reply_text(
            msg, reply_markup=self.dynamic_reply_markup["risk"]
        )
        self.uniq_msg_id.append(msgs.message_id)
        return ConversationHandler.END

    # Coin config Setting
    async def edit_config_per_coin(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["H"] == "BACK_TO_MENU":
            msgs = await query.edit_message_text(
                text=f"{self.watchlist_reply_text}",
                reply_markup=self.dynamic_reply_markup["setting"],
            )
        else:
            await query.edit_message_text("กำลังโหลดข้อมูลแท่งเทียน โปรดรอซักครู่")
            self.vxma_menu_selected_state = "vxma_settings"
            configs = bot_setting()
            self.vxma_settings["id"] = int(callback["H"])
            config = configs.iloc[self.vxma_settings["id"]]

            for x, y in config.items():
                self.vxma_settings[x] = y
            symbol = self.vxma_settings["symbol"]
            self.update_inline_keyboard()
            await self.vxma_send_candle_pic(query)
            self.text_reply_bot_setting = (
                f"รายการตั้งค่ากลยุทธ์สำหรับ {symbol[:-5].replace('/','')}"
            )
            await query.delete_message()
            msgs = await query.message.reply_text(
                text=self.text_reply_bot_setting,
                reply_markup=self.dynamic_reply_markup[self.vxma_menu_selected_state],
            )
        self.uniq_msg_id.append(msgs.message_id)

    async def vxma_settings_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ) -> None:
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["H"] in self.vxma_settings.keys():
            self.vxma_settings_selected_state = callback["H"]
            self.vxma_selected_state_type = callback["Type"]
            if self.vxma_selected_state_type == "bool":
                self.vxma_settings[self.vxma_settings_selected_state] = (
                    False
                    if self.vxma_settings[self.vxma_settings_selected_state]
                    else True
                )
                self.update_inline_keyboard()
                msgs = await query.edit_message_text(
                    text=self.text_reply_bot_setting
                    + f"\n\n{vxma_settings_info[self.vxma_settings_selected_state]} สำเร็จ",
                    reply_markup=self.dynamic_reply_markup[
                        self.vxma_menu_selected_state
                    ],
                )
            else:
                msg = await query.edit_message_text(
                    text=f"ท่านได้เลือกเมนู {vxma_settings_info[self.vxma_settings_selected_state]}\
    \n\n\nค่าปัจจุบันคือ {self.vxma_settings[self.vxma_settings_selected_state]}\
     โปรดกรอกข้อมูลเพื่อทำการแก้ไข\n\nกด /cancel เพื่อยกเลิก"
                )
                self.ask_msg_id.append(msg.message_id)
                return SETTING_STATE
        elif callback["H"] == "BACK":
            if self.vxma_menu_selected_state == "vxma_settings":
                msgs = await query.edit_message_text(
                    text="โปรดเลือกเหรียญดังนี้:", reply_markup=self.coins_settings_key
                )
            elif self.vxma_menu_selected_state == "vxma_settings_1":
                msgs = await query.edit_message_text(
                    text="โปรดเลือกกลยุทธ์ของท่าน",
                    reply_markup=self.reply_markup["analyse"],
                )
        elif callback["H"] == "CHART":
            await self.vxma_send_candle_pic(query)
            await query.delete_message()
            msgs = await query.message.reply_text(
                text=self.text_reply_bot_setting,
                reply_markup=self.dynamic_reply_markup[self.vxma_menu_selected_state],
            )
        elif callback["H"] == "BACK_2":
            self.vxma_menu_selected_state = "vxma_settings_1"
            msgs = await query.edit_message_text(
                text=self.text_reply_bot_setting,
                reply_markup=self.dynamic_reply_markup[self.vxma_menu_selected_state],
            )
        elif callback["H"] == "Setting":
            self.vxma_menu_selected_state = "vxma_settings_2"
            msgs = await query.edit_message_text(
                text=f"รายการตั้งค่ากลยุทธ์สำหรับ {self.vxma_settings['symbol']}",
                reply_markup=self.dynamic_reply_markup[self.vxma_menu_selected_state],
            )
        elif callback["H"] == "SAVE":
            msgs = await query.edit_message_text(
                text=f"โปรดยืนยัน หากต้องการบันทึกข้อมูลเหรียญ {self.vxma_settings['symbol']}",
                reply_markup=self.reply_markup["vxma_settings_confirm_save"],
            )
        elif callback["H"] == "SAVE_ADD":
            text = [
                f"{key} : {value}\n"
                for key, value in self.vxma_settings.items()
                if key != "id"
            ]
            text0 = "รายการ การตั้งค่าดังต่อไปนี้จะถูกเพิ่มไปยังฐานข้อมูล\n" + "".join(
                text
            )
            msgs = await query.edit_message_text(
                text=f"{text0}\n\nโปรดยืนยัน หากต้องการบันทึกข้อมูลเหรียญ {self.vxma_settings['symbol']}",
                reply_markup=self.reply_markup["vxma_settings_confirm_save_2"],
            )
        elif callback["H"] == "TRADE":
            await query.edit_message_text("กำลังอัพเดตราคาเหรียญ โปรดรอซักครู่")
            self.trade_menu_selected = "vxma_settings_1"
            exchange = await self.binance_.get_exchange()
            self.trade_order["symbol"] = self.vxma_settings["symbol"]
            self.trade_order["price"] = await self.binance_.get_bidask(
                self.trade_order["symbol"], "bid"
            )
            markets = await exchange.fetchMarkets()
            self.trade_order["min_amt"] = float(
                (
                    data["limits"]["amount"]["min"]
                    for data in markets
                    if data["symbol"] == self.trade_order["symbol"]
                ).__next__()
            )
            if self.trade_order["min_amt"] * self.trade_order["price"] < 5.0:
                self.trade_order["min_amt"] = exchange.amount_to_precision(
                    self.trade_order["symbol"], 6.0 / self.trade_order["price"]
                )
            await self.binance_.update_balance()
            currnet_position = await self.bot_trade.check_current_position(
                self.trade_order["symbol"], self.binance_.position_data.copy()
            )
            await self.binance_.disconnect()
            if currnet_position["leverage"] > 0:
                self.trade_order["lev"] = currnet_position["leverage"]
            text = f"คู่เหรียญ  {self.trade_order['symbol']}\nราคาปัจจุบัน : {self.trade_order['price']}$"
            if currnet_position["long"]["position"]:
                pnl_t = "ขาดทุน" if currnet_position["long"]["pnl"] < 0.0 else "กำไร"
                self.trade_order["pnl"] = currnet_position["long"]["pnl"]
                text += f"\n\n ท่านมี Position Long ของ เหรียญนี้อยู่ในมือ\n\
เป็นจำนวน  {round(currnet_position['long']['amount'], 3)} เหรียญ\n\
ใช้ Margin  {round(currnet_position['long']['margin'], 3)}$\n\
 {pnl_t} {round(currnet_position['long']['pnl'], 3)}$"

            if currnet_position["short"]["position"]:
                pnl_t = "ขาดทุน" if currnet_position["short"]["pnl"] < 0.0 else "กำไร"
                self.trade_order["pnl"] = currnet_position["short"]["pnl"]
                text += f"\n\n ท่านมี Position Short ของ เหรียญนี้อยู่ในมือ\n\
เป็นจำนวน  {round(currnet_position['short']['amount'], 3)} เหรียญ\n\
ใช้ Margin  {round(currnet_position['short']['margin'], 3)}$\n\
{pnl_t} {round(currnet_position['short']['pnl'], 3)}$"

            self.update_inline_keyboard()
            self.trade_reply_text = text
            msgs = await query.edit_message_text(
                text=self.trade_reply_text,
                reply_markup=self.dynamic_reply_markup["trade"],
            )
        elif callback["H"] == "DELETE":
            msgs = await query.edit_message_text(
                text=f"โปรดยืนยัน หากต้องการลบข้อมูลเหรียญ {self.vxma_settings['symbol']}",
                reply_markup=self.reply_markup["vxma_settings_confirm_del"],
            )
        self.uniq_msg_id.append(msgs.message_id)
        return ConversationHandler.END

    #     async def vxma_edit_settings_confirm(
    #         self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    #     ):
    #         query = update.callback_query
    #         await query.answer()
    #         callback = eval(query.data)
    #         if callback["H"] == "BACK":
    #             msgs = await query.edit_message_text(
    #                 text=self.text_reply_bot_setting,
    #                 reply_markup=self.dynamic_reply_markup[self.vxma_menu_selected_state],
    #             )
    #             self.uniq_msg_id.append(msgs.message_id)
    # return ConversationHandler.END
    #         else:
    #             msg = await query.edit_message_text(
    #                 text=f"ท่านได้เลือกเมนู {vxma_settings_info[self.vxma_settings_selected_state]}\
    # \n\n\nค่าปัจจุบันคือ {self.vxma_settings[self.vxma_settings_selected_state]}\
    #  โปรดกรอกข้อมูลเพื่อทำการแก้ไข\n\nกด /cancel เพื่อยกเลิก"
    #             )
    #             self.ask_msg_id.append(msg.message_id)
    #             return SETTING_STATE

    async def vxma_get_settings(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        respon = update.message.text
        self.msg_id.append(update.message.message_id)
        try:
            text = f"\nได้ทำการเปลี่ยน {vxma_settings_info[self.vxma_settings_selected_state]}\
จากเดิม : {self.vxma_settings[self.vxma_settings_selected_state]} ไปเป็น {respon} เรียบร้อย"
            if self.vxma_selected_state_type == "int":
                self.vxma_settings[self.vxma_settings_selected_state] = int(respon)
            elif self.vxma_selected_state_type == "float":
                self.vxma_settings[self.vxma_settings_selected_state] = float(respon)
            elif self.vxma_selected_state_type == "str":
                if self.vxma_settings_selected_state == "symbol":
                    symbol = str(respon).upper()
                    if ":" in symbol:
                        self.vxma_settings[self.vxma_settings_selected_state] = symbol
                    else:
                        if symbol.endswith("BUSD") or symbol.endswith("USDT"):
                            quote = "BUSD" if symbol.endswith("BUSD") else "USDT"
                            base = symbol[:-4]
                        else:
                            quote = "USDT"
                            base = symbol
                        self.vxma_settings[
                            self.vxma_settings_selected_state
                        ] = f"{base}/{quote}:{quote}"
                else:
                    self.vxma_settings[self.vxma_settings_selected_state] = str(respon)
                self.text_reply_bot_setting = (
                    f"รายการตั้งค่ากลยุทธ์สำหรับ {self.vxma_settings['symbol']}"
                )
            if self.vxma_settings_selected_state in TA_TYPE:
                msg0 = await update.message.reply_text(
                    "กำลังโหลดข้อมูลแท่งเทียน โปรดรอซักครู่"
                )
                self.ask_msg_id.append(msg0.message_id)
                await self.vxma_send_candle_pic(update)

        except Exception as e:
            text = f"\n\nเกิดข้อผิดพลาด :{e}\n\nโปรดทำรายการใหม่อีกครั้ง"
        self.update_inline_keyboard()
        msgs = await update.message.reply_text(
            text=self.text_reply_bot_setting + text,
            reply_markup=self.dynamic_reply_markup[self.vxma_menu_selected_state],
        )
        self.uniq_msg_id.append(msgs.message_id)
        await self.delete_ask_messages(context)
        return ConversationHandler.END

    async def back_to_vxma_settings(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        if query is not None:
            # For Back Buttons
            await query.answer()
            msgs = await query.edit_message_text(
                text=self.text_reply_bot_setting,
                reply_markup=self.dynamic_reply_markup[self.vxma_menu_selected_state],
            )
            self.uniq_msg_id.append(msgs.message_id)
        else:
            # For Commands cancel
            self.msg_id.append(update.message.message_id)
            await self.delete_unig_messages(context)
            msgs = await update.message.reply_text(
                text=self.text_reply_bot_setting,
                reply_markup=self.dynamic_reply_markup[self.vxma_menu_selected_state],
            )
            self.uniq_msg_id.append(msgs.message_id)
            return ConversationHandler.END

    async def vxma_save_settings_confirm(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["H"] == "BACK":
            msgs = await query.edit_message_text(
                text=self.text_reply_bot_setting,
                reply_markup=self.dynamic_reply_markup[self.vxma_menu_selected_state],
            )
        else:
            try:
                configs = bot_setting()
                config = configs.loc[self.vxma_settings["id"]]
                for key in config.keys():
                    config[key] = self.vxma_settings[key]
                configs.loc[self.vxma_settings["id"]] = config
                configs.to_csv("bot_config.csv", index=True)
                text = f"\n\nได้บันทึกข้อมูลเหรียญ {self.vxma_settings['symbol']} สำหรับบอทเรียบร้อยแล้วค่ะ"
                self.bot_trade.update_watchlist()
                msg = f"{self.watchlist_reply_text}" + text
                msgs = await query.edit_message_text(
                    text=msg, reply_markup=self.dynamic_reply_markup["setting"]
                )
            except Exception as e:
                text = f"เกิดข้อผิดพลาด {e}\n\nโปรดทำรายการใหม่อีกครั้งค่ะ"
                msgs = await query.edit_message_text(
                    text=self.text_reply_bot_setting + text,
                    reply_markup=self.dynamic_reply_markup[
                        self.vxma_menu_selected_state
                    ],
                )
        self.uniq_msg_id.append(msgs.message_id)

    async def vxma_save_settings_confirm_2(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["H"] == "BACK":
            msgs = await query.edit_message_text(
                text=self.text_reply_bot_setting,
                reply_markup=self.dynamic_reply_markup[self.vxma_menu_selected_state],
            )
        else:
            try:
                configs = bot_setting()
                self.vxma_settings["id"] = len(configs.index) + 1
                config = pd.DataFrame(
                    data=[vxma_settings.values()], columns=vxma_settings.keys()
                )
                config = config.set_index("id")
                configs = pd.concat([configs, config], axis=0, ignore_index=True)
                configs.to_csv("bot_config.csv", index=True)
                text = f"\n\nได้บันทึกข้อมูลเหรียญ {self.vxma_settings['symbol']} สำหรับบอทเรียบร้อยแล้วค่ะ"
                self.bot_trade.update_watchlist()
                msgs = await query.edit_message_text(
                    text=self.text_reply_bot_setting + text,
                    reply_markup=self.dynamic_reply_markup[
                        self.vxma_menu_selected_state
                    ],
                )
            except Exception as e:
                text = f"เกิดข้อผิดพลาด {e}\n\nโปรดทำรายการใหม่อีกครั้งค่ะ"
                msgs = await query.edit_message_text(
                    text=self.text_reply_bot_setting + text,
                    reply_markup=self.dynamic_reply_markup[
                        self.vxma_menu_selected_state
                    ],
                )
        self.uniq_msg_id.append(msgs.message_id)

    async def vxma_del_settings_confirm(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["H"] == "BACK":
            msgs = await query.edit_message_text(
                text=self.text_reply_bot_setting,
                reply_markup=self.dynamic_reply_markup[self.vxma_menu_selected_state],
            )
        else:
            try:
                configs = bot_setting()
                configs = configs.drop(self.vxma_settings["id"])
                configs.reset_index(drop=True, inplace=True)
                configs.to_csv("bot_config.csv", index=True, index_label="id")
                text = f"\n\nได้ลบข้อมูลเหรียญ {self.vxma_settings['symbol']} สำหรับบอทเรียบร้อยแล้วค่ะ"
                self.bot_trade.update_watchlist()
                msg = f"{self.watchlist_reply_text}" + text
                msgs = await query.edit_message_text(
                    text=msg, reply_markup=self.dynamic_reply_markup["setting"]
                )
            except Exception as e:
                text = f"เกิดข้อผิดพลาด {e}\n\nโปรดทำรายการใหม่อีกครั้งค่ะ"
                msgs = await query.edit_message_text(
                    text=self.text_reply_bot_setting + text,
                    reply_markup=self.dynamic_reply_markup[
                        self.vxma_menu_selected_state
                    ],
                )
        self.uniq_msg_id.append(msgs.message_id)

    ## Secure menu
    ## API
    async def set_api_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        """Handler to asks for API setting"""
        query = update.callback_query
        await query.answer()
        msg = await query.edit_message_text(
            text="โปรดกรอก API KEY จาก Binance\n\n กด /cancel เพื่อยกเลิก"
        )
        self.ask_msg_id.append(msg.message_id)
        return STEP1_API

    async def get_api_key(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler that received API KEY STEP1"""
        respon = update.message.text
        self.msg_id.append(update.message.message_id)
        self.sec_info["API_KEY"] = str(respon)
        await self.delete_ask_messages(context)
        msg = await update.message.reply_text(
            f"API KEY Binance ของท่าคือ {self.sec_info['API_KEY']}\nโปรดกรอก API SECRET ต่อไป\n\n กด /cancel เพื่อยกเลิก",
        )
        self.ask_msg_id.append(msg.message_id)
        return STEP2_API_SEC

    async def get_api_sec(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler that received API SECRET STEP2"""
        respon = update.message.text
        self.msg_id.append(update.message.message_id)
        self.sec_info["API_SEC"] = str(respon)
        msg0 = await update.message.reply_text("กำลังทดสอบ API โปรดรอซักครู่.....")
        self.ask_msg_id.append(msg0.message_id)
        try:
            binance_test = Binance(
                api=self.sec_info["API_KEY"], sapi=self.sec_info["API_SEC"]
            )
            exchange = await binance_test.get_exchange()
            balance = await exchange.fetch_balance()
            await exchange.close()
            fiat_balance = {x: y for x, y in balance.items() if "USD" in x[-4:]}
            with sqlite3.connect("vxma.db", check_same_thread=False) as con:
                # Read
                config = pd.read_sql("SELECT * FROM key", con=con)
                # Edit able
                # apikey freeB minB apisec notify
                config["apikey"][0] = self.sec_info["API_KEY"]
                config["apisec"][0] = self.sec_info["API_SEC"]
                # Save
                config = config.set_index("apikey")
                config.to_sql(
                    "key",
                    con=con,
                    if_exists="replace",
                    index=True,
                    index_label="apikey",
                )
                con.commit()
            text = (
                "BUSD"
                + f"\nFree   : {round(fiat_balance['BUSD']['free'],2)}$"
                + f"\nMargin : {round(fiat_balance['BUSD']['used'],2)}$"
                + f"\nTotal  : {round(fiat_balance['BUSD']['total'],2)}$\nUSDT"
                + f"\nFree   : {round(fiat_balance['USDT']['free'],2)}$"
                + f"\nMargin : {round(fiat_balance['USDT']['used'],2)}$"
                + f"\nTotal  : {round(fiat_balance['USDT']['total'],2)}$"
            )
            msg = await update.message.reply_text(
                f"ตั้งค่า API {self.sec_info['API_KEY'][:10]} สำเร็จ\n{text}",
                reply_markup=self.reply_markup["secure"],
            )
        except Exception as e:
            msg = await update.message.reply_text(
                f"ตั้งค่า API {self.sec_info['API_KEY'][:10]} เกิดข้อผิดพลาด\n{e}",
                reply_markup=self.reply_markup["secure"],
            )
        self.uniq_msg_id.append(msg.message_id)
        await self.delete_ask_messages(context)
        return ConversationHandler.END

    async def back_to_secure_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """This Handler can Handle both command and inline button respons"""
        query = update.callback_query
        if query is not None:
            # For Back Buttons
            await query.answer()
            msgs = await query.edit_message_text(
                text=f"{self.watchlist_reply_text}",
                reply_markup=self.dynamic_reply_markup["setting"],
            )
            self.uniq_msg_id.append(msgs.message_id)
        else:
            # For Commands cancel
            self.msg_id.append(update.message.message_id)
            await self.delete_unig_messages(context)
            msgs = await update.message.reply_text(
                text=f"{self.watchlist_reply_text}",
                reply_markup=self.dynamic_reply_markup["setting"],
            )
            self.uniq_msg_id.append(msgs.message_id)
            return ConversationHandler.END

    async def delete_unig_messages(self, context) -> None:
        if len(self.uniq_msg_id) > 0:
            tasks = [
                asyncio.create_task(self.delete_messages(cid, context))
                for cid in self.uniq_msg_id
            ]
            await asyncio.gather(*tasks)

    async def delete_ask_messages(self, context) -> None:
        if len(self.ask_msg_id) > 0:
            tasks = [
                asyncio.create_task(self.delete_messages(cid, context))
                for cid in self.ask_msg_id
            ]
            await asyncio.gather(*tasks)

    async def delete_messages(self, cid, context: ContextTypes.DEFAULT_TYPE):
        try:
            await context.bot.delete_message(chat_id=self.chat_id, message_id=cid)
            self.msg_id.remove(cid)
        except Exception:
            pass

    ## Customs Tasks to run once
    async def clear_task(self, context: ContextTypes.DEFAULT_TYPE):
        while True:
            if len(self.msg_id) > 0:
                for id in self.msg_id:
                    try:
                        await context.bot.delete_message(
                            chat_id=self.chat_id, message_id=id
                        )
                        self.msg_id.remove(id)
                    except Exception:
                        continue
                self.msg_id.clear()
            await asyncio.sleep(1)

    async def make_bot_task(self, context: ContextTypes.DEFAULT_TYPE):
        self.bot_trade.add_app_context(context)
        while True:
            if self.status_bot:
                try:
                    await asyncio.shield(self.bot_trade.run_bot())
                except Exception as e:
                    print(e)
                    continue
            await asyncio.sleep(1)

    async def echo(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ) -> None:
        """Echo the user message."""
        self.uniq_msg_id.append(update.message.message_id)
        question = update.message.text
        contents = {"role": "user", "content": f"{question}"}
        self.conversation.append(contents)
        text = chat(self.conversation)
        msg = await update.message.reply_text(text["choices"][0]["message"]["content"])
        self.uniq_msg_id.append(msg.message_id)


def main():
    while True:
        try:
            app = Telegram(f"{os.environ['TelegramToken']}")
            app.setup_bot()
        except KeyboardInterrupt:
            return
        else:
            continue


if __name__ == "__main__":
    main()
