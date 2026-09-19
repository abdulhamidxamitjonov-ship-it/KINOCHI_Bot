from aiogram.fsm.state import State, StatesGroup


class MovieAddState(StatesGroup):
    waiting_video = State()
    waiting_info = State()
    waiting_poster = State()


class SeriesAddState(StatesGroup):
    waiting_video = State()
    waiting_info = State()
    waiting_poster = State()
