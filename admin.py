import asyncio

from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import database as db
from config import ADMIN_IDS
from emojis import tg
from keyboards import admin_menu, back_kb

router = Router()


def admin_only(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class AddProduct(StatesGroup):
    name = State()
    description = State()
    price = State()
    reseller_price = State()


class AddStock(StatesGroup):
    product_id = State()
    keys = State()


class SetReseller(StatesGroup):
    user_id = State()


class AddBalance(StatesGroup):
    user_id = State()
    amount = State()


class Broadcast(StatesGroup):
    text = State()


@router.callback_query(F.data == "admin")
async def admin_panel(call: CallbackQuery):
    if not admin_only(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    await call.message.edit_text(f"{tg('gear')} <b>Админ-панель</b>", reply_markup=admin_menu())
    await call.answer()


# ---------- ADD PRODUCT ----------

@router.callback_query(F.data == "admin_add_product")
async def add_product_start(call: CallbackQuery, state: FSMContext):
    if not admin_only(call.from_user.id):
        return
    await state.set_state(AddProduct.name)
    await call.message.edit_text("Введи название товара:", reply_markup=back_kb("admin"))
    await call.answer()


@router.message(StateFilter(AddProduct.name))
async def add_product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProduct.description)
    await message.answer("Введи описание товара:")


@router.message(StateFilter(AddProduct.description))
async def add_product_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddProduct.price)
    await message.answer("Введи розничную цену (число):")


@router.message(StateFilter(AddProduct.price))
async def add_product_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Нужно число, попробуй ещё раз:")
        return
    await state.update_data(price=price)
    await state.set_state(AddProduct.reseller_price)
    await message.answer("Введи цену для реселлеров (число):")


@router.message(StateFilter(AddProduct.reseller_price))
async def add_product_reseller_price(message: Message, state: FSMContext):
    try:
        reseller_price = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Нужно число, попробуй ещё раз:")
        return
    data = await state.get_data()
    await db.add_product(data["name"], data["description"], data["price"], reseller_price)
    await state.clear()
    await message.answer(f"{tg('check')} Товар добавлен!", reply_markup=admin_menu())


# ---------- ADD STOCK ----------

@router.callback_query(F.data == "admin_add_stock")
async def add_stock_start(call: CallbackQuery, state: FSMContext):
    if not admin_only(call.from_user.id):
        return
    products = await db.list_products(active_only=False)
    if not products:
        await call.message.edit_text("Сначала добавь хотя бы один товар.", reply_markup=admin_menu())
        await call.answer()
        return
    listing = "\n".join(f"{p['id']} — {p['name']}" for p in products)
    await state.set_state(AddStock.product_id)
    await call.message.edit_text(
        f"Введи ID товара, к которому добавляем ключи:\n\n{listing}", reply_markup=back_kb("admin")
    )
    await call.answer()


@router.message(StateFilter(AddStock.product_id))
async def add_stock_pid(message: Message, state: FSMContext):
    try:
        pid = int(message.text)
    except ValueError:
        await message.answer("Нужен числовой ID, попробуй ещё раз:")
        return
    product = await db.get_product(pid)
    if not product:
        await message.answer("Товар с таким ID не найден, попробуй ещё раз:")
        return
    await state.update_data(product_id=pid)
    await state.set_state(AddStock.keys)
    await message.answer("Пришли ключи — каждый с новой строки:")


@router.message(StateFilter(AddStock.keys))
async def add_stock_keys(message: Message, state: FSMContext):
    keys = [line.strip() for line in message.text.splitlines() if line.strip()]
    data = await state.get_data()
    await db.add_stock_bulk(data["product_id"], keys)
    await state.clear()
    await message.answer(f"{tg('check')} Добавлено ключей: {len(keys)}", reply_markup=admin_menu())


# ---------- SET RESELLER ----------

@router.callback_query(F.data == "admin_set_reseller")
async def set_reseller_start(call: CallbackQuery, state: FSMContext):
    if not admin_only(call.from_user.id):
        return
    await state.set_state(SetReseller.user_id)
    await call.message.edit_text(
        "Пришли Telegram ID пользователя, которому нужно выдать статус реселлера:",
        reply_markup=back_kb("admin"),
    )
    await call.answer()


@router.message(StateFilter(SetReseller.user_id))
async def set_reseller_apply(message: Message, state: FSMContext):
    try:
        uid = int(message.text)
    except ValueError:
        await message.answer("Нужен числовой ID, попробуй ещё раз:")
        return
    user = await db.get_user(uid)
    if not user:
        await message.answer("Такой пользователь ещё не запускал бота.")
        await state.clear()
        return
    await db.set_reseller(uid, True)
    await state.clear()
    await message.answer(f"{tg('diamond')} Пользователь {uid} теперь реселлер.", reply_markup=admin_menu())


# ---------- ADD BALANCE ----------

@router.callback_query(F.data == "admin_add_balance")
async def add_balance_start(call: CallbackQuery, state: FSMContext):
    if not admin_only(call.from_user.id):
        return
    await state.set_state(AddBalance.user_id)
    await call.message.edit_text("Пришли Telegram ID пользователя:", reply_markup=back_kb("admin"))
    await call.answer()


@router.message(StateFilter(AddBalance.user_id))
async def add_balance_uid(message: Message, state: FSMContext):
    try:
        uid = int(message.text)
    except ValueError:
        await message.answer("Нужен числовой ID, попробуй ещё раз:")
        return
    user = await db.get_user(uid)
    if not user:
        await message.answer("Такой пользователь ещё не запускал бота.")
        await state.clear()
        return
    await state.update_data(user_id=uid)
    await state.set_state(AddBalance.amount)
    await message.answer("На сколько пополнить баланс (число, можно отрицательное)?")


@router.message(StateFilter(AddBalance.amount))
async def add_balance_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Нужно число, попробуй ещё раз:")
        return
    data = await state.get_data()
    await db.set_balance(data["user_id"], amount)
    await state.clear()
    await message.answer(f"{tg('money')} Баланс пользователя {data['user_id']} изменён на {amount}.", reply_markup=admin_menu())


# ---------- STATS ----------

@router.callback_query(F.data == "admin_stats")
async def show_stats(call: CallbackQuery):
    if not admin_only(call.from_user.id):
        return
    s = await db.stats()
    text = (
        f"{tg('star')} <b>Статистика</b>\n\n"
        f"Пользователей: {s['users']}\n"
        f"Реселлеров: {s['resellers']}\n"
        f"Заказов: {s['orders']}\n"
        f"Выручка: {s['revenue']}"
    )
    await call.message.edit_text(text, reply_markup=admin_menu())
    await call.answer()


# ---------- BROADCAST ----------

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    if not admin_only(call.from_user.id):
        return
    await state.set_state(Broadcast.text)
    await call.message.edit_text("Пришли текст рассылки (HTML разрешён):", reply_markup=back_kb("admin"))
    await call.answer()


@router.message(StateFilter(Broadcast.text))
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    ids = await db.all_user_ids()
    sent, failed = 0, 0
    status_msg = await message.answer(f"Рассылка запущена на {len(ids)} пользователей...")
    for uid in ids:
        try:
            await bot.send_message(uid, message.html_text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # чтобы не упереться в лимиты Telegram
    await status_msg.edit_text(f"{tg('check')} Готово. Успешно: {sent}, ошибок: {failed}.")
