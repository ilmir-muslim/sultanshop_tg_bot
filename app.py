import asyncio
import os
import json
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from dotenv import find_dotenv, load_dotenv


load_dotenv(find_dotenv())

from config import ADMIN_FILE
from middlewares.db import DataBaseSession

from database.engine import create_db, session_maker

from handlers.user_private import user_private_router
from handlers.user_group import send_random_item_periodically, user_group_router
from handlers.admin_private import admin_router
from handlers.menu_processing import menu_progressing_router
from handlers.deliverer_private import deliverer_private_router

# from common.bot_cmds_list import private
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",  # Формат логов
    handlers=[
        logging.FileHandler(
            "app.log", encoding="utf-8"
        ),  # Логи сохраняются в файл app.log
        logging.StreamHandler(),  # Логи также выводятся в терминал
    ],
)

# Пример использования логирования
logging.info("Приложение запущено")

# ALLOWED_UPDATES = ['message', 'edited_message', 'callback_query']

bot = Bot(
    token=os.getenv("TELEGRAM_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)


async def initialize_bot_data(bot: Bot, session_maker):
    """
    Инициализация данных для бота, таких как список администраторов и доставщиков.
    """
    if os.path.exists(ADMIN_FILE):
        with open(ADMIN_FILE, "r", encoding="utf-8") as file:
            admin_list = json.load(file)
            bot.my_admins_list = admin_list
    else:
        bot.my_admins_list = []


dp = Dispatcher()

dp.include_router(user_private_router)
dp.include_router(user_group_router)
dp.include_router(admin_router)
dp.include_router(menu_progressing_router)
dp.include_router(deliverer_private_router)


async def on_startup(bot):

    await create_db()

    await initialize_bot_data(bot, session_maker)

    asyncio.create_task(send_random_item_periodically(session_maker, bot))


async def on_shutdown(bot):
    print("бот лег")


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    dp.update.middleware(DataBaseSession(session_pool=session_maker))

    await bot.delete_webhook(drop_pending_updates=True)
    # await bot.delete_my_commands(scope=types.BotCommandScopeAllPrivateChats())
    # await bot.set_my_commands(commands=private, scope=types.BotCommandScopeAllPrivateChats())
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


asyncio.run(main())
