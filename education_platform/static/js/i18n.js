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
    "nav.search":      "Поиск",
    "nav.how_it_works":"Как это работает",
    "nav.about":       "О нас",
    "nav.contact":     "Контакты",
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
    "nav.home":        "Асосӣ",
    "nav.dashboard":   "Кабинет",
    "nav.login":       "Вуруд",
    "nav.register":    "Сабти ном",
    "nav.logout":      "Хуруҷ",
    "nav.courses":     "Курсҳо",
    "nav.search":      "Ҷустуҷӯ",
    "nav.how_it_works":"Тарзи кор",
    "nav.about":       "Дар бораи мо",
    "nav.contact":     "Тамос",
    "nav.my_courses":  "Курсҳои ман",
    "nav.hello":       "Салом, {name}",
    "base.description": "EduHub — платформаи муосири таълимӣ барои донишҷӯёну омӯзгорон",

    // Подвал
    "footer.rights": "Ҳамаи ҳуқуқҳо маҳфузанд.",

    // Hero
    "hero.title":    "Биёмӯз. Рушд кун. Муваффақ шав.",
    "hero.subtitle": "Платформаи муосир барои донишҷӯёну омӯзгорон. Таълимро худи ҳозир оғоз кунед.",
    "hero.cta_register": "Оғози ройгон",
    "hero.cta_login":    "Вуруд ба ҳисоб",
    "hero.card1": "Курсҳои босифат",
    "hero.card2": "Дастовардҳо",
    "hero.card3": "Беҳтарин омӯзгорон",

    // Статистика
    "stats.students": "Донишҷӯ",
    "stats.courses":  "Курс",
    "stats.teachers": "Омӯзгор",

    // Главная
    "home.popular_courses":     "Курсҳои маъмул",
    "home.popular_courses_sub": "Таълимро аз беҳтарин барномаҳо оғоз кунед",
    "home.no_courses":          "Ҳоло курсе нест. Ҳамчун омӯзгор сабти ном кунеду нахустин курсро созед!",
    "home.why_us":              "Чаро EduHub?",

    // Особенности
    "feature.fast":         "Оғози зуд",
    "feature.fast_desc":    "Зуд сабти ном шаведу ба омӯзиш шурӯъ кунед",
    "feature.focused":      "Таълими мақсаднок",
    "feature.focused_desc": "Курсҳои мушаххас аз омӯзгорони ботаҷриба бидуни об",
    "feature.simple":       "Интерфейси оддӣ",
    "feature.simple_desc":  "Платформаи қулай ва осонфаҳм",

    // Формы
    "form.email":    "Почтаи электронӣ",
    "form.password": "Рамз",
    "form.name":     "Ному насаб",
    "form.role":     "Нақш",
    "form.name_ph":  "Иван Иванов",
    "form.email_ph": "you@example.com",
    "form.pass_ph":  "••••••••",
    "form.pass_min_ph": "Камаш 6 аломат",

    // Роли
    "role.student": "Донишҷӯ",
    "role.teacher": "Омӯзгор",

    // Вход
    "login.title_page":    "Вуруд — EduHub",
    "login.title":         "Вуруд ба ҳисоб",
    "login.subtitle":      "Хуш омадед!",
    "login.submit":        "Вуруд",
    "login.no_account":    "Ҳисоб надоред?",
    "login.register_link": "Сабти ном",

    // Регистрация
    "register.title_page":   "Сабти ном — EduHub",
    "register.title":        "Эҷоди ҳисоб",
    "register.subtitle":     "Ба ҳазорон донишҷӯёну омӯзгорон пайваст шавед",
    "register.submit":       "Сабти ном",
    "register.have_account": "Аллакай ҳисоб доред?",
    "register.login_link":   "Вуруд",

    // Кабинет студента
    "student.welcome":     "Хуш омадед,",
    "student.subtitle":    "Омӯзишро идома диҳед — ҳамаи курсҳо дастрасанд",
    "student.all_courses": "Ҳамаи курсҳо",
    "student.no_courses":  "Ҳоло курсе нест. Баъдтар биёед!",

    // Кабинет преподавателя
    "teacher.welcome":       "Хуш омадед,",
    "teacher.subtitle":      "Курсҳоятонро идора кунеду ба донишҷӯён кумак намоед",
    "teacher.add_course":    "+ Эҷоди курс",
    "teacher.my_courses":    "Курсҳои ман",
    "teacher.no_courses":    "Шумо ҳоло курсе надоред. Аввалин курсро созед!",
    "teacher.create_course": "Эҷоди курси нав",
    "teacher.edit_course":   "Таҳрири курс",
    "teacher.manage":        "Идоракунии курс",

    // Курс
    "course.open":           "Кушодан",
    "course.view":           "Дидан",
    "course.edit":           "Таҳрир",
    "course.delete":         "Ҳазф",
    "course.badge":          "Курс",
    "course.about":          "Дар бораи курс",
    "course.no_description": "Тавсиф илова нашудааст.",
    "course.teacher":        "Омӯзгор",
    "course.created_at":     "Санаи эҷод",
    "course.enroll":         "Ба курс пайвастан",
    "course.enrolled":       "Курс дастрас аст",
    "course.title":          "Номи курс",
    "course.description":    "Тавсиф",

    // Действия
    "action.cancel": "Бекор кардан",
    "action.create": "Эҷод кардан",
    "action.save":   "Сабт",
    "action.delete": "Ҳазф",

    // Валидация
    "validation.name_required":     "Номро ворид кунед",
    "validation.email_required":    "Почтаро ворид кунед",
    "validation.email_invalid":     "Почтаи дуруст ворид кунед",
    "validation.password_required": "Рамзро ворид кунед",
    "validation.password_short":    "Рамз бояд камаш 6 аломат бошад",
    "validation.title_required":    "Номи курсро ворид кунед",

    // Общие (Common)
    "common.error_delete": "Хатогӣ ҳангоми ҳазф",
    "common.error_conn":   "Хатои пайвастшавӣ",
    "common.no_desc":      "Бе тавсиф",
    "common.no_rating":    "Бе баҳо",
    "common.back_cab":     "Бозгашт ба кабинет",
    "common.reset":        "Тоза кардан",
    "common.search_btn":   "🔍 Ҷустуҷӯ",

    // Каталог курсов
    "catalog.title":       "📚 Курсҳо",
    "catalog.search":      "Ҷустуҷӯи курсҳо...",
    "catalog.all_cat":     "Ҳамаи категорияҳо",
    "catalog.results":     "Натиҷа барои: «{q}» — {count} курс",
    "catalog.empty_q":     "Барои «{q}» чизе ёфт нашуд",
    "catalog.empty":       "Ҳоло курсҳо нестанд",
    "catalog.view_all":    "Дидани ҳамаи курсҳо",
    "catalog.open":        "Кушодан →",

    // Управление курсом
    "manage.back":           "← Курсҳои ман",
    "manage.materials":      "Маводи курс:",
    "manage.del_file":       "Файл ҳазф шавад?",
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
    "manage.passed_lessons": "Дарсҳои хатмшуда",
    "manage.last_active":    "Охирин фаъолият",
    "manage.no_data":        "Маълумот нест",
    "manage.no_students":    "Ҳоло донишҷӯён ба ин курс напайвастаанд.",
    "manage.confirm_delete_course": "Курс ҳазф шавад?",
    "manage.confirm_del_mod": "Модул бо тамоми дарсҳояш ҳазф шавад?",
    "manage.new_lesson":     "Дарси нав",
    "manage.lesson_title":   "Номи дарс",
    "manage.lesson_video":   "Пайванд ба видео (YouTube/Vimeo)",
    "manage.lesson_desc":    "Тавсиф / матн",
    "manage.lesson_create":  "Эҷоди дарс",

    // Страница курса
    "course_page.breadcrumbs_home": "Асосӣ",
    "course_page.breadcrumbs_cat":  "Курсҳо",
    "course_page.reviews_count":    "({count} тафсир)",
    "course_page.about":            "Дар бораи курс",
    "course_page.materials":        "📎 Маводи курс",
    "course_page.progress":         "Пешрафт: {pct}%",
    "course_page.content":          "Мундариҷаи курс",
    "course_page.lessons_count":    "{count} дарс",
    "course_page.reviews":          "⭐ Тафсирҳо ({count})",
    "course_page.leave_review":     "Тафсир навиштан",
    "course_page.edit_review":      "Таҳрири тафсир",
    "course_page.review_ph":        "Тафсири шумо...",
    "course_page.send_review":      "Ирсол",
    "course_page.teacher":          "Омӯзгор",
    "course_page.modules_count":    "Модулҳо",
    "course_page.created":          "Эҷод шудааст",
    "course_page.rating":           "Рейтинг",
    "course_page.start_learning":   "Оғози омӯзиш",
    "course_page.login_btn":        "Вуруд",
    "course_page.gear_manage":      "⚙️ Идора",
    "course_page.avail":            "✅ Курс дастрас аст",
    "course_page.start_continue":   "▶ Оғоз / Идома",

    // Урок
    "lesson.back_course":    "← {title}",
    "lesson.materials":      "📎 Маводҳо",
    "lesson.quiz":           "Гузаштан ба тест →",
    "lesson.questions":      "{count} савол",
    "lesson.done":           "✅ Дарс анҷом ёфт",
    "lesson.mark_done":      "✅ Ҳамчун анҷомёфта қайд кардан",
    "lesson.tools":          "⚙️ Воситаҳои омӯзгор",
    "lesson.add_mat":        "📎 Иловаи мавод",
    "lesson.mat_title":      "Номгӯй",
    "lesson.mat_link":       "Пайванд",
    "lesson.mat_type_oth":   "Дигар",
    "lesson.mat_add":        "Илова",
    "lesson.create_quiz":    "🧠 Эҷоди тест",
    "lesson.quiz_title":     "Номи тест",
    "lesson.quiz_create":    "Эҷод",
    "lesson.quiz_exists":    "🧠 Тест эҷод шудааст",
    "lesson.quiz_open":      "Кушодани тест",
    "lesson.q_text":         "Матни савол",
    "lesson.q_single":       "Як ҷавоб",
    "lesson.q_multi":        "Чанд ҷавоб",
    "lesson.ans_correct":    "Дуруст",
    "lesson.add_variant":    "+ Вариант",
    "lesson.add_q":          "Иловаи савол",
    "lesson.qa":             "💬 Саволу ҷавоб",
    "lesson.ask_ph":         "Савол диҳед...",
    "lesson.send":           "Ирсол",
    "lesson.login_req":      "Барои шарҳ навиштан ворид шавед",
    "lesson.reply_ph":       "Ҷавоб...",
    "lesson.reply_btn":      "↩ Ҷавоб додан",
    "lesson.no_comments":    "Ҳоло шарҳе нест. Аввалин бошед!",

    // Квиз
    "quiz.result":       "Натиҷа: {score}%",
    "quiz.correct_of":   "Ҷавоби дуруст: <strong>{correct}</strong> аз <strong>{total}</strong>",
    "quiz.success":      "Олӣ! Шумо хуб гузаштед!",
    "quiz.warning":      "Бад не! Маводро такрор кунеду боз кӯшиш кунед.",
    "quiz.error":        "Тавсия медиҳем дарсро дубора омӯзед.",
    "quiz.retry":        "Аз нав гузаштан",
    "quiz.back_lesson":  "← Бозгашт ба дарс",
    "quiz.q_count":      "{count} савол",
    "quiz.q_num":        "Саволи {num}",
    "quiz.submit":       "Ирсоли ҷавобҳо →",

    // Профиль 
    "profile.teacher":       "👨‍🏫 Омӯзгор",
    "profile.student":       "👩‍🎓 Донишҷӯ",
    "profile.my_cab":        "Кабинети ман",
    "profile.my_courses":    "📚 Курсҳои ман ({count})",
    "profile.course_stat":   "{modules} модул · {lessons} дарс",
    "profile.no_created":    "Шумо ҳоло курсе эҷод накардаед",
    "profile.create_btn":    "Эҷоди курс",
    "profile.my_progress":   "📈 Пешрафти ман",
    "profile.passed_of":     "Аз {total} дарс {done} анҷом ёфт",
    "profile.no_started":    "Шумо ҳанӯз курсеро оғоз накардаед",
    "profile.find_courses":  "Ҷустуҷӯи курсҳо",
    "profile.my_reviews":    "⭐ Тафсирҳои ман",

    // Assessment
    "ass.title":         "Хуш омадед!",
    "ass.subtitle":      "Барои дарёфти беҳтарин курсҳо, ба чанд савол ҷавоб диҳед. Ин сатҳи шуморо муайян мекунад.",
    "ass.q1":            "1. Сатҳи худро дар математика чӣ гуна арзёбӣ мекунед?",
    "ass.q1_1":          "Мавзӯъҳои асосиро суст медонам",
    "ass.q1_2":          "Асосҳоро медонам, аммо дар ҳалли масъалаҳо душворӣ мекашам",
    "ass.q1_3":          "Сатҳи миёна, аксариятро ҳал мекунам",
    "ass.q1_4":          "Сатҳи хуб, ба масъалаҳои мураккаб омодаам",
    "ass.q2":            "2. Дар тести миллӣ чӣ қадар боварӣ доред?",
    "ass.q2_1":          "Қариб ки омода нестам",
    "ass.q2_2":          "Танҳо масъалаҳои оддиро ҳал мекунам",
    "ass.q2_3":          "Масъалаҳои сатҳи миёнаро",
    "ass.q2_4":          "Аксарияти масъалаҳоро медонам",
    "ass.q3":            "3. Чӣ қадар вақт боз омодагӣ мебинед?",
    "ass.q3_1":          "Ҳанӯз оғоз накардаам",
    "ass.q3_2":          "Камтар аз 3 моҳ",
    "ass.q3_3":          "3–6 моҳ",
    "ass.q3_4":          "Зиёда аз 6 моҳ",
    "ass.q4":            "4. Ҳадафи омӯзишии шумо ҳоло чист?",
    "ass.q4_1":          "Омӯхтани асосҳо",
    "ass.q4_2":          "Такрори барномаи мактабӣ",
    "ass.q4_3":          "Омодагӣ ба тести миллӣ",
    "ass.q4_4":          "Ҳалли масъалаҳои мураккаб",
    "ass.q5":            "5. Дар як ҳафта чанд соат меомӯзед?",
    "ass.q5_1":          "1–2 соат",
    "ass.q5_2":          "3–5 соат",
    "ass.q5_3":          "6–10 соат",
    "ass.q5_4":          "Зиёда аз 10 соат",
    "ass.submit":        "Ирсол ва дидани курсҳо",

    // Рекомендованные
    "rec.title":         "Курсҳои тавсияшуда",
    "rec.level":         "Сатҳи шумо:",
    "rec.desc":          "Барномаҳои зер ба дониш ва ҳадафҳои шумо мувофиқанд.",
    "rec.go_course":     "Ба курс гузаштан",
    "rec.empty_p1":      "Мутаассифона, ҳоло курсҳои мувофиқ нестанд. Аз каталоги пурра истифода баред.",
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
