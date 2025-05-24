from venv import logger
from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from database.models import (
    Banner,
    Cart,
    Category,
    Deliverer,
    DelivererReview,
    Orders,
    OrderItem,
    Product,
    Seller,
    Users,
    WaitList,
)


############### Работа с баннерами (информационными страницами) ###############


async def orm_add_banner_description(session: AsyncSession, data: dict):
    # Добавляем новый или изменяем существующий по именам
    # пунктов меню: main, about, cart, shipping, payment, catalog
    query = select(Banner)
    result = await session.execute(query)
    if result.first():
        return
    session.add_all(
        [
            Banner(name=name, description=description)
            for name, description in data.items()
        ]
    )
    await session.commit()


async def orm_change_banner_image(session: AsyncSession, name: str, image: str):
    query = update(Banner).where(Banner.name == name).values(image=image)
    await session.execute(query)
    await session.commit()


async def orm_get_banner(session: AsyncSession, page: str):
    query = select(Banner).where(Banner.name == page)
    result = await session.execute(query)
    return result.scalar()


async def orm_get_info_pages(session: AsyncSession):
    query = select(Banner)
    result = await session.execute(query)
    return result.scalars().all()


async def orm_update_orders_banner_description(session: AsyncSession, user_id: int):
    """
    Обновляет описание заказов пользователя со статусами "оформлен" и "в работе"
    в поле description записи с именем 'orders' в таблице Banner.

    :param session: Сессия базы данных.
    :param user_id: ID пользователя.
    """
    # Выполняем запрос для получения заказов пользователя с соединением связанных таблиц
    query = (
        select(
            Orders.id,
            Orders.delivery_address,
            Orders.status,
            Orders.total_price,
            OrderItem.quantity,
            Product.name,
            Product.price,
            Deliverer.first_name,  # Добавляем поле из таблицы Deliverer
            Deliverer.phone,  # Добавляем поле из таблицы Deliverer
        )
        .join(Orders.items)  # Соединяем с таблицей OrderItem
        .join(OrderItem.product)  # Соединяем с таблицей Product
        .outerjoin(
            Orders.deliverer
        )  # Соединяем с таблицей Deliverer (outerjoin для необязательной связи)
        .where(Orders.user_id == user_id, Orders.status.in_(["Оформлен", "В работе"]))
    )
    result = await session.execute(query)
    user_orders = result.fetchall()

    # Формируем текст для записи в поле description
    if not user_orders:
        description = "У вас нет активных заказов."
    else:
        orders_text = ["<strong>Ваши заказы:</strong>"]
        current_order_id = None
        for row in user_orders:
            if row.id != current_order_id:
                # Добавляем информацию о новом заказе
                if current_order_id is not None:
                    # Добавляем разделитель после предыдущего заказа
                    orders_text.append("🔸🔸🔸🔸🔸🔸🔸🔸🔸🔸🔸🔸🔸🔸🔸🔸🔸🔸🔸🔸\n")

                current_order_id = row.id
                deliverer_info = (
                    f"🛵 Курьер : {row.first_name}\n"
                    f"📱 Номер телефона курьера : {row.phone}\n"
                    if row.first_name and row.phone
                    else "Курьер не назначен.\n"
                )
                orders_text.append(
                    f"🆔 Заказ #{row.id}\n"
                    f"📍 Адрес доставки: {row.delivery_address}\n"
                    f"📦 Статус: {row.status}\n"
                    f"💰 Сумма: {row.total_price}£\n"
                    f"{deliverer_info}"
                    f"-----------------------------------\n"
                    "Товары:"
                )
            # Добавляем информацию о товаре в заказе
            orders_text.append(f"- {row.name} x {row.quantity} ({row.price}£ за шт.)")
        orders_text.append("-----------------------------------")
        description = "\n".join(orders_text)
        logger.debug(f"DEBUG: {description}")

    # Ограничиваем длину текста, если он слишком длинный
    
    if len(description) > 1024:
        description = description[:1020] + "...\n(Слишком много данных для отображения)"

    # Обновляем поле description в записи с именем 'orders' в таблице Banner
    update_query = (
        update(Banner).where(Banner.name == "orders").values(description=description)
    )
    await session.execute(update_query)
    await session.commit()

    # Логируем обновление для отладки
    print(f"DEBUG: Поле description обновлено для записи 'orders': {description}")


############################ Категории ######################################


async def orm_get_categories(session: AsyncSession):
    query = select(Category)
    result = await session.execute(query)
    return result.scalars().all()


async def orm_create_categories(session: AsyncSession, categories: list):
    query = select(Category)
    result = await session.execute(query)
    if result.first():
        return
    session.add_all([Category(name=name) for name in categories])
    await session.commit()


async def orm_add_category(session: AsyncSession, category_name: str):
    query = select(Category).where(Category.name == category_name)
    result = await session.execute(query)
    if result.first():
        return False

    # Добавляем новую категорию
    session.add(Category(name=category_name))
    await session.commit()
    return True


############ Админка: добавить/изменить/удалить товар ########################


async def orm_add_product(session: AsyncSession, data: dict):
    new_product = Product(
        name=data["name"],
        description=data["description"],
        category_id=int(data["category"]),
        seller_id=int(data["seller"]),
        purchase_price=float(data["purchase_price"]),
        price=float(data["price"]),
        image=data["image"],
    )
    session.add(new_product)
    await session.commit()


async def orm_get_product(session: AsyncSession, product_id: int):
    query = (
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.category),
            selectinload(Product.seller),
        )
    )
    result = await session.execute(query)
    return result.scalar()


async def orm_get_product_by_name(session: AsyncSession, product_name: str):
    result = await session.execute(
        select(Product.id).where(Product.name == product_name)
    )
    product_id = result.scalar()
    return product_id


async def orm_get_products(session: AsyncSession, category_id: int = None):
    """
    Получить список товаров. Если передан category_id, фильтрует по категории.
    """
    query = select(Product).options(
        selectinload(Product.category),  # Предзагрузка данных категории
        selectinload(Product.seller),  # Предзагрузка данных продавца
    )
    if category_id is not None:
        query = query.where(Product.category_id == category_id)

    result = await session.execute(query)
    return result.scalars().all()


async def orm_update_product(session: AsyncSession, product_id: int, data: dict):
    query = (
        update(Product)
        .where(Product.id == product_id)
        .values(
            name=data["name"],
            description=data["description"],
            category_id=int(data["category"]),
            seller_id=int(data["seller"]),
            purchase_price=float(data["purchase_price"]),
            price=float(data["price"]),
            image=data["image"],
        )
    )
    await session.execute(query)
    await session.commit()


async def orm_update_product_availability(
    session: AsyncSession, product_id: int, is_available: bool
):
    query = (
        update(Product)
        .where(Product.id == product_id)
        .values(is_available=is_available)
    )
    await session.execute(query)
    await session.commit()


async def orm_check_product_available(session: AsyncSession, product_id: int) -> bool:
    """
    Проверяет, доступен ли продукт (is_available = True).

    :param session: Сессия базы данных.
    :param product_id: ID продукта.
    :return: True, если продукт доступен, иначе False.
    """
    query = select(Product.is_available).where(Product.id == product_id)
    result = await session.execute(query)
    is_available = result.scalar()
    return bool(is_available)


async def orm_delete_product(session: AsyncSession, product_id: int):
    query = delete(Product).where(Product.id == product_id)
    await session.execute(query)
    await session.commit()


##################### работа с пользователями #####################################


async def orm_add_user(
    session: AsyncSession,
    user_id: int,
    first_name: str | None = None,
    last_name: str | None = None,
    phone: str | None = None,
):
    query = select(Users).where(Users.user_id == user_id)
    result = await session.execute(query)
    if result.first() is None:
        session.add(
            Users(
                user_id=user_id, first_name=first_name, last_name=last_name, phone=phone
            )
        )
        await session.commit()


async def orm_get_user(session: AsyncSession, user_id: int):
    query = select(Users).where(Users.user_id == user_id)
    result = await session.execute(query)
    return result.scalar()


async def orm_update_user(session: AsyncSession, user_id: int, data: dict):
    # Получаем текущие данные пользователя
    result = await session.execute(select(Users).where(Users.user_id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise NoResultFound(f"User with id {user_id} not found")

    # Фильтруем переданные данные: оставляем только те, которые есть в модели
    update_data = {
        key: value
        for key, value in data.items()
        if hasattr(Users, key) and value is not None
    }

    if update_data:  # Обновляем только если есть данные
        query = update(Users).where(Users.user_id == user_id).values(**update_data)
        await session.execute(query)
        await session.commit()


##################### работа с продавцами #####################################


async def orm_get_sellers(session: AsyncSession):
    query = select(Seller).where()
    result = await session.execute(query)
    return result.scalars().all()


async def orm_add_seller(
    session: AsyncSession,
    name: str,
    description: str = None,
    phone: str = None,
    address: str = None,
):
    existing_seller = await session.execute(select(Seller).where(Seller.name == name))
    if existing_seller.scalar():
        return False

    new_seller = Seller(
        name=name,
        description=description,
        phone=phone,
        address=address,
    )
    session.add(new_seller)
    await session.commit()
    return True


######################## Работа с корзинами #######################################


async def orm_add_to_cart(session: AsyncSession, user_id: int, product_id: int):
    query = select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    cart = await session.execute(query)
    cart = cart.scalar()
    if cart:
        cart.quantity += 1
        await session.commit()
        return cart
    else:
        session.add(Cart(user_id=user_id, product_id=product_id, quantity=1))
        await session.commit()


async def orm_get_user_carts(session: AsyncSession, user_id):
    query = (
        select(Cart).filter(Cart.user_id == user_id).options(joinedload(Cart.product))
    )
    result = await session.execute(query)
    return result.scalars().all()


async def orm_delete_from_cart(session: AsyncSession, user_id: int, product_id: int):
    query = delete(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    await session.execute(query)
    await session.commit()


async def orm_reduce_product_in_cart(
    session: AsyncSession, user_id: int, product_id: int
):
    query = select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    cart = await session.execute(query)
    cart = cart.scalar()

    if not cart:
        return
    if cart.quantity > 1:
        cart.quantity -= 1
        await session.commit()
        return True
    else:
        await orm_delete_from_cart(session, user_id, product_id)
        await session.commit()
        return False


async def orm_get_quantity_in_cart(session: AsyncSession, user_id: int):
    query = select(func.sum(Cart.quantity)).where(Cart.user_id == user_id)
    result = await session.execute(query)
    total_quantity = result.scalar()
    return total_quantity or 0


######################## Работа с заказами #######################################


async def orm_create_order(
    session: AsyncSession, 
    user_id: int, 
    delivery_address: str, 
    phone_number: str
) -> Orders:
    # 1. Получаем товары из корзины с загруженными продуктами
    query = (
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(joinedload(Cart.product))
    )
    result = await session.execute(query)
    cart_items = result.scalars().all()

    if not cart_items:
        return None

    # 2. Считаем общую сумму
    total_price = sum(item.product.price * item.quantity for item in cart_items)

    # 3. Создаём заказ 
    new_order = Orders(
        user_id=user_id,
        delivery_address=delivery_address,
        total_price=total_price,
        status="Оформлен",
    )
    session.add(new_order)
    await session.flush()  # Получаем ID заказа

    # 4. Создаём OrderItem 
    order_item = [
        OrderItem(
            order_id=new_order.id, 
            product_id=item.product_id, 
            quantity=item.quantity
        )
        for item in cart_items
    ]
    session.add_all(order_item)

    # 5. Очищаем корзину 
    delete_query = delete(Cart).where(Cart.user_id == user_id)
    await session.execute(delete_query)

    # 6. Дополнительно загружаем связанные данные перед возвратом
    full_order = await session.execute(
        select(Orders)
        .where(Orders.id == new_order.id)
        .options(
            selectinload(Orders.user),
            selectinload(Orders.items).joinedload(OrderItem.product)
        )
    )
    full_order = full_order.scalar_one()

    await session.commit()
    return full_order



async def orm_get_orders(session: AsyncSession, status: str = None, order_id: int = None):
    query = select(Orders).options(
        selectinload(Orders.user),
        selectinload(Orders.items).selectinload(OrderItem.product),
        selectinload(Orders.deliverer),
    )
    if order_id is not None:
        query = query.where(Orders.id == order_id)
    elif status is not None:
        query = query.where(Orders.status == status)

    result = await session.execute(query)
    if order_id is not None:
        return result.scalar_one_or_none()
    return result.scalars().all()


async def orm_get_user_orders(session: AsyncSession, user_id: int):
    query = (
        select(Orders)
        .where(Orders.user_id == user_id, Orders.status.in_(["Оформлен", "В работе"]))
        .options(joinedload(Orders.items).joinedload(OrderItem.product))
    )
    result = await session.execute(query)
    return result.scalars().all()


async def orm_update_order(session: AsyncSession, order_id: int, data: dict):
    """
    Обновляет запись в таблице Order.

    :param session: Сессия базы данных.
    :param order_id: ID заказа, который нужно обновить.
    :param data: Словарь с данными для обновления.
                 Ключи должны соответствовать полям модели Order.
    :return: Обновлённый объект Order.
    """
    query = (
        update(Orders)
        .where(Orders.id == order_id)
        .values(**data)
        .execution_options(synchronize_session="fetch")
    )
    await session.execute(query)
    await session.commit()


################# работа со списком заявок ################################


async def orm_add_to_wait_list(session: AsyncSession, user_id: int, product_id: int):
    """
    Добавляет запись в таблицу WaitList.

    :param session: Сессия базы данных.
    :param user_id: ID пользователя.
    :param product_id: ID продукта.
    :return: True, если запись успешно добавлена, иначе False (если запись уже существует).
    """
    # Проверяем, существует ли уже запись в WaitList
    query = select(WaitList).where(
        WaitList.user_id == user_id, WaitList.product_id == product_id
    )
    result = await session.execute(query)
    existing_entry = result.scalar()

    if existing_entry:
        return False  # Запись уже существует

    # Создаем новую запись
    new_wait_list_entry = WaitList(user_id=user_id, product_id=product_id)
    session.add(new_wait_list_entry)
    await session.commit()
    return True


################# работа с доставкой и доставщиками################################


async def orm_get_delivery_zones(session: AsyncSession):
    """
    Возвращает продукты из таблицы Product с категорией "Доставка/Курьер"
    и названием, начинающимся со слов "Зона доставки ".
    """
    query = (
        select(Product)
        .join(Product.category)  # Соединяем с таблицей Category
        .where(
            Category.name == "Доставка/Курьер",  # Фильтруем по категории
            Product.name.like(
                "Зона доставки %"
            ),  # Название начинается с "Зона доставки "
        )
    )
    result = await session.execute(query)
    return result.scalars().all()


async def orm_add_deliverer(
    session: AsyncSession,
    telegram_id: int,
    telegram_name: str = None,
    first_name: str = None,
    last_name: str = None,
    phone: str = None,
):
    """
    Добавляет нового доставщика в таблицу Deliverer.

    :param session: Сессия базы данных.
    :param telegram_id: Уникальный Telegram ID доставщика.
    :param telegram_name: Имя пользователя в Telegram.
    :param first_name: Имя доставщика.
    :param last_name: Фамилия доставщика.
    :param phone: Телефон доставщика.
    """
    new_deliverer = Deliverer(
        telegram_id=telegram_id,
        telegram_name=telegram_name,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
    )
    session.add(new_deliverer)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise ValueError(
            f"Доставщик с telegram_id={telegram_id} уже существует."
        ) from e


async def orm_get_deliverers(session: AsyncSession, telegram_id: int = None):
    """
    Возвращает список всех доставщиков или одного доставщика по telegram_id.

    :param session: Сессия базы данных.
    :param telegram_id: Telegram ID доставщика (опционально).
    :return: Список доставщиков, один доставщик (если указан telegram_id) или False, если доставщик не найден.
    """
    query = select(Deliverer)
    if telegram_id is not None:
        query = query.where(Deliverer.telegram_id == telegram_id)

    result = await session.execute(query)
    if telegram_id is not None:
        deliverer = result.scalar_one_or_none()
        if deliverer is None:
            return False  # Возвращаем False, если доставщик не найден
        return deliverer
    return result.scalars().all()  # Возвращаем список доставщиков


async def orm_update_deliverer(session: AsyncSession, telegram_id: int, data: dict):
    """
    Обновляет данные доставщика в таблице Deliverer.

    :param session: Сессия базы данных.
    :param telegram_id: Уникальный Telegram ID доставщика.
    :param telegram_name: Имя пользователя в Telegram.
    :param first_name: Имя доставщика.
    :param last_name: Фамилия доставщика.
    :param phone: Телефон доставщика.
    """
    query = update(Deliverer).where(Deliverer.telegram_id == telegram_id).values(**data)
    await session.execute(query)
    await session.commit()


############ работа с отзывами #######################################


async def orm_add_review(
    session: AsyncSession,
    user_id: int,
    deliverer_id: int,
    order_id: int,
    rating: int,
    text: str = None,
):
    """
    Добавляет отзыв в базу данных.
    """
    new_review = DelivererReview(
        user_id=user_id,
        deliverer_id=deliverer_id,
        order_id=order_id,
        rating=rating,
        text=text,
    )
    session.add(new_review)
    await session.commit()


async def orm_update_review(session: AsyncSession, data: dict):
    """
    Обновляет отзыв в базе данных. Если отзыв не найден, выбрасывает исключение.

    :param session: Сессия базы данных.
    :param data: Словарь с данными для обновления.
                 Ключи должны соответствовать полям модели Reviews.
    """
    # Проверяем, существует ли отзыв
    query = select(DelivererReview).where(
        DelivererReview.user_id == data["user_id"],
        DelivererReview.deliverer_id == data["deliverer_id"],  # исправлено
        DelivererReview.order_id == data["order_id"],
    )
    result = await session.execute(query)
    review = result.scalar_one_or_none()

    if not review:
        raise NoResultFound("Отзыв не найден. Обновление невозможно.")

    # Выполняем обновление
    update_query = (
        update(DelivererReview)
        .where(
            DelivererReview.user_id == data["user_id"],
            DelivererReview.deliverer_id == data["deliverer_id"],
            DelivererReview.order_id == data["order_id"],
        )
        .values(**data)
        .execution_options(synchronize_session="fetch")
    )
    await session.execute(update_query)
    await session.commit()


async def orm_get_deliverer_reviews_and_update_summary(
    session: AsyncSession, deliverer_id: int
) -> float:
    """
    Извлекает все оценки доставщика, вычисляет среднее арифметическое и обновляет rating_summary.

    :param session: Сессия базы данных.
    :param deliverer_id: ID доставщика.
    :return: Среднее арифметическое рейтинга.
    """
    # Получаем все оценки доставщика
    query = select(DelivererReview.rating).where(
        DelivererReview.deliverer_id == deliverer_id
    )
    result = await session.execute(query)
    ratings = result.scalars().all()

    if not ratings:
        raise ValueError(f"Для доставщика с ID {deliverer_id} нет отзывов.")

    # Вычисляем среднее арифметическое
    average_rating = sum(ratings) / len(ratings)

    # Обновляем поле rating_summary в таблице Deliverer
    update_query = (
        update(Deliverer)
        .where(Deliverer.id == deliverer_id)
        .values(rating_summary=average_rating)
        .execution_options(synchronize_session="fetch")
    )
    await session.execute(update_query)
    await session.commit()

    return average_rating
