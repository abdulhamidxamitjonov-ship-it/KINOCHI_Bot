from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func
from app.config import settings
from app.database.database import Session
from app.database.models import User, Movie, Series, Episode, VipPayment
from app.keyboards.admin import menu
from app.states.admin_content import MovieAddState, SeriesAddState
from app.utils.entities import serialize_entities, deserialize_entities
from app.utils.deep_links import movie_link, series_link

router = Router()


def is_admin(m):
    return m.from_user.id in settings.admins


def parse_info(text: str):
    """Parse the admin's labeled content message while keeping the original text intact."""
    values = {"title": "", "year": None, "genre": "", "country": "", "rating": ""}
    aliases = {
        "nomi": "title", "kino nomi": "title", "serial nomi": "title", "title": "title", "название": "title",
        "yil": "year", "yili": "year", "год": "year",
        "janr": "genre", "janri": "genre", "жанр": "genre",
        "davlat": "country", "davlati": "country", "mamlakat": "country", "страна": "country",
        "reyting": "rating", "reytingi": "rating", "rating": "rating", "рейтинг": "rating",
    }
    for raw in text.splitlines():
        if ":" not in raw:
            continue
        k, v = raw.split(":", 1)
        key = aliases.get(k.strip().lower())
        if not key:
            continue
        v = v.strip()
        if key == "year":
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
