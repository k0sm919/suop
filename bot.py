import telebot
from telebot import types
import json
import os

TOKEN = os.getenv("TOKEN", "ВСТАВЬ_СЮДА_ТОКЕН_БОТА")
ADMIN_ID = 6719518185

bot = telebot.TeleBot(TOKEN)
DATA_FILE = "data.json"


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


user_states = {}


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


def catalog_nav_kb(idx, total):
    kb = types.InlineKeyboardMarkup(row_width=3)
    if idx > 0:
        prev_btn = types.InlineKeyboardButton("⬅️", callback_data="nav_" + str(idx - 1))
    else:
        prev_btn = types.InlineKeyboardButton("·", callback_data="noop")

    if idx < total - 1:
        next_btn = types.InlineKeyboardButton("➡️", callback_data="nav_" + str(idx + 1))
    else:
        next_btn = types.InlineKeyboardButton("·", callback_data="noop")

    counter = types.InlineKeyboardButton(str(idx + 1) + "/" + str(total), callback_data="noop")
    kb.row(prev_btn, counter, next_btn)
    kb.row(types.InlineKeyboardButton("🛍 Купить", callback_data="buy_" + str(idx)))
    kb.row(types.InlineKeyboardButton("🏠 В меню", callback_data="close_catalog"))
    return kb


def send_product(chat_id, idx, edit_message_id=None):
    data = load_data()
    products = data["products"]
    if not products:
        bot.send_message(chat_id, "Каталог пуст.", reply_markup=catalog_menu())
        return

    if idx < 0:
        idx = 0
    if idx > len(products) - 1:
        idx = len(products) - 1

    p = products[idx]
    caption = "📦 " + p["name"] + "\n💵 Цена: " + str(p["price"]) + " ₽"
    kb = catalog_nav_kb(idx, len(products))

    if edit_message_id is not None:
        try:
            if p.get("photo"):
                media = types.InputMediaPhoto(p["photo"], caption=caption)
                bot.edit_message_media(media, chat_id=chat_id,
                                       message_id=edit_message_id, reply_markup=kb)
            else:
                bot.edit_message_text(caption, chat_id=chat_id,
                                      message_id=edit_message_id, reply_markup=kb)
            return
        except Exception:
            try:
                bot.delete_message(chat_id, edit_message_id)
            except Exception:
                pass

    if p.get("photo"):
        bot.send_photo(chat_id, p["photo"], caption=caption, reply_markup=kb)
    else:
        bot.send_message(chat_id, caption, reply_markup=kb)


@bot.message_handler(commands=["start"])
def start(message):
    data = load_data()
    get_user(data, message.from_user.id)
    save_data(data)
    user_states.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "Главное меню", reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    bot.send_message(message.chat.id, "Профиль", reply_markup=profile_menu())


@bot.message_handler(func=lambda m: m.text == "💰 Баланс")
def balance(message):
    data = load_data()
    u = get_user(data, message.from_user.id)
    save_data(data)
    bot.send_message(message.chat.id, "💰 Ваш баланс: " + str(u["balance"]) + " ₽")


@bot.message_handler(func=lambda m: m.text == "📦 Кол-во покупок")
def purchases(message):
    data = load_data()
    u = get_user(data, message.from_user.id)
    save_data(data)
    bot.send_message(message.chat.id, "📦 Количество покупок: " + str(u["purchases"]))


@bot.message_handler(func=lambda m: m.text == "➕ Пополнить баланс")
def topup_start(message):
    user_states[message.from_user.id] = {"state": "topup", "data": {}}
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
    u["balance"] = u["balance"] + amount
    save_data(data)
    user_states.pop(message.from_user.id, None)
    bot.send_message(message.chat.id,
                     "✅ Баланс пополнен на " + str(amount) + " ₽\n💰 Текущий баланс: " + str(u["balance"]) + " ₽",
                     reply_markup=profile_menu())


@bot.message_handler(func=lambda m: m.text == "🛒 Каталог")
def catalog(message):
    data = load_data()
    if not data["products"]:
        bot.send_message(message.chat.id, "Каталог пуст.", reply_markup=catalog_menu())
        return
    bot.send_message(message.chat.id, "🛒 Каталог товаров:", reply_markup=catalog_menu())
    send_product(message.chat.id, 0)


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
    u["balance"] = u["balance"] - product["price"]
    u["purchases"] = u["purchases"] + 1
    save_data(data)
    bot.answer_callback_query(call.id, "✅ Покупка совершена!")
    bot.send_message(call.message.chat.id,
                     "✅ Вы купили: " + product["name"] + "\n"
                     "💵 Списано: " + str(product["price"]) + " ₽\n"
                     "💰 Остаток баланса: " + str(u["balance"]) + " ₽")
    desc = product.get("description")
    if desc:
        bot.send_message(call.message.chat.id, "📝 Описание:\n\n" + desc)
    deliver = product.get("deliver_photo")
    if deliver:
        bot.send_photo(call.message.chat.id, deliver, caption="🎁 Ваш товар:")
    else:
        bot.send_message(call.message.chat.id, "🎁 Товар выдан (без фото).")


@bot.message_handler(func=lambda m: m.text == "⬅️ Назад")
def back(message):
    user_states.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "Главное меню", reply_markup=main_menu())


@bot.message_handler(commands=["add"])
def add_start(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У вас нет прав для добавления товаров.")
        return
    user_states[message.from_user.id] = {"state": "add_name", "data": {}}
    bot.send_message(message.chat.id,
                     "Шаг 1/5. Введите название товара:",
                     reply_markup=cancel_kb())


@bot.message_handler(func=lambda m: user       _states.get(m.from user_user.id, {}).get_st("state") == "add_name",
                     content_types=["atestext"])
def add_name(message):
    if.pop message.text == "❌ Отмена":
(message.from_user.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu())
        return
    user_states[message.from_user.id]["data"]["name"] = message.text.strip()
    user_states[message.from_user.id]["state"] = "add_price"
    bot.send_message(message.chat.id, "Шаг 2/5. Введите цену (₽):", reply_markup=cancel_kb())


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
                     "Шаг 3/5. Введите описание товара\n(отправится покупателю после покупки):",
                     reply_markup=cancel_kb())


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
                     "Шаг 4/5. Отправьте фото для витрины (его увидят все в каталоге).\n"
                     "Или нажмите «⏭ Пропустить».",
                     reply_markup=skip_kb())


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
                             "Шаг 5/5. Отправьте фото-выдачу — оно придёт покупателю после покупки.\n"
                             "Или нажмите «⏭ Пропустить».",
                             reply_markup=skip_kb())
            return
        bot.send_message(message.chat.id, "⚠️ Отправьте фото или нажмите «⏭ Пропустить».")
        return
    user_states[uid]["data"]["photo"] = message.photo[-1].file_id
    user_states[uid]["state"] = "add_deliver"
    bot.send_message(message.chat.id,
                     "Шаг 5/5. Отправьте фото-выдачу — оно придёт покупателю после покупки.\n"
                     "Или нажмите «⏭ Пропустить».",
                     reply_markup=skip_kb())


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
    new_product = {
        "name": d["name"],
        "price": d["price"],
        "description": d["description"],
        "photo": d.get("photo"),
        "deliver_photo": d.get("deliver_photo")
    }
    data["products"].append(new_product)
    save_data(data)
    user_states.pop(uid, None)

    bot.send_message(message.chat.id,
                     "✅ Товар добавлен:\n\n"
                     "📦 " + d["name"] + "\n"
                     "💵 " + str(d["price"]) + " ₽",
                     reply_markup=main_menu())


@bot.message_handler(commands=["del"])
def del_product(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У вас нет прав.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        bot.reply_to(message, "Использование: /del НОМЕР")
        return
    idx = int(parts[1]) - 1
    data = load_data()
    if idx < 0 or idx >= len(data["products"]):
        bot.reply_to(message, "⚠️ Товар не найден.")
        return
    removed = data["products"].pop(idx)
    save_data(data)
    bot.reply_to(message, "🗑 Удалён товар: " + removed["name"])


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
        text = text + str(i) + ". " + p["name"] + " — " + str(p["price"]) + " ₽\n"
    bot.reply_to(message, text)


@bot.message_handler(commands=["cancel"])
def cancel(message):
    user_states.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu())


if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()