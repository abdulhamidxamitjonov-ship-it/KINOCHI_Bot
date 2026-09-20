from aiogram.fsm.state import State, StatesGroup


class UserContentState(StatesGroup):
    waiting_movie_code = State()
    waiting_series_code = State()
