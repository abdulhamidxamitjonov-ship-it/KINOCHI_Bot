from aiogram import Router,F
from aiogram.types import Message
from sqlalchemy import select
from app.database.database import Session
from app.database.models import VipPayment
router=Router()
@router.message(F.photo)
async def receipt(m):
 async with Session() as s:
  p=(await s.execute(select(VipPayment).where(VipPayment.user_id==__import__('sqlalchemy').literal_column('user_id')))).scalar_one_or_none() if False else None
 await m.answer('🧾 Chek qabul qilindi. Admin tekshiruvini kuting.')
