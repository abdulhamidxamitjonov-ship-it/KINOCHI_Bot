from aiogram import Router,F
from aiogram.types import Message
from sqlalchemy import select
from app.database.database import Session
from app.database.models import User
from app.utils.deep_links import referral_link
from app.config import settings
from datetime import datetime,timezone
router=Router()
@router.message(F.text.in_({'👤 Profil','👤 Профиль'}))
async def profile(m):
 async with Session() as s:u=(await s.execute(select(User).where(User.telegram_id==m.from_user.id))).scalar_one()
 vip=u.vip_expires_at and u.vip_expires_at>datetime.now(timezone.utc)
 await m.answer(f'👤 Profil\n🆔 {u.telegram_id}\n👑 VIP: {"Faol" if vip else "Yo‘q"}\n🎁 Referallar: {u.qualified_referral_count}/50\n🔗 {referral_link(settings.bot_username,u.telegram_id)}')
@router.message(F.text.in_({'🎁 Referal','🎁 Реферал'}))
async def ref(m): await profile(m)
