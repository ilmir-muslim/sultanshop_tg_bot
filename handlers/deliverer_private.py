from aiogram import F, Bot, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup

from database.orm_query import (
    orm_add_deliverer,
    orm_add_review,
    orm_get_deliverer_reviews_and_update_summary,
    orm_get_deliverers,
    orm_get_orders,
    orm_update_deliverer,
    orm_update_order,
    orm_update_review,
)
from filters.chat_types import ChatTypeFilter
from kbds.inline import inline_buttons_kb
from kbds.reply import get_keyboard


deliverer_private_router = Router()
deliverer_private_router.message.filter(ChatTypeFilter(["private"]))


class DelivererRatingState(StatesGroup):
    waiting_for_phone = State()


class SharedContextDeliverer:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_is_active(self, user_id: int) -> bool:
        """Получает актуальное состояние is_active из БД."""
        deliverer = await orm_get_deliverers(self.session, telegram_id=user_id)
        if not deliverer:
            raise ValueError("Доставщик не найден в БД")
        return deliverer.is_active

    async def get_deliverer_kb(self, user_id: int) -> types.ReplyKeyboardMarkup:
        """Возвращает клавиатуру через get_keyboard, учитывая is_active."""
        is_active = await self.get_is_active(user_id)
        return get_keyboard(
            "список активных заказов",
            "принимаю заказы" if not is_active else "не принимаю заказы",
        )

    async def send_active_orders(self, message: types.Message):
        """
        Отправляет список активных заказов в личные сообщения доставщику.
        """
        orders = await orm_get_orders(self.session, status="Оформлен")
        if not orders:
            await message.answer("Нет активных заказов.")
            return

        for order in orders:
            if not order.delivery_address.lower() == "самовывоз":
                await message.answer(
                    f"📦 Заказ №{order.id}\n"
                    f"👤 Покупатель: {order.user.first_name} {order.user.last_name}\n"
                    f"📞 Телефон: {order.user.phone or 'Телефон не указан'}\n"
                    f"📍 Адрес доставки: {order.delivery_address}\n"
                    f"💰 Общая стоимость: {order.total_price} £.\n"
                    f"📋 Статус: {order.status}\n"
                    f"🕒 Дата создания: {order.created.strftime('%d.%m.%Y %H:%M')}\n",
                    reply_markup=inline_buttons_kb(
                        {"принять заказ": {"callback_data": f"accept_order_{order.id}"}}
                    ),
                )


@deliverer_private_router.message(Command("deliverer"))
async def delivery_command(
    message: types.Message, session: AsyncSession, state: FSMContext
):
    """
    Обработчик команды /deliverer
    """
    user_id = message.from_user.id
    deliverer = await orm_get_deliverers(session, telegram_id=user_id)

    if not deliverer:
        await message.answer("Введите номер телефона")
        # Переводим пользователя в состояние ожидания номера телефона
        await state.set_state(DelivererRatingState.waiting_for_phone)
    else:
        shared_context = SharedContextDeliverer(session)
        deliverer_kb = await shared_context.get_deliverer_kb(user_id)
        await message.answer(
            "Вы в меню для доставщиков. Выберите действие", reply_markup=deliverer_kb
        )


@deliverer_private_router.message(DelivererRatingState.waiting_for_phone)
async def handle_phone_number(
    message: types.Message, session: AsyncSession, state: FSMContext
):
    """
    Обрабатывает сообщение с номером телефона.
    """
    user_id = message.from_user.id
    user_name = message.from_user.username
    user_first_name = message.from_user.first_name
    user_last_name = message.from_user.last_name
    phone_number = message.text  # Получаем номер телефона из сообщения

    # Добавляем доставщика в базу данных
    await orm_add_deliverer(
        session,
        telegram_id=user_id,
        telegram_name=user_name,
        first_name=user_first_name,
        last_name=user_last_name,
        phone=phone_number,
    )

    # Завершаем состояние
    await state.clear()
    shared_context = SharedContextDeliverer(session)
    # Отправляем сообщение о завершении регистрации
    deliverer_kb = await shared_context.get_deliverer_kb(user_id)
    await message.answer(
        "Вы успешно зарегистрированы как доставщик", reply_markup=deliverer_kb
    )


@deliverer_private_router.message(F.text == "список активных заказов")
async def active_orders(message: types.Message, session: AsyncSession):
    """
    Обработчик кнопки "список активных заказов"
    """
    context = SharedContextDeliverer(session)
    await context.send_active_orders(message)


@deliverer_private_router.message(F.text.in_(["принимаю заказы", "не принимаю заказы"]))
async def deliverer_status(message: types.Message, session: AsyncSession):
    """
    Обработчик кнопки "принимаю заказы" или "не принимаю заказы"
    """
    user_id = message.from_user.id
    if message.text == "принимаю заказы":
        data = {"is_active": True}
        await orm_update_deliverer(session, telegram_id=user_id, data=data)
        # Теперь получаем актуальную клавиатуру
        shared_context = SharedContextDeliverer(session)
        deliverer_kb = await shared_context.get_deliverer_kb(user_id)
        await message.answer(
            "Вы принимаете заказы, новые заказы будут приходить в этот чат",
            reply_markup=deliverer_kb,
        )
    elif message.text == "не принимаю заказы":
        data = {"is_active": False}
        await orm_update_deliverer(session, telegram_id=user_id, data=data)
        shared_context = SharedContextDeliverer(session)
        deliverer_kb = await shared_context.get_deliverer_kb(user_id)
        await message.answer(
            "Вы не принимаете заказы, заказы не будут приходить",
            reply_markup=deliverer_kb,
        )


@deliverer_private_router.callback_query(F.data.startswith("accept_order_"))
async def accept_order(callback: types.CallbackQuery, session: AsyncSession, bot: Bot):
    """
    Обработчик кнопки "принять заказ"
    """
    deliverer = await orm_get_deliverers(session, telegram_id=callback.from_user.id)
    order_id = int(callback.data.split("_")[-1])
    order = await orm_get_orders(session, order_id=order_id)
    data_for_update = {
        "deliverer_id": deliverer.id,
        "status": "В работе",
    }
    await bot.send_message(
        order.user_id,
        f"Ваш заказ №{order_id} был принят курьером {deliverer.first_name}\n"
        f"номер телефона: {deliverer.phone}\n"
        f"написать курьеру: @{deliverer.telegram_name}\n"
        f"Ожидайте доставку.",
    )
    await orm_update_order(session, order_id, data_for_update)
    await callback.message.answer(
        f'Вы приняли заказ №{order_id}, нажмите кнопку "я выполнил заказ", когда совершите доставку',
        reply_markup=inline_buttons_kb(
            {
                "я выполнил заказ": {
                    "callback_data": f"complete_order_{order_id}",
                }
            }
        ),
    )


@deliverer_private_router.callback_query(F.data.startswith("complete_order_"))
async def complete_order(
    callback: types.CallbackQuery, session: AsyncSession, bot: Bot
):
    """
    Обработчик кнопки "я выполнил заказ"
    """
    order_id = int(callback.data.split("_")[-1])
    order = await orm_get_orders(session, order_id=order_id)

    data_for_update = {
        "status": "Выполнен",
    }
    # await bot.send_message(
    #     order.user_id,
    #     f"Ваш заказ №{order_id} был выполнен! \n"
    #     f"Поставьте оценку доставщику и оставьте отзыв",
    #     reply_markup=get_raiting_keyboard(
    #         target_type="deliverer",
    #         target_id=order.deliverer,  # ID доставщика
    #         order_id=order_id,  # ID заказа
    #     ),
    # )
    await orm_update_order(session, order_id, data_for_update)
    await callback.answer(f"Вы завершили заказ №{order_id}")
    context = SharedContextDeliverer(session)
    await context.send_active_orders(callback.message)


@deliverer_private_router.callback_query(F.data.startswith("deliverer_"))
async def deliverer_rating(
    callback: types.CallbackQuery, session: AsyncSession, state: FSMContext
):
    """
    Обработчик кнопки "⭐️"
    """
    # Извлекаем данные из callback_data
    data = callback.data.split("_")
    deliverer_id = int(data[1])  # ID доставщика
    order_id = int(data[2])  # ID заказа
    rating = int(data[3])  # Оценка

    # Сохраняем рейтинг в базе данных
    await orm_add_review(
        session,
        user_id=callback.from_user.id,
        deliverer_id=deliverer_id,
        order_id=order_id,
        rating=rating,
    )

    # Сохраняем данные в FSM
    await state.update_data(deliverer_id=deliverer_id, order_id=order_id)

    # Переводим пользователя в состояние ожидания текста отзыва
    await state.set_state(DelivererRatingState.waiting_for_phone)
    await callback.answer(
        f"Спасибо за вашу оценку! Вы поставили {rating} звёзд.\n"
        "Теперь вы можете оставить текстовый отзыв о доставщике."
    )


@deliverer_private_router.message(DelivererRatingState.waiting_for_phone)
async def handle_review_text(
    message: types.Message, session: AsyncSession, state: FSMContext
):
    """
    Обработчик текста отзыва.
    """
    # Получаем данные из FSM
    data = await state.get_data()
    deliverer_id = data["deliverer_id"]
    order_id = data["order_id"]

    # Добавляем текст отзыва в данные состояния
    review_text = message.text
    await state.update_data(review_text=review_text)

    # Сохраняем текст отзыва в базе данных
    await orm_update_review(
        session,
        data={
            "user_id": message.from_user.id,
            "deliverer_id": deliverer_id,
            "order_id": order_id,
            "text": review_text,
        },
    )
    orm_get_deliverer_reviews_and_update_summary(
        session,
        deliverer_id=deliverer_id,
    )
    # Завершаем состояние
    await state.clear()

    await message.answer("Спасибо за ваш отзыв! Он был успешно сохранён.")
