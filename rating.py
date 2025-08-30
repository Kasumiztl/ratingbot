import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram import F

API_TOKEN = "8280767748:AAEx7IfdqqY8kLFJZWLvSQ7kgtyhQwop68Y"
ADMIN_ID = 5594235882

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- база ---
conn = sqlite3.connect("bot.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    role TEXT,
    rating INTEGER DEFAULT 10
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user INTEGER,
    to_user INTEGER,
    reason TEXT
)
""")
conn.commit()
temp_registration = {}  # user_id -> {"role": str}

# --- /start ---
@dp.message(Command("start"))
async def start_cmd(message: Message):
    cur.execute("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,))
    if cur.fetchone():
        await message.answer("Ты уже зарегистрирован ✅")
    else:
        await message.answer("Напиши свою роль:")

# --- регистрация роли и username ---
@dp.message(~F.text.startswith("/"))
async def register_role_or_username(message: Message):
    user_id = message.from_user.id

    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if cur.fetchone():
        return  # уже зарегистрирован

    # если ещё нет роли → сохраняем роль и спрашиваем username
    if user_id not in temp_registration:
        temp_registration[user_id] = {"role": message.text.strip()}
        await message.answer("Отлично! Теперь напиши свой username (например: @username):")
        return

    # если роль уже есть → сохраняем username и добавляем в базу
    username = message.text.strip().lstrip("@")
    role = temp_registration[user_id]["role"]

    cur.execute(
        "INSERT INTO users (user_id, username, role, rating) VALUES (?, ?, ?, ?)",
        (user_id, username, role, 10)
    )
    conn.commit()
    temp_registration.pop(user_id)

    await message.answer(f"Регистрация завершена! Роль: {role}, username: @{username}, рейтинг 10/10 ✅")

# --- жалоба ---
@dp.message(Command("complain"))
async def complain(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Формат: /complain @username причина")
        return

    target_username = args[1].lstrip("@")
    reason = args[2]

    cur.execute("SELECT user_id FROM users WHERE username = ?", (target_username,))
    result = cur.fetchone()
    if not result:
        await message.answer("Участник не найден")
        return

    target_id = result[0]
    cur.execute("INSERT INTO complaints (from_user, to_user, reason) VALUES (?, ?, ?)",
                (message.from_user.id, target_id, reason))
    conn.commit()

    await message.answer(f"Жалоба на @{target_username} отправлена")

# --- жалобы на пользователя ---
@dp.message(Command("complaints"))
async def show_complaints(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Формат: /complaints @username")
        return

    target_username = args[1].lstrip("@")
    cur.execute("SELECT user_id, role FROM users WHERE username = ?", (target_username,))
    result = cur.fetchone()
    if not result:
        await message.answer("Участник не найден ")
        return

    target_id, role = result
    cur.execute("SELECT from_user, reason FROM complaints WHERE to_user = ?", (target_id,))
    complaints = cur.fetchall()

    if not complaints:
        await message.answer(f"На @{target_username} ({role}) жалоб нет ")
    else:
        text = "\n".join([f"- от {uid}: {reason}" for uid, reason in complaints])
        await message.answer(f"Жалобы на @{target_username} ({role}):\n{text}")

# --- рейтинг конкретного игрока ---
@dp.message(Command("rating"))
async def show_rating(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Формат: /rating @username")
        return

    target_username = args[1].lstrip("@")
    cur.execute("SELECT role, rating FROM users WHERE username = ?", (target_username,))
    result = cur.fetchone()
    if not result:
        await message.answer("Участник не найден ")
    else:
        role, rating = result
        await message.answer(f"@{target_username} ({role}) имеет рейтинг {rating}/10 ⭐")

# --- список всех рейтингов ---
@dp.message(Command("all_ratings"))
async def all_ratings(message: Message):
    cur.execute("SELECT username, role, rating FROM users ORDER BY rating DESC")
    users = cur.fetchall()
    if not users:
        await message.answer("Пока нет зарегистрированных участников")
    else:
        text = "\n".join([f"@{u} ({r}) → {ra}/10" for u, r, ra in users])
        await message.answer("Рейтинги участников:\n" + text)

# --- изменение рейтинга (только админ) ---
@dp.message(Command("set_rating"))
async def set_rating(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У тебя нет прав ")
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Формат: /set_rating @username число")
        return

    target_username = args[1].lstrip("@")
    new_rating = int(args[2])

    cur.execute("UPDATE users SET rating = ? WHERE username = ?", (new_rating, target_username))
    conn.commit()

    await message.answer(f"Рейтинг @{target_username} теперь {new_rating}/10 ")

# --- запуск ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
