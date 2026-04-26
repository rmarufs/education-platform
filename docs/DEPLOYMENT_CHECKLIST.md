# ✅ Видео Интеграция - Чеклист Внедрения

## Развёртывание

### Локальное развёртывание

- [ ] **Шаг 1: Обновить requirements.txt**
  - ✅ Добавлено: `supabase==1.4.0`
  - Проверка: `grep supabase requirements.txt`

- [ ] **Шаг 2: Установить зависимости**
  ```bash
  pip install supabase==1.4.0
  # или
  pip install -r requirements.txt
  ```

- [ ] **Шаг 3: Создать Supabase проект**
  - Зайти на https://supabase.com
  - Создать новый проект или выбрать существующий
  - Скопировать:
    - `Project URL` → `SUPABASE_URL`
    - `Anon Public Key` → `SUPABASE_KEY`

- [ ] **Шаг 4: Установить переменные окружения**
  - Создать/обновить `.env`:
    ```env
    SUPABASE_URL=https://your-project.supabase.co
    SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    ```

- [ ] **Шаг 5: Запустить приложение**
  ```bash
  python main.py
  # Должна вывести: ✅ Фурузон запущен. База данных инициализирована.
  # Миграция БД выполнится автоматически
  ```

- [ ] **Шаг 6: Проверить в браузере**
  ```
  http://localhost:8000
  ```

### Развёртывание на Render

- [ ] **Шаг 1: Добавить переменные окружения**
  - Settings → Environment
  - Добавить:
    - `SUPABASE_URL` = `https://your-project.supabase.co`
    - `SUPABASE_KEY` = `your-anon-key`

- [ ] **Шаг 2: Выложить код**
  - `git push` на главную ветку
  - Render автоматически задеплоит

- [ ] **Шаг 3: Проверить логи**
  - Settings → Logs
  - Должно быть: `✅ ...запущен. База данных инициализирована.`

- [ ] **Шаг 4: Тестировать**
  - Залогиниться как учитель
  - Создать урок с видео
  - Смотреть как ученик

---

## Тестирование

### Функциональное тестирование

- [ ] **Загрузка видео**
  - [ ] Перетащить видео в зону (drag & drop)
  - [ ] Нажать на зону для выбора файла
  - [ ] Видео валидируется (формат, размер)
  - [ ] Показывается статус "⏳ Загрузка видео..."
  - [ ] После загрузки: "✅ Видео загружено успешно"
  - [ ] Filename сохраняется в форму

- [ ] **Создание урока**
  - [ ] Заполнить: название, описание
  - [ ] Загрузить видео ИЛИ вставить YouTube ссылку
  - [ ] Создать урок
  - [ ] Урок сохранён с видео (🎬 иконка)

- [ ] **Редактирование урока**
  - [ ] Открыть существующий урок для редактирования
  - [ ] Видно загруженное видео (превью)
  - [ ] Можно загрузить новое видео
  - [ ] Можно изменить YouTube ссылку
  - [ ] Сохранить изменения

- [ ] **Воспроизведение видео (ученик)**
  - [ ] Открыть урок как ученик
  - [ ] Видеоплеер загружается
  - [ ] Видео воспроизводится
  - [ ] Кнопки управления работают (Play, Pause, Volume)
  - [ ] Прогресс-бар меняется

- [ ] **YouTube видео (обратная совместимость)**
  - [ ] Добавить YouTube ссылку
  - [ ] Урок сохранён 
  - [ ] YouTube iframe отображается корректно
  - [ ] Видео воспроизводится

- [ ] **Иконки в интерфейсе**
  - [ ] 🎬 иконка для уроков с видео (оба типа)
  - [ ] 📄 иконка для уроков без видео
  - [ ] ✅ иконка для завершённых уроков

### Ошибки и edge cases

- [ ] **Файл слишком большой (>100MB)**
  - [ ] Ошибка на загрузку: "❌ Файл слишком большой"
  - [ ] Урок не создаётся

- [ ] **Неподдерживаемый формат (не видео)**
  - [ ] Ошибка на загрузку: "❌ Недопустимый формат видео"
  - [ ] Урок не создаётся

- [ ] **Потеря соединения при загрузке**
  - [ ] Повторить загрузку
  - [ ] Видео загружается повторно

- [ ] **Истечение подписанной URL (>2 мин)**
  - [ ] При обновлении страницы: новый URL
  - [ ] Видео продолжает воспроизведение

- [ ] **Не авторизован (нет session)**
  - [ ] Error 401 при попытке получить URL
  - [ ] Ошибка на видеоплеере: "❌ Вы не авторизованы"

- [ ] **Учитель не может загружать (student)**
  - [ ] Error 403 на `/videos/upload`
  - [ ] Форма не активна

---

## Верификация компонентов

### Backend компоненты

- [ ] **app/video_service.py**
  - [ ] Создан
  - [ ] Методы: `upload_video()`, `get_signed_url()`, `delete_video()`
  - [ ] Обработка ошибок Supabase
  - [ ] Логирование операций

- [ ] **app/routers/videos.py**
  - [ ] Создан с двумя endpoints
  - [ ] `POST /videos/upload` — требует auth (teacher)
  - [ ] `GET /videos/{filename}/url` — требует auth (any)
  - [ ] Возвращает корректные JSON ответы

- [ ] **app/config.py**
  - [ ] Добавлены `SUPABASE_URL` и `SUPABASE_KEY`
  - [ ] Переменные валидируются (`_get_required_env`)
  - [ ] При отсутствии — выбрасывает ошибку

- [ ] **app/models/lesson.py**
  - [ ] Добавлено поле `video_filename`
  - [ ] Тип: `String(255), nullable=True`
  - [ ] Существует наряду с `video_url`

- [ ] **app/routers/lessons.py**
  - [ ] `create_lesson()` принимает `video_filename`
  - [ ] `edit_lesson()` принимает `video_filename`
  - [ ] Сохраняет оба поля в БД

- [ ] **app/init_video_tables.py**
  - [ ] Создан
  - [ ] Выполняет миграцию БД при старте
  - [ ] Логирует результаты

- [ ] **main.py**
  - [ ] Импортирован `from app.routers import videos`
  - [ ] Зарегистрирован `app.include_router(videos.router)`
  - [ ] Импортирован `from app.init_video_tables import init_video_tables`
  - [ ] Вызван `init_video_tables()` в `@app.on_event("startup")`

### Frontend компоненты

- [ ] **static/js/video_upload.js**
  - [ ] Создан
  - [ ] Класс `VideoUploadManager` инициализируется
  - [ ] Drag & drop события работают
  - [ ] Валидация файла (тип, размер)
  - [ ] Отправка POST на `/videos/upload`
  - [ ] Сохранение filename в `[name="video_filename"]`
  - [ ] Показ статуса загрузки
  - [ ] Превью загруженного файла

- [ ] **static/js/video_playback.js**
  - [ ] Создан
  - [ ] Класс `SecureVideoPlayer` инициализируется
  - [ ] Получает filename из `data-video-filename`
  - [ ] Отправляет GET на `/videos/{filename}/url`
  - [ ] Создаёт `<video>` элемент
  - [ ] Устанавливает `src` в подписанный URL
  - [ ] Обновляет URL каждые 100 сек

- [ ] **static/css/video_upload.css**
  - [ ] Создан
  - [ ] Стили для `.video-upload-zone`
  - [ ] Состояния: normal, dragover, uploading, success, error
  - [ ] Адаптивный дизайн (mobile-friendly)
  - [ ] Стили для `.video-upload-status`

- [ ] **templates/course_manage.html**
  - [ ] Обновлена форма добавления урока
  - [ ] Добавлена drag & drop зона (вместо YouTube поля)
  - [ ] Две опции: загрузка + YouTube ссылка
  - [ ] Поле `video_filename` скрыто
  - [ ] Script включает `video_upload.js`
  - [ ] Функции `openAddLessonModal()` и `openEditLessonModal()` обновлены
  - [ ] Иконка 🎬 учитывает оба `video_url` и `video_filename`

- [ ] **templates/lesson_page.html**
  - [ ] Updated video section для обоих типов видео
  - [ ] `data-video-filename` на `.video-container` если загруженное видео
  - [ ] YouTube iframe если `video_url`
  - [ ] Placeholder если нет видео
  - [ ] Script `video_playback.js` подключен
  - [ ] Иконки в боковой панели учитывают оба типа

- [ ] **templates/course_page.html**
  - [ ] Иконка в списке уроков учитывает оба `video_url` и `video_filename`

- [ ] **templates/base.html**
  - [ ] Добавлена ссылка на `video_upload.css`

### База данных

- [ ] **migrations/001_add_video_filename.sql**
  - [ ] Создан файл
  - [ ] Содержит ALTER TABLE для добавления колонки
  - [ ] Содержит CREATE INDEX для оптимизации

- [ ] **Миграция автоматическая**
  - [ ] При старте приложения: `init_video_tables()`
  - [ ] Добавляет колонку без ошибок (IF NOT EXISTS)
  - [ ] Логирует результат

### Документация

- [ ] **docs/VIDEO_INTEGRATION.md**
  - [ ] Полная техническая документация
  - [ ] Архитектура, API, диаграммы
  - [ ] Примеры использования
  - [ ] Troubleshooting

- [ ] **QUICKSTART_VIDEO.md**
  - [ ] Быстрый старт за 5 минут
  - [ ] Пошаговые инструкции
  - [ ] Проверка что работает

- [ ] **VIDEO_IMPLEMENTATION_SUMMARY.md**
  - [ ] Итоговый отчёт
  - [ ] Что было сделано
  - [ ] Как использовать
  - [ ] Рекомендации для продакшена

---

## Production Checklist

- [ ] **Supabase Production Setup**
  - [ ] Bucket `videos` создан
  - [ ] Bucket установлен как PRIVATE
  - [ ] RLS политики настроены
  - [ ] CORS настроены (добавлен домен приложения)

- [ ] **Безопасность**
  - [ ] Переменные окружения надёжно хранены (не в git)
  - [ ] SUPABASE_KEY это anon key (не service role)
  - [ ] Логирование включено для audit trail
  - [ ] Backup стратегия для videos bucket

- [ ] **Мониторинг**
  - [ ] Логирование ошибок Supabase
  - [ ] Алерты на failed uploads
  - [ ] Отслеживание использования storage

- [ ] **Performance**
  - [ ] Проверить скорость загрузки видео
  - [ ] Проверить скорость получения подписанных URL
  - [ ] Проверить потребление bandwidth

- [ ] **Scaling**
  - [ ] Supabase plan позволяет ожидаемый объём данных
  - [ ] Нет бутылочек в коде
  - [ ] Rate limiting (если нужно)

---

## Rollback Plan

Если что-то не работает:

1. **Откатить код:**
   ```bash
   git revert <commit-hash>
   git push
   ```

2. **Отключить видео функцию:**
   - Переименовать `app/routers/videos.py` в `_videos.py`
   - Закомментировать импорт в `main.py`
   - Перезагрузить приложение

3. **Восстановить БД:**
   ```bash
   ALTER TABLE lessons DROP COLUMN IF EXISTS video_filename;
   ```

---

## Знов Features (для будущего)

После основной функцию готовы рассмотреть:

- [ ] Автоматическое сжатие видео (ffmpeg)
- [ ] Генерация thumbnail из первого кадра
- [ ] Субтитры (ASR + SRT)
- [ ] Статистика просмотров видео
- [ ] Ограничение скачиваний
- [ ] Live streaming (HLS)
- [ ] Video chapters/timeline
- [ ] Adaptive bitrate streaming

---

## Финальная Проверка

```bash
# Синтаксис Python
python -m py_compile app/video_service.py app/routers/videos.py app/init_video_tables.py

# Конфиг
grep -c "SUPABASE" app/config.py
# Должно быть: 2 (URL и KEY)

# Роуты
grep -c "videos" main.py
# Должно быть: 2 (import + include_router)

# Модель
grep "video_filename" app/models/lesson.py
# Должно найти поле

# Файлы
ls -la app/video_service.py app/routers/videos.py static/js/video_*.js
# Все файлы существуют
```

---

**Статус:** ✅ ВСЛ ГОТОВО К РАЗВЁРТЫВАНИЮ

Следуйте чеклисту и видео интеграция будет работать как часы! 🚀
