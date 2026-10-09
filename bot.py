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
user_states = {}

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

def cancel_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("❌ Отмена")
    return kb

def skip_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("⏭ Пропустить", "❌ Отмена")
    return kb

# ---------- Клавиатура листания каталога ----------
def catalog_nav_kb(idx, total):
    kb = types.InlineKeyboardMarkup(row_width=3)
    prev_btn = types.InlineKeyboardButton("⬅️", callback_data=f"nav_{idx-1}") if idx > 0 \
        else types.InlineKeyboardButton("·", callback_data="noop")
    next_btn = types.InlineKeyboardButton("➡️", callback_data=f"nav_{idx+1}") if idx < total - 1 \
        else types.InlineKeyboardButton("·", callback_data="noop")
    counter = types.InlineKeyboardButton(f"{idx+1}/{total}", callback_data="noop")
    kb.row(prev_btn, counter, next_btn)
    kb.row(types.InlineKeyboardButton("🛍 Купить", callback_data=f"buy_{idx}"))
    kb.row(types.InlineKeyboardButton("🏠 В меню", callback_data="close_catalog"))
    return kb

# ---------- Отправка одного товара ----------
def send_product(chat_id, idx, edit_message_id=None):
    data = load_data()
    products = data["products"]
    if not products:
        bot.send_message(chat_id, "Каталог пуст.", reply_markup=catalog_menu())
        return
    idx = max(0, min(idx, len(products) - 1))
    p = products[idx]
    caption = f"📦 {p['name']}\n💵 Цена: {p['price']} ₽"
    kb = catalog_nav_kb(idx, len(products))

    if edit_message_id:
        # Редактируем существующее сообщение
        try:
            if p.get("photo"):
                media = types.InputMediaPhoto(p["photo"], caption=caption)
                bot.edit_message_media(media, chat_id=chat_id, message_id=edit_message_id, reply_markup=kb)
            else:
                bot.edit_message_text(caption, chat_id=chat_id, message_id=edit_message_id, reply_markup=kb)
        except Exception:
            # Если редактировать нельзя (был текст, стал фото, или наоборот) — удаляем и отправляем заново
            try:
                bot.delete_message(chat_id, edit_message_id)
            except Exception:
                pass
            if p.get("photo"):
                bot.send_photo(chat_id, p["photo"], caption=caption, reply_markup=kb)
            else:
                bot.send_message(chat_id, caption, reply_markup=kb)
    else:
        if p.get("photo"):
            bot.send_photo(chat_id, p["photo"], caption=caption, reply_markup=kb)
        else:
            bot.send_message(chat_id, caption, reply_markup=kb)

# ---------- /start ----------
@bot.message_handler(commands=["start"])
def start(message):
    data = load_data()
    get_user(data, message.from_user.id)
    save_data(data)
    user_states.pop(message.from_user.id, None)
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
    bot.send_message(message.chat.id, "Введите сумму пополнения (₽):", reply_markup=cancel_kb())

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("state") == "topup",
                     content_types=["text"])
def topup_amount(message):
    if message.text == "❌ Отмена":
        user_states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=profile_menu())
        return
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
    bot.send_message(message.chat.id,
                     f"✅ Баланс пополнен на {amount} ₽\n💰 Текущий баланс: {u['balance']} ₽",
                     reply_markup=profile_menu())

# ---------- Каталог ----------
@bot.message_handler(func=lambda m: m.text == "🛒 Каталог")
def catalog(message):
    data = load_data()
    if not data["products"]:
        bot.send_message(message.chat.id, "Каталог пуст.", reply_markup=catalog_menu())
        return
    bot.send_message(message.chat.id, "🛒 Каталог товаров:", reply_markup=catalog_menu())
    send_product(message.chat.id, 0)

# ---------- Навигация по каталогу ----------
@bot.callback_query_handler(func=lambda c: c.data.startswith("nav_"))
def nav_product(call):
    idx = int(call.data.split("_")[1])
    bot.answer_callback_query(call.id)
    send_product(call.message.chat.id, idx, edit_message_id=call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data == "noop")
def noop(call):
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "close_catalog")
def close_catalog(call):
    bot.answer_callback_query(call.id)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    bot.send_message(call.message.chat.id, "Главное меню", reply_markup=main_menu())

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

    bot.send_message(call.message.chat.id,
                     f"✅ Вы купили: {product['name']}\n"
                     f"💵 Списано: {product['price']} ₽\n"
                     f"💰 Остаток баланса: {u['balance']} ₽")

    desc = product.get("description")
    if desc:
        bot.send_message(call.message.chat.id, f"📝 Описание:\n\n{desc}")

    deliver = product.get("deliver_photo")
    if deliver:
        bot.send_photo(call.message.chat.id, deliver, caption="🎁 Ваш товар:")
    else:
        bot.send_message(call.message.chat.id, "🎁 Товар выдан (фото не задано админом).")

# ---------- Назад ----------
@bot.message_handler(func=lambda m: m.text == "⬅️ Назад")
def back(message):
    user_states.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "Главное меню", reply_markup=main_menu())

# ---------- /add ----------
@bot.message_handler(commands=["add"])
def add_start(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У вас нет прав для добавления товаров.")
        return
    user_states[message.from_user.id] = {"state": "add_name", "data": {}}
    bot.send_message(message.chat.id,
                     "Шаг 1/5. Введите **название** товара:",
                     parse_mode="Markdown",
                     reply_markup=cancel_kb())

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("state") == "add_name",
                     content_types=["text"])
def add_name(message):
    if message.text == "❌ Отмена":
        user_states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu())
        return
    user_states[message.from_user.id]["data"]["name"] = message.text.strip()
    user_states[message.from_user.id]["state"] = "add_price"
    bot.send_message(message.chat.id, "Шаг 2/5. Введите **цену** (₽):",
                     parse_mode="Markdown", reply_markup=cancel_kb())

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("state") == "add_price",
                     content_types=["text"])
def add_price(message):
    if message.text == "❌ Отмена":
        user_states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu())
        return
    try:
        price = float(message.text.replace(",", ".").strip())
        if price < 0:
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ Введите число.")
        return
    user_states[message.from_user.id]["data"]["price"] = price
    user_states[message.from_user.id]["state"] = "add_desc"
    bot.send_message(message.chat.id,
                     "Шаг 3/5. Введите **описание** товара\n(оно отправится покупателю **после покупки**):",
                     parse_mode="Markdown", reply_markup=cancel_kb())

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("state") == "add_desc",
                     content_types=["text"])
def add_desc(message):
    if message.text == "❌ Отмена":
        user_states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu())
        return
    user_states[message.from_user.id]["data"]["description"] = message.text.strip()
    user_states[message.from_user.id]["state"] = "add_photo"
    bot.send_message(message.chat.id,
                     "Шаг 4/5. Отправьте **фото для витрины** (его увидят все в каталоге).\n"
                     "Или нажмите «⏭ Пропустить».",
                     parse_mode="Markdown", reply_markup=skip_kb())

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("state") == "add_photo",
                     content_types=["photo", "text"])
def add_photo(message):
    uid = message.from_user.id
    if message.content_type == "text":
        if message.text == "❌ Отмена":
            user_states.pop(uid, None)
            bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu())
            return
        if message.text == "⏭ Пропустить":
            user_states[uid]["data"]["photo"] = None
            user_states[uid]["state"] = "add_deliver"
            bot.send_message(message.chat.id,
                             "Шаг 5/5. Отправьте **фото-выдачу** — оно отправится покупателю **после покупки**.\n"
                             "Или нажмите «⏭ Пропустить».",
                             parse_mode="Markdown", reply_markup=skip_kb())
            return
        bot.send_message(message.chat.id, "⚠️ Отправьте фото или нажмите «⏭ Пропустить».")
        return

    user_states[uid]["data"]["photo"] = message.photo[-1].file_id
    user_states[uid]["state"] = "add_deliver"
    bot.send_message(message.chat.id,
                     "Шаг 5/5. Отправьте **фото-выдачу** — оно отправится покупателю **после покупки**.\n"
                     "Или нажмите «⏭ Пропустить».",
                     parse_mode="Markdown", reply_markup=skip_kb())

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("state") == "add_deliver",
                     content_types=["photo", "text"])
def add_deliver(message):
    uid = message.from_user.id
    d = user_states[uid]["data"]

    if message.content_type == "text":
        if message.text == "❌ Отмена":
            user_states.pop(uid, None)
            bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu())
            return
        if message.text == "⏭ Пропустить":
            d["deliver_photo"] = None
        else:
            bot.send_message(message.chat.id, "⚠️ Отправьте фото или нажмите «⏭ Пропустить».")
            return
    else:
        d["deliver_photo"] = message.photo[-1].file_id

    data = load_data()
    data["products"].append({
        "name": d["name"],
        "price": d["price"],
        "description": d["description"],
       )
 "photo": d.get("photo"),
        "del   iver_photo": d.get("deliver_photo")
    })
    save_data(data save)
    user_states.pop(uid, None)

    bot.send_message(message_data.chat.id,
                     f"✅ Това(dataр добавлен:\n\n"
                     f"📦 {d['name']}\n"
                     f"💵 {d['price']} ₽\n"
                     f"📝 Описание: {'есть' if d['description'] else '—'}\n"
                     f"🖼 Фото витрины: {'есть' if d.get('photo') else '—'}\n"
                     f"🎁 Фото-выдача: {'есть' if d.get('deliver_photo') else '—'}",
                     reply_markup=main_menu())

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
        has_photo = "🖼" if p.get("photo") else "—"
        has_deliver = "🎁" if p.get("deliver_photo") else "—"
        text += f"{i}. {p['name']} — {p['price']} ₽  {has_photo} {has_deliver}\n"
    bot.reply_to(message, text)

# ---------- /cancel ----------
@bot.message_handler(commands=["cancel"])
def cancel(message):
    user_states.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu())

# ---------- Запуск ----------
if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()