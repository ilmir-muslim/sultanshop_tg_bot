import logging
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InputMediaPhoto
from aiogram import F, Bot, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import (
    check_delivery_is_available,
    orm_add_to_cart,
    orm_delete_from_cart,
    orm_get_banner,
    orm_get_categories,
    orm_get_delivery_zones,
    orm_get_pickup_points,
    orm_get_products,
    orm_get_quantity_in_cart,
    orm_get_user_carts,
    orm_reduce_product_in_cart,
    orm_update_orders_banner_description,
)
from kbds.inline import (
    # create_order_menu_btns,
    get_callback_btns,
    get_products_btns,
    get_user_cart,
    get_user_catalog_btns,
    get_user_main_btns,
)

from utils.json_operations import save_sharing_data
from utils.paginator import Paginator


menu_progressing_router = Router()


class SharedContexMenu:
    def __init__(self, callback, session, bot):
        self.session = session
        self.bot = bot
        self.callback = callback

    async def return_to_cart(self, user_id):
        cart = await orm_get_user_carts(self.session, user_id)
        if not cart:
            banner = await orm_get_banner(self.session, "cart")
            media = InputMediaPhoto(
                media=banner.image, caption=f"<strong>{banner.description}</strong>"
            )
            reply_markup = get_user_cart(
                level=3,
                page=None,
                pagination_btns=None,
                product_id=None,
            )
        else:
            media, reply_markup = await carts(
                session=self.session,
                level=3,
                menu_name="cart",
                page=1,
                user_id=user_id,
                product_id=cart[0].product.id,
            )
        await self.callback.message.edit_media(media=media, reply_markup=reply_markup)


async def main_menu(session, level, menu_name, user_id=None):
    banner = await orm_get_banner(session, menu_name)
    image = InputMediaPhoto(media=banner.image, caption=banner.description)
    quantity = await orm_get_quantity_in_cart(session, user_id=user_id)
    delivery_is_available = await check_delivery_is_available(session)

    kbds = get_user_main_btns(
        level=level,
        quantity=quantity,
        delivery_is_available=delivery_is_available,
    )

    return image, kbds


async def catalog(session, level, menu_name, user_id=None):
    banner = await orm_get_banner(session, menu_name)
    image = InputMediaPhoto(media=banner.image, caption=banner.description)
    delivery_is_available = await check_delivery_is_available(session)
    categories = await orm_get_categories(session)
    quantity = await orm_get_quantity_in_cart(session, user_id=user_id)
    kbds = get_user_catalog_btns(
        level=level,
        categories=categories,
        quantity=quantity,
        delivery_is_available=delivery_is_available,
    )

    return image, kbds


def pages(paginator: Paginator):
    btns = dict()
    if paginator.has_previous():
        btns["◀ Пред."] = "previous"

    if paginator.has_next():
        btns["След. ▶"] = "next"

    return btns


async def products(session, level, category, page, user_id=None):
    products = await orm_get_products(session, category_id=category)
    products = [
        product
        for product in products
        if not (
            product.category.name == "Доставка/Курьер" and product.is_available is False
        )
    ]

    paginator = Paginator(products, page=page)
    product = paginator.get_page()[0]
    is_available = product.is_available

    image = InputMediaPhoto(
        media=product.image,
        caption=f"<strong>{product.name}</strong>\n"
        f"{product.description}\n"
        f"<strong>Стоимость: {round(product.price, 2)}</strong>\n"
        f"<strong>Товар {paginator.page} из {paginator.pages}</strong>\n"
        f"<strong>Категория: {product.category.name}</strong>\n"
        f"<strong>{"есть " if is_available else "нет "}в наличии</strong>\n",
        parse_mode="HTML",
    )

    pagination_btns = pages(paginator)

    quantity = await orm_get_quantity_in_cart(session, user_id=user_id)
    kbds = get_products_btns(
        level=level,
        category=category,
        page=page,
        pagination_btns=pagination_btns,
        product_id=product.id,
        quantity=quantity,
        is_available=is_available,
    )

    return image, kbds


async def carts(session, level, menu_name, page, user_id, product_id):
    if menu_name == "delete":
        await orm_delete_from_cart(session, user_id, product_id)
        if page > 1:
            page -= 1
    elif menu_name == "decrement":
        is_cart = await orm_reduce_product_in_cart(session, user_id, product_id)
        if page > 1 and not is_cart:
            page -= 1
    elif menu_name == "increment":
        await orm_add_to_cart(session, user_id, product_id)

    carts = await orm_get_user_carts(session, user_id)

    if not carts:
        banner = await orm_get_banner(session, "cart")
        image = InputMediaPhoto(
            media=banner.image, caption=f"<strong>{banner.description}</strong>"
        )

        kbds = get_user_cart(
            level=level,
            page=None,
            pagination_btns=None,
            product_id=None,
        )

    else:
        paginator = Paginator(carts, page=page)

        cart = paginator.get_page()[0]

        cart_price = round(cart.quantity * cart.product.price, 2)
        total_price = round(
            sum(cart.quantity * cart.product.price for cart in carts), 2
        )
        print(f"DEBUG: Общая сумма: {total_price}")
        # Составляем табличку содержимого корзины
        cart_summary_lines = [
            "Товар      | Кол | Цена   | Сумма",
            "----------------------------------",
        ]

    for c in carts:
        name = c.product.name[:10].ljust(10)  # Название товара
        qty = str(c.quantity).rjust(3)  # Количество
        price_per_unit = f"{c.product.price:.2f}".rjust(6)  # Цена за штуку
        total = f"{c.quantity * c.product.price:.2f}".rjust(5)  # Сумма
        cart_summary_lines.append(f"{name} | {qty} | {price_per_unit} | {total}")

        cart_summary_text = "\n".join(cart_summary_lines)

        # Собираем caption
        caption = (
            f"<strong>{cart.product.name}</strong>\n"
            f"{cart.product.price}£ x {cart.quantity} = {cart_price}£\n"
            f"Товар {paginator.page} из {paginator.pages} в корзине.\n"
            f"📦 <u>Содержимое корзины:</u>\n"
            f"<pre>{cart_summary_text}</pre>\n"
            f"💰 <strong>Общая стоимость:</strong> {total_price}£"
        )

        # Если caption слишком длинный — урезаем таблицу
        if len(caption) > 1024:
            cart_summary_text = "\n".join(cart_summary_lines[:5] + ["...и др."])
            caption = (
                f"<strong>{cart.product.name}</strong>\n"
                f"{cart.product.price}£ x {cart.quantity} = {cart_price}£\n"
                f"Товар {paginator.page} из {paginator.pages} в корзине.\n"
                f"📦 <u>Содержимое корзины:</u>\n"
                f"<pre>{cart_summary_text}</pre>\n"
                f"💰 <strong>Общая стоимость:</strong> {total_price}£"
            )

        # Создаём image
        image = InputMediaPhoto(
            media=cart.product.image, caption=caption, parse_mode="HTML"
        )

        pagination_btns = pages(paginator)

        kbds = get_user_cart(
            level=level,
            page=page,
            pagination_btns=pagination_btns,
            product_id=cart.product.id,
        )

    return image, kbds


async def orders(session: AsyncSession, level: int, menu_name: str, user_id: int):
    # Создаём описание заказов в таблице Banner
    await orm_update_orders_banner_description(session, user_id)
    logging.info(f"Обновлено описание баннера с заказами для пользователя {user_id}")

    # Получаем баннер с обновлённым описанием заказов
    banner = await orm_get_banner(session, menu_name)

    caption = banner.description

    # Ограничиваем длину текста, если он слишком длинный
    if len(caption) > 1024:
        caption = caption[:1020] + "...\n(Слишком много данных для отображения)"

    # Формируем изображение и кнопки
    image = InputMediaPhoto(media=banner.image, caption=caption, parse_mode="HTML")
    delivery_is_available = await check_delivery_is_available(session)
    quantity = await orm_get_quantity_in_cart(session, user_id=user_id)
    kbds = get_user_main_btns(
        level=level,
        quantity=quantity,
        delivery_is_available=delivery_is_available,
    )

    return image, kbds


async def shipping(session: AsyncSession, level: int, menu_name: str, user_id: int):
    # Получаем баннер с обновлённым описанием доставки
    banner = await orm_get_banner(session, menu_name)

    caption = banner.description
    # Формируем изображение и кнопки
    image = InputMediaPhoto(media=banner.image, caption=caption, parse_mode="HTML")
    delivery_zone = await orm_get_delivery_zones(session)
    btns = {
        delivery_zone.name: f"delivery_zone_{delivery_zone.id}"
        for delivery_zone in delivery_zone
    }
    logging.info(f"Получены зоны доставки для пользователя {user_id}: {btns}")
    btns["Назад"] = "main_menu"
    btns["Самовывоз"] = "self_pickup"
    kbds = get_callback_btns(btns=btns)
    return image, kbds


async def pickup(session: AsyncSession, level: int, menu_name: str):
    banner = await orm_get_banner(session, menu_name)
    caption = banner.description
    image = InputMediaPhoto(media=banner.image, caption=caption, parse_mode="HTML")
    pickup_points = await orm_get_pickup_points(session)
    btns = {
        point.district: f"pickup_point_{point.id}"
        for point in pickup_points
        if point.district
    }
    btns["Назад"] = "main_menu"
    kbds = get_callback_btns(btns=btns)

    return image, kbds


@menu_progressing_router.callback_query(F.data.startswith("delivery_zone_"))
async def add_delivery_to_cart(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
):
    delivery_zone_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    await orm_add_to_cart(session, user_id, delivery_zone_id)
    await callback.answer("Доставка добавлена в корзину.")
    context = SharedContexMenu(callback, session, bot)
    await context.return_to_cart(user_id)


@menu_progressing_router.callback_query(F.data == "self_pickup")
async def add_self_pickup_to_adress(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
):
    user_id = callback.from_user.id
    update_order_data = {str(user_id): {"delivery_address": "Самовывоз"}}
    save_sharing_data(update_order_data)
    await callback.answer("Выбран самовывоз.")
    context = SharedContexMenu(callback, session, bot)
    await context.return_to_cart(user_id)


@menu_progressing_router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    image, kbds = await get_menu_content(
        session=session,
        level=0,  # Уровень главного меню
        menu_name="main",
        user_id=user_id,
    )
    await callback.message.edit_media(media=image, reply_markup=kbds)
    await callback.answer()  # Закрываем уведомление


async def get_menu_content(
    session: AsyncSession,
    level: int,
    menu_name: str,
    category: int | None = None,
    page: int | None = None,
    product_id: int | None = None,
    user_id: int | None = None,
):
    if level == 0:
        return await main_menu(session, level, menu_name, user_id)
    elif level == 1:
        return await catalog(session, level, menu_name, user_id)
    elif level == 2:
        return await products(session, level, category, page, user_id)
    elif level == 3:
        return await carts(session, level, menu_name, page, user_id, product_id)
    elif level == 4:
        return await orders(session, level, menu_name, user_id)
    elif level == 5:
        return await shipping(session, level, menu_name, user_id)
    elif level == 6:
        return await pickup(session, level, menu_name)
