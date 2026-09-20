from aiogram.fsm.state import State, StatesGroup

class MovieAddState(StatesGroup):
    waiting_video = State()
    waiting_info = State()

class SeriesAddState(StatesGroup):
    waiting_video = State()
    waiting_info = State()

class SeriesEpisodeAddState(StatesGroup):
    waiting_video = State()
    waiting_season = State()
    waiting_episode = State()

class MovieEditState(StatesGroup):
    waiting_info = State()

class SeriesEditState(StatesGroup):
    waiting_info = State()

class MandatoryAddState(StatesGroup):
    waiting_url = State()

class VipPurchaseState(StatesGroup):
    waiting_receipt = State()
