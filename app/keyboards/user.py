from aiogram.types import InlineKeyboardMarkup,InlineKeyboardButton,ReplyKeyboardMarkup,KeyboardButton

def lang(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🇺🇿 O‘zbek',callback_data='lang_uz'),InlineKeyboardButton(text='🇷🇺 Русский',callback_data='lang_ru')]])
def main(ru=False):
    rows=[['🎬 Найти фильм','📺 Сериалы'],['👑 VIP','🎁 Реферал'],['👤 Профиль','📢 Наш канал'],['🌐 Язык','ℹ️ О боте']] if ru else [['🎬 Kino izlash','📺 Seriallar'],['👑 VIP','🎁 Referal'],['👤 Profil','📢 Kanalimiz'],['🌐 Til','ℹ️ Bot haqida']]
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=x) for x in r] for r in rows],resize_keyboard=True)
def mandatory(items):
    rows=[[InlineKeyboardButton(text='📢 Majburiy obuna',callback_data=f'mandatory_sub_{x.id}')] for x in items]
    rows.append([InlineKeyboardButton(text='🔄 Tekshirish',callback_data='mandatory_check')]); return InlineKeyboardMarkup(inline_keyboard=rows)
def phone(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='📱 Raqamni yuborish',request_contact=True)]],resize_keyboard=True,one_time_keyboard=True)
