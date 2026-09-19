# 🎬 Kodli Kino + Serial + VIP Bot

Production-oriented Telegram bot skeleton for Python 3.11+, aiogram 3, PostgreSQL, SQLAlchemy Async, Alembic and Render.

## 1. Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m app.main
```

Windows activation: `.venv\\Scripts\\activate`.

## 2. Environment

Fill `.env` with `BOT_TOKEN`, `BOT_USERNAME`, `ADMIN_IDS`, `DATABASE_URL`, public ad channel values, private movie channel values and card values.

`ADMIN_IDS` is a comma-separated list, e.g. `123456789,987654321`.

## 3. Telegram channels

### Public advertisement channel
Set:
- `AD_CHANNEL_ID`
- `AD_CHANNEL_URL`

Add the bot as an administrator with permission to post.

### Private movie database channel
Set:
- `PRIVATE_MOVIE_CHANNEL_ID`
- `PRIVATE_MOVIE_CHANNEL_URL`

Add the bot as administrator so it can access channel posts. Videos are represented by Telegram `file_id` instead of being stored on Render.

## 4. Mandatory subscription

Each mandatory channel/group must have the bot as administrator. Use only the minimum permissions needed for the selected Telegram chat type. The admin configuration should validate that the bot can access the chat.

The end-user UI intentionally hides whether a mandatory item is a channel, group or request-to-join. Every item is displayed as exactly `📢 Majburiy obuna`; Telegram itself reveals the destination after the user taps it.

Telegram does not expose a universal raw click counter. Do not invent clicks. Use subscription checks and invite tracking where Telegram API permits it.

## 5. VIP

Default plans:
- 3 days — 7,000 UZS
- 7 days — 15,000 UZS
- 14 days — 23,000 UZS
- 30 days — 39,000 UZS
- 90 days — 55,000 UZS
- 1 year — 145,000 UZS

Manual card payments are stored as PENDING until an authorized admin verifies them.

## 6. Referral

A referral qualifies after the invited user starts, completes registration and mandatory subscription checks. Every 50 qualified referrals grants 14 VIP days. Duplicate and self-referrals must be rejected.

## 7. Custom Emoji

Telegram message entities are stored in JSON fields so custom emoji metadata can be preserved when text is handled programmatically. Keep Telegram UTF-16 offsets intact.

## 8. Render

This project is configured as a Render Background Worker. The start command runs migrations and then starts polling:

`alembic upgrade head && python -m app.main`

Create a PostgreSQL database and provide the environment variables in the Render dashboard.

## 9. Security

Never commit `.env`. Never place real bot tokens or card credentials in source code. All sensitive admin actions must be server-side authorized. Payment state transitions must be idempotent.

## 10. Important implementation note

Telegram permissions and invite/request APIs differ by chat type and Bot API version. The project should fail clearly when a required capability is unavailable rather than pretending that an event was recorded.

## Render Web Service

This project is configured for **Render Web Service**, not Background Worker.

The application starts a small HTTP server on `0.0.0.0:$PORT` and exposes:

- `/` — simple running message
- `/health` — health check returning JSON

At the same time, the Telegram bot runs with long polling in the same process.

Render supplies the `PORT` environment variable automatically. Do not hardcode a public port in Render. The application falls back to `10000` only for local development.

Recommended Render settings:

- Service Type: **Web Service**
- Build Command: `pip install -r requirements.txt`
- Start Command: `alembic upgrade head && python -m app.main`
- Health Check Path: `/health`

## 🎬 Kino/serial qo‘shishning yangi admin oqimi

Admin panelda **🎬 Kinolar → ➕ Kino qo‘shish** yoki **📺 Seriallar → ➕ Serial qo‘shish** tanlanadi.

1. Admin avval videoni botga yuboradi.
2. Bot kino/serial nomi, yil, janr, davlat, reyting va tavsifni bitta xabarda so‘raydi.
3. Admin shu xabarda Telegram Premium Custom Emoji ishlatishi mumkin; bot Telegram entity ma’lumotlarini saqlaydi va reklama postida qayta ishlatadi.
4. Bot reklama uchun poster/afishani so‘raydi.
5. Admin poster yuboradi va qo‘shish jarayoni tugaydi.
6. Bot kontentni PostgreSQL bazasiga saqlaydi va `AD_CHANNEL_ID` ko‘rsatilgan reklama kanaliga poster + metadata + deep-link tugmasini avtomatik yuboradi.

Serial qo‘shishda yuborilgan birinchi video avtomatik ravishda **1-fasl, 1-qism** sifatida saqlanadi. Keyingi qismlar uchun serial boshqaruviga alohida episode qo‘shish funksiyasi kengaytirilishi mumkin.

Videolar Render diskiga yuklab olinmaydi: Telegram `file_id`/`file_unique_id` saqlanadi.
