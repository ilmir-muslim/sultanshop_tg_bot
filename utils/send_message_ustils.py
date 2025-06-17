import hashlib
import json
import logging

from aiogram import Bot
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.deep_linking import create_start_link


from sqlalchemy.ext.asyncio import AsyncSession

from config import GROUPS_FILE
from kbds.inline import inline_buttons_kb
from database.orm_query import orm_get_product_by_name
from utils.json_operations import save_callback_data



class BuyCallbackData(CallbackData, prefix="buy"):
    product_hash: str  # MD5 от названия (32 символа)
    product_id: int

    @classmethod
    def from_product(cls, product_name: str, product_id: int):
        product_hash = hashlib.md5(product_name.encode()).hexdigest()
        return cls(product_hash=product_hash, product_id=product_id)
    

async def send_product_message(
    session: AsyncSession,
    bot: Bot,
    product_data: dict,
) -> None:
    """
    Формирует и отправляет сообщение о товаре в указанный чат.
    
    Args:
        session: Асинхронная сессия SQLAlchemy
        bot: Экземпляр бота AIOGram
        chat_id: ID чата, куда отправляем сообщение
        product_data: Данные товара (name, description, price, image)
    """

    with open(GROUPS_FILE, "r", encoding="utf-8") as file:
        chats = json.load(file)


    # Проверяем обязательные поля
    required_fields = ["name", "description", "price", "image"]
    if not all(field in product_data for field in required_fields):
        logging.error(f"Неполные данные товара: {product_data}")
        return

    # Получаем ID товара из БД
    product_id = await orm_get_product_by_name(
        session=session,
        product_name=product_data["name"],
    )
    product_data["id"] = product_id

    # Формируем callback и сохраняем его
    callback_data = BuyCallbackData.from_product(
        product_name=product_data["name"],
        product_id=product_id,
    ).pack()

    
    logging.info(f"ID товара: {product_id}")

    # Создаем ссылку для кнопки "Купить"
    url = await create_start_link(bot, f"add_to_cart_{product_id}")
    logging.info(f"Сформированная ссылка: {url}")

    # Формируем текст сообщения
    item_text = (
        f"<strong>{product_data['name']}</strong>\n"
        f"{product_data['description']}\n"
        f"<strong>Цена:</strong> {product_data['price']}£\n"
    )

    # Создаем клавиатуру с кнопкой "Купить"
    keyboard = inline_buttons_kb({"Купить": {"url": url}})

    # Отправляем сообщение
    for chat_id in chats:
        try:
            save_callback_data(callback_data, product_data, chat_id)
            await bot.send_photo(
                chat_id=chat_id,
                photo=product_data["image"],
                caption=item_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            logging.info(f"Отправлено в {chat_id}")

        except Exception as e:
            logging.error(f"Ошибка отправки в {chat_id}: {e}")