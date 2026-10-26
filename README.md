# Alina private Telegram bot

Telegram-бот продаёт разовый доступ в приватный канал через YooKassa.
Платёж автоматически проверяется фоновым worker на VPS. После подтверждения бот выдаёт
персональную одноразовую invite-ссылку на 24 часа. Ручная кнопка проверки остаётся
резервным сценарием.

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

AUTO_FULFILLMENT_ENABLED=false
REMINDERS_ENABLED=false
PAYMENT_POLL_INTERVAL_SECONDS=30
PAYMENT_POLL_BATCH_SIZE=20
INVITE_TTL_HOURS=24
REMINDER_DELAYS_HOURS=1,24

SUPPORT_USERNAME=@a_vng
ADMIN_TELEGRAM_IDS=123456789
```

Важно:

- `BOT_TOKEN` берется у `@BotFather`.
- `CHANNEL_ID` должен быть id приватного канала, обычно формата `-100...`.
- Бот должен быть администратором канала и иметь право создавать invite-ссылки.
- `YOOKASSA_RETURN_URL` обычно равен ссылке на бота, например `https://t.me/your_bot_username`.
- `SUPABASE_SERVICE_ROLE_KEY` обязателен и хранится только на сервере. Anon key не
  используется для операций с платежами.
- Для VPS polling-деплоя `TELEGRAM_WEBHOOK_SECRET` можно оставить пустым.
- `ADMIN_TELEGRAM_IDS` — числовые Telegram ID администраторов через запятую.
- Автовыдача и напоминания выключены по умолчанию для безопасного production-роллаута.

## Supabase

1. Сделайте резервную копию production-базы.
2. Для нового проекта сначала выполните `supabase/schema.sql`.
3. Затем выполните `supabase/migrations/20260829_reliability.sql`.
4. Миграция сохраняет старые платежи, переносит состояние выдачи доступа и включает RLS.
5. Перед включением автоматизации проверьте, что сервер использует именно
   `SUPABASE_SERVICE_ROLE_KEY`.

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
pip install -r requirements-dev.txt
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

Polling и Telegram webhook нельзя использовать одновременно на одном токене. При запуске
polling бот отключает webhook, но сохраняет накопившиеся Telegram updates.

Проверки перед коммитом:

```bash
ruff check .
ruff format --check .
coverage run -m pytest
coverage report --fail-under=40
```

## Администрирование

Команды доступны только пользователям из `ADMIN_TELEGRAM_IDS`:

- `/stats` — воронка, выручка и незавершённые платежи за 24 часа, 7 и 30 дней;
- `/errors` — последние нерешённые ошибки выдачи;
- `/health` — Supabase, worker, флаги и последняя ошибка.

## Безопасный rollout

1. Оставьте `AUTO_FULFILLMENT_ENABLED=false` и `REMINDERS_ENABLED=false`.
2. Примените миграцию Supabase, обновите код и перезапустите systemd.
3. Выполните один контролируемый реальный платёж и проверьте ручную кнопку.
4. Включите `AUTO_FULFILLMENT_ENABLED=true`, перезапустите сервис и проверьте
   автоматическую выдачу.
5. Соберите семь дней базовой статистики.
6. Включите `REMINDERS_ENABLED=true`; сравните следующие 14 дней с базовым периодом.

Перед rollout также проверьте в кабинете YooKassa, что по последнему успешному платежу
сформирован фискальный чек.

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

Обновление деплоится автоматически: push в `main` запускает `.github/workflows/ci.yml`
(линтер, тесты, затем SSH-деплой на VPS через `scripts/deploy_remote.sh`).
В репозитории нужен secret `DEPLOY_SSH_KEY` — приватный deploy-ключ для
`admin@<VPS>:22222` (публичная часть добавлена в `~/.ssh/authorized_keys`).

Ручное обновление, если CI недоступен:

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
- Повторные нажатия не создают несколько платежей.
- После оплаты worker автоматически выдаёт invite-ссылку не позднее двух минут.
- Invite-ссылка принимает одного участника и истекает через 24 часа.
- `/health`, `/stats` и `/errors` доступны администратору.

## Webhook / Vercel

В проекте сохранены legacy-файлы `api/webhook.py` и `vercel.json`. Production-сценарий
этого проекта — VPS polling; Vercel не используется для уведомлений YooKassa.
Не запускайте polling и Telegram webhook одновременно на одном токене.

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
- На сервере всегда используйте `SUPABASE_SERVICE_ROLE_KEY`; таблицы платежей, выдачи и
  аналитики закрыты RLS от anon/authenticated ролей.
