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
    MessageHandler,
    filters,
)

from src.AppData import HELP_MESSAGE, WELCOME_MESSAGE
from src.CCXT_Binance import account_balance, binance_i


class Telegram:
    def __init__(self, token: str):
        self.Token = token
        self.application = ApplicationBuilder().token(self.Token).build()
        self.msg_id = []
        self.chat_id = 0
        self.uniq_msg_id = []

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
            "trade": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "USDT", callback_data='{"Mode": "trade", "Method": "USDT"}'
                        ),
                        InlineKeyboardButton(
                            "BUSD", callback_data='{"Mode": "trade", "Method": "BUSD"}'
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "ทั้งหมด",
                            callback_data='{"Mode": "trade", "Method": "ALL"}',
                        ),
                        InlineKeyboardButton(
                            "กลับ", callback_data='{"Mode": "trade", "Method": "BACK"}'
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
            "setting": InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "BOT STATUS : {status_bot}",
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
                            "SCAN : {status_scan}",
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
                            "ความเสี่ยงที่รับได้ : {status_risk}",
                            callback_data='{"Mode": "risk", "Method": "MAX_RISK"}',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "จะหยุดบอทเมื่อเงินเหลือ : {min_balance}",
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

    def setup_bot(self) -> None:
        # Basic Commands
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

        # Handler for unknown commands
        self.application.add_handler(MessageHandler(filters.COMMAND, self.unknown))

        self.application.run_polling()
        self.application.create_task(self.clear_task())

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
        pass

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

    async def back_to_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        await query.answer()
        callback = eval(query.data)
        if callback["Method"] == "BACK":
            msg = "Please choose:"
            msgs = await query.edit_message_text(
                text=msg, reply_markup=self.reply_markup["menu"]
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
                reply_markup=self.reply_markup["setting"],
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
        delete_list = self.uniq_msg_id + self.msg_id
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
