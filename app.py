import asyncio
import os
import pandas as pd
import sqlite3
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

from src.AppData import HELP_MESSAGE, WELCOME_MESSAGE, POSITION_COLLUMN, split_list
from src.AppData.Appdata import AppConfig
from src.Bot import BotTrade
from src.CCXT_Binance import (
    Binance,
    account_balance,
    binance_i,
    get_bidask,
)
import warnings

warnings.filterwarnings("ignore")

## Constanc represent ConversationHandler step
## TRADE HANDLER
T_SYMBOL, T_AMT, T_PRICE, T_TP, T_SL = range(5)
## API MENU
STEP1_API, STEP2_API_SEC = range(5, 7)
## BotSetting
B_RISK, B_MIN_BL, B_SYMBOL = range(7, 10)


class Telegram:
    def __init__(self, token: str):
        self.Token = token
        self.application = ApplicationBuilder().token(self.Token).build()
        self.chat_id = 0
        self.msg_id = []
        self.ask_msg_id = []
        self.uniq_msg_id = []
        self.bot_trade = ""
        self.status_bot = False
        self.status_scan = False
        self.risk = {"max_risk": 50.0, "min_balance": 10.0}
        self.trade_reply_text = ":"
        self.risk_reply_text = ":"
        self.trade_order = {
            "symbol": "",
            "type": "MARKET",
            "price": 0.0,
            "amt": 0.0,
            "tp_price": 0.0,
            "sl_price": 0.0,
        }
        self.sec_info = {
            "API_KEY": "",
            "API_SEC": "",
            "PASS": "",
        }
        self.dynamic_reply_markup = {}
        self.reply_markup = {
            "menu": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "💰เช็คกระเป๋าเงิน",
                            callback_data='{"Mode": "menu", "Method": "CheckBalance"}',
                        ),
                        InlineKeyboardButton(
                            "💹เทรดมือ",
                            callback_data='{"Mode": "menuex", "Method": "Trade"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "📈📉วิเคราะห์กราฟ",
                            callback_data='{"Mode": "menu", "Method": "Analyser"}',
                        ),
                        InlineKeyboardButton(
                            "📊กำไร/ขาดทุน",
                            callback_data='{"Mode": "menu", "Method": "PositionData"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "🤖ตั้งค่าบอท",
                            callback_data='{"Mode": "menu", "Method": "BotSetting"}',
                        ),
                        InlineKeyboardButton(
                            "⚙️ตั้งค่า API",
                            callback_data='{"Mode": "menu", "Method": "apiSetting"}',
                        ),
                        InlineKeyboardButton(
                            "❌ปิด",
                            callback_data='{"Mode": "menu", "Method": "X"}',
                        ),
                    ],
                ]
            ),
            "fiat": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "USDT", callback_data='{"Mode": "fiat", "Method": "USDT"}'
                        ),
                        InlineKeyboardButton(
                            "BUSD", callback_data='{"Mode": "fiat", "Method": "BUSD"}'
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "ทั้งหมด", callback_data='{"Mode": "fiat", "Method": "ALL"}'
                        ),
                        InlineKeyboardButton(
                            "❌ กลับ", callback_data='{"Mode": "fiat", "Method": "BACK"}'
                        ),
                    ],
                ]
            ),
            "secure": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⚙️ตั้งค่า API",
                            callback_data='{"Mode": "secure", "Method": "API"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "⚙️ตั้งค่ารหัสผ่าน",
                            callback_data='{"Mode": "secure", "Method": "PASS"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "❌ กลับ",
                            callback_data='{"Mode": "secure", "Method": "BACK"}',
                        ),
                    ],
                ]
            ),
            "analyse": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "VXMA",
                            callback_data='{"Mode": "analyse", "Method": "VXMA"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "❌ กลับ",
                            callback_data='{"Mode": "analyse", "Method": "BACK"}',
                        )
                    ],
                ]
            ),
            "order_type": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "MARKET",
                            callback_data='{"Mode": "order_type", "Method": "MARKET"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "❌ กลับ",
                            callback_data='{"Mode": "order_type", "Method": "BACK"}',
                        )
                    ],
                ]
            ),
            "pnl": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "ℹ️ดูรายละเอียด",
                            callback_data='{"Mode": "pnl", "Method": "COINS"}',
                        ),
                    ],
                    # [
                    #     InlineKeyboardButton(
                    #         "ตั้งค่า TP/SL",
                    #         callback_data='{"Mode": "pnl", "Method": "TPSL"}',
                    #     ),
                    # ],
                    [
                        InlineKeyboardButton(
                            "❌ กลับ", callback_data='{"Mode": "pnl", "Method": "BACK"}'
                        ),
                    ],
                ]
            ),
        }

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
        }

    def load_database(self) -> None:
        config = AppConfig()
        self.risk["max_risk"] = config.max_margin
        self.risk["min_balance"] = config.min_balance

    def setup_bot(self) -> None:
        # Basic Commands
        self.update_inline_keyboard()

        handlers = [
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
            # trade_handler
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
            # CallbackQueryHandler(
            #     self.trade_short_button,
            #     lambda x: (eval(x))["Mode"] == "trade"
            #     and (eval(x))["Method"] == "LONG",
            # ),
            # # Short Buttons
            # CallbackQueryHandler(
            #     self.trade_short_button,
            #     lambda x: (eval(x))["Mode"] == "trade"
            #     and (eval(x))["Method"] == "SHORT",
            # ),
            # Setting Handler
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
            # Symbols
            # edit symbol fot pnl
            CallbackQueryHandler(
                self.show_info_pnl_per_coin,
                lambda x: (eval(x))["Mode"] == "pnl" and (eval(x))["Method"] == "COINS",
            ),
            CallbackQueryHandler(self.info_pnl_per_coin, filters.Regex("^PNL:")),
            ## TODO add symbols handler for setting
            CallbackQueryHandler(self.edit_config_per_coin, filters.Regex("^COINS:")),
            # secure_handler
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
                fallbacks=[CommandHandler("cancel", self.back_to_menu)],
            ),
            # TODO
            # Handler for unknown commands
            MessageHandler(filters.COMMAND, self.unknown),
        ]

        # Add all Handlers.
        self.application.add_handlers(handlers)
        # Running Background job.
        self.application.job_queue.run_once(self.make_bot_task, when=1)
        self.application.job_queue.run_once(self.clear_task, when=1)

        self.application.run_polling()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sends a message with three Keyboard buttons attached."""
        self.chat_id = update.effective_chat.id
        self.bot_trade.update_chat_id(self.chat_id)
        print("App Started")
        await context.bot.delete_message(
            chat_id=self.chat_id, message_id=update.message.message_id
        )

        msg = await update.message.reply_text(
            WELCOME_MESSAGE, reply_markup=self.reply_key
        )
        self.uniq_msg_id.append(msg.message_id)

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
            await account_balance.update_balance()
            await binance_i.disconnect()
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
            await account_balance.update_balance()
            balance = account_balance.balance
            positions = balance["info"]["positions"]
            status = pd.DataFrame(
                [
                    position
                    for position in positions
                    if float(position["positionAmt"]) != 0
                ],
                columns=POSITION_COLLUMN,
            )
            if len(status.index) > 0:
                text = [
                    f"{status['symbol'][i]} จำนวน {status['positionAmt'][i]} P/L {status['unrealizedProfit'][i]}\n"
                    for i in range(len(status.index))
                ]
                text_reply = self.pnl_reply = "Postion ที่มีการเปิดอยู่\n".join(text)
            else:
                text_reply = "ไม่มี Postion ที่มีการเปิดอยู่"
            msgs = await query.edit_message_text(
                text=text_reply,
                reply_markup=self.reply_markup["pnl"],
            )
        elif callback["Method"] == "BotSetting":
            msgs = await query.edit_message_text(
                text=f"เหรียญที่ดูอยู่ : {self.bot_trade.watchlist}\n\nโปรดเลือกการตั้งค่า",
                reply_markup=self.dynamic_reply_markup["setting"],
            )
        elif callback["Method"] == "apiSetting":
            msgs = await query.edit_message_text(
                text="โปรดเลือกการตั้งค่า",
                reply_markup=self.reply_markup["secure"],
            )
        elif callback["Method"] == "X":
            query.message.delete()

        else:
            msgs = await query.edit_message_text(
                text="Selected again!", reply_markup=self.reply_markup["menu"]
            )
        # Save message_id to delete at the end.
        if isinstance(msgs.message_id, int):
            self.uniq_msg_id.append(msgs.message_id)

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
        fiat_balance = account_balance.fiat_balance

        if callback["Method"] == "ALL":
            msg = (
                "BUSD"
                + f"\nFree   : {round(fiat_balance['BUSD']['free'],2)}$"
                + f"\nMargin : {round(fiat_balance['BUSD']['used'],2)}$"
                + f"\nTotal  : {round(fiat_balance['BUSD']['total'],2)}$\nUSDT"
                + f"\nFree   : {round(fiat_balance['USDT']['free'],2)}$"
                + f"\nMargin : {round(fiat_balance['USDT']['used'],2)}$"
                + f"\nTotal  : {round(fiat_balance['USDT']['total'],2)}$"
            )
        elif callback["Method"] == "BUSD":
            msg = (
                "BUSD"
                + f"\nFree   : {round(fiat_balance['BUSD']['free'],2)}$"
                + f"\nMargin : {round(fiat_balance['BUSD']['used'],2)}$"
                + f"\nTotal  : {round(fiat_balance['BUSD']['total'],2)}$"
            )
        elif callback["Method"] == "USDT":
            msg = (
                "USDT"
                + f"\nFree   : {round(fiat_balance['USDT']['free'],2)}$"
                + f"\nMargin : {round(fiat_balance['USDT']['used'],2)}$"
                + f"\nTotal  : {round(fiat_balance['USDT']['total'],2)}$"
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
            self.trade_reply_text, reply_markup=self.dynamic_reply_markup["trade"]
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
        self.trade_order = {
            "symbol": "",
            "type": "MARKET",
            "price": 0.0,
            "amt": 0.0,
            "tp_price": 0.0,
            "sl_price": 0.0,
        }
        self.trade_order["symbol"] = respon.upper()
        """TODO"""
        exchange = await binance_i.get_exchange()
        self.trade_order["price"] = await get_bidask(
            self.trade_order["symbol"], exchange, "bid"
        )
        await account_balance.update_balance()
        balance = account_balance.balance
        positions = balance["info"]["positions"]
        status = pd.DataFrame(
            [position for position in positions if float(position["positionAmt"]) != 0],
            columns=POSITION_COLLUMN,
        )
        currnet_position = await self.bot_trade.check_current_position(
            self.trade_order["symbol"], status
        )
        await binance_i.disconnect()
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
        self.trade_order["amt"] = float(respon)
        self.update_inline_keyboard()

        msg = await update.message.reply_text(
            self.trade_reply_text,
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
        self.trade_order["tp_price"] = float(respon)
        self.update_inline_keyboard()
        msg = await update.message.reply_text(
            self.trade_reply_text,
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
        self.trade_order["sl_price"] = float(respon)
        self.update_inline_keyboard()

        msg = await update.message.reply_text(
            self.trade_reply_text,
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
                text=self.trade_reply_text,
                reply_markup=self.dynamic_reply_markup["trade"],
            )
        else:
            self.trade_order["type"] = f"{callback['Method']}"
            self.update_inline_keyboard()
            msgs = await query.edit_message_text(
                text=self.trade_reply_text,
                reply_markup=self.dynamic_reply_markup["trade"],
            )
        self.uniq_msg_id.append(msgs.message_id)

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
                self.bot_trade.stop_bot()
            elif not self.status_bot:
                self.status_bot = True
                self.bot_trade.start_bot()
            self.update_inline_keyboard()
            msg = f"เหรียญที่ดูอยู่ : {self.bot_trade.watchlist}\n\nโปรดเลือกการตั้งค่า"
            msgs = await query.edit_message_text(
                text=msg, reply_markup=self.dynamic_reply_markup["setting"]
            )
        elif callback["Method"] == "SCAN":
            if self.status_scan:
                self.status_scan = False
                self.bot_trade.disable_scan()
            elif not self.status_scan:
                self.status_scan = True
                self.bot_trade.enable_scan()
            self.update_inline_keyboard()
            msg = f"เหรียญที่ดูอยู่ : {self.bot_trade.watchlist}\n\nโปรดเลือกการตั้งค่า"
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
                        f"{symbol[:-5]}".replace("/", ""),
                        callback_data=f"COINS:{symbol}",
                    )
                    for symbol in symbol_list
                ]
                for symbol_list in split_list(self.bot_trade.watchlist, 3)
            ]
            coins_key = InlineKeyboardMarkup(
                coins
                + [
                    [
                        InlineKeyboardButton(
                            "❌ กลับ",
                            callback_data="COINS:BACK_TO_MENU",
                        )
                    ]
                ]
            )
            msgs = await query.edit_message_text(text=msg, reply_markup=coins_key)
        self.uniq_msg_id.append(msgs.message_id)

    async def show_info_pnl_per_coin(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        await account_balance.update_balance()
        balance = account_balance.balance
        positions = balance["info"]["positions"]
        status = pd.DataFrame(
            [position for position in positions if float(position["positionAmt"]) != 0],
            columns=POSITION_COLLUMN,
        )
        if len(status.index) > 0:
            positiondata = [
                (
                    f"{status['symbol'][i]}",
                    f"{status['symbol'][i]} P/L {status['unrealizedProfit'][i]}",
                )
                for i in range(len(status.index))
            ]
            msg = "โปรดเลือกเหรียญดังนี้:"
            coins = [
                [
                    InlineKeyboardButton(
                        f"{x}",
                        callback_data=f"PNL:{i}",
                    )
                    for i, x in symbol_list
                ]
                for symbol_list in split_list(positiondata, 3)
            ]
            coins_key = InlineKeyboardMarkup(
                coins
                + [
                    [
                        InlineKeyboardButton(
                            "❌ กลับ",
                            callback_data="PNL:BACK_TO_MENU",
                        )
                    ]
                ]
            )
        else:
            msg = "ท่านไม่มี Position ใด ๆ อยู่ในขณะนี้"
        msgs = await query.edit_message_text(text=msg, reply_markup=coins_key)
        self.uniq_msg_id.append(msgs.message_id)

    async def info_pnl_per_coin(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        callback = query.data
        if callback[4:] == "BACK_TO_MENU":
            msgs = await query.edit_message_text(
                text=f"{self.pnl_reply}",
                reply_markup=self.reply_markup["pnl"],
            )
        else:
            ## TODO EDIT POSITION
            msgs = await query.edit_message_text(
                text=f"ท่านได้เลือกเหรียญ : {callback}",
                reply_markup=self.reply_markup["pnl"],
            )

        self.uniq_msg_id.append(msgs.message_id)

    async def get_max_risk_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE  # pyright: ignore
    ):
        query = update.callback_query
        await query.answer()
        msg = await query.edit_message_text(
            text="โปรดกรอกจำนวนความเสี่ยงที่ท่านรับได้\n\
จำนวนนี้ จะนำไปคำนวนระหว่างความเสี่ยงทั้งหมด และ Postion ในมือ\n\n กด /cancel เพื่อยกเลิก"
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
            text="โปรดกรอกจำนวน กระเ๋าเงินขั้นต่ำที่จะทำการหยุดบอท\n\n กด /cancel เพื่อยกเลิก"
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
        msg = (
            self.risk_reply_text
            + f"เหรียญที่ดูอยู่ : {self.bot_trade.watchlist}\n\nโปรดเลือกการตั้งค่า"
        )
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
        callback = query.data
        symbol = callback[6:]
        msgs = await query.edit_message_text(
            text=f"ท่านได้เลือกเหรียญ : {symbol}",
            reply_markup=self.dynamic_reply_markup["setting"],
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
            balance = exchange.fetch_balance()
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
