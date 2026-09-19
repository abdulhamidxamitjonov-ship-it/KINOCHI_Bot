from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from app.database.models import VipPayment
from app.database.database import Session
from app.states.admin_content import MovieAddState, SeriesAddState

router = Router()

@router.message(F.photo)
async def receipt(m: Message, state: FSMContext):
    # Never treat an admin's movie/series poster as a payment receipt.
    current = await state.get_state()
    if current in {
        MovieAddState.waiting_poster.state,
        SeriesAddState.waiting_poster.state,
        MovieAddState.waiting_video.state,
        SeriesAddState.waiting_video.state,
        MovieAddState.waiting_info.state,
        SeriesAddState.waiting_info.state,
    }:
        return

    # Accept a receipt only when the user has a pending VIP payment.
    async with Session() as s:
        from sqlalchemy import select
        from app.database.models import User
        u = (await s.execute(
            select(User).where(User.telegram_id == m.from_user.id)
        )).scalar_one_or_none()
        if not u:
            return

        payment = (await s.execute(
            select(VipPayment)
            .where(VipPayment.user_id == u.id, VipPayment.status == 'PENDING')
            .order_by(VipPayment.created_at.desc())
        )).scalars().first()

        if not payment:
            return

        payment.receipt_file_id = m.photo[-1].file_id
        await s.commit()

    await m.answer('🧾 Chek qabul qilindi. Admin tekshiruvini kuting.')
