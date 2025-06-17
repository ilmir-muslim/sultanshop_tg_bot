import asyncio
from asyncio.log import logger
import json
import logging
import hashlib
import random
from datetime import datetime, time

from aiogram import Bot, types, Router
from aiogram.filters import Command

from sqlalchemy.ext.asyncio import async_sessionmaker

from config import GROUPS_FILE
from filters.chat_types import ChatTypeFilter

from utils.json_operations import (
    get_and_remove_random_item,
)
from utils.send_message_ustils import send_product_message


user_group_router = Router()
user_group_router.message.filter(ChatTypeFilter(["group", "supergroup", "channel"]))
user_group_router.edited_message.filter(
    ChatTypeFilter(["group", "supergroup", "channel"])
)
user_group_router.channel_post.filter(ChatTypeFilter(["channel"]))


@user_group_router.channel_post(Command("get_channel_id"))
async def get_channel_id(message: types.Message):
    channel_id = message.chat.id

    # Загружаем текущий список id чатов
    try:
        with open(GROUPS_FILE, "r", encoding="utf-8") as file:
            chats = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        chats = []

    # Добавляем id, если его ещё нет
    if channel_id not in chats:
        chats.append(channel_id)
        with open(GROUPS_FILE, "w", encoding="utf-8") as file:
            json.dump(chats, file, ensure_ascii=False, indent=2)
        logger.info(f"ID этого канала: {channel_id}\nКанал добавлен в рассылку.")
    else:
        logger.info(f"ID этого канала: {channel_id}\nКанал уже есть в рассылке.")


async def send_random_item_periodically(session_maker: async_sessionmaker, bot: Bot):
    """Отправляет случайные товары в группы и каналы только в разрешенное время (9:00-21:00)"""
    logging.info("Функция send_random_item_periodically запущена")

    # Настройки времени работы (9:00 - 21:00)
    START_TIME = time(9, 0)  # 9:00 утра
    END_TIME = time(21, 0)  # 21:00 вечера
    DAY_INTERVAL = 86400

    while True:
        try:
            random_offset = random.randint(-7200, 7200)  # в секундах (-2ч, +2ч)
            sleep_time = DAY_INTERVAL + random_offset
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

            # Отправляем сообщения
            async with session_maker() as session:
                random_item = await get_and_remove_random_item(session)
                await send_product_message(session, bot, random_item)

            # Пауза между проверками (60 секунд)
            await asyncio.sleep(sleep_time)

        except Exception as e:
            logging.error(f"Критическая ошибка: {e}")
            await asyncio.sleep(sleep_time)
