/**
 * i18n.js — Поддержка двух языков: русский (ru) и таджикский (tj)
 * Переключение происходит без перезагрузки страницы.
 */

const translations = {
  ru: {
    // Навигация
    "nav.home":        "Главная",
    "nav.dashboard":   "Кабинет",
    "nav.login":       "Войти",
    "nav.register":    "Регистрация",
    "nav.logout":      "Выйти",
    "nav.courses":     "Курсы",
    "nav.my_courses":  "Мои курсы",
    "nav.hello":       "Привет, {name}",
    "base.description": "EduHub — современная образовательная платформа для студентов и преподавателей",

    // Подвал
    "footer.rights": "Все права защищены.",

    // Hero
    "hero.title":    "Учись. Развивайся. Достигай.",
    "hero.subtitle": "Современная платформа для студентов и преподавателей. Открой доступ к знаниям прямо сейчас.",
    "hero.cta_register": "Начать бесплатно",
    "hero.cta_login":    "Войти в аккаунт",
    "hero.card1": "Качественные курсы",
    "hero.card2": "Достижения",
    "hero.card3": "Лучшие преподаватели",

    // Статистика
    "stats.students": "Студентов",
    "stats.courses":  "Курсов",
    "stats.teachers": "Преподавателей",

    // Главная страница
    "home.popular_courses":     "Популярные курсы",
    "home.popular_courses_sub": "Начни обучение с лучших программ нашей платформы",
    "home.no_courses":          "Курсы пока не добавлены. Зарегистрируйся как преподаватель и создай первый!",
    "home.why_us":              "Почему EduHub?",

    // Особенности
    "feature.fast":         "Быстрый старт",
    "feature.fast_desc":    "Зарегистрируйся за пару минут и сразу начинай обучение",
    "feature.focused":      "Целевое обучение",
    "feature.focused_desc": "Чёткие курсы от опытных преподавателей без лишней воды",
    "feature.simple":       "Простой интерфейс",
    "feature.simple_desc":  "Удобная платформа без лишней сложности",

    // Формы
    "form.email":    "Email",
    "form.password": "Пароль",
    "form.name":     "Ваше имя",
    "form.role":     "Я являюсь",
    "form.name_ph":  "Иван Иванов",
    "form.email_ph": "you@example.com",
    "form.pass_ph":  "••••••••",
    "form.pass_min_ph": "Минимум 6 символов",

    // Роли
    "role.student": "Студент",
    "role.teacher": "Преподаватель",

    // Страница входа
    "login.title_page":    "Вход — EduHub",
    "login.title":         "Вход в аккаунт",
    "login.subtitle":      "Рады видеть вас снова!",
    "login.submit":        "Войти",
    "login.no_account":    "Нет аккаунта?",
    "login.register_link": "Зарегистрироваться",

    // Регистрация
    "register.title_page":   "Регистрация — EduHub",
    "register.title":        "Создать аккаунт",
    "register.subtitle":     "Присоединяйтесь к тысячам учеников и преподавателей",
    "register.submit":       "Зарегистрироваться",
    "register.have_account": "Уже есть аккаунт?",
    "register.login_link":   "Войти",

    // Кабинет студента
    "student.welcome":     "Добро пожаловать,",
    "student.subtitle":    "Продолжай обучение — все курсы платформы доступны тебе",
    "student.all_courses": "Все курсы",
    "student.no_courses":  "Пока нет доступных курсов. Загляни позже!",

    // Кабинет преподавателя
    "teacher.welcome":       "Добро пожаловать,",
    "teacher.subtitle":      "Управляйте своими курсами и помогайте студентам учиться",
    "teacher.add_course":    "+ Создать курс",
    "teacher.my_courses":    "Мои курсы",
    "teacher.no_courses":    "У вас пока нет курсов. Создайте первый!",
    "teacher.create_course": "Создать новый курс",
    "teacher.edit_course":   "Редактировать курс",
    "teacher.manage":        "Управление курсом",

    // Курс
    "course.open":           "Открыть курс",
    "course.view":           "Просмотр",
    "course.edit":           "Изменить",
    "course.delete":         "Удалить",
    "course.badge":          "Курс",
    "course.about":          "О курсе",
    "course.no_description": "Описание курса пока не добавлено.",
    "course.teacher":        "Преподаватель",
    "course.created_at":     "Дата создания",
    "course.enroll":         "Записаться на курс",
    "course.enrolled":       "Курс доступен вам",
    "course.title":          "Название курса",
    "course.description":    "Описание",

    // Действия
    "action.cancel": "Отмена",
    "action.create": "Создать",
    "action.save":   "Сохранить",
    "action.delete": "Удалить",

    // Валидация
    "validation.name_required":     "Введите ваше имя",
    "validation.email_required":    "Введите email",
    "validation.email_invalid":     "Введите корректный email",
    "validation.password_required": "Введите пароль",
    "validation.password_short":    "Пароль должен быть не менее 6 символов",
    "validation.title_required":    "Введите название курса",

    // Общие (Common)
    "common.error_delete": "Ошибка при удалении",
    "common.error_conn":   "Ошибка соединения",
    "common.no_desc":      "Нет описания",
    "common.no_rating":    "Нет оценок",
    "common.back_cab":     "Вернуться в кабинет",
    "common.reset":        "Сброс",
    "common.search_btn":   "🔍 Найти",

    // Каталог курсов
    "catalog.title":       "📚 Курсы",
    "catalog.search":      "Поиск курсов...",
    "catalog.all_cat":     "Все категории",
    "catalog.results":     "Результаты по запросу: «{q}» — {count} курс(ов)",
    "catalog.empty_q":     "Ничего не найдено по запросу «{q}»",
    "catalog.empty":       "Курсов пока нет",
    "catalog.view_all":    "Посмотреть все курсы",
    "catalog.open":        "Открыть →",

    // Управление курсом
    "manage.back":           "← Мои курсы",
    "manage.materials":      "Материалы курса:",
    "manage.del_file":       "Удалить файл?",
    "manage.view":           "👁 Просмотр",
    "manage.edit":           "✏️ Редактировать",
    "manage.modules_lbl":    "Модули курса",
    "manage.files_count":    "{count} файл(ов)",
    "manage.no_lessons":     "Уроков ещё нет",
    "manage.add_lesson":     "+ Добавить урок",
    "manage.no_modules":     "Модулей ещё нет. Добавьте первый!",
    "manage.new_mod_ph":     "Название нового модуля",
    "manage.add_mod_btn":    "+ Модуль",
    "manage.activity_lbl":   "Активность студентов",
    "manage.student":        "Студент",
    "manage.progress":       "Прогресс",
    "manage.passed_lessons": "Пройдено уроков",
    "manage.last_active":    "Последняя активность",
    "manage.no_data":        "Нет данных",
    "manage.no_students":    "Пока нет студентов, начавших обучение на этом курсе.",
    "manage.confirm_delete_course": "Вы уверены, что хотите удалить этот курс?",
    "manage.confirm_del_mod": "Удалить модуль со всеми уроками?",
    "manage.new_lesson":     "Новый урок",
    "manage.lesson_title":   "Название урока",
    "manage.lesson_video":   "Ссылка на видео (YouTube/Vimeo)",
    "manage.lesson_desc":    "Описание / текст",
    "manage.lesson_create":  "Создать урок",

    // Страница курса
    "course_page.breadcrumbs_home": "Главная",
    "course_page.breadcrumbs_cat":  "Курсы",
    "course_page.reviews_count":    "({count} отзыв(ов))",
    "course_page.about":            "О курсе",
    "course_page.materials":        "📎 Материалы курса",
    "course_page.progress":         "Прогресс: {pct}%",
    "course_page.content":          "Содержание курса",
    "course_page.lessons_count":    "{count} урок(ов)",
    "course_page.reviews":          "⭐ Отзывы ({count})",
    "course_page.leave_review":     "Оставить отзыв",
    "course_page.edit_review":      "Изменить отзыв",
    "course_page.review_ph":        "Ваш отзыв о курсе...",
    "course_page.send_review":      "Отправить отзыв",
    "course_page.teacher":          "Преподаватель",
    "course_page.modules_count":    "Модулей",
    "course_page.created":          "Создан",
    "course_page.rating":           "Рейтинг",
    "course_page.start_learning":   "Начать обучение",
    "course_page.login_btn":        "Войти",
    "course_page.gear_manage":      "⚙️ Управление",
    "course_page.avail":            "✅ Курс доступен вам",
    "course_page.start_continue":   "▶ Начать / Продолжить",

    // Урок
    "lesson.back_course":    "← {title}",
    "lesson.materials":      "📎 Материалы",
    "lesson.quiz":           "Пройти квиз →",
    "lesson.questions":      "{count} вопрос(ов)",
    "lesson.done":           "✅ Урок завершён",
    "lesson.mark_done":      "✅ Отметить как пройденный",
    "lesson.tools":          "⚙️ Инструменты преподавателя",
    "lesson.add_mat":        "📎 Добавить материал",
    "lesson.mat_title":      "Название",
    "lesson.mat_link":       "Ссылка на файл",
    "lesson.mat_type_oth":   "Другое",
    "lesson.mat_add":        "Добавить",
    "lesson.create_quiz":    "🧠 Создать квиз",
    "lesson.quiz_title":     "Название квиза",
    "lesson.quiz_create":    "Создать",
    "lesson.quiz_exists":    "🧠 Квиз уже создан",
    "lesson.quiz_open":      "Открыть квиз",
    "lesson.q_text":         "Текст вопроса",
    "lesson.q_single":       "Один ответ",
    "lesson.q_multi":        "Несколько ответов",
    "lesson.ans_correct":    "Правильный",
    "lesson.add_variant":    "+ Вариант",
    "lesson.add_q":          "Добавить вопрос",
    "lesson.qa":             "💬 Вопросы и ответы",
    "lesson.ask_ph":         "Задайте вопрос...",
    "lesson.send":           "Отправить",
    "lesson.login_req":      "Войдите, чтобы оставить комментарий",
    "lesson.reply_ph":       "Ответить...",
    "lesson.reply_btn":      "↩ Ответить",
    "lesson.no_comments":    "Комментариев ещё нет. Будьте первым!",

    // Квиз
    "quiz.result":       "Результат: {score}%",
    "quiz.correct_of":   "Правильных ответов: <strong>{correct}</strong> из <strong>{total}</strong>",
    "quiz.success":      "Отлично! Вы отлично справились!",
    "quiz.warning":      "Неплохо! Повторите материал и попробуйте снова.",
    "quiz.error":        "Рекомендуем пересмотреть урок перед повторной попыткой.",
    "quiz.retry":        "Пройти ещё раз",
    "quiz.back_lesson":  "← Вернуться к уроку",
    "quiz.q_count":      "{count} вопрос(ов)",
    "quiz.q_num":        "Вопрос {num}",
    "quiz.submit":       "Отправить ответы →",

    // Профиль 
    "profile.teacher":       "👨‍🏫 Преподаватель",
    "profile.student":       "👩‍🎓 Студент",
    "profile.my_cab":        "Мой кабинет",
    "profile.my_courses":    "📚 Мои курсы ({count})",
    "profile.course_stat":   "{modules} модул(ей) · {lessons} урок(ов)",
    "profile.no_created":    "Вы ещё не создали ни одного курса",
    "profile.create_btn":    "Создать курс",
    "profile.my_progress":   "📈 Мой прогресс",
    "profile.passed_of":     "{done} / {total} уроков пройдено",
    "profile.no_started":    "Вы ещё не начали ни одного курса",
    "profile.find_courses":  "Найти курсы",
    "profile.my_reviews":    "⭐ Мои отзывы",

    // Assessment
    "ass.title":         "Добро пожаловать!",
    "ass.subtitle":      "Чтобы предложить вам наиболее подходящие курсы, пожалуйста, ответьте на несколько коротких вопросов. Это поможет определить ваш текущий уровень подготовки.",
    "ass.q1":            "1. Как вы оцениваете свой текущий уровень по математике?",
    "ass.q1_1":          "Я плохо понимаю базовые темы",
    "ass.q1_2":          "Понимаю основы, но решаю задачи с трудом",
    "ass.q1_3":          "Средний уровень, могу решать многие задачи",
    "ass.q1_4":          "Хороший уровень, готовлюсь к сложным задачам тестирования",
    "ass.q2":            "2. Насколько уверенно вы решаете задачи из национального тестирования?",
    "ass.q2_1":          "Почти не могу решать",
    "ass.q2_2":          "Иногда могу решить простые",
    "ass.q2_3":          "Могу решать средние задачи",
    "ass.q2_4":          "Уверенно решаю большинство задач",
    "ass.q3":            "3. Сколько времени вы уже готовитесь к поступлению?",
    "ass.q3_1":          "Ещё не начинал",
    "ass.q3_2":          "Менее 3 месяцев",
    "ass.q3_3":          "3–6 месяцев",
    "ass.q3_4":          "Более 6 месяцев",
    "ass.q4":            "4. Какая цель обучения для вас сейчас?",
    "ass.q4_1":          "Понять базовые темы",
    "ass.q4_2":          "Подтянуть школьную программу",
    "ass.q4_3":          "Подготовиться к тестированию",
    "ass.q4_4":          "Улучшить результаты и решать сложные задачи",
    "ass.q5":            "5. Сколько времени в неделю вы готовы уделять обучению?",
    "ass.q5_1":          "1–2 часа",
    "ass.q5_2":          "3–5 часов",
    "ass.q5_3":          "6–10 часов",
    "ass.q5_4":          "Более 10 часов",
    "ass.submit":        "Завершить и посмотреть подходящие курсы",

    // Рекомендованные
    "rec.title":         "Recommended Courses",
    "rec.level":         "Ваш текущий уровень:",
    "rec.desc":          "Мы подобрали для вас программы, которые идеально соответствуют вашим знаниям и целям.",
    "rec.go_course":     "Перейти к курсу",
    "rec.empty_p1":      "К сожалению, подходящих курсов пока нет. Попробуйте изучить полный каталог.",
    "rec.full_cat":      "Полный каталог"
  },

  tj: {
    // Навигация
    "nav.home":        "Саҳифаи асосӣ",
    "nav.dashboard":   "Кабинет",
    "nav.login":       "Даромадан",
    "nav.register":    "Бақайдгирӣ",
    "nav.logout":      "Баромадан",
    "nav.courses":     "Курсҳо",
    "nav.my_courses":  "Курсҳои ман",
    "nav.hello":       "Салом, {name}",
    "base.description": "EduHub — платформаи муосири таълимӣ барои донишҷӯён ва муаллимон",

    // Подвал
    "footer.rights": "Ҳама ҳуқуқҳо ҳифз шудаанд.",

    // Hero
    "hero.title":    "Ёд гир. Инкишоф ёб. Ба даст ор.",
    "hero.subtitle": "Платформаи муосир барои донишҷӯён ва муаллимон. Ҳоло ба дониш дастрасӣ пайдо кун.",
    "hero.cta_register": "Ройгон оғоз кунед",
    "hero.cta_login":    "Ба ҳисоб даромадан",
    "hero.card1": "Курсҳои сифатӣ",
    "hero.card2": "Дастовардҳо",
    "hero.card3": "Беҳтарин муаллимон",

    // Статистика
    "stats.students": "Донишҷӯён",
    "stats.courses":  "Курсҳо",
    "stats.teachers": "Муаллимон",

    // Главная
    "home.popular_courses":     "Курсҳои маъмул",
    "home.popular_courses_sub": "Аз беҳтарин барномаҳои платформаи мо таълимро оғоз кунед",
    "home.no_courses":          "Ҳоло курсе илова нашудааст. Ҳамчун муаллим ба қайд гиред ва аввалинро эҷод кунед!",
    "home.why_us":              "Чаро EduHub?",

    // Особенности
    "feature.fast":         "Оғози зуд",
    "feature.fast_desc":    "Дар якчанд дақиқа ба қайд гиред ва фавран таълимро оғоз кунед",
    "feature.focused":      "Таълими мақсадноки",
    "feature.focused_desc": "Курсҳои равшан аз муаллимони бодаст бидуни обу ҳаво",
    "feature.simple":       "Интерфейси оддӣ",
    "feature.simple_desc":  "Платформаи қулай бидуни мураккабии зиёдатӣ",

    // Формы
    "form.email":    "Почтаи электронӣ",
    "form.password": "Рамз",
    "form.name":     "Номи шумо",
    "form.role":     "Ман ҳастам",
    "form.name_ph":  "Иван Иванов",
    "form.email_ph": "you@example.com",
    "form.pass_ph":  "••••••••",
    "form.pass_min_ph": "На камтар аз 6 аломат",

    // Роли
    "role.student": "Донишҷӯ",
    "role.teacher": "Муаллим",

    // Вход
    "login.title_page":    "Даромад — EduHub",
    "login.title":         "Ворид шудан ба ҳисоб",
    "login.subtitle":      "Хуш омадед!",
    "login.submit":        "Даромадан",
    "login.no_account":    "Ҳисоб надоред?",
    "login.register_link": "Ба қайд гиридан",

    // Регистрация
    "register.title_page":   "Бақайдгирӣ — EduHub",
    "register.title":        "Ҳисоб эҷод кунед",
    "register.subtitle":     "Ба ҳазорон донишҷӯён ва муаллимон ҳамроҳ шавед",
    "register.submit":       "Ба қайд гиридан",
    "register.have_account": "Аллакай ҳисоб доред?",
    "register.login_link":   "Даромадан",

    // Кабинет студента
    "student.welcome":     "Хуш омадед,",
    "student.subtitle":    "Таълимро идома дщед — ҳамаи курсҳои платформа дастраси шумо аст",
    "student.all_courses": "Ҳамаи курсҳо",
    "student.no_courses":  "Ҳоло курсе мавҷуд нест. Баъдтар биёед!",

    // Кабинет преподавателя
    "teacher.welcome":       "Хуш омадед,",
    "teacher.subtitle":      "Курсҳои худро идора кунед ва ба донишҷӯён кумак кунед",
    "teacher.add_course":    "+ Курс эҷод кунед",
    "teacher.my_courses":    "Курсҳои ман",
    "teacher.no_courses":    "Ҳоло курсе надоред. Аввалинро эҷод кунед!",
    "teacher.create_course": "Курси нав эҷод кунед",
    "teacher.edit_course":   "Курсро таҳрир кунед",
    "teacher.manage":        "Идоракунии курс",

    // Курс
    "course.open":           "Курсро кушоед",
    "course.view":           "Дидан",
    "course.edit":           "Таҳрир",
    "course.delete":         "Ҳазф кунед",
    "course.badge":          "Курс",
    "course.about":          "Дар бораи курс",
    "course.no_description": "Тавсифи курс ҳоло илова нашудааст.",
    "course.teacher":        "Муаллим",
    "course.created_at":     "Санаи эҷод",
    "course.enroll":         "Ба курс навиштан",
    "course.enrolled":       "Курс дастраси шумо аст",
    "course.title":          "Номи курс",
    "course.description":    "Тавсиф",

    // Действия
    "action.cancel": "Бекор кунед",
    "action.create": "Эҷод кунед",
    "action.save":   "Сохранего",
    "action.delete": "Ҳазф кунед",

    // Валидация
    "validation.name_required":     "Номи худро ворид кунед",
    "validation.email_required":    "Почтаи электрониро ворид кунед",
    "validation.email_invalid":     "Почтаи электронии дурустро ворид кунед",
    "validation.password_required": "Рамзро ворид кунед",
    "validation.password_short":    "Рамз бояд на камтар аз 6 аломат бошад",
    "validation.title_required":    "Номи курсро ворид кунед",

    // Общие (Common)
    "common.error_delete": "Хатогӣ ҳангоми ҳазф",
    "common.error_conn":   "Хатои пайвастшавӣ",
    "common.no_desc":      "Тавсиф надорад",
    "common.no_rating":    "Баҳогузорӣ нашудааст",
    "common.back_cab":     "Бозгашт ба кабинет",
    "common.reset":        "Тоза кардан",
    "common.search_btn":   "🔍 Ҷустуҷӯ",

    // Каталог курсов
    "catalog.title":       "📚 Курсҳо",
    "catalog.search":      "Ҷустуҷӯи курсҳо...",
    "catalog.all_cat":     "Ҳамаи категорияҳо",
    "catalog.results":     "Натиҷаҳо тибқи дархости: «{q}» — {count} курс",
    "catalog.empty_q":     "Тибқи дархости «{q}» чизе ёфт нашуд",
    "catalog.empty":       "Ҳоло курсҳо нестанд",
    "catalog.view_all":    "Дидани ҳамаи курсҳо",
    "catalog.open":        "Кушодан →",

    // Управление курсом
    "manage.back":           "← Курсҳои ман",
    "manage.materials":      "Маводҳои курс:",
    "manage.del_file":       "Оё ин файл ҳазф шавад?",
    "manage.view":           "👁 Дидан",
    "manage.edit":           "✏️ Таҳрир",
    "manage.modules_lbl":    "Модулҳои курс",
    "manage.files_count":    "{count} файл",
    "manage.no_lessons":     "Ҳанӯз дарсҳо нестанд",
    "manage.add_lesson":     "+ Иловаи дарс",
    "manage.no_modules":     "Ҳанӯз модулҳо нестанд. Аввалинро илова кунед!",
    "manage.new_mod_ph":     "Номи модули нав",
    "manage.add_mod_btn":    "+ Модул",
    "manage.activity_lbl":   "Фаъолияти донишҷӯён",
    "manage.student":        "Донишҷӯ",
    "manage.progress":       "Пешрафт",
    "manage.passed_lessons": "Дарсҳои гузашта",
    "manage.last_active":    "Фаъолияти охирин",
    "manage.no_data":        "Маълумот нест",
    "manage.no_students":    "Ҳоло донишҷӯёне, ки ин курсро оғоз кардаанд, вуҷуд надоранд.",
    "manage.confirm_delete_course": "Оё мутмаин ҳастед, ки мехоҳед ин курсро ҳазф кунед?",
    "manage.confirm_del_mod": "Оё модул бо тамоми дарсҳояш ҳазф шавад?",
    "manage.new_lesson":     "Дарси нав",
    "manage.lesson_title":   "Номи дарс",
    "manage.lesson_video":   "Истинод ба видео (YouTube/Vimeo)",
    "manage.lesson_desc":    "Тавсиф / матн",
    "manage.lesson_create":  "Дарс эҷод кардан",

    // Страница курса
    "course_page.breadcrumbs_home": "Асосӣ",
    "course_page.breadcrumbs_cat":  "Курсҳо",
    "course_page.reviews_count":    "({count} тафсир)",
    "course_page.about":            "Дар бораи курс",
    "course_page.materials":        "📎 Маводҳои курс",
    "course_page.progress":         "Пешрафт: {pct}%",
    "course_page.content":          "Мӯҳтавои курс",
    "course_page.lessons_count":    "{count} дарс",
    "course_page.reviews":          "⭐ Тафсирҳо ({count})",
    "course_page.leave_review":     "Тафсир гузоштан",
    "course_page.edit_review":      "Тағйир додани тафсир",
    "course_page.review_ph":        "Тафсири шумо дар бораи курс...",
    "course_page.send_review":      "Фиристодан",
    "course_page.teacher":          "Муаллим",
    "course_page.modules_count":    "Модулҳо",
    "course_page.created":          "Эҷод шудааст",
    "course_page.rating":           "Рейтинг",
    "course_page.start_learning":   "Оғози таълим",
    "course_page.login_btn":        "Даромадан",
    "course_page.gear_manage":      "⚙️ Идоракунӣ",
    "course_page.avail":            "✅ Курс ба шумо дастрас аст",
    "course_page.start_continue":   "▶ Оғоз / Идома",

    // Урок
    "lesson.back_course":    "← {title}",
    "lesson.materials":      "📎 Маводҳо",
    "lesson.quiz":           "Гузаштан аз квиз →",
    "lesson.questions":      "{count} савол",
    "lesson.done":           "✅ Дарс ба анҷом расид",
    "lesson.mark_done":      "✅ Ҳамчун тамомшуда қайд кардан",
    "lesson.tools":          "⚙️ Воситаҳои муаллим",
    "lesson.add_mat":        "📎 Иловаи мавод",
    "lesson.mat_title":      "Номгӯй",
    "lesson.mat_link":       "Истинод ба файл",
    "lesson.mat_type_oth":   "Дигар",
    "lesson.mat_add":        "Илова",
    "lesson.create_quiz":    "🧠 Эҷоди квиз",
    "lesson.quiz_title":     "Номи квиз",
    "lesson.quiz_create":    "Эҷод",
    "lesson.quiz_exists":    "🧠 Квиз аллакай эҷод шудааст",
    "lesson.quiz_open":      "Кушодани квиз",
    "lesson.q_text":         "Матни савол",
    "lesson.q_single":       "Як ҷавоб",
    "lesson.q_multi":        "Якчанд ҷавоб",
    "lesson.ans_correct":    "Дуруст",
    "lesson.add_variant":    "+ Вариант",
    "lesson.add_q":          "Иловаи савол",
    "lesson.qa":             "💬 Саволҳо ва ҷавобҳо",
    "lesson.ask_ph":         "Саволи худро диҳед...",
    "lesson.send":           "Фиристодан",
    "lesson.login_req":      "Барои навиштани шарҳ ба ҳисоб дароед",
    "lesson.reply_ph":       "Ҷавоб додан...",
    "lesson.reply_btn":      "↩ Ҷавоб додан",
    "lesson.no_comments":    "Ҳоло шарҳе нест. Аввалин бошед!",

    // Квиз
    "quiz.result":       "Натиҷа: {score}%",
    "quiz.correct_of":   "Ҷавобҳои дуруст: <strong>{correct}</strong> аз <strong>{total}</strong>",
    "quiz.success":      "Олӣ! Шумо баҳои аъло гирифтед!",
    "quiz.warning":      "Бад не! Маводро такрор кунед ва боз кӯшиш кунед.",
    "quiz.error":        "Тавсия медиҳем, ки пеш аз кӯшиши такрорӣ дарсро аз нав бинед.",
    "quiz.retry":        "Боз як бор гузаштан",
    "quiz.back_lesson":  "← Бозгашт ба дарс",
    "quiz.q_count":      "{count} савол",
    "quiz.q_num":        "Саволи {num}",
    "quiz.submit":       "Фиристодани ҷавобҳо →",

    // Профиль 
    "profile.teacher":       "👨‍🏫 Муаллим",
    "profile.student":       "👩‍🎓 Донишҷӯ",
    "profile.my_cab":        "Кабинети ман",
    "profile.my_courses":    "📚 Курсҳои ман ({count})",
    "profile.course_stat":   "{modules} модул · {lessons} дарс",
    "profile.no_created":    "Шумо ҳоло ягон курс эҷод накардаед",
    "profile.create_btn":    "Эҷоди курс",
    "profile.my_progress":   "📈 Пешрафти ман",
    "profile.passed_of":     "Аз {total} дарс {done}-тоашро гузаштед",
    "profile.no_started":    "Шумо ҳанӯз ягон курсро оғоз накардаед",
    "profile.find_courses":  "Ёфтани курсҳо",
    "profile.my_reviews":    "⭐ Тафсирҳои ман",

    // Assessment
    "ass.title":         "Хуш омадед!",
    "ass.subtitle":      "Барои он ки ба шумо беҳтарин курсҳоро пешниҳод кунем, лутфан ба чанд саволи кӯтоҳ ҷавоб диҳед. Ин ба мо кӯмак мекунад сатҳи дониши шуморо муайян намоем.",
    "ass.q1":            "1. Сатҳи кунунии худро дар риёзиёт (математика) чӣ гуна арзёбӣ мекунед?",
    "ass.q1_1":          "Мавзӯъҳои асосиро суст мефаҳмам",
    "ass.q1_2":          "Асосҳоро мефаҳмам, аммо масъалаҳоро бо душворӣ ҳал мекунам",
    "ass.q1_3":          "Сатҳи миёна, бисёр масъалаҳоро ҳал карда метавонам",
    "ass.q1_4":          "Сатҳи хуб, ба масъалаҳои мураккаби тестӣ омода мешавам",
    "ass.q2":            "2. То чӣ андоза масъалаҳои тести миллиро боварӣ доред?",
    "ass.q2_1":          "Қариб ки ҳал карда наметавонам",
    "ass.q2_2":          "Баъзан метавонам масъалаҳои оддиро ҳал кунам",
    "ass.q2_3":          "Метавонам масъалаҳои сатҳи миёнаро ҳал кунам",
    "ass.q2_4":          "Аксарияти масъалаҳоро бо боварӣ ҳал мекунам",
    "ass.q3":            "3. Чӣ қадар вақт боз барои дохил шудан омодагӣ мебинед?",
    "ass.q3_1":          "Ҳанӯз оғоз накардаам",
    "ass.q3_2":          "Камтар аз 3 моҳ",
    "ass.q3_3":          "3–6 моҳ",
    "ass.q3_4":          "Зиёда аз 6 моҳ",
    "ass.q4":            "4. Ҳадафи омӯзишии шумо дар ҳоли ҳозир чист?",
    "ass.q4_1":          "Фаҳмидани мавзӯъҳои асосӣ",
    "ass.q4_2":          "Ёд гирифтани барномаи мактабӣ",
    "ass.q4_3":          "Омодагӣ ба тести миллӣ",
    "ass.q4_4":          "Беҳтар кардани натиҷаҳо ва ҳалли масъалаҳои мураккаб",
    "ass.q5":            "5. Дар як ҳафта чанд соатро метавонед ба омӯзиш ҷудо кунед?",
    "ass.q5_1":          "1–2 соат",
    "ass.q5_2":          "3–5 соат",
    "ass.q5_3":          "6–10 соат",
    "ass.q5_4":          "Зиёда аз 10 соат",
    "ass.submit":        "Анҷом додан ва дидани курсҳои мувофиқ",

    // Рекомендованные
    "rec.title":         "Курсҳои тавсияшуда",
    "rec.level":         "Сатҳи кунунии шумо:",
    "rec.desc":          "Мо барномаҳоеро интихоб кардем, ки ба дониш ва ҳадафҳои шумо комилан мувофиқанд.",
    "rec.go_course":     "Ба курс гузаштан",
    "rec.empty_p1":      "Мутаассифона, ҳоло курсҳои мувофиқ вуҷуд надоранд. Кӯшиш кунед аз каталоги пурра истифода баред.",
    "rec.full_cat":      "Каталоги пурра"
  }
};

// Текущий язык (по умолчанию — русский)
let currentLang = localStorage.getItem('lang') || 'ru';

/**
 * Устанавливает язык интерфейса и переводит все элементы с data-i18n.
 * @param {string} lang — 'ru' или 'tj'
 */
function setLang(lang) {
  if (!translations[lang]) return;
  currentLang = lang;
  localStorage.setItem('lang', lang);

  // Обновляем атрибут lang на html
  document.documentElement.setAttribute('lang', lang);
  document.documentElement.setAttribute('data-lang', lang);

  // Подсвечиваем активную кнопку переключателя
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('active', btn.id === `lang-${lang}`);
  });

  // Переводим все элементы с data-i18n
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const paramsAttr = el.getAttribute('data-i18n-params');
    let text = translations[lang][key] || key;

    // Подставляем параметры вида {name}
    if (paramsAttr) {
      try {
        const params = JSON.parse(paramsAttr);
        Object.entries(params).forEach(([k, v]) => {
          text = text.replace(`{${k}}`, v);
        });
      } catch (_) {}
    }

    el.textContent = text;
  });

  // Переводим заголовки страниц (title), если у них есть data-i18n-title
  const titleEl = document.querySelector('title[data-i18n-title]');
  if (titleEl) {
    const key = titleEl.getAttribute('data-i18n-title');
    const paramsAttr = titleEl.getAttribute('data-i18n-params');
    let text = translations[lang][key] || key;
    if (paramsAttr) {
      try {
        const params = JSON.parse(paramsAttr);
        Object.entries(params).forEach(([k, v]) => {
          text = text.replace(`{${k}}`, v);
        });
      } catch (_) {}
    }
    document.title = text;
  }
}

/**
 * Получить перевод по ключу.
 * @param {string} key
 * @param {Object} [params]
 * @returns {string}
 */
function t(key, params = {}) {
  let text = translations[currentLang][key] || translations['ru'][key] || key;
  Object.entries(params).forEach(([k, v]) => {
    text = text.replace(`{${k}}`, v);
  });
  return text;
}

// Применяем язык при загрузке страницы
document.addEventListener('DOMContentLoaded', () => setLang(currentLang));
