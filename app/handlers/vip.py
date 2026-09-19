from aiogram import Router,F
from aiogram.types import Message
from sqlalchemy import select
from app.database.database import Session
from app.database.models import User,VipPlan,VipPayment
from app.keyboards.user import main
from app.config import settings
from uuid import uuid4
router=Router()
@router.message(F.text.in_({'👑 VIP','👑 VIP'}))
async def vip(m):
 async with Session() as s:
  plans=(await s.execute(select(VipPlan).where(VipPlan.active==True))).scalars().all(); u=(await s.execute(select(User).where(User.telegram_id==m.from_user.id))).scalar_one()
 if not plans:return await m.answer('VIP tariflari mavjud emas.')
 for p in plans:
  pid='VIP-'+uuid4().hex[:10].upper(); s.add(VipPayment(payment_id=pid,user_id=u.id,plan_id=p.id,amount=p.price));
  await m.answer(f'👑 {p.name_uz}\n💰 {p.price:,} UZS\n\n💳 To‘lov ID: {pid}\n\nUZCARD: {settings.uzcard_card_number}\nKarta egasi: {settings.uzcard_card_name}\n\n🧾 To‘lovni amalga oshirib, chekni shu chatga yuboring.')
 await s.commit()
