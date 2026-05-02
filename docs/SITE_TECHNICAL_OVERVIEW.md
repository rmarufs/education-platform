# SITE TECHNICAL OVERVIEW

## 1. Что это за продукт

`Фурузон` — серверно-рендеримая образовательная платформа на `FastAPI + Jinja2`, где:

- студенты проходят стартовый ассессмент, получают рекомендации и изучают курсы;
- преподаватели создают курсы, модули, уроки, материалы и тесты;
- администратор модерирует преподавателей, пользователей и курсы.

По текущему коду это не marketplace с покупками и не LMS с отдельной сущностью enrollment. Логика проще:

- студенту доступны страницы курсов без отдельной записи на курс;
- “мой курс” для студента появляется фактически через прогресс по урокам;
- прогресс строится на отметке урока как завершённого;
- тесты сейчас в основном заведены через `Google Forms`-ссылки, хотя в проекте сохранена и собственная встроенная quiz-система.

## 2. Текущий стек

### Backend

- `FastAPI`
- `SQLAlchemy 2.0`
- `Jinja2`
- `Starlette SessionMiddleware`
- `GZipMiddleware`
- `bcrypt`
- `python-dotenv`
- `psycopg2-binary`

### Frontend

- серверный рендеринг HTML через `Jinja2`
- нативный `JavaScript` без frontend framework
- `CSS` в `static/css/style.css`, `mobile.css`, `admin.css`
- клиентская i18n-переводилка `RU/TJ` в `static/js/i18n.js`
- светлая/тёмная тема через `localStorage`

### Данные и файлы

- основная БД: `PostgreSQL` через `DATABASE_URL`
- ORM-модели в `app/models`
- файлы и документы:
  - материалы уроков: `static/materials/`
  - документы преподавателей: `static/documents/`
  - локальные изображения курсов: `static/uploads/course_images/`
- изображения курсов могут уходить в `Cloudinary`

### Runtime / deploy

- точка входа: `main.py`
- приложение: `main:app`
- docs endpoint: `/api/docs`
- production dependency: `gunicorn`

## 3. Архитектурная модель

Приложение построено как монолит с разделением по слоям:

- `main.py`
  - создание `FastAPI` приложения
  - middleware
  - подключение роутеров
  - главная страница
  - startup/init DB
  - глобальные обработчики ошибок
- `app/config.py`
  - загрузка `.env`
  - обязательные переменные окружения
- `app/database.py`
  - engine/session
  - `init_db()`
  - автосоздание таблиц
  - “ручные” миграции через SQL
  - индексы
- `app/models/`
  - SQLAlchemy-сущности
- `app/routers/`
  - пользовательские сценарии и страницы
- `app/quiz_flow.py`
  - отдельный слой бизнес-логики прохождения уроков/квизов
- `templates/`
  - SSR-шаблоны
- `static/js/`
  - UI-поведение, модалки, поиск, rich-text, i18n

Это не JSON API-first система. Основной UX идёт через HTML-страницы и формы, а JSON endpoints используются точечно:

- поиск;
- список курсов;
- сохранение/удаление Google Forms URL;
- API для подстановки данных курса при редактировании.

## 4. Реальная структура проекта

### Ключевые директории

```text
app/
  config.py
  database.py
  dependencies.py
  quiz_flow.py
  models/
  routers/

templates/
  base.html
  index.html
  dashboard_student.html
  dashboard_teacher.html
  course_page.html
  course_manage.html
  lesson_page.html
  quiz_page.html
  search.html
  profile.html
  admin/
  errors/

static/
  css/
  js/
  documents/
  uploads/
  materials/

docs/
  SITE_TECHNICAL_OVERVIEW.md
  PROJECT_STRUCTURE.md
  DEPLOYMENT.md
  ...
```

### Файлы, с которых лучше начинать знакомство

- `main.py` — композиция приложения
- `app/database.py` — БД, init, автодоработки схемы
- `app/routers/courses.py` — самый плотный бизнес-модуль
- `app/routers/lessons.py` — уроки, материалы, прогресс
- `app/routers/quizzes.py` — встроенные квизы и teacher analytics
- `app/quiz_flow.py` — ключевая логика переходов и unlock-механики
- `templates/course_manage.html` — реальный teacher UX
- `templates/course_page.html` — student-facing страница курса
- `static/js/main.js` и `static/js/courses.js` — заметная часть UI-логики

## 5. Роли и права

В системе 4 роли:

- `student`
- `teacher`
- `teacher_pending`
- `admin`

### Как это работает

- первый зарегистрированный пользователь автоматически становится `admin`;
- обычный студент после регистрации попадает на стартовый ассессмент;
- преподаватель при регистрации получает `teacher_pending`;
- только админ одобряет или отклоняет преподавателя;
- заблокированный пользователь (`is_active = false`) не может войти.

### Проверка доступа

- сессия хранит `user_id`, `user_role`, `user_name`;
- авторизация построена на signed cookies через `SessionMiddleware`;
- отдельного JWT нет;
- централизованная dependency-авторизация есть, но часть роутеров проверяет роль локально.

## 6. Главные продуктовые сущности

### `User`

- имя, email, хеш пароля
- роль
- `level` после ассессмента
- флаг завершения ассессмента
- документы и bio преподавателя
- флаг активности

### `Course`

- название, описание, обложка
- уровень `Beginner / Intermediate / Advanced`
- преподаватель
- категория
- рейтинг
- `quiz_url` для внешнего финального теста

### `Module`

- принадлежит курсу
- название, описание
- порядок внутри курса
- `quiz_url`

### `Lesson`

- принадлежит модулю
- название
- `video_url`
- описание
- порядок внутри модуля
- `quiz_url`

### `Material`

- может быть привязан к курсу или уроку
- хранит title, file URL, type

### `Progress`

- уникальная связка `student + lesson`
- фиксирует факт завершения урока
- отдельной модели “запись на курс” нет

### `Review`

- уникальный отзыв студента на курс
- рейтинг 1–5 и текст

### `Comment`

- комментарии под уроком
- есть ответы
- фактически поддерживается древовидность до 2 уровней

### `Quiz / Question / Answer / QuizAttempt / QuizResult`

- встроенная quiz-система
- квиз может принадлежать:
  - уроку
  - модулю
  - курсу
- `QuizAttempt` хранит факт успешного прохождения
- `QuizResult` хранит сохранённые результаты, если `save_results = true`

### `AssessmentResponse`

- ответы стартового опроса студента
- один ответ на пользователя

### `ContactMessage`

- запись из контактной формы

## 7. Основные пользовательские сценарии

### 7.1 Гость

- видит главную, каталог, поиск, about/how-it-works/contact;
- может открыть страницу курса;
- чтобы начать обучение, должен зарегистрироваться или войти.

### 7.2 Студент

#### Онбординг

1. регистрация;
2. если роль `student`, обязательный ассессмент;
3. по сумме 5 ответов выставляется уровень:
   - `<= 6` → `Beginner`
   - `<= 11` → `Intermediate`
   - иначе `Advanced`
4. после этого редирект в каталог.

#### Обучение

- студент открывает курс;
- стартует с первого урока первого модуля;
- вручную отмечает урок как завершённый;
- после завершения урока система вычисляет next step:
  - квиз урока;
  - следующий урок;
  - квиз модуля;
  - следующий модуль;
  - квиз курса;
  - страница завершения курса.

#### Прогресс

- прогресс считается по completed lessons;
- student dashboard показывает только те курсы, где уже есть progress;
- на странице курса строится процент завершения;
- в профиле также собирается прогресс по курсам.

#### Коммуникация и social

- может оставлять отзыв на курс;
- может писать комментарии под уроком и отвечать на комментарии.

### 7.3 Преподаватель

#### После одобрения

- получает teacher dashboard;
- может создавать и редактировать только свои курсы.

#### Управление контентом

- создаёт курс;
- задаёт категорию, уровень, описание, обложку;
- прикрепляет course-level материалы;
- создаёт модули;
- в модулях создаёт уроки;
- к урокам добавляет видео, описание, файлы и тесты.

#### Тесты

Сейчас по UI основной сценарий идёт через `Google Forms`:

- преподаватель сохраняет URL формы для курса/модуля/урока;
- студент проходит её во встроенном iframe-оверлее.

В проекте также есть своя встроенная quiz-система:

- создание quiz для course/module/lesson;
- создание single/multiple/open вопросов;
- сохранение результатов;
- teacher analytics.

Но в основных student/teacher шаблонах встроенные карточки квизов местами выключены через `if false`, поэтому надо считать систему “частично сохранённой, но не главным текущим UX”.

#### Аналитика

- teacher manage page показывает активность студентов по курсу;
- есть отдельные страницы с результатами квизов преподавателя.

### 7.4 Администратор

- обзор платформы;
- заявки преподавателей;
- список пользователей;
- блокировка / разблокировка пользователей;
- удаление пользователей;
- просмотр и удаление курсов;
- экспорт ассессментов в CSV.

## 8. Бизнес-логика, которую важно понимать

### 8.1 Прогресс строится от уроков, а не от enrolment

Ключевой момент: в БД нет отдельной модели “студент записан на курс”.

Следствие:

- “доступ к курсу” по сути открыт;
- “мой курс” определяется косвенно, если у студента есть записи в `progress`;
- student dashboard не отражает “сохранённые/избранные/купленные” курсы, только начатые.

### 8.2 Ассессмент влияет на рекомендации

Маршрут `/courses/recommended` строит выборку по `user.level`:

- `Beginner` → только beginner-курсы;
- `Intermediate` → beginner + intermediate;
- `Advanced` → все курсы.

Рекомендации сейчас простые и rule-based, без персонализации.

### 8.3 Рейтинг курса считается по отзывам

- студент может иметь только один отзыв на курс;
- повторная отправка обновляет существующий отзыв;
- после сохранения средний рейтинг курса пересчитывается.

### 8.4 Unlock логика квизов вынесена в `app/quiz_flow.py`

Это отдельный важный модуль.

Правила:

- lesson quiz открывается после завершения урока;
- module quiz открывается только когда:
  - завершены все уроки модуля;
  - пройдены все lesson-level quizzes этого модуля;
- course quiz открывается только когда завершены все модули и их квизы;
- после успешного прохождения квиза система вычисляет, куда вести студента дальше.

### 8.5 Проходной балл встроенного квиза

`QUIZ_PASS_PERCENTAGE = 80`, но проверка сделана как:

- `passed = percentage > 80`

То есть `80%` по текущему коду не считается прохождением. Это надо знать как фактическое поведение системы.

### 8.6 Документы преподавателя

- на регистрации преподаватель может загрузить PDF/JPG/JPEG/PNG/WEBP;
- файл хранится локально в `static/documents/`;
- при reject администратор удаляет документ и переводит пользователя обратно в `student`.

## 9. Реальные роуты и функциональные модули

### Auth

`app/routers/auth.py`

- `/register` `GET/POST`
- `/register/pending`
- `/login` `GET/POST`
- `/logout`

### User flows

`app/routers/users.py`

- `/dashboard`
- `/assessment` `GET/POST`
- `/dashboard/student`
- `/dashboard/teacher`

### Courses

`app/routers/courses.py`

- `/courses/catalog`
- `/courses/api/list`
- `/courses/recommended`
- `/courses/create`
- `/courses/{course_id}`
- `/courses/{course_id}/manage`
- `/courses/{course_id}/edit`
- `/courses/{course_id}/delete`
- `/courses/{course_id}/completed`
- `/courses/api/quiz-url` `POST/DELETE`
- `/courses/materials/{material_id}/delete`
- `/courses/api/{course_id}`

### Modules

`app/routers/modules.py`

- `/modules/create`
- `/modules/{module_id}/edit`
- `/modules/{module_id}/delete`

### Lessons

`app/routers/lessons.py`

- `/lessons/create`
- `/lessons/{lesson_id}`
- `/lessons/{lesson_id}/edit`
- `/lessons/{lesson_id}/delete`
- `/lessons/{lesson_id}/material`
- `/lessons/{lesson_id}/upload`
- `/lessons/{lesson_id}/complete`
- `/lessons/{lesson_id}/continue`

### Reviews and comments

- `/courses/{course_id}/review`
- `/lessons/{lesson_id}/comment`
- `/comments/{comment_id}/reply`

### Pages and search

`app/routers/pages.py`

- `/about`
- `/how-it-works`
- `/contact` `GET/POST`
- `/search`
- `/api/search`
- `/teachers/{teacher_id}`

### Profile

`app/routers/profile.py`

- `/profile`

### Quizzes

`app/routers/quizzes.py`

- `/quiz/create`
- `/quiz/{quiz_id}`
- `/quiz/{quiz_id}/submit`
- `/quiz/{quiz_id}/settings`
- `/quiz/{quiz_id}/question`
- `/dashboard/teacher/quiz-results`
- `/dashboard/teacher/quiz-results/{quiz_id}`

### Admin

`app/routers/admin.py`

- `/admin`
- `/admin/teachers`
- `/admin/teachers/{user_id}/approve`
- `/admin/teachers/{user_id}/reject`
- `/admin/users`
- `/admin/users/{user_id}/toggle-active`
- `/admin/users/{user_id}/delete`
- `/admin/courses`
- `/admin/courses/{course_id}/delete`
- `/admin/export-assessments`

## 10. Frontend-логика

### Общий UI слой

`templates/base.html`:

- навигация;
- тема light/dark;
- RU/TJ переключение языка;
- mobile menu;
- logout confirm modal;
- подключение общих JS/CSS.

### i18n

`static/js/i18n.js`:

- словарь переводов на `ru` и `tj`;
- переводы применяются на клиенте через `data-i18n` атрибуты;
- язык сохраняется в `localStorage`.

### Rich text

`static/js/richtext.js`:

- самописный редактор поверх `contenteditable`;
- поддержка базового форматирования;
- HTML сохраняется в hidden input;
- используется в формах описания курсов/модулей/уроков.

### UI-скрипты

`static/js/main.js`:

- тосты;
- reveal-анимации;
- Google Forms modal/iframe;
- общие вспомогательные UI-функции.

`static/js/courses.js`:

- модалки create/edit course;
- preview/drag&drop обложки;
- валидация изображения;
- часть управления курсом на клиенте.

`static/js/auth.js`:

- клиентская валидация login/register.

`static/js/quiz_builder.js`:

- динамика конструктора встроенных квизов.

### Поиск

`templates/search.html`:

- frontend сам вызывает `/api/search`;
- фильтры:
  - текст;
  - категория;
  - уровень;
  - сортировка;
- есть client-side render карточек и пагинации.

## 11. Данные, интеграции и хранение файлов

### Переменные окружения

Сейчас код требует обязательные env:

- `SECRET_KEY`
- `DATABASE_URL`
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

Опционально:

- `PLATFORM_NAME`
- `SESSION_MAX_AGE`

### Что реально интегрировано

- `Cloudinary` для обложек курсов
- `Google Forms` как внешний механизм тестов
- `Google Fonts`
- `YouTube`/внешние видео по `video_url`

### Что не подтверждается текущим кодом

В репозитории есть старые упоминания `Supabase`, `JWT`, `CORS`, отдельного video-service, но в текущем коде, который реально исполняется, этого нет как активной части приложения.

## 12. База данных и инициализация

`app/database.py` делает три вещи на старте:

1. `Base.metadata.create_all(...)`
2. запускает ручные доработки схемы в `_migrate_enum_and_columns()`
3. создаёт индексы в `_create_performance_indexes()`

Это значит:

- миграции не вынесены в Alembic;
- схема частично “эволюционирует” на runtime;
- часть поведения зависит от startup приложения.

Для нового сильного инженера это важный сигнал: текущее управление схемой скорее ad-hoc, чем дисциплинированный migration pipeline.

## 13. Текущее состояние продукта по коду

### Что уже выглядит рабочим

- регистрация / логин / сессии
- роли и модерация преподавателей
- CRUD курсов / модулей / уроков
- загрузка материалов
- student progress
- отзывы и комментарии
- поиск
- teacher dashboards
- admin panel

### Что выглядит переходным состоянием

- coexistence двух систем тестов:
  - `Google Forms` как текущий рабочий UX
  - встроенные квизы как сохранённая, но не везде активная логика

### Что отсутствует

- automated tests
- полноценные DB migrations через Alembic
- единая permission architecture
- сущность enrollment/subscription/purchase
- email notifications
- API versioning
- SPA/frontend framework

## 14. Технический долг и риски

### Архитектурные

- бизнес-логика размазана между роутерами, шаблонами и JS;
- много серверных форм и редиректов, мало явной доменной изоляции;
- часть проверок доступа дублируется вручную в каждом роутере.

### По данным и БД

- runtime-миграции вместо нормального migration workflow;
- в `_create_performance_indexes()` есть попытка создать индекс по `comments.author_id`, хотя модель комментария использует `user_id`;
- проект опирается на eager loading и ручные оптимизации, но без тестов производительности.

### По продуктовой логике

- нет отдельной записи студента на курс;
- прохождение курса основано только на `Progress`;
- встроенный quiz pass threshold фактически `> 80`, а не `>= 80`.

### По документации

- текущий `README.md` местами расходится с фактическим состоянием репозитория;
- новому специалисту лучше доверять именно коду, а не старым описаниям.

## 15. Как бы я объяснил проект новому senior-специалисту в двух фразах

Это монолитная LMS-платформа на `FastAPI + SSR Jinja2`, где роли, контент и учебные сценарии уже работают, но архитектура ещё находится между MVP и production-hardening. Основной контентный поток стабилен, а вот слой тестов, миграций и модели “записи на курс” требуют продуктового и технического доопределения.

## 16. Что смотреть в первую очередь, если нужно продолжать разработку

### Если задача про продуктовые сценарии

- `app/routers/courses.py`
- `app/routers/lessons.py`
- `app/quiz_flow.py`

### Если задача про роли и доступы

- `app/routers/auth.py`
- `app/routers/users.py`
- `app/routers/admin.py`
- `app/dependencies.py`

### Если задача про teacher UX

- `templates/dashboard_teacher.html`
- `templates/course_manage.html`
- `templates/_quiz_authoring_macros.html`
- `static/js/courses.js`

### Если задача про student UX

- `templates/course_page.html`
- `templates/lesson_page.html`
- `templates/dashboard_student.html`
- `templates/search.html`

### Если задача про схему данных

- `app/models/*`
- `app/database.py`

## 17. Итог

По факту это образовательная платформа с:

- авторизацией по cookie-session;
- ролями `student / teacher / teacher_pending / admin`;
- курсами, модулями, уроками и материалами;
- прогрессом студентов;
- рекомендациями после стартового ассессмента;
- отзывами, комментариями и teacher/admin кабинетами;
- текущим production-потоком тестов через `Google Forms`;
- сохранённой встроенной quiz-системой как вторым, не до конца выключенным слоем.

Если передавать проект сильному специалисту, этого документа достаточно как стартовой карты: что это за сайт, где лежит логика, как устроены данные, какие сценарии уже есть и где находятся текущие ограничения.
