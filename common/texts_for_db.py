from aiogram.utils.formatting import Bold, as_marked_section, as_list


categories = []

description_for_info_pages = {
    "main": "Добро пожаловать!",
    "about": ('Магазин Султан. Товары и услуги\n'
            'Контакты нашего магазина:\n'
            'Телефон: +201026282854\n'
            'Телеграм: @Vmisreabusultan, @Ilmir_muslim'),
    "payment": as_marked_section(
        Bold("Варианты оплаты:"),
        "Карта российского банка",
        "vodafon cash",
        "При получении наличными",
        "USDT",
        marker="✅ ",
    ).as_html(),
    "shipping": as_list(
        as_marked_section(
            Bold("Варианты доставки"),
            "Курьер",
            "Самовывоз",
            marker="✅ ",
        ),
    ).as_html(),
    'catalog': 'Категории:',
    'cart': 'В корзине ничего нет!'

}
