import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import telebot
from telebot import types
import time
import threading
import re

URL = 'https://rus.auto24.ee/kasutatud/nimekiri.php?bn=2&a=100&ae=1&af=50&otsi=%D0%BF%D0%BE%D0%B8%D1%81%D0%BA20(31878)&ak=0'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

TOKEN = '7055872752:AAF9oKANnV51UkgzPVoNkI8rQKkg5V7s5DQ'
CHECK_INTERVAL = 5
MAX_HASHES = 1000 

bot = telebot.TeleBot(TOKEN)
subscribed_chats = set()
last_seen_hashes = set()

def create_session():
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def fetch_new_listings():
    session = create_session()
    try:
        response = session.get(URL, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        new_listings = []
        current_hashes = {el.get('data-hsh') for el in soup.select('.result-row.item-odd.v-log.item-first') if el.get('data-hsh')}
        new_hashes = current_hashes.difference(last_seen_hashes)
        removed_hashes = last_seen_hashes.difference(current_hashes)

        # Обновляем last_seen_hashes
        last_seen_hashes.symmetric_difference_update(removed_hashes)
        last_seen_hashes.update(new_hashes)

        # Управление размером last_seen_hashes
        if len(last_seen_hashes) > MAX_HASHES:
            last_seen_hashes = set(list(last_seen_hashes)[:MAX_HASHES])

        # Обработка новых объявлений
        for el in soup.select('.result-row.item-odd.v-log.item-first'):
            data_hash = el.get('data-hsh', None)
            if data_hash in new_hashes:
                # Собираем информацию о новых объявлениях (схема парсинга как в исходном коде)
                # ...
                new_listings.append(listing_info)

        return new_listings
    except requests.RequestException as e:
        print(f"Ошибка при получении списка: {e}")
        return []

def notify_subscribers(listings):
    for chat_id in subscribed_chats:
        for listing in listings:
            message_text = (f"{listing['name']} {listing['model']} {listing['engine']}\n"
                            f"{listing['finance_info']}\n"
                            f"{listing['year_info']} | {listing['mileage_info']} | {listing['fuel_info']} | "
                            f"{listing['transmission_info']} | {listing['bodytype_info']} | {listing['drive_info']}\n"
                            f"Ссылка: {listing['link']}")
            if listing.get('image_url'):
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
        bot.send_message(chat_id, "Вы уже подписаны на уведомления.")

@bot.message_handler(func=lambda message: message.text == 'Отписаться')
def unsubscribe(message):
    chat_id = message.chat.id
    if chat_id in subscribed_chats:
        subscribed_chats.remove(chat_id)
        bot.send_message(chat_id, "Вы отписались от уведомлений о автомобильных листингах.")
    else:
        bot.send_message(chat_id, "Вы не были подписаны на уведомления.")

def schedule_fetch():
    while True:
        new_listings = fetch_new_listings()
        if new_listings:
            notify_subscribers(new_listings)
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    thread = threading.Thread(target=schedule_fetch)
    thread.start()
    bot.polling(non_stop=True)