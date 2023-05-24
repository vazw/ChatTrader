import asyncio
from datetime import datetime
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
    AppConfig,
    TATable,
    bot_setting,
    candle,
    write_trade_record,
    edit_all_trade_record,
    vxma_settings,
    vxma_settings_info,
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
        self.bot_trade = ""
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
        self.vxma_selected_state = ""
        self.trade_order = {}
        self.sec_info = {
            "API_KEY": "",
            "API_SEC": "",
            "PASS": "",
        }
        self.vxma_settings = vxma_settings
        self.dynamic_reply_markup = {}
        self.reply_markup = REPLY_MARKUP

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
        self.load_database()

    def update_inline_keyboard(self):
        self.dynamic_reply_markup = {
            "trade": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            f"Order Type: {self.trade_order['type']}",
                            callback_data='{"Mode": "trade", "Method": "Type"}',
                        ),
                        InlineKeyboardButton(
                            f"Leverage: X{self.trade_order['lev']}",
                            callback_data='{"Mode": "trade", "Method": "Lev"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            f"ราคา : {self.trade_order['price']}",
                            callback_data='{"Mode": "trade", "Method": "Price"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            f"จำนวน : {self.trade_order['amt'] if self.trade_order['amt'] > 0.0 else '--.--'}",
                            callback_data='{"Mode": "trade", "Method": "Amt"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            f"TP : {self.trade_order['tp_price'] if self.trade_order['tp_price'] > 0.0 else '--.--'}",
                            callback_data='{"Mode": "trade", "Method": "TP"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            f"SL : {self.trade_order['sl_price'] if self.trade_order['sl_price'] > 0.0 else '--.--'}",
                            callback_data='{"Mode": "trade", "Method": "SL"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "LONG 📈",
                            callback_data='{"Mode": "trade", "Method": "LONG"}',
                        ),
                        InlineKeyboardButton(
                            "📉 SHORT",
                            callback_data='{"Mode": "trade", "Method": "SHORT"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "เปลี่ยนเหรียญ",
                            callback_data='{"Mode": "trade", "Method": "Change"}',
                        ),
                        InlineKeyboardButton(
                            "❌ กลับ",
                            callback_data='{"Mode": "trade", "Method": "BACK"}',
                        ),
                    ],
                ]
            ),
            "setting": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            f"BOT STATUS : {'ON 🟢' if self.status_bot else 'OFF 🔴'}",
                            callback_data='{"Mode": "setting", "Method": "BOT"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "ตั้งค่าความเสี่ยง",
                            callback_data='{"Mode": "setting", "Method": "RISK"}',
                        ),
                        InlineKeyboardButton(
                            "ตั้งค่ารายเหรียญ",
                            callback_data='{"Mode": "setting", "Method": "COINS"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            f"SCAN : {'ON 🟢' if self.status_scan else 'OFF 🔴'}",
                            callback_data='{"Mode": "setting", "Method": "SCAN"}',
                        ),
                        InlineKeyboardButton(
                            "❌ กลับ",
                            callback_data='{"Mode": "setting", "Method": "BACK"}',
                        ),
                    ],
                ]
            ),
            "risk": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            f"ความเสี่ยงที่รับได้ : {self.risk['max_risk']}",
                            callback_data='{"Mode": "risk", "Method": "MAX_RISK"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            f"จะหยุดบอทเมื่อเงินเหลือ : {self.risk['min_balance']}",
                            callback_data='{"Mode": "risk", "Method": "MIN_BALANCE"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "บันทึก",
                            callback_data='{"Mode": "risk", "Method": "SAVE"}',
                        ),
                        InlineKeyboardButton(
                            "❌ กลับ",
                            callback_data='{"Mode": "risk", "Method": "BACK"}',
                        ),
                    ],
                ]
            ),
            "position": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            f"TP : {self.trade_order['tp_price'] if self.trade_order['tp_price'] > 0.0 else '--.--'}",
                            callback_data='{"Mode": "position", "Method": "TP"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            f"SL : {self.trade_order['sl_price'] if self.trade_order['sl_price'] > 0.0 else '--.--'}",
                            callback_data='{"Mode": "position", "Method": "SL"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            f"ปิด Postion : {self.trade_order['price']}",
                            callback_data='{"Mode": "position_", "Method": "Close"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            f"Leverage: X{self.trade_order['lev']}",
                            callback_data='{"Mode": "position", "Method": "Lev"}',
                        ),
                        InlineKeyboardButton(
                            "❌ กลับ",
                            callback_data='{"Mode": "position_", "Method": "BACK"}',
                        ),
                    ],
                ]
            ),
            "vxma_settings": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings" , "Method": "timeframe", "Type": "str"}',
                            text=f"timeframe : {self.vxma_settings['timeframe']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "hedge", "Type": "bool"}',
                            text=f"hedge : {'ON 🟢' if self.vxma_settings['hedge'] else 'OFF 🔴'}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "hedgeTF", "Type": "str"}',
                            text=f"hedgeTF : {self.vxma_settings['hedgeTF']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "ATR", "Type": "int"}',
                            text=f"ATR : {self.vxma_settings['ATR']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "ATR_m", "Type": "float"}',
                            text=f"ATR_m : {self.vxma_settings['ATR_m']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "Pivot", "Type": "int"}',
                            text=f"Pivot : {self.vxma_settings['Pivot']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "EMA", "Type": "int"}',
                            text=f"EMA : {self.vxma_settings['EMA']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "subhag", "Type": "int"}',
                            text=f"subhag : {self.vxma_settings['subhag']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method" : "smooth", "Type": "int"}',
                            text=f"smooth : {self.vxma_settings['smooth']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "RSI", "Type": "int"}',
                            text=f"RSI : {self.vxma_settings['RSI']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "Andean", "Type": "int"}',
                            text=f"Andean : {self.vxma_settings['Andean']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "leverage", "Type": "int"}',
                            text=f"leverage : {self.vxma_settings['leverage']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "Useshort", "Type": "bool"}',
                            text=f"Useshort : {'ON 🟢' if self.vxma_settings['Useshort'] else 'OFF 🔴'}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method":"UseTP", "Type": "bool"}',
                            text=f"UseTP : {'ON 🟢' if self.vxma_settings['UseTP'] else 'OFF 🔴'}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "UseTP2", "Type": "bool"}',
                            text=f"UseTP2 : {'ON 🟢' if self.vxma_settings['UseTP2'] else 'OFF 🔴'}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "Uselong", "Type": "bool"}',
                            text=f"Uselong : {'ON 🟢' if self.vxma_settings['Uselong'] else 'OFF 🔴'}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "UseSL", "Type": "bool"}',
                            text=f"UseSL : {'ON 🟢' if self.vxma_settings['UseSL'] else 'OFF 🔴'}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "Tail_SL", "Type": "bool"}',
                            text=f"Tail_SL : {'ON 🟢' if self.vxma_settings['Tail_SL'] else 'OFF 🔴'}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "TP1", "Type": "int"}',
                            text=f"TP1 : {self.vxma_settings['TP1']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "RR1", "Type": "float"}',
                            text=f"RR1 : {self.vxma_settings['RR1']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "RR2", "Type": "float"}',
                            text=f"RR2 : {self.vxma_settings['RR2']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "TP2", "Type": "int"}',
                            text=f"TP2 : {self.vxma_settings['TP2']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "Risk", "Type": "str"}',
                            text=f"Risk : {self.vxma_settings['Risk']}",
                        ),
                        InlineKeyboardButton(
                            callback_data='{"Mode": "vxma_settings", "Method": "maxMargin, "Type": "str""}',
                            text=f"maxMargin : {self.vxma_settings['maxMargin']}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "กราฟ📈",
                            callback_data='{"Mode": "vxma_settings", "Method": "CHART"}',
                        ),
                        InlineKeyboardButton(
                            "💾บันทึก",
                            callback_data='{"Mode": "vxma_settings", "Method": "SAVE"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "ลบ🗑",
                            callback_data='{"Mode": "vxma_settings", "Method": "DELETE"}',
                        ),
                        InlineKeyboardButton(
                            "❌ กลับ",
                            callback_data='{"Mode": "vxma_settings", "Method": "BACK"}',
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
            "new_lev": 10,
            "lev": 10,
            "e_price": 0.0,
            "price": 0.0,
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
                lambda x: (eval(x))["Mode"]
                in ["fiat", "trade", "analyse", "pnl", "setting", "secure"]
                and (eval(x))["Method"] == "BACK",
            ),
        ]

        main_menu_handlers = [
            # Handlers set for buttons workarounds.
            CallbackQueryHandler(
                self.button_menu, lambda x: (eval(x))["Mode"] == "menu"
            ),
            CallbackQueryHandler(
                self.fiat_handler, lambda x: (eval(x))["Mode"] == "fiat"
            ),
            CallbackQueryHandler(
                self.setting_handler, lambda x: (eval(x))["Mode"] == "setting"
            ),
        ]

        # trade_handler
        trade_menu_handlers = [
            # symbol
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.get_symbol_handler,
                        lambda x: (eval(x))["Mode"] == "menuex"
                        and (eval(x))["Method"] == "Trade",
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
                        lambda x: (eval(x))["Mode"] == "trade"
                        and (eval(x))["Method"] == "Change",
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
                        lambda x: (eval(x))["Mode"] == "trade"
                        and (eval(x))["Method"] == "Lev",
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
                        lambda x: (eval(x))["Mode"] == "trade"
                        and (eval(x))["Method"] == "Amt",
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
                        lambda x: (eval(x))["Mode"] == "trade"
                        and (eval(x))["Method"] == "TP",
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
                        lambda x: (eval(x))["Mode"] == "trade"
                        and (eval(x))["Method"] == "SL",
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
                lambda x: (eval(x))["Mode"] == "trade"
                and (eval(x))["Method"] == "Type",
            ),
            CallbackQueryHandler(
                self.trade_order_type_handler,
                lambda x: (eval(x))["Mode"] == "order_type",
            ),
            # Long Buttons
            CallbackQueryHandler(
                self.trade_long_button,
                lambda x: (eval(x))["Mode"] == "trade"
                and (eval(x))["Method"] == "LONG",
            ),
            # # Short Buttons
            CallbackQueryHandler(
                self.trade_short_button,
                lambda x: (eval(x))["Mode"] == "trade"
                and (eval(x))["Method"] == "SHORT",
            ),
        ]

        position_pnl_handlers = [
            # confirm buttons
            CallbackQueryHandler(
                self.position_confirm_lev,
                lambda x: (eval(x))["Mode"] == "position_confirm_lev",
            ),
            CallbackQueryHandler(
                self.position_confirm_sl,
                lambda x: (eval(x))["Mode"] == "position_confirm_sl",
            ),
            CallbackQueryHandler(
                self.position_confirm_tp,
                lambda x: (eval(x))["Mode"] == "position_confirm_tp",
            ),
            # Symbols
            CallbackQueryHandler(
                self.info_pnl_per_coin,
                lambda x: (eval(x))["Mode"] == "PNLC",
            ),
            # back from info_pnl_per_coin
            CallbackQueryHandler(
                self.show_info_pnl_per_coin,
                lambda x: (eval(x))["Mode"] == "position_"
                and (eval(x))["Method"] == "BACK",
            ),
            # edit symbol fot pnl
            CallbackQueryHandler(
                self.show_info_pnl_per_coin,
                lambda x: (eval(x))["Mode"] == "pnl" and (eval(x))["Method"] == "COINS",
            ),
            # ClosePosition
            CallbackQueryHandler(
                self.position_close_handler,
                lambda x: (eval(x))["Mode"] == "position_"
                and (eval(x))["Method"] == "Close",
            ),
            # edit TP,SL,Leverage Handlers
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.position_get_tp_price_handler,
                        lambda x: (eval(x))["Mode"] == "position"
                        and (eval(x))["Method"] == "TP",
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
                fallbacks=[CommandHandler("cancel", self.back_to_info_pnl_per_coin)],
            ),
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.position_get_sl_price_handler,
                        lambda x: (eval(x))["Mode"] == "position"
                        and (eval(x))["Method"] == "SL",
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
                fallbacks=[CommandHandler("cancel", self.back_to_info_pnl_per_coin)],
            ),
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.position_get_lev_handler,
                        lambda x: (eval(x))["Mode"] == "position"
                        and (eval(x))["Method"] == "Lev",
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
                fallbacks=[CommandHandler("cancel", self.back_to_info_pnl_per_coin)],
            ),
        ]

        # Setting Handler
        bot_setting_handlers = [
            # Risk
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.get_max_risk_handler,
                        lambda x: (eval(x))["Mode"] == "risk"
                        and (eval(x))["Method"] == "MAX_RISK",
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
                        lambda x: (eval(x))["Mode"] == "risk"
                        and (eval(x))["Method"] == "MIN_BALANCE",
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
                lambda x: (eval(x))["Mode"] == "risk" and (eval(x))["Method"] == "SAVE",
            ),
            CallbackQueryHandler(
                self.back_from_risk_menu,
                lambda x: ((eval(x))["Mode"] == "risk" or (eval(x))["Mode"] == "COINS")
                and (eval(x))["Method"] == "BACK",
            ),
            ## TODO add symbols handler for setting
            CallbackQueryHandler(
                self.edit_config_per_coin,
                lambda x: (eval(x))["Mode"] == "COINS",
            ),
            CallbackQueryHandler(
                self.vxma_settings_handler,
                lambda x: (eval(x))["Mode"] == "vxma_settings",
            ),
            CallbackQueryHandler(
                self.vxma_save_settings_confirm,
                lambda x: (eval(x))["Mode"] == "vxma_settings_confirm_save",
            ),
            CallbackQueryHandler(
                self.vxma_del_settings_confirm,
                lambda x: (eval(x))["Mode"] == "vxma_settings_confirm_del",
            ),
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.vxma_edit_settings_confirm,
                        lambda x: (eval(x))["Mode"] == "vxma_settings_confirm",
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
                        lambda x: (eval(x))["Mode"] == "secure"
                        and (eval(x))["Method"] == "API",
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
        # Handler for unknown commands at the last handler
        self.application.add_handler(MessageHandler(filters.COMMAND, self.unknown))

        # Running Background job.
        self.application.job_queue.run_once(self.make_bot_task, when=1)
        self.application.job_queue.run_once(self.clear_task, when=1)

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
        delete_list = self.uniq_msg_id + self.msg_id + self.ask_msg_id
        if len(delete_list) > 0:
            for id in delete_list:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue

        self.msg_id.clear()
        self.uniq_msg_id.clear()
        msg = await update.message.reply_text("Cleared!!")
        self.msg_id.append(msg.message_id)

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ) -> None:
        """Displays info on how to use the bot."""
        msg = await update.message.reply_text(HELP_MESSAGE)
        self.msg_id.append(msg.message_id)

    async def unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Sorry, I didn't understand that command.",
        )
        self.msg_id.append(msg.message_id)

    ## Main Menu Nesting
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sends a message with three inline buttons attached."""
        await context.bot.delete_message(
            chat_id=self.chat_id, message_id=update.message.message_id
        )
        msg = await update.message.reply_text(
            "Please choose:", reply_markup=self.reply_markup["menu"]
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
        if callback["Method"] == "CheckBalance":
            msgs = await query.edit_message_text(
                text="โปรดเลือกกระเป๋าเงินเฟียต",
                reply_markup=self.reply_markup["fiat"],
            )
            await self.binance_.update_balance()
            await self.binance_.disconnect()
            # Trade use different callback
        # elif callback["Method"] == "Trade":
        #     msgs = await query.edit_message_text(
        #         text="Please Select Fiat Balance",
        #         reply_markup=self.reply_markup["trade"],
        #     )
        elif callback["Method"] == "Analyser":
            msgs = await query.edit_message_text(
                text="โปรดเลือกกลยุทธ์ของท่าน",
                reply_markup=self.reply_markup["analyse"],
            )
        elif callback["Method"] == "PositionData":
            await self.binance_.update_balance()
            await self.binance_.disconnect()
            status = self.binance_.position_data
            if len(status.index) > 0:
                text = [
                    f"{status['symbol'][i]} จำนวน {status['positionAmt'][i]} P/L {round(status['unrealizedProfit'][i], 3)}$\n"
                    for i in range(len(status.index))
                ]
                text_reply = self.pnl_reply = "Postion ที่มีการเปิดอยู่\n" + "".join(
                    text
                )
            else:
                text_reply = "ไม่มี Postion ที่มีการเปิดอยู่"
            msgs = await query.edit_message_text(
                text=text_reply,
                reply_markup=self.reply_markup["pnl"],
            )
        elif callback["Method"] == "BotSetting":
            text = [
                f"{symbol[:-5]} {tf}\n"
                for id, symbol, tf in self.bot_trade.watchlist  # pyright: ignore
            ]
            self.watchlist_reply_text = (
                "เหรียญที่ดูอยู่ :\n" + "".join(text) + "\n\nโปรดเลือกการตั้งค่า"
            )
            msgs = await query.edit_message_text(
                text=f"{self.watchlist_reply_text}",
                reply_markup=self.dynamic_reply_markup["setting"],
            )
        elif callback["Method"] == "apiSetting":
            msgs = await query.edit_message_text(
                text="โปรดเลือกการตั้งค่า",
                reply_markup=self.reply_markup["secure"],
            )
        elif callback["Method"] == "X":
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
        msg = "Please choose:"
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
            for id in self.uniq_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
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
        callback = eval(query.data)
        fiat_balance = self.binance_.fiat_balance
        status = self.binance_.position_data
        netunpl = float(
            status["unrealizedProfit"].astype("float64").sum()
            if not status.empty
            else 0.0
        )

        if callback["Method"] == "ALL":
            msg = (
                "BUSD"
                + f"\nFree   : {round(fiat_balance['BUSD']['free'],2)}$"
                + f"\nMargin : {round(fiat_balance['BUSD']['used'],2)}$"
                + f"\nTotal  : {round(fiat_balance['BUSD']['total'],2)}$\nUSDT"
                + f"\nFree   : {round(fiat_balance['USDT']['free'],2)}$"
                + f"\nMargin : {round(fiat_balance['USDT']['used'],2)}$"
                + f"\nTotal  : {round(fiat_balance['USDT']['total'],2)}$"
                + f"\nNet Profit/Loss  : {round(netunpl,2)}$"
            )
        elif callback["Method"] == "BUSD":
            msg = (
                "BUSD"
                + f"\nFree   : {round(fiat_balance['BUSD']['free'],2)}$"
                + f"\nMargin : {round(fiat_balance['BUSD']['used'],2)}$"
                + f"\nTotal  : {round(fiat_balance['BUSD']['total'],2)}$"
                + f"\nNet Profit/Loss  : {round(netunpl,2)}$"
            )
        elif callback["Method"] == "USDT":
            msg = (
                "USDT"
                + f"\nFree   : {round(fiat_balance['USDT']['free'],2)}$"
                + f"\nMargin : {round(fiat_balance['USDT']['used'],2)}$"
                + f"\nTotal  : {round(fiat_balance['USDT']['total'],2)}$"
                + f"\nNet Profit/Loss  : {round(netunpl,2)}$"
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
        for id in self.ask_msg_id:
            try:
                await context.bot.delete_message(chat_id=self.chat_id, message_id=id)
            except Exception:
                continue
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
            text="โปรดใส่ชื่อเหรียญ \n\n กด /cancel เพื่อยกเลิก"
        )
        self.ask_msg_id.append(msg.message_id)
        return T_SYMBOL

    async def update_trade_symbol(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handler that received trade symbol (STEP1)"""
        respon = update.message.text
        self.msg_id.append(update.message.message_id)
        self.reset_trade_order_data()
        self.trade_order["symbol"] = respon.upper()
        """TODO"""
        try:
            self.trade_order["price"] = await self.binance_.get_bidask(
                self.trade_order["symbol"], "bid"
            )
            await self.binance_.update_balance()
            currnet_position = await self.bot_trade.check_current_position(
                self.trade_order["symbol"], self.binance_.position_data.copy()
            )
            await self.binance_.disconnect()
            if currnet_position["leverage"] > 0:
                self.trade_order["lev"] = currnet_position["leverage"]
            self.update_inline_keyboard()
            text = f"คู่เหรียญ  {self.trade_order['symbol']}\nราคาปัจจุบัน : {self.trade_order['price']}$"
            if currnet_position["long"]["position"]:
                text = (
                    text
                    + f"\n\n ท่านมี Position Long ของ เหรียญนี้อยู่ในมือ\n\
                เป็นจำนวน  {round(currnet_position['long']['amount'], 3)} เหรียญ\n\
                กำไร/ขาดทุน {round(currnet_position['long']['pnl'], 3)}$"
                )
            elif currnet_position["short"]["position"]:
                text = (
                    text
                    + f"\n\n ท่านมี Position Short ของ เหรียญนี้อยู่ในมือ\n\
                เป็นจำนวน  {round(currnet_position['short']['amount'], 3)} เหรียญ\n\
                กำไร/ขาดทุน {round(currnet_position['short']['pnl'], 3)}$"
                )
            self.trade_reply_text = text
        except Exception as e:
            text = f"เกิดข้อผิดพลาด {e} ขึ้นกับเหรียญที่ท่านเลือก: {respon} โปรดลองเปลี่ยนเหรียญใหม่อีกครั้งค่ะ"

        msg = await update.message.reply_text(
            text,
            reply_markup=self.dynamic_reply_markup["trade"],
        )
        self.uniq_msg_id.append(msg.message_id)
        if len(self.ask_msg_id) > 0:
            for id in self.ask_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
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
            margin = (
                self.trade_order["price"]
                * self.trade_order["amt"]
                / self.trade_order["lev"]
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
        if len(self.ask_msg_id) > 0:
            for id in self.ask_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
        return ConversationHandler.END

    async def get_amount_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        """Handler to asks for trade amount"""
        query = update.callback_query
        await query.answer()
        msg = await query.edit_message_text(
            text="โปรดใส่จำนวนเหรียญ \n\n กด /cancel เพื่อยกเลิก"
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
            margin = (
                self.trade_order["price"]
                * self.trade_order["amt"]
                / self.trade_order["lev"]
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
        if len(self.ask_msg_id) > 0:
            for id in self.ask_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
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
        if len(self.ask_msg_id) > 0:
            for id in self.ask_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
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
        if len(self.ask_msg_id) > 0:
            for id in self.ask_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
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
        if callback["Method"] == "BACK":
            msgs = await query.edit_message_text(
                text=self.trade_reply_text + self.trade_reply_margin,
                reply_markup=self.dynamic_reply_markup["trade"],
            )
        else:
            self.trade_order["type"] = f"{callback['Method']}"
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
                    abs(self.trade_order["amt"]),
                    params={
                        "positionSide": self.bot_trade.currentMode.Lside,
                        "newClientOrderId": orderid,
                    },
                )
                await self.binance_.update_balance(force=True)
                return f"\n\nรายงานการทำธุรกรรม :\n\
ได้ออกคำสั่งเปิด Long สำหรับ : {self.trade_order['symbol']}\n\
จำนวน : {self.trade_order['amt']}\n\
Leverage: {self.trade_order['lev']}\n"
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
        text_repons = ["", "", "", ""]
        await query.answer()
        exchange = await self.binance_.get_exchange()
        await self.binance_.connect_loads()
        try:
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
                text2 = await open_tp_long()
                text_repons[2] = text2
            if self.trade_order["sl"]:
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
                    abs(self.trade_order["amt"]),
                    params={
                        "positionSide": self.bot_trade.currentMode.Sside,
                        "newClientOrderId": orderid,
                    },
                )
                await self.binance_.update_balance(force=True)
                return f"\n\nรายงานการทำธุรกรรม :\n\
ได้ออกคำสั่งเปิด Short สำหรับ : {self.trade_order['symbol']}\n\
จำนวน : {self.trade_order['amt']}\n\
Leverage: {self.trade_order['lev']}\n"
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
        text_repons = ["", "", "", ""]
        await query.answer()
        exchange = await self.binance_.get_exchange()
        await self.binance_.connect_loads()
        try:
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
                text2 = await open_tp_short()
                text_repons[2] = text2
            if self.trade_order["sl"]:
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

    ## Analyser menu
    async def analyse_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ) -> None:
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["Method"] == "VXMA":
            msg = "Please choose:"
            msgs = await query.edit_message_text(
                text=msg, reply_markup=self.reply_markup["menu"]
            )
        self.uniq_msg_id.append(msgs.message_id)

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
        if len(self.ask_msg_id) > 0:
            for id in self.ask_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
        return ConversationHandler.END

    async def position_confirm_lev(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["Method"] == "BACK":
            msgs = await query.edit_message_text(
                text=self.coin_pnl_reply_text,
                reply_markup=self.dynamic_reply_markup["position"],
            )
        elif callback["Method"] == "OK":
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
            pnl_t = "ขาดทุน" if self.trade_order["pnl"] < 0.0 else "กำไร"
            text = f"{self.trade_order['type'].upper()} Postion\n\
🪙จำนวน {self.trade_order['amt']}\n\
💶ราคาเข้า : {self.trade_order['e_price']}\n\
💵ราคาปัจจุบัน : {self.trade_order['price']}\n\
💰Margin ที่ใช้ : {self.trade_order['margin']}$\n\
Leverage : X{self.trade_order['lev']}\n\
💸{pnl_t} : {self.trade_order['pnl']}$\n"
            self.coin_pnl_reply_text = f"{self.trade_order['symbol']}" + text
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
        text = (
            f"เดิมของท่านคือ : {self.trade_order['tp_price']}"
            if self.trade_order["tp_price"] != 0.0
            else ""
        )
        msg = await query.edit_message_text(
            text=f"ราคา Take Profit {self.trade_order['type']} ของ\
{self.trade_order['symbol']} {text}\n\
ราคาเปิด Position นี้คือ : {self.trade_order['price']}\n\
โปรดใส่ราคา Take Profit หากต้องการแก้ไข \n\n กด /cancel เพื่อยกเลิก"
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
            self.trade_order["new_tp_price"] = float(respon)
            self.trade_order["tp"] = True
            text_ = (
                f" จาก {self.trade_order['tp_price']} "
                if self.trade_order["tp_price"] != 0.0
                else ""
            )

            text = f"ท่านต้องการแก้ไขราคา Take Profit {text_}\
ไปเป็น {self.trade_order['new_tp_price']}\n\
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
        if len(self.ask_msg_id) > 0:
            for id in self.ask_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
        return ConversationHandler.END

    async def position_confirm_tp(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        async def open_tp(side: str = "buy", position_side: str = "BOTH"):
            orderid = get_order_id()
            try:
                orderTP = await exchange.create_order(
                    self.trade_order["symbol"],
                    "TAKE_PROFIT_MARKET",
                    side,
                    abs(self.trade_order["amt"]),
                    self.trade_order["new_tp_price"],
                    params={
                        "stopPrice": self.trade_order["new_tp_price"],
                        "triggerPrice": self.trade_order["new_tp_price"],
                        "positionSide": position_side,
                        "newClientOrderId": orderid,
                    },
                )
                return f"\n{orderTP['status']} -> ส่งคำสั่ง Take Profit ที่ {self.trade_order['new_tp_price']} เรียบร้อยแล้ว"

            except Exception as e:
                return f"\nเกิดข้อผิดพลาดตอนส่งคำสั่ง Take Profit :{e}"

        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["Method"] == "BACK":
            msgs = await query.edit_message_text(
                text=self.coin_pnl_reply_text,
                reply_markup=self.dynamic_reply_markup["position"],
            )
        elif callback["Method"] == "OK":
            exchange = await self.binance_.get_exchange()
            if self.trade_order["tp_id"] != 0:
                self.binance_.cancel_order(
                    self.trade_order["symbol"], self.trade_order["tp_id"]
                )
            if self.trade_order["type"] == "long":
                text = await open_tp("sell", self.bot_trade.currentMode.Lside)
            elif self.trade_order["type"] == "short":
                text = await open_tp("buy", self.bot_trade.currentMode.Sside)
            await self.binance_.disconnect()
            self.trade_order["tp_price"] = self.trade_order["new_tp_price"]

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
        text = (
            f"เดิมของท่านคือ : {self.trade_order['sl_price']}"
            if self.trade_order["sl_price"] != 0.0
            else ""
        )
        msg = await query.edit_message_text(
            text=f"ราคา Stop-Loss {self.trade_order['type']} ของ\
{self.trade_order['symbol']} {text}\n\
ราคาเปิด Position นี้คือ : {self.trade_order['price']}\n\
โปรดใส่ราคา Stop-Loss ใหม่หากต้องการแก้ไข \n\n กด /cancel เพื่อยกเลิก"
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
            self.trade_order["new_sl_price"] = float(respon)
            self.trade_order["sl"] = True
            text_ = (
                f" จาก {self.trade_order['sl_price']} "
                if self.trade_order["sl_price"] != 0.0
                else ""
            )
            text = f"\n\nท่านต้องการแก้ไขราคา Stop-Loss \
{text_}\
ไปเป็น {self.trade_order['new_sl_price']}\n\
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
        if len(self.ask_msg_id) > 0:
            for id in self.ask_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
        return ConversationHandler.END

    async def position_confirm_sl(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        async def open_sl(side: str = "buy", position_side: str = "BOTH"):
            orderid = get_order_id()
            try:
                orderTP = await exchange.create_order(
                    self.trade_order["symbol"],
                    "stop_market",
                    side,
                    abs(self.trade_order["amt"]),
                    params={
                        "stopPrice": self.trade_order["new_sl_price"],
                        "positionSide": position_side,
                        "newClientOrderId": orderid,
                    },
                )
                return f"\n{orderTP['status']} -> ส่งคำสั่ง Stop-Loss ที่ {self.trade_order['new_sl_price']} เรียบร้อยแล้ว"

            except Exception as e:
                return f"\nเกิดข้อผิดพลาดตอนส่งคำสั่ง Stop-Loss :{e}"

        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["Method"] == "BACK":
            msgs = await query.edit_message_text(
                text=self.coin_pnl_reply_text,
                reply_markup=self.dynamic_reply_markup["position"],
            )
        elif callback["Method"] == "OK":
            exchange = await self.binance_.get_exchange()
            if self.trade_order["sl_id"] != 0:
                self.binance_.cancel_order(
                    self.trade_order["symbol"], self.trade_order["sl_id"]
                )
            if self.trade_order["type"] == "long":
                text = await open_sl("sell", self.bot_trade.currentMode.Lside)
            elif self.trade_order["type"] == "short":
                text = await open_sl("buy", self.bot_trade.currentMode.Sside)
            await self.binance_.disconnect()
            self.trade_order["sl_price"] = self.trade_order["new_sl_price"]

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
                    abs(self.trade_order["amt"]),
                    params={
                        "positionSide": position_side,
                        "newClientOrderId": orderid,
                    },
                )
                await self.binance_.update_balance(force=True)
                pnl = "\nกำไร" if self.trade_order["pnl"] > 0.0 else "ขาดทุน"
                return f"{order['status']} - ธุรกรรมที่ถูกปิดไป{pnl} : {self.trade_order['pnl']}$"
            except Exception as e:
                return f"\nเกิดข้อผิดพลาดในการปิด Order เดิม :{e}"

        query = update.callback_query
        await query.answer()
        exchange = await self.binance_.get_exchange()
        if self.trade_order["type"] == "long":
            text = await close_order("sell", self.bot_trade.currentMode.Lside)
        elif self.trade_order["type"] == "short":
            text = await close_order("buy", self.bot_trade.currentMode.Sside)
        await self.binance_.update_balance(True)
        await self.binance_.disconnect()
        msgs = await query.edit_message_text(
            text=self.coin_pnl_reply_text + text,
            reply_markup=self.reply_markup["menu"],
        )

        self.uniq_msg_id.append(msgs.message_id)

    async def back_to_info_pnl_per_coin(
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
            for id in self.uniq_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
            msgs = await update.message.reply_text(
                self.coin_pnl_reply_text,
                reply_markup=self.dynamic_reply_markup["position"],
            )
            self.uniq_msg_id.append(msgs.message_id)
            return ConversationHandler.END

    async def show_info_pnl_per_coin(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        await self.binance_.update_balance()
        await self.binance_.disconnect()
        pnl_back_button = [
            [
                InlineKeyboardButton(
                    "❌ กลับ",
                    callback_data="{'Mode': 'PNLC', 'Method' :'BACK_TO_MENU'}",
                    ## Chnage back to JSONDict
                )
            ]
        ]
        status = self.binance_.position_data
        if len(status.index) > 0:
            positiondata = [
                (
                    json.dumps(
                        {
                            "Mode": "PNLC",
                            "Method": status["symbol"][i],
                            "Side": status["positionSide"][i],
                        }
                    ),
                    f"{status['symbol'][i]} P/L {round(status['unrealizedProfit'][i], 3)}$",
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
                    for i, x in symbol_list
                ]
                for symbol_list in split_list(positiondata, 3)
            ]
            coins_key = InlineKeyboardMarkup(coins + pnl_back_button)
        else:
            coins_key = InlineKeyboardMarkup(pnl_back_button)
            msg = "ท่านไม่มี Position ใด ๆ อยู่ในขณะนี้"
        msgs = await query.edit_message_text(text=msg, reply_markup=coins_key)
        self.uniq_msg_id.append(msgs.message_id)

    async def info_pnl_per_coin(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["Method"] == "BACK_TO_MENU":
            msgs = await query.edit_message_text(
                text=f"{self.pnl_reply}",
                reply_markup=self.reply_markup["pnl"],
            )
        else:
            ## TODO EDIT POSITION
            self.reset_trade_order_data()
            self.trade_order["symbol"] = f"{callback['Method']}"
            self.trade_order["price"] = await self.binance_.get_bidask(
                self.trade_order["symbol"], "bid"
            )
            position_data = await self.bot_trade.check_current_position(
                self.trade_order["symbol"], self.binance_.position_data.copy()
            )
            self.trade_order["type"] = (
                f"{callback['Side']}".lower()
                if callback["Side"] != "BOTH"
                else "long"
                if position_data["long"]["position"]
                else "short"
            )
            symbol_order = await self.binance_.get_tp_sl_price(
                self.trade_order["symbol"], f"{callback['Side']}".upper()
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
            self.trade_order["tp_id"] = symbol_order["tp_id"]
            self.trade_order["sl_id"] = symbol_order["sl_id"]
            self.trade_order["tp_price"] = symbol_order["tp_price"]
            self.trade_order["sl_price"] = symbol_order["sl_price"]
            self.trade_order["lev"] = position_data["leverage"]
            text = f"{self.trade_order['type'].upper()} Postion\n\
🪙จำนวน {self.trade_order['amt']}\n\
💶ราคาเข้า : {self.trade_order['e_price']}\n\
💵ราคาปัจจุบัน : {self.trade_order['price']}\n\
💰Margin ที่ใช้ : {self.trade_order['margin']}$\n\
Leverage : X{self.trade_order['lev']}\n\
💸{pnl_t} : {self.trade_order['pnl']}$\n"
            self.coin_pnl_reply_text = f"{self.trade_order['symbol']}" + text
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
        if callback["Method"] == "BOT":
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
        elif callback["Method"] == "SCAN":
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
        elif callback["Method"] == "RISK":
            msg = "อย่าเสี่ยงมากนะคะนายท่าน :"
            msgs = await query.edit_message_text(
                text=msg, reply_markup=self.dynamic_reply_markup["risk"]
            )
        elif callback["Method"] == "COINS":
            msg = "โปรดเลือกเหรียญดังนี้:"
            coins = [
                [
                    InlineKeyboardButton(
                        f"{symbol[:-5]} {tf}".replace("/", ""),
                        callback_data=json.dumps({"Mode": "COINS", "Method": cid}),
                    )
                    for cid, symbol, tf in symbol_list
                ]
                for symbol_list in split_list(self.bot_trade.watchlist, 3)
            ] + [
                [
                    InlineKeyboardButton(
                        "❌ กลับ",
                        callback_data="{'Mode': 'COINS', 'Method': 'BACK_TO_MENU'}",
                    )
                ]
            ]
            self.coins_settings_key = InlineKeyboardMarkup(coins)
            print(coins)
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
            text = f"ท่านได้กำหนดความเสี่ยงทั้งหมดไว้ที่ : {self.risk['max_risk']}"
            self.risk_reply_text = text
            self.update_inline_keyboard()
        except Exception as e:
            text = f"เกิดข้อผิดพลาด {e}\nโปรดทำรายการใหม่อีกรั้ง"

        msg = await update.message.reply_text(
            text,
            reply_markup=self.dynamic_reply_markup["risk"],
        )
        self.uniq_msg_id.append(msg.message_id)
        if len(self.ask_msg_id) > 0:
            for id in self.ask_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
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
        if len(self.ask_msg_id) > 0:
            for id in self.ask_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
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
        for id in self.uniq_msg_id:
            try:
                await context.bot.delete_message(chat_id=self.chat_id, message_id=id)
            except Exception:
                continue
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
        if callback["Method"] == "BACK_TO_MENU":
            msgs = await query.edit_message_text(
                text=f"{self.watchlist_reply_text}",
                reply_markup=self.dynamic_reply_markup["setting"],
            )
        else:
            configs = bot_setting()
            self.vxma_settings["id"] = callback["Method"]
            config = configs.loc[self.vxma_settings["id"],]
            ta_data = TATable(
                atr_p=config["ATR"],
                atr_m=config["ATR_m"],
                ema=config["EMA"],
                linear=config["subhag"],
                smooth=config["smooth"],
                rsi=config["RSI"],
                aol=config["Andean"],
                pivot=config["Pivot"],
            )

            for config_ in split_list(config.items(), 2):
                for x, y in config_:
                    self.vxma_settings[x] = y
            symbol = self.vxma_settings["symbol"]
            timeframe = self.vxma_settings["timeframe"]
            self.update_inline_keyboard()
            df = await self.bot_trade.bot_3(
                self.vxma_settings["symbol"], ta_data.__dict__, timeframe
            )
            path = candle(df, symbol, timeframe)
            msgs0 = await query.message.reply_photo(path)
            self.uniq_msg_id.append(msgs0.message_id)
            self.text_reply_bot_setting = (
                f"รายการตั้งค่า สำหรับกลยุทธ์ สำหรับ {symbol[:-5].replace('/','')}"
            )
            await query.delete_message()
            msgs = await query.message.reply_text(
                text=self.text_reply_bot_setting,
                reply_markup=self.dynamic_reply_markup["vxma_settings"],
            )
        self.uniq_msg_id.append(msgs.message_id)

    async def vxma_settings_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ) -> None:
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["Method"] == "BACK":
            msgs = await query.edit_message_text(
                text="โปรดเลือกเหรียญดังนี้:", reply_markup=self.coins_settings_key
            )
        elif callback["Method"] == "CHART":
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
            path = candle(
                df, self.vxma_settings["symbol"], self.vxma_settings["timeframe"]
            )
            msgs0 = await query.message.reply_photo(path)
            self.uniq_msg_id.append(msgs0.message_id)
            await query.delete_message()
            msgs = await query.message.reply_text(
                text=self.text_reply_bot_setting,
                reply_markup=self.dynamic_reply_markup["vxma_settings"],
            )
        elif callback["Method"] == "SAVE":
            msgs = await query.edit_message_text(
                text=f"โปรดยืนยัน หากต้องการบันทึกข้อมูลเหรียญ {self.vxma_settings['symbol']}",
                reply_markup=self.reply_markup["vxma_settings_confirm_save"],
            )
        elif callback["Method"] == "DELETE":
            msgs = await query.edit_message_text(
                text=f"โปรดยืนยัน หากต้องการลบข้อมูลเหรียญ {self.vxma_settings['symbol']}",
                reply_markup=self.reply_markup["vxma_settings_confirm_del"],
            )
        elif callback["Method"] in self.vxma_settings.keys():
            self.vxma_selected_state = callback["Method"]
            self.vxma_selected_state_type = callback["Type"]
            if self.vxma_selected_state_type == "bool":
                self.vxma_settings[self.vxma_selected_state] = (
                    False if self.vxma_settings[self.vxma_selected_state] else True
                )
                self.update_inline_keyboard()
                msgs = await query.edit_message_text(
                    text=self.text_reply_bot_setting
                    + f"\n\n{vxma_settings_info[self.vxma_selected_state]} สำเร็จ",
                    reply_markup=self.dynamic_reply_markup["vxma_settings"],
                )
            else:
                text = f"ท่านได้เลือกเมนู {vxma_settings_info[self.vxma_selected_state]} \n\nท่านต้องการแก้ไขใช่หรือไม่?"
                msgs = await query.edit_message_text(
                    text=self.text_reply_bot_setting + f"\n\n{text}",
                    reply_markup=self.reply_markup["vxma_settings_confirm"],
                )
        self.uniq_msg_id.append(msgs.message_id)

    async def vxma_edit_settings_confirm(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["Method"] == "BACK":
            msgs = await query.edit_message_text(
                text=self.text_reply_bot_setting,
                reply_markup=self.dynamic_reply_markup["vxma_settings"],
            )
            self.uniq_msg_id.append(msgs.message_id)
            return ConversationHandler.END
        else:
            msg = await query.edit_message_text(
                text=f"ท่านได้เลือกเมนู {vxma_settings_info[self.vxma_selected_state]} \n\n\nค่าปัจจุบันคือ {self.vxma_settings[self.vxma_selected_state]} โปรดกรอกข้อมูลเพื่อทำการแก้ไข\n\nกด /cancel เพื่อยกเลิก"
            )
            self.ask_msg_id.append(msg.message_id)
            return SETTING_STATE

    async def vxma_get_settings(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        respon = update.message.text
        self.msg_id.append(update.message.message_id)
        try:
            text = f"\nได้ทำการเปลี่ยน {vxma_settings_info[self.vxma_selected_state]}\
จากเดิม : {self.vxma_settings[self.vxma_selected_state]} ไปเป็น {respon} เรียบร้อย"
            if self.vxma_selected_state_type == "int":
                self.vxma_settings[self.vxma_selected_state] = int(respon)
            elif self.vxma_selected_state_type == "float":
                self.vxma_settings[self.vxma_selected_state] = float(respon)
            elif self.vxma_selected_state_type == "str":
                self.vxma_settings[self.vxma_selected_state] = str(respon)

        except Exception as e:
            text = f"\n\nเกิดข้อผิดพลาด :{e}\n\nโปรดทำรายการใหม่อีกครั้ง"
        self.update_inline_keyboard()
        msgs = await update.message.reply_text(
            text=self.text_reply_bot_setting + text,
            reply_markup=self.dynamic_reply_markup["vxma_settings"],
        )
        self.uniq_msg_id.append(msgs.message_id)
        if len(self.ask_msg_id) > 0:
            for id in self.ask_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
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
                reply_markup=self.dynamic_reply_markup["vxma_settings"],
            )
            self.uniq_msg_id.append(msgs.message_id)
        else:
            # For Commands cancel
            self.msg_id.append(update.message.message_id)
            for id in self.uniq_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
            msgs = await update.message.reply_text(
                text=self.text_reply_bot_setting,
                reply_markup=self.dynamic_reply_markup["vxma_settings"],
            )
            self.uniq_msg_id.append(msgs.message_id)
            return ConversationHandler.END

    async def vxma_save_settings_confirm(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["Method"] == "BACK":
            msgs = await query.edit_message_text(
                text=self.text_reply_bot_setting,
                reply_markup=self.dynamic_reply_markup["vxma_settings"],
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
                    reply_markup=self.dynamic_reply_markup["vxma_settings"],
                )
        self.uniq_msg_id.append(msgs.message_id)

    async def vxma_del_settings_confirm(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["Method"] == "BACK":
            msgs = await query.edit_message_text(
                text=self.text_reply_bot_setting,
                reply_markup=self.dynamic_reply_markup["vxma_settings"],
            )
        else:
            try:
                configs = bot_setting()
                configs = configs.drop(self.vxma_settings["id"])
                configs.to_csv("bot_config.csv", index=True)
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
                    reply_markup=self.dynamic_reply_markup["vxma_settings"],
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
        if len(self.ask_msg_id) > 0:
            for id in self.ask_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
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
        """TODO ACTIVE API AND FETCH BALANCE BEFORE SAVED"""
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
                f"ตั้งค่าสำหรับ API {self.sec_info['API_KEY'][:10]} สำเร็จ\n{text}",
                reply_markup=self.reply_markup["secure"],
            )
        except Exception as e:
            msg = await update.message.reply_text(
                f"ตั้งค่าสำหรับ API {self.sec_info['API_KEY'][:10]} เกิดข้อผิดพลาด\n{e}",
                reply_markup=self.reply_markup["secure"],
            )
        self.uniq_msg_id.append(msg.message_id)
        if len(self.ask_msg_id) > 0:
            for id in self.ask_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
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
                text="โปรดเลือกการตั้งค่า",
                reply_markup=self.reply_markup["secure"],
            )
            self.uniq_msg_id.append(msgs.message_id)
        else:
            # For Commands cancel
            self.msg_id.append(update.message.message_id)
            for id in self.uniq_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=self.chat_id, message_id=id
                    )
                except Exception:
                    continue
            msgs = await update.message.reply_text(
                text="โปรดเลือกการตั้งค่า",
                reply_markup=self.reply_markup["secure"],
            )
            self.uniq_msg_id.append(msgs.message_id)
            return ConversationHandler.END

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
            await asyncio.sleep(1)

    async def make_bot_task(self, context: ContextTypes.DEFAULT_TYPE):
        self.bot_trade = BotTrade(
            context, self.chat_id, self.status_bot, self.status_scan
        )
        while True:
            if self.status_bot:
                try:
                    await self.bot_trade.run_bot()
                except Exception as e:
                    print(e)
                    continue
            await asyncio.sleep(1)


def main():
    while True:
        try:
            from dotenv import load_dotenv

            load_dotenv()
            app = Telegram(f"{os.environ['TelegramToken']}")
            app.setup_bot()
        except KeyboardInterrupt:
            return
        else:
            continue


if __name__ == "__main__":
    main()
