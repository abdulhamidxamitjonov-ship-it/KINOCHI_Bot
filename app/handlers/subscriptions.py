from aiogram import Router,F
from aiogram.types import CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton,Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from app.database.database import Session
from app.database.models import MandatoryChannel,User,SubscriptionTracking
from app.keyboards.user import mandatory
from app.services.subscription_service import check_all
from app.config import settings
from app.states.admin_content import MandatoryAddState
router=Router()
async def show(bot,message,user_id):
 async with Session() as s:
  items=(await s.execute(select(MandatoryChannel).where(MandatoryChannel.active==True))).scalars().all()
  if items and not await check_all(bot,user_id,s): await message.answer('📢 Majburiy obuna',reply_markup=mandatory(items)); return False
 return True
@router.callback_query(F.data=='mandatory_check')
async def check(c):
 async with Session() as s: ok=await check_all(c.bot,c.from_user.id,s)
 await c.answer('✅ Obuna tekshirildi!' if ok else '❌ Barcha majburiy obunalarni bajaring va qaytadan tekshiring.',show_alert=True)
 if ok: await c.message.delete()
@router.callback_query(F.data.startswith('mandatory_sub_'))
async def open_sub(c):
 sid=int(c.data.rsplit('_',1)[1])
 async with Session() as s:x=await s.get(MandatoryChannel,sid)
 if x: await c.message.answer('📢 Majburiy obuna',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📢 Majburiy obuna',url=x.url)]]))
 await c.answer()
