import requests
import time
import schedule
from bs4 import BeautifulSoup

# Параметры для поиска билетов
import os
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATION_FROM = os.getenv("STATION_FROM")
STATION_TO = os.getenv("STATION_TO")
TRAINS = os.getenv("TRAINS").split(",")  # Разбиваем на список
DATES_RANGE = [-2, -1, 0, 1, 2, 3]  # Диапазон дат (от -2 до +3 дней)
CLASS_ID = "К"  # Купе

# Данные Telegram
TELEGRAM_BOT_TOKEN = "your_bot_token"  # Здесь будет токен бота
TELEGRAM_CHAT_ID = "your_chat_id"  # Здесь будет ID чата

def get_ticket_info(date):
    """Получает информацию о билетах на указанную дату"""
    url = f"https://booking.uz.gov.ua/search-trips/{STATION_FROM}/{STATION_TO}/list?startDate={date}"
    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Ошибка загрузки страницы: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
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
    """Основная функция проверки билетов"""
    print("🔍 Проверяем билеты...")
    found_tickets = []

    for offset in DATES_RANGE:
        date = (time.time() + offset * 86400)  # Генерация даты
        formatted_date = time.strftime("%Y-%m-%d", time.gmtime(date))
        tickets = get_ticket_info(formatted_date)
        
        if tickets:
            found_tickets.extend(tickets)

    if found_tickets:
        message = "🚆 Найдены билеты с нижними местами:\n"
        for ticket in found_tickets:
            message += f"Поезд {ticket['train']} ({ticket['date']})\nСсылка: {ticket['link']}\n\n"
        send_telegram_message(message)
        print("✅ Найдены билеты! Уведомление отправлено.")
    else:
        print("❌ Нижних мест нет.")

# Запуск проверки раз в 2 минуты
schedule.every(2).minutes.do(check_tickets)

if __name__ == "__main__":
    print("🚀 Скрипт запущен!")
    while True:
        schedule.run_pending()
        time.sleep(1)
