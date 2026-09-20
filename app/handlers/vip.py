from datetime import datetime, timedelta, timezone
from uuid import uuid4

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from app.database.database import Session
from app.database.models import User, VipPlan, VipPayment
from app.config import settings
from app.states.admin_content import VipPurchaseState

router = Router()
PAYMENT_TTL_MINUTES = 5


def plans_kb(plans):
    rows = []
    for p in plans:
        rows.append([InlineKeyboardButton(
            text=f"{p.name_uz} — {p.price:,} UZS",
            callback_data=f"vip_plan:{p.id}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def card_text():
    # VIP payments use only the HUMO card configured in ENV.
    # Do not fall back to UZCARD, VISA, or MASTERCARD.
    if settings.humo_card_number:
        return (
            f"💳 HUMO\n{settings.humo_card_number}\n"
            f"👤 Karta egasi: {settings.humo_card_name or '-'}"
        )
    return "❌ HUMO karta ma’lumotlari sozlanmagan. Admin ENV sozlamalarini tekshirsin."


@router.message(F.text.in_({'👑 VIP'}))
async def vip_menu(m: Message):
    async with Session() as s:
        plans = (await s.execute(
            select(VipPlan).where(VipPlan.active.is_(True)).order_by(VipPlan.days)
        )).scalars().all()
    if not plans:
        return await m.answer('👑 Hozircha VIP tariflari mavjud emas.')
    await m.answer(
        '👑 <b>VIP OBUNA</b>\n\n'
        'O‘zingizga kerakli tarifni tanlang:',
        reply_markup=plans_kb(plans)
    )


@router.callback_query(F.data.startswith('vip_plan:'))
async def choose_plan(c: CallbackQuery, state: FSMContext):
    plan_id = int(c.data.split(':', 1)[1])
    async with Session() as s:
        user = (await s.execute(select(User).where(User.telegram_id == c.from_user.id))).scalar_one_or_none()
        plan = await s.get(VipPlan, plan_id)
        if not user or not plan or not plan.active:
            return await c.answer('Tarif topilmadi.', show_alert=True)

        # Only one active payment attempt per user. Old pending attempts are
        # expired immediately so one receipt cannot attach to two payments.
        now = datetime.now(timezone.utc)
        pending = (await s.execute(
            select(VipPayment).where(VipPayment.user_id == user.id, VipPayment.status == 'PENDING')
        )).scalars().all()
        for old in pending:
            old.status = 'EXPIRED'
            old.rejection_reason = 'Yangi VIP to‘lovi boshlandi.'

        payment_id = 'VIP-' + uuid4().hex[:10].upper()
        payment = VipPayment(
            payment_id=payment_id,
            user_id=user.id,
            plan_id=plan.id,
            amount=plan.price,
            expires_at=now + timedelta(minutes=PAYMENT_TTL_MINUTES),
        )
        s.add(payment)
        await s.commit()

    await state.set_state(VipPurchaseState.waiting_receipt)
    await state.update_data(payment_id=payment_id)
    await c.message.answer(
        f"👑 <b>{plan.name_uz}</b>\n"
        f"💰 To‘lov: <b>{plan.price:,} UZS</b>\n\n"
        f"{card_text()}\n\n"
        f"🧾 To‘lovni amalga oshiring va chek rasmini shu chatga yuboring.\n"
        f"⏳ Chek yuborish uchun <b>{PAYMENT_TTL_MINUTES} daqiqa</b> vaqt bor.\n\n"
        f"🆔 To‘lov ID: <code>{payment_id}</code>"
    )
    await c.answer()
