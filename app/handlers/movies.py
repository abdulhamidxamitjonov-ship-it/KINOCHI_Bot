from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from datetime import datetime, timezone
from app.database.database import Session
from app.database.models import User, Movie, ContentView
from app.services.subscription_service import check_all
from app.config import settings
from app.utils.protection import protect_for_user
from app.utils.entities import deserialize_entities
from app.states.user_content import UserContentState

router = Router()

def vip(u):
    return bool(u.vip_expires_at and u.vip_expires_at > datetime.now(timezone.utc))

@router.message(F.text.in_({'🎬 Kino izlash', '🎬 Найти фильм'}))
async def prompt(m: Message, state: FSMContext):
    await state.set_state(UserContentState.waiting_movie_code)
    await m.answer('🎬 Kino kodini yuboring.')

@router.message(UserContentState.waiting_movie_code, F.text)
async def code(m: Message, state: FSMContext):
    code_value = m.text.strip()
    async with Session() as s:
        u = (await s.execute(select(User).where(User.telegram_id == m.from_user.id))).scalar_one_or_none()
        movie = (await s.execute(select(Movie).where(Movie.code == code_value))).scalar_one_or_none()
        if not u:
            return
        if not movie:
            return await m.answer('❌ Bu kod bilan kino topilmadi. Kino kodini qayta yuboring.')
        if not vip(u) and not await check_all(m.bot, m.from_user.id, s):
            return await m.answer('❌ Barcha majburiy obunalarni bajaring va qaytadan tekshiring.')
        if movie.vip_only and not vip(u):
            return await m.answer('👑 Bu kino faqat VIP uchun.')
        movie.views += 1
        s.add(ContentView(content_type='movie', content_id=movie.id, user_id=u.id))
        await s.commit()
        title = movie.title_ru if u.language == 'ru' else movie.title_uz
        desc = movie.description_ru if u.language == 'ru' else movie.description_uz
        metadata = getattr(movie, 'metadata_text', None) or (
            f'🎬 {title}\n📅 {movie.year or "-"}\n🎭 {movie.genre or "-"}\n'
            f'🌍 {movie.country or "-"}\n⭐ {movie.rating or "-"}\n🔢 Kod: {movie.code}'
            + (f'\n\n📝 {desc}' if desc else '')
        )
        metadata_entities = deserialize_entities(getattr(movie, 'metadata_entities', None) or [])
        video = movie.video_file_id
        poster = movie.poster_file_id
    await state.clear()
    protect = protect_for_user(m.from_user.id, settings.admins)
    if poster:
        await m.answer_photo(poster, caption=title, protect_content=protect)
    if video:
        await m.answer_video(
            video,
            caption=metadata,
            caption_entities=metadata_entities or None,
            protect_content=protect,
        )
