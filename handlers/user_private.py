from calendar import c
import logging
from aiogram import F, Bot, types, Router
from aiogram.filters import CommandObject, CommandStart


from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.payload import decode_payload
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import (
    orm_add_to_cart,
    orm_add_to_wait_list,
    orm_add_user,
    orm_create_order,
    orm_get_user,
    orm_update_user,
)

from filters.chat_types import ChatTypeFilter
from handlers.menu_processing import get_menu_content, main_menu
from kbds.inline import (
    MenuCallBack,
    one_button_kb,
    phone_confirm_kb,
    address_confirm_kb,
)


class OrderState(StatesGroup):
    waiting_for_address = State()
    waiting_for_phone_number = State()


user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(["private"]))


@user_private_router.message(CommandStart())
async def start_cmd(
    message: types.Message, session: AsyncSession, command: CommandObject
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
    callback: types.CallbackQuery, state: FSMContext, session: AsyncSession
):
    user_id = callback.from_user.id
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
    callback: types.CallbackQuery, state: FSMContext, session: AsyncSession
):
    user = await orm_get_user(session, callback.from_user.id)
    await state.update_data(phone_number=user.phone)  # Записываем телефон в стейт

    if user.address:
        await callback.message.answer(
            f"Ваш адрес: {user.address}\nВы хотите его использовать?",
            reply_markup=address_confirm_kb,
        )
        await state.set_state(OrderState.waiting_for_address)
    else:
        await callback.message.answer(
            'Введите адрес доставки или напишите "самовывоз":'
        )
        await state.set_state(OrderState.waiting_for_address)


@user_private_router.callback_query(F.data == "change_phone")
async def change_phone(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новый номер телефона:")


@user_private_router.message(OrderState.waiting_for_phone_number)
async def process_phone_number(message: types.Message, state: FSMContext):
    phone_number = message.text.strip()

    if not phone_number.startswith("+") or not phone_number[1:].isdigit():
        await message.answer("Некорректный номер. Введите в формате +201234567890")
        return

    await state.update_data(phone_number=phone_number)

    await message.answer('Введите адрес доставки или напишите "самовывоз":')
    await state.set_state(OrderState.waiting_for_address)


# 3. Подтверждение адреса или ввод нового
@user_private_router.callback_query(F.data == "confirm_address")
async def confirm_address(
    callback: types.CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
):
    data = await state.get_data()
    phone_number = data.get("phone_number")

    user = await orm_get_user(session, callback.from_user.id)
    delivery_address = user.address

    # Только теперь записываем адрес в state
    await state.update_data(delivery_address=delivery_address)

    # Создаем заказ
    new_order = await orm_create_order(
        session, callback.from_user.id, delivery_address, phone_number
    )

    order_details = (
        f"📦 Новый заказ №{new_order.id}\n"
        f"👤 Покупатель: {callback.from_user.first_name} {callback.from_user.last_name}\n"
        f"📞 Телефон: {phone_number}\n"
        f"📍 Адрес: {delivery_address}\n"
        f"💰 Стоимость: {new_order.total_price} £."
    )

    for admin_id in bot.my_admins_list:
        try:
            await bot.send_message(
                admin_id,
                order_details,
                reply_markup=one_button_kb(
                    text="В работе", callback_data="status_in_progress"
                ),
            )
        except Exception as e:
            print(f"Не удалось отправить сообщение администратору {admin_id}: {e}")

    await callback.message.answer(
        f"✅ Заказ №{new_order.id} создан!\n📞 Телефон: {phone_number}\n📍 Адрес: {delivery_address}\n💰 Стоимость: {new_order.total_price} £."
    )

    user_id = callback.from_user.id
    await callback.answer("Спасибо за ваш заказ!")
    await main_menu(session, level=0, menu_name="main", user_id=user_id)
    await state.clear()


@user_private_router.callback_query(F.data == "change_address")
async def change_address(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        'Введите новый адрес или напишите "самовывоз"):',
    )


@user_private_router.message(OrderState.waiting_for_address)
async def process_address(
    message: types.Message, state: FSMContext, session: AsyncSession, bot: Bot
):
    user = message.from_user
    data = await state.get_data()
    phone_number = data.get("phone_number")
    user_id = message.from_user.id
    delivery_address = message.text.strip()

    # Записываем адрес в state только после подтверждения или ввода
    await state.update_data(delivery_address=delivery_address)

    # Обновляем данные пользователя
    await orm_update_user(
        session,
        user_id=user_id,
        data={  # ✅ Передаём данные в виде словаря
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": phone_number,
            "address": delivery_address,
        },
    )

    # Создаем заказ
    new_order = await orm_create_order(
        session, user_id, delivery_address, phone_number
    )

    order_details = (
        f"📦 Новый заказ №{new_order.id}\n"
        f"👤 Покупатель: {message.from_user.first_name} {message.from_user.last_name}\n"
        f"📞 Телефон: {phone_number}\n"
        f"📍 Адрес: {delivery_address}\n"
        f"💰 Стоимость: {new_order.total_price} £"
    )

    for admin_id in bot.my_admins_list:
        try:
            await bot.send_message(
                admin_id,
                order_details,
                reply_markup=one_button_kb(
                    text="В работе", callback_data="status_in_progress"
                ),
            )
        except Exception as e:
            print(f"Не удалось отправить сообщение администратору {admin_id}: {e}")

    await message.answer(
        f"✅ Заказ №{new_order.id} создан!\n📞 Телефон: {phone_number}\n📍 Адрес: {delivery_address}\n💰 Стоимость: {new_order.total_price} £."
    )

    user_id = message.from_user.id
    await message.answer("Спасибо за ваш заказ!")
    await main_menu(session, level=0, menu_name="main", user_id=user_id)

    await state.clear()
