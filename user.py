from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

import database as db
from config import ADMIN_IDS, CURRENCY, SHOP_NAME
from emojis import tg
from keyboards import main_menu, catalog_kb, product_kb, back_kb

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    args = message.text.split(maxsplit=1)
    invited_by = None
    if len(args) > 1 and args[1].startswith("ref_"):
        ref_code = args[1].removeprefix("ref_")
        inviter = await db.get_user_by_ref(ref_code)
        if inviter and inviter["user_id"] != message.from_user.id:
            invited_by = inviter["user_id"]

    await db.get_or_create_user(message.from_user.id, message.from_user.username, invited_by)

    text = (
        f"{tg('fire')} <b>{SHOP_NAME}</b> {tg('fire')}\n\n"
        f"Добро пожаловать{', ' + message.from_user.first_name if message.from_user.first_name else ''}!\n"
        f"Здесь ты можешь купить доступ к нашим продуктам и, если ты реселлер — "
        f"зарабатывать на реф. программе.\n\n"
        f"{tg('diamond')} Выбирай раздел ниже {tg('diamond')}"
    )
    await message.answer(text, reply_markup=main_menu(is_admin(message.from_user.id)))


@router.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery):
    await call.message.edit_text(
        f"{tg('fire')} <b>{SHOP_NAME}</b> — главное меню",
        reply_markup=main_menu(is_admin(call.from_user.id)),
    )
    await call.answer()


@router.callback_query(F.data == "catalog")
async def show_catalog(call: CallbackQuery):
    products = await db.list_products()
    if not products:
        await call.message.edit_text("Пока пусто, загляни позже 🙂", reply_markup=back_kb())
        await call.answer()
        return
    await call.message.edit_text(
        f"{tg('key')} <b>Каталог товаров</b>\nВыбери позицию:",
        reply_markup=catalog_kb(products),
    )
    await call.answer()


@router.callback_query(F.data.startswith("product_"))
async def show_product(call: CallbackQuery):
    product_id = int(call.data.split("_")[1])
    product = await db.get_product(product_id)
    if not product:
        await call.answer("Товар не найден", show_alert=True)
        return

    user = await db.get_user(call.from_user.id)
    price = product["reseller_price"] if user and user["is_reseller"] else product["price"]
    count = await db.stock_count(product_id)

    text = (
        f"{tg('star')} <b>{product['name']}</b>\n\n"
        f"{product['description']}\n\n"
        f"{tg('money')} Цена: <b>{price} {CURRENCY}</b>\n"
        f"{tg('check') if count else tg('cross')} В наличии: <b>{count}</b> шт."
    )
    await call.message.edit_text(text, reply_markup=product_kb(product_id))
    await call.answer()


@router.callback_query(F.data.startswith("buy_"))
async def buy_product(call: CallbackQuery):
    product_id = int(call.data.split("_")[1])
    result = await db.buy_product(call.from_user.id, product_id)
    if not result:
        await call.answer(
            "Не получилось купить: либо нет товара в наличии, либо не хватает баланса.",
            show_alert=True,
        )
        return

    text = (
        f"{tg('check')} <b>Покупка успешна!</b>\n\n"
        f"Списано: <b>{result['price']} {CURRENCY}</b>\n\n"
        f"{tg('key')} Твой ключ:\n<code>{result['key']}</code>"
    )
    await call.message.answer(text)
    await call.answer()


@router.callback_query(F.data == "balance")
async def show_balance(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    status = f"{tg('diamond')} Реселлер" if user["is_reseller"] else "Обычный клиент"
    text = (
        f"{tg('money')} <b>Твой баланс:</b> {user['balance']} {CURRENCY}\n"
        f"Статус: {status}\n\n"
        f"Чтобы пополнить баланс — напиши в поддержку."
    )
    await call.message.edit_text(text, reply_markup=back_kb())
    await call.answer()


@router.callback_query(F.data == "orders")
async def show_orders(call: CallbackQuery):
    orders = await db.user_orders(call.from_user.id)
    if not orders:
        await call.message.edit_text("У тебя пока нет покупок.", reply_markup=back_kb())
        await call.answer()
        return
    lines = [f"{tg('check')} <b>История покупок</b>\n"]
    for o in orders[:20]:
        lines.append(f"• {o['product_name']} — {o['price_paid']} {CURRENCY} ({o['created_at'][:16]})")
    await call.message.edit_text("\n".join(lines), reply_markup=back_kb())
    await call.answer()


@router.callback_query(F.data == "referral")
async def show_referral(call: CallbackQuery, bot: Bot):
    user = await db.get_user(call.from_user.id)
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{user['ref_code']}"
    status = "активен ✅" if user["is_reseller"] else "не активен (обратись к админу за статусом реселлера)"

    text = (
        f"{tg('rocket')} <b>Реферальная программа</b>\n\n"
        f"Твоя ссылка:\n<code>{link}</code>\n\n"
        f"Статус реселлера: {status}\n"
        f"Если ты реселлер — получаешь бонус на баланс с каждой покупки "
        f"приглашённого пользователя."
    )
    await call.message.edit_text(text, reply_markup=back_kb())
    await call.answer()


@router.callback_query(F.data == "support")
async def show_support(call: CallbackQuery):
    text = f"{tg('warning')} По всем вопросам пиши администратору магазина."
    await call.message.edit_text(text, reply_markup=back_kb())
    await call.answer()


@router.message(Command("getemoji"))
async def get_emoji_ids(message: Message):
    """Утилита для админа: ответь этой командой на сообщение с premium-эмодзи,
    чтобы получить их custom_emoji_id для файла emojis.py"""
    if not is_admin(message.from_user.id):
        return
    if not message.reply_to_message:
        await message.answer("Ответь этой командой на сообщение, содержащее premium-эмодзи.")
        return

    target = message.reply_to_message
    if not target.entities:
        await message.answer("В этом сообщении не найдено эмодзи-сущностей.")
        return

    found = []
    for ent in target.entities:
        if ent.type == "custom_emoji":
            piece = target.text[ent.offset: ent.offset + ent.length]
            found.append(f"{piece} → <code>{ent.custom_emoji_id}</code>")

    if not found:
        await message.answer("Premium-эмодзи не найдены (обычные эмодзи не имеют ID).")
        return

    await message.answer("Найденные ID:\n" + "\n".join(found))
