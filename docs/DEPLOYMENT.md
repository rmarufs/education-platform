# 🚀 Гайд по развёртыванию (Deployment)

Полная инструкция по развёртыванию образовательной платформы на Production.

## 📋 Оглавление
- [Серверные требования](#серверные-требования)
- [Production Setup](#production-setup)
- [Database](#database)
- [Supabase Storage](#supabase-storage)
- [Web Server (NGINX)](#web-server-nginx)
- [Application Server (Gunicorn)](#application-server-gunicorn)
- [SSL/HTTPS](#sslhttps)
- [Мониторинг](#мониторинг)
- [Backup & Recovery](#backup--recovery)

---

## 💻 Серверные требования

### Минимальные требования
- **CPU:** 2 cores
- **RAM:** 2 GB
- **Storage:** 20 GB (+ место для видео)
- **OS:** Ubuntu 20.04 LTS, Debian 11, или CentOS 8

### Рекомендуемые требования
- **CPU:** 4 cores
- **RAM:** 4 GB
- **Storage:** 100+ GB
- **OS:** Ubuntu 22.04 LTS

### Сервисы
- Ubuntu/Debian VPS (DigitalOcean, Hetzner, AWS EC2 и т.д.)
- PostgreSQL 12+ (облачное или самостоятельно)
- Supabase (облачное)

---

## ⚙️ Production Setup

### 1. Обновляем систему
```bash
sudo apt-get update
sudo apt-get upgrade -y
```

### 2. Устанавливаем зависимости
```bash
sudo apt-get install -y \
    python3.10 \
    python3.10-venv \
    python3.10-dev \
    python3-pip \
    postgresql-client \
    nginx \
    certbot \
    python3-certbot-nginx \
    supervisor \
    git
```

### 3. Создаём пользователя приложения
```bash
sudo useradd -m -s /bin/bash app
sudo usermod -aG sudo app
sudo -u app mkdir -p /home/app/education_platform
```

### 4. Клонируем репозиторий
```bash
cd /home/app/education_platform
sudo -u app git clone <repository-url> .
```

### 5. Создаём виртуальное окружение
```bash
sudo -u app python3.10 -m venv venv
sudo -u app venv/bin/pip install --upgrade pip
sudo -u app venv/bin/pip install -r requirements.txt
```

### 6. Конфигурируем переменные окружения
```bash
sudo -u app cp config/.env.example config/.env.production
sudo -u app nano config/.env.production
```

**Пример значений для production:**
```env
# Database
DATABASE_URL=postgresql://user:password@db-host:5432/education_db

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Security
SECRET_KEY=generate-random-secure-key-here-min-32-chars!@#$%

# Cloudinary
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Application
DEBUG=False
PLATFORM_NAME=Education Platform
ALLOWED_ORIGINS=https://example.com,https://www.example.com

# Email (опционально)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=noreply@example.com
SMTP_PASSWORD=your-app-password
```

---

## 🗄️ Database

### Локальное развёртывание PostgreSQL

```bash
# Установка
sudo apt-get install -y postgresql postgresql-contrib

# Запуск
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Создание БД и пользователя
sudo -u postgres psql << EOF
CREATE DATABASE education_db;
CREATE USER app_user WITH PASSWORD 'strong_password_here';
ALTER ROLE app_user SET client_encoding TO 'utf8';
ALTER ROLE app_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE app_user SET default_transaction_deferrable TO on;
ALTER ROLE app_user SET default_transaction_read_committed TO on;
GRANT ALL PRIVILEGES ON DATABASE education_db TO app_user;
\c education_db
GRANT ALL ON SCHEMA public TO app_user;
EOF
```

### Облачное PostgreSQL (рекомендуется)

**DigitalOcean Managed Databases:**
- Копируете connection string
- Добавляете в `config/.env.production`: `DATABASE_URL=...`

```bash
# Проверка подключения
sudo -u app /home/app/education_platform/venv/bin/python << EOF
from app.database import engine
with engine.connect() as conn:
    result = conn.execute("SELECT 1")
    print("✅ Database connection successful!")
EOF
```

---

## 📹 Supabase Storage

### 1. Создаём Supabase проект
- Переходим на https://supabase.com
- Создаём новый проект
- Копируем Project URL и Anon Key

### 2. Инициализируем видео-бакет
```bash
cd /home/app/education_platform
sudo -u app venv/bin/python scripts/setup_video_bucket.py
```

**Что создалось:**
- ✅ Bucket `education_videos`
- ✅ RLS политики
- ✅ CORS конфигурация

### 3. Проверка
```bash
curl https://your-project.supabase.co/storage/v1/buckets/education_videos \
  -H "Authorization: Bearer YOUR_ANON_KEY"
```

---

## 🌐 Web Server (NGINX)

### 1. Создаём конфиг NGINX
```bash
sudo nano /etc/nginx/sites-available/education_platform
```

**Конфиг:**
```nginx
upstream education_app {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

# Redirect HTTP → HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name example.com www.example.com;

    return 301 https://$server_name$request_uri;
}

# HTTPS конфиг
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name example.com www.example.com;

    # SSL сертификаты (заполнить после установки Certbot)
    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    
    # SSL параметры
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Логи
    access_log /var/log/nginx/education_platform.access.log;
    error_log /var/log/nginx/education_platform.error.log;

    # Ограничения
    client_max_body_size 500M;  # Для видео
    
    # Gzip сжатие
    gzip on;
    gzip_types text/html text/plain text/css text/javascript 
               application/javascript application/json;

    # Проксирование
    location / {
        proxy_pass http://education_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Timeout для видео
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Статические файлы (кэширование)
    location /static/ {
        alias /home/app/education_platform/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
}
```

### 2. Включаем конфиг
```bash
sudo ln -s /etc/nginx/sites-available/education_platform \
    /etc/nginx/sites-enabled/

# Проверка синтаксиса
sudo nginx -t

# Перезагрузка
sudo systemctl restart nginx
```

---

## 🐍 Application Server (Gunicorn)

### 1. Создаём конфиг Gunicorn
```bash
sudo -u app nano /home/app/education_platform/config/gunicorn.conf.py
```

**Конфиг:**
```python
import multiprocessing

# Общие параметры
bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000

# Логирование
accesslog = "/home/app/education_platform/data/logs/access.log"
errorlog = "/home/app/education_platform/data/logs/error.log"
loglevel = "info"

# Timeout
timeout = 120

# Процессы
preload_app = True
daemon = False
```

### 2. Создаём Systemd service
```bash
sudo nano /etc/systemd/system/education_platform.service
```

**Service файл:**
```ini
[Unit]
Description=Education Platform FastAPI Service
After=network.target

[Service]
Type=notify
User=app
Group=app
WorkingDirectory=/home/app/education_platform

Environment="PATH=/home/app/education_platform/venv/bin"
ExecStart=/home/app/education_platform/venv/bin/gunicorn \
    --config config/gunicorn.conf.py main:app

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. Запускаем сервис
```bash
sudo systemctl daemon-reload
sudo systemctl enable education_platform
sudo systemctl start education_platform
sudo systemctl status education_platform
```

### 4. Проверка
```bash
curl http://127.0.0.1:8000/
```

---

## 🔒 SSL/HTTPS

### Установка Let's Encrypt сертификата

```bash
# Установка Certbot
sudo apt-get install -y certbot python3-certbot-nginx

# Получение сертификата
sudo certbot certonly --nginx -d example.com -d www.example.com

# Автоматическое обновление
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Проверка
sudo certbot renew --dry-run
```

---

## 📊 Мониторинг

### 1. Логирование

**Основные логи:**
```bash
# Приложение
tail -f /home/app/education_platform/data/logs/error.log

# NGINX
tail -f /var/log/nginx/education_platform.error.log

# Systemd
sudo journalctl -u education_platform -f
```

### 2. Health Check

```bash
# Создаём скрипт мониторинга
sudo nano /usr/local/bin/check_education_platform.sh
```

**Скрипт:**
```bash
#!/bin/bash

# Проверка приложения
curl -f http://127.0.0.1:8000/health || exit 1

# Проверка БД
psql -h localhost -U app_user -d education_db -c "SELECT 1" || exit 1

# Проверка Supabase
curl -f https://your-project.supabase.co/rest/v1/ || exit 1

echo "✅ All services OK"
```

```bash
sudo chmod +x /usr/local/bin/check_education_platform.sh
```

### 3. Uptime Monitoring

**С использованием Cron:**
```bash
# Каждые 5 минут
*/5 * * * * /usr/local/bin/check_education_platform.sh >> /home/app/education_platform/data/logs/monitor.log 2>&1
```

---

## 💾 Backup & Recovery

### 1. PostgreSQL Backup

```bash
# Полная резервная копия
sudo -u postgres pg_dump -Fc education_db > /home/app/education_platform/data/backups/$(date +%Y-%m-%d).dump

# Автоматизированный backup (Cron)
0 2 * * * sudo -u postgres pg_dump -Fc education_db > /home/app/education_platform/data/backups/backup_$(date +\%Y-\%m-\%d).dump
```

### 2. Восстановление из резервной копии

```bash
# Восстановить БД
sudo -u postgres pg_restore -d education_db /path/to/backup.dump
```

### 3. Supabase Storage Backup

```bash
# Скачать видео с Supabase
aws s3 sync s3://your-bucket/education_videos ./backups/videos/ \
    --endpoint-url https://your-project.supabase.co/storage/v1
```

---

## ✅ Финальный чеклист

- [ ] PostgreSQL запущена и доступна
- [ ] Supabase проект создан и конфигурирован
- [ ] NGINX конфиг синтаксически верен
- [ ] Gunicorn сервис запущен
- [ ] SSL сертификат установлен
- [ ] Backup система настроена
- [ ] Мониторинг активен
- [ ] Логирование работает
- [ ] Firewall правила установлены
- [ ] DNS настроены

---

## 🚨 Troubleshooting

### Приложение не запускается
```bash
sudo journalctl -u education_platform -n 50
sudo systemctl restart education_platform
```

### Проблема с БД
```bash
# Проверка подключения
psql -h your-db-host -U app_user -d education_db -c "SELECT 1"

# Проверка логов
sudo tail -f /var/log/postgresql/
```

### Проблема с NGINX
```bash
# Синтаксис
sudo nginx -t

# Перезагрузка
sudo systemctl restart nginx

# Логи
sudo tail -f /var/log/nginx/education_platform.error.log
```

---

**Версия гайда:** 2.0  
**Дата обновления:** 26 апреля 2026 г.  
**Поддержка:** Создайте Issue в GitHub
