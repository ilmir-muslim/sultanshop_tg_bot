from aiogram.utils.formatting import Bold, as_marked_section, as_list


categories = []

description_for_info_pages = {
    "main": "Добро пожаловать!",
    "about": ('Магазин Султан. Товары и услуги\n'
            'Контакты нашего магазина:\n'
            'Телефон: +201026282854\n'
            'Телеграм: @Vmisreabusultan, @Ilmir_muslim'),
    "shipping": as_list(
        as_marked_section(
            Bold("Для самовывоза: "),
            "дождитесь сообщения о том что ваш заказ готов к выдаче",
            "и приходите к нам в магазин по адресу: https://maps.app.goo.gl/bEAY1Zy45zn28A4e9?g_st=it",
            marker="✅ ",
        ),
    ).as_html(),
    'catalog': 'Категории:',
    'cart': 'В корзине ничего нет!'

}
