FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-u", "bot/main.py"]
