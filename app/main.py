import asyncio
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

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


async def setup_bot_commands(bot: Bot) -> None:
    # User commands
    await bot.set_my_commands([
        BotCommand(command="start", description="Botni ishga tushirish"),
    ], scope=BotCommandScopeDefault())

    # Full admin command menu is visible in the bottom-left menu button
    # only for configured admin chats.
    admin_commands = [
        BotCommand(command="admin", description="Admin panel"),
        BotCommand(command="stats", description="Statistika"),
        BotCommand(command="movies", description="Kinolar"),
        BotCommand(command="series", description="Seriallar"),
        BotCommand(command="users", description="Foydalanuvchilar"),
        BotCommand(command="vip", description="VIP boshqaruvi"),
        BotCommand(command="payments", description="To‘lovlar"),
        BotCommand(command="channels", description="Majburiy obuna"),
        BotCommand(command="broadcast", description="Xabar yuborish"),
    ]
    for admin_id in settings.admins:
        await bot.set_my_commands(
            admin_commands,
            scope=BotCommandScopeChat(chat_id=admin_id),
        )


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

    await setup_bot_commands(bot)

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
