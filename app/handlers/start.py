from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from datetime import datetime, timezone
from app.database.database import Session
from app.database.models import User, Movie, Series, Episode
from app.keyboards.user import lang, main, phone
from app.handlers.subscriptions import show
from app.locales.uz import TEXT as UZ
from app.locales.ru import TEXT as RU
from app.services.subscription_service import check_all, can_access

router = Router()


def t(u, k):
    return (UZ if u.language == 'uz' else RU)[k]


def active_vip(u):
    return bool(u.vip_expires_at and u.vip_expires_at > datetime.now(timezone.utc))


async def open_payload(m: Message, payload: str):
    if not payload:
        return False
    kind, _, code = payload.partition('_')
    if not code:
        return False
    async with Session() as s:
        u = (await s.execute(select(User).where(User.telegram_id == m.from_user.id))).scalar_one_or_none()
        if not u:
            return False
        if not active_vip(u) and not await check_all(m.bot, m.from_user.id, s):
            await m.answer('❌ Barcha majburiy obunalarni bajaring va qaytadan tekshiring.')
            return True
        if kind == 'movie':
            content = (await s.execute(select(Movie).where(Movie.code == code))).scalar_one_or_none()
            if not content:
                await m.answer('❌ Kino topilmadi.')
                return True
            ok, reason = await can_access(s, m.from_user.id, content.vip_only)
            if not ok:
                await m.answer(reason)
                return True
            content.views += 1
            await s.commit()
            title = content.title_ru if u.language == 'ru' else content.title_uz
            desc = content.description_ru if u.language == 'ru' else content.description_uz
            if content.poster_file_id:
                await m.answer_photo(content.poster_file_id, caption=desc or title)
            if content.video_file_id:
                await m.answer_video(content.video_file_id, caption=title)
            return True
        if kind == 'series':
            content = (await s.execute(select(Series).where(Series.code == code))).scalar_one_or_none()
            if not content:
                await m.answer('❌ Serial topilmadi.')
                return True
            if content.vip_only and not active_vip(u):
                await m.answer('👑 Bu serial faqat VIP uchun.')
                return True
            eps = (await s.execute(select(Episode).where(Episode.series_id == content.id).order_by(Episode.season_number, Episode.episode_number))).scalars().all()
            title = content.title_ru if u.language == 'ru' else content.title_uz
            desc = content.description_ru if u.language == 'ru' else content.description_uz
            if content.poster_file_id:
                await m.answer_photo(content.poster_file_id, caption=desc or title)
            seasons = sorted({e.season_number for e in eps})
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f'📺 {sn}-FASL', callback_data=f'season:{content.id}:{sn}')] for sn in seasons
            ])
            await m.answer(f'📺 {title}\n\nFaslni tanlang:', reply_markup=kb)
            return True
    return False


@router.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    payload = ''
    if m.text and ' ' in m.text:
        payload = m.text.split(' ', 1)[1].strip()
    async with Session() as s:
        u = (await s.execute(select(User).where(User.telegram_id == m.from_user.id))).scalar_one_or_none()
        if not u:
            u = User(telegram_id=m.from_user.id, username=m.from_user.username, first_name=m.from_user.first_name)
            s.add(u)
            await s.commit()
    await state.update_data(start_payload=payload)
    await m.answer('Tilni tanlang / Выберите язык:', reply_markup=lang())


@router.callback_query(F.data.startswith('lang_'))
async def language(c: CallbackQuery, state: FSMContext):
    lng = c.data.split('_')[1]
    async with Session() as s:
        u = (await s.execute(select(User).where(User.telegram_id == c.from_user.id))).scalar_one()
        u.language = lng
        await s.commit()
    await c.message.answer((UZ if lng == 'uz' else RU)['welcome'], reply_markup=phone())
    await c.answer()


@router.message(F.contact)
async def contact(m: Message, state: FSMContext):
    if m.contact.user_id and m.contact.user_id != m.from_user.id:
        return await m.answer('❌ Faqat o‘z Telegram akkauntingiz raqamini yuboring.')
    async with Session() as s:
        u = (await s.execute(select(User).where(User.telegram_id == m.from_user.id))).scalar_one()
        u.registration_status = True
        await s.commit()
        text = t(u, 'main')
        lng = u.language
    data = await state.get_data()
    payload = data.get('start_payload', '')
    await state.clear()
    if await show(m.bot, m, m.from_user.id):
        await m.answer(text, reply_markup=main(lng == 'ru'))
        if payload:
            await open_payload(m, payload)
