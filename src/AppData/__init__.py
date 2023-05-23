from collections import deque
from src.AppData.Appdata import (
    ColorCS,
    Last_update,
    Timer,
)

colorCS = ColorCS()
lastUpdate = Last_update()
candle_ohlc = {}
timer = Timer()
notify_history = {}

HELP_MESSAGE = "\
กด /start ในครั้งแรก เพื่อให้บอทจำแชท\n\
กด /clear เพื่อล้างข้อความสนทนา(ไม่ลบแจ้งเตือน)\n\
กด /help หากเกิดข้อสงสัย\n\
กด /menu เพื่อแสดงเมนูบริหารความเสี่ยง"

WELCOME_MESSAGE = "\
สวัสดีค่ะนายท่าน ดิฉันคือผู้ช่วย จัดการ/บริหาร ความเสี่ยงของนายท่าน\n\
กด /clear เพื่อล้างข้อความสนทนา(ไม่ลบแจ้งเตือน)\n\
กด /help หากเกิดข้อสงสัย\n\
มาเริ่มกันเลย! กด /menu เพื่อแสดงเมนูบริหารความเสี่ยง"

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


def retry(max_retries, on_fail):
    def wrapper(fn):
        def inner(*args, **kwargs):
            so_far = 0
            exceptions = {}
            while so_far <= max_retries:
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    exceptions[type(e)] = str(e)
                    so_far += 1
            return on_fail("\n".join(exceptions.values()))

        return inner

    return wrapper
