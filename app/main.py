import asyncio
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import settings
from app.handlers import (
    admin,
    movies,
    payments,
    profile,
    series,
    start,
    subscriptions,
    vip,
)
from app.utils.logger import setup_logging


async def health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "kino-bot"})


async def root(request: web.Request) -> web.Response:
    return web.Response(text="Kino Bot is running.")


async def start_web_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", root)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    return runner


async def main() -> None:
    setup_logging(settings.log_level)

    bot = Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    for router in [
        start.router,
        subscriptions.router,
        movies.router,
        series.router,
        vip.router,
        profile.router,
        payments.router,
        admin.router,
    ]:
        dp.include_router(router)

    web_runner = await start_web_server()

    try:
        await dp.start_polling(bot)
    finally:
        await web_runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
