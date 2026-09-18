import datetime
import secrets

import aiosqlite

from config import DB_PATH, RESELLER_PERCENT

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    balance     REAL DEFAULT 0,
    is_reseller INTEGER DEFAULT 0,
    ref_code    TEXT UNIQUE,
    invited_by  INTEGER,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT,
    description     TEXT,
    price           REAL,
    reseller_price  REAL,
    active          INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS stock (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  INTEGER,
    key_value   TEXT,
    is_sold     INTEGER DEFAULT 0,
    buyer_id    INTEGER,
    sold_at     TEXT,
    FOREIGN KEY (product_id) REFERENCES products (id)
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    product_id  INTEGER,
    price_paid  REAL,
    created_at  TEXT
);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


# ---------- USERS ----------

async def get_or_create_user(user_id: int, username: str, invited_by: int | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if row:
            return dict(row)

        ref_code = secrets.token_hex(4)
        await db.execute(
            "INSERT INTO users (user_id, username, ref_code, invited_by, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, username, ref_code, invited_by, datetime.datetime.utcnow().isoformat()),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row)


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_user_by_ref(ref_code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE ref_code = ?", (ref_code,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_balance(user_id: int, amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()


async def set_reseller(user_id: int, flag: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_reseller = ? WHERE user_id = ?", (int(flag), user_id))
        await db.commit()


async def all_user_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users")
        rows = await cur.fetchall()
        return [r[0] for r in rows]


# ---------- PRODUCTS ----------

async def add_product(name: str, description: str, price: float, reseller_price: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO products (name, description, price, reseller_price) VALUES (?, ?, ?, ?)",
            (name, description, price, reseller_price),
        )
        await db.commit()


async def list_products(active_only: bool = True):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        q = "SELECT * FROM products"
        if active_only:
            q += " WHERE active = 1"
        cur = await db.execute(q)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_product(product_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def stock_count(product_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM stock WHERE product_id = ? AND is_sold = 0", (product_id,)
        )
        (count,) = await cur.fetchone()
        return count


async def add_stock_bulk(product_id: int, keys: list[str]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            "INSERT INTO stock (product_id, key_value) VALUES (?, ?)",
            [(product_id, k) for k in keys],
        )
        await db.commit()


# ---------- ORDERS ----------

async def buy_product(user_id: int, product_id: int) -> dict | None:
    """Списывает баланс, выдаёт ключ, начисляет реф. бонус пригласившему реселлеру.
    Возвращает {'key': ..., 'price': ...} или None, если нет стока/денег."""
    user = await get_user(user_id)
    product = await get_product(product_id)
    if not user or not product:
        return None

    price = product["reseller_price"] if user["is_reseller"] else product["price"]
    if user["balance"] < price:
        return None

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM stock WHERE product_id = ? AND is_sold = 0 LIMIT 1", (product_id,)
        )
        stock_row = await cur.fetchone()
        if not stock_row:
            return None

        now = datetime.datetime.utcnow().isoformat()
        await db.execute(
            "UPDATE stock SET is_sold = 1, buyer_id = ?, sold_at = ? WHERE id = ?",
            (user_id, now, stock_row["id"]),
        )
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, user_id))
        await db.execute(
            "INSERT INTO orders (user_id, product_id, price_paid, created_at) VALUES (?, ?, ?, ?)",
            (user_id, product_id, price, now),
        )
        await db.commit()

        # реферальный бонус тому, кто привёл покупателя (если он реселлер)
        if user["invited_by"]:
            cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user["invited_by"],))
            inviter = await cur.fetchone()
            if inviter and inviter["is_reseller"]:
                bonus = price * RESELLER_PERCENT / 100
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (bonus, inviter["user_id"]),
                )
                await db.commit()

        return {"key": stock_row["key_value"], "price": price}


async def user_orders(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT o.*, p.name as product_name FROM orders o "
            "JOIN products p ON p.id = o.product_id "
            "WHERE o.user_id = ? ORDER BY o.created_at DESC",
            (user_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def stats():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        (users_count,) = await cur.fetchone()
        cur = await db.execute("SELECT COUNT(*), COALESCE(SUM(price_paid),0) FROM orders")
        orders_count, revenue = await cur.fetchone()
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE is_reseller = 1")
        (resellers_count,) = await cur.fetchone()
        return {
            "users": users_count,
            "orders": orders_count,
            "revenue": revenue,
            "resellers": resellers_count,
        }
