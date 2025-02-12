import os
import time
import logging
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import schedule
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Настроим логгер
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Загружаем переменные из .env файла
load_dotenv()

# Параметры для поиска билетов
STATION_FROM = os.getenv("STATION_FROM")
STATION_TO = os.getenv("STATION_TO")
TRAINS = os.getenv("TRAINS", "").split(",")  # Разбиваем на список
START_DATE = os.getenv("START_DATE")  # Дата начала поиска
CLASS_ID = "К"  # Купе

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def check_env_vars():
    """Проверка наличия необходимых переменных окружения"""
    required_vars = ["STATION_FROM", "STATION_TO", "TRAINS", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "START_DATE"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logging.error(f"Отсутствуют необходимые переменные окружения: {', '.join(missing_vars)}")
        exit(1)

check_env_vars()  # Проверяем перед запуском

def get_ticket_info(date, retries=3):
    """Получает информацию о билетах на указанную дату с повторными попытками"""
    url = f"https://booking.uz.gov.ua/search-trips/{STATION_FROM}/{STATION_TO}/list?startDate={date}"
    headers = {"User-Agent": "Mozilla/5.0"}

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Проверяем статус ответа
            soup = BeautifulSoup(response.text, "html.parser")
            return parse_tickets(soup, date)
        except requests.RequestException as e:
            logging.error(f"Ошибка запроса (попытка {attempt + 1}): {e}")
            time.sleep(5)  # Ждем 5 секунд перед повторной попыткой
    return []

def parse_tickets(soup, date):
    """Парсит страницу и извлекает информацию о билетах"""
    tickets = []
    for trip in soup.find_all("div", class_="trip"):
        train_number_tag = trip.find("div", class_="train-number")
        if not train_number_tag:
            continue

        train_number = train_number_tag.text.strip()
        if train_number not in TRAINS:
            continue

        # Получаем ссылки на классы
        class_links = trip.find_all("a", class_="class-link")
        for link in class_links:
            href = link.get("href", "")
            if CLASS_ID in href:
                seat_text = link.text.strip()
                try:
                    available_seats = int(seat_text.split()[0])
                except ValueError:
                    continue  # Если не удалось определить количество мест, пропускаем

                if available_seats > 0:
                    tickets.append({
                        "train": train_number,
                        "date": date,
                        "link": f"https://booking.uz.gov.ua{href}"
                    })
    return tickets

def send_telegram_message(message):
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}

    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Ошибка отправки сообщения в Telegram: {e}")

def check_tickets():
    """Основная функция проверки билетов с параллельными запросами"""
    logging.info("🔍 Проверяем билеты...")
    found_tickets = []

    start_date = datetime.strptime(START_DATE, "%Y-%m-%d")  # Преобразуем дату в объект
    dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6)]  # Генерируем даты на 6 дней

    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(get_ticket_info, date): date for date in dates}

        for future in futures:
            tickets = future.result()
            if tickets:
                found_tickets.extend(tickets)

    if found_tickets:
        message = "🚆 Найдены билеты с нижними местами:\n"
        for ticket in found_tickets:
            message += f"Поезд {ticket['train']} ({ticket['date']})\nСсылка: {ticket['link']}\n\n"
        
        # Если билетов много, отправляем с паузами
        for chunk in [message[i:i+4096] for i in range(0, len(message), 4096)]:  
            send_telegram_message(chunk)
            time.sleep(1)

        logging.info("✅ Найдены билеты! Уведомление отправлено.")
    else:
        logging.info("❌ Нижних мест нет.")

# Запуск проверки раз в 10 минут
schedule.every(10).minutes.do(check_tickets)

if __name__ == "__main__":
    logging.info("🚀 Скрипт запущен!")
    while True:
        schedule.run_pending()
        time.sleep(1)
