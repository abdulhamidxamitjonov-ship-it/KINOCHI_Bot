from sqlalchemy import select
from datetime import datetime,timezone
from app.database.models import MandatoryChannel,User
async def check_all(bot,user_id,s):
    subs=(await s.execute(select(MandatoryChannel).where(MandatoryChannel.active==True))).scalars().all()
    for sub in subs:
        try:
            member=await bot.get_chat_member(sub.chat_id,user_id)
            if member.status in ('left','kicked'): return False
        except Exception: return False
    return True
async def can_access(s,telegram_id,vip_only):
    u=(await s.execute(select(User).where(User.telegram_id==telegram_id))).scalar_one_or_none()
    if not u:return False,'❌ Ro‘yxatdan o‘ting.'
    if vip_only and not (u.vip_expires_at and u.vip_expires_at>datetime.now(timezone.utc)): return False,'👑 Bu kontent faqat VIP uchun.'
    return True,''
