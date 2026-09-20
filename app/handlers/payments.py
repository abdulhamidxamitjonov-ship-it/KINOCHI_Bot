from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from app.config import settings
from app.database.database import Session
from app.database.models import User, VipPayment, VipPlan
from app.states.admin_content import VipPurchaseState

router = Router()


def admin_payment_kb(payment_id: str):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='✅ Tasdiqlash', callback_data=f'vip_payment:approve:{payment_id}'),
        InlineKeyboardButton(text='❌ Rad etish', callback_data=f'vip_payment:reject:{payment_id}'),
    ]])


@router.message(VipPurchaseState.waiting_receipt, F.photo)
async def receipt(m: Message, state: FSMContext):
    data = await state.get_data()
    payment_id = data.get('payment_id')
    if not payment_id:
        await state.clear()
        return await m.answer('❌ Faol VIP to‘lovi topilmadi. VIP bo‘limidan qaytadan boshlang.')

    async with Session() as s:
        payment = (await s.execute(
            select(VipPayment).where(VipPayment.payment_id == payment_id).with_for_update()
        )).scalar_one_or_none()
        if not payment:
            await state.clear()
            return await m.answer('❌ To‘lov topilmadi.')
        now = datetime.now(timezone.utc)
        if payment.status != 'PENDING':
            await state.clear()
            return await m.answer('⚠️ Bu to‘lov allaqachon yakunlangan. Yangi VIP to‘lovini boshlang.')
        if payment.expires_at and payment.expires_at <= now:
            payment.status = 'EXPIRED'
            payment.rejection_reason = '5 daqiqalik to‘lov muddati tugagan.'
            await s.commit()
            await state.clear()
            return await m.answer('⏰ 5 daqiqalik to‘lov vaqti tugagan. VIP xaridini qaytadan boshlang.')

        user = await s.get(User, payment.user_id)
        plan = await s.get(VipPlan, payment.plan_id)
        if not user or not plan:
            await state.clear()
            return await m.answer('❌ To‘lov ma’lumotlari topilmadi.')

        payment.receipt_file_id = m.photo[-1].file_id
        await s.commit()

        admin_text = (
            '👑 <b>YANGI VIP TO‘LOVI</b>\n\n'
            f'👤 Ism: {user.first_name or "-"}\n'
            f'🆔 Telegram ID: <code>{user.telegram_id}</code>\n'
            f'🔗 Username: @{user.username if user.username else "-"}\n'
        )
        admin_text += (
            f'\n\n📦 Tarif: <b>{plan.name_uz}</b>'
            f'\n💰 Summa: <b>{payment.amount:,} {payment.currency}</b>'
            f'\n🆔 To‘lov ID: <code>{payment.payment_id}</code>'
            f'\n⏳ Muddati: 5 daqiqa'
            f'\n📌 Holati: <b>PENDING</b>'
        )
        receipt_id = payment.receipt_file_id

    # Send to every configured admin immediately after receipt is stored.
    sent = 0
    for aid in settings.admins:
        try:
            await m.bot.send_photo(aid, receipt_id, caption=admin_text, reply_markup=admin_payment_kb(payment_id))
            sent += 1
        except Exception:
            # One unavailable admin must not block the user's payment record.
            continue

    await state.clear()
    await m.answer(
        '🧾 Chek qabul qilindi.\n'
        f'👑 {plan.name_uz}\n'
        f'💰 {payment.amount:,} UZS\n\n'
        '⏳ Admin tasdiqlashini kuting.'
    )
