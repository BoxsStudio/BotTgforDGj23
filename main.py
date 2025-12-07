import telebot
from telebot import types
import requests
import sqlite3

# ==========================================
# 👇 ВСТАВЬ СЮДА ТОКЕН
BOT_TOKEN = '7563995019:AAHoypRKD5OLC4MlvpzoaMxoP9LFdy09nfU'
# ==========================================

bot = telebot.TeleBot(BOT_TOKEN)


# --- 🗄 БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('weather.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_cities (
            user_id INTEGER,
            city_name TEXT
        )
    ''')
    conn.commit()
    conn.close()


def add_city(user_id, city):
    """
    Сохраняет город, автоматически делая Первую Букву Заглавной.
    """
    conn = sqlite3.connect('weather.db')
    cursor = conn.cursor()

    # .title() делает "москва" -> "Москва", "нью-йорк" -> "Нью-Йорк"
    city_formatted = city.strip().title()
    city_check = city_formatted.lower()

    # Проверяем дубликаты
    cursor.execute("SELECT city_name FROM user_cities WHERE user_id=?", (user_id,))
    rows = cursor.fetchall()

    for row in rows:
        if row[0].lower() == city_check:
            conn.close()
            return False  # Уже есть

    cursor.execute("INSERT INTO user_cities VALUES (?, ?)", (user_id, city_formatted))
    conn.commit()
    conn.close()
    return True


def get_user_cities(user_id):
    conn = sqlite3.connect('weather.db')
    cursor = conn.cursor()
    cursor.execute("SELECT city_name FROM user_cities WHERE user_id=?", (user_id,))
    cities = [row[0] for row in cursor.fetchall()]
    conn.close()
    return cities


def delete_city(user_id, city):
    conn = sqlite3.connect('weather.db')
    cursor = conn.cursor()
    # Удаляем без учета регистра, чтобы точно найти
    cursor.execute("DELETE FROM user_cities WHERE user_id=? AND lower(city_name)=?", (user_id, city.lower()))
    conn.commit()
    conn.close()


# --- ☁️ ПОГОДА ---
def check_city_exists(city):
    try:
        url = f"https://wttr.in/{city}?format=3"
        response = requests.get(url, timeout=3)
        return response.status_code == 200
    except:
        return False


def get_weather_data(city):
    url = f"https://wttr.in/{city}?M&lang=ru&format=%l:\n%c+%t\n💨+Ветер:+%w\n💦+Влажность:+%h"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text.strip()
        return "❌ Данные не найдены."
    except Exception as e:
        print(f"Ошибка погоды: {e}")
        return "❌ Ошибка соединения."


# --- ⌨️ МЕНЮ (ReplyKeyboardMarkup) ---

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Узнать погоду", "⭐ Мои города")
    markup.row("➕ Добавить город")
    return markup


def cities_menu(user_id):
    """Создает меню, где кнопки - это сохраненные города"""
    cities = get_user_cities(user_id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    # Добавляем кнопки городов (убеждаемся, что они с большой буквы)
    for city in cities:
        markup.add(types.KeyboardButton(city))

    markup.row("🗑 Удалить город", "🔙 Назад")
    return markup


# --- 📩 ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    init_db()
    bot.send_message(message.chat.id, "👋 Бот готов! Меню внизу.", reply_markup=main_menu())


# 1. Поиск погоды (один раз)
@bot.message_handler(func=lambda message: message.text == "🔍 Узнать погоду")
def ask_weather(message):
    msg = bot.send_message(message.chat.id, "✍️ Напишите название города:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, show_weather_once)


def show_weather_once(message):
    city = message.text
    print(f"📡 Запрос погоды: {city}")
    report = get_weather_data(city)
    bot.send_message(message.chat.id, report, reply_markup=main_menu())


# 2. Добавление города
@bot.message_handler(func=lambda message: message.text == "➕ Добавить город")
def ask_save(message):
    msg = bot.send_message(message.chat.id, "✍️ Введите название города (я сам исправлю регистр):",
                           reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, save_city_step)


def save_city_step(message):
    city = message.text
    # Проверяем существование
    if check_city_exists(city):
        # add_city внутри себя сделает .title() (С Большой Буквы)
        if add_city(message.from_user.id, city):
            formatted_name = city.strip().title()
            bot.send_message(message.chat.id, f"✅ Город **{formatted_name}** сохранен!", parse_mode="Markdown",
                             reply_markup=main_menu())
        else:
            bot.send_message(message.chat.id, f"ℹ️ Такой город уже есть.", reply_markup=main_menu())
    else:
        bot.send_message(message.chat.id, "❌ Город не найден. Проверьте название.", reply_markup=main_menu())


# 3. Меню Мои города
@bot.message_handler(func=lambda message: message.text == "⭐ Мои города")
def open_cities_menu(message):
    user_id = message.from_user.id
    cities = get_user_cities(user_id)

    if not cities:
        bot.send_message(message.chat.id, "📭 Список пуст. Добавьте города.", reply_markup=main_menu())
    else:
        bot.send_message(message.chat.id, "📂 Ваши города (выберите, чтобы узнать погоду):",
                         reply_markup=cities_menu(user_id))


# 4. Назад
@bot.message_handler(func=lambda message: message.text == "🔙 Назад")
def back_to_main(message):
    bot.send_message(message.chat.id, "Главное меню", reply_markup=main_menu())


# 5. Удаление города
@bot.message_handler(func=lambda message: message.text == "🗑 Удалить город")
def ask_delete(message):
    msg = bot.send_message(message.chat.id, "👇 Нажмите на кнопку с городом, который хотите удалить:")
    bot.register_next_step_handler(msg, delete_city_step)


def delete_city_step(message):
    city = message.text
    if city == "🔙 Назад":
        back_to_main(message)
        return

    # Удаляем
    delete_city(message.from_user.id, city)
    print(f"🗑 Удален город: {city}")

    # Показываем обновленное меню
    bot.send_message(message.chat.id, f"✅ Город {city} удален.", reply_markup=cities_menu(message.from_user.id))


# 6. Обработка нажатия на кнопку с именем города
@bot.message_handler(content_types=['text'])
def check_text_for_city(message):
    user_id = message.from_user.id
    cities = get_user_cities(user_id)

    # Если текст сообщения совпадает с одним из сохраненных городов
    if message.text in cities:
        city = message.text
        print(f"📡 Запрос погоды из меню для: {city}")
        report = get_weather_data(city)
        bot.send_message(message.chat.id, report)
    else:
        bot.send_message(message.chat.id, "Я не понимаю команду. Используйте меню.")


if __name__ == '__main__':
    init_db()
    print("✅ Бот запущен (Города с Большой Буквы)")
    bot.infinity_polling()