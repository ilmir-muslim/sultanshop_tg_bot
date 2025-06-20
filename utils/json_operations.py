import json
import hashlib
import logging
import random
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import orm_check_product_available, orm_get_products
from utils.json_utils import decimal_default, prepare_for_json
from config import ADMIN_FILE


def save_admins(admins_list):
    try:
        with open(ADMIN_FILE, "r", encoding="utf-8") as file:
            existing_admins = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_admins = []

    if isinstance(admins_list, int):
        admins_list = [admins_list]
    for admin_id in admins_list:
        if admin_id not in existing_admins:
            existing_admins.append(admin_id)

    with open(ADMIN_FILE, "w", encoding="utf-8") as file:
        json.dump(existing_admins, file, ensure_ascii=False, indent=4)


def save_added_goods(added_good):
    try:
        with open("added_goods.json", "r", encoding="utf-8") as file:
            existing_goods = json.load(file)
    except FileNotFoundError:
        existing_goods = []
    existing_goods.append(added_good)

    with open("added_goods.json", "w", encoding="utf-8") as file:
        json.dump(existing_goods, file, ensure_ascii=False, indent=4)


async def get_and_remove_random_item(session: AsyncSession):
    """
    Получает случайный товар из файла или БД, удаляет его из списка и возвращает.
    Если файл пуст, загружает все товары из базы данных.
    """
    # Загружаем данные из файла
    goods = []
    try:
        with open("added_goods.json", "r", encoding="utf-8") as file:
            goods = json.load(file)
        logging.debug(f"Загружено {len(goods)} товаров из файла")
    except FileNotFoundError:
        logging.info("Файл added_goods.json не найден, будет создан новый")
    except json.JSONDecodeError as e:
        logging.error(f"Ошибка чтения JSON: {e}. Файл будет пересоздан")
    except Exception as e:
        logging.error(f"Неожиданная ошибка при чтении файла: {e}")

    # Если товаров нет, загружаем из БД
    if not goods:
        try:
            products = await orm_get_products(session)
            if not products:
                logging.error("В базе данных нет товаров")
                return None

            goods = []
            for product in products:
                try:
                    is_available = await orm_check_product_available(
                        session, product.id
                    )
                    if not is_available or product.name.startswith("Зона доставки"):
                        logging.info(f"Товар {product.name} недоступен")
                        continue
                    item_data = {
                        "id": product.id,
                        "name": product.name,
                        "description": product.description,
                        "category": product.category.id if product.category else None,
                        "seller": product.seller.id if product.seller else None,
                        "purchase_price": product.purchase_price,
                        "price": product.price,
                        "image": product.image,
                    }
                    goods.append(prepare_for_json(item_data))
                except Exception as e:
                    logging.error(
                        f"Ошибка обработки товара {getattr(product, 'name', 'UNKNOWN')}: {e}"
                    )

            # Сохраняем в файл
            try:
                with open("added_goods.json", "w", encoding="utf-8") as file:
                    json.dump(
                        goods,
                        file,
                        ensure_ascii=False,
                        indent=4,
                        default=decimal_default,
                    )
                logging.info(f"Сохранено {len(goods)} товаров в файл")
            except Exception as e:
                logging.error(f"Ошибка сохранения товаров в файл: {e}")
                # Продолжаем работу без сохранения в файл

        except Exception as e:
            logging.error(f"Ошибка загрузки товаров из БД: {e}")
            return None

    # Проверяем наличие товаров
    if not goods:
        logging.error("Нет доступных товаров для отправки")
        return None

    # Выбираем и удаляем случайный товар
    try:
        random_item = random.choice(goods)
        logging.debug(f"Выбран товар: {random_item['name']}")

        # Удаляем товар из списка
        goods.remove(random_item)

        # Обновляем файл
        try:
            with open("added_goods.json", "w", encoding="utf-8") as file:
                json.dump(
                    goods, file, ensure_ascii=False, indent=4, default=decimal_default
                )
        except Exception as e:
            logging.error(f"Ошибка обновления файла товаров: {e}")
            # Продолжаем работу без сохранения изменений

        return random_item

    except Exception as e:
        logging.error(f"Ошибка при обработке случайного товара: {e}")
        return None


CALLBACK_FILE = "button_callbacks.json"


def generate_callback_data(item, chat_id) -> str:
    """
    Генерирует уникальный хэш для товара с учетом группы и изображения.
    """
    unique_string = f"{item['name']}_{item['price']}_{item['description']}_{chat_id}_{item['image']}"
    return hashlib.md5(unique_string.encode()).hexdigest()


def save_callback_data(callback_data, item, chat_id):
    """
    Сохраняет соответствие хэша и данных товара в файл.
    """
    CALLBACK_FILE = "button_callbacks.json"
    try:
        with open(CALLBACK_FILE, "r", encoding="utf-8") as file:
            callbacks = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        callbacks = {}

    # Сохраняем хэш и данные товара
    callbacks[callback_data] = {"item": item, "chat_id": chat_id}

    with open(CALLBACK_FILE, "w", encoding="utf-8") as file:
        json.dump(callbacks, file, ensure_ascii=False, indent=4)

SHARING_DATA_FILE = "sharing_data.json"

def save_sharing_data(sharing_data):
    """
    Добавляет данные в файл sharing_data.json для использования в других частях кода.
    """
    try:
        with open(SHARING_DATA_FILE, "r", encoding="utf-8") as file:
            existing_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_data = {}

    # Обновляем существующие данные новыми
    existing_data.update(sharing_data)

    # Сохраняем обновлённый словарь в файл
    with open(SHARING_DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(existing_data, file, ensure_ascii=False, indent=4)
    logging.info("Данные для шеринга сохранены в файл sharing_data.json")


def load_sharing_data(user_id) -> dict:
    """
    Возвращает значение dict_key для конкретного user_id из sharing_data.json.
    """
    with open(SHARING_DATA_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)
    user_data = data.get(str(user_id), {})
    return user_data

def delete_sharing_data(user_id):
    """
    Удаляет данные для конкретного user_id из sharing_data.json.
    """
    try:
        with open(SHARING_DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        if str(user_id) in data:
            del data[str(user_id)]
            with open(SHARING_DATA_FILE, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
            logging.info(f"Данные для user_id {user_id} удалены из sharing_data.json")
        else:
            logging.warning(f"Нет данных для user_id {user_id} в sharing_data.json")
    except FileNotFoundError:
        logging.error("Файл sharing_data.json не найден")
    except json.JSONDecodeError:
        logging.error("Ошибка чтения JSON: файл может быть повреждён")
    except Exception as e:
        logging.error(f"Неожиданная ошибка: {e}")