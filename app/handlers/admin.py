import re
from uuid import uuid4
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func, delete
from app.config import settings
from app.database.database import Session
from app.database.models import User, Movie, Series, Episode, VipPayment, MandatoryChannel
from app.keyboards.admin import menu, confirm
from app.states.admin_content import (
    MovieAddState, SeriesAddState, SeriesEpisodeAddState,
    MovieEditState, SeriesEditState, MandatoryAddState
)
from app.utils.entities import serialize_entities, deserialize_entities
from app.utils.deep_links import movie_link, series_link

router=Router()
def is_admin_id(uid): return uid in settings.admins
def is_admin(m): return is_admin_id(m.from_user.id)

def parse_info(text):
    values = {
        'title': '', 'year': None, 'genre': '',
        'country': '', 'rating': '', 'description': '', 'code': ''
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
        'описание': 'description', 'kod': 'code', 'kodi': 'code', 'code': 'code', 'код': 'code'
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
    return f"""📝 {n.title()} ma'lumotlarini bitta xabarda yuboring.

🎬 {n.title()} nomi: ...
📅 Yil: ...
🎭 Janr: ...
🌍 Davlat: ...
⭐ Reyting: ...
📝 Tavsif: ...
🔢 Kod: ...

⚠️ Kodni eng oxirgi qatorda yozing. Bot aynan shu kod bilan saqlaydi.
Premium Custom Emoji ishlatishingiz mumkin."""

def ad_kb(kind,code):
    url=(movie_link(settings.bot_username.lstrip('@'),code) if kind=='movie' else series_link(settings.bot_username.lstrip('@'),code))
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='▶️ KINONI OLISH' if kind=='movie' else '▶️ SERIALNI KO‘RISH',url=url)]])

def ad_caption(obj,kind):
    text=getattr(obj,'metadata_text',None)
    if text: return text
    title=obj.title_uz; desc=obj.description_uz or ''
    lines=[f'🎬 {title}',f'📅 {obj.year or '-'}',f'🎭 {obj.genre or '-'}',f'🌍 {obj.country or '-'}',f'⭐ {obj.rating or '-'}',f'🔢 Kod: {obj.code}']
    if desc: lines += ['', '📝 '+desc]
    return '\n'.join(lines)

async def publish_ad(bot,obj,kind):
    if not settings.ad_channel_id or not settings.bot_username: return
    await bot.send_message(settings.ad_channel_id,ad_caption(obj,kind),entities=deserialize_entities(getattr(obj,'metadata_entities',None) or []) or None,reply_markup=ad_kb(kind,obj.code))

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

# ---------------- CONTENT ADMIN ----------------

def admin_content_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='➕ Kino qo‘shish', callback_data='content:add_movie')],
        [InlineKeyboardButton(text='✏️ Kino tahrirlash', callback_data='content:movies')],
        [InlineKeyboardButton(text='➕ Serial qo‘shish', callback_data='content:add_series')],
        [InlineKeyboardButton(text='✏️ Serial / qism tahrirlash', callback_data='content:series')],
    ])

@router.message(Command('movies'))
async def movies_cmd(m):
    if is_admin(m):
        await m.answer('🎬 Kinolar bo‘limi', reply_markup=admin_content_kb())

@router.message(Command('series'))
async def series_cmd(m):
    if is_admin(m):
        await m.answer('📺 Seriallar bo‘limi', reply_markup=admin_content_kb())

@router.message(F.text=='🎬 Kinolar')
async def movies_menu(m):
    await movies_cmd(m)

@router.message(F.text=='📺 Seriallar')
async def series_menu(m):
    await series_cmd(m)

@router.callback_query(F.data=='content:home')
async def content_home(c):
    if not is_admin_id(c.from_user.id): return await c.answer('Ruxsat yo‘q', show_alert=True)
    await c.message.edit_text('🗂 Kontent boshqaruvi', reply_markup=admin_content_kb())
    await c.answer()

@router.callback_query(F.data=='content:add_movie')
async def add_movie(c,state):
    if not is_admin_id(c.from_user.id): return await c.answer('Ruxsat yo‘q',show_alert=True)
    await state.clear(); await state.set_state(MovieAddState.waiting_video)
    await c.message.answer('🎬 Avval kino videosini yuboring.')
    await c.answer()

@router.callback_query(F.data=='content:add_series')
async def add_series(c,state):
    if not is_admin_id(c.from_user.id): return await c.answer('Ruxsat yo‘q',show_alert=True)
    await state.clear(); await state.set_state(SeriesAddState.waiting_video)
    await c.message.answer('📺 Avval serialning 1-qism videosini yuboring.')
    await c.answer()

@router.callback_query(F.data=='content:movies')
async def movie_list(c):
    if not is_admin_id(c.from_user.id): return await c.answer('Ruxsat yo‘q',show_alert=True)
    async with Session() as s:
        items=(await s.execute(select(Movie).order_by(Movie.id.desc()).limit(50))).scalars().all()
    rows=[]
    for x in items:
        rows.append([InlineKeyboardButton(text=f'🎬 {x.code} — {x.title_uz[:35]}', callback_data=f'content:movie:{x.id}')])
    rows.append([InlineKeyboardButton(text='➕ Kino qo‘shish',callback_data='content:add_movie')])
    rows.append([InlineKeyboardButton(text='🔙 Orqaga',callback_data='content:home')])
    await c.message.edit_text('🎬 Qo‘shilgan kinolar:', reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await c.answer()

@router.callback_query(F.data=='content:series')
async def series_list(c):
    if not is_admin_id(c.from_user.id): return await c.answer('Ruxsat yo‘q',show_alert=True)
    async with Session() as s:
        items=(await s.execute(select(Series).order_by(Series.id.desc()).limit(50))).scalars().all()
    rows=[]
    for x in items:
        rows.append([InlineKeyboardButton(text=f'📺 {x.code} — {x.title_uz[:35]}', callback_data=f'content:series:{x.id}')])
    rows.append([InlineKeyboardButton(text='➕ Serial qo‘shish',callback_data='content:add_series')])
    rows.append([InlineKeyboardButton(text='🔙 Orqaga',callback_data='content:home')])
    await c.message.edit_text('📺 Qo‘shilgan seriallar:', reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await c.answer()

@router.callback_query(F.data.startswith('content:movie:'))
async def movie_manage(c):
    if not is_admin_id(c.from_user.id): return await c.answer('Ruxsat yo‘q',show_alert=True)
    mid=int(c.data.rsplit(':',1)[1])
    async with Session() as s:
        x=await s.get(Movie,mid)
    if not x: return await c.answer('Kino topilmadi',show_alert=True)
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✏️ Tahrirlash',callback_data=f'content:movie_edit:{mid}')],
        [InlineKeyboardButton(text='🗑 O‘chirish',callback_data=f'content:movie_delete:{mid}')],
        [InlineKeyboardButton(text='🔙 Kinolar',callback_data='content:movies')]
    ])
    await c.message.edit_text(f'🎬 {x.title_uz}\n🔢 Kod: {x.code}\n👁 Ko‘rishlar: {x.views}',reply_markup=kb)
    await c.answer()

@router.callback_query(F.data.startswith('content:series:'))
async def series_manage(c):
    if not is_admin_id(c.from_user.id): return await c.answer('Ruxsat yo‘q',show_alert=True)
    sid=int(c.data.rsplit(':',1)[1])
    async with Session() as s:
        x=await s.get(Series,sid)
        eps=(await s.execute(select(Episode).where(Episode.series_id==sid).order_by(Episode.season_number,Episode.episode_number))).scalars().all()
    if not x: return await c.answer('Serial topilmadi',show_alert=True)
    seasons=sorted({e.season_number for e in eps})
    info=f'📺 {x.title_uz}\n🔢 Kod: {x.code}\n📚 Fasllar: {len(seasons)}\n🎞 Qismlar: {len(eps)}'
    rows=[
        [InlineKeyboardButton(text='➕ Boshqa qism/fasl qo‘shish',callback_data=f'content:episode_add:{sid}')],
        [InlineKeyboardButton(text='✏️ Serial ma’lumotini tahrirlash',callback_data=f'content:series_edit:{sid}')],
    ]
    for e in eps[:50]:
        rows.append([InlineKeyboardButton(text=f'🎞 {e.season_number}-fasl {e.episode_number}-qism',callback_data=f'content:episode:{e.id}')])
    rows.append([InlineKeyboardButton(text='🗑 Serialni o‘chirish',callback_data=f'content:series_delete:{sid}')])
    rows.append([InlineKeyboardButton(text='🔙 Seriallar',callback_data='content:series')])
    await c.message.edit_text(info,reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await c.answer()

@router.callback_query(F.data.startswith('content:episode_add:'))
async def episode_add_start(c,state):
    if not is_admin_id(c.from_user.id): return await c.answer('Ruxsat yo‘q',show_alert=True)
    sid=int(c.data.rsplit(':',1)[1])
    async with Session() as s: x=await s.get(Series,sid)
    if not x: return await c.answer('Serial topilmadi',show_alert=True)
    await state.clear(); await state.update_data(series_id=sid); await state.set_state(SeriesEpisodeAddState.waiting_video)
    await c.message.answer(f'📺 {x.title_uz}\n\n🎬 Yangi qism videosini yuboring.')
    await c.answer()

@router.message(SeriesEpisodeAddState.waiting_video,F.video)
async def episode_video(m,state):
    await state.update_data(video_file_id=m.video.file_id,video_file_unique_id=m.video.file_unique_id)
    await state.set_state(SeriesEpisodeAddState.waiting_season)
    await m.answer('📚 Qaysi fasl? Masalan: 1')

@router.message(SeriesEpisodeAddState.waiting_season,F.text)
async def episode_season(m,state):
    try: sn=int(m.text.strip())
    except ValueError: return await m.answer('❌ Fasl raqamini faqat son bilan yuboring.')
    if sn<1: return await m.answer('❌ Fasl raqami 1 dan boshlanadi.')
    await state.update_data(season_number=sn); await state.set_state(SeriesEpisodeAddState.waiting_episode)
    await m.answer('🎞 Qaysi qism? Masalan: 2')

@router.message(SeriesEpisodeAddState.waiting_episode,F.text)
async def episode_number(m,state):
    try: en=int(m.text.strip())
    except ValueError: return await m.answer('❌ Qism raqamini faqat son bilan yuboring.')
    if en<1: return await m.answer('❌ Qism raqami 1 dan boshlanadi.')
    d=await state.get_data()
    async with Session() as s:
        x=await s.get(Series,d['series_id'])
        if not x: await state.clear(); return await m.answer('❌ Serial topilmadi.')
        exists=(await s.execute(select(Episode).where(Episode.series_id==x.id,Episode.season_number==d['season_number'],Episode.episode_number==en))).scalar_one_or_none()
        if exists: return await m.answer('❌ Bu fasl va qism allaqachon mavjud. Boshqa raqam yuboring.')
        e=Episode(series_id=x.id,season_number=d['season_number'],episode_number=en,title_uz=x.title_uz,title_ru=x.title_ru,description_uz=x.description_uz,description_ru=x.description_ru,description_uz_entities=x.description_uz_entities,description_ru_entities=x.description_ru_entities,video_file_id=d['video_file_id'],video_file_unique_id=d['video_file_unique_id'])
        s.add(e); await s.commit()
    await state.clear(); await m.answer(f'✅ Qo‘shildi: {x.title_uz}\n🎞 {d["season_number"]}-fasl {en}-qism')

@router.callback_query(F.data.startswith('content:episode:'))
async def episode_manage(c):
    if not is_admin_id(c.from_user.id): return await c.answer('Ruxsat yo‘q',show_alert=True)
    eid=int(c.data.rsplit(':',1)[1])
    async with Session() as s:
        e=await s.get(Episode,eid)
        x=await s.get(Series,e.series_id) if e else None
    if not e or not x: return await c.answer('Qism topilmadi',show_alert=True)
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🗑 Qismni o‘chirish',callback_data=f'content:episode_delete:{eid}')],
        [InlineKeyboardButton(text='🔙 Serialga qaytish',callback_data=f'content:series:{x.id}')]
    ])
    await c.message.edit_text(f'📺 {x.title_uz}\n🎞 {e.season_number}-fasl {e.episode_number}-qism',reply_markup=kb); await c.answer()

@router.callback_query(F.data.startswith('content:episode_delete:'))
async def episode_delete(c):
    if not is_admin_id(c.from_user.id): return await c.answer('Ruxsat yo‘q',show_alert=True)
    eid=int(c.data.rsplit(':',1)[1])
    async with Session() as s:
        e=await s.get(Episode,eid)
        if not e: return await c.answer('Qism topilmadi',show_alert=True)
        sid=e.series_id; await s.delete(e); await s.commit()
    await c.answer('✅ Qism o‘chirildi'); await c.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 Serialga qaytish',callback_data=f'content:series:{sid}')]]))

@router.callback_query(F.data.startswith('content:movie_delete:'))
async def movie_delete(c):
    if not is_admin_id(c.from_user.id): return await c.answer('Ruxsat yo‘q',show_alert=True)
    mid=int(c.data.rsplit(':',1)[1])
    async with Session() as s:
        x=await s.get(Movie,mid)
        if not x:return await c.answer('Kino topilmadi',show_alert=True)
        await s.delete(x); await s.commit()
    await c.answer('✅ Kino o‘chirildi'); await movie_list(c)

@router.callback_query(F.data.startswith('content:series_delete:'))
async def series_delete(c):
    if not is_admin_id(c.from_user.id): return await c.answer('Ruxsat yo‘q',show_alert=True)
    sid=int(c.data.rsplit(':',1)[1])
    async with Session() as s:
        x=await s.get(Series,sid)
        if not x:return await c.answer('Serial topilmadi',show_alert=True)
        await s.delete(x); await s.commit()
    await c.answer('✅ Serial o‘chirildi'); await series_list(c)

@router.callback_query(F.data.startswith('content:movie_edit:'))
async def movie_edit_start(c,state):
    if not is_admin_id(c.from_user.id): return await c.answer('Ruxsat yo‘q',show_alert=True)
    mid=int(c.data.rsplit(':',1)[1]); await state.clear(); await state.update_data(movie_id=mid); await state.set_state(MovieEditState.waiting_info)
    await c.message.answer('✏️ Yangi kino ma’lumotlarini bitta xabarda yuboring:\nNomi, Yil, Janr, Davlat, Reyting, Tavsif, Kod') ; await c.answer()

@router.message(MovieEditState.waiting_info,F.text)
async def movie_edit_save(m,state):
    info=parse_info(m.text); d=await state.get_data();
    if not info['title'] or not info['code']: return await m.answer('❌ Nomi va kod majburiy.')
    async with Session() as s:
        x=await s.get(Movie,d['movie_id'])
        dup=(await s.execute(select(Movie).where(Movie.code==info['code'],Movie.id!=x.id))).scalar_one_or_none() if x else None
        if not x:return await m.answer('❌ Kino topilmadi.')
        if dup or (await s.execute(select(Series).where(Series.code==info['code']))).scalar_one_or_none():return await m.answer('❌ Bu kod band.')
        x.code=info['code'];x.title_uz=x.title_ru=info['title'];x.description_uz=x.description_ru=info['description'];x.description_uz_entities=x.description_ru_entities=x.metadata_entities=serialize_entities(m.entities);x.metadata_text=m.text;x.year=info['year'];x.genre=info['genre'];x.country=info['country'];x.rating=info['rating'];await s.commit()
    await state.clear(); await m.answer('✅ Kino ma’lumotlari tahrirlandi.')

@router.callback_query(F.data.startswith('content:series_edit:'))
async def series_edit_start(c,state):
    if not is_admin_id(c.from_user.id): return await c.answer('Ruxsat yo‘q',show_alert=True)
    sid=int(c.data.rsplit(':',1)[1]); await state.clear(); await state.update_data(series_id=sid); await state.set_state(SeriesEditState.waiting_info)
    await c.message.answer('✏️ Yangi serial ma’lumotlarini bitta xabarda yuboring:\nNomi, Yil, Janr, Davlat, Reyting, Tavsif, Kod'); await c.answer()

@router.message(SeriesEditState.waiting_info,F.text)
async def series_edit_save(m,state):
    info=parse_info(m.text); d=await state.get_data()
    if not info['title'] or not info['code']: return await m.answer('❌ Nomi va kod majburiy.')
    async with Session() as s:
        x=await s.get(Series,d['series_id'])
        if not x:return await m.answer('❌ Serial topilmadi.')
        dup=(await s.execute(select(Series).where(Series.code==info['code'],Series.id!=x.id))).scalar_one_or_none()
        if dup or (await s.execute(select(Movie).where(Movie.code==info['code']))).scalar_one_or_none():return await m.answer('❌ Bu kod band.')
        x.code=info['code'];x.title_uz=x.title_ru=info['title'];x.description_uz=x.description_ru=info['description'];x.description_uz_entities=x.description_ru_entities=x.metadata_entities=serialize_entities(m.entities);x.metadata_text=m.text;x.year=info['year'];x.genre=info['genre'];x.country=info['country'];x.rating=info['rating'];await s.commit()
    await state.clear(); await m.answer('✅ Serial ma’lumotlari tahrirlandi.')

# Existing movie/series creation handlers remain below.

@router.message(MovieAddState.waiting_video,F.video)
async def mv(m,state):
    await state.update_data(video_file_id=m.video.file_id,video_file_unique_id=m.video.file_unique_id)
    await state.set_state(MovieAddState.waiting_info)
    await m.answer(info_prompt('movie'))

@router.message(MovieAddState.waiting_info,F.text)
async def mi(m,state):
    info=parse_info(m.text)
    if not info['title']:
        return await m.answer('❌ Kino nomi topilmadi. Masalan: 🎬 Kino nomi: Qasos')
    if not info['code']:
        return await m.answer('❌ Kino kodi topilmadi. Kodni eng oxirgi qatorda yozing: 🔢 Kod: 1234')
    d=await state.get_data()
    code=info['code'].strip()
    if len(code)>64 or any(ch.isspace() for ch in code): return await m.answer('❌ Kod noto‘g‘ri. Kod 64 belgigacha va bo‘shliqsiz bo‘lsin.')
    async with Session() as s:
        if (await s.execute(select(Movie).where(Movie.code==code))).scalar_one_or_none() or (await s.execute(select(Series).where(Series.code==code))).scalar_one_or_none():
            return await m.answer('❌ Bu kod allaqachon ishlatilgan. Boshqa kod kiriting.')
        x=Movie(code=code,title_uz=info['title'],title_ru=info['title'],description_uz=info['description'],description_ru=info['description'],description_uz_entities=serialize_entities(m.entities),description_ru_entities=serialize_entities(m.entities),metadata_text=m.text,metadata_entities=serialize_entities(m.entities),year=info['year'],genre=info['genre'],country=info['country'],rating=info['rating'],video_file_id=d['video_file_id'],video_file_unique_id=d['video_file_unique_id'])
        s.add(x); await s.commit(); await s.refresh(x)
    await publish_ad(m.bot,x,'movie'); await state.clear()
    await m.answer(f'✅ Kino qo‘shildi!\n🎬 {x.title_uz}\n🔢 Kod: {x.code}')

@router.message(SeriesAddState.waiting_video,F.video)
async def sv(m,state):
    await state.update_data(video_file_id=m.video.file_id,video_file_unique_id=m.video.file_unique_id)
    await state.set_state(SeriesAddState.waiting_info)
    await m.answer(info_prompt('series'))

@router.message(SeriesAddState.waiting_info,F.text)
async def si(m,state):
    info=parse_info(m.text)
    if not info['title']:
        return await m.answer('❌ Serial nomi topilmadi. Masalan: 🎬 Serial nomi: ...')
    if not info['code']:
        return await m.answer('❌ Serial kodi topilmadi. Kodni eng oxirgi qatorda yozing: 🔢 Kod: 1234')
    d=await state.get_data(); code=info['code'].strip()
    if len(code)>64 or any(ch.isspace() for ch in code): return await m.answer('❌ Kod noto‘g‘ri. Kod 64 belgigacha va bo‘shliqsiz bo‘lsin.')
    async with Session() as s:
        if (await s.execute(select(Movie).where(Movie.code==code))).scalar_one_or_none() or (await s.execute(select(Series).where(Series.code==code))).scalar_one_or_none():
            return await m.answer('❌ Bu kod allaqachon ishlatilgan. Boshqa kod kiriting.')
        x=Series(code=code,title_uz=info['title'],title_ru=info['title'],description_uz=info['description'],description_ru=info['description'],description_uz_entities=serialize_entities(m.entities),description_ru_entities=serialize_entities(m.entities),metadata_text=m.text,metadata_entities=serialize_entities(m.entities),year=info['year'],genre=info['genre'],country=info['country'],rating=info['rating'])
        s.add(x); await s.flush()
        s.add(Episode(series_id=x.id,season_number=1,episode_number=1,title_uz=info['title'],title_ru=info['title'],description_uz=info['description'],description_ru=info['description'],description_uz_entities=serialize_entities(m.entities),description_ru_entities=serialize_entities(m.entities),video_file_id=d['video_file_id'],video_file_unique_id=d['video_file_unique_id']))
        await s.commit(); await s.refresh(x)
    await publish_ad(m.bot,x,'series'); await state.clear()
    await m.answer(f'✅ Serial qo‘shildi!\n📺 {x.title_uz}\n🔢 Kod: {x.code}\n🎞 1-qism: 1-fasl')

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
            metadata_text=caption,
            metadata_entities=serialize_entities(post.caption_entities),
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
    rows.insert(0,[InlineKeyboardButton(text='➕ Kanal/guruh qo‘shish',callback_data='mandatory_add_help')])
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


# ---------- Mandatory subscription by URL ----------
def _resolve_chat_from_url(url: str):
    url = url.strip()
    if url.startswith('@'):
        return url
    m = re.match(r'^https?://t\.me/([A-Za-z0-9_]{5,})/?$', url)
    if m:
        return '@' + m.group(1)
    m = re.match(r'^https?://t\.me/c/(\d+)(?:/\d+)?/?$', url)
    if m:
        return int('-100' + m.group(1))
    return None

@router.callback_query(F.data == 'mandatory_add_help')
async def mandatory_add_start(c, state):
    if not is_admin_id(c.from_user.id):
        return await c.answer('Ruxsat yo‘q', show_alert=True)
    await state.set_state(MandatoryAddState.waiting_url)
    await c.message.answer(
        '➕ Kanal yoki guruh havolasini yuboring.\n\n'
        'Masalan:\n'
        'https://t.me/kanal_nomi\n'
        'https://t.me/c/123456789/1\n\n'
        '⚠️ Bot shu kanal/guruhda administrator bo‘lishi kerak.'
    )
    await c.answer()

@router.message(MandatoryAddState.waiting_url)
async def mandatory_add_url(m, state):
    if not is_admin(m):
        return
    url = (m.text or '').strip()
    target = _resolve_chat_from_url(url)
    if target is None:
        return await m.answer(
            '❌ Bu havoladan kanal/guruhni aniqlab bo‘lmadi.\n\n'
            'Public kanal/guruh uchun: https://t.me/username\n'
            'Private kanal/guruh uchun esa Telegramdagi xabar havolasini yuboring: https://t.me/c/123456789/1'
        )
    try:
        chat = await m.bot.get_chat(target)
        me = await m.bot.get_chat_member(chat.id, m.bot.id)
        if me.status not in ('administrator', 'creator'):
            return await m.answer('❌ Bot bu kanal/guruhda administrator emas.')
    except Exception:
        return await m.answer(
            '❌ Kanal/guruhni topib bo‘lmadi. Botni avval administrator qiling va havolani qayta yuboring.'
        )
    async with Session() as s:
        exists = (await s.execute(
            select(MandatoryChannel).where(MandatoryChannel.chat_id == chat.id, MandatoryChannel.active.is_(True))
        )).scalar_one_or_none()
        if exists:
            await state.clear()
            return await m.answer('⚠️ Bu kanal/guruh allaqachon majburiy obunada.')
        code = f'{chat.id}_{uuid4().hex[:8]}'
        s.add(MandatoryChannel(
            chat_id=chat.id,
            title=chat.title or str(chat.id),
            url=url,
            chat_type=chat.type,
            tracking_code=code,
        ))
        await s.commit()
    await state.clear()
    await m.answer(f'✅ Majburiy obuna qo‘shildi:\n📢 {chat.title or chat.id}\n🔗 {url}')

# ---------- Admin panel sections ----------
@router.message(F.text == '📊 Statistika')
async def stats_button(m):
    if is_admin(m):
        await stats(m)

@router.message(F.text == '👥 Foydalanuvchilar')
async def users_button(m):
    if not is_admin(m): return
    async with Session() as s:
        total = await s.scalar(select(func.count()).select_from(User))
        vip_users = await s.scalar(select(func.count()).select_from(User).where(User.vip_expires_at != None))
    await m.answer(f'👥 Foydalanuvchilar\n\nJami: {total}\n👑 VIP bo‘lganlar: {vip_users}')

@router.message(F.text == '🎁 Referallar')
async def referrals_button(m):
    if not is_admin(m): return
    from app.database.models import Referral
    async with Session() as s:
        total = await s.scalar(select(func.count()).select_from(Referral))
        qualified = await s.scalar(select(func.count()).select_from(Referral).where(Referral.status == 'QUALIFIED'))
    await m.answer(f'🎁 Referallar\n\nJami: {total}\n✅ Tasdiqlangan: {qualified}')

@router.message(F.text == '📣 Reklama')
async def broadcast_button(m):
    if not is_admin(m): return
    await m.answer('📣 Reklama\n\nXabar yuborish uchun /broadcast buyrug‘idan foydalaning.')

@router.message(F.text == '⚙️ Sozlamalar')
async def settings_button(m):
    if not is_admin(m): return
    await m.answer(
        '⚙️ Sozlamalar\n\n'
        f'🤖 Bot: @{settings.bot_username.lstrip("@")}\n'
        f'📢 Reklama kanali: {settings.ad_channel_url or "sozlanmagan"}\n'
        f'🗄 Private kanal: {settings.private_movie_channel_url or "sozlanmagan"}'
    )

@router.message(F.text == '💳 To‘lovlar')
async def payments_button(m):
    if not is_admin(m): return
    async with Session() as s:
        pending = (await s.execute(
            select(VipPayment).where(VipPayment.status == 'PENDING').order_by(VipPayment.created_at.desc())
        )).scalars().all()
    if not pending:
        return await m.answer('💳 Hozircha kutilayotgan VIP to‘lovlari yo‘q.')
    await m.answer('💳 Kutilayotgan to‘lovlar: ' + str(len(pending)) + '\nCheklar kelishi bilan ular adminlarga avtomatik yuboriladi.')

# ---------- VIP payment approval: atomic, idempotent ----------
@router.callback_query(F.data.startswith('vip_payment:'))
async def vip_payment_action(c: CallbackQuery):
    if not is_admin_id(c.from_user.id):
        return await c.answer('Ruxsat yo‘q', show_alert=True)
    _, action, payment_id = c.data.split(':', 2)
    from datetime import datetime, timezone, timedelta
    from app.database.models import VipTransaction, VipPlan
    async with Session() as s:
        payment = (await s.execute(
            select(VipPayment).where(VipPayment.payment_id == payment_id).with_for_update()
        )).scalar_one_or_none()
        if not payment:
            return await c.answer('❌ To‘lov topilmadi.', show_alert=True)
        if payment.status != 'PENDING':
            label = {'APPROVED':'✅ Tasdiqlangan','REJECTED':'❌ Rad etilgan','EXPIRED':'⏰ Muddati tugagan'}.get(payment.status, payment.status)
            return await c.answer(f'⚠️ Bu to‘lov allaqachon yakunlangan: {label}', show_alert=True)
        now = datetime.now(timezone.utc)
        if payment.expires_at and payment.expires_at <= now:
            payment.status = 'EXPIRED'
            payment.rejection_reason = '5 daqiqalik to‘lov muddati tugagan.'
            await s.commit()
            return await c.answer('⏰ To‘lovning 5 daqiqalik muddati tugagan.', show_alert=True)
        if not payment.receipt_file_id:
            return await c.answer('⚠️ Chek hali yuborilmagan.', show_alert=True)
        user = await s.get(User, payment.user_id)
        plan = await s.get(VipPlan, payment.plan_id)
        if not user or not plan:
            return await c.answer('❌ To‘lov ma’lumotlari topilmadi.', show_alert=True)
        payment.status = 'APPROVED' if action == 'approve' else 'REJECTED'
        payment.verified_at = now
        payment.verified_by = c.from_user.id
        if action == 'approve':
            current = user.vip_expires_at
            base = current if current and current > now else now
            user.vip_expires_at = base + timedelta(days=plan.days)
            s.add(VipTransaction(user_id=user.id, type='PURCHASE', days=plan.days, payment_id=payment.payment_id, admin_id=c.from_user.id))
        else:
            payment.rejection_reason = 'Admin tomonidan rad etildi.'
        await s.commit()
        status_text = '✅ TASDIQLANGAN' if action == 'approve' else '❌ RAD ETILGAN'
        expires = user.vip_expires_at.strftime('%d.%m.%Y %H:%M') if action == 'approve' and user.vip_expires_at else '-'
    await c.message.edit_caption(
        caption=(c.message.caption or '') + f'\n\n<b>HOLAT: {status_text}</b>\n👨‍💼 Admin ID: <code>{c.from_user.id}</code>' + (f'\n⏳ VIP: {expires}' if action == 'approve' else ''),
        reply_markup=None
    )
    try:
        await c.bot.send_message(
            user.telegram_id,
            f"{'✅ VIP to‘lovingiz tasdiqlandi!' if action == 'approve' else '❌ VIP to‘lovingiz rad etildi.'}\n\n"
            f'👑 Tarif: {plan.name_uz}\n💰 Summa: {payment.amount:,} UZS' +
            (f'\n⏳ VIP muddati: {expires}' if action == 'approve' else '')
        )
    except Exception:
        pass
    await c.answer('To‘lov tasdiqlandi.' if action == 'approve' else 'To‘lov rad etildi.')
