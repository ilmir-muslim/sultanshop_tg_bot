from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm import joinedload, selectinload
from yarl import Query

from database.models import (
    Banner,
    Cart,
    Category,
    Order,
    OrderItem,
    Product,
    Seller,
    User,
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
            Order.id,
            Order.delivery_address,
            Order.status,
            Order.total_price,
            OrderItem.quantity,
            Product.name,
            Product.price,
        )
        .join(Order.items)  # Соединяем с таблицей OrderItem
        .join(OrderItem.product)  # Соединяем с таблицей Product
        .where(Order.user_id == user_id, Order.status.in_(["Оформлен", "в работе"]))
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
                current_order_id = row.id
                orders_text.append(
                    f"🆔 Заказ #{row.id}\n"
                    f"📍 Адрес доставки: {row.delivery_address}\n"
                    f"📦 Статус: {row.status}\n"
                    f"💰 Сумма: {row.total_price}£\n"
                    "Товары:"
                )
            # Добавляем информацию о товаре в заказе
            orders_text.append(
                f"- {row.name} x {row.quantity} ({row.price}£ за шт.)"
            )
        orders_text.append("-----------------------------------")
        description = "\n".join(orders_text)

    # Ограничиваем длину текста, если он слишком длинный
    if len(description) > 1024:
        description = description[:1020] + "...\n(Слишком много данных для отображения)"

    # Обновляем поле description в записи с именем 'orders' в таблице Banner
    update_query = (
        update(Banner)
        .where(Banner.name == "orders")
        .values(description=description)
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


async def orm_update_product(session: AsyncSession, product_id: int, data):
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
            is_available=data["is_available"],
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
    query = select(User).where(User.user_id == user_id)
    result = await session.execute(query)
    if result.first() is None:
        session.add(
            User(
                user_id=user_id, first_name=first_name, last_name=last_name, phone=phone
            )
        )
        await session.commit()


async def orm_get_user(session: AsyncSession, user_id: int):
    query = select(User).where(User.user_id == user_id)
    result = await session.execute(query)
    return result.scalar()


async def orm_update_user(session: AsyncSession, user_id: int, data: dict):
    # Получаем текущие данные пользователя
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise NoResultFound(f"User with id {user_id} not found")

    # Фильтруем переданные данные: оставляем только те, которые есть в модели
    update_data = {
        key: value
        for key, value in data.items()
        if hasattr(User, key) and value is not None
    }

    if update_data:  # Обновляем только если есть данные
        query = update(User).where(User.user_id == user_id).values(**update_data)
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
    session: AsyncSession, user_id: int, delivery_address: str, phone_number: str
):
    # 1. Получаем товары из корзины
    query = (
        select(Cart).where(Cart.user_id == user_id).options(joinedload(Cart.product))
    )
    result = await session.execute(query)
    cart_items = result.scalars().all()

    if not cart_items:
        return None

    # 2. Считаем общую сумму
    total_price = sum(item.product.price * item.quantity for item in cart_items)

    # 3. Создаём заказ
    new_order = Order(
        user_id=user_id,
        delivery_address=delivery_address,
        total_price=total_price,
        status="Оформлен",
    )
    session.add(new_order)
    await session.flush()  # Получаем ID заказа

    # 4. Создаём OrderItem для каждого товара
    order_items = [
        OrderItem(
            order_id=new_order.id,
            product_id=item.product_id,
            quantity=item.quantity
        )
        for item in cart_items
    ]
    session.add_all(order_items)

    # 5. Очищаем корзину
    delete_query = delete(Cart).where(Cart.user_id == user_id)
    await session.execute(delete_query)
    
    await session.commit()
    return new_order


async def orm_get_orders(session: AsyncSession, status: str = None):
    query = (
        select(Order)
        .where(Order.status == status)
        .options(
            selectinload(Order.user),  # Предзагрузка данных пользователя
            selectinload(Order.items).selectinload(
                OrderItem.product
            ),  # Предзагрузка товаров
        )
    )
    result = await session.execute(query)
    return result.scalars().all()


async def orm_get_user_orders(session: AsyncSession, user_id: int):
    query = (
        select(Order)
        .where(Order.user_id == user_id, Order.status.in_(["Оформлен", "В работе"]))
        .options(joinedload(Order.items).joinedload(OrderItem.product))
    )
    result = await session.execute(query)
    return result.scalars().all()


async def orm_update_order_status(session: AsyncSession, order_id: int, status: str):
    query = update(Order).where(Order.id == order_id).values(status=status)
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
