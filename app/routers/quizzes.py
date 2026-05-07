# Роутер квизов
from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.dependencies import get_user, is_student, is_teacher, is_admin
from app.models.course import Course
from app.models.lesson import Lesson
from app.models.module import Module
from app.models.quiz import Answer, Question, Quiz, QuizAttempt, QuizResult
from app.models.user import User
from app.quiz_flow import (
    QUIZ_PASS_PERCENTAGE,
    next_after_quiz,
    normalize_open_answer,
    quiz_back_target,
    quiz_binding_label,
    quiz_is_unlocked,
    quiz_owner_course_id,
)

router = APIRouter(prefix="/quiz")
dashboard_router = APIRouter()
templates = Jinja2Templates(directory="templates")


def require_teacher(request, db):
    user = get_user(request, db)
    if not user:
        raise HTTPException(status_code=401)
    if not (is_teacher(user) or is_admin(user)):
        raise HTTPException(status_code=403)
    return user


def _quiz_editor_target(quiz: Quiz) -> str:
    if quiz.lesson_id:
        return f"lesson-quiz-{quiz.lesson_id}"
    if quiz.module_id:
        return f"module-quiz-{quiz.module_id}"
    if quiz.course_id:
        return "course-quiz-main"
    return ""


def _quiz_edit_page_url(quiz: Quiz) -> str:
    if quiz.lesson_id:
        owner_course_id = quiz_owner_course_id(quiz)
        if owner_course_id:
            return f"/courses/{owner_course_id}/manage"
        return f"/lessons/{quiz.lesson_id}"
    owner_course_id = quiz_owner_course_id(quiz)
    if owner_course_id:
        return f"/courses/{owner_course_id}/manage"
    return "/courses/catalog"


def _redirect_with_error(url: str, message: str, target: str = "") -> RedirectResponse:
    query = {"quiz_error": message}
    if target:
        query["quiz_error_target"] = target
    separator = "&" if "?" in url else "?"
    return RedirectResponse(f"{url}{separator}{urlencode(query)}", status_code=302)


def _quiz_result_payload(
    *,
    correct: int,
    total: int,
    percentage: int,
    passed: bool,
) -> dict[str, int | bool]:
    return {
        "correct": correct,
        "total": total,
        "percentage": percentage,
        "passed": passed,
    }


def _validate_question_payload(question_type: str, answers: list[tuple[str, bool]], correct_text: str) -> None:
    if question_type == "open":
        if not correct_text:
            raise HTTPException(status_code=400, detail="Для открытого вопроса укажите правильный ответ")
        return

    if len(answers) < 2:
        raise HTTPException(status_code=400, detail="Добавьте минимум два варианта ответа")

    correct_count = sum(1 for _, is_correct in answers if is_correct)
    if question_type == "single" and correct_count != 1:
        raise HTTPException(status_code=400, detail="Для вопроса с одним ответом отметьте ровно один правильный вариант")
    if question_type == "multiple" and correct_count < 1:
        raise HTTPException(status_code=400, detail="Для вопроса с несколькими ответами отметьте хотя бы один правильный вариант")


def _resolve_quiz_scope(
    db: Session,
    teacher: User,
    lesson_id: int | None = None,
    module_id: int | None = None,
    course_id: int | None = None,
) -> tuple[dict[str, int], Course]:
    scope_ids = {
        "lesson_id": lesson_id,
        "module_id": module_id,
        "course_id": course_id,
    }
    selected_scopes = {key: value for key, value in scope_ids.items() if value}
    if len(selected_scopes) != 1:
        raise HTTPException(status_code=400, detail="Нужно выбрать один уровень для квиза")

    if lesson_id:
        lesson = db.query(Lesson).options(joinedload(Lesson.module), joinedload(Lesson.quiz)).filter(Lesson.id == lesson_id).first()
        if not lesson:
            raise HTTPException(status_code=404, detail="Урок не найден")
        course = db.query(Course).filter(Course.id == lesson.module.course_id, Course.teacher_id == teacher.id).first()
        if not course:
            raise HTTPException(status_code=403)
        if lesson.quiz:
            raise HTTPException(status_code=400, detail="Квиз для этого урока уже существует")
        return {"lesson_id": lesson_id}, course

    if module_id:
        module = db.query(Module).options(joinedload(Module.quiz)).filter(Module.id == module_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Модуль не найден")
        course = db.query(Course).filter(Course.id == module.course_id, Course.teacher_id == teacher.id).first()
        if not course:
            raise HTTPException(status_code=403)
        if module.quiz:
            raise HTTPException(status_code=400, detail="Квиз для этого модуля уже существует")
        return {"module_id": module_id}, course

    course = db.query(Course).options(joinedload(Course.quiz)).filter(Course.id == course_id, Course.teacher_id == teacher.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    if course.quiz:
        raise HTTPException(status_code=400, detail="Квиз для этого курса уже существует")
    return {"course_id": course_id}, course


def _load_quiz(db: Session, quiz_id: int) -> Quiz | None:
    return (
        db.query(Quiz)
        .options(
            joinedload(Quiz.lesson).joinedload(Lesson.module),
            joinedload(Quiz.module),
            joinedload(Quiz.course),
            joinedload(Quiz.questions).joinedload(Question.answers),
        )
        .filter(Quiz.id == quiz_id)
        .first()
    )


def _latest_results(results: list[QuizResult]) -> list[QuizResult]:
    latest_by_student: dict[int, QuizResult] = {}
    for result in sorted(results, key=lambda item: (item.created_at, item.id), reverse=True):
        latest_by_student.setdefault(result.student_id, result)
    return sorted(latest_by_student.values(), key=lambda item: (item.created_at, item.id), reverse=True)


def _teacher_owned_quizzes(db: Session, teacher_id: int) -> list[Quiz]:
    courses = (
        db.query(Course)
        .options(
            joinedload(Course.quiz).selectinload(Quiz.results).joinedload(QuizResult.student),
            selectinload(Course.modules).joinedload(Module.quiz).selectinload(Quiz.results).joinedload(QuizResult.student),
            selectinload(Course.modules).selectinload(Module.lessons).joinedload(Lesson.quiz).selectinload(Quiz.results).joinedload(QuizResult.student),
        )
        .filter(Course.teacher_id == teacher_id)
        .all()
    )

    quizzes: list[Quiz] = []
    for course in courses:
        if course.quiz and course.quiz.save_results:
            course.quiz.course = course
            quizzes.append(course.quiz)
        for module in course.modules:
            if module.quiz and module.quiz.save_results:
                module.quiz.module = module
                quizzes.append(module.quiz)
            for lesson in module.lessons:
                if lesson.quiz and lesson.quiz.save_results:
                    lesson.quiz.lesson = lesson
                    quizzes.append(lesson.quiz)

    return quizzes


# ── Создать квиз (teacher) ──────────────────────────────────────
@router.post("/create")
def create_quiz(
    request: Request,
    lesson_id: int | None = Form(None),
    module_id: int | None = Form(None),
    course_id: int | None = Form(None),
    title: str = Form(...),
    save_results: bool = Form(False),
    db: Session = Depends(get_db),
):
    teacher = require_teacher(request, db)
    quiz_scope, course = _resolve_quiz_scope(
        db,
        teacher,
        lesson_id=lesson_id,
        module_id=module_id,
        course_id=course_id,
    )

    title = title.strip()
    if not title:
        return _redirect_with_error(f"/courses/{course.id}/manage", "Название квиза обязательно")

    quiz = Quiz(title=title, save_results=save_results, **quiz_scope)
    db.add(quiz)
    db.commit()
    return RedirectResponse(f"/courses/{course.id}/manage", status_code=302)


# ── Страница квиза для студента ─────────────────────────────────
@router.get("/{quiz_id}", response_class=HTMLResponse)
def quiz_page(quiz_id: int, request: Request, db: Session = Depends(get_db)):
    quiz = _load_quiz(db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Квиз не найден")

    user = get_user(request, db)
    back_url, back_i18n = quiz_back_target(quiz)

    if is_student(user) and not quiz_is_unlocked(db, user.id, quiz):
        return RedirectResponse(back_url, status_code=302)

    passed_before = False
    if is_student(user):
        passed_before = (
            db.query(QuizAttempt.id)
            .filter(QuizAttempt.quiz_id == quiz.id, QuizAttempt.student_id == user.id)
            .first()
            is not None
        )

    return templates.TemplateResponse("quiz/quiz_page.html", {
        "request": request,
        "quiz": quiz,
        "user": user,
        "back_url": back_url,
        "back_i18n": back_i18n,
        "passed_before": passed_before,
        "retry_mode": request.query_params.get("retry") == "1",
    })


# ── Отправить ответы квиза ──────────────────────────────────────
@router.post("/{quiz_id}/submit")
async def submit_quiz(quiz_id: int, request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse("/login", status_code=302)

    user = get_user(request, db)
    if not is_student(user):
        raise HTTPException(status_code=403)

    quiz = _load_quiz(db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404)
    if not quiz_is_unlocked(db, user.id, quiz):
        back_url, _ = quiz_back_target(quiz)
        return RedirectResponse(back_url, status_code=302)

    form = await request.form()
    total = len(quiz.questions)
    correct = 0

    for question in quiz.questions:
        if question.question_type == "open":
            student_answer = normalize_open_answer(form.get(f"q_{question.id}", ""))
            if student_answer and student_answer == normalize_open_answer(question.correct_text):
                correct += 1
            continue

        selected_ids = form.getlist(f"q_{question.id}")
        correct_ids = [str(answer.id) for answer in question.answers if answer.is_correct]
        if sorted(selected_ids) == sorted(correct_ids):
            correct += 1

    percentage = int(correct / total * 100) if total > 0 else 0
    passed = percentage > QUIZ_PASS_PERCENTAGE
    now = datetime.utcnow()
    existing_checkpoint = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.quiz_id == quiz.id, QuizAttempt.student_id == user.id)
        .first()
    )

    if passed:
        pass_checkpoint = existing_checkpoint
        if not pass_checkpoint:
            pass_checkpoint = QuizAttempt(
                quiz_id=quiz.id,
                student_id=user.id,
            )
            db.add(pass_checkpoint)
        pass_checkpoint.correct = correct
        pass_checkpoint.total = total
        pass_checkpoint.score = percentage
        pass_checkpoint.completed_at = now

    if quiz.save_results:
        db.add(QuizResult(
            quiz_id=quiz.id,
            student_id=user.id,
            score=correct,
            total=total,
            percentage=percentage,
            passed=passed,
            created_at=now,
        ))

    db.commit()

    back_url, back_i18n = quiz_back_target(quiz)
    return templates.TemplateResponse("quiz/quiz_page.html", {
        "request": request,
        "quiz": quiz,
        "user": user,
        "back_url": back_url,
        "back_i18n": back_i18n,
        "result": _quiz_result_payload(correct=correct, total=total, percentage=percentage, passed=passed),
        "next_url": next_after_quiz(db, user.id, quiz.id) if passed else None,
        "retry_url": f"/quiz/{quiz.id}?retry=1",
        "passed_before": bool(existing_checkpoint or passed),
        "retry_mode": False,
    })


@router.post("/{quiz_id}/settings")
def update_quiz_settings(
    quiz_id: int,
    request: Request,
    title: str = Form(...),
    save_results: bool = Form(False),
    db: Session = Depends(get_db),
):
    teacher = require_teacher(request, db)
    quiz = (
        db.query(Quiz)
        .options(
            joinedload(Quiz.lesson).joinedload(Lesson.module),
            joinedload(Quiz.module),
            joinedload(Quiz.course),
        )
        .filter(Quiz.id == quiz_id)
        .first()
    )
    if not quiz:
        raise HTTPException(status_code=404)

    owner_course_id = quiz_owner_course_id(quiz)
    course = db.query(Course).filter(Course.id == owner_course_id, Course.teacher_id == teacher.id).first()
    if not course:
        raise HTTPException(status_code=403)

    title = title.strip()
    if not title:
        return _redirect_with_error(_quiz_edit_page_url(quiz), "Название квиза обязательно", _quiz_editor_target(quiz))

    quiz.title = title
    quiz.save_results = save_results
    db.commit()
    return RedirectResponse(f"/courses/{course.id}/manage", status_code=302)


# ── Добавить вопрос и ответы ────────────────────────────────────
@router.post("/{quiz_id}/question")
async def add_question(
    quiz_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    teacher = require_teacher(request, db)
    quiz = (
        db.query(Quiz)
        .options(
            joinedload(Quiz.lesson).joinedload(Lesson.module),
            joinedload(Quiz.module),
            joinedload(Quiz.course),
        )
        .filter(Quiz.id == quiz_id)
        .first()
    )
    if not quiz:
        raise HTTPException(status_code=404)

    owner_course_id = quiz_owner_course_id(quiz)
    course = db.query(Course).filter(Course.id == owner_course_id, Course.teacher_id == teacher.id).first()
    if not course:
        raise HTTPException(status_code=403)

    form = await request.form()
    q_text = form.get("question_text", "").strip()
    q_type = form.get("question_type", "single")
    correct_text = form.get("correct_text", "").strip()
    quiz_edit_url = _quiz_edit_page_url(quiz)
    quiz_edit_target = _quiz_editor_target(quiz)

    if not q_text:
        return _redirect_with_error(quiz_edit_url, "Текст вопроса обязателен", quiz_edit_target)
    if q_type not in {"single", "multiple", "open"}:
        return _redirect_with_error(quiz_edit_url, "Недопустимый тип вопроса", quiz_edit_target)

    answers: list[tuple[str, bool]] = []
    i = 1
    while f"answer_{i}" in form:
        a_text = form.get(f"answer_{i}", "").strip()
        is_correct = form.get(f"correct_{i}") == "on"
        if a_text:
            answers.append((a_text, is_correct))
        i += 1

    try:
        _validate_question_payload(q_type, answers, correct_text)
    except HTTPException as exc:
        return _redirect_with_error(quiz_edit_url, str(exc.detail), quiz_edit_target)

    question = Question(
        quiz_id=quiz_id,
        question_text=q_text,
        question_type=q_type,
        correct_text=correct_text or None,
    )
    db.add(question)
    db.flush()

    for a_text, is_correct in answers:
        db.add(Answer(question_id=question.id, answer_text=a_text, is_correct=is_correct))

    db.commit()
    return RedirectResponse(f"/courses/{course.id}/manage", status_code=302)


# ── Результаты тестов преподавателя ─────────────────────────────
@dashboard_router.get("/dashboard/teacher/quiz-results", response_class=HTMLResponse)
def teacher_quiz_results(request: Request, db: Session = Depends(get_db)):
    teacher = require_teacher(request, db)
    quizzes = _teacher_owned_quizzes(db, teacher.id)

    quiz_cards = []
    for quiz in quizzes:
        latest_results = _latest_results(list(quiz.results))
        average_percentage = int(round(sum(result.percentage for result in latest_results) / len(latest_results))) if latest_results else 0
        quiz_cards.append({
            "quiz": quiz,
            "binding_label": quiz_binding_label(quiz),
            "students_count": len(latest_results),
            "average_percentage": average_percentage,
        })

    quiz_cards.sort(key=lambda item: item["quiz"].title.lower())

    return templates.TemplateResponse("quiz/teacher_quiz_results.html", {
        "request": request,
        "user": teacher,
        "quiz_cards": quiz_cards,
        "active_page": "quiz_results",
    })


@dashboard_router.get("/dashboard/teacher/quiz-results/{quiz_id}", response_class=HTMLResponse)
def teacher_quiz_results_detail(quiz_id: int, request: Request, db: Session = Depends(get_db)):
    teacher = require_teacher(request, db)
    quiz = (
        db.query(Quiz)
        .options(
            joinedload(Quiz.lesson).joinedload(Lesson.module),
            joinedload(Quiz.module),
            joinedload(Quiz.course),
            selectinload(Quiz.results).joinedload(QuizResult.student),
        )
        .filter(Quiz.id == quiz_id, Quiz.save_results == True)  # noqa: E712
        .first()
    )
    if not quiz:
        raise HTTPException(status_code=404)

    owner_course_id = quiz_owner_course_id(quiz)
    course = db.query(Course).filter(Course.id == owner_course_id, Course.teacher_id == teacher.id).first()
    if not course:
        raise HTTPException(status_code=403)

    latest_results = _latest_results(list(quiz.results))

    return templates.TemplateResponse("quiz/teacher_quiz_results_detail.html", {
        "request": request,
        "user": teacher,
        "quiz": quiz,
        "binding_label": quiz_binding_label(quiz),
        "results": latest_results,
        "active_page": "quiz_results",
    })
