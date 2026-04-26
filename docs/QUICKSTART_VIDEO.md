# 🚀 Быстрый Старт: Видео Интеграция

## За 5 минут до первого видео

### 1️⃣ Установка (30 сек)

```bash
# Обновить зависимости
pip install -r requirements.txt

# или конкретно
pip install supabase==1.4.0
```

### 2️⃣ Суpabase Аккаунт (2 мин)

1. Зайти на https://supabase.com
2. Создать новый проект (или выбрать существующий)
3. Скопировать из Settings → API:
   - **Project URL** → `SUPABASE_URL`
   - **Anon Public Key** → `SUPABASE_KEY`

### 3️⃣ Переменные Окружения (1 мин)

**Создать/обновить `.env`:**
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Или в Render:**
- Settings → Environment → Add variable
- SUPABASE_URL
- SUPABASE_KEY

### 4️⃣ База Данных (1 мин)

```bash
# Миграция (запустить в PostgreSQL)
psql $DATABASE_URL < migrations/001_add_video_filename.sql

# Или вручную скопировать и выполнить SQL в pgAdmin/Render console
```

### 5️⃣ Готово! 🎉

```bash
# Запустить приложение
python main.py

# Открыть в браузере
# http://localhost:8000
```

---

## Проверка что работает

### Как преподаватель:

1. Залогиниться  
2. Создать курс → Модуль → Урок
3. В форме урока будет:
   - **Drag & Drop зона** для видео (вверху)  
   - **YouTube поле** ниже

4. Выбрать видео файл (MP4, WebM, MOV, AVI, MKV)
5. Видео автоматически загрузится  
6. Появится статус "✅ Видео загружено"
7. Создать урок

### Как ученик:

1. Открыть курс → Модуль → Урок
2. Видеть видеоплеер с загруженным видео
3. Нажать Play → видео воспроизводится
4. Автоматическое обновление ссылки каждые 100 сек

---

## Если что-то не работает

### Видео не загружается

```
❌ Ошибка 500 при /videos/upload
```

**Проверить:**
1. `SUPABASE_URL` и `SUPABASE_KEY` установлены
2. Bucket `videos` создан (Settings → Storage в Supabase)
3. Размер видео < 100MB
4. Формат поддерживаемый (не .mov снят на iPhone)

**Смотреть логи:**
```bash
# Lokali
tail -f app.log

# Render
Settings → Logs → View Live Logs
```

### Видео не воспроизводится

```
❌ Video.error или пустой экран
```

**Проверить:**
1. Пользователь авторизован (есть session cookie)
2. URL в консоли браузера содержит token
3. Supabase RLS политики правильные

**Отладка:**
```javascript
// В браузер консоли
fetch('/videos/filename.mp4/url').then(r => r.json()).then(console.log)
```

### CORS ошибка

```
❌ Cross-Origin Request Blocked
```

**Решение:**
- Supabase Dashboard → Settings → CORS
- Добавить домен: `https://yourdomain.com`

---

## Файлы которые нужно проверить

- ✅ `requirements.txt` — есть `supabase==1.4.0`
- ✅ `.env` — есть `SUPABASE_URL` и `SUPABASE_KEY`
- ✅ `app/config.py` — импортирует переменные  
- ✅ `app/video_service.py` — создан
- ✅ `app/routers/videos.py` — создан
- ✅ `main.py` — включен `videos.router`
- ✅ `app/models/lesson.py` — есть `video_filename`
- ✅ `static/js/video_upload.js` — создан
- ✅ `static/js/video_playback.js` — создан

---

## Команды для тестирования

### Загрузить видео через curl

```bash
# Получить сессию (залогиниться пользователем в браузере и скопировать session cookie)

curl -X POST \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -F "file=@sample_video.mp4" \
  http://localhost:8000/videos/upload
```

### Получить подписанный URL

```bash
curl -X GET \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  http://localhost:8000/videos/a1b2c3d4e5f6.mp4/url
```

---

## Если нужна помощь

1. **Документация:** [docs/VIDEO_INTEGRATION.md](./VIDEO_INTEGRATION.md)
2. **Supabase Docs:** https://supabase.com/docs/guides/storage
3. **FastAPI Docs:** http://localhost:8000/api/docs (когда запущено)

---

## Что дальше?

- 📝 Посмотреть полную документацию в [docs/VIDEO_INTEGRATION.md](./VIDEO_INTEGRATION.md)
- 🔧 Настроить RLS политики в Supabase для большей безопасности
- 📊 Добавить логирование просмотров видео (опционально)
- 🎥 Рассмотреть сжатие видео для оптимизации (ffmpeg/celery)
