import asyncio
import os
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

from src.AppData import HELP_MESSAGE, WELCOME_MESSAGE
from src.CCXT_Binance import account_balance, binance_i

## Constanc represent ConversationHandler step
STEP1, STEP2 = range(2)


class Telegram:
    def __init__(self, token: str):
        self.Token = token
        self.application = ApplicationBuilder().token(self.Token).build()
        self.chat_id = 0
        self.msg_id = []
        self.ask_msg_id = []
        self.uniq_msg_id = []
        self.status_bot = False
        self.status_scan = False
        self.risk = {"max_risk": 50.0, "min_balance": 10.0}
        self.trade_order = {
            "symbol": "",
            "type": "MARKET",
            "price": 0.0,
            "amt": 0.0,
            "tp_price": 0.0,
            "sl_price": 0.0,
        }
        self.dynamic_reply_markup = {}
        self.reply_markup = {
            "menu": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "เช็คกระเป๋าเงิน",
                            callback_data='{"Mode": "menu", "Method": "CheckBalance"}',
                        ),
                        InlineKeyboardButton(
                            "เทรดมือ",
                            callback_data='{"Mode": "menuex", "Method": "Trade"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "วิเคราะห์กราฟ",
                            callback_data='{"Mode": "menu", "Method": "Analyser"}',
                        ),
                        InlineKeyboardButton(
                            "กำไร/ขาดทุน",
                            callback_data='{"Mode": "menu", "Method": "PositionData"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "ตั้งค่าบอท",
                            callback_data='{"Mode": "menu", "Method": "BotSetting"}',
                        ),
                        InlineKeyboardButton(
                            "ตั้งค่า API",
                            callback_data='{"Mode": "menu", "Method": "apiSetting"}',
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
                            "กลับ", callback_data='{"Mode": "fiat", "Method": "BACK"}'
                        ),
                    ],
                ]
            ),
            "secure": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "ตั้งค่า API",
                            callback_data='{"Mode": "secure", "Method": "API"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "ตั้งค่ารหัสผ่าน",
                            callback_data='{"Mode": "secure", "Method": "PASS"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "กลับ", callback_data='{"Mode": "secure", "Method": "BACK"}'
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
                            "กลับ",
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
                            "กลับ",
                            callback_data='{"Mode": "order_type", "Method": "BACK"}',
                        )
                    ],
                ]
            ),
            "pnl": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "ดูรายละเอียด",
                            callback_data='{"Mode": "pnl", "Method": "COINS"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "ตั้งค่า TP/SL",
                            callback_data='{"Mode": "pnl", "Method": "TPSL"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "กลับ", callback_data='{"Mode": "pnl", "Method": "BACK"}'
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
                            f"จำนวน : {self.trade_order['amt']}",
                            callback_data='{"Mode": "trade", "Method": "Amt"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            f"TP : {self.trade_order['tp_price']}",
                            callback_data='{"Mode": "trade", "Method": "TP"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            f"SL : {self.trade_order['sl_price']}",
                            callback_data='{"Mode": "trade", "Method": "SL"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "LONG", callback_data='{"Mode": "trade", "Method": "LONG"}'
                        ),
                        InlineKeyboardButton(
                            "SHORT",
                            callback_data='{"Mode": "trade", "Method": "SHORT"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "เปลี่ยนเหรียญ",
                            callback_data='{"Mode": "trade", "Method": "Change"}',
                        ),
                        InlineKeyboardButton(
                            "กลับ", callback_data='{"Mode": "trade", "Method": "BACK"}'
                        ),
                    ],
                ]
            ),
            "setting": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            f"BOT STATUS : {'ON' if self.status_bot else 'OFF'}",
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
                            f"SCAN : {'ON' if self.status_scan else 'OFF'}",
                            callback_data='{"Mode": "setting", "Method": "SCAN"}',
                        ),
                        InlineKeyboardButton(
                            "กลับ",
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
                            "กลับ",
                            callback_data='{"Mode": "risk", "Method": "BACK"}',
                        ),
                    ],
                ]
            ),
        }

    def setup_bot(self) -> None:
        # Basic Commands
        self.update_inline_keyboard()
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("menu", self.menu_command))
        self.application.add_handler(CommandHandler("clear", self.clear_command))

        # Handler for Back to menu for all menu
        self.application.add_handler(
            CallbackQueryHandler(
                self.back_to_menu,
                lambda x: (eval(x))["Mode"]
                in ["fiat", "trade", "analyse", "pnl", "setting", "secure"]
                and (eval(x))["Method"] == "BACK",
            )
        )

        # Handlers set for buttons workarounds.
        self.application.add_handler(
            CallbackQueryHandler(
                self.button_menu, lambda x: (eval(x))["Mode"] == "menu"
            )
        )
        self.application.add_handler(
            CallbackQueryHandler(
                self.fiat_handler, lambda x: (eval(x))["Mode"] == "fiat"
            )
        )
        self.application.add_handler(
            CallbackQueryHandler(
                self.setting_handler, lambda x: (eval(x))["Mode"] == "setting"
            )
        )

        self.application.add_handler(
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.trade_handler,
                        lambda x: (eval(x))["Mode"] == "menuex"
                        and (eval(x))["Method"] == "Trade",
                    )
                ],
                states={
                    STEP1: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, self.update_trade_symbol
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.back_to_menu)],
            )
        )

        # Handler for unknown commands
        self.application.add_handler(MessageHandler(filters.COMMAND, self.unknown))

        # Running Background job.
        self.application.job_queue.run_repeating(self.clear_task, interval=2, first=0)

        self.application.run_polling()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sends a message with three Keyboard buttons attached."""
        self.chat_id = update.effective_chat.id
        print("App Started")
        await context.bot.delete_message(
            chat_id=self.chat_id, message_id=update.message.message_id
        )

        msg = await update.message.reply_text(
            WELCOME_MESSAGE, reply_markup=self.reply_key
        )
        self.uniq_msg_id.append(msg.message_id)

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sends a message with three inline buttons attached."""
        await context.bot.delete_message(
            chat_id=self.chat_id, message_id=update.message.message_id
        )
        msg = await update.message.reply_text(
            "Please choose:", reply_markup=self.reply_markup["menu"]
        )
        self.uniq_msg_id.append(msg.message_id)

    async def fiat_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """If received CheckBalance Mode do this"""
        query = update.callback_query

        await query.answer()
        callback = eval(query.data)
        await account_balance.update_balance()
        await binance_i.disconnect()
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

    async def trade_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """If received CheckBalance Mode do this"""
        query = update.callback_query
        await query.answer()
        msg = await query.edit_message_text(text="โปรดใส่ชื่อเหรียญ ")
        self.ask_msg_id.append(msg.message_id)
        return STEP1

    async def update_trade_symbol(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        respon = update.message.text
        self.trade_order["symbol"] = respon.upper()
        msg = await update.message.reply_text(
            f"คู่เหรียญ  {self.trade_order['symbol']}\nราคาปัจจุบัน : 26,880",
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

    async def analyse_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
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

    async def setting_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["Method"] == "BOT":
            self.status_bot = False if self.status_bot else True
            self.update_inline_keyboard()
            msg = "เหรียญที่ดูอยู่ : {watchlist}\n\nโปรดเลือกการตั้งค่า"
            msgs = await query.edit_message_text(
                text=msg, reply_markup=self.dynamic_reply_markup["setting"]
            )
        self.uniq_msg_id.append(msgs.message_id)

    async def back_to_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        msg = "Please choose:"
        try:
            await query.answer()
            msgs = await query.edit_message_text(
                text=msg, reply_markup=self.reply_markup["menu"]
            )
        except Exception:
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

    async def button_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Parses the CallbackQuery and updates the message text."""
        query = update.callback_query

        await query.answer()
        callback = eval(query.data)
        ## Main menu will be here
        if callback["Method"] == "CheckBalance":
            msgs = await query.edit_message_text(
                text="โปรดเลือกกระเป๋าเงินเฟียต",
                reply_markup=self.reply_markup["fiat"],
            )
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
            msgs = await query.edit_message_text(
                text="Postion ที่มีการเปิดอยู่\n{position_data}",
                reply_markup=self.reply_markup["pnl"],
            )
        elif callback["Method"] == "BotSetting":
            msgs = await query.edit_message_text(
                text="เหรียญที่ดูอยู่ : {watchlist}\n\nโปรดเลือกการตั้งค่า",
                reply_markup=self.dynamic_reply_markup["setting"],
            )
        elif callback["Method"] == "apiSetting":
            msgs = await query.edit_message_text(
                text="โปรดเลือกการตั้งค่า",
                reply_markup=self.reply_markup["secure"],
            )

        else:
            msgs = await query.edit_message_text(
                text="Selected again!", reply_markup=self.reply_markup["menu"]
            )
        # Save message_id to delete at the end.
        self.uniq_msg_id.append(msgs.message_id)

    async def clear_task(self):
        while True:
            if len(self.msg_id) > 0:
                for id in self.msg_id:
                    try:
                        await self.application.bot.delete_message(
                            chat_id=self.chat_id, message_id=id
                        )
                        self.msg_id.remove(id)
                    except Exception:
                        continue
            await asyncio.sleep(1)

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
