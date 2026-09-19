from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from app.database.database import Session
from app.database.models import User, Series, Episode, ContentView
from app.services.subscription_service import can_access, check_all
from datetime import datetime, timezone

router = Router()


def active_vip(u):
    return bool(u.vip_expires_at and u.vip_expires_at > datetime.now(timezone.utc))


@router.message(F.text.in_({'📺 Seriallar','📺 Сериалы'}))
async def series_prompt(m):
    await m.answer('📺 Serial kodini yuboring.')


@router.message(F.text.regexp(r'^\w+$'))
async def series_code(m: Message):
    async with Session() as s:
        u = (await s.execute(select(User).where(User.telegram_id == m.from_user.id))).scalar_one_or_none()
        series = (await s.execute(select(Series).where(Series.code == m.text.strip()))).scalar_one_or_none()
        if not u or not series:
            return
        if not active_vip(u) and not await check_all(m.bot, m.from_user.id, s):
            return await m.answer('❌ Barcha majburiy obunalarni bajaring va qaytadan tekshiring.')
        if series.vip_only and not active_vip(u):
            return await m.answer('👑 Bu serial faqat VIP uchun.')
        eps = (await s.execute(select(Episode).where(Episode.series_id == series.id).order_by(Episode.season_number, Episode.episode_number))).scalars().all()
        title = series.title_ru if u.language == 'ru' else series.title_uz
        desc = series.description_ru if u.language == 'ru' else series.description_uz
        poster = series.poster_file_id
    if poster:
        await m.answer_photo(poster, caption=desc or title)
    seasons = sorted({e.season_number for e in eps})
    buttons = [[InlineKeyboardButton(text=f'📺 {s}-FASL', callback_data=f'season:{series.id}:{s}')] for s in seasons]
    buttons.append([InlineKeyboardButton(text='⬅️ Orqaga', callback_data='series_back')])
    await m.answer(f'📺 {title}\n\nFaslni tanlang:', reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith('season:'))
async def season(c: CallbackQuery):
    _, sid, sn = c.data.split(':')
    sid, sn = int(sid), int(sn)
    async with Session() as s:
        u = (await s.execute(select(User).where(User.telegram_id == c.from_user.id))).scalar_one_or_none()
        series = await s.get(Series, sid)
        eps = (await s.execute(select(Episode).where(Episode.series_id == sid, Episode.season_number == sn).order_by(Episode.episode_number))).scalars().all()
        if not u or not series: return await c.answer('Topilmadi.', show_alert=True)
        if not active_vip(u) and not await check_all(c.bot, c.from_user.id, s):
            return await c.answer('Majburiy obunani bajaring.', show_alert=True)
        if series.vip_only and not active_vip(u): return await c.answer('👑 VIP kontent.', show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f'▶️ {e.episode_number}-qism' + (' 🔒' if e.vip_only else ''), callback_data=f'episode:{e.id}')] for e in eps])
    await c.message.edit_text(f'📺 {series.title_ru if u.language == "ru" else series.title_uz}\n\n📺 {sn}-FASL\nQismni tanlang:', reply_markup=kb)
    await c.answer()


@router.callback_query(F.data.startswith('episode:'))
async def episode(c: CallbackQuery):
    eid = int(c.data.split(':')[1])
    async with Session() as s:
        u = (await s.execute(select(User).where(User.telegram_id == c.from_user.id))).scalar_one_or_none()
        ep = await s.get(Episode, eid)
        if not u or not ep: return await c.answer('Topilmadi.', show_alert=True)
        series = await s.get(Series, ep.series_id)
        if not active_vip(u) and not await check_all(c.bot, c.from_user.id, s):
            return await c.answer('Majburiy obunani bajaring.', show_alert=True)
        ok, reason = await can_access(s, c.from_user.id, ep.vip_only or series.vip_only)
        if not ok: return await c.answer(reason, show_alert=True)
        ep.views += 1
        s.add(ContentView(content_type='episode', content_id=ep.id, user_id=u.id))
        await s.commit()
        title = series.title_ru if u.language == 'ru' else series.title_uz
    await c.bot.send_video(c.from_user.id, ep.video_file_id, caption=f'📺 {title}\n🎬 {ep.season_number}-fasl • {ep.episode_number}-qism', protect_content=(c.from_user.id not in settings.admins))
    await c.answer()
