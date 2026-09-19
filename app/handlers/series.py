from aiogram import Router,F
from aiogram.types import Message,CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton
from sqlalchemy import select
from datetime import datetime,timezone
from app.database.database import Session
from app.database.models import User,Series,Episode,ContentView
from app.services.subscription_service import check_all
from app.config import settings
router=Router()
def vip(u):return bool(u.vip_expires_at and u.vip_expires_at>datetime.now(timezone.utc))
@router.message(F.text.in_({'📺 Seriallar','📺 Сериалы'}))
async def prompt(m):await m.answer('📺 Serial kodini yuboring.')
@router.message(F.text.regexp(r'^\w+$'))
async def code(m):
 async with Session() as s:
  u=(await s.execute(select(User).where(User.telegram_id==m.from_user.id))).scalar_one_or_none(); x=(await s.execute(select(Series).where(Series.code==m.text.strip()))).scalar_one_or_none()
  if not u or not x:return
  if not vip(u) and not await check_all(m.bot,m.from_user.id,s):return await m.answer('❌ Barcha majburiy obunalarni bajaring va qaytadan tekshiring.')
  if x.vip_only and not vip(u):return await m.answer('👑 Bu serial faqat VIP uchun.')
  eps=(await s.execute(select(Episode).where(Episode.series_id==x.id).order_by(Episode.season_number,Episode.episode_number))).scalars().all(); title=x.title_ru if u.language=='ru' else x.title_uz
  poster=x.poster_file_id
 if poster:await m.answer_photo(poster,caption=title,protect_content=m.from_user.id not in settings.admins)
 seasons=sorted({e.season_number for e in eps}); await m.answer(f'📺 {title}\n\nFaslni tanlang:',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f'📺 {n}-FASL',callback_data=f'season:{x.id}:{n}')] for n in seasons]))
@router.callback_query(F.data.startswith('season:'))
async def season(c):
 _,sid,sn=c.data.split(':');sid=int(sid);sn=int(sn)
 async with Session() as s:
  u=(await s.execute(select(User).where(User.telegram_id==c.from_user.id))).scalar_one_or_none(); x=await s.get(Series,sid); eps=(await s.execute(select(Episode).where(Episode.series_id==sid,Episode.season_number==sn).order_by(Episode.episode_number))).scalars().all()
  if not u or not x:return await c.answer('Topilmadi',show_alert=True)
  if not vip(u) and not await check_all(c.bot,c.from_user.id,s):return await c.answer('Majburiy obunani bajaring.',show_alert=True)
  if x.vip_only and not vip(u):return await c.answer('👑 VIP kontent.',show_alert=True)
 kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f'▶️ {e.episode_number}-qism'+(' 🔒' if e.vip_only else ''),callback_data=f'episode:{e.id}')] for e in eps]); await c.message.edit_text(f'📺 {x.title_ru if u.language=="ru" else x.title_uz}\n\n📺 {sn}-FASL\nQismni tanlang:',reply_markup=kb);await c.answer()
@router.callback_query(F.data.startswith('episode:'))
async def episode(c):
 eid=int(c.data.split(':')[1])
 async with Session() as s:
  u=(await s.execute(select(User).where(User.telegram_id==c.from_user.id))).scalar_one_or_none();e=await s.get(Episode,eid)
  if not u or not e:return await c.answer('Topilmadi',show_alert=True)
  x=await s.get(Series,e.series_id)
  if not vip(u) and not await check_all(c.bot,c.from_user.id,s):return await c.answer('Majburiy obunani bajaring.',show_alert=True)
  if (e.vip_only or x.vip_only) and not vip(u):return await c.answer('👑 VIP kontent.',show_alert=True)
  e.views+=1;s.add(ContentView(content_type='episode',content_id=e.id,user_id=u.id));await s.commit();title=x.title_ru if u.language=='ru' else x.title_uz;vid=e.video_file_id
 await c.bot.send_video(c.from_user.id,vid,caption=f'📺 {title}\n🎬 {e.season_number}-fasl • {e.episode_number}-qism',protect_content=c.from_user.id not in settings.admins);await c.answer()
