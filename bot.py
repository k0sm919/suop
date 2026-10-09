import telebot
from telebot import types
import json
import os

# ---------- Настройки ----------
TOKEN = os.getenv("TOKEN", "ВСТАВЬ_СЮДА_ТОКЕН_БОТА")
ADMIN_ID = 6719518185

bot = telebot.TeleBot(TOKEN)
DATA_FILE = "data.json"

# ---------- Работа с данными ----------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"products": [], "users": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(data, uid):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = {"balance": 0, "purchases": 0}
    return data["users"][uid]

# ---------- Состояния ----------
user_states = {}  # uid -> {"state": "..."}

# ---------- Клавиатуры ----------
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("👤 Профиль", "🛒 Каталог")
    return kb

def profile_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 Баланс", "📦 Кол-во покупок")
    kb.add("➕ Пополнить баланс")
    kb.add("⬅️ Назад")
    return kb

def catalog_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("⬅️ Назад")
    return kb

# ---------- /start ----------
@bot.message_handler(commands=["start"])
def start(message):
    data = load_data()
    get_user(data, message.from_user.id)
    save_data(data)
    bot.send_message(message.chat.id, "Главное меню", reply_markup=main_menu())

# ---------- Профиль ----------
@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    bot.send_message(message.chat.id, "Профиль", reply_markup=profile_menu())

@bot.message_handler(func=lambda m: m.text == "💰 Баланс")
def balance(message):
    data = load_data()
    u = get_user(data, message.from_user.id)
    save_data(data)
    bot.send_message(message.chat.id, f"💰 Ваш баланс: {u['balance']} ₽")

@bot.message_handler(func=lambda m: m.text == "📦 Кол-во покупок")
def purchases(message):
    data = load_data()
    u = get_user(data, message.from_user.id)
    save_data(data)
    bot.send_message(message.chat.id, f"📦 Количество покупок: {u['purchases']}")

# ---------- Пополнение баланса ----------
@bot.message_handler(func=lambda m: m.text == "➕ Пополнить баланс")
def topup_start(message):
    user_states[message.from_user.id] = {"state": "topup"}
    bot.send_message(
        message.chat.id,
        "Введите сумму пополнения (₽):",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(
    func=lambda m: user_states.get(m.from_user.id, {}).get("state") == "topup",
    content_types=["text"]
)
def topup_amount(message):
    try:
        amount = float(message.text.replace(",", ".").strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ Введите положительное число.")
        return

    data = load_data()
    u = get_user(data, message.from_user.id)
    u["balance"] += amount
    save_data(data)
    user_states.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        f"✅ Баланс пополнен на {amount} ₽\n💰 Текущий баланс: {u['balance']} ₽",
        reply_markup=profile_menu()
    )

# ---------- Каталог ----------
@bot.message_handler(func=lambda m: m.text == "🛒 Каталог")
def catalog(message):
    data = load_data()
    products = data["products"]
    if not products:
        bot.send_message(message.chat.id, "Каталог пуст.", reply_markup=catalog_menu())
        return

    bot.send_message(message.chat.id, "🛒 Каталог товаров:", reply_markup=catalog_menu())
    for i, p in enumerate(products):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🛍 Купить", callback_data=f"buy_{i}"))
        caption = f"📦 {p['name']}\n💵 Цена: {p['price']} ₽"
        if p.get("photo"):
            bot.send_photo(message.chat.id, p["photo"], caption=caption, reply_markup=kb)
        else:
            bot.send_message(message.chat.id, caption, reply_markup=kb)

# ---------- Покупка ----------
@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def buy_product(call):
    idx = int(call.data.split("_")[1])
    data = load_data()
    if idx >= len(data["products"]):
        bot.answer_callback_query(call.id, "Товар не найден.")
        return
    product = data["products"][idx]
    u = get_user(data, call.from_user.id)

    if u["balance"] < product["price"]:
        bot.answer_callback_query(call.id, "❌ Недостаточно средств.", show_alert=True)
        return

    u["balance"] -= product["price"]
    u["purchases"] += 1
    save_data(data)

    bot.answer_callback_query(call.id, "✅ Покупка совершена!")
    bot.send_message(
        call.message.chat.id,
        f"✅ Вы купили: {product['name']}\n"
        f"💵 Списано: {product['price']} ₽\n"
        f"💰 Остаток баланса: {u['balance']} ₽"
    )

# ---------- Назад ----------
@bot.message_handler(func=lambda m: m.text == "⬅️ Назад")
def back(message):
    user_states.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "Главное меню", reply_markup=main_menu())

# ---------- /add ----------
@bot.message_handler(commands=["add"])
def add_product(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У вас нет прав для добавления товаров.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or "|" not in parts[1]:
        bot.reply_to(
            message,
            "Использование: /add Название | Цена\nПример: /add iPhone 15 | 79999"
        )
        return

    name, price = parts[1].split("|", 1)
    name = name.strip()
    try:
        price = float(price.replace(",", ".").strip())
    except ValueError:
        bot.reply_to(message, "⚠️ Цена должна быть числом.")
        return

    data = load_data()
    data["products"].append({"name": name, "price": price, "photo": None})
    save_data(data)

    bot.reply_to(
        message,
        f"✅ Товар добавлен:\n{name} — {price} ₽\n\n"
        f"📸 Можешь отправить фото товара следующим сообщением, чтобы прикрепить его."
    )

# ---------- /del ----------
@bot.message_handler(commands=["del"])
def del_product(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У вас нет прав.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        bot.reply_to(message, "Использование: /del НОМЕР\nНомера смотри в /list")
        return
    idx = int(parts[1]) - 1
    data = load_data()
    if idx < 0 or idx >= len(data["products"]):
        bot.reply_to(message, "⚠️ Товар с таким номером не найден.")
        return
    removed = data["products"].pop(idx)
    save_data(data)
    bot.reply_to(message, f"🗑 Удалён товар: {removed['name']}")

# ---------- /list ----------
@bot.message_handler(commands=["list"])
def list_products(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У вас нет прав.")
        return
    data = load_data()
    if not data["products"]:
        bot.reply_to(message, "Каталог пуст.")
        return
    text = "📋 Список товаров:\n\n"
    for i, p in enumerate(data["products"], 1):
        photo = "📸" if p.get("photo") else "—"
        text += f"{i}. {p['name']} — {p['price']} ₽  {photo}\n"
    bot.reply_to(message, text)

# ---------- Приём фото (для последнего товара) ----------
@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    if message.from_user.id != ADMIN_ID:
        return
    data = load_data()
    if not data["products"]:
        bot.reply_to(message, "Сначала добавь товар через /add")
        return
    file_id = message.photo[-1].file_id
    data["products"][-1]["photo"] = file_id
    save_data(data)
    bot.reply_to(message, f"📸 Фото прикреплено к товару: {data['products'][-1]['name']}")

# ---------- Запуск ----------
if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()