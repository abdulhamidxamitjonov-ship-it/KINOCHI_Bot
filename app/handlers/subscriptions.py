from aiogram import Router,F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from app.database.database import Session
from app.database.models import MandatoryChannel,User
from app.keyboards.user import mandatory
from app.services.subscription_service import check_all
router=Router()
async def show(bot,message,user_id):
 async with Session() as s:
  items=(await s.execute(select(MandatoryChannel).where(MandatoryChannel.active==True))).scalars().all()
  if items and not await check_all(bot,user_id,s): await message.answer('📢 Majburiy obuna',reply_markup=mandatory(items)); return False
 return True
@router.callback_query(F.data=='mandatory_check')
async def check(c):
 async with Session() as s:
  ok=await check_all(c.bot,c.from_user.id,s)
 await c.answer('✅ Obuna tekshirildi!' if ok else '❌ Barcha majburiy obunalarni bajaring va qaytadan tekshiring.',show_alert=True)
@router.callback_query(F.data.startswith('mandatory_sub_'))
async def open_sub(c):
 sid=int(c.data.rsplit('_',1)[1])
 async with Session() as s: sub=(await s.execute(select(MandatoryChannel).where(MandatoryChannel.id==sid))).scalar_one_or_none()
 if sub: await c.message.answer('📢 Majburiy obuna',reply_markup=__import__('aiogram').types.InlineKeyboardMarkup(inline_keyboard=[[__import__('aiogram').types.InlineKeyboardButton(text='📢 Majburiy obuna',url=sub.url)]]))
 await c.answer()
