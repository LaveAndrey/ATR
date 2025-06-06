FROM python:3.12.8

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs

ENV PYTHONPATH=/app \
    TZ=Europe/Moscow \
    PYTHONUNBUFFERED=1

# Команда для запуска приложения
CMD ["python", "main.py"]