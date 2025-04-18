import json
import os
from string import punctuation

from aiogram import F, Bot, types, Router
from aiogram.filters import Command

from filters.chat_types import ChatTypeFilter
from common.restricted_words import restricted_words
from utils.json_operations import save_admins


user_group_router = Router()
user_group_router.message.filter(ChatTypeFilter(["group", "supergroup"]))
user_group_router.edited_message.filter(ChatTypeFilter(["group", "supergroup"]))

ADMIN_FILE = "admins.json"



@user_group_router.message(Command("admin"))
async def get_admins(message: types.Message, bot: Bot):
    chat_id = message.chat.id
    admins_list = await bot.get_chat_administrators(chat_id)

    # Формируем новый список админов, исключая ботов
    admins_list = [
        member.user.id
        for member in admins_list
        if member.status in ["creator", "administrator"] and not member.user.is_bot
    ]

    save_admins(admins_list)

    if os.path.exists(ADMIN_FILE):
        with open(ADMIN_FILE, "r", encoding="utf-8") as file:
            bot.my_admins_list = json.load(file)

    if message.from_user.id in bot.my_admins_list:
        await message.delete()


def clean_text(text: str):
    return text.translate(str.maketrans("", "", punctuation))


@user_group_router.edited_message()
@user_group_router.message()
async def cleaner(message: types.Message):
    if restricted_words.intersection(clean_text(message.text.lower()).split()):
        await message.answer(
            f"{message.from_user.first_name}, соблюддайте порядок в чате!"
        )
        await message.delete()
        # await message.chat.ban(message.from_user.id)

#TODO реализовать вывод вновь внесенных товаров в каталог