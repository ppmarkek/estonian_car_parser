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

bot = telebot.TeleBot(TOKEN)

subscribed_chats = set()
last_seen_hashes = set()

def create_session():
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 502, 503, 504 ])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session


def fetch_new_listings():
    session = create_session()
    try:
        response = session.get(URL, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        new_listings = []
        for el in soup.select('.result-row.item-odd.v-log.item-first'):
            data_hash = el.get('data-hsh', None)
            title = el.select('.description > .title > a > span')
            finance = el.select_one('.description > .finance > .pv > .price')
            extra_year = el.select_one('.description > .extra > .year')
            extra_mileage = el.select_one('.description > .extra > .mileage')
            extra_fuel = el.select_one('.description > .extra > .fuel')
            extra_transmission = el.select_one('.description > .extra > .transmission')
            extra_bodytype = el.select_one('.description > .extra > .bodytype')
            extra_drive = el.select_one('.description > .extra > .drive')
            link_element = el.select_one('a.row-link')
            if link_element and link_element.has_attr('href'):
                link_path = link_element['href']
                full_link = f"https://rus.auto24.ee{link_path}"
            else:
                full_link = "Ссылка не найдена"
            image_element = el.select_one('span.thumb')
            image_url = None
            if image_element:
                style_attr = image_element.get('style', '')
                match = re.search(r"url\('(.+?)'\)", style_attr)
            if match:
                image_url = match.group(1)

            if title and len(title) >= 4 and data_hash and data_hash not in last_seen_hashes:
                name = title[0].text.strip() if title[0] else ""
                model = title[2].text.strip() if title[2] else ""
                engine = title[3].text.strip() if title[3] else ""
                finance_info = finance.text.strip() if finance else "Финансы не указаны"
                year_info = extra_year.text.strip() if extra_year else ""
                mileage_info = extra_mileage.text.strip() if extra_mileage else ""
                fuel_info = extra_fuel.text.strip() if extra_fuel else ""
                transmission_info = extra_transmission.text.strip() if extra_transmission else ""
                bodytype_info = extra_bodytype.text.strip() if extra_bodytype else ""
                drive_info = extra_drive.text.strip() if extra_drive else ""

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
