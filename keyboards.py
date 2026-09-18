from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from emojis import EMOJI


def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{EMOJI['fire']['fallback']} Каталог", callback_data="catalog")
    b.button(text=f"{EMOJI['money']['fallback']} Баланс", callback_data="balance")
    b.button(text=f"{EMOJI['key']['fallback']} Мои покупки", callback_data="orders")
    b.button(text=f"{EMOJI['diamond']['fallback']} Реф. программа", callback_data="referral")
    b.button(text="🛟 Поддержка", callback_data="support")
    if is_admin:
        b.button(text=f"{EMOJI['gear']['fallback']} Админ-панель", callback_data="admin")
    b.adjust(2, 2, 1, 1)
    return b.as_markup()


def catalog_kb(products: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in products:
        b.button(text=f"{p['name']}", callback_data=f"product_{p['id']}")
    b.button(text="⬅️ Назад", callback_data="back_main")
    b.adjust(1)
    return b.as_markup()


def product_kb(product_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{EMOJI['check']['fallback']} Купить", callback_data=f"buy_{product_id}")
    b.button(text="⬅️ К каталогу", callback_data="catalog")
    b.adjust(1)
    return b.as_markup()


def back_kb(target: str = "back_main") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад", callback_data=target)
    return b.as_markup()


def admin_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить товар", callback_data="admin_add_product")
    b.button(text="📦 Добавить ключи на склад", callback_data="admin_add_stock")
    b.button(text="📊 Статистика", callback_data="admin_stats")
    b.button(text="📢 Рассылка", callback_data="admin_broadcast")
    b.button(text="🤝 Выдать статус реселлера", callback_data="admin_set_reseller")
    b.button(text="💸 Пополнить баланс юзеру", callback_data="admin_add_balance")
    b.button(text="⬅️ Назад", callback_data="back_main")
    b.adjust(1)
    return b.as_markup()
