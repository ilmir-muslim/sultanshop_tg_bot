import logging
from unicodedata import category
from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter, or_f
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Category, Seller
from database.orm_query import (
    orm_add_category,
    orm_add_seller,
    orm_change_banner_image,
    orm_get_categories,
    orm_add_product,
    orm_delete_product,
    orm_get_info_pages,
    orm_get_orders,
    orm_get_product,
    orm_get_products,
    orm_get_sellers,
    orm_update_product,
)

from filters.callback_filters import StatusCallback
from filters.chat_types import ChatTypeFilter, IsAdmin

from kbds.inline import get_callback_btns, get_status_keyboard
from kbds.reply import get_keyboard
from utils.json_operations import save_added_goods


admin_router = Router()
admin_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())



ADMIN_KB = get_keyboard(
    "Добавить товар",
    "Ассортимент",
    "Добавить/Изменить баннер",
    "Заказы",
    placeholder="Выберите действие",
    sizes=(2,),
)


@admin_router.message(Command("admin"))
async def admin_features(message: types.Message):
    await message.answer("Что хотите сделать?", reply_markup=ADMIN_KB)


@admin_router.message(F.text == 'Ассортимент')
async def admin_features(message: types.Message, session: AsyncSession):
    categories = await orm_get_categories(session)
    btns = {category.name : f'category_{category.id}' for category in categories}
    btns["показать все товары"] = "show_all_products"
    await message.answer("Выберите категорию", reply_markup=get_callback_btns(btns=btns))

@admin_router.callback_query(F.data == "show_all_products")
async def show_all_products(callback: types.CallbackQuery, session: AsyncSession):
    products = await orm_get_products(session)
    for product in products:
        await callback.message.answer_photo(
            product.image,
            caption=f"<strong>{product.name}</strong>\n"
                f"<strong>{product.description}</strong>\n"
                f"<strong>Закупочная цена: {round(product.purchase_price, 2)}</strong>\n"
                f"<strong>Розничная цена: {round(product.price, 2)}</strong>\n"
                f"<strong>Категория: {product.category.name}</strong>\n"
                f"<strong>Продавец: {product.seller.name}</strong>\n"
                f"<strong>Количество на складе: {product.quantity}</strong>\n", 
        parse_mode="HTML",
        reply_markup=get_callback_btns(
                btns={
                    "Удалить": f"delete_{product.id}",
                    "Изменить": f"change_{product.id}",
                },
                sizes=(2,)
            ),
        )
    await callback.answer()


@admin_router.callback_query(F.data.startswith('category_'))
async def starring_at_product(callback: types.CallbackQuery, session: AsyncSession):
    category_id = callback.data.split('_')[-1]
    for product in await orm_get_products(session, int(category_id)):
        await callback.message.answer_photo(
            product.image,
            caption=f"<strong>{product.name}</strong>\n"
                f"<strong>{product.description}</strong>\n"
                f"<strong>Закупочная цена: {round(product.purchase_price, 2)}</strong>\n"
                f"<strong>Розничная цена: {round(product.price, 2)}</strong>\n"
                f"<strong>Категория: {product.category.name}</strong>\n"
                f"<strong>Продавец: {product.seller.name}</strong>\n"
                f"<strong>Количество на складе: {product.quantity}</strong>\n", 
        parse_mode="HTML",
        reply_markup=get_callback_btns(
                btns={
                    "Удалить": f"delete_{product.id}",
                    "Изменить": f"change_{product.id}",
                },
                sizes=(2,)
            ),
        )
    await callback.answer()



@admin_router.callback_query(F.data.startswith("delete_"))
async def delete_product_callback(callback: types.CallbackQuery, session: AsyncSession):
    product_id = callback.data.split("_")[-1]
    await orm_delete_product(session, int(product_id))

    await callback.answer("Товар удален")
    await callback.message.answer("Товар удален!")


################# Микро FSM для загрузки/изменения баннеров ############################

class AddBanner(StatesGroup):
    image = State()

# Отправляем перечень информационных страниц бота и становимся в состояние отправки photo
@admin_router.message(StateFilter(None), F.text == 'Добавить/Изменить баннер')
async def add_image2(message: types.Message, state: FSMContext, session: AsyncSession):
    pages_names = [page.name for page in await orm_get_info_pages(session)]
    await message.answer(f"Отправьте фото баннера.\nВ описании укажите для какой страницы:\
                         \n{', '.join(pages_names)}")
    await state.set_state(AddBanner.image)

# Добавляем/изменяем изображение в таблице (там уже есть записанные страницы по именам:
# main, catalog, cart(для пустой корзины), about, payment, shipping
@admin_router.message(AddBanner.image, F.photo)
async def add_banner(message: types.Message, state: FSMContext, session: AsyncSession):
    image_id = message.photo[-1].file_id
    for_page = message.caption.strip()
    pages_names = [page.name for page in await orm_get_info_pages(session)]
    if for_page not in pages_names:
        await message.answer(f"Введите нормальное название страницы, например:\
                         \n{', '.join(pages_names)}")
        return
    await orm_change_banner_image(session, for_page, image_id,)
    await message.answer("Баннер добавлен/изменен.")
    await state.clear()

# ловим некоррекный ввод
@admin_router.message(AddBanner.image)
async def add_banner2(message: types.Message, state: FSMContext):
    await message.answer("Отправьте фото баннера или отмена")

#########################################################################################



######################### FSM для дабавления/изменения товаров админом ###################

class AddProduct(StatesGroup):
    # Шаги состояний
    name = State()
    description = State()
    category = State()
    new_category = State()
    seller = State()
    new_seller = State()
    quantity = State()
    price = State()
    image = State()

    product_for_change = None
    #TODO сделать так, чтобы при изменении товара можно было выбрать нужный параметр для изменения

    texts = {
        "AddProduct:name": "Введите название заново:",
        "AddProduct:description": "Введите описание заново:",
        "AddProduct:category": "Выберите категорию  заново ⬆️",
        "AddProduct:price": "Введите стоимость заново:",
        "AddProduct:image": "Этот стейт последний, поэтому...",
    }


# Становимся в состояние ожидания ввода name
@admin_router.callback_query(StateFilter(None), F.data.startswith("change_"))
async def change_product_callback(
    callback: types.CallbackQuery, state: FSMContext, session: AsyncSession
):
    product_id = callback.data.split("_")[-1]

    product_for_change = await orm_get_product(session, int(product_id))

    AddProduct.product_for_change = product_for_change

    await callback.answer()
    await callback.message.answer(
        "Введите название товара", reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(AddProduct.name)


# Становимся в состояние ожидания ввода name
@admin_router.message(StateFilter(None), F.text == "Добавить товар")
async def add_product(message: types.Message, state: FSMContext):
    await message.answer(
        "Введите название товара", reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(AddProduct.name)

#TODO добавить выбор продавца при добалении товара

# Хендлер отмены и сброса состояния должен быть всегда именно здесь,
# после того, как только встали в состояние номер 1 (элементарная очередность фильтров)
@admin_router.message(StateFilter("*"), Command("отмена"))
@admin_router.message(StateFilter("*"), F.text.casefold() == "отмена")
async def cancel_handler(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        return
    if AddProduct.product_for_change:
        AddProduct.product_for_change = None
    await state.clear()
    await message.answer("Действия отменены", reply_markup=ADMIN_KB)


# Вернутся на шаг назад (на прошлое состояние)
@admin_router.message(StateFilter("*"), Command("назад"))
@admin_router.message(StateFilter("*"), F.text.casefold() == "назад")
async def back_step_handler(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()

    if current_state == AddProduct.name:
        await message.answer(
            'Предидущего шага нет, или введите название товара или напишите "отмена"'
        )
        return

    previous = None
    for step in AddProduct.__all_states__:
        if step.state == current_state:
            await state.set_state(previous)
            await message.answer(
                f"Ок, вы вернулись к прошлому шагу \n {AddProduct.texts[previous.state]}"
            )
            return
        previous = step


# Ловим данные для состояние name и потом меняем состояние на description
@admin_router.message(AddProduct.name, F.text)
async def add_name(message: types.Message, state: FSMContext):
    if message.text == "." and AddProduct.product_for_change:
        await state.update_data(name=AddProduct.product_for_change.name)
    else:
        # Здесь можно сделать какую либо дополнительную проверку
        # и выйти из хендлера не меняя состояние с отправкой соответствующего сообщения
        # например:
        if 4 >= len(message.text) >= 150:
            await message.answer(
                "Название товара не должно превышать 150 символов\nили быть менее 5ти символов. \n Введите заново"
            )
            return

        await state.update_data(name=message.text)
    await message.answer("Введите описание товара")
    await state.set_state(AddProduct.description)

# Хендлер для отлова некорректных вводов для состояния name
@admin_router.message(AddProduct.name)
async def add_name2(message: types.Message, state: FSMContext):
    await message.answer("Вы ввели не допустимые данные, введите текст названия товара")


# Ловим данные для состояние description и потом меняем состояние на price
@admin_router.message(AddProduct.description, F.text)
async def add_description(message: types.Message, state: FSMContext, session: AsyncSession):
    if message.text == "." and AddProduct.product_for_change:
        await state.update_data(description=AddProduct.product_for_change.description)
    else:
        if 4 >= len(message.text):
            await message.answer(
                "Слишком короткое описание. \n Введите заново"
            )
            return
        await state.update_data(description=message.text)

    categories = await orm_get_categories(session)
    btns = {category.name : str(category.id) for category in categories}
    btns["Добавить категорию"] = "add_category"
    if AddProduct.product_for_change:
        btns["пропустить"] = "skip_category"
    await message.answer("Выберите категорию", reply_markup=get_callback_btns(btns=btns))
    await state.set_state(AddProduct.category)

# Хендлер для отлова некорректных вводов для состояния description
@admin_router.message(AddProduct.description)
async def add_description2(message: types.Message, state: FSMContext):
    await message.answer("Вы ввели не допустимые данные, введите текст описания товара")


@admin_router.callback_query(AddProduct.category, F.data == "add_category")
async def add_new_category(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название новой категории:")
    await state.set_state(AddProduct.new_category)

@admin_router.message(AddProduct.new_category, F.text)
async def save_new_category(message: types.Message, state: FSMContext, session: AsyncSession):
    category_name = message.text.strip()

    success = await orm_add_category(session, category_name)
    if success:
        await message.answer(f"Категория '{category_name}' успешно добавлена!")
    else:
        await message.answer(f"Категория '{category_name}' уже существует.")

    # Повторно выводим список категорий
    categories = await orm_get_categories(session)
    btns = {category.name: str(category.id) for category in categories}
    btns["Добавить категорию"] = "add_category"
    if AddProduct.product_for_change:
        btns["пропустить"] = "skip_category"
    await message.answer("Выберите категорию", reply_markup=get_callback_btns(btns=btns))
    await state.set_state(AddProduct.category)

@admin_router.message(AddProduct.category, F.data == "skip_category")
async def skip_category(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(category=AddProduct.product_for_change.category.id)

# Ловим callback выбора категории
@admin_router.callback_query(AddProduct.category)
async def category_choice(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    if callback.data == "skip_category":
        # Если пользователь выбрал "пропустить", оставляем категорию без изменений
        await state.update_data(category=AddProduct.product_for_change.category)
        sellers = await orm_get_sellers(session)
        btns = {seller.name: str(seller.id) for seller in sellers}
        btns["Добавить продавца"] = "add_seller"
        if AddProduct.product_for_change:
            btns["пропустить"] = "skip_seller"
        await callback.message.answer('Выберите продавца', reply_markup=get_callback_btns(btns=btns))
        await state.set_state(AddProduct.seller)
        return

    # Проверяем, что callback.data можно преобразовать в int
    try:
        category_id = int(callback.data)
    except ValueError:
        await callback.message.answer("Некорректный выбор. Используйте кнопки для выбора категории.")
        await callback.answer()
        return

    # Проверяем, что категория существует
    if category_id in [category.id for category in await orm_get_categories(session)]:
        await callback.answer()
        await state.update_data(category=category_id)

        sellers = await orm_get_sellers(session)
        btns = {seller.name: str(seller.id) for seller in sellers}
        btns["Добавить продавца"] = "add_seller"
        if AddProduct.product_for_change:
            btns["пропустить"] = "skip_seller"
        await callback.message.answer('Выберите продавца', reply_markup=get_callback_btns(btns=btns))
        await state.set_state(AddProduct.seller)
    else:
        await callback.message.answer('Используйте кнопки для выбора категории')
        await callback.answer()


#Ловим любые некорректные действия, кроме нажатия на кнопку выбора категории
@admin_router.message(AddProduct.category)
async def category_choice2(message: types.Message, state: FSMContext):
    await message.answer("'Выберите катеорию из кнопок, либо добавьте новую категорию'") 



@admin_router.callback_query(AddProduct.seller, F.data == "add_seller")
async def add_new_seller(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Введите данные нового продавца через запятую в формате:\n"
        "Имя, Описание, Телефон, Адрес\n\n"
        "Пример: Иван Иванов, продавец-молодец!, +79991234567, Москва\n\n"
        "Если какие-то данные не нужны, оставьте их пустыми, например:\n"
        "Иван Иванов,,,Москва"
    )
    await state.set_state(AddProduct.new_seller)  # Используем уже существующее состояние

@admin_router.message(AddProduct.new_seller, F.text)
async def save_new_seller(message: types.Message, state: FSMContext, session: AsyncSession):
    # Разделяем введённые данные по запятой
    data = message.text.split(",")
    if len(data) < 1 or not data[0].strip():
        await message.answer("Имя продавца обязательно. Попробуйте снова.")
        return

    # Извлекаем данные
    seller_name = data[0].strip()
    seller_description = data[1].strip() if len(data) > 1 and data[1].strip() else None
    seller_phone = data[2].strip() if len(data) > 2 and data[2].strip() else None
    seller_address = data[3].strip() if len(data) > 3 and data[3].strip() else None

    # Сохраняем продавца в базу данных
    success = await orm_add_seller(
        session,
        name=seller_name,
        description=seller_description,
        phone=seller_phone,
        address=seller_address,
    )

    if success:
        await message.answer(f"Продавец '{seller_name}' успешно добавлен!")
    else:
        await message.answer(f"Продавец '{seller_name}' уже существует.")

    # Возвращаем пользователя к выбору продавца
    sellers = await orm_get_sellers(session)
    btns = {seller.name: str(seller.id) for seller in sellers}
    btns["Добавить продавца"] = "add_seller"
    if AddProduct.product_for_change:
        btns["пропустить"] = "skip"
    await message.answer("Выберите продавца", reply_markup=get_callback_btns(btns=btns))
    await state.set_state(AddProduct.seller)

@admin_router.callback_query(AddProduct.seller)
async def seller_choice(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    if callback.data == "skip_seller":
        # Если пользователь выбрал "пропустить", оставляем продавца без изменений
        await state.update_data(seller=AddProduct.product_for_change.seller)
        await callback.message.answer("Введите количество товара:")
        await state.set_state(AddProduct.quantity)
        return

    # Проверяем, что callback.data можно преобразовать в int
    try:
        seller_id = int(callback.data)
    except ValueError:
        await callback.message.answer("Некорректный выбор. Используйте кнопки для выбора продавца.")
        await callback.answer()
        return

    # Проверяем, что продавец существует
    if seller_id in [seller.id for seller in await orm_get_sellers(session)]:
        await callback.answer()
        await state.update_data(seller=seller_id)
        await callback.message.answer("Введите количество товара:")
        await state.set_state(AddProduct.quantity)
    else:
        await callback.message.answer("Используйте кнопки для выбора продавца")
        await callback.answer()

@admin_router.message(AddProduct.quantity, F.text)
async def add_quantity(message: types.Message, state: FSMContext):
    if message.text == "." and AddProduct.product_for_change:
        await state.update_data(quantity=AddProduct.product_for_change.quantity)
    else:
        # Здесь можно сделать какую либо дополнительную проверку
        # и выйти из хендлера не меняя состояние с отправкой соответствующего сообщения
        # например:
        if not message.text.isdigit() or int(message.text) <= 0:
            await message.answer(
                "Количество товара должно быть целым числом больше 0.\nВведите заново"
            )
            return
    try:
        quantity = int(message.text)
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите корректное количество (целое число больше 0).")
        return

    await state.update_data(quantity=quantity)
    await message.answer("Введите введите закупочную цену и цену продажи через запятую в формате 10.5, 15.0:")
    await state.set_state(AddProduct.price)

# Ловим данные для состояние price и потом меняем состояние на image
@admin_router.message(AddProduct.price, F.text)
async def add_price(message: types.Message, state: FSMContext):
    if message.text == "." and AddProduct.product_for_change:
        await state.update_data(
            price=AddProduct.product_for_change.price,
            purchase_price=AddProduct.product_for_change.purchase_price,
        )
    else:
        try:
            # Разделяем введённые значения по запятой
            prices = message.text.split(",")
            if len(prices) != 2:
                raise ValueError("Ожидается два значения, разделённых запятой")

            # Преобразуем значения в числа
            purchase_price = float(prices[0].replace(",", ".").strip())
            price = float(prices[1].replace(",", ".").strip())

            if purchase_price <= 0 or price <= 0:
                raise ValueError("Цены должны быть положительными числами")
        except ValueError:
            await message.answer(
                "Введите корректные значения цен в формате: закупочная, розничная\n"
                "Например: 10.5, 15.0"
            )
            return

        # Сохраняем значения в состояние FSM
        await state.update_data(purchase_price=purchase_price, price=price)

    await message.answer("Загрузите изображение товара")
    await state.set_state(AddProduct.image)

# Хендлер для отлова некорректных ввода для состояния price
@admin_router.message(AddProduct.price)
async def add_price2(message: types.Message, state: FSMContext):
    await message.answer("Вы ввели не допустимые данные, введите стоимость товара")


# Ловим данные для состояние image и потом выходим из состояний
@admin_router.message(AddProduct.image, or_f(F.photo, F.text == "."))
async def add_image(message: types.Message, state: FSMContext, session: AsyncSession):
    if message.text and message.text == "." and AddProduct.product_for_change:
        await state.update_data(image=AddProduct.product_for_change.image)
    elif message.photo:
        await state.update_data(image=message.photo[-1].file_id)
    else:
        await message.answer("Отправьте фото товара")
        return

    data = await state.get_data()

    # Преобразуем объект Category в ID, если это объект
    if isinstance(data.get("category"), Category):
        data["category"] = data["category"].id
    if isinstance(data.get("seller"), Seller):
        data["seller"] = data["seller"].id

    logging.info(f"Данные для обновления/добавления товара: {data}")

    try:
        if AddProduct.product_for_change:
            logging.info(f"Обновляем товар с ID {AddProduct.product_for_change.id} данными: {data}")
            await orm_update_product(session, AddProduct.product_for_change.id, data)
        else:
            logging.info(f"Добавляем новый товар с данными: {data}")
            await orm_add_product(session, data)
        save_added_goods(data)
        await message.answer("Товар добавлен/изменен", reply_markup=ADMIN_KB)
        await state.clear()

    except Exception as e:
        logging.error(f"Ошибка при обновлении/добавлении товара: {e}")
        await message.answer(
            f"Ошибка: \n{str(e)}\nОбратись к программеру, он опять денег хочет",
            reply_markup=ADMIN_KB,
        )
        await state.clear()

    AddProduct.product_for_change = None


    AddProduct.product_for_change = None

# Ловим все прочее некорректное поведение для этого состояния
@admin_router.message(AddProduct.image)
async def add_image2(message: types.Message, state: FSMContext):
    await message.answer("Отправьте фото пищи")

@admin_router.message(F.text == 'Заказы')
async def orders(message: types.Message):
    await message.answer(
        "Выберите статус заказа",
        reply_markup=get_status_keyboard(),
    )

@admin_router.callback_query(StatusCallback.filter())
async def handle_status_callback(callback: types.CallbackQuery, callback_data: dict, session: AsyncSession):
    status = callback_data.value
    orders = await orm_get_orders(session, status=status)

    for order in orders:
        await callback.message.answer(
            f"📦 Заказ №{order.id}\n"
            f"👤 Покупатель: {order.user.first_name} {order.user.last_name}\n"
            f"📞 Телефон: {order.user.phone or 'Телефон не указан'}\n"
            f"📍 Адрес доставки: {order.delivery_address}\n"
            f"💰 Общая стоимость: {order.total_price} £.\n"
            f"📋 Статус: {order.status}\n"
            f"🕒 Дата создания: {order.created.strftime('%d.%m.%Y %H:%M')}\n"
)

    await callback.answer()