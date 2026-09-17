from flask import Blueprint, render_template, request, redirect, url_for, flash

from auth import login_required
from uploads import save_local_attachment, upload_video
from database import (
    list_all_lessons,
    get_lesson,
    create_lesson,
    update_lesson,
    delete_lesson,
    get_assignments_by_lesson,
    create_assignment,
    update_assignment,
    delete_assignment,
    get_assignment,
    get_assignment_options,
    list_students,
    get_student_lessons_with_status,
    get_submissions_for_student,
    get_submissions_for_assignment,
    grade_submission,
    get_teacher_overview_stats,
    get_pending_submissions,
)

MAX_QUIZ_OPTIONS = 4


def _parse_assignment_form(form):
    """Читає форму завдання і повертає (type, options, correct_option) або None при помилці валідації."""

    type_ = form.get("type", "text")

    if type_ != "quiz":
        return "text", None, None

    raw_options = [form.get(f"option_{i}", "").strip() for i in range(MAX_QUIZ_OPTIONS)]
    options = [o for o in raw_options if o]

    correct_raw = form.get("correct_option")
    correct_index = None

    if correct_raw not in (None, "") and correct_raw.isdigit():
        raw_idx = int(correct_raw)

        if 0 <= raw_idx < len(raw_options) and raw_options[raw_idx]:
            correct_index = options.index(raw_options[raw_idx])

    if len(options) < 2 or correct_index is None:
        return None

    return "quiz", options, correct_index


def _resolve_lesson_media(form, files):
    """Обробляє поля відео/вкладення уроку: завантажений файл має пріоритет над посиланням."""

    video_url = form.get("video_url", "").strip() or None
    attachment_url = form.get("attachment_url", "").strip() or None

    video_file = files.get("video_file")

    if video_file and video_file.filename:
        uploaded_url, error = upload_video(video_file)

        if error:
            return None, None, error

        video_url = uploaded_url

    attachment_file = files.get("attachment_file")

    if attachment_file and attachment_file.filename:
        uploaded_url, error = save_local_attachment(attachment_file)

        if error:
            return None, None, error

        attachment_url = uploaded_url

    return video_url, attachment_url, None


teacher_bp = Blueprint("teacher", __name__, url_prefix="/teacher")

COURSES = ["starter", "plus", "premium"]


@teacher_bp.route("/")
@login_required(role="teacher")
def dashboard(account):
    lessons = list_all_lessons()

    lessons_by_course = {course: [] for course in COURSES}

    for lesson in lessons:
        lessons_by_course.setdefault(lesson["course"], []).append(lesson)

    students = list_students()
    stats = get_teacher_overview_stats()

    return render_template(
        "teacher/dashboard.html",
        account=account,
        lessons_by_course=lessons_by_course,
        courses=COURSES,
        students_count=len(students),
        stats=stats,
    )


@teacher_bp.route("/submissions/pending")
@login_required(role="teacher")
def pending_submissions(account):
    submissions = get_pending_submissions()

    return render_template(
        "teacher/pending_submissions.html",
        account=account,
        submissions=submissions,
    )


@teacher_bp.route("/lessons/new", methods=["GET", "POST"])
@login_required(role="teacher")
def new_lesson(account):
    if request.method == "POST":
        course = request.form.get("course")
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "")
        scheduled_at = request.form.get("scheduled_at", "").strip() or None
        order_index = int(request.form.get("order_index") or 0)

        if not title or course not in COURSES:
            flash("Заповніть назву та оберіть курс", "error")
            return render_template("teacher/lesson_form.html", account=account, courses=COURSES, lesson=None)

        video_url, attachment_url, media_error = _resolve_lesson_media(request.form, request.files)

        if media_error:
            flash(media_error, "error")
            return render_template("teacher/lesson_form.html", account=account, courses=COURSES, lesson=None)

        lesson_id = create_lesson(course, title, content, video_url, attachment_url, scheduled_at, order_index)

        flash("Урок створено", "success")
        return redirect(url_for("teacher.edit_lesson", lesson_id=lesson_id))

    return render_template("teacher/lesson_form.html", account=account, courses=COURSES, lesson=None)


@teacher_bp.route("/lessons/<int:lesson_id>/edit", methods=["GET", "POST"])
@login_required(role="teacher")
def edit_lesson(account, lesson_id):
    lesson = get_lesson(lesson_id)

    if lesson is None:
        flash("Урок не знайдено", "error")
        return redirect(url_for("teacher.dashboard"))

    if request.method == "POST":
        course = request.form.get("course")
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "")
        scheduled_at = request.form.get("scheduled_at", "").strip() or None
        order_index = int(request.form.get("order_index") or 0)
        is_published = request.form.get("is_published") == "on"

        if not title or course not in COURSES:
            flash("Заповніть назву та оберіть курс", "error")
            return redirect(url_for("teacher.edit_lesson", lesson_id=lesson_id))

        video_url, attachment_url, media_error = _resolve_lesson_media(request.form, request.files)

        if media_error:
            flash(media_error, "error")
            return redirect(url_for("teacher.edit_lesson", lesson_id=lesson_id))

        update_lesson(lesson_id, course, title, content, video_url, attachment_url, scheduled_at, order_index, is_published)

        flash("Зміни збережено", "success")
        return redirect(url_for("teacher.edit_lesson", lesson_id=lesson_id))

    assignments = get_assignments_by_lesson(lesson_id)
    assignment_options = {
        a["id"]: (get_assignment_options(a) + [""] * MAX_QUIZ_OPTIONS)[:MAX_QUIZ_OPTIONS]
        for a in assignments
    }

    return render_template(
        "teacher/lesson_form.html",
        account=account,
        courses=COURSES,
        lesson=lesson,
        assignments=assignments,
        assignment_options=assignment_options,
    )


@teacher_bp.route("/lessons/<int:lesson_id>/delete", methods=["POST"])
@login_required(role="teacher")
def remove_lesson(account, lesson_id):
    delete_lesson(lesson_id)
    flash("Урок видалено", "success")
    return redirect(url_for("teacher.dashboard"))


@teacher_bp.route("/lessons/<int:lesson_id>/assignments/new", methods=["POST"])
@login_required(role="teacher")
def new_assignment(account, lesson_id):
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "")
    order_index = int(request.form.get("order_index") or 0)

    if not title:
        flash("Вкажіть назву завдання", "error")
        return redirect(url_for("teacher.edit_lesson", lesson_id=lesson_id))

    parsed = _parse_assignment_form(request.form)

    if parsed is None:
        flash("Для тесту потрібно щонайменше 2 варіанти відповіді та позначена правильна", "error")
        return redirect(url_for("teacher.edit_lesson", lesson_id=lesson_id))

    type_, options, correct_option = parsed

    create_assignment(lesson_id, title, description, order_index, type_, options, correct_option)
    flash("Завдання додано", "success")

    return redirect(url_for("teacher.edit_lesson", lesson_id=lesson_id))


@teacher_bp.route("/assignments/<int:assignment_id>/edit", methods=["POST"])
@login_required(role="teacher")
def edit_assignment(account, assignment_id):
    assignment = get_assignment(assignment_id)

    if assignment is None:
        flash("Завдання не знайдено", "error")
        return redirect(url_for("teacher.dashboard"))

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "")
    order_index = int(request.form.get("order_index") or 0)

    if not title:
        flash("Вкажіть назву завдання", "error")
        return redirect(url_for("teacher.edit_lesson", lesson_id=assignment["lesson_id"]))

    parsed = _parse_assignment_form(request.form)

    if parsed is None:
        flash("Для тесту потрібно щонайменше 2 варіанти відповіді та позначена правильна", "error")
        return redirect(url_for("teacher.edit_lesson", lesson_id=assignment["lesson_id"]))

    type_, options, correct_option = parsed

    update_assignment(assignment_id, title, description, order_index, type_, options, correct_option)
    flash("Завдання оновлено", "success")

    return redirect(url_for("teacher.edit_lesson", lesson_id=assignment["lesson_id"]))


@teacher_bp.route("/assignments/<int:assignment_id>/delete", methods=["POST"])
@login_required(role="teacher")
def remove_assignment(account, assignment_id):
    assignment = get_assignment(assignment_id)

    if assignment is None:
        flash("Завдання не знайдено", "error")
        return redirect(url_for("teacher.dashboard"))

    lesson_id = assignment["lesson_id"]
    delete_assignment(assignment_id)

    flash("Завдання видалено", "success")
    return redirect(url_for("teacher.edit_lesson", lesson_id=lesson_id))


@teacher_bp.route("/students")
@login_required(role="teacher")
def students(account):
    all_students = list_students()

    return render_template("teacher/students.html", account=account, students=all_students)


@teacher_bp.route("/students/<int:student_id>")
@login_required(role="teacher")
def student_detail(account, student_id):
    students_list = list_students()
    student = next((s for s in students_list if s["id"] == student_id), None)

    if student is None:
        flash("Учня не знайдено", "error")
        return redirect(url_for("teacher.students"))

    lessons_with_status = []

    if student["course"]:
        lessons_with_status = get_student_lessons_with_status(student_id, student["course"])

    for entry in lessons_with_status:
        entry["assignments"] = get_assignments_by_lesson(entry["lesson"]["id"])
        entry["submissions"] = get_submissions_for_student(student_id, entry["lesson"]["id"])

    return render_template(
        "teacher/student_detail.html",
        account=account,
        student=student,
        lessons_with_status=lessons_with_status,
    )


@teacher_bp.route("/assignments/<int:assignment_id>/submissions")
@login_required(role="teacher")
def assignment_submissions(account, assignment_id):
    assignment = get_assignment(assignment_id)

    if assignment is None:
        flash("Завдання не знайдено", "error")
        return redirect(url_for("teacher.dashboard"))

    submissions = get_submissions_for_assignment(assignment_id)

    return render_template(
        "teacher/submissions.html",
        account=account,
        assignment=assignment,
        submissions=submissions,
    )


@teacher_bp.route("/submissions/<int:submission_id>/grade", methods=["POST"])
@login_required(role="teacher")
def grade(account, submission_id):
    score = request.form.get("score", "").strip()
    feedback = request.form.get("feedback", "")
    redirect_to = request.form.get("redirect_to") or url_for("teacher.dashboard")

    grade_submission(submission_id, int(score) if score else None, feedback)

    flash("Оцінку збережено", "success")
    return redirect(redirect_to)
