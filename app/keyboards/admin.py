from aiogram.types import InlineKeyboardMarkup,InlineKeyboardButton,ReplyKeyboardMarkup,KeyboardButton
def menu():
 r=[['🎬 Kinolar','📺 Seriallar'],['👑 VIP','💳 To‘lovlar'],['📢 Majburiy obuna','🎁 Referallar'],['📣 Reklama','👥 Foydalanuvchilar'],['📊 Statistika','⚙️ Sozlamalar']]
 return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=x) for x in row] for row in r],resize_keyboard=True)
def confirm(prefix): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Ha',callback_data=f'{prefix}:yes'),InlineKeyboardButton(text='❌ Bekor',callback_data=f'{prefix}:no')]])
