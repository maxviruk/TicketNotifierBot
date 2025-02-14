# Используем официальный образ Python 3.12
FROM python:3.12

WORKDIR /app

# Устанавливаем необходимые зависимости для Chrome и ChromeDriver
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    gnupg \
    libxss1 \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libgbm1 \
    libpangocairo-1.0-0 \
    libxcomposite1 \
    libxrandr2 \
    xdg-utils \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Node.js через официальный репозиторий
RUN curl -sL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Установка Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google-chrome-keyring.gpg \
    && echo 'deb [signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main' | tee /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Установка ChromeDriver
RUN CHROME_DRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE) && \
    wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROME_DRIVER_VERSION}/chromedriver_linux64.zip" && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    rm /tmp/chromedriver.zip && \
    chmod +x /usr/local/bin/chromedriver

# Проверка наличия ChromeDriver
RUN ls -l /usr/local/bin/chromedriver

# Установка зависимостей Python
COPY requirements.txt .  # Копируем только requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Клонируем репозиторий
RUN git clone https://github.com/maxviruk/TicketNotifierBot.git /app

# Установка Railway CLI
RUN npm install -g @railway/cli

# Копируем оставшиеся файлы проекта
COPY . .  # Здесь копируем все остальные файлы проекта, кроме уже скопированных

# Запуск Python приложения
CMD ["python", "main.py"]
