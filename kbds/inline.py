from aiogram.filters import callback_data
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from filters.callback_filters import StatusCallback


class MenuCallBack(CallbackData, prefix="menu"):
    level: int
    menu_name: str
    category: int | None = None
    page: int = 1
    product_id: int | None = None


class plural_goods:
    def __init__(self, count: int):
        self.count = count

    def __str__(self):
        if self.count == 1:
            return "товар"
        elif 2 <= self.count <= 4:
            return "товара"
        else:
            return "товаров"


def get_user_main_btns(*, level: int, sizes: tuple[int] = (2,), quantity: int = 0):
    keyboard = InlineKeyboardBuilder()
    btns = {
        "Товары 🏪": ("catalog", 1),
        "Корзина 🛒" if quantity == 0 else f"Корзина 🛒 {quantity}": ("cart", 3),
        "О нас ℹ️": ("about", level),
        "Мои заказы 📦": ("orders", 4),
        "Доставка/Курьер 🛵": ("shipping", 5),
    }

    for text, (menu_name, target_level) in btns.items():
        keyboard.add(
            InlineKeyboardButton(
                text=text,
                callback_data=MenuCallBack(
                    level=target_level, menu_name=menu_name
                ).pack(),
            )
        )

    return keyboard.adjust(*sizes).as_markup()


def get_user_catalog_btns(
    *, level: int, categories: list, sizes: tuple[int] = (2,), quantity: int = 0
):
    keyboard = InlineKeyboardBuilder()

    keyboard.add(
        InlineKeyboardButton(
            text="Назад",
            callback_data=MenuCallBack(level=level - 1, menu_name="main").pack(),
        )
    )
    keyboard.add(
        InlineKeyboardButton(
            text=(
                "Корзина 🛒"
                if quantity == 0
                else f"В корзине 🛒 {quantity} {plural_goods(quantity)}"
            ),
            callback_data=MenuCallBack(level=3, menu_name="cart").pack(),
        )
    )

    for c in categories:
        keyboard.add(
            InlineKeyboardButton(
                text=c.name,
                callback_data=MenuCallBack(
                    level=level + 1, menu_name=c.name, category=c.id
                ).pack(),
            )
        )

    return keyboard.adjust(*sizes).as_markup()


def get_products_btns(
    *,
    level: int,
    category: int,
    page: int,
    pagination_btns: dict,
    product_id: int,
    sizes: tuple[int] = (2, 1),
    quantity: int = 0,
    is_available: bool = True,
):
    keyboard = InlineKeyboardBuilder()

    keyboard.add(
        InlineKeyboardButton(
            text="Назад",
            callback_data=MenuCallBack(level=level - 1, menu_name="catalog").pack(),
        )
    )
    keyboard.add(
        InlineKeyboardButton(
            text=(
                "Корзина 🛒"
                if quantity == 0
                else f"В корзине 🛒 {quantity} {plural_goods(quantity)}"
            ),
            callback_data=MenuCallBack(level=3, menu_name="cart").pack(),
        )
    )
    keyboard.add(
        InlineKeyboardButton(
            text="Купить 💵 " if is_available else "Заявка 🔔",
            callback_data=MenuCallBack(
                level=level,
                menu_name="add_to_cart" if is_available else "add_to_waitlist",
                product_id=product_id,
            ).pack(),
        )
    )

    keyboard.adjust(*sizes)

    row = []
    for text, menu_name in pagination_btns.items():
        if menu_name == "next":
            row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=MenuCallBack(
                        level=level,
                        menu_name=menu_name,
                        category=category,
                        page=page + 1,
                    ).pack(),
                )
            )

        elif menu_name == "previous":
            row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=MenuCallBack(
                        level=level,
                        menu_name=menu_name,
                        category=category,
                        page=page - 1,
                    ).pack(),
                )
            )

    return keyboard.row(*row).as_markup()


def get_user_cart(
    *,
    level: int,
    page: int | None,
    pagination_btns: dict | None,
    product_id: int | None,
    sizes: tuple[int] = (3,),
):
    keyboard = InlineKeyboardBuilder()
    if page:
        keyboard.add(
            InlineKeyboardButton(
                text="Удалить",
                callback_data=MenuCallBack(
                    level=level, menu_name="delete", product_id=product_id, page=page
                ).pack(),
            )
        )
        keyboard.add(
            InlineKeyboardButton(
                text="-1",
                callback_data=MenuCallBack(
                    level=level, menu_name="decrement", product_id=product_id, page=page
                ).pack(),
            )
        )
        keyboard.add(
            InlineKeyboardButton(
                text="+1",
                callback_data=MenuCallBack(
                    level=level, menu_name="increment", product_id=product_id, page=page
                ).pack(),
            )
        )

        keyboard.adjust(*sizes)

        row = []
        for text, menu_name in pagination_btns.items():
            if menu_name == "next":
                row.append(
                    InlineKeyboardButton(
                        text=text,
                        callback_data=MenuCallBack(
                            level=level, menu_name=menu_name, page=page + 1
                        ).pack(),
                    )
                )
            elif menu_name == "previous":
                row.append(
                    InlineKeyboardButton(
                        text=text,
                        callback_data=MenuCallBack(
                            level=level, menu_name=menu_name, page=page - 1
                        ).pack(),
                    )
                )

        keyboard.row(*row)

        row2 = [
            InlineKeyboardButton(
                text="На главную 🏠",
                callback_data=MenuCallBack(level=0, menu_name="main").pack(),
            ),
            InlineKeyboardButton(text="Оформить заказ 📦", callback_data="make_order"),
        ]
        return keyboard.row(*row2).as_markup()
    else:
        keyboard.add(
            InlineKeyboardButton(
                text="На главную 🏠",
                callback_data=MenuCallBack(level=0, menu_name="main").pack(),
            )
        )

        return keyboard.adjust(*sizes).as_markup()


def get_callback_btns(*, btns: dict[str, str], sizes: tuple[int] = (2,)):
    keyboard = InlineKeyboardBuilder()

    for text, data in btns.items():
        keyboard.add(InlineKeyboardButton(text=text, callback_data=str(data)))

    return keyboard.adjust(*sizes).as_markup()


phone_confirm_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_phone")],
        [InlineKeyboardButton(text="✏ Ввести другой", callback_data="change_phone")],
    ]
)

address_confirm_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_address")],
        [InlineKeyboardButton(text="✏ Ввести другой", callback_data="change_address")],
    ]
)


def get_status_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="оформлен",
                    callback_data=StatusCallback(value="оформлен").pack(),
                ),
                InlineKeyboardButton(
                    text="в работе",
                    callback_data=StatusCallback(value="в работе").pack(),
                ),
                InlineKeyboardButton(
                    text="выполнен",
                    callback_data=StatusCallback(value="выполнен").pack(),
                ),
            ]
        ]
    )


def one_button_kb(text: str, **kwargs):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text, **kwargs  # Передаем дополнительные аргументы
                )
            ]
        ]
    )


def get_raiting_keyboard(
    target_type: str, target_id: int, order_id: int
) -> InlineKeyboardMarkup:
    """
    Генерирует клавиатуру для оценки.
    """
    buttons = [
        InlineKeyboardButton(
            text="⭐️ 1", callback_data=f"{target_type}_{target_id}_{order_id}_1"
        ),
        InlineKeyboardButton(
            text="⭐️ 2", callback_data=f"{target_type}_{target_id}_{order_id}_2"
        ),
        InlineKeyboardButton(
            text="⭐️ 3", callback_data=f"{target_type}_{target_id}_{order_id}_3"
        ),
        InlineKeyboardButton(
            text="⭐️ 4", callback_data=f"{target_type}_{target_id}_{order_id}_4"
        ),
        InlineKeyboardButton(
            text="⭐️ 5", callback_data=f"{target_type}_{target_id}_{order_id}_5"
        ),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])
