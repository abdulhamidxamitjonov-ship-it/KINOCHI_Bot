import asyncio, os, logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from app.config import settings
from app.handlers import admin, movies, payments, profile, series, start, subscriptions, vip
from app.utils.logger import setup_logging

logger = logging.getLogger(__name__)

async def health(request):
    return web.json_response({'status': 'ok', 'service': 'kino-bot'})

async def setup_commands(bot):
    await bot.set_my_commands(
        [BotCommand(command='start', description='Botni ishga tushirish')],
        scope=BotCommandScopeDefault()
    )

    cmds = [
        ('admin', 'Admin paneli'),
        ('stats', 'Statistika'),
        ('movies', 'Kinolar'),
        ('series', 'Seriallar'),
        ('users', 'Foydalanuvchilar'),
        ('vip', 'VIP'),
        ('payments', 'To‘lovlar'),
        ('channels', 'Majburiy obunalar'),
        ('broadcast', 'Xabar yuborish'),
    ]

    # One invalid/inactive admin must never stop the whole bot.
    for aid in settings.admins:
        try:
            await bot.set_my_commands(
                [BotCommand(command=a, description=d) for a, d in cmds],
                scope=BotCommandScopeChat(chat_id=aid)
            )
        except Exception as e:
            logger.warning("Could not set admin commands for %s: %s", aid, e)

async def main():
    setup_logging(settings.log_level)
    bot = Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    await setup_commands(bot)

    for r in [
        start.router,
        subscriptions.router,
        admin.router,
        series.router,
        movies.router,
        vip.router,
        profile.router,
        payments.router,
    ]:
        dp.include_router(r)

    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text='Kino Bot is running.'))
    app.router.add_get('/health', health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(
        runner,
        '0.0.0.0',
        int(os.getenv('PORT', '10000'))
    )
    await site.start()

    logger.info("Kino Bot started. Admins: %s", sorted(settings.admins))

    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
