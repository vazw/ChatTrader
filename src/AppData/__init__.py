from src.AppData.Appdata import (
    ColorCS,
    Last_update,
    PositionMode,
    Timer,
)

colorCS = ColorCS()
lastUpdate = Last_update()
currentMode = PositionMode()
candle_ohlc = {}
timer = Timer()
notify_history = {}

HELP_MESSAGE = "\
Use /start to test this bot.\n\
Use /help for help menu\n\
Use /menu for App menu\n\
Use /clear to clear message\n\
after Started use inline menu to perfrom task"

WELCOME_MESSAGE = "\
Welcome to the AssistancBot\n\
Use /help for help menu\n\
Use /clear to clear message\n\
after Started Use /menu for App menu's inline menu to perfrom task"
