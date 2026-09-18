import os

# --- Основные настройки ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8931268434:AAFueu8bchNprBovQgzRdedRfrONB6pNr-U")

# ID админов (можно несколько)
ADMIN_IDS = [
    123456789,  # <- замени на свой Telegram ID
]

DB_PATH = "shop.db"

# Процент, который реселлер получает на баланс с каждой продажи по его реф. ссылке
RESELLER_PERCENT = 15  # в процентах

# Валюта отображения (просто текст, платёжку подключаешь сам)
CURRENCY = "₽"

# Название магазина в текстах
SHOP_NAME = "OXIDE SHOP"
