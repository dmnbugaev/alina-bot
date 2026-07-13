# Alina private Telegram bot

Telegram-бот продает единоразовый доступ в приватный канал через YooKassa.
После оплаты пользователь возвращается в бот, нажимает «Проверить оплату», бот проверяет платеж, сохраняет статус в Supabase и выдает одноразовую invite-ссылку.

## Стек

- Python 3.12
- aiogram 3
- Supabase PostgreSQL
- YooKassa Python SDK
- FastAPI для webhook-деплоя
- python-dotenv

## Переменные окружения

Создайте `.env` на основе `.env.example`:

```env
BOT_TOKEN=1234567890:replace_with_botfather_token
CHANNEL_ID=-1001234567890

YOOKASSA_SHOP_ID=123456
YOOKASSA_SECRET_KEY=test_or_live_secret_key
YOOKASSA_RETURN_URL=https://t.me/your_bot_username

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_publishable_or_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key

PAYMENT_AMOUNT=499.00
PAYMENT_CURRENCY=RUB
PAYMENT_DESCRIPTION=Единоразовый доступ в приватный Telegram-канал

TELEGRAM_WEBHOOK_SECRET=
```

Важно:

- `BOT_TOKEN` берется у `@BotFather`.
- `CHANNEL_ID` должен быть id приватного канала, обычно формата `-100...`.
- Бот должен быть администратором канала и иметь право создавать invite-ссылки.
- `YOOKASSA_RETURN_URL` обычно равен ссылке на бота, например `https://t.me/your_bot_username`.
- `SUPABASE_SERVICE_ROLE_KEY` храните только на сервере.
- Для VPS polling-деплоя `TELEGRAM_WEBHOOK_SECRET` можно оставить пустым.

## Supabase

1. Откройте Supabase project.
2. Перейдите в SQL Editor.
3. Выполните файл `supabase/schema.sql`.
4. Повторный запуск безопасен: `create table if not exists` и `create index if not exists` не удаляют данные.
5. Если включен RLS, используйте `SUPABASE_SERVICE_ROLE_KEY` на сервере или настройте policies для `select`, `insert`, `update` таблицы `payments`.

Проверка подключения:

```bash
python scripts/check_supabase.py
```

Скрипт создаст тестовый платеж, проверит чтение и обновление, затем удалит тестовую запись.

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Заполните `.env`, затем проверьте Telegram:

```bash
python scripts/check_telegram.py
```

Запуск в polling-режиме:

```bash
python -m bot.main
```

Polling и webhook нельзя использовать одновременно на одном токене. Перед запуском polling бот удаляет webhook через `delete_webhook`.

## Деплой на VPS через `/var/www`

Инструкция рассчитана на Ubuntu 22.04/24.04 и запуск бота в polling-режиме через `systemd`.

### 1. Подготовить сервер

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip git
```

Создайте директорию проекта:

```bash
sudo mkdir -p /var/www/alina-privat-telegram
sudo chown -R $USER:$USER /var/www/alina-privat-telegram
```

Если проект в Git:

```bash
git clone <YOUR_REPO_URL> /var/www/alina-privat-telegram
cd /var/www/alina-privat-telegram
```

Если Git не используется, загрузите файлы проекта в `/var/www/alina-privat-telegram`.

### 2. Установить зависимости

```bash
cd /var/www/alina-privat-telegram
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Настроить `.env`

```bash
cd /var/www/alina-privat-telegram
cp .env.example .env
nano .env
```

Заполните все значения. Для polling-деплоя на VPS оставьте `TELEGRAM_WEBHOOK_SECRET` пустым.

Права на `.env`:

```bash
chmod 600 .env
```

### 4. Проверить подключения

```bash
cd /var/www/alina-privat-telegram
source .venv/bin/activate
python scripts/check_telegram.py
python scripts/check_supabase.py
```

Обе команды должны завершиться без ошибок.

Если ранее был настроен webhook, удалите его:

```bash
python scripts/delete_webhook.py
```

### 5. Создать systemd service

```bash
sudo nano /etc/systemd/system/alina-telegram-bot.service
```

Вставьте конфиг:

```ini
[Unit]
Description=Alina private Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/var/www/alina-privat-telegram
Environment=PYTHONUNBUFFERED=1
ExecStart=/var/www/alina-privat-telegram/.venv/bin/python -m bot.main
Restart=always
RestartSec=5
User=YOUR_LINUX_USER
Group=YOUR_LINUX_USER

[Install]
WantedBy=multi-user.target
```

Замените `YOUR_LINUX_USER` на пользователя, которому принадлежит папка проекта.

### 6. Запустить сервис

```bash
sudo systemctl daemon-reload
sudo systemctl enable alina-telegram-bot
sudo systemctl start alina-telegram-bot
sudo systemctl status alina-telegram-bot
```

Логи:

```bash
journalctl -u alina-telegram-bot -f
```

### 7. Обновление кода

```bash
cd /var/www/alina-privat-telegram
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart alina-telegram-bot
sudo systemctl status alina-telegram-bot
```

### 8. VPS checklist

- `systemctl status alina-telegram-bot` показывает `active (running)`.
- В логах нет ошибок `Unauthorized`, `Forbidden`, `ValidationError`.
- Команда `/start` в Telegram отвечает.
- Бот является администратором приватного канала.
- После оплаты кнопка «Проверить оплату» выдает invite-ссылку.

## Webhook / Vercel

В проекте также есть `api/webhook.py` и `vercel.json`, но для VPS через `/var/www` используйте polling-режим из инструкции выше. Не запускайте polling и webhook одновременно на одном токене.

Для настройки webhook:

```bash
python scripts/set_webhook.py https://your-domain.example/api/webhook
```

Для возврата на polling:

```bash
python scripts/delete_webhook.py
python -m bot.main
```

## Безопасность

- Не храните реальные токены в репозитории.
- Не публикуйте `.env`.
- Перевыпустите токены, если они попадали в публичный репозиторий или чат.
- На сервере используйте `SUPABASE_SERVICE_ROLE_KEY`, если в Supabase включен RLS.
