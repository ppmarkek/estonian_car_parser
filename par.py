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
CHECK_INTERVAL = 1

bot = telebot.TeleBot(TOKEN)

subscribed_chats = set()
last_seen_hashes = set()

def create_session(proxy=None):
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.2 Safari/605.1.15'
    })
    if proxy:
        session.proxies.update(proxy)
    return session

proxy_list = [
    {"http": "http://148.230.206.229:8080", "https": "https://148.230.206.229:8080"},
    {"http": "http://185.201.8.166:80", "https": "https://185.201.8.166:80"},
    {"http": "http://195.138.73.54:44017", "https": "https://195.138.73.54:44017"},
    {"http": "http://93.123.22.151:80", "https": "https://93.123.22.151:80"},
    {"http": "http://103.84.177.35:8083", "https": "https://103.84.177.35:8083"},
    {"http": "http://197.98.201.97:10642", "https": "https://197.98.201.97:10642"},
    {"http": "http://103.28.112.126:8080", "https": "https://103.28.112.126:8080"},
    {"http": "http://220.248.70.237:9002", "https": "https://220.248.70.237:9002"},
    {"http": "http://188.34.179.101:80", "https": "https://188.34.179.101:80"},
    {"http": "http://112.30.155.83:12792", "https": "https://112.30.155.83:12792"},
    {"http": "http://121.236.236.33:8089", "https": "https://121.236.236.33:8089"},
    {"http": "http://94.131.107.45:3128", "https": "https://94.131.107.45:3128"},
    {"http": "http://38.52.222.242:999", "https": "https://38.52.222.242:999"},
    {"http": "http://36.6.145.236:8089", "https": "https://36.6.145.236:8089"},
]

def fetch_new_listings():
    for proxy in proxy_list:
        session = create_session(proxy)
        try:
            response = session.get(URL, headers=HEADERS)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            new_listings = []

            current_hashes = {el.get('data-hsh') for el in soup.select('.result-row.item-odd.v-log.item-first') if el.get('data-hsh')}

            new_hashes = current_hashes.difference(last_seen_hashes)
            removed_hashes = last_seen_hashes.difference(current_hashes)

            last_seen_hashes.difference_update(removed_hashes)
            last_seen_hashes.update(new_hashes)

            for el in soup.select('.result-row.item-odd.v-log.item-first'):
                data_hash = el.get('data-hsh', None)
                if data_hash in new_hashes:
                    title = el.select('.description > .title > a > span')
                    finance = el.select_one('.description > .finance > .pv > .price')
                    extra_year = el.select_one('.description > .extra > .year')
                    extra_mileage = el.select_one('.description > .extra > .mileage')
                    extra_fuel = el.select_one('.description > .extra > .fuel')
                    extra_transmission = el.select_one('.description > .extra > .transmission')
                    extra_bodytype = el.select_one('.description > .extra > .bodytype')
                    extra_drive = el.select_one('.description > .extra > .drive')
                    link_element = el.select_one('a.row-link')
                    full_link = f"https://rus.auto24.ee{link_element['href']}" if link_element and link_element.has_attr('href') else "Ссылка не найдена"

                    image_element = el.select_one('span.thumb')
                    image_url = None
                    if image_element:
                        style_attr = image_element.get('style', '')
                        match = re.search(r"url\('(.+?)'\)", style_attr)
                        if match:
                            image_url = match.group(1)

                    if title and len(title) >= 4:
                        listing_info = {
                            'name': title[0].text.strip() if title[0] else "",
                            'model': title[2].text.strip() if title[2] else "",
                            'engine': title[3].text.strip() if title[3] else "",
                            'finance_info': finance.text.strip() if finance else "Финансы не указаны",
                            'year_info': extra_year.text.strip() if extra_year else "",
                            'mileage_info': extra_mileage.text.strip() if extra_mileage else "",
                            'fuel_info': extra_fuel.text.strip() if extra_fuel else "",
                            'transmission_info': extra_transmission.text.strip() if extra_transmission else "",
                            'bodytype_info': extra_bodytype.text.strip() if extra_bodytype else "",
                            'drive_info': extra_drive.text.strip() if extra_drive else "",
                            'link': full_link,
                            'image_url': image_url
                        }
                        new_listings.append(listing_info)
            return new_listings
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print("403 ошибка, смена прокси")
            time.sleep(10)
        except requests.RequestException as e:
            print(f"Ошибка при запросе: {e}")



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
