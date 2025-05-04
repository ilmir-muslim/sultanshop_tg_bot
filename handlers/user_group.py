import asyncio
import json
import logging
import hashlib
import os
from string import punctuation
from datetime import datetime, time

from aiogram import Bot, types, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.deep_linking import create_start_link


from sqlalchemy.ext.asyncio import async_sessionmaker

from database.orm_query import orm_get_product_by_name
from filters.chat_types import ChatTypeFilter
# from common.restricted_words import restricted_words
from kbds.inline import one_button_kb
from utils.json_operations import (
    get_and_remove_random_item,
    save_admins,
    save_callback_data,
)


class BuyCallbackData(CallbackData, prefix="buy"):
    product_hash: str  # MD5 от названия (32 символа)
    product_id: int

    @classmethod
    def from_product(cls, product_name: str, product_id: int):
        product_hash = hashlib.md5(product_name.encode()).hexdigest()
        return cls(product_hash=product_hash, product_id=product_id)


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


# def clean_text(text: str):
#     return text.translate(str.maketrans("", "", punctuation))


# @user_group_router.edited_message()
# @user_group_router.message()
# async def cleaner(message: types.Message):
#     if restricted_words.intersection(clean_text(message.text.lower()).split()):
#         await message.answer(
#             f"{message.from_user.first_name}, соблюдайте порядок в чате!"
#         )
#         await message.delete()
#         # await message.chat.ban(message.from_user.id)


async def send_random_item_periodically(session_maker: async_sessionmaker, bot: Bot):
    """Отправляет случайные товары в группы только в разрешенное время (9:00-21:00)"""
    logging.info("Функция send_random_item_periodically запущена")

    # Настройки времени работы (9:00 - 21:00)
    START_TIME = time(0, 0)  # 9:00 утра
    END_TIME = time(23, 0)  # 21:00 вечера

    while True:
        try:
            current_time = datetime.now().time()

            # Проверяем, находится ли текущее время в разрешенном периоде
            if not (START_TIME <= current_time <= END_TIME):
                # Вычисляем сколько осталось до начала следующего рабочего периода
                if current_time > END_TIME:
                    # Если текущее время после 21:00, ждем до 9:00 следующего дня
                    seconds_until_morning = (
                        (24 * 3600)
                        - (
                            current_time.hour * 3600
                            + current_time.minute * 60
                            + current_time.second
                        )
                        + (START_TIME.hour * 3600)
                    )
                else:
                    # Если текущее время до 9:00, ждем до 9:00
                    seconds_until_morning = (START_TIME.hour * 3600) - (
                        current_time.hour * 3600
                        + current_time.minute * 60
                        + current_time.second
                    )

                logging.info(
                    f"Вне рабочего времени. Следующая проверка через {seconds_until_morning} секунд"
                )
                await asyncio.sleep(seconds_until_morning)
                continue

            # Загружаем список групп
            try:
                with open("groups.json", "r", encoding="utf-8") as file:
                    groups = json.load(file)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logging.error(f"Ошибка загрузки groups.json: {e}")
                await asyncio.sleep(60)
                continue

            if not groups:
                logging.warning("Нет групп для отправки")
                await asyncio.sleep(60)
                continue

            # Отправляем сообщения
            async with session_maker() as session:
                for chat_id in groups:
                    try:
                        random_item = await get_and_remove_random_item(session)
                        # Проверка обязательных полей
                        required_fields = ["name", "description", "price", "image"]
                        if not all(field in random_item for field in required_fields):
                            logging.error(f"Неполные данные товара: {random_item}")
                            continue

                        # Формируем сообщение
                        item_text = (
                            f"<strong>{random_item['name']}</strong>\n"
                            f"{random_item['description']}\n"
                            f"<strong>Цена:</strong> {random_item['price']}£\n"
                        )
                        random_item["id"] = await orm_get_product_by_name(
                            session=session, product_name=random_item["name"]
                        )

                        callback_data = BuyCallbackData.from_product(
                            product_name=random_item["name"],
                            product_id=random_item["id"],
                        ).pack()

                        save_callback_data(callback_data, random_item, chat_id)
                        logging.info(f"ID товара: {random_item['id']}")
                        url = await create_start_link(
                            bot, f"add_to_cart_{random_item['id']}"
                        )
                        logging.info(f"Сформированная ссылка: {url}")
                        keyboard = one_button_kb(text="Купить", url=url)

                        await bot.send_photo(
                            chat_id=chat_id,
                            photo=random_item["image"],
                            caption=item_text,
                            reply_markup=keyboard,
                            parse_mode="HTML",
                        )
                        logging.info(f"Отправлено в {chat_id}")

                    except Exception as e:
                        logging.error(f"Ошибка отправки в {chat_id}: {e}")

            # Пауза между проверками (60 секунд)
            await asyncio.sleep(60)

        except Exception as e:
            logging.error(f"Критическая ошибка: {e}")
            await asyncio.sleep(60)
