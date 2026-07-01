FROM python:3.11-slim

WORKDIR /app

# Встановлюємо залежності
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо код
COPY . .

# Запускаємо бота
CMD ["python", "buki_bot.py"]
