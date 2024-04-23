import requests
from bs4 import BeautifulSoup
import telebot
from telebot import types
import time
import threading
import re
import tkinter as tk
from tkinter import messagebox

URL = 'https://rus.auto24.ee/kasutatud/nimekiri.php?bn=2&a=100&ae=1&af=50&otsi=%D0%BF%D0%BE%D0%B8%D1%81%D0%BA20(31878)&ak=0'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'
}

TOKEN = '7055872752:AAF9oKANnV51UkgzPVoNkI8rQKkg5V7s5DQ'
CHECK_INTERVAL = 1

bot = telebot.TeleBot(TOKEN)
subscribed_chats = set()
last_seen_hashes = set()

stop_thread = False
status_label = None

def fetch_new_listings():
    while not stop_thread:
        try:
            response = requests.get(URL, headers=HEADERS)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            new_listings = []
            for el in soup.select('.result-row.item-odd.v-log.item-first'):
                data_hash = el.get('data-hsh', None)
                if data_hash in last_seen_hashes:
                    continue

                title_elements = el.select('.description > .title > a > span')
                if title_elements and len(title_elements) >= 4:
                    name = title_elements[0].text.strip()
                    model = title_elements[2].text.strip()
                    engine = title_elements[3].text.strip()
                else:
                    continue  # Skip if essential info is missing

                finance = el.select_one('.description > .finance > .pv > .price')
                finance_info = finance.text.strip() if finance else "Финансы не указаны"

                extra_elements = el.select('.description > .extra > span')
                year_info = extra_elements[0].text.strip() if extra_elements else ""
                mileage_info = extra_elements[1].text.strip() if extra_elements else ""
                fuel_info = extra_elements[2].text.strip() if extra_elements else ""
                transmission_info = extra_elements[3].text.strip() if extra_elements else ""
                bodytype_info = extra_elements[4].text.strip() if extra_elements else ""
                drive_info = extra_elements[5].text.strip() if extra_elements else ""

                link_element = el.select_one('a.row-link')
                full_link = f"https://rus.auto24.ee{link_element['href']}" if link_element else "Ссылка не найдена"

                image_element = el.select_one('span.thumb')
                image_url = None
                if image_element:
                    style_attr = image_element.get('style', '')
                    match = re.search(r"url\('(.+?)'\)", style_attr)
                    if match:
                        image_url = match.group(1)

                listing_info = {
                    'name': name,
                    'model': model,
                    'engine': engine,
                    'finance_info': finance_info,
                    'year_info': year_info,
                    'mileage_info': mileage_info,
                    'fuel_info': fuel_info,
                    'transmission_info': transmission_info,
                    'bodytype_info': bodytype_info,
                    'drive_info': drive_info,
                    'link': full_link,
                    'image_url': image_url
                }
                new_listings.append(listing_info)
                last_seen_hashes.add(data_hash)

            if new_listings:
                notify_subscribers(new_listings)
            time.sleep(CHECK_INTERVAL)
        except requests.RequestException as e:
            print(f"Error fetching listings: {e}")
            time.sleep(CHECK_INTERVAL)

def notify_subscribers(listings):
    for chat_id in subscribed_chats:
        for listing in listings:
            message_text = (f"{listing['name']} {listing['model']} {listing['engine']}\n"
                            f"{listing['finance_info']}\n"
                            f"{listing['year_info']} | {listing['mileage_info']} | {listing['fuel_info']} | "
                            f"{listing['transmission_info']} | {listing['bodytype_info']} | {listing['drive_info']}\n"
                            f"Ссылка: {listing['link']}")
            if listing['image_url']:
                bot.send_photo(chat_id, photo=listing['image_url'], caption=message_text)
            else:
                bot.send_message(chat_id, message_text)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    subscribe_button = types.KeyboardButton('Подписаться')
    unsubscribe_button = types.KeyboardButton('Отписаться')
    markup.add(subscribe_button, unsubscribe_button)
    bot.send_message(message.chat.id, "Привет! Чтобы подписаться или отписаться, используйте кнопки ниже.", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == 'Подписаться')
def subscribe(message):
    chat_id = message.chat.id
    if chat_id not in subscribed_chats:
        subscribed_chats.add(chat_id)
        bot.send_message(chat_id, "Вы подписались на уведомления о новых автомобильных листингах.")
    else:
        bot.send_message(chat_id, "Вы уже подписаны.")

@bot.message_handler(func=lambda message: message.text == 'Отписаться')
def unsubscribe(message):
    chat_id = message.chat.id
    if chat_id in subscribed_chats:
        subscribed_chats.remove(chat_id)
        bot.send_message(chat_id, "Вы отписались от уведомлений.")

def bot_polling():
    try:
        bot.polling(non_stop=True)
    finally:
        bot.stop_polling()

def start_bot():
    global stop_thread, status_label
    stop_thread = False
    threading.Thread(target=bot_polling).start()
    threading.Thread(target=fetch_new_listings).start()
    if status_label:
        status_label.config(text="Bot is running", fg="green")

def stop_bot():
    global stop_thread, status_label
    stop_thread = True
    print("Bot stopped")
    if status_label:
        status_label.config(text="Bot is stopped", fg="red")

def create_gui():
    global status_label
    root = tk.Tk()
    root.title("Telegram Bot Controller")

    start_button = tk.Button(root, text="Start Bot", command=start_bot, bg='green', fg='white')
    start_button.pack(pady=20, padx=20)

    stop_button = tk.Button(root, text="Stop Bot", command=stop_bot, bg='red', fg='white')
    stop_button.pack(pady=20, padx=20)

    status_label = tk.Label(root, text="Bot is stopped", fg="red")
    status_label.pack(pady=10)

    root.mainloop()

if __name__ == '__main__':
    create_gui()