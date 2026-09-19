from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import re
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func
from app.config import settings
from app.database.database import Session
from app.database.models import User, Movie, Series, Episode, VipPayment, MandatoryChannel
from app.keyboards.admin import menu
from app.states.admin_content import MovieAddState, SeriesAddState
from app.utils.entities import serialize_entities, deserialize_entities
from app.utils.deep_links import movie_link, series_link

router = Router()


def is_admin(m):
    return m.from_user.id in settings.admins


def _admin_protected(user_id: int) -> bool:
    return user_id not in settings.admins


def mandatory_admin_keyboard(items):
    rows = []
    for item in items:
        rows.append([InlineKeyboardButton(text=f'🗑 {item.title[:40]}', callback_data=f'mandatory_delete:{item.id}')])
    rows.append([InlineKeyboardButton(text='❌ Yopish', callback_data='mandatory_admin_close')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_info(text: str):
    """Parse the admin's labeled content message while keeping the original text intact."""
    values = {"title": "", "year": None, "genre": "", "country": "", "rating": "", "description": ""}
    aliases = {
        "nomi": "title", "kino nomi": "title", "serial nomi": "title", "title": "title", "название": "title",
        "yil": "year", "yili": "year", "год": "year",
        "janr": "genre", "janri": "genre", "жанр": "genre",
        "davlat": "country", "davlati": "country", "mamlakat": "country", "страна": "country",
        "reyting": "rating", "reytingi": "rating", "rating": "rating", "рейтинг": "rating",
        "tavsif": "description", "description": "description", "описание": "description",
    }
    for raw in text.splitlines():
        if ":" not in raw:
            continue
        k, v = raw.split(":", 1)
        # Admin often uses Telegram emoji before labels (🎬, 📅, 🎭, ...).
        # Remove leading symbols so `🎬 Kino nomi` is parsed as `kino nomi`.
        clean_key = re.sub(r'^([^\w]+)', '', k.strip(), flags=re.UNICODE).strip().lower()
        clean_key = re.sub(r'\s+', ' ', clean_key)
        key = aliases.get(clean_key)
        if not key:
            continue
        v = v.strip()
        if key == "description":
            values[key] = v
        elif key == "year":
            try: values[key] = int(v)
            except ValueError: values[key] = None
        else:
            values[key] = v
    return values


def content_info_prompt(kind: str):
    noun = "kino" if kind == "movie" else "serial"
    return (
        f"📝 Endi {noun} ma'lumotlarini yuboring.\n\n"
        "Premium Custom Emoji ishlatishingiz mumkin — bot ularni saqlab qoladi.\n\n"
        "Tavsiya etilgan format:\n"
        f"🎬 {noun.title()} nomi: ...\n"
        "📅 Yil: ...\n"
        "🎭 Janr: ...\n"
        "🌍 Davlat: ...\n"
        "⭐ Reyting: ...\n"
        "📝 Tavsif: ...\n\n"
        "Barchasini bitta xabarda yuboring."
    )


def ad_keyboard(kind: str, code: str):
    username = settings.bot_username.lstrip("@")
    url = movie_link(username, code) if kind == "movie" else series_link(username, code)
    text = "▶️ KINONI OLISH" if kind == "movie" else "▶️ SERIALNI KO‘RISH"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, url=url)]])


async def post_movie_ad(bot, movie):
    if not settings.ad_channel_id or not settings.bot_username:
        return
    caption = movie.description_uz or movie.title_uz
    if len(caption) > 1024:
        caption = caption[:1021] + "..."
    await bot.send_photo(
        settings.ad_channel_id,
        movie.poster_file_id,
        caption=caption,
        caption_entities=deserialize_entities(movie.description_uz_entities),
        reply_markup=ad_keyboard("movie", movie.code),
    )


async def post_series_ad(bot, series):
    if not settings.ad_channel_id or not settings.bot_username:
        return
    caption = series.description_uz or series.title_uz
    if len(caption) > 1024:
        caption = caption[:1021] + "..."
    await bot.send_photo(
        settings.ad_channel_id,
        series.poster_file_id,
        caption=caption,
        caption_entities=deserialize_entities(series.description_uz_entities),
        reply_markup=ad_keyboard("series", series.code),
    )


async def _next_code(session, requested: str | None = None) -> str:
    if requested and requested.strip():
        code = requested.strip()
        exists = await session.execute(select(Movie).where(Movie.code == code))
        if exists.scalar_one_or_none() is None:
            return code
    result = await session.execute(select(func.max(Movie.id)))
    max_id = result.scalar() or 0
    return str(max_id + 1)


@router.channel_post(F.video)
async def private_channel_video(post: Message):
    """Import videos posted directly to the configured private movie channel.

    Telegram channel posts arrive as `channel_post`, not normal `message` updates.
    We only import from the exact PRIVATE_MOVIE_CHANNEL_ID, store Telegram file_id
    (no large video is downloaded to Render), and parse metadata from the caption.
    """
    channel_id = settings.private_movie_channel_id
    if not channel_id or post.chat.id != channel_id:
        return

    caption = post.caption or ""
    info = parse_info(caption)
    if not info["title"]:
        await post.bot.send_message(
            channel_id,
            "❌ Video qabul qilindi, lekin caption ichidan kino nomi topilmadi.\n"
            "Masalan: 🎬 Kino nomi: Qasos\n"
            "📅 Yil: 2017\n🎭 Janr: #Triller #Boevik\n🌍 Davlat: AQSH\n⭐ Reyting: 6.4",
            reply_to_message_id=post.message_id,
        )
        return

    requested_code = None
    for raw in caption.splitlines():
        if ":" not in raw:
            continue
        k, v = raw.split(":", 1)
        clean = re.sub(r'^[^\w]+', '', k.strip(), flags=re.UNICODE).strip().lower()
        if clean in {"kino kodi", "kod", "код", "movie code"}:
            requested_code = v.strip()
            break

    async with Session() as s:
        duplicate = (await s.execute(
            select(Movie).where(
                Movie.source_channel_id == post.chat.id,
                Movie.source_message_id == post.message_id,
            )
        )).scalar_one_or_none()
        if duplicate:
            return
        code = await _next_code(s, requested_code)
        movie = Movie(
            code=code,
            title_uz=info["title"],
            title_ru=info["title"],
            description_uz=caption,
            description_ru=caption,
            description_uz_entities=serialize_entities(post.caption_entities),
            description_ru_entities=serialize_entities(post.caption_entities),
            year=info.get("year"),
            genre=info.get("genre"),
            country=info.get("country"),
            rating=info.get("rating"),
            video_file_id=post.video.file_id,
            video_file_unique_id=post.video.file_unique_id,
            source_channel_id=post.chat.id,
            source_message_id=post.message_id,
        )
        s.add(movie)
        await s.commit()

    await post.bot.send_message(
        channel_id,
        f"✅ Bot bazasiga saqlandi.\n🎬 {movie.title_uz}\n🔢 Kino kodi: {movie.code}\n\n"
        "ℹ️ Video Telegram file_id orqali saqlandi, Render serveriga yuklab olinmadi.\n"
        "🖼️ Reklama kanaliga poster yuborilsa, keyin reklama joylash mumkin.",
        reply_to_message_id=post.message_id,
    )


@router.message(Command('admin'))
async def admin(m):
    if not is_admin(m):
        return await m.answer('❌ Bu bo‘lim faqat adminlar uchun.')
    await m.answer('🛠 Admin panel', reply_markup=menu())


@router.message(F.text == '🎬 Kinolar')
async def movies_admin(m: Message):
    if not is_admin(m): return
    await m.answer('🎬 Kinolar bo‘limi', reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='➕ Kino qo‘shish', callback_data='content:add_movie')],
    ]))


@router.message(F.text == '📺 Seriallar')
async def series_admin(m: Message):
    if not is_admin(m): return
    await m.answer('📺 Seriallar bo‘limi', reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='➕ Serial qo‘shish', callback_data='content:add_series')],
    ]))


@router.callback_query(F.data == 'content:add_movie')
async def add_movie_start(c: CallbackQuery, state: FSMContext):
    if c.from_user.id not in settings.admins: return await c.answer('Ruxsat yo‘q.', show_alert=True)
    await state.clear()
    await state.set_state(MovieAddState.waiting_video)
    await c.message.answer('🎬 Kino videosini yuboring.')
    await c.answer()


@router.callback_query(F.data == 'content:add_series')
async def add_series_start(c: CallbackQuery, state: FSMContext):
    if c.from_user.id not in settings.admins: return await c.answer('Ruxsat yo‘q.', show_alert=True)
    await state.clear()
    await state.set_state(SeriesAddState.waiting_video)
    await c.message.answer('📺 Serialning 1-qism videosini yuboring.')
    await c.answer()


@router.message(MovieAddState.waiting_video, F.video)
async def movie_video(m: Message, state: FSMContext):
    await state.update_data(video_file_id=m.video.file_id, video_file_unique_id=m.video.file_unique_id, source_message_id=m.message_id)
    await state.set_state(MovieAddState.waiting_info)
    await m.answer(content_info_prompt('movie'))


@router.message(MovieAddState.waiting_video)
async def movie_video_wrong(m: Message):
    await m.answer('❌ Iltimos, kino videosini Telegram video ko‘rinishida yuboring.')


@router.message(MovieAddState.waiting_info, F.text)
async def movie_info(m: Message, state: FSMContext):
    info = parse_info(m.text)
    if not info['title']:
        return await m.answer('❌ Kino nomi topilmadi. Masalan: 🎬 Kino nomi: Avatar')
    if len(m.text) > 1024:
        return await m.answer('❌ Reklama captioni 1024 belgidan oshmasligi kerak. Ma’lumotni qisqaroq yuboring.')
    await state.update_data(
        title=info['title'], year=info['year'], genre=info['genre'], country=info['country'], rating=info['rating'],
        description=m.text, entities=serialize_entities(m.entities)
    )
    await state.set_state(MovieAddState.waiting_poster)
    await m.answer('🖼️ Endi shu kino uchun reklama kanalida ko‘rsatiladigan poster/afishani yuboring.')


@router.message(MovieAddState.waiting_info)
async def movie_info_wrong(m: Message):
    await m.answer('❌ Ma’lumotlarni bitta matnli xabarda yuboring.')


@router.message(MovieAddState.waiting_poster, F.photo)
async def movie_poster(m: Message, state: FSMContext):
    data = await state.get_data()
    async with Session() as s:
        movie = Movie(
            code='', title_uz=data['title'], title_ru=data['title'],
            description_uz=data['description'], description_ru=data['description'],
            description_uz_entities=data.get('entities', []), description_ru_entities=data.get('entities', []),
            year=data.get('year'), genre=data.get('genre'), country=data.get('country'), rating=data.get('rating'),
            poster_file_id=m.photo[-1].file_id, video_file_id=data['video_file_id'],
            video_file_unique_id=data.get('video_file_unique_id'), source_message_id=data.get('source_message_id')
        )
        s.add(movie)
        await s.flush()
        movie.code = str(movie.id)
        await s.commit()
    await state.clear()
    try:
        await post_movie_ad(m.bot, movie)
        ad = '📢 Reklama kanliga avtomatik joylandi.'
    except Exception as e:
        ad = f'⚠️ Kino saqlandi, lekin reklama kanaliga joylashda xato yuz berdi: {str(e)[:250]}'
    await m.answer(f'✅ Kino muvaffaqiyatli qo‘shildi.\n\n🎬 {movie.title_uz}\n🔢 Kod: {movie.code}\n\n{ad}')


@router.message(MovieAddState.waiting_poster)
async def movie_poster_wrong(m: Message):
    await m.answer('❌ Iltimos, poster/afishani rasm ko‘rinishida yuboring.')


@router.message(SeriesAddState.waiting_video, F.video)
async def series_video(m: Message, state: FSMContext):
    await state.update_data(video_file_id=m.video.file_id, video_file_unique_id=m.video.file_unique_id, source_message_id=m.message_id)
    await state.set_state(SeriesAddState.waiting_info)
    await m.answer(content_info_prompt('series'))


@router.message(SeriesAddState.waiting_video)
async def series_video_wrong(m: Message):
    await m.answer('❌ Iltimos, serial videosini Telegram video ko‘rinishida yuboring.')


@router.message(SeriesAddState.waiting_info, F.text)
async def series_info(m: Message, state: FSMContext):
    info = parse_info(m.text)
    if not info['title']:
        return await m.answer('❌ Serial nomi topilmadi. Masalan: 📺 Serial nomi: Stranger Things')
    if len(m.text) > 1024:
        return await m.answer('❌ Reklama captioni 1024 belgidan oshmasligi kerak. Ma’lumotni qisqaroq yuboring.')
    await state.update_data(
        title=info['title'], year=info['year'], genre=info['genre'], country=info['country'], rating=info['rating'],
        description=m.text, entities=serialize_entities(m.entities)
    )
    await state.set_state(SeriesAddState.waiting_poster)
    await m.answer('🖼️ Endi shu serial uchun reklama kanalida ko‘rsatiladigan poster/afishani yuboring.')


@router.message(SeriesAddState.waiting_info)
async def series_info_wrong(m: Message):
    await m.answer('❌ Ma’lumotlarni bitta matnli xabarda yuboring.')


@router.message(SeriesAddState.waiting_poster, F.photo)
async def series_poster(m: Message, state: FSMContext):
    data = await state.get_data()
    async with Session() as s:
        series = Series(
            code='', title_uz=data['title'], title_ru=data['title'],
            description_uz=data['description'], description_ru=data['description'],
            description_uz_entities=data.get('entities', []), description_ru_entities=data.get('entities', []),
            year=data.get('year'), genre=data.get('genre'), country=data.get('country'), rating=data.get('rating'),
            poster_file_id=m.photo[-1].file_id
        )
        s.add(series)
        await s.flush()
        series.code = str(series.id)
        # The video sent at the beginning becomes Season 1, Episode 1.
        ep = Episode(
            series_id=series.id, season_number=1, episode_number=1,
            title_uz='1-qism', title_ru='1 серия',
            video_file_id=data['video_file_id'], video_file_unique_id=data.get('video_file_unique_id'),
            source_message_id=data.get('source_message_id')
        )
        s.add(ep)
        await s.commit()
    await state.clear()
    try:
        await post_series_ad(m.bot, series)
        ad = '📢 Reklama kanliga avtomatik joylandi.'
    except Exception as e:
        ad = f'⚠️ Serial saqlandi, lekin reklama kanaliga joylashda xato yuz berdi: {str(e)[:250]}'
    await m.answer(
        f'✅ Serial muvaffaqiyatli qo‘shildi.\n\n📺 {series.title_uz}\n🔢 Kod: {series.code}\n🎬 1-fasl, 1-qism saqlandi.\n\n{ad}'
    )


@router.message(SeriesAddState.waiting_poster)
async def series_poster_wrong(m: Message):
    await m.answer('❌ Iltimos, poster/afishani rasm ko‘rinishida yuboring.')


@router.message(Command('channels'))
async def channels_cmd(m: Message):
    if not is_admin(m):
        return
    async with Session() as s:
        items = (await s.execute(select(MandatoryChannel).where(MandatoryChannel.active == True).order_by(MandatoryChannel.id))).scalars().all()
    if not items:
        return await m.answer('📢 Hozir faol majburiy obuna yo‘q.')
    text = '📢 Majburiy obunalar\n\n' + '\n'.join(
        f'{i.id}. 📢 Majburiy obuna — {i.title}\n   ID: {i.chat_id}\n   {i.url}' for i in items
    )
    text += '\n\n🗑 O‘chirish uchun pastdagi tugmani bosing.'
    await m.answer(text, reply_markup=mandatory_admin_keyboard(items))


@router.message(F.text == '📢 Majburiy obuna')
async def channels_btn(m: Message):
    await channels_cmd(m)


@router.callback_query(F.data.startswith('mandatory_delete:'))
async def mandatory_delete_prompt(c: CallbackQuery):
    if c.from_user.id not in settings.admins:
        return await c.answer('Ruxsat yo‘q.', show_alert=True)
    sid = int(c.data.split(':', 1)[1])
    await c.message.answer(
        '⚠️ Ushbu majburiy obunani o‘chirishni tasdiqlaysizmi?',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✅ Ha, o‘chirish', callback_data=f'mandatory_delete_confirm:{sid}')],
            [InlineKeyboardButton(text='❌ Bekor qilish', callback_data='mandatory_admin_close')],
        ])
    )
    await c.answer()


@router.callback_query(F.data.startswith('mandatory_delete_confirm:'))
async def mandatory_delete_confirm(c: CallbackQuery):
    if c.from_user.id not in settings.admins:
        return await c.answer('Ruxsat yo‘q.', show_alert=True)
    sid = int(c.data.split(':', 1)[1])
    async with Session() as s:
        item = await s.get(MandatoryChannel, sid)
        if not item:
            await c.answer('Bu majburiy obuna allaqachon o‘chirilgan.', show_alert=True)
            return
        item.active = False
        await s.commit()
    await c.message.edit_text(f'✅ Majburiy obuna o‘chirildi.\n📢 {item.title}')
    await c.answer('O‘chirildi')


@router.callback_query(F.data == 'mandatory_admin_close')
async def mandatory_admin_close(c: CallbackQuery):
    if c.from_user.id not in settings.admins:
        return await c.answer('Ruxsat yo‘q.', show_alert=True)
    await c.message.delete()
    await c.answer()


@router.message(Command('movies'))
async def movies_cmd(m: Message):
    if not is_admin(m): return
    await movies_admin(m)


@router.message(Command('series'))
async def series_cmd(m: Message):
    if not is_admin(m): return
    await series_admin(m)


@router.message(Command('users'))
async def users_cmd(m: Message):
    if not is_admin(m): return
    async with Session() as s:
        count = await s.scalar(select(func.count()).select_from(User))
    await m.answer(f'👥 Foydalanuvchilar soni: {count}')


@router.message(Command('vip'))
async def vip_cmd(m: Message):
    if not is_admin(m): return
    await m.answer('👑 VIP boshqaruvi uchun /admin panelidan foydalaning.')


@router.message(Command('payments'))
async def payments_cmd(m: Message):
    if not is_admin(m): return
    async with Session() as s:
        count = await s.scalar(select(func.count()).select_from(VipPayment).where(VipPayment.status == 'PENDING'))
    await m.answer(f'💳 Kutilayotgan to‘lovlar: {count}')


@router.message(Command('broadcast'))
async def broadcast_cmd(m: Message):
    if not is_admin(m): return
    await m.answer('📣 Broadcast funksiyasi admin paneldagi reklama/xabar bo‘limi orqali boshqariladi.')


@router.message(Command('stats'))
async def stats(m):
    if not is_admin(m): return
    async with Session() as s:
        users = await s.scalar(select(func.count()).select_from(User))
        movies = await s.scalar(select(func.count()).select_from(Movie))
        series = await s.scalar(select(func.count()).select_from(Series))
        pending = await s.scalar(select(func.count()).select_from(VipPayment).where(VipPayment.status == 'PENDING'))
    await m.answer(f'📊 Statistika\n👥 Users: {users}\n🎬 Movies: {movies}\n📺 Series: {series}\n💳 Pending: {pending}')


@router.message(F.text == '📊 Statistika')
async def stats_btn(m):
    await stats(m)
