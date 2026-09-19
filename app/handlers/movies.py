from aiogram import Router,F
from aiogram.types import Message,CallbackQuery
from sqlalchemy import select
from app.database.database import Session
from app.database.models import User,Movie,ContentView
from app.services.subscription_service import can_access,check_all
router=Router()
@router.message(F.text.in_({'🎬 Kino izlash','🎬 Найти фильм'}))
async def search_prompt(m): await m.answer('🎬 Kino kodini yuboring.')
@router.message(F.text.regexp(r'^\w+$'))
async def code(m:Message):
    async with Session() as s:
        u=(await s.execute(select(User).where(User.telegram_id==m.from_user.id))).scalar_one_or_none(); movie=(await s.execute(select(Movie).where(Movie.code==m.text.strip()))).scalar_one_or_none()
        if not u or not movie: return await m.answer('❌ Kontent topilmadi.')
        if not (u.vip_expires_at and u.vip_expires_at > __import__('datetime').datetime.now(__import__('datetime').timezone.utc)) and not await check_all(m.bot,m.from_user.id,s):
            return await m.answer('❌ Barcha majburiy obunalarni bajaring va qaytadan tekshiring.')
        ok,reason=await can_access(s,m.from_user.id,movie.vip_only)
        if not ok: return await m.answer(reason)
        movie.views+=1; s.add(ContentView(content_type='movie',content_id=movie.id,user_id=u.id)); await s.commit()
        title=movie.title_ru if u.language=='ru' else movie.title_uz; desc=movie.description_ru if u.language=='ru' else movie.description_uz
    is_admin = m.from_user.id in __import__('app.config', fromlist=['settings']).settings.admins
    if movie.poster_file_id:
        await m.answer_photo(movie.poster_file_id, caption=desc or title, protect_content=not is_admin)
    if movie.video_file_id:
        await m.answer_video(movie.video_file_id, caption=title, protect_content=not is_admin)
