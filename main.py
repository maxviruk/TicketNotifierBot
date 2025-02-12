import os
import time
import logging
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import schedule

# Настроим логгер
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Параметры для поиска билетов
STATION_FROM = os.getenv("STATION_FROM")
STATION_TO = os.getenv("STATION_TO")
TRAINS = os.getenv("TRAINS").split(",")  # Разбиваем на список
DATES_RANGE = [-2, -1, 0, 1, 2, 3]  # Диапазон дат (от -2 до +3 дней)
CLASS_ID = "К"  # Купе

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Здесь будет токен бота
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Здесь будет ID чата

def check_env_vars():
    """Проверка наличия необходимых переменных окружения"""
    required_vars = ["STATION_FROM", "STATION_TO", "TRAINS", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    missing_vars = [var for var in required_vars if os.getenv(var) is None]

    if missing_vars:
        logging.error(f"Отсутствуют необходимые переменные окружения: {', '.join(missing_vars)}")
        exit(1)

check_env_vars()  # Проверяем перед запуском

def get_ticket_info(date, retries=3):
    """Получает информацию о билетах на указанную дату с повторными попытками в случае ошибки"""
    url = f"https://booking.uz.gov.ua/search-trips/{STATION_FROM}/{STATION_TO}/list?startDate={date}"
    headers = {"User-Agent": "Mozilla/5.0"}

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Проверяем статус ответа
            soup = BeautifulSoup(response.text, "html.parser")
            return parse_tickets(soup, date)
        except requests.RequestException as e:
            logging.error(f"Попытка {attempt + 1} не удалась. Ошибка: {e}")
            time.sleep(5)  # Ждем 5 секунд перед повторной попыткой
    return []

def parse_tickets(soup, date):
    """Парсит страницу и извлекает информацию о билетах"""
    tickets = []
    for trip in soup.find_all("div", class_="trip"):
        train_number = trip.find("div", class_="train-number").text.strip()
        if train_number not in TRAINS:
            continue  # Пропускаем поезда, которые не заданы

        # Получаем ссылки на классы
        class_links = trip.find_all("a", class_="class-link")
        for link in class_links:
            if CLASS_ID in link["href"]:  # Проверяем, что это купе
                seat_text = link.text.strip()
                available_seats = int(seat_text.split()[0])  # Количество мест

                # Проверяем, есть ли нижние места
                if available_seats > 0:
                    tickets.append({
                        "train": train_number,
                        "date": date,
                        "link": "https://booking.uz.gov.ua" + link["href"]
                    })
    return tickets

def send_telegram_message(message):
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=data)

def check_tickets():
    """Основная функция проверки билетов с параллельными запросами"""
    logging.info("🔍 Проверяем билеты...")
    found_tickets = []

    with ThreadPoolExecutor() as executor:
        futures = []
        for offset in DATES_RANGE:
            date = (time.time() + offset * 86400)
            formatted_date = time.strftime("%Y-%m-%d", time.gmtime(date))
            futures.append(executor.submit(get_ticket_info, formatted_date))

        for future in futures:
            tickets = future.result()
            if tickets:
                found_tickets.extend(tickets)

    if found_tickets:
        message = "🚆 Найдены билеты с нижними местами:\n"
        for ticket in found_tickets:
            message += f"Поезд {ticket['train']} ({ticket['date']})\nСсылка: {ticket['link']}\n\n"
        send_telegram_message(message)
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
