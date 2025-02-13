import os
import time
import logging
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import schedule
from datetime import datetime, timedelta
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Настроим логгер
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Проверяем установленные пакеты
try:
    result = subprocess.run(["pip", "list"], capture_output=True, text=True)
    logging.info(f"\U0001F4E6 Установленные пакеты:\n{result.stdout}")
except Exception as e:
    logging.error(f"Ошибка при получении списка пакетов: {e}")

# Загружаем переменные окружения
STATION_FROM = os.getenv("STATION_FROM")
STATION_TO = os.getenv("STATION_TO")
TRAINS = os.getenv("TRAINS", "").split(",")
START_DATE = os.getenv("START_DATE")
CLASS_ID = os.getenv("CLASS_ID", "К")  # Добавлен параметр для выбора типа места
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Проверка наличия переменных окружения
def check_env_vars():
    required_vars = ["STATION_FROM", "STATION_TO", "TRAINS", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "START_DATE"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logging.error(f"❌ Отсутствуют переменные окружения: {', '.join(missing_vars)}")
        exit(1)

check_env_vars()
logging.info(f"🔍 STATION_FROM: {STATION_FROM}, STATION_TO: {STATION_TO}, TRAINS: {TRAINS}, START_DATE: {START_DATE}")
logging.info(f"🔍 TELEGRAM_BOT_TOKEN: {bool(TELEGRAM_BOT_TOKEN)}, TELEGRAM_CHAT_ID: {bool(TELEGRAM_CHAT_ID)}")

# Указываем путь к ChromeDriver
chrome_driver_path = "/usr/local/bin/chromedriver"  # Используем локально установленный ChromeDriver

# Настройка опций для Chrome
chrome_options = Options()
chrome_options.add_argument("--headless")  # Безголовый режим
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# Инициализация WebDriver
driver = webdriver.Chrome(service=Service(chrome_driver_path), options=chrome_options)

# Получение информации о билетах
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

# Парсинг данных с сайта
def parse_tickets(soup, date):
    tickets = []
    for trip in soup.find_all("div", class_="trip"):
        train_name_tag = trip.find("div", class_="skew-x-12")
        if not train_name_tag:
            continue
        
        train_number = train_name_tag.text.strip()
        if train_number not in TRAINS:
            continue
            
        train_name = train_name_tag.text.strip() if train_name_tag else "Неизвестно"
        coupe_tag = trip.find("h4", class_="Typography Typography--h4 flex justify-center text-center lg:hidden")
        coupe_info = coupe_tag.text.strip() if coupe_tag else "Неизвестно"

        for link in trip.find_all("a", class_="class-link"):
            href = link.get("href", "")
            if CLASS_ID in href:
                seat_text = link.text.strip()
                try:
                    available_seats = int(seat_text.split()[0])
                except ValueError:
                    continue
                
                if available_seats > 0:
                    ticket_info = {
                        "train": train_number, 
                        "train_name": train_name,  # Добавляем имя поезда
                        "date": date, 
                        "coupe_info": coupe_info,  # Добавляем информацию о купе
                        "link": f"https://booking.uz.gov.ua{href}",
                        "seats": available_seats
                    }
                    tickets.append(ticket_info)
    return tickets

# Отправка сообщений в Telegram
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Ошибка отправки в Telegram: {e}")

# Основная проверка билетов
def check_tickets():
    try:
        logging.info("🔍 Проверяем билеты...")
        found_tickets = []
        
        start_date = datetime.strptime(START_DATE, "%Y-%m-%d")
        dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)]  # Анализируем 5 дней
        
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(get_ticket_info, date): date for date in dates}
            for future in futures:
                tickets = future.result()
                if tickets:
                    found_tickets.extend(tickets)

        if found_tickets:
            message = "🚆 Найдены билеты:\n"
            for ticket in found_tickets:
                message += f"Поезд {ticket['train']} ({ticket['train_name']})\nКупе: {ticket['coupe_info']}\nСсылка: {ticket['link']}\nМеста: {ticket['seats']}\n\n"
            
            for chunk in [message[i:i+4096] for i in range(0, len(message), 4096)]:
                send_telegram_message(chunk)
                time.sleep(1)
            logging.info("✅ Найдены билеты! Уведомление отправлено.")
        else:
            logging.info("❌ Нижних мест нет.")
    except Exception as e:
        logging.error(f"Ошибка в check_tickets: {e}")

# Запуск проверки каждые 5 минут
schedule.every(5).minutes.do(check_tickets)

if __name__ == "__main__":
    logging.info("🚀 Скрипт запущен!")
    while True:
        logging.info("⏳ Ожидание...")
        schedule.run_pending()
        time.sleep(60)
