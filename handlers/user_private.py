import logging
from venv import logger
from aiogram import F, Bot, types, Router
from aiogram.filters import CommandObject, CommandStart


from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import (
    check_delivery_is_available,
    orm_add_to_cart,
    orm_add_to_wait_list,
    orm_add_user,
    orm_create_order,
    orm_get_deliverers,
    orm_get_pickup_points,
    orm_get_user,
    orm_get_user_carts,
    orm_update_user,
)

from filters.chat_types import ChatTypeFilter
from handlers.menu_processing import get_menu_content, main_menu, shipping
from kbds.inline import (
    MenuCallBack,
    inline_buttons_kb,
    phone_confirm_kb,
    address_confirm_kb,
)
from utils.json_operations import (
    load_sharing_data,
    save_sharing_data,
)


class OrderState(StatesGroup):
    waiting_for_address = State()
    waiting_for_phone_number = State()


class SharedContextUser:
    def __init__(self, session, bot):
        self.session = session
        self.bot = bot

    async def order_details_text(self, order, state: FSMContext) -> dict:
        """формирует текст для сообщения с деталями заказа."""
        delivery_info = ""
        show_pickup = False

        # Проверяем адрес доставки
        if order.delivery_address and order.delivery_address.strip().lower() != "самовывоз":
            delivery_info = f"📍 Адрес доставки: {order.delivery_address}\n"
        else:
            # Если FSM передан — пробуем взять пункт выдачи
            pickup_point_info = ""
            if state is not None:
                data = await state.get_data()
                pickup_point_id = data.get("pickup_point_id")

                if pickup_point_id:
                    pickup_point = await orm_get_pickup_points(self.session, pickup_point_id)
                    if pickup_point:
                        pickup_point_info = (
                            f"🏬 Пункт выдачи: {pickup_point.district},{pickup_point.address}\n"
                            f"Google карты: {pickup_point.google_map_location}"
                        )
                        # Сохраняем данные о пункте выдачи в файл
                        save_sharing_data({
                            str(order.user.user_id): {
                                "pickup_point_id": pickup_point.id,
                                "pickup_point_district": pickup_point.district,
                                "pickup_point_address": pickup_point.address,
                                "pickup_point_google_map_location": pickup_point.google_map_location,
                            }
                        })
            delivery_info = pickup_point_info or "🏬 Пункт выдачи: не выбран\n"
            
        order_details = (
            f"📦 Новый заказ №{order.id}\n"
            f"👤 Покупатель: {order.user.first_name} {order.user.last_name}\n"
            f"📞 Телефон: {order.user.phone or 'Телефон не указан'}\n\n"
            f"{delivery_info}\n"
            f"💰 Общая стоимость: {order.total_price} £.\n"
            f"📋 Статус: {order.status}\n"
            f"🕒 Дата создания: {order.created.strftime('%d.%m.%Y %H:%M')}\n"
        )
        if order.items:
            order_details += "\n🛒 Товары в заказе:\n"
            for idx, item in enumerate(order.items, start=1):
                order_details += f"{idx}. {item.product.name} - {item.quantity} шт. x {item.product.price} £ = {item.quantity * item.product.price} £\n"

        order_details_for_buyer = (
            f"📦 Новый заказ №{order.id}\n\n"
            f"📞 Телефон оператора: +201026282854 \n"
            f"💬 Телеграм: @Vmisreabusultan \n\n"
            f"{delivery_info}\n"
            f"💰 Общая стоимость: {order.total_price} £.\n"
            f"📋 Статус: {order.status}\n"
            f"🕒 Дата создания: {order.created.strftime('%d.%m.%Y %H:%M')}\n"
        )

        # Добавляем товары в заказ
        if order.items:
            order_details_for_buyer += "\n🛒 Товары в заказе:\n"
            for idx, item in enumerate(order.items, start=1):
                order_details_for_buyer += f"{idx}. {item.product.name} - {item.quantity} шт. x {item.product.price} £ = {item.quantity * item.product.price} £\n"
        return {
            "order_details": order_details,
            "order_details_for_buyer": order_details_for_buyer,
        }

    async def send_message_to_deliverers(self, order, state: FSMContext) -> types.Message:
        """Отправляет сообщение с деталями заказа доставщику."""
        deliverers = await orm_get_deliverers(session=self.session)

        logger.debug(f"deliverers raw: {deliverers}")

        my_deliverer_list = [
            deliverer.telegram_id for deliverer in deliverers if deliverer.is_active
        ]
        logger.debug(f"my_deliverer_list {my_deliverer_list}")

        order_details_dict = await self.order_details_text(order=order, state=state)
        order_text = order_details_dict["order_details"]

        for deliverer in my_deliverer_list:
            try:
                await self.bot.send_message(
                    deliverer,
                    order_text,
                    reply_markup=inline_buttons_kb(
                        {"Принять заказ": {"callback_data": f"accept_order_{order.id}"}}
                    ),
                )
            except Exception as e:
                logger.exception(f"Ошибка при отправке доставщику {deliverer}")

    async def send_message_to_admins(self, order, state) -> types.Message:
        """Отправляет сообщение с деталями заказа администратору."""

        admin_list = self.bot.my_admins_list
        logger.debug(f"admin_list raw: {admin_list}")

        order_details_dict = await self.order_details_text(order=order, state=state)
        order_text = order_details_dict["order_details"]

        for admin in admin_list:
            try:
                await self.bot.send_message(
                    admin,
                    order_text,
                    reply_markup=inline_buttons_kb(
                        {"В работе": {"callback_data": f"admin_accept_order_{order.id}"}},
                    ),
                )
            except Exception as e:
                logger.exception(f"Ошибка при отправке администратору {admin}")

    async def finish_order(self, user, state, delivery_address: str):
        data = await state.get_data()
        phone_number = data.get("phone_number")
        user_id = user.id

        await state.update_data(delivery_address=delivery_address)

        await orm_update_user(
            self.session,
            user_id=user_id,
            data={
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": phone_number,
                "address": delivery_address,
            },
        )

        new_order = await orm_create_order(
            self.session, user_id, delivery_address, phone_number
        )
        logger.debug(f"Новый заказ: {new_order}")
        order_details_dict = await self.order_details_text(order=new_order, state=state)
        order_details_for_buyer = order_details_dict["order_details_for_buyer"]

        if delivery_address.strip().lower() != "самовывоз":
            await self.send_message_to_deliverers(new_order, state=state)

        await self.send_message_to_admins(new_order, state=state)
        await self.bot.send_message(user_id, order_details_for_buyer)
        await self.bot.send_message(user_id, "Спасибо за ваш заказ!")
        media, reply_markup = await main_menu(
            self.session, level=0, menu_name="main", user_id=user_id
        )
        await self.bot.send_photo(
            user_id, photo=media.media, caption=media.caption, reply_markup=reply_markup
        )
        await state.clear()

    async def check_delivery_is_avalible(self, user_id):
        delivery_is_available = await check_delivery_is_available(self.session)
        if not delivery_is_available:
            update_order_data = {str(user_id): {"delivery_address": f"Самовывоз"}}
            save_sharing_data(update_order_data)


user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(["private"]))


@user_private_router.message(CommandStart())
async def start_cmd(
    message: types.Message, session: AsyncSession, command: CommandObject, bot: Bot
):
    try:
        logging.info(f"Start command message: {message.text}")
        logging.info(f"Start command args: {command.args}")
        args = command.args  # безопасно брать из объекта команды
        if args and args.startswith("add_to_cart_"):
            try:
                product_id = int(args.split("_")[-1])
            except (IndexError, ValueError):
                await message.answer("Некорректный параметр товара.")
                return

            user = message.from_user

            # Добавляем пользователя и товар в корзину
            await orm_add_user(
                session,
                user_id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                phone=None,
            )

            await orm_add_to_cart(session, user_id=user.id, product_id=product_id)
            await message.answer("Товар добавлен в корзину")

            user_id = message.from_user.id
            media, reply_markup = await get_menu_content(
                session, level=0, menu_name="main", user_id=user_id
            )
            await message.answer_photo(
                media.media, caption=media.caption, reply_markup=reply_markup
            )

        else:
            user_id = message.from_user.id
            media, reply_markup = await get_menu_content(
                session, level=0, menu_name="main", user_id=user_id
            )
            await message.answer_photo(
                media.media, caption=media.caption, reply_markup=reply_markup
            )

    except Exception as e:
        logging.error(f"Ошибка в start_cmd: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")


async def add_to_cart(
    callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession
):
    user = callback.from_user
    await orm_add_user(
        session,
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=None,
    )
    await orm_add_to_cart(session, user_id=user.id, product_id=callback_data.product_id)
    await callback.answer("Товар добавлен в корзину.")


async def add_to_waitlist(
    callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession
):
    user = callback.from_user
    # Добавляем пользователя в список ожидания
    success_added = await orm_add_to_wait_list(
        session, user_id=user.id, product_id=callback_data.product_id
    )
    if success_added:
        await callback.answer("Вам придет оповещение, когда товар появится в наличии.")
    else:
        await callback.answer("Вы уже оставили заявку на этот товар")


@user_private_router.callback_query(MenuCallBack.filter())
async def user_menu(
    callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession
):
    if callback_data.menu_name == "add_to_cart":
        await add_to_cart(callback, callback_data, session)

        return

    if callback_data.menu_name == "add_to_waitlist":
        await add_to_waitlist(callback, callback_data, session)
        return

    media, reply_markup = await get_menu_content(
        session,
        level=callback_data.level,
        menu_name=callback_data.menu_name,
        category=callback_data.category,
        page=callback_data.page,
        product_id=callback_data.product_id,
        user_id=callback.from_user.id,
    )

    await callback.message.edit_media(media=media, reply_markup=reply_markup)
    await callback.answer()


# 1. Начало оформления заказа
@user_private_router.callback_query(F.data == "make_order")
async def make_order(
    callback: types.CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
):
    user_id = callback.from_user.id
    context = SharedContextUser(session, bot)
    await context.check_delivery_is_avalible(user_id)
    cart = await orm_get_user_carts(session, user_id=user_id)
    has_delivery_zone = any(
        item.product.name.startswith("Зона доставки") for item in cart
    )
    try:
        has_delivery_address = load_sharing_data(user_id).get("delivery_address")
    except FileNotFoundError:
        has_delivery_address = False
    except Exception as e:
        logging.error(f"Ошибка при загрузке данных: {e}")
        has_delivery_address = False
    logger.debug(f"has_delivery_address: {has_delivery_address}")

    if has_delivery_address == "Самовывоз":
        media, reply_markup = await get_menu_content(
            session=session,
            level=6,
            menu_name="pickup",
        )
        await bot.send_photo(
            user_id,
            photo=media.media,
            caption=media.caption,
            reply_markup=reply_markup,
        )
        return

    elif not has_delivery_zone and not has_delivery_address:
        media, reply_markup = await shipping(
            session=session, level=5, menu_name="shipping", user_id=user_id
        )
        await callback.answer("Выберите способ получения товара")
        await bot.send_photo(
            user_id,
            photo=media.media,
            caption=media.caption,
            reply_markup=reply_markup,
        )
        return

    user = await orm_get_user(
        session, user_id
    )  # Проверяем, есть ли пользователь в базе

    if user and user.phone:
        # Если пользователь есть, предлагаем подтвердить номер

        await callback.message.answer(
            f"Ваш номер телефона: {user.phone}\nВы хотите его использовать?",
            reply_markup=phone_confirm_kb,
        )
    else:
        # Запрашиваем номер
        await callback.message.answer(
            "Введите номер телефона (например, +201234567890):"
        )

    await state.set_state(OrderState.waiting_for_phone_number)


@user_private_router.callback_query(F.data.startswith("pickup_point_"))
async def select_pickup_point(
    callback: types.CallbackQuery, session: AsyncSession, state: FSMContext
):
    pickup_point_id = int(callback.data.split("_")[-1])
    await state.update_data(pickup_point_id=pickup_point_id)
    user_id = callback.from_user.id
    user = await orm_get_user(session, user_id)
    if user and user.phone:
        await callback.message.answer(
            f"Ваш номер телефона: {user.phone}\nВы хотите его использовать?",
            reply_markup=phone_confirm_kb,
        )
    else:
        await callback.message.answer(
            "Введите номер телефона (например, +201234567890):"
        )
    await state.set_state(OrderState.waiting_for_phone_number)


@user_private_router.callback_query(F.data == "orders")
async def user_orders(callback: types.CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id

    # Вызываем функцию orders для получения списка заказов
    media, reply_markup = await get_menu_content(
        session=session,
        level=4,  # Уровень меню для заказов
        menu_name="orders",
        user_id=user_id,
    )

    # Отправляем пользователю список заказов
    await callback.message.edit_media(media=media, reply_markup=reply_markup)
    await callback.answer()


# 2. Подтверждение номера телефона или ввод нового
@user_private_router.callback_query(F.data == "confirm_phone")
async def confirm_phone(
    callback: types.CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
):
    user = await orm_get_user(session, callback.from_user.id)
    await state.update_data(phone_number=user.phone)  # Записываем телефон в стейт
    try:
        self_pickup = load_sharing_data(callback.from_user.id)
    except FileNotFoundError:
        self_pickup = False
    except Exception as e:
        logging.error(f"Ошибка при загрузке данных: {e}")
        self_pickup = False

    if self_pickup:
        context = SharedContextUser(session, bot)
        await context.finish_order(
            user=callback.from_user,
            state=state,
            delivery_address="самовывоз",
        )

    else:
        if user.address and user.address.lower() != "самовывоз":

            await callback.message.answer(
                f"Ваш адрес: {user.address}\nВы хотите его использовать?",
                reply_markup=address_confirm_kb,
            )
            await state.set_state(OrderState.waiting_for_address)
        else:
            await callback.message.answer("Введите адрес доставки:")

            await state.set_state(OrderState.waiting_for_address)


@user_private_router.callback_query(F.data == "change_phone")
async def change_phone(callback: types.CallbackQuery):
    await callback.message.answer("Введите новый номер телефона:")


@user_private_router.message(OrderState.waiting_for_phone_number)
async def process_phone_number(message: types.Message, state: FSMContext):
    phone_number = message.text.strip()

    if not phone_number.startswith("+") or not phone_number[1:].isdigit():
        await message.answer("Некорректный номер. Введите в формате +201234567890")
        return

    await state.update_data(phone_number=phone_number)

    await message.answer("Введите адрес доставки:")
    await state.set_state(OrderState.waiting_for_address)


# 3. Подтверждение адреса или ввод нового
@user_private_router.callback_query(F.data == "confirm_address")
async def confirm_address(
    callback: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
):
    user = await orm_get_user(session, callback.from_user.id)
    delivery_address = user.address
    context = SharedContextUser(session, bot)
    await context.finish_order(
        user=callback.from_user,
        state=state,
        delivery_address=delivery_address,
    )


@user_private_router.callback_query(F.data == "change_address")
async def change_address(callback: types.CallbackQuery):
    await callback.message.answer('Введите новый адрес"):')


@user_private_router.message(OrderState.waiting_for_address)
async def process_address(
    message: types.Message, state: FSMContext, session: AsyncSession, bot: Bot
):
    context = SharedContextUser(session, bot)
    await context.finish_order(
        user=message.from_user,
        state=state,
        delivery_address=message.text.strip(),
    )
