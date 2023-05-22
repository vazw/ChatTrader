from collections import deque
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

POSITION_COLLUMN = [
    "symbol",
    "entryPrice",
    "positionSide",
    "unrealizedProfit",
    "positionAmt",
    "initialMargin",
    "leverage",
]


def split_list(input_list, chunk_size):
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
