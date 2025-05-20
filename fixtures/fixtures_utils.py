import json
import datetime
import decimal

from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Base


def custom_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


async def dump_fixtures(session: AsyncSession, output_file="fixtures/fixtures.json"):
    data = {}
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        table = cls.__tablename__
        result = await session.execute(cls.__table__.select())
        records = result.all()
        data[table] = [dict(row._mapping) for row in records]

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=custom_serializer)


def parse_datetime_fields(record: dict, fields: list[str]):
    """Преобразует строковые даты в datetime-объекты"""
    for field in fields:
        if field in record and isinstance(record[field], str):
            try:
                record[field] = datetime.fromisoformat(record[field])
            except ValueError:
                pass  # на случай некорректной строки
    return record


async def load_fixtures(session: AsyncSession, input_file="fixtures/fixtures.json"):
    models = {
        mapper.class_.__tablename__: mapper.class_ for mapper in Base.registry.mappers
    }

    with open(input_file, "r", encoding="utf-8") as f:
        fixtures = json.load(f)

    # Удаляем старые данные
    for table in reversed(models.keys()):
        if table in fixtures:
            await session.execute(models[table].__table__.delete())
    await session.commit()

    # Загружаем новые данные
    for table in fixtures:
        model = models[table]
        for record in fixtures[table]:
            # Попробуем преобразовать поля 'created' и 'updated' если они есть
            record = parse_datetime_fields(record, ["created", "updated"])
            session.add(model(**record))
    await session.commit()
