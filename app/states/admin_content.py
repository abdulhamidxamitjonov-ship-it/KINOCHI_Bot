from aiogram.fsm.state import State,StatesGroup
class MovieAddState(StatesGroup): waiting_video=State(); waiting_info=State(); waiting_poster=State()
class SeriesAddState(StatesGroup): waiting_video=State(); waiting_info=State(); waiting_poster=State()
class MandatoryAddState(StatesGroup): waiting_chat_id=State(); waiting_url=State()
