import asyncio
import os

from aiogram import Bot, Dispatcher, types

from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

from handlers.user_privat import user_privat_router

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

dp.include_router(user_privat_router)


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
