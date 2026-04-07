# Роутер квизов
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.user import User
from app.models.lesson import Lesson
from app.models.quiz import Quiz, Question, Answer
from app.models.module import Module

router = APIRouter(prefix="/quiz")
templates = Jinja2Templates(directory="templates")


def get_user(request, db):
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.query(User).filter(User.id == uid).first()


def require_teacher(request, db):
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(status_code=401)
    user = db.query(User).filter(User.id == uid).first()
    if not user or user.role.value not in ("teacher", "admin"):
        raise HTTPException(status_code=403)
    return user


# ── Страница квиза для студента ─────────────────────────────────
@router.get("/{quiz_id}", response_class=HTMLResponse)
def quiz_page(quiz_id: int, request: Request, db: Session = Depends(get_db)):
    quiz = (
        db.query(Quiz)
        .options(joinedload(Quiz.questions).joinedload(Question.answers))
        .filter(Quiz.id == quiz_id)
        .first()
    )
    if not quiz:
        raise HTTPException(status_code=404, detail="Квиз не найден")
    user = get_user(request, db)
    return templates.TemplateResponse("quiz_page.html", {
        "request": request, "quiz": quiz, "user": user
    })


# ── Отправить ответы квиза ──────────────────────────────────────
@router.post("/{quiz_id}/submit")
async def submit_quiz(quiz_id: int, request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse("/login", status_code=302)

    quiz = (
        db.query(Quiz)
        .options(joinedload(Quiz.questions).joinedload(Question.answers))
        .filter(Quiz.id == quiz_id)
        .first()
    )
    if not quiz:
        raise HTTPException(status_code=404)

    form = await request.form()
    total = len(quiz.questions)
    correct = 0

    for question in quiz.questions:
        selected_ids = form.getlist(f"q_{question.id}")
        correct_ids = [str(a.id) for a in question.answers if a.is_correct]
        if sorted(selected_ids) == sorted(correct_ids):
            correct += 1

    score = int(correct / total * 100) if total > 0 else 0
    return templates.TemplateResponse("quiz_page.html", {
        "request": request,
        "quiz": quiz,
        "user": get_user(request, db),
        "result": {"correct": correct, "total": total, "score": score},
    })


# ── Создать квиз (teacher) ──────────────────────────────────────
@router.post("/create")
def create_quiz(
    request: Request,
    lesson_id: int = Form(...),
    title: str = Form(...),
    db: Session = Depends(get_db),
):
    teacher = require_teacher(request, db)
    lesson = db.query(Lesson).options(joinedload(Lesson.module)).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404)
    from app.models.course import Course
    course = db.query(Course).filter(Course.id == lesson.module.course_id, Course.teacher_id == teacher.id).first()
    if not course:
        raise HTTPException(status_code=403)

    quiz = Quiz(lesson_id=lesson_id, title=title)
    db.add(quiz)
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
    quiz = db.query(Quiz).options(joinedload(Quiz.lesson).joinedload(Lesson.module)).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404)
    from app.models.course import Course
    course = db.query(Course).filter(
        Course.id == quiz.lesson.module.course_id, Course.teacher_id == teacher.id
    ).first()
    if not course:
        raise HTTPException(status_code=403)

    form = await request.form()
    q_text = form.get("question_text", "").strip()
    q_type = form.get("question_type", "single")

    if not q_text:
        raise HTTPException(status_code=400, detail="Текст вопроса обязателен")

    question = Question(quiz_id=quiz_id, question_text=q_text, question_type=q_type)
    db.add(question)
    db.flush()  # получаем id

    # Ответы: answer_1, answer_2, ... correct_1, correct_2, ...
    i = 1
    while f"answer_{i}" in form:
        a_text = form.get(f"answer_{i}", "").strip()
        is_correct = form.get(f"correct_{i}") == "on"
        if a_text:
            db.add(Answer(question_id=question.id, answer_text=a_text, is_correct=is_correct))
        i += 1

    db.commit()
    return RedirectResponse(f"/courses/{course.id}/manage", status_code=302)
