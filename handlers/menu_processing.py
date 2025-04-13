from aiogram.types import InlineKeyboardButton, InputMediaPhoto
from aiogram import F, Router, types
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import (
    orm_add_to_cart,
    orm_delete_from_cart,
    orm_get_banner,
    orm_get_categories,
    orm_get_products,
    orm_get_user_carts,
    orm_reduce_product_in_cart,
)
from kbds.inline import (
    # create_order_menu_btns,
    get_callback_btns,
    get_products_btns,
    get_user_cart,
    get_user_catalog_btns,
    get_user_main_btns,
)

from utils.paginator import Paginator


menu_progressing_router = Router()


async def main_menu(session, level, menu_name):
    banner = await orm_get_banner(session, menu_name)
    image = InputMediaPhoto(media=banner.image, caption=banner.description)

    kbds = get_user_main_btns(level=level)

    return image, kbds


async def catalog(session, level, menu_name):
    banner = await orm_get_banner(session, menu_name)
    image = InputMediaPhoto(media=banner.image, caption=banner.description)

    categories = await orm_get_categories(session)
    kbds = get_user_catalog_btns(level=level, categories=categories)

    return image, kbds


def pages(paginator: Paginator):
    btns = dict()
    if paginator.has_previous():
        btns["◀ Пред."] = "previous"

    if paginator.has_next():
        btns["След. ▶"] = "next"

    return btns


async def products(session, level, category, page):
    products = await orm_get_products(session, category_id=category)

    paginator = Paginator(products, page=page)
    product = paginator.get_page()[0]

    image = InputMediaPhoto(
        media=product.image,
        caption=f"<strong>{product.name}</strong>\n"
        f"{product.description}\n"
        f"Стоимость: {round(product.price, 2)}\n"
        f"<strong>Товар {paginator.page} из {paginator.pages}</strong>\n"
        f"<strong>Категория: {product.category.name}</strong>\n"
        f"<strong>Продавец: {product.seller.name}</strong>\n"
        f"<strong>Количество на складе: {product.quantity}</strong>\n",
        parse_mode="HTML",
    )

    pagination_btns = pages(paginator)

    kbds = get_products_btns(
        level=level,
        category=category,
        page=page,
        pagination_btns=pagination_btns,
        product_id=product.id,
    )

    kbds.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text="📋 Показать все",
                callback_data=f"show_all_in_category_{category}",  # Простая строка с категорией
            )
        ]
    )
    return image, kbds


@menu_progressing_router.callback_query(F.data.startswith("show_all_in_category_"))
async def show_all_products(callback: CallbackQuery, session: AsyncSession):
    category_id = int(callback.data.split("_")[-1])
    products = await orm_get_products(session, category_id=category_id)

    for product in products:
        # Используем get_products_btns для создания клавиатуры
        reply_markup = get_products_btns(
            level=2,
            category=category_id,
            page=1,
            pagination_btns={},
            product_id=product.id,
            sizes=(2, 1),
        )

        await callback.message.answer_photo(
            product.image,
            caption=f"<strong>{product.name}</strong>\n"
            f"{product.description}\n"
            f"Стоимость: {round(product.price, 2)}\n"
            f"<strong>Категория: {product.category.name}</strong>\n"
            f"<strong>Продавец: {product.seller.name}</strong>\n"
            f"<strong>Количество на складе: {product.quantity}</strong>\n",
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

    await callback.answer("Показаны все товары в категории.")


async def carts(session, level, menu_name, page, user_id, product_id):
    if menu_name == "delete":
        await orm_delete_from_cart(session, user_id, product_id)
        if page > 1:
            page -= 1
    elif menu_name == "decrement":
        is_cart = await orm_reduce_product_in_cart(session, user_id, product_id)
        if page > 1 and not is_cart:
            page-= 1
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
        # Составляем табличку содержимого корзины
        cart_summary_lines = [
            "Товар         Кол-во   Сумма",
            "-----------------------------",
        ]
        for c in carts:
            name = c.product.name[:12].ljust(12)
            qty = f"x{c.quantity}".ljust(7)
            price = f"{round(c.product.price * c.quantity, 2)}£"
            cart_summary_lines.append(f"{name}{qty}{price}")

        cart_summary_text = "\n".join(cart_summary_lines)

        # Собираем caption
        caption = (
            f"<strong>{cart.product.name}</strong>\n"
            f"{cart.product.price}£ x {cart.quantity} = {cart_price}£\n"
            f"Товар {paginator.page} из {paginator.pages} в корзине.\n\n"
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
                f"Товар {paginator.page} из {paginator.pages} в корзине.\n\n"
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
        return await main_menu(session, level, menu_name)
    elif level == 1:
        return await catalog(session, level, menu_name)
    elif level == 2:
        return await products(session, level, category, page)
    elif level == 3:
        return await carts(session, level, menu_name, page, user_id, product_id)
 