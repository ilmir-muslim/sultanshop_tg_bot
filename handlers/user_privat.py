from aiogram import types, Router
from aiogram.filters import CommandStart, Command


user_privat_router = Router()

@user_privat_router.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(f"Привет, {message.from_user.first_name}")

@user_privat_router.message(Command("menu"))
async def menu_cmd(message: types.Message):
    await message.answer("Меню")