from aiogram.fsm.state import State, StatesGroup

class MovieAddState(StatesGroup):
    waiting_video = State()
    waiting_info = State()

class SeriesAddState(StatesGroup):
    waiting_video = State()
    waiting_info = State()

class MandatoryAddState(StatesGroup):
    waiting_url = State()

class VipPurchaseState(StatesGroup):
    waiting_receipt = State()
