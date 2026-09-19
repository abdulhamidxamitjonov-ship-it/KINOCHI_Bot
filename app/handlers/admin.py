import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func, delete
from app.config import settings
from app.database.database import Session
from app.database.models import User, Movie, Series, Episode, VipPayment, MandatoryChannel
from app.keyboards.admin import menu, confirm
from app.states.admin_content import MovieAddState, SeriesAddState
from app.utils.entities import serialize_entities, deserialize_entities
from app.utils.deep_links import movie_link, series_link

router=Router()
def is_admin_id(uid): return uid in settings.admins
def is_admin(m): return is_admin_id(m.from_user.id)

def parse_info(text):
    values = {
        'title': '', 'year': None, 'genre': '',
        'country': '', 'rating': '', 'description': ''
    }

    aliases = {
        'nomi': 'title', 'kino nomi': 'title', 'serial nomi': 'title',
        'film nomi': 'title', 'title': 'title', 'название': 'title',
        'yil': 'year', 'yili': 'year', 'год': 'year',
        'janr': 'genre', 'janri': 'genre', 'жанр': 'genre',
        'davlat': 'country', 'davlati': 'country',
        'mamlakat': 'country', 'страна': 'country',
        'reyting': 'rating', 'reytingi': 'rating', 'rating': 'rating',
        'рейтинг': 'rating',
        'tavsif': 'description', 'description': 'description',
        'описание': 'description'
    }

    for raw in (text or '').splitlines():
        if ':' not in raw:
            continue

        k, v = raw.split(':', 1)

        # Remove Telegram/Unicode emoji and punctuation before matching.
        k = k.strip().lower()
        k = re.sub(r'[\U00010000-\U0010ffff]', '', k)
        k = re.sub(r'^[^\w]+', '', k, flags=re.UNICODE)
        k = re.sub(r'\s+', ' ', k).strip()
        key = aliases.get(k)
        if not key:
            continue

        v = v.strip()
        if key == 'year':
            m = re.search(r'\b(19|20)\d{2}\b', v)
            if m:
                values[key] = int(m.group())
        else:
            values[key] = v

    return values

def info_prompt(kind):
    n='kino' if kind=='movie' else 'serial'
    return f'''📝 {n.title()} ma'lumotlarini bitta xabarda yuboring.\n\n🎬 {n.title()} nomi: ...\n📅 Yil: ...\n🎭 Janr: ...\n🌍 Davlat: ...\n⭐ Reyting: ...\n📝 Tavsif: ...\n\nPremium Custom Emoji ishlatishingiz mumkin.'''

def ad_kb(kind,code):
    url=(movie_link(settings.bot_username.lstrip('@'),code) if kind=='movie' else series_link(settings.bot_username.lstrip('@'),code))
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='▶️ KINONI OLISH' if kind=='movie' else '▶️ SERIALNI KO‘RISH',url=url)]])

def ad_caption(obj,kind):
    title=obj.title_uz
    desc=obj.description_uz or ''
    lines=[f'🎬 {title}',f'📅 {obj.year or "—"}',f'🎭 {obj.genre or "—"}',f'🌍 {obj.country or "—"}',f'⭐ {obj.rating or "—"}',f'🔢 Kod: {obj.code}']
    if desc: lines += ['', '📝 '+desc]
    return '\n'.join(lines)

def shifted_entities(entities,prefix):
    if not entities:return []
    # Telegram entity offsets are UTF-16; prefix is plain ASCII/emoji. Compute exact UTF-16 length.
    shift=len(prefix.encode('utf-16-le'))//2
    out=[]
    for e in entities:
        d=e.model_dump(); d['offset']=d.get('offset',0)+shift; out.append(d)
    return deserialize_entities(out)

async def publish_ad(bot,obj,kind):
    if not settings.ad_channel_id or not settings.bot_username or not obj.poster_file_id:return
    caption=ad_caption(obj,kind)
    # Preserve custom emoji in the description portion.
    prefix='\n'.join([f'🎬 {obj.title_uz}',f'📅 {obj.year or "—"}',f'🎭 {obj.genre or "—"}',f'🌍 {obj.country or "—"}',f'⭐ {obj.rating or "—"}',f'🔢 Kod: {obj.code}'])+'\n\n📝 '
    entities=shifted_entities(deserialize_entities(obj.description_uz_entities),prefix)
    await bot.send_photo(settings.ad_channel_id,obj.poster_file_id,caption=caption,caption_entities=entities,reply_markup=ad_kb(kind,obj.code))

async def next_code(s):
    mx=(await s.execute(select(func.max(Movie.id)))).scalar() or 0
    # ensure uniqueness across movie/series
    code=str(mx+1)
    while (await s.execute(select(Movie).where(Movie.code==code))).scalar_one_or_none() or (await s.execute(select(Series).where(Series.code==code))).scalar_one_or_none(): mx+=1; code=str(mx+1)
    return code

@router.message(Command('admin'))
async def admin_cmd(m):
    if is_admin(m): await m.answer('🛠 Admin panel',reply_markup=menu())

@router.message(Command('stats'))
async def stats(m):
    if not is_admin(m): return
    async with Session() as s:
        vals=[]
        for model,label in [(User,'👥 Users'),(Movie,'🎬 Kinolar'),(Series,'📺 Seriallar'),(Episode,'🎞 Qismlar'),(VipPayment,'💳 To‘lovlar'),(MandatoryChannel,'📢 Majburiy obuna')]: vals.append(f'{label}: {await s.scalar(select(func.count()).select_from(model))}')
    await m.answer('📊 Statistika\n'+'\n'.join(vals))

@router.message(Command('movies'))
async def movies_cmd(m):
    if is_admin(m): await m.answer('🎬 Kinolar',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='➕ Kino qo‘shish',callback_data='content:add_movie')]]))
@router.message(Command('series'))
async def series_cmd(m):
    if is_admin(m): await m.answer('📺 Seriallar',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='➕ Serial qo‘shish',callback_data='content:add_series')]]))

@router.message(F.text=='🎬 Kinolar')
async def movies_menu(m): await movies_cmd(m)
@router.message(F.text=='📺 Seriallar')
async def series_menu(m): await series_cmd(m)

@router.callback_query(F.data=='content:add_movie')
async def add_movie(c,state):
    if not is_admin_id(c.from_user.id): return await c.answer('Ruxsat yo‘q',show_alert=True)
    await state.clear(); await state.set_state(MovieAddState.waiting_video); await c.message.answer('🎬 Avval kino videosini yuboring.'); await c.answer()
@router.callback_query(F.data=='content:add_series')
async def add_series(c,state):
    if not is_admin_id(c.from_user.id): return await c.answer('Ruxsat yo‘q',show_alert=True)
    await state.clear(); await state.set_state(SeriesAddState.waiting_video); await c.message.answer('📺 Avval 1-qism videosini yuboring.'); await c.answer()

@router.message(MovieAddState.waiting_video,F.video)
async def mv(m,state):
    await state.update_data(video_file_id=m.video.file_id,video_file_unique_id=m.video.file_unique_id); await state.set_state(MovieAddState.waiting_info); await m.answer(info_prompt('movie'))
@router.message(MovieAddState.waiting_info,F.text)
async def mi(m,state):
    info=parse_info(m.text)
    if not info['title']: return await m.answer('❌ Kino nomi topilmadi. Masalan: 🎬 Kino nomi: Qasos')
    await state.update_data(info=info,description_entities=serialize_entities(m.entities)); await state.set_state(MovieAddState.waiting_poster); await m.answer('🖼 Endi reklama kanalida chiqadigan poster rasmini yuboring.')
@router.message(MovieAddState.waiting_poster,F.photo)
async def mp(m,state):
    d=await state.get_data(); info=d['info']
    async with Session() as s:
        code=await next_code(s); x=Movie(code=code,title_uz=info['title'],title_ru=info['title'],description_uz=info['description'],description_ru=info['description'],description_uz_entities=d.get('description_entities'),description_ru_entities=d.get('description_entities'),year=info['year'],genre=info['genre'],country=info['country'],rating=info['rating'],poster_file_id=m.photo[-1].file_id,video_file_id=d['video_file_id'],video_file_unique_id=d['video_file_unique_id']); s.add(x); await s.commit(); await s.refresh(x)
    await publish_ad(m.bot,x,'movie'); await state.clear(); await m.answer(f'✅ Kino qo‘shildi!\n🎬 {x.title_uz}\n🔢 Kod: {x.code}')

@router.message(SeriesAddState.waiting_video,F.video)
async def sv(m,state):
    await state.update_data(video_file_id=m.video.file_id,video_file_unique_id=m.video.file_unique_id); await state.set_state(SeriesAddState.waiting_info); await m.answer(info_prompt('series'))
@router.message(SeriesAddState.waiting_info,F.text)
async def si(m,state):
    info=parse_info(m.text)
    if not info['title']: return await m.answer('❌ Serial nomi topilmadi. Masalan: 🎬 Serial nomi: ...')
    await state.update_data(info=info,description_entities=serialize_entities(m.entities)); await state.set_state(SeriesAddState.waiting_poster); await m.answer('🖼 Endi serial reklama posterini yuboring.')
@router.message(SeriesAddState.waiting_poster,F.photo)
async def sp(m,state):
    d=await state.get_data(); info=d['info']
    async with Session() as s:
        code=await next_code(s); x=Series(code=code,title_uz=info['title'],title_ru=info['title'],description_uz=info['description'],description_ru=info['description'],description_uz_entities=d.get('description_entities'),description_ru_entities=d.get('description_entities'),year=info['year'],genre=info['genre'],country=info['country'],rating=info['rating'],poster_file_id=m.photo[-1].file_id); s.add(x); await s.flush(); s.add(Episode(series_id=x.id,season_number=1,episode_number=1,title_uz=info['title'],title_ru=info['title'],description_uz=info['description'],description_ru=info['description'],description_uz_entities=d.get('description_entities'),description_ru_entities=d.get('description_entities'),video_file_id=d['video_file_id'],video_file_unique_id=d['video_file_unique_id'])); await s.commit(); await s.refresh(x)
    await publish_ad(m.bot,x,'series'); await state.clear(); await m.answer(f'✅ Serial qo‘shildi!\n📺 {x.title_uz}\n🔢 Kod: {x.code}\n🎞 1-qism: 1-fasl')

@router.channel_post(F.video)
async def private_import(post: Message):
    """Import a video posted by an admin into the private movie database channel.

    Telegram keeps the video in the channel; we store its file_id/file_unique_id
    in PostgreSQL, so Render never downloads the large video.
    """
    if not settings.private_movie_channel_id:
        return
    if post.chat.id != settings.private_movie_channel_id:
        return

    caption = post.caption or ''
    info = parse_info(caption)

    # Accept the normal channel format shown to the admin:
    # 🎬 Kino nomi: Qasos
    # 📅 Yil: 2017
    # 🎭 Janr: ...
    # 🌍 Davlat: ...
    # ⭐ Reyting: ...
    # 📝 Tavsif: ...
    if not info['title']:
        await post.reply(
            '❌ Kino nomi topilmadi.\n\n'
            'Caption ichida quyidagidek yozing:\n'
            '🎬 Kino nomi: Qasos\n'
            '📅 Yil: 2017\n'
            '🎭 Janr: #Triller #Jangari\n'
            '🌍 Davlat: AQSH\n'
            '⭐ Reyting: 6.4\n'
            '📝 Tavsif: ...'
        )
        return

    async with Session() as s:
        dup = (
            await s.execute(
                select(Movie).where(
                    Movie.source_channel_id == post.chat.id,
                    Movie.source_message_id == post.message_id
                )
            )
        ).scalar_one_or_none()

        if dup:
            return

        code = await next_code(s)
        x = Movie(
            code=code,
            title_uz=info['title'],
            title_ru=info['title'],
            description_uz=info['description'] or '',
            description_ru=info['description'] or '',
            description_uz_entities=serialize_entities(post.caption_entities),
            description_ru_entities=serialize_entities(post.caption_entities),
            year=info['year'],
            genre=info['genre'],
            country=info['country'],
            rating=info['rating'],
            video_file_id=post.video.file_id,
            video_file_unique_id=post.video.file_unique_id,
            source_channel_id=post.chat.id,
            source_message_id=post.message_id
        )
        s.add(x)
        await s.commit()

    await post.reply(
        f'✅ Kino bazaga avtomatik saqlandi!\n'
        f'🎬 {x.title_uz}\n'
        f'🔢 Kino kodi: {x.code}\n\n'
        f'ℹ️ Video Telegram kanalida qoladi, bot esa file_id orqali ishlatadi.'
    )

@router.message(F.text=='📢 Majburiy obuna')
async def mandatory_menu(m):
    if not is_admin(m):return
    async with Session() as s: items=(await s.execute(select(MandatoryChannel).where(MandatoryChannel.active==True))).scalars().all()
    rows=[[InlineKeyboardButton(text=f'🗑 {x.title[:35]}',callback_data=f'mandatory_delete:{x.id}')] for x in items]
    rows.insert(0,[InlineKeyboardButton(text='➕ Qo‘shish (ID + URL)',callback_data='mandatory_add_help')])
    await m.answer('📢 Majburiy obuna\n\nO‘chirish uchun kerakli obunani bosing.',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
@router.callback_query(F.data.startswith('mandatory_delete:'))
async def mandatory_delete(c):
    if not is_admin_id(c.from_user.id):return await c.answer('Ruxsat yo‘q',show_alert=True)
    sid=int(c.data.split(':')[1]); await c.message.edit_reply_markup(reply_markup=confirm(f'mandatory_del_confirm:{sid}')); await c.answer()
@router.callback_query(F.data.startswith('mandatory_del_confirm:'))
async def mandatory_confirm(c):
    if not is_admin_id(c.from_user.id):return await c.answer('Ruxsat yo‘q',show_alert=True)
    parts=c.data.split(':'); sid=int(parts[1]); ok=parts[2]=='yes'
    if ok:
        async with Session() as s:
            x=await s.get(MandatoryChannel,sid)
            if x: x.active=False; await s.commit()
        await c.message.edit_text('✅ Majburiy obuna o‘chirildi.')
    else: await c.message.edit_text('❌ Bekor qilindi.')
    await c.answer()
@router.callback_query(F.data=='mandatory_add_help')
async def add_help(c):
    if is_admin_id(c.from_user.id): await c.message.answer('➕ Qo‘shish funksiyasi uchun /channels bo‘limidan foydalaning. Format: chat ID va havola.')
    await c.answer()

@router.message(Command('channels'))
async def channels_cmd(m): await mandatory_menu(m)
@router.message(Command('users'))
async def users_cmd(m):
    if not is_admin(m):return
    async with Session() as s: n=await s.scalar(select(func.count()).select_from(User))
    await m.answer(f'👥 Foydalanuvchilar: {n}')
@router.message(Command('vip'))
async def vip_cmd(m):
    if is_admin(m): await m.answer('👑 VIP boshqaruvi admin panel orqali amalga oshiriladi.')
@router.message(Command('payments'))
async def pay_cmd(m):
    if is_admin(m): await m.answer('💳 To‘lovlar bo‘limi.')
@router.message(Command('broadcast'))
async def broadcast_cmd(m):
    if is_admin(m): await m.answer('📣 Broadcast bo‘limi.')
