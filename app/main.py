import asyncio,os
from aiohttp import web
from aiogram import Bot,Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand,BotCommandScopeChat,BotCommandScopeDefault
from app.config import settings
from app.handlers import admin,movies,payments,profile,series,start,subscriptions,vip
from app.utils.logger import setup_logging
async def health(request):return web.json_response({'status':'ok','service':'kino-bot'})
async def setup_commands(bot):
 await bot.set_my_commands([BotCommand(command='start',description='Botni ishga tushirish')],scope=BotCommandScopeDefault())
 cmds=[('admin','Admin paneli'),('stats','Statistika'),('movies','Kinolar'),('series','Seriallar'),('users','Foydalanuvchilar'),('vip','VIP'),('payments','To‘lovlar'),('channels','Majburiy obunalar'),('broadcast','Xabar yuborish')]
 for aid in settings.admins: await bot.set_my_commands([BotCommand(command=a,description=d) for a,d in cmds],scope=BotCommandScopeChat(chat_id=aid))
async def main():
 setup_logging(settings.log_level);bot=Bot(settings.bot_token,default=DefaultBotProperties(parse_mode=ParseMode.HTML));dp=Dispatcher();await setup_commands(bot)
 for r in [start.router,subscriptions.router,movies.router,series.router,vip.router,profile.router,payments.router,admin.router]:dp.include_router(r)
 app=web.Application();app.router.add_get('/',lambda r:web.Response(text='Kino Bot is running.'));app.router.add_get('/health',health);runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'0.0.0.0',int(os.getenv('PORT','10000')));await site.start()
 try:await dp.start_polling(bot)
 finally:await runner.cleanup();await bot.session.close()
if __name__=='__main__':asyncio.run(main())
