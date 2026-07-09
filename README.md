# Telegram bot for private channel access

Бот продает единоразовый доступ в приватный Telegram-канал через YooKassa. После оплаты пользователь возвращается в бот, нажимает `Проверить оплату`, бот проверяет платеж в YooKassa, сохраняет статус в Supabase и отправляет одноразовую invite-ссылку.

## Что изменено для скорости и деплоя

- Синхронные запросы в Supabase и YooKassa вынесены из event loop через `asyncio.to_thread`, поэтому один медленный внешний API не блокирует обработку других Telegram updates.
- Supabase и YooKassa service-клиенты переиспользуются через cache, а не создаются заново на каждый callback.
- Добавлен webhook endpoint `api/webhook.py` для Vercel и других serverless-платформ.
- Polling-режим `python -m bot.main` сохранен для VPS.
- Добавлены `vercel.json`, `pyproject.toml`, `.python-version`, `.gitignore`.
- Добавлен безопасный `.env.example` без реальных секретов.
- Добавлен составной индекс Supabase для быстрых запросов `telegram_id + status + created_at`.

## Стек

- Python 3.12 для деплоя, Python 3.11+ допустим локально
- aiogram 3
- FastAPI для webhook-деплоя
- Supabase PostgreSQL
- YooKassa Python SDK
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
- `CHANNEL_ID` должен быть id приватного канала, обычно вида `-100...`.
- Бот должен быть администратором канала и иметь право создавать invite-ссылки.
- `YOOKASSA_RETURN_URL` для этого проекта обычно равен ссылке на бота, например `https://t.me/your_bot_username`.
- `SUPABASE_SERVICE_ROLE_KEY` храните только на сервере. Не добавляйте его в публичный репозиторий.
- `TELEGRAM_WEBHOOK_SECRET` нужен для webhook-деплоя. Сгенерируйте длинную случайную строку. Для polling на VPS можно оставить пустым.

Если реальные токены уже попадали в `.env.example` или репозиторий, перевыпустите их: BotFather token, YooKassa secret key и Supabase service role key.

## Supabase

1. Откройте Supabase project.
2. Перейдите в SQL Editor.
3. Выполните файл `supabase/schema.sql`.
4. Если таблица уже существовала, повторный запуск безопасен: `create table if not exists` и `create index if not exists` не удаляют данные.
5. Если включен RLS, используйте `SUPABASE_SERVICE_ROLE_KEY` на сервере или настройте policies, которые разрешают боту `select`, `insert`, `update` для таблицы `payments`.

Проверка из локальной машины:

```powershell
python scripts/check_supabase.py
```

Скрипт создаст тестовый платеж, проверит чтение/обновление и удалит тестовую запись.

## Локальный запуск

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Заполните `.env`, затем проверьте Telegram:

```powershell
python scripts/check_telegram.py
```

Запуск в polling-режиме:

```powershell
python -m bot.main
```

Polling и webhook одновременно использовать нельзя. Перед polling бот сам удаляет webhook через `delete_webhook`.

## Деплой на VPS

Ниже пример для Ubuntu 24.04/22.04. Команды выполняются под обычным пользователем с `sudo`.

### 1. Подготовить сервер

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip git
```

Если проект лежит в Git:

```bash
cd /opt
sudo git clone <YOUR_REPO_URL> alina-privat-telegram
sudo chown -R $USER:$USER /opt/alina-privat-telegram
cd /opt/alina-privat-telegram
```

Если Git нет, загрузите папку проекта на сервер, например в `/opt/alina-privat-telegram`.

### 2. Установить зависимости

```bash
cd /opt/alina-privat-telegram
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Создать `.env`

```bash
cp .env.example .env
nano .env
```

Заполните все значения. Для VPS polling-деплоя `TELEGRAM_WEBHOOK_SECRET` можно оставить пустым.

### 4. Проверить подключения

```bash
source .venv/bin/activate
python scripts/check_telegram.py
python scripts/check_supabase.py
```

Обе команды должны завершиться без ошибок.

### 5. Создать systemd service

```bash
sudo nano /etc/systemd/system/alina-telegram-bot.service
```

Вставьте:

```ini
[Unit]
Description=Alina private Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/alina-privat-telegram
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/alina-privat-telegram/.venv/bin/python -m bot.main
Restart=always
RestartSec=5
User=YOUR_LINUX_USER
Group=YOUR_LINUX_USER

[Install]
WantedBy=multi-user.target
```

Замените `YOUR_LINUX_USER` на пользователя, под которым лежит проект.

### 6. Запустить сервис

```bash
sudo systemctl daemon-reload
sudo systemctl enable alina-telegram-bot
sudo systemctl start alina-telegram-bot
sudo systemctl status alina-telegram-bot
```

Посмотреть логи:

```bash
journalctl -u alina-telegram-bot -f
```

Перезапуск после обновления кода:

```bash
cd /opt/alina-privat-telegram
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart alina-telegram-bot
```

### 7. VPS checklist

- `systemctl status` показывает `active (running)`.
- В логах нет ошибок `Unauthorized`, `Forbidden`, `ValidationError`.
- Команда `/start` в Telegram отвечает.
- Бот является администратором канала.
- После оплаты кнопка `Проверить оплату` выдает invite-ссылку.

## Деплой на Vercel

На Vercel бот работает только через webhook. Polling там не подходит, потому что serverless function не должна постоянно висеть в фоне.

Актуальная документация:

- Vercel Python Runtime: https://vercel.com/docs/functions/runtimes/python
- aiogram webhook: https://docs.aiogram.dev/en/latest/dispatcher/webhook.html
- Telegram `setWebhook`: https://core.telegram.org/bots/api#setwebhook

### 1. Подготовить проект

В проект уже добавлены:

- `api/webhook.py` - FastAPI app для Telegram webhook.
- `pyproject.toml` - entrypoint `api.webhook:app`.
- `vercel.json` - настройки function и исключение лишних файлов.
- `.python-version` - Python 3.12.

### 2. Задать переменные окружения

В Vercel dashboard:

1. Откройте Project.
2. Перейдите в Settings -> Environment Variables.
3. Добавьте все переменные из `.env.example`.
4. Для `TELEGRAM_WEBHOOK_SECRET` задайте длинную случайную строку.
5. Убедитесь, что переменные доступны для Production.

Пример генерации секрета локально:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Задеплоить

Через Git:

1. Загрузите проект в GitHub/GitLab/Bitbucket.
2. Импортируйте репозиторий в Vercel.
3. Framework Preset можно оставить auto.
4. Build command не нужен.
5. Deploy.

Через Vercel CLI:

```bash
npm i -g vercel
vercel login
vercel
vercel --prod
```

После деплоя у вас будет URL вида:

```text
https://your-project.vercel.app
```

Проверьте healthcheck:

```bash
curl https://your-project.vercel.app/
```

Ожидаемый ответ:

```json
{"status":"ok"}
```

### 4. Установить Telegram webhook

Локально или на любой машине, где есть `.env` с теми же значениями:

```bash
python scripts/set_webhook.py https://your-project.vercel.app/api/webhook
```

Скрипт передаст в Telegram:

- webhook URL;
- `TELEGRAM_WEBHOOK_SECRET`;
- список используемых update types;
- `drop_pending_updates=True`.

Проверить webhook можно через Telegram API:

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

В ответе должны быть:

- `url`: `https://your-project.vercel.app/api/webhook`;
- `last_error_message` отсутствует или пустой;
- `pending_update_count` не растет постоянно.

### 5. Если нужно вернуться на VPS polling

Перед запуском polling удалите webhook:

```bash
python scripts/delete_webhook.py
python -m bot.main
```

### 6. Vercel checklist

- `/` на домене Vercel возвращает `{"status":"ok"}`.
- `getWebhookInfo` показывает правильный webhook URL.
- В Vercel Logs нет `403 Invalid webhook secret`.
- `/start` в Telegram отвечает после установки webhook.
- YooKassa `return_url` ведет обратно в Telegram-бота, а не на Vercel webhook.

## Production notes

- Для максимальной надежности VPS polling проще и стабильнее: бот постоянно запущен, нет cold start.
- Vercel удобен, если нужен serverless-деплой без VPS, но первый ответ после простоя может быть медленнее из-за cold start.
- Не запускайте одновременно VPS polling и Vercel webhook на одном токене.
- Логи `*.log`, `.env`, `.venv`, `.vercel` исключены через `.gitignore`.
- Реальные секреты нельзя хранить в репозитории. Используйте environment variables на сервере/платформе.
#   a l i n a - b o t  
 