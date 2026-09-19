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
@router.callback_query(F.data=='mandatory_add_help')
async def add_start(c,state):
 if c.from_user.id not in settings.admins:return await c.answer('Ruxsat yo‘q',show_alert=True)
 await state.set_state(MandatoryAddState.waiting_chat_id);await c.message.answer('➕ Kanal/guruh chat ID sini yuboring. Masalan: -1001234567890');await c.answer()
@router.message(MandatoryAddState.waiting_chat_id)
async def add_id(m,state):
 if m.from_user.id not in settings.admins:return
 try: cid=int(m.text.strip())
 except: return await m.answer('❌ Chat ID noto‘g‘ri.')
 await state.update_data(chat_id=cid);await state.set_state(MandatoryAddState.waiting_url);await m.answer('🔗 Endi kanal/guruh havolasini yuboring.');
@router.message(MandatoryAddState.waiting_url)
async def add_url(m,state):
 if m.from_user.id not in settings.admins:return
 url=m.text.strip();d=await state.get_data()
 try: chat=await m.bot.get_chat(d['chat_id'])
 except Exception as e:return await m.answer('❌ Bot bu chatni ko‘ra olmadi. Botni avval administrator qiling va IDni tekshiring.')
 async with Session() as s:
  s.add(MandatoryChannel(chat_id=chat.id,title=chat.title or str(chat.id),url=url,chat_type=chat.type,tracking_code=f'{chat.id}_{abs(hash(url))%1000000}'));await s.commit()
 await state.clear();await m.answer(f'✅ Majburiy obuna qo‘shildi: {chat.title or chat.id}')
