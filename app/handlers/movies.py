from aiogram import Router,F
from aiogram.types import Message
from sqlalchemy import select
from datetime import datetime,timezone
from app.database.database import Session
from app.database.models import User,Movie,ContentView
from app.services.subscription_service import check_all
from app.config import settings
router=Router()
def vip(u): return bool(u.vip_expires_at and u.vip_expires_at>datetime.now(timezone.utc))
@router.message(F.text.in_({'🎬 Kino izlash','🎬 Найти фильм'}))
async def prompt(m): await m.answer('🎬 Kino kodini yuboring.')
@router.message(F.text.regexp(r'^\w+$'))
async def code(m):
    async with Session() as s:
        u=(await s.execute(select(User).where(User.telegram_id==m.from_user.id))).scalar_one_or_none(); movie=(await s.execute(select(Movie).where(Movie.code==m.text.strip()))).scalar_one_or_none()
        if not u or not movie:return
        if not vip(u) and not await check_all(m.bot,m.from_user.id,s): return await m.answer('❌ Barcha majburiy obunalarni bajaring va qaytadan tekshiring.')
        if movie.vip_only and not vip(u):return await m.answer('👑 Bu kino faqat VIP uchun.')
        movie.views+=1;s.add(ContentView(content_type='movie',content_id=movie.id,user_id=u.id));await s.commit(); title=movie.title_ru if u.language=='ru' else movie.title_uz; desc=movie.description_ru if u.language=='ru' else movie.description_uz
        poster,video=movie.poster_file_id,movie.video_file_id
    protect=m.from_user.id not in settings.admins
    if poster: await m.answer_photo(poster,caption=desc or title,protect_content=protect)
    if video: await m.answer_video(video,caption=title,protect_content=protect)
