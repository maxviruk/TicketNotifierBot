import json
import os

# Путь к файлу для хранения истории
history_file = "history.json"

# Функция для сохранения истории в файл
def save_history(ticket_info):
    try:
        # Проверяем, существует ли файл, если нет - создаем
        if os.path.exists(history_file):
            with open(history_file, "r") as file:
                history = json.load(file)
        else:
            history = []

        # Добавляем новые данные в историю
        history.append(ticket_info)

        # Сохраняем обновленную историю в файл
        with open(history_file, "w") as file:
            json.dump(history, file, indent=4)

        logging.info("✅ История успешно сохранена!")
    except Exception as e:
        logging.error(f"Ошибка при сохранении истории: {e}")

# Модификация функции для сохранения истории с найденными билетами
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
                message += f"Поезд {ticket['train']} ({ticket['date']})\nСсылка: {ticket['link']}\nМеста: {ticket['seats']}\n\n"
            
            # Разбиваем сообщение на части (Telegram ограничение 4096 символов)
            for chunk in [message[i:i+4096] for i in range(0, len(message), 4096)]:
                send_telegram_message(chunk)
                time.sleep(1)

            logging.info("✅ Найдены билеты! Уведомление отправлено.")

            # Сохраняем историю проверок
            for ticket in found_tickets:
                save_history(ticket)

        else:
            logging.info("❌ Нижних мест нет.")
    except Exception as e:
        logging.error(f"Ошибка в check_tickets: {e}")
