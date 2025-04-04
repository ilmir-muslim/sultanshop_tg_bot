from aiogram.filters.callback_data import CallbackData

class StatusCallback(CallbackData, prefix="status"):
    value: str