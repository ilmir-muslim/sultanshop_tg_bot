import asyncio
import os

from aiogram import Bot, Dispatcher
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()


@dp.message()
async def echo(message):
    await message.answer(message.text)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
