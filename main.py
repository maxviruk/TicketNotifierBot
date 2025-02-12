import os
import time
import logging
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import schedule
from datetime import datetime, timedelta
from dotenv import load_dotenv
import subprocess

# Настроим логгер
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Проверяем установленные пакеты
try:
    result = subprocess.run(["pip", "list"], capture_output=True, text=True)
    logging.info(f"📦 Установленные пакеты:\n{result.stdout}")
except Exception as e:
    logging.error(f"Ошибка при получении списка пакетов: {e}")

# Загружаем переменные окружения
logging.info("🛠️ Загружаем .env...")
load_dotenv()
logging.info("✅ Переменные .env загружены.")

# Параметры поиска билетов
STATION_FROM = os.getenv("STATION_FROM")
STATION_TO = os.getenv("STATION_TO")
TRAINS = os.getenv("TRAINS", "").split(",")
START_DATE = os.getenv("START_DATE")
CLASS_ID = "К"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Проверяем и выведем загруженные переменные окружения (безопасно) переменные окружения
logging.info(f"🔍 STATION_FROM: {STATION_FROM}, STATION_TO: {STATION_TO}, TRAINS: {TRAINS}, START_DATE: {START_DATE}")
logging.info(f"🔍 TELEGRAM_BOT_TOKEN: {bool(TELEGRAM_BOT_TOKEN)}, TELEGRAM_CHAT_ID: {TELEGRAM_CHAT_ID}")

# logging.info(f"STATION_FROM: {STATION_FROM}")
# logging.info(f"STATION_TO: {STATION_TO}")
# logging.info(f"TRAINS: {TRAINS}")
# logging.info(f"START_DATE: {START_DATE}")
# logging.info(f"TELEGRAM_CHAT_ID: {bool(TELEGRAM_CHAT_ID)}")  # Покажет True, если переменная загружена
# logging.info(f"TELEGRAM_BOT_TOKEN: {bool(TELEGRAM_BOT_TOKEN)}")  # Аналогично


def check_env_vars():
    required_vars = ["STATION_FROM", "STATION_TO", "TRAINS", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "START_DATE"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logging.error(f"❌ Отсутствуют переменные окружения: {', '.join(missing_vars)}")
        exit(1)

check_env_vars()

def get_ticket_info(date, retries=3):
    url = f"https://booking.uz.gov.ua/search-trips/{STATION_FROM}/{STATION_TO}/list?startDate={date}"
    headers = {"User-Agent": "Mozilla/5.0"}
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            return parse_tickets(soup, date)
        except requests.RequestException as e:
            logging.error(f"Ошибка запроса (попытка {attempt + 1}): {e}")
            time.sleep(5)
    return []

def parse_tickets(soup, date):
    tickets = []
    for trip in soup.find_all("div", class_="trip"):
        train_number_tag = trip.find("div", class_="train-number")
        if not train_number_tag:
            continue
        train_number = train_number_tag.text.strip()
        if train_number not in TRAINS:
            continue
        for link in trip.find_all("a", class_="class-link"):
            href = link.get("href", "")
            if CLASS_ID in href:
                seat_text = link.text.strip()
                try:
                    available_seats = int(seat_text.split()[0])
                except ValueError:
                    continue
                if available_seats > 0:
                    tickets.append({"train": train_number, "date": date, "link": f"https://booking.uz.gov.ua{href}"})
    return tickets

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Ошибка отправки в Telegram: {e}")

def check_tickets():
    logging.info("🔍 Проверяем билеты...")
    found_tickets = []
    start_date = datetime.strptime(START_DATE, "%Y-%m-%d")
    dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6)]
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(get_ticket_info, date): date for date in dates}
        for future in futures:
            tickets = future.result()
            if tickets:
                found_tickets.extend(tickets)
    if found_tickets:
        message = "🚆 Найдены билеты:\n"
        for ticket in found_tickets:
            message += f"Поезд {ticket['train']} ({ticket['date']})\nСсылка: {ticket['link']}\n\n"
        for chunk in [message[i:i+4096] for i in range(0, len(message), 4096)]:
            send_telegram_message(chunk)
            time.sleep(1)
        logging.info("✅ Найдены билеты! Уведомление отправлено.")
    else:
        logging.info("❌ Нижних мест нет.")

schedule.every(10).minutes.do(check_tickets)

if __name__ == "__main__":
    logging.info("🚀 Скрипт запущен!")
    while True:
        logging.info("⏳ Ожидание...")
        schedule.run_pending()
        time.sleep(60)
