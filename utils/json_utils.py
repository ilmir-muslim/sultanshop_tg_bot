from decimal import Decimal

def decimal_default(obj):
    """Конвертер для Decimal в float при сериализации JSON"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

def prepare_for_json(data):
    """Подготавливает данные для сериализации в JSON"""
    if isinstance(data, (list, tuple)):
        return [prepare_for_json(item) for item in data]
    elif isinstance(data, dict):
        return {key: prepare_for_json(value) for key, value in data.items()}
    elif isinstance(data, Decimal):
        return float(data)
    return data